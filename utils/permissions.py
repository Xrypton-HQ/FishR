import discord
from typing import Optional
import logging
from config import OWNER_ID
from utils.database import db

logger = logging.getLogger(__name__)


async def is_owner(user_id: int) -> bool:
    """Check if user is the main owner."""
    return user_id == OWNER_ID


async def is_whitelisted(user_id: int) -> bool:
    """Check if user is in the owner whitelist."""
    async with db.acquire() as conn:
        async with conn.execute(
            "SELECT 1 FROM whitelist WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None


async def can_use_owner_commands(user_id: int) -> bool:
    """Check if user can use owner commands."""
    return await is_owner(user_id) or await is_whitelisted(user_id)


async def add_to_whitelist(user_id: int) -> bool:
    """
    Add user to whitelist.
    Returns True if added, False if already exists.
    """
    try:
        async with db.acquire() as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)",
                (user_id,)
            )
            await conn.commit()
             
            # Check if insert was successful
            async with conn.execute(
                "SELECT 1 FROM whitelist WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None
    except Exception as e:
        logger.error(f"Failed to add user {user_id} to whitelist: {e}")
        return False


async def remove_from_whitelist(user_id: int) -> bool:
    """
    Remove user from whitelist.
    Returns True if removed, False if not found.
    """
    try:
        async with db.acquire() as conn:
            cursor = await conn.execute(
                "DELETE FROM whitelist WHERE user_id = ?",
                (user_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to remove user {user_id} from whitelist: {e}")
        return False


async def get_whitelist() -> list[int]:
    """Get all whitelisted user IDs."""
    try:
        async with db.acquire() as conn:
            async with conn.execute("SELECT user_id FROM whitelist") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    except Exception as e:
        logger.error(f"Failed to get whitelist: {e}")
        return []
