import discord
import asyncio
from discord.ext import commands
import logging
import time

from utils.database import (
    get_user, create_user, create_job_entry, get_job, set_user_job,
    update_work_timestamp, safe_deduct_gems
)
from utils.embeds import (
    job_selected_layout, insufficient_gems_layout,
    no_job_layout, work_cooldown_layout, work_success_layout,
    minigame_layout
)
from utils.constants import JOBS, WORK_COOLDOWN, EMOJI_CREDITS
from utils.cooldowns import get_remaining_cooldown, format_cooldown
from utils.views import JobSelectView
from utils.minigames import (
    JanitorView, CashierMemoryView, LibrarianView, DeveloperView, TraderView
)
from config import WORK_COOLDOWN as COOLDOWN_SECONDS

logger = logging.getLogger(__name__)


class Jobs(commands.Cog):
    """Job and work commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="job", aliases=["jobs", "career"])
    async def job(self, ctx: commands.Context):
        """Open the employment center to select a job."""
        user_id = ctx.author.id

        await create_user(user_id)
        await create_job_entry(user_id)

        user = await get_user(user_id)
        job_row = await get_job(user_id)

        gems = user["gems"] if user else 0
        current_job = job_row["current_job"] if job_row else None

        async def on_job_selected(job_key: str):
            pass

        view = JobSelectView(
            author_id=ctx.author.id,
            gems=gems,
            current_job=current_job,
            on_job_selected=on_job_selected,
            timeout=60.0
        )

        await ctx.send(view=view)

    @commands.hybrid_command(name="work", aliases=["shift"])
    async def work(self, ctx: commands.Context):
        """Work your job to earn credits."""
        user_id = ctx.author.id

        await create_user(user_id)
        await create_job_entry(user_id)

        job_row = await get_job(user_id)

        if not job_row or not job_row["current_job"]:
            await ctx.send(view=no_job_layout())
            return

        current_job = job_row["current_job"]
        last_used = job_row["work_last_used"] if job_row["work_last_used"] else 0

        remaining = get_remaining_cooldown(last_used, WORK_COOLDOWN)
        if remaining > 0:
            await ctx.send(view=work_cooldown_layout(remaining))
            return

        job = JOBS.get(current_job)
        if not job:
            await ctx.send(view=minigame_layout("❌ Error", "Invalid job.", discord.Color.red()))
            return

        payout = job["payout"]

        async def on_complete():
            pass

        if current_job == "janitor":
            view = JanitorView(
                author_id=user_id,
                payout=payout,
                on_complete=on_complete,
                timeout=5.0
            )
            await ctx.send(view=view)
        elif current_job == "cashier":
            view = CashierMemoryView(
                author_id=user_id,
                payout=payout,
                on_complete=on_complete,
                timeout=10.0
            )
            await ctx.send(view=view)
        elif current_job == "librarian":
            view = LibrarianView(
                author_id=user_id,
                payout=payout,
                on_complete=on_complete,
                timeout=15.0
            )
            await ctx.send(view=view)
        elif current_job == "developer":
            view = DeveloperView(
                author_id=user_id,
                payout=payout,
                on_complete=on_complete,
                timeout=20.0
            )
            await ctx.send(view=view)
        elif current_job == "trader":
            view = TraderView(
                author_id=user_id,
                payout=payout,
                on_complete=on_complete,
                timeout=15.0
            )
            await ctx.send(view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Jobs(bot))