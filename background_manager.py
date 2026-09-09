from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import re
import uuid

from PIL import Image
from werkzeug.utils import secure_filename

from database import get_connection

BASE_DIR = Path(__file__).resolve().parent
BACKGROUND_DIR = BASE_DIR / 'userdata' / 'backgrounds'
BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif'}
VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'm4v'}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
IMAGE_MIMES = {'image/png', 'image/jpeg', 'image/webp', 'image/bmp', 'image/gif'}
VIDEO_MIMES = {'video/mp4', 'video/webm', 'video/quicktime', 'video/x-m4v'}
BACKGROUND_TYPES = {
    'default', 'vanta', 'particles', 'image', 'gif', 'video',
    'slideshow', 'random-videos', 'random-gifs', 'online'
}


def _extension(filename: str) -> str:
    return Path(filename or '').suffix.lower().lstrip('.')


def validar_arquivo_background(filename: str, mimetype: str | None = None) -> str:
    extension = _extension(filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError('Formato não permitido. Use imagem, GIF ou vídeo compatível.')
    mime = (mimetype or '').lower().split(';', 1)[0]
    if extension in IMAGE_EXTENSIONS:
        if mime and mime not in IMAGE_MIMES:
            raise ValueError('O tipo MIME da imagem não é válido.')
    elif mime and mime not in VIDEO_MIMES:
        raise ValueError('O tipo MIME do vídeo não é válido.')
    return extension


def salvar_upload_background(upload) -> str:
    if not upload or not upload.filename:
        raise ValueError('Nenhum arquivo foi selecionado.')
    extension = validar_arquivo_background(upload.filename, upload.mimetype)
    safe_name = secure_filename(Path(upload.filename).stem) or 'background'
    target = BACKGROUND_DIR / f'{safe_name}-{uuid.uuid4().hex[:10]}.{extension}'
    upload.save(target)
    if extension in IMAGE_EXTENSIONS:
        try:
            with Image.open(target) as image:
                image.verify()
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise ValueError('O arquivo não é uma imagem válida.') from exc
    return f'backgrounds/{target.name}'


def caminho_background(relative_path: str) -> Path:
    path = (BACKGROUND_DIR.parent / (relative_path or '')).resolve()
    if BACKGROUND_DIR.parent.resolve() not in path.parents:
        raise ValueError('Caminho de background inválido.')
    return path


def _normalizar_config(data: dict | None) -> dict:
    data = dict(data or {})
    options = data.get('options') or {}
    if isinstance(options, str):
        try:
            options = json.loads(options)
        except json.JSONDecodeError:
            options = {}
    data.update(options)
    tipo = str(data.get('type') or 'default').strip().lower()
    if tipo not in BACKGROUND_TYPES:
        tipo = 'default'
    try:
        speed = max(0, min(5, float(data.get('speed', 1))))
    except (TypeError, ValueError):
        speed = 1
    try:
        opacity = max(0, min(1, float(data.get('opacity', 1))))
    except (TypeError, ValueError):
        opacity = 1
    try:
        fps = int(data.get('fps', 60))
    except (TypeError, ValueError):
        fps = 60
    fps = fps if fps in {30, 60, 0} else 60
    try:
        transition = max(0, min(2000, int(data.get('transition', 500))))
    except (TypeError, ValueError):
        transition = 500
    config = {
        'type': tipo,
        'effect': re.sub(r'[^a-z0-9_-]', '', str(data.get('effect') or '').lower())[:40],
        'file': str(data.get('file') or '')[:500],
        'folder': str(data.get('folder') or '')[:500],
        'color1': str(data.get('color1') or '#38bdf8')[:20],
        'color2': str(data.get('color2') or '#0f172a')[:20],
        'speed': speed,
        'opacity': opacity,
        'fps': fps,
        'shuffle': 1 if data.get('shuffle') else 0,
        'transition': transition,
        'options': options,
    }
    for key in ('amount', 'size', 'interval', 'connections', 'mouse', 'eco', 'disable_notebook', 'disable_game', 'reduce_cpu', 'reduce_gpu'):
        if key in data:
            config[key] = data[key]
            config['options'][key] = data[key]
    return config


def obter_background(user_id: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute('SELECT * FROM background_settings WHERE user_id = ?', (user_id,)).fetchone()
        if not row:
            return _normalizar_config({})
        config = dict(row)
        config.pop('id', None)
        config.pop('user_id', None)
        return _normalizar_config(config)
    finally:
        conn.close()


def salvar_background(user_id: str, data: dict) -> dict:
    config = _normalizar_config(data)
    if config['file'] and not config['file'].startswith(('http://', 'https://')):
        caminho_background(config['file'])
    updated_at = datetime.now().isoformat(timespec='seconds')
    conn = get_connection()
    try:
        conn.execute(
            '''INSERT INTO background_settings
               (user_id, type, effect, file, folder, color1, color2, speed, opacity, fps, shuffle, transition, options, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
               type=excluded.type, effect=excluded.effect, file=excluded.file, folder=excluded.folder,
               color1=excluded.color1, color2=excluded.color2, speed=excluded.speed, opacity=excluded.opacity,
               fps=excluded.fps, shuffle=excluded.shuffle, transition=excluded.transition, options=excluded.options, updated_at=excluded.updated_at''',
            (user_id, config['type'], config['effect'], config['file'], config['folder'], config['color1'],
             config['color2'], config['speed'], config['opacity'], config['fps'], config['shuffle'],
             config['transition'], json.dumps(config.get('options', {}), ensure_ascii=True), updated_at),
        )
        conn.commit()
    finally:
        conn.close()
    return config


def redefinir_background(user_id: str) -> dict:
    return salvar_background(user_id, {'type': 'default'})


def arquivos_da_pasta(folder: str, extensions: set[str]) -> list[str]:
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        raise ValueError('A pasta selecionada não existe.')
    return sorted(
        (str(path) for path in root.iterdir() if path.is_file() and _extension(path.name) in extensions),
        key=str.lower,
    )
