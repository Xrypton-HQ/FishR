"""
Activity tracking module for treasure chest spawn logic.
Tracks message frequency per channel using rolling time windows.
"""

import asyncio
import logging
import time
from collections import deque
from typing import Optional, Deque, Tuple

import discord
from discord.ext import tasks

logger = logging.getLogger(__name__)

# Activity window configuration
ACTIVITY_WINDOW_SECONDS = 60  # Look back 60 seconds
ACTIVITY_THRESHOLD_MIN = 15   # Minimum messages for "high" activity
ACTIVITY_THRESHOLD_MAX = 30   # Maximum messages before considered spam

# Global activity store: {channel_id: deque(timestamps)}
_channel_activity: dict[int, Deque[float]] = {}
_activity_lock = asyncio.Lock()


class ChannelActivity:
    """Manages activity tracking for a single channel."""
    
    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        self.timestamps: Deque[float] = deque()
        self._last_cleanup = time.time()
    
    def add_message(self, timestamp: float) -> None:
        """Add a message timestamp and clean old entries."""
        self.timestamps.append(timestamp)
        self._cleanup_old(timestamp)
    
    def _cleanup_old(self, current_time: float) -> None:
        """Remove timestamps older than the activity window."""
        cutoff = current_time - ACTIVITY_WINDOW_SECONDS
        while self.timestamps and self.timestamps[0] < cutoff:
            self.timestamps.popleft()
    
    def get_count(self, current_time: Optional[float] = None) -> int:
        """Get message count in current activity window."""
        if current_time is None:
            current_time = time.time()
        self._cleanup_old(current_time)
        return len(self.timestamps)
    
    def is_highly_active(self, current_time: Optional[float] = None) -> bool:
        """Check if channel meets high activity threshold."""
        count = self.get_count(current_time)
        return ACTIVITY_THRESHOLD_MIN <= count <= ACTIVITY_THRESHOLD_MAX
    
    def is_above_threshold(self, current_time: Optional[float] = None) -> bool:
        """Check if channel has at least minimum activity."""
        count = self.get_count(current_time)
        return count >= ACTIVITY_THRESHOLD_MIN


async def track_message(channel_id: int, timestamp: Optional[float] = None) -> None:
    """
    Record a message for activity tracking.
    Called from on_message event.
    """
    if timestamp is None:
        timestamp = time.time()
    
    async with _activity_lock:
        if channel_id not in _channel_activity:
            _channel_activity[channel_id] = ChannelActivity(channel_id)
        
        _channel_activity[channel_id].add_message(timestamp)
        
        # Periodic cleanup of empty channels (every 1000 messages approx)
        if len(_channel_activity[channel_id].timestamps) == 0:
            _channel_activity.pop(channel_id, None)


def get_channel_activity(channel_id: int) -> Optional[ChannelActivity]:
    """Get activity tracker for a channel if it exists."""
    return _channel_activity.get(channel_id)


async def is_channel_active(channel_id: int) -> bool:
    """
    Check if channel has enough recent activity for chest spawn.
    Acquires lock to ensure safe concurrent access.
    """
    async with _activity_lock:
        activity = _channel_activity.get(channel_id)
        if activity is None:
            return False
        return activity.is_above_threshold()


async def get_active_channels() -> list[int]:
    """
    Get list of channel IDs currently meeting activity threshold.
    Returns a copy to avoid concurrent modification issues.
    """
    active = []
    current = time.time()
    async with _activity_lock:
        for channel_id, activity in _channel_activity.items():
            if activity.is_above_threshold(current):
                active.append(channel_id)
    return active


async def cleanup_inactive_channels(max_idle_seconds: float = 300.0) -> None:
    """
    Remove activity data for channels that haven't had messages in a while.
    Prevents memory leaks from abandoned channels.
    Acquires lock to avoid concurrent modification.
    """
    current = time.time()
    cutoff = current - max_idle_seconds
    
    to_remove = []
    async with _activity_lock:
        for channel_id, activity in _channel_activity.items():
            if not activity.timestamps or activity.timestamps[-1] < cutoff:
                to_remove.append(channel_id)
        for channel_id in to_remove:
            _channel_activity.pop(channel_id, None)
    
    if to_remove:
        logger.debug(f"Cleaned up {len(to_remove)} inactive channel activity trackers")
    
    # Since this is called from async context, run it in a task
    # But we need to run it synchronously within the async context? Actually cleanup_task is async loop,
    # so we can await a helper.
    # We'll change the call site to use an async version.
    pass


# Background task for periodic cleanup
@tasks.loop(minutes=5)
async def cleanup_task():
    """Periodically clean up old activity data."""
    await cleanup_inactive_channels()
    logger.debug(f"Active channel count: {len(_channel_activity)}")


async def start_cleanup_task(bot: discord.Client):
    """Start the background cleanup task."""
    cleanup_task.start()
    logger.info("Started activity cleanup task")


async def stop_cleanup_task():
    """Stop the background cleanup task."""
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("Stopped activity cleanup task")
