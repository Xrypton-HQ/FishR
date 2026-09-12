"""
Treasure chest event system.
Handles spawning, claiming, rewards, and cooldown management.
"""

import asyncio
import logging
import random
import time
from typing import Optional, Dict
import discord

from utils.database import db, update_credits, update_fish, create_user
from utils.activity import is_channel_active
from utils.event_views import TreasureChestLayoutView, build_treasure_spawn_view

logger = logging.getLogger(__name__)

# Configuration
GLOBAL_COOLDOWN = 600  # 10 minutes in seconds
CHANNEL_COOLDOWN = 1200  # 20 minutes in seconds
SPAWN_CHANCE = 15  # 15% chance when activity threshold met
VIEW_TIMEOUT = 45.0  # 45 seconds to claim

# State tracking (in-memory)
_active_chests: Dict[int, int] = {}      # {channel_id: message_id}
_active_views: Dict[int, TreasureChestLayoutView] = {}  # {message_id: view}
_chest_lock = asyncio.Lock()


async def get_cooldowns() -> tuple[float, dict[int, float]]:
    """
    Load cooldowns from database.
    Returns (last_global_spawn, {channel_id: last_spawn}).
    """
    async with db.acquire() as conn:
        # Get global cooldown
        cursor = await conn.execute(
            "SELECT last_global_spawn FROM treasure_cooldowns WHERE channel_id = 0"
        )
        global_row = await cursor.fetchone()
        last_global = global_row["last_global_spawn"] if global_row else 0
        
        # Get all channel cooldowns
        cursor = await conn.execute(
            "SELECT channel_id, last_channel_spawn FROM treasure_cooldowns"
        )
        rows = await cursor.fetchall()
        channel_cooldowns = {row["channel_id"]: row["last_channel_spawn"] for row in rows}
        
        return last_global, channel_cooldowns


async def update_global_cooldown(timestamp: Optional[float] = None) -> None:
    """Update global cooldown timestamp."""
    if timestamp is None:
        timestamp = time.time()
    
    async with db.acquire() as conn:
        await conn.execute(
            """INSERT OR REPLACE INTO treasure_cooldowns 
               (channel_id, last_global_spawn) VALUES (0, ?)""",
            (timestamp,)
        )
        await conn.commit()


async def update_channel_cooldown(channel_id: int, timestamp: Optional[float] = None) -> None:
    """Update channel-specific cooldown."""
    if timestamp is None:
        timestamp = time.time()
    
    async with db.acquire() as conn:
        await conn.execute(
            """INSERT OR REPLACE INTO treasure_cooldowns 
               (channel_id, last_channel_spawn, last_global_spawn) 
               VALUES (?, ?, COALESCE((SELECT last_global_spawn FROM treasure_cooldowns WHERE channel_id = 0), 0))""",
            (channel_id, timestamp)
        )
        await conn.commit()


async def can_spawn_in_channel(channel_id: int, current_time: Optional[float] = None) -> tuple[bool, str]:
    """
    Check if a treasure chest can spawn in the given channel.
    Returns (can_spawn, reason).
    """
    if current_time is None:
        current_time = time.time()
    
    # Check global cooldown
    last_global, channel_cooldowns = await get_cooldowns()
    time_since_global = current_time - last_global
    
    if time_since_global < GLOBAL_COOLDOWN:
        remaining = GLOBAL_COOLDOWN - time_since_global
        return False, f"Global cooldown: {int(remaining)}s remaining"
    
    # Check channel cooldown
    last_channel = channel_cooldowns.get(channel_id, 0)
    time_since_channel = current_time - last_channel
    
    if time_since_channel < CHANNEL_COOLDOWN:
        remaining = CHANNEL_COOLDOWN - time_since_channel
        return False, f"Channel cooldown: {int(remaining)}s remaining"
    
    # Check activity threshold
    if not await is_channel_active(channel_id):
        return False, "Channel activity too low"
    
    return True, "OK"


async def try_spawn_chest(channel: discord.TextChannel) -> Optional[discord.Message]:
    """
    Attempt to spawn a treasure chest in the given channel.
    Returns the spawned message if successful, None otherwise.
    """
    async with _chest_lock:
        # Prevent duplicate spawns in same channel
        if channel.id in _active_chests:
            return None
        
        current_time = time.time()
        can_spawn, reason = await can_spawn_in_channel(channel.id, current_time)
        
        if not can_spawn:
            logger.debug(f"Cannot spawn in #{channel} (id={channel.id}): {reason}")
            return None
        
        # Random spawn chance
        if random.randint(1, 100) > SPAWN_CHANCE:
            logger.debug(f"Spawn chance failed in #{channel}")
            return None
    
    # Calculate rewards
    credits_reward = random.randint(500, 1500)
    fish_reward = random.randint(1, 10)
    
    # Build LayoutView with spawn message and claim button
    view = build_treasure_spawn_view(
        chest_id=0,  # Will be updated after DB insert
        credits=credits_reward,
        fish=fish_reward,
        timeout=VIEW_TIMEOUT
    )
    
    try:
        # Send message with LayoutView (contains both message and button)
        message = await channel.send(view=view)
        # Store message reference in view for timeout handling
        view.message = message
        view.channel_id = channel.id
        
        # Record in database
        async with db.acquire() as conn:
            cursor = await conn.execute(
                """INSERT INTO treasure_chests 
                   (channel_id, message_id, spawned_at, credits_reward, fish_reward, status)
                   VALUES (?, ?, ?, ?, ?, 'active')""",
                (channel.id, message.id, int(current_time), credits_reward, fish_reward)
            )
            chest_id = cursor.lastrowid
            view.chest_id = chest_id
            view._btn.custom_id = f"treasure_claim_{chest_id}"
        
        # Update cooldowns
        await update_global_cooldown(current_time)
        await update_channel_cooldown(channel.id, current_time)
        
        # Track active chest
        async with _chest_lock:
            _active_chests[channel.id] = message.id
            _active_views[message.id] = view
        
        logger.info(
            f"Spawned treasure chest in {channel.guild}/{channel} "
            f"(chest_id={chest_id}, msg_id={message.id}, credits={credits_reward}, fish={fish_reward})"
        )
        
        # Start background task to mark as expired in DB after timeout
        asyncio.create_task(_expire_chest_task(chest_id, channel.id, message.id, VIEW_TIMEOUT))
        
        return message
    
    except Exception as e:
        logger.error(f"Failed to spawn chest in {channel.id}: {e}", exc_info=True)
        return None


async def claim_treasure(chest_id: int, user_id: int) -> tuple[bool, str]:
    """
    Process a treasure chest claim.
    Returns (success, message).
    """
    async with db.acquire() as conn:
        # Atomic claim using UPDATE...WHERE to prevent race conditions
        cursor = await conn.execute(
            """UPDATE treasure_chests 
               SET claimed_by = ?, claimed_at = ?, status = 'claimed'
               WHERE id = ? AND status = 'active'""",
            (user_id, int(time.time()), chest_id)
        )
        await conn.commit()
        
        if cursor.rowcount == 0:
            return False, "This treasure has already been claimed or expired!"
        
        # Get chest details
        cursor = await conn.execute(
            "SELECT credits_reward, fish_reward FROM treasure_chests WHERE id = ?",
            (chest_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return False, "Treasure data not found!"
        
        credits = row["credits_reward"]
        fish = row["fish_reward"]
        
        # Ensure user exists
        await create_user(user_id)
        
        # Award rewards atomically
        try:
            await update_credits(user_id, credits)
            await update_fish(user_id, fish)
            logger.info(f"User {user_id} claimed treasure {chest_id}: +{credits} credits, +{fish} fish")
            return True, f"Claimed! +{credits} credits, +{fish} fish"
        except Exception as e:
            logger.error(f"Failed to award rewards for chest {chest_id}: {e}", exc_info=True)
            return False, "Failed to award rewards. Please contact an admin."


async def _expire_chest_task(chest_id: int, channel_id: int, message_id: int, timeout: float):
    """
    Background task: after timeout, mark chest as expired in DB.
    UI updates are handled by the view's on_timeout.
    """
    try:
        await asyncio.sleep(timeout)
        
        # Check if chest is still active (not claimed)
        async with db.acquire() as conn:
            cursor = await conn.execute(
                "SELECT status FROM treasure_chests WHERE id = ?",
                (chest_id,)
            )
            row = await cursor.fetchone()
            
            if not row or row["status"] != 'active':
                # Already claimed, nothing to do
                return
            
            # Mark as expired in DB
            await conn.execute(
                "UPDATE treasure_chests SET status = 'expired' WHERE id = ?",
                (chest_id,)
            )
            await conn.commit()
        
        logger.info(f"Treasure chest {chest_id} in channel {channel_id} expired (unclaimed)")
        
        # Clean up active tracking
        async with _chest_lock:
            _active_chests.pop(channel_id, None)
            _active_views.pop(message_id, None)
        
    except asyncio.CancelledError:
        # Task cancelled (chest was claimed)
        pass
    except Exception as e:
        logger.error(f"Error in expiration task for chest {chest_id}: {e}", exc_info=True)


def get_active_chest_count() -> int:
    """Get number of currently active (unclaimed) chests."""
    return len(_active_chests)


async def clear_channel_chest(channel_id: int) -> None:
    """Remove chest from active tracking."""
    async with _chest_lock:
        message_id = _active_chests.pop(channel_id, None)
        if message_id:
            _active_views.pop(message_id, None)
