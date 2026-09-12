import discord

# Colors
COLOR_SUCCESS = discord.Color.green()
COLOR_ERROR = discord.Color.red()
COLOR_FISHING = discord.Color.blue()
COLOR_SHOP = discord.Color.gold()
COLOR_MARKET = discord.Color.purple()
COLOR_JOB = discord.Color.dark_grey()

# Emojis - FishR custom emojis
EMOJI_WARNING = "<:warn:1506626253455757452>"
EMOJI_CHART = "<:charts:1507342498350104667>"
EMOJI_COIN = "<:coin:1507342169047044116>"
EMOJI_FISH = "<:fish:1506626215119814786>"        # actual fish icon
EMOJI_ROD = "<:fishrfishrod:1463117392577171632>"      # fishing rod icon
EMOJI_MEMBER = "<:fishrmember:1463117395286556782>"
EMOJI_NO = "<:new_cross:1506624750602948658>"          # ❌ red cross
EMOJI_SUITCASE = "<:fishrsuitcase:1463117376286621736>"
EMOJI_TRASH = "<:fishrtrash:1463117378408808460>"
EMOJI_VERIFY = "<:checkmark:1506624747256156260>"    # ✅ green check

# Aliases for convenience
EMOJI_CREDITS = EMOJI_COIN
EMOJI_GEMS = "<:gems:1507343206587830332>"
EMOJI_FISHING = EMOJI_FISH
EMOJI_MONEY = "💰"
EMOJI_UPGRADE = "⬆️"
EMOJI_FRENZY = "⚡"

# Upgrade definitions
UPGRADES = {
    "stronger_rod": {
        "name": "Stronger Rod",
        "description": "Catch 2 more fish per level",
        "base_price": 100,
        "price_multiplier": 1.5,
    },
    "frenzy": {
        "name": "Fishing Frenzy",
        "description": "4x fish multiplier for 1 hour (stackable)",
        "base_price": 700,
        "price_multiplier": 1.0,
        "is_buff": True,
        "duration": 3600,
    },
    "new_rod": {
        "name": "New Rod",
        "description": "2x catch multiplier per level (stacks multiplicatively)",
        "base_price": 1000,
        "price_multiplier": 2.0,
    },
}

# Job definitions
JOBS = {
    "janitor": {
        "name": "Janitor",
        "emoji": "🧹",
        "cost": 5,
        "payout": 500,
        "difficulty": "Very Easy",
        "difficulty_emoji": "🔴",
        "description": "Clean up the server. Just push a button.",
    },
    "cashier": {
        "name": "Cashier",
        "emoji": "🛒",
        "cost": 15,
        "payout": 1200,
        "difficulty": "Easy",
        "difficulty_emoji": "🔴",
        "description": "Check out items by remembering a short string or picking correct change.",
    },
    "librarian": {
        "name": "Librarian",
        "emoji": "📚",
        "cost": 40,
        "payout": 3000,
        "difficulty": "Medium",
        "difficulty_emoji": "🔴",
        "description": "Organize books. Untangle words fast.",
    },
    "developer": {
        "name": "Software Developer",
        "emoji": "💻",
        "cost": 100,
        "payout": 7500,
        "difficulty": "Hard",
        "difficulty_emoji": "🔴",
        "description": "Write code under pressure! Fast typing required.",
    },
    "trader": {
        "name": "Stock Trader",
        "emoji": "📈",
        "cost": 250,
        "payout": 15000,
        "difficulty": "Expert",
        "difficulty_emoji": "🔴",
        "description": "Calculate fast math equations in your head.",
    },
}

# Cooldown settings
WORK_COOLDOWN = 1800  # 30 minutes in seconds