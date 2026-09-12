# Database configuration
DATABASE_PATH = "database.db"
WAL_MODE = True

# Bot configuration
PREFIX = "."
TOKEN = "#ripjuut"

# Owner configuration
OWNER_ID = 1513893188341989487

# API Keys (loaded from environment, never hardcode secrets!)
import os
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Game settings
FISHING_COOLDOWN = 5  # seconds
FISHING_WAIT_MIN = 2  # min seconds for fish bite
FISHING_WAIT_MAX = 5  # max seconds for fish bite
FISHING_REACTION_WINDOW = 2  # seconds to reel in
FISHING_BASE_MIN = 1
FISHING_BASE_MAX = 3

# Frenzy settings
FRENZY_DURATION = 3600  # 1 hour in seconds
FRENZY_PRICE = 700

# Market settings
MARKET_REFRESH_MINUTES = 5
MARKET_PRICE_MIN = 2
MARKET_PRICE_MAX = 8

# Work cooldown
WORK_COOLDOWN = 1800  # 30 minutes in seconds

# Steal cooldown
STEAL_COOLDOWN = 120  # 2 minutes in seconds

# FishR Website API (Vercel + Upstash Redis sync)
FISHR_API_URL = "https://fishr.vercel.app/api/commands"
FISHR_UPDATE_SECRET = "change-this-secret-in-production"
