# error.py
# discord.py 2.6+ / py-cord layouts
# because humans keep inventing new ways to break commands

import discord
from discord.ext import commands
import traceback
import aiohttp


WEBHOOK_URL = "YOUR_WEBHOOK_URL"

from difflib import get_close_matches


# =========================
# COMMAND NOT FOUND VIEW
# =========================

class CommandNotFoundView(discord.ui.LayoutView):

    def __init__(self, command: str):
        super().__init__(timeout=15)

        self.container1 = discord.ui.Container(
            discord.ui.TextDisplay(
                content=f"command not found, did you mean **{command}**?"
            ),
        )

        self.add_item(self.container1)

# =========================
# BASIC ERROR VIEW
# =========================

class Error(discord.ui.LayoutView):
    def __init__(self, description: str):
        super().__init__(timeout=20)

        self.container1 = discord.ui.Container(
            discord.ui.TextDisplay(
                content=f"# An Error Occured!\n{description}"
            ),
        )

        self.add_item(self.container1)


# =========================
# MISSING ARGUMENT VIEW
# =========================

class MissArgu(discord.ui.LayoutView):
    def __init__(
        self,
        arg: str,
        description: str,
        syntax: str,
        example: str,
    ):
        super().__init__(timeout=30)

        self.container1 = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(
                    content=(
                        f"# Missing Argument: {arg}\n"
                        f"{description}\n"
                        "parameters: `[target] [duration] [reason]`\n\n"
                        "```yaml\n"
                        f"Syntax: {syntax}\n"
                        f"Example: {example}\n"
                        "```"
                    )
                ),
                accessory=discord.ui.Thumbnail(
                    media="https://images-ext-1.discordapp.net/external/OTOkf7-uAxfNgvfLogO6BaGitU25fO6X_Era-nmdRII/%3Fsize%3D1024/https/cdn.discordapp.com/avatars/1447869784937988201/19baf93704a66d4fccbfb411f533ee4a.png?format=webp&quality=lossless&width=420&height=420",
                ),
            ),
        )

        self.add_item(self.container1)


# =========================
# REPORT BUTTON
# =========================

class ReportButton(discord.ui.Button):
    def __init__(self, error_traceback: str):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="Report",
            custom_id="report_error_btn",
        )

        self.error_traceback = error_traceback

    async def callback(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="Error Reported",
            description=f"```py\n{self.error_traceback[:3900]}\n```",
            color=discord.Color.red(),
        )

        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(
                WEBHOOK_URL,
                session=session
            )

            await webhook.send(embed=embed)

        await interaction.response.send_message(
            "Error reported successfully.",
            ephemeral=True
        )


# =========================
# MAIN ERROR COMPONENTS
# =========================

class Components(discord.ui.LayoutView):

    def __init__(self, error_traceback: str):
        super().__init__(timeout=60)

        self.container1 = discord.ui.Container(
            discord.ui.TextDisplay(
                content=(
                    "# An Error Occured\n\n"
                    "```py\n"
                    f"{error_traceback[:3500]}\n"
                    "```"
                )
            ),
            discord.ui.ActionRow(
                ReportButton(error_traceback)
            ),
        )

        self.add_item(self.container1)


# =========================
# ERROR COG
# =========================

class ErrorHandler(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError
    ):

        if hasattr(ctx.command, "on_error"):
            return

        error = getattr(error, "original", error)

        # Missing Required Argument
        if isinstance(error, commands.MissingRequiredArgument):

            view = MissArgu(
                arg=error.param.name,
                description="You forgot to provide a required parameter.",
                syntax=f"{ctx.clean_prefix}{ctx.command.qualified_name} <arg>",
                example=f"{ctx.clean_prefix}{ctx.command.qualified_name} @user 1d being annoying",
            )

            return await ctx.send(view=view)

        # Bad Argument
        elif isinstance(error, commands.BadArgument):

            return await ctx.send(view=Error("Invalid argument type provided."))

        elif isinstance(error, commands.MemberNotFound):
            return await ctx.send(view=Error("Member was not found."))

        elif isinstance(error, commands.UserNotFound):
            return await ctx.send(view=Error("User was not found."))

        elif isinstance(error, commands.RoleNotFound):
            return await ctx.send(view=Error("Role was not found."))

        elif isinstance(error, commands.ChannelNotFound):
            return await ctx.send(view=Error("Channel was not found."))

        elif isinstance(error, commands.EmojiNotFound):
            return await ctx.send(view=Error("Emoji was not found."))

        elif isinstance(error, commands.MissingPermissions):
            perms = ", ".join(error.missing_permissions)
            return await ctx.send(view=Error(f"You are missing permissions:\n`{perms}`"))

        elif isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions)
            return await ctx.send(view=Error(f"Bot is missing permissions:\n`{perms}`"))

        elif isinstance(error, commands.CommandOnCooldown):
            return await ctx.send(
                view=Error(f"Slow down lil bro.\nTry again in `{round(error.retry_after, 2)}s`")
            )

        elif isinstance(error, commands.NSFWChannelRequired):
            return await ctx.send(view=Error("This command requires an NSFW channel."))

        elif isinstance(error, commands.NoPrivateMessage):
            return await ctx.send(view=Error("This command cannot be used in DMs."))

        elif isinstance(error, commands.PrivateMessageOnly):
            return await ctx.send(view=Error("This command can only be used in DMs."))

        elif isinstance(error, commands.DisabledCommand):
            return await ctx.send(view=Error("This command is currently disabled."))

        elif isinstance(error, commands.CheckFailure):
            return await ctx.send(view=Error("You cannot use this command."))

        elif isinstance(error, commands.NotOwner):
            return await ctx.send(view=Error("Only the bot owner can use this command."))

        elif isinstance(error, commands.MissingRole):
            return await ctx.send(
                view=Error(f"You need the role `{error.missing_role}` to use this command.")
            )

        elif isinstance(error, commands.MissingAnyRole):
            roles = ", ".join(error.missing_roles)
            return await ctx.send(view=Error(f"You need one of these roles:\n`{roles}`"))

        elif isinstance(error, commands.MaxConcurrencyReached):
            return await ctx.send(view=Error("This command is already running."))

        # =========================
        # Command Not Found (FIXED)
        # =========================
        elif isinstance(error, commands.CommandNotFound):

            attempted = ctx.message.content[len(ctx.prefix):].split(" ")[0]

            command_names = [
                command.name
                for command in self.bot.commands
                if not command.hidden
            ]

            matches = get_close_matches(
                attempted,
                command_names,
                n=1,
                cutoff=0.5
            )

            if matches:
                return await ctx.send(view=CommandNotFoundView(matches[0]))

            return await ctx.send(view=Error("Command not found."))

        else:

            tb = "".join(
                traceback.format_exception(
                    type(error),
                    error,
                    error.__traceback__
                )
            )

            print(tb)

            return await ctx.send(view=Components(tb))