import discord
import asyncio
from discord.ext import commands, tasks
import logging

from tasks.market_task import update_market_price
from utils.database import get_market_price, get_next_market_refresh, get_previous_market_price
from utils.embeds import market_layout, error_layout
from config import MARKET_REFRESH_MINUTES

logger = logging.getLogger(__name__)


class Market(commands.Cog):
    """Market system with dynamic fish pricing."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.market_loop.start()

    def cog_unload(self):
        self.market_loop.cancel()

    @tasks.loop(minutes=MARKET_REFRESH_MINUTES)
    async def market_loop(self):
        """Background task to update market price."""
        try:
            await update_market_price()
        except Exception as e:
            logger.error(f"Market loop error: {e}", exc_info=True)

    @market_loop.before_loop
    async def before_market_loop(self):
        """Wait for bot to be ready before starting loop."""
        await self.bot.wait_until_ready()

    @commands.hybrid_command(name="market")
    async def market(self, ctx: commands.Context):
        """Show current market price and next refresh."""
        try:
            price = await get_market_price()
            previous_price = await get_previous_market_price()
            next_refresh = await get_next_market_refresh()

            await ctx.send(view=market_layout(price, previous_price, next_refresh))
        except Exception as e:
            logger.error(f"Market command error: {e}", exc_info=True)
            await ctx.send(
                view=error_layout("Failed to retrieve market data.")
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Market(bot))