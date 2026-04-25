-- ============================================
-- Dragon Empire — Supabase Database Schema
-- Run this in Supabase SQL Editor
-- ============================================

-- 1. PLAYERS TABLE
CREATE TABLE IF NOT EXISTS players (
  id BIGSERIAL PRIMARY KEY,
  telegram_id BIGINT UNIQUE NOT NULL,
  username TEXT,
  first_name TEXT,
  hero_name TEXT DEFAULT 'Hero',
  level INTEGER DEFAULT 1,
  xp INTEGER DEFAULT 0,
  xp_next INTEGER DEFAULT 1000,
  hp INTEGER DEFAULT 100,
  hp_max INTEGER DEFAULT 100,
  mana INTEGER DEFAULT 50,
  mana_max INTEGER DEFAULT 50,
  gold INTEGER DEFAULT 500,
  gems INTEGER DEFAULT 0,
  energy INTEGER DEFAULT 20,
  energy_max INTEGER DEFAULT 20,
  energy_last_regen TIMESTAMPTZ DEFAULT NOW(),
  attack INTEGER DEFAULT 50,
  defense INTEGER DEFAULT 30,
  speed INTEGER DEFAULT 20,
  crit_chance INTEGER DEFAULT 5,
  guild_id INTEGER REFERENCES guilds(id) ON DELETE SET NULL,
  battles_won INTEGER DEFAULT 0,
  battles_total INTEGER DEFAULT 0,
  referred_by BIGINT,
  referral_count INTEGER DEFAULT 0,
  referral_earnings INTEGER DEFAULT 0,
  is_banned BOOLEAN DEFAULT FALSE,
  ban_reason TEXT,
  last_seen TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. GUILDS TABLE
CREATE TABLE IF NOT EXISTS guilds (
  id BIGSERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  emoji TEXT DEFAULT '⚔️',
  master_id BIGINT,
  member_count INTEGER DEFAULT 0,
  total_power BIGINT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Fix FK (guilds references players, players references guilds — use deferred)
ALTER TABLE players ADD CONSTRAINT fk_guild
  FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;

-- 3. ENEMIES TABLE
CREATE TABLE IF NOT EXISTS enemies (
  id BIGSERIAL PRIMARY KEY,
  emoji TEXT NOT NULL,
  name TEXT NOT NULL,
  level INTEGER NOT NULL,
  hp_max INTEGER NOT NULL,
  reward_gold INTEGER NOT NULL,
  reward_xp INTEGER NOT NULL,
  is_boss BOOLEAN DEFAULT FALSE,
  is_active BOOLEAN DEFAULT TRUE
);

-- Default enemies
INSERT INTO enemies (emoji, name, level, hp_max, reward_gold, reward_xp, is_boss) VALUES
  ('🐉', 'Shadow Dragon', 15, 2000, 500, 400, TRUE),
  ('👹', 'Dark Orc', 10, 800, 120, 100, FALSE),
  ('🧟', 'Zombie King', 8, 600, 80, 70, FALSE),
  ('🕷️', 'Poison Spider', 5, 300, 40, 30, FALSE),
  ('💀', 'Death Knight', 20, 3500, 900, 750, TRUE);

-- 4. ITEMS TABLE
CREATE TABLE IF NOT EXISTS items (
  id BIGSERIAL PRIMARY KEY,
  emoji TEXT NOT NULL,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('weapon','armor','potion','gem_pack')),
  rarity TEXT DEFAULT 'common' CHECK (rarity IN ('common','rare','epic','legendary')),
  atk_bonus INTEGER DEFAULT 0,
  def_bonus INTEGER DEFAULT 0,
  hp_bonus INTEGER DEFAULT 0,
  mana_bonus INTEGER DEFAULT 0,
  speed_bonus INTEGER DEFAULT 0,
  price_gold INTEGER DEFAULT 0,
  price_stars INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT TRUE
);

-- Default items
INSERT INTO items (emoji, name, type, rarity, atk_bonus, def_bonus, price_gold) VALUES
  ('🗡️', 'Steel Sword', 'weapon', 'common', 45, 0, 300),
  ('🔱', 'Trident of Doom', 'weapon', 'rare', 120, 0, 800),
  ('🛡️', 'Iron Shield', 'armor', 'common', 0, 60, 200),
  ('👑', 'Dragon Crown', 'armor', 'epic', 50, 80, 1500),
  ('❤️', 'HP Potion', 'potion', 'common', 0, 0, 50),
  ('🔮', 'Mana Crystal', 'potion', 'common', 0, 0, 80);

-- 5. PLAYER INVENTORY
CREATE TABLE IF NOT EXISTS player_inventory (
  id BIGSERIAL PRIMARY KEY,
  player_id BIGINT REFERENCES players(id) ON DELETE CASCADE,
  item_id BIGINT REFERENCES items(id),
  quantity INTEGER DEFAULT 1,
  equipped BOOLEAN DEFAULT FALSE,
  acquired_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(player_id, item_id)
);

-- 6. BATTLE LOG
CREATE TABLE IF NOT EXISTS battle_log (
  id BIGSERIAL PRIMARY KEY,
  player_id BIGINT REFERENCES players(id) ON DELETE CASCADE,
  enemy_id BIGINT REFERENCES enemies(id),
  won BOOLEAN NOT NULL,
  damage_dealt INTEGER DEFAULT 0,
  gold_earned INTEGER DEFAULT 0,
  xp_earned INTEGER DEFAULT 0,
  fought_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. DAILY QUESTS
CREATE TABLE IF NOT EXISTS quests (
  id BIGSERIAL PRIMARY KEY,
  emoji TEXT DEFAULT '📜',
  name TEXT NOT NULL,
  description TEXT,
  type TEXT NOT NULL CHECK (type IN ('battles','dungeon','guild','purchase','referral')),
  target_count INTEGER DEFAULT 1,
  reward_gold INTEGER DEFAULT 0,
  reward_gems INTEGER DEFAULT 0,
  reward_xp INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT TRUE
);

INSERT INTO quests (emoji, name, type, target_count, reward_gold, reward_xp) VALUES
  ('⚔️', '5 მტრის დამარცხება', 'battles', 5, 300, 200),
  ('🏰', 'Dungeon-ის გავლა', 'dungeon', 1, 0, 150),
  ('👥', 'გილდიაში შეხვედრა', 'guild', 1, 100, 50);

-- 8. PLAYER QUEST PROGRESS
CREATE TABLE IF NOT EXISTS player_quests (
  id BIGSERIAL PRIMARY KEY,
  player_id BIGINT REFERENCES players(id) ON DELETE CASCADE,
  quest_id BIGINT REFERENCES quests(id),
  progress INTEGER DEFAULT 0,
  completed BOOLEAN DEFAULT FALSE,
  quest_date DATE DEFAULT CURRENT_DATE,
  UNIQUE(player_id, quest_id, quest_date)
);

-- 9. AD ANALYTICS
CREATE TABLE IF NOT EXISTS ad_clicks (
  id BIGSERIAL PRIMARY KEY,
  player_id BIGINT REFERENCES players(id) ON DELETE SET NULL,
  ad_type TEXT,
  clicked_at TIMESTAMPTZ DEFAULT NOW()
);

-- 10. TRANSACTIONS
CREATE TABLE IF NOT EXISTS transactions (
  id BIGSERIAL PRIMARY KEY,
  player_id BIGINT REFERENCES players(id) ON DELETE SET NULL,
  type TEXT NOT NULL CHECK (type IN ('purchase','reward','referral','ad_reward','battle_reward')),
  amount INTEGER NOT NULL,
  currency TEXT NOT NULL CHECK (currency IN ('gold','gems','stars')),
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ===== INDEXES =====
CREATE INDEX idx_players_telegram ON players(telegram_id);
CREATE INDEX idx_battles_player ON battle_log(player_id);
CREATE INDEX idx_battles_date ON battle_log(fought_at);
CREATE INDEX idx_transactions_player ON transactions(player_id);
CREATE INDEX idx_quests_player_date ON player_quests(player_id, quest_date);

-- ===== ROW LEVEL SECURITY =====
ALTER TABLE players ENABLE ROW LEVEL SECURITY;
ALTER TABLE battle_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_quests ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS (backend uses this)
-- Anon role: no access (all requests go through backend)

-- ===== LEADERBOARD VIEW =====
CREATE OR REPLACE VIEW leaderboard AS
SELECT
  p.id,
  p.telegram_id,
  p.hero_name,
  p.level,
  p.attack + p.defense + p.speed AS power,
  p.battles_won,
  g.name AS guild_name,
  g.emoji AS guild_emoji,
  RANK() OVER (ORDER BY (p.attack + p.defense + p.speed) DESC) AS rank
FROM players p
LEFT JOIN guilds g ON p.guild_id = g.id
WHERE p.is_banned = FALSE;

-- ===== ENERGY REGEN FUNCTION =====
CREATE OR REPLACE FUNCTION regen_energy(p_telegram_id BIGINT)
RETURNS INTEGER AS $$
DECLARE
  v_player players%ROWTYPE;
  v_minutes_passed INTEGER;
  v_energy_gained INTEGER;
  v_new_energy INTEGER;
BEGIN
  SELECT * INTO v_player FROM players WHERE telegram_id = p_telegram_id;
  IF NOT FOUND THEN RETURN 0; END IF;

  v_minutes_passed := EXTRACT(EPOCH FROM (NOW() - v_player.energy_last_regen)) / 60;
  v_energy_gained := FLOOR(v_minutes_passed / 3); -- +1 energy every 3 minutes

  IF v_energy_gained > 0 THEN
    v_new_energy := LEAST(v_player.energy_max, v_player.energy + v_energy_gained);
    UPDATE players
    SET energy = v_new_energy,
        energy_last_regen = energy_last_regen + (v_energy_gained * INTERVAL '3 minutes')
    WHERE telegram_id = p_telegram_id;
    RETURN v_new_energy;
  END IF;

  RETURN v_player.energy;
END;
$$ LANGUAGE plpgsql;
