# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response, send_from_directory
from flask_sock import Sock
from modelos.usuario import Usuario, Admin, USUARIOS_DB, obter_senha_admin_padrao
from modelos.jogo import Jogo, Categoria, JOGOS_DB
from modelos.posts import Post, Comentario, POSTS_DB, COMENTARIOS_POSTS_DB
from modelos.amigos_biblioteca import (
    GerenciadorAmigos, GerenciadorBiblioteca, GerenciadorReviews,
    GerenciadorNotificacoes, GerenciadorMensagens,
    AMIZADES_DB, BIBLIOTECA_DB, REVIEWS_DB, REVIEW_COMENTARIOS_DB, NOTIFICACOES_DB, MENSAGENS_DB
)
import modelos.amigos_biblioteca as amigos_biblioteca_module
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Thread, Timer
import base64
import csv
import json
import os
import platform
import re
import subprocess
import shutil
import sys
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
import time
from functools import lru_cache
from html.parser import HTMLParser
from html import escape, unescape
from urllib.parse import quote, urlparse, urlencode
from smtp_service import (
    enviar_email,
    enviar_email_teste,
    get_smtp_config,
    listar_fila,
    listar_logs,
    processar_fila_email,
    update_smtp_config,
)
from urllib.request import Request, urlopen
from io import BytesIO
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
import secrets
import sqlite3

IS_WINDOWS = os.name == 'nt'
IS_VERCEL = os.environ.get('VERCEL') == '1'
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@gamelink.com'


def is_desktop_gameunexa() -> bool:
    return IS_WINDOWS and not IS_VERCEL


def is_web_gameunexa() -> bool:
    return not is_desktop_gameunexa()


def format_folder_label(display_name: str, folder_path: str = '') -> str:
    label_name = (display_name or 'Pasta').strip() or 'Pasta'
    safe_path = (folder_path or '').strip()
    if safe_path:
        return f"📁 {label_name}\n{safe_path}"
    return f"📁 {label_name}\nPasta selecionada no computador"


def build_browser_library_reference(display_name: str, folder_path: str = '') -> str:
    safe_name = (display_name or 'Pasta').strip() or 'Pasta'
    safe_path = (folder_path or '').strip()
    if safe_path.startswith('browser:'):
        return safe_path
    if safe_path:
        return f"browser:{safe_name}|{safe_path}"
    return f"browser:{safe_name}|{safe_name}"

from paths import CACHE_DIR, ENV_PATH, UPLOADS_DIR, SUPPORT_UPLOAD_DIR, ensure_app_data_dirs, resource_path, TEMP_DIR
from excecao import GameLinkException, AutenticacaoError, OperacaoInvalidaError
from steam_audit import (
    log_steamid_resolvido, log_steamid_falha,
    log_fetch_xml_iniciado, log_fetch_xml_sucesso, log_fetch_xml_erro,
    log_parse_xml_iniciado, log_parse_xml_sucesso, log_parse_xml_erro,
    log_jogos_extraidos, log_paginacao_finalizada, log_bibliotecas_obtidas,
    log_deduplicacao, log_import_iniciado, log_jogo_criado_catalogo,
    log_jogo_ja_existia_catalogo, log_jogo_adicionado_biblioteca,
    log_jogo_atualizado_biblioteca, log_jogo_import_erro, log_import_finalizado,
    log_validacao_banco_dados, log_validacao_interface, log_discrepancia,
    limpar_log_audit, ler_log_audit
)
from steam_api import obter_jogos, obter_perfil, obter_status, obter_jogo
from steam_api import obter_jogos, obter_perfil, obter_status, obter_jogo, obter_estatisticas_jogo, formatar_playtime
from library_manager import unificar_biblioteca, scan_library_root, persistir_registros_instalados
from launcher_manager import LauncherManager
from presenca_sync import callback_mudanca_presenca, callback_mudanca_presenca_global
import time

if IS_WINDOWS:
    from steam_local import listar_jogos_instalados
    from automatic_library import scan_automatic_library, scan_local_folders
    from folder_picker import select_folder
    from process_detector import inicializar_detector, parar_detector, obter_detector
else:
    def listar_jogos_instalados(*args, **kwargs):
        return []

    def scan_automatic_library(*args, **kwargs):
        return []

    def scan_local_folders(*args, **kwargs):
        return []

    def select_folder() -> str:
        return ''

    def inicializar_detector(*args, **kwargs):
        return None

    def parar_detector(*args, **kwargs):
        return None

    def obter_detector(*args, **kwargs):
        return None

# Cache global para rastrear estado de presença e saber se necessita sincronização
_CACHE_ESTADO_PRESENCA = {}  # {email: {'steam': bool, 'hydra': bool, 'timestamp': float}}
_LOCK_CACHE_PRESENCA = Lock()

from modelos.suporte import (
    CATEGORIAS_SUPORTE,
    PRIORIDADES_SUPORTE,
    STATUS_SUPORTE_INICIAIS,
    ChamadoSuporte,
    MensagemSuporte,
    AnexoSuporte,
    HistoricoSuporte,
    normalizar_slug,
    gerar_codigo_suporte,
)

if IS_WINDOWS and not IS_VERCEL:
    try:
        import webview
    except Exception as exc:
        webview = None
        WEBVIEW_IMPORT_ERROR = exc
else:
    webview = None
    WEBVIEW_IMPORT_ERROR = None
from database import (
    init_db,
    get_connection,
    carregar_estado_persistido,
    obter_biblioteca_filtrada,
    persistir_usuario,
    persistir_categoria,
    persistir_jogo,
    remover_jogo,
    persistir_post,
    persistir_comentario_post,
    marcar_post_visivel,
    marcar_comentario_post_visivel,
    persistir_post_like,
    persistir_amizade,
    remover_amizade,
    persistir_biblioteca_item,
    remover_biblioteca_item,
    persistir_review,
    persistir_review_comentario,
    marcar_review_visivel,
    marcar_review_comentario_visivel,
    persistir_notificacao,
    marcar_notificacao_lida,
    persistir_mensagem,
    persistir_reacao_mensagem,
    excluir_usuario_completo,
)
from game_database import listar_games_instalados
from game_matcher import names_match, normalize_game_name
from background_manager import (
    ALLOWED_EXTENSIONS,
    BACKGROUND_DIR,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    arquivos_da_pasta,
    obter_background,
    redefinir_background,
    salvar_background,
    salvar_upload_background,
)
from soundboard_api import soundboard_bp

app = Flask(
    __name__,
    template_folder=resource_path('templates'),
    static_folder=resource_path('static'),
)
sock = Sock(app)

SOUNDBOARD_SIGNALING_ROOMS = {}
SOUNDBOARD_SIGNALING_LOCK = Lock()

CHAT_UPLOAD_DIR = str(UPLOADS_DIR / 'chat')
MAX_CHAT_UPLOAD_SIZE = 5 * 1024 * 1024
ALLOWED_CHAT_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
ALLOWED_CHAT_FILE_EXTENSIONS = {'pdf', 'zip', 'rar', 'docx', 'txt', 'png', 'jpg', 'jpeg', 'webp', 'mp4'}

# Rastreamento de estado real (não cache - validado sempre)
_hydra_state_real = {
    'hydra_ativo': False,
    'jogo_atual': '',
    'ultima_validacao': 0,
    'processos_detectados': [],
}

# Bloqueio para evitar race conditions
import threading
_hydra_state_lock = threading.Lock()

PENDING_CHAT_MESSAGES = {}
PENDING_CHAT_LOCK = Lock()
_AUTO_LIBRARY_STATUS = {}
_AUTO_LIBRARY_STATUS_LOCK = Lock()
_AUTO_LIBRARY_DB_LOCK = Lock()


def _formatar_humano_relativo(data_value, agora: datetime | None = None) -> str:
    if not data_value:
        return 'Nunca'

    if isinstance(data_value, str):
        try:
            data_value = datetime.fromisoformat(data_value.replace('Z', '+00:00'))
        except Exception:
            return 'Recentemente'

    if agora is None:
        agora = datetime.now()

    if isinstance(data_value, datetime):
        if data_value.tzinfo is not None:
            data_value = data_value.astimezone().replace(tzinfo=None)
        if agora.tzinfo is not None:
            agora = agora.astimezone().replace(tzinfo=None)

        diff = max(0, int((agora - data_value).total_seconds()))
        if diff < 60:
            return 'agora'
        if diff < 3600:
            return f'há {diff // 60} minuto(s)'
        if diff < 86400:
            horas = diff // 3600
            return f'há {horas} hora(s)'
        if diff < 172800:
            return 'ontem'
        dias = diff // 86400
        return f'há {dias} dia(s)'

    return 'Recentemente'


def _formatar_hora_resumida(data_value, agora: datetime | None = None) -> str:
    if not data_value:
        return 'Nunca'

    if isinstance(data_value, str):
        try:
            data_value = datetime.fromisoformat(data_value.replace('Z', '+00:00'))
        except Exception:
            return 'Nunca'

    if agora is None:
        agora = datetime.now()

    if isinstance(data_value, datetime):
        if data_value.tzinfo is not None:
            data_value = data_value.astimezone().replace(tzinfo=None)
        if agora.tzinfo is not None:
            agora = agora.astimezone().replace(tzinfo=None)
        return data_value.strftime('%d/%m às %H:%M')

    return 'Nunca'


def _inferir_dispositivo(user_agent: str | None) -> str:
    ua = (user_agent or '').lower()
    if any(token in ua for token in ['iphone', 'android', 'mobile']):
        return 'Mobile'
    if any(token in ua for token in ['ipad', 'tablet']):
        return 'Tablet'
    if any(token in ua for token in ['macbook', 'laptop', 'chromebook']):
        return 'Notebook'
    return 'Desktop'


def _montar_dados_status_panel(usuario, user_agent: str | None = None) -> dict:
    agora = datetime.now()
    ultimo_update = getattr(usuario, 'steam_last_update', None) or getattr(usuario, 'hydra_last_update', None)
    ultimo_update_dt = None
    if isinstance(ultimo_update, str):
        try:
            ultimo_update_dt = datetime.fromisoformat(ultimo_update.replace('Z', '+00:00'))
        except Exception:
            ultimo_update_dt = None

    if hasattr(usuario, 'steam_current_game') and usuario.steam_current_game:
        jogo_atual = usuario.steam_current_game
        launcher = 'Steam'
        status_key = 'busy'
        status_label = 'Ocupado'
        status_icon = 'fa-solid fa-gamepad'
        status_class = 'status-busy'
        estado_texto = 'Jogando agora'
    elif getattr(usuario, 'hydra_current_game', ''):
        jogo_atual = usuario.hydra_current_game
        launcher = 'Hydra'
        status_key = 'busy'
        status_label = 'Ocupado'
        status_icon = 'fa-solid fa-gamepad'
        status_class = 'status-busy'
        estado_texto = 'Jogando agora'
    elif getattr(usuario, 'steam_online', False):
        jogo_atual = ''
        launcher = 'Steam'
        status_key = 'online'
        status_label = 'Online'
        status_icon = 'fa-solid fa-circle-dot'
        status_class = 'status-online'
        estado_texto = 'Disponível'
    else:
        jogo_atual = ''
        launcher = 'Manual'
        status_key = 'offline'
        status_label = 'Offline'
        status_icon = 'fa-solid fa-circle'
        status_class = 'status-offline'
        estado_texto = 'Offline'

    tempo_online = '0m'
    if status_key in {'online', 'busy'} and ultimo_update_dt:
        diff = max(0, int((agora - ultimo_update_dt).total_seconds()))
        minutes = max(0, diff // 60)
        if minutes < 60:
            tempo_online = f'{minutes}min'
        else:
            horas = minutes // 60
            mins = minutes % 60
            tempo_online = f'{horas}h {mins}min' if mins else f'{horas}h'

    if status_key == 'offline' and ultimo_update_dt:
        diff = max(0, int((agora - ultimo_update_dt).total_seconds()))
        if diff > 86400 * 3:
            status_key = 'absent'
            status_label = 'Ausente'
            status_icon = 'fa-solid fa-clock'
            status_class = 'status-absent'

    badges = []
    if getattr(usuario, 'steam_id64', ''):
        badges.append('Steam')
    if getattr(usuario, 'hydra_current_game', '') or getattr(usuario, 'hydra_token', '') or getattr(usuario, 'hydra_usuario', ''):
        badges.append('Hydra')
    badges.append('Manual')

    cover_url = ''
    if jogo_atual:
        cover_url = _resolver_capa_presenca(
            usuario,
            jogo_atual,
            getattr(usuario, 'steam_current_game_appid', None) if launcher == 'Steam' else None,
            launcher,
        )

    return {
        'status_key': status_key,
        'status_label': status_label,
        'status_icon': status_icon,
        'status_class': status_class,
        'estado_texto': estado_texto,
        'jogo': jogo_atual,
        'cover_url': cover_url,
        'launcher': launcher,
        'launcher_badges': badges,
        'last_activity': _formatar_humano_relativo(ultimo_update, agora),
        'last_activity_timestamp': _formatar_hora_resumida(ultimo_update, agora),
        'device': _inferir_dispositivo(user_agent),
        'tempo_online': tempo_online,
        'updated_at_tooltip': f'Status atualizado em { _formatar_hora_resumida(ultimo_update, agora) }',
        'online': bool(getattr(usuario, 'steam_online', False) or getattr(usuario, 'hydra_current_game', '') or bool(getattr(usuario, 'steam_current_game', ''))),
    }


app.jinja_env.globals['montar_status_panel_data'] = lambda usuario, user_agent=None: _montar_dados_status_panel(usuario, user_agent=user_agent)


def _criar_mensagem_pendente(meu_email: str, email_destino: str, conteudo: str, reply_to_id, reply_to_conteudo, anexo_data: dict | None = None):
    pending_id = f"pending-{uuid4().hex}"
    entry = {
        'id': pending_id,
        'email_remetente': meu_email,
        'email_destino': email_destino,
        'conteudo': conteudo,
        'reply_to_id': reply_to_id,
        'reply_to_conteudo': reply_to_conteudo,
        'anexo_data': anexo_data,
        'status': 'pending',
        'created_at': datetime.now(),
    }
    with PENDING_CHAT_LOCK:
        PENDING_CHAT_MESSAGES[pending_id] = entry
    timer = Timer(5.0, _finalizar_envio_pendente, args=(pending_id,))
    timer.daemon = True
    entry['timer'] = timer
    timer.start()
    return entry


def _cancelar_mensagem_pendente(pending_id: str):
    with PENDING_CHAT_LOCK:
        entry = PENDING_CHAT_MESSAGES.pop(pending_id, None)
    if entry and entry.get('timer'):
        entry['timer'].cancel()
    return bool(entry)


def _finalizar_envio_pendente(pending_id: str):
    with PENDING_CHAT_LOCK:
        entry = PENDING_CHAT_MESSAGES.pop(pending_id, None)
    if not entry:
        return None

    meu_email = entry.get('email_remetente')
    email_destino = entry.get('email_destino')
    if not meu_email or not email_destino:
        return None

    novo_id = max([m.id for m in MENSAGENS_DB], default=0) + 1
    mensagem = GerenciadorMensagens.enviar_mensagem(novo_id, meu_email, email_destino, entry.get('conteudo') or '📎 Anexo enviado')
    mensagem.tipo = 'image' if entry.get('anexo_data') and entry['anexo_data']['tipo'] == 'image' else 'file' if entry.get('anexo_data') else 'text'
    mensagem.anexo_url = entry.get('anexo_data', {}).get('url') if entry.get('anexo_data') else None
    mensagem.anexo_nome = entry.get('anexo_data', {}).get('nome') if entry.get('anexo_data') else None
    mensagem.anexo_tamanho = entry.get('anexo_data', {}).get('tamanho') if entry.get('anexo_data') else None
    mensagem.anexo_tipo = entry.get('anexo_data', {}).get('tipo') if entry.get('anexo_data') else None
    mensagem.reply_to_id = int(entry['reply_to_id']) if entry.get('reply_to_id') not in (None, '', False) else None
    mensagem.reply_to_conteudo = entry.get('reply_to_conteudo') or None
    mensagem.status = 'sent'
    persistir_mensagem(mensagem)

    todas_notifs = [n for lista in NOTIFICACOES_DB.values() for n in lista]
    id_notif = max([n.id for n in todas_notifs], default=0) + 1
    remetente = USUARIOS_DB.get(meu_email)
    GerenciadorNotificacoes.criar_notificacao(
        id_notif=id_notif,
        email_receptor=email_destino,
        tipo='mensagem',
        titulo='💬 Nova mensagem recebida',
        descricao=f'{remetente.nome if remetente else meu_email} enviou uma nova mensagem para você.',
        link=f'/conversa/{meu_email}'
    )
    for notif in NOTIFICACOES_DB.get(email_destino, []):
        if notif.id == id_notif:
            persistir_notificacao(notif)
            break

    return mensagem


def _carregar_env_local() -> None:
    caminho_env = str(ENV_PATH)
    if not os.path.exists(caminho_env):
        return

    with open(caminho_env, 'r', encoding='utf-8') as arquivo:
        for linha in arquivo:
            texto = linha.strip()
            if not texto or texto.startswith('#') or '=' not in texto:
                continue
            chave, valor = texto.split('=', 1)
            chave = chave.strip()
            valor = valor.strip().strip('"').strip("'")
            if chave and chave not in os.environ:
                os.environ[chave] = valor


_carregar_env_local()

_SECRET_KEY = os.environ.get('SECRET_KEY')
if not _SECRET_KEY:
    if IS_VERCEL:
        _SECRET_KEY = 'gamelink-vercel-stable-fallback-secret'
        print('[VERCEL STARTUP] SECRET_KEY ausente; usando fallback estável para manter a Function ativa.')
    else:
        _SECRET_KEY = 'gamelink-local-development-secret'

app.config.update(
    SECRET_KEY=_SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=(
        IS_VERCEL
        or
        os.environ.get('SESSION_COOKIE_SECURE', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
        or os.environ.get('FLASK_ENV', '').strip().lower() in {'production', 'prod'}
    ),
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    UPLOAD_FOLDER=str(SUPPORT_UPLOAD_DIR),
)
app.secret_key = app.config['SECRET_KEY']
app.register_blueprint(soundboard_bp)


@app.route('/app-data/uploads/<path:filename>')
def app_data_upload(filename):
    return send_from_directory(str(UPLOADS_DIR), filename)


@app.route('/app-data/cache/covers/<path:filename>')
def app_data_cover(filename):
    return send_from_directory(str(CACHE_DIR / 'covers'), filename)

try:
    ensure_app_data_dirs()
except OSError as exc:
    print(str(exc), file=sys.stderr)
    if IS_WINDOWS and not IS_VERCEL:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror('GAME-UNEXA', str(exc))
            root.destroy()
        except Exception:
            pass
    raise SystemExit(1) from exc

# Inicializa o banco de dados SQLite se ainda não existir
init_db()


def _garantir_biblioteca_db_consistente() -> None:
    if getattr(amigos_biblioteca_module, 'BIBLIOTECA_DB', None) is not BIBLIOTECA_DB:
        amigos_biblioteca_module.BIBLIOTECA_DB = BIBLIOTECA_DB


def _sanitizar_texto(valor) -> str:
    if valor is None:
        return ''
    texto = str(valor)
    texto = re.sub(r'<[^>]+>', '', texto)
    texto = re.sub(r'[\x00-\x1f\x7f]', '', texto)
    return texto.strip()


def _detectar_so() -> str:
    return platform.system() or 'Desconhecido'


def _detectar_navegador(user_agent: str) -> str:
    agente = (user_agent or '').lower()
    if 'edg/' in agente:
        return 'Microsoft Edge'
    if 'chrome/' in agente:
        return 'Google Chrome'
    if 'firefox/' in agente:
        return 'Mozilla Firefox'
    if 'safari/' in agente and 'chrome' not in agente:
        return 'Safari'
    if 'opr/' in agente or 'opera' in agente:
        return 'Opera'
    return 'Desconhecido'


def _detectar_resolucao(request_obj) -> str:
    return _sanitizar_texto(request_obj.form.get('resolucao_tela')) or 'Não informada'


def _obter_ip() -> str:
    if request.headers.get('X-Forwarded-For'):
        return _sanitizar_texto(request.headers.get('X-Forwarded-For').split(',')[0])
    return request.remote_addr or 'Não disponível'


def _obter_status_suporte(slug: str) -> str:
    mapping = {item[0]: item[1] for item in STATUS_SUPORTE_INICIAIS}
    return mapping.get(slug, 'Aberto')


def _obter_categoria_suporte(slug: str) -> str:
    mapping = {item[0]: item[1] for item in CATEGORIAS_SUPORTE}
    return mapping.get(slug, '📌 Outro')


def _salvar_anexo_chamado(chamado_id: int, mensagem_id: int | None, upload, max_size_mb: int = 10) -> dict | None:
    if upload is None or not getattr(upload, 'filename', ''):
        return None

    nome_original = _sanitizar_texto(upload.filename)
    if not nome_original:
        return None

    nome_seguro = secure_filename(nome_original)
    ext = os.path.splitext(nome_seguro)[1].lower()
    ext_permitida = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mov', '.avi', '.mkv', '.webm', '.zip', '.rar', '.7z', '.tar', '.gz', '.log', '.txt', '.pdf'}
    ext_dangerous = {'.exe', '.bat', '.cmd', '.com', '.scr', '.pif', '.js', '.html', '.htm', '.php', '.asp', '.aspx', '.jar', '.vbs', '.ps1', '.py', '.sh', '.svg', '.dll', '.msi', '.lnk', '.reg'}
    if ext in ext_dangerous or ext not in ext_permitida:
        raise ValueError('Tipo de arquivo não permitido para segurança.')

    upload.stream.seek(0, os.SEEK_END)
    tamanho = upload.stream.tell()
    upload.stream.seek(0)
    if tamanho > max_size_mb * 1024 * 1024:
        raise ValueError(f'O arquivo excede o limite de {max_size_mb} MB.')

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    nome_arquivo = f"{int(datetime.now().timestamp() * 1000)}_{nome_seguro}"
    caminho = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
    upload.save(caminho)

    return {
        'nome_original': nome_original,
        'nome_arquivo': nome_arquivo,
        'caminho': os.path.join('app-data', 'uploads', 'suporte', nome_arquivo),
        'tipo_mime': upload.mimetype or 'application/octet-stream',
        'tamanho': tamanho,
        'chamado_id': chamado_id,
        'mensagem_id': mensagem_id,
    }


def _persistir_anexo(anexo_data: dict) -> None:
    conn = get_connection()
    conn.execute(
        '''
        INSERT INTO suporte_anexos (chamado_id, mensagem_id, nome_original, nome_arquivo, caminho, tipo_mime, tamanho, data_upload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            anexo_data['chamado_id'],
            anexo_data['mensagem_id'],
            anexo_data['nome_original'],
            anexo_data['nome_arquivo'],
            anexo_data['caminho'],
            anexo_data['tipo_mime'],
            anexo_data['tamanho'],
            datetime.now().isoformat(timespec='seconds'),
        ),
    )
    conn.commit()
    conn.close()


def _adicionar_historico_suporte(chamado_id: int, usuario_email: str, acao: str, detalhes: str) -> None:
    conn = get_connection()
    conn.execute(
        '''
        INSERT INTO suporte_historico (chamado_id, usuario_email, acao, detalhes, data_registro)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (chamado_id, usuario_email, acao, detalhes, datetime.now().isoformat(timespec='seconds')),
    )
    conn.commit()
    conn.close()


def _criar_notificacao_suporte(destinatario: str, chamado_id: int, codigo: str, mensagem: str) -> None:
    conn = get_connection()
    cursor = conn.execute('SELECT MAX(id) FROM notificacoes')
    ultimo = cursor.fetchone()[0] or 0
    notif = GerenciadorNotificacoes.criar_notificacao(
        ultimo + 1,
        destinatario,
        'suporte',
        'Resposta no suporte',
        f'{mensagem} ({codigo})',
        f'/suporte/chamado/{chamado_id}',
    )
    persistir_notificacao(notif)
    conn.close()


_garantir_biblioteca_db_consistente()

HYDRA_SYNC_EXECUTOR = ThreadPoolExecutor(max_workers=2)
HYDRA_SYNC_TASKS: dict[str, dict] = {}
HYDRA_SYNC_TASK_LOCK = Lock()
HYDRA_CACHE_FILE_STATE: dict[str, tuple[float, tuple[list[dict], str]]] = {}


def _normalizar_email(email: str) -> str:
    return (email or '').strip().lower()


def _mascarar_email(email: str) -> str:
    valor = _normalizar_email(email)
    if not valor or '@' not in valor:
        return valor
    local, dominio = valor.split('@', 1)
    if len(local) <= 1:
        return f'{local or "*"}@{dominio}'
    if len(local) == 2:
        return f'{local[0]}*@{dominio}'
    mascarado = f'{local[0]}{"*" * min(6, max(1, len(local) - 1))}'
    return f'{mascarado}@{dominio}'


def _gerar_codigo_verificacao() -> str:
    return f'{secrets.randbelow(1000000):06d}'


def _enviar_codigo_verificacao_email(destinatario: str, codigo: str, nome: str) -> bool:
    config = get_smtp_config()
    if not config['server']:
        print(f'[GameUnexa] Verificação local para {destinatario}: {codigo}')
        return False

    resultado = enviar_email(
        destinatario=destinatario,
        assunto='Seu código de verificação GameUnexa',
        corpo=(
            f'Olá, {nome}.\n\n'
            f'Seu código de verificação do GameUnexa é: {codigo}\n\n'
            'Esse código expira em 10 minutos.\n'
            'Se você não solicitou este cadastro, ignore esta mensagem.'
        ),
        tipo_email='verificacao',
        background=True,
    )
    return resultado.get('status') in {'queued', 'sent'}


def _cadastro_pendente_valido() -> dict | None:
    pendente = session.get('cadastro_pendente')
    if not pendente:
        return None
    if pendente.get('expira_em', 0) < time.time():
        session.pop('cadastro_pendente', None)
        session.pop('cadastro_ultimo_envio', None)
        return None
    return pendente


def _carregar_usuarios_do_banco() -> None:
    USUARIOS_DB.clear()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
         SELECT id, nome, email, password, idade, gosto_jogos, telefone,
             steam_id64, steam_api_key, steam_online, steam_current_game, 
             steam_current_game_appid, steam_playtime_minutes, steam_last_update,
             hydra_account_email, hydra_usuario, hydra_pin, hydra_token, hydra_current_game, hydra_last_update, foto_perfil, is_admin
        FROM usuarios
        ORDER BY id ASC
        '''
    )
    for row in cursor.fetchall():
        user = Admin(row['id'], row['nome'], row['email'], row['password']) if row['is_admin'] else Usuario(row['id'], row['nome'], row['email'], row['password'])
        user.idade = row['idade']
        user.gosto_jogos = row['gosto_jogos'] or ''
        user.telefone = row['telefone'] or ''
        user.steam_id64 = row['steam_id64'] or ''
        user.steam_api_key = row['steam_api_key'] or ''
        user.steam_online = bool(row['steam_online']) if row['steam_online'] is not None else False
        user.steam_current_game = row['steam_current_game'] or ''
        user.steam_current_game_appid = row['steam_current_game_appid']
        user.steam_playtime_minutes = row['steam_playtime_minutes'] or 0
        user.steam_last_update = row['steam_last_update'] or None
        user.hydra_account_email = row['hydra_account_email'] or ''
        user.hydra_usuario = row['hydra_usuario'] or ''
        user.hydra_pin = row['hydra_pin'] or ''
        user.hydra_token = row['hydra_token'] or ''
        user.hydra_current_game = row['hydra_current_game'] or ''
        user.hydra_last_update = row['hydra_last_update'] or None
        user.foto_perfil = row['foto_perfil'] or ''
        USUARIOS_DB[user.email.lower()] = user
    conn.close()


def _salvar_usuario_no_banco(user) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    idade = getattr(user, 'idade', None)
    gosto_jogos = getattr(user, 'gosto_jogos', '')
    telefone = getattr(user, 'telefone', '')
    steam_id64 = getattr(user, 'steam_id64', '')
    steam_api_key = getattr(user, 'steam_api_key', '')
    steam_online = bool(getattr(user, 'steam_online', False))
    steam_current_game = getattr(user, 'steam_current_game', '')
    steam_current_game_appid = getattr(user, 'steam_current_game_appid', None)
    steam_playtime_minutes = getattr(user, 'steam_playtime_minutes', 0)
    steam_last_update = getattr(user, 'steam_last_update', None)
    hydra_account_email = getattr(user, 'hydra_account_email', '')
    hydra_usuario = getattr(user, 'hydra_usuario', '')
    hydra_pin = getattr(user, 'hydra_pin', '')
    hydra_token = getattr(user, 'hydra_token', '')
    hydra_current_game = getattr(user, 'hydra_current_game', '')
    hydra_last_update = getattr(user, 'hydra_last_update', None)
    foto_perfil = getattr(user, 'foto_perfil', '')

    cursor.execute(
        '''
        INSERT INTO usuarios (
            nome, email, password, idade, gosto_jogos, telefone,
            steam_id64, steam_api_key, steam_online, steam_current_game,
            steam_current_game_appid, steam_playtime_minutes, steam_last_update,
            hydra_account_email, hydra_usuario, hydra_pin, hydra_token, hydra_current_game, hydra_last_update, foto_perfil, is_admin
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            nome=excluded.nome,
            password=excluded.password,
            idade=excluded.idade,
            gosto_jogos=excluded.gosto_jogos,
            telefone=excluded.telefone,
            steam_id64=excluded.steam_id64,
            steam_api_key=excluded.steam_api_key,
            steam_online=excluded.steam_online,
            steam_current_game=excluded.steam_current_game,
            steam_current_game_appid=excluded.steam_current_game_appid,
            steam_playtime_minutes=excluded.steam_playtime_minutes,
            steam_last_update=excluded.steam_last_update,
            hydra_account_email=excluded.hydra_account_email,
            hydra_usuario=excluded.hydra_usuario,
            hydra_pin=excluded.hydra_pin,
            hydra_token=excluded.hydra_token,
            hydra_current_game=excluded.hydra_current_game,
            hydra_last_update=excluded.hydra_last_update,
            foto_perfil=excluded.foto_perfil,
            is_admin=excluded.is_admin
        ''',
        (
            getattr(user, 'nome', ''),
            getattr(user, 'email', ''),
            getattr(user, '_Usuario__password', '') if hasattr(user, '_Usuario__password') else '',
            idade,
            gosto_jogos,
            telefone,
            steam_id64,
            steam_api_key,
            1 if steam_online else 0,
            steam_current_game,
            steam_current_game_appid,
            steam_playtime_minutes,
            steam_last_update,
            hydra_account_email,
            hydra_usuario,
            hydra_pin,
            hydra_token,
            hydra_current_game,
            hydra_last_update,
            foto_perfil,
            1 if isinstance(user, Admin) else 0,
        )
    )
    conn.commit()
    conn.close()


def _garantir_admin_no_banco() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM usuarios WHERE email = ?', (ADMIN_EMAIL,))
    if cursor.fetchone()[0] == 0:
        senha_admin = obter_senha_admin_padrao()
        admin_obj = Admin(1, 'Caxa', ADMIN_EMAIL, senha_admin, nivel_acesso=5)
        admin_obj.definir_senha(senha_admin)
        cursor.execute(
            'INSERT INTO usuarios (id, nome, email, password, is_admin) VALUES (?, ?, ?, ?, ?)',
            (1, admin_obj.nome, admin_obj.email, admin_obj._Usuario__password, 1)
        )
        conn.commit()
    conn.close()


_garantir_admin_no_banco()
_carregar_usuarios_do_banco()

# Configuração de uploads persistentes
UPLOAD_FOLDER = str(UPLOADS_DIR)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024  # 15MB; endpoints menores validam seus próprios limites

DEFAULT_HYDRA_API_BASE_URL = (
    os.environ.get('HYDRA_API_BASE_URL', 'https://hydra-api-us-east-1.losbroxas.org')
    .strip()
    .rstrip('/')
)
HYDRA_APPDATA_DIR = os.path.join(os.environ.get('APPDATA', ''), 'hydralauncher')


def _obter_hydra_data_dirs() -> list[str]:
    caminhos_base = []
    vistos = set()

    for env_var in ('APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'PROGRAMFILES', 'PROGRAMFILES(X86)', 'USERPROFILE'):
        valor = os.environ.get(env_var, '').strip()
        if valor and valor not in vistos:
            vistos.add(valor)
            caminhos_base.append(valor)

    user_profile = os.environ.get('USERPROFILE', '').strip()
    if user_profile:
        for sub in (os.path.join('AppData', 'Roaming'), os.path.join('AppData', 'Local'), 'Documents'):
            caminho = os.path.join(user_profile, sub)
            if caminho and caminho not in vistos:
                vistos.add(caminho)
                caminhos_base.append(caminho)

    candidatos = []
    for base in caminhos_base:
        if not base:
            continue
        for nome in ('hydralauncher', 'Hydra Launcher', 'Hydra'):
            diretorio = os.path.join(base, nome)
            if diretorio not in vistos:
                vistos.add(diretorio)
                candidatos.append(diretorio)

    for base in (os.environ.get('PROGRAMFILES', ''), os.environ.get('PROGRAMFILES(X86)', '')):
        if base and os.path.isdir(base):
            try:
                for nome in os.listdir(base):
                    if 'hydra' in nome.lower():
                        diretorio = os.path.join(base, nome)
                        if os.path.isdir(diretorio) and diretorio not in vistos:
                            vistos.add(diretorio)
                            candidatos.append(diretorio)
            except OSError:
                pass

    for base in (os.environ.get('APPDATA', ''), os.environ.get('LOCALAPPDATA', '')):
        if base and os.path.isdir(base):
            try:
                for nome in os.listdir(base):
                    if 'hydra' in nome.lower():
                        diretorio = os.path.join(base, nome)
                        if os.path.isdir(diretorio) and diretorio not in vistos:
                            vistos.add(diretorio)
                            candidatos.append(diretorio)
            except OSError:
                pass

    return candidatos


def _obter_hydra_appdata_pastas_possiveis() -> list[str]:
    return _obter_hydra_data_dirs()


def _obter_hydra_appdata_dir() -> str:
    candidatos = _obter_hydra_data_dirs()
    app.logger.info('[Hydra Cache] Diretórios Hydra candidatos: %s', candidatos)
    for diretorio in candidatos:
        if os.path.isdir(diretorio):
            if os.path.isdir(os.path.join(diretorio, 'hydra-db')) or os.path.isdir(os.path.join(diretorio, 'logs')) or os.path.isdir(os.path.join(diretorio, 'Local Storage')):
                app.logger.info('[Hydra Cache] Diretório Hydra válido encontrado: %s', diretorio)
                return diretorio
    if os.path.isdir(HYDRA_APPDATA_DIR):
        app.logger.info('[Hydra Cache] Usando HYDRA_APPDATA_DIR fallback: %s', HYDRA_APPDATA_DIR)
        return HYDRA_APPDATA_DIR
    app.logger.warning('[Hydra Cache] Nenhum diretório Hydra válido encontrado.')
    return ''


# Controle de presença online em memória
ONLINE_USERS = set()
CALL_PRESENCE = {}

CALL_PRESENCE_TTL = 35

def esta_online(email: str) -> bool:
    normalized = _normalizar_email(email)
    user = USUARIOS_DB.get(normalized)
    if user:
        if user.hydra_current_game:
            return True
        current_user_email = _normalizar_email(session.get('user_email', ''))
        if normalized == current_user_email and _hydra_local_ativo_real():
            return True
        if user.steam_online:
            return True
    return normalized in ONLINE_USERS or _presenca_call_ativa(normalized)


def _presenca_call_ativa(email: str) -> bool:
    dados = CALL_PRESENCE.get(email)
    if not dados:
        return False
    return (time.time() - dados.get('last_seen', 0)) <= CALL_PRESENCE_TTL


def _registrar_presenca_call(email: str, room_slug: str) -> None:
    agora = time.time()
    app.logger.debug('[Discord Call] registrar presenca: email=%s, room_slug=%s, agora=%s', email, room_slug, agora)
    dados_atuais = CALL_PRESENCE.get(email, {})
    CALL_PRESENCE[email] = {
        'room_slug': room_slug,
        'last_seen': agora,
        'joined_at': dados_atuais.get('joined_at', agora),
    }


def _remover_presenca_call(email: str) -> None:
    CALL_PRESENCE.pop(email, None)


def _limpar_presencas_call() -> None:
    expiradas = [email for email, dados in CALL_PRESENCE.items() if (time.time() - dados.get('last_seen', 0)) > CALL_PRESENCE_TTL]
    for email in expiradas:
        CALL_PRESENCE.pop(email, None)
        user = USUARIOS_DB.get(email)
        if user:
            user.discord_online = False


def _obter_participantes_call_ativos(room_slug: str) -> list:
    _limpar_presencas_call()
    participantes = []
    for email, dados in CALL_PRESENCE.items():
        if dados.get('room_slug') != room_slug:
            continue
        usuario = USUARIOS_DB.get(email)
        if not usuario:
            continue
        participantes.append({
            'email': usuario.email,
            'nome': usuario.nome,
            'foto_perfil': getattr(usuario, 'foto_perfil', ''),
            'joined_at': dados.get('joined_at', dados.get('last_seen', time.time())),
            'last_seen': dados.get('last_seen', time.time()),
        })
    participantes.sort(key=lambda item: item['nome'].lower())
    return participantes


def _formatar_tempo_decorrido(segundos: float) -> str:
    total = max(0, int(segundos))
    horas, resto = divmod(total, 3600)
    minutos, segundos = divmod(resto, 60)
    return f'{horas:02d}:{minutos:02d}:{segundos:02d}'


def _serializar_status_call(room_slug: str) -> dict:
    participantes_ativos = _obter_participantes_call_ativos(room_slug)
    call_iniciada_em = min((item['joined_at'] for item in participantes_ativos), default=time.time())
    return {
        'participantes_ativos': participantes_ativos,
        'quantidade': len(participantes_ativos),
        'tempo_decorrido': _formatar_tempo_decorrido(time.time() - call_iniciada_em),
        'call_iniciada_em': call_iniciada_em,
    }

@app.context_processor
def inject_status_helpers():
    _limpar_presencas_call()
    return {'esta_online': esta_online, 'em_call': _presenca_call_ativa}

def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False
    return True


def _salvar_anexo_chat(upload, tipo: str) -> dict | None:
    if not upload or not getattr(upload, 'filename', None):
        return None
    nome_original = secure_filename(upload.filename)
    if not nome_original:
        return None

    extensao = nome_original.rsplit('.', 1)[1].lower() if '.' in nome_original else ''
    if tipo == 'image' and extensao not in ALLOWED_CHAT_IMAGE_EXTENSIONS:
        return None
    if tipo == 'file' and extensao not in ALLOWED_CHAT_FILE_EXTENSIONS:
        return None

    tamanho = getattr(upload, 'content_length', None)
    if tamanho is not None and tamanho > MAX_CHAT_UPLOAD_SIZE:
        return None

    nome_arquivo = f'{uuid4().hex}_{nome_original}'
    caminho = os.path.join(CHAT_UPLOAD_DIR, nome_arquivo)
    upload.save(caminho)

    return {
        'nome': nome_original,
        'caminho': os.path.join('app-data', 'uploads', 'chat', nome_arquivo),
        'url': url_for('app_data_upload', filename=f'chat/{nome_arquivo}', _external=False),
        'tipo': 'image' if tipo == 'image' else 'file',
        'extensao': extensao,
    }


def _gerar_csrf_token() -> str:
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


@app.context_processor
def inject_security_context():
    return {'csrf_token': _gerar_csrf_token}


@app.before_request
def _proteger_sessoes_e_csrf():
    session.permanent = True
    if request.method in {'POST', 'PUT', 'DELETE', 'PATCH'}:
        token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        if not token or not secrets.compare_digest(token, session.get('csrf_token', '')):
            app.logger.warning(
                '[CSRF] Requisição inválida: method=%s path=%s token presente=%s, session_has_token=%s',
                request.method,
                request.path,
                bool(token),
                'csrf_token' in session,
            )
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'erro': 'Token CSRF inválido.'}), 400
            return render_template('erro.html', mensagem='Requisição inválida ou sessão expirada.'), 400


@app.after_request
def _aplicar_headers_seguro(resposta):
    resposta.headers['Content-Security-Policy'] = "default-src 'self' https:; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https:; script-src 'self' 'unsafe-inline' https:; font-src 'self' https: data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    resposta.headers['X-Content-Type-Options'] = 'nosniff'
    resposta.headers['X-Frame-Options'] = 'DENY'
    resposta.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    resposta.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    resposta.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    return resposta


@app.errorhandler(400)
def erro_400(_erro):
    return render_template('erro.html', mensagem='Requisição inválida.'), 400


@app.errorhandler(401)
def erro_401(_erro):
    return render_template('erro.html', mensagem='Você precisa fazer login para acessar esta página.'), 401


@app.errorhandler(403)
def erro_403(_erro):
    return render_template('erro.html', mensagem='Você não tem permissão para acessar este recurso.'), 403


@app.errorhandler(404)
def erro_404(_erro):
    return render_template('erro.html', mensagem='Página não encontrada.'), 404


@app.errorhandler(500)
def erro_500(_erro):
    return render_template('erro.html', mensagem='Ocorreu um erro inesperado. Tente novamente em instantes.'), 500


def _is_valid_cached_cover(caminho_arquivo: str) -> bool:
    """
    Verifies if a cached cover file is a real image (not a placeholder).
    Real covers are typically 30KB+, placeholders are ~1KB SVG files.
    """
    if not os.path.exists(caminho_arquivo):
        return False
    try:
        tamanho_bytes = os.path.getsize(caminho_arquivo)
        # Generated placeholders are valid image files too, but are not cache covers.
        if tamanho_bytes < 5000:
            return False
        # Try to open as image to verify it's valid
        img = Image.open(caminho_arquivo)
        img.verify()
        return True
    except Exception:
        return False


_CAPAS_EM_RESOLUCAO: set[str] = set()
_CAPAS_USUARIOS_AGENDADOS: set[str] = set()
_CAPAS_RESOLUCAO_LOCK = Lock()
_CAPAS_EXECUTOR = ThreadPoolExecutor(max_workers=4)


@lru_cache(maxsize=512)
def _obter_appid_steam_indice_local(titulo: str) -> int | None:
    termo = _normalizar_busca(titulo)
    if not termo:
        return None
    caminho = str(CACHE_DIR / 'steam_local_index.json')
    try:
        with open(caminho, 'r', encoding='utf-8') as arquivo:
            payload = json.load(arquivo)
        registros = payload.get('data', []) if isinstance(payload, dict) else []
        for registro in registros:
            nome = _normalizar_busca(str(registro.get('name') or ''))
            appid = registro.get('appid')
            if nome == termo and str(appid).isdigit():
                return int(appid)
    except (OSError, ValueError, TypeError):
        return None
    return None


@lru_cache(maxsize=512)
def _obter_appid_steam_por_nome(titulo: str) -> int | None:
    termo = (titulo or '').strip()
    if not termo:
        return None
    try:
        url = f'https://store.steampowered.com/api/storesearch/?term={quote(termo)}&cc=us&l=en'
        request = Request(url, headers={'User-Agent': 'GameUnexa/1.0', 'Accept': 'application/json'})
        with urlopen(request, timeout=5) as resposta:
            payload = json.loads(resposta.read().decode('utf-8', errors='replace'))
        busca = _normalizar_busca(termo)
        resultados = payload.get('items', []) if isinstance(payload, dict) else []
        for resultado in resultados:
            nome = _normalizar_busca(str(resultado.get('name') or ''))
            appid = resultado.get('id')
            if nome == busca and str(appid).isdigit():
                return int(appid)
        return None
    except Exception:
        return None


def _get_game_cover_centralized(
    titulo: str,
    appid: int | None = None,
    origem: str = 'manual',
    permitir_remoto: bool = True,
) -> str:
    """
    CENTRALIZED COVER RESOLVER
    
    Unified function to resolve game covers with proper prioritization:
    1. Steam AppID real cached images first
    2. Title-based real cached images (not 1KB placeholders)
    3. Download from external sources if needed
    4. Fall back to placeholder only as last resort
    
    This function ensures consistency across 2D/3D/Steam/Hydra/Manual interfaces.
    """
    if not titulo or not isinstance(titulo, str):
        return _capa_fallback('Jogo')
    
    titulo = titulo.strip()
    if not titulo:
        return _capa_fallback('Jogo')

    # A page render must stay local; remote AppID discovery is background-only.
    titulo_normalizado = _normalizar_titulo_capa(titulo)
    chave_title = f"title:{titulo_normalizado.lower()}"
    caminho_title = _caminho_cache_capa(chave_title)
    if _is_valid_cached_cover(caminho_title):
        return _caminho_cache_url(chave_title)

    if not appid:
        appid = _obter_appid_steam_indice_local(titulo)
    if not appid and permitir_remoto:
        appid = _obter_appid_steam_por_nome(titulo)

    # PRIORITY 1: Steam AppID
    if appid and isinstance(appid, int) and appid > 0:
        chave_appid = f"appid:{appid}"
        caminho_appid = _caminho_cache_capa(chave_appid)
        if _is_valid_cached_cover(caminho_appid):
            return _caminho_cache_url(chave_appid)

        if not permitir_remoto:
            return f'https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_600x900.jpg'
        
        if permitir_remoto:
            for url_steam in (
                f'https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_600x900.jpg',
                f'https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900.jpg',
                f'https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg',
            ):
                try:
                    resultado = _salvar_capa_em_cache(url_steam, chave_appid)
                    if resultado:
                        return resultado
                except Exception:
                    continue
    
    if not permitir_remoto:
        return _capa_fallback(titulo)

    # PRIORITY 3: Try to download from external sources
    try:
        # Try RAWG
        capa_rawg = _obter_capa_rawg(titulo)
        if capa_rawg:
            resultado = _salvar_capa_em_cache(capa_rawg, chave_title)
            if resultado:
                return resultado
    except Exception:
        pass
    
    # PRIORITY 4: Fall back to placeholder
    return _capa_fallback(titulo)


def _resolver_capa_item_background(email: str, item, jogo, origem: str, appid: int | None, chave: str) -> None:
    with _CAPAS_RESOLUCAO_LOCK:
        if chave in _CAPAS_EM_RESOLUCAO:
            return
        _CAPAS_EM_RESOLUCAO.add(chave)
    try:
        capa = _get_game_cover_centralized(getattr(jogo, 'titulo', ''), appid, origem, permitir_remoto=True)
        if capa and not capa.startswith('data:'):
            item.cover_url = capa
            persistir_biblioteca_item(item)
    except Exception as erro:
        print(f'[Covers Background] erro para {email}/{chave}: {erro}')
    finally:
        with _CAPAS_RESOLUCAO_LOCK:
            _CAPAS_EM_RESOLUCAO.discard(chave)


def _preencher_capas_biblioteca(email: str) -> None:
    """Queue missing covers after the response without blocking navigation."""
    try:
        itens = GerenciadorBiblioteca.obter_biblioteca(email)
        for item in itens:
            jogo = JOGOS_DB.get(getattr(item, 'jogo_id', 0))
            if not jogo:
                continue
            origem = (getattr(item, 'launcher', '') or getattr(item, 'origem', '') or 'manual').strip().lower()
            if origem not in {'steam', 'hydra', 'manual'}:
                origem = 'manual'
            capa_atual = getattr(item, 'cover_url', '') or ''
            if _usar_capa_armazenada(capa_atual, origem):
                continue
            appid = None
            codigo = str(getattr(item, 'codigo_origem', '') or '').strip()
            if codigo.isdigit():
                appid = int(codigo)
            elif origem == 'steam' and str(getattr(jogo, 'id', '')).isdigit():
                appid = int(jogo.id)
            chave = f'appid:{appid}' if appid else f'game:{getattr(jogo, "id", "")}'
            _CAPAS_EXECUTOR.submit(
                _resolver_capa_item_background,
                email,
                item,
                jogo,
                origem,
                appid,
                chave,
            )
    except Exception as erro:
        print(f'[Covers Background] erro para {email}: {erro}')


def _agendar_capas_biblioteca(email: str) -> None:
    email = (email or '').strip().lower()
    if not email:
        return
    with _CAPAS_RESOLUCAO_LOCK:
        if email in _CAPAS_USUARIOS_AGENDADOS:
            return
        _CAPAS_USUARIOS_AGENDADOS.add(email)

    def executar() -> None:
        try:
            _preencher_capas_biblioteca(email)
        finally:
            with _CAPAS_RESOLUCAO_LOCK:
                _CAPAS_USUARIOS_AGENDADOS.discard(email)

    Thread(target=executar, daemon=True).start()


def _capa_fallback(titulo: str) -> str:
    titulo_texto = (titulo or 'Jogo').strip() or 'Jogo'
    titulo_limpo = escape(titulo_texto[:40])
    svg = f'''
    <svg xmlns="http://www.w3.org/2000/svg" width="600" height="900" viewBox="0 0 600 900">
        <defs>
            <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stop-color="#071120"/>
                <stop offset="45%" stop-color="#0f172a"/>
                <stop offset="100%" stop-color="#111827"/>
            </linearGradient>
            <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.95"/>
                <stop offset="100%" stop-color="#2563eb" stop-opacity="0.25"/>
            </linearGradient>
            <filter id="blur" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="32"/>
            </filter>
        </defs>
        <rect width="600" height="900" rx="36" fill="url(#bg)"/>
        <circle cx="158" cy="182" r="170" fill="#38bdf8" fill-opacity="0.16" filter="url(#blur)"/>
        <circle cx="452" cy="760" r="220" fill="#2563eb" fill-opacity="0.18" filter="url(#blur)"/>
        <rect x="38" y="38" width="524" height="824" rx="30" fill="rgba(255,255,255,0.04)" stroke="rgba(148,163,184,0.18)"/>
        <rect x="92" y="690" width="416" height="12" rx="6" fill="url(#accent)"/>
        <rect x="92" y="714" width="308" height="8" rx="4" fill="rgba(148,163,184,0.16)"/>
        <circle cx="300" cy="320" r="74" fill="rgba(56,189,248,0.16)" stroke="rgba(125,211,252,0.42)" stroke-width="2"/>
        <path d="M300 258c24 0 43 19 43 43 0 24-19 43-43 43-24 0-43-19-43-43 0-24 19-43 43-43Zm0 94c46 0 84 24 84 54v24H216v-24c0-30 38-54 84-54Z" fill="#7dd3fc" fill-opacity="0.9"/>
        <text x="300" y="430" fill="#f8fafc" font-family="Arial, Helvetica, sans-serif" font-size="27" font-weight="700" text-anchor="middle">{titulo_limpo}</text>
        <text x="300" y="478" fill="#cbd5e1" font-family="Arial, Helvetica, sans-serif" font-size="17" font-weight="500" text-anchor="middle">Capa indisponível</text>
        <text x="300" y="512" fill="#7dd3fc" font-family="Arial, Helvetica, sans-serif" font-size="15" font-weight="500" text-anchor="middle">Tentando localizar</text>
    </svg>
    '''.strip()
    return 'data:image/svg+xml;charset=UTF-8,' + quote(svg)


def _normalizar_busca(texto: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', (texto or '').lower()).strip()


def _extrair_ano_texto(titulo: str) -> int | None:
    correspondencia = re.search(r'\b(19\d{2}|20\d{2})\b', titulo or '')
    if not correspondencia:
        return None
    ano = int(correspondencia.group(1))
    return ano if 1950 <= ano <= 2035 else None


def _titulo_sem_ano(titulo: str) -> str:
    texto = re.sub(r'\b(19\d{2}|20\d{2})\b', ' ', titulo or '')
    return _normalizar_busca(texto)


RAWG_SLUGS_FIXOS = {
    ('the witcher 3', None): 'the-witcher-3-wild-hunt',
    ('the witcher 3 wild hunt', None): 'the-witcher-3-wild-hunt',
    ('elden ring', None): 'elden-ring',
    ('gta v', None): 'grand-theft-auto-v',
    ('grand theft auto v', None): 'grand-theft-auto-v',
    ('god of war', 2005): 'god-of-war',
    ('god of war', 2018): 'god-of-war-2',
    ('god of war ragnarok', 2022): 'god-of-war-ragnarok',
}


def _normalizar_titulo_capa(titulo: str) -> str:
    texto = (titulo or '').strip()
    texto = texto.replace('™', '').replace('®', '').replace('_', ' ')
    texto = re.sub(r'\b(edition|definitive edition|complete edition|deluxe edition|remastered|goty|gold edition|ultimate edition|hd|remake|demo|beta|alpha|early access)\b', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\b(iii|ii|iv|v|vi|vii|viii|ix|x)\b', lambda m: str(int(['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x'].index(m.group(1)) + 1) if False else m.group(1)), texto, flags=re.IGNORECASE)
    texto = re.sub(r'\b(19\d{2}|20\d{2})\b', '', texto)
    texto = re.sub(r'[^\w\s]+', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    texto = re.sub(r'\b(the|and)\b', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\s+', ' ', texto).strip()
    texto = re.sub(r'\b([ivx]+)\b', lambda m: m.group(1).lower(), texto, flags=re.IGNORECASE)
    if texto.lower().endswith(' edition'):
        texto = texto[:-8].strip()
    return texto


def _normalizar_titulo_capa_para_busca(titulo: str) -> str:
    texto = _normalizar_titulo_capa(titulo)
    texto = re.sub(r'\bthe\b', '', texto, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', texto).strip()


def _buscar_html_com_user_agent(url: str, timeout: int = 10) -> str:
    request = Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        },
    )
    with urlopen(request, timeout=timeout) as resposta:
        return resposta.read().decode('utf-8', errors='replace')


def _obter_slug_rawg(titulo: str, ano: int | None = None) -> str | None:
    ano_detectado = ano if ano is not None else _extrair_ano_texto(titulo)
    titulo_base = _titulo_sem_ano(titulo)

    slug_fixo = RAWG_SLUGS_FIXOS.get((titulo_base, ano_detectado)) or RAWG_SLUGS_FIXOS.get((titulo_base, None))
    if slug_fixo:
        return slug_fixo

    try:
        html = _buscar_html_com_user_agent(f'https://rawg.io/games?search={quote(titulo_base or titulo)}', timeout=10)
        candidatos = re.findall(r'<a class="game-card-medium__info__name" href="/games/([^"]+)">([^<]+)', html, re.I)
    except Exception:
        return None
    if not candidatos:
        return None

    busca_normalizada = _normalizar_busca(_normalizar_titulo_capa_para_busca(titulo)) or _normalizar_busca(titulo)
    melhor_slug = None
    melhor_pontuacao = 0.0
    for slug, nome in candidatos:
        nome_normalizado = _normalizar_busca(nome)
        pontuacao = SequenceMatcher(None, busca_normalizada, nome_normalizado).ratio()
        if ano_detectado and re.search(rf'\b{ano_detectado}\b', nome):
            pontuacao += 0.25
        if busca_normalizada and nome_normalizado == busca_normalizada:
            pontuacao += 0.4
        if pontuacao > melhor_pontuacao:
            melhor_pontuacao = pontuacao
            melhor_slug = slug

    if melhor_pontuacao < 0.9:
        return None

    return melhor_slug


def _obter_capa_rawg(titulo: str, ano: int | None = None) -> str | None:
    slug = _obter_slug_rawg(titulo, ano)
    if not slug:
        return None

    try:
        html = _buscar_html_com_user_agent(f'https://rawg.io/games/{slug}', timeout=10)
        correspondencia = re.search(r'property="og:image" content="([^"]+)"', html, re.I)
    except Exception:
        return None
    if correspondencia:
        return correspondencia.group(1)

    return None


def _caminho_cache_capa(chave: str) -> str:
    nome_arquivo = f"{re.sub(r'[^a-zA-Z0-9._-]+', '_', chave).strip('_') or 'cover'}.webp"
    return str(CACHE_DIR / 'covers' / nome_arquivo)


def _caminho_cache_url(chave: str) -> str:
    return f"/app-data/cache/covers/{os.path.basename(_caminho_cache_capa(chave))}"


def _extrair_urls_imagem_html(html: str) -> list[str]:
    urls = []
    for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I):
        urls.append(match.group(1))
    for match in re.finditer(r'property="og:image" content="([^"]+)"', html, re.I):
        urls.append(match.group(1))
    return list(dict.fromkeys(urls))


def _salvar_capa_em_cache(url: str, chave: str) -> str | None:
    if not url:
        return None
    caminho = _caminho_cache_capa(chave)
    if os.path.exists(caminho) and _is_valid_cached_cover(caminho):
        return _caminho_cache_url(chave)
    if os.path.exists(caminho):
        try:
            os.remove(caminho)
        except OSError:
            return None

    try:
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request, timeout=15) as resposta:
            dados = resposta.read()
        if not dados:
            return None
        content_type = resposta.headers.get('Content-Type', '') if hasattr(resposta, 'headers') else ''
        if 'text/html' in content_type.lower():
            texto = dados.decode('utf-8', errors='replace')
            urls_imagem = _extrair_urls_imagem_html(texto)
            for imagem_url in urls_imagem:
                if imagem_url.startswith('http'):
                    return _salvar_capa_em_cache(imagem_url, chave)
            return None

        imagem = Image.open(BytesIO(dados)).convert('RGB')
        largura, altura = imagem.size
        if largura < 300 or altura < 200:
            return None
        imagem = ImageOps.fit(imagem, (600, 900), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        imagem.save(caminho, format='WEBP', quality=90)
        return _caminho_cache_url(chave)
    except Exception:
        return None


def _gerar_placeholder_capa(titulo: str) -> str:
    return _capa_fallback(titulo)


def _usar_capa_armazenada(url: str | None, origem: str | None = None, appid: int | None = None) -> bool:
    if not url:
        return False
    url_normalizada = (url or '').strip().lower()
    if not url_normalizada:
        return False
    if url_normalizada.startswith('data:image'):
        return False
    if url_normalizada.startswith('/app-data/cache/covers/'):
        caminho = os.path.join(os.path.dirname(__file__), url_normalizada.lstrip('/').replace('/', os.sep))
        if not _is_valid_cached_cover(caminho):
            return False
        correspondencia = re.search(r'/appid_(\d+)\.webp$', url_normalizada)
        if correspondencia and (not appid or int(correspondencia.group(1)) != int(appid)):
            return False
        return True
    if 'icon' in url_normalizada and 'hydra' in url_normalizada:
        return False
    if '/icon' in url_normalizada or 'iconurl' in url_normalizada or 'icons/' in url_normalizada:
        return False
    if origem and origem.lower() == 'hydra' and ('icon' in url_normalizada or 'thumbnail' in url_normalizada):
        return False
    return True


def _resolver_capa_jogo(titulo: str, appid: int | None = None, metadata: dict | None = None) -> str:
    texto = (titulo or '').strip()
    if not texto and not appid:
        return _gerar_placeholder_capa('Jogo')

    chave = f"appid:{appid}" if appid else f"title:{texto.lower()}"
    caminho_cache = _caminho_cache_capa(chave)
    if os.path.exists(caminho_cache):
        return _caminho_cache_url(chave)

    candidatos = []
    if appid:
        candidatos.append(('Steam CDN', f'https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_600x900.jpg'))
    if metadata and metadata.get('cover_url'):
        candidatos.append(('Hydra Metadata', metadata['cover_url']))
    if texto:
        nome_busca = _normalizar_titulo_capa_para_busca(texto)
        candidatos.extend([
            ('RAWG', f'https://rawg.io/games?search={quote(nome_busca)}'),
            ('SteamGridDB', f'https://www.steamgriddb.com/search/autocomplete/{quote(nome_busca)}'),
            ('IGDB', f'https://www.igdb.com/search?q={quote(nome_busca)}'),
        ])

    for _nome_fonte, url in candidatos:
        if not url:
            continue
        resultado = _salvar_capa_em_cache(url, chave)
        if resultado:
            return resultado

    return _gerar_placeholder_capa(texto or 'Jogo')
    # New function to resolve cover presence
def _resolver_capa_presenca(usuario, titulo: str, appid: int | None = None, launcher: str = '') -> str:
    """Reutiliza a capa da biblioteca antes de consultar qualquer fallback externo."""
    titulo_normalizado = _normalizar_busca(titulo)
    appid_texto = str(appid or '').strip()
    origem = (launcher or '').strip().lower()

    try:
        itens = GerenciadorBiblioteca.obter_biblioteca(usuario.email)
    except Exception:
        itens = []

    for item in itens:
        jogo = JOGOS_DB.get(getattr(item, 'jogo_id', 0))
        nome_jogo = getattr(jogo, 'titulo', '') if jogo else ''
        codigo_origem = str(getattr(item, 'codigo_origem', '') or '').strip()
        mesmo_appid = bool(appid_texto and (str(getattr(item, 'jogo_id', '')) == appid_texto or codigo_origem == appid_texto))
        mesmo_nome = bool(titulo_normalizado and _normalizar_busca(nome_jogo) == titulo_normalizado)
        item_origem = (getattr(item, 'launcher', '') or getattr(item, 'origem', '') or '').strip().lower()
        origem_compativel = not origem or not item_origem or origem == item_origem or {origem, item_origem} == {'local', 'manual'}
        capa = getattr(item, 'cover_url', '') or ''
        if (mesmo_appid or mesmo_nome) and origem_compativel and _usar_capa_armazenada(capa, item_origem):
            return capa

    return _resolver_capa_jogo(titulo, appid=appid)


@lru_cache(maxsize=256)
def obter_capa_jogo(titulo: str, ano: int | None = None) -> str:
    if not titulo:
        return _capa_fallback('Jogo')

    texto = (titulo or '').strip()
    if not texto:
        return _capa_fallback('Jogo')

    chave = f"title:{texto.lower()}"
    caminho_cache = _caminho_cache_capa(chave)
    if os.path.exists(caminho_cache):
        return _caminho_cache_url(chave)

    try:
        capa_rawg = _obter_capa_rawg(texto, ano)
        if capa_rawg:
            resultado = _salvar_capa_em_cache(capa_rawg, chave)
            if resultado:
                return resultado
    except Exception:
        pass

    return _resolver_capa_jogo(texto)


def _capa_steam_jogo(appid: int) -> str:
    if not appid:
        return ''
    return _resolver_capa_jogo('', appid=appid)


def _capa_para_jogo_catalogo(jogo, usadas: set[str], permitir_remoto: bool = True) -> str:
    """Use centralized cover resolver instead of scattered functions."""
    titulo = getattr(jogo, 'titulo', '') or ''
    appid = int(getattr(jogo, 'id', 0) or 0) if getattr(jogo, 'genero', '').lower() == 'steam' else None
    origem = getattr(jogo, 'genero', '').lower() if getattr(jogo, 'genero', '').lower() in {'steam', 'hydra'} else 'manual'
    
    # Use centralized resolver
    capa = _get_game_cover_centralized(titulo, appid, origem, permitir_remoto=permitir_remoto)
    if capa:
        usadas.add(capa)
    return capa


def _capa_unica_para_lista(titulo: str, ano: int | None, usadas: set[str]) -> str:
    capa = obter_capa_jogo(titulo, ano)
    if capa in usadas:
        capa = _gerar_placeholder_capa(titulo)
    usadas.add(capa)
    return capa


def _steam_api_key_usuario(user) -> str:
    return (getattr(user, 'steam_api_key', '') or os.environ.get('STEAM_API_KEY') or '').strip()


def _steam_id_ou_vanity_usuario(user) -> str:
    return (getattr(user, 'steam_id64', '') or '').strip()


def _hydra_fetch_json(url: str, extra_headers: dict | None = None) -> dict | list:
    headers = {
        'User-Agent': 'GameUnexa/1.0',
        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
    }
    if extra_headers:
        headers.update(extra_headers)

    request = Request(
        url,
        headers=headers,
    )
    with urlopen(request, timeout=8) as resposta:
        return json.loads(resposta.read().decode('utf-8', errors='replace'))


def _hydra_token_local_detectado() -> str:
    tokens = _hydra_tokens_locais_detectados()
    return tokens[0] if tokens else ''


def _hydra_tokens_locais_detectados() -> list[str]:
    hydra_dir = _obter_hydra_appdata_dir()
    if not hydra_dir:
        return []

    candidatos = [
        os.path.join(hydra_dir, 'hydra-db', '000005.ldb'),
        os.path.join(hydra_dir, 'hydra-db', '000006.log'),
        os.path.join(hydra_dir, 'logs', 'network.txt'),
        os.path.join(hydra_dir, 'logs', 'info.txt'),
        os.path.join(hydra_dir, 'logs', 'logs.txt'),
    ]

    tokens_encontrados = []

    for caminho in candidatos:
        if not os.path.isfile(caminho):
            continue

        try:
            with open(caminho, 'r', encoding='utf-8', errors='replace') as arquivo:
                conteudo = arquivo.read()
        except OSError:
            continue

        padroes = (
            r'"accessToken"\s*:\s*"([^"]+)"',
            r'"workwondersJwt"\s*:\s*"([^"]+)"',
            r'"token"\s*:\s*"([^"]+)"',
            r"workwondersJwt:\s*'([^']+)'",
            r"token:\s*'([^']+)'",
        )

        for padrao in padroes:
            for token in re.findall(padrao, conteudo):
                token = token.strip()
                if token and token not in tokens_encontrados:
                    tokens_encontrados.append(token)

        for token in re.findall(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", conteudo):
            token = token.strip()
            if token and token not in tokens_encontrados:
                tokens_encontrados.append(token)

    return tokens_encontrados


def _obter_hydra_cache_arquivos(hydra_dir: str) -> list[str]:
    arquivos = []
    candidatos = [
        os.path.join(hydra_dir, 'logs', 'network.txt'),
        os.path.join(hydra_dir, 'logs', 'network.log'),
        os.path.join(hydra_dir, 'logs', 'network.old.txt'),
        os.path.join(hydra_dir, 'logs', 'logs.txt'),
        os.path.join(hydra_dir, 'logs', 'info.txt'),
        os.path.join(hydra_dir, 'logs', 'error.txt'),
    ]

    for caminho in candidatos:
        if os.path.isfile(caminho):
            arquivos.append(caminho)

    for subdir in ('hydra-db', os.path.join('Local Storage', 'leveldb'), 'shared_proto_db'):
        pasta = os.path.join(hydra_dir, subdir)
        if os.path.isdir(pasta):
            for nome_arquivo in os.listdir(pasta):
                nome_arquivo_lower = nome_arquivo.lower()
                if nome_arquivo_lower.endswith(('.log', '.ldb')):
                    arquivos.append(os.path.join(pasta, nome_arquivo))

    if arquivos:
        arquivos = sorted(set(arquivos))
    return arquivos


def _hydra_parse_cache_text(conteudo: str) -> tuple[list[dict], str]:
    jogos = []
    display_name = ''

    if not conteudo:
        return [], display_name


    match_display_name = re.search(r"displayName\s*[:=]\s*['\"]([^'\"]+)['\"]", conteudo)
    if match_display_name:
        display_name = match_display_name.group(1).strip()

    padroes = [
        re.compile(
            r"objectId\s*[:=]\s*['\"](?P<objectId>[^'\"]+)['\"]"  # object id
            r".*?shop\s*[:=]\s*['\"](?P<shop>[^'\"]+)['\"]"  # shop
            r".*?title\s*[:=]\s*['\"](?P<title>[^'\"]+)['\"]"  # title
            r".*?(?:coverImageUrl|libraryHeroImageUrl|heroImageUrl|iconUrl)\s*[:=]\s*['\"](?P<coverImageUrl>[^'\"]*)['\"]"  # cover
            r".*?(?:playTimeInSeconds|playTimeInMilliseconds)\s*[:=]\s*(?P<playTime>\d+)",
            re.S,
        ),
        re.compile(
            r"objectId\s*[:=]\s*['\"](?P<objectId>[^'\"]+)['\"]"  # object id
            r".*?shop\s*[:=]\s*['\"](?P<shop>[^'\"]+)['\"]"  # shop
            r".*?title\s*[:=]\s*['\"](?P<title>[^'\"]+)['\"]"  # title
            r".*?(?:playTimeInSeconds|playTimeInMilliseconds)\s*[:=]\s*(?P<playTime>\d+)",
            re.S,
        ),
    ]

    vistos = set()
    for padrao in padroes:
        for match in padrao.finditer(conteudo):
            object_id = match.group('objectId').strip()
            if not object_id:
                continue
            chave = object_id.lower()
            if chave in vistos:
                continue
            vistos.add(chave)

            titulo = match.group('title').strip()
            cover_url = (match.groupdict().get('coverImageUrl') or '').strip()
            play_time = int(match.group('playTime') or 0)
            if 'playtimeinmilliseconds' in match.group(0).lower():
                play_time = int(play_time // 1000)

            jogos.append({
                'objectId': object_id,
                'shop': match.group('shop').strip(),
                'title': titulo,
                'cover_url': cover_url,
                'playTimeInSeconds': play_time,
                'isPinned': False,
                'isFavorite': False,
                'achievements_unlocked': 0,
                'achievements_total': 0,
            })

    return jogos, display_name


def _hydra_cache_local_jogos() -> tuple[list[dict], str]:
    hydra_dir = _obter_hydra_appdata_dir()
    if not hydra_dir:
        app.logger.warning('[Hydra Cache] Não foi possível localizar diretório Hydra Launcher.')
        return [], ''

    arquivos_cache = _obter_hydra_cache_arquivos(hydra_dir)
    app.logger.info('[Hydra Cache] Diretório identificado: %s', hydra_dir)
    app.logger.info('[Hydra Cache] Arquivos de cache candidatos: %s', arquivos_cache)

    if not arquivos_cache:
        app.logger.warning('[Hydra Cache] Nenhum arquivo de cache Hydra encontrado em %s', hydra_dir)
        return [], ''

    display_name = ''
    jogos_por_id = {}

    for caminho_log in arquivos_cache:
        try:
            stat = os.stat(caminho_log)
        except OSError as exc:
            app.logger.warning('[Hydra Cache] Falha ao acessar arquivo %s: %s', caminho_log, exc)
            continue

        file_state = (stat.st_mtime, stat.st_size)
        cached = HYDRA_CACHE_FILE_STATE.get(caminho_log)
        if cached and cached[0] == file_state:
            jogos_arquivo, display_arquivo = cached[1]
            app.logger.info('[Hydra Cache] Usando cache para arquivo %s', caminho_log)
        else:
            try:
                with open(caminho_log, 'r', encoding='utf-8', errors='replace') as arquivo:
                    conteudo = arquivo.read()
            except OSError as exc:
                app.logger.warning('[Hydra Cache] Falha ao ler arquivo de cache Hydra (%s): %s', caminho_log, exc)
                continue

            jogos_arquivo, display_arquivo = _hydra_parse_cache_text(conteudo)
            HYDRA_CACHE_FILE_STATE[caminho_log] = (file_state, (jogos_arquivo, display_arquivo))

        if display_arquivo:
            display_name = display_arquivo

        for jogo in jogos_arquivo:
            chave = (str(jogo.get('objectId') or jogo.get('title') or '')).strip().lower()
            if not chave:
                continue
            existente = jogos_por_id.get(chave)
            if existente is None or (jogo.get('playTimeInSeconds') or 0) > (existente.get('playTimeInSeconds') or 0):
                jogos_por_id[chave] = jogo

        app.logger.info('[Hydra Cache] %d jogos extraídos de %s', len(jogos_arquivo), caminho_log)

    jogos = sorted(jogos_por_id.values(), key=lambda item: item.get('playTimeInSeconds', 0), reverse=True)
    if jogos:
        app.logger.info('[Hydra Cache] Total de jogos únicos encontrados: %d', len(jogos))
        return jogos, display_name

    app.logger.info('[Hydra Cache] Nenhum jogo encontrado nos arquivos de cache analisados.')
    return [], display_name


def _hydra_get_running_processes() -> set[str]:
    """Obtém lista de processos REAIS em execução no Windows (SEM CACHE).
    
    Esta função SEMPRE consulta o Windows para obter estado real.
    Nunca retorna dados em cache.
    
    Returns:
        Set com nomes de executáveis em minúsculas
    """
    try:
        # Tasklist rápido - SEM CACHE
        resultado = subprocess.run(
            ['tasklist'],
            capture_output=True,
            text=True,
            timeout=2.0,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if resultado.returncode != 0:
            return set()
        
        processos = set()
        for linha in resultado.stdout.split('\n'):
            linha = linha.strip().lower()
            if linha and '.exe' in linha:
                partes = linha.split()
                if partes:
                    processos.add(partes[0])
        
        return processos
    except subprocess.TimeoutExpired:
        print('[Hydra REAL-STATE] Timeout ao listar processos')
        return set()
    except Exception as e:
        print(f'[Hydra REAL-STATE] Erro ao listar processos: {e}')
        return set()


def _hydra_obter_whitelist_executaveis() -> set[str]:
    """Extrai executáveis REAIS de jogos instalados.
    
    ESTRATÉGIA DEFINITIVA:
    1. Lê da pasta de jogos do Hydra (se existir)
    2. Adiciona executáveis da biblioteca local (BIBLIOTECA_DB)
    3. NUNCA retorna None - sempre retorna um set (vazio se necessário)
    4. Rejeita ABSOLUTAMENTE tudo se não tiver confirmação de jogo
    
    Returns:
        Set com executáveis em minúsculas (.exe incluído)
        Vazio se nenhum jogo for encontrado (modo SUPER SEGURO)
    """
    whitelist = set()
    
    # ESTRATÉGIA 1: Ler da pasta de jogos do Hydra
    try:
        games_dir = os.path.join(HYDRA_APPDATA_DIR, 'games')
        if os.path.isdir(games_dir):
            print(f'[Hydra WHITELIST] Lendo pasta de jogos: {games_dir}')
            for pasta_jogo in os.listdir(games_dir):
                caminho_jogo = os.path.join(games_dir, pasta_jogo)
                if os.path.isdir(caminho_jogo):
                    meta_file = os.path.join(caminho_jogo, 'metadata.json')
                    if os.path.isfile(meta_file):
                        try:
                            with open(meta_file, 'r', encoding='utf-8', errors='replace') as f:
                                meta = json.load(f)
                                exe = (meta.get('executable') or 
                                      meta.get('executablePath') or 
                                      meta.get('launchPath') or '').lower().strip()
                                
                                if exe and exe.endswith('.exe'):
                                    whitelist.add(exe)
                                    game_title = meta.get('title', pasta_jogo)
                                    print(f'[Hydra WHITELIST] OK Jogo Hydra: {game_title} -> {exe}')
                        except Exception as e:
                            print(f'[Hydra WHITELIST] Erro ao ler {meta_file}: {e}')
    except Exception as e:
        print(f'[Hydra WHITELIST] Erro ao ler pasta de jogos: {e}')
    
    # ESTRATÉGIA 2: Adiciona executáveis da biblioteca local do GameUnexa
    try:
        if BIBLIOTECA_DB and isinstance(BIBLIOTECA_DB, dict):
            print(f'[Hydra WHITELIST] Lendo biblioteca local ({len(BIBLIOTECA_DB)} itens)')
            for game_id, item in BIBLIOTECA_DB.items():
                try:
                    exe = None
                    
                    if hasattr(item, 'executavel'):
                        exe = item.executavel
                    elif hasattr(item, 'executable'):
                        exe = item.executable
                    elif hasattr(item, 'launch_path'):
                        exe = item.launch_path
                    elif isinstance(item, dict):
                        exe = item.get('executavel') or item.get('executable')
                    
                    if exe:
                        exe = str(exe).lower().strip()
                        if '\\' in exe or '/' in exe:
                            exe = os.path.basename(exe)
                        
                        if exe and exe.endswith('.exe'):
                            whitelist.add(exe)
                            game_title = getattr(item, 'titulo', getattr(item, 'title', game_id))
                            print(f'[Hydra WHITELIST] OK Jogo GameUnexa: {game_title} -> {exe}')
                except Exception as e:
                    print(f'[Hydra WHITELIST] Erro ao processar item {game_id}: {e}')
    except Exception as e:
        print(f'[Hydra WHITELIST] Erro ao ler BIBLIOTECA_DB: {e}')
    
    if not whitelist:
        print('[Hydra WHITELIST] AVISO: Nenhum jogo encontrado - modo SUPER SEGURO')
    else:
        print(f'[Hydra WHITELIST] OK Total de executaveis validos: {len(whitelist)}')
        for exe in sorted(whitelist)[:3]:
            print(f'[Hydra WHITELIST]    - {exe}')
    
    return whitelist


# BLACKLIST ABRANGENTE: Todos os processos que NÃO são jogos
# Inclui: Sistema, Drivers, Antivírus, Navegadores, Messaging, Dev Tools
_BLACKLIST_PROCESSOS_SISTEMA = {
    # Sistema Windows
    'system.exe', 'idle.exe', 'svchost.exe', 'services.exe', 'lsass.exe',
    'smss.exe', 'csrss.exe', 'wininit.exe', 'winlogon.exe', 'logonui.exe',
    'userinit.exe', 'dwm.exe', 'explorer.exe', 'taskhostw.exe', 'taskhost.exe',
    'conhost.exe', 'spoolsv.exe', 'rundll32.exe', 'regsvcs.exe', 'regasm.exe',
    'msiexec.exe', 'wisptis.exe',
    
    # Gerenciador de tarefas e ferramentas
    'taskmgr.exe', 'taskmgrexe', 'taskmgre.exe', 'devmgmt.exe', 'diskmgmt.exe',
    'compmgmt.exe', 'eventvwr.exe', 'perfmon.exe', 'resmon.exe', 'werfault.exe',
    'drwtsn32.exe', 'verclsid.exe', 'wudfhost.exe',
    
    # Antivírus e Segurança
    'msseces.exe', 'avp.exe', 'avpui.exe', 'avgui.exe', 'afwserv.exe',
    'fshoster32.exe', 'mcshield.exe', 'mctray.exe', 'isafe.exe',
    'ntssrvcs.exe', 'symproxysvc.exe', 'zlsvc.exe', 'zlclient.exe',
    'emsw.exe', 'shstat.exe', 'swdoctor.exe', 'swagent.exe',
    
    # Navegadores
    'chrome.exe', 'firefox.exe', 'msedge.exe', 'iexplore.exe', 'opera.exe',
    'safari.exe', 'vivaldi.exe', 'brave.exe', 'waterfox.exe',
    
    # Comunicação
    'discord.exe', 'telegram.exe', 'whatsapp.exe', 'skype.exe', 'teams.exe',
    'slack.exe', 'thunderbird.exe', 'outlook.exe',
    
    # Produtividade
    'winword.exe', 'excel.exe', 'powerpnt.exe', 'onenote.exe', 'access.exe',
    'code.exe', 'vim.exe', 'notepad.exe', 'notepad++.exe',
    
    # Cloud/Sync
    'dropbox.exe', 'googledrivesync.exe', 'onedrive.exe', 'sync.exe',
    
    # Serviços
    'python.exe', 'pythonw.exe', 'node.exe', 'npm.exe', 'java.exe', 'javaw.exe',
    'ruby.exe', 'perl.exe', 'php.exe', 'flask.exe', 'hydra.exe',
    
    # Sistema/Drivers
    'svchost.exe', 'rundll32.exe', 'ctfmon.exe', 'dllhost.exe',
    'nvcontainer.exe', 'nvdisplay.exe', 'amd radeon settings.exe',
    'igfxem.exe', 'igfxtray.exe', 'hkcmd.exe',
    
    # Audio/Vídeo
    'audiodg.exe', 'snd.exe', 'wmplayer.exe', 'vlc.exe', 'mpv.exe',
    'mpc-hc.exe', 'potplayer.exe',
    
    # Utilitários
    '7zfm.exe', 'winrar.exe', 'peazip.exe', 'everything.exe',
    'totalcmd.exe', 'powertoys.exe', 'putty.exe', 'winscp.exe',
    
    # Virtualização
    'vmwareplayer.exe', 'vmware.exe', 'vboxheadless.exe', 'virtualbox.exe',
    
    # Game Launchers/Platform Utilities (não são jogos)
    'steam.exe', 'launcher.exe',
    'gog galaxy.exe', 'bethesdanet.exe', 'uplay.exe', 'ubisoft.exe',
    'playnite.exe', 'lutris.exe', 'wineserver.exe', 'proton.exe',
    'steamruntime.exe', 'steamwebhelper.exe', 'steamclient.exe',
    
    # Windows Store e Serviços
    'wsappx.exe', 'w10updateassistant.exe', 'windowsupdater.exe',
    'trustedinstaller.exe', 'tiworker.exe', 'searchindexer.exe',
    'searchfilterhost.exe', 'searchprotocolhost.exe', 'background transfer service.exe',
    
    # Drivers/Kernel
    'ntdll.exe', 'kernel32.exe', 'dxgi.dll', 'd3d11.dll', 'dxdiag.exe',
    'dxdiagn.dll', 'wddm1_0.exe'
}


def _hydra_detect_running_game_real() -> str:
    """Detecta jogo em execução NO HYDRA com validacao RIGOROSA (SEM CACHE).
    
    ARQUITETURA DEFINITIVA:
    1. Obtém whitelist de jogos REAIS instalados
    2. Obtém processos em execução
    3. REJEITA TUDO na BLACKLIST de sistema
    4. VALIDA contra a WHITELIST
    5. SO retorna se confirmado como jogo
    
    Returns:
        Nome do jogo ou string vazia ('')
    """
    # PASSO 1: Obter whitelist de jogos REAIS
    whitelist = _hydra_obter_whitelist_executaveis()
    
    # Se nao ha nenhum jogo instalado, nada a fazer
    if not whitelist:
        print('[Hydra DETECT] Info: Nenhum jogo instalado detectado')
        return ''
    
    # PASSO 2: Obter processos em execucao
    processos_ativos = _hydra_get_running_processes()
    
    if not processos_ativos:
        print('[Hydra DETECT] Info: Nenhum processo ativo')
        return ''
    
    print(f'[Hydra DETECT] Processos ativos: {len(processos_ativos)}')
    print(f'[Hydra DETECT] Whitelist de jogos: {len(whitelist)} itens')
    
    # PASSO 3: Filtrar BLACKLIST (primeira linha de defesa)
    print(f'[Hydra DETECT] Filtrando blacklist...')
    processos_candidatos = set()
    processos_rejeitados = set()
    
    for proc in processos_ativos:
        if proc in _BLACKLIST_PROCESSOS_SISTEMA:
            processos_rejeitados.add(proc)
            continue
        processos_candidatos.add(proc)
    
    if processos_rejeitados:
        print(f'[Hydra DETECT] Rejeitados pela blacklist: {len(processos_rejeitados)}')
        for proc in sorted(processos_rejeitados)[:3]:
            print(f'[Hydra DETECT]    - {proc}')
    
    if not processos_candidatos:
        print(f'[Hydra DETECT] Nenhum candidato apos blacklist')
        return ''
    
    print(f'[Hydra DETECT] Candidatos apos blacklist: {len(processos_candidatos)}')
    
    # PASSO 4: Validar contra WHITELIST
    print(f'[Hydra DETECT] Validando contra whitelist...')
    processos_validos = [p for p in processos_candidatos if p in whitelist]
    
    if processos_validos:
        jogo_exe = processos_validos[0]
        jogo_nome = jogo_exe.replace('.exe', '').title()
        print(f'[Hydra DETECT] OK JOGO DETECTADO: "{jogo_nome}" (exe: {jogo_exe})')
        return jogo_nome
    
    print(f'[Hydra DETECT] Nenhum processo corresponde a whitelist')
    return ''




def _hydra_local_ativo_real() -> bool:
    """Verifica se Hydra REALMENTE está em execução (SEM CACHE).
    
    Sempre consulta o Windows para estado REAL.
    
    Returns:
        True se Hydra está rodando, False caso contrário
    """
    processos = _hydra_get_running_processes()
    
    # Procura por qualquer processo contendo 'hydra'
    for proc in processos:
        if 'hydra' in proc.lower():
            print(f'[Hydra REAL] Hydra detectado: {proc}')
            return True
    
    print(f'[Hydra REAL] Hydra NÃO está rodando')
    return False


def _hydra_get_full_state_real() -> dict:
    """Retorna ESTADO REAL COMPLETO do Hydra (SEM CACHE).
    
    Este é o ponto central de verdade para o estado do Hydra.
    SEMPRE valida contra o sistema real.
    NUNCA usa dados armazenados.
    
    Returns:
        Dict com {'hydra_ativo': bool, 'jogo': str, 'usuario': str}
    """
    estado = {
        'hydra_ativo': _hydra_local_ativo_real(),
        'jogo': '',
        'usuario': ''
    }
    
    # Se Hydra não está ativo, não precisa procurar jogo
    if not estado['hydra_ativo']:
        return estado
    
    # Hydra está ativo, procura por jogo
    estado['jogo'] = _hydra_detect_running_game_real()
    
    # Tenta obter nome de usuário
    try:
        config_path = os.path.join(HYDRA_APPDATA_DIR, 'config.json')
        if os.path.isfile(config_path):
            with open(config_path, 'r', encoding='utf-8', errors='replace') as f:
                config = json.load(f)
                estado['usuario'] = config.get('userDetails', {}).get('username', '').strip() or config.get('username', '').strip()
    except Exception:
        pass  # Silencioso
    
    return estado


def _hydra_sincronizar_estado_real(user) -> None:
    """Sincroniza estado do usuário com ESTADO REAL do Hydra (SEM CACHE).
    
    SEMPRE valida contra o sistema real.
    Limpa estado inconsistente.
    NUNCA confia em dados armazenados.
    
    Args:
        user: Usuario object
    """
    if not user:
        return
    
    # Valida estado REAL do sistema (SEMPRE!)
    estado_real = _hydra_get_full_state_real()
    agora = datetime.now().isoformat()
    estado_armazenado = getattr(user, 'hydra_current_game', '') or ''
    
    print(f'[Hydra SYNC] {user.email}: Validando estado REAL')
    print(f'[Hydra SYNC]   Hydra ativo: {estado_real["hydra_ativo"]}')
    print(f'[Hydra SYNC]   Jogo real: "{estado_real["jogo"]}"')
    print(f'[Hydra SYNC]   Armazenado: "{estado_armazenado}"')
    
    # Caso 1: Hydra não está rodando
    if not estado_real['hydra_ativo']:
        if estado_armazenado:
            print('[Hydra SYNC] INCONSISTENCIA: Hydra FECHADO mas DB tem status')
            print(f'[Hydra SYNC] 🔧 CORRIGINDO: Limpando')
            user.hydra_current_game = ''
            user.hydra_last_update = agora
            _salvar_usuario_no_banco(user)
        return
    
    # Caso 2: Hydra ativo - verifica se jogo mudou
    if estado_real['jogo'] != estado_armazenado:
        if estado_real['jogo']:
            print(f'[Hydra SYNC] JOGO INICIADO: "{estado_real["jogo"]}"')
        else:
            print(f'[Hydra SYNC] 🛑 JOGO FECHADO')
        
        user.hydra_current_game = estado_real['jogo']
        user.hydra_last_update = agora
        _salvar_usuario_no_banco(user)
        print('[Hydra SYNC] Atualizado')


# Manter para compatibilidade com código antigo
def _hydra_atualizar_status_local(user) -> None:
    """Compatibilidade - redireciona para nova função."""
    _hydra_sincronizar_estado_real(user)


def _hydra_email_conta_usuario(user) -> str:
    return (getattr(user, 'hydra_account_email', '') or '').strip()


def _hydra_usuario_usuario(user) -> str:
    return (getattr(user, 'hydra_usuario', '') or '').strip()


def _hydra_pin_usuario(user) -> str:
    return (getattr(user, 'hydra_pin', '') or '').strip()


def _hydra_token_usuario(user) -> str:
    return (getattr(user, 'hydra_token', '') or '').strip()


def _hydra_fetch_autenticado_json(base_url: str, caminho: str, token: str) -> dict | list:
    return _hydra_fetch_json(
        f'{base_url}{caminho}',
        {'Authorization': f'Bearer {token}'}
    )


def _hydra_ler_duracao_em_segundos(item: dict) -> int:
    for chave in (
        'playTimeInSeconds',
        'playTimeSeconds',
        'playtime_seconds',
        'timePlayedSeconds',
        'secondsPlayed',
        'durationSeconds',
    ):
        valor = item.get(chave)
        if valor not in (None, ''):
            try:
                return max(0, int(float(valor)))
            except (TypeError, ValueError):
                pass

    for chave in (
        'playtime_forever',
        'playTimeInMinutes',
        'playtimeMinutes',
        'timePlayedMinutes',
        'minutesPlayed',
        'durationMinutes',
    ):
        valor = item.get(chave)
        if valor not in (None, ''):
            try:
                return max(0, int(float(valor) * 60))
            except (TypeError, ValueError):
                pass

    return 0


def _hydra_ler_conquistas_item(item: dict) -> tuple[int, int]:
    conquistas = item.get('achievements') or item.get('achievement') or item.get('conquistas')
    desbloqueadas = 0
    total = 0

    if isinstance(conquistas, list):
        total = len(conquistas)
        desbloqueadas = sum(
            1
            for conquista in conquistas
            if isinstance(conquista, dict)
            and bool(
                conquista.get('unlocked')
                or conquista.get('earned')
                or conquista.get('completed')
                or conquista.get('active')
            )
        )
    elif isinstance(conquistas, dict):
        desbloqueadas = int(
            conquistas.get('unlocked')
            or conquistas.get('unlockedCount')
            or conquistas.get('earned')
            or conquistas.get('completed')
            or conquistas.get('progress')
            or 0
        )
        total = int(
            conquistas.get('total')
            or conquistas.get('count')
            or conquistas.get('achievementCount')
            or 0
        )
    else:
        desbloqueadas = int(
            item.get('achievementsUnlocked')
            or item.get('unlockedAchievements')
            or item.get('achievementUnlockedCount')
            or 0
        )
        total = int(
            item.get('achievementsTotal')
            or item.get('totalAchievements')
            or item.get('achievementTotalCount')
            or 0
        )

    if total == 0 and desbloqueadas > 0:
        total = desbloqueadas
    if total and desbloqueadas > total:
        desbloqueadas = total

    return max(0, desbloqueadas), max(0, total)


def _hydra_extrair_jogos_exportados(dados_exportados: dict | list) -> list[dict]:
    if isinstance(dados_exportados, list):
        itens = dados_exportados
    elif isinstance(dados_exportados, dict):
        itens = []
        for chave in ('library', 'games', 'items', 'pinnedGames', 'profileGames'):
            valor = dados_exportados.get(chave)
            if isinstance(valor, list):
                itens.extend(valor)

        if not itens:
            for chave in ('data', 'result', 'results'):
                valor = dados_exportados.get(chave)
                if isinstance(valor, list):
                    itens.extend(valor)
                elif isinstance(valor, dict):
                    for chave_interna in ('library', 'games', 'items', 'pinnedGames'):
                        valor_interno = valor.get(chave_interna)
                        if isinstance(valor_interno, list):
                            itens.extend(valor_interno)
    else:
        return []

    jogos = []
    for indice, item in enumerate(itens, start=1):
        if not isinstance(item, dict):
            continue

        titulo = (
            item.get('title')
            or item.get('name')
            or item.get('gameTitle')
            or item.get('gameName')
            or item.get('appName')
            or ''
        ).strip()
        if not titulo:
            continue

        codigo_origem = str(
            item.get('id')
            or item.get('gameId')
            or item.get('appid')
            or item.get('slug')
            or titulo
        ).strip().lower()
        play_seconds = _hydra_ler_duracao_em_segundos(item)
        conquistas_desbloqueadas, conquistas_total = _hydra_ler_conquistas_item(item)

        jogos.append({
            'titulo': titulo,
            'codigo_origem': codigo_origem or f'hydra-{indice}',
            'play_seconds': play_seconds,
            'conquistas_desbloqueadas': conquistas_desbloqueadas,
            'conquistas_total': conquistas_total,
        })

    return jogos


def _hydra_contexto_local(user) -> dict:
    jogos = []
    capas_usadas: set[str] = set()
    conquistas_desbloqueadas_total = 0
    conquistas_total = 0

    for item in GerenciadorBiblioteca.obter_biblioteca(user.email):
        if (getattr(item, 'origem', '') or '').lower() != 'hydra':
            continue

        jogo = JOGOS_DB.get(item.jogo_id)
        if not jogo:
            continue

        desbloqueadas = int(getattr(item, 'conquistas_desbloqueadas', 0) or 0)
        total_item = int(getattr(item, 'conquistas_total', 0) or 0)
        conquistas_desbloqueadas_total += desbloqueadas
        conquistas_total += total_item

        jogos.append({
            'appid': jogo.id,
            'name': jogo.titulo,
            'title': jogo.titulo,
            'playTimeInSeconds': int(getattr(item, 'tempo_jogado_horas', 0) or 0) * 3600,
            'shop': 'hydra',
            'cover_url': _capa_unica_para_lista(jogo.titulo, jogo.ano, capas_usadas),
            'achievements_unlocked': desbloqueadas,
            'achievements_total': total_item,
        })

    if not jogos:
        return {
            'configurado': False,
            'erro': 'Importe uma exportação local da Hydra para exibir sua biblioteca aqui.',
            'jogos': [],
            'jogos_totais': 0,
            'usuario': None,
            'perfil_url': None,
            'base_url': None,
            'email_conta': _hydra_email_conta_usuario(user),
            'hydra_usuario': _hydra_usuario_usuario(user),
            'hydra_pin': _hydra_pin_usuario(user),
            'origem': 'importacao_local',
        }

    return {
        'configurado': True,
        'erro': None,
        'jogos': jogos,
        'jogos_totais': len(jogos),
        'usuario': {'displayName': user.nome, 'email': user.email},
        'perfil_url': None,
        'base_url': None,
        'email_conta': _hydra_email_conta_usuario(user),
        'hydra_usuario': _hydra_usuario_usuario(user),
        'hydra_pin': _hydra_pin_usuario(user),
        'origem': 'importacao_local',
        'conquistas': {
            'unlocked': conquistas_desbloqueadas_total,
            'total': conquistas_total,
            'percent': round((conquistas_desbloqueadas_total / conquistas_total) * 100) if conquistas_total else 0,
        },
    }


def importar_hydra_para_biblioteca_local(meu_email: str, exportacao_json: str) -> tuple[int, int, str | None]:
    user = USUARIOS_DB.get(meu_email)
    if not user:
        return 0, 0, 'Usuário não encontrado.'

    try:
        dados_exportados = json.loads(exportacao_json)
    except json.JSONDecodeError:
        return 0, 0, 'A exportação Hydra precisa estar em JSON válido.'

    jogos_exportados = _hydra_extrair_jogos_exportados(dados_exportados)
    if not jogos_exportados:
        return 0, 0, 'Nenhum jogo foi encontrado nessa exportação Hydra.'

    jogos_importados = 0
    jogos_ja_existiam = 0

    for jogo_exportado in jogos_exportados:
        titulo = jogo_exportado['titulo']
        codigo_origem = jogo_exportado['codigo_origem']

        item_existente = next(
            (
                item
                for item in GerenciadorBiblioteca.obter_biblioteca(meu_email)
                if (getattr(item, 'origem', '') or '').lower() == 'hydra'
                and (getattr(item, 'codigo_origem', '') or '') == codigo_origem
            ),
            None,
        )
        if item_existente:
            jogos_ja_existiam += 1
            continue

        jogo_catalogo = next(
            (
                jogo
                for jogo in JOGOS_DB.values()
                if jogo.titulo.strip().lower() == titulo.strip().lower()
                and jogo.desenvolvedora.lower() == 'hydra'
            ),
            None,
        )
        if not jogo_catalogo:
            novo_id_jogo = max(JOGOS_DB.keys(), default=0) + 1
            jogo_catalogo = Jogo(novo_id_jogo, titulo, 'Hydra', 'Hydra', datetime.now().year)
            try:
                jogo_catalogo.associar_categoria(_obter_ou_criar_categoria('Hydra'))
            except Exception:
                pass
            JOGOS_DB[novo_id_jogo] = jogo_catalogo
            persistir_jogo(jogo_catalogo, getattr(jogo_catalogo, '_categorias', []))

        novo_id_biblioteca = max([b.id for b in BIBLIOTECA_DB.values()], default=0) + 1
        item = GerenciadorBiblioteca.adicionar_jogo(novo_id_biblioteca, meu_email, jogo_catalogo.id, origem='hydra', launcher='hydra')
        item.codigo_origem = codigo_origem
        item.tempo_jogado_horas = int(round((jogo_exportado['play_seconds'] or 0) / 3600))
        item.conquistas_desbloqueadas = int(jogo_exportado['conquistas_desbloqueadas'] or 0)
        item.conquistas_total = int(jogo_exportado['conquistas_total'] or 0)
        persistir_biblioteca_item(item)
        jogos_importados += 1

    if jogos_importados:
        return jogos_importados, jogos_ja_existiam, None

    return 0, jogos_ja_existiam, 'Nenhum jogo novo foi importado da exportação Hydra.'


def _hydra_importar_contexto_para_biblioteca_local(user, hydra_contexto: dict) -> tuple[int, int]:
    jogos = hydra_contexto.get('jogos') or []
    jogos_importados = 0
    jogos_ja_existiam = 0

    for jogo_hydra in jogos:
        if not isinstance(jogo_hydra, dict):
            continue

        titulo = (jogo_hydra.get('title') or jogo_hydra.get('name') or '').strip()
        if not titulo:
            continue

        codigo_origem = str(jogo_hydra.get('objectId') or jogo_hydra.get('object_id') or jogo_hydra.get('id') or titulo).strip().lower()

        item_existente = next(
            (
                item
                for item in GerenciadorBiblioteca.obter_biblioteca(user.email)
                if (getattr(item, 'origem', '') or '').lower() == 'hydra'
                and (getattr(item, 'codigo_origem', '') or '') == codigo_origem
            ),
            None,
        )
        if item_existente:
            jogos_ja_existiam += 1
            continue

        jogo_catalogo = next(
            (
                jogo
                for jogo in JOGOS_DB.values()
                if jogo.titulo.strip().lower() == titulo.strip().lower()
                and jogo.desenvolvedora.lower() == 'hydra'
            ),
            None,
        )
        if not jogo_catalogo:
            novo_id_jogo = max(JOGOS_DB.keys(), default=0) + 1
            jogo_catalogo = Jogo(novo_id_jogo, titulo, 'Hydra', 'Hydra', datetime.now().year)
            try:
                jogo_catalogo.associar_categoria(_obter_ou_criar_categoria('Hydra'))
            except Exception:
                pass
            JOGOS_DB[novo_id_jogo] = jogo_catalogo
            persistir_jogo(jogo_catalogo, getattr(jogo_catalogo, '_categorias', []))

        chave_biblioteca = f'{user.email}_{jogo_catalogo.id}'
        item = BIBLIOTECA_DB.get(chave_biblioteca)
        if item is None:
            novo_id_biblioteca = max([b.id for b in BIBLIOTECA_DB.values()], default=0) + 1
            item = GerenciadorBiblioteca.adicionar_jogo(novo_id_biblioteca, user.email, jogo_catalogo.id, origem='hydra', launcher='hydra')
        item.origem = 'hydra'
        item.launcher = 'hydra'
        item.codigo_origem = codigo_origem
        item.cover_url = (jogo_hydra.get('cover_url') or jogo_hydra.get('libraryImageUrl') or jogo_hydra.get('iconUrl') or '')
        item.tempo_jogado_horas = int(round((jogo_hydra.get('playTimeInSeconds') or 0) / 3600))
        item.conquistas_desbloqueadas = int(jogo_hydra.get('achievements_unlocked') or 0)
        item.conquistas_total = int(jogo_hydra.get('achievements_total') or 0)
        persistir_biblioteca_item(item)
        jogos_importados += 1

    return jogos_importados, jogos_ja_existiam


def _hydra_normalizar_capa(jogo: dict) -> str:
    candidatos = [
        jogo.get('cover_url'),
        jogo.get('coverUrl'),
        jogo.get('heroImageUrl'),
        jogo.get('backgroundImageUrl'),
    ]
    for candidato in candidatos:
        if _usar_capa_armazenada(candidato, 'hydra'):
            return candidato
    return _capa_fallback(jogo.get('title') or jogo.get('name') or 'Jogo')


def _hydra_normalizar_jogos(jogos: list[dict]) -> list[dict]:
    resultados = []
    vistos = set()

    for jogo in jogos or []:
        if not isinstance(jogo, dict):
            continue

        object_id = str(jogo.get('objectId') or jogo.get('object_id') or jogo.get('id') or '').strip()
        titulo = (jogo.get('title') or jogo.get('name') or jogo.get('displayName') or object_id or 'Jogo').strip()
        if not object_id:
            object_id = titulo

        if object_id in vistos:
            continue
        vistos.add(object_id)

        tempo_jogado = int(jogo.get('playTimeInSeconds') or jogo.get('playtimeInSeconds') or jogo.get('play_time_in_seconds') or 0)

        resultados.append({
            'objectId': object_id,
            'shop': (jogo.get('shop') or 'hydra').strip() if isinstance(jogo.get('shop'), str) else 'hydra',
            'title': titulo,
            'playTimeInSeconds': tempo_jogado,
            'cover_url': _hydra_normalizar_capa(jogo),
            'isPinned': bool(jogo.get('isPinned')),
            'isFavorite': bool(jogo.get('isFavorite')),
        })

    resultados.sort(key=lambda item: item.get('playTimeInSeconds') or 0, reverse=True)
    return resultados


def montar_hydra_contexto(user) -> dict:
    base_url = DEFAULT_HYDRA_API_BASE_URL
    hydra_usuario = _hydra_usuario_usuario(user)
    hydra_pin = _hydra_pin_usuario(user)
    hydra_token = _hydra_token_usuario(user)
    hydra_email_conta = _hydra_email_conta_usuario(user)
    contexto_local = _hydra_contexto_local(user)

    if contexto_local.get('configurado'):
        return contexto_local

    if hydra_token:
        try:
            perfil = _hydra_fetch_autenticado_json(base_url, '/profile/me', hydra_token)
        except Exception:
            if contexto_local.get('configurado'):
                return contexto_local
            return {
                'configurado': False,
                'erro': 'O token Hydra informado parece inválido ou expirado.',
                'jogos': [],
                'jogos_totais': 0,
                'usuario': None,
                'perfil_url': None,
                'base_url': base_url,
                'email_conta': hydra_email_conta,
                'hydra_usuario': hydra_usuario,
                'hydra_pin': hydra_pin,
            }

        try:
            biblioteca = _hydra_fetch_autenticado_json(
                base_url,
                '/profile/games?take=18&skip=0&sortBy=playedRecently',
                hydra_token,
            )
        except Exception:
            if contexto_local.get('configurado'):
                return contexto_local
            return {
                'configurado': True,
                'erro': 'Não foi possível carregar a biblioteca autenticada da Hydra.',
                'jogos': [],
                'jogos_totais': 0,
                'usuario': perfil if isinstance(perfil, dict) else None,
                'perfil_url': f"{base_url}/users/{(perfil or {}).get('id')}" if isinstance(perfil, dict) and (perfil or {}).get('id') else None,
                'base_url': base_url,
                'email_conta': hydra_email_conta,
                'hydra_usuario': hydra_usuario,
                'hydra_pin': hydra_pin,
            }

        if isinstance(biblioteca, dict):
            jogos = list(
                biblioteca.get('library')
                or biblioteca.get('games')
                or biblioteca.get('items')
                or []
            )
            total = int(biblioteca.get('totalCount') or biblioteca.get('count') or len(jogos))
        else:
            jogos = list(biblioteca or [])
            total = len(jogos)

        jogos_normalizados = _hydra_normalizar_jogos(jogos)

        return {
            'configurado': True,
            'erro': None,
            'jogos': jogos_normalizados[:8],
            'jogos_totais': total,
            'usuario': perfil if isinstance(perfil, dict) else None,
            'perfil_url': f"{base_url}/users/{perfil.get('id')}" if isinstance(perfil, dict) and perfil.get('id') else None,
            'base_url': base_url,
            'email_conta': hydra_email_conta,
            'hydra_usuario': hydra_usuario,
            'hydra_pin': hydra_pin,
        }

    return {
        'configurado': contexto_local.get('configurado', False),
        'erro': contexto_local.get('erro') or 'A Hydra não oferece API pública para integração nativa. Importe uma exportação local em JSON para exibir a biblioteca.',
        'jogos': contexto_local.get('jogos', []),
        'jogos_totais': contexto_local.get('jogos_totais', 0),
        'usuario': contexto_local.get('usuario'),
        'perfil_url': contexto_local.get('perfil_url'),
        'base_url': contexto_local.get('base_url'),
        'email_conta': hydra_email_conta,
        'hydra_usuario': hydra_usuario,
        'hydra_pin': hydra_pin,
        'origem': contexto_local.get('origem', 'importacao_local'),
        'conquistas': contexto_local.get('conquistas'),
    }

    try:
        perfil = _hydra_fetch_json(perfil_url)
    except Exception:
        perfil = {}

    try:
        biblioteca = _hydra_fetch_json(biblioteca_url)
    except Exception as exc:
        return {
            'configurado': True,
            'erro': 'Não foi possível carregar a biblioteca Hydra. Verifique o ID/URL do perfil e a base da API.',
            'jogos': [],
            'jogos_totais': 0,
            'usuario': perfil if isinstance(perfil, dict) else None,
            'perfil_url': perfil_url,
            'base_url': base_url,
            'email_conta': hydra_email_conta,
        }

    if isinstance(biblioteca, dict):
        jogos = list(biblioteca.get('pinnedGames') or []) + list(biblioteca.get('library') or [])
        total = int(biblioteca.get('totalCount') or biblioteca.get('count') or len(jogos))
    else:
        jogos = list(biblioteca or [])
        total = len(jogos)

    jogos_normalizados = _hydra_normalizar_jogos(jogos)

    return {
        'configurado': True,
        'erro': None,
        'jogos': jogos_normalizados[:8],
        'jogos_totais': total,
        'usuario': perfil if isinstance(perfil, dict) else None,
        'perfil_url': perfil_url,
        'base_url': base_url,
        'email_conta': hydra_email_conta,
            'hydra_usuario': hydra_usuario,
            'hydra_pin': hydra_pin,
    }


def _steam_resposta_indica_login_ou_bloqueio(texto: str) -> bool:
    if not texto:
        return False

    texto_normalizado = texto.lower()
    sinais = [
        'iniciar sessão',
        'sign in',
        'login',
        'steam guard',
        'captcha',
        'please wait',
        'temporarily unavailable',
        'too many requests',
        'access denied',
        'verify your account',
        'to continue',
    ]

    if '<gameslist>' in texto_normalizado or '<gameslist' in texto_normalizado:
        return False

    return any(sinal in texto_normalizado for sinal in sinais)


def _deduplicar_jogos_steam(jogos: list) -> list:
    if not jogos:
        return []

    jogos_unicos = {}
    for jogo in jogos:
        appid = int(jogo.get('appid') or 0)
        if not appid:
            continue

        atual = jogos_unicos.get(appid)
        if not atual or int(jogo.get('playtime_forever') or 0) > int(atual.get('playtime_forever') or 0):
            jogos_unicos[appid] = jogo

    resultado = list(jogos_unicos.values())
    resultado.sort(key=lambda item: int(item.get('playtime_forever') or 0), reverse=True)
    return resultado


def _steam_fetch_public_games_paginated(steam_id64: str, api_key: str = '', page_size: int = 200, force_refresh: bool = False) -> list[dict]:
    """Compatibilidade: usa a API oficial e os manifests locais da Steam em vez do scraping da página pública."""
    if not steam_id64:
        log_fetch_xml_erro(steam_id64, 0, "SteamID64 vazio")
        return []

    api_key = (api_key or os.environ.get('STEAM_API_KEY') or '').strip()
    try:
        jogos_api = obter_jogos(steam_id64, api_key, force_refresh=force_refresh)
    except Exception as exc:
        log_fetch_xml_erro(steam_id64, 0, str(exc))
        return []

    resultado = []
    for jogo in jogos_api:
        appid = int(jogo.get('appid') or 0)
        if not appid:
            continue
        resultado.append({
            'appid': appid,
            'name': jogo.get('name') or f'App {appid}',
            'playtime_forever': int(jogo.get('playtime_forever') or 0),
            'cover_url': jogo.get('cover_url') or f'https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg',
        })

    resultado = _deduplicar_jogos_steam(resultado)
    log_bibliotecas_obtidas(steam_id64, 'api_official', len(resultado))
    return resultado


def _steam_fetch_json(url: str) -> dict:
    # User-Agent mais realista para evitar bloqueios
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    ]
    import random
    user_agent = random.choice(user_agents)
    
    request = Request(
        url,
        headers={
            'User-Agent': user_agent,
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://steamcommunity.com/',
        },
    )
    try:
        with urlopen(request, timeout=15) as resposta:
            http_code = resposta.getcode()
            if http_code != 200:
                raise Exception(f"HTTP {http_code}")
            return json.loads(resposta.read().decode('utf-8', errors='replace'))
    except Exception as e:
        raise Exception(f"Erro ao buscar JSON: {str(e)}")


def _steam_fetch_text(url: str) -> str:
    # User-Agent mais realista para evitar bloqueios
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    ]
    import random
    user_agent = random.choice(user_agents)
    
    request = Request(
        url,
        headers={
            'User-Agent': user_agent,
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept': '*/*',
            'Referer': 'https://steamcommunity.com/',
        },
    )
    try:
        with urlopen(request, timeout=15) as resposta:
            http_code = resposta.getcode()
            if http_code != 200:
                raise Exception(f"HTTP {http_code}")
            conteudo = resposta.read()
            # Tenta UTF-8 primeiro, depois latin-1 se falhar
            try:
                return conteudo.decode('utf-8')
            except UnicodeDecodeError:
                return conteudo.decode('latin-1', errors='replace')
    except Exception as e:
        raise Exception(f"Erro ao buscar texto: {str(e)}")


def _steam_post_text(url: str, dados: dict) -> str:
    payload = urlencode(dados).encode('utf-8')
    request = Request(
        url,
        data=payload,
        headers={
            'User-Agent': 'GameUnexa/1.0',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        },
    )
    with urlopen(request, timeout=8) as resposta:
        return resposta.read().decode('utf-8', errors='replace')


def _steam_extrair_steamid_de_claimed_id(claimed_id: str) -> str | None:
    correspondencia = re.search(r'/openid/id/(\d{17})$', claimed_id or '')
    if correspondencia:
        return correspondencia.group(1)
    correspondencia = re.search(r'(\d{17})', claimed_id or '')
    return correspondencia.group(1) if correspondencia else None


def _steam_build_openid_url(return_to: str, realm: str) -> str:
    parametros = {
        'openid.ns': 'http://specs.openid.net/auth/2.0',
        'openid.mode': 'checkid_setup',
        'openid.return_to': return_to,
        'openid.realm': realm,
        'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
    }
    return 'https://steamcommunity.com/openid/login?' + urlencode(parametros)


def _steam_verificar_resposta_openid(dados: dict) -> bool:
    parametros = {
        chave: valor for chave, valor in dados.items()
        if chave.startswith('openid.')
    }
    parametros['openid.mode'] = 'check_authentication'
    resposta = _steam_post_text('https://steamcommunity.com/openid/login', parametros)
    return 'is_valid:true' in resposta.replace(' ', '').lower()


def _steam_resolver_steamid(steam_id_ou_vanity: str, api_key: str) -> str | None:
    texto = (steam_id_ou_vanity or '').strip()
    if not texto:
        return None

    correspondencia = re.search(r'\b(\d{17})\b', texto)
    if correspondencia:
        return correspondencia.group(1)

    if '/profiles/' in texto:
        correspondencia = re.search(r'/profiles/(\d{17})', texto)
        if correspondencia:
            return correspondencia.group(1)

    vanity = texto
    if texto.startswith('http'):
        parsed = urlparse(texto)
        if '/id/' in parsed.path:
            vanity = parsed.path.split('/id/', 1)[1].strip('/')
        elif '/profiles/' in parsed.path:
            correspondencia = re.search(r'/profiles/(\d{17})', parsed.path)
            if correspondencia:
                return correspondencia.group(1)
            vanity = parsed.path.strip('/')
        else:
            vanity = parsed.path.strip('/') or texto
    elif '/id/' in texto:
        vanity = texto.split('/id/', 1)[1].strip('/')

    if not api_key or not vanity:
        return None

    url = (
        'https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?'
        f'key={quote(api_key)}&vanityurl={quote(vanity)}'
    )
    dados = _steam_fetch_json(url)
    response = dados.get('response', {}) or {}
    if response.get('success') == 1:
        return response.get('steamid')
    return None


def _steam_owned_games(steam_id64: str, api_key: str) -> list:
    url = (
        'https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?'
        f'key={quote(api_key)}&steamid={quote(steam_id64)}'
        '&include_appinfo=1&include_played_free_games=1&format=json'
    )
    try:
        dados = _steam_fetch_json(url)
    except Exception:
        return []

    jogos = dados.get('response', {}).get('games', []) or []
    resultado = []
    for jogo in jogos:
        appid = jogo.get('appid')
        if not appid:
            continue
        resultado.append({
            'appid': appid,
            'name': jogo.get('name') or f'App {appid}',
            'playtime_forever': int(jogo.get('playtime_forever') or 0),
            'cover_url': f'https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg',
        })

    return _deduplicar_jogos_steam(resultado)


def _steam_most_played_games_publico(steam_id64: str) -> list:
    """Fallback compatível: usa a API oficial da Steam e os manifests locais quando não há perfil público."""
    if not steam_id64:
        return []

    api_key = os.environ.get('STEAM_API_KEY', '').strip()
    try:
        jogos = unificar_biblioteca(steam_id64, api_key)
    except Exception:
        return []

    resultado = []
    for jogo in jogos:
        appid = int(jogo.get('appid') or 0)
        if not appid:
            continue
        resultado.append({
            'appid': appid,
            'name': jogo.get('name') or f'App {appid}',
            'playtime_forever': int(jogo.get('playtime_forever') or 0),
            'cover_url': jogo.get('cover_url') or f'https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg',
        })

    resultado_final = _deduplicar_jogos_steam(resultado)
    log_bibliotecas_obtidas(steam_id64, 'most_played_api', len(resultado_final))
    return resultado_final


def _steam_obter_biblioteca_publica_completa(steam_id64: str, api_key: str = '', force_refresh: bool = False) -> list[dict]:
    if not steam_id64:
        log_bibliotecas_obtidas(steam_id64, 'nenhuma', 0)
        return []

    jogos = _steam_fetch_public_games_paginated(steam_id64, api_key=api_key, force_refresh=force_refresh)

    if not jogos:
        log_bibliotecas_obtidas(steam_id64, 'vazia', 0)

    return jogos


def _steam_achievements_jogo(steam_id64: str, api_key: str, appid: int) -> dict | None:
    if not appid:
        return None

    url_player = (
        'https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/?'
        f'key={quote(api_key)}&steamid={quote(steam_id64)}&appid={appid}&l=pt-BR'
    )
    url_schema = (
        'https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/?'
        f'key={quote(api_key)}&appid={appid}&l=pt-BR'
    )

    try:
        dados_player = _steam_fetch_json(url_player)
        dados_schema = _steam_fetch_json(url_schema)
    except Exception:
        return None

    playerstats = dados_player.get('playerstats', {}) or {}
    schema_stats = (dados_schema.get('game', {}) or {}).get('availableGameStats', {}) or {}
    schema_achievements = schema_stats.get('achievements', []) or []
    player_achievements = {item.get('apiname'): item for item in playerstats.get('achievements', []) or []}

    conquistas = []
    for conquista in schema_achievements:
        apiname = conquista.get('name')
        player_item = player_achievements.get(apiname, {})
        unlocked = bool(player_item.get('achieved'))
        conquistas.append({
            'apiname': apiname,
            'title': conquista.get('displayName') or apiname or 'Conquista',
            'description': conquista.get('description') or '',
            'icon': conquista.get('icon') if unlocked else conquista.get('icongray') or conquista.get('icon'),
            'unlocked': unlocked,
            'unlock_time': player_item.get('unlocktime'),
        })

    total = len(conquistas)
    unlocked_total = sum(1 for conquista in conquistas if conquista['unlocked'])

    return {
        'appid': appid,
        'total': total,
        'unlocked': unlocked_total,
        'percent': round((unlocked_total / total) * 100, 1) if total else 0,
        'achievements': conquistas,
    }


@lru_cache(maxsize=256)
def _steam_achievements_publico(steam_id64: str, appid: int) -> dict | None:
    if not steam_id64 or not appid:
        return None

    url = f'https://steamcommunity.com/profiles/{steam_id64}/stats/{appid}/?tab=achievements'

    try:
        html = _buscar_html_com_user_agent(url, timeout=8)
    except Exception:
        return None

    resumo = re.search(r'(\d+)\s+of\s+(\d+)\s+\((\d+)%\)\s+achievements earned', html, re.I)
    unlocked_total = int(resumo.group(1)) if resumo else 0
    total = int(resumo.group(2)) if resumo else 0
    percent = float(resumo.group(3)) if resumo else 0

    class _ParserConquistasPublicas(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.conquistas = []
            self._em_conquista = False
            self._profundidade_div = 0
            self._campo_atual = None
            self._buffer_campo = []
            self._conquista_atual = {}

        def handle_starttag(self, tag, attrs):
            atributos = dict(attrs)
            classes = (atributos.get('class', '') or '').split()

            if tag == 'div' and 'achieveRow' in classes:
                self._em_conquista = True
                self._profundidade_div = 1
                self._campo_atual = None
                self._buffer_campo = []
                self._conquista_atual = {'apiname': None, 'title': '', 'description': '', 'icon': '', 'unlocked': False, 'unlock_time': ''}
                return

            if not self._em_conquista:
                return

            if tag == 'div':
                self._profundidade_div += 1
                if 'achieveUnlockTime' in classes:
                    self._campo_atual = 'unlock_time'
                    self._buffer_campo = []
                return

            if tag == 'img' and not self._conquista_atual.get('icon'):
                self._conquista_atual['icon'] = atributos.get('src', '')
                return

            if tag == 'h3' and 'ellipsis' in classes:
                self._campo_atual = 'title'
                self._buffer_campo = []
                return

            if tag == 'h5':
                self._campo_atual = 'description'
                self._buffer_campo = []

        def handle_endtag(self, tag):
            if not self._em_conquista:
                return

            if self._campo_atual in {'title', 'description', 'unlock_time'} and tag in {'h3', 'h5', 'div'}:
                texto = unescape(''.join(self._buffer_campo)).strip()
                if self._campo_atual == 'unlock_time':
                    self._conquista_atual['unlock_time'] = texto
                    self._conquista_atual['unlocked'] = bool(texto)
                else:
                    self._conquista_atual[self._campo_atual] = texto
                self._campo_atual = None
                self._buffer_campo = []

            if tag == 'div':
                self._profundidade_div -= 1
                if self._profundidade_div <= 0:
                    titulo_limpo = self._conquista_atual.get('title', '').strip() or 'Conquista'
                    descricao_limpa = self._conquista_atual.get('description', '').strip()
                    desbloqueio_limpo = self._conquista_atual.get('unlock_time', '').strip()
                    imagem = self._conquista_atual.get('icon', '')
                    if imagem or titulo_limpo != 'Conquista' or descricao_limpa or desbloqueio_limpo:
                        self.conquistas.append({
                            'apiname': None,
                            'title': titulo_limpo,
                            'description': descricao_limpa,
                            'icon': imagem,
                            'unlocked': bool(desbloqueio_limpo),
                            'unlock_time': desbloqueio_limpo,
                        })
                    self._em_conquista = False
                    self._campo_atual = None
                    self._buffer_campo = []
                    self._conquista_atual = {}

        def handle_data(self, data):
            if self._em_conquista and self._campo_atual:
                self._buffer_campo.append(data)

    parser = _ParserConquistasPublicas()
    parser.feed(html)
    conquistas = parser.conquistas

    if not conquistas:
        return None

    if not total:
        total = len(conquistas)
    if not unlocked_total:
        unlocked_total = len([conquista for conquista in conquistas if conquista['unlocked']])
    if not percent and total:
        percent = round((unlocked_total / total) * 100, 1)

    return {
        'appid': appid,
        'total': total,
        'unlocked': unlocked_total,
        'percent': percent,
        'achievements': conquistas,
        'source': 'steam_publico',
    }


def _buscar_status_steam_usuario(steam_id64: str, api_key: str = '', force_refresh: bool = False) -> dict:
    """
    Busca o status atual do usuário na Steam usando a Web API.
    Steam personastate: 0=offline, 1=online, 2=busy, 3=away, 4=snooze, 5=looking to trade, 6=looking to play
    Retorna um dicionário com as informações de status.
    """
    if not steam_id64:
        return {'online': False, 'game': '', 'appid': None}

    try:
        # Tenta primeiro via API Web (mais confiável)
        api_key = (api_key or os.environ.get('STEAM_API_KEY', '')).strip()
        
        if api_key:
            # Usar a API Web oficial da Steam
            # Adiciona timestamp para force refresh (cache busting)
            timestamp = f'&_t={int(time.time())}' if force_refresh else ''
            url = (
                'https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?'
                f'key={quote(api_key)}&steamids={quote(steam_id64)}&format=json{timestamp}'
            )
            try:
                dados = _steam_fetch_json(url)
                players = dados.get('response', {}).get('players', [])
                
                if players:
                    player = players[0]
                    personastate = int(player.get('personastate', 0) or 0)
                    # Qualquer estado diferente de 0 é online ou visível de alguma forma
                    is_online = personastate != 0
                    
                    # Tenta múltiplas fontes para o nome do jogo (ordem de preferência)
                    current_game = (player.get('gameextrainfo') or '').strip()
                    raw_appid = player.get('gameid')
                    appid = None

                    # Se não tiver gameextrainfo, tenta outros campos
                    if not current_game:
                        current_game = (player.get('gamename') or '').strip()

                    if not current_game:
                        state_msg = (player.get('stateMessage') or '').strip()
                        if state_msg:
                            state_lower = state_msg.lower()
                            for prefix in ['playing ', 'jogando ', 'in-game ', 'in game ', 'em jogo '] :
                                if state_lower.startswith(prefix):
                                    current_game = state_msg[len(prefix):].strip()
                                    break

                            if not current_game:
                                current_game = state_msg

                    # Evita estados genéricos exibidos como jogos
                    if current_game:
                        generic_statuses = {
                            'online', 'offline', 'away', 'busy', 'snooze',
                            'looking to trade', 'looking to play', 'in-game', 'in game',
                            'playing', 'jogando', 'em jogo'
                        }
                        if current_game.lower() in generic_statuses:
                            current_game = ''

                    # Extrai appid quando não houver nome do jogo disponível
                    if raw_appid:
                        try:
                            appid = int(raw_appid)
                            if not current_game and appid > 0 and personastate != 0:
                                current_game = f'[Jogo {appid}]'
                        except (ValueError, TypeError):
                            appid = None

                    resultado = {
                        'online': is_online,
                        'game': current_game or '',
                        'appid': appid,
                    }
                    print(f'[Steam API] {steam_id64}: online={is_online}, game="{current_game}", appid={appid}, raw_response_keys={list(player.keys())}')
                    return resultado
            except Exception as e:
                print(f'[Steam API] Erro: {str(e)}')
                # Fallback para XML se a API falhar
        
        # Fallback: usar XML do perfil público com cache busting
        print(f'[Steam XML] Tentando XML de {steam_id64}')
        timestamp = f'&_t={int(time.time())}' if force_refresh else ''
        if steam_id64.isdigit():
            url = f'https://steamcommunity.com/profiles/{steam_id64}/?xml=1{timestamp}'
        else:
            url = f'https://steamcommunity.com/id/{quote(steam_id64)}/?xml=1{timestamp}'
        xml_texto = _steam_fetch_text(url)
        
        if not xml_texto or len(xml_texto) < 100:
            print(f'[Steam XML] Resposta vazia')
            return {'online': False, 'game': '', 'appid': None}
        
        raiz = ET.fromstring(xml_texto)

        # Busca o status online
        online_state = (raiz.findtext('onlineState') or 'offline').strip().lower()
        is_online = online_state != 'offline'

        # Busca o jogo
        current_game = (raiz.findtext('gameExtraInfo') or '').strip() or (raiz.findtext('gameFriendlyName') or '').strip() or (raiz.findtext('gameName') or '').strip()
        if not current_game:
            state_msg = (raiz.findtext('stateMessage') or '').strip()
            if state_msg:
                state_lower = state_msg.lower().strip()
                prefixes = ['playing ', 'jogando ', 'in-game ', 'in game ', 'em jogo ']
                for prefix in prefixes:
                    if state_lower.startswith(prefix):
                        current_game = state_msg[len(prefix):].strip()
                        break

                if not current_game:
                    current_game = state_msg

                # Evita estados genéricos como "online", "offline", "away", "busy" etc.
                generic_statuses = {
                    'online', 'offline', 'away', 'busy', 'snooze',
                    'looking to trade', 'looking to play', 'in-game', 'in game',
                    'playing', 'jogando', 'em jogo'
                }
                if current_game and current_game.lower() in generic_statuses:
                    current_game = ''

        # Se estiver online e não tiver jogo, ainda permanece online
        if not current_game and is_online:
            current_game = ''

        # Extrai appid se houver jogo
        appid = None
        if current_game:
            game_link = (raiz.findtext('gameLink') or '').strip()
            m = re.search(r'/app/(\d+)', game_link)
            if m:
                appid = int(m.group(1))

        resultado = {
            'online': is_online,
            'game': current_game or '',
            'appid': appid,
        }
        print(f'[Steam XML] {steam_id64}: {resultado}')
        return resultado
        
    except Exception as e:
        print(f'[Steam] Erro: {str(e)}')
        return {'online': False, 'game': '', 'appid': None}


def sincronizar_status_steam(user_email: str) -> None:
    """
    Sincroniza o status atual da Steam do usuário com o banco de dados.
    """
    meu_email = _normalizar_email(user_email)
    user = USUARIOS_DB.get(meu_email)

    if not user:
        return

    steam_id = _steam_id_ou_vanity_usuario(user)
    api_key = _steam_api_key_usuario(user)

    if steam_id and not steam_id.isdigit():
        steam_id = _steam_resolver_steamid(steam_id, api_key) or steam_id

    if not steam_id:
        return

    try:
        perfil = obter_perfil(steam_id, api_key)
        status = obter_status(steam_id, api_key)
    except Exception as exc:
        print(f'[Sincronizar Steam] Erro oficial para {user.email}: {exc}')
        user.steam_online = False
        user.steam_current_game = ''
        user.steam_current_game_appid = None
        user.steam_last_update = datetime.now().isoformat()
        _salvar_usuario_no_banco(user)
        return

    user.steam_online = bool(status.get('online'))
    user.steam_current_game = status.get('game') or ''
    user.steam_current_game_appid = status.get('appid') if status.get('game') else None
    user.steam_last_update = datetime.now().isoformat()
    if perfil.get('avatar'):
        user.foto_perfil = perfil.get('avatar', '')

    _salvar_usuario_no_banco(user)

    print(f'[Sincronizar Steam] {user.email}: online={user.steam_online}, game="{user.steam_current_game}", appid={user.steam_current_game_appid}')


def sincronizar_steam_oficial(user_email: str) -> dict:
    """Sincronização explícita usando a integração oficial da Steam."""
    meu_email = _normalizar_email(user_email)
    user = USUARIOS_DB.get(meu_email)
    if not user:
        return {'sincronizado': False, 'erro': 'Usuário não encontrado'}

    steam_id64 = (getattr(user, 'steam_id64', '') or '').strip()
    api_key = (getattr(user, 'steam_api_key', '') or '').strip()

    if not steam_id64:
        return {'sincronizado': False, 'erro': 'SteamID64 não configurado'}

    perfil = obter_perfil(steam_id64, api_key)
    status = obter_status(steam_id64, api_key)
    jogos = unificar_biblioteca(steam_id64, api_key)

    user.steam_online = bool(status.get('online'))
    user.steam_current_game = status.get('game') or ''
    user.steam_current_game_appid = status.get('appid') if status.get('game') else None
    user.steam_last_update = datetime.now().isoformat()
    user.foto_perfil = perfil.get('avatar') or user.foto_perfil or ''
    _salvar_usuario_no_banco(user)

    importar_steam_para_biblioteca_local(meu_email)

    return {
        'sincronizado': True,
        'steam_id64': steam_id64,
        'perfil': perfil,
        'status': status,
        'jogos': jogos[:8],
        'jogos_total': len(jogos),
    }


def montar_steam_contexto(user, steam_appid: int | None = None, force_refresh: bool = False) -> dict:
    steam_input = _steam_id_ou_vanity_usuario(user)
    api_key = _steam_api_key_usuario(user)
    steam_id64 = None
    jogos = []
    conquistas = None
    erro = None
    fonte_jogos = 'api_official'
    capas_usadas: set[str] = set()

    if steam_input:
        steam_id64 = _steam_resolver_steamid(steam_input, api_key)
        if not steam_id64:
            erro = 'Não foi possível resolver sua conta Steam. Use o SteamID64 ou faça o login oficial via OpenID.'
        else:
            jogos = _steam_obter_biblioteca_publica_completa(steam_id64, api_key=api_key, force_refresh=force_refresh)
            if jogos:
                fonte_jogos = 'api_official'
            else:
                jogos = []
                erro = (
                    'A Steam foi identificada, mas a biblioteca não está acessível. '
                    'Deixe os jogos públicos ou informe uma Steam API Key válida para sincronizar todos os jogos.'
                )

            jogos = _deduplicar_jogos_steam(jogos)
            if steam_appid is None and jogos:
                steam_appid = jogos[0]['appid']
            if steam_appid and api_key:
                conquistas = _steam_achievements_jogo(steam_id64, api_key, int(steam_appid))

            for jogo in jogos:
                jogo['cover_url'] = _get_game_cover_centralized(
                    jogo.get('title') or jogo.get('name') or 'Jogo',
                    int(jogo.get('appid') or 0) or None,
                    'steam',
                    permitir_remoto=False,
                )

    if not jogos:
        raiz_steam = (getattr(user, 'steam_library_path', '') or '').strip() or None
        jogos = [
            {
                'appid': int(jogo.get('appid') or 0),
                'name': jogo.get('name') or f"App {jogo.get('appid')}",
                'playtime_forever': 0,
                'install_dir': jogo.get('install_dir') or '',
                'path': jogo.get('path') or '',
                'cover_url': _get_game_cover_centralized(
                    jogo.get('name') or 'Jogo',
                    int(jogo.get('appid') or 0) or None,
                    'steam',
                    permitir_remoto=False,
                ),
            }
            for jogo in listar_jogos_instalados(steam_root=raiz_steam, force=True)
        ]
        if jogos:
            fonte_jogos = 'manifest_local'
            erro = None

    jogo_selecionado = None
    if steam_appid and jogos:
        jogo_selecionado = next((jogo for jogo in jogos if int(jogo['appid']) == int(steam_appid)), None)
    if not jogo_selecionado and jogos:
        jogo_selecionado = jogos[0]

    if jogo_selecionado and not jogo_selecionado.get('cover_url'):
        jogo_selecionado['cover_url'] = _get_game_cover_centralized(
            jogo_selecionado.get('title') or jogo_selecionado.get('name') or 'Jogo',
            int(jogo_selecionado.get('appid') or 0) or None,
            'steam',
            permitir_remoto=False,
        )

    return {
        'steam_input': steam_input,
        'steam_id64': steam_id64,
        'api_key_configurada': bool(api_key),
        'jogos': jogos,
        'jogo_selecionado': jogo_selecionado,
        'steam_appid': int(steam_appid) if steam_appid else None,
        'conquistas': conquistas,
        'erro': erro,
        'fonte_jogos': fonte_jogos,
        'configurado': bool(steam_id64),
    }


def _obter_metadados_installed_games(email: str, jogo_titulo: str, launcher: str) -> dict:
    launcher_busca = (launcher or 'manual').strip().lower()
    registros = listar_games_instalados(email, launcher_busca)
    registro = next(
        (item for item in reversed(registros)
         if normalize_game_name(item.get('nome') or '') == normalize_game_name(jogo_titulo)),
        None,
    )
    if not registro:
        return {}
    return {
        'nome': registro.get('nome') or '',
        'launcher': registro.get('launcher') or '',
        'appid': registro.get('appid') or '',
        'library_root': registro.get('library_root') or '',
        'game_folder': registro.get('game_folder') or '',
        'exe_name': registro.get('exe_name') or '',
        'executavel': registro.get('exe_path') or '',
        'pasta': registro.get('game_folder') or '',
        'icon_path': registro.get('icon_path') or '',
        'cover_path': registro.get('cover_path') or '',
        'installed': bool(registro.get('installed')),
        'favorite': bool(registro.get('favorite')),
        'last_scan': registro.get('last_scan') or '',
        'hash': registro.get('hash') or '',
    }


def _obter_metadados_launcher(email: str, jogo_titulo: str, launcher: str) -> dict:
    metadata_installed = _obter_metadados_installed_games(email, jogo_titulo, launcher)
    if metadata_installed:
        return metadata_installed

    conn = get_connection()
    try:
        rows = conn.execute(
            'SELECT caminho, executavel, pasta, icone, ultima_verificacao, appid, launcher_path, launcher_type, launcher_exe, launcher_args, last_scan, nome_jogo FROM launcher_library WHERE email_usuario = ? AND launcher = ? ORDER BY id DESC',
            (email, (launcher or 'manual').lower()),
        ).fetchall()
        row = next(
            (item for item in rows
             if normalize_game_name(item['nome_jogo'] or '') == normalize_game_name(jogo_titulo)),
            None,
        )
        if not row:
            return {}
        return {
            'caminho': row['caminho'] or '',
            'executavel': row['executavel'] or '',
            'pasta': row['pasta'] or '',
            'icone': row['icone'] or '',
            'ultima_verificacao': row['ultima_verificacao'] or '',
            'appid': row['appid'] or '',
            'launcher_path': row['launcher_path'] or '',
            'launcher_type': row['launcher_type'] or '',
            'launcher_exe': row['launcher_exe'] or '',
            'launcher_args': row['launcher_args'] or '',
            'last_scan': row['last_scan'] or '',
        }
    finally:
        conn.close()


def _normalizar_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(path or '')) if path else ''


def _normalizar_nome_jogo(nome_jogo: str) -> str:
    if not nome_jogo:
        return ''
    texto = os.path.basename(str(nome_jogo)).strip()
    texto = os.path.splitext(texto)[0]
    texto = texto.replace('_', ' ').replace('.', ' ')
    texto = re.sub(r'[-]+', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    if not texto:
        return ''

    lower = texto.lower()
    if 'dragon' in lower and 'ball' in lower and 'fighterz' in lower:
        return 'Dragon Ball FighterZ'
    if 'pragmata' in lower:
        return 'PRAGMATA'
    if 'black myth wukong' in lower or 'blackmythwukong' in lower:
        return 'Black Myth Wukong'
    if 'db xenoverse 2' in lower:
        return 'DB Xenoverse 2'
    if 'db xenoverse' in lower:
        return 'DB Xenoverse'

    for termo in [' legendary edition', ' ultimate edition', ' definitive edition', ' complete edition', ' deluxe edition', ' enhanced edition', ' standard edition', ' gold edition', ' collector edition', ' trial']:
        if termo in lower:
            texto = texto[: lower.find(termo)].strip()
            break

    texto = re.sub(r'\b(v|ver|version)\s*\d[\w.]*\b', '', texto, flags=re.I)
    texto = re.sub(r'\b(edition|expansion|dlc)\b', '', texto, flags=re.I)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto.title() if not texto.isupper() else texto


def _deve_ignorar_path(path: str) -> bool:
    if not path:
        return True
    partes = [parte.lower() for parte in Path(path).parts]
    if not partes:
        return True
    ignorar_dirs = {
        'steam', 'steamworks', 'easyanticheat', 'eos', 'crashreport', 'bootstrap', 'redist', 'support', 'commonredist', 'engine', 'redistributables', 'installer', 'directx', 'vc', 'tools'
    }
    for parte in partes:
        if parte in ignorar_dirs:
            return True
        if parte.startswith('launcher'):
            return True
    return False


def _escolher_executavel_principal(installdir: str, nome_jogo: str | None = None) -> str:
    if not installdir or not os.path.isdir(installdir):
        return ''

    nome_jogo = (nome_jogo or '').strip()
    nome_base = _normalizar_nome_jogo(nome_jogo)
    nome_busca = _normalizar_texto_busca(nome_base or nome_jogo)
    nome_tokens = set(re.findall(r'[a-z0-9]+', nome_busca))
    candidatos: list[tuple[int, str]] = []
    fallback_caminho = ''

    for raiz, dirs, arquivos in os.walk(installdir):
        dirs[:] = [d for d in dirs if not _deve_ignorar_path(os.path.join(raiz, d))]
        for arquivo in sorted(arquivos):
            caminho = os.path.join(raiz, arquivo)
            nome_baixo = arquivo.lower()
            if not nome_baixo.endswith('.exe'):
                continue
            if _deve_ignorar_path(caminho):
                continue
            if any(token in nome_baixo for token in ['launcher', 'crashreport', 'easyanticheat', 'eosoverlay', 'bootstrap', 'steamworks', 'steamhelper', 'updater', 'installer', 'setup', 'uninstall', 'benchmark', 'editor', 'shippingserver', 'dedicatedserver', 'shadercompiler', 'steam', 'unitycrashhandler', 'vc_redist', 'dxsetup', 'eac']):
                continue

            if not fallback_caminho:
                fallback_caminho = caminho

            tamanho = os.path.getsize(caminho) if os.path.exists(caminho) else 0
            arquivo_base = os.path.splitext(arquivo)[0]
            base_busca = _normalizar_texto_busca(arquivo_base)
            tokens_arquivo = set(re.findall(r'[a-z0-9]+', base_busca))
            relpath = os.path.relpath(caminho, installdir)
            rel_parts = [parte.lower() for parte in Path(relpath).parts[:-1]]
            depth = len(rel_parts)
            score = 0

            if nome_tokens:
                score += sum(25 for token in nome_tokens if token in tokens_arquivo)
            if nome_base and nome_base.lower() in base_busca:
                score += 60
            if nome_jogo and _normalizar_texto_busca(nome_jogo) in base_busca:
                score += 40
            if nome_jogo and SequenceMatcher(None, nome_busca, base_busca).ratio() > 0.45:
                score += int(SequenceMatcher(None, nome_busca, base_busca).ratio() * 40)
            if os.path.basename(installdir).lower() in base_busca:
                score += 30
            if arquivo_base.lower() == os.path.basename(installdir).lower():
                score += 80
            if depth <= 1:
                score += 40
            if any(parte in {'binaries', 'win64', 'win32', 'x64'} for parte in rel_parts):
                score += 20
            if 'shipping' in base_busca:
                score += 20
            if tamanho > 2_000_000:
                score += 5
            if score > 0:
                candidatos.append((score, caminho))

    if not candidatos:
        return fallback_caminho

    candidatos.sort(key=lambda item: item[0], reverse=True)
    melhor = max(candidatos, key=lambda item: item[0])
    return melhor[1] if melhor[0] > 0 else candidatos[0][1]


def _registrar_log(mensagem: str) -> None:
    print(f'[Launcher] {mensagem}')


LAUNCHER_MANAGER = LauncherManager(logger=_registrar_log)


def _escolher_pasta_windows() -> str:
    """Compatibilidade interna para o seletor Win32 SHBrowseForFolderW/SHGetPathFromIDListW."""
    return select_folder()


def _escolher_executavel_windows() -> str:
    """Abre o seletor nativo para escolher somente um executável."""
    try:
        if os.name == 'nt' and webview is not None and getattr(webview, 'windows', None):
            resultado = webview.windows[0].create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=('Executáveis (*.exe)', '*.exe'),
            )
            if isinstance(resultado, (list, tuple)):
                return resultado[0] if resultado else ''
            return str(resultado or '')
    except Exception as exc:
        _registrar_log(f'Erro ao abrir diálogo pywebview de executável: {exc}')

    try:
        if os.name == 'nt':
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            try:
                arquivo = filedialog.askopenfilename(
                    title='Selecionar executável',
                    filetypes=[('Executáveis', '*.exe')],
                )
            finally:
                root.destroy()
            return str(arquivo or '').strip()
    except Exception as exc:
        _registrar_log(f'Erro ao abrir seletor de executável via Tk: {exc}')
    return ''


def _abrir_pasta_explorer(caminho: str) -> bool:
    if not caminho:
        return False
    try:
        if os.name == 'nt':
            if os.path.isdir(caminho):
                os.startfile(caminho)  # type: ignore[attr-defined]
                return True
            if os.path.exists(caminho):
                os.startfile(os.path.dirname(caminho))  # type: ignore[attr-defined]
                return True
        else:
            subprocess.Popen(['xdg-open', caminho], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    except Exception as exc:
        _registrar_log(f'Erro ao abrir pasta: {exc}')
    return False


def _executar_async(func, *args, **kwargs):
    thread = Thread(target=func, args=args, kwargs=kwargs, daemon=True)
    thread.start()
    return thread


def _listar_executaveis_em_pasta(base_dir: str) -> list[str]:
    if not base_dir or not os.path.isdir(base_dir):
        return []

    executaveis: list[str] = []
    for raiz, dirs, arquivos in os.walk(base_dir):
        dirs[:] = [d for d in dirs if not _deve_ignorar_path(os.path.join(raiz, d))]
        for arquivo in sorted(arquivos):
            caminho = os.path.join(raiz, arquivo)
            nome_baixo = arquivo.lower()
            if not nome_baixo.endswith('.exe'):
                continue
            if _deve_ignorar_path(caminho):
                continue
            if any(token in nome_baixo for token in ['launcher', 'crashreport', 'easyanticheat', 'eosoverlay', 'bootstrap', 'steamworks', 'steamhelper', 'updater', 'installer', 'setup', 'uninstall', 'benchmark', 'editor', 'shippingserver', 'dedicatedserver', 'shadercompiler', 'steam', 'unitycrashhandler', 'vc_redist', 'dxsetup', 'eac']):
                continue
            executaveis.append(caminho)
    return executaveis


def _descobrir_jogos_por_raiz(base_dir: str, launcher: str) -> list[dict]:
    if not base_dir or not os.path.isdir(base_dir):
        return []

    jogos: list[dict] = []
    for entrada in sorted(Path(base_dir).iterdir(), key=lambda p: p.name.lower()):
        if not entrada.is_dir():
            continue

        nome_jogo = _normalizar_nome_jogo(entrada.name)
        executaveis = _listar_executaveis_em_pasta(str(entrada))
        _registrar_log('Encontrado jogo')
        _registrar_log(f'Nome: {nome_jogo or entrada.name}')
        _registrar_log(f'Pasta: {entrada}')
        if executaveis:
            _registrar_log('Executáveis encontrados')
            for caminho in executaveis[:12]:
                _registrar_log(os.path.basename(caminho))
        else:
            _registrar_log('Executáveis encontrados: nenhum')

        executavel = _escolher_executavel_principal(str(entrada), entrada.name)
        _registrar_log(f'Executável escolhido: {executavel}')
        if not executavel:
            continue

        _registrar_log('Salvando banco')
        _registrar_log(f'game_folder: {entrada}')
        _registrar_log(f'exe_path: {executavel}')
        jogos.append({
            'nome': nome_jogo or entrada.name,
            'launcher': (launcher or 'manual').strip().lower(),
            'caminho': str(entrada),
            'pasta': str(entrada),
            'executavel': executavel,
            'appid': '',
        })
    return jogos


def _descobrir_jogos_hydra(base_dir: str) -> list[dict]:
    return _descobrir_jogos_por_raiz(base_dir, 'hydra')


def _descobrir_jogos_steam(steam_root: str) -> list[dict]:
    if not steam_root:
        return []

    roots: list[str] = []
    normalized = Path(steam_root)
    common_path = normalized / 'steamapps' / 'common'
    if common_path.is_dir():
        roots.append(str(common_path))

    if normalized.name.lower() == 'common' and (normalized.parent / 'steamapps').is_dir():
        roots.append(str(normalized))

    libraryfile = normalized / 'steamapps' / 'libraryfolders.vdf'
    if libraryfile.exists():
        try:
            texto = libraryfile.read_text(encoding='utf-8', errors='ignore')
            for match in re.finditer(r'"([A-Za-z]:\\[^"\n]+)"', texto):
                root_candidate = match.group(1).replace('\\', '\\')
                candidate_path = Path(root_candidate)
                common_candidate = candidate_path / 'steamapps' / 'common'
                if common_candidate.is_dir() and str(common_candidate) not in roots:
                    roots.append(str(common_candidate))
        except Exception:
            pass

    if not roots:
        roots = [steam_root]

    jogos: list[dict] = []
    for base_dir in roots:
        jogos.extend(_descobrir_jogos_por_raiz(base_dir, 'steam'))
    return jogos


def _persistir_jogos_descobertos(email: str, jogos: list[dict], launcher: str) -> int:
    with _AUTO_LIBRARY_DB_LOCK:
        return _persistir_jogos_descobertos_locked(email, jogos, launcher)


def _persistir_jogos_descobertos_locked(email: str, jogos: list[dict], launcher: str) -> int:
    total = 0
    for item in jogos:
        nome_jogo = (item.get('nome') or '').strip()
        if not nome_jogo:
            continue

        launcher_norm = (launcher or 'manual').strip().lower()
        caminho = (item.get('caminho') or item.get('library_root') or '').strip()
        executavel = (item.get('executavel') or item.get('exe_path') or '').strip()
        pasta = (item.get('pasta') or item.get('game_folder') or '').strip()
        icone = (item.get('icone') or '').strip()
        appid = (item.get('appid') or '').strip()

        conn = get_connection()
        try:
            conn.execute(
                '''
                INSERT INTO launcher_library (
                    email_usuario, nome_jogo, launcher, caminho, executavel, pasta, icone, ultima_verificacao, hash, appid,
                    launcher_path, launcher_type, launcher_exe, launcher_args, last_scan
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email_usuario, launcher, appid, nome_jogo) DO UPDATE SET
                    caminho=excluded.caminho,
                    executavel=excluded.executavel,
                    pasta=excluded.pasta,
                    icone=excluded.icone,
                    ultima_verificacao=excluded.ultima_verificacao,
                    hash=excluded.hash,
                    appid=excluded.appid,
                    launcher_path=excluded.launcher_path,
                    launcher_type=excluded.launcher_type,
                    launcher_exe=excluded.launcher_exe,
                    launcher_args=excluded.launcher_args,
                    last_scan=excluded.last_scan
                ''',
                (
                    email,
                    nome_jogo,
                    launcher_norm,
                    caminho,
                    executavel,
                    pasta,
                    icone,
                    datetime.now().isoformat(timespec='seconds'),
                    '',
                    appid,
                    caminho,
                    launcher_norm,
                    executavel,
                    '',
                    datetime.now().isoformat(timespec='seconds'),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        jogo = None
        if launcher_norm == 'steam' and appid.isdigit():
            jogo = JOGOS_DB.get(int(appid))
        if jogo is None:
            nome_normalizado = normalize_game_name(nome_jogo)
            jogo = next(
                (j for j in JOGOS_DB.values()
                 if normalize_game_name(str(j.titulo)) == nome_normalizado),
                None,
            )
        if not jogo:
            novo_id = max(JOGOS_DB.keys(), default=0) + 1
            jogo = Jogo(novo_id, nome_jogo, launcher_norm.title(), launcher_norm.title(), datetime.now().year)
            JOGOS_DB[novo_id] = jogo
            persistir_jogo(jogo, [])

        chave = f"{email}_{jogo.id}"
        existente = BIBLIOTECA_DB.get(chave)
        if existente is None and appid:
            existente = next(
                (item for item in BIBLIOTECA_DB.values()
                 if item.email_usuario == email
                 and (getattr(item, 'launcher', '') or getattr(item, 'origem', '')).strip().lower() == launcher_norm
                 and str(getattr(item, 'codigo_origem', '') or '') == appid),
                None,
            )
        if existente is None:
            existente = next(
                (item for item in BIBLIOTECA_DB.values()
                 if item.email_usuario == email and (
                     (pasta and (getattr(item, 'launcher', '') or getattr(item, 'origem', '')).strip().lower() == launcher_norm
                      and _normalizar_path(getattr(item, 'install_folder', '') or getattr(item, 'pasta_instalacao', '')) == _normalizar_path(pasta))
                 )),
                None,
            )
        if existente is None:
            novo_item = GerenciadorBiblioteca.adicionar_jogo(max([b.id for b in BIBLIOTECA_DB.values()], default=0) + 1, email, jogo.id, origem=launcher_norm, launcher=launcher_norm)
            existente = novo_item
        origem_existente = (getattr(existente, 'launcher', '') or getattr(existente, 'origem', '') or '').strip().lower()
        launcher_final = 'steam' if origem_existente == 'steam' and launcher_norm != 'steam' else launcher_norm
        existente.launcher = launcher_final
        existente.origem = launcher_final
        if not getattr(existente, 'manual_override', False):
            existente.executable_path = executavel or getattr(existente, 'executable_path', '') or ''
            existente.install_folder = pasta or getattr(existente, 'install_folder', '') or ''
            existente.executable_name = os.path.basename(existente.executable_path) if existente.executable_path else ''
        existente.codigo_origem = getattr(existente, 'codigo_origem', '') or appid or ''
        if not getattr(existente, 'manual_override', False):
            setattr(existente, 'pasta_instalacao', pasta or getattr(existente, 'pasta_instalacao', '') or '')
        persistir_biblioteca_item(existente)
        total += 1
    return total


def _limpar_registros_automaticos(email: str, launcher: str, registros: list[dict]) -> dict:
    launcher = (launcher or 'manual').strip().lower()
    ids_validos = {str(item.get('appid') or '').strip() for item in registros if str(item.get('appid') or '').strip()}
    pastas_validas = {_normalizar_path(item.get('game_folder') or item.get('pasta') or '') for item in registros}
    removidos_launcher = 0
    conn = get_connection()
    try:
        rows = conn.execute(
            'SELECT id, appid, pasta FROM launcher_library WHERE email_usuario = ? AND launcher = ?',
            (email, launcher),
        ).fetchall()
        for row in rows:
            appid = str(row['appid'] or '').strip()
            pasta = _normalizar_path(row['pasta'] or '')
            if (appid and appid not in ids_validos) or (not appid and pasta not in pastas_validas):
                conn.execute('DELETE FROM launcher_library WHERE id = ?', (row['id'],))
                removidos_launcher += 1
        conn.commit()
    finally:
        conn.close()

    removidos_biblioteca = 0
    for chave, item in list(BIBLIOTECA_DB.items()):
        if item.email_usuario != email:
            continue
        origem = (getattr(item, 'launcher', '') or getattr(item, 'origem', '') or '').strip().lower()
        if origem != launcher:
            continue
        codigo = str(getattr(item, 'codigo_origem', '') or '').strip()
        pasta = _normalizar_path(getattr(item, 'install_folder', '') or getattr(item, 'pasta_instalacao', '') or '')
        identidade_valida = (codigo and codigo in ids_validos) or (not codigo and pasta in pastas_validas)
        if getattr(item, 'manual_override', False) and identidade_valida:
            continue
        if (codigo and codigo not in ids_validos) or (not codigo and pasta not in pastas_validas):
            remover_biblioteca_item(email, item.jogo_id)
            BIBLIOTECA_DB.pop(chave, None)
            removidos_biblioteca += 1
    return {'launcher': removidos_launcher, 'biblioteca': removidos_biblioteca}


def _sincronizar_biblioteca_launcher(email: str, steam_root: str | None = None, hydra_root: str | None = None, force: bool = False) -> dict:
    user = USUARIOS_DB.get((email or '').strip().lower())
    if not user:
        return {'steam': 0, 'hydra': 0, 'total': 0}

    steam_path = (steam_root or getattr(user, 'steam_library_path', '') or '').strip()
    hydra_path = (hydra_root or getattr(user, 'hydra_library_path', '') or '').strip()
    if steam_path:
        user.steam_library_path = steam_path
    if hydra_path:
        user.hydra_library_path = hydra_path
    persistir_usuario(user)

    total = 0
    if steam_path:
        registros_steam = scan_automatic_library([], include_steam=True, steam_root=steam_path)
        limpeza = _limpar_registros_automaticos(email, 'steam', registros_steam)
        _registrar_log(f"[REINDEX] Steam encontrados={len(registros_steam)} removidos_launcher={limpeza['launcher']} removidos_biblioteca={limpeza['biblioteca']}")
        total += persistir_registros_instalados(email, registros_steam, 'steam')
        total += _persistir_jogos_descobertos(email, registros_steam, 'steam')
    if hydra_path:
        registros_hydra = scan_local_folders([hydra_path], origin='hydra')
        limpeza = _limpar_registros_automaticos(email, 'hydra', registros_hydra)
        _registrar_log(f"[REINDEX] Hydra encontrados={len(registros_hydra)} removidos_launcher={limpeza['launcher']} removidos_biblioteca={limpeza['biblioteca']}")
        total += persistir_registros_instalados(email, registros_hydra, 'hydra')
        total += _persistir_jogos_descobertos(email, registros_hydra, 'hydra')
    return {'steam': int(bool(steam_path)), 'hydra': int(bool(hydra_path)), 'total': total}


def _montar_cards_jogar(email: str) -> list:
    cards = []
    capas_usadas: set[str] = set()
    biblioteca_items = GerenciadorBiblioteca.obter_biblioteca(email)
    for item in biblioteca_items:
        jogo = JOGOS_DB.get(item.jogo_id)
        if not jogo:
            continue
        origem = (getattr(item, 'launcher', '') or getattr(item, 'origem', '') or '').strip().lower()
        if origem not in {'steam', 'hydra', 'manual'}:
            origem = 'manual'
        if origem == 'manual' and (getattr(jogo, 'desenvolvedora', '') or '').strip().lower() == 'steam' and str(getattr(jogo, 'id', '')).isdigit():
            origem = 'steam'
        capa_item = getattr(item, 'cover_url', '') or ''
        if not _usar_capa_armazenada(capa_item, origem):
            capa_item = ''
        metadata = _obter_metadados_launcher(email, jogo.titulo, origem)
        if not getattr(item, 'manual_override', False):
            item.executable_path = getattr(item, 'executable_path', '') or metadata.get('executavel', '') or ''
            if not getattr(item, 'pasta_instalacao', ''):
                setattr(item, 'pasta_instalacao', metadata.get('pasta') or '')
        cards.append({
            'item': item,
            'jogo': jogo,
            'capa_url': (capa_item or _capa_para_jogo_catalogo(jogo, capas_usadas, permitir_remoto=False)),
            'capa_fallback': _capa_fallback(jogo.titulo),
            'origem': origem,
            'favorito': bool(getattr(item, 'favorito', False)),
            'pode_jogar': origem in {'steam', 'hydra', 'manual'},
            'status': getattr(item, 'status', 'offline') or 'offline',
            'executavel': getattr(item, 'executable_path', '') or metadata.get('executavel', ''),
            'pasta_instalacao': getattr(item, 'pasta_instalacao', '') or metadata.get('pasta', ''),
            'manual_override': bool(getattr(item, 'manual_override', False)),
            'executable_name': getattr(item, 'executable_name', '') or os.path.basename(getattr(item, 'executable_path', '') or ''),
            'launcher_display': (
                ('Steam' if origem == 'steam' else 'Hydra' if origem == 'hydra' else 'Local')
                + (' · Executável local' if getattr(item, 'executable_path', '') else '')
            ),
            'ultima_vez': _formatar_hora_resumida(getattr(item, 'last_launched_at', None)),
            'recente': bool(getattr(item, 'last_launched_at', None)),
            'appid': (
                (metadata.get('appid') if str(metadata.get('appid') or '').isdigit() else '')
                or (getattr(item, 'codigo_origem', '') if str(getattr(item, 'codigo_origem', '') or '').isdigit() else '')
                or (str(jogo.id) if origem == 'steam' and str(getattr(jogo, 'id', '')).isdigit() else '')
                or ''
            ),
        })

    cards.sort(key=lambda card: (0 if card['favorito'] else 1, card['jogo'].titulo.lower()))
    return cards


def _montar_games_data_jogar(cards: list) -> list:
    """Converte os mesmos cards da biblioteca clássica em dados JSON para a UI 3D."""
    games_data = []
    for card in cards:
        jogo = card.get('jogo')
        if not jogo:
            continue
        titulo = getattr(jogo, 'titulo', '') or ''
        genero = getattr(jogo, 'genero', '') or ''
        launcher_display = card.get('launcher_display') or ''
        games_data.append({
            'id': getattr(jogo, 'id', None),
            'title': titulo,
            'genre': genero,
            'platform': launcher_display,
            'rating': getattr(card.get('item'), 'nota', 0) or 0,
            'developer': getattr(jogo, 'desenvolvedora', '') or '',
            'desc': f'{genero} · {launcher_display}'.strip(' ·'),
            'coverUrl': card.get('capa_url') or card.get('capa_fallback') or '',
            'favorito': bool(card.get('favorito')),
            'origem': card.get('origem') or 'manual',
            'executavel': card.get('executavel') or '',
            'launcher': card.get('launcher_display') or card.get('origem') or 'manual',
            'appid': card.get('appid') or '',
            'recente': bool(card.get('recente')),
        })
    return games_data


def montar_biblioteca_cards(email: str, launcher: str | None = None) -> list:
    cards = []
    capas_usadas: set[str] = set()
    biblioteca_items = obter_biblioteca_filtrada(email, launcher) if launcher else GerenciadorBiblioteca.obter_biblioteca(email)
    for item in biblioteca_items:
        jogo = JOGOS_DB.get(item.jogo_id)
        if not jogo:
            continue

        origem = (getattr(item, 'launcher', '') or getattr(item, 'origem', '') or '').strip().lower()
        if origem not in {'steam', 'hydra', 'manual'}:
            origem = 'manual'

        fonte = origem if origem in {'steam', 'hydra', 'manual'} else 'manual'
        appid = None
        codigo = str(getattr(item, 'codigo_origem', '') or '').strip()
        if codigo.isdigit():
            appid = int(codigo)
        elif fonte == 'steam' and str(getattr(jogo, 'id', '')).isdigit():
            appid = int(jogo.id)

        # Try to use stored cover_url first
        capa_item = getattr(item, 'cover_url', '') or ''
        if not _usar_capa_armazenada(capa_item, fonte, appid):
            capa_item = ''
        
        # If no stored cover, use centralized resolver
        if not capa_item:
            titulo = getattr(jogo, 'titulo', '') or ''
            capa_item = _get_game_cover_centralized(titulo, appid, fonte, permitir_remoto=False)
        
        cards.append({
            'item': item,
            'jogo': jogo,
            'capa_url': capa_item or _capa_fallback(getattr(jogo, 'titulo', '')),
            'capa_fallback': _capa_fallback(getattr(jogo, 'titulo', '')),
            'esta_na_biblioteca': True,
            'origem': fonte,
        })

    contagem_origens = {
        'steam': sum(1 for card in cards if card['origem'] == 'steam'),
        'hydra': sum(1 for card in cards if card['origem'] == 'hydra'),
        'manual': sum(1 for card in cards if card['origem'] == 'manual'),
    }
    print(f'[Library Debug] usuário={email} total_cards={len(cards)} steam={contagem_origens["steam"]} hydra={contagem_origens["hydra"]} manual={contagem_origens["manual"]}')
    return cards


def _obter_ou_criar_categoria(nome_categoria: str) -> Categoria:
    categoria_existente = next(
        (cat for cat in CATEGORIAS_DB.values() if cat.nome.strip().lower() == nome_categoria.strip().lower()),
        None,
    )
    if categoria_existente:
        return categoria_existente

    novo_id_categoria = max(CATEGORIAS_DB.keys(), default=0) + 1
    categoria = Categoria(novo_id_categoria, nome_categoria)
    CATEGORIAS_DB[novo_id_categoria] = categoria
    persistir_categoria(categoria)
    return categoria


def _steam_jogo_para_catalogo(jogo_steam: dict) -> Jogo:
    appid = int(jogo_steam.get('appid') or 0)
    nome = (jogo_steam.get('name') or f'App {appid}').strip()
    jogo = Jogo(appid, nome, 'Steam', 'Steam', datetime.now().year)
    try:
        jogo.associar_categoria(_obter_ou_criar_categoria('Steam'))
        jogo.associar_categoria(_obter_ou_criar_categoria('Meus jogos'))
    except Exception:
        pass
    jogo.capa_url = _capa_steam_jogo(appid)
    jogo.capa_fallback = _capa_fallback(nome)
    return jogo


def _obter_jogo_por_item(item) -> dict | None:
    jogo = JOGOS_DB.get(getattr(item, 'jogo_id', 0))
    if not jogo:
        return None
    return {
        'id': jogo.id,
        'titulo': jogo.titulo,
        'genero': jogo.genero,
        'desenvolvedora': jogo.desenvolvedora,
        'ano': jogo.ano,
        'launcher': getattr(item, 'launcher', 'manual') or 'manual',
        'origem': getattr(item, 'origem', 'manual') or 'manual',
    }


def _atualizar_status_jogo(item, novo_status: str, jogo_titulo: str | None = None) -> None:
    item.status = novo_status
    item.last_played_game = jogo_titulo or getattr(item, 'last_played_game', '') or ''
    item.last_launched_at = datetime.now()
    persistir_biblioteca_item(item)


def _listar_diretorios_pesquisa() -> list[str]:
    diretorios: list[str] = []
    if os.name == 'nt':
        usuario = os.path.expanduser('~')
        if usuario:
            diretorios.extend([
                os.path.join(usuario, 'Desktop'),
                os.path.join(usuario, 'AppData', 'Roaming', 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
                os.path.join(usuario, 'AppData', 'Local', 'Microsoft', 'WindowsApps'),
            ])
        diretorios.extend([
            os.path.join('C:', os.sep, 'ProgramData', 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
            os.path.join('C:', os.sep, 'Program Files'),
            os.path.join('C:', os.sep, 'Program Files (x86)'),
            os.path.join('D:', os.sep, 'Games'),
            os.path.join('E:', os.sep, 'Games'),
            os.path.join('C:', os.sep, 'Program Files', 'Steam', 'steamapps', 'common'),
            os.path.join('C:', os.sep, 'Program Files (x86)', 'Steam', 'steamapps', 'common'),
            os.path.join('D:', os.sep, 'SteamLibrary', 'steamapps', 'common'),
            os.path.join('E:', os.sep, 'SteamLibrary', 'steamapps', 'common'),
        ])
    else:
        diretorios.extend([
            os.path.expanduser('~/Desktop'),
            '/usr/games',
        ])

    return [d for d in diretorios if d]


def _normalizar_texto_busca(texto: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (texto or '').lower())


def _resolver_atalho_windows(caminho_atalho: str) -> str:
    if os.name != 'nt' or not caminho_atalho.lower().endswith('.lnk'):
        return ''
    try:
        comando = (
            "$sh = New-Object -ComObject WScript.Shell; "
            "$lnk = $sh.CreateShortcut('{0}'); "
            "Write-Output $lnk.TargetPath"
        ).format(caminho_atalho.replace("'", "''"))
        resultado = subprocess.run(
            ['powershell', '-NoProfile', '-Command', comando],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if resultado.returncode == 0:
            alvo = (resultado.stdout or '').strip()
            if alvo and os.path.exists(alvo):
                return alvo
    except Exception:
        pass
    return ''


def _localizar_executavel_jogo(item, jogo_titulo: str | None = None) -> str:
    caminho = getattr(item, 'executable_path', '') or ''
    if caminho and os.path.exists(caminho):
        return caminho
    if getattr(item, 'manual_override', False):
        return ''

    jogo = JOGOS_DB.get(getattr(item, 'jogo_id', 0))
    titulo = (jogo_titulo or getattr(jogo, 'titulo', '') or '').strip()
    candidatos = []
    if titulo:
        candidatos.append(titulo)
        candidatos.append(os.path.splitext(os.path.basename(titulo))[0])
        candidatos.append(_normalizar_texto_busca(titulo))
        for token in re.split(r'[^a-z0-9]+', _normalizar_texto_busca(titulo)):
            if token:
                candidatos.append(token)

    for base_dir in _listar_diretorios_pesquisa():
        if not base_dir or not os.path.isdir(base_dir):
            continue
        for raiz, _, arquivos in os.walk(base_dir):
            for nome_arquivo in arquivos:
                caminho_arquivo = os.path.join(raiz, nome_arquivo)
                nome_baixo = nome_arquivo.lower()
                extensoes = ('.exe', '.bat', '.cmd', '.com', '.scr')
                if not nome_baixo.endswith(extensoes) and not nome_baixo.endswith('.lnk'):
                    continue

                caminho_resolvido = caminho_arquivo
                if nome_baixo.endswith('.lnk'):
                    caminho_resolvido = _resolver_atalho_windows(caminho_arquivo) or caminho_arquivo

                if not os.path.exists(caminho_resolvido):
                    continue

                nome_base = os.path.splitext(os.path.basename(caminho_resolvido))[0].lower()
                caminho_normalizado = _normalizar_texto_busca(os.path.abspath(caminho_resolvido))
                for candidato in candidatos:
                    if not candidato:
                        continue
                    candidato_normalizado = _normalizar_texto_busca(str(candidato))
                    if not candidato_normalizado:
                        continue
                    if candidato_normalizado in caminho_normalizado or candidato_normalizado in nome_base:
                        item.executable_path = caminho_resolvido
                        item.pasta_instalacao = os.path.dirname(caminho_resolvido)
                        try:
                            persistir_biblioteca_item(item)
                        except Exception:
                            pass
                        return caminho_resolvido

    return ''


def _iniciar_jogo(item) -> dict:
    detector = obter_detector() or inicializar_detector(callback_mudanca_presenca_global)
    jogo = JOGOS_DB.get(getattr(item, 'jogo_id', 0))
    titulo = getattr(jogo, 'titulo', '') if jogo else ''
    origem = (getattr(item, 'launcher', '') or getattr(item, 'origem', '') or '').strip().lower()
    appid = getattr(item, 'codigo_origem', '') if origem == 'steam' else None
    detector.registrar_jogo_esperado(titulo, appid, getattr(item, 'executable_path', '') or '')
    resultado = LAUNCHER_MANAGER.iniciar_jogo(item)
    if resultado.get('ok') and resultado.get('success'):
        _atualizar_status_jogo(item, 'playing', titulo)
    else:
        detector.limpar_jogo_esperado()
    return resultado


def _steam_normalizar_appid(valor) -> str:
    texto = str(valor or '').strip()
    if not texto:
        return ''
    try:
        return str(int(float(texto)))
    except (TypeError, ValueError):
        return ''


def importar_steam_para_biblioteca_local(meu_email: str) -> tuple[int, int, str | None]:
    _garantir_biblioteca_db_consistente()
    user = USUARIOS_DB.get(meu_email)
    if not user:
        return 0, 0, 'Usuário não encontrado.'

    steam_contexto = montar_steam_contexto(user, force_refresh=True)
    raiz_steam = (getattr(user, 'steam_library_path', '') or '').strip() or None
    jogos_manifest = listar_jogos_instalados(steam_root=raiz_steam, force=True)
    jogos_api = steam_contexto.get('jogos', []) or []

    jogos_por_appid: dict[str, dict] = {}
    for jogo in jogos_manifest + jogos_api:
        appid = _steam_normalizar_appid(jogo.get('appid') or jogo.get('id'))
        if not appid:
            continue
        atual = jogos_por_appid.get(appid) or {}
        jogos_por_appid[appid] = {**atual, **jogo, 'appid': int(appid)}

    jogos_conectados = list(jogos_por_appid.values())
    steam_contexto['jogos'] = jogos_conectados

    if not jogos_conectados:
        return 0, 0, steam_contexto.get('erro') or 'Nenhum jogo encontrado nos manifests locais ou na biblioteca Steam.'

    steam_id64 = steam_contexto.get('steam_id64', '')
    jogos_encontrados = len(jogos_conectados)
    current_appids = {str(jogo.get('appid') or '').strip() for jogo in jogos_conectados if str(jogo.get('appid') or '').strip()}

    print(f'[STEAM IMPORT] user={meu_email} steam_id64={steam_id64} api={len(jogos_api)} manifest={len(jogos_manifest)} unidos={len(jogos_conectados)}')
    print(f'[STEAM IMPORT] AppIDs atuais: {sorted(map(int, current_appids))[:10]} ... total={len(current_appids)}')

    removidos_steam = 0
    for item in list(BIBLIOTECA_DB.values()):
        if item.email_usuario != meu_email:
            continue

        origem = (getattr(item, 'launcher', '') or getattr(item, 'origem', '') or '').strip().lower()
        codigo = _steam_normalizar_appid(getattr(item, 'codigo_origem', '') or getattr(item, 'jogo_id', ''))
        if getattr(item, 'manual_override', False) and not codigo:
            continue

        if origem == 'steam' or codigo:
            if codigo and codigo not in current_appids:
                BIBLIOTECA_DB.pop(f"{meu_email}_{item.jogo_id}", None)
                try:
                    remover_biblioteca_item(meu_email, item.jogo_id)
                except Exception:
                    pass
                removidos_steam += 1
                continue

            if not codigo and origem == 'steam' and not str(item.jogo_id).strip().isdigit():
                BIBLIOTECA_DB.pop(f"{meu_email}_{item.jogo_id}", None)
                try:
                    remover_biblioteca_item(meu_email, item.jogo_id)
                except Exception:
                    pass
                removidos_steam += 1
    print(f'[STEAM IMPORT] removidos_stale={removidos_steam}')

    log_import_iniciado(meu_email, steam_id64, jogos_encontrados)

    jogos_importados = 0
    jogos_ja_existiam = 0
    produtos_validos = []
    appids_importados = []
    appids_atualizados = []

    for jogo_steam in jogos_conectados:
        appid = int(jogo_steam.get('appid') or 0)
        if not appid:
            continue

        try:
            if appid not in JOGOS_DB:
                jogo_catalogo = _steam_jogo_para_catalogo(jogo_steam)
                JOGOS_DB[appid] = jogo_catalogo
                persistir_jogo(jogo_catalogo, jogo_catalogo._categorias)
                log_jogo_criado_catalogo(appid, jogo_steam.get('name', 'Desconhecido'))
            else:
                log_jogo_ja_existia_catalogo(appid)

            chave_biblioteca = f"{meu_email}_{appid}"
            item_existente = BIBLIOTECA_DB.get(chave_biblioteca)
            if item_existente is None:
                item_existente = next(
                    (item for item in BIBLIOTECA_DB.values()
                     if item.email_usuario == meu_email and str(getattr(item, 'codigo_origem', '') or '').strip() == str(appid)
                     and (getattr(item, 'launcher', '') or getattr(item, 'origem', '') or '').strip().lower() == 'steam'),
                    None,
                )

            if item_existente is not None:
                jogos_ja_existiam += 1
                horas_jogadas = int(round((jogo_steam.get('playtime_forever') or 0) / 60))
                item_existente.atualizar_tempo_jogado(horas_jogadas)
                item_existente.cover_url = _capa_steam_jogo(appid)
                item_existente.origem = 'steam'
                item_existente.launcher = 'steam'
                item_existente.codigo_origem = str(appid)
                item_existente.jogo_id = appid
                item_existente.email_usuario = meu_email
                persistir_biblioteca_item(item_existente)
                log_jogo_atualizado_biblioteca(meu_email, appid, jogo_steam.get('name', 'Desconhecido'), horas_jogadas)
                appids_atualizados.append(appid)
                produtos_validos.append(appid)
                continue

            novo_id_biblioteca = max([b.id for b in BIBLIOTECA_DB.values()], default=0) + 1
            item = GerenciadorBiblioteca.adicionar_jogo(novo_id_biblioteca, meu_email, appid, origem='steam', launcher='steam')
            horas_jogadas = int(round((jogo_steam.get('playtime_forever') or 0) / 60))
            item.atualizar_tempo_jogado(horas_jogadas)
            item.cover_url = _capa_steam_jogo(appid)
            item.origem = 'steam'
            item.launcher = 'steam'
            item.codigo_origem = str(appid)
            persistir_biblioteca_item(item)
            jogos_importados += 1
            log_jogo_adicionado_biblioteca(meu_email, appid, jogo_steam.get('name', 'Desconhecido'), horas_jogadas)
            appids_importados.append(appid)
            produtos_validos.append(appid)

        except Exception as e:
            log_jogo_import_erro(meu_email, appid, str(e))
            continue

    biblioteca_usuario = GerenciadorBiblioteca.obter_biblioteca(meu_email)
    biblioteca_steam = [
        item for item in biblioteca_usuario
        if (getattr(item, 'launcher', '') or getattr(item, 'origem', '') or '').strip().lower() == 'steam'
    ]
    quantidade_banco = len(biblioteca_steam)
    appids_banco = [int(str(getattr(item, 'codigo_origem', '') or getattr(item, 'jogo_id', '')).strip()) for item in biblioteca_steam if str(getattr(item, 'codigo_origem', '') or getattr(item, 'jogo_id', '')).strip().isdigit()]

    print(f'[STEAM IMPORT] banco_steam_final={quantidade_banco} appids={appids_banco[:10]}')
    log_validacao_banco_dados(meu_email, steam_id64, quantidade_banco, appids_banco)

    jogos_perdidos = max(0, jogos_encontrados - len(set(appids_banco) | set(produtos_validos)))
    if jogos_perdidos > 0:
        appids_encontrados = [int(j.get('appid', 0)) for j in jogos_conectados if str(j.get('appid', 0)).strip()]
        appids_nao_importados = [aid for aid in appids_encontrados if aid not in appids_importados and aid not in appids_atualizados]
        log_discrepancia('ENCONTRADOS', jogos_encontrados, 'IMPORTADOS', len(set(appids_banco) | set(produtos_validos)), appids_nao_importados)

    log_import_finalizado(meu_email, steam_id64, jogos_encontrados, jogos_importados, jogos_ja_existiam, jogos_perdidos)

    erro = None
    if jogos_importados:
        erro = None
    elif not jogos_ja_existiam:
        erro = steam_contexto.get('erro') or 'Nenhum jogo da Steam foi importado.'

    return jogos_importados, jogos_ja_existiam, erro


def montar_amigos_contexto(email: str) -> dict:
    amigos_emails = GerenciadorAmigos.obter_amigos(email)
    amigos = [USUARIOS_DB.get(amigo_email) for amigo_email in amigos_emails if USUARIOS_DB.get(amigo_email)]
    
    # Get pending requests where user is the receptor
    pendentes_recebidas = GerenciadorAmigos.obter_solicitacoes_pendentes(email)
    pendentes_recebidas_emails = {sol.email_solicitante for sol in pendentes_recebidas}
    
    # Get pending requests where user is the solicitante (SENT BY the logged-in user)
    pendentes_enviadas_emails = set()
    for amizade in AMIZADES_DB.values():
        if amizade.status == 'pendente' and amizade.email_solicitante == email:
            pendentes_enviadas_emails.add(amizade.email_receptor)
    
    # Combine both sets of pending requests
    todas_pendentes_emails = pendentes_recebidas_emails | pendentes_enviadas_emails
    
    sugeridos = []

    for amigo_email, usuario in USUARIOS_DB.items():
        if amigo_email == email:
            continue
        if amigo_email in amigos_emails:
            continue
        if amigo_email in todas_pendentes_emails:
            continue
        if GerenciadorAmigos.sao_amigos(email, amigo_email):
            continue
        sugeridos.append({
            'email': amigo_email,
            'nome': usuario.nome,
        })

    return {
        'amigos_emails': amigos_emails,
        'amigos': amigos,
        'pendentes': pendentes_recebidas,
        'sugeridos': sugeridos,
    }


def _normalizar_texto_busca(texto: str) -> str:
    if texto is None:
        return ''
    texto = str(texto)
    texto = unicodedata.normalize('NFKD', texto)
    texto = texto.encode('ascii', 'ignore').decode('ascii')
    texto = texto.lower()
    texto = re.sub(r'[^a-z0-9]+', ' ', texto).strip()
    return texto


def _corresponde_busca(texto: str, termo: str) -> bool:
    termo_normalizado = _normalizar_texto_busca(termo)
    if not termo_normalizado:
        return True

    texto_normalizado = _normalizar_texto_busca(texto)
    if not texto_normalizado:
        return False

    if termo_normalizado in texto_normalizado:
        return True

    tokens = [token for token in texto_normalizado.split() if token]
    if not tokens:
        return False

    for token in tokens:
        if termo_normalizado in token:
            return True
        if token in termo_normalizado:
            return True
        if len(termo_normalizado) >= 3 and len(token) >= 3:
            if SequenceMatcher(None, termo_normalizado, token).ratio() >= 0.8:
                return True

    return False


def _calcular_amigos_em_comum(meu_email: str, outro_email: str) -> int:
    """Calcula quantos amigos em comum dois usuários têm."""
    meus_amigos = set(GerenciadorAmigos.obter_amigos(meu_email))
    amigos_do_outro = set(GerenciadorAmigos.obter_amigos(outro_email))
    return len(meus_amigos & amigos_do_outro)


def _obter_status_steam_formato(usuario) -> str:
    """Retorna status Steam formatado para exibição."""
    if usuario.steam_current_game:
        return f"🎮 Jogando {usuario.steam_current_game}"
    elif usuario.steam_online:
        return "🟢 Na Steam"
    return "🔴 Offline"


def _obter_status_hydra_formato(usuario) -> str:
    """Retorna status Hydra formatado para exibição."""
    if usuario.hydra_current_game:
        return f"⚡ Jogando {usuario.hydra_current_game}"
    elif usuario.tem_hydra_conectada():
        return "🟢 Hydra conectado"
    return "🔴 Desconectado"


def _tem_steam_conectada(usuario) -> bool:
    """Verifica se usuário tem Steam conectada."""
    steam_id = (getattr(usuario, 'steam_id64', '') or '').strip()
    return bool(steam_id)


def _tem_hydra_conectada_usuario(usuario) -> bool:
    """Verifica se usuário tem Hydra conectada."""
    return usuario.tem_hydra_conectada() if hasattr(usuario, 'tem_hydra_conectada') else bool(
        (getattr(usuario, 'hydra_token', '') or '').strip() or 
        (getattr(usuario, 'hydra_usuario', '') or '').strip() or 
        (getattr(usuario, 'hydra_account_email', '') or '').strip()
    )


def _obter_nome_e_nickname(nome: str | None, email: str) -> tuple[str, str]:
    email_normalizado = (email or '').strip()
    nickname = email_normalizado.split('@', 1)[0] if '@' in email_normalizado else email_normalizado
    nome_display = (nome or '').strip() or nickname
    return nome_display, nickname


def _obter_status_steam_formato_linha(steam_current_game, steam_online) -> str:
    steam_current_game = (steam_current_game or '').strip()
    if steam_current_game:
        return f"🎮 Jogando {steam_current_game}"
    if bool(steam_online):
        return "🟢 Steam conectado"
    return "🔴 Offline"


def _obter_status_hydra_formato_linha(hydra_current_game, hydra_account_email, hydra_usuario, hydra_token) -> str:
    hydra_current_game = (hydra_current_game or '').strip()
    if hydra_current_game:
        return f"⚡ Jogando {hydra_current_game}"
    if any(value.strip() for value in ((hydra_account_email or ''), (hydra_usuario or ''), (hydra_token or ''))):
        return "🟢 Hydra conectado"
    return "🔴 Offline"


def montar_sugestoes_contexto(email: str, termo: str = '', pagina_atual: int = 1, por_pagina: int = 3, 
                              filtro: str = 'todos', ordenacao: str = 'nome_asc') -> dict:
    """
    Monta contexto de sugestões com carregamento DINÂMICO do banco de dados.

    ⚡ CARREGAMENTO DINÂMICO:
    - Busca SEMPRE os usuários ATUAIS do banco SQLite
    - Novos usuários cadastrados aparecem AUTOMATICAMENTE
    - Sem cache permanente - cada chamada reflete o estado atual do banco
    - Novos dados são inclusos na próxima request, sem reinicialização

    Filtros disponíveis: todos, steam, hydra, mais_jogos, novos
    Ordenação: nome_asc, nome_desc, jogos_asc, jogos_desc, mais_recentes, mais_antigos, mais_amigos
    """
    termo_normalizado = (termo or '').strip().lower()

    filtro_lower = (filtro or 'todos').lower().strip()
    ordenacao_lower = (ordenacao or 'nome_asc').lower().strip()

    filtros_validos = {'todos', 'steam', 'hydra', 'mais_jogos', 'novos'}
    if filtro_lower not in filtros_validos:
        filtro_lower = 'todos'

    ordenacoes_validas = {'nome_asc', 'nome_desc', 'jogos_asc', 'jogos_desc', 'mais_recentes', 'mais_amigos'}
    if ordenacao_lower not in ordenacoes_validas:
        ordenacao_lower = 'nome_asc'

    email_atual = (email or '').strip().lower()
    if not email_atual:
        return {
            'termo': termo,
            'filtro': filtro_lower,
            'ordenacao': ordenacao_lower,
            'pagina_atual': 1,
            'total_paginas': 0,
            'total': 0,
            'total_usuarios_sugeridos': 0,
            'per_page': por_pagina,
            'offset': 0,
            'tem_anterior': False,
            'tem_proxima': False,
            'sugestoes': [],
            '_sugestoes_internos': [],
        }

    where_clauses = ['lower(trim(u.email)) != ?', "lower(trim(u.email)) != 'admin@gamelink.com'"]
    params = [email_atual]
    if email_atual != 'admin@gamelink.com':
        where_clauses.append(
            '''
            NOT EXISTS (
                SELECT 1 FROM amizades a
                WHERE a.status IN ('aceito', 'pendente')
                  AND (
                        (lower(trim(a.email_solicitante)) = ? AND lower(trim(a.email_receptor)) = lower(trim(u.email)))
                        OR
                        (lower(trim(a.email_receptor)) = ? AND lower(trim(a.email_solicitante)) = lower(trim(u.email)))
                      )
            )
            '''.strip()
        )
        params.extend([email_atual, email_atual])

    if termo_normalizado:
        termo_like = f'%{termo_normalizado}%'
        where_clauses.append(
            '''
            (
                lower(trim(u.nome)) LIKE ?
                OR lower(trim(substr(u.email, 1, instr(u.email, '@') - 1))) LIKE ?
                OR lower(trim(u.email)) LIKE ?
            )
            '''.strip()
        )
        params.extend([termo_like, termo_like, termo_like])

    if filtro_lower == 'steam':
        where_clauses.append("trim(coalesce(u.steam_id64, '')) != ''")
    elif filtro_lower == 'hydra':
        where_clauses.append(
            "(trim(coalesce(u.hydra_account_email, '')) != '' OR trim(coalesce(u.hydra_usuario, '')) != '' OR trim(coalesce(u.hydra_token, '')) != '')"
        )
    elif filtro_lower == 'mais_jogos':
        where_clauses.append(
            "(SELECT COUNT(*) FROM biblioteca b WHERE lower(trim(b.email_usuario)) = lower(trim(u.email))) > 10"
        )
    elif filtro_lower == 'novos':
        where_clauses.append("date(u.data_cadastro) >= date('now', '-30 days')")

    order_by = "lower(trim(coalesce(nullif(u.nome, ''), substr(u.email, 1, instr(u.email, '@') - 1)))) ASC, lower(trim(u.email)) ASC"
    if ordenacao_lower == 'nome_desc':
        order_by = "lower(trim(coalesce(nullif(u.nome, ''), substr(u.email, 1, instr(u.email, '@') - 1)))) DESC, lower(trim(u.email)) ASC"
    elif ordenacao_lower == 'jogos_asc':
        order_by = "jogos_count ASC, lower(trim(u.email)) ASC"
    elif ordenacao_lower == 'jogos_desc':
        order_by = "jogos_count DESC, lower(trim(u.email)) ASC"
    elif ordenacao_lower == 'mais_recentes':
        order_by = "u.data_cadastro DESC, lower(trim(u.email)) ASC"
    elif ordenacao_lower == 'mais_antigos':
        order_by = "u.data_cadastro ASC, lower(trim(u.email)) ASC"
    elif ordenacao_lower == 'mais_amigos':
        order_by = "amigos_em_comum DESC, lower(trim(u.email)) ASC"

    pagina_atual = max(1, pagina_atual)

    where_clause = ' AND '.join(where_clauses)
    count_sql = f'SELECT COUNT(*) AS total FROM usuarios u WHERE {where_clause}'

    conn = get_connection()
    cursor = conn.cursor()
    total = cursor.execute(count_sql, params).fetchone()['total'] or 0
    total_paginas = (total + por_pagina - 1) // por_pagina if total else 0

    if total == 0:
        conn.close()
        return {
            'termo': termo,
            'filtro': filtro_lower,
            'ordenacao': ordenacao_lower,
            'pagina_atual': pagina_atual,
            'total_paginas': 0,
            'total': 0,
            'total_usuarios_sugeridos': 0,
            'per_page': por_pagina,
            'offset': 0,
            'tem_anterior': False,
            'tem_proxima': False,
            'sugestoes': [],
            '_sugestoes_internos': [],
        }

    if pagina_atual > total_paginas:
        conn.close()
        return {
            'termo': termo,
            'filtro': filtro_lower,
            'ordenacao': ordenacao_lower,
            'pagina_atual': pagina_atual,
            'total_paginas': total_paginas,
            'total': total,
            'total_usuarios_sugeridos': total,
            'per_page': por_pagina,
            'offset': (pagina_atual - 1) * por_pagina,
            'tem_anterior': total_paginas > 0,
            'tem_proxima': False,
            'sugestoes': [],
            '_sugestoes_internos': [],
        }

    offset = (pagina_atual - 1) * por_pagina

    page_sql = f'''
        SELECT
            u.nome,
            u.email,
            coalesce(u.foto_perfil, '') AS foto_perfil,
            u.steam_id64,
            u.steam_online,
            u.steam_current_game,
            u.hydra_account_email,
            u.hydra_usuario,
            u.hydra_token,
            u.hydra_current_game,
            u.data_cadastro,
            (
                SELECT COUNT(*)
                FROM biblioteca b
                WHERE lower(trim(b.email_usuario)) = lower(trim(u.email))
            ) AS jogos_count,
            (
                SELECT COUNT(DISTINCT meus.friend)
                FROM (
                    SELECT CASE
                        WHEN lower(trim(a.email_solicitante)) = ? THEN lower(trim(a.email_receptor))
                        ELSE lower(trim(a.email_solicitante))
                    END AS friend
                    FROM amizades a
                    WHERE a.status = 'aceito'
                      AND (lower(trim(a.email_solicitante)) = ? OR lower(trim(a.email_receptor)) = ?)
                ) AS meus
                INNER JOIN (
                    SELECT CASE
                        WHEN lower(trim(a2.email_solicitante)) = lower(trim(u.email)) THEN lower(trim(a2.email_receptor))
                        ELSE lower(trim(a2.email_solicitante))
                    END AS friend
                    FROM amizades a2
                    WHERE a2.status = 'aceito'
                      AND (lower(trim(a2.email_solicitante)) = lower(trim(u.email)) OR lower(trim(a2.email_receptor)) = lower(trim(u.email)))
                ) AS outros
                ON meus.friend = outros.friend
            ) AS amigos_em_comum
        FROM usuarios u
        WHERE {where_clause}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
    '''

    page_params = [email_atual, email_atual, email_atual] + params + [por_pagina, offset]
    rows = cursor.execute(page_sql, page_params).fetchall()
    conn.close()

    sugestoes_resposta = []
    for row in rows:
        nome_display, nickname = _obter_nome_e_nickname(row['nome'], row['email'])
        avatar_url = (row['foto_perfil'] or '').strip()
        jogos_count = int(row['jogos_count'] or 0)
        tem_steam = bool((row['steam_id64'] or '').strip())
        tem_hydra = any(value.strip() for value in ((row['hydra_account_email'] or ''), (row['hydra_usuario'] or ''), (row['hydra_token'] or '')))

        online_status = '🟢 Online' if tem_steam or tem_hydra or bool(row['steam_online']) else '🔴 Offline'
        sugestoes_resposta.append({
            'nome': nome_display,
            'nickname': nickname,
            'avatar_url': avatar_url,
            'email': row['email'],
            'jogos_count': jogos_count,
            'status_online': online_status,
            'status_steam': _obter_status_steam_formato_linha(row['steam_current_game'], row['steam_online']),
            'status_hydra': _obter_status_hydra_formato_linha(row['hydra_current_game'], row['hydra_account_email'], row['hydra_usuario'], row['hydra_token']),
            'tem_steam': tem_steam,
            'tem_hydra': tem_hydra,
            'amigos_em_comum': int(row['amigos_em_comum'] or 0),
            'data_cadastro': row['data_cadastro'] or '',
        })

    tem_anterior = pagina_atual > 1
    tem_proxima = pagina_atual < total_paginas

    return {
        'termo': termo,
        'filtro': filtro_lower,
        'ordenacao': ordenacao_lower,
        'pagina_atual': pagina_atual,
        'total_paginas': total_paginas,
        'total': total,
        'total_usuarios_sugeridos': total,
        'per_page': por_pagina,
        'offset': offset,
        'tem_anterior': tem_anterior,
        'tem_proxima': tem_proxima,
        'sugestoes': sugestoes_resposta,
        '_sugestoes_internos': [],
    }


@app.route('/sugestoes')
@app.route('/api/sugestoes')

def sugestoes():
    if 'user_email' not in session:
        return jsonify({'erro': 'Não autorizado'}), 401

    termo = request.args.get('search', request.args.get('termo', '')).strip()
    pagina = request.args.get('page', type=int)
    if pagina is None:
        pagina = request.args.get('pagina', type=int)
    pagina = pagina or 1

    por_pagina = request.args.get('limit', type=int)
    if por_pagina is None:
        por_pagina = request.args.get('per_page', type=int)
    por_pagina = por_pagina or 3
    filtro = request.args.get('filter', request.args.get('filtro', 'todos')).strip().lower()
    ordenacao = request.args.get('sort', request.args.get('ordenacao', 'nome_asc')).strip().lower()
    
    # Validar parâmetros
    pagina = max(1, pagina)
    por_pagina = max(1, por_pagina)
    
    # Filtros válidos
    filtros_validos = {'todos', 'steam', 'hydra', 'mais_jogos', 'novos'}
    if filtro not in filtros_validos:
        filtro = 'todos'
    
    # Ordenações válidas
    ordenacoes_validas = {'nome_asc', 'nome_desc', 'jogos_asc', 'jogos_desc', 'mais_recentes', 'mais_antigos', 'mais_amigos'}
    if ordenacao not in ordenacoes_validas:
        ordenacao = 'nome_asc'
    
    inicio = time.time()
    print(f'[SUGESTOES] Consulta iniciada - Usuário: {session["user_email"]}, Search: "{termo}", Page: {pagina}, Filter: {filtro}, Sort: {ordenacao}')
    
    dados = montar_sugestoes_contexto(
        session['user_email'], 
        termo, 
        pagina, 
        por_pagina,
        filtro,
        ordenacao
    )
    
    duracao_ms = int((time.time() - inicio) * 1000)
    print(f'[SUGESTOES] Consulta finalizada - Usuários encontrados: {len(dados.get("sugestoes", []))}, Total: {dados.get("total_usuarios_sugeridos", 0)}, Tempo: {duracao_ms}ms')
    
    response = {
        'users': dados['sugestoes'],
        'sugestoes': dados['sugestoes'],
        'page': dados['pagina_atual'],
        'pages': dados['total_paginas'],
        'per_page': dados['per_page'],
        'limit': dados['per_page'],
        'total': dados['total_usuarios_sugeridos'],
        'total_usuarios_sugeridos': dados['total_usuarios_sugeridos'],
        'pagina_atual': dados['pagina_atual'],
        'total_paginas': dados['total_paginas'],
        'offset': dados['offset'],
        'tem_anterior': dados['tem_anterior'],
        'tem_proxima': dados['tem_proxima'],
        'search': termo,
        'filter': filtro,
        'sort': ordenacao,
    }
    
    return jsonify(response)


# Moderação de Conteúdo Dinâmica (Suporta o arquivo com espaço ou corrigido)
import importlib.util
import re
import unicodedata
from difflib import SequenceMatcher
try:
    spec = importlib.util.spec_from_file_location("moderacao", "modelos/moderação de conteudo.py")
    moderacao = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(moderacao)
    moderate_text = moderacao.moderate_text
except Exception:
    def moderate_text(texto):
        proibidas = ['spam', 'ofensa', 'impróprio']
        achados = [p for p in proibidas if p in texto.lower()]
        return {"allowed": len(achados) == 0, "blocked_terms": achados}

# Carga inicial de dados unificada
_estado_persistido = carregar_estado_persistido()
CATEGORIAS_DB = _estado_persistido.get('categorias_db', {})
if not JOGOS_DB:
    c1 = Categoria(1, "RPG")
    c2 = Categoria(2, "Ação")
    CATEGORIAS_DB[1] = c1
    CATEGORIAS_DB[2] = c2
    persistir_categoria(c1)
    persistir_categoria(c2)

    j1 = Jogo(1, "The Witcher 3", "RPG", "CD Projekt Red", 2015)
    j1.associar_categoria(c1)
    j2 = Jogo(2, "Elden Ring", "RPG", "FromSoftware", 2022)
    j2.associar_categoria(c1)
    j3 = Jogo(3, "GTA V", "Ação", "Rockstar", 2013)
    j3.associar_categoria(c2)

    JOGOS_DB[1] = j1
    JOGOS_DB[2] = j2
    JOGOS_DB[3] = j3
    persistir_jogo(j1, [c1])
    persistir_jogo(j2, [c1])
    persistir_jogo(j3, [c2])

    if ADMIN_EMAIL not in USUARIOS_DB:
        admin_password = obter_senha_admin_padrao()
        admin = Admin(1, "Caxa", ADMIN_EMAIL, admin_password, nivel_acesso=5)
        USUARIOS_DB[admin.email.lower()] = admin
        persistir_usuario(admin)

# --- Rotas de Autenticação ---
@app.route('/')
def index(): 
    return redirect(url_for('login'))

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        acao = (request.form.get('acao') or 'iniciar').strip().lower()

        if acao in {'verificar', 'reenviar'}:
            pendente = _cadastro_pendente_valido()
            if not pendente:
                flash('Este código expirou. Solicite um novo código.', 'warning')
                return render_template('cadastro.html', verificacao_pendente=False)

            if acao == 'reenviar':
                agora = time.time()
                ultimo_envio = float(session.get('cadastro_ultimo_envio', 0) or 0)
                if agora - ultimo_envio < 30:
                    flash('Aguarde alguns segundos antes de solicitar outro código.', 'warning')
                    return render_template(
                        'cadastro.html',
                        verificacao_pendente=True,
                        email_pendente=pendente['email'],
                        email_pendente_mascarado=_mascarar_email(pendente['email']),
                    )

                novo_codigo = _gerar_codigo_verificacao()
                pendente['codigo'] = novo_codigo
                pendente['expira_em'] = agora + 600
                session['cadastro_pendente'] = pendente
                session['cadastro_ultimo_envio'] = agora
                try:
                    if _enviar_codigo_verificacao_email(pendente['email'], novo_codigo, pendente['nome']):
                        flash('Novo código enviado para seu e-mail.', 'info')
                        codigo_local = None
                    else:
                        flash('SMTP não configurado. O código foi exibido localmente para teste.', 'warning')
                        codigo_local = novo_codigo
                except Exception as exc:
                    flash(f'Não foi possível reenviar o código: {exc}', 'danger')
                    codigo_local = pendente.get('codigo')
                return render_template(
                    'cadastro.html',
                    verificacao_pendente=True,
                    email_pendente=pendente['email'],
                    email_pendente_mascarado=_mascarar_email(pendente['email']),
                    codigo_local=codigo_local,
                )

            codigo_informado = (request.form.get('codigo_verificacao') or '').strip()
            if codigo_informado != pendente.get('codigo'):
                flash('Código de verificação inválido.', 'danger')
                return render_template(
                    'cadastro.html',
                    verificacao_pendente=True,
                    email_pendente=pendente['email'],
                    email_pendente_mascarado=_mascarar_email(pendente['email']),
                )

            email = pendente['email']
            nome = pendente['nome']
            senha = pendente['senha']
            if email in USUARIOS_DB:
                session.pop('cadastro_pendente', None)
                session.pop('cadastro_ultimo_envio', None)
                flash('E-mail já cadastrado!', 'danger')
                return render_template('cadastro.html', verificacao_pendente=False)

            proximo_id = max([user.id for user in USUARIOS_DB.values()], default=0) + 1
            novo_usuario = Usuario(proximo_id, nome, email, senha)
            novo_usuario.data_cadastro = datetime.now().isoformat(timespec='seconds')
            USUARIOS_DB[email] = novo_usuario
            persistir_usuario(novo_usuario)
            enviar_email(
                destinatario=email,
                assunto='Bem-vindo ao GameUnexa',
                corpo=(
                    f'Olá, {nome}!\n\n'
                    'Seu cadastro foi concluído com sucesso no GameUnexa.\n'
                    'Acesse o sistema e aproveite sua nova comunidade de jogos.'
                ),
                tipo_email='welcome',
                template_name='emails/welcome.html',
                context={
                    'titulo': 'Bem-vindo ao GameUnexa',
                    'mensagem': f'Olá, {nome}! Seu cadastro foi concluído com sucesso no GameUnexa.',
                },
                background=True,
            )
            session.pop('cadastro_pendente', None)
            session.pop('cadastro_ultimo_envio', None)
            flash('E-mail verificado. Cadastro concluído!', 'success')
            return redirect(url_for('login'))

        nome = request.form.get('nome', '').strip()
        email = _normalizar_email(request.form.get('email', ''))
        senha = request.form.get('senha', '')
        if not nome or not email or not senha:
            flash('Preencha nome, e-mail e senha para continuar.', 'danger')
            return render_template('cadastro.html', verificacao_pendente=False)
        if email in USUARIOS_DB:
            flash('E-mail já cadastrado!', 'danger')
            return render_template('cadastro.html', verificacao_pendente=False)

        codigo = _gerar_codigo_verificacao()
        session['cadastro_pendente'] = {
            'nome': nome,
            'email': email,
            'senha': senha,
            'codigo': codigo,
            'expira_em': time.time() + 600,
        }
        session['cadastro_ultimo_envio'] = time.time()
        try:
            if _enviar_codigo_verificacao_email(email, codigo, nome):
                flash('Enviamos um código de verificação para seu e-mail.', 'info')
                codigo_local = None
            else:
                flash('SMTP não configurado. O código foi exibido localmente para teste.', 'warning')
                codigo_local = codigo
            return render_template(
                'cadastro.html',
                verificacao_pendente=True,
                email_pendente=email,
                email_pendente_mascarado=_mascarar_email(email),
                codigo_local=codigo_local,
            )
        except Exception as exc:
            flash(f'Não foi possível enviar o e-mail de verificação: {exc}', 'danger')
            return render_template(
                'cadastro.html',
                verificacao_pendente=True,
                email_pendente=email,
                email_pendente_mascarado=_mascarar_email(email),
                codigo_local=codigo,
            )
    pendente = _cadastro_pendente_valido()
    return render_template(
        'cadastro.html',
        verificacao_pendente=bool(pendente),
        email_pendente=(pendente or {}).get('email'),
        email_pendente_mascarado=_mascarar_email((pendente or {}).get('email') or ''),
        codigo_local=(pendente or {}).get('codigo'),
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = _normalizar_email(request.form['email'])
        senha = request.form['senha']
        user = USUARIOS_DB.get(email)
        if user and user.verificar_senha(senha):
            if not user.senha_esta_hasheada():
                user.definir_senha(senha)
                persistir_usuario(user)
            session.clear()
            session['user_email'] = user.email
            session['user_nome'] = user.nome
            session['is_admin'] = isinstance(user, Admin)
            session['csrf_token'] = secrets.token_hex(32)
            ONLINE_USERS.add(user.email)
            return redirect(url_for('dashboard'))
        flash("Credenciais inválidas.", "danger")
    return render_template('login.html')


def _background_user():
    email = session.get('user_email')
    return email if email else None


@app.route('/api/background', methods=['GET', 'POST'])
def api_background():
    email = _background_user()
    if not email:
        return jsonify({'ok': False, 'erro': 'login'}), 401
    if request.method == 'GET':
        return jsonify({'ok': True, 'background': obter_background(email)})
    data = request.get_json(silent=True) or request.form.to_dict()
    try:
        config = salvar_background(email, data)
    except ValueError as exc:
        return jsonify({'ok': False, 'erro': str(exc)}), 400
    return jsonify({'ok': True, 'background': config})


@app.route('/api/background/upload', methods=['POST'])
def api_background_upload():
    email = _background_user()
    if not email:
        return jsonify({'ok': False, 'erro': 'login'}), 401
    try:
        relative_file = salvar_upload_background(request.files.get('file'))
    except ValueError as exc:
        return jsonify({'ok': False, 'erro': str(exc)}), 400
    return jsonify({'ok': True, 'file': relative_file})


@app.route('/api/background/select-folder', methods=['POST'])
def api_background_select_folder():
    email = _background_user()
    if not email:
        return jsonify({'ok': False, 'erro': 'login'}), 401
    kind = (request.get_json(silent=True) or request.form).get('kind', 'slideshow')
    extensions = IMAGE_EXTENSIONS if kind in {'slideshow', 'random-gifs'} else VIDEO_EXTENSIONS
    selected_folder = (request.get_json(silent=True) or request.form).get('folder', '').strip()
    if not selected_folder:
        selected_folder = _escolher_pasta_windows()
    try:
        source_files = arquivos_da_pasta(selected_folder, extensions)
    except ValueError as exc:
        return jsonify({'ok': False, 'erro': str(exc)}), 400
    if not source_files:
        return jsonify({'ok': False, 'erro': 'Nenhum arquivo compatível foi encontrado na pasta.'}), 400
    folder_name = f'{kind}-{uuid4().hex[:10]}'
    target_folder = BACKGROUND_DIR / folder_name
    target_folder.mkdir(parents=True, exist_ok=True)
    copied_files = []
    for source_file in source_files:
        target_file = target_folder / secure_filename(os.path.basename(source_file))
        shutil.copy2(source_file, target_file)
        copied_files.append(f'backgrounds/{folder_name}/{target_file.name}')
    return jsonify({'ok': True, 'folder': f'backgrounds/{folder_name}', 'files': copied_files})


@app.route('/api/background/reset', methods=['POST'])
def api_background_reset():
    email = _background_user()
    if not email:
        return jsonify({'ok': False, 'erro': 'login'}), 401
    return jsonify({'ok': True, 'background': redefinir_background(email)})


@app.route('/userdata/backgrounds/<path:filename>')
def background_asset(filename):
    relative_filename = str(filename or '').replace('\\', '/').lstrip('/')
    if relative_filename.lower().startswith('backgrounds/'):
        relative_filename = relative_filename[len('backgrounds/'):]
    return send_from_directory(str(BACKGROUND_DIR), relative_filename)

@app.route('/recuperar', methods=['GET', 'POST'])
def recuperar():
    if request.method == 'POST':
        email = _normalizar_email(request.form.get('email', ''))
        user = USUARIOS_DB.get(email)
        if user:
            user.token_recuperacao = secrets.token_urlsafe(24)
            enviar_email(
                destinatario=email,
                assunto='Recuperação de senha GameUnexa',
                corpo=(
                    f'Olá, {user.nome}!\n\n'
                    'Recebemos uma solicitação de recuperação de senha.\n'
                    f'Use o token: {user.token_recuperacao}\n\n'
                    'Se você não solicitou, ignore esta mensagem.'
                ),
                tipo_email='recovery',
                background=True,
            )
            flash('Se o e-mail existir, você receberá instruções para redefinir a senha.', 'info')
            return render_template('recuperar.html', email=email, token_gerado=True)
        flash('Se o e-mail existir, você receberá instruções para redefinir a senha.', 'info')
    return render_template('recuperar.html', token_gerado=False)


@app.route('/steam/conectar')
def steam_conectar():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))

    return_to = url_for('steam_callback', _external=True)
    realm = request.host_url
    return redirect(_steam_build_openid_url(return_to, realm))


@app.route('/steam', methods=['GET', 'POST'])
def steam_configuracao():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))

    user = USUARIOS_DB.get(_normalizar_email(meu_email))
    if not user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        api_key = request.form.get('steam_api_key', '').strip()
        steam_id64 = request.form.get('steam_id64', '').strip()
        if api_key and not re.fullmatch(r'[0-9a-fA-F]{32}', api_key):
            flash('A Steam API Key deve conter 32 caracteres hexadecimais.', 'warning')
            return redirect(url_for('steam_configuracao'))
        if steam_id64 and not re.fullmatch(r'\d{17}', steam_id64):
            flash('Informe um SteamID64 válido com 17 dígitos.', 'warning')
            return redirect(url_for('steam_configuracao'))
        if api_key:
            user.steam_api_key = api_key
        if steam_id64:
            user.steam_id64 = steam_id64
        persistir_usuario(user)
        flash('Configuração Steam atualizada. Agora você pode sincronizar sua biblioteca.', 'success')
        return redirect(url_for('steam_configuracao'))

    cards = montar_biblioteca_cards(meu_email, 'steam')
    return render_template(
        'steam.html',
        usuario=user,
        jogos_steam=len(cards),
        steam_configurada=bool(_steam_id_ou_vanity_usuario(user)),
    )


@app.route('/steam/callback')
def steam_callback():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))

    dados = request.values.to_dict(flat=True)
    if dados.get('openid.mode') != 'id_res':
        flash('Falha ao conectar com a Steam.', 'danger')
        return redirect(url_for('perfil', email=meu_email))

    try:
        if not _steam_verificar_resposta_openid(dados):
            flash('Não foi possível validar sua conta Steam.', 'danger')
            return redirect(url_for('perfil', email=meu_email))
    except Exception:
        flash('Não foi possível validar sua conta Steam.', 'danger')
        return redirect(url_for('perfil', email=meu_email))

    claimed_id = dados.get('openid.claimed_id') or dados.get('openid.identity') or ''
    steam_id64 = _steam_extrair_steamid_de_claimed_id(claimed_id)
    if not steam_id64:
        flash('Não foi possível identificar seu SteamID64.', 'danger')
        return redirect(url_for('perfil', email=meu_email))

    user = USUARIOS_DB.get(meu_email)
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('login'))

    user.steam_id64 = steam_id64
    persistir_usuario(user)

    jogos_importados, jogos_ja_existiam, erro_steam = importar_steam_para_biblioteca_local(meu_email)
    if jogos_importados:
        flash(f'Steam conectada e {jogos_importados} jogo(s) foram importados para sua biblioteca.', 'success')
    elif jogos_ja_existiam:
        flash('Steam conectada. Sua biblioteca local já estava sincronizada.', 'info')
    elif erro_steam:
        flash(f'Steam conectada, mas a biblioteca não pôde ser importada: {erro_steam}', 'warning')
    else:
        flash('Steam conectada, mas nenhum jogo foi importado.', 'warning')

    return redirect(url_for('perfil', email=meu_email))

@app.route('/redefinir', methods=['POST'])
def redefinir():
    email = request.form['email']
    token = request.form['token']
    nova_senha = request.form['nova_senha']
    user = USUARIOS_DB.get(email)
    if user:
        try:
            user.alterar_senha_com_token(token, nova_senha)
            flash("Senha redefinida com sucesso!", "success")
            return redirect(url_for('login'))
        except AutenticacaoError as e:
            flash(str(e), "danger")
    return redirect(url_for('recuperar'))

@app.route('/admin/smtp', methods=['GET', 'POST'])
def admin_smtp_config():
    if 'user_email' not in session or not session.get('is_admin'):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        action = (request.form.get('action') or '').strip().lower()
        if action == 'testar':
            destinatario = (request.form.get('test_destinatario') or session['user_email']).strip()
            resultado = enviar_email_teste(destinatario, background=False)
            if resultado.get('status') == 'sent':
                flash('Teste SMTP realizado com sucesso.', 'success')
            else:
                erro = resultado.get('error') or 'Falha desconhecida ao testar SMTP.'
                flash(f'Teste SMTP falhou: {erro}', 'danger')
            return redirect(url_for('admin_smtp_config'))

        values = {
            'SMTP_ENABLED': request.form.get('SMTP_ENABLED', 'true'),
            'SMTP_SERVER': request.form.get('SMTP_SERVER', ''),
            'SMTP_PORT': request.form.get('SMTP_PORT', '587'),
            'SMTP_USERNAME': request.form.get('SMTP_USERNAME', ''),
            'SMTP_PASSWORD': request.form.get('SMTP_PASSWORD', ''),
            'SMTP_TLS': request.form.get('SMTP_TLS', 'true'),
            'SMTP_SSL': request.form.get('SMTP_SSL', 'false'),
            'MAIL_FROM': request.form.get('MAIL_FROM', ''),
            'MAIL_FROM_NAME': request.form.get('MAIL_FROM_NAME', 'GameUnexa'),
            'ADMIN_SUPPORT_EMAIL': request.form.get('ADMIN_SUPPORT_EMAIL', 'gracilianoa50@gmail.com'),
        }
        update_smtp_config(values)
        flash('Configurações SMTP atualizadas.', 'success')
        return redirect(url_for('admin_smtp_config'))

    return render_template(
        'admin_smtp.html',
        config=get_smtp_config(),
        logs=listar_logs(20),
        fila=listar_fila(20),
    )


@app.route('/admin/smtp/processar')
def admin_smtp_processar():
    if 'user_email' not in session or not session.get('is_admin'):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('login'))
    processar_fila_email(10)
    flash('Fila de e-mails processada.', 'info')
    return redirect(url_for('admin_smtp_config'))


def _paginar_itens_com_metadados(itens, pagina_atual, por_pagina=6):
    itens = list(itens or [])
    total = len(itens)
    por_pagina = max(1, int(por_pagina or 1))

    if total == 0:
        return {
            'pagina_atual': 1,
            'total_paginas': 1,
            'total': 0,
            'itens_pagina': [],
            'offset': 0,
            'per_page': por_pagina,
            'tem_anterior': False,
            'tem_proxima': False,
        }

    total_paginas = max(1, (total + por_pagina - 1) // por_pagina)
    pagina = max(1, int(pagina_atual or 1))
    # If page is beyond valid range, don't force to last page - let offset naturally produce empty slice
    offset = (pagina - 1) * por_pagina
    fim = offset + por_pagina
    
    # Determine if there's a previous/next page based on the REQUESTED page number
    tem_anterior = pagina > 1
    tem_proxima = pagina < total_paginas

    return {
        'pagina_atual': pagina,
        'total_paginas': total_paginas,
        'total': total,
        'itens_pagina': itens[offset:fim],
        'offset': offset,
        'per_page': por_pagina,
        'tem_anterior': pagina > 1,
        'tem_proxima': pagina < total_paginas,
    }


def paginar_itens(itens, pagina_atual, por_pagina=6):
    metadata = _paginar_itens_com_metadados(itens, pagina_atual, por_pagina)
    return metadata['pagina_atual'], metadata['total_paginas'], metadata['total'], metadata['itens_pagina']


def _remover_registros_relacionados_usuario(email: str):
    email_normalizado = _normalizar_email(email)
    if not email_normalizado:
        return

    for chave in list(AMIZADES_DB.keys()):
        amizade = AMIZADES_DB[chave]
        if amizade.email_solicitante == email_normalizado or amizade.email_receptor == email_normalizado:
            del AMIZADES_DB[chave]

    for chave in list(BIBLIOTECA_DB.keys()):
        if chave.startswith(f'{email_normalizado}_'):
            del BIBLIOTECA_DB[chave]

    for chave in list(REVIEWS_DB.keys()):
        if REVIEWS_DB[chave].email_usuario == email_normalizado:
            del REVIEWS_DB[chave]

    REVIEW_COMENTARIOS_DB[:] = [item for item in REVIEW_COMENTARIOS_DB if item.email_usuario != email_normalizado]

    for post_id, post in list(POSTS_DB.items()):
        if post.autor_email == email_normalizado:
            del POSTS_DB[post_id]
        else:
            post.usuarios_curtidas = [usuario for usuario in post.usuarios_curtidas if usuario != email_normalizado]

    COMENTARIOS_POSTS_DB[:] = [item for item in COMENTARIOS_POSTS_DB if item.autor_email != email_normalizado]
    NOTIFICACOES_DB.pop(email_normalizado, None)
    MENSAGENS_DB[:] = [item for item in MENSAGENS_DB if item.email_remetente != email_normalizado and item.email_destino != email_normalizado]
    ONLINE_USERS.discard(email_normalizado)
    USUARIOS_DB.pop(email_normalizado, None)


# --- Rotas de Dashboard e Jogos ---
def _sincronizar_status_dashboard_background(email: str) -> None:
    try:
        user = USUARIOS_DB.get(_normalizar_email(email))
        if not user:
            return
        _hydra_atualizar_status_local(user)
        persistir_usuario(user)
        ultimo_update = getattr(user, 'steam_last_update', None)
        deve_sincronizar = not ultimo_update
        if ultimo_update:
            try:
                deve_sincronizar = datetime.now() - datetime.fromisoformat(ultimo_update) > timedelta(seconds=60)
            except Exception:
                deve_sincronizar = True
        if getattr(user, 'steam_id64', '') and deve_sincronizar:
            sincronizar_status_steam(email)
    except Exception as erro:
        print(f'[Dashboard Background] erro ao sincronizar status: {erro}')


@app.route('/dashboard')
def dashboard():
    if 'user_email' not in session: 
        return redirect(url_for('login'))
    
    meu_email = session['user_email']
    # Status Steam/Hydra é atualizado depois da resposta para não bloquear login/dashboard.
    Thread(target=_sincronizar_status_dashboard_background, args=(meu_email,), daemon=True).start()
    jogos = list(JOGOS_DB.values())
    capas_usadas: set[str] = set()
    for jogo in jogos:
        jogo.capa_url = _capa_para_jogo_catalogo(jogo, capas_usadas, permitir_remoto=False)
        jogo.capa_fallback = _capa_fallback(jogo.titulo)

    pagina_atual, total_paginas, total_jogos, jogos_pagina = paginar_itens(
        jogos,
        request.args.get('pagina', 1, type=int),
        6,
    )

    posts_visiveis = {k: v for k, v in POSTS_DB.items() if v.visivel}
    comentarios_visiveis = [c for c in COMENTARIOS_POSTS_DB if c.visivel]
    notif_list = GerenciadorNotificacoes.obter_notificacoes(meu_email)
    notif_nao_lidas = GerenciadorNotificacoes.contar_nao_lidas(meu_email)
    biblioteca_cards_todos = montar_biblioteca_cards(meu_email)
    _agendar_capas_biblioteca(meu_email)
    totais_por_origem = {
        origem: sum(1 for card in biblioteca_cards_todos if card.get('origem') == origem)
        for origem in ('steam', 'hydra', 'manual')
    }
    biblioteca_pagina_atual, biblioteca_total_paginas, _, biblioteca_cards = paginar_itens(
        biblioteca_cards_todos,
        request.args.get('biblioteca_pagina', 1, type=int),
        6,
    )

    def biblioteca_paginacao_url(pagina):
        return url_for('dashboard', foco='biblioteca', biblioteca_pagina=pagina)

    contexto_amigos = montar_amigos_contexto(meu_email)
    amigos_ativos = [amigo for amigo in contexto_amigos['amigos'] if esta_online(amigo.email)]
    sugestoes_contexto = montar_sugestoes_contexto(meu_email, '', 1, 3)

    return render_template(
        'dashboard.html', 
        jogos=jogos,
        jogos_pagina=jogos_pagina,
        pagina_atual=pagina_atual,
        total_paginas=total_paginas,
        total_jogos=total_jogos,
        usuarios=USUARIOS_DB, 
        posts=posts_visiveis, 
        comentarios_posts=comentarios_visiveis, 
        notif_nao_lidas=notif_nao_lidas,
        notificacoes=notif_list,
        biblioteca_cards=biblioteca_cards,
        total_biblioteca=len(biblioteca_cards_todos),
        totais_por_origem=totais_por_origem,
        biblioteca_pagina_atual=biblioteca_pagina_atual,
        biblioteca_total_paginas=biblioteca_total_paginas,
        biblioteca_paginacao_url=biblioteca_paginacao_url,
        amigos=contexto_amigos['amigos'],
        amigos_ativos=amigos_ativos,
        amigos_emails=contexto_amigos['amigos_emails'],
        solicitacoes_pendentes=contexto_amigos['pendentes'],
        usuarios_sugeridos=contexto_amigos['sugeridos'],
        sugestoes_pagina=sugestoes_contexto['sugestoes'],
        sugestoes_pagina_atual=sugestoes_contexto['pagina_atual'],
        sugestoes_total_paginas=sugestoes_contexto['total_paginas'],
        sugestoes_total=sugestoes_contexto['total'],
        sugestoes_total_usuarios=sugestoes_contexto['total_usuarios_sugeridos'],
        sugestoes_termo=sugestoes_contexto['termo'],
        sugestoes_mode='dashboard',
        sugestoes_per_page=sugestoes_contexto['per_page'],
        hydra_local_ativa=_hydra_local_ativo_real()
    )

@app.route('/jogos/novo', methods=['POST'])
def novo_jogo():
    if not session.get('is_admin'): 
        return redirect(url_for('dashboard'))
    try:
        novo_id = max(JOGOS_DB.keys(), default=0) + 1
        jogo = Jogo(novo_id, request.form['titulo'], request.form['genero'], request.form['desenvolvedora'], int(request.form['ano']))
        
        # Garante amarração de Categoria (RF10)
        categoria_existente = next((c for c in CATEGORIAS_DB.values() if c.nome.lower() == jogo.genero.lower()), None)
        if not categoria_existente:
            id_cat = len(CATEGORIAS_DB) + 1
            categoria_existente = Categoria(id_cat, jogo.genero)
            CATEGORIAS_DB[id_cat] = categoria_existente
            persistir_categoria(categoria_existente)
        jogo.associar_categoria(categoria_existente)
        
        JOGOS_DB[novo_id] = jogo
        persistir_jogo(jogo, [categoria_existente])
        flash("Jogo cadastrado!", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for('dashboard'))

@app.route('/jogos/deletar/<int:id>', methods=['POST'])
def deletar_jogo(id):
    if session.get('is_admin') and id in JOGOS_DB: 
        del JOGOS_DB[id]
        remover_jogo(id)
        flash("Jogo deletado!", "success")
    return redirect(url_for('dashboard'))

# --- Busca Avançada (RF13) ---
@app.route('/busca')
def busca():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    meu_email = session['user_email']
    termo = request.args.get('termo', '').lower()
    filtro = request.args.get('filtro', 'titulo')
    resultados = []

    capas_usadas: set[str] = set()
    for jogo in JOGOS_DB.values():
        if filtro == 'titulo' and termo in jogo.titulo.lower():
            resultados.append(jogo)
        elif filtro == 'genero' and termo in jogo.genero.lower():
            resultados.append(jogo)

    for jogo in resultados:
        jogo.capa_url = _capa_para_jogo_catalogo(jogo, capas_usadas, permitir_remoto=False)
        jogo.capa_fallback = _capa_fallback(jogo.titulo)

    _agendar_capas_biblioteca(meu_email)

    pagina_atual, total_paginas, total_jogos, jogos_pagina = paginar_itens(
        resultados,
        request.args.get('pagina', 1, type=int),
        6,
    )

    posts_visiveis = {k: v for k, v in POSTS_DB.items() if v.visivel}
    comentarios_visiveis = [c for c in COMENTARIOS_POSTS_DB if c.visivel]
    notif_list = GerenciadorNotificacoes.obter_notificacoes(meu_email)
    notif_nao_lidas = GerenciadorNotificacoes.contar_nao_lidas(meu_email)
    biblioteca_cards = montar_biblioteca_cards(meu_email)
    contexto_amigos = montar_amigos_contexto(meu_email)
    sugestoes_contexto = montar_sugestoes_contexto(meu_email, termo, 1, 3)

    return render_template(
        'dashboard.html',
        jogos=resultados,
        jogos_pagina=jogos_pagina,
        pagina_atual=pagina_atual,
        total_paginas=total_paginas,
        total_jogos=total_jogos,
        usuarios=USUARIOS_DB,
        posts=posts_visiveis,
        comentarios_posts=comentarios_visiveis,
        notif_nao_lidas=notif_nao_lidas,
        notificacoes=notif_list,
        biblioteca_cards=biblioteca_cards,
        amigos=contexto_amigos['amigos'],
        amigos_emails=contexto_amigos['amigos_emails'],
        solicitacoes_pendentes=contexto_amigos['pendentes'],
        usuarios_sugeridos=contexto_amigos['sugeridos'],
        sugestoes_pagina=sugestoes_contexto['sugestoes'],
        sugestoes_pagina_atual=sugestoes_contexto['pagina_atual'],
        sugestoes_total_paginas=sugestoes_contexto['total_paginas'],
        sugestoes_total=sugestoes_contexto['total'],
        sugestoes_total_usuarios=sugestoes_contexto['total_usuarios_sugeridos'],
        sugestoes_termo=sugestoes_contexto['termo'],
        busca_termo=termo,
        filtro_selecionado=filtro,
        modo_busca=True
    )

# --- Funcionalidades de Rede Social ---
@app.route('/perfil/<email>')
def perfil(email):
    if 'user_email' not in session: 
        return redirect(url_for('login'))
    user = USUARIOS_DB.get(email)
    if not user:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for('dashboard'))

    meu_email = session.get('user_email')
    if email == meu_email:
        _hydra_atualizar_status_local(user)

    amigos = GerenciadorAmigos.obter_amigos(email)
    steam_contexto = montar_steam_contexto(user, request.args.get('steam_appid', type=int))
    hydra_contexto = montar_hydra_contexto(user)
    reviews_usuario = []
    for review in GerenciadorReviews.obter_reviews_usuario(email):
        jogo = JOGOS_DB.get(review.jogo_id)
        comentarios = GerenciadorReviews.obter_comentarios_review(review.id)
        reviews_usuario.append({
            'id': review.id,
            'titulo': review.titulo,
            'conteudo': review.conteudo,
            'nota': review.nota,
            'jogo_titulo': jogo.titulo if jogo else f'Jogo #{review.jogo_id}',
            'data': review.data_criacao.strftime('%d/%m/%Y'),
            'total_comentarios': len(comentarios),
            'comentarios': [
                {
                    'id': comentario.id,
                    'autor_email': comentario.email_usuario,
                    'autor_nome': USUARIOS_DB.get(comentario.email_usuario).nome if USUARIOS_DB.get(comentario.email_usuario) else comentario.email_usuario,
                    'texto': comentario.texto,
                    'data': comentario.data_criacao.strftime('%d/%m/%Y %H:%M')
                }
                for comentario in comentarios
            ]
        })
    
    # === SISTEMA DE RELACIONAMENTO DEDICADO ===
    sao_amigos = False
    tem_solicitacao_pendente = False
    usuarios_ativos_disponiveis = []
    
    if meu_email and meu_email != email:
        sao_amigos = GerenciadorAmigos.sao_amigos(meu_email, email)
        
        solicitacoes_para_mim = GerenciadorAmigos.obter_solicitacoes_pendentes(meu_email)
        for sol in solicitacoes_para_mim:
            if sol.email_solicitante == email:
                tem_solicitacao_pendente = True
                break

    amigos_emails = set(GerenciadorAmigos.obter_amigos(meu_email)) if meu_email else set()
    pendentes_comigo = set()
    if meu_email:
        for solicitacao in AMIZADES_DB.values():
            if solicitacao.status != 'pendente':
                continue
            if solicitacao.email_solicitante == meu_email:
                pendentes_comigo.add(solicitacao.email_receptor)
            elif solicitacao.email_receptor == meu_email:
                pendentes_comigo.add(solicitacao.email_solicitante)

    if meu_email:
        usuarios_ativos_disponiveis = sorted(
            [
                usuario
                for usuario in USUARIOS_DB.values()
                if usuario.email != meu_email
                and usuario.email not in amigos_emails
                and usuario.email not in pendentes_comigo
                and esta_online(usuario.email)
            ],
            key=lambda usuario: usuario.nome.lower()
        )

    return render_template(
        'perfil.html', 
        usuario=user, 
        amigos=amigos, 
        usuarios=USUARIOS_DB, 
        jogos=list(JOGOS_DB.values()),
        comentarios=[c for c in COMENTARIOS_POSTS_DB if c.visivel],
        biblioteca_cards=montar_biblioteca_cards(email),
        reviews_usuario=reviews_usuario,
        steam_contexto=steam_contexto,
        hydra_contexto=hydra_contexto,
        hydra_local_ativa=(email == meu_email and _hydra_local_ativo_real()),
        sao_amigos=sao_amigos,
        tem_solicitacao_pendente=tem_solicitacao_pendente,
        usuarios_ativos_disponiveis=usuarios_ativos_disponiveis
    )

@app.route('/perfil/editar')
def editar_perfil():
    if 'user_email' not in session: 
        return redirect(url_for('login'))
    user = USUARIOS_DB.get(session['user_email'])
    if not user:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for('dashboard'))
    return render_template('editar_perfil.html', usuario=user)

@app.route('/perfil/salvar', methods=['POST'])
def salvar_perfil():
    if 'user_email' not in session: 
        return redirect(url_for('login'))
    user = USUARIOS_DB.get(session['user_email'])
    if not user:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for('dashboard'))

    acao = (request.form.get('acao') or 'salvar_perfil').strip()
    
    servidor_anterior = user.discord_server
    user.nome = request.form.get('nome', user.nome)
    idade_str = request.form.get('idade', '').strip()
    user.idade = int(idade_str) if idade_str else None
    user.gosto_jogos = request.form.get('gosto_jogos', '')
    user.telefone = request.form.get('telefone', '')
    user.discord_tag = request.form.get('discord_tag', '').strip()
    user.discord_server = request.form.get('discord_server', '').strip()
    user.discord_online = request.form.get('discord_online') == '1'
    if 'foto_perfil' in request.form:
        user.foto_perfil = request.form.get('foto_perfil', '').strip()
    if 'foto_perfil_upload' in request.files:
        file = request.files['foto_perfil_upload']
        if file and file.filename and allowed_file(file.filename):
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            filename = secure_filename(f"{session['user_email']}_{int(datetime.now().timestamp())}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            user.foto_perfil = f"/app-data/uploads/{filename}"
    if 'steam_id64' in request.form:
        user.steam_id64 = request.form.get('steam_id64', '').strip()
    if 'steam_api_key' in request.form:
        steam_api_key = request.form.get('steam_api_key', '').strip()
        if steam_api_key:
            user.steam_api_key = steam_api_key
    if 'hydra_account_email' in request.form:
        user.hydra_account_email = request.form.get('hydra_account_email', '').strip()
    if 'hydra_usuario' in request.form:
        user.hydra_usuario = request.form.get('hydra_usuario', '').strip()
    if 'hydra_pin' in request.form:
        user.hydra_pin = request.form.get('hydra_pin', '').strip()
    if 'hydra_token' in request.form:
        user.hydra_token = request.form.get('hydra_token', '').strip()
    
    session['user_nome'] = user.nome
    persistir_usuario(user)

    if user.discord_server and user.discord_server != servidor_anterior:
        flash("Servidor Discord configurado! Abrindo o convite...", "success")
        return redirect(user.obter_link_discord() or url_for('perfil', email=session['user_email']))

    flash("Perfil atualizado com sucesso!", "success")
    return redirect(url_for('perfil', email=session['user_email']))


@app.route('/hydra/conectar', methods=['GET', 'POST'])
@app.route('/hydra/login', methods=['GET', 'POST'])
def hydra_conectar():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))

    user = USUARIOS_DB.get(meu_email)
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('dashboard'))

    hydra_profile_id = getattr(user, 'hydra_profile_id', '') or ''
    hydra_api_base_url = getattr(user, 'hydra_api_base_url', '') or DEFAULT_HYDRA_API_BASE_URL
    hydra_account_email = _hydra_email_conta_usuario(user)
    hydra_usuario = _hydra_usuario_usuario(user)
    hydra_pin = _hydra_pin_usuario(user)
    hydra_token = _hydra_token_usuario(user)
    hydra_entrada = hydra_token or hydra_profile_id
    hydra_token_local = _hydra_token_local_detectado()

    if request.method == 'GET':
        return redirect(url_for('perfil', email=meu_email) + '#hydra-games-section')

    if request.method == 'POST':
        hydra_account_email = request.form.get('hydra_account_email', '').strip()
        hydra_usuario = request.form.get('hydra_usuario', '').strip()
        hydra_pin = request.form.get('hydra_pin', '').strip()
        hydra_token = request.form.get('hydra_entrada', '').strip() or request.form.get('hydra_token', '').strip()
        hydra_entrada = hydra_token or hydra_usuario or hydra_pin

        if not hydra_entrada:
            flash('Preencha o token Hydra ou o ID/URL do perfil.', 'warning')
        else:
            user.hydra_token = hydra_token
            user.hydra_profile_id = ''
            user.hydra_usuario = hydra_usuario
            user.hydra_pin = hydra_pin
            user.hydra_account_email = hydra_account_email
            persistir_usuario(user)
            flash('Conexão Hydra salva com sucesso.', 'success')
            return redirect(url_for('perfil', email=meu_email) + '#hydra-games-section')

    return render_template(
        'hydra_login.html',
        usuario=user,
        hydra_contexto=montar_hydra_contexto(user),
        hydra_entrada=hydra_entrada,
        hydra_token_local=hydra_token_local,
        hydra_account_email=hydra_account_email,
        hydra_usuario=hydra_usuario,
        hydra_pin=hydra_pin,
    )


@app.route('/hydra/detectar-sessao', methods=['POST'])
def hydra_detectar_sessao_local():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))

    user = USUARIOS_DB.get(meu_email)
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('hydra_conectar'))

    jogos_cacheados, display_name_cacheado = _hydra_cache_local_jogos()
    if not jogos_cacheados:
        flash('Não encontrei cache local da Hydra neste PC.', 'warning')
        return redirect(url_for('hydra_conectar'))

    jogos_para_importar = _hydra_normalizar_jogos(jogos_cacheados)

    jogos_importados, jogos_ja_existiam = _hydra_importar_contexto_para_biblioteca_local(user, {'jogos': jogos_para_importar})

    if jogos_importados:
        flash(f'Cache local da Hydra detectado. {jogos_importados} jogo(s) foram importados para sua biblioteca.', 'success')
    elif jogos_ja_existiam:
        flash('Cache local da Hydra detectado. Sua biblioteca local já estava atualizada.', 'info')
    else:
        flash('Cache local da Hydra detectado, mas nenhum jogo foi carregado para a biblioteca.', 'warning')

    return redirect(url_for('minha_biblioteca', filtro='hydra'))


@app.route('/hydra/importar', methods=['POST'])
def importar_hydra_exportacao():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))

    user = USUARIOS_DB.get(meu_email)
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('hydra_conectar'))

    arquivo = request.files.get('hydra_exportacao')
    if not arquivo or not getattr(arquivo, 'filename', ''):
        flash('Envie um arquivo JSON de exportação da Hydra.', 'warning')
        return redirect(url_for('hydra_conectar'))

    try:
        exportacao_json = arquivo.read().decode('utf-8-sig').strip()
    except UnicodeDecodeError:
        flash('A exportação Hydra precisa estar em UTF-8.', 'warning')
        return redirect(url_for('hydra_conectar'))

    if not exportacao_json:
        flash('O arquivo de exportação da Hydra está vazio.', 'warning')
        return redirect(url_for('hydra_conectar'))

    jogos_importados, jogos_ja_existiam, erro_hydra = importar_hydra_para_biblioteca_local(meu_email, exportacao_json)

    if jogos_importados:
        flash(f'{jogos_importados} jogo(s) da Hydra foram importados para sua biblioteca local.', 'success')
    elif jogos_ja_existiam:
        flash('Sua biblioteca local já tinha esses jogos da Hydra importados.', 'info')
    elif erro_hydra:
        flash(erro_hydra, 'warning')
    else:
        flash('Nenhum jogo da Hydra foi importado.', 'warning')

    return redirect(url_for('hydra_conectar'))


@app.route('/steam/sincronizar', methods=['POST'])
def sincronizar_steam():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))

    try:
        resultado = sincronizar_steam_oficial(meu_email)
    except Exception as exc:
        app.logger.warning('[Steam] sincronização falhou: %s', exc)
        resultado = {'sincronizado': False, 'erro': 'Não foi possível sincronizar a Steam agora. Verifique a configuração e a privacidade da conta.'}
    if resultado.get('sincronizado'):
        jogos_total = resultado.get('jogos_total', 0)
        flash(f'Steam sincronizada com {jogos_total} jogo(s) encontrado(s).', 'success')
    elif resultado.get('erro'):
        flash(resultado['erro'], 'warning')
    else:
        flash('Não foi possível sincronizar a Steam.', 'warning')

    return redirect(request.referrer or url_for('perfil', email=meu_email))


@app.route('/steam/sync-agora')
def sync_steam_agora():
    """Sincronização agressiva com cache busting - atualiza o status instantaneamente"""
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'erro': 'Não autenticado'}), 401

    user = USUARIOS_DB.get(_normalizar_email(meu_email))
    if not user:
        return jsonify({'erro': 'Usuário não encontrado'}), 404
    
    steam_id = _steam_id_ou_vanity_usuario(user)
    api_key = _steam_api_key_usuario(user)
    
    if steam_id and not steam_id.isdigit():
        steam_id = _steam_resolver_steamid(steam_id, api_key) or steam_id
    
    if not steam_id:
        return jsonify({'erro': 'Steam ID não configurada'}), 400
    
    try:
        perfil = obter_perfil(steam_id, api_key)
        status = obter_status(steam_id, api_key)
    except Exception as exc:
        print(f'[/steam/sync-agora] Erro oficial: {exc}')
        return jsonify({'erro': f'Erro ao consultar a Steam: {exc}'}), 500
    
    # Atualiza usuário
    user.steam_online = bool(status.get('online'))
    user.steam_current_game = status.get('game') or ''
    user.steam_current_game_appid = status.get('appid') if status.get('game') else None
    user.steam_last_update = datetime.now().isoformat()
    if perfil.get('avatar'):
        user.foto_perfil = perfil.get('avatar', '')

    _salvar_usuario_no_banco(user)
    _hydra_atualizar_status_local(user)
    
    print(f'[/steam/sync-agora] {user.email}: online={user.steam_online}, game="{user.steam_current_game}", appid={user.steam_current_game_appid}')
    
    status_panel = _montar_dados_status_panel(user, request.headers.get('User-Agent'))

    return jsonify({
        'online': user.steam_online,
        'jogo': user.steam_current_game,
        'appid': user.steam_current_game_appid,
        'atualizado_em': user.steam_last_update,
        'hydra_jogo': getattr(user, 'hydra_current_game', ''),
        'hydra_atualizado_em': getattr(user, 'hydra_last_update', None),
        'foto_perfil': getattr(user, 'foto_perfil', ''),
        'status_panel': status_panel,
    })

@app.route('/presenca/detectada')
def obter_presenca_detectada():
    """
    Retorna o estado de presença detectado automaticamente (Steam/Hydra) com dados enriquecidos.
    
    Resposta esperada pelo frontend:
    {
        "online": true,
        "steam": true,
        "hydra": false,
        "launcher": "Steam",
        "device": "Desktop",
        "ultima_atividade": "Agora",
        "tempo_online": 125,
        "necessita_sync": true
    }
    """
    import time
    
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'erro': 'Não autenticado'}), 401

    meu_email_normalizado = _normalizar_email(meu_email)
    user = USUARIOS_DB.get(meu_email_normalizado)
    if not user:
        return jsonify({'erro': 'Usuário não encontrado'}), 404

    # Reconstruir estado real a cada chamada para evitar cache/stale state
    if getattr(user, 'steam_id64', ''):
        try:
            sincronizar_status_steam(meu_email)
        except Exception as e:
            print(f'[/presenca/detectada] Erro ao sincronizar Steam: {e}')

    try:
        _hydra_sincronizar_estado_real(user)
    except Exception as e:
        print(f'[/presenca/detectada] Erro ao sincronizar Hydra: {e}')

    user = USUARIOS_DB.get(meu_email_normalizado)

    detector = obter_detector()
    if not detector:
        try:
            detector = inicializar_detector(callback_mudanca_presenca_global)
            print('[/presenca/detectada] Detector iniciado preguiçosamente no endpoint.')
        except Exception as e:
            print(f'[/presenca/detectada] Erro ao inicializar detector: {e}')

    detector_ativo = False
    steam_detectado = False
    hydra_detectado = False
    processo_jogo = ''
    jogo_nome = ''
    launcher = 'none'
    playing = False
    online = False
    launcher_icon = 'fa-solid fa-circle'

    if detector:
        try:
            estado_detector = detector.obter_estado_ao_vivo()
            steam_detectado = estado_detector.get('steam_ativo', False)
            hydra_detectado = estado_detector.get('hydra_ativo', False)
            processo_jogo = estado_detector.get('jogo_atual') or ''
            launcher_icon = estado_detector.get('launcher_icon', 'fa-solid fa-circle') or 'fa-solid fa-circle'
            detector_ativo = True
        except Exception as e:
            print(f'[/presenca/detectada] Erro ao obter estado do detector ao vivo: {e}')
            estado_detector = {}
    else:
        estado_detector = {}

    steam_game = getattr(user, 'steam_current_game', '') or ''
    steam_game_appid = getattr(user, 'steam_current_game_appid', None)
    hydra_game = getattr(user, 'hydra_current_game', '') or ''

    if processo_jogo:
        jogo_nome = processo_jogo
        playing = True
        launcher = (estado_detector.get('launcher') or 'local').lower()
    elif detector_ativo and estado_detector.get('playing') is False:
        jogo_nome = ''
        playing = False
        launcher = 'steam' if steam_detectado else 'none'
    elif steam_game:
        jogo_nome = steam_game
        playing = True
        launcher = 'steam'
    elif hydra_game:
        jogo_nome = hydra_game
        playing = True
        launcher = 'hydra'
    else:
        jogo_nome = ''
        playing = False

    if not playing:
        if steam_detectado or getattr(user, 'steam_online', False):
            launcher = 'steam'
        elif hydra_detectado or hydra_game:
            launcher = 'hydra'
        else:
            launcher = 'none'

    online = bool(playing or steam_detectado or hydra_detectado or getattr(user, 'steam_online', False) or hydra_game)
    status_value = 'online' if online else 'offline'

    # Obtém informações de atividade
    agora = datetime.now()
    ultimo_update = getattr(user, 'steam_last_update', None) or getattr(user, 'hydra_last_update', None)
    ultima_atividade = _formatar_humano_relativo(ultimo_update, agora)

    ultimo_update_iso = None
    if ultimo_update:
        if isinstance(ultimo_update, datetime):
            ultimo_update_iso = ultimo_update.isoformat()
        else:
            ultimo_update_iso = str(ultimo_update)

    # Calcula tempo online em segundos (para o frontend incrementar)
    tempo_online_segundos = 0
    if online and ultimo_update:
        if isinstance(ultimo_update, str):
            try:
                ultimo_update_dt = datetime.fromisoformat(ultimo_update.replace('Z', '+00:00'))
            except Exception:
                ultimo_update_dt = None
        else:
            ultimo_update_dt = ultimo_update

        if ultimo_update_dt:
            if ultimo_update_dt.tzinfo is not None:
                ultimo_update_dt = ultimo_update_dt.astimezone().replace(tzinfo=None)
            if agora.tzinfo is not None:
                agora = agora.astimezone().replace(tzinfo=None)
            tempo_online_segundos = max(0, int((agora - ultimo_update_dt).total_seconds()))

    # Obtém dispositivo
    device = _inferir_dispositivo(request.headers.get('User-Agent'))

    # Rastreia se necessita sincronização
    necessita_sync = False
    with _LOCK_CACHE_PRESENCA:
        cache_anterior = _CACHE_ESTADO_PRESENCA.get(meu_email_normalizado, {})
        estado_novo = {
            'steam': steam_detectado,
            'hydra': hydra_detectado,
            'playing': playing,
            'game_name': jogo_nome,
            'timestamp': time.time()
        }

        if not cache_anterior:
            necessita_sync = online
        else:
            steam_mudou = cache_anterior.get('steam', False) != steam_detectado
            hydra_mudou = cache_anterior.get('hydra', False) != hydra_detectado
            playing_mudou = cache_anterior.get('playing', False) != playing
            game_name_mudou = cache_anterior.get('game_name', '') != jogo_nome

            if steam_mudou or hydra_mudou or playing_mudou or game_name_mudou:
                necessita_sync = True

        _CACHE_ESTADO_PRESENCA[meu_email_normalizado] = estado_novo

    # Priorizar dados detectados em tempo-real (appid/path/launcher) quando disponíveis
    detected_appid = estado_detector.get('appid') if estado_detector else None
    detected_path = estado_detector.get('path') if estado_detector else None
    detected_launcher = estado_detector.get('launcher') if estado_detector else None
    detected_source = 'Steam' if str(detected_launcher or '').lower() == 'steam' else 'Local' if playing else None

    if detector_ativo:
        # Preferir valores persistidos (Steam API) quando o usuário tem game salvo, caso contrário usar detector
        appid_value = steam_game_appid if steam_game else (detected_appid if detected_appid else None)
        since_value = datetime.fromtimestamp(estado_detector.get('timestamp', time.time())).isoformat() if estado_detector else ultimo_update_iso
    else:
        appid_value = steam_game_appid if steam_game else None
        since_value = ultimo_update_iso

    session_time = 0
    started_at = since_value
    if playing and estado_detector:
        try:
            session_time = max(0, int(time.time() - float(estado_detector.get('timestamp', time.time()))))
        except Exception:
            session_time = 0

    cover_url = _resolver_capa_presenca(user, jogo_nome, appid_value, launcher) if playing else ''

    print(f'[/presenca/detectada] {meu_email}: steam={steam_detectado}, hydra={hydra_detectado}, online={online}, playing={playing}, game_name="{jogo_nome}", launcher={launcher}, status={status_value}, necessita_sync={necessita_sync}')

    game_payload = {
        'running': bool(playing and jogo_nome),
        'name': jogo_nome or None,
        'source': detected_source or ('Hydra' if playing and launcher == 'hydra' else None),
        'appid': appid_value if playing else None,
        'executable': os.path.basename(detected_path) if playing and detected_path else None,
        'path': detected_path if playing else None,
    }

    return jsonify({
        'presence': 'online' if online else 'offline',
        'game': game_payload,
        'online': online,
        'steam': steam_detectado,
        'hydra': hydra_detectado,
        'launcher': launcher,
        'status': status_value,
        'playing': playing,
        'game_name': jogo_nome,
        'appid': appid_value,
        'game_appid': appid_value,
        'game_path': detected_path,
        'game_launcher': detected_launcher or launcher,
        'since': since_value,
        'started_at': started_at,
        'session_time': session_time,
        'cover': cover_url,
        'launcher_icon': launcher_icon,
        'device': device,
        'ultima_atividade': ultima_atividade,
        'tempo_online': tempo_online_segundos,
        'necessita_sync': necessita_sync,
        'jogo': jogo_nome,
        'timestamp': time.time(),
    })


@app.route('/steam/status/sincronizar', methods=['POST'])
def sincronizar_status_steam_endpoint():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'erro': 'Não autenticado'}), 401

    try:
        sincronizar_status_steam(meu_email)
        user = USUARIOS_DB.get(_normalizar_email(meu_email))
        if user:
            _hydra_atualizar_status_local(user)
            return jsonify({
                'sucesso': True,
                'status': user.obter_status_steam(),
                'online': user.steam_online,
                'jogo': user.steam_current_game,
                'atualizado_em': user.steam_last_update,
                'hydra_jogo': user.hydra_current_game,
                'hydra_atualizado_em': user.hydra_last_update,
            })
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

    return jsonify({'erro': 'Usuário não encontrado'}), 404


@app.route('/steam/status/<email>')
def obter_status_steam_usuario(email):
    """Retorna o status da Steam de um usuário específico.
    
    🔴 CRÍTICO: SEMPRE valida contra estado REAL do sistema.
    Nunca confia apenas em dados armazenados.
    """
    email_normalizado = _normalizar_email(email)
    user = USUARIOS_DB.get(email_normalizado)

    if not user:
        return jsonify({'erro': 'Usuário não encontrado'}), 404

    # PASSO 1: Sincronizar Steam
    try:
        if getattr(user, 'steam_id64', ''):
            sincronizar_status_steam(user.email)
    except Exception as e:
        print(f'[Steam Status] Erro ao sincronizar Steam: {e}')

    # PASSO 2: Para o usuário logado, fazer validação PROFUNDA do Hydra
    is_current_user = email_normalizado == _normalizar_email(session.get('user_email'))
    if is_current_user:
        print(f'\n[Status Endpoint] Usuário logado: {email_normalizado}')
        print(f'[Status Endpoint] Fazendo validação PROFUNDA do estado real...')
        
        # VALIDAÇÃO PROFUNDA - SEMPRE
        _hydra_sincronizar_estado_real(user)
        
        # Recarrega usuário para pegar dados atualizados
        user = USUARIOS_DB.get(email_normalizado)

    # PASSO 3: Montar resposta com estado validado
    # Para usuário logado, sempre revalida Hydra
    hydra_connected = False
    if is_current_user:
        estado_real = _hydra_get_full_state_real()
        hydra_connected = estado_real['hydra_ativo']
        
        print(f'[Status Endpoint] Estado real Hydra:')
        print(f'[Status Endpoint]   Ativo: {hydra_connected}')
        print(f'[Status Endpoint]   Jogo: "{estado_real["jogo"]}"')
        print(f'[Status Endpoint]   DB agora tem: "{user.hydra_current_game}"')

    online_status = bool(
        user.steam_online
        or user.hydra_current_game
        or hydra_connected
    )

    return jsonify({
        'email': user.email,
        'nome': user.nome,
        'status': user.obter_status_geral(),
        'steam_status': user.obter_status_steam(),
        'hydra_status': user.obter_status_hydra(),
        'online': online_status,
        'jogo': user.steam_current_game,
        'appid': user.steam_current_game_appid,
        'atualizado_em': user.steam_last_update,
        'hydra_connected': hydra_connected,
        'hydra_jogo': user.hydra_current_game,
        'hydra_atualizado_em': user.hydra_last_update,
    })

@app.route('/steam/test')
def steam_test():
    """Teste simples de conexão com Steam"""
    meu_email = session.get('user_email')
    if not meu_email:
        return "Não autenticado", 401
    
    user = USUARIOS_DB.get(_normalizar_email(meu_email))
    if not user:
        return "Usuário não encontrado", 404
    
    resultado = f"""
    <h2>🔧 Teste Steam</h2>
    <p><strong>Email:</strong> {user.email}</p>
    <p><strong>Steam ID64:</strong> {user.steam_id64 or 'NÃO CONFIGURADA'}</p>
    <p><strong>Steam online:</strong> {user.steam_online}</p>
    <p><strong>Steam current_game:</strong> {user.steam_current_game}</p>
    <p><strong>Steam appid:</strong> {user.steam_current_game_appid}</p>
    <p><strong>Steam last_update:</strong> {user.steam_last_update}</p>
    
    <hr>
    <h3>Status Parseado:</h3>
    <p>{user.obter_status_steam()}</p>
    
    <hr>
    <h3>Ações:</h3>
    <form method="POST" action="/steam/status/sincronizar" style="margin: 10px 0;">
        <button type="submit" style="padding: 10px 20px; font-size: 16px;">🔄 Sincronizar Agora</button>
    </form>
    
    <a href="/steam/debug/status" style="display: inline-block; margin: 10px 0; padding: 10px 20px; background: #0066cc; color: white; text-decoration: none; border-radius: 5px;">
        📊 Ver JSON Debug
    </a>
    """
    return resultado, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/steam/debug/status')
def debug_status_steam():
    """Endpoint de debug para testar o status da Steam do usuário logado."""
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'erro': 'Não autenticado'}), 401
    
    user = USUARIOS_DB.get(_normalizar_email(meu_email))
    if not user:
        return jsonify({'erro': 'Usuário não encontrado'}), 404
    
    steam_id = _steam_id_ou_vanity_usuario(user)
    api_key = _steam_api_key_usuario(user)
    
    # Resolve Steam ID se for vanity URL
    if steam_id and not steam_id.isdigit():
        steam_id = _steam_resolver_steamid(steam_id, api_key) or steam_id
    
    if not steam_id:
        return jsonify({'erro': 'Steam ID não configurada'}), 400
    
    resultado = {
        'steam_id': steam_id,
        'has_api_key': bool(api_key),
        'status': _buscar_status_steam_usuario(steam_id, api_key, force_refresh=True),
        'requerimentos': {
            'perfil_publico': 'Seu perfil Steam precisa estar PÚBLICO',
            'visibilidade_jogo': 'A visibilidade de "Jogo em progresso" precisa estar PÚBLICA',
            'api_key': 'Uma Steam API Key melhora muito a detecção (opcional)',
        }
    }
    
    return jsonify(resultado)

@app.route('/steam/debug/resposta-bruta')
def debug_resposta_bruta_steam():
    """Mostra a resposta bruta da Steam para debug."""
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'erro': 'Não autenticado'}), 401
    
    user = USUARIOS_DB.get(_normalizar_email(meu_email))
    if not user:
        return jsonify({'erro': 'Usuário não encontrado'}), 404
    
    steam_id = _steam_id_ou_vanity_usuario(user)
    api_key = _steam_api_key_usuario(user)
    
    if steam_id and not steam_id.isdigit():
        steam_id = _steam_resolver_steamid(steam_id, api_key) or steam_id
    
    if not steam_id:
        return jsonify({'erro': 'Steam ID não configurada'}), 400
    
    # Testa conexão com a API
    resultado_api = {}
    if api_key:
        try:
            timestamp = f'&_t={int(time.time())}'
            url = (
                'https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?'
                f'key={quote(api_key)}&steamids={quote(steam_id)}&format=json{timestamp}'
            )
            dados = _steam_fetch_json(url)
            players = dados.get('response', {}).get('players', [])
            if players:
                resultado_api = {
                    'sucesso': True,
                    'player': players[0],
                    'url': url[:50] + '...'
                }
            else:
                resultado_api = {'sucesso': False, 'erro': 'Nenhum jogador encontrado'}
        except Exception as e:
            resultado_api = {'sucesso': False, 'erro': str(e)}
    
    # Testa conexão com XML
    resultado_xml = {}
    try:
        if steam_id.isdigit():
            url = f'https://steamcommunity.com/profiles/{steam_id}/?xml=1&_t={int(time.time())}'
        else:
            url = f'https://steamcommunity.com/id/{quote(steam_id)}/?xml=1&_t={int(time.time())}'
        xml_texto = _steam_fetch_text(url)
        if xml_texto and len(xml_texto) > 100:
            raiz = ET.fromstring(xml_texto)
            resultado_xml = {
                'sucesso': True,
                'gameExtraInfo': raiz.findtext('gameExtraInfo'),
                'stateMessage': raiz.findtext('stateMessage'),
                'onlineState': raiz.findtext('onlineState'),
                'gameName': raiz.findtext('gameName'),
                'url': url[:50] + '...'
            }
        else:
            resultado_xml = {'sucesso': False, 'erro': 'Resposta vazia ou muito curta'}
    except Exception as e:
        resultado_xml = {'sucesso': False, 'erro': str(e)}
    
    return jsonify({
        'steam_id': steam_id,
        'api_key_presente': bool(api_key),
        'api_resposta': resultado_api,
        'xml_resposta': resultado_xml,
        'status_processado': _buscar_status_steam_usuario(steam_id, api_key, force_refresh=True)
    })


@app.route('/steam/audit-log')
def steam_audit_log():
    """Visualizar logs de auditoria do scraping Steam (apenas para admin ou debug)"""
    # Nota: Em produção, adicione verificação de admin
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'erro': 'Não autenticado'}), 401
    
    try:
        conteudo_log = ler_log_audit()
        
        # Formata como HTML se solicitado
        if request.args.get('format') == 'html':
            html = f"""
            <html>
            <head>
                <title>Audit Log - Steam Scraping</title>
                <style>
                    body {{ font-family: monospace; background: #1e1e1e; color: #00ff00; padding: 20px; }}
                    pre {{ background: #0d0d0d; padding: 15px; border-radius: 5px; overflow-x: auto; }}
                    .error {{ color: #ff4444; }}
                    .success {{ color: #44ff44; }}
                    .info {{ color: #4488ff; }}
                    .warning {{ color: #ffaa44; }}
                    .download {{ 
                        display: inline-block; 
                        margin-bottom: 20px; 
                        padding: 10px 20px; 
                        background: #0066cc; 
                        color: white; 
                        text-decoration: none; 
                        border-radius: 5px; 
                    }}
                </style>
            </head>
            <body>
                <h1>🔍 Steam Scraping - Audit Log</h1>
                <a href="/steam/audit-log?download=1" class="download">⬇️ Download Log (TXT)</a>
                <pre>{conteudo_log}</pre>
            </body>
            </html>
            """
            return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
        
        # Download como arquivo de texto
        if request.args.get('download'):
            return conteudo_log, 200, {
                'Content-Type': 'text/plain; charset=utf-8',
                'Content-Disposition': 'attachment; filename=steam_audit.log'
            }
        
        # Retorna como JSON
        linhas = conteudo_log.split('\n')
        
        # Processa linhas para extração de dados
        resumo = {
            'total_linhas': len(linhas),
            'total_erros': sum(1 for l in linhas if '[ERROR' in l or '[CRITICAL' in l),
            'total_sucessos': sum(1 for l in linhas if '[INFO' in l),
            'etapas_registradas': sorted(list(set([
                l.split('] [')[1].split(']')[0] 
                for l in linhas 
                if '] [' in l
            ]))),
        }
        
        return jsonify({
            'sucesso': True,
            'resumo': resumo,
            'log_completo': conteudo_log,
            'urls_uteis': {
                'visualizar_html': '/steam/audit-log?format=html',
                'download_txt': '/steam/audit-log?download=1',
                'json': '/steam/audit-log'
            }
        })
    
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'erro': str(e),
            'dica': 'Nenhum log foi gerado ainda. Execute uma importação de Steam primeiro.'
        }), 404


@app.route('/steam/audit-limpar', methods=['POST'])
def steam_audit_limpar():
    """Limpa o arquivo de audit log (requer autenticação)"""
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'erro': 'Não autenticado'}), 401
    
    try:
        limpar_log_audit()
        return jsonify({
            'sucesso': True,
            'mensagem': 'Log de auditoria foi limpo com sucesso'
        })
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@app.route('/discord/abrir')
def abrir_discord():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    user = USUARIOS_DB.get(session['user_email'])
    if not user:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for('dashboard'))

    if not user.discord_server:
        flash("JITS CALL não configurado no seu perfil.", "warning")
        return redirect(url_for('perfil', email=user.email))

    user.discord_online = True
    link_discord = user.obter_link_discord()
    if link_discord:
        return redirect(link_discord)

    flash("Não foi possível abrir o Discord. Verifique o link no seu perfil.", "danger")
    return redirect(url_for('perfil', email=user.email))


def _normalizar_servidor_discord(texto: str) -> str:
    texto = (texto or '').strip()
    if not texto:
        return 'Geral'
    if 'discord.gg/' in texto:
        texto = texto.split('discord.gg/', 1)[1]
    elif 'discord.com/invite/' in texto:
        texto = texto.split('discord.com/invite/', 1)[1]
    return texto.rstrip('/').strip() or 'Geral'


def _slug_servidor_discord(texto: str) -> str:
    texto = _normalizar_servidor_discord(texto)
    slug = re.sub(r'[^a-z0-9]+', '-', texto.lower()).strip('-')
    return slug or 'geral'


@app.route('/discord/call')
def discord_call():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))

    user = USUARIOS_DB.get(meu_email)
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('dashboard'))

    app.logger.debug('[Discord Call] entrada route: user_email=%s, query=%s', meu_email, request.args.to_dict())
    servidor = _normalizar_servidor_discord(request.args.get('servidor', '') or user.discord_server or 'Geral')
    room_slug = _slug_servidor_discord(servidor)
    room_name = f'gamelink-{room_slug}'
    convite_url = url_for('discord_call', servidor=servidor, _external=True)
    session['call_room_slug'] = room_slug

    app.logger.debug('[Discord Call] user found: email=%s, discord_server=%s', user.email, user.discord_server)
    user.discord_online = True
    _registrar_presenca_call(user.email, room_slug)
    app.logger.debug('[Discord Call] room_slug=%s room_name=%s convite_url=%s', room_slug, room_name, convite_url)

    servidores_recomendados = []
    vistos = set()
    for usuario in USUARIOS_DB.values():
        servidor_usuario = _normalizar_servidor_discord(usuario.discord_server)
        if not servidor_usuario or servidor_usuario == 'Geral':
            continue
        slug_usuario = _slug_servidor_discord(servidor_usuario)
        if slug_usuario in vistos:
            continue
        vistos.add(slug_usuario)
        servidores_recomendados.append({
            'nome': servidor_usuario,
            'slug': slug_usuario,
            'convite': url_for('discord_call', servidor=servidor_usuario),
        })

    servidores_recomendados.sort(key=lambda item: item['nome'].lower())
    participantes = [
        usuario for usuario in USUARIOS_DB.values()
        if _slug_servidor_discord(_normalizar_servidor_discord(usuario.discord_server)) == room_slug
    ]
    status_call = _serializar_status_call(room_slug)
    sugestoes_contexto = montar_sugestoes_contexto(meu_email, '', 1, 4)

    return render_template(
        'discord_call.html',
        usuario=user,
        servidor=servidor,
        room_name=room_name,
        room_slug=room_slug,
        convite_url=convite_url,
        servidores_recomendados=servidores_recomendados,
        participantes=participantes,
        participantes_ativos=status_call['participantes_ativos'],
        quantidade_participantes=status_call['quantidade'],
        call_iniciada_em=status_call['call_iniciada_em'],
        tempo_decorrido=status_call['tempo_decorrido'],
        sugestoes_pagina=sugestoes_contexto['sugestoes'],
        sugestoes_pagina_atual=sugestoes_contexto['pagina_atual'],
        sugestoes_total_paginas=sugestoes_contexto['total_paginas'],
        sugestoes_total=sugestoes_contexto['total'],
        sugestoes_total_usuarios=sugestoes_contexto['total_usuarios_sugeridos'],
        sugestoes_termo=sugestoes_contexto['termo'],
        sugestoes_mode='call',
        sugestoes_per_page=sugestoes_contexto['per_page'],
        call_invite_url=convite_url,
        call_room_slug=room_slug,
        call_status_url=url_for('discord_call_status', servidor=servidor),
    )


@app.route('/discord/call/status')
def discord_call_status():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'error': 'not_logged_in'}), 401

    servidor = _normalizar_servidor_discord(request.args.get('servidor', '') or 'Geral')
    room_slug = _slug_servidor_discord(servidor)
    status_call = _serializar_status_call(room_slug)
    return jsonify({'ok': True, **status_call})


@app.route('/discord/call/presenca', methods=['POST'])
def discord_call_presenca():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'error': 'not_logged_in'}), 401

    dados = request.get_json(silent=True) or {}
    room_slug = _slug_servidor_discord(dados.get('room_slug') or '')
    sala_da_sessao = session.get('call_room_slug')
    if not room_slug or not sala_da_sessao or room_slug != sala_da_sessao:
        app.logger.warning('[Discord Call] presença rejeitada: room_slug=%s, sala_da_sessao=%s', room_slug, sala_da_sessao)
        return jsonify({'ok': False, 'error': 'invalid_room'}), 400
    _registrar_presenca_call(meu_email, room_slug)

    user = USUARIOS_DB.get(meu_email)
    if user:
        user.discord_online = True

    return jsonify({'ok': True})


@app.route('/discord/call/sair', methods=['POST'])
def discord_call_sair():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'error': 'not_logged_in'}), 401

    _remover_presenca_call(meu_email)
    app.logger.debug('[Discord Call] saída: user_email=%s, room_slug=%s', meu_email, session.get('call_room_slug'))
    session.pop('call_room_slug', None)
    user = USUARIOS_DB.get(meu_email)
    if user:
        user.discord_online = False

    return jsonify({'ok': True})


@sock.route('/ws/soundboard')
def soundboard_signaling(ws):
    email = session.get('user_email')
    room_slug = session.get('call_room_slug')
    if not email or not room_slug:
        ws.send(json.dumps({'type': 'error', 'message': 'Sessão de Soundboard inválida.'}))
        return

    peer_id = _normalizar_email(email)
    with SOUNDBOARD_SIGNALING_LOCK:
        room = SOUNDBOARD_SIGNALING_ROOMS.setdefault(room_slug, {})
        existing_peers = list(room.keys())
        room[peer_id] = ws

    def send_message(target_ws, payload):
        try:
            target_ws.send(json.dumps(payload, ensure_ascii=False))
            return True
        except Exception:
            return False

    send_message(ws, {'type': 'room-state', 'roomId': room_slug, 'selfId': peer_id, 'peers': existing_peers})
    with SOUNDBOARD_SIGNALING_LOCK:
        peers_snapshot = list(SOUNDBOARD_SIGNALING_ROOMS.get(room_slug, {}).items())
    for other_id, other_ws in peers_snapshot:
        if other_id != peer_id:
            send_message(other_ws, {'type': 'peer-joined', 'roomId': room_slug, 'peerId': peer_id})

    try:
        while True:
            raw_message = ws.receive()
            if raw_message is None:
                break
            try:
                message = json.loads(raw_message)
            except (TypeError, ValueError):
                send_message(ws, {'type': 'error', 'message': 'Mensagem de sinalização inválida.'})
                continue
            if message.get('roomId') != room_slug or message.get('to') == peer_id:
                continue
            target_id = message.get('to')
            if not target_id:
                continue
            with SOUNDBOARD_SIGNALING_LOCK:
                target_ws = SOUNDBOARD_SIGNALING_ROOMS.get(room_slug, {}).get(target_id)
            if target_ws:
                payload = {key: message[key] for key in ('type', 'roomId', 'from', 'description', 'candidate', 'effectId', 'timestamp') if key in message}
                payload['from'] = peer_id
                send_message(target_ws, payload)
    finally:
        with SOUNDBOARD_SIGNALING_LOCK:
            room = SOUNDBOARD_SIGNALING_ROOMS.get(room_slug, {})
            if room.get(peer_id) is ws:
                room.pop(peer_id, None)
            remaining_peers = list(room.items())
            if not room:
                SOUNDBOARD_SIGNALING_ROOMS.pop(room_slug, None)
        for _, other_ws in remaining_peers:
            send_message(other_ws, {'type': 'peer-left', 'roomId': room_slug, 'peerId': peer_id})

@app.route('/mensagens')
def mensagens():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))

    amigos = []
    for amigo_email in GerenciadorAmigos.obter_amigos(meu_email):
        usuario = USUARIOS_DB.get(amigo_email)
        if not usuario:
            continue
        amigos.append({
            'email': amigo_email,
            'nome': getattr(usuario, 'nome', amigo_email),
            'foto_perfil': getattr(usuario, 'foto_perfil', ''),
            'status': 'Online' if getattr(usuario, 'steam_online', False) or getattr(usuario, 'discord_online', False) else 'Offline',
        })

    conversas = []
    notificacoes = GerenciadorNotificacoes.obter_notificacoes(meu_email, nao_lidas_apenas=True)
    for amigo in amigos:
        mensagens = GerenciadorMensagens.obter_conversa(meu_email, amigo['email'])
        ultima = mensagens[-1] if mensagens else None
        unread_count = sum(
            1
            for notif in notificacoes
            if notif.tipo == 'mensagem' and str(notif.link or '').endswith(f"/{amigo['email']}")
        )
        if ultima:
            if ultima.data_envio.date() == datetime.now().date():
                horario = ultima.data_envio.strftime('%H:%M')
            elif ultima.data_envio.date() == (datetime.now().date() - timedelta(days=1)):
                horario = 'Ontem'
            else:
                horario = ultima.data_envio.strftime('%d/%m')
            ultima_texto = ultima.conteudo if getattr(ultima, 'conteudo', '').strip() else '📎 Anexo'
        else:
            horario = ''
            ultima_texto = 'Nenhuma mensagem ainda'

        conversas.append({
            'email': amigo['email'],
            'nome': amigo['nome'],
            'foto_perfil': amigo['foto_perfil'],
            'status': amigo['status'],
            'ultima_texto': ultima_texto,
            'horario': horario,
            'unread_count': unread_count,
            'ultima_data': ultima.data_envio if ultima else None,
        })

    conversas.sort(key=lambda item: item['ultima_data'] or datetime.min, reverse=True)
    return render_template('mensagens.html', amigos=amigos, conversas=conversas, usuarios=USUARIOS_DB)


@app.route('/conversa/<email_amigo>')
def conversa(email_amigo):
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))
    if not GerenciadorAmigos.sao_amigos(meu_email, email_amigo):
        flash("Você só pode conversar com amigos.", "danger")
        return redirect(url_for('perfil', email=email_amigo))

    amigo = USUARIOS_DB.get(email_amigo)
    if not amigo:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for('dashboard'))

    mensagens = GerenciadorMensagens.obter_conversa(meu_email, email_amigo)
    return render_template('conversa.html', amigo=amigo, mensagens=mensagens, usuarios=USUARIOS_DB)


@app.route('/conversa/<email_amigo>/mensagens')
def listar_mensagens(email_amigo):
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'error': 'not_logged_in'}), 401

    if not GerenciadorAmigos.sao_amigos(meu_email, email_amigo):
        return jsonify({'ok': False, 'error': 'not_friends'}), 403

    since_id = request.args.get('since_id', type=int)
    mensagens = GerenciadorMensagens.obter_conversa(meu_email, email_amigo)
    if since_id is not None:
        mensagens = [m for m in mensagens if m.id > since_id]

    return jsonify({'ok': True, 'mensagens': [m.serializar() for m in mensagens]})


@app.route('/conversa/<email_destino>/enviar', methods=['POST'])
def enviar_mensagem(email_destino):
    meu_email = session.get('user_email')
    if not meu_email:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'error': 'not_logged_in'}), 401
        return redirect(url_for('login'))

    if not GerenciadorAmigos.sao_amigos(meu_email, email_destino):
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'error': 'not_friends'}), 403
        flash("Você só pode enviar mensagens para amigos.", "danger")
        return redirect(url_for('perfil', email=email_destino))

    payload = request.get_json(silent=True) or {}
    form_data = request.form or {}
    conteudo = (payload.get('conteudo') or form_data.get('conteudo') or '').strip()
    reply_to_id = payload.get('reply_to_id') or form_data.get('reply_to_id')
    reply_to_conteudo = payload.get('reply_to_conteudo') or form_data.get('reply_to_conteudo')

    anexo_image = request.files.get('imagem') if request.files else None
    anexo_file = request.files.get('anexo') if request.files else None
    anexo_data = None

    if anexo_image and getattr(anexo_image, 'filename', ''):
        anexo_data = _salvar_anexo_chat(anexo_image, 'image')
    elif anexo_file and getattr(anexo_file, 'filename', ''):
        anexo_data = _salvar_anexo_chat(anexo_file, 'file')

    if not conteudo and not anexo_data:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'error': 'empty_message'}), 400
        flash("Mensagem não pode ser vazia.", "danger")
        return redirect(url_for('conversa', email_amigo=email_destino))

    pending_entry = _criar_mensagem_pendente(
        meu_email=meu_email,
        email_destino=email_destino,
        conteudo=conteudo or '📎 Anexo enviado',
        reply_to_id=reply_to_id,
        reply_to_conteudo=reply_to_conteudo,
        anexo_data=anexo_data,
    )
    mensagem = _finalizar_envio_pendente(pending_entry['id'])
    if not mensagem:
        return jsonify({'ok': False, 'error': 'send_failed'}), 500

    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'mensagem': mensagem.serializar()})

    flash("Mensagem enviada!", "success")
    return redirect(url_for('conversa', email_amigo=email_destino))


@app.route('/conversa/<email_amigo>/mensagem/pendente/<pending_id>/cancelar', methods=['POST'])
def cancelar_mensagem_pendente(email_amigo, pending_id):
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'error': 'not_logged_in'}), 401

    if not GerenciadorAmigos.sao_amigos(meu_email, email_amigo):
        return jsonify({'ok': False, 'error': 'not_friends'}), 403

    cancelled = _cancelar_mensagem_pendente(pending_id)
    return jsonify({'ok': cancelled, 'cancelled': cancelled})


@app.route('/conversa/<email_amigo>/mensagens/pendentes')
def listar_mensagens_pendentes(email_amigo):
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'error': 'not_logged_in'}), 401

    if not GerenciadorAmigos.sao_amigos(meu_email, email_amigo):
        return jsonify({'ok': False, 'error': 'not_friends'}), 403

    with PENDING_CHAT_LOCK:
        pendentes = [
            {
                'id': value['id'],
                'conteudo': value['conteudo'],
                'email_destino': value['email_destino'],
                'status': value['status'],
            }
            for value in PENDING_CHAT_MESSAGES.values()
            if value.get('email_remetente') == meu_email and value.get('email_destino') == email_amigo
        ]
    return jsonify({'ok': True, 'pendentes': pendentes})


@app.route('/conversa/<email_amigo>/mensagem/<int:mensagem_id>/cancelar', methods=['POST'])
def cancelar_mensagem(email_amigo, mensagem_id):
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'error': 'not_logged_in'}), 401

    if not GerenciadorAmigos.sao_amigos(meu_email, email_amigo):
        return jsonify({'ok': False, 'error': 'not_friends'}), 403

    mensagem = next((m for m in MENSAGENS_DB if m.id == mensagem_id and {m.email_remetente, m.email_destino} == {meu_email, email_amigo}), None)
    if not mensagem:
        return jsonify({'ok': False, 'error': 'message_not_found'}), 404

    try:
        mensagem.cancelar(meu_email)
    except OperacaoInvalidaError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 403

    persistir_mensagem(mensagem)
    return jsonify({'ok': True, 'mensagem': mensagem.serializar(meu_email), 'message_text': 'Você cancelou esta mensagem.' if mensagem.email_remetente == meu_email else 'Esta mensagem foi cancelada.'})


@app.route('/conversa/<email_amigo>/mensagem/<int:mensagem_id>/reagir', methods=['POST'])
def reagir_mensagem(email_amigo, mensagem_id):
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'error': 'not_logged_in'}), 401

    if not GerenciadorAmigos.sao_amigos(meu_email, email_amigo):
        return jsonify({'ok': False, 'error': 'not_friends'}), 403

    payload = request.get_json(silent=True) or request.form or {}
    emoji = (payload.get('emoji') or '').strip()
    if not emoji:
        return jsonify({'ok': False, 'error': 'missing_emoji'}), 400

    mensagem = next((m for m in MENSAGENS_DB if m.id == mensagem_id and {m.email_remetente, m.email_destino} == {meu_email, email_amigo}), None)
    if not mensagem:
        return jsonify({'ok': False, 'error': 'message_not_found'}), 404

    persistir_mensagem(mensagem)

    reacao_anterior = mensagem.reacoes_por_usuario.get(meu_email.lower())
    remover = reacao_anterior == emoji
    if remover:
        mensagem.reacoes_por_usuario.pop(meu_email.lower(), None)
        mensagem.reacoes[emoji] = mensagem.reacoes.get(emoji, 0) - 1
        if mensagem.reacoes[emoji] <= 0:
            del mensagem.reacoes[emoji]
        persistir_reacao_mensagem(mensagem.id, meu_email.lower(), emoji, remover=True)
    else:
        if reacao_anterior:
            mensagem.reacoes[reacao_anterior] = mensagem.reacoes.get(reacao_anterior, 0) - 1
            if mensagem.reacoes[reacao_anterior] <= 0:
                del mensagem.reacoes[reacao_anterior]
        mensagem.reacoes_por_usuario[meu_email.lower()] = emoji
        mensagem.reacoes[emoji] = mensagem.reacoes.get(emoji, 0) + 1
        persistir_reacao_mensagem(mensagem.id, meu_email.lower(), emoji, remover=False)

    return jsonify({'ok': True, 'mensagem': mensagem.serializar(meu_email)})

@app.route('/amizade/adicionar/<email_alvo>')
def adicionar_amigo(email_alvo):
    meu_email = session.get('user_email')
    email_alvo = _normalizar_email(email_alvo)
    if not meu_email or meu_email == email_alvo:
        return redirect(url_for('dashboard'))
    try:
        # 1. Envia a solicitação de amizade
        id_solicitacao = max([s.id for s in AMIZADES_DB.values()], default=0) + 1
        amizade = GerenciadorAmigos.enviar_solicitacao(id_solicitacao, meu_email, email_alvo)
        persistir_amizade(amizade)
        
        # Criamos um ID incremental para a notificação buscar de todas as listas de usuários
        todas_notifs = [n for lista in NOTIFICACOES_DB.values() for n in lista]
        id_notif = max([n.id for n in todas_notifs], default=0) + 1
        
        GerenciadorNotificacoes.criar_notificacao(
            id_notif=id_notif,
            email_receptor=email_alvo,       # Quem recebe é o alvo
            tipo='amizade',                  # Tipo esperado pelo seu html
            titulo='👥 Nova Solicitação de Amizade!',
            descricao=f'{meu_email} enviou um pedido de amizade para você.',
            link=f'/amizade/aceitar/{meu_email}' # Link direto para aceitar a solicitação
        )
        for notif in NOTIFICACOES_DB.get(email_alvo, []):
            if notif.id == id_notif:
                persistir_notificacao(notif)
                break

        flash("Solicitação de amizade enviada!", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for('perfil', email=email_alvo))

@app.route('/amizade/aceitar/<email_amigo>')
def aceitar_amizade(email_amigo):
    meu_email = session.get('user_email')
    email_amigo = _normalizar_email(email_amigo)
    if not meu_email: 
        return redirect(url_for('login'))
    try:
        GerenciadorAmigos.aceitar_solicitacao(meu_email, email_amigo)
        chave = f"{min(meu_email, email_amigo)}_{max(meu_email, email_amigo)}"
        if chave in AMIZADES_DB:
            persistir_amizade(AMIZADES_DB[chave])
        
        # Criação correta do Objeto de Notificação
        todas_notifs = [n for lista in NOTIFICACOES_DB.values() for n in lista]
        id_notif = max([n.id for n in todas_notifs], default=0) + 1
        
        GerenciadorNotificacoes.criar_notificacao(
            id_notif=id_notif,
            email_receptor=email_amigo,
            tipo='amizade',
            titulo='🤝 Solicitação Aceita!',
            descricao=f'{session.get("user_nome")} aceitou o seu pedido de amizade. Agora vocês são amigos!',
            link=f'/perfil/{meu_email}'
        )
        for notif in NOTIFICACOES_DB.get(email_amigo, []):
            if notif.id == id_notif:
                persistir_notificacao(notif)
                break

        flash("Amizade aceita!", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for('perfil', email=email_amigo)) # Redireciona de volta para o perfil do seu novo amigo

@app.route('/amizade/recusar/<email_amigo>')
def recusar_amizade(email_amigo):
    meu_email = session.get('user_email')
    email_amigo = _normalizar_email(email_amigo)
    if not meu_email: 
        return redirect(url_for('login'))
    try:
        GerenciadorAmigos.recusar_solicitacao(meu_email, email_amigo)
        chave = f"{min(meu_email, email_amigo)}_{max(meu_email, email_amigo)}"
        if chave in AMIZADES_DB:
            persistir_amizade(AMIZADES_DB[chave])
        flash("Solicitação recusada!", "info")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for('perfil', email=email_amigo)) #Mantém no perfil

@app.route('/amizade/remover/<email_amigo>')
def remover_amigo(email_amigo):
    meu_email = session.get('user_email')
    email_amigo = _normalizar_email(email_amigo)
    if not meu_email: 
        return redirect(url_for('login'))
    try:
        GerenciadorAmigos.recusar_solicitacao(meu_email, email_amigo)
        remover_amizade(meu_email, email_amigo)
        flash("Amigo removido!", "info")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for('perfil', email=email_amigo)) 

# --- Rotas de Biblioteca Pessoal ---
@app.route('/biblioteca/adicionar/<int:jogo_id>')
def adicionar_biblioteca(jogo_id):
    meu_email = session.get('user_email')
    if not meu_email: 
        return redirect(url_for('login'))
    try:
        id_biblioteca = max([b.id for b in BIBLIOTECA_DB.values()], default=0) + 1
        item = GerenciadorBiblioteca.adicionar_jogo(id_biblioteca, meu_email, jogo_id)
        persistir_biblioteca_item(item)
        flash("Jogo adicionado à biblioteca!", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for('dashboard', foco='biblioteca'))

@app.route('/biblioteca/remover/<int:jogo_id>')
def remover_biblioteca(jogo_id):
    meu_email = session.get('user_email')
    if not meu_email: 
        return redirect(url_for('login'))
    try:
        GerenciadorBiblioteca.remover_jogo(meu_email, jogo_id)
        remover_biblioteca_item(meu_email, jogo_id)
        flash("Jogo removido da biblioteca!", "info")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/biblioteca/avaliar/<int:jogo_id>', methods=['POST'])
def avaliar_biblioteca(jogo_id):
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))
    nota = request.form.get('nota', '0.0')
    comentario = request.form.get('comentario', '').strip()
    try:
        nota = float(nota)
        item = GerenciadorBiblioteca.atualizar_avaliacao(meu_email, jogo_id, nota, comentario)
        persistir_biblioteca_item(item)
        if comentario:
            flash(f"Avaliação atualizada para {nota:.1f} estrelas com comentário!", "success")
        else:
            flash(f"Avaliação atualizada para {nota:.1f} estrelas!", "success")
    except Exception as e:
        flash(f"Erro ao avaliar: {str(e)}", "danger")
    return redirect(request.referrer or url_for('biblioteca'))


@app.route('/steam/importar-biblioteca', methods=['POST'])
def importar_biblioteca_steam():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))

    user = USUARIOS_DB.get(meu_email)
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('biblioteca'))

    jogos_importados, jogos_ja_existiam, erro_steam = importar_steam_para_biblioteca_local(meu_email)

    if jogos_importados:
        flash(f'{jogos_importados} jogo(s) da Steam foram importados para sua biblioteca local.', 'success')
    elif jogos_ja_existiam:
        flash('Sua biblioteca local já tinha os jogos da Steam importados.', 'info')
    elif erro_steam:
        flash(erro_steam, 'warning')
    else:
        flash('Nenhum jogo da Steam foi importado.', 'warning')

    return redirect(request.referrer or url_for('biblioteca'))

def _render_biblioteca_view(meu_email: str, launcher: str | None = None, filtro: str = 'all'):
    biblioteca_cards_todos = montar_biblioteca_cards(meu_email, launcher)
    _agendar_capas_biblioteca(meu_email)
    biblioteca_cards_gerais = montar_biblioteca_cards(meu_email)
    total_biblioteca_geral = len(biblioteca_cards_gerais)
    totais_por_origem = {
        origem: sum(1 for card in biblioteca_cards_gerais if card.get('origem') == origem)
        for origem in ('steam', 'hydra', 'manual')
    }
    busca = request.args.get('busca', request.args.get('search', '')).strip().lower()
    if busca:
        biblioteca_cards_todos = [
            card for card in biblioteca_cards_todos
            if any(
                busca in str(valor or '').lower()
                for valor in (
                    getattr(card['jogo'], 'titulo', ''),
                    getattr(card['jogo'], 'genero', ''),
                    card.get('origem', ''),
                )
            )
        ]
    por_pagina = 10
    pagina_atual = max(1, request.args.get('pagina', 1, type=int) or 1)
    total_itens = len(biblioteca_cards_todos)
    total_paginas = (total_itens + por_pagina - 1) // por_pagina if total_itens else 0
    if total_paginas and pagina_atual > total_paginas:
        pagina_atual = total_paginas
    inicio = (pagina_atual - 1) * por_pagina
    biblioteca_cards = biblioteca_cards_todos[inicio:inicio + por_pagina]
    def biblioteca_paginacao_url(pagina):
        return url_for(request.endpoint or 'minha_biblioteca', filtro=filtro, busca=busca, pagina=pagina)

    steam_contexto = montar_steam_contexto(USUARIOS_DB.get(meu_email))
    contexto = dict(
        biblioteca_cards=biblioteca_cards,
        jogos=JOGOS_DB,
        usuarios=USUARIOS_DB,
        steam_contexto=steam_contexto,
        filtro=filtro,
        biblioteca_busca=busca,
        total_biblioteca=total_itens,
        total_biblioteca_geral=total_biblioteca_geral,
        totais_por_origem=totais_por_origem,
        pagina_atual=pagina_atual,
        total_paginas=total_paginas,
        biblioteca_paginacao_url=biblioteca_paginacao_url,
    )
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('ajax') == '1':
        return render_template('_biblioteca_conteudo.html', **contexto)
    return render_template('biblioteca.html', **contexto)

@app.route('/biblioteca/todos')
def biblioteca_todos():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))
    return _render_biblioteca_view(meu_email, None, 'all')

@app.route('/biblioteca/steam')
def biblioteca_steam():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))
    return _render_biblioteca_view(meu_email, 'steam', 'steam')

@app.route('/biblioteca/hydra')
def biblioteca_hydra():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))
    return _render_biblioteca_view(meu_email, 'hydra', 'hydra')

@app.route('/biblioteca/manual')
def biblioteca_manual():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))
    return _render_biblioteca_view(meu_email, 'manual', 'manual')

@app.route('/biblioteca')
def minha_biblioteca():
    meu_email = session.get('user_email')
    if not meu_email: 
        return redirect(url_for('login'))
    filtro = request.args.get('filtro', 'all').strip().lower()
    launcher_filter = filtro if filtro in {'steam', 'hydra', 'manual'} else None
    return _render_biblioteca_view(meu_email, launcher_filter, filtro)

@app.route('/jogar')
def jogar():
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))
    cards = _montar_cards_jogar(meu_email)
    _agendar_capas_biblioteca(meu_email)
    user = USUARIOS_DB.get(meu_email)
    requested_view = (request.args.get('view') or '').strip().lower()
    library_view = requested_view if requested_view in {'2d', '3d'} else (getattr(user, 'library_view', '3d') if user else '3d')
    if library_view == '3d':
        games_data = _montar_games_data_jogar(cards)
        return render_template('biblioteca_de_jogos_3d_definitiva.html', cards=cards, games_data=games_data, user=user, library_view=library_view)
    return render_template('jogar.html', cards=cards, jogos=JOGOS_DB, usuarios=USUARIOS_DB, steam_contexto={}, user=user)


@app.route('/jogar/dados')
def dados_biblioteca_jogar():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'}), 401
    cards = _montar_cards_jogar(meu_email)
    _agendar_capas_biblioteca(meu_email)
    return jsonify({'ok': True, 'games': _montar_games_data_jogar(cards), 'total': len(cards)})


@app.route('/api/games/<int:game_id>/stats')
def api_game_stats(game_id: int):
    email = session.get('user_email')
    if not email:
        return jsonify({'success': False, 'message': 'Não autenticado'}), 401

    item = next(
        (registro for registro in GerenciadorBiblioteca.obter_biblioteca(email)
         if int(getattr(registro, 'jogo_id', 0) or 0) == game_id),
        None,
    )
    jogo = JOGOS_DB.get(game_id)
    if not item or not jogo:
        return jsonify({'success': False, 'message': 'Jogo não encontrado'}), 404

    origem = (getattr(item, 'launcher', '') or getattr(item, 'origem', '') or 'manual').strip().lower()
    if origem == 'manual' and (getattr(jogo, 'desenvolvedora', '') or '').strip().lower() == 'steam' and str(getattr(jogo, 'id', '')).isdigit():
        origem = 'steam'
    if origem != 'steam':
        minutos_locais = int(getattr(item, 'tempo_jogado_horas', 0) or 0) * 60
        total_local = int(getattr(item, 'conquistas_total', 0) or 0)
        desbloqueadas_locais = min(
            int(getattr(item, 'conquistas_desbloqueadas', 0) or 0),
            total_local,
        ) if total_local else None
        tem_playtime_local = bool(getattr(item, 'tempo_jogado_horas', 0) is not None and minutos_locais > 0)
        tem_stats_locais = tem_playtime_local or total_local > 0
        return jsonify({
            'success': True,
            'game_id': game_id,
            'source': origem or 'local',
            'playtime': {
                'minutes': minutos_locais,
                'formatted': formatar_playtime(minutos_locais),
            } if tem_playtime_local else None,
            'achievements': {
                'unlocked': desbloqueadas_locais,
                'total': total_local,
                'percentage': round((desbloqueadas_locais / total_local) * 100, 1),
            } if total_local else None,
            'last_played': getattr(item, 'last_launched_at', None).isoformat(timespec='seconds') if getattr(item, 'last_launched_at', None) else None,
            'sync_status': 'local_record' if tem_stats_locais else 'unsupported_platform',
            'message': None if tem_stats_locais else 'Estatísticas não disponíveis para esta plataforma',
        })

    appid_text = str(getattr(item, 'codigo_origem', '') or '').strip()
    appid = int(appid_text) if appid_text.isdigit() else (int(jogo.id) if str(getattr(jogo, 'id', '')).isdigit() else None)
    user = USUARIOS_DB.get(email)
    steam_id64 = str(getattr(user, 'steam_id64', '') or '').strip() if user else ''
    api_key = _steam_api_key_usuario(user) if user else os.environ.get('STEAM_API_KEY', '').strip()
    if not appid:
        return jsonify({
            'success': True,
            'game_id': game_id,
            'source': 'steam',
            'playtime': None,
            'achievements': None,
            'last_played': None,
            'sync_status': 'missing_appid',
            'message': 'Steam AppID indisponível',
        })

    force_refresh = request.args.get('refresh') == '1'
    stats = obter_estatisticas_jogo(steam_id64, api_key, appid, force_refresh=force_refresh)
    minutos = stats.get('playtime_minutes')
    conquistas = stats.get('achievements')
    return jsonify({
        'success': True,
        'game_id': game_id,
        'source': 'steam',
        'steam_appid': appid,
        'playtime': {
            'minutes': minutos,
            'formatted': formatar_playtime(minutos),
        } if minutos is not None else None,
        'achievements': conquistas,
        'last_played': None,
        'sync_status': stats.get('status', 'unavailable'),
        'message': (
            'Steam indisponível temporariamente; exibindo a última sincronização válida'
            if stats.get('stale')
            else (None if minutos is not None or conquistas is not None else 'Dados indisponíveis')
        ),
        'updated_at': datetime.now().isoformat(timespec='seconds'),
    })

@app.route('/api/library/covers')
def api_library_covers():
    email = session.get('user_email')
    if not email:
        return jsonify({'ok': False, 'erro': 'Não autenticado'}), 401

    requested_ids = {
        int(value)
        for value in request.args.get('ids', '').split(',')
        if value.strip().isdigit()
    }
    if not requested_ids:
        return jsonify({'ok': True, 'covers': {}})

    items_by_game = {
        getattr(item, 'jogo_id', 0): item
        for item in GerenciadorBiblioteca.obter_biblioteca(email)
        if getattr(item, 'jogo_id', 0) in requested_ids
    }
    covers = {}
    for game_id in requested_ids:
        jogo = JOGOS_DB.get(game_id)
        if not jogo:
            continue
        item = items_by_game.get(game_id)
        origem = (getattr(item, 'launcher', '') if item else '') or (getattr(item, 'origem', '') if item else '') or 'manual'
        origem = origem.strip().lower()
        if origem not in {'steam', 'hydra', 'manual'}:
            origem = 'manual'
        stored_cover = getattr(item, 'cover_url', '') if item else ''
        appid = None
        codigo = str(getattr(item, 'codigo_origem', '') or '').strip() if item else ''
        if codigo.isdigit():
            appid = int(codigo)
        elif origem == 'steam' and str(getattr(jogo, 'id', '')).isdigit():
            appid = int(jogo.id)
        cover = stored_cover if _usar_capa_armazenada(stored_cover, origem) else ''
        if not cover:
            cover = _get_game_cover_centralized(getattr(jogo, 'titulo', ''), appid, origem, permitir_remoto=False)
        status = 'cached' if cover and not cover.startswith('data:') else 'loading'
        if status == 'loading' and item:
            chave = f'appid:{appid}' if appid else f'game:{game_id}'
            _CAPAS_EXECUTOR.submit(
                _resolver_capa_item_background,
                email,
                item,
                jogo,
                origem,
                appid,
                chave,
            )
        covers[str(game_id)] = {
            'url': cover,
            'status': status,
        }
    return jsonify({'ok': True, 'covers': covers})

@app.route('/jogar/configuracoes/estilo', methods=['POST'])
def configurar_estilo_biblioteca_jogar():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'}), 401
    view = (request.form.get('library_view') or request.form.get('library_style') or '').strip().lower()
    view = {'classic': '2d', '3d': '3d'}.get(view, view)
    if view not in {'2d', '3d'}:
        return jsonify({'ok': False, 'erro': 'estilo-invalido'}), 400
    user = USUARIOS_DB.get(meu_email)
    if not user:
        return jsonify({'ok': False, 'erro': 'usuario-nao-encontrado'}), 404
    user.library_view = view
    persistir_usuario(user)
    return jsonify({'ok': True, 'library_view': view})

def _processar_selecao_pasta(meu_email: str, launcher: str, pasta: str | None = None) -> dict:
    launcher = (launcher or '').strip().lower()
    if launcher not in {'steam', 'hydra'}:
        return {'ok': False, 'erro': 'launcher-invalido'}

    pasta = (pasta or '').strip()
    if not pasta:
        pasta = _escolher_pasta_windows()
    if not pasta:
        return {'ok': False, 'erro': 'pasta-vazia'}

    user = USUARIOS_DB.get(meu_email)
    if user:
        if launcher == 'steam':
            user.steam_library_path = pasta
        elif launcher == 'hydra':
            user.hydra_library_path = pasta
        persistir_usuario(user)

    _registrar_log(f'Pasta {launcher.upper()} selecionada: {pasta}')
    _executar_async(_sincronizar_biblioteca_launcher, meu_email, pasta if launcher == 'steam' else None, pasta if launcher == 'hydra' else None, True)
    return {'ok': True, 'launcher': launcher, 'pasta': pasta}


@app.route('/jogar/configuracoes', methods=['POST'])
def configurar_jogar_libraries():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'})

    launcher = (request.form.get('launcher') or '').strip().lower()
    resultado = _processar_selecao_pasta(meu_email, launcher, request.form.get('pasta'))
    return jsonify(resultado)

@app.route('/jogar/pasta/<launcher>', methods=['POST'])
def escolher_pasta_launcher(launcher):
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'})
    return jsonify(_processar_selecao_pasta(meu_email, launcher, request.form.get('pasta')))

@app.route('/selecionar_pasta_steam', methods=['POST'])
def selecionar_pasta_steam():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'})
    return jsonify(_processar_selecao_pasta(meu_email, 'steam', request.form.get('pasta')))

@app.route('/steam/biblioteca-local')
def biblioteca_local_steam():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'}), 401
    user = USUARIOS_DB.get(meu_email)
    if not user:
        return jsonify({'ok': False, 'erro': 'usuario-nao-encontrado'}), 404
    raiz = (getattr(user, 'steam_library_path', '') or '').strip() or None
    jogos = listar_jogos_instalados(steam_root=raiz, force=True)
    jogos.sort(key=lambda jogo: (str(jogo.get('name') or '').casefold(), str(jogo.get('appid') or '')))
    return jsonify({
        'ok': True,
        'library': raiz or '',
        'games': jogos,
        'total': len(jogos),
    })

@app.route('/selecionar_pasta_hydra', methods=['POST'])
def selecionar_pasta_hydra():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'})
    return jsonify(_processar_selecao_pasta(meu_email, 'hydra', request.form.get('pasta')))

@app.route('/steam/select-library', methods=['POST'])
def selecionar_pasta_steam_compat():
    return selecionar_pasta_steam()

@app.route('/hydra/select-library', methods=['POST'])
def selecionar_pasta_hydra_compat():
    return selecionar_pasta_hydra()

@app.route('/jogar/atualizar', methods=['POST'])
def atualizar_biblioteca_jogar():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'})

    user = USUARIOS_DB.get(meu_email)
    if not user:
        return jsonify({'ok': False, 'erro': 'usuario-nao-encontrado'})

    _registrar_log('Biblioteca atualizada')
    _executar_async(
        _sincronizar_biblioteca_launcher,
        meu_email,
        getattr(user, 'steam_library_path', '') or None,
        getattr(user, 'hydra_library_path', '') or None,
        True,
    )
    return jsonify({'ok': True})

def _scan_biblioteca_automatica(email: str) -> None:
    user = USUARIOS_DB.get((email or '').strip().lower())
    if not user:
        return
    with _AUTO_LIBRARY_STATUS_LOCK:
        _AUTO_LIBRARY_STATUS[email] = {'status': 'scanning', 'found': 0, 'error': ''}
    try:
        server_folders = [
            folder for folder in (getattr(user, 'auto_library_folders', []) or [])
            if not str(folder).strip().lower().startswith('browser:')
        ]
        registros = scan_automatic_library(
            server_folders,
            include_steam=True,
            steam_root=getattr(user, 'steam_library_path', '') or '',
        )
        por_origem: dict[str, list[dict]] = {}
        for registro in registros:
            origem = (registro.get('launcher') or 'manual').strip().lower()
            por_origem.setdefault(origem, []).append(registro)
        for origem, itens in por_origem.items():
            persistir_registros_instalados(email, itens, origem)
        _persistir_jogos_descobertos_por_origem(email, registros)
        user.auto_last_scan = datetime.now().isoformat(timespec='seconds')
        persistir_usuario(user)
        with _AUTO_LIBRARY_STATUS_LOCK:
            _AUTO_LIBRARY_STATUS[email] = {'status': 'completed', 'found': len(registros), 'error': ''}
    except Exception as exc:
        _registrar_log(f'Erro na Biblioteca Automática: {exc}')
        with _AUTO_LIBRARY_STATUS_LOCK:
            _AUTO_LIBRARY_STATUS[email] = {'status': 'error', 'found': 0, 'error': str(exc)}


def _persistir_jogos_descobertos_por_origem(email: str, registros: list[dict]) -> int:
    total = 0
    por_origem: dict[str, list[dict]] = {}
    for registro in registros:
        por_origem.setdefault((registro.get('launcher') or 'manual').strip().lower(), []).append(registro)
    for origem, itens in por_origem.items():
        total += _persistir_jogos_descobertos(email, itens, origem)
    return total


@app.route('/jogar/biblioteca-automatica', methods=['GET', 'POST'])
def biblioteca_automatica_config():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'}), 401
    user = USUARIOS_DB.get(meu_email)
    if not user:
        return jsonify({'ok': False, 'erro': 'usuario-nao-encontrado'}), 404
    if request.method == 'POST':
        folders = request.form.getlist('pastas') or request.form.getlist('folders')
        if not folders:
            folders = [request.form.get('pasta', '')]
        if len(folders) == 1 and ',' in folders[0]:
            folders = folders[0].split(',')
        folders = list(dict.fromkeys(folder.strip() for folder in folders if folder and folder.strip()))
        user.auto_library_enabled = request.form.get('ativar', request.form.get('enabled', '0')) in {'1', 'true', 'on'}
        user.auto_library_folders = folders
        persistir_usuario(user)
    registros = listar_games_instalados(meu_email)
    with _AUTO_LIBRARY_STATUS_LOCK:
        scan_status = dict(_AUTO_LIBRARY_STATUS.get(meu_email, {'status': 'idle', 'found': 0, 'error': ''}))
    return jsonify({
        'ok': True,
        'enabled': bool(getattr(user, 'auto_library_enabled', False)),
        'folders': getattr(user, 'auto_library_folders', []) or [],
        'last_scan': getattr(user, 'auto_last_scan', None),
        'games_found': sum(1 for registro in registros if registro.get('installed')),
        'steam': sum(1 for registro in registros if registro.get('installed') and registro.get('launcher') == 'steam'),
        'folders_games': sum(1 for registro in registros if registro.get('installed') and registro.get('launcher') == 'manual'),
        'scan_status': scan_status.get('status', 'idle'),
        'scan_found': scan_status.get('found', 0),
        'scan_error': scan_status.get('error', ''),
        'desktop_mode': is_desktop_gameunexa(),
        'web_mode': is_web_gameunexa(),
    })


@app.route('/jogar/biblioteca-automatica/pasta', methods=['POST'])
def selecionar_pasta_biblioteca_automatica():
    if not session.get('user_email'):
        return jsonify({'ok': False, 'erro': 'login'}), 401
    try:
        if is_desktop_gameunexa():
            pasta = _escolher_pasta_windows()
            if not pasta:
                return jsonify({'ok': False, 'erro': 'Seleção cancelada.'}), 400
            return jsonify({'ok': True, 'pasta': pasta, 'mode': 'desktop'})
        return jsonify({'ok': False, 'erro': 'Seleção direta de pasta não está disponível no navegador. Use o seletor do navegador.', 'mode': 'web'}), 400
    except Exception as exc:
        app.logger.warning('[auto-library] selecionar_pasta_biblioteca_automatica: %s', exc)
        return jsonify({'ok': False, 'erro': 'Não foi possível abrir o seletor de pasta.'}), 400


@app.route('/api/library/select-folder', methods=['POST'])
def api_library_select_folder():
    if not session.get('user_email'):
        return jsonify({'ok': False, 'erro': 'login'}), 401
    if is_desktop_gameunexa():
        pasta = _escolher_pasta_windows()
        if not pasta:
            return jsonify({'ok': False, 'erro': 'Seleção cancelada.'}), 400
        return jsonify({'ok': True, 'folder': pasta, 'display': format_folder_label('Pasta selecionada', pasta), 'mode': 'desktop'})
    return jsonify({'ok': False, 'erro': 'Seleção de pasta do navegador deve ocorrer no frontend com showDirectoryPicker().', 'mode': 'web'}), 400


@app.route('/api/library/local/import', methods=['POST'])
def api_library_local_import():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'}), 401

    payload = request.get_json(silent=True) or {}
    games = payload.get('games') if isinstance(payload, dict) else None
    if not isinstance(games, list):
        return jsonify({'ok': False, 'erro': 'Lista de jogos inválida.'}), 400

    registros = []
    for item in games:
        if not isinstance(item, dict):
            continue
        nome = (item.get('name') or item.get('nome') or '').strip()
        if not nome:
            continue

        library_root = (item.get('path') or item.get('library_root') or item.get('folder') or '').strip()
        exe_name = (item.get('executable') or item.get('exe_name') or item.get('executable_name') or '').strip()
        exe_path = (item.get('executable_path') or item.get('exe_path') or exe_name).strip()

        registros.append({
            'nome': nome,
            'launcher': 'manual',
            'appid': str(item.get('appid') or '').strip(),
            'library_root': library_root,
            'game_folder': library_root,
            'exe_name': exe_name,
            'exe_path': exe_path,
            'installed': True,
            'favorite': bool(item.get('favorite')),
            'last_scan': datetime.now().isoformat(timespec='seconds'),
            'hash': '',
        })

    if not registros:
        return jsonify({'ok': False, 'erro': 'Nenhum jogo válido foi encontrado para importação.'}), 400

    total_biblioteca = _persistir_jogos_descobertos(meu_email, registros, 'manual')
    total_installed = persistir_registros_instalados(meu_email, registros, 'manual')
    user = USUARIOS_DB.get((meu_email or '').strip().lower())
    if user is not None:
        user.auto_last_scan = datetime.now().isoformat(timespec='seconds')
        persistir_usuario(user)
    return jsonify({'ok': True, 'imported': total_biblioteca, 'installed': total_installed, 'total': max(total_biblioteca, total_installed)})


@app.route('/jogar/biblioteca-automatica/scan', methods=['POST'])
def escanear_biblioteca_automatica():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'}), 401
    user = USUARIOS_DB.get(meu_email)
    if not user:
        return jsonify({'ok': False, 'erro': 'usuario-nao-encontrado'}), 404
    with _AUTO_LIBRARY_STATUS_LOCK:
        if _AUTO_LIBRARY_STATUS.get(meu_email, {}).get('status') == 'scanning':
            return jsonify({'ok': True, 'status': 'scanning'})
        _AUTO_LIBRARY_STATUS[meu_email] = {'status': 'scanning', 'found': 0, 'error': ''}
    _executar_async(_scan_biblioteca_automatica, meu_email)
    return jsonify({'ok': True, 'status': 'scanning'})

@app.route('/jogar/<int:jogo_id>/play', methods=['POST'])
def jogar_jogo(jogo_id: int):
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'success': False, 'erro': 'login'})
    item = next((item for item in GerenciadorBiblioteca.obter_biblioteca(meu_email) if item.jogo_id == jogo_id), None)
    if not item:
        return jsonify({'ok': False, 'success': False, 'erro': 'jogo-nao-encontrado'})
    resultado = _iniciar_jogo(item)
    payload = {
        'ok': bool(resultado.get('ok')),
        'success': bool(resultado.get('success')),
        'modo': resultado.get('modo', 'manual'),
        'titulo': JOGOS_DB.get(jogo_id).titulo if jogo_id in JOGOS_DB else '',
        'pid': resultado.get('pid'),
    }
    if resultado.get('error'):
        payload['error'] = resultado['error']
    if resultado.get('ok'):
        return jsonify(payload)
    return jsonify(payload)

@app.route('/jogar/<int:jogo_id>/favorito', methods=['POST'])
def alternar_favorito_jogo(jogo_id: int):
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'})
    item = next((item for item in GerenciadorBiblioteca.obter_biblioteca(meu_email) if item.jogo_id == jogo_id), None)
    if not item:
        return jsonify({'ok': False, 'erro': 'jogo-nao-encontrado'})
    item.alternar_favorito()
    persistir_biblioteca_item(item)
    return jsonify({'ok': True, 'favorito': bool(getattr(item, 'favorito', False))})

@app.route('/jogar/<int:jogo_id>/executavel', methods=['POST'])
def definir_executavel_jogo(jogo_id: int):
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'})
    item = next((item for item in GerenciadorBiblioteca.obter_biblioteca(meu_email) if item.jogo_id == jogo_id), None)
    if not item:
        return jsonify({'ok': False, 'erro': 'jogo-nao-encontrado'})
    valor_anterior = getattr(item, 'executable_path', '') or ''
    caminho = request.form.get('caminho', '').strip() or _escolher_executavel_windows()
    if not caminho:
        return jsonify({'ok': False, 'erro': 'caminho-vazio'})
    caminho = os.path.abspath(caminho)
    if not caminho.lower().endswith('.exe') or not os.path.isfile(caminho):
        return jsonify({'ok': False, 'erro': 'executavel-invalido', 'mensagem': 'Selecione um arquivo .exe existente.'})
    item.executable_path = caminho
    item.pasta_instalacao = os.path.dirname(caminho)
    item.install_folder = item.pasta_instalacao
    item.executable_name = os.path.basename(caminho)
    item.updated_at = datetime.now().isoformat(timespec='seconds')
    item.manual_override = True
    print('================================')
    print('Executável recebido')
    print(f'ID do jogo: {jogo_id}')
    print(f'Nome do jogo: {getattr(JOGOS_DB.get(jogo_id), "titulo", "")}')
    print(f'Valor antigo: {valor_anterior}')
    print(f'Valor novo: {item.executable_path}')
    print('UPDATE iniciado')
    persistir_biblioteca_item(item)
    conn = get_connection()
    try:
        cursor = conn.execute(
            '''
            UPDATE biblioteca
            SET executable_path = ?, install_folder = ?, executable_name = ?,
                updated_at = ?, manual_override = 1
            WHERE email_usuario = ? AND jogo_id = ?
            ''',
            (item.executable_path, item.install_folder, item.executable_name, item.updated_at, meu_email, jogo_id),
        )
        print(f'Rows afetadas: {cursor.rowcount}')
        conn.commit()
        valor_salvo = conn.execute(
            'SELECT executable_path FROM biblioteca WHERE email_usuario = ? AND jogo_id = ?',
            (meu_email, jogo_id),
        ).fetchone()
        print(f'Valor salvo no banco: {valor_salvo[0] if valor_salvo else ""}')
        print('Commit executado')
    finally:
        conn.close()
    print('================================')
    _registrar_log(f'Executável salvo para jogo {jogo_id}: {caminho}')
    return jsonify({'ok': True, 'executable_name': item.executable_name, 'install_folder': item.install_folder, 'manual_override': True})


@app.route('/jogar/<int:jogo_id>/executavel/remover', methods=['POST'])
def remover_executavel_manual(jogo_id: int):
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'})
    item = next((item for item in GerenciadorBiblioteca.obter_biblioteca(meu_email) if item.jogo_id == jogo_id), None)
    if not item:
        return jsonify({'ok': False, 'erro': 'jogo-nao-encontrado'})
    item.executable_path = ''
    item.install_folder = ''
    item.executable_name = ''
    item.pasta_instalacao = ''
    item.updated_at = datetime.now().isoformat(timespec='seconds')
    item.manual_override = False
    persistir_biblioteca_item(item)
    conn = get_connection()
    try:
        conn.execute(
            '''
            UPDATE biblioteca
            SET executable_path = NULL, install_folder = NULL, executable_name = NULL,
                updated_at = ?, manual_override = 0
            WHERE email_usuario = ? AND jogo_id = ?
            ''',
            (item.updated_at, meu_email, jogo_id),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({'ok': True, 'manual_override': False})

@app.route('/jogar/<int:jogo_id>/abrir-pasta', methods=['POST'])
def abrir_pasta_jogo(jogo_id: int):
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'ok': False, 'erro': 'login'})
    item = next((item for item in GerenciadorBiblioteca.obter_biblioteca(meu_email) if item.jogo_id == jogo_id), None)
    if not item:
        return jsonify({'ok': False, 'erro': 'jogo-nao-encontrado'})

    resultado = LAUNCHER_MANAGER.abrir_pasta_jogo(item)
    return jsonify(resultado)

# --- Rotas de Reviews ---
@app.route('/jogo/<int:jogo_id>/review/novo', methods=['POST'])
def novo_review(jogo_id):
    meu_email = session.get('user_email')
    if not meu_email: 
        return redirect(url_for('login'))
    if jogo_id not in JOGOS_DB:
        flash("Jogo não encontrado!", "danger")
        return redirect(url_for('dashboard'))
    if not GerenciadorBiblioteca.jogo_na_biblioteca(meu_email, jogo_id):
        flash("Você precisa adicionar o jogo à biblioteca primeiro!", "danger")
        return redirect(url_for('dashboard'))
    
    titulo = request.form.get('titulo', '').strip()
    conteudo = request.form.get('conteudo', '').strip()
    nota = request.form.get('nota', '5.0')
    
    try:
        nota = float(nota)
        res = moderate_text(titulo)
        res_c = moderate_text(conteudo)
        if not res.get('allowed', True) or not res_c.get('allowed', True):
            flash("Seu review contém conteúdo impróprio!", "danger")
            return redirect(url_for('perfil', email=meu_email))
        
        if not titulo or not conteudo:
            flash("Título e conteúdo são obrigatórios!", "danger")
            return redirect(url_for('perfil', email=meu_email))
        
        if nota < 0 or nota > 5:
            raise ValueError("A nota precisa estar entre 0.0 e 5.0")

        id_review = max(REVIEWS_DB.keys(), default=0) + 1
        review = GerenciadorReviews.criar_review(id_review, jogo_id, meu_email, titulo, conteudo, nota)
        persistir_review(review)
        flash("Review publicado com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao criar review: {str(e)}", "danger")
    return redirect(url_for('perfil', email=meu_email))

@app.route('/review/<int:review_id>/deletar', methods=['POST'])
def deletar_review(review_id):
    meu_email = session.get('user_email')
    if not meu_email: 
        return redirect(url_for('login'))
    review = REVIEWS_DB.get(review_id)
    if not review or (review.email_usuario != meu_email and not session.get('is_admin')):
        flash("Não tem permissão para deletar este review!", "danger")
        return redirect(url_for('dashboard'))
    try:
        GerenciadorReviews.deletar_review(review_id)
        marcar_review_visivel(review_id, False)
        flash("Review deletado!", "info")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/review/<int:review_id>/curtir', methods=['POST'])
def curtir_review(review_id):
    review = REVIEWS_DB.get(review_id)
    if not review:
        return jsonify({'erro': 'Review não encontrado'}), 404
    review.adicionar_curtida()
    persistir_review(review)
    return jsonify({'curtidas': review.curtidas})

@app.route('/review/<int:review_id>/comentar', methods=['POST'])
def comentar_review(review_id):
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))

    review = REVIEWS_DB.get(review_id)
    if not review or not review.visivel:
        flash('Review não encontrada.', 'danger')
        return redirect(url_for('dashboard'))

    texto = request.form.get('texto', '').strip()
    if not texto:
        flash('Comentário não pode estar vazio!', 'danger')
        return redirect(request.referrer or url_for('perfil', email=review.email_usuario))

    resultado = moderate_text(texto)
    if not resultado.get('allowed', True):
        flash('Comentário contém termos impróprios!', 'danger')
        return redirect(request.referrer or url_for('perfil', email=review.email_usuario))

    try:
        novo_id = max([c.id for c in REVIEW_COMENTARIOS_DB], default=0) + 1
        comentario = GerenciadorReviews.adicionar_comentario_review(novo_id, review_id, meu_email, texto)
        persistir_review_comentario(comentario)
        flash('Comentário adicionado na review!', 'success')
    except Exception as e:
        flash(f'Erro ao comentar review: {str(e)}', 'danger')

    return redirect(request.referrer or url_for('perfil', email=review.email_usuario))

@app.route('/review/comentario/<int:comentario_id>/deletar', methods=['POST'])
def deletar_comentario_review(comentario_id):
    meu_email = session.get('user_email')
    if not meu_email:
        return redirect(url_for('login'))

    comentario = next((c for c in REVIEW_COMENTARIOS_DB if c.id == comentario_id), None)
    if not comentario:
        flash('Comentário não encontrado.', 'danger')
        return redirect(url_for('dashboard'))

    if comentario.email_usuario != meu_email and not session.get('is_admin'):
        flash('Sem permissão para deletar este comentário.', 'danger')
        return redirect(request.referrer or url_for('perfil', email=REVIEWS_DB[comentario.review_id].email_usuario if comentario.review_id in REVIEWS_DB else meu_email))

    try:
        GerenciadorReviews.deletar_comentario_review(comentario_id)
        marcar_review_comentario_visivel(comentario_id, False)
        flash('Comentário deletado!', 'info')
    except Exception as e:
        flash(str(e), 'danger')

    review = REVIEWS_DB.get(comentario.review_id)
    return redirect(request.referrer or url_for('perfil', email=review.email_usuario if review else meu_email))

# --- Central de Suporte ---
@app.route('/suporte', methods=['GET'])
def central_suporte():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    termo = (request.args.get('termo') or '').strip()
    filtro_status = request.args.get('status') or ''
    filtro_categoria = request.args.get('categoria') or ''
    ordenar = request.args.get('ordenar') or 'recentes'

    conn = get_connection()
    query = '''
        SELECT c.id, c.codigo, c.titulo, c.categoria_slug, c.prioridade, c.status_slug,
               c.data_criacao, c.hora_criacao, c.usuario_email, c.usuario_nome, c.email_contato,
               COUNT(m.id) as mensagens
        FROM suporte_chamados c
        LEFT JOIN suporte_mensagens m ON m.chamado_id = c.id
    '''
    clauses = []
    params = []
    if not session.get('is_admin'):
        clauses.append('c.usuario_email = ?')
        params.append(session['user_email'])

    if termo:
        clauses.append('(c.titulo LIKE ? OR c.descricao LIKE ? OR c.codigo LIKE ?)')
        termo_like = f'%{termo}%'
        params.extend([termo_like, termo_like, termo_like])

    if filtro_status:
        clauses.append('c.status_slug = ?')
        params.append(filtro_status)

    if filtro_categoria:
        clauses.append('c.categoria_slug = ?')
        params.append(filtro_categoria)

    if clauses:
        query += ' WHERE ' + ' AND '.join(clauses)

    query += ' GROUP BY c.id ORDER BY '
    if ordenar == 'antigos':
        query += 'c.data_criacao ASC, c.hora_criacao ASC'
    elif ordenar == 'prioridade':
        query += "CASE c.prioridade WHEN 'Crítica' THEN 0 WHEN 'Alta' THEN 1 WHEN 'Média' THEN 2 ELSE 3 END, c.data_criacao DESC"
    else:
        query += 'c.data_criacao DESC, c.hora_criacao DESC'

    chamados = [dict(row) for row in conn.execute(query, params).fetchall()]
    support_stats = {}
    if session.get('is_admin'):
        status_rows = conn.execute(
            'SELECT status_slug, COUNT(*) AS total FROM suporte_chamados GROUP BY status_slug'
        ).fetchall()
        support_stats = {row['status_slug']: row['total'] for row in status_rows}
        support_stats['total'] = sum(support_stats.values())
    conn.close()

    return render_template(
        'suporte.html',
        chamados=chamados,
        categorias=CATEGORIAS_SUPORTE,
        prioridades=PRIORIDADES_SUPORTE,
        status_list=STATUS_SUPORTE_INICIAIS,
        termo=termo,
        filtro_status=filtro_status,
        filtro_categoria=filtro_categoria,
        ordenar=ordenar,
        is_admin=session.get('is_admin', False),
        support_stats=support_stats,
    )


@app.route('/admin/suporte')
def admin_suporte():
    if 'user_email' not in session or not session.get('is_admin'):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('login'))
    return redirect(url_for('central_suporte'))


@app.route('/suporte/novo', methods=['POST'])
def novo_chamado_suporte():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    titulo = _sanitizar_texto(request.form.get('titulo'))
    categoria = (request.form.get('categoria') or 'other').strip().lower()
    descricao = _sanitizar_texto(request.form.get('descricao'))
    prioridade = _sanitizar_texto(request.form.get('prioridade')) or 'Média'
    passos = _sanitizar_texto(request.form.get('passos_reproducao'))
    esperado = _sanitizar_texto(request.form.get('resultado_esperado'))
    obtido = _sanitizar_texto(request.form.get('resultado_obtido'))

    if not titulo or not descricao or categoria not in {slug for slug, _ in CATEGORIAS_SUPORTE}:
        flash('Título, categoria e descrição são obrigatórios.', 'danger')
        return redirect(url_for('central_suporte'))

    conn = get_connection()
    codigo = gerar_codigo_suporte(categoria, conn)
    agora = datetime.now()
    usuario = USUARIOS_DB.get(session['user_email'])
    chamado_id = None
    cursor = conn.execute(
        '''
        INSERT INTO suporte_chamados (
            codigo, titulo, categoria_slug, descricao, passos_reproducao, resultado_esperado,
            resultado_obtido, prioridade, versao_gamelink, so, navegador, resolucao_tela,
            data_criacao, hora_criacao, usuario_email, usuario_nome, usuario_id, email_contato, status_slug
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            codigo,
            titulo,
            categoria,
            descricao,
            passos,
            esperado,
            obtido,
            prioridade,
            os.environ.get('GAME_LINK_VERSION', '1.0.0'),
            _detectar_so(),
            _detectar_navegador(request.headers.get('User-Agent', '')),
            _detectar_resolucao(request),
            agora.date().isoformat(),
            agora.strftime('%H:%M:%S'),
            session['user_email'],
            session.get('user_nome') or (usuario.nome if usuario else 'Usuário'),
            usuario.id if usuario else None,
            session['user_email'],
            'aberto',
        ),
    )
    chamado_id = cursor.lastrowid
    conn.execute(
        '''
        INSERT INTO suporte_mensagens (chamado_id, autor_email, autor_nome, conteudo, tipo, data_envio)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (
            chamado_id,
            session['user_email'],
            session.get('user_nome') or (usuario.nome if usuario else 'Usuário'),
            f"Chamado criado: {descricao}",
            'usuario',
            agora.isoformat(timespec='seconds'),
        ),
    )
    conn.commit()
    conn.close()

    attachments_paths = []
    for upload in request.files.getlist('anexo'):
        if not upload or not getattr(upload, 'filename', ''):
            continue
        try:
            anexo = _salvar_anexo_chamado(chamado_id, None, upload)
            if anexo:
                _persistir_anexo(anexo)
                attachments_paths.append(os.path.join(os.path.dirname(__file__), anexo['caminho']))
        except Exception as exc:
            flash(f'Erro ao anexar {upload.filename}: {exc}', 'warning')

    _adicionar_historico_suporte(chamado_id, session['user_email'], 'criar', 'Chamado criado pelo usuário')
    for admin_email in [u.email for u in USUARIOS_DB.values() if isinstance(u, Admin)]:
        _criar_notificacao_suporte(admin_email, chamado_id, codigo, 'Novo chamado criado')

    config = get_smtp_config()
    admin_email = config['admin_support_email']
    usuario = USUARIOS_DB.get(session['user_email']) or None
    mensagem_admin = (
        f'Novo chamado de suporte criado no GameUnexa.\n\n'
        f'Protocolo: {codigo}\n'
        f'Usuário: {session.get("user_nome") or (usuario.nome if usuario else "Usuário")}\n'
        f'ID do usuário: {usuario.id if usuario else "N/A"}\n'
        f'E-mail: {session["user_email"]}\n'
        f'Categoria: {_obter_categoria_suporte(categoria)}\n'
        f'Prioridade: {prioridade}\n'
        f'Título: {titulo}\n'
        f'Descrição: {descricao}\n\n'
        f'Sistema operacional: {_detectar_so()}\n'
        f'Browser: {_detectar_navegador(request.headers.get("User-Agent", ""))}\n'
        f'Data: {agora.date().isoformat()}\n'
        f'Hora: {agora.strftime("%H:%M:%S")}\n'
    )
    enviar_email(
        destinatario=admin_email,
        assunto=f'[GameUnexa] Novo Chamado - {codigo}',
        corpo=mensagem_admin,
        tipo_email='support_admin',
        template_name='emails/support_ticket.html',
        context={
            'titulo': f'Novo chamado de suporte: {codigo}',
            'protocolo': codigo,
            'usuario': session.get('user_nome') or (usuario.nome if usuario else 'Usuário'),
            'usuario_email': session['user_email'],
            'usuario_id': usuario.id if usuario else 'N/A',
            'categoria': _obter_categoria_suporte(categoria),
            'prioridade': prioridade,
            'titulo_chamado': titulo,
            'descricao': descricao,
            'sistema_operacional': _detectar_so(),
            'browser': _detectar_navegador(request.headers.get('User-Agent', '')),
            'ip': _obter_ip(),
            'data': agora.date().isoformat(),
            'hora': agora.strftime('%H:%M:%S'),
            'anexos': anexos_info,
            'link': url_for('ver_chamado_suporte', chamado_id=chamado_id, _external=True),
        },
        attachments=attachments_paths or None,
        background=True,
    )
    enviar_email(
        destinatario=session['user_email'],
        assunto=f'[GameUnexa] Chamado Recebido - {codigo}',
        corpo=(
            f'Olá, {session.get("user_nome") or (usuario.nome if usuario else "usuário")}.\n\n'
            f'Recebemos sua solicitação. Nossa equipe analisará o chamado o mais rápido possível.\n\n'
            f'Número do protocolo: {codigo}\n'
            f'Título: {titulo}\n'
            f'Categoria: {_obter_categoria_suporte(categoria)}\n'
            f'Prioridade: {prioridade}\n\n'
            'Agradecemos por nos enviar este chamado.'
        ),
        tipo_email='support_user',
        template_name='emails/support_ticket.html',
        context={
            'titulo': f'Chamado recebido: {codigo}',
            'protocolo': codigo,
            'usuario': session.get('user_nome') or (usuario.nome if usuario else 'Usuário'),
            'categoria': _obter_categoria_suporte(categoria),
            'prioridade': prioridade,
            'titulo_chamado': titulo,
            'descricao': descricao,
            'sistema_operacional': _detectar_so(),
            'browser': _detectar_navegador(request.headers.get('User-Agent', '')),
            'ip': _obter_ip(),
            'data': agora.date().isoformat(),
            'hora': agora.strftime('%H:%M:%S'),
            'anexos': anexos_info,
            'mensagem_confirmacao': 'Recebemos sua solicitação. Nossa equipe analisará o chamado o mais rápido possível.',
            'link': url_for('ver_chamado_suporte', chamado_id=chamado_id, _external=True),
        },
        background=True,
    )

    flash(f'Chamado enviado com sucesso! Seu número é {codigo}.', 'success')
    return redirect(url_for('ver_chamado_suporte', chamado_id=chamado_id))


@app.route('/suporte/chamado/<int:chamado_id>')
def ver_chamado_suporte(chamado_id):
    if 'user_email' not in session:
        return redirect(url_for('login'))

    conn = get_connection()
    chamado = conn.execute(
        '''
        SELECT * FROM suporte_chamados WHERE id = ?
        ''',
        (chamado_id,),
    ).fetchone()
    if not chamado:
        conn.close()
        flash('Chamado não encontrado.', 'danger')
        return redirect(url_for('central_suporte'))

    if not session.get('is_admin') and chamado['usuario_email'] != session['user_email']:
        conn.close()
        flash('Você não tem permissão para visualizar este chamado.', 'danger')
        return redirect(url_for('central_suporte'))

    mensagens = [dict(row) for row in conn.execute(
        '''
        SELECT * FROM suporte_mensagens WHERE chamado_id = ? ORDER BY id ASC
        ''',
        (chamado_id,),
    ).fetchall()]
    anexos = [dict(row) for row in conn.execute(
        '''
        SELECT * FROM suporte_anexos WHERE chamado_id = ? ORDER BY id ASC
        ''',
        (chamado_id,),
    ).fetchall()]
    historico = [dict(row) for row in conn.execute(
        '''
        SELECT * FROM suporte_historico WHERE chamado_id = ? ORDER BY id ASC
        ''',
        (chamado_id,),
    ).fetchall()]
    conn.close()

    return render_template(
        'suporte.html',
        chamado=chamado,
        mensagens=mensagens,
        anexos=anexos,
        historico=historico,
        categorias=CATEGORIAS_SUPORTE,
        prioridades=PRIORIDADES_SUPORTE,
        status_list=STATUS_SUPORTE_INICIAIS,
        is_admin=session.get('is_admin', False),
        modo_visualizacao=True,
    )


@app.route('/suporte/chamado/<int:chamado_id>/mensagem', methods=['POST'])
def responder_chamado_suporte(chamado_id):
    if 'user_email' not in session:
        return redirect(url_for('login'))

    conn = get_connection()
    chamado = conn.execute('SELECT * FROM suporte_chamados WHERE id = ?', (chamado_id,)).fetchone()
    if not chamado:
        conn.close()
        flash('Chamado não encontrado.', 'danger')
        return redirect(url_for('central_suporte'))

    if not session.get('is_admin') and chamado['usuario_email'] != session['user_email']:
        conn.close()
        flash('Sem permissão.', 'danger')
        return redirect(url_for('central_suporte'))

    conteudo = _sanitizar_texto(request.form.get('mensagem'))
    if not conteudo:
        conn.close()
        flash('A mensagem não pode ficar vazia.', 'danger')
        return redirect(url_for('ver_chamado_suporte', chamado_id=chamado_id))

    agora = datetime.now()
    tipo = 'admin' if session.get('is_admin') else 'usuario'
    cursor = conn.execute(
        '''
        INSERT INTO suporte_mensagens (chamado_id, autor_email, autor_nome, conteudo, tipo, data_envio)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (
            chamado_id,
            session['user_email'],
            session.get('user_nome') or session['user_email'],
            conteudo,
            tipo,
            agora.isoformat(timespec='seconds'),
        ),
    )
    mensagem_id = cursor.lastrowid
    conn.commit()
    conn.close()

    attachments_paths = []
    for upload in request.files.getlist('anexo'):
        if not upload or not getattr(upload, 'filename', ''):
            continue
        try:
            anexo = _salvar_anexo_chamado(chamado_id, mensagem_id, upload)
            if anexo:
                _persistir_anexo(anexo)
                attachments_paths.append(os.path.join(os.path.dirname(__file__), anexo['caminho']))
        except Exception as exc:
            flash(f'Erro ao anexar {upload.filename}: {exc}', 'warning')

    _adicionar_historico_suporte(chamado_id, session['user_email'], 'mensagem', 'Nova mensagem adicionada')
    if session.get('is_admin'):
        _criar_notificacao_suporte(chamado['usuario_email'], chamado_id, chamado['codigo'], 'Uma nova resposta foi enviada pelo suporte')
        enviar_email(
            destinatario=chamado['usuario_email'],
            assunto=f'Resposta ao chamado {chamado["codigo"]}',
            corpo=(
                f'Olá.\n\n'
                f'Uma nova resposta foi adicionada ao chamado {chamado["codigo"]}.\n'
                f'Nova mensagem: {conteudo}\n\n'
                f'Status atual: {_obter_status_suporte(chamado["status_slug"])}\n'
            ),
            tipo_email='support_reply',
            template_name='emails/support_reply.html',
            context={
                'titulo': f'Resposta ao chamado {chamado["codigo"]}',
                'protocolo': chamado['codigo'],
                'mensagem': conteudo,
                'status_atual': _obter_status_suporte(chamado['status_slug']),
                'link': url_for('ver_chamado_suporte', chamado_id=chamado_id, _external=True),
            },
            attachments=attachments_paths or None,
            background=True,
        )
    else:
        for admin_email in [u.email for u in USUARIOS_DB.values() if isinstance(u, Admin)]:
            _criar_notificacao_suporte(admin_email, chamado_id, chamado['codigo'], 'Novo comentário de usuário')

    flash('Mensagem enviada.', 'success')
    return redirect(url_for('ver_chamado_suporte', chamado_id=chamado_id))


@app.route('/suporte/chamado/<int:chamado_id>/status', methods=['POST'])
def atualizar_status_chamado_suporte(chamado_id):
    if 'user_email' not in session or not session.get('is_admin'):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('central_suporte'))

    novo_status = (request.form.get('status') or 'aberto').strip().lower()
    conn = get_connection()
    conn.execute('UPDATE suporte_chamados SET status_slug = ? WHERE id = ?', (novo_status, chamado_id))
    conn.commit()
    conn.close()
    _adicionar_historico_suporte(chamado_id, session['user_email'], 'status', f'Status alterado para {_obter_status_suporte(novo_status)}')
    flash('Status atualizado.', 'success')
    return redirect(url_for('ver_chamado_suporte', chamado_id=chamado_id))


@app.route('/suporte/chamado/<int:chamado_id>/fechar', methods=['POST'])
def fechar_chamado_suporte(chamado_id):
    if 'user_email' not in session or not session.get('is_admin'):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('central_suporte'))
    conn = get_connection()
    conn.execute('UPDATE suporte_chamados SET status_slug = ? WHERE id = ?', ('fechado', chamado_id))
    conn.commit()
    conn.close()
    _adicionar_historico_suporte(chamado_id, session['user_email'], 'fechar', 'Chamado fechado pelo administrador')
    flash('Chamado fechado.', 'success')
    return redirect(url_for('ver_chamado_suporte', chamado_id=chamado_id))


@app.route('/suporte/chamado/<int:chamado_id>/reabrir', methods=['POST'])
def reabrir_chamado_suporte(chamado_id):
    if 'user_email' not in session or not session.get('is_admin'):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('central_suporte'))
    conn = get_connection()
    conn.execute('UPDATE suporte_chamados SET status_slug = ? WHERE id = ?', ('aberto', chamado_id))
    conn.commit()
    conn.close()
    _adicionar_historico_suporte(chamado_id, session['user_email'], 'reabrir', 'Chamado reaberto pelo administrador')
    flash('Chamado reaberto.', 'success')
    return redirect(url_for('ver_chamado_suporte', chamado_id=chamado_id))


@app.route('/suporte/chamado/<int:chamado_id>/excluir', methods=['POST'])
def excluir_chamado_suporte(chamado_id):
    if 'user_email' not in session or not session.get('is_admin'):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('central_suporte'))

    conn = get_connection()
    conn.execute('DELETE FROM suporte_historico WHERE chamado_id = ?', (chamado_id,))
    conn.execute('DELETE FROM suporte_anexos WHERE chamado_id = ?', (chamado_id,))
    conn.execute('DELETE FROM suporte_mensagens WHERE chamado_id = ?', (chamado_id,))
    conn.execute('DELETE FROM suporte_chamados WHERE id = ?', (chamado_id,))
    conn.commit()
    conn.close()
    flash('Chamado excluído.', 'success')
    return redirect(url_for('central_suporte'))


@app.route('/suporte/exportar/csv')
def exportar_suporte_csv():
    if 'user_email' not in session or not session.get('is_admin'):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('central_suporte'))

    conn = get_connection()
    rows = conn.execute('SELECT codigo, titulo, categoria_slug, prioridade, status_slug, usuario_email, data_criacao, hora_criacao FROM suporte_chamados ORDER BY id DESC').fetchall()
    conn.close()
    output = []
    output.append('codigo,titulo,categoria,prioridade,status,usuario,data,hora\n')
    for row in rows:
        output.append(','.join([str(row[i] or '').replace(',', ';').replace('\n', ' ') for i in range(8)]) + '\n')
    return Response(''.join(output), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=support.csv'})


@app.route('/suporte/exportar/excel')
def exportar_suporte_excel():
    if 'user_email' not in session or not session.get('is_admin'):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('central_suporte'))

    conn = get_connection()
    rows = conn.execute('SELECT codigo, titulo, categoria_slug, prioridade, status_slug, usuario_email, data_criacao, hora_criacao FROM suporte_chamados ORDER BY id DESC').fetchall()
    conn.close()
    output = []
    output.append('codigo\ttitulo\tcategoria\tprioridade\tstatus\tusuario\tdata\thora\n')
    for row in rows:
        output.append('\t'.join([str(row[i] or '').replace('\t', ' ').replace('\n', ' ') for i in range(8)]) + '\n')
    return Response(''.join(output), mimetype='application/vnd.ms-excel', headers={'Content-Disposition': 'attachment; filename=support.xls'})

# --- Rotas de Notificações ---
@app.route('/notificacoes')
def notificacoes():
    meu_email = session.get('user_email')
    if not meu_email: 
        return redirect(url_for('login'))
    notif_list = GerenciadorNotificacoes.obter_notificacoes(meu_email)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('ajax') == '1':
        return render_template('_notificacoes_conteudo.html', notificacoes=notif_list, usuarios=USUARIOS_DB)
    
    # Se o usuário acessou digitando a URL no navegador, entrega a página completa:
    return render_template('notificacoes.html', notificacoes=notif_list, usuarios=USUARIOS_DB)

@app.route('/notificacao/<int:notif_id>/marcar-lida', methods=['POST'])
def marcar_notif_lida(notif_id):
    meu_email = session.get('user_email')
    if not meu_email: 
        return jsonify({'erro': 'Não logado'}), 401
    try:
        GerenciadorNotificacoes.marcar_como_lida(meu_email, notif_id)
        marcar_notificacao_lida(meu_email, notif_id)
        return jsonify({'sucesso': True})
    except Exception as e:
        return jsonify({'erro': str(e)}), 400


@app.route('/mensagens/nao-lidas/contador')
def contador_mensagens_nao_lidas():
    meu_email = session.get('user_email')
    if not meu_email:
        return jsonify({'count': 0})

    count = GerenciadorNotificacoes.contar_nao_lidas_por_tipo(meu_email, 'mensagem')
    return jsonify({'count': count})

# --- Rotas para Posts ---
@app.route('/posts/novo', methods=['POST'])
def novo_post():
    if 'user_email' not in session: 
        return redirect(url_for('login'))
    
    titulo = request.form.get('titulo', '').strip()
    conteudo = request.form.get('conteudo', '').strip()
    
    if not titulo or not conteudo:
        flash("Título e conteúdo são obrigatórios!", "danger")
        return redirect(url_for('dashboard'))
    
    res_t = moderate_text(titulo)
    res_c = moderate_text(conteudo)
    if not res_t.get('allowed', True) or not res_c.get('allowed', True):
        flash("Conteúdo contém termos impróprios!", "danger")
        return redirect(url_for('dashboard'))
    
    imagem_url = None
    if 'imagem' in request.files:
        file = request.files['imagem']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(f"{session['user_email']}_{int(datetime.now().timestamp())}_{file.filename}")
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            imagem_url = f"/app-data/uploads/{filename}"
    
    novo_id = max(POSTS_DB.keys(), default=0) + 1
    novo_post_obj = Post(novo_id, session['user_email'], titulo, conteudo, imagem_url)
    POSTS_DB[novo_id] = novo_post_obj
    persistir_post(novo_post_obj)
    
    # Sistema de Notificações Ativas
    amigos = GerenciadorAmigos.obter_amigos(session['user_email'])
    user_atual = USUARIOS_DB.get(session['user_email'])
    nome_autor = user_atual.nome if user_atual else session['user_email']
    
    for email_amigo in amigos:
        id_notif = max([n.id for notifs in NOTIFICACOES_DB.values() for n in notifs], default=0) + 1
        GerenciadorNotificacoes.notificar_novo_post(
            email_amigo,
            f"Novo post de {nome_autor}",
            f"{nome_autor} postou: {titulo[:50]}...",
            novo_id,
            id_notif
        )
        for notif in NOTIFICACOES_DB.get(email_amigo, []):
            if notif.id == id_notif:
                persistir_notificacao(notif)
                break
    
    flash("Post criado com sucesso!", "success")
    return redirect(url_for('dashboard'))

@app.route('/posts/<int:post_id>')
def ver_post(post_id):
    if 'user_email' not in session: 
        return redirect(url_for('login'))
    post = POSTS_DB.get(post_id)
    if not post or not post.visivel:
        flash("Post não encontrado.", "danger")
        return redirect(url_for('dashboard'))
    
    comentarios = [c for c in COMENTARIOS_POSTS_DB if c.post_id == post_id and c.visivel]
    autor = USUARIOS_DB.get(post.autor_email)
    return render_template('ver_post.html', post=post, comentarios=comentarios, autor=autor, usuarios=USUARIOS_DB)

@app.route('/posts/<int:post_id>/curtir', methods=['POST'])
def curtir_post(post_id):
    if 'user_email' not in session: 
        return jsonify({'error': 'Não logado'}), 401
    post = POSTS_DB.get(post_id)
    if not post:
        return jsonify({'error': 'Post não encontrado'}), 404
    
    email = session['user_email']
    curtiu = False if post.usuario_curtiu(email) else True
    post.descurtir(email) if post.usuario_curtiu(email) else post.curtir(email)
    persistir_post_like(post_id, email, curtiu)
    
    return jsonify({'curtiu': curtiu, 'total_curtidas': post.get_total_curtidas()})

@app.route('/posts/<int:post_id>/comentar', methods=['POST'])
def comentar_post(post_id):
    if 'user_email' not in session: 
        return redirect(url_for('login'))
    post = POSTS_DB.get(post_id)
    if not post or not post.visivel:
        flash("Post não encontrado.", "danger")
        return redirect(url_for('dashboard'))
    
    texto = request.form.get('texto', '').strip()
    if not texto:
        flash("Comentário não pode estar vazio!", "danger")
        return redirect(url_for('ver_post', post_id=post_id))
    
    res = moderate_text(texto)
    if not res.get('allowed', True):
        flash("Comentário contém termos impróprios!", "danger")
        return redirect(url_for('ver_post', post_id=post_id))
    
    novo_id = len(COMENTARIOS_POSTS_DB) + 1
    comentario = Comentario(novo_id, post_id, session['user_email'], texto)
    COMENTARIOS_POSTS_DB.append(comentario)
    post.adicionar_comentario(novo_id)
    persistir_comentario_post(comentario)
    
    flash("Comentário adicionado com sucesso!", "success")
    return redirect(url_for('ver_post', post_id=post_id))

@app.route('/posts/<int:post_id>/deletar', methods=['POST'])
def deletar_post(post_id):
    if 'user_email' not in session: 
        return redirect(url_for('login'))
    post = POSTS_DB.get(post_id)
    if not post:
        flash("Post não encontrado.", "danger")
        return redirect(url_for('dashboard'))
    
    if session['user_email'] != post.autor_email and not session.get('is_admin'):
        flash("Sem permissão para deletar.", "danger")
        return redirect(url_for('ver_post', post_id=post_id))
    
    post.visivel = False
    marcar_post_visivel(post_id, False)
    flash("Post deletado!", "success")
    return redirect(url_for('dashboard'))

@app.route('/comentario/<int:comentario_id>/deletar', methods=['POST'])
def deletar_comentario_post(comentario_id):
    if 'user_email' not in session: 
        return redirect(url_for('login'))
    comentario = next((c for c in COMENTARIOS_POSTS_DB if c.id == comentario_id), None)
    if not comentario:
        flash("Comentário não encontrado.", "danger")
        return redirect(url_for('dashboard'))
    
    if session['user_email'] != comentario.autor_email and not session.get('is_admin'):
        flash("Sem permissão.", "danger")
        return redirect(url_for('ver_post', post_id=comentario.post_id))
    
    comentario.visivel = False
    marcar_comentario_post_visivel(comentario_id, False)
    flash("Comentário deletado!", "success")
    return redirect(url_for('ver_post', post_id=comentario.post_id))

@app.route('/moderacao/posts')
def painel_moderacao_posts():
    if not session.get('is_admin'): 
        return redirect(url_for('dashboard'))
    posts_ocultos = {k: v for k, v in POSTS_DB.items() if not v.visivel}
    comentarios_ocultos = [c for c in COMENTARIOS_POSTS_DB if not c.visivel]
    return render_template('painel_moderacao.html', posts_ocultos=posts_ocultos, comentarios_ocultos=comentarios_ocultos, usuarios=USUARIOS_DB)

@app.route('/moderacao/post/<int:post_id>/restaurar', methods=['POST'])
def restaurar_post(post_id):
    if not session.get('is_admin'): 
        return redirect(url_for('dashboard'))
    post = POSTS_DB.get(post_id)
    if post:
        post.visivel = True
        flash("Post restaurado!", "success")
    return redirect(url_for('painel_moderacao_posts'))

@app.route('/boss/usuarios')
def gerenciar_usuarios():
    if not session.get('is_admin'):
        return redirect(url_for('dashboard'))

    usuarios_lista = []
    for usuario in USUARIOS_DB.values():
        usuarios_lista.append({
            'email': usuario.email,
            'nome': usuario.nome or 'Sem nome',
            'nickname': (usuario.email or '').split('@', 1)[0],
            'avatar_url': getattr(usuario, 'foto_perfil', '') or '',
            'data_cadastro': getattr(usuario, 'data_cadastro', None) or 'Sem data',
            'amigos_count': len(GerenciadorAmigos.obter_amigos(usuario.email)),
            'jogos_count': len(GerenciadorBiblioteca.obter_biblioteca(usuario.email)),
            'status': usuario.obter_status_geral() if hasattr(usuario, 'obter_status_geral') else 'Offline',
            'is_admin': isinstance(usuario, Admin),
        })

    usuarios_lista.sort(key=lambda item: item['nome'].lower())
    return render_template('gerenciar_usuarios.html', usuarios=usuarios_lista, session_email=session.get('user_email'))


def _processar_exclusao_usuario(email):
    administrador = session.get('user_email')
    request_path = request.path
    operacao_inicio = time.time()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_context = f'admin={administrador} target={email} path={request_path} timestamp={timestamp}'
    app.logger.debug('[Excluir Usuário] entrada %s', log_context)

    if not session.get('is_admin'):
        mensagem = 'Acesso negado.'
        app.logger.warning('[Excluir Usuário] %s sem permissão', log_context)
        return {'success': False, 'message': mensagem}, 403

    email_normalizado = _normalizar_email(email)
    if not email_normalizado:
        mensagem = 'Usuário inválido.'
        app.logger.warning('[Excluir Usuário] %s inválido', log_context)
        return {'success': False, 'message': mensagem}, 400

    if email_normalizado == _normalizar_email(administrador):
        mensagem = 'Não é possível excluir sua própria conta.'
        app.logger.warning('[Excluir Usuário] %s tentativa de autoexclusão', log_context)
        return {'success': False, 'message': mensagem}, 400

    usuario_alvo = USUARIOS_DB.get(email_normalizado)
    if not usuario_alvo:
        mensagem = 'Usuário não encontrado.'
        app.logger.warning('[Excluir Usuário] %s não encontrado', log_context)
        return {'success': False, 'message': mensagem}, 404

    try:
        app.logger.debug('[Excluir Usuário] %s validações OK. iniciando exclusão', log_context)
        excluir_usuario_completo(email_normalizado)
        _remover_registros_relacionados_usuario(email_normalizado)
        duracao = time.time() - operacao_inicio
        app.logger.debug('[Excluir Usuário] %s exclusão concluída e commit efetuado', log_context)
        app.logger.info('[Excluir Usuário] %s resultado=sucesso duracao=%.3fs', log_context, duracao)
        return {'success': True, 'message': 'Usuário excluído com sucesso.'}, 200
    except Exception as exc:
        duracao = time.time() - operacao_inicio
        app.logger.exception('[Excluir Usuário] %s resultado=erro duracao=%.3fs', log_context, duracao)
        mensagem = f'Não foi possível excluir o usuário: {exc}'
        return {'success': False, 'message': mensagem}, 500


@app.route('/boss/usuarios/<path:email>/excluir', methods=['POST'])
def excluir_usuario(email):
    result, status_code = _processar_exclusao_usuario(email)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(result), status_code
    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'danger')
    return redirect(url_for('gerenciar_usuarios'))


@app.route('/api/boss/usuarios/<path:email>/excluir', methods=['POST'])
def api_excluir_usuario(email):
    result, status_code = _processar_exclusao_usuario(email)
    return jsonify(result), status_code


@app.route('/logout')
def logout():
    email = session.get('user_email')
    if email in ONLINE_USERS:
        ONLINE_USERS.discard(email)
    _remover_presenca_call(email)
    user = USUARIOS_DB.get(email)
    if user:
        user.discord_online = False
    session.clear()
    return redirect(url_for('login'))

# --- Rotas de API para AJAX ---
@app.route('/api/reviews/usuario/<email>')
def api_reviews_usuario(email):
    reviews = GerenciadorReviews.obter_reviews_usuario(email)
    reviews_data = []
    for review in reviews:
        jogo = JOGOS_DB.get(review.jogo_id)
        comentarios = GerenciadorReviews.obter_comentarios_review(review.id)
        reviews_data.append({
            'id': review.id,
            'titulo': review.titulo,
            'conteudo': review.conteudo,
            'nota': review.nota,
            'jogo_titulo': jogo.titulo if jogo else f"Jogo #{review.jogo_id}",
            'data': review.data_criacao.strftime('%d/%m/%Y'),
            'total_comentarios': len(comentarios),
            'comentarios': [
                {
                    'id': comentario.id,
                    'autor_email': comentario.email_usuario,
                    'autor_nome': USUARIOS_DB.get(comentario.email_usuario).nome if USUARIOS_DB.get(comentario.email_usuario) else comentario.email_usuario,
                    'texto': comentario.texto,
                    'data': comentario.data_criacao.strftime('%d/%m/%Y %H:%M')
                }
                for comentario in comentarios
            ]
        })
    return jsonify({'reviews': reviews_data})

@app.route('/api/biblioteca/<email>')
def api_biblioteca(email):
    if email != session.get('user_email'):
        return jsonify({'erro': 'Acesso negado'}), 403
    biblioteca = GerenciadorBiblioteca.obter_biblioteca(email)
    items = []
    for item in biblioteca:
        jogo = JOGOS_DB.get(item.jogo_id)
        items.append({
            'id': item.id,
            'jogo_id': item.jogo_id,
            'jogo_titulo': jogo.titulo if jogo else f"Jogo #{item.jogo_id}",
            'data_adicao': item.data_adicao.strftime('%d/%m/%Y'),
            'tempo_jogado': item.tempo_jogado_horas,
            'concluido': item.concluido,
            'platinado': item.platinado
        })
    return jsonify({'biblioteca': items})

@app.route('/api/amigos/<email>')
def api_amigos(email):
    amigos = GerenciadorAmigos.obter_amigos(email)
    amigos_data = []
    for amigo_email in amigos:
        user = USUARIOS_DB.get(amigo_email)
        if user:
            amigos_data.append({'email': amigo_email, 'nome': user.nome})
    return jsonify({'amigos': amigos_data})

from threading import Event, Thread
import webbrowser

if IS_WINDOWS and not IS_VERCEL:
    try:
        import webview
    except Exception as exc:
        webview = None
        WEBVIEW_IMPORT_ERROR = exc
else:
    webview = None
    WEBVIEW_IMPORT_ERROR = None


def iniciar_flask():
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)


class DesktopApi:
    def select_folder(self) -> str:
        return select_folder()


if __name__ == '__main__':
    print('[Startup] Inicializando detector de presença Steam/Hydra...')
    try:
        inicializar_detector(callback_mudanca_presenca_global)
        print('[Startup] OK - Detector de presença iniciado com sucesso')
    except Exception as e:
        print(f'[Startup] ERRO - Falha ao inicializar detector: {e}')
        import traceback
        traceback.print_exc()
    
    # Iniciar Flask em thread daemon (não interfere com detector)
    Thread(target=iniciar_flask, daemon=True).start()

    if webview is None:
        print(f'Webview indisponível: {WEBVIEW_IMPORT_ERROR}')
        print('Abrindo o navegador em vez disso...')
        webbrowser.open('http://127.0.0.1:5000/login')
    else:
        try:
            webview.create_window(
                'GameUnexa',
                'http://127.0.0.1:5000/login',
                width=1400,
                height=900,
                js_api=DesktopApi(),
            )
            webview.start()
        except Exception as exc:
            print(f'Não foi possível iniciar a janela desktop: {exc}')
            print('Abrindo o navegador em vez disso...')
            webbrowser.open('http://127.0.0.1:5000/login')

    try:
        Event().wait()
    except KeyboardInterrupt:
        print('Encerrando o servidor...')