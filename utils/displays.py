import discord
from typing import Optional
from utils.embeds import create_container, error_layout
from utils.constants import COLOR_ERROR, COLOR_SUCCESS


async def send_error_view(ctx, message: str, ephemeral: bool = False):
    """Send an error message as a LayoutView."""
    view = error_layout(message)
    await ctx.send(view=view, ephemeral=ephemeral)


async def send_success_view(ctx, message: str, ephemeral: bool = False):
    """Send a success message as a LayoutView."""
    view = create_container(
        title="Success",
        description=message,
        color=COLOR_SUCCESS
    )
    await ctx.send(view=view, ephemeral=ephemeral)


def create_missing_argument_embed(bot, command_name: str, missing_arg: str, options: list = None, ctx=None):
    """Create an embed for missing arguments."""
    if options:
        options_str = ", ".join([f"`{opt}`" for opt in options])
        description = f"Missing argument: **{missing_arg}**\nValid options: {options_str}"
    else:
        description = f"Missing argument: **{missing_arg}**"
    
    embed = discord.Embed(
        title=f"Usage: {command_name}",
        description=description,
        color=COLOR_ERROR
    )
    
    if ctx:
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    
    return embed


async def send_embed(ctx, embed: discord.Embed, ephemeral: bool = False):
    """Send an embed message."""
    await ctx.send(embed=embed, ephemeral=ephemeral)