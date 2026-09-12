-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    credits INTEGER DEFAULT 0,
    bank INTEGER DEFAULT 0,
    gems INTEGER DEFAULT 0,
    daily_streak INTEGER DEFAULT 0,
    last_daily INTEGER DEFAULT 0
);

-- Inventory table
CREATE TABLE IF NOT EXISTS inventory (
    user_id INTEGER PRIMARY KEY,
    fish INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Upgrades table
CREATE TABLE IF NOT EXISTS upgrades (
    user_id INTEGER PRIMARY KEY,
    stronger_rod INTEGER DEFAULT 0,
    new_rod INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Buffs table
CREATE TABLE IF NOT EXISTS buffs (
    user_id INTEGER PRIMARY KEY,
    frenzy_until INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Market table (single row with id=1)
CREATE TABLE IF NOT EXISTS market (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    fish_price INTEGER DEFAULT 5,
    updated_at INTEGER
);

-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    user_id INTEGER PRIMARY KEY,
    current_job TEXT DEFAULT NULL,
    work_last_used INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Steal cooldowns table
CREATE TABLE IF NOT EXISTS steal_cooldowns (
    user_id INTEGER PRIMARY KEY,
    last_stolen INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Beg cooldowns table
CREATE TABLE IF NOT EXISTS beg_cooldowns (
    user_id INTEGER PRIMARY KEY,
    last_beg INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Juul stats table
CREATE TABLE IF NOT EXISTS juul_stats (
    guild_id TEXT PRIMARY KEY,
    data BLOB,
    enabled BOOLEAN DEFAULT 1,
    flavor TEXT DEFAULT 'mango',
    holder_id TEXT,
    hits INTEGER DEFAULT 0,
    passes INTEGER DEFAULT 0,
    steals INTEGER DEFAULT 0
);

-- Juul users table
CREATE TABLE IF NOT EXISTS juul_users (
    guild_id TEXT,
    user_id TEXT,
    hits INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id),
    FOREIGN KEY (guild_id) REFERENCES juul_stats(guild_id) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_users_credits ON users(credits DESC);
CREATE INDEX IF NOT EXISTS idx_market_updated ON market(updated_at);

-- Owner whitelist table
CREATE TABLE IF NOT EXISTS whitelist (
    user_id INTEGER PRIMARY KEY
);

-- System prompts table
CREATE TABLE IF NOT EXISTS ai_prompts (
    guild_id INTEGER PRIMARY KEY,
    prompt TEXT NOT NULL
);

-- Prefixes table
CREATE TABLE IF NOT EXISTS prefixes (
    guild_id INTEGER NOT NULL,
    prefix TEXT NOT NULL,
    PRIMARY KEY (guild_id, prefix)
);

-- AI channels table
CREATE TABLE IF NOT EXISTS ai_channels (
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    enabled INTEGER DEFAULT 1,
    PRIMARY KEY (guild_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_prefixes_guild ON prefixes(guild_id);
CREATE INDEX IF NOT EXISTS idx_ai_channels_guild ON ai_channels(guild_id);

-- Antinuke tables
CREATE TABLE IF NOT EXISTS antinuke_config (
    guild_id INTEGER PRIMARY KEY,
    enabled INTEGER DEFAULT 0,
    log_channel_id INTEGER,
    threshold_bans INTEGER DEFAULT 3,
    threshold_kicks INTEGER DEFAULT 3,
    threshold_channel_del INTEGER DEFAULT 3,
    threshold_role_del INTEGER DEFAULT 3,
    threshold_channel_create INTEGER DEFAULT 5,
    threshold_role_create INTEGER DEFAULT 5,
    threshold_time_window INTEGER DEFAULT 10
);

CREATE TABLE IF NOT EXISTS antinuke_whitelist (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, user_id),
    FOREIGN KEY (guild_id) REFERENCES antinuke_config(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS antinuke_modules (
    guild_id INTEGER PRIMARY KEY,
    ban_punishment TEXT DEFAULT 'ban',
    kick_punishment TEXT DEFAULT 'ban',
    channel_del_punishment TEXT DEFAULT 'ban',
    role_del_punishment TEXT DEFAULT 'ban',
    bot_add_punishment TEXT DEFAULT 'ban',
    webhook_punishment TEXT DEFAULT 'ban',
    role_update_punishment TEXT DEFAULT 'ban',
    detect_bans INTEGER DEFAULT 1,
    detect_kicks INTEGER DEFAULT 1,
    detect_channel_del INTEGER DEFAULT 1,
    detect_role_del INTEGER DEFAULT 1,
    detect_bot_add INTEGER DEFAULT 1,
    detect_webhook INTEGER DEFAULT 1,
    detect_role_update INTEGER DEFAULT 1,
    detect_vanity_change INTEGER DEFAULT 1,
    detect_guild_update INTEGER DEFAULT 1,
    detect_prune INTEGER DEFAULT 1,
    detect_member_role_update INTEGER DEFAULT 1,
    detect_channel_create INTEGER DEFAULT 1,
    detect_role_create INTEGER DEFAULT 1,
    channel_create_punishment TEXT DEFAULT 'ban',
    role_create_punishment TEXT DEFAULT 'ban'
);

CREATE TABLE IF NOT EXISTS antinuke_action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    executor_id INTEGER,
    action_type TEXT NOT NULL,
    target_id INTEGER,
    punishment_applied TEXT,
    timestamp INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (guild_id) REFERENCES antinuke_config(guild_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_antinuke_config_guild ON antinuke_config(guild_id);
CREATE INDEX IF NOT EXISTS idx_antinuke_whitelist_guild ON antinuke_whitelist(guild_id);
CREATE INDEX IF NOT EXISTS idx_antinuke_modules_guild ON antinuke_modules(guild_id);
CREATE INDEX IF NOT EXISTS idx_antinuke_log_guild ON antinuke_action_log(guild_id);

-- Giveaway tables
CREATE TABLE IF NOT EXISTS giveaways (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    prize TEXT NOT NULL,
    image TEXT,
    winners INTEGER NOT NULL,
    duration INTEGER NOT NULL,
    started_at INTEGER NOT NULL,
    ends_at INTEGER NOT NULL,
    ended INTEGER DEFAULT 0,
    winner_ids TEXT
);

CREATE TABLE IF NOT EXISTS giveaway_entries (
    giveaway_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (giveaway_id, user_id),
    FOREIGN KEY (giveaway_id) REFERENCES giveaways(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS giveaway_blacklist (
    user_id INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS giveaway_channels (
    guild_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_giveaways_ends_at ON giveaways(ends_at);
CREATE INDEX IF NOT EXISTS idx_giveaways_guild ON giveaways(guild_id);

-- Welcome config table
CREATE TABLE IF NOT EXISTS welcome_config (
    guild_id INTEGER PRIMARY KEY,
    channel_id INTEGER,
    enabled INTEGER DEFAULT 1,
    embed_mode INTEGER DEFAULT 0,
    title TEXT,
    description TEXT,
    image_url TEXT
);