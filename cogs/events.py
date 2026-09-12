"""
Events cog: treasure chest spawning based on channel activity.
Monitors message traffic and spawns treasure chests in highly active channels.
"""

import asyncio
import logging
import random
import time
from typing import Optional
import discord
from discord.ext import commands, tasks
from discord import TextChannel

from utils.activity import track_message, start_cleanup_task, stop_cleanup_task
from utils.treasure import (
    try_spawn_chest,
    get_active_chest_count,
    clear_channel_chest,
    _active_chests
)
from utils.database import db

logger = logging.getLogger(__name__)


class TreasureEvents(commands.Cog):
    """
    Treasure chest event system.
    Spawns random treasure chests in highly active channels.
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_spawn_attempt: float = 0
        self._spawn_interval: float = 10.0  
        self._enabled: bool = True
    
    async def cog_load(self) -> None:
        """Start background tasks when cog loads."""
        await start_cleanup_task(self.bot)
        self.spawn_check_task.start()
        logger.info("Treasure event system started")
    
    async def cog_unload(self) -> None:
        """Clean up when cog unloads."""
        self.spawn_check_task.cancel()
        await stop_cleanup_task()
        logger.info("Treasure event system stopped")
    
    def _should_attempt_spawn(self) -> bool:
        """
        Rate limiting: don't attempt spawns too frequently.
        """
        now = time.time()
        elapsed = now - self._last_spawn_attempt
        return elapsed >= self._spawn_interval
    
    def _select_eligible_channel(self) -> Optional[TextChannel]:
        """
        Select a random eligible channel for chest spawn.
        Returns a channel object or None.
        """
        eligible_channels = []
        
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                
                perms = channel.permissions_for(guild.me)
                if not perms.send_messages:
                    continue
                
                
                if channel.id in _active_chests:
                    continue
                
                eligible_channels.append(channel)
        
        if not eligible_channels:
            return None
        
        
        return random.choice(eligible_channels)
    
    @tasks.loop(seconds=10)
    async def spawn_check_task(self):
        """
        Background task: periodically check for eligible channels and attempt spawn.
        Runs every 10 seconds.
        """
        if not self._enabled:
            return
        
        if not self._should_attempt_spawn():
            return
        
        self._last_spawn_attempt = time.time()
        
        try:
            
            channel = self._select_eligible_channel()
            if channel is None:
                return
            
            
            message = await try_spawn_chest(channel)
            if message:
                logger.info(f"Treasure chest spawned in channel '{channel.name}' ({channel.id})")
        
        except Exception as e:
            logger.error(f"Error in spawn check task: {e}", exc_info=True)
    
    @spawn_check_task.before_loop
    async def before_spawn_check(self):
        """Wait for bot to be ready before starting task."""
        await self.bot.wait_until_ready()
    
    
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Track message activity for treasure spawn eligibility.
        """
        
        if message.author.bot:
            return
        
        
        if not isinstance(message.channel, TextChannel):
            return
        
        await track_message(message.channel.id, time.time())
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """
        Clean up activity tracking when a channel is deleted.
        """
        from utils.activity import _channel_activity
        _channel_activity.pop(channel.id, None)
        await clear_channel_chest(channel.id)
    
    
    
    @commands.hybrid_command(name="treasurespawn", hidden=True)
    @commands.is_owner()
    async def treasure_spawn_manual(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """
        Manually spawn a treasure chest in current or specified channel.
        Owner-only command.
        """
        target_channel = channel or ctx.channel
        
        message = await try_spawn_chest(target_channel)
        if message:
            await ctx.send(f"✅ Treasure chest spawned in {target_channel.mention}!", delete_after=5)
        else:
            await ctx.send(f"❌ Could not spawn treasure chest in {target_channel.mention}. Check cooldowns/logs.", delete_after=5)
    
    @commands.hybrid_command(name="treasurestats", hidden=True)
    @commands.is_owner()
    async def treasure_stats(self, ctx: commands.Context):
        """
        Show treasure chest statistics.
        Owner-only command.
        """
        from utils.treasure import _active_chests
        from utils.activity import _channel_activity
        
        active_count = len(_active_chests)
        tracked_channels = len(_channel_activity)
        
        embed = discord.Embed(
            title="Treasure Chest Stats",
            color=discord.Color.gold()
        )
        embed.add_field(name="Active Chests", value=str(active_count), inline=True)
        embed.add_field(name="Tracked Channels", value=str(tracked_channels), inline=True)
        embed.add_field(name="System Enabled", value=str(self._enabled), inline=True)
        
        await ctx.send(embed=embed, delete_after=10)
    
    @commands.hybrid_command(name="treasuretoggle", hidden=True)
    @commands.is_owner()
    async def treasure_toggle(self, ctx: commands.Context, enabled: bool = None):
        """
        Enable/disable treasure chest spawning.
        """
        if enabled is None:
            enabled = not self._enabled
        
        self._enabled = enabled
        status = "enabled" if enabled else "disabled"
        await ctx.send(f"✅ Treasure chest spawning {status}.", delete_after=5)


async def setup(bot: commands.Bot):
    await bot.add_cog(TreasureEvents(bot))
