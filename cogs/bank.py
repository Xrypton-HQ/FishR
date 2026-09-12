import discord
import random
import time
from discord.ext import commands
from typing import Optional
import logging

from utils.database import (
    get_user, create_user, deposit_credits, withdraw_credits,
    get_steal_cooldown, set_steal_cooldown, safe_deduct_credits, db
)
from utils.embeds import (
    bank_layout, steal_success_layout, steal_failed_layout,
    steal_cooldown_layout, steal_empty_wallet_layout, error_layout,
    create_container
)
from utils.cooldowns import get_remaining_cooldown
from config import STEAL_COOLDOWN

logger = logging.getLogger(__name__)


class DepositModal(discord.ui.Modal, title="Deposit Credits"):
    amount = discord.ui.TextInput(
        label="Amount to deposit",
        placeholder="Enter amount or 'all' for all wallet credits",
        style=discord.TextStyle.short
    )

    def __init__(self, author_id: int, on_complete):
        super().__init__()
        self.author_id = author_id
        self.on_complete = on_complete

    async def on_submit(self, interaction: discord.Interaction):
        await self.on_complete(self.author_id, interaction, self.amount.value)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(
            view=error_layout("An error occurred. Please try again."),
            ephemeral=True
        )


class WithdrawModal(discord.ui.Modal, title="Withdraw Credits"):
    amount = discord.ui.TextInput(
        label="Amount to withdraw",
        placeholder="Enter amount or 'all' for all bank credits",
        style=discord.TextStyle.short
    )

    def __init__(self, author_id: int, on_complete):
        super().__init__()
        self.author_id = author_id
        self.on_complete = on_complete

    async def on_submit(self, interaction: discord.Interaction):
        await self.on_complete(self.author_id, interaction, self.amount.value)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(
            view=error_layout("An error occurred. Please try again."),
            ephemeral=True
        )


class BankView(discord.ui.LayoutView):
    def __init__(self, wallet: int, bank: int, account_name: str, cog, author_id: int):
        super().__init__()
        self.wallet = wallet
        self.bank = bank
        self.account_name = account_name
        self.cog = cog
        self.author_id = author_id

        # Create buttons with callbacks
        self._deposit_btn = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="deposit",
            custom_id="c6a2d310748b49718ec7f22473cb8565",
        )
        self._deposit_btn.callback = self._deposit_callback

        self._withdraw_btn = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="withdraw",
            custom_id="4a00cf260d12484fac1914089fd204d9",
        )
        self._withdraw_btn.callback = self._withdraw_callback

        container = discord.ui.Container(
            discord.ui.TextDisplay(content=f"# FishR National Bank\naccount name: `{account_name}`\nwallet: `{wallet}`\nbank: `{bank}`\n\n-# bank money cant be stolen by thefts"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.ActionRow(self._deposit_btn, self._withdraw_btn),
            accent_color=discord.Color.green()
        )
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This interaction is not for you.", ephemeral=True)
            return False
        return True

    async def _deposit_callback(self, interaction: discord.Interaction):
        modal = DepositModal(
            author_id=interaction.user.id,
            on_complete=self._handle_deposit
        )
        await interaction.response.send_modal(modal)

    async def _withdraw_callback(self, interaction: discord.Interaction):
        modal = WithdrawModal(
            author_id=interaction.user.id,
            on_complete=self._handle_withdraw
        )
        await interaction.response.send_modal(modal)

    async def _handle_deposit(self, author_id: int, interaction: discord.Interaction, amount: str):
        user_id = author_id
        user = await get_user(user_id)
        if not user:
            await interaction.response.send_message(view=error_layout("Failed to load your data."), ephemeral=True)
            return

        wallet = user["credits"]

        if amount.lower() == "all":
            deposit_amount = wallet
        else:
            try:
                deposit_amount = int(amount)
            except ValueError:
                await interaction.response.send_message(view=error_layout("Invalid amount. Use a number or 'all'."), ephemeral=True)
                return

        if deposit_amount <= 0:
            await interaction.response.send_message(view=error_layout("Amount must be positive."), ephemeral=True)
            return

        if deposit_amount > wallet:
            await interaction.response.send_message(view=error_layout(f"You only have {wallet} credits in your wallet."), ephemeral=True)
            return

        success = await deposit_credits(user_id, deposit_amount)
        if success:
            new_user = await get_user(user_id)
            new_container = bank_layout(new_user["credits"], new_user["bank"], interaction.user.display_name).children[0]
            self.children[0] = new_container
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                view=create_container(
                    title="🏦 Deposit Successful",
                    description=f"Deposited **{deposit_amount:,}** credits into your bank.",
                    color=discord.Color.green().value
                ),
                ephemeral=True
            )
        else:
            await interaction.response.send_message(view=error_layout("Deposit failed. Try again."), ephemeral=True)

    async def _handle_withdraw(self, author_id: int, interaction: discord.Interaction, amount: str):
        user_id = author_id
        user = await get_user(user_id)
        if not user:
            await interaction.response.send_message(view=error_layout("Failed to load your data."), ephemeral=True)
            return

        bank_balance = user["bank"]

        if amount.lower() == "all":
            withdraw_amount = bank_balance
        else:
            try:
                withdraw_amount = int(amount)
            except ValueError:
                await interaction.response.send_message(view=error_layout("Invalid amount. Use a number or 'all'."), ephemeral=True)
                return

        if withdraw_amount <= 0:
            await interaction.response.send_message(view=error_layout("Amount must be positive."), ephemeral=True)
            return

        if withdraw_amount > bank_balance:
            await interaction.response.send_message(view=error_layout(f"You only have {bank_balance:,} credits in your bank."), ephemeral=True)
            return

        success = await withdraw_credits(user_id, withdraw_amount)
        if success:
            new_user = await get_user(user_id)
            new_container = bank_layout(new_user["credits"], new_user["bank"], interaction.user.display_name).children[0]
            self.children[0] = new_container
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                view=create_container(
                    title="💸 Withdrawal Successful",
                    description=f"Withdrew **{withdraw_amount:,}** credits from your bank.",
                    color=discord.Color.green().value
                ),
                ephemeral=True
            )
        else:
            await interaction.response.send_message(view=error_layout("Withdrawal failed. Try again."), ephemeral=True)


class Bank(commands.Cog):
    """Banking and stealing commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="bank", aliases=["vault"])
    async def bank(self, ctx: commands.Context):
        """Display your banking information."""
        user_id = ctx.author.id

        await create_user(user_id)

        user = await get_user(user_id)
        if not user:
            await ctx.send(view=error_layout("Failed to load your data."))
            return

        wallet = user["credits"]
        bank = user["bank"]
        account_name = ctx.author.display_name

        view = BankView(wallet, bank, account_name, self, ctx.author.id)
        await ctx.send(view=view)

    @commands.hybrid_command(name="deposit", aliases=["dep"])
    async def deposit(self, ctx: commands.Context, amount: str):
        """Deposit credits into your bank."""
        user_id = ctx.author.id

        await create_user(user_id)

        user = await get_user(user_id)
        if not user:
            await ctx.send(view=error_layout("Failed to load your data."))
            return

        wallet = user["credits"]

        # Parse amount
        if amount.lower() == "all":
            deposit_amount = wallet
        else:
            try:
                deposit_amount = int(amount)
            except ValueError:
                await ctx.send(view=error_layout("Invalid amount. Use a number or 'all'."))
                return

        if deposit_amount <= 0:
            await ctx.send(view=error_layout("Amount must be positive."))
            return

        if deposit_amount > wallet:
            await ctx.send(view=error_layout(f"You only have {wallet} credits in your wallet."))
            return

        success = await deposit_credits(user_id, deposit_amount)
        if success:
            await ctx.send(
                view=create_container(
                    title="🏦 Deposit Successful",
                    description=f"Deposited **{deposit_amount:,}** credits into your bank.",
                    color=discord.Color.green().value
                )
            )
        else:
            await ctx.send(view=error_layout("Deposit failed. Try again."))

    @commands.hybrid_command(name="withdraw", aliases=["with"])
    async def withdraw(self, ctx: commands.Context, amount: str):
        """Withdraw credits from your bank."""
        user_id = ctx.author.id

        await create_user(user_id)

        user = await get_user(user_id)
        if not user:
            await ctx.send(view=error_layout("Failed to load your data."))
            return

        bank_balance = user["bank"]

        # Parse amount
        if amount.lower() == "all":
            withdraw_amount = bank_balance
        else:
            try:
                withdraw_amount = int(amount)
            except ValueError:
                await ctx.send(view=error_layout("Invalid amount. Use a number or 'all'."))
                return

        if withdraw_amount <= 0:
            await ctx.send(view=error_layout("Amount must be positive."))
            return

        if withdraw_amount > bank_balance:
            await ctx.send(view=error_layout(f"You only have {bank_balance:,} credits in your bank."))
            return

        success = await withdraw_credits(user_id, withdraw_amount)
        if success:
            await ctx.send(
                view=create_container(
                    title="💸 Withdrawal Successful",
                    description=f"Withdrew **{withdraw_amount:,}** credits from your bank.",
                    color=discord.Color.green().value
                )
            )
        else:
            await ctx.send(view=error_layout("Withdrawal failed. Try again."))

    @commands.hybrid_command(name="steal", aliases=["rob", "mug"])
    async def steal(self, ctx: commands.Context, target: discord.Member):
        """Attempt to steal credits from another user."""
        thief_id = ctx.author.id

        if target.id == thief_id:
            await ctx.send(view=error_layout("You cannot steal from yourself."))
            return

        if target.bot:
            await ctx.send(view=error_layout("You cannot steal from bots."))
            return

        await create_user(thief_id)
        await create_user(target.id)

        # Check cooldown
        last_stolen = await get_steal_cooldown(thief_id)
        remaining = get_remaining_cooldown(last_stolen, STEAL_COOLDOWN)
        if remaining > 0:
            await ctx.send(view=steal_cooldown_layout(remaining))
            return

        # Get target's wallet
        target_user = await get_user(target.id)
        if not target_user:
            await ctx.send(view=error_layout("Failed to load target's data."))
            return

        target_wallet = target_user["credits"]

        if target_wallet <= 0:
            await ctx.send(view=steal_empty_wallet_layout())
            return

        # Get thief's wallet for penalty calculation
        thief_user = await get_user(thief_id)
        thief_wallet = thief_user["credits"] if thief_user else 0

        # 50% chance success or failure
        success = random.choice([True, False])

        if success:
            steal_amount = random.randint(int(target_wallet * 0.1), int(target_wallet * 0.35))
            steal_amount = min(steal_amount, target_wallet)

            # Atomically steal from target and give to thief
            async with db.acquire() as conn:
                cursor = await conn.execute(
                    "UPDATE users SET credits = credits - ? WHERE user_id = ? AND credits >= ?",
                    (steal_amount, target.id, steal_amount)
                )
                if cursor.rowcount > 0:
                    await conn.execute(
                        "UPDATE users SET credits = credits + ? WHERE user_id = ?",
                        (steal_amount, thief_id)
                    )
                    await conn.commit()
                    await set_steal_cooldown(thief_id, int(time.time()))
                    await ctx.send(view=steal_success_layout(target.display_name, steal_amount))
                else:
                    await ctx.send(view=steal_empty_wallet_layout())
        else:
            # Thief pays penalty
            penalty = random.randint(int(thief_wallet * 0.05), int(thief_wallet * 0.15))
            penalty = min(penalty, thief_wallet)

            success = await safe_deduct_credits(thief_id, penalty)
            if success:
                await set_steal_cooldown(thief_id, int(time.time()))
                await ctx.send(view=steal_failed_layout(target.display_name, penalty))
            else:
                await ctx.send(view=error_layout("You were caught but had no money to pay as fine."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Bank(bot))