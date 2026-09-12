import discord
from discord.ext import commands
import aiosqlite
import time
from utils.embeds import error_layout
from utils.constants import COLOR_SUCCESS, COLOR_ERROR
from typing import Optional

DB_PATH = "database.db"

class AFK(commands.Cog):
    """AFK system with presets, nick changes, and mention notifications."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS afk_status (
                    user_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    status TEXT,
                    timestamp INTEGER,
                    preset TEXT
                );
                CREATE TABLE IF NOT EXISTS afk_presets (
                    user_id INTEGER,
                    name TEXT,
                    status TEXT,
                    PRIMARY KEY (user_id, name)
                );
            """)
            await db.commit()

    async def _set_afk(self, member: discord.Member, status: str, preset: Optional[str] = None):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO afk_status (user_id, guild_id, status, timestamp, preset) VALUES (?, ?, ?, ?, ?)",
                (member.id, member.guild.id, status, int(time.time()), preset)
            )
            await db.commit()

        # Nickname handling
        try:
            if not member.nick or not member.nick.startswith("[AFK]"):
                original = member.nick or member.name
                new_nick = f"[AFK] {original}"[:32]
                await member.edit(nick=new_nick, reason="AFK status")
        except discord.Forbidden:
            pass

    async def _remove_afk(self, member: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM afk_status WHERE user_id = ?", (member.id,))
            await db.commit()

        try:
            if member.nick and member.nick.startswith("[AFK]"):
                original = member.nick[6:].strip()
                await member.edit(nick=original or None, reason="Returned from AFK")
        except discord.Forbidden:
            pass

    async def _get_afk(self, user_id: int, guild_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT status, timestamp, preset FROM afk_status WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            return await cursor.fetchone()

    async def _get_presets(self, user_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT name, status FROM afk_presets WHERE user_id = ?",
                (user_id,)
            )
            return await cursor.fetchall()

    @commands.hybrid_group(name="afk", invoke_without_command=True, description="AFK system with presets")
    async def afk(self, ctx: commands.Context, *, message: Optional[str] = None):
        """Set AFK status. Use preset name or custom message."""
        member = ctx.author
        if message:
            if "@everyone" in message or "@here" in message:
                embed = discord.Embed(description="You cannot use @everyone or @here in your AFK status.", color=COLOR_ERROR)
                await ctx.send(embed=embed)
                return
            # Check if it's a preset
            presets = await self._get_presets(member.id)
            preset_match = next((p for p in presets if p[0].lower() == message.lower()), None)
            if preset_match:
                status = preset_match[1]
                preset_name = preset_match[0]
            else:
                status = message
                preset_name = None
        else:
            status = "AFK"
            preset_name = None

        await self._set_afk(member, status, preset_name)

        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(content="**AFK Set**"),
            discord.ui.TextDisplay(content=f"You're now AFK with status: **{status}**"),
            
        ))
        await ctx.send(view=view)

    @afk.command(name="list", description="List all AFK users")
    async def afk_list(self, ctx: commands.Context):
        """List all AFK users in the server."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id, status, timestamp FROM afk_status WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            rows = await cursor.fetchall()

        if not rows:
            view = discord.ui.LayoutView()
            view.add_item(discord.ui.Container(
                discord.ui.TextDisplay(content="No users are currently AFK."),
                
            ))
            await ctx.send(view=view)
            return

        lines = []
        for user_id, status, ts in rows:
            user = ctx.guild.get_member(user_id)
            if user:
                time_str = f"<t:{ts}:R>"
                lines.append(f"• {user.mention} — {status} ({time_str})")

        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(content="**AFK Users**"),
            discord.ui.TextDisplay(content="\n".join(lines) if lines else "No users AFK."),
            
        ))
        await ctx.send(view=view)

    @afk.command(name="presetadd", description="Add AFK preset")
    async def preset_add(self, ctx: commands.Context, name: str, *, status: str):
        """Add a new AFK preset."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO afk_presets (user_id, name, status) VALUES (?, ?, ?)",
                (ctx.author.id, name, status)
            )
            await db.commit()

        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(content=f"Preset **{name}** added."),
            
        ))
        await ctx.send(view=view)

    @afk.command(name="presetrem", description="Remove AFK preset")
    async def preset_rem(self, ctx: commands.Context, name: str):
        """Remove an AFK preset."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM afk_presets WHERE user_id = ? AND name = ?",
                (ctx.author.id, name)
            )
            await db.commit()

        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(content=f"Preset **{name}** removed."),
            
        ))
        await ctx.send(view=view)

    @afk.command(name="presetedit", description="Edit AFK preset")
    async def preset_edit(self, ctx: commands.Context, name: str, *, new_status: str):
        """Edit an existing AFK preset."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "UPDATE afk_presets SET status = ? WHERE user_id = ? AND name = ?",
                (new_status, ctx.author.id, name)
            )
            await db.commit()
            if cursor.rowcount == 0:
                await ctx.send(view=error_layout("Preset not found."))
                return

        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(content=f"Preset **{name}** updated."),
            
        ))
        await ctx.send(view=view)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Auto un-AFK if user was AFK
        afk_data = await self._get_afk(message.author.id, message.guild.id)
        if afk_data:
            await self._remove_afk(message.author)
            try:
                await message.channel.send(f"Welcome back {message.author.mention}! I've removed your AFK status.", delete_after=5)
            except:
                pass
            return

        # Check for mentions or replies to AFK users
        for mentioned in message.mentions:
            if mentioned.id == message.author.id:
                continue
            data = await self._get_afk(mentioned.id, message.guild.id)
            if data:
                status, ts, preset = data
                view = discord.ui.LayoutView()
                container = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"**{mentioned.display_name} is AFK**"),
                    discord.ui.TextDisplay(content=f"**Status:** {status}\n**Since:** <t:{ts}:R>"),
                    
                )
                if preset:
                    container.add_item(discord.ui.TextDisplay(content=f"Preset: {preset}"))
                view.add_item(container)
                try:
                    await message.channel.send(view=view, delete_after=10)
                except:
                    pass

        # Reply check
        if message.reference and message.reference.resolved:
            replied_user = message.reference.resolved.author
            if not replied_user.bot:
                data = await self._get_afk(replied_user.id, message.guild.id)
                if data:
                    status, ts, preset = data
                    view = discord.ui.LayoutView()
                    container = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"**{replied_user.display_name} is AFK**"),
                        discord.ui.TextDisplay(content=f"**Status:** {status}\n**Since:** <t:{ts}:R>"),
                        accent_color=COLOR_ERROR
                    )
                    if preset:
                        container.add_item(discord.ui.TextDisplay(content=f"Preset: {preset}"))
                    view.add_item(container)
                    try:
                        await message.channel.send(view=view, delete_after=10)
                    except:
                        pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AFK(bot))
