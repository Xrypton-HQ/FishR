# Bot → API Sync Example (Python)
# Works with both Redis and Supabase versions of the API

# Add this to your FishR bot (e.g. in bot.py on_ready or in a new cog)

import os
import httpx
from cogs.help import HELP_CATEGORIES   # or wherever your categories live

FISHR_API_URL = os.getenv("FISHR_API_URL", "https://your-project.vercel.app/api/commands")
FISHR_API_SECRET = os.getenv("FISHR_UPDATE_SECRET")  # must match the one in Vercel env

async def sync_commands_to_website():
    """Call this from on_ready or after loading cogs."""
    payload = {
        "categories": HELP_CATEGORIES
    }

    headers = {
        "Content-Type": "application/json",
        "x-fishr-secret": FISHR_API_SECRET
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(FISHR_API_URL, json=payload, headers=headers)
            print(f"[FishR Web] Commands synced to Redis API: {resp.status_code} {resp.json()}")
        except Exception as e:
            print(f"[FishR Web] Failed to sync commands: {e}")


# Example usage in bot.py:
#
# async def on_ready(self):
#     ...
#     await sync_commands_to_website()
#
# Or run it manually with a hidden command:
# @commands.command()
# async def syncweb(self, ctx):
#     await sync_commands_to_website()
#     await ctx.send("Commands pushed to website Redis.")

# Requirements: pip install httpx
# Set these env vars on the bot host:
#   FISHR_API_URL=https://fishr-web.vercel.app/api/commands
#   FISHR_UPDATE_SECRET=the-same-secret-you-set-in-vercel
