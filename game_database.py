from __future__ import annotations

from database import get_connection


def listar_games_instalados(email_usuario: str, launcher: str | None = None) -> list[dict]:
    conn = get_connection()
    try:
        if launcher:
            rows = conn.execute(
                'SELECT * FROM installed_games WHERE email_usuario = ? AND launcher = ? ORDER BY nome COLLATE NOCASE',
                (email_usuario, launcher.strip().lower()),
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM installed_games WHERE email_usuario = ? ORDER BY nome COLLATE NOCASE',
                (email_usuario,),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def persistir_game_instalado(email_usuario: str, registro: dict) -> None:
    conn = get_connection()
    try:
        conn.execute(
            '''
            INSERT INTO installed_games (
                email_usuario, nome, launcher, appid, library_root, game_folder, exe_name, exe_path,
                icon_path, cover_path, installed, favorite, last_scan, hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email_usuario, launcher, nome) DO UPDATE SET
                appid=excluded.appid,
                library_root=excluded.library_root,
                game_folder=excluded.game_folder,
                exe_name=excluded.exe_name,
                exe_path=excluded.exe_path,
                icon_path=excluded.icon_path,
                cover_path=excluded.cover_path,
                installed=excluded.installed,
                favorite=excluded.favorite,
                last_scan=excluded.last_scan,
                hash=excluded.hash
            ''',
            (
                email_usuario,
                (registro.get('nome') or '').strip(),
                (registro.get('launcher') or 'manual').strip().lower(),
                registro.get('appid') or '',
                registro.get('library_root') or '',
                registro.get('game_folder') or '',
                registro.get('exe_name') or '',
                registro.get('exe_path') or '',
                registro.get('icon_path') or '',
                registro.get('cover_path') or '',
                1 if registro.get('installed') else 0,
                1 if registro.get('favorite') else 0,
                registro.get('last_scan') or '',
                registro.get('hash') or '',
            ),
        )
        conn.commit()
    finally:
        conn.close()


def apagar_game_instalado(email_usuario: str, launcher: str, nome: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            'DELETE FROM installed_games WHERE email_usuario = ? AND launcher = ? AND nome = ?',
            (email_usuario, launcher.strip().lower(), nome.strip()),
        )
        conn.commit()
    finally:
        conn.close()
