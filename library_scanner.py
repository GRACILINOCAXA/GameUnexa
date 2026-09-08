from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from exe_detector import detect_executable

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


def _resolver_roots_da_biblioteca(root: str, launcher: str) -> list[str]:
    root = (root or '').strip()
    if not root:
        return []

    normalized = Path(root)
    roots: list[str] = []
    common_path = normalized / 'steamapps' / 'common'
    if common_path.is_dir():
        roots.append(str(common_path))

    if normalized.name.lower() == 'common' and (normalized.parent / 'steamapps').is_dir():
        roots.append(str(normalized))

    if launcher.lower() == 'steam':
        libraryfile = normalized / 'steamapps' / 'libraryfolders.vdf'
        if libraryfile.exists():
            try:
                texto = libraryfile.read_text(encoding='utf-8', errors='ignore')
                for match in re.finditer(r'"([A-Za-z]:\\[^"\n]+)"', texto):
                    candidate_path = Path(match.group(1).replace('\\', '\\'))
                    common_candidate = candidate_path / 'steamapps' / 'common'
                    if common_candidate.is_dir() and str(common_candidate) not in roots:
                        roots.append(str(common_candidate))
            except Exception:
                pass

    if not roots:
        roots = [root]
    return roots


def _deve_ignorar_dir(path: str) -> bool:
    if not path:
        return True
    partes = [parte.lower() for parte in Path(path).parts]
    return any(parte in IGNORAR_PASTAS for parte in partes)


def scan_library_root(root: str, launcher: str = 'steam') -> list[dict]:
    registros: list[dict] = []
    for base_dir in _resolver_roots_da_biblioteca(root, launcher):
        for entrada in sorted(Path(base_dir).iterdir(), key=lambda p: p.name.lower()):
            if not entrada.is_dir():
                continue
            if _deve_ignorar_dir(str(entrada)):
                continue
            exe_path = detect_executable(str(entrada), entrada.name)
            if not exe_path:
                continue
            registros.append({
                'nome': re.sub(r'\s+', ' ', (entrada.name or '').replace('_', ' ').strip()),
                'launcher': (launcher or 'manual').strip().lower(),
                'library_root': root,
                'game_folder': str(entrada),
                'exe_name': os.path.basename(exe_path),
                'exe_path': exe_path,
                'icon_path': '',
                'cover_path': '',
                'installed': True,
                'favorite': False,
                'last_scan': datetime.now().isoformat(timespec='seconds'),
                'hash': '',
            })
    return registros
