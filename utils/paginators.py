import discord
from typing import List, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class PaginatorView(discord.ui.LayoutView):
    """
    Paginator for Components V2 that embeds navigation buttons in each page.
    """

    def __init__(
        self,
        author_id: int,
        pages: List[discord.ui.Container],
        timeout: float = 120.0
    ):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.pages = pages
        self.current_page = 0
        self.total_pages = len(pages)
        self.message: Optional[discord.Message] = None

        # Build first page with buttons
        self._build_page(0)

    def _build_page(self, page_index: int) -> None:
        """Build a page view with content and navigation buttons."""
        self.clear_items()
        
        content = self.pages[page_index]
        prev_btn = discord.ui.Button(
            label="Previous",
            style=discord.ButtonStyle.secondary,
            emoji="◀️",
            disabled=page_index == 0,
            custom_id=f"prev_{page_index}"
        )
        prev_btn.callback = self._make_prev_callback(page_index)
        
        next_btn = discord.ui.Button(
            label="Next",
            style=discord.ButtonStyle.secondary,
            emoji="▶️",
            disabled=page_index == self.total_pages - 1,
            custom_id=f"next_{page_index}"
        )
        next_btn.callback = self._make_next_callback(page_index)
        
        self.add_item(content)
        self.add_item(discord.ui.ActionRow(prev_btn, next_btn))

    def _make_prev_callback(self, current_page: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.author_id:
                await interaction.response.send_message(
                    "This interaction is not for you.", ephemeral=True
                )
                return
            if current_page > 0:
                self.current_page = current_page - 1
                self._build_page(self.current_page)
                await interaction.response.edit_message(view=self)
        return callback

    def _make_next_callback(self, current_page: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.author_id:
                await interaction.response.send_message(
                    "This interaction is not for you.", ephemeral=True
                )
                return
            if current_page < self.total_pages - 1:
                self.current_page = current_page + 1
                self._build_page(self.current_page)
                await interaction.response.edit_message(view=self)
        return callback

    async def on_timeout(self) -> None:
        """Disable all buttons on timeout."""
        for item in self.children:
            if isinstance(item, discord.ui.ActionRow):
                for child in item.children:
                    if isinstance(child, discord.ui.Button):
                        child.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    async def start(self, ctx) -> discord.Message:
        """Send the initial paginator message."""
        self.message = await ctx.send(view=self)
        return self.message