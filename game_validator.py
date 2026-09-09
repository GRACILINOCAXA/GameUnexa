from __future__ import annotations

import os
from pathlib import Path

IGNORAR_NOMES = {
    'unins000.exe',
    'setup.exe',
    'install.exe',
    'launcher_updater.exe',
    'crashreport.exe',
    'vc_redist.exe',
    'dxsetup.exe',
    'easyanticheat.exe',
    'redistributable.exe',
    'benchmark.exe',
    'updater.exe',
    'installer.exe',
    'uninstall.exe',
    'steam.exe',
    'epicwebhelper.exe',
    'unitycrashhandler.exe',
    'eac.exe',
}

IGNORAR_PASTAS = {
    '_commonredist',
    'engine',
    'redistributables',
    'support',
    'installer',
    'directx',
    'vc',
    'tools',
    'redist',
    'bin',
    'crashreport',
}


def should_ignore_path(path: str) -> bool:
    if not path:
        return True
    parts = [part.lower() for part in Path(path).parts]
    return any(part in IGNORAR_PASTAS for part in parts) or any(part.startswith('launcher') for part in parts)


def should_ignore_exe(name: str) -> bool:
    base = Path(name or '').stem.lower()
    return base in IGNORAR_NOMES or (name or '').lower() in IGNORAR_NOMES


def is_valid_game_record(record: dict) -> bool:
    if not record:
        return False
    game_folder = (record.get('game_folder') or '').strip()
    exe_path = (record.get('exe_path') or '').strip()
    return bool(game_folder and exe_path and os.path.isdir(game_folder) and os.path.isfile(exe_path))
