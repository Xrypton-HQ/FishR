import discord
import random
import msgspec
from typing import Optional
from discord.ext import commands
from utils.database import db
from utils.displays import (
    send_error_view,
    send_success_view,
    send_embed
)
from cogs.help import send_subcommand_help

class juul_state(msgspec.Struct):
    enabled: bool = True
    flavor: str = "mango"
    holder_id: Optional[str] = None
    hits: int = 0
    passes: int = 0
    steals: int = 0

async def migrate_table():
    try:
        await db.execute(
            "ALTER TABLE juul_stats ADD COLUMN data BLOB"
        )
    except Exception:
        pass

async def fetch_state(
    guild_id: int
) -> juul_state:
    row = await db.fetch_one(
        "SELECT data, enabled, flavor, holder_id, hits, passes, steals FROM juul_stats WHERE guild_id = ?",
        str(guild_id)
    )
    if not row:
        state = juul_state()
        await db.execute(
            "INSERT INTO juul_stats (guild_id, data) VALUES (?, ?)",
            str(guild_id),
            msgspec.msgpack.encode(state)
        )
        return state
    if row["data"] is not None:
        return msgspec.msgpack.decode(
            row["data"],
            type=juul_state
        )
    state = juul_state(
        enabled=bool(row["enabled"]) if row["enabled"] is not None else True,
        flavor=row["flavor"] if row["flavor"] is not None else "mango",
        holder_id=row["holder_id"],
        hits=row["hits"] if row["hits"] is not None else 0,
        passes=row["passes"] if row["passes"] is not None else 0,
        steals=row["steals"] if row["steals"] is not None else 0
    )
    await db.execute(
        "UPDATE juul_stats SET data = ? WHERE guild_id = ?",
        msgspec.msgpack.encode(state),
        str(guild_id)
    )
    return state

async def get_stats(
    guild_id: int
) -> juul_state:
    await migrate_table()
    return await fetch_state(
        guild_id
    )

async def save_stats(
    guild_id: int,
    state: juul_state
):
    await db.execute(
        "UPDATE juul_stats SET data = ? WHERE guild_id = ?",
        msgspec.msgpack.encode(state),
        str(guild_id)
    )

class juul(commands.Cog, name="juul"):
    def __init__(
        self,
        bot
    ):
        self.bot = bot

    @commands.hybrid_group(
        name="juul",
        aliases=["vape"],
        description="share a juul with your friends!",
        invoke_without_command=True,
        extras={"example": ",juul hit"}
    )
    async def juul_cmd(
        self,
        ctx
    ):
        await send_subcommand_help(ctx, self.juul_cmd)

    @juul_cmd.command(
        name="flavor",
        description="change the servers juul's flavor",
        extras={"example": ",juul flavor mint"}
    )
    @commands.has_permissions(manage_guild=True)
    async def juul_flavor(
        self,
        ctx,
        *,
        flavor: Optional[str] = None
    ):
        if flavor is None:
            await send_subcommand_help(ctx, self.juul_cmd)
            return
        state = await get_stats(ctx.guild.id)
        if not state.enabled:
            return await send_error_view(
                ctx,
                "the juul is currently disabled."
            )
        state.flavor = flavor[:30]
        await save_stats(
            ctx.guild.id,
            state
        )
        await send_success_view(
            ctx,
            f"the server juul flavor is now set to **{state.flavor}**!"
        )

    @juul_cmd.command(
        name="toggle",
        description="toggle the servers juul on or off",
        extras={"example": ",juul toggle"}
    )
    @commands.has_permissions(manage_guild=True)
    async def juul_toggle(
        self,
        ctx
    ):
        state = await get_stats(ctx.guild.id)
        state.enabled = not state.enabled
        await save_stats(
            ctx.guild.id,
            state
        )
        status = "enabled" if state.enabled else "disabled"
        await send_success_view(
            ctx,
            f"the server juul is now **{status}**."
        )

    @juul_cmd.command(
        name="hit",
        description="hit the servers juul",
        extras={"example": ",juul hit"}
    )
    async def juul_hit(
        self,
        ctx
    ):
        state = await get_stats(ctx.guild.id)
        if not state.enabled:
            return await send_error_view(
                ctx,
                "the juul is currently disabled."
            )
        if state.holder_id and state.holder_id != str(ctx.author.id):
            return await send_error_view(
                ctx,
                f"you don't have the juul right now! <@{state.holder_id}> has it. steal it from them!"
            )
        state.hits += 1
        state.holder_id = str(ctx.author.id)
        await db.execute(
            "UPDATE juul_stats SET data = ? WHERE guild_id = ?",
            msgspec.msgpack.encode(state),
            str(ctx.guild.id)
        )
        await db.execute(
            "INSERT INTO juul_users (guild_id, user_id, hits) VALUES (?, ?, 1) ON CONFLICT(guild_id, user_id) DO UPDATE SET hits = hits + 1",
            str(ctx.guild.id),
            str(ctx.author.id)
        )
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"🚬 {ctx.author.mention} takes a massive hit of the **{state.flavor}** juul!"
            ),
            accent_colour=discord.Colour.from_rgb(
                0,
                255,
                127
            )
        )
        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

    @juul_cmd.command(
        name="stats",
        description="show the servers juul stats",
        extras={"example": ",juul stats"}
    )
    async def juul_stats(
        self,
        ctx
    ):
        state = await get_stats(ctx.guild.id)
        comp = [
            discord.ui.TextDisplay("**server juul stats**"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                f"flavor: {state.flavor}\ntotal hits: {state.hits}\npasses: {state.passes}\nsteals: {state.steals}"
            )
        ]
        if state.holder_id:
            comp.append(
                discord.ui.TextDisplay(
                    f"current holder: <@{state.holder_id}>"
                )
            )
        container = discord.ui.Container(
            *comp,
            accent_colour=discord.Colour.blurple()
        )
        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

    @juul_cmd.command(
        name="steal",
        description="steal the servers juul",
        extras={"example": ",juul steal"}
    )
    async def juul_steal(
        self,
        ctx
    ):
        state = await get_stats(ctx.guild.id)
        if not state.enabled:
            return await send_error_view(
                ctx,
                "the juul is currently disabled."
            )
        if not state.holder_id:
            return await send_error_view(
                ctx,
                "no one has the juul right now. just hit it!"
            )
        if state.holder_id == str(ctx.author.id):
            return await send_error_view(
                ctx,
                "you already have the juul!"
            )
        if random.randint(1, 100) > 60:
            old_holder = state.holder_id
            state.steals += 1
            state.holder_id = str(ctx.author.id)
            await save_stats(
                ctx.guild.id,
                state
            )
            return await send_success_view(
                ctx,
                f"{ctx.author.mention} stole the juul from <@{old_holder}>!"
            )
        await send_error_view(
            ctx,
            f"{ctx.author.mention} tried to steal the juul from <@{state.holder_id}> but failed lol"
        )

    @juul_cmd.command(
        name="pass",
        description="pass the servers juul to someone else",
        extras={"example": ",juul pass @user"}
    )
    async def juul_pass(
        self,
        ctx,
        *,
        member: Optional[discord.Member] = None
    ):
        if member is None:
            await send_subcommand_help(ctx, self.juul_cmd)
            return
        state = await get_stats(ctx.guild.id)
        if not state.enabled:
            return await send_error_view(
                ctx,
                "the juul is currently disabled."
            )
        if state.holder_id != str(ctx.author.id):
            return await send_error_view(
                ctx,
                "you don't have the juul to pass!"
            )
        state.passes += 1
        state.holder_id = str(member.id)
        await save_stats(
            ctx.guild.id,
            state
        )
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"💨 {ctx.author.mention} passes the juul to {member.mention}."
            ),
            accent_colour=discord.Colour.from_rgb(
                0,
                255,
                127
            )
        )
        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

async def setup(
    bot
):
    try:
        await db.execute(
            "ALTER TABLE juul_stats ADD COLUMN data BLOB"
        )
    except Exception:
        pass
    await bot.add_cog(juul(bot))