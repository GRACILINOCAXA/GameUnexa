import os
import json
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash
from modelos.usuario import obter_senha_admin_padrao
from modelos.suporte import CATEGORIAS_SUPORTE, STATUS_SUPORTE_INICIAIS


def gerar_hash_senha(password: str) -> str:
    return generate_password_hash(password)

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'gamelink.db')

SCHEMA = """
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
    epic_library_path TEXT,
    hydra_account_email TEXT,
    hydra_usuario TEXT,
    hydra_pin TEXT,
    hydra_token TEXT,
    hydra_current_game TEXT,
    hydra_last_update TEXT,
    library_style TEXT NOT NULL DEFAULT 'classic',
    auto_library_enabled INTEGER NOT NULL DEFAULT 0,
    auto_library_folders TEXT NOT NULL DEFAULT '[]',
    auto_last_scan TEXT,
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

CREATE TABLE IF NOT EXISTS sound_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    icon TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sound_effects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    storage_url TEXT DEFAULT '',
    category_id INTEGER,
    icon TEXT DEFAULT '',
    duration REAL NOT NULL DEFAULT 0,
    volume REAL NOT NULL DEFAULT 1.0,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    play_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(category_id) REFERENCES sound_categories(id) ON DELETE SET NULL,
    FOREIGN KEY(created_by) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sound_effect_favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    effect_id INTEGER NOT NULL,
    user_email TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(effect_id, user_email),
    FOREIGN KEY(effect_id) REFERENCES sound_effects(id) ON DELETE CASCADE,
    FOREIGN KEY(user_email) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sound_effect_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    effect_id INTEGER NOT NULL,
    user_email TEXT NOT NULL,
    played_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(effect_id) REFERENCES sound_effects(id) ON DELETE CASCADE,
    FOREIGN KEY(user_email) REFERENCES usuarios(email) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sound_effects_active
    ON sound_effects (is_active, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_sound_effects_category
    ON sound_effects (category_id, is_active);

CREATE INDEX IF NOT EXISTS idx_sound_effects_name
    ON sound_effects (name COLLATE NOCASE);

CREATE INDEX IF NOT EXISTS idx_sound_effects_created_by
    ON sound_effects (created_by, is_active);

CREATE INDEX IF NOT EXISTS idx_sound_favorites_user
    ON sound_effect_favorites (user_email, effect_id);

CREATE INDEX IF NOT EXISTS idx_sound_history_user
    ON sound_effect_history (user_email, played_at DESC);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    conn.execute('PRAGMA busy_timeout = 30000;')
    return conn


def _ensure_usuario_columns(conn):
    cursor = conn.cursor()
    cursor.execute('PRAGMA table_info(usuarios)')
    existing_columns = {row[1] for row in cursor.fetchall()}

    columns_to_add = [
        ('steam_id64', 'TEXT'),
        ('steam_api_key', 'TEXT'),
        ('steam_library_path', 'TEXT'),
        ('hydra_library_path', 'TEXT'),
        ('epic_library_path', 'TEXT'),
        ('steam_online', 'INTEGER'),
        ('steam_current_game', 'TEXT'),
        ('steam_current_game_appid', 'INTEGER'),
        ('steam_playtime_minutes', 'INTEGER'),
        ('steam_last_update', 'TEXT'),
        ('hydra_account_email', 'TEXT'),
        ('hydra_usuario', 'TEXT'),
        ('hydra_pin', 'TEXT'),
        ('hydra_token', 'TEXT'),
        ('hydra_current_game', 'TEXT'),
        ('hydra_last_update', 'TEXT'),
        ('library_style', "TEXT NOT NULL DEFAULT 'classic'"),
        ('library_view', "TEXT NOT NULL DEFAULT '2d'"),
        ('auto_library_enabled', 'INTEGER NOT NULL DEFAULT 0'),
        ('auto_library_folders', "TEXT NOT NULL DEFAULT '[]'"),
        ('auto_last_scan', 'TEXT'),
        ('foto_perfil', 'TEXT'),
        ('data_cadastro', 'TEXT'),
    ]

    for column_name, column_type in columns_to_add:
        if column_name not in existing_columns:
            cursor.execute(
                f'ALTER TABLE usuarios ADD COLUMN {column_name} {column_type}'
            )

    conn.commit()


def _ensure_mensagem_columns(conn):
    cursor = conn.cursor()
    cursor.execute('PRAGMA table_info(mensagens)')
    existing_columns = {row[1] for row in cursor.fetchall()}

    for column_name, column_type in [('status', 'TEXT'), ('canceled_at', 'TEXT'), ('canceled_by', 'TEXT')]:
        if column_name not in existing_columns:
            cursor.execute(f'ALTER TABLE mensagens ADD COLUMN {column_name} {column_type}')

    conn.commit()


def _ensure_biblioteca_columns(conn):
    cursor = conn.cursor()
    cursor.execute('PRAGMA table_info(biblioteca)')
    existing_columns = {row[1] for row in cursor.fetchall()}

    added_launcher = False
    for column_name, column_type in [
        ('origem', 'TEXT'),
        ('launcher', 'TEXT'),
        ('codigo_origem', 'TEXT'),
        ('cover_url', 'TEXT'),
        ('favorito', 'INTEGER'),
        ('executable_path', 'TEXT'),
        ('install_folder', 'TEXT'),
        ('executable_name', 'TEXT'),
        ('updated_at', 'TEXT'),
        ('manual_override', 'INTEGER'),
        ('last_launched_at', 'TEXT'),
        ('last_played_game', 'TEXT'),
        ('status', 'TEXT'),
        ('conquistas_desbloqueadas', 'INTEGER'),
        ('conquistas_total', 'INTEGER'),
    ]:
        if column_name not in existing_columns:
            cursor.execute(f'ALTER TABLE biblioteca ADD COLUMN {column_name} {column_type}')
            if column_name == 'launcher':
                added_launcher = True

    if added_launcher:
        cursor.execute(
            """
            UPDATE biblioteca
            SET launcher = LOWER(COALESCE(origem, CASE WHEN platinado = 1 THEN 'steam' ELSE 'manual' END))
            WHERE launcher IS NULL OR launcher = ''
            """
        )

    if 'codigo_origem' in existing_columns or added_launcher:
        cursor.execute(
            """
            UPDATE biblioteca
            SET codigo_origem = CAST(jogo_id AS TEXT)
            WHERE LOWER(TRIM(COALESCE(launcher, origem, ''))) = 'steam'
              AND LOWER(TRIM(COALESCE(codigo_origem, ''))) = 'steam'
            """
        )
        cursor.execute(
            """
            UPDATE biblioteca
            SET codigo_origem = CAST(jogo_id AS TEXT),
                origem = 'steam',
                launcher = 'steam'
            WHERE (codigo_origem IS NULL OR TRIM(codigo_origem) = '')
              AND EXISTS (
                  SELECT 1 FROM jogos
                  WHERE jogos.id = biblioteca.jogo_id
                    AND LOWER(TRIM(jogos.desenvolvedora)) = 'steam'
              )
            """
        )

    conn.commit()


def _ensure_launcher_library_columns(conn):
    cursor = conn.cursor()
    cursor.execute('PRAGMA table_info(launcher_library)')
    existing_columns = {row[1] for row in cursor.fetchall()}

    for column_name, column_type in [
        ('launcher_path', 'TEXT'),
        ('launcher_type', 'TEXT'),
        ('launcher_exe', 'TEXT'),
        ('launcher_args', 'TEXT'),
        ('last_scan', 'TEXT'),
    ]:
        if column_name not in existing_columns:
            cursor.execute(f'ALTER TABLE launcher_library ADD COLUMN {column_name} {column_type}')

    conn.commit()


def _ensure_installed_games_table(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='installed_games'")
    if cursor.fetchone():
        return
    cursor.execute(
        '''
        CREATE TABLE installed_games (
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
        )
        '''
    )
    conn.commit()


def _ensure_background_columns(conn):
    cursor = conn.cursor()
    cursor.execute('PRAGMA table_info(background_settings)')
    existing_columns = {row[1] for row in cursor.fetchall()}
    if 'options' not in existing_columns:
        cursor.execute("ALTER TABLE background_settings ADD COLUMN options TEXT NOT NULL DEFAULT '{}'")
    conn.commit()


def init_db():
    print('================================')
    print('Inicializando GameUnexa')
    print(f'Arquivo SQLite: {os.path.abspath(DB_PATH)}')
    print('================================')
    conn = get_connection()
    conn.execute('PRAGMA journal_mode = WAL;')
    conn.executescript(SCHEMA)
    _ensure_usuario_columns(conn)
    _ensure_biblioteca_columns(conn)
    _ensure_launcher_library_columns(conn)
    _ensure_installed_games_table(conn)
    _ensure_background_columns(conn)
    _ensure_mensagem_columns(conn)
    _ensure_biblioteca_columns(conn)
    conn.execute(
        '''
        UPDATE biblioteca
        SET origem = 'steam', launcher = 'steam'
        WHERE LOWER(TRIM(COALESCE(codigo_origem, ''))) = 'steam'
        '''
    )
    conn.commit()
    conn.close()


def obter_biblioteca_filtrada(email: str, launcher: str | None = None) -> list:
    from modelos.amigos_biblioteca import BibliotecaJogo

    conn = get_connection()
    if launcher and launcher in {'steam', 'hydra', 'manual'}:
        cursor = conn.execute(
            '''
            SELECT *
            FROM biblioteca
            WHERE email_usuario = ?
              AND (
                    LOWER(TRIM(launcher)) = ?
                    OR (
                        launcher IS NULL OR LOWER(TRIM(launcher)) = ''
                    ) AND LOWER(TRIM(COALESCE(origem, ''))) = ?
                  )
            ORDER BY id ASC
            ''',
            (email, launcher.strip().lower(), launcher.strip().lower()),
        )
    else:
        cursor = conn.execute(
            'SELECT * FROM biblioteca WHERE email_usuario = ? ORDER BY id ASC',
            (email,),
        )

    itens = []
    for row in cursor.fetchall():
        if 'origem' in row.keys() and row['origem']:
            origem_banco = str(row['origem']).strip().lower()
        elif 'launcher' in row.keys() and row['launcher']:
            origem_banco = str(row['launcher']).strip().lower()
        else:
            origem_banco = 'steam' if row['platinado'] else 'manual'

        item = BibliotecaJogo(row['id'], row['email_usuario'], row['jogo_id'], origem_banco)
        item.data_adicao = _dt_from_db(row['data_adicao']) or item.data_adicao
        item.tempo_jogado_horas = row['tempo_jogado_horas'] or 0
        item.concluido = bool(row['concluido'])
        item.platinado = bool(row['platinado'])
        item.codigo_origem = row['codigo_origem'] or '' if 'codigo_origem' in row.keys() else ''
        if item.codigo_origem.strip().lower() == 'steam':
            origem_banco = 'steam'
        item.cover_url = row['cover_url'] or '' if 'cover_url' in row.keys() else ''
        item.launcher = 'steam' if origem_banco == 'steam' else (str(row['launcher']).strip().lower() if 'launcher' in row.keys() and row['launcher'] else origem_banco)
        item.origem = origem_banco
        item.favorito = bool(row['favorito']) if 'favorito' in row.keys() and row['favorito'] is not None else False
        item.executable_path = row['executable_path'] or '' if 'executable_path' in row.keys() else ''
        item.install_folder = row['install_folder'] or '' if 'install_folder' in row.keys() else ''
        item.pasta_instalacao = item.install_folder or item.pasta_instalacao
        item.executable_name = row['executable_name'] or '' if 'executable_name' in row.keys() else ''
        item.updated_at = row['updated_at'] if 'updated_at' in row.keys() else None
        item.manual_override = bool(row['manual_override']) if 'manual_override' in row.keys() else False
        item.last_launched_at = _dt_from_db(row['last_launched_at']) if 'last_launched_at' in row.keys() and row['last_launched_at'] else None
        item.last_played_game = row['last_played_game'] or '' if 'last_played_game' in row.keys() else ''
        item.status = row['status'] or 'offline' if 'status' in row.keys() and row['status'] else 'offline'
        item.conquistas_desbloqueadas = row['conquistas_desbloqueadas'] or 0 if 'conquistas_desbloqueadas' in row.keys() else 0
        item.conquistas_total = row['conquistas_total'] or 0 if 'conquistas_total' in row.keys() else 0
        itens.append(item)
    conn.close()
    return itens


def obter_biblioteca_steam(email: str) -> list:
    """Retorna apenas os jogos da biblioteca do launcher Steam."""
    return obter_biblioteca_filtrada(email, 'steam')


def obter_biblioteca_hydra(email: str) -> list:
    """Retorna apenas os jogos da biblioteca do launcher Hydra."""
    return obter_biblioteca_filtrada(email, 'hydra')


def obter_biblioteca_manual(email: str) -> list:
    """Retorna apenas os jogos adicionados manualmente."""
    return obter_biblioteca_filtrada(email, 'manual')


def obter_biblioteca_unificada(email: str) -> list:
    """Retorna todos os jogos da biblioteca do usuário."""
    return obter_biblioteca_filtrada(email, None)


def seed_initial_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM usuarios')
    if cursor.fetchone()[0] == 0:
        senha_admin = obter_senha_admin_padrao()
        cursor.execute(
            'INSERT INTO usuarios (nome, email, password, is_admin) VALUES (?, ?, ?, ?)',
            ('Caxa', 'admin@gamelink.com', gerar_hash_senha(senha_admin), 1)
        )

    cursor.execute('SELECT COUNT(*) FROM categorias')
    if cursor.fetchone()[0] == 0:
        categorias = [('RPG',), ('Ação',)]
        cursor.executemany('INSERT INTO categorias (nome) VALUES (?)', categorias)

    cursor.execute('SELECT COUNT(*) FROM jogos')
    if cursor.fetchone()[0] == 0:
        jogos = [
            ('The Witcher 3', 'RPG', 'CD Projekt Red', 2015),
            ('Elden Ring', 'RPG', 'FromSoftware', 2022),
            ('GTA V', 'Ação', 'Rockstar', 2013),
        ]
        cursor.executemany(
            'INSERT INTO jogos (titulo, genero, desenvolvedora, ano) VALUES (?, ?, ?, ?)',
            jogos
        )

    cursor.execute('SELECT COUNT(*) FROM suporte_categorias')
    if cursor.fetchone()[0] == 0:
        categorias = [(slug, nome) for slug, nome in CATEGORIAS_SUPORTE]
        cursor.executemany('INSERT INTO suporte_categorias (slug, nome) VALUES (?, ?)', categorias)

    cursor.execute('SELECT COUNT(*) FROM suporte_status')
    if cursor.fetchone()[0] == 0:
        status = [(slug, nome) for slug, nome in STATUS_SUPORTE_INICIAIS]
        cursor.executemany('INSERT INTO suporte_status (slug, nome) VALUES (?, ?)', status)

    conn.commit()
    conn.close()


def reset_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    seed_initial_data()


def _dt_to_db(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat(sep=' ', timespec='seconds')


def _dt_from_db(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')


def carregar_estado_persistido():
    from modelos.usuario import USUARIOS_DB, Usuario, Admin
    from modelos.jogo import JOGOS_DB, Jogo, Categoria
    from modelos.posts import POSTS_DB, COMENTARIOS_POSTS_DB, Post, Comentario
    from modelos.amigos_biblioteca import (
        AMIZADES_DB, BIBLIOTECA_DB, REVIEWS_DB, REVIEW_COMENTARIOS_DB,
        NOTIFICACOES_DB, MENSAGENS_DB,
        SolicitacaoAmizade, BibliotecaJogo, Review, ComentarioReview,
        Notificacao, Mensagem,
    )

    conn = get_connection()
    cursor = conn.cursor()

    USUARIOS_DB.clear()
    JOGOS_DB.clear()
    POSTS_DB.clear()
    COMENTARIOS_POSTS_DB.clear()
    AMIZADES_DB.clear()
    BIBLIOTECA_DB.clear()
    REVIEWS_DB.clear()
    REVIEW_COMENTARIOS_DB.clear()
    NOTIFICACOES_DB.clear()
    MENSAGENS_DB.clear()

    cursor.execute('SELECT * FROM usuarios ORDER BY id ASC')
    for row in cursor.fetchall():
        usuario = Admin(row['id'], row['nome'], row['email'], row['password']) if row['is_admin'] else Usuario(row['id'], row['nome'], row['email'], row['password'])
        usuario.token_recuperacao = row['token_recuperacao']
        usuario.idade = row['idade']
        usuario.gosto_jogos = row['gosto_jogos'] or ''
        usuario.telefone = row['telefone'] or ''
        usuario.steam_id64 = row['steam_id64'] or ''
        usuario.steam_api_key = row['steam_api_key'] or ''
        usuario.steam_library_path = row['steam_library_path'] if 'steam_library_path' in row.keys() else ''
        usuario.epic_library_path = row['epic_library_path'] if 'epic_library_path' in row.keys() else ''
        usuario.hydra_library_path = row['hydra_library_path'] if 'hydra_library_path' in row.keys() else ''
        usuario.hydra_account_email = row['hydra_account_email'] or ''
        usuario.hydra_usuario = row['hydra_usuario'] or ''
        usuario.hydra_pin = row['hydra_pin'] or ''
        usuario.hydra_token = row['hydra_token'] or ''
        legacy_style = row['library_style'] if 'library_style' in row.keys() else 'classic'
        stored_view = row['library_view'] if 'library_view' in row.keys() else ''
        usuario.library_view = '3d' if legacy_style == '3d' else (stored_view if stored_view in {'2d', '3d'} else '2d')
        usuario.auto_library_enabled = bool(row['auto_library_enabled']) if 'auto_library_enabled' in row.keys() else False
        try:
            usuario.auto_library_folders = json.loads(row['auto_library_folders'] or '[]') if 'auto_library_folders' in row.keys() else []
        except (TypeError, ValueError):
            usuario.auto_library_folders = []
        if not isinstance(usuario.auto_library_folders, list):
            usuario.auto_library_folders = []
        usuario.auto_last_scan = row['auto_last_scan'] if 'auto_last_scan' in row.keys() else None
        usuario.foto_perfil = row['foto_perfil'] or ''
        usuario.data_cadastro = row['data_cadastro'] or None
        if not usuario.data_cadastro:
            usuario.data_cadastro = datetime.now().isoformat(timespec='seconds')
        USUARIOS_DB[usuario.email.lower()] = usuario

    cursor.execute('SELECT * FROM categorias ORDER BY id ASC')
    categorias_db = {row['id']: Categoria(row['id'], row['nome']) for row in cursor.fetchall()}

    cursor.execute('SELECT * FROM jogos ORDER BY id ASC')
    for row in cursor.fetchall():
        jogo = Jogo(row['id'], row['titulo'], row['genero'], row['desenvolvedora'], row['ano'])
        JOGOS_DB[jogo.id] = jogo

    cursor.execute('SELECT jogo_id, categoria_id FROM jogo_categoria ORDER BY id ASC')
    for row in cursor.fetchall():
        jogo = JOGOS_DB.get(row['jogo_id'])
        categoria = categorias_db.get(row['categoria_id'])
        if jogo and categoria:
            try:
                jogo.associar_categoria(categoria)
            except Exception:
                pass

    cursor.execute('SELECT * FROM posts ORDER BY id ASC')
    for row in cursor.fetchall():
        post = Post(row['id'], row['autor_email'], row['titulo'], row['conteudo'], row['imagem_url'])
        post.data_criacao = _dt_from_db(row['data_criacao']) or post.data_criacao
        post.visivel = bool(row['visivel'])
        POSTS_DB[post.id] = post

    cursor.execute('SELECT * FROM comentarios ORDER BY id ASC')
    for row in cursor.fetchall():
        comentario = Comentario(row['id'], row['post_id'], row['autor_email'], row['texto'])
        comentario.data_criacao = _dt_from_db(row['data_criacao']) or comentario.data_criacao
        comentario.visivel = bool(row['visivel'])
        COMENTARIOS_POSTS_DB.append(comentario)
        post = POSTS_DB.get(comentario.post_id)
        if post:
            post.adicionar_comentario(comentario.id)

    cursor.execute('SELECT * FROM post_likes ORDER BY id ASC')
    for row in cursor.fetchall():
        post = POSTS_DB.get(row['post_id'])
        if post and row['email_usuario'] not in post.usuarios_curtidas:
            post.usuarios_curtidas.append(row['email_usuario'])

    cursor.execute('SELECT * FROM amizades ORDER BY id ASC')
    for row in cursor.fetchall():
        amizade = SolicitacaoAmizade(row['id'], row['email_solicitante'], row['email_receptor'])
        amizade.status = row['status']
        amizade.data_solicitacao = _dt_from_db(row['data_solicitacao']) or amizade.data_solicitacao
        amizade.data_aceito = _dt_from_db(row['data_aceito']) if 'data_aceito' in row.keys() else None
        chave = f"{min(amizade.email_solicitante, amizade.email_receptor)}_{max(amizade.email_solicitante, amizade.email_receptor)}"
        AMIZADES_DB[chave] = amizade

    cursor.execute('SELECT * FROM biblioteca ORDER BY id ASC')
    for row in cursor.fetchall():
        if 'origem' in row.keys() and row['origem']:
            origem_banco = str(row['origem']).strip().lower()
        elif 'launcher' in row.keys() and row['launcher']:
            origem_banco = str(row['launcher']).strip().lower()
        else:
            origem_banco = 'steam' if row['platinado'] else 'manual'

        item = BibliotecaJogo(row['id'], row['email_usuario'], row['jogo_id'], origem_banco)
        item.data_adicao = _dt_from_db(row['data_adicao']) or item.data_adicao
        item.tempo_jogado_horas = row['tempo_jogado_horas'] or 0
        item.concluido = bool(row['concluido'])
        item.platinado = bool(row['platinado'])
        item.codigo_origem = row['codigo_origem'] or '' if 'codigo_origem' in row.keys() else ''
        if item.codigo_origem.strip().lower() == 'steam':
            origem_banco = 'steam'
        item.cover_url = row['cover_url'] or '' if 'cover_url' in row.keys() else ''
        item.launcher = 'steam' if origem_banco == 'steam' else (str(row['launcher']).strip().lower() if 'launcher' in row.keys() and row['launcher'] else origem_banco)
        item.origem = origem_banco
        item.executable_path = row['executable_path'] or '' if 'executable_path' in row.keys() else ''
        item.install_folder = row['install_folder'] or '' if 'install_folder' in row.keys() else ''
        item.pasta_instalacao = item.install_folder
        item.executable_name = row['executable_name'] or '' if 'executable_name' in row.keys() else ''
        item.updated_at = row['updated_at'] if 'updated_at' in row.keys() else None
        item.manual_override = bool(row['manual_override']) if 'manual_override' in row.keys() else False
        item.last_launched_at = _dt_from_db(row['last_launched_at']) if 'last_launched_at' in row.keys() and row['last_launched_at'] else None
        item.last_played_game = row['last_played_game'] or '' if 'last_played_game' in row.keys() else ''
        item.status = row['status'] or 'offline' if 'status' in row.keys() and row['status'] else 'offline'
        BIBLIOTECA_DB[f"{item.email_usuario}_{item.jogo_id}"] = item

    cursor.execute('SELECT * FROM reviews ORDER BY id ASC')
    for row in cursor.fetchall():
        review = Review(row['id'], row['jogo_id'], row['email_usuario'], row['titulo'], row['conteudo'], row['nota'])
        review.data_criacao = _dt_from_db(row['data_criacao']) or review.data_criacao
        review.visivel = bool(row['visivel'])
        review.curtidas = row['curtidas'] or 0
        REVIEWS_DB[review.id] = review

    cursor.execute('SELECT * FROM review_comentarios ORDER BY id ASC')
    for row in cursor.fetchall():
        comentario = ComentarioReview(row['id'], row['review_id'], row['email_usuario'], row['texto'])
        comentario.data_criacao = _dt_from_db(row['data_criacao']) or comentario.data_criacao
        comentario.visivel = bool(row['visivel'])
        REVIEW_COMENTARIOS_DB.append(comentario)
        review = REVIEWS_DB.get(comentario.review_id)
        if review:
            review.adicionar_comentario(comentario.id)

    cursor.execute('SELECT * FROM notificacoes ORDER BY id ASC')
    for row in cursor.fetchall():
        notif = Notificacao(row['id'], row['email_receptor'], row['tipo'], row['titulo'], row['descricao'], row['link'])
        notif.data_criacao = _dt_from_db(row['data_criacao']) or notif.data_criacao
        notif.lida = bool(row['lida'])
        NOTIFICACOES_DB.setdefault(notif.email_receptor, []).append(notif)

    cursor.execute('SELECT * FROM mensagens ORDER BY id ASC')
    colunas_mensagens = {row[1] for row in conn.execute('PRAGMA table_info(mensagens)').fetchall()}
    for row in cursor.fetchall():
        mensagem = Mensagem(row['id'], row['email_remetente'], row['email_destino'], row['conteudo'])
        mensagem.data_envio = _dt_from_db(row['data_envio']) or mensagem.data_envio
        if 'status' in colunas_mensagens:
            mensagem.status = row['status'] or 'sent'
        if 'canceled_at' in colunas_mensagens:
            mensagem.canceled_at = _dt_from_db(row['canceled_at']) if row['canceled_at'] else None
        if 'canceled_by' in colunas_mensagens:
            mensagem.canceled_by = row['canceled_by']
        if mensagem.status == 'cancelada':
            mensagem.conteudo = ''
        MENSAGENS_DB.append(mensagem)

    cursor.execute('SELECT * FROM mensagem_reacoes ORDER BY id ASC')
    for row in cursor.fetchall():
        mensagem = next((item for item in MENSAGENS_DB if item.id == row['mensagem_id']), None)
        if mensagem:
            mensagem.registrar_reacao(row['emoji'], row['email_usuario'])

    print(f'[Banco] Jogos carregados: {len(JOGOS_DB)}')
    print(f'[Banco] Itens de biblioteca carregados: {len(BIBLIOTECA_DB)}')
    for item in BIBLIOTECA_DB.values():
        estado_executavel = 'encontrado' if getattr(item, 'executable_path', '') else 'vazio'
        print(f'[Banco] Jogo {item.jogo_id}: executável {estado_executavel}')

    conn.close()
    return {
        'categorias_db': categorias_db,
    }


def persistir_usuario(user):
    conn = get_connection()
    try:
        _ensure_usuario_columns(conn)
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(usuarios)')
        colunas = {row[1] for row in cursor.fetchall()}

        campos_insert = ['nome', 'email', 'password']
        valores_insert = [user.nome, user.email, user._Usuario__password if hasattr(user, '_Usuario__password') else '']

        if 'token_recuperacao' in colunas:
            campos_insert.append('token_recuperacao')
            valores_insert.append(getattr(user, 'token_recuperacao', None))
        if 'idade' in colunas:
            campos_insert.append('idade')
            valores_insert.append(getattr(user, 'idade', None))
        if 'gosto_jogos' in colunas:
            campos_insert.append('gosto_jogos')
            valores_insert.append(getattr(user, 'gosto_jogos', ''))
        if 'telefone' in colunas:
            campos_insert.append('telefone')
            valores_insert.append(getattr(user, 'telefone', ''))
        if 'steam_id64' in colunas:
            campos_insert.append('steam_id64')
            valores_insert.append(getattr(user, 'steam_id64', ''))
        if 'steam_api_key' in colunas:
            campos_insert.append('steam_api_key')
            valores_insert.append(getattr(user, 'steam_api_key', ''))
        if 'steam_library_path' in colunas:
            campos_insert.append('steam_library_path')
            valores_insert.append(getattr(user, 'steam_library_path', ''))
        if 'epic_library_path' in colunas:
            campos_insert.append('epic_library_path')
            valores_insert.append(getattr(user, 'epic_library_path', ''))
        if 'hydra_library_path' in colunas:
            campos_insert.append('hydra_library_path')
            valores_insert.append(getattr(user, 'hydra_library_path', ''))
        if 'hydra_account_email' in colunas:
            campos_insert.append('hydra_account_email')
            valores_insert.append(getattr(user, 'hydra_account_email', ''))
        if 'hydra_usuario' in colunas:
            campos_insert.append('hydra_usuario')
            valores_insert.append(getattr(user, 'hydra_usuario', ''))
        if 'hydra_pin' in colunas:
            campos_insert.append('hydra_pin')
            valores_insert.append(getattr(user, 'hydra_pin', ''))
        if 'hydra_token' in colunas:
            campos_insert.append('hydra_token')
            valores_insert.append(getattr(user, 'hydra_token', ''))
        if 'hydra_current_game' in colunas:
            campos_insert.append('hydra_current_game')
            valores_insert.append(getattr(user, 'hydra_current_game', ''))
        if 'hydra_last_update' in colunas:
            campos_insert.append('hydra_last_update')
            valores_insert.append(getattr(user, 'hydra_last_update', None))
        if 'library_style' in colunas:
            campos_insert.append('library_style')
            valores_insert.append('3d' if getattr(user, 'library_view', '2d') == '3d' else 'classic')
        if 'library_view' in colunas:
            campos_insert.append('library_view')
            valores_insert.append(getattr(user, 'library_view', '2d'))
        if 'auto_library_enabled' in colunas:
            campos_insert.append('auto_library_enabled')
            valores_insert.append(1 if getattr(user, 'auto_library_enabled', False) else 0)
        if 'auto_library_folders' in colunas:
            campos_insert.append('auto_library_folders')
            valores_insert.append(json.dumps(getattr(user, 'auto_library_folders', []) or [], ensure_ascii=False))
        if 'auto_last_scan' in colunas:
            campos_insert.append('auto_last_scan')
            valores_insert.append(getattr(user, 'auto_last_scan', None))
        if 'foto_perfil' in colunas:
            campos_insert.append('foto_perfil')
            valores_insert.append(getattr(user, 'foto_perfil', ''))
        if 'data_cadastro' in colunas:
            campos_insert.append('data_cadastro')
            valores_insert.append(_dt_to_db(getattr(user, 'data_cadastro', None)))
        if 'is_admin' in colunas:
            campos_insert.append('is_admin')
            valores_insert.append(1 if user.__class__.__name__ == 'Admin' else 0)

        placeholders = ', '.join('?' for _ in campos_insert)
        upsert_columns = []
        for campo in campos_insert:
            if campo == 'email':
                continue
            upsert_columns.append(f'{campo}=excluded.{campo}')

        cursor.execute(
            f'''
            INSERT INTO usuarios ({', '.join(campos_insert)})
            VALUES ({placeholders})
            ON CONFLICT(email) DO UPDATE SET {', '.join(upsert_columns)}
            ''',
            valores_insert,
        )
        conn.commit()
    finally:
        conn.close()


def persistir_categoria(categoria):
    conn = get_connection()
    conn.execute(
        'INSERT INTO categorias (id, nome) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET nome=excluded.nome',
        (categoria.id, categoria.nome),
    )
    conn.commit()
    conn.close()


def persistir_jogo(jogo, categorias=None):
    conn = get_connection()
    conn.execute(
        '''
        INSERT INTO jogos (id, titulo, genero, desenvolvedora, ano) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET titulo=excluded.titulo, genero=excluded.genero,
            desenvolvedora=excluded.desenvolvedora, ano=excluded.ano
        ''',
        (jogo.id, jogo.titulo, jogo.genero, jogo.desenvolvedora, jogo.ano),
    )
    conn.execute('DELETE FROM jogo_categoria WHERE jogo_id = ?', (jogo.id,))
    categorias = categorias or []
    for categoria in categorias:
        categoria_id = getattr(categoria, 'id', categoria)
        conn.execute('INSERT OR IGNORE INTO jogo_categoria (jogo_id, categoria_id) VALUES (?, ?)', (jogo.id, categoria_id))
    conn.commit()
    conn.close()


def remover_jogo(jogo_id: int):
    conn = get_connection()
    conn.execute('DELETE FROM jogo_categoria WHERE jogo_id = ?', (jogo_id,))
    conn.execute('DELETE FROM jogos WHERE id = ?', (jogo_id,))
    conn.commit()
    conn.close()


def excluir_usuario_completo(email: str):
    email = (email or '').strip().lower()
    if not email:
        raise ValueError('Email do usuário é obrigatório')

    conn = get_connection()
    try:
        conn.execute('BEGIN')
        foto_relativa = None
        usuario_row = conn.execute('SELECT foto_perfil FROM usuarios WHERE lower(email) = ?', (email,)).fetchone()
        if usuario_row:
            foto_relativa = usuario_row['foto_perfil'] or ''

        conn.execute('DELETE FROM usuarios WHERE lower(email) = ?', (email,))

        if foto_relativa:
            if foto_relativa.startswith('/static/uploads/'):
                nome_arquivo = foto_relativa.split('/static/uploads/', 1)[1]
                caminho_arquivo = os.path.join(BASE_DIR, 'static', 'uploads', nome_arquivo)
                if os.path.exists(caminho_arquivo):
                    os.remove(caminho_arquivo)
            elif foto_relativa.startswith('static/uploads/'):
                caminho_arquivo = os.path.join(BASE_DIR, foto_relativa)
                if os.path.exists(caminho_arquivo):
                    os.remove(caminho_arquivo)

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def persistir_post(post):
    conn = get_connection()
    conn.execute(
        '''
        INSERT INTO posts (id, autor_email, titulo, conteudo, imagem_url, data_criacao, visivel)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET autor_email=excluded.autor_email, titulo=excluded.titulo,
            conteudo=excluded.conteudo, imagem_url=excluded.imagem_url, data_criacao=excluded.data_criacao,
            visivel=excluded.visivel
        ''',
        (post.id, post.autor_email, post.titulo, post.conteudo, post.imagem_url, _dt_to_db(post.data_criacao), 1 if post.visivel else 0),
    )
    conn.commit()
    conn.close()


def persistir_comentario_post(comentario):
    conn = get_connection()
    conn.execute(
        '''
        INSERT INTO comentarios (id, post_id, autor_email, texto, data_criacao, visivel)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET post_id=excluded.post_id, autor_email=excluded.autor_email,
            texto=excluded.texto, data_criacao=excluded.data_criacao, visivel=excluded.visivel
        ''',
        (comentario.id, comentario.post_id, comentario.autor_email, comentario.texto, _dt_to_db(comentario.data_criacao), 1 if comentario.visivel else 0),
    )
    conn.commit()
    conn.close()


def marcar_post_visivel(post_id: int, visivel: bool):
    conn = get_connection()
    conn.execute('UPDATE posts SET visivel = ? WHERE id = ?', (1 if visivel else 0, post_id))
    conn.commit()
    conn.close()


def marcar_comentario_post_visivel(comentario_id: int, visivel: bool):
    conn = get_connection()
    conn.execute('UPDATE comentarios SET visivel = ? WHERE id = ?', (1 if visivel else 0, comentario_id))
    conn.commit()
    conn.close()


def persistir_biblioteca_item(item):
    conn = get_connection()
    conn.execute(
        '''
        INSERT INTO biblioteca (
            id, email_usuario, jogo_id, data_adicao, tempo_jogado_horas, concluido, platinado,
            origem, launcher, codigo_origem, cover_url, executable_path, install_folder,
            executable_name, updated_at, manual_override, favorito, last_launched_at,
            last_played_game, status, conquistas_desbloqueadas, conquistas_total
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(email_usuario, jogo_id) DO UPDATE SET
            data_adicao=excluded.data_adicao,
            tempo_jogado_horas=excluded.tempo_jogado_horas,
            concluido=excluded.concluido,
            platinado=excluded.platinado,
            origem=excluded.origem,
            launcher=excluded.launcher,
            codigo_origem=excluded.codigo_origem,
            cover_url=excluded.cover_url,
            executable_path=excluded.executable_path,
            install_folder=excluded.install_folder,
            executable_name=excluded.executable_name,
            updated_at=excluded.updated_at,
            manual_override=excluded.manual_override,
            favorito=excluded.favorito,
            last_launched_at=excluded.last_launched_at,
            last_played_game=excluded.last_played_game,
            status=excluded.status,
            conquistas_desbloqueadas=excluded.conquistas_desbloqueadas,
            conquistas_total=excluded.conquistas_total
        ''',
        (
            item.id,
            item.email_usuario,
            item.jogo_id,
            _dt_to_db(item.data_adicao),
            item.tempo_jogado_horas,
            1 if item.concluido else 0,
            1 if item.platinado else 0,
            getattr(item, 'origem', '') or 'manual',
            getattr(item, 'launcher', '') or getattr(item, 'origem', '') or 'manual',
            getattr(item, 'codigo_origem', '') or '',
            getattr(item, 'cover_url', '') or '',
            getattr(item, 'executable_path', '') or '',
            getattr(item, 'install_folder', '') or getattr(item, 'pasta_instalacao', '') or '',
            getattr(item, 'executable_name', '') or (os.path.basename(getattr(item, 'executable_path', '') or '') if getattr(item, 'executable_path', '') else ''),
            _dt_to_db(getattr(item, 'updated_at', None)),
            1 if getattr(item, 'manual_override', False) else 0,
            1 if getattr(item, 'favorito', False) else 0,
            _dt_to_db(getattr(item, 'last_launched_at', None)),
            getattr(item, 'last_played_game', '') or '',
            getattr(item, 'status', 'offline') or 'offline',
            int(getattr(item, 'conquistas_desbloqueadas', 0) or 0),
            int(getattr(item, 'conquistas_total', 0) or 0),
        ),
    )
    conn.commit()
    conn.close()


def remover_biblioteca_item(email_usuario: str, jogo_id: int):
    conn = get_connection()
    conn.execute('DELETE FROM biblioteca WHERE email_usuario = ? AND jogo_id = ?', (email_usuario, jogo_id))
    conn.commit()
    conn.close()


def persistir_amizade(amizade):
    conn = get_connection()
    try:
        conn.execute(
            '''
            INSERT INTO amizades (id, email_solicitante, email_receptor, status, data_solicitacao, data_aceito)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(email_solicitante, email_receptor) DO UPDATE SET
                id=excluded.id,
                status=excluded.status,
                data_solicitacao=excluded.data_solicitacao,
                data_aceito=excluded.data_aceito
            ''',
            (
                amizade.id,
                amizade.email_solicitante,
                amizade.email_receptor,
                amizade.status,
                _dt_to_db(amizade.data_solicitacao),
                _dt_to_db(getattr(amizade, 'data_aceito', None)),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def remover_amizade(email1: str, email2: str):
    conn = get_connection()
    try:
        conn.execute(
            'DELETE FROM amizades WHERE (email_solicitante = ? AND email_receptor = ?) OR (email_solicitante = ? AND email_receptor = ?)',
            (email1, email2, email2, email1),
        )
        conn.commit()
    finally:
        conn.close()


def persistir_post_like(post_id: int, email_usuario: str, curtiu: bool):
    conn = get_connection()
    try:
        if curtiu:
            conn.execute(
                '''
                INSERT OR IGNORE INTO post_likes (post_id, email_usuario)
                VALUES (?, ?)
                ''',
                (post_id, (email_usuario or '').strip().lower()),
            )
        else:
            conn.execute(
                'DELETE FROM post_likes WHERE post_id = ? AND email_usuario = ?',
                (post_id, (email_usuario or '').strip().lower()),
            )
        conn.commit()
    finally:
        conn.close()


def persistir_review(review):
    conn = get_connection()
    conn.execute(
        '''
        INSERT INTO reviews (id, jogo_id, email_usuario, titulo, conteudo, nota, data_criacao, visivel, curtidas)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            jogo_id=excluded.jogo_id,
            email_usuario=excluded.email_usuario,
            titulo=excluded.titulo,
            conteudo=excluded.conteudo,
            nota=excluded.nota,
            data_criacao=excluded.data_criacao,
            visivel=excluded.visivel,
            curtidas=excluded.curtidas
        ''',
        (review.id, review.jogo_id, review.email_usuario, review.titulo, review.conteudo, review.nota, _dt_to_db(review.data_criacao), 1 if review.visivel else 0, review.curtidas),
    )
    conn.commit()
    conn.close()


def persistir_review_comentario(comentario):
    conn = get_connection()
    conn.execute(
        '''
        INSERT INTO review_comentarios (id, review_id, email_usuario, texto, data_criacao, visivel)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET review_id=excluded.review_id, email_usuario=excluded.email_usuario,
            texto=excluded.texto, data_criacao=excluded.data_criacao, visivel=excluded.visivel
        ''',
        (comentario.id, comentario.review_id, comentario.email_usuario, comentario.texto, _dt_to_db(comentario.data_criacao), 1 if comentario.visivel else 0),
    )
    conn.commit()
    conn.close()


def marcar_review_visivel(review_id: int, visivel: bool):
    conn = get_connection()
    conn.execute('UPDATE reviews SET visivel = ? WHERE id = ?', (1 if visivel else 0, review_id))
    conn.commit()
    conn.close()


def marcar_review_comentario_visivel(comentario_id: int, visivel: bool):
    conn = get_connection()
    conn.execute('UPDATE review_comentarios SET visivel = ? WHERE id = ?', (1 if visivel else 0, comentario_id))
    conn.commit()
    conn.close()


def persistir_notificacao(notif):
    conn = get_connection()
    try:
        conn.execute(
            '''
            INSERT INTO notificacoes (id, email_receptor, tipo, titulo, descricao, link, data_criacao, lida)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                email_receptor=excluded.email_receptor,
                tipo=excluded.tipo,
                titulo=excluded.titulo,
                descricao=excluded.descricao,
                link=excluded.link,
                data_criacao=excluded.data_criacao,
                lida=excluded.lida
            ''',
            (notif.id, notif.email_receptor, notif.tipo, notif.titulo, notif.descricao, notif.link, _dt_to_db(notif.data_criacao), 1 if notif.lida else 0),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
    finally:
        conn.close()


def marcar_notificacao_lida(email_receptor: str, notif_id: int):
    conn = get_connection()
    conn.execute('UPDATE notificacoes SET lida = 1 WHERE email_receptor = ? AND id = ?', (email_receptor, notif_id))
    conn.commit()
    conn.close()


def persistir_mensagem(mensagem):
    conn = get_connection()
    try:
        _ensure_mensagem_columns(conn)
        conn.execute(
            '''
            INSERT INTO mensagens (id, email_remetente, email_destino, conteudo, data_envio, status, canceled_at, canceled_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                email_remetente=excluded.email_remetente,
                email_destino=excluded.email_destino,
                conteudo=excluded.conteudo,
                data_envio=excluded.data_envio,
                status=excluded.status,
                canceled_at=excluded.canceled_at,
                canceled_by=excluded.canceled_by
            ''',
            (
                mensagem.id,
                mensagem.email_remetente,
                mensagem.email_destino,
                mensagem.conteudo,
                _dt_to_db(mensagem.data_envio),
                mensagem.status,
                _dt_to_db(getattr(mensagem, 'canceled_at', None)),
                getattr(mensagem, 'canceled_by', None),
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
    finally:
        conn.close()


def persistir_reacao_mensagem(mensagem_id: int, email_usuario: str, emoji: str, remover: bool = False):
    conn = get_connection()
    try:
        mensagem_existe = conn.execute('SELECT 1 FROM mensagens WHERE id = ?', (mensagem_id,)).fetchone()
        usuario_existe = conn.execute('SELECT 1 FROM usuarios WHERE lower(email) = ?', ((email_usuario or '').strip().lower(),)).fetchone()
        if not mensagem_existe or not usuario_existe:
            return

        if remover:
            conn.execute('DELETE FROM mensagem_reacoes WHERE mensagem_id = ? AND email_usuario = ?', (mensagem_id, email_usuario))
        else:
            conn.execute(
                '''
                INSERT INTO mensagem_reacoes (mensagem_id, email_usuario, emoji, data_reacao)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(mensagem_id, email_usuario) DO UPDATE SET emoji=excluded.emoji, data_reacao=excluded.data_reacao
                ''',
                (mensagem_id, email_usuario, emoji, _dt_to_db(datetime.now())),
            )
        conn.commit()
    finally:
        conn.close()


if __name__ == '__main__':
    init_db()
    seed_initial_data()
    print(f'Banco de dados criado em: {DB_PATH}')
