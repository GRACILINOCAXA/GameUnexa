PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    hydra_library_path TEXT,
    hydra_account_email TEXT,
    hydra_usuario TEXT,
    hydra_pin TEXT,
    hydra_token TEXT,
    hydra_current_game TEXT,
    hydra_last_update TEXT,
    library_style TEXT NOT NULL DEFAULT 'classic',
    foto_perfil TEXT,
    data_cadastro TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS categorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS jogos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    genero TEXT NOT NULL,
    desenvolvedora TEXT NOT NULL,
    ano INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS jogo_categoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jogo_id INTEGER NOT NULL,
    categoria_id INTEGER NOT NULL,
    UNIQUE(jogo_id, categoria_id),
    FOREIGN KEY(jogo_id) REFERENCES jogos(id) ON DELETE CASCADE,
    FOREIGN KEY(categoria_id) REFERENCES categorias(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    autor_email TEXT NOT NULL,
    titulo TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    imagem_url TEXT,
    data_criacao TEXT NOT NULL,
    visivel INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(autor_email) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comentarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    autor_email TEXT NOT NULL,
    texto TEXT NOT NULL,
    data_criacao TEXT NOT NULL,
    visivel INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY(autor_email) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS amizades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_solicitante TEXT NOT NULL,
    email_receptor TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendente',
    data_solicitacao TEXT NOT NULL,
    data_aceito TEXT,
    UNIQUE(email_solicitante, email_receptor),
    FOREIGN KEY(email_solicitante) REFERENCES usuarios(email) ON DELETE CASCADE,
    FOREIGN KEY(email_receptor) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS biblioteca (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_usuario TEXT NOT NULL,
    jogo_id INTEGER NOT NULL,
    data_adicao TEXT NOT NULL,
    tempo_jogado_horas INTEGER NOT NULL DEFAULT 0,
    concluido INTEGER NOT NULL DEFAULT 0,
    platinado INTEGER NOT NULL DEFAULT 0,
    origem TEXT DEFAULT 'manual',
    launcher TEXT DEFAULT 'manual',
    codigo_origem TEXT DEFAULT '',
    cover_url TEXT DEFAULT '',
    executable_path TEXT DEFAULT '',
    install_folder TEXT DEFAULT '',
    executable_name TEXT DEFAULT '',
    updated_at TEXT,
    manual_override INTEGER NOT NULL DEFAULT 0,
    favorito INTEGER NOT NULL DEFAULT 0,
    last_launched_at TEXT,
    last_played_game TEXT DEFAULT '',
    status TEXT DEFAULT 'offline',
    conquistas_desbloqueadas INTEGER NOT NULL DEFAULT 0,
    conquistas_total INTEGER NOT NULL DEFAULT 0,
    UNIQUE(email_usuario, jogo_id),
    FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE,
    FOREIGN KEY(jogo_id) REFERENCES jogos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jogo_id INTEGER NOT NULL,
    email_usuario TEXT NOT NULL,
    titulo TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    nota INTEGER NOT NULL,
    data_criacao TEXT NOT NULL,
    visivel INTEGER NOT NULL DEFAULT 1,
    curtidas INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(jogo_id) REFERENCES jogos(id) ON DELETE CASCADE,
    FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS review_comentarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL,
    email_usuario TEXT NOT NULL,
    texto TEXT NOT NULL,
    data_criacao TEXT NOT NULL,
    visivel INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(review_id) REFERENCES reviews(id) ON DELETE CASCADE,
    FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notificacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_receptor TEXT NOT NULL,
    tipo TEXT NOT NULL,
    titulo TEXT NOT NULL,
    descricao TEXT NOT NULL,
    link TEXT,
    data_criacao TEXT NOT NULL,
    lida INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(email_receptor) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS post_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    email_usuario TEXT NOT NULL,
    UNIQUE(post_id, email_usuario),
    FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS suporte_categorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suporte_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suporte_chamados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    titulo TEXT NOT NULL,
    categoria_slug TEXT NOT NULL,
    descricao TEXT NOT NULL,
    passos_reproducao TEXT,
    resultado_esperado TEXT,
    resultado_obtido TEXT,
    prioridade TEXT NOT NULL DEFAULT 'Média',
    versao_gamelink TEXT,
    so TEXT,
    navegador TEXT,
    resolucao_tela TEXT,
    data_criacao TEXT NOT NULL,
    hora_criacao TEXT NOT NULL,
    usuario_email TEXT NOT NULL,
    usuario_nome TEXT NOT NULL,
    usuario_id INTEGER,
    email_contato TEXT,
    status_slug TEXT NOT NULL DEFAULT 'aberto',
    status_id INTEGER,
    FOREIGN KEY(usuario_email) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS suporte_mensagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chamado_id INTEGER NOT NULL,
    autor_email TEXT NOT NULL,
    autor_nome TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'usuario',
    data_envio TEXT NOT NULL,
    FOREIGN KEY(chamado_id) REFERENCES suporte_chamados(id) ON DELETE CASCADE,
    FOREIGN KEY(autor_email) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS suporte_anexos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chamado_id INTEGER NOT NULL,
    mensagem_id INTEGER,
    nome_original TEXT NOT NULL,
    nome_arquivo TEXT NOT NULL,
    caminho TEXT NOT NULL,
    tipo_mime TEXT,
    tamanho INTEGER NOT NULL DEFAULT 0,
    data_upload TEXT NOT NULL,
    FOREIGN KEY(chamado_id) REFERENCES suporte_chamados(id) ON DELETE CASCADE,
    FOREIGN KEY(mensagem_id) REFERENCES suporte_mensagens(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS suporte_historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chamado_id INTEGER NOT NULL,
    usuario_email TEXT NOT NULL,
    acao TEXT NOT NULL,
    detalhes TEXT,
    data_registro TEXT NOT NULL,
    FOREIGN KEY(chamado_id) REFERENCES suporte_chamados(id) ON DELETE CASCADE,
    FOREIGN KEY(usuario_email) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mensagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_remetente TEXT NOT NULL,
    email_destino TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    data_envio TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'sent',
    canceled_at TEXT,
    canceled_by TEXT,
    FOREIGN KEY(email_remetente) REFERENCES usuarios(email) ON DELETE CASCADE,
    FOREIGN KEY(email_destino) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mensagem_reacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mensagem_id INTEGER NOT NULL,
    email_usuario TEXT NOT NULL,
    emoji TEXT NOT NULL,
    data_reacao TEXT NOT NULL,
    UNIQUE(mensagem_id, email_usuario),
    FOREIGN KEY(mensagem_id) REFERENCES mensagens(id) ON DELETE CASCADE,
    FOREIGN KEY(email_usuario) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS known_executables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exe_name TEXT NOT NULL,
    exe_path TEXT NOT NULL UNIQUE,
    sha256 TEXT,
    display_name TEXT,
    icon_path TEXT,
    launcher TEXT DEFAULT 'local',
    last_seen TEXT,
    times_detected INTEGER NOT NULL DEFAULT 0,
    is_game INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS launcher_library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_usuario TEXT NOT NULL,
    nome_jogo TEXT NOT NULL,
    launcher TEXT NOT NULL DEFAULT 'manual',
    caminho TEXT,
    executavel TEXT,
    pasta TEXT,
    icone TEXT,
    ultima_verificacao TEXT,
    hash TEXT,
    appid TEXT,
    launcher_path TEXT,
    launcher_type TEXT,
    launcher_exe TEXT,
    launcher_args TEXT,
    last_scan TEXT,
    UNIQUE(email_usuario, launcher, appid, nome_jogo)
);

CREATE TABLE IF NOT EXISTS installed_games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_usuario TEXT NOT NULL,
    nome TEXT NOT NULL,
    launcher TEXT NOT NULL DEFAULT 'manual',
    appid TEXT,
    library_root TEXT,
    game_folder TEXT,
    exe_name TEXT,
    exe_path TEXT,
    icon_path TEXT,
    cover_path TEXT,
    installed INTEGER NOT NULL DEFAULT 0,
    favorite INTEGER NOT NULL DEFAULT 0,
    last_scan TEXT,
    hash TEXT,
    UNIQUE(email_usuario, launcher, nome)
);

CREATE TABLE IF NOT EXISTS background_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL DEFAULT 'default',
    effect TEXT DEFAULT '',
    file TEXT DEFAULT '',
    folder TEXT DEFAULT '',
    color1 TEXT DEFAULT '#38bdf8',
    color2 TEXT DEFAULT '#0f172a',
    speed REAL NOT NULL DEFAULT 1,
    opacity REAL NOT NULL DEFAULT 1,
    fps INTEGER NOT NULL DEFAULT 60,
    shuffle INTEGER NOT NULL DEFAULT 0,
    transition INTEGER NOT NULL DEFAULT 500,
    options TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);
