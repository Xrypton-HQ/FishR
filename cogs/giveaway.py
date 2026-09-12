import discord
import random
import asyncio
import time
import logging
from discord import MediaGalleryItem
from discord.ext import commands
from typing import Optional, Callable, Coroutine, Any

from utils.database import (
    create_giveaway, get_giveaway_by_message, get_giveaway_by_id,
    get_latest_giveaway, get_all_active_giveaways, add_giveaway_entry,
    remove_giveaway_entry, get_giveaway_entries, get_entry_count,
    end_giveaway, is_user_in_giveaway, is_user_blacklisted, add_to_blacklist,
    remove_from_blacklist, get_blacklist, get_giveaway_channel, set_giveaway_channel
)
from utils.embeds import error_layout
from utils.constants import COLOR_SUCCESS, COLOR_ERROR

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "https://files.catbox.moe/khkd8q.png"


def parse_duration(duration_str: str) -> int:
    """Parse duration string like '1h30m' or '30m' or '45s' into seconds."""
    seconds = 0
    i = 0
    while i < len(duration_str):
        num = ""
        while i < len(duration_str) and duration_str[i].isdigit():
            num += duration_str[i]
            i += 1
        if i < len(duration_str):
            unit = duration_str[i].lower()
            if unit == 's':
                seconds += int(num)
            elif unit == 'm':
                seconds += int(num) * 60
            elif unit == 'h':
                seconds += int(num) * 3600
            i += 1
    return seconds


class GiveawayView(discord.ui.LayoutView):
    """UI view for giveaway interaction with Join/Leave/Entries buttons."""
    
    def __init__(self, giveaway_id: int, prize: str, winners: int,
                 ends_at: int, entries: int, server_icon: str, image: str = DEFAULT_IMAGE):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.prize = prize
        self.winners = winners
        self.ends_at = ends_at
        self.server_icon = server_icon
        self.image = image
        
        self._join_btn = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Join",
            custom_id=f"giveaway_join_{giveaway_id}"
        )
        self._join_btn.callback = self._join_callback
        
        self._leave_btn = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label="Leave",
            custom_id=f"giveaway_leave_{giveaway_id}"
        )
        self._leave_btn.callback = self._leave_callback
        
        self._entries_btn = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Entries",
            custom_id=f"giveaway_entries_{giveaway_id}"
        )
        self._entries_btn.callback = self._entries_callback
        
        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(content=f"# {prize}\n\n> winners: `{winners}`\n> entries: `{entries}`\n> ends: <t:{ends_at}:R>"),
                accessory=discord.ui.Thumbnail(media=server_icon),
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.MediaGallery(
                MediaGalleryItem(media=image),
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.ActionRow(
                self._join_btn,
                self._leave_btn,
                self._entries_btn,
            ),
        )
        self.add_item(container)
    
    async def _join_callback(self, interaction: discord.Interaction):
        """Handle join button clicks."""
        if await is_user_blacklisted(interaction.user.id):
            await interaction.response.send_message(
                "You are blacklisted from entering giveaways!", ephemeral=True
            )
            return

        # Defer initial response to allow editing the original message later
        await interaction.response.defer()

        try:
            entry_added = await add_giveaway_entry(self.giveaway_id, interaction.user.id)
            if entry_added:
                updated_entries = await get_giveaway_entries(self.giveaway_id)
                updated_count = len(updated_entries)
                updated_view = GiveawayView(
                    giveaway_id=self.giveaway_id,
                    prize=self.prize,
                    winners=self.winners,
                    ends_at=self.ends_at,
                    entries=updated_count,
                    server_icon=self.server_icon,
                    image=self.image
                )
                await interaction.edit_original_response(view=updated_view)
                await interaction.followup.send("You have entered the giveaway!", ephemeral=True)
            else:
                await interaction.followup.send(
                    "You are already entered in this giveaway!", ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error adding entry: {e}")
            await interaction.followup.send(
                "An error occurred while entering the giveaway.", ephemeral=True
            )
            return
        
        try:
            entry_added = await add_giveaway_entry(self.giveaway_id, interaction.user.id)
            if entry_added:
                await interaction.response.send_message(
                    "You have entered the giveaway!", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "You are already entered in this giveaway!", ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error adding entry: {e}")
            await interaction.response.send_message(
                "An error occurred while entering the giveaway.", ephemeral=True
            )
    
    async def _leave_callback(self, interaction: discord.Interaction):
        """Handle leave button clicks."""
        try:
            removed = await remove_giveaway_entry(self.giveaway_id, interaction.user.id)
            if removed:
                await interaction.response.send_message(
                    "You have left the giveaway.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "You were not entered in this giveaway.", ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error removing entry: {e}")
            await interaction.response.send_message(
                "An error occurred while leaving the giveaway.", ephemeral=True
            )
    
    async def _entries_callback(self, interaction: discord.Interaction):
        """Handle entries button clicks."""
        entries = await get_giveaway_entries(self.giveaway_id)
        count = len(entries)
        
        if not entries:
            view = discord.ui.LayoutView()
            view.add_item(discord.ui.Container(
                discord.ui.TextDisplay(content="**📊 Giveaway Entries**"),
                discord.ui.TextDisplay(content="No entries yet."),
                accent_color=COLOR_SUCCESS
            ))
            await interaction.response.send_message(view=view, ephemeral=True)
            return
        
        user_mentions = []
        for user_id in entries[:20]:
            user_mentions.append(f"<@{user_id}>")
        
        more_text = f"\n... and {count - 20} more" if count > 20 else ""
        entries_text = "\n".join(user_mentions) + more_text
        
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(content=f"**📊 Giveaway Entries ({count})**"),
            discord.ui.TextDisplay(content=entries_text),
            accent_color=COLOR_SUCCESS
        ))
        await interaction.response.send_message(view=view, ephemeral=True)


class Giveaway(commands.Cog):
    """Giveaway commands and management."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ending_tasks: dict[int, asyncio.Task] = {}
    
    async def _pick_winners(self, entries: list[int], count: int) -> list[int]:
        """Pick random winners from entries."""
        if len(entries) <= count:
            return entries
        return random.sample(entries, count)
    
    async def _end_giveaway(self, giveaway, interaction: Optional[discord.Interaction] = None):
        """End a giveaway and select winners."""
        giveaway_id = giveaway["id"]
        channel_id = giveaway["channel_id"]
        message_id = giveaway["message_id"]
        prize = giveaway["prize"]
        winners_needed = giveaway["winners"]
        
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(channel_id)
            
            message = await channel.fetch_message(message_id)
            
            entries = await get_giveaway_entries(giveaway_id)
            
            if entries:
                winners = await self._pick_winners(entries, min(winners_needed, len(entries)))
                await end_giveaway(giveaway_id, winners)
                
                winner_mentions = ", ".join(f"<@{w}>" for w in winners)
                ended_view = discord.ui.LayoutView()
                ended_view.add_item(discord.ui.Container(
                    discord.ui.TextDisplay(content=f"## 🎉 Giveaway Ended!\n**Prize:** {prize}\n**Winners:** {winner_mentions}")
                ))
                await message.edit(view=ended_view)
                
                for winner_id in winners:
                    try:
                        user = self.bot.get_user(winner_id)
                        if user:
                            await user.send(
                                f"🎉 Congratulations! You won the **{prize}** giveaway on **{channel.guild.name}**!"
                            )
                    except Exception as e:
                        logger.warning(f"Could not DM winner {winner_id}: {e}")
            else:
                await end_giveaway(giveaway_id, [])
                ended_view = discord.ui.LayoutView()
                ended_view.add_item(discord.ui.Container(
                    discord.ui.TextDisplay(content=f"## 🎉 Giveaway Ended!\n**Prize:** {prize}\n**No valid entries.**")
                ))
                await message.edit(view=ended_view)
            
            if interaction:
                view = discord.ui.LayoutView()
                view.add_item(discord.ui.Container(
                    discord.ui.TextDisplay(content="**✅ Giveaway Ended**"),
                    discord.ui.TextDisplay(content=f"Giveaway for **{prize}** has ended!"),
                    accent_color=COLOR_SUCCESS
                ))
                await interaction.response.send_message(view=view, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error ending giveaway {giveaway_id}: {e}", exc_info=True)
    
    @commands.hybrid_group(name="giveaway", invoke_without_command=True)
    async def giveaway(self, ctx: commands.Context):
        """Giveaway management commands."""
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(content="# 🎁 Giveaway Commands"),
            discord.ui.TextDisplay(content=(
                "`.giveaway start [winners] [duration] [prize] (image)` - Start a giveaway\n"
                "`.giveaway end [giveaway]` - End a giveaway\n"
                "`.giveaway blacklist [user]` - Blacklist a user\n"
                "`.giveaway unblacklist [user]` - Remove from blacklist\n"
                "`.giveaway listblacklist` - Show blacklisted users\n"
                "`.giveaway reroll` - Reroll winners\n"
                "`.giveaway channel` - Set default giveaway channel"
            )),
            accent_color=COLOR_SUCCESS
        ))
        await ctx.send(view=view)
    
    @giveaway.command(name="start")
    async def start(self, ctx: commands.Context, winners: int, duration: str,
                    prize: str, image: Optional[str] = DEFAULT_IMAGE):
        """Start a giveaway with specified winners, duration, and prize."""
        if winners < 1:
            await ctx.send(view=error_layout("Winners must be at least 1."))
            return
        
        duration_seconds = parse_duration(duration)
        if duration_seconds <= 0:
            await ctx.send(view=error_layout("Invalid duration format. Use format like '1h30m' or '30m'."))
            return
        
        channel = ctx.channel
        guild = ctx.guild
        
        starts_at = int(time.time())
        ends_at = starts_at + duration_seconds
        
        server_icon = guild.icon.url if guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png"
        
        msg = await ctx.send(view=GiveawayView(
            giveaway_id=0,
            prize=prize,
            winners=winners,
            ends_at=ends_at,
            entries=0,
            server_icon=server_icon,
            image=image
        ))
        
        giveaway_id = await create_giveaway(
            message_id=msg.id,
            channel_id=channel.id,
            guild_id=guild.id,
            prize=prize,
            winners=winners,
            duration=duration_seconds,
            started_at=starts_at,
            ends_at=ends_at,
            image=image
        )
        
        view = GiveawayView(
            giveaway_id=giveaway_id,
            prize=prize,
            winners=winners,
            ends_at=ends_at,
            entries=0,
            server_icon=server_icon,
            image=image
        )
        
        await msg.edit(view=view)
        
        self.bot.loop.create_task(self._schedule_end(giveaway_id, ends_at))
    
    async def _schedule_end(self, giveaway_id: int, ends_at: int):
        """Schedule the end of a giveaway."""
        now = int(time.time())
        wait_time = max(0, ends_at - now)
        await asyncio.sleep(wait_time)
        
        try:
            giveaway = await get_giveaway_by_id(giveaway_id)
            if giveaway and not giveaway["ended"]:
                await self._end_giveaway(giveaway)
        except Exception as e:
            logger.error(f"Error in scheduled giveaway end: {e}")

    async def _reattach_views(self):
        """Re-attach persistent views for active giveaways after restart."""
        try:
            active = await get_all_active_giveaways()
            for g in active:
                try:
                    channel = self.bot.get_channel(g["channel_id"])
                    if channel is None:
                        channel = await self.bot.fetch_channel(g["channel_id"])
                    msg = await channel.fetch_message(g["message_id"])
                    entries = await get_giveaway_entries(g["id"])
                    count = len(entries)
                    guild = getattr(channel, "guild", None)
                    server_icon = guild.icon.url if guild and guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png"
                    view = GiveawayView(
                        giveaway_id=g["id"],
                        prize=g["prize"],
                        winners=g["winners"],
                        ends_at=g["ends_at"],
                        entries=count,
                        server_icon=server_icon,
                        image=g.get("image") or DEFAULT_IMAGE
                    )
                    self.bot.add_view(view, message_id=msg.id)
                    if g["id"] not in self._ending_tasks:
                        self.bot.loop.create_task(self._schedule_end(g["id"], g["ends_at"]))
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"Failed to reattach giveaway views: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        await self._reattach_views()
    
    @giveaway.command(name="end")
    async def end_cmd(self, ctx: commands.Context, giveaway_id: Optional[int] = None):
        """End a giveaway. Defaults to latest giveaway if not specified."""
        if giveaway_id:
            giveaway = await get_giveaway_by_id(giveaway_id)
        else:
            giveaway = await get_latest_giveaway(ctx.guild.id)
        
        if not giveaway:
            await ctx.send(view=error_layout("No active giveaway found."))
            return
        
        if giveaway["ended"]:
            await ctx.send(view=error_layout("This giveaway has already ended."))
            return
        
        await self._end_giveaway(giveaway)
    
    @giveaway.command(name="blacklist")
    async def blacklist_cmd(self, ctx: commands.Context, user: discord.Member):
        """Blacklist a user from entering giveaways."""
        await add_to_blacklist(user.id)
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(content="**✅ User Blacklisted**"),
            discord.ui.TextDisplay(content=f"{user.mention} can no longer enter giveaways."),
            accent_color=COLOR_SUCCESS
        ))
        await ctx.send(view=view)
    
    @giveaway.command(name="unblacklist")
    async def unblacklist_cmd(self, ctx: commands.Context, user: discord.Member):
        """Remove a user from the giveaway blacklist."""
        removed = await remove_from_blacklist(user.id)
        if removed:
            view = discord.ui.LayoutView()
            view.add_item(discord.ui.Container(
                discord.ui.TextDisplay(content="**✅ User Unblacklisted**"),
                discord.ui.TextDisplay(content=f"{user.mention} can now enter giveaways."),
                accent_color=COLOR_SUCCESS
            ))
        else:
            view = discord.ui.LayoutView()
            view.add_item(discord.ui.Container(
                discord.ui.TextDisplay(content="**ℹ️ Not Blacklisted**"),
                discord.ui.TextDisplay(content=f"{user.mention} is not blacklisted."),
                accent_color=COLOR_SUCCESS
            ))
        await ctx.send(view=view)
    
    @giveaway.command(name="listblacklist")
    async def listblacklist_cmd(self, ctx: commands.Context):
        """Show all blacklisted users."""
        blacklisted = await get_blacklist()
        if not blacklisted:
            view = discord.ui.LayoutView()
            view.add_item(discord.ui.Container(
                discord.ui.TextDisplay(content="**📋 Blacklist Empty**"),
                discord.ui.TextDisplay(content="No users are blacklisted from giveaways."),
                accent_color=COLOR_SUCCESS
            ))
        else:
            user_mentions = ", ".join(f"<@{uid}>" for uid in blacklisted[:20])
            view = discord.ui.LayoutView()
            view.add_item(discord.ui.Container(
                discord.ui.TextDisplay(content="**📋 Blacklisted Users**"),
                discord.ui.TextDisplay(content=user_mentions + 
                    ("..." if len(blacklisted) > 20 else "")),
                accent_color=COLOR_SUCCESS
            ))
        await ctx.send(view=view)
    
    @giveaway.command(name="reroll")
    async def reroll_cmd(self, ctx: commands.Context):
        """Reroll winners for the latest giveaway."""
        giveaway = await get_latest_giveaway(ctx.guild.id)
        
        if not giveaway:
            await ctx.send(view=error_layout("No recent giveaway found."))
            return
        
        entries = await get_giveaway_entries(giveaway["id"])
        
        if not entries:
            await ctx.send(view=error_layout("No entries in this giveaway to reroll."))
            return
        
        winners = await self._pick_winners(entries, min(giveaway["winners"], len(entries)))
        
        view = discord.ui.LayoutView()
        winner_mentions = ", ".join(f"<@{w}>" for w in winners)
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(content="**🎉 Rerolled Winners**"),
            discord.ui.TextDisplay(content=f"Prize: **{giveaway['prize']}**\nWinners: {winner_mentions}"),
            accent_color=COLOR_SUCCESS
        ))
        await ctx.send(view=view)
    
    @giveaway.command(name="channel")
    async def channel_cmd(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set the default giveaway channel for this server."""
        target_channel = channel or ctx.channel
        await set_giveaway_channel(ctx.guild.id, target_channel.id)
        
        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(content="**✅ Default Channel Set**"),
            discord.ui.TextDisplay(content=f"Giveaways will default to {target_channel.mention}"),
            accent_color=COLOR_SUCCESS
        ))
        await ctx.send(view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaway(bot))