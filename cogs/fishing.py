import discord
import random
import asyncio
import time
from discord.ext import commands
from typing import Optional
import logging

from utils.database import (
    get_user, create_user, update_credits, update_fish, update_gems,
    get_inventory, get_upgrades, get_buffs, set_frenzy_until,
    safe_update_fish
)
from utils.embeds import fishing_layout, cooldown_layout, error_layout
from utils.views import ReelingView
from utils.constants import *
from config import FISHING_COOLDOWN, FISHING_WAIT_MIN, FISHING_WAIT_MAX, \
    FISHING_REACTION_WINDOW, FISHING_BASE_MIN, FISHING_BASE_MAX

logger = logging.getLogger(__name__)


class Fishing(commands.Cog):
    """Fishing commands and mechanics."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        self.active_sessions: set[int] = set()

    async def get_fish_amount(self, user_id: int, base_amount: int) -> int:
        """Calculate final fish amount including all modifiers."""
        upgrades = await get_upgrades(user_id)
        stronger_rod = upgrades["stronger_rod"] if upgrades else 0
        new_rod = upgrades["new_rod"] if upgrades else 0

        total = base_amount + stronger_rod * 2
        total *= (2 ** new_rod)

        
        buffs = await get_buffs(user_id)
        if buffs and buffs["frenzy_until"] > time.time():
            total *= 4

        return total

    async def _handle_reel(
        self, interaction: discord.Interaction, user_id: int, base_amount: int
    ) -> None:
        try:
            fish_amount = await self.get_fish_amount(user_id, base_amount)
            await update_fish(user_id, fish_amount)

            if random.random() < 0.2:
                gems_gained = random.randint(4, 9)
                await update_gems(user_id, gems_gained)
                view = fishing_layout("success", amount=fish_amount, gems=gems_gained)
            else:
                view = fishing_layout("success", amount=fish_amount)

            await interaction.response.edit_message(view=view)
            
        except Exception as e:
            logger.error(f"Reel error: {e}", exc_info=True)
            await interaction.response.edit_message(
                view=error_layout("Something went wrong while processing your catch!")
            )

    @commands.hybrid_command(name="fish", aliases=["f"])
    @commands.cooldown(1, FISHING_COOLDOWN, commands.BucketType.user)
    async def fish(self, ctx: commands.Context):
        """Go fishing! Cast your line and catch fish."""
        user_id = ctx.author.id

        
        if user_id in self.active_sessions:
            await ctx.send(
                view=error_layout("You already have a fishing line in the water!"),
                delete_after=5
            )
            return

        
        await create_user(user_id)

        self.active_sessions.add(user_id)

        try:
            
            msg = await ctx.send(view=fishing_layout("cast"))

            
            wait_time = random.uniform(FISHING_WAIT_MIN, FISHING_WAIT_MAX)
            await asyncio.sleep(wait_time)

            
            base_amount = random.randint(FISHING_BASE_MIN, FISHING_BASE_MAX)

            view = ReelingView(
                author_id=user_id,
                base_amount=base_amount,
                on_reel=self._handle_reel,
                timeout=FISHING_REACTION_WINDOW
            )

            await msg.edit(view=view)

            try:
                await view.wait()
            except asyncio.TimeoutError:
                pass

            
            if not view.reeled:
                await msg.edit(view=fishing_layout("miss"))

        finally:
            self.active_sessions.discard(user_id)

    @fish.error
    async def fish_error(self, ctx: commands.Context, error):
        """Handle fish command errors."""
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(view=cooldown_layout(int(error.retry_after)))
        else:
            logger.error(f"Fish error: {error}", exc_info=True)
            await ctx.send(
                view=error_layout("An unexpected error occurred while fishing."),
                delete_after=10
            )

    @commands.hybrid_command(name="cast")
    async def cast(self, ctx: commands.Context):
        """Alias for fish."""
        await self.fish(ctx)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fishing(bot))
