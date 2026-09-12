import random
import time
import logging

from utils.database import set_market_price
from config import MARKET_PRICE_MIN, MARKET_PRICE_MAX

logger = logging.getLogger(__name__)


async def update_market_price() -> None:
    """Generate a new random market price and persist to database."""
    new_price = random.randint(MARKET_PRICE_MIN, MARKET_PRICE_MAX)
    timestamp = int(time.time())
    await set_market_price(new_price, timestamp)
    logger.info(f"Market price updated to {new_price} credits")
