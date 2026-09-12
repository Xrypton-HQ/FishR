# cogs/help.py

from __future__ import annotations

import discord
from discord.ext import commands


SUPPORT_SERVER = "https://discord.gg/YWG5ryEZGS"
BOT_AVATAR = (
    "https://images-ext-1.discordapp.net/external/X7NT3lTx9rDaSny9G5LagbpIcTatixvx0pUPjiwN3lU/%3Fsize%3D1024/https/cdn.discordapp.com/avatars/1447869784937988201/5b5aab6f0b816870ce9156e6a67f531e.png?format=webp&quality=lossless&width=521&height=521"
)


async def send_subcommand_help(ctx: commands.Context, cmd: commands.Command):
    """Send subcommand help embed for a command group."""
    subcommands = []
    if hasattr(cmd, "commands"):
        for sub in cmd.commands:
            if hasattr(sub, "commands") and sub.commands:
                # nested subcommands
                for subsub in sub.commands:
                    desc = getattr(subsub, "description", None) or subsub.help or subsub.short_doc or "No description"
                    subcommands.append((f"{sub.name} {subsub.name}", desc))
            else:
                desc = getattr(sub, "description", None) or sub.help or sub.short_doc or "No description"
                subcommands.append((sub.name, desc))

    count = len(subcommands)
    lines = [f"> {name} - {desc}" for name, desc in subcommands]
    body = "\n".join(lines)
    content = f"## ({count}) {cmd.name}\n\n{body}"

    class subcmdhelp(discord.ui.LayoutView):
        container1 = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(content=content),
                accessory=discord.ui.Thumbnail(media=BOT_AVATAR),
            ),
        )

    await ctx.send(view=subcmdhelp())


HELP_CATEGORIES: dict[str, dict] = {
    "economy": {
        "emoji": "💰",
        "title": "Economy Commands",
        "description": "money n stuff",
        "commands": [
            (".balance", "view ur balance"),
            (".daily", "claim daily credits"),
            (".give", "send credits to users"),
            (".pay", "alias for give"),
            (".transfer", "alias for give"),
            (".send", "alias for give"),
            (".beg", "beg random npcs"),
            (".panhandle", "alias for beg"),
        ],
    },
    "banking": {
        "emoji": "🏦",
        "title": "Banking Commands",
        "description": "protect ur money fr",
        "commands": [
            (".bank", "view ur vault"),
            (".vault", "alias for bank"),
            (".deposit", "deposit credits"),
            (".dep", "alias for deposit"),
            (".withdraw", "withdraw credits"),
            (".with", "alias for withdraw"),
        ],
    },
    "crime": {
        "emoji": "🦹",
        "title": "Crime Commands",
        "description": "totally legal",
        "commands": [
            (".steal", "steal from users"),
            (".rob", "alias for steal"),
            (".mug", "alias for steal"),
        ],
    },
    "fishing": {
        "emoji": "🎣",
        "title": "Fishing Commands",
        "description": "fish gambling",
        "commands": [
            (".fish", "go fishing"),
            (".sell", "sell ur fish"),
            (".market", "view fish prices"),
            (".shop", "buy upgrades"),
        ],
    },
    "jobs": {
        "emoji": "🏢",
        "title": "Job Commands",
        "description": "forced labor update",
        "commands": [
            (".job", "get a job"),
            (".work", "work ur shift"),
            (".shift", "alias for work"),
        ],
    },
    "afk": {
        "emoji": "💤",
        "title": "AFK Commands",
        "description": "set it and forget it",
        "commands": [
            (".afk [msg/preset]", "mark afk + nick change"),
            (".afk list", "show all afk users"),
            (".afk presetadd", "save status preset"),
            (".afk presetrem", "delete preset"),
            (".afk presetedit", "update preset"),
        ],
    },
    "giveaway": {
        "emoji": "🎁",
        "title": "Giveaway Commands",
        "description": "free stuff",
        "commands": [
            (".giveaway start", "start giveaway"),
            (".giveaway end", "end giveaway"),
            (".giveaway blacklist", "blacklist user"),
            (".giveaway unblacklist", "unblacklist"),
            (".giveaway listblacklist", "show blacklist"),
            (".giveaway reroll", "reroll winners"),
            (".giveaway channel", "set default channel"),
        ],
    },
    "shop": {
        "emoji": "🛒",
        "title": "Shop Commands",
        "description": "buy cool stuff",
        "commands": [
            (".shop", "view shop"),
            (".buy", "purchase item"),
        ],
    },
    "market": {
        "emoji": "📈",
        "title": "Market Commands",
        "description": "fish market",
        "commands": [
            (".market", "fish prices"),
            (".sell", "sell fish"),
        ],
    },
    "ai": {
        "emoji": "🤖",
        "title": "AI Commands",
        "description": "chronically online bot",
        "commands": [
            ("@FishR", "talk to ai"),
            ("reply to bot", "continue convo"),
            ("@everyone + bot", "trigger ai"),
        ],
    },
    "info": {
        "emoji": "ℹ️",
        "title": "Info Commands",
        "description": "user n server info",
        "commands": [
            (".avatar", "show someone's pfp"),
            (".banner", "show someone's banner"),
            (".profile", "see info about a user"),
            (".device", "see what device someone's on"),
            (".serverinfo", "see info about this server"),
            (".servericon", "show the server icon"),
            (".serverbanner", "show the server banner"),
            (".servertag", "view someone's server tag"),
            (".serversplash", "show the server splash"),
        ],
    },
    "welcome": {
        "emoji": "👋",
        "title": "Welcome Commands",
        "description": "greeting system",
        "commands": [
            (".greet channel set", "set welcome channel"),
            (".greet channel remove", "remove welcome channel"),
            (".greet embed toggle", "toggle embed mode"),
            (".greet embed title", "set embed title"),
            (".greet embed description", "set embed description"),
            (".greet embed image", "set embed image"),
            (".greet toggle", "enable/disable welcomer"),
            (".greet reset", "reset all settings"),
        ],
    },
    "vape": {
        "emoji": "🚬",
        "title": "Vape Commands",
        "description": "juul simulator",
        "commands": [
            (".vape flavor", "set juul flavor"),
            (".vape toggle", "enable/disable juul"),
            (".vape hit", "hit the juul"),
            (".vape stats", "view juul stats"),
            (".vape steal", "steal the juul"),
            (".vape pass", "pass the juul"),
        ],
    },
    "fun": {
        "emoji": "🎮",
        "title": "Fun Commands",
        "description": "games & utilities",
        "commands": [
            (".fun 8ball", "ask the magic 8ball"),
            (".fun dice", "roll dice"),
            (".fun coinflip", "flip a coin"),
            (".fun dih", "check dih size"),
            (".fun choose", "choose from options"),
            (".fun rps", "rock paper scissors"),
            (".fun humble", "ai roast generator"),
            (".fun caption", "add text to images"),
            (".fun base64", "encode/decode base64"),
            (".fun ai", "ask the ai anything"),
            (".fun aiclear", "clear ai memory"),
            (".fun sha256", "generate sha256 hash"),
            (".fun steal", "steal emojis/stickers"),
            (".fun translate", "translate text"),
            (".fun urban", "urban dictionary"),
            (".fun img2gif", "convert image to gif"),
            (".8ball", "magic 8ball alias"),
            (".dice", "dice roll alias"),
        ],
    },
    "other": {
        "emoji": "⚙️",
        "title": "Other Commands",
        "description": "misc & utility",
        "commands": [
            (".prefix", "manage server prefix"),
            (".get", "info commands"),
            (".ai", "talk to ai"),
            (".antinuke", "antinuke config"),
            (".owner", "bot owner cmds"),
        ],
    },
}


class HelpCategorySelect(discord.ui.Select):
    def __init__(self):
        options = []

        for key, value in HELP_CATEGORIES.items():
            options.append(
                discord.SelectOption(
                    label=value["title"],
                    value=key,
                    description=value["description"],
                    emoji=value["emoji"],
                )
            )

        super().__init__(
            placeholder="choose a category",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="fishr_help_select",
        )

    async def callback(self, interaction: discord.Interaction):
        view: HelpView = self.view

        if interaction.user.id != view.author_id:
            return await interaction.response.send_message(
                "This interaction is not for you.",
                ephemeral=True,
            )

        category = HELP_CATEGORIES[self.values[0]]

        command_text = "\n".join(
            f"`{cmd}` - {desc}"
            for cmd, desc in category["commands"]
        )

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                content=(
                    f"# {category['emoji']} {category['title']}\n"
                    f"{category['description']}\n\n"
                    f"{command_text}"
                )
            ),
            discord.ui.Separator(
                visible=True,
                spacing=discord.SeparatorSpacing.small,
            ),
            discord.ui.ActionRow(self),
            discord.ui.Separator(
                visible=True,
                spacing=discord.SeparatorSpacing.small,
            ),
            discord.ui.TextDisplay(content="-# the support server is the best place to get help."),
            discord.ui.ActionRow(
                discord.ui.Button(
                    url=SUPPORT_SERVER,
                    style=discord.ButtonStyle.link,
                    label="support",
                )
            ),
        )

        view.clear_items()
        view.add_item(container)


        await interaction.response.edit_message(
            view=view
        )


class HelpView(discord.ui.LayoutView):
    def __init__(self, author_id: int, command_count: int):
        super().__init__(timeout=300)

        self.author_id = author_id

        self.select = HelpCategorySelect()

        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(
                    content=(
                        "# FishR Help\n"
                        f"i have `{command_count}` commands ok?\n"
                        "my prefix is `.` rn\n"
                        "click a category from below to get started\n\n"
                    )
                ),
                accessory=discord.ui.Thumbnail(
                    media=BOT_AVATAR,
                ),
            ),
            discord.ui.Separator(
                visible=True,
                spacing=discord.SeparatorSpacing.small,
            ),
            discord.ui.ActionRow(
                self.select,
            ),
            discord.ui.Separator(
                visible=True,
                spacing=discord.SeparatorSpacing.small,
            ),
            discord.ui.Section(
                discord.ui.TextDisplay(
                    content="-# the support server is the best place to get help."
                ),
                accessory=discord.ui.Button(
                    url=SUPPORT_SERVER,
                    style=discord.ButtonStyle.link,
                    label="support",
                ),
            ),
        )

        self.add_item(container)

    async def on_timeout(self):
        for item in self.walk_children():
            if isinstance(item, discord.ui.Select):
                item.disabled = True

        try:
            if hasattr(self, "message"):
                await self.message.edit(view=self)
        except Exception:
            pass


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="help",
        aliases=["h", "commands", "cmds"],
    )
    async def help_command(self, ctx: commands.Context):
        command_count = len(
            [
                command
                for command in self.bot.commands
                if not command.hidden
            ]
        )

        view = HelpView(
            author_id=ctx.author.id,
            command_count=command_count,
        )

        message = await ctx.send(
            view=view
        )

        view.message = message


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))