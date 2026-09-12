# FishR Web - Vercel + Supabase Commands API

This folder is now a complete Vercel project:
- Static retro Windows-style website (index.html)
- Serverless API at /api/commands (stores & serves command list via Supabase Postgres)

## Quick Start (Local)

1. Install Vercel CLI:
   npm i -g vercel

2. Copy env:
   cp .env.example .env.local

3. Get Supabase (free):
   - Go to https://supabase.com
   - Create a new project
   - Go to Project Settings → API and copy:
     • Project URL
     • service_role key (under "Project API keys" → service_role)
   - Copy them into .env.local as SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY

4. Set a strong secret in .env.local (FISHR_UPDATE_SECRET)

5. Run locally:
   vercel dev

6. Open http://localhost:3000

## Deploy to Production

1. Push this folder to GitHub (or use Vercel dashboard → Import Git repo)

2. In Vercel project settings:
   - Add the 3 environment variables (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, FISHR_UPDATE_SECRET)
   - Framework preset: Other (static)

3. Deploy

4. Your API will be live at:
   https://your-project.vercel.app/api/commands

## How the sync works

- Bot sends POST /api/commands with the full HELP_CATEGORIES
- Includes header x-fishr-secret
- Vercel function writes to Supabase Postgres table `bot_commands`
- Website fetches GET /api/commands when user opens the Commands tab
- Data is always fresh from the bot

See api/bot-sync-example.py for the exact code to add to the Python bot.

## Notes

- Data is stored in Supabase Postgres (no TTL, permanent until overwritten)
- CORS is open (*) for simplicity
- No rate limiting yet (add if you want)
- Remember to create the `bot_commands` table in Supabase (SQL is in api/commands.js)

## Vercel Deployment Error Fix

If you see:

> "No Output Directory named "public" found after the Build completed."

This happens because Vercel expects a `public/` folder by default for static sites.

**Solution (already applied):**

A `vercel.json` file has been added to the root of FishR Web with:

```json
{
  "outputDirectory": ".",
  "buildCommand": "echo 'Static site with serverless functions - no build step'",
  "framework": null
}
```

This tells Vercel to use the current directory as output (since index.html and /api/ are at the root).

**Alternative (in Vercel Dashboard):**
- Project Settings → Build & Development Settings
- Output Directory → `.` (a single dot)
- Build Command → leave empty or `echo 'no build'`
- Framework Preset → None / Other

After this change, redeploy. The site + `/api/commands` functions will work correctly.
