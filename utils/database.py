import aiosqlite
import asyncio
import logging
from typing import Any, Optional
from contextlib import asynccontextmanager
from config import WAL_MODE, MARKET_REFRESH_MINUTES
import time

logger = logging.getLogger(__name__)


class Database:
    """Async SQLite database wrapper with connection pooling and WAL mode."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Establish database connection and initialize schema."""
        async with self._lock:
            if self._connection is None:
                self._connection = await aiosqlite.connect(self.db_path)
                self._connection.row_factory = aiosqlite.Row
                await self._initialize_db()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _ensure_table_columns(self) -> None:
        """Ensure all required table columns exist (for backward compatibility)."""
        assert self._connection is not None

        # Check and add bank column to users table if missing
        try:
            await self._connection.execute("ALTER TABLE users ADD COLUMN bank INTEGER DEFAULT 0")
            logger.info("Added bank column to users table")
        except aiosqlite.OperationalError as e:
            if "duplicate column name" not in str(e):
                logger.error(f"Error adding bank column: {e}")

        # Check and add gems column to users table if missing
        try:
            await self._connection.execute("ALTER TABLE users ADD COLUMN gems INTEGER DEFAULT 0")
            logger.info("Added gems column to users table")
        except aiosqlite.OperationalError as e:
            if "duplicate column name" not in str(e):
                logger.error(f"Error adding gems column: {e}")

        # Check and add daily_streak column to users table if missing
        try:
            await self._connection.execute("ALTER TABLE users ADD COLUMN daily_streak INTEGER DEFAULT 0")
            logger.info("Added daily_streak column to users table")
        except aiosqlite.OperationalError as e:
            if "duplicate column name" not in str(e):
                logger.error(f"Error adding daily_streak column: {e}")

        # Check and add last_daily column to users table if missing
        try:
            await self._connection.execute("ALTER TABLE users ADD COLUMN last_daily INTEGER DEFAULT 0")
            logger.info("Added last_daily column to users table")
        except aiosqlite.OperationalError as e:
            if "duplicate column name" not in str(e):
                logger.error(f"Error adding last_daily column: {e}")
            # Column already exists, which is fine

        # Add antinuke columns if missing (for existing databases)
        antinuke_config_cols = [
            ("threshold_channel_create", "INTEGER DEFAULT 5"),
            ("threshold_role_create", "INTEGER DEFAULT 5"),
        ]
        for col_name, col_type in antinuke_config_cols:
            try:
                await self._connection.execute(f"ALTER TABLE antinuke_config ADD COLUMN {col_name} {col_type}")
            except aiosqlite.OperationalError:
                pass  # Column already exists

        antinuke_modules_cols = [
            ("detect_channel_create", "INTEGER DEFAULT 1"),
            ("detect_role_create", "INTEGER DEFAULT 1"),
            ("channel_create_punishment", "TEXT DEFAULT 'ban'"),
            ("role_create_punishment", "TEXT DEFAULT 'ban'"),
        ]
        for col_name, col_type in antinuke_modules_cols:
            try:
                await self._connection.execute(f"ALTER TABLE antinuke_modules ADD COLUMN {col_name} {col_type}")
            except aiosqlite.OperationalError:
                pass  # Column already exists
            
    async def _initialize_db(self) -> None:
        """Initialize database schema and WAL mode."""
        assert self._connection is not None

        # Load main schema
        with open("data/schema.sql", "r") as f:
            schema = f.read()
        await self._connection.executescript(schema)
        
        # Load treasure chest schema
        try:
            with open("data/treasure_schema.sql", "r") as f:
                treasure_schema = f.read()
            await self._connection.executescript(treasure_schema)
        except FileNotFoundError:
            logger.warning("treasure_schema.sql not found, skipping treasure tables")
        
        # Enable WAL mode for better concurrency
        if WAL_MODE:
            await self._connection.execute("PRAGMA journal_mode=WAL")

        # Ensure all required columns exist (for backward compatibility)
        await self._ensure_table_columns()

        await self._connection.commit()
        logger.info("Database initialized with WAL mode enabled")

    @asynccontextmanager
    async def acquire(self) -> aiosqlite.Connection:
        """Acquire a database connection with async context manager."""
        async with self._lock:
            if self._connection is None:
                await self.connect()
            yield self._connection

    async def fetch_one(
        self, query: str, *args: Any
    ) -> Optional[aiosqlite.Row]:
        """Fetch single row."""
        async with self.acquire() as conn:
            async with conn.execute(query, args) as cursor:
                return await cursor.fetchone()

    async def fetch_all(
        self, query: str, *args: Any
    ) -> list[aiosqlite.Row]:
        """Fetch all rows."""
        async with self.acquire() as conn:
            async with conn.execute(query, args) as cursor:
                return await cursor.fetchall()

    async def execute(self, query: str, *args: Any) -> aiosqlite.Cursor:
        """Execute a query and return cursor."""
        async with self.acquire() as conn:
            cursor = await conn.execute(query, args)
            await conn.commit()
            return cursor

    async def executemany(
        self, query: str, args_seq: list[tuple]
    ) -> aiosqlite.Cursor:
        """Execute many queries."""
        async with self.acquire() as conn:
            cursor = await conn.executemany(query, args_seq)
            await conn.commit()
            return cursor


# Global database instance
db = Database("database.db")


async def get_user(user_id: int) -> Optional[aiosqlite.Row]:
    """Get user row by ID."""
    return await db.fetch_one(
        "SELECT * FROM users WHERE user_id = ?", user_id
    )


async def create_user(user_id: int) -> None:
    """Create new user with default values (idempotent)."""
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id, credits, bank, gems) VALUES (?, 0, 0, 0)",
        user_id
    )
    await db.execute(
        "INSERT OR IGNORE INTO inventory (user_id, fish) VALUES (?, 0)",
        user_id
    )
    await db.execute(
        "INSERT OR IGNORE INTO upgrades (user_id, stronger_rod, new_rod) VALUES (?, 0, 0)",
        user_id
    )
    await db.execute(
        "INSERT OR IGNORE INTO buffs (user_id, frenzy_until) VALUES (?, 0)",
        user_id
    )
    await db.execute(
        "INSERT OR IGNORE INTO steal_cooldowns (user_id, last_stolen) VALUES (?, 0)",
        user_id
    )


async def update_credits(user_id: int, amount: int) -> None:
    """Update user credits by adding amount (can be negative)."""
    await db.execute(
        "UPDATE users SET credits = credits + ? WHERE user_id = ?",
        amount, user_id
    )


async def update_gems(user_id: int, amount: int) -> None:
    """Update user gems by adding amount (can be negative)."""
    await db.execute(
        "UPDATE users SET gems = gems + ? WHERE user_id = ?",
        amount, user_id
    )

async def set_daily_claim(user_id: int, timestamp: int, reward: int) -> None:
    """
    Atomically increment daily streak and update last_daily timestamp,
    then add reward credits.
    """
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE users SET daily_streak = daily_streak + 1, last_daily = ? WHERE user_id = ?",
            (timestamp, user_id)
        )
        await conn.execute(
            "UPDATE users SET credits = credits + ? WHERE user_id = ?",
            (reward, user_id)
        )
        await conn.commit()

        return cursor.rowcount > 0


async def safe_deduct_gems(user_id: int, amount: int) -> bool:
    """
    Atomically deduct gems if sufficient funds.
    Returns True if successful, False if insufficient gems.
    """
    async with db.acquire() as conn:
        cursor = await conn.execute(
            "UPDATE users SET gems = gems - ? WHERE user_id = ? AND gems >= ?",
            (amount, user_id, amount)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def safe_deduct_credits(user_id: int, amount: int) -> bool:
    """
    Atomically deduct credits if sufficient funds.
    Returns True if successful, False if insufficient credits.
    """
    async with db.acquire() as conn:
        cursor = await conn.execute(
            "UPDATE users SET credits = credits - ? WHERE user_id = ? AND credits >= ?",
            (amount, user_id, amount)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def update_fish(user_id: int, amount: int) -> None:
    """Update user fish count by adding amount (can be negative)."""
    await db.execute(
        "UPDATE inventory SET fish = fish + ? WHERE user_id = ?",
        amount, user_id
    )


async def safe_update_fish(user_id: int, amount: int) -> bool:
    """
    Atomically update fish count. For negative amounts, ensures non-negative result.
    Returns True if successful, False if insufficient fish for subtraction.
    """
    async with db.acquire() as conn:
        if amount >= 0:
            cursor = await conn.execute(
                "UPDATE inventory SET fish = fish + ? WHERE user_id = ?",
                (amount, user_id)
            )
        else:
            subtract = -amount
            cursor = await conn.execute(
                "UPDATE inventory SET fish = fish - ? WHERE user_id = ? AND fish >= ?",
                (subtract, user_id, subtract)
            )
        await conn.commit()
        return cursor.rowcount > 0


async def get_inventory(user_id: int) -> Optional[aiosqlite.Row]:
    """Get user inventory."""
    return await db.fetch_one(
        "SELECT * FROM inventory WHERE user_id = ?", user_id
    )


async def get_upgrades(user_id: int) -> Optional[aiosqlite.Row]:
    """Get user upgrades."""
    return await db.fetch_one(
        "SELECT * FROM upgrades WHERE user_id = ?", user_id
    )


async def update_upgrade(
    user_id: int, upgrade: str, level: int
) -> None:
    """Set upgrade level."""
    await db.execute(
        f"UPDATE upgrades SET {upgrade} = ? WHERE user_id = ?",
        level, user_id
    )


async def get_buffs(user_id: int) -> Optional[aiosqlite.Row]:
    """Get user buffs."""
    return await db.fetch_one(
        "SELECT * FROM buffs WHERE user_id = ?", user_id
    )


async def set_frenzy_until(user_id: int, timestamp: int) -> None:
    """Set frenzy end timestamp (adds duration if already active)."""
    current = await db.fetch_one(
        "SELECT frenzy_until FROM buffs WHERE user_id = ?", user_id
    )
    if current and current["frenzy_until"] > 0:
        # Extend existing frenzy
        timestamp = max(timestamp, current["frenzy_until"])
    await db.execute(
        "UPDATE buffs SET frenzy_until = ? WHERE user_id = ?",
        timestamp, user_id
    )


async def get_market_price() -> int:
    """Get current market price."""
    row = await db.fetch_one("SELECT fish_price FROM market WHERE id = 1")
    return row["fish_price"] if row else 5


async def set_market_price(price: int, timestamp: int) -> None:
    """Update market price."""
    await db.execute(
        "INSERT OR REPLACE INTO market (id, fish_price, updated_at) VALUES (1, ?, ?)",
        price, timestamp
    )


async def get_next_market_refresh() -> int:
    """Get timestamp when market will next refresh."""
    row = await db.fetch_one("SELECT updated_at FROM market WHERE id = 1")
    interval = MARKET_REFRESH_MINUTES * 60
    if row and row["updated_at"]:
        return row["updated_at"] + interval
    # No record yet, first refresh in interval seconds from now
    return int(time.time() + interval)


async def get_leaderboard(limit: int = 10) -> list[aiosqlite.Row]:
    """Get top users by credits."""
    return await db.fetch_all(
        "SELECT user_id, credits FROM users ORDER BY credits DESC LIMIT ?",
        limit
    )


# Job-related database functions

async def create_job_entry(user_id: int) -> None:
    """Create job entry for user if not exists."""
    await db.execute(
        "INSERT OR IGNORE INTO jobs (user_id, current_job, work_last_used) VALUES (?, NULL, 0)",
        user_id
    )


async def get_job(user_id: int) -> Optional[aiosqlite.Row]:
    """Get user's current job data."""
    return await db.fetch_one(
        "SELECT * FROM jobs WHERE user_id = ?", user_id
    )


async def set_user_job(user_id: int, job_name: str) -> None:
    """Set user's current job."""
    await db.execute(
        "INSERT OR REPLACE INTO jobs (user_id, current_job, work_last_used) VALUES (?, ?, COALESCE((SELECT work_last_used FROM jobs WHERE user_id = ?), 0))",
        user_id, job_name, user_id
    )


async def update_work_timestamp(user_id: int, timestamp: int) -> None:
    """Update last work timestamp for user."""
    await db.execute(
        "UPDATE jobs SET work_last_used = ? WHERE user_id = ?",
        timestamp, user_id
    )


async def get_previous_market_price() -> Optional[int]:
    """Get the previous market price for trend comparison."""
    row = await db.fetch_one(
        "SELECT fish_price FROM market WHERE id = 1"
    )
    return row["fish_price"] if row else None


# Bank-related database functions

async def deposit_credits(user_id: int, amount: int) -> bool:
    """Atomically move credits from wallet to bank. Returns True if successful."""
    async with db.acquire() as conn:
        # First check if user has enough credits
        cursor = await conn.execute(
            "UPDATE users SET credits = credits - ?, bank = bank + ? WHERE user_id = ? AND credits >= ?",
            (amount, amount, user_id, amount)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def withdraw_credits(user_id: int, amount: int) -> bool:
    """Atomically move credits from bank to wallet. Returns True if successful."""
    async with db.acquire() as conn:
        cursor = await conn.execute(
            "UPDATE users SET bank = bank - ?, credits = credits + ? WHERE user_id = ? AND bank >= ?",
            (amount, amount, user_id, amount)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def get_steal_cooldown(user_id: int) -> int:
    """Get last steal timestamp for user."""
    row = await db.fetch_one(
        "SELECT last_stolen FROM steal_cooldowns WHERE user_id = ?", user_id
    )
    return row["last_stolen"] if row else 0


async def set_steal_cooldown(user_id: int, timestamp: int) -> None:
    """Set last steal timestamp for user."""
    await db.execute(
        "INSERT OR REPLACE INTO steal_cooldowns (user_id, last_stolen) VALUES (?, ?)",
        user_id, timestamp
    )


# Daily tracking database functions

async def get_daily_data(user_id: int) -> Optional[aiosqlite.Row]:
    """Get user's daily tracking data (streak and last_claim)."""
    return await db.fetch_one(
        "SELECT daily_streak, last_daily FROM users WHERE user_id = ?",
        user_id
    )


async def set_daily_claim(user_id: int, timestamp: int, reward: int) -> None:
    """
    Atomically increment daily streak, update last_daily timestamp,
    and add reward credits in one query.
    """
    async with db.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET daily_streak = daily_streak + 1,
                last_daily = ?,
                credits = credits + ?
            WHERE user_id = ?
            """,
            (timestamp, reward, user_id)
        )
        await conn.commit()



async def reset_daily_streak(user_id: int, timestamp: int) -> None:
    """Reset user's daily streak to 0 and set last_claim timestamp."""
    await db.execute(
        "UPDATE users SET daily_streak = 0, last_daily = ? WHERE user_id = ?",
        timestamp, user_id
    )


# Gift transfer database function

async def safe_transfer_credits(sender_id: int, receiver_id: int, amount: int) -> tuple[bool, int]:
    """
    Atomically transfer credits from sender to receiver with 2% fee.
    Returns (success, fee_amount).
    Deducts (amount + fee) from sender, adds (amount) to receiver.
    """
    import math
    fee = math.ceil(amount * 0.02)
    total_deduction = amount + fee

    async with db.acquire() as conn:
        # Check sender has enough credits
        cursor = await conn.execute(
            "SELECT credits FROM users WHERE user_id = ? AND credits >= ?",
            (sender_id, total_deduction)
        )
        sender = await cursor.fetchone()
        if not sender:
            return False, 0

        # Perform atomic transfer
        await conn.execute(
            "UPDATE users SET credits = credits - ? WHERE user_id = ?",
            (total_deduction, sender_id)
        )
        await conn.execute(
            "UPDATE users SET credits = credits + ? WHERE user_id = ?",
            (amount, receiver_id)
        )
        await conn.commit()
        return True, fee


# Beg cooldown database functions

async def get_beg_cooldown(user_id: int) -> int:
    """Get last beg timestamp for user."""
    row = await db.fetch_one(
        "SELECT last_beg FROM beg_cooldowns WHERE user_id = ?", user_id
    )
    return row["last_beg"] if row else 0


async def set_beg_cooldown(user_id: int, timestamp: int) -> None:
    """Set last beg timestamp for user."""
    await db.execute(
        "INSERT OR REPLACE INTO beg_cooldowns (user_id, last_beg) VALUES (?, ?)",
        user_id, timestamp
    )


# Treasure chest database functions

async def create_treasure_chest(
    channel_id: int,
    message_id: int,
    spawned_at: int,
    credits: int,
    fish: int
) -> int:
    """
    Create a new treasure chest record.
    Returns the chest ID.
    """
    cursor = await db.execute(
        """INSERT INTO treasure_chests 
           (channel_id, message_id, spawned_at, credits_reward, fish_reward, status)
           VALUES (?, ?, ?, ?, ?, 'active')""",
        channel_id, message_id, spawned_at, credits, fish
    )
    return cursor.lastrowid


async def claim_treasure_chest(chest_id: int, user_id: int, claimed_at: int) -> bool:
    """
    Atomically claim a treasure chest.
    Returns True if claim was successful, False if already claimed.
    """
    async with db.acquire() as conn:
        cursor = await conn.execute(
            """UPDATE treasure_chests 
               SET claimed_by = ?, claimed_at = ?, status = 'claimed'
               WHERE id = ? AND status = 'active'""",
            (user_id, claimed_at, chest_id)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def get_treasure_chest(chest_id: int) -> Optional[aiosqlite.Row]:
    """Get treasure chest data by ID."""
    return await db.fetch_one(
        "SELECT * FROM treasure_chests WHERE id = ?",
        chest_id
    )


async def get_active_treasure_by_message(message_id: int) -> Optional[aiosqlite.Row]:
    """Get active treasure chest by message ID."""
    return await db.fetch_one(
        "SELECT * FROM treasure_chests WHERE message_id = ? AND status = 'active'",
        message_id
    )


async def expire_treasure_chest(chest_id: int) -> bool:
    """Mark a treasure chest as expired (timeout)."""
    async with db.acquire() as conn:
        cursor = await conn.execute(
            "UPDATE treasure_chests SET status = 'expired' WHERE id = ? AND status = 'active'",
            (chest_id,)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def get_treasure_stats() -> dict:
    """Get aggregate treasure chest statistics."""
    async with db.acquire() as conn:
        # Total spawned
        cursor = await conn.execute("SELECT COUNT(*) as count FROM treasure_chests")
        total_spawned = (await cursor.fetchone())["count"]
        
        # Total claimed
        cursor = await conn.execute(
            "SELECT COUNT(*) as count FROM treasure_chests WHERE status = 'claimed'"
        )
        total_claimed = (await cursor.fetchone())["count"]
        
        # Total expired
        cursor = await conn.execute(
            "SELECT COUNT(*) as count FROM treasure_chests WHERE status = 'expired'"
        )
        total_expired = (await cursor.fetchone())["count"]
        
        # Total credits awarded
        cursor = await conn.execute(
            "SELECT SUM(credits_reward) as total FROM treasure_chests WHERE status = 'claimed'"
        )
        total_credits = (await cursor.fetchone())["total"] or 0
        
        # Total fish awarded
        cursor = await conn.execute(
            "SELECT SUM(fish_reward) as total FROM treasure_chests WHERE status = 'claimed'"
        )
        total_fish = (await cursor.fetchone())["total"] or 0
        
        return {
            "total_spawned": total_spawned,
            "total_claimed": total_claimed,
            "total_expired": total_expired,
            "total_credits_awarded": total_credits,
            "total_fish_awarded": total_fish
        }


# Cooldown functions

async def get_global_cooldown() -> int:
    """Get timestamp of last global treasure spawn."""
    row = await db.fetch_one(
        "SELECT last_global_spawn FROM treasure_cooldowns WHERE channel_id = 0"
    )
    return row["last_global_spawn"] if row else 0


async def get_channel_cooldown(channel_id: int) -> int:
    """Get timestamp of last spawn in specific channel."""
    row = await db.fetch_one(
        "SELECT last_channel_spawn FROM treasure_cooldowns WHERE channel_id = ?",
        (channel_id,)
    )
    return row["last_channel_spawn"] if row else 0


# Prefix management functions

async def get_prefixes(guild_id: int) -> list[str]:
    """Get all custom prefixes for a guild."""
    rows = await db.fetch_all(
        "SELECT prefix FROM prefixes WHERE guild_id = ?",
        guild_id
    )
    return [row["prefix"] for row in rows]


async def add_prefix(guild_id: int, prefix: str) -> None:
    """Add a custom prefix for a guild."""
    await db.execute(
        "INSERT OR IGNORE INTO prefixes (guild_id, prefix) VALUES (?, ?)",
        guild_id, prefix
    )


async def remove_prefix(guild_id: int, prefix: str) -> bool:
    """Remove a custom prefix from a guild."""
    cursor = await db.execute(
        "DELETE FROM prefixes WHERE guild_id = ? AND prefix = ?",
        guild_id, prefix
    )
    return cursor.rowcount > 0


async def clear_prefixes(guild_id: int) -> None:
    """Remove all custom prefixes from a guild."""
    await db.execute("DELETE FROM prefixes WHERE guild_id = ?", guild_id)


# AI prompt functions

async def get_ai_prompt(guild_id: int) -> Optional[str]:
    """Get custom system prompt for a guild."""
    row = await db.fetch_one(
        "SELECT prompt FROM ai_prompts WHERE guild_id = ?",
        guild_id
    )
    return row["prompt"] if row else None


async def set_ai_prompt(guild_id: int, prompt: str) -> None:
    """Set a custom system prompt for a guild."""
    await db.execute(
        "INSERT OR REPLACE INTO ai_prompts (guild_id, prompt) VALUES (?, ?)",
        guild_id, prompt
    )


async def delete_ai_prompt(guild_id: int) -> None:
    """Delete custom system prompt for a guild."""
    await db.execute(
        "DELETE FROM ai_prompts WHERE guild_id = ?",
        guild_id
    )


# Antinuke database functions

async def get_antinuke_config(guild_id: int) -> Optional[aiosqlite.Row]:
    """Get antinuke configuration for a guild."""
    return await db.fetch_one(
        "SELECT * FROM antinuke_config WHERE guild_id = ?",
        guild_id
    )


async def set_antinuke_enabled(guild_id: int, enabled: bool) -> None:
    """Enable or disable antinuke for a guild."""
    await db.execute(
        "INSERT OR REPLACE INTO antinuke_config (guild_id, enabled) VALUES (?, ?)",
        guild_id, int(enabled)
    )


async def get_antinuke_whitelist(guild_id: int) -> list[int]:
    """Get list of whitelisted user IDs for a guild."""
    rows = await db.fetch_all(
        "SELECT user_id FROM antinuke_whitelist WHERE guild_id = ?",
        guild_id
    )
    return [row["user_id"] for row in rows]


async def add_to_antinuke_whitelist(guild_id: int, user_id: int) -> None:
    """Add a user to the antinuke whitelist."""
    await db.execute(
        "INSERT OR IGNORE INTO antinuke_whitelist (guild_id, user_id) VALUES (?, ?)",
        guild_id, user_id
    )


async def remove_from_antinuke_whitelist(guild_id: int, user_id: int) -> None:
    """Remove a user from the antinuke whitelist."""
    await db.execute(
        "DELETE FROM antinuke_whitelist WHERE guild_id = ? AND user_id = ?",
        guild_id, user_id
    )


async def get_antinuke_modules(guild_id: int) -> Optional[aiosqlite.Row]:
    """Get antinuke module settings for a guild."""
    return await db.fetch_one(
        "SELECT * FROM antinuke_modules WHERE guild_id = ?",
        guild_id
    )


async def set_antinuke_punishment(guild_id: int, event: str, punishment: str) -> None:
    """Set punishment for an antinuke event type."""
    await db.execute(
        f"UPDATE antinuke_modules SET {event} = ? WHERE guild_id = ?",
        punishment, guild_id
    )


async def log_antinuke_action(
    guild_id: int,
    executor_id: Optional[int],
    action_type: str,
    target_id: Optional[int],
    punishment: Optional[str]
) -> None:
    """Log an antinuke action to the database."""
    await db.execute(
        """INSERT INTO antinuke_action_log 
           (guild_id, executor_id, action_type, target_id, punishment_applied)
           VALUES (?, ?, ?, ?, ?)""",
        guild_id, executor_id, action_type, target_id, punishment
    )


# Giveaway database functions

async def create_giveaway(
    message_id: int,
    channel_id: int,
    guild_id: int,
    prize: str,
    winners: int,
    duration: int,
    started_at: int,
    ends_at: int,
    image: Optional[str] = None
) -> int:
    """Create a new giveaway record. Returns the giveaway ID."""
    cursor = await db.execute(
        """INSERT INTO giveaways 
           (message_id, channel_id, guild_id, prize, winners, duration, 
            started_at, ends_at, image)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        message_id, channel_id, guild_id, prize, winners, duration,
        started_at, ends_at, image
    )
    return cursor.lastrowid


async def get_giveaway_by_message(message_id: int) -> Optional[aiosqlite.Row]:
    """Get a giveaway by its message ID."""
    return await db.fetch_one(
        "SELECT * FROM giveaways WHERE message_id = ?",
        message_id
    )


async def get_giveaway_by_id(giveaway_id: int) -> Optional[aiosqlite.Row]:
    """Get a giveaway by its ID."""
    return await db.fetch_one(
        "SELECT * FROM giveaways WHERE id = ?",
        giveaway_id
    )


async def get_latest_giveaway(guild_id: int) -> Optional[aiosqlite.Row]:
    """Get the latest ongoing giveaway for a guild."""
    return await db.fetch_one(
        """SELECT * FROM giveaways 
           WHERE guild_id = ? AND ended = 0 
           ORDER BY started_at DESC LIMIT 1""",
        guild_id
    )


async def get_all_active_giveaways() -> list[aiosqlite.Row]:
    """Get all active giveaways that haven't ended yet."""
    return await db.fetch_all(
        "SELECT * FROM giveaways WHERE ended = 0 AND ends_at > 0"
    )


async def add_giveaway_entry(giveaway_id: int, user_id: int) -> bool:
    """Add a user to a giveaway. Returns True if successful."""
    try:
        await db.execute(
            "INSERT OR IGNORE INTO giveaway_entries (giveaway_id, user_id) VALUES (?, ?)",
            giveaway_id, user_id
        )
        return True
    except Exception:
        return False


async def remove_giveaway_entry(giveaway_id: int, user_id: int) -> bool:
    """Remove a user from a giveaway. Returns True if successful."""
    cursor = await db.execute(
        "DELETE FROM giveaway_entries WHERE giveaway_id = ? AND user_id = ?",
        giveaway_id, user_id
    )
    return cursor.rowcount > 0


async def get_giveaway_entries(giveaway_id: int) -> list[int]:
    """Get all user IDs entered in a giveaway."""
    rows = await db.fetch_all(
        "SELECT user_id FROM giveaway_entries WHERE giveaway_id = ?",
        giveaway_id
    )
    return [row["user_id"] for row in rows]


async def get_entry_count(giveaway_id: int) -> int:
    """Get the number of entries in a giveaway."""
    row = await db.fetch_one(
        "SELECT COUNT(*) as count FROM giveaway_entries WHERE giveaway_id = ?",
        giveaway_id
    )
    return row["count"] if row else 0


async def end_giveaway(giveaway_id: int, winner_ids: list[int]) -> None:
    """Mark a giveaway as ended with its winners."""
    await db.execute(
        "UPDATE giveaways SET ended = 1, winner_ids = ? WHERE id = ?",
        ",".join(map(str, winner_ids)), giveaway_id
    )


async def is_user_in_giveaway(giveaway_id: int, user_id: int) -> bool:
    """Check if a user is entered in a giveaway."""
    row = await db.fetch_one(
        "SELECT 1 FROM giveaway_entries WHERE giveaway_id = ? AND user_id = ?",
        giveaway_id, user_id
    )
    return row is not None


# Blacklist functions

async def is_user_blacklisted(user_id: int) -> bool:
    """Check if a user is blacklisted from giveaways."""
    row = await db.fetch_one(
        "SELECT 1 FROM giveaway_blacklist WHERE user_id = ?",
        user_id
    )
    return row is not None


async def add_to_blacklist(user_id: int) -> None:
    """Add a user to the giveaway blacklist."""
    await db.execute(
        "INSERT OR IGNORE INTO giveaway_blacklist (user_id) VALUES (?)",
        user_id
    )


async def remove_from_blacklist(user_id: int) -> bool:
    """Remove a user from the giveaway blacklist. Returns True if removed."""
    cursor = await db.execute(
        "DELETE FROM giveaway_blacklist WHERE user_id = ?",
        user_id
    )
    return cursor.rowcount > 0


async def get_blacklist() -> list[int]:
    """Get all blacklisted user IDs."""
    rows = await db.fetch_all("SELECT user_id FROM giveaway_blacklist")
    return [row["user_id"] for row in rows]


# Default channel functions

async def get_giveaway_channel(guild_id: int) -> Optional[int]:
    """Get the default giveaway channel for a guild."""
    row = await db.fetch_one(
        "SELECT channel_id FROM giveaway_channels WHERE guild_id = ?",
        guild_id
    )
    return row["channel_id"] if row else None


async def set_giveaway_channel(guild_id: int, channel_id: int) -> None:
    """Set the default giveaway channel for a guild."""
    await db.execute(
        "INSERT OR REPLACE INTO giveaway_channels (guild_id, channel_id) VALUES (?, ?)",
        guild_id, channel_id
    )
