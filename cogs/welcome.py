import discord
from discord.ext import commands
from utils.database import db
import logging

from cogs.help import send_subcommand_help

logger = logging.getLogger(__name__)


def replace_variables(text: str, member: discord.Member) -> str:
    """Replace welcome message variables."""
    if not text:
        return text
    guild = member.guild
    replacements = {
        "{user.mention}": member.mention,
        "{user.name}": member.display_name,
        "{server.name}": guild.name,
        "{member.count}": str(guild.member_count),
        "{server.banner}": guild.banner.url if guild.banner else "",
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text


class WelcomeDefault(discord.ui.LayoutView):
    container1 = discord.ui.Container(
        discord.ui.TextDisplay(content="# 👋 {user.mention}\nWelcome to {server.name} {user.mention}! the server now has {member.count}"),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        discord.ui.MediaGallery(
            discord.MediaGalleryItem(media="{server.banner}"),
        ),
    )


class Welcome(commands.Cog):
    """Customizable welcome system with text and embed support."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_welcome_config(self, guild_id: int):
        return await db.fetch_one(
            "SELECT * FROM welcome_config WHERE guild_id = ?", guild_id
        )

    async def set_channel(self, guild_id: int, channel_id: int | None):
        await db.execute(
            """INSERT OR REPLACE INTO welcome_config 
               (guild_id, channel_id, enabled, embed_mode, title, description, image_url)
               VALUES (?, ?, COALESCE((SELECT enabled FROM welcome_config WHERE guild_id=?), 1),
                       COALESCE((SELECT embed_mode FROM welcome_config WHERE guild_id=?), 0),
                       (SELECT title FROM welcome_config WHERE guild_id=?),
                       (SELECT description FROM welcome_config WHERE guild_id=?),
                       (SELECT image_url FROM welcome_config WHERE guild_id=?))""",
            guild_id, channel_id, guild_id, guild_id, guild_id, guild_id, guild_id
        )

    async def update_config(self, guild_id: int, **kwargs):
        config = await self.get_welcome_config(guild_id)
        if config:
            enabled = config["enabled"]
            embed_mode = config["embed_mode"]
            title = kwargs.get("title", config["title"])
            description = kwargs.get("description", config["description"])
            image_url = kwargs.get("image_url", config["image_url"])
            channel_id = config["channel_id"]
        else:
            enabled = 1
            embed_mode = 0
            title = kwargs.get("title")
            description = kwargs.get("description")
            image_url = kwargs.get("image_url")
            channel_id = None

        await db.execute(
            """INSERT OR REPLACE INTO welcome_config 
               (guild_id, channel_id, enabled, embed_mode, title, description, image_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            guild_id, channel_id, enabled, embed_mode, title, description, image_url
        )

    async def send_welcome(self, member: discord.Member, force: bool = False):
        config = await self.get_welcome_config(member.guild.id)
        if not config:
            return
        if not force and not config["enabled"]:
            return
        channel_id = config["channel_id"]
        if not channel_id:
            return
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        try:
            if config["embed_mode"]:
                title = replace_variables(config["title"] or "# 👋 Welcome {user.mention}", member)
                desc = replace_variables(config["description"] or "Welcome to {server.name}!", member)
                image = replace_variables(config.get("image_url") or "", member) if config.get("image_url") else None
                if image == "":
                    image = None

                class CustomWelcome(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=title + "\n" + desc),
                        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    )
                    if image:
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content=title + "\n" + desc),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.MediaGallery(discord.MediaGalleryItem(media=image)),
                        )

                await channel.send(view=CustomWelcome())
            else:
                content = replace_variables("# 👋 {user.mention}\nWelcome to {server.name} {user.mention}! the server now has {member.count} members.", member)
                banner_url = member.guild.banner.url if member.guild.banner else None
                class DefaultWelcome(discord.ui.LayoutView):
                    if banner_url:
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content=content),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.MediaGallery(
                                discord.MediaGalleryItem(media=banner_url),
                            ),
                        )
                    else:
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content=content),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                        )
                await channel.send(view=DefaultWelcome())
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")

    @commands.hybrid_group(name="greet", invoke_without_command=True, description="Welcome system commands")
    async def greet(self, ctx: commands.Context):
        if ctx.interaction:
            await ctx.send_help(ctx.command)
        else:
            await send_subcommand_help(ctx, ctx.command)

    @greet.group(name="channel")
    async def greet_channel(self, ctx: commands.Context):
        pass

    @greet_channel.command(name="set", description="Set the welcome channel")
    @commands.has_permissions(manage_guild=True)
    async def channel_set(self, ctx: commands.Context, channel: discord.TextChannel):
        await self.set_channel(ctx.guild.id, channel.id)
        embed = discord.Embed(title="Welcome Channel Set", description=f"Welcome messages will now be sent to {channel.mention}.", color=0x57F287)
        await ctx.send(embed=embed)

    @greet_channel.command(name="remove", description="Remove the welcome channel")
    @commands.has_permissions(manage_guild=True)
    async def channel_remove(self, ctx: commands.Context):
        await self.set_channel(ctx.guild.id, None)
        embed = discord.Embed(title="Welcome Channel Removed", description="Welcome channel has been removed.", color=0xED4245)
        await ctx.send(embed=embed)

    @greet.group(name="embed")
    async def greet_embed(self, ctx: commands.Context):
        pass

    @greet_embed.command(name="toggle", description="Toggle embed mode on/off")
    @commands.has_permissions(manage_guild=True)
    async def embed_toggle(self, ctx: commands.Context):
        config = await self.get_welcome_config(ctx.guild.id)
        current = config["embed_mode"] if config else 0
        new_mode = 0 if current else 1
        await self.update_config(ctx.guild.id, embed_mode=new_mode)
        status = "enabled" if new_mode else "disabled"
        embed = discord.Embed(title="Embed Mode Toggled", description=f"Embed mode is now {status}.", color=0x57F287)
        await ctx.send(embed=embed)

    @greet_embed.command(name="title", description="Set the embed title")
    @commands.has_permissions(manage_guild=True)
    async def embed_title(self, ctx: commands.Context, *, title: str):
        await self.update_config(ctx.guild.id, title=title)
        embed = discord.Embed(title="Embed Title Set", description=f"Title set to: {title}", color=0x57F287)
        await ctx.send(embed=embed)

    @greet_embed.command(name="description", description="Set the embed description")
    @commands.has_permissions(manage_guild=True)
    async def embed_description(self, ctx: commands.Context, *, description: str):
        await self.update_config(ctx.guild.id, description=description)
        embed = discord.Embed(title="Embed Description Set", description="Description updated.", color=0x57F287)
        await ctx.send(embed=embed)

    @greet_embed.command(name="image", description="Set the embed image URL")
    @commands.has_permissions(manage_guild=True)
    async def embed_image(self, ctx: commands.Context, url: str):
        if not url.startswith(("http://", "https://")):
            await ctx.send("Invalid URL. Must start with http:// or https://")
            return
        await self.update_config(ctx.guild.id, image_url=url)
        embed = discord.Embed(title="Embed Image Set", description="Image URL updated.", color=0x57F287)
        await ctx.send(embed=embed)

    @greet.command(name="toggle", description="Enable or disable the welcome system")
    @commands.has_permissions(manage_guild=True)
    async def greet_toggle(self, ctx: commands.Context):
        config = await self.get_welcome_config(ctx.guild.id)
        current = config["enabled"] if config else 1
        new_enabled = 0 if current else 1
        await db.execute(
            "UPDATE welcome_config SET enabled = ? WHERE guild_id = ?",
            new_enabled, ctx.guild.id
        )
        if not await self.get_welcome_config(ctx.guild.id):
            await self.update_config(ctx.guild.id)
            await db.execute("UPDATE welcome_config SET enabled = ? WHERE guild_id = ?", new_enabled, ctx.guild.id)
        status = "enabled" if new_enabled else "disabled"
        embed = discord.Embed(title="Welcome Module Toggled", description=f"Welcome system is now {status}.", color=0x57F287)
        await ctx.send(embed=embed)

    @greet.command(name="reset", description="Reset all welcome settings to defaults")
    @commands.has_permissions(manage_guild=True)
    async def greet_reset(self, ctx: commands.Context):
        await db.execute("DELETE FROM welcome_config WHERE guild_id = ?", ctx.guild.id)
        embed = discord.Embed(title="Welcome Settings Reset", description="All welcome settings have been reset to defaults.", color=0x57F287)
        await ctx.send(embed=embed)

    @greet.command(name="test", description="Test the current welcome configuration by sending it to the welcome channel")
    @commands.has_permissions(manage_guild=True)
    async def greet_test(self, ctx: commands.Context):
        config = await self.get_welcome_config(ctx.guild.id)
        if not config or not config["channel_id"]:
            embed = discord.Embed(title="No Welcome Channel", description="Please set a welcome channel first using `/greet channel set`.", color=0xED4245)
            await ctx.send(embed=embed)
            return
        channel = self.bot.get_channel(config["channel_id"])
        if not channel:
            embed = discord.Embed(title="Channel Not Found", description="The configured welcome channel could not be found.", color=0xED4245)
            await ctx.send(embed=embed)
            return
        await self.send_welcome(ctx.author, force=True)
        embed = discord.Embed(title="Welcome Test Sent", description=f"A test welcome message has been sent to {channel.mention}.", color=0x57F287)
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        await self.send_welcome(member)



async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
