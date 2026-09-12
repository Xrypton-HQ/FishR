import discord
from discord.ext import commands
from utils.database import db
from cogs.help import send_subcommand_help


class Prefix(commands.Cog):
    """Prefix management commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(name="prefix", invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def prefix_cmd(self, ctx: commands.Context):
        """Show prefix usage."""
        await send_subcommand_help(ctx, ctx.command)

    @prefix_cmd.command(name="set")
    async def prefix_set(self, ctx: commands.Context, prefix: str):
        """Set a custom per-server prefix."""
        if len(prefix) > 5:
            await ctx.send("Prefix must be 5 characters or less.")
            return

        await db.execute(
            "INSERT OR REPLACE INTO prefixes (guild_id, prefix) VALUES (?, ?)",
            ctx.guild.id, prefix
        )
        await ctx.send(f"Prefix set to `{prefix}`")

    @prefix_cmd.command(name="list")
    async def prefix_list(self, ctx: commands.Context):
        """List all prefixes in the server."""
        rows = await db.fetch_all(
            "SELECT prefix FROM prefixes WHERE guild_id = ?",
            ctx.guild.id
        )
        if not rows:
            await ctx.send("No custom prefixes set in this server.")
            return

        prefixes = [row["prefix"] for row in rows]
        await ctx.send(f"Prefixes in this server:\n" + "\n".join(f"- `{p}`" for p in prefixes))

    @prefix_cmd.command(name="remove")
    async def prefix_remove(self, ctx: commands.Context, prefix: str):
        """Remove a prefix from the server."""
        cursor = await db.execute(
            "DELETE FROM prefixes WHERE guild_id = ? AND prefix = ?",
            ctx.guild.id, prefix
        )
        if cursor.rowcount > 0:
            await ctx.send(f"Prefix `{prefix}` removed.")
        else:
            await ctx.send(f"Prefix `{prefix}` not found.")

    @prefix_cmd.command(name="reset")
    async def prefix_reset(self, ctx: commands.Context):
        """Remove all prefixes from the server."""
        await db.execute(
            "DELETE FROM prefixes WHERE guild_id = ?",
            ctx.guild.id
        )
        await ctx.send("All prefixes removed.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Prefix(bot))