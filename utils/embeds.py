import discord
import random
import string
from typing import Optional, List
from utils.constants import *
import time

def generate_random_string(length: int) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def generate_math_problem() -> tuple[int, str]:
    num1 = random.randint(1, 50)
    num2 = random.randint(1, 50)
    operation = random.choice(['+', '-', '*'])

    if operation == '+':
        answer = num1 + num2
        problem = f"{num1} + {num2}"
    elif operation == '-':
        if num1 < num2:
            num1, num2 = num2, num1
        answer = num1 - num2
        problem = f"{num1} - {num2}"
    else:
        answer = num1 * num2
        problem = f"{num1} × {num2}"

    return answer, problem


def generate_scrambled_word() -> tuple[str, str]:
    words = ["PYTHON", "JAVASCRIPT", "DISCORD", "PROGRAMMING", "FUNCTION",
             "VARIABLE", "STRING", "INTEGER", "BOOLEAN", "ARRAY", "OBJECT",
             "CLASS", "METHOD", "RETURN", "IMPORT", "EXPORT", "ASYNC", "AWAIT",
             "FRAMEWORK", "LIBRARY", "DATABASE", "API", "FRONTEND", "BACKEND"]

    word = random.choice(words)
    scrambled = ''.join(random.sample(word, len(word)))

    while scrambled == word:
        scrambled = ''.join(random.sample(word, len(word)))

    return word, scrambled


def create_container(
    title: str,
    description: str = "",
    color: int = 0x57F287,
    thumbnail: Optional[str] = None,
    image: Optional[str] = None,
    footer: Optional[str] = None,
) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    components = [
        discord.ui.TextDisplay(content=f"## {title}"),
        discord.ui.TextDisplay(content=description),
    ]
    if footer:
        components.append(discord.ui.TextDisplay(content=footer))
    view.add_item(discord.ui.Container(*components, accent_color=color))
    return view


def fishing_layout(phase: str, amount: int = None, gems: int = None) -> discord.ui.LayoutView:
    messages = {
        "cast": "You cast your line into the water... watch your bobber carefully!",
        "bite": "## A fish bit the line! **REEL IT IN FAST!**",
        "success": f"You successfully reeled it in! Caught {amount} {EMOJI_FISH}!" if amount else "You successfully reeled it in!",
        "miss": "The fish got away! You weren't fast enough.",
    }
    titles = {
        "cast": f"## {EMOJI_FISHING} Fishing",
        "bite": f"## {EMOJI_FISHING} Fishing",
        "success": f"## {EMOJI_VERIFY} Successful Catch",
        "miss": f"## {EMOJI_WARNING} Missed Catch",
    }
    description = messages.get(phase, messages["cast"])
    title = titles.get(phase, titles["cast"])
    color = COLOR_FISHING if phase in ("cast", "bite") else (
        COLOR_SUCCESS if phase == "success" else COLOR_ERROR
    )

    view = discord.ui.LayoutView()
    components = [
        discord.ui.TextDisplay(content=f"**{title}**"),
        discord.ui.TextDisplay(content=description),
    ]
    if gems is not None:
        components.append(discord.ui.TextDisplay(content=f"Also found **{gems}** {EMOJI_GEMS}!"))
    view.add_item(discord.ui.Container(*components, accent_color=color))
    return view


def balance_view(
    credits: int, gems: int, fish: int, user: discord.Member, bank: int = 0
) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    total = credits + bank
    section = discord.ui.Section(
        discord.ui.TextDisplay(content=(
            f"## {user.display_name}'s Balance\n"
            f"> {EMOJI_COIN} **Wallet:** `{credits:,}`\n"
            f"> {EMOJI_COIN} **Bank:** `{bank:,}`\n"
            f"> {EMOJI_GEMS} **Gems:** `{gems:,}`\n"
            f"> {EMOJI_FISH} **Fish:** `{fish:,}`\n\n"
            f"__Total: `{total:,}` credits__"
        )),
        accessory=discord.ui.Thumbnail(media=user.display_avatar.url),
    )
    container = discord.ui.Container(section, accent_color=0xE74C3C)
    view.add_item(container)
    return view


def shop_view(user_data: dict, page: int = 0) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    upgrades = list(UPGRADES.items())
    items_per_page = 4

    page_upgrades = upgrades[page * items_per_page:(page + 1) * items_per_page]

    items_content = []
    for key, data in page_upgrades:
        owned = user_data.get(key, 0)
        price = data["base_price"]
        items_content.append(
            f"> {data['name']} - {price} {EMOJI_COIN}\n"
            f"> {data['description']}\n"
            f"> Owned: Lvl {owned}"
        )

    components = [
        discord.ui.TextDisplay(content="# 🛒 upgrade shop"),
        discord.ui.TextDisplay(content="\n\n".join(items_content)),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        discord.ui.ActionRow(
            discord.ui.Select(
                custom_id="502487d1255d431dd59cd93aac88b028",
                placeholder="Select an item.",
                options=[
                    discord.SelectOption(label=data["name"], value=key)
                    for key, data in upgrades
                ],
            ),
        ),
        discord.ui.ActionRow(
            discord.ui.Select(
                custom_id="4051a5da010a49c2bc9038c8b70bc820",
                placeholder="Quantity",
                options=[
                    discord.SelectOption(label="1", value="4450ffd035cb4c6ed308863827be4e34"),
                    discord.SelectOption(label="5", value="9a64ba4aa0b74f00e8b3ab9f1fac93a0"),
                    discord.SelectOption(label="10", value="e3f1c5b357ff4325e8e5e42962582367"),
                    discord.SelectOption(label="Max", value="d614625aef204590a19204c02bcd0431"),
                ],
            ),
        ),
    ]

    if len(upgrades) > items_per_page:
        components.append(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        pagination_buttons = [
            discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="Back",
                custom_id="d54527781b6647ff8874811bc7465381",
                disabled=page == 0,
            ),
            discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="Next",
                custom_id="3fc452a3f0a547aee59499002074f60d",
                disabled=page >= (len(upgrades) + items_per_page - 1) // items_per_page - 1,
            ),
        ]
        components.append(discord.ui.ActionRow(*pagination_buttons))

    view.add_item(discord.ui.Container(*components, accent_color=COLOR_SHOP))
    return view


def inventory_view(
    user: discord.Member,
    fish: int,
    upgrades: dict,
    frenzy_until: int
) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    frenzy_active = frenzy_until > time.time()
    frenzy_status = f"{EMOJI_VERIFY} Active" if frenzy_active else f"{EMOJI_NO} Inactive"
    frenzy_end = f"<t:{frenzy_until}:R>" if frenzy_active else "N/A"

    components = [
        discord.ui.TextDisplay(content=f"**{user.display_name}'s Inventory**"),
        discord.ui.TextDisplay(content=(
            f"{EMOJI_FISH} **Fish:** {fish:,}\n"
            f"{EMOJI_UPGRADE} **Stronger Rod:** Lvl {upgrades['stronger_rod']}\n"
            f"{EMOJI_UPGRADE} **New Rod:** Lvl {upgrades['new_rod']}"
        )),
        discord.ui.TextDisplay(content=f"{EMOJI_FRENZY} Fishing Frenzy\n{frenzy_status}\nEnds: {frenzy_end}"),
    ]
    view.add_item(discord.ui.Container(*components, accent_color=COLOR_SUCCESS))
    return view


def market_layout(price: int, previous_price: Optional[int], next_refresh: int) -> discord.ui.LayoutView:
    trend_emoji = "➡️"
    if previous_price is not None:
        if price > previous_price:
            trend_emoji = "📈"
        elif price < previous_price:
            trend_emoji = "📉"

    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content="**🐟 Fish Market**"),
        discord.ui.TextDisplay(content=(
            f"{EMOJI_FISH} **Current Price:** {price} {EMOJI_CREDITS} per fish\n\n"
            f"**Trend:** {trend_emoji}\n\n"
            f"**Next Refresh:** <t:{next_refresh}:R>"
        )),
        accent_color=COLOR_MARKET
    ))
    return view


def sell_confirmation_layout(count: int, price: int, total: int) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content="**🛒 Confirm Sale**"),
        discord.ui.TextDisplay(content=(
            f"Are you sure you want to sell **{count} {EMOJI_FISH}** at "
            f"**{price} {EMOJI_CREDITS}** each?\n\n"
            f"**Total Profit:** +{total} {EMOJI_CREDITS}"
        )),
        accent_color=COLOR_MARKET
    ))
    return view


def leaderboard_view(
    entries: list[tuple[int, int]], bot: discord.Client
) -> tuple[discord.ui.LayoutView, list[discord.ui.LayoutView]]:
    views = []
    chunk_size = 10
    chunks = [entries[i:i + chunk_size] for i in range(0, len(entries), chunk_size)]

    for page_num, chunk in enumerate(chunks, 1):
        view = discord.ui.LayoutView()
        lines = []
        for rank, (user_id, credits) in enumerate(chunk, start=(page_num - 1) * chunk_size + 1):
            try:
                user = bot.get_user(user_id)
                name = user.display_name if user else f"User {user_id}"
            except AttributeError:
                name = f"User {user_id}"
            lines.append(f"**#{rank} {name}** — {credits:,} {EMOJI_CREDITS}")

        container = discord.ui.Container(
            discord.ui.TextDisplay(content="**🏆 Leaderboard**"),
            discord.ui.TextDisplay(content="\n".join(lines)),
            accent_color=COLOR_SHOP,
        )
        view.add_item(container)
        views.append(view)

    first_view = views[0] if views else discord.ui.LayoutView()
    return first_view, views


def cooldown_layout(seconds: int) -> discord.ui.LayoutView:
    minutes = seconds // 60
    secs = seconds % 60
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content="**⏳ Cooldown Active**"),
        discord.ui.TextDisplay(content=f"You must wait **{minutes}m {secs}s** before fishing again."),
        accent_color=COLOR_ERROR
    ))
    return view


def error_layout(message: str) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content=f"<:new_cross:1506624750602948658> {message}"),
        accent_color=COLOR_ERROR
    ))
    return view


def job_center_layout(current_job: Optional[str]) -> discord.ui.LayoutView:
    if current_job:
        job_name = JOBS.get(current_job, {}).get("name", current_job.title())
        description = f"You are currently employed as **{job_name}.**\n\nReview the available jobs below and select one.\nRemember: higher paying jobs require more brain power during !work."
    else:
        description = "You are currently unemployed.\n\nReview the available jobs below and select one.\nRemember: higher paying jobs require more brain power during !work."

    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content="**🏢 Employment Center**"),
        discord.ui.TextDisplay(content=description),
        accent_color=COLOR_JOB
    ))
    return view


def job_selected_layout(job_key: str) -> discord.ui.LayoutView:
    job = JOBS[job_key]
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content=f"{job['emoji']} {job['name']} Selected!"),
        discord.ui.TextDisplay(content=f"You are now employed as a **{job['name']}**!\nUse `.work` to earn credits."),
        accent_color=COLOR_SUCCESS
    ))
    return view


def insufficient_gems_layout(required: int, owned: int) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content=f"**{EMOJI_NO} Insufficient Gems**"),
        discord.ui.TextDisplay(content=(
            f"You do not have enough gems for this job.\n\n"
            f"**Required:** {required} {EMOJI_GEMS}\n"
            f"**Owned:** {owned} {EMOJI_GEMS}"
        )),
        accent_color=COLOR_ERROR
    ))
    return view


def no_job_layout() -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content=f"**{EMOJI_NO} No Job**"),
        discord.ui.TextDisplay(content="You don't have a job! Use `.job` to get one."),
        accent_color=COLOR_ERROR
    ))
    return view


def work_cooldown_layout(seconds: int) -> discord.ui.LayoutView:
    minutes = seconds // 60
    secs = seconds % 60
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content="**⏳ Work Cooldown**"),
        discord.ui.TextDisplay(content=f"You can work again in **{minutes}m {secs}s.**"),
        accent_color=COLOR_ERROR
    ))
    return view


def work_success_layout(job_key: str, payout: int) -> discord.ui.LayoutView:
    job = JOBS[job_key]
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content=f"{job['emoji']} Work Complete!"),
        discord.ui.TextDisplay(content=f"You worked hard and earned **{payout}** {EMOJI_CREDITS}!"),
        accent_color=COLOR_SUCCESS
    ))
    return view


def minigame_layout(title: str, description: str, color: discord.Color = COLOR_JOB) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content=f"**{title}**"),
        discord.ui.TextDisplay(content=description),
        accent_color=color
    ))
    return view


def change_layout(amount: int) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content="**🛒 Cashier Minigame**"),
        discord.ui.TextDisplay(content=f"Customer paid with a larger bill.\nSelect the correct change for **{amount}** credits."),
        accent_color=COLOR_JOB
    ))
    return view


def bank_layout(wallet: int, bank: int, account_name: str = "user") -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content=f"# FishR National Bank\naccount name: `{account_name}`\nwallet: `{wallet}`\nbank: `{bank}`\n\n-# bank money cant be stolen by thefts"),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        discord.ui.ActionRow(
            discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="deposit",
                custom_id="c6a2d310748b49718ec7f22473cb8565",
            ),
            discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="withdraw",
                custom_id="4a00cf260d12484fac1914089fd204d9",
            ),
        ),
        accent_color=COLOR_SUCCESS
    ))
    return view


def steal_success_layout(target_name: str, amount: int) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content="**🦹 Steal Successful**"),
        discord.ui.TextDisplay(content=f"You stole **{amount:,}** credits from {target_name}!"),
        accent_color=COLOR_SUCCESS
    ))
    return view


def steal_failed_layout(target_name: str, amount: int) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content="**🚔 Steal Failed**"),
        discord.ui.TextDisplay(content=f"You were caught trying to rob {target_name} and paid a fine of **{amount:,}** credits!"),
        accent_color=COLOR_ERROR
    ))
    return view


def steal_cooldown_layout(seconds: int) -> discord.ui.LayoutView:
    minutes = seconds // 60
    secs = seconds % 60
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content="**⏳ Steal Cooldown**"),
        discord.ui.TextDisplay(content=f"You can steal again in **{minutes}m {secs}s.**"),
        accent_color=COLOR_ERROR
    ))
    return view


def steal_empty_wallet_layout() -> discord.ui.LayoutView:
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content=f"**{EMOJI_NO} No Credits**"),
        discord.ui.TextDisplay(content="That user has no stealable credits."),
        accent_color=COLOR_ERROR
    ))
    return view


def missing_argument_layout(
    argument: str,
    command_name: str,
    command_description: str,
    aliases: list[str],
    example: str,
    module: str,
) -> discord.ui.LayoutView:
    alias_text = ", ".join(aliases) if aliases else "None"
    view = discord.ui.LayoutView()
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(content=f"# Missing Argument: {argument}\n**{command_name}** - {command_description}\nalias: {alias_text}\nexample: `{example}`\n```\n[..] is required\n(..) is optional\n```"),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        discord.ui.TextDisplay(content=f"-# {module} module"),
        accent_color=COLOR_ERROR,
    ))
    return view


def server_join_layout(guild: discord.Guild, invite_url: str = None) -> discord.ui.LayoutView:
    owner = guild.owner
    permissions = guild.me.guild_permissions
    perm_text = "Admin" if permissions.administrator else "Manage Messages" if permissions.manage_messages else "Basic"
    
    icon_url = guild.icon.url if guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png"
    
    join_url = invite_url if invite_url else "https://discord.gg"
    
    view = discord.ui.LayoutView()
    container = discord.ui.Container(
        discord.ui.Section(
            discord.ui.TextDisplay(content=f"# FishR joined new server!\n\nGeneral Information\n> **Server:** {guild.name}\n> **Server ID:** `{guild.id}`\n> **Owner:** {owner} (`{owner.id}`)\n\nBot Information:\n> Permissions: **{perm_text}**"),
            accessory=discord.ui.Thumbnail(media=icon_url)
        ),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        discord.ui.ActionRow(
            discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="Leave",
                custom_id="bd402784de4d48cde460ed96416e8960",
            ),
            discord.ui.Button(
                url=join_url,
                style=discord.ButtonStyle.link,
                label="Join",
            ),
        ),
    )
    view.add_item(container)
    return view


def invite_created_layout(guild: discord.Guild, invite_url: str) -> discord.ui.LayoutView:
    owner = guild.owner
    permissions = guild.me.guild_permissions
    perm_text = "Admin" if permissions.administrator else "Manage Messages" if permissions.manage_messages else "Basic"
    
    icon_url = guild.icon.url if guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png"
    
    view = discord.ui.LayoutView()
    container = discord.ui.Container(
        discord.ui.Section(
            discord.ui.TextDisplay(content=f"# Invite Created!\nserver name: `{guild.name}`\nmembers: `{guild.member_count or 0}`\nowner: `{owner}`\nbot permissions: `{perm_text}`"),
            accessory=discord.ui.Thumbnail(media=icon_url)
        ),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        discord.ui.ActionRow(
            discord.ui.Button(
                url=invite_url,
                style=discord.ButtonStyle.link,
                label="Join",
            ),
        ),
    )
    view.add_item(container)
    return view


# Legacy embed helpers for older cogs (fun.py etc.)
def create_embed(*, title: str = None, description: str = None, color: int = 0x5865F2, bot=None):
    embed = discord.Embed(title=title, description=description, color=color)
    if bot and hasattr(bot, "user"):
        embed.set_footer(text=str(bot.user.name))
    return embed

def create_error_embed(message: str, bot=None):
    embed = discord.Embed(title="Error", description=message, color=0xE74C3C)
    if bot and hasattr(bot, "user"):
        embed.set_footer(text=str(bot.user.name))
    return embed

def create_success_embed(message: str, bot=None):
    embed = discord.Embed(title="Success", description=message, color=0x57F287)
    if bot and hasattr(bot, "user"):
        embed.set_footer(text=str(bot.user.name))
    return embed