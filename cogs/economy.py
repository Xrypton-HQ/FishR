import discord
import asyncio
import time
import math
import logging
from discord.ext import commands
from typing import Optional
import random

from utils.database import (
    get_user, create_user, update_credits, safe_deduct_credits, safe_update_fish,
    get_inventory, get_leaderboard, get_market_price,
    get_daily_data, set_daily_claim, reset_daily_streak,
    safe_transfer_credits, get_beg_cooldown, set_beg_cooldown
)
from utils.embeds import (
    balance_view, sell_confirmation_layout, error_layout,
    leaderboard_view, cooldown_layout, create_container
)
from utils.views import ConfirmationView
from utils.constants import EMOJI_VERIFY, EMOJI_NO
from utils.constants import EMOJI_FISH, EMOJI_CREDITS, COLOR_SUCCESS, COLOR_ERROR
from utils.cooldowns import format_cooldown, get_remaining_cooldown
from utils.economy_utils import (
    calculate_daily_reward, format_daily_cooldown,
    get_beg_outcome, BEG_COOLDOWN
)

logger = logging.getLogger(__name__)


class Economy(commands.Cog):
    """Economy commands: balance, sell, leaderboard, daily, give, beg."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    

    @commands.hybrid_command(name="balance", aliases=["bal", "money"])
    async def balance(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Show your balance or another user's balance."""
        target = member or ctx.author
        user_id = target.id

        await create_user(user_id)

        inv = await get_inventory(user_id)
        user = await get_user(user_id)

        credits = user["credits"] if user else 0
        fish = inv["fish"] if inv else 0
        gems = user["gems"] if user else 0
        bank = user["bank"] if user else 0

        await ctx.send(view=balance_view(credits, gems, fish, target, bank))

    

    @commands.hybrid_command(name="sell")
    async def sell(self, ctx: commands.Context, amount: Optional[int] = None):
        """Sell fish for credits at market price."""
        user_id = ctx.author.id
        await create_user(user_id)

        inv = await get_inventory(user_id)
        fish_count = inv["fish"] if inv else 0

        if fish_count <= 0:
            await ctx.send(
                view=error_layout("You don't have any fish to sell!"),
                delete_after=5
            )
            return

        
        if amount is None:
            sell_amount = fish_count
        else:
            if amount <= 0:
                await ctx.send(
                    view=error_layout("Amount must be positive!"),
                    delete_after=5
                )
                return
            sell_amount = min(amount, fish_count)

        
        price = await get_market_price()
        total = sell_amount * price

        async def on_confirm(interaction: discord.Interaction):
            try:
                
                fish_success = await safe_update_fish(user_id, -sell_amount)
                if not fish_success:
                    await interaction.response.edit_message(
                        view=error_layout("Not enough fish to sell!")
                    )
                    return

                
                try:
                    await update_credits(user_id, total)
                except Exception:
                    
                    await safe_update_fish(user_id, sell_amount)
                    await interaction.response.edit_message(
                        view=error_layout("Failed to add credits. Sale cancelled, fish refunded.")
                    )
                    return

                embed = create_container(
                    title=f"{EMOJI_VERIFY} Sale Complete",
                    description=(
                        f"You sold **{sell_amount}** {EMOJI_FISH} "
                        f"for **{total}** {EMOJI_CREDITS}!"
                    ),
                    color=discord.Color.green().value
                )
                await interaction.response.edit_message(view=embed)

            except Exception as e:
                logger.error(f"Sell error: {e}", exc_info=True)
                await interaction.response.edit_message(
                    view=error_layout("An error occurred during sale.")
                )

        async def on_cancel(interaction: discord.Interaction):
            await interaction.response.edit_message(
                view=error_layout("Sale cancelled.")
            )

        view = ConfirmationView(
            author_id=ctx.author.id,
            on_confirm=on_confirm,
            on_cancel=on_cancel,
            content_view=sell_confirmation_layout(sell_amount, price, total),
            timeout=60.0
        )

        await ctx.send(view=view)

    

    @commands.hybrid_command(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard(self, ctx: commands.Context):
        """Show top 10 users by credits."""
        entries = await get_leaderboard(10)

        if not entries:
            await ctx.send(
                view=error_layout("No users found."),
                delete_after=5
            )
            return

        view, pages = leaderboard_view(entries, self.bot)
        await ctx.send(view=view)

    

    @commands.hybrid_command(name="daily")
    async def daily(self, ctx: commands.Context):
        """Claim your daily reward with streak bonuses!"""
        user_id = ctx.author.id
        await create_user(user_id)

        user = await get_user(user_id)
        if not user:
            await ctx.send(view=error_layout("Failed to retrieve user data."))
            return

        last_daily = user["last_daily"] or 0
        current_streak = user["daily_streak"] or 0

        
        remaining = get_remaining_cooldown(last_daily, 24 * 60 * 60)
        if remaining > 0:
            formatted = format_daily_cooldown(remaining)
            await ctx.send(view=error_layout(f"You must wait **{formatted}** before fishing again."))
            return

        now = int(time.time())

        
        grace_period = 12 * 60 * 60  
        elapsed = now - last_daily

        if last_daily == 0:
            
            new_streak = 1
        elif elapsed <= 24 * 60 * 60 + grace_period:
            
            new_streak = current_streak + 1
        else:
            
            new_streak = 1

        
        reward = calculate_daily_reward(new_streak)

        
        try:
            if new_streak == 1 and last_daily != 0 and elapsed > 24 * 60 * 60:
                
                await reset_daily_streak(user_id, now)
            await set_daily_claim(user_id, now, reward)
        except Exception as e:
            logger.error(f"Daily claim error for {user_id}: {e}", exc_info=True)
            await ctx.send(view=error_layout("An error occurred while claiming your daily reward."))
            return

        
        view = discord.ui.LayoutView()
        components = [
        discord.ui.TextDisplay(content="**🎁 Daily Reward**"),
        discord.ui.TextDisplay(content=(
            f"Claimed:\n"
            f"{EMOJI_CREDITS} **+{reward}** credits\n\n"
            f"🔥 Current Streak:\n"
            f"**{new_streak}** day{'s' if new_streak != 1 else ''}"
        )),
        discord.ui.TextDisplay(content=f"*Claimed by {ctx.author.display_name}*"),
    ]
        container = discord.ui.Container(
            *components,
            accent_color=COLOR_SUCCESS
        )
        view.add_item(container)

        await ctx.send(view=view)

    

    @commands.hybrid_command(name="give", aliases=["transfer", "pay", "send"])
    async def give(self, ctx: commands.Context, recipient: discord.Member, amount: int):
        """Transfer credits to another user (2% fee applies)."""
        sender_id = ctx.author.id
        receiver_id = recipient.id

        
        if sender_id == receiver_id:
            await ctx.send(view=error_layout("You cannot send credits to yourself."))
            return

        if recipient.bot:
            await ctx.send(view=error_layout("You cannot send credits to bots."))
            return

        valid, error_msg = validate_transfer_amount(amount)
        if not valid:
            await ctx.send(view=error_layout(error_msg))
            return

        
        await create_user(sender_id)
        await create_user(receiver_id)

        sender = await get_user(sender_id)
        if not sender:
            await ctx.send(view=error_layout("Could not find your account."))
            return

        if sender["credits"] < amount:
            await ctx.send(view=error_layout("Insufficient credits in your wallet."))
            return

        
        fee = calculate_transfer_fee(amount)
        total_deduction = amount + fee

        
        success, actual_fee = await safe_transfer_credits(sender_id, receiver_id, amount)

        if not success:
            await ctx.send(view=error_layout("Transfer failed. Insufficient funds or an error occurred."))
            return

        
        view = discord.ui.LayoutView()
        components = [
            discord.ui.TextDisplay(content="**💸 Transfer Complete**"),
            discord.ui.TextDisplay(content=(
                f"**Sent:**\n"
                f"{EMOJI_CREDITS} {amount:,} credits\n\n"
                f"**Fee:**\n"
                f"{EMOJI_CREDITS} {actual_fee:,} credits\n\n"
                f"**Recipient Received:**\n"
                f"{EMOJI_CREDITS} {amount:,} credits"
            )),
            discord.ui.TextDisplay(content=f"*To: {recipient.display_name}*"),
        ]
        container = discord.ui.Container(
            *components,
            accent_color=COLOR_SUCCESS
        )
        view.add_item(container)

        await ctx.send(view=view)

    

    @commands.hybrid_command(name="beg", aliases=["begging", "panhandle"])
    async def beg(self, ctx: commands.Context):
        """Beg random NPCs for credits!"""
        user_id = ctx.author.id
        await create_user(user_id)

        
        last_beg = await get_beg_cooldown(user_id) or 0
        remaining = get_remaining_cooldown(last_beg, BEG_COOLDOWN)

        if remaining > 0:
            formatted = format_cooldown(remaining)
            await ctx.send(
                view=error_layout(f"You must wait **{formatted}** before begging again."),
                delete_after=10
            )
            return

        
        outcome_type, amount_change, message = get_beg_outcome()

        now = int(time.time())
        reward = 0

        
        if outcome_type == "success":
            reward = amount_change
            await update_credits(user_id, reward)
            emoji = EMOJI_VERIFY
            title = "🎉 Begging Success"
        elif outcome_type == "failure":
            emoji = "💀"
            title = "😔 No Luck"
        else:  
            reward = amount_change  
            
            user = await get_user(user_id)
            if user and user["credits"] >= -reward:
                await safe_deduct_credits(user_id, -reward)
            else:
                
                outcome_type = "failure"
                reward = 0
                message = random.choice(FAILURE_MESSAGES)
                emoji = "💀"
                title = "😔 No Luck"
            if outcome_type == "backfire":
                emoji = "🚫"
                title = "😢 Backfire!"

        
        await set_beg_cooldown(user_id, now)


        view = discord.ui.LayoutView()
        components = [
            discord.ui.TextDisplay(content=f"**{title}**"),
            discord.ui.TextDisplay(content=f"{emoji} {message}"),
        ]

        if reward != 0:
            components.append(
                discord.ui.TextDisplay(
                    content=f"{EMOJI_CREDITS} **{reward:,}** credits"
                )
            )

        components.append(
            discord.ui.TextDisplay(content=f"*Cooldown: {format_cooldown(BEG_COOLDOWN)}*")
        )

        container = discord.ui.Container(
            *components,
            accent_color=COLOR_SUCCESS if outcome_type == "success" else COLOR_ERROR
        )
        view.add_item(container)

        await ctx.send(view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
