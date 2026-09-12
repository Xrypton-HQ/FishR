import discord
from typing import Any, Callable, Coroutine, Optional
from discord.ui import Button, Select, View, LayoutView
import asyncio
from utils.constants import EMOJI_VERIFY, EMOJI_NO


class CooldownView(View):
    """View with built-in cooldown per user."""

    def __init__(self, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self._cooldowns: dict[int, float] = {}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only command author can interact."""
        if not hasattr(self, "author_id"):
            return True

        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This interaction is not for you.",
                ephemeral=True
            )
            return False

        # Check cooldown
        now = asyncio.get_event_loop().time()
        last = self._cooldowns.get(interaction.user.id, 0)
        if now - last < 1.0:  # 1 second button cooldown
            await interaction.response.send_message(
                "Please wait before clicking again.",
                ephemeral=True
            )
            return False

        self._cooldowns[interaction.user.id] = now
        return True

    async def on_timeout(self) -> None:
        """Disable all buttons on timeout."""
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True


class ConfirmationView(LayoutView):
    """Yes/No confirmation view with optional content container."""

    def __init__(
        self,
        author_id: int,
        on_confirm: Callable[[discord.Interaction], Coroutine[Any, Any, None]],
        on_cancel: Callable[[discord.Interaction], Coroutine[Any, Any, None]],
        content_view: Optional[discord.ui.LayoutView] = None,
        timeout: float = 60.0,
    ):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

        self._confirm_btn = discord.ui.Button(
            label="Confirm", style=discord.ButtonStyle.green, emoji=EMOJI_VERIFY
        )
        self._confirm_btn.callback = self._confirm_callback
        
        self._cancel_btn = discord.ui.Button(
            label="Cancel", style=discord.ButtonStyle.red, emoji=EMOJI_NO
        )
        self._cancel_btn.callback = self._cancel_callback

        components = []
        if content_view is not None and content_view.children:
            for child in content_view.children:
                if isinstance(child, discord.ui.Container):
                    for subchild in child.children:
                        components.append(subchild)
                else:
                    components.append(child)
        
        components.append(discord.ui.ActionRow(self._confirm_btn, self._cancel_btn))
        
        container = discord.ui.Container(*components, accent_color=0)
        self.add_item(container)

    async def _confirm_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This interaction is not for you.", ephemeral=True
            )
            return
        await self.on_confirm(interaction)
        self.stop()

    async def _cancel_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This interaction is not for you.", ephemeral=True
            )
            return
        await self.on_cancel(interaction)
        self.stop()

    async def on_timeout(self):
        self._confirm_btn.disabled = True
        self._cancel_btn.disabled = True


class QuantitySelectView(LayoutView):
    """View with quantity selection buttons and optional title/description."""

    QUANTITIES = [1, 5, 10, 100]

    def __init__(
        self,
        author_id: int,
        max_qty: int,
        on_select: Callable[[int, discord.Interaction], Coroutine[Any, Any, None]],
        title: str = "",
        description: str = "",
        timeout: float = 120.0,
    ):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.max_qty = max_qty
        self.on_select = on_select

        # Add optional container
        if title or description:
             components = []
             if title:
                 components.append(discord.ui.TextDisplay(content=f"**{title}**"))
             if description:
                 components.append(discord.ui.TextDisplay(content=description))
             container = discord.ui.Container(
                 *components,
                 accent_color=0xFFD700,  # gold for shop
             )
             self.add_item(container)

        # Add buttons in ActionRows (required for Components V2)
        row_buttons = []
        for qty in self.QUANTITIES:
            button = Button(
                label=str(qty),
                style=discord.ButtonStyle.secondary,
                disabled=qty > max_qty,
            )
            button.callback = self._make_callback(qty)
            row_buttons.append(button)

        half = max_qty // 2 if max_qty > 0 else 0
        half_btn = Button(
            label="Half",
            style=discord.ButtonStyle.secondary,
            disabled=half == 0,
        )
        half_btn.callback = self._make_callback(half)
        row_buttons.append(half_btn)

        max_btn = Button(
            label="Max",
            style=discord.ButtonStyle.blurple,
            disabled=max_qty == 0,
        )
        max_btn.callback = self._make_callback(max_qty)
        row_buttons.append(max_btn)

        # Place buttons in ActionRows (max 5 per row)
        for i in range(0, len(row_buttons), 5):
            self.add_item(discord.ui.ActionRow(*row_buttons[i:i+5]))

    def _make_callback(
        self, qty: int
    ) -> Callable[[discord.Interaction], Coroutine[Any, Any, None]]:
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.author_id:
                await interaction.response.send_message(
                    "This interaction is not for you.", ephemeral=True
                )
                return
            await self.on_select(qty, interaction)
            self.stop()
        return callback

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True


class ReelingView(LayoutView):
    """View for fishing reel-in button with result callback."""

    def __init__(
        self,
        author_id: int,
        base_amount: int,
        on_reel: Callable[[discord.Interaction, int, int], Coroutine[Any, Any, None]],
        timeout: float = 2.0,
    ):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.base_amount = base_amount
        self.on_reel = on_reel
        self.reeled = False

        self._btn = discord.ui.Button(
            label="Reel It In",
            style=discord.ButtonStyle.primary,
            emoji="🎣",
            custom_id="reel_button"
        )
        self._btn.callback = self._reel_callback

        container = discord.ui.Container(
            discord.ui.TextDisplay(content="**A fish is biting! REEL IT IN!**"),
            discord.ui.ActionRow(self._btn),
            accent_color=0x57F287,
        )
        self.add_item(container)

    async def _reel_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This interaction is not for you.", ephemeral=True
            )
            return

        if self.reeled:
            await interaction.response.send_message(
                "You already reeled in!", ephemeral=True
            )
            return

        self.reeled = True
        self._btn.disabled = True
        await self.on_reel(interaction, self.author_id, self.base_amount)
        self.stop()

    async def on_timeout(self) -> None:
        """Disable button on timeout."""
        if self._btn:
            self._btn.disabled = True
            if self.reeled:
                self._btn.label = "Reeled!"
                self._btn.emoji = EMOJI_VERIFY


# ==================== Job Selection Views ====================

from utils.constants import JOBS, EMOJI_GEMS, EMOJI_CREDITS, COLOR_JOB
from utils.embeds import job_selected_layout, insufficient_gems_layout, fishing_layout
from utils.database import safe_deduct_gems, set_user_job, create_job_entry


class JobSelect(Select):
    """Job selection dropdown."""

    def __init__(
        self,
        author_id: int,
        gems: int,
        current_job: Optional[str],
        on_job_selected: Callable[[str], Coroutine[Any, Any, None]],
    ):
        self.author_id = author_id
        self.gems = gems
        self.current_job = current_job
        self.on_job_selected = on_job_selected

        options = []
        for key, job in JOBS.items():
            owned_marker = f" {EMOJI_VERIFY}" if current_job == key else ""
            options.append(
                discord.SelectOption(
                    label=f"{job['emoji']} {job['name']}{owned_marker}",
                    description=f"Cost: {job['cost']} {EMOJI_GEMS} | Payout: {job['payout']} {EMOJI_CREDITS}",
                    value=key,
                    emoji=job['emoji']
                )
            )

        super().__init__(
            placeholder="Choose a job...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This interaction is not for you.", ephemeral=True
            )
            return

        job_key = self.values[0]
        job = JOBS[job_key]

        if self.gems < job['cost']:
            await interaction.response.edit_message(
                view=insufficient_gems_layout(job['cost'], self.gems)
            )
            return

        # Deduct gems and set job
        success = await safe_deduct_gems(self.author_id, job['cost'])
        if not success:
            await interaction.response.edit_message(
                view=insufficient_gems_layout(job['cost'], self.gems)
            )
            return

        await create_job_entry(self.author_id)
        await set_user_job(self.author_id, job_key)

        await interaction.response.edit_message(
            view=job_selected_layout(job_key)
        )
        await self.on_job_selected(job_key)
        self.view.stop()


class JobSelectView(LayoutView):
    """View containing job selection dropdown with description container."""

    def __init__(
        self,
        author_id: int,
        gems: int,
        current_job: Optional[str],
        on_job_selected: Callable[[str], Coroutine[Any, Any, None]],
        timeout: float = 60.0,
    ):
        super().__init__(timeout=timeout)
        self.author_id = author_id

        # Build description container
        title = "🏢 Employment Center"
        if current_job:
            job_name = JOBS.get(current_job, {}).get("name", current_job.title())
            description = f"You are currently employed as **{job_name}.**\n\nReview the available jobs below and select one.\nRemember: higher paying jobs require more brain power during !work."
        else:
            description = "You are currently unemployed.\n\nReview the available jobs below and select one.\nRemember: higher paying jobs require more brain power during !work."

        select = JobSelect(author_id, gems, current_job, on_job_selected)
        
        container = discord.ui.Container(
            *[
                discord.ui.TextDisplay(content=f"**{title}**"),
                discord.ui.TextDisplay(content=description),
                discord.ui.ActionRow(select),
            ],
            accent_color=COLOR_JOB,
        )
        self.add_item(container)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This interaction is not for you.", ephemeral=True
            )
            return False
        return True