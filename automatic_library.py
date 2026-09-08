"""Descoberta local de jogos para a biblioteca unificada do usuário."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

from library_manager import localizar_executavel_na_pasta
from exe_detector import classify_executable
from steam_local import construir_indice_steam_local


def normalize_game_name(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (name or '').casefold())


def _normal_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(path or ''))


def _record(name: str, folder: str, executable: str, origin: str, appid: str = '', library: str = '', manifest: bool = False) -> dict:
    classification = classify_executable(executable, name, manifest=manifest)
    return {
        'nome': re.sub(r'\s+', ' ', (name or Path(folder).name).replace('_', ' ').strip()),
        'launcher': origin,
        'appid': str(appid or ''),
        'library_root': library or folder,
        'game_folder': folder,
        'exe_name': os.path.basename(executable),
        'exe_path': executable,
        'installed': True,
        'platform': origin,
        'platform_id': str(appid or ''),
        'canonical_game_id': f'{origin}:{appid}' if appid else f'{origin}:{_normal_path(folder)}',
        'classification': classification['classification'],
        'confidence': classification['confidence'],
        'identification_reason': classification['reason'],
    }


def scan_steam(steam_root: str = '') -> list[dict]:
    records = []
    configured_root = Path((steam_root or '').strip()).expanduser()
    if configured_root.name.casefold() == 'common' and configured_root.parent.name.casefold() == 'steamapps':
        configured_root = configured_root.parent.parent
    index = construir_indice_steam_local(str(configured_root)) if configured_root.is_dir() else construir_indice_steam_local()
    for game in index:
        folder = game.get('path') or ''
        if not os.path.isdir(folder):
            continue
        executable = localizar_executavel_na_pasta(folder, game.get('name') or Path(folder).name)
        if executable:
            record = _record(game.get('name', ''), folder, executable, 'steam', game.get('appid', ''), game.get('library', ''), manifest=True)
            if record['classification'] == 'GAME':
                records.append(record)
    return records


def scan_local_folders(folders: Iterable[str], origin: str = 'manual') -> list[dict]:
    records = []
    for configured in folders:
        root = Path(str(configured).strip()).expanduser()
        if not root.is_dir():
            continue
        try:
            child_folders = [item for item in sorted(root.iterdir(), key=lambda item: item.name.casefold()) if item.is_dir()]
        except OSError:
            continue
        candidates = child_folders or [root]
        for folder in candidates:
            executable = localizar_executavel_na_pasta(str(folder), folder.name)
            if executable:
                record = _record(folder.name, str(folder), executable, origin, library=str(root))
                if record['classification'] == 'GAME':
                    records.append(record)
    return records


def deduplicate_records(records: Iterable[dict]) -> list[dict]:
    result: list[dict] = []
    indexes: dict[tuple[str, str], int] = {}
    for record in records:
        platform = str(record.get('platform') or record.get('launcher') or 'manual').strip().lower()
        appid = str(record.get('appid') or '').strip()
        path = _normal_path(record.get('game_folder') or '')
        executable = _normal_path(record.get('exe_path') or '')
        keys = [('platform_id', f'{platform}:{appid}')] if appid else []
        keys.append(('path', f'{platform}:{path}'))
        if executable:
            keys.append(('exe', executable))
        existing_index = next((indexes.get(key) for key in keys if key[1] and key in indexes), None)
        if existing_index is None:
            existing_index = len(result)
            result.append(record)
        else:
            current = result[existing_index]
            if current.get('launcher') != 'steam' and record.get('launcher') == 'steam':
                result[existing_index] = {**current, **record}
            else:
                for field in ('appid', 'exe_path', 'exe_name', 'library_root'):
                    if record.get(field) and not current.get(field):
                        current[field] = record[field]
        merged = result[existing_index]
        merged_platform = str(merged.get('platform') or merged.get('launcher') or 'manual').strip().lower()
        merged_appid = str(merged.get('appid') or '').strip()
        for key in (
            ('platform_id', f'{merged_platform}:{merged_appid}' if merged_appid else ''),
            ('path', f'{merged_platform}:{_normal_path(merged.get("game_folder") or "")}'),
            ('exe', _normal_path(merged.get('exe_path') or '')),
        ):
            if key[1]:
                indexes[key] = existing_index
    return result


def scan_automatic_library(folders: Iterable[str], include_steam: bool = True, steam_root: str = '') -> list[dict]:
    records = scan_steam(steam_root) if include_steam else []
    records.extend(scan_local_folders(folders))
    return deduplicate_records(records)