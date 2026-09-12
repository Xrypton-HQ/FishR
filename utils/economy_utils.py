import random
import time
import math
from typing import Optional, Tuple

# Constants
DAILY_BASE_REWARD = 100
DAILY_STREAK_BONUS = 25
DAILY_COOLDOWN = 24 * 60 * 60  # 24 hours in seconds
DAILY_GRACE_PERIOD = 12 * 60 * 60  # 12 hours grace period

BEG_COOLDOWN = 60  # 60 seconds
BEG_SUCCESS_MIN = 25
BEG_SUCCESS_MAX = 250
BEG_BACKFIRE_MIN = 10
BEG_BACKFIRE_MAX = 100
BEG_SUCCESS_RATE = 0.65
BEG_FAILURE_RATE = 0.25
BEG_BACKFIRE_RATE = 0.10

TRANSFER_FEE_RATE = 0.02


def calculate_daily_reward(streak: int) -> int:
    """
    Calculate daily reward based on current streak.
    Formula: 100 + (streak * 25)
    """
    return DAILY_BASE_REWARD + (streak * DAILY_STREAK_BONUS)


def format_daily_cooldown(seconds: int) -> str:
    """
    Format daily cooldown time as human-readable string.
    Examples: "5h 22m", "12h 0m", "0h 45m"
    """
    if seconds <= 0:
        return "0s"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def get_remaining_daily_cooldown(last_claim: int) -> int:
    """
    Calculate remaining cooldown until next daily claim.
    Returns seconds remaining, or 0 if ready.
    """
    now = int(time.time())
    elapsed = now - last_claim
    remaining = DAILY_COOLDOWN - elapsed
    return max(0, remaining)


def is_daily_ready(last_claim: int) -> bool:
    """Check if user can claim daily reward."""
    return get_remaining_daily_cooldown(last_claim) == 0


def validate_transfer_amount(amount: int) -> Tuple[bool, Optional[str]]:
    """
    Validate transfer amount.
    Returns (is_valid, error_message).
    """
    if amount <= 0:
        return False, "Amount must be a positive number."
    if amount > 1_000_000:
        return False, "Amount cannot exceed 1,000,000 credits."
    return True, None


def calculate_transfer_fee(amount: int) -> int:
    """Calculate 2% transfer fee, rounded up."""
    return math.ceil(amount * TRANSFER_FEE_RATE)


def get_beg_outcome() -> Tuple[str, int, str]:
    """
    Get random beg outcome.
    Returns (outcome_type, amount_change, message).
    outcome_type: 'success', 'failure', or 'backfire'
    """
    roll = random.random()

    if roll < BEG_SUCCESS_RATE:
        # Success: gain credits
        amount = random.randint(BEG_SUCCESS_MIN, BEG_SUCCESS_MAX)
        msg = random.choice(SUCCESS_MESSAGES)
        return "success", amount, msg

    elif roll < BEG_SUCCESS_RATE + BEG_FAILURE_RATE:
        # Failure: no change
        msg = random.choice(FAILURE_MESSAGES)
        return "failure", 0, msg

    else:
        # Backfire: lose credits
        amount = random.randint(BEG_BACKFIRE_MIN, BEG_BACKFIRE_MAX)
        msg = random.choice(BACKFIRE_MESSAGES)
        return "backfire", -amount, msg


# Random messages for beg outcomes
SUCCESS_MESSAGES = [
    "🧓 A stranger felt bad for you and gave you {amount} credits.",
    "🐟 A fisherman tossed you {amount} credits.",
    "🪙 Someone dropped coins into your cup. +{amount} credits.",
    "🍕 A pizza delivery guy shared a tip of {amount} credits!",
    "🎰 You found a lucky coin worth {amount} credits!",
    "💝 A generous donor gave you {amount} credits!",
    "🌾 You harvested some extra crops and sold them for {amount} credits!",
    "🎯 Your luck turned around! You earned {amount} credits!",
]

FAILURE_MESSAGES = [
    "💀 Everyone ignored you.",
    "🗑️ Someone threw trash at you instead.",
    "😐 You begged for hours but got nothing.",
    "🚶 People walked past without a second glance.",
    "🐶 A dog barked at you and took your spot.",
    "📱 Everyone was too busy on their phones to notice you.",
]

BACKFIRE_MESSAGES = [
    "🚔 You got fined for public disturbance. Lost {amount} credits.",
    "🦅 A bird stole {amount} credits from your wallet!",
    "💥 You accidentally dropped {amount} credits and someone took them!",
    "👮 A security guard caught you and confiscated {amount} credits!",
    "🃏 You were tricked and gave {amount} credits to a scammer!",
    "🏥 You had to pay a medical bill of {amount} credits!",
]
