import os
import re
import wave
from datetime import datetime
from uuid import uuid4

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from database import get_connection
from paths import SOUNDBOARD_DIR

soundboard_bp = Blueprint('soundboard', __name__)

SOUNDBOARD_UPLOAD_DIR = str(SOUNDBOARD_DIR)
SOUNDBOARD_ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a', 'aac', 'flac', 'webm'}
MAX_SOUNDBOARD_UPLOAD_SIZE = 15 * 1024 * 1024
MAX_SOUNDBOARD_DURATION = 10.0

try:
    from mutagen import File as mutagen_file, MutagenError
except ImportError:
    mutagen_file = None
    MutagenError = Exception


def _soundboard_category_slug(nome: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', (nome or '').strip().lower()).strip('-') or 'geral'


def _soundboard_arquivo_valido(nome_arquivo: str | None) -> bool:
    if not nome_arquivo:
        return False
    nome_seguro = secure_filename(nome_arquivo)
    if '.' not in nome_seguro:
        return False
    ext = nome_seguro.rsplit('.', 1)[-1].lower()
    return ext in SOUNDBOARD_ALLOWED_EXTENSIONS


def _soundboard_salvar_arquivo(upload) -> dict:
    if not upload or not getattr(upload, 'filename', ''):
        raise ValueError('arquivo_obrigatorio')

    nome_original = secure_filename(upload.filename)
    if not _soundboard_arquivo_valido(nome_original):
        raise ValueError('Formato de áudio inválido. Use MP3, WAV, OGG, M4A, AAC, FLAC ou WEBM.')

    tamanho = getattr(upload, 'content_length', None)
    if tamanho is None:
        upload.stream.seek(0, os.SEEK_END)
        tamanho = upload.stream.tell()
        upload.stream.seek(0)
    if tamanho > MAX_SOUNDBOARD_UPLOAD_SIZE:
        raise ValueError('Arquivo de áudio muito grande. Máximo permitido: 15 MB.')

    nome_seguro = f'{uuid4().hex}_{nome_original}'
    caminho_local = os.path.join(SOUNDBOARD_UPLOAD_DIR, nome_seguro)
    upload.save(caminho_local)
    try:
        duration = _soundboard_obter_duracao(caminho_local)
    except ValueError:
        if os.path.exists(caminho_local):
            os.remove(caminho_local)
        raise
    url = url_for('app_data_upload', filename=f'soundboard/{nome_seguro}', _external=False)
    return {'filename': nome_seguro, 'file_path': caminho_local, 'storage_url': url, 'duration': duration}


def _soundboard_obter_duracao(file_path: str) -> float:
    try:
        if file_path.lower().endswith('.wav'):
            with wave.open(file_path, 'rb') as audio_file:
                duration = audio_file.getnframes() / float(audio_file.getframerate() or 1)
        elif mutagen_file:
            audio_file = mutagen_file(file_path)
            duration = float(getattr(getattr(audio_file, 'info', None), 'length', 0) or 0)
        elif file_path.lower().endswith('.mp3'):
            duration = _soundboard_mp3_duracao_fallback(file_path)
        else:
            raise ValueError('Não foi possível identificar a duração deste áudio.')
    except (OSError, TypeError, ValueError, ZeroDivisionError, MutagenError) as exc:
        raise ValueError('Não foi possível identificar a duração deste áudio.') from exc
    if duration <= 0:
        raise ValueError('Não foi possível identificar a duração deste áudio.')
    if duration > MAX_SOUNDBOARD_DURATION:
        raise ValueError('O áudio deve ter no máximo 10 segundos.')
    return round(duration, 3)


def _soundboard_mp3_duracao_fallback(file_path: str) -> float:
    bitrate_tables = {
        3: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
        2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
    }
    sample_rates = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}
    samples_per_frame = {3: 1152, 2: 576, 0: 576}
    frame_count = 0
    sample_count = 0
    with open(file_path, 'rb') as audio_file:
        data = audio_file.read()
    for index in range(max(0, len(data) - 4)):
        first, second, third, fourth = data[index:index + 4]
        if first != 0xFF or second & 0xE0 != 0xE0:
            continue
        version = (second >> 3) & 0x03
        layer = (second >> 1) & 0x03
        bitrate_index = (third >> 4) & 0x0F
        sample_rate_index = (third >> 2) & 0x03
        if version == 1 or layer != 1 or bitrate_index in {0, 15} or sample_rate_index == 3:
            continue
        version_group = 3 if version == 3 else 2
        if version == 0:
            version_group = 0
        bitrate = bitrate_tables[3 if version_group == 3 else 2][bitrate_index] * 1000
        sample_rate = sample_rates[version_group][sample_rate_index]
        if not bitrate or not sample_rate:
            continue
        padding = (third >> 1) & 1
        frame_length = (144 * bitrate // sample_rate if version_group == 3 else 72 * bitrate // sample_rate) + padding
        if frame_length < 24 or index + frame_length > len(data):
            continue
        frame_count += 1
        sample_count += samples_per_frame[version_group]
        if frame_count > 200000:
            break
    if not frame_count:
        raise ValueError('Não foi possível identificar a duração deste áudio.')
    return sample_count / float(_soundboard_mp3_sample_rate(data, sample_rates))


def _soundboard_mp3_sample_rate(data: bytes, sample_rates: dict) -> int:
    for index in range(max(0, len(data) - 4)):
        if data[index] == 0xFF and data[index + 1] & 0xE0 == 0xE0:
            version = (data[index + 1] >> 3) & 0x03
            sample_rate_index = (data[index + 2] >> 2) & 0x03
            if version != 1 and sample_rate_index < 3:
                return sample_rates[3 if version == 3 else 2 if version == 2 else 0][sample_rate_index]
    raise ValueError('Não foi possível identificar a duração deste áudio.')


def _soundboard_serializar_efeito(row) -> dict:
    return {
        'id': row['id'],
        'name': row['name'],
        'description': row['description'] or '',
        'filename': row['filename'],
        'file_path': row['file_path'],
        'url': row['storage_url'] or url_for('static', filename=f'uploads/soundboard/{row["filename"]}', _external=False),
        'icon': row['icon'] or '🔊',
        'duration': round(float(row['duration'] or 0), 3),
        'volume': max(0.0, min(1.0, float(row['volume'] or 1.0))),
        'play_count': row['play_count'] or 0,
        'recent_at': row['recent_at'],
        'favorite': bool(row['favorite']),
        'created_by': row['created_by'],
        'created_at': row['created_at'],
        'category': {'id': row['category_id'], 'name': row['category_name'], 'slug': row['category_slug'], 'icon': row['category_icon'] or '🎵'} if row['category_id'] else None,
    }


def _soundboard_ensure_category(conn, name: str, icon: str = '') -> int:
    cleaned_name = (name or 'Geral').strip() or 'Geral'
    slug = _soundboard_category_slug(cleaned_name)
    row = conn.execute('SELECT id FROM sound_categories WHERE slug = ? LIMIT 1', (slug,)).fetchone()
    if row:
        conn.execute('UPDATE sound_categories SET name = ?, icon = ? WHERE id = ?', (cleaned_name, icon or '', row['id']))
        return row['id']
    cursor = conn.execute(
        'INSERT INTO sound_categories (name, slug, icon, created_at) VALUES (?, ?, ?, ?)',
        (cleaned_name, slug, icon or '', datetime.utcnow().isoformat(timespec='seconds')),
    )
    return cursor.lastrowid


@soundboard_bp.route('/api/soundboard/categories')
def api_soundboard_categories():
    if 'user_email' not in session:
        return jsonify({'ok': False, 'error': 'not_logged_in'}), 401
    conn = get_connection()
    try:
        rows = conn.execute('SELECT id, name, slug, icon FROM sound_categories ORDER BY name ASC').fetchall()
        return jsonify({
            'ok': True,
            'categories': [
                {'id': row['id'], 'name': row['name'], 'slug': row['slug'], 'icon': row['icon'] or '🎵'}
                for row in rows
            ]
        })
    finally:
        conn.close()


@soundboard_bp.route('/api/soundboard')
def api_soundboard_list():
    if 'user_email' not in session:
        return jsonify({'ok': False, 'error': 'not_logged_in'}), 401

    page = max(1, int(request.args.get('page', 1)))
    per_page = min(60, max(8, int(request.args.get('per_page', 24))))
    search = (request.args.get('search') or '').strip()
    category_slug = (request.args.get('category') or '').strip()
    favorites_only = request.args.get('favorites', '').lower() in {'1', 'true', 'yes'}
    recent_only = request.args.get('recent', '').lower() in {'1', 'true', 'yes'}

    conn = get_connection()
    try:
        where = ['se.is_active = 1']
        params = []
        if search:
            term = f'%{search}%'
            where.append('(se.name LIKE ? OR se.description LIKE ? OR sc.name LIKE ?)')
            params.extend([term, term, term])
        if category_slug:
            where.append('sc.slug = ?')
            params.append(category_slug)
        if favorites_only:
            where.append('EXISTS (SELECT 1 FROM sound_effect_favorites sf WHERE sf.effect_id = se.id AND sf.user_email = ?)')
            params.append(session['user_email'])
        if recent_only:
            where.append('EXISTS (SELECT 1 FROM sound_effect_history sh WHERE sh.effect_id = se.id AND sh.user_email = ? LIMIT 1)')
            params.append(session['user_email'])

        order_by = 'recent_at DESC, se.play_count DESC' if recent_only else 'se.play_count DESC, se.created_at DESC'
        sql = '''
            SELECT se.id, se.name, se.description, se.filename, se.file_path, se.storage_url, se.icon,
                   se.play_count, se.created_by, se.created_at, se.duration, se.volume,
                   sc.id AS category_id, sc.name AS category_name, sc.slug AS category_slug, sc.icon AS category_icon,
                   (SELECT MAX(sh.played_at) FROM sound_effect_history sh WHERE sh.effect_id = se.id AND sh.user_email = ?) AS recent_at,
                   EXISTS (SELECT 1 FROM sound_effect_favorites sf WHERE sf.effect_id = se.id AND sf.user_email = ?) AS favorite
            FROM sound_effects se
            LEFT JOIN sound_categories sc ON sc.id = se.category_id
            WHERE %s
            ORDER BY %s
        ''' % (' AND '.join(where), order_by)

        params = [session['user_email'], session['user_email']] + params
        rows = conn.execute(sql, params).fetchall()
        available_rows = [row for row in rows if os.path.isfile(row['file_path'])]
        total = len(available_rows)
        page_rows = available_rows[(page - 1) * per_page:page * per_page]
        effects = [_soundboard_serializar_efeito(row) for row in page_rows]

        total_pages = max(1, (total + per_page - 1) // per_page)
        return jsonify({'ok': True, 'page': page, 'per_page': per_page, 'total': total, 'total_pages': total_pages, 'effects': effects})
    finally:
        conn.close()


@soundboard_bp.route('/api/soundboard', methods=['POST'])
def api_soundboard_create():
    if 'user_email' not in session:
        return jsonify({'ok': False, 'error': 'not_logged_in'}), 401

    file_upload = request.files.get('file')
    if not file_upload or not getattr(file_upload, 'filename', ''):
        return jsonify({'ok': False, 'error': 'arquivo_obrigatorio'}), 400

    try:
        audio_info = _soundboard_salvar_arquivo(file_upload)
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400

    name = (request.form.get('name') or '').strip()
    description = (request.form.get('description') or '').strip()
    category_name = (request.form.get('category') or 'Geral').strip() or 'Geral'
    icon = (request.form.get('icon') or '🔊').strip() or '🔊'

    if not name:
        if os.path.exists(audio_info['file_path']):
            os.remove(audio_info['file_path'])
        return jsonify({'ok': False, 'error': 'nome_obrigatorio'}), 400

    conn = get_connection()
    try:
        category_id = _soundboard_ensure_category(conn, category_name, icon)
        created_at = datetime.utcnow().isoformat(timespec='seconds')
        cursor = conn.execute(
            'INSERT INTO sound_effects (name, description, filename, file_path, storage_url, category_id, icon, duration, volume, created_by, created_at, updated_at, is_active, play_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1.0, ?, ?, ?, 1, 0)',
            (name, description, audio_info['filename'], audio_info['file_path'], audio_info['storage_url'], category_id, icon, audio_info['duration'], session['user_email'], created_at, created_at),
        )
        conn.commit()
        effect = conn.execute('''
            SELECT se.*, sc.id AS category_id, sc.name AS category_name, sc.slug AS category_slug, sc.icon AS category_icon,
                   NULL AS recent_at, 0 AS favorite
            FROM sound_effects se LEFT JOIN sound_categories sc ON sc.id = se.category_id WHERE se.id = ?
        ''', (cursor.lastrowid,)).fetchone()
        return jsonify({'ok': True, 'effect': _soundboard_serializar_efeito(effect)})
    except Exception as exc:
        if audio_info and os.path.exists(audio_info['file_path']):
            os.remove(audio_info['file_path'])
        current_app.logger.exception('[Soundboard] Falha ao persistir efeito: %s', exc)
        return jsonify({'ok': False, 'error': 'O servidor não conseguiu salvar o efeito.'}), 500
    finally:
        conn.close()


@soundboard_bp.route('/api/soundboard/<int:effect_id>/play', methods=['POST'])
def api_soundboard_play(effect_id):
    if 'user_email' not in session:
        return jsonify({'ok': False, 'error': 'not_logged_in'}), 401
    conn = get_connection()
    try:
        row = conn.execute('SELECT id, play_count FROM sound_effects WHERE id = ? AND is_active = 1', (effect_id,)).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'not_found'}), 404
        updated_count = int(row['play_count']) + 1
        conn.execute('UPDATE sound_effects SET play_count = ?, updated_at = ? WHERE id = ?', (updated_count, datetime.utcnow().isoformat(timespec='seconds'), effect_id))
        conn.execute('INSERT INTO sound_effect_history (effect_id, user_email, played_at) VALUES (?, ?, ?)', (effect_id, session['user_email'], datetime.utcnow().isoformat(timespec='seconds')))
        conn.commit()
        return jsonify({'ok': True, 'play_count': updated_count})
    finally:
        conn.close()


@soundboard_bp.route('/api/soundboard/<int:effect_id>/favorite', methods=['POST', 'DELETE'])
def api_soundboard_favorite(effect_id):
    if 'user_email' not in session:
        return jsonify({'ok': False, 'error': 'not_logged_in'}), 401
    conn = get_connection()
    try:
        if request.method == 'POST':
            conn.execute('INSERT OR IGNORE INTO sound_effect_favorites (effect_id, user_email, created_at) VALUES (?, ?, ?)', (effect_id, session['user_email'], datetime.utcnow().isoformat(timespec='seconds')))
            conn.commit()
            return jsonify({'ok': True, 'favorite': True})
        conn.execute('DELETE FROM sound_effect_favorites WHERE effect_id = ? AND user_email = ?', (effect_id, session['user_email']))
        conn.commit()
        return jsonify({'ok': True, 'favorite': False})
    finally:
        conn.close()


@soundboard_bp.route('/admin/soundboard')
def admin_soundboard():
    if 'user_email' not in session or not session.get('is_admin'):
        flash('Você precisa ser administrador para acessar este painel.', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('admin_soundboard.html')


@soundboard_bp.route('/api/soundboard/<int:effect_id>/volume', methods=['POST'])
def api_soundboard_volume(effect_id):
    if 'user_email' not in session:
        return jsonify({'ok': False, 'error': 'not_logged_in'}), 401
    data = request.get_json(silent=True) or {}
    try:
        volume = max(0.0, min(1.0, float(data.get('volume', 1.0))))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'volume_invalido'}), 400
    conn = get_connection()
    try:
        updated = conn.execute('UPDATE sound_effects SET volume = ?, updated_at = ? WHERE id = ? AND is_active = 1', (volume, datetime.utcnow().isoformat(timespec='seconds'), effect_id)).rowcount
        if not updated:
            return jsonify({'ok': False, 'error': 'not_found'}), 404
        conn.commit()
        return jsonify({'ok': True, 'volume': volume})
    finally:
        conn.close()
