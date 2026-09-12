-- Treasure Chest Event System
-- Adds tables for tracking treasure chest spawns, claims, and cooldowns

-- Treasure chest spawns log
CREATE TABLE IF NOT EXISTS treasure_chests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    spawned_at INTEGER NOT NULL,
    claimed_by INTEGER DEFAULT NULL,
    claimed_at INTEGER DEFAULT NULL,
    credits_reward INTEGER NOT NULL,
    fish_reward INTEGER NOT NULL,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'claimed', 'expired')),
    FOREIGN KEY (claimed_by) REFERENCES users(user_id) ON DELETE SET NULL
);

-- Cooldown tracking
CREATE TABLE IF NOT EXISTS treasure_cooldowns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER UNIQUE NOT NULL,
    last_channel_spawn INTEGER DEFAULT 0,
    last_global_spawn INTEGER DEFAULT 0
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_treasure_chests_channel ON treasure_chests(channel_id);
CREATE INDEX IF NOT EXISTS idx_treasure_chests_status ON treasure_chests(status);
CREATE INDEX IF NOT EXISTS idx_treasure_chests_spawned_at ON treasure_chests(spawned_at);
CREATE INDEX IF NOT EXISTS idx_treasure_cooldowns_channel ON treasure_cooldowns(channel_id);
