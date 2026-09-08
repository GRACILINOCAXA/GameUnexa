-- GameUnexa - PostgreSQL persistente para autenticação
-- Compatível com Supabase, Neon, Railway PostgreSQL e PostgreSQL padrão.
-- O aplicativo também executa esta inicialização automaticamente quando
-- DATABASE_URL estiver configurada na Vercel.

CREATE TABLE IF NOT EXISTS gameunexa_usuarios (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    token_recuperacao TEXT,
    idade INTEGER,
    gosto_jogos TEXT,
    telefone TEXT,
    steam_id64 TEXT,
    steam_api_key TEXT,
    steam_library_path TEXT,
    steam_online BOOLEAN NOT NULL DEFAULT FALSE,
    steam_current_game TEXT,
    steam_current_game_appid BIGINT,
    steam_playtime_minutes INTEGER NOT NULL DEFAULT 0,
    steam_last_update TEXT,
    hydra_library_path TEXT,
    hydra_account_email TEXT,
    hydra_usuario TEXT,
    hydra_pin TEXT,
    hydra_token TEXT,
    hydra_current_game TEXT,
    hydra_last_update TEXT,
    library_style TEXT NOT NULL DEFAULT 'classic',
    library_view TEXT NOT NULL DEFAULT '2d',
    auto_library_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    auto_library_folders TEXT NOT NULL DEFAULT '[]',
    auto_last_scan TEXT,
    foto_perfil TEXT,
    data_cadastro TEXT,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_gameunexa_usuarios_email_lower
    ON gameunexa_usuarios (LOWER(email));

CREATE TABLE IF NOT EXISTS gameunexa_pending_registrations (
    email TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    codigo TEXT NOT NULL,
    expira_em DOUBLE PRECISION NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gameunexa_pending_expira
    ON gameunexa_pending_registrations (expira_em);

-- Compatibilidade com bancos criados por versões anteriores.
ALTER TABLE gameunexa_usuarios ADD COLUMN IF NOT EXISTS steam_online BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE gameunexa_usuarios ADD COLUMN IF NOT EXISTS steam_current_game TEXT;
ALTER TABLE gameunexa_usuarios ADD COLUMN IF NOT EXISTS steam_current_game_appid BIGINT;
ALTER TABLE gameunexa_usuarios ADD COLUMN IF NOT EXISTS steam_playtime_minutes INTEGER NOT NULL DEFAULT 0;
ALTER TABLE gameunexa_usuarios ADD COLUMN IF NOT EXISTS steam_last_update TEXT;
ALTER TABLE gameunexa_usuarios ADD COLUMN IF NOT EXISTS library_view TEXT NOT NULL DEFAULT '2d';
ALTER TABLE gameunexa_usuarios ADD COLUMN IF NOT EXISTS auto_library_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE gameunexa_usuarios ADD COLUMN IF NOT EXISTS auto_library_folders TEXT NOT NULL DEFAULT '[]';
ALTER TABLE gameunexa_usuarios ADD COLUMN IF NOT EXISTS auto_last_scan TEXT;
ALTER TABLE gameunexa_usuarios ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE gameunexa_usuarios ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
