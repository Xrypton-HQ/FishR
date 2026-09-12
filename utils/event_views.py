"""
Treasure chest event UI components.
Contains buttons, views, and embed builders for treasure chest events.
"""

import asyncio
import logging
import random
from typing import Optional
import discord

from utils.constants import EMOJI_CREDITS, EMOJI_FISH, COLOR_SHOP

logger = logging.getLogger(__name__)


class TreasureChestLayoutView(discord.ui.LayoutView):
    """
    LayoutView for treasure chest spawns with integrated claim button.
    Uses Components V2 for the spawn message and button together.
    """
    
    def __init__(
        self,
        chest_id: int,
        credits: int,
        fish: int,
        timeout: float = 45.0
    ):
        super().__init__(timeout=timeout)
        self.chest_id = chest_id
        self.credits = credits
        self.fish = fish
        self.claimed = False
        self.claimer_id: Optional[int] = None
        self.claimer_name: Optional[str] = None
        self.message: Optional[discord.Message] = None
        self.channel_id: Optional[int] = None
        self._claim_lock = asyncio.Lock()
        self._btn: Optional[discord.ui.Button] = None
    
    async def on_timeout(self) -> None:
        """Disable button and show expired view when timeout occurs."""
        if self._btn:
            self._btn.disabled = True
            self._btn.label = "⌛ Expired"
            self._btn.style = discord.ButtonStyle.secondary
        
        if self.message:
            try:
                await self.message.edit(view=build_treasure_expired_view())
            except discord.NotFound:
                pass
            except Exception as e:
                logger.warning(f"Could not edit expired chest message on timeout: {e}")
    
    @discord.ui.button(
        label="🎁 Claim Reward",
        style=discord.ButtonStyle.success,
        emoji="🎉",
        custom_id="treasure_claim"
    )
    async def claim_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Handle claim button click."""
        user_id = interaction.user.id
        
        async with self._claim_lock:
            if self.claimed:
                await interaction.response.send_message(
                    "❌ This treasure chest has already been claimed!",
                    ephemeral=True
                )
                return
            
            self.claimed = True
            self.claimer_id = user_id
            self.claimer_name = interaction.user.display_name
            button.disabled = True
            button.label = "⏳ Processing..."
            button.style = discord.ButtonStyle.secondary
        
        await interaction.response.defer()
        
        try:
            from utils.treasure import claim_treasure, _active_chests, _active_views, _chest_lock
            success, msg = await claim_treasure(self.chest_id, user_id)
            
            if success:
                button.label = "🎁 Claimed!"
                button.style = discord.ButtonStyle.primary
                
                claimed_view = build_treasure_claimed_view(
                    user=interaction.user,
                    credits=self.credits,
                    fish=self.fish
                )
                
                await interaction.edit_original_response(view=claimed_view)
                
                async with _chest_lock:
                    if self.channel_id:
                        _active_chests.pop(self.channel_id, None)
                    _active_views.pop(self.message.id, None)
                
                self.stop()
            else:
                async with self._claim_lock:
                    self.claimed = False
                button.disabled = True
                button.label = "❌ Gone"
                await interaction.edit_original_response(view=self)
                await interaction.followup.send(f"❌ {msg}", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error processing claim for chest {self.chest_id}: {e}", exc_info=True)
            async with self._claim_lock:
                self.claimed = False
            button.disabled = True
            button.label = "❌ Error"
            await interaction.edit_original_response(view=self)
            await interaction.followup.send("❌ An error occurred while claiming. Please try again later.", ephemeral=True)


def build_treasure_spawn_view(
    chest_id: int,
    credits: int,
    fish: int,
    timeout: float = 45.0
) -> TreasureChestLayoutView:
    """
    Build a LayoutView for treasure chest with spawn message and claim button.
    Returns a TreasureChestLayoutView with the treasure chest appearance and button.
    """
    view = TreasureChestLayoutView(
        chest_id=chest_id,
        credits=credits,
        fish=fish,
        timeout=timeout
    )
    
    sparkles = ["✨", "⭐", "💫", "🔮"]
    sparkle = random.choice(sparkles)
    
    view._btn = discord.ui.Button(
        label="🎁 Claim Reward",
        style=discord.ButtonStyle.success,
        emoji="🎉",
        custom_id="treasure_claim"
    )
    
    components = [
        discord.ui.TextDisplay(content=f"**{sparkle} Treasure Chest Appeared!**"),
        discord.ui.TextDisplay(content=(
            "A mysterious treasure chest appeared during the chaos...\n\n"
            "**Be the FIRST to claim it!**"
        )),
        discord.ui.Separator(),
        discord.ui.TextDisplay(content="*Click the button below before it vanishes!*"),
        discord.ui.ActionRow(view._btn),
    ]
    
    container = discord.ui.Container(
        *components,
        accent_color=0xFFD700
    )
    view.add_item(container)
    
    view._btn.callback = view.claim_button
    
    return view


class TreasureChestView:
    """
    Data holder for treasure chest state.
    Used for type compatibility with existing tracking code.
    Deprecated: Use TreasureChestLayoutView instead.
    """
    
    def __init__(
        self,
        chest_id: int,
        credits: int,
        fish: int,
        timeout: float = 45.0
    ):
        self.chest_id = chest_id
        self.credits = credits
        self.fish = fish
        self.claimed = False
        self.claimer_id: Optional[int] = None
        self.claimer_name: Optional[str] = None
        self.message: Optional[discord.Message] = None
        self.channel_id: Optional[int] = None
        self._claim_lock = asyncio.Lock()


def build_treasure_claimed_view(
    user: discord.User,
    credits: int,
    fish: int
) -> discord.ui.LayoutView:
    """
    Build a LayoutView for successfully claimed treasure.
    """
    view = discord.ui.LayoutView()
    
    components = [
        discord.ui.TextDisplay(content="**🎉 Treasure Claimed!**"),
        discord.ui.TextDisplay(content=(
            f"{user.mention} claimed the treasure chest!\n\n"
            f"**Rewards:**\n"
            f"{EMOJI_CREDITS} **+{credits:,}** credits\n"
            f"{EMOJI_FISH} **+{fish:,}** fish"
        )),
        discord.ui.Separator(),
        discord.ui.TextDisplay(content=f"*Claimed by {user.display_name}*"),
    ]
    
    container = discord.ui.Container(
        *components,
        accent_color=COLOR_SHOP
    )
    view.add_item(container)
    return view


def build_treasure_expired_view() -> discord.ui.LayoutView:
    """
    Build a LayoutView for expired (unclaimed) treasure chest.
    """
    view = discord.ui.LayoutView()
    
    components = [
        discord.ui.TextDisplay(content="**🪙 The Treasure Vanished...**"),
        discord.ui.TextDisplay(content=(
            "Nobody claimed it in time.\n\n"
            "The chest disappeared into the ether..."
        )),
        discord.ui.Separator(),
        discord.ui.TextDisplay(content="*Better luck next time!*"),
    ]
    
    container = discord.ui.Container(
        *components,
        accent_color=0x808080
    )
    view.add_item(container)
    return view