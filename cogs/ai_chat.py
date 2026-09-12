import discord
import asyncio
import random
import logging
from discord.ext import commands
from typing import Optional
from discord.ui import Modal, TextInput

from utils.ai import (
    get_ai_response,
    needs_search,
    context,
    get_web_enhanced_response,
    track_user,
    SYSTEM_PROMPT
)
from utils.database import db
from cogs.help import send_subcommand_help

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = 3


class PromptModal(Modal, title="Set System Prompt"):
    prompt_input = TextInput(
        label="System Prompt",
        placeholder="Enter new system prompt...",
        style=discord.TextStyle.long,
        max_length=2000
    )

    def __init__(self, current_prompt: str = ""):
        super().__init__()
        self.prompt_input.default = current_prompt

    async def on_submit(self, interaction: discord.Interaction):
        await db.execute(
            "INSERT OR REPLACE INTO ai_prompts (guild_id, prompt) VALUES (?, ?)",
            interaction.guild_id, self.prompt_input.value
        )
        await interaction.response.send_message("Prompt updated!", ephemeral=True)


class AIChat(commands.Cog):
    """AI chat functionality."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cooldowns: dict = {}
        self._enabled = True
        self._channels_enabled = True

    def _is_on_cooldown(self, user_id: int) -> bool:
        return self._cooldowns.get(user_id, 0) > asyncio.get_event_loop().time()

    def _set_cooldown(self, user_id: int):
        self._cooldowns[user_id] = asyncio.get_event_loop().time() + COOLDOWN_SECONDS

    async def _build_messages(self, user_id: int, query: str, search_results: list = None, guild_id: int = None) -> list:
        messages = await context.get_context(user_id)

        if search_results:
            search_context = "Recent info: " + "; ".join(
                r.get("body", "")[:100] for r in search_results[:2]
            )
            messages.append({"role": "system", "content": search_context})

        messages.append({"role": "user", "content": query})
        return messages

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.author.id == self.bot.user.id:
            return

        if not self._enabled:
            return

        if message.guild is None:
            return

        ai_channel_ids = await db.fetch_all(
            "SELECT channel_id FROM ai_channels WHERE guild_id = ? AND enabled = 1",
            message.guild.id
        )
        ai_channel_ids = [row["channel_id"] for row in ai_channel_ids]

        is_ai_channel = message.channel.id in ai_channel_ids
        is_mentioned = self.bot.user in message.mentions
        is_reply_to_bot = (
            message.reference 
            and message.reference.resolved 
            and message.reference.resolved.author.id == self.bot.user.id
        )

        should_respond = is_ai_channel or is_mentioned or is_reply_to_bot

        # If not in AI channel and channels mode is disabled, only respond to mentions/replies
        if not self._channels_enabled and not (is_mentioned or is_reply_to_bot):
            return

        if not should_respond:
            return

        if self._is_on_cooldown(message.author.id):
            return

        self._set_cooldown(message.author.id)

        try:
            # Fetch recent channel messages for context
            recent_messages = []
            try:
                async for msg in message.channel.history(limit=12, before=message):
                    if not msg.author.bot and msg.content.strip():
                        recent_messages.append(f"{msg.author.display_name}: {msg.content[:150]}")
            except Exception:
                pass

            channel_context = ""
            if recent_messages:
                channel_context = "[Recent messages in this channel]\n" + "\n".join(recent_messages[::-1])

            messages = await self._build_messages(message.author.id, message.content, [], message.guild.id)

            # Inject channel history at the beginning if available
            if channel_context:
                messages.insert(0, {"role": "system", "content": channel_context})

            guild_prompt = await db.fetch_one(
                "SELECT prompt FROM ai_prompts WHERE guild_id = ?",
                message.guild.id
            )
            custom_prompt = guild_prompt["prompt"] if guild_prompt else None

            async with message.channel.typing():
                await asyncio.sleep(random.uniform(1, 3))

                if needs_search(message.content):
                    response = await get_web_enhanced_response(message.content, messages, system_prompt=custom_prompt)
                else:
                    response = await get_ai_response(messages, system_prompt=custom_prompt)

                if response:
                    response = response.strip().strip('"').strip("'")
                    
                    await message.reply(response[:200])
                    await track_user(message.author.display_name)

                    await context.add_message(message.author.id, "user", message.content, message.author.display_name)
                    await context.add_message(message.author.id, "assistant", response, "FishR")

        except Exception as e:
            logger.error(f"AI chat error: {e}")
            try:
                await message.channel.send("idk broke rn")
            except:
                pass

    @commands.hybrid_group(name="ai", invoke_without_command=True)
    async def ai_cmd(self, ctx: commands.Context):
        """AI management commands."""
        await send_subcommand_help(ctx, ctx.command)

    @ai_cmd.group(name="channel", invoke_without_command=True)
    async def ai_channel(self, ctx: commands.Context):
        """AI channel management."""
        await send_subcommand_help(ctx, ctx.command)

    @ai_channel.command(name="set")
    async def ai_channel_set(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Set an AI channel where the bot will respond to all messages."""
        channel = channel or ctx.channel
        await db.execute(
            "INSERT OR REPLACE INTO ai_channels (guild_id, channel_id, enabled) VALUES (?, ?, 1)",
            ctx.guild.id, channel.id
        )
        await ctx.send(f"AI channel set to {channel.mention}")

    @ai_channel.command(name="remove")
    async def ai_channel_remove(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Remove an AI channel."""
        channel = channel or ctx.channel
        cursor = await db.execute(
            "DELETE FROM ai_channels WHERE guild_id = ? AND channel_id = ?",
            ctx.guild.id, channel.id
        )
        if cursor.rowcount > 0:
            await ctx.send(f"AI channel removed from {channel.mention}")
        else:
            await ctx.send(f"{channel.mention} is not an AI channel.")

    @ai_channel.command(name="list")
    async def ai_channel_list(self, ctx: commands.Context):
        """List all AI channels in the server."""
        rows = await db.fetch_all(
            "SELECT channel_id FROM ai_channels WHERE guild_id = ? AND enabled = 1",
            ctx.guild.id
        )
        if not rows:
            await ctx.send("No AI channels set in this server.")
            return

        channels = []
        for row in rows:
            ch = ctx.guild.get_channel(row["channel_id"])
            if ch:
                channels.append(ch.mention)
            else:
                channels.append(f"<#{row['channel_id']}>")

        await ctx.send("AI channels:\n" + "\n".join(channels))

    @ai_channel.command(name="toggle")
    async def ai_channel_toggle(self, ctx: commands.Context):
        """Toggle AI channels on/off."""
        self._channels_enabled = not self._channels_enabled
        status = "enabled" if self._channels_enabled else "disabled"
        await ctx.send(f"AI channels are now {status}.")

    @ai_cmd.command(name="toggle")
    async def ai_toggle(self, ctx: commands.Context):
        """Toggle the entire AI on/off (on by default)."""
        self._enabled = not self._enabled
        status = "enabled" if self._enabled else "disabled"
        await ctx.send(f"AI is now {status}.")

    @ai_cmd.group(name="prompt", invoke_without_command=True)
    async def ai_prompt(self, ctx: commands.Context):
        """AI prompt management."""
        await send_subcommand_help(ctx, ctx.command)

    @ai_prompt.command(name="set")
    async def ai_prompt_set(self, ctx: commands.Context):
        """Set a custom system prompt via modal."""
        if ctx.interaction:
            current = await db.fetch_one(
                "SELECT prompt FROM ai_prompts WHERE guild_id = ?",
                ctx.guild.id
            )
            current_prompt = current["prompt"] if current else SYSTEM_PROMPT.strip()
            modal = PromptModal(current_prompt)
            await ctx.interaction.response.send_modal(modal)
        else:
            await ctx.send("Use `/ai prompt set` (slash command) to open the prompt editor.")

    @ai_prompt.command(name="reset")
    async def ai_prompt_reset(self, ctx: commands.Context):
        """Reset the system prompt to default."""
        await db.execute(
            "DELETE FROM ai_prompts WHERE guild_id = ?",
            ctx.guild.id
        )
        await ctx.send("System prompt reset to default.")


async def setup(bot: commands.Bot):
    await bot.add_cog(AIChat(bot))