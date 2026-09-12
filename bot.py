import discord
import os
import asyncio
import logging
from typing import Optional
import aiohttp

from discord.ext import commands, tasks
from dotenv import load_dotenv
from itertools import cycle
from colorama import Fore, Style, init

import discord_ios 

from utils.database import db, get_prefixes
from utils.embeds import missing_argument_layout, server_join_layout
from config import TOKEN, PREFIX, GROQ_API_KEY, FISHR_API_URL, FISHR_UPDATE_SECRET


init(autoreset=True)


load_dotenv()

TOKEN = os.getenv("TOKEN") or TOKEN
PREFIX = os.getenv("PREFIX") or PREFIX
FISHR_API_URL = os.getenv("FISHR_API_URL") or FISHR_API_URL
FISHR_UPDATE_SECRET = os.getenv("FISHR_UPDATE_SECRET") or FISHR_UPDATE_SECRET


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] - [%(levelname)s] - [%(name)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("fishr.log", mode="a"),
        logging.StreamHandler(),
    ]
)

logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("discord.http").setLevel(logging.WARNING)
logging.getLogger("discord.gateway").setLevel(logging.WARNING)
logging.getLogger("discord.client").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

logger = logging.getLogger("FishR")


intents = discord.Intents.default()
intents.members = True
intents.guilds = True


class FishRBot(commands.Bot):

    def __init__(self):
        async def get_prefix(bot, message):
            prefixes = [PREFIX]
            if message.guild:
                custom_prefixes = await get_prefixes(message.guild.id)
                if custom_prefixes:
                    prefixes.extend(custom_prefixes)
            return commands.when_mentioned_or(*prefixes)(bot, message)

        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            case_insensitive=True,
            help_command=None,
            allowed_mentions=discord.AllowedMentions.none()
        )
        self.status_messages = cycle([])
        
        FishRBot._instance = self

    
    _instance: Optional['FishRBot'] = None

    async def setup_hook(self):

        await db.connect()
        logger.info("Database connected")

        cogs = [
            "cogs.owner",
            "cogs.fishing",
            "cogs.economy",
            "cogs.shop",
            "cogs.market",
            "cogs.jobs",
            "cogs.bank",
            "cogs.ai_chat",
            "cogs.vape",
            "cogs.help",
            "cogs.events",
            "cogs.get",
            "cogs.prefix",
            "cogs.antinuke",
            "cogs.afk",
            "cogs.giveaway",
            "cogs.welcome",
            "cogs.fun",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load {cog}: {e}", exc_info=True)

        self.synced = await self.tree.sync()
        logger.info(f"Synced {len(self.synced)} slash commands")

    async def on_ready(self):

        guilds = len(self.guilds)
        users = sum(g.member_count or 0 for g in self.guilds)
        slash_cmds = len(self.synced)
        prefix_cmds = len(self.commands)

        logger.info(f"FishR is ready! Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {guilds} guilds with {users:,} users")
        logger.info(f"Loaded {prefix_cmds} prefix commands, {slash_cmds} slash commands")

        banner = f"""
{Fore.CYAN}
██████╗ ██╗███████╗██╗  ██╗██████╗
██╔════╝ ██║██╔════╝██║  ██║██╔══██╗
████╗  ██║███████╗███████║██████╔╝
██╔══╝  ██║╚════██║██╔══██║██╔══██╗
██║     ██║███████║██║  ██║██║  ██║
╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝
{Style.RESET_ALL}
"""

        print(banner)

        print(f"{Fore.GREEN}Logged in as:{Style.RESET_ALL} {self.user}")
        print(f"{Fore.GREEN}Connected to:{Style.RESET_ALL} {guilds} Guilds")
        print(f"{Fore.GREEN}Watching over:{Style.RESET_ALL} {users:,} Users")
        print(f"{Fore.GREEN}Synced:{Style.RESET_ALL} {slash_cmds} Slash Commands")
        print(f"{Fore.GREEN}Loaded:{Style.RESET_ALL} {prefix_cmds} Prefix Commands")
        print(f"{Fore.MAGENTA}{'-' * 45}{Style.RESET_ALL}")

        
        statuses = [
            f"{guilds} Guilds • {users:,} Users",
            f"chilling inside {guilds} peoples servers",
            f"{users:,} users LOVE me!!",
            f"did you know i have {slash_cmds} slash commands?"
        ]

        self.status_messages = cycle(statuses)

        if not self.rotate_status.is_running():
            self.rotate_status.start()

    @tasks.loop(minutes=1)
    async def rotate_status(self):

        status = next(self.status_messages)

        
        await self.change_presence(
            activity=discord.CustomActivity(name=status)
        )

    @rotate_status.before_loop
    async def before_rotate_status(self):
        await self.wait_until_ready()

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandNotFound):
            return
        logger.info(f"Command error in {ctx.command}: {error}")
        if isinstance(error, commands.MissingRequiredArgument):
            param = error.param
            command = ctx.command
            command_name = command.name
            command_description = command.help or "No description available."
            aliases = list(command.aliases)
            module = command.cog.qualified_name if command.cog else "General"

            example = self._build_command_example(command)

            await ctx.send(
                view=missing_argument_layout(
                    argument=param.name,
                    command_name=command_name,
                    command_description=command_description,
                    aliases=aliases,
                    example=example,
                    module=module,
                ),
                delete_after=10,
            )
            return

        if isinstance(error, commands.BadArgument):
            command = ctx.command
            example = self._build_command_example(command)

            await ctx.send(
                view=missing_argument_layout(
                    argument="invalid argument",
                    command_name=command.name,
                    command_description=command.help or "No description available.",
                    aliases=list(command.aliases),
                    example=example,
                    module=command.cog.qualified_name if command.cog else "General",
                ),
                delete_after=10,
            )
            return

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.CheckFailure):
            return

        logger.error(f"Unhandled command error: {error}", exc_info=True)

    def _build_command_example(self, command: commands.Command) -> str:
        parts = [f".{command.name}"]

        for param_name, param in command.params.items():
            if param_name in ("self", "ctx"):
                continue

            is_optional = param.default is not param.empty
            if is_optional:
                parts.append(f"({param_name})")
            else:
                parts.append(f"[{param_name}]")

        return " ".join(parts)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        class WelcomeComponents(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.Section(
                    discord.ui.TextDisplay(content="# Welcome to FishR\nyou now have **fishr** in your server! the most powerful economy bot with over 25+ commands\nmy default prefix is `.` and you can run `.help` to get started"),
                    accessory=discord.ui.Thumbnail(
                        media="https://images-ext-1.discordapp.net/external/OTOkf7-uAxfNgvfLogO6BaGitU25fO6X_Era-nmdRII/%3Fsize%3D1024/https/cdn.discordapp.com/avatars/1447869784937988201/19baf93704a66d4fccbfb411f533ee4a.png?format=webp&quality=lossless&width=420&height=420",
                    ),
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.Section(
                    discord.ui.TextDisplay(content="-# the support server is the best place to get help ->"),
                    accessory=discord.ui.Button(
                        url="https://discord.gg/YWG5ryEZGS",
                        style=discord.ButtonStyle.link,
                        label="support",
                    ),
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.ActionRow(
                    discord.ui.Button(
                        url="https://ptb.discord.com/oauth2/authorize?client_id=1447869784937988201",
                        style=discord.ButtonStyle.link,
                        label="Invite",
                    ),
                    discord.ui.Button(
                        url="https://fishr.ct.ws",
                        style=discord.ButtonStyle.link,
                        label="Website",
                    ),
                ),
            )

        class LeaveComponents(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content="i have left this server due to it not having more then **5** members\n\nif you think this was a mistake please contact support"),
                discord.ui.ActionRow(
                    discord.ui.Button(
                        url="https://discord.gg/YWG5ryEZGS",
                        style=discord.ButtonStyle.link,
                        label="support",
                    ),
                ),
            )

        if guild.member_count < 5:
            channel = guild.system_channel
            if channel is None:
                channel = next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)

            if channel:
                try:
                    await channel.send(view=LeaveComponents())
                except discord.Forbidden:
                    pass

            logger.info(f"fishr left server: {guild.name} (id: {guild.id}) - under 5 members")
            await guild.leave()
            return

        channel = guild.system_channel
        if channel is None:
            channel = next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)

        if channel:
            try:
                await channel.send(view=WelcomeComponents())
            except discord.Forbidden:
                pass

        invite = await guild.text_channels[0].create_invite(max_uses=0) if guild.text_channels else None
        invite_link = invite.url if invite else "No invite available"
        logger.info(f"fishr joined this server: {guild.name} (id: {guild.id}) | invite: {invite_link}")

        # Send notification to bot logs channel
        bot_logs_channel_id = 1505494735454994502
        bot_logs_channel = self.get_channel(bot_logs_channel_id)
        if bot_logs_channel and invite:
            try:
                await bot_logs_channel.send(view=server_join_layout(guild, invite.url))
            except discord.Forbidden:
                pass

async def main():

    logger.info("Starting FishR bot...")
    bot = FishRBot()

    try:
        async with bot:
            await bot.start(TOKEN)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received — shutting down cleanly.")


if __name__ == "__main__":
    asyncio.run(main())