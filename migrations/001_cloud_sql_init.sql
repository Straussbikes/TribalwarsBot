-- Migração Inicial Cloud SQL (PostgreSQL) para TribalWarsBot
-- Tabelas: app_users, game_accounts, game_worlds, villages

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Tabela de Utilizadores da Aplicação
CREATE TABLE IF NOT EXISTS app_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    license_type VARCHAR(50) NOT NULL DEFAULT 'standard',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users(email);

-- 2. Tabela de Contas de Jogo
CREATE TABLE IF NOT EXISTS game_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    app_user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    game_username VARCHAR(100) NOT NULL,
    credentials_vault BYTEA NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_game_username UNIQUE (app_user_id, game_username)
);

CREATE INDEX IF NOT EXISTS idx_game_accounts_user_id ON game_accounts(app_user_id);
CREATE INDEX IF NOT EXISTS idx_game_accounts_username ON game_accounts(game_username);

-- 3. Tabela de Mundos de Jogo Concorrentes
CREATE TABLE IF NOT EXISTS game_worlds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_account_id UUID NOT NULL REFERENCES game_accounts(id) ON DELETE CASCADE,
    world_code VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_account_world UNIQUE (game_account_id, world_code)
);

CREATE INDEX IF NOT EXISTS idx_game_worlds_account_id ON game_worlds(game_account_id);
CREATE INDEX IF NOT EXISTS idx_game_worlds_code ON game_worlds(world_code);

-- 4. Tabela de Aldeias
CREATE TABLE IF NOT EXISTS villages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_world_id UUID NOT NULL REFERENCES game_worlds(id) ON DELETE CASCADE,
    village_game_id INTEGER NOT NULL,
    village_name VARCHAR(100) NOT NULL,
    coord_x INTEGER NOT NULL,
    coord_y INTEGER NOT NULL,
    active_build_model_id VARCHAR(100),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_world_village_game_id UNIQUE (game_world_id, village_game_id)
);

CREATE INDEX IF NOT EXISTS idx_villages_world_id ON villages(game_world_id);
CREATE INDEX IF NOT EXISTS idx_villages_game_id ON villages(village_game_id);
