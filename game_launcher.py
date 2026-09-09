from __future__ import annotations

import os
import subprocess
from pathlib import Path

from game_validator import is_valid_game_record
from launcher_manager import iniciar_executavel


def iniciar_jogo_salvo(game_record: dict) -> dict:
    exe_path = (game_record.get('exe_path') or '').strip()
    appid = (game_record.get('appid') or '').strip()
    launcher = (game_record.get('launcher') or 'manual').strip().lower()

    if not is_valid_game_record(game_record):
        return {'ok': False, 'success': False, 'modo': launcher or 'manual', 'error': 'Registro inválido: game_folder/exe_path ausentes ou inexistentes.'}

    if launcher == 'steam' and appid:
        try:
            steam_url = f'steam://rungameid/{appid}'
            if os.name == 'nt':
                os.startfile(steam_url)
                return {'ok': True, 'success': True, 'modo': 'steam', 'pid': None}
        except Exception:
            pass

    if not exe_path or not os.path.exists(exe_path):
        return {'ok': False, 'success': False, 'modo': launcher or 'manual', 'error': 'Executável não encontrado ou origem inválida.'}

    cwd = os.path.dirname(exe_path) or os.getcwd()
    try:
        resultado = iniciar_executavel(exe_path, cwd=cwd)
        return {
            'ok': True,
            'success': True,
            'modo': launcher or 'manual',
            'pid': resultado.get('pid'),
            'elevated': resultado.get('elevated', False),
        }
    except Exception as exc:
        return {'ok': False, 'success': False, 'modo': launcher or 'manual', 'error': f'{type(exc).__name__}: {exc}'}
