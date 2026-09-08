import json
import os
import sqlite3
import smtplib
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from paths import DB_PATH, ENV_PATH, resource_path

BASE_DIR = os.path.dirname(__file__)
TEMPLATES_DIR = resource_path('templates')

TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(['html', 'xml'])
)
EXECUTOR = ThreadPoolExecutor(max_workers=4)
_EXECUTOR_LOCK = threading.Lock()


def _carregar_env_local() -> None:
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH, 'r', encoding='utf-8') as handle:
        for linha in handle:
            texto = linha.strip()
            if not texto or texto.startswith('#') or '=' not in texto:
                continue
            chave, valor = texto.split('=', 1)
            chave = chave.strip()
            valor = valor.strip().strip('"').strip("'")
            if chave and chave not in os.environ:
                os.environ[chave] = valor


_carregar_env_local()


def _coerce_bool(valor: Any, default: bool = False) -> bool:
    if valor is None:
        return default
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in {'1', 'true', 'yes', 'on', 'sim'}


def _coerce_int(valor: Any, default: int) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return default


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables() -> None:
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS email_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_envio TEXT NOT NULL,
            destinatario TEXT NOT NULL,
            tipo_email TEXT NOT NULL,
            status TEXT NOT NULL,
            tempo_ms INTEGER DEFAULT 0,
            tentativas INTEGER DEFAULT 0,
            erro TEXT
        );

        CREATE TABLE IF NOT EXISTS email_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_criacao TEXT NOT NULL,
            destinatario TEXT NOT NULL,
            assunto TEXT NOT NULL,
            corpo TEXT NOT NULL,
            tipo_email TEXT NOT NULL,
            template_name TEXT,
            context_json TEXT,
            attachments_json TEXT,
            smtp_enabled INTEGER,
            status TEXT NOT NULL DEFAULT 'queued',
            tentativas INTEGER NOT NULL DEFAULT 0,
            erro TEXT,
            ultimo_envio TEXT
        );
        """
    )

    existing_columns = [row[1] for row in conn.execute("PRAGMA table_info(email_queue)").fetchall()]
    if 'attachments_json' not in existing_columns:
        conn.execute('ALTER TABLE email_queue ADD COLUMN attachments_json TEXT')
    if 'smtp_enabled' not in existing_columns:
        conn.execute('ALTER TABLE email_queue ADD COLUMN smtp_enabled INTEGER')
    conn.commit()
    conn.close()


_ensure_tables()


def get_smtp_config() -> dict[str, Any]:
    _carregar_env_local()
    return {
        'enabled': _coerce_bool(os.environ.get('SMTP_ENABLED', 'true'), True),
        'server': (os.environ.get('SMTP_SERVER') or '').strip(),
        'port': _coerce_int(os.environ.get('SMTP_PORT', '587'), 587),
        'username': (os.environ.get('SMTP_USERNAME') or '').strip(),
        'password': (os.environ.get('SMTP_PASSWORD') or '').strip(),
        'tls': _coerce_bool(os.environ.get('SMTP_TLS', 'true'), True),
        'ssl': _coerce_bool(os.environ.get('SMTP_SSL', 'false'), False),
        'mail_from': (os.environ.get('MAIL_FROM') or os.environ.get('SMTP_USERNAME') or 'noreply@gamelink.local').strip(),
        'mail_from_name': (os.environ.get('MAIL_FROM_NAME') or 'GameUnexa').strip(),
        'admin_support_email': (os.environ.get('ADMIN_SUPPORT_EMAIL') or 'gracilianoa50@gmail.com').strip(),
    }


def update_smtp_config(values: dict[str, Any]) -> dict[str, Any]:
    env_path = Path(ENV_PATH)
    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding='utf-8').splitlines()

    current = {}
    for linha in existing_lines:
        if '=' in linha and not linha.strip().startswith('#'):
            chave, valor = linha.split('=', 1)
            current[chave.strip()] = valor.strip()

    for chave, valor in values.items():
        if valor is None:
            continue
        current[chave] = str(valor)
        os.environ[chave] = str(valor)

    lines = []
    for chave in [
        'SMTP_ENABLED',
        'SMTP_SERVER',
        'SMTP_PORT',
        'SMTP_USERNAME',
        'SMTP_PASSWORD',
        'SMTP_TLS',
        'SMTP_SSL',
        'MAIL_FROM',
        'MAIL_FROM_NAME',
        'ADMIN_SUPPORT_EMAIL',
    ]:
        if chave in current:
            lines.append(f'{chave}={current[chave]}')
    if lines:
        env_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return get_smtp_config()


def _sanitize_error(error: Exception | str | None) -> str | None:
    if not error:
        return None
    texto = str(error)
    if not texto:
        return None
    return texto.replace(os.environ.get('SMTP_PASSWORD', ''), '***').replace(os.environ.get('SMTP_USERNAME', ''), '***')


def _record_log(destinatario: str, tipo_email: str, status: str, tempo_ms: int, tentativas: int, erro: str | None = None) -> None:
    conn = get_connection()
    conn.execute(
        '''
        INSERT INTO email_logs (data_envio, destinatario, tipo_email, status, tempo_ms, tentativas, erro)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            datetime.now().isoformat(timespec='seconds'),
            destinatario,
            tipo_email,
            status,
            tempo_ms,
            tentativas,
            erro,
        ),
    )
    conn.commit()
    conn.close()


def _enqueue_email(destinatario: str, assunto: str, corpo: str, tipo_email: str, template_name: str | None = None, context: dict[str, Any] | None = None, attachments: list[str] | None = None, smtp_enabled: bool | None = None) -> int:
    _ensure_tables()
    conn = get_connection()
    cursor = conn.execute(
        '''
        INSERT INTO email_queue (data_criacao, destinatario, assunto, corpo, tipo_email, template_name, context_json, attachments_json, smtp_enabled, status, tentativas, erro, ultimo_envio)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            datetime.now().isoformat(timespec='seconds'),
            destinatario,
            assunto,
            corpo,
            tipo_email,
            template_name,
            None if context is None else json.dumps(context),
            None if attachments is None else json.dumps(attachments),
            None if smtp_enabled is None else int(bool(smtp_enabled)),
            'queued',
            0,
            None,
            None,
        ),
    )
    conn.commit()
    queue_id = cursor.lastrowid
    conn.close()
    return queue_id


def _render_html_template(template_name: str, context: dict[str, Any]) -> str:
    try:
        template = TEMPLATE_ENV.get_template(template_name)
        return template.render(**context)
    except Exception:
        return ''


def _build_message(destinatario: str, assunto: str, corpo: str, template_name: str | None = None, context: dict[str, Any] | None = None) -> EmailMessage:
    config = get_smtp_config()
    message = EmailMessage()
    message['Subject'] = assunto
    message['From'] = f"{config['mail_from_name']} <{config['mail_from']}>"
    message['To'] = destinatario
    message['Reply-To'] = config['mail_from']
    message.set_content(corpo, subtype='plain')

    if template_name:
        html_body = _render_html_template(template_name, context or {})
        if html_body:
            message.add_alternative(html_body, subtype='html')
    return message


def _send_message_smtp(message: EmailMessage, config: dict[str, Any] | None = None) -> None:
    config = config or get_smtp_config()
    if not config['enabled'] or not config['server']:
        raise RuntimeError('SMTP desativado ou sem servidor configurado.')

    if config['ssl']:
        server = smtplib.SMTP_SSL(config['server'], config['port'], timeout=20)
    else:
        server = smtplib.SMTP(config['server'], config['port'], timeout=20)

    try:
        server.ehlo()
        if config['tls'] and not config['ssl']:
            server.starttls()
            server.ehlo()
        if config['username']:
            server.login(config['username'], config['password'])
        server.send_message(message)
    finally:
        server.quit()


def processar_fila_email(limit: int = 10) -> list[dict[str, Any]]:
    _ensure_tables()
    conn = get_connection()
    rows = conn.execute(
        '''
        SELECT * FROM email_queue
        WHERE status IN ('queued', 'failed')
        ORDER BY id ASC
        LIMIT ?
        ''',
        (limit,),
    ).fetchall()
    conn.close()

    resultados = []
    for row in rows:
        resultados.append(processar_email_queue_item(row['id']))
    return resultados


def processar_email_queue_item(queue_id: int) -> dict[str, Any]:
    _ensure_tables()
    conn = get_connection()
    row = conn.execute('SELECT * FROM email_queue WHERE id = ?', (queue_id,)).fetchone()
    if not row:
        conn.close()
        return {'status': 'missing', 'queue_id': queue_id}

    config = get_smtp_config()
    if not config['enabled'] or not config['server']:
        erro = 'SMTP desativado ou sem servidor configurado.'
        conn.execute(
            'UPDATE email_queue SET status = ?, tentativas = tentativas + 1, erro = ? WHERE id = ?',
            ('queued', erro, queue_id),
        )
        conn.commit()
        conn.close()
        _record_log(row['destinatario'], row['tipo_email'], 'queued', 0, int(row['tentativas']) + 1, erro)
        return {'status': 'queued', 'queue_id': queue_id}

    tentativa = int(row['tentativas']) + 1
    started = datetime.now()
    try:
        context = None
        if row['context_json']:
            try:
                context = json.loads(row['context_json'])
            except Exception:
                context = {'context': row['context_json']}

        attachments = None
        if row['attachments_json']:
            try:
                attachments = json.loads(row['attachments_json'])
            except Exception:
                attachments = None

        message = _build_message(
            row['destinatario'],
            row['assunto'],
            row['corpo'],
            row['template_name'],
            context,
        )
        if attachments:
            for attachment_path in attachments:
                try:
                    abs_path = os.path.abspath(attachment_path)
                    if os.path.exists(abs_path):
                        with open(abs_path, 'rb') as f:
                            data = f.read()
                        maintype = 'application'
                        subtype = 'octet-stream'
                        filename = os.path.basename(abs_path)
                        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
                except Exception:
                    pass

        if row['smtp_enabled'] is not None:
            config['enabled'] = bool(row['smtp_enabled'])

        _send_message_smtp(message, config=config)
        tempo_ms = int((datetime.now() - started).total_seconds() * 1000)
        conn.execute(
            'UPDATE email_queue SET status = ?, tentativas = ?, erro = NULL, ultimo_envio = ? WHERE id = ?',
            ('sent', tentativa, datetime.now().isoformat(timespec='seconds'), queue_id),
        )
        conn.commit()
        conn.close()
        _record_log(row['destinatario'], row['tipo_email'], 'sent', tempo_ms, tentativa)
        return {'status': 'sent', 'queue_id': queue_id, 'attempts': tentativa}
    except Exception as exc:
        tempo_ms = int((datetime.now() - started).total_seconds() * 1000)
        erro = _sanitize_error(exc) or 'Erro desconhecido ao enviar e-mail.'
        conn.execute(
            'UPDATE email_queue SET status = ?, tentativas = ?, erro = ?, ultimo_envio = ? WHERE id = ?',
            ('failed', tentativa, erro, datetime.now().isoformat(timespec='seconds'), queue_id),
        )
        conn.commit()
        conn.close()
        _record_log(row['destinatario'], row['tipo_email'], 'failed', tempo_ms, tentativa, erro)
        return {'status': 'failed', 'queue_id': queue_id, 'error': erro, 'attempts': tentativa}


def enviar_email(
    destinatario: str,
    assunto: str,
    corpo: str,
    tipo_email: str = 'general',
    template_name: str | None = None,
    context: dict[str, Any] | None = None,
    attachments: list[str] | None = None,
    smtp_enabled: bool | None = None,
    background: bool = True,
) -> dict[str, Any]:
    _ensure_tables()
    config = get_smtp_config()
    if smtp_enabled is not None:
        config['enabled'] = smtp_enabled

    queue_id = _enqueue_email(destinatario, assunto, corpo, tipo_email, template_name, context, attachments, smtp_enabled)
    if background:
        with _EXECUTOR_LOCK:
            EXECUTOR.submit(processar_email_queue_item, queue_id)
        return {'status': 'queued', 'queue_id': queue_id}

    return processar_email_queue_item(queue_id)


def enviar_email_teste(destinatario: str, background: bool = True) -> dict[str, Any]:
    return enviar_email(
        destinatario=destinatario,
        assunto='Teste SMTP GameUnexa',
        corpo='Este é um e-mail de teste enviado pelo sistema SMTP do GameUnexa.',
        tipo_email='teste',
        template_name='emails/teste.html',
        context={'titulo': 'Teste SMTP', 'mensagem': 'Este é um e-mail de teste enviado pelo sistema SMTP do GameUnexa.'},
        background=background,
    )


def listar_logs(limit: int = 50) -> list[dict[str, Any]]:
    _ensure_tables()
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM email_logs ORDER BY id DESC LIMIT ?',
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def listar_fila(limit: int = 50) -> list[dict[str, Any]]:
    _ensure_tables()
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM email_queue ORDER BY id DESC LIMIT ?',
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
