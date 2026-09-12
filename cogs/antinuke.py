"""
Antinuke cog: protects servers from malicious raids, nukes, and mass actions.
Monitors various events and applies punishments when thresholds are exceeded.
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Optional

import discord
from discord.ext import commands

from utils.database import db
from utils.constants import EMOJI_VERIFY, EMOJI_NO
from cogs.help import send_subcommand_help

logger = logging.getLogger(__name__)

PUNISHERS = ("ban", "kick", "mute", "strip")
DEFAULT_PUNISHMENT = "ban"

EVENT_THRESHOLDS = {
    "ban": "threshold_bans",
    "kick": "threshold_kicks",
    "channel_delete": "threshold_channel_del",
    "role_delete": "threshold_role_del",
    "channel_create": "threshold_channel_create",
    "role_create": "threshold_role_create",
}


class ActionTracker:
    """Tracks user actions for rate-limiting detection."""

    def __init__(self):
        self._actions: dict[int, list[tuple[str, float]]] = defaultdict(list)

    def record(self, user_id: int, action_type: str) -> list[tuple[str, float]]:
        self._actions[user_id].append((action_type, time.time()))
        return self._actions[user_id]

    def cleanup(self, user_id: int, max_age: int = 60) -> None:
        now = time.time()
        self._actions[user_id] = [
            (action, ts) for action, ts in self._actions[user_id] if now - ts <= max_age
        ]

    def count(self, user_id: int, action_type: str, window: int = 10) -> int:
        now = time.time()
        actions = self._actions.get(user_id, [])
        return sum(1 for action, ts in actions if action == action_type and now - ts <= window)


class Antinuke(commands.Cog):
    """Protects servers from malicious raids and nukes."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tracker = ActionTracker()
        self._punish_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._pending_punishments: dict[int, set[tuple[str, int]]] = defaultdict(set)

    async def _get_config(self, guild_id: int) -> dict:
        row = await db.fetch_one(
            "SELECT * FROM antinuke_config WHERE guild_id = ?", guild_id
        )
        if row:
            return dict(row)
        return await self._create_default_config(guild_id)

    async def _create_default_config(self, guild_id: int) -> dict:
        await db.execute(
            """INSERT OR IGNORE INTO antinuke_config 
               (guild_id, enabled, log_channel_id, threshold_bans, threshold_kicks, 
                threshold_channel_del, threshold_role_del, threshold_channel_create, 
                threshold_role_create, threshold_time_window)
               VALUES (?, 0, NULL, 3, 3, 3, 3, 5, 5, 10)""",
            guild_id,
        )
        await db.execute(
            """INSERT OR IGNORE INTO antinuke_modules (guild_id) VALUES (?)""",
            guild_id,
        )
        return await self._get_config(guild_id)

    async def _get_modules(self, guild_id: int) -> dict:
        row = await db.fetch_one(
            "SELECT * FROM antinuke_modules WHERE guild_id = ?", guild_id
        )
        if row:
            return dict(row)
        return {
            "detect_bans": 1,
            "detect_kicks": 1,
            "detect_channel_del": 1,
            "detect_role_del": 1,
            "detect_bot_add": 1,
            "detect_webhook": 1,
            "detect_role_update": 1,
            "detect_vanity_change": 1,
            "detect_guild_update": 1,
            "detect_prune": 1,
            "detect_member_role_update": 1,
            "detect_channel_create": 1,
            "detect_role_create": 1,
            "ban_punishment": DEFAULT_PUNISHMENT,
            "kick_punishment": DEFAULT_PUNISHMENT,
            "channel_del_punishment": DEFAULT_PUNISHMENT,
            "role_del_punishment": DEFAULT_PUNISHMENT,
            "bot_add_punishment": DEFAULT_PUNISHMENT,
            "webhook_punishment": DEFAULT_PUNISHMENT,
            "role_update_punishment": DEFAULT_PUNISHMENT,
            "channel_create_punishment": DEFAULT_PUNISHMENT,
            "role_create_punishment": DEFAULT_PUNISHMENT,
        }

    async def _is_whitelisted(self, guild_id: int, user_id: int) -> bool:
        row = await db.fetch_one(
            "SELECT 1 FROM antinuke_whitelist WHERE guild_id = ? AND user_id = ?",
            guild_id, user_id,
        )
        return row is not None

    async def _is_enabled(self, guild_id: int) -> bool:
        row = await db.fetch_one(
            "SELECT enabled FROM antinuke_config WHERE guild_id = ?", guild_id
        )
        return bool(row and row["enabled"])

    async def _log_action(
        self, guild_id: int, executor_id: Optional[int], action_type: str,
        target_id: Optional[int], punishment: Optional[str]
    ) -> None:
        await db.execute(
            """INSERT INTO antinuke_action_log 
               (guild_id, executor_id, action_type, target_id, punishment_applied)
               VALUES (?, ?, ?, ?, ?)""",
            guild_id, executor_id, action_type, target_id, punishment,
        )

    async def _send_log(self, guild: discord.Guild, embed: discord.Embed) -> None:
        config = await self._get_config(guild.id)
        log_channel_id = config.get("log_channel_id")
        if not log_channel_id:
            return
        channel = guild.get_channel(log_channel_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass

    async def _get_executor_from_audit(
        self, guild: discord.Guild, action_type: discord.AuditLogAction, 
        target_id: int = None
    ) -> Optional[discord.Member]:
        logger.debug(f"Antinuke: fetching audit log for action {action_type}, target={target_id}")
        try:
            async for entry in guild.audit_logs(limit=5, action=action_type):
                if target_id and entry.target.id != target_id:
                    continue
                if isinstance(entry.user, discord.Member):
                    logger.debug(f"Antinuke: found executor {entry.user} from audit log")
                    return entry.user
                member = guild.get_member(entry.user.id)
                if member:
                    logger.debug(f"Antinuke: found executor {member} from audit log")
                    return member
            logger.debug(f"Antinuke: no matching audit log entry found")
        except discord.Forbidden:
            logger.warning(f"Antinuke: permission denied accessing audit log")
        except discord.HTTPException as e:
            logger.error(f"Antinuke: audit log fetch failed: {e}")
        return None

    async def _punish(
        self, guild: discord.Guild, user: discord.Member, punishment: str,
        reason: str
    ) -> bool:
        async with self._punish_locks[guild.id]:
            try:
                if punishment == "ban":
                    await guild.ban(user, reason=reason, delete_message_days=0)
                elif punishment == "kick":
                    await guild.kick(user, reason=reason)
                elif punishment == "mute":
                    mute_role = discord.utils.get(guild.roles, name="Muted")
                    if not mute_role:
                        mute_role = await guild.create_role(
                            name="Muted", reason="Antinuke mute role"
                        )
                        for channel in guild.channels:
                            try:
                                await channel.set_permissions(
                                    mute_role, speak=False, send_messages=False
                                )
                            except discord.Forbidden:
                                pass
                    await user.add_roles(mute_role, reason=reason)
                elif punishment == "strip":
                    roles = [r for r in user.roles if r.name != "@everyone"]
                    if roles:
                        await user.remove_roles(*roles, reason=reason)
                else:
                    return False
                return True
            except discord.Forbidden:
                return False
            except discord.HTTPException as e:
                logger.error(f"Punishment failed: {e}")
                return False

    def _create_log_embed(
        self, action: str, executor: Optional[discord.Member],
        target: Optional[discord.Member], punishment: Optional[str]
    ) -> discord.Embed:
        embed = discord.Embed(
            title="🛡️ Antinuke Action",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Action", value=action, inline=True)
        if executor:
            embed.add_field(name="Executor", value=f"{executor} (`{executor.id}`)", inline=True)
        if target:
            embed.add_field(name="Target", value=f"{target} (`{target.id}`)", inline=True)
        if punishment:
            embed.add_field(name="Punishment", value=punishment, inline=True)
        return embed

    async def _process_action(
        self, guild: discord.Guild, user: discord.Member, action_type: str,
        target: Optional[discord.Member] = None
    ) -> None:
        logger.info(f"Antinuke processing action: {action_type} by {user} ({user.id}) in guild {guild.id}")
        if not await self._is_enabled(guild.id):
            logger.debug(f"Antinuke disabled for guild {guild.id}")
            return
        if await self._is_whitelisted(guild.id, user.id):
            logger.debug(f"User {user.id} is whitelisted in guild {guild.id}")
            return
        if user == guild.owner:
            logger.debug(f"User {user.id} is guild owner in guild {guild.id}")
            return
        if user == self.bot.user:
            logger.debug(f"User {user.id} is the bot itself")
            return

        modules = await self._get_modules(guild.id)

        if not modules.get(f"detect_{action_type}", False):
            return

        self.tracker.record(user.id, action_type)
        self.tracker.cleanup(user.id)

        config = await self._get_config(guild.id)
        threshold_key = EVENT_THRESHOLDS.get(action_type)
        window = config.get("threshold_time_window", 10)
        threshold = config.get(threshold_key, 3) if threshold_key else 3

        count = self.tracker.count(user.id, action_type, window)

        if count >= threshold:
            punishment_key = f"{action_type}_punishment"
            punishment = modules.get(punishment_key, DEFAULT_PUNISHMENT)

            await self._log_action(
                guild.id, user.id, action_type,
                target.id if target else None, punishment
            )
            await self._punish(guild, user, punishment, f"Antinuke: {action_type}")
            self.tracker._actions[user.id] = []

            embed = self._create_log_embed(action_type, user, target, punishment)
            await self._send_log(guild, embed)

    @commands.hybrid_group(name="antinuke", invoke_without_command=True)
    @commands.has_guild_permissions(administrator=True)
    async def antinuke(self, ctx: commands.Context):
        """Base antinuke command."""
        await send_subcommand_help(ctx, self.antinuke)

    @antinuke.command(name="setup")
    @commands.has_guild_permissions(administrator=True)
    async def antinuke_setup(self, ctx: commands.Context):
        """Set up antinuke with default values."""
        await self._create_default_config(ctx.guild.id)

        await db.execute(
            "UPDATE antinuke_config SET enabled = 1 WHERE guild_id = ?",
            ctx.guild.id,
        )

        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(content=f"{EMOJI_VERIFY} Antinuke has been set up with default values.\n"
            "- Thresholds: 3 actions per 10 seconds\n"
            "- Punishment: Ban\n"
            "- All modules enabled"),
            discord.ui.TextDisplay(content="Use `.antinuke modules` to toggle specific protections."),
            accent_color=discord.Color.green(),
        ))
        await ctx.send(view=view)

    @antinuke.command(name="modules")
    @commands.has_guild_permissions(administrator=True)
    async def antinuke_modules(self, ctx: commands.Context):
        """Enable/disable specific event monitoring."""
        modules = await self._get_modules(ctx.guild.id)

        module_list = [
            ("detect_bans", "Ban Detection", "Detect mass bans"),
            ("detect_kicks", "Kick Detection", "Detect mass kicks"),
            ("detect_channel_del", "Channel Delete", "Detect mass channel deletion"),
            ("detect_role_del", "Role Delete", "Detect mass role deletion"),
            ("detect_channel_create", "Channel Create", "Detect mass channel creation"),
            ("detect_role_create", "Role Create", "Detect mass role creation"),
            ("detect_bot_add", "Bot Add", "Detect suspicious bot additions"),
            ("detect_webhook", "Webhook Spam", "Detect webhook spam"),
            ("detect_role_update", "Role Update", "Detect spammy role updates"),
            ("detect_vanity_change", "Vanity Change", "Detect vanity URL changes"),
            ("detect_guild_update", "Guild Update", "Detect guild icon/name changes"),
            ("detect_prune", "Prune Detection", "Detect member pruning"),
            ("detect_member_role_update", "Member Role Update", "Detect unauthorized role changes"),
        ]

        lines = []
        for key, name, desc in module_list:
            status = "✅" if modules.get(key) else "❌"
            lines.append(f"{status} **{name}** - {desc}")

        view = discord.ui.LayoutView()
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(content="# Antinuke Modules\nToggle with `.antinuke toggle <module>`"),
            discord.ui.TextDisplay(content="\n".join(lines)),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(content="Available modules: bans, kicks, channel-del, role-del, bot-add, webhook, role-update, vanity-change, guild-update, prune, member-role-update"),
            accent_color=discord.Color.blue(),
        ))
        await ctx.send(view=view)

    @antinuke.command(name="toggle")
    @commands.has_guild_permissions(administrator=True)
    async def antinuke_toggle(self, ctx: commands.Context, module: str):
        """Toggle a specific antinuke module."""
        module_map = {
            "bans": "detect_bans",
            "kicks": "detect_kicks",
            "channel-del": "detect_channel_del",
            "role-del": "detect_role_del",
            "channel-create": "detect_channel_create",
            "role-create": "detect_role_create",
            "bot-add": "detect_bot_add",
            "webhook": "detect_webhook",
            "role-update": "detect_role_update",
            "vanity-change": "detect_vanity_change",
            "guild-update": "detect_guild_update",
            "prune": "detect_prune",
            "member-role-update": "detect_member_role_update",
        }

        if module.lower() not in module_map:
            return await ctx.send("❌ Invalid module. Use `.antinuke modules` to see available modules.")

        column = module_map[module.lower()]
        modules = await self._get_modules(ctx.guild.id)
        current = modules.get(column, 0)
        new_value = 0 if current else 1

        await db.execute(
            f"UPDATE antinuke_modules SET {column} = ? WHERE guild_id = ?",
            new_value, ctx.guild.id,
        )

        status = "enabled" if new_value else "disabled"
        await ctx.send(f"✅ Module `{module}` has been {status}.")

    @antinuke.command(name="whitelist")
    @commands.has_guild_permissions(administrator=True)
    async def antinuke_whitelist(self, ctx: commands.Context, action: str, user: discord.Member = None):
        """Manage whitelisted users."""
        if action.lower() == "list":
            rows = await db.fetch_all(
                "SELECT user_id FROM antinuke_whitelist WHERE guild_id = ?",
                ctx.guild.id,
            )
            if not rows:
                return await ctx.send("❌ No whitelisted users.")
            mentions = ", ".join(f"<@{r['user_id']}>" for r in rows)
            await ctx.send(f"ℹ️ Whitelisted users: {mentions}")

        elif action.lower() == "add" and user:
            await db.execute(
                "INSERT OR IGNORE INTO antinuke_whitelist (guild_id, user_id) VALUES (?, ?)",
                ctx.guild.id, user.id,
            )
            await ctx.send(f"✅ {user} has been whitelisted.")

        elif action.lower() == "remove" and user:
            await db.execute(
                "DELETE FROM antinuke_whitelist WHERE guild_id = ? AND user_id = ?",
                ctx.guild.id, user.id,
            )
            await ctx.send(f"✅ {user} has been removed from whitelist.")

        else:
            await ctx.send("❌ Usage: `.antinuke whitelist <add|remove|list> [user]`")

    @antinuke.command(name="logchannel")
    @commands.has_guild_permissions(administrator=True)
    async def antinuke_logchannel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Set the log channel for antinuke alerts."""
        target = channel or ctx.channel
        await db.execute(
            "UPDATE antinuke_config SET log_channel_id = ? WHERE guild_id = ?",
            target.id, ctx.guild.id,
        )
        await ctx.send(f"✅ Log channel set to {target.mention}.")

    @antinuke.command(name="thresholds")
    @commands.has_guild_permissions(administrator=True)
    async def antinuke_thresholds(self, ctx: commands.Context, threshold: int = None):
        """Set action thresholds."""
        if threshold is None:
            config = await self._get_config(ctx.guild.id)
            await ctx.send(f"ℹ️ Current thresholds: Bans/Kicks/ChannelDel/RoleDel: {config.get('threshold_bans', 3)} per {config.get('threshold_time_window', 10)}s | ChannelCreate/RoleCreate: {config.get('threshold_channel_create', 5)} per {config.get('threshold_time_window', 10)}s")
            return

        if threshold < 1 or threshold > 20:
            return await ctx.send("❌ Threshold must be between 1 and 20.")

        await db.execute(
            "UPDATE antinuke_config SET threshold_bans = ?, threshold_kicks = ?, threshold_channel_del = ?, threshold_role_del = ?, threshold_channel_create = ?, threshold_role_create = ? WHERE guild_id = ?",
            threshold, threshold, threshold, threshold, threshold, threshold, ctx.guild.id,
        )
        await ctx.send(f"✅ Thresholds set to {threshold} per 10 seconds.")

    @antinuke.command(name="punishment")
    @commands.has_guild_permissions(administrator=True)
    async def antinuke_punishment(self, ctx: commands.Context, event: str = None, punishment: str = None):
        """Set punishment for an event type."""
        if event is None or punishment is None:
            await ctx.send("❌ Usage: `.antinuke punishment <event|all> <ban|kick|mute|strip>`")
            return

        event_map = {
            "ban": "ban_punishment",
            "kick": "kick_punishment",
            "channel-del": "channel_del_punishment",
            "role-del": "role_del_punishment",
            "channel-create": "channel_create_punishment",
            "role-create": "role_create_punishment",
            "bot-add": "bot_add_punishment",
            "webhook": "webhook_punishment",
        }

        if event.lower() == "all":
            if punishment.lower() not in PUNISHERS:
                return await ctx.send("❌ Invalid punishment. Use: ban, kick, mute, strip")

            for column in event_map.values():
                await db.execute(
                    f"UPDATE antinuke_modules SET {column} = ? WHERE guild_id = ?",
                    punishment.lower(), ctx.guild.id,
                )
            await ctx.send(f"✅ Punishment for **all events** set to `{punishment}`.")
            return

        if event.lower() not in event_map:
            return await ctx.send("❌ Invalid event. Use: ban, kick, channel-del, role-del, channel-create, role-create, bot-add, webhook, all")

        if punishment.lower() not in PUNISHERS:
            return await ctx.send("❌ Invalid punishment. Use: ban, kick, mute, strip")

        column = event_map[event.lower()]
        await db.execute(
            f"UPDATE antinuke_modules SET {column} = ? WHERE guild_id = ?",
            punishment.lower(), ctx.guild.id,
        )
        await ctx.send(f"✅ Punishment for `{event}` set to `{punishment}`.")

    async def _handle_punishable_action(
        self, guild: discord.Guild, action_type: discord.AuditLogAction,
        action_name: str, target_id: int = None
    ) -> None:
        logger.debug(f"Antinuke: _handle_punishable_action called for {action_name}")
        if not await self._is_enabled(guild.id):
            logger.debug(f"Antinuke: disabled for guild {guild.id}")
            return
        modules = await self._get_modules(guild.id)
        if not modules.get(f"detect_{action_name}"):
            logger.debug(f"Antinuke: module detect_{action_name} disabled")
            return

        executor = await self._get_executor_from_audit(guild, action_type, target_id)
        if not executor:
            logger.debug(f"Antinuke: no executor found for {action_name}")
            return
        logger.info(f"Antinuke: executor found {executor} ({executor.id}) for {action_name}")
        if executor == guild.owner:
            logger.debug(f"Antinuke: executor is guild owner")
            return
        if executor == self.bot.user:
            logger.debug(f"Antinuke: executor is bot itself")
            return
        if await self._is_whitelisted(guild.id, executor.id):
            logger.debug(f"Antinuke: executor is whitelisted")
            return

        await self._process_action(guild, executor, action_name)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        logger.info(f"Antinuke: on_member_ban triggered - guild={guild.id}, user={user.id}")
        await self._handle_punishable_action(
            guild, discord.AuditLogAction.ban, "ban", user.id
        )

    @commands.Cog.listener()
    async def on_member_kick(self, guild: discord.Guild, user: discord.User):
        await self._handle_punishable_action(
            guild, discord.AuditLogAction.kick, "kick", user.id
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        logger.info(f"Antinuke: on_guild_channel_delete triggered - guild={channel.guild.id}, channel={channel.id}")
        await self._handle_punishable_action(
            channel.guild, discord.AuditLogAction.channel_delete, "channel_delete", channel.id
        )

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        logger.info(f"Antinuke: on_guild_channel_create triggered - guild={channel.guild.id}, channel={channel.id}")
        if not await self._is_enabled(channel.guild.id):
            return
        modules = await self._get_modules(channel.guild.id)
        if not modules.get("detect_channel_create"):
            return

        executor = await self._get_executor_from_audit(
            channel.guild, discord.AuditLogAction.channel_create, channel.id
        )
        logger.info(f"Antinuke: channel create executor = {executor}")
        if executor and executor != channel.guild.owner and not await self._is_whitelisted(channel.guild.id, executor.id):
            await self._process_action(channel.guild, executor, "channel_create")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        logger.info(f"Antinuke: on_guild_role_delete triggered - guild={role.guild.id}, role={role.id}")
        await self._handle_punishable_action(
            role.guild, discord.AuditLogAction.role_delete, "role_delete", role.id
        )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        if not await self._is_enabled(role.guild.id):
            return
        modules = await self._get_modules(role.guild.id)
        if not modules.get("detect_role_create"):
            return

        executor = await self._get_executor_from_audit(
            role.guild, discord.AuditLogAction.role_create, role.id
        )
        if executor and executor != role.guild.owner and not await self._is_whitelisted(role.guild.id, executor.id):
            await self._process_action(role.guild, executor, "role_create")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot:
            return
        if not await self._is_enabled(member.guild.id):
            return
        modules = await self._get_modules(member.guild.id)
        if not modules.get("detect_bot_add"):
            return

        executor = await self._get_executor_from_audit(
            member.guild, discord.AuditLogAction.bot_add, member.id
        )
        if executor and executor != member.guild.owner and not await self._is_whitelisted(member.guild.id, executor.id):
            await self._process_action(member.guild, executor, "bot_add")

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel):
        await self._handle_punishable_action(
            channel.guild, discord.AuditLogAction.webhook_create, "webhook"
        )

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        if before.vanity_url_code != after.vanity_url_code:
            if not await self._is_enabled(after.id):
                return
            modules = await self._get_modules(after.id)
            if not modules.get("detect_vanity_change"):
                return

            executor = await self._get_executor_from_audit(
                after, discord.AuditLogAction.guild_update
            )
            if executor and executor != after.owner and not await self._is_whitelisted(after.id, executor.id):
                punishment = modules.get("guild_update_punishment", DEFAULT_PUNISHMENT)
                await self._punish(after, executor, punishment, "Antinuke: vanity change")
                embed = self._create_log_embed("vanity_change", executor, None, punishment)
                await self._send_log(after, embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles == after.roles:
            return
        if not await self._is_enabled(after.guild.id):
            return
        modules = await self._get_modules(after.guild.id)
        if not modules.get("detect_member_role_update"):
            return

        executor = await self._get_executor_from_audit(
            after.guild, discord.AuditLogAction.member_role_update
        )
        if executor and executor != after.guild.owner and not await self._is_whitelisted(after.guild.id, executor.id):
            await self._process_action(after.guild, executor, "member_role_update")


async def setup(bot: commands.Bot):
    await bot.add_cog(Antinuke(bot))