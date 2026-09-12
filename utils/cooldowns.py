import time
from typing import Dict


def format_cooldown(seconds: int) -> str:
    """Format cooldown time as human readable string."""
    if seconds <= 0:
        return "0s"
    
    minutes = seconds // 60
    secs = seconds % 60
    
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def get_remaining_cooldown(last_used: int, cooldown_seconds: int) -> int:
    """Calculate remaining cooldown seconds. Returns 0 if ready."""
    now = int(time.time())
    elapsed = now - last_used
    remaining = cooldown_seconds - elapsed
    return max(0, remaining)


def is_on_cooldown(last_used: int, cooldown_seconds: int) -> bool:
    """Check if an action is still on cooldown."""
    return get_remaining_cooldown(last_used, cooldown_seconds) > 0