"""Integração local e legítima com o Epic Games Launcher.

O módulo só lê os manifests JSON gravados pelo launcher oficial e abre os
protocolos oficiais da Epic. Não acessa credenciais nem baixa conteúdo.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from game_validator import is_valid_game_record
from library_manager import localizar_executavel_na_pasta

EPIC_LAUNCHER_CANDIDATES = (
    Path(os.environ.get('PROGRAMFILES', r'C:\\Program Files')) / 'Epic Games' / 'Launcher' / 'Portal' / 'Binaries' / 'Win64' / 'EpicGamesLauncher.exe',
    Path(os.environ.get('PROGRAMFILES(X86)', r'C:\\Program Files (x86)')) / 'Epic Games' / 'Launcher' / 'Portal' / 'Binaries' / 'Win64' / 'EpicGamesLauncher.exe',
    Path(os.environ.get('LOCALAPPDATA', '')) / 'EpicGamesLauncher' / 'Saved' / 'Config' / 'Windows' / 'GameUserSettings.ini',
)


def detectar_epic_launcher(configurado: str | None = None) -> str:
    """Retorna o executável do launcher, priorizando o caminho salvo."""
    candidatos = [Path(configurado)] if configurado else []
    candidatos.extend(EPIC_LAUNCHER_CANDIDATES[:2])
    for candidato in candidatos:
        if candidato.is_file() and candidato.suffix.lower() == '.exe':
            return str(candidato)
    return ''


def _manifest_dirs(raiz: str | None = None) -> list[Path]:
    candidatos = []
    if raiz:
        candidatos.append(Path(raiz))
    program_data = os.environ.get('PROGRAMDATA', r'C:\\ProgramData')
    candidatos.append(Path(program_data) / 'Epic' / 'EpicGamesLauncher' / 'Data' / 'Manifests')
    return list(dict.fromkeys(candidatos))


def _ler_manifest(caminho: Path) -> dict | None:
    try:
        dados = json.loads(caminho.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(dados, dict):
        return None
    app_name = str(dados.get('AppName') or '').strip()
    install_location = str(dados.get('InstallLocation') or '').strip()
    if not app_name or not install_location or dados.get('bIsIncomplete', False):
        return None
    pasta = Path(install_location)
    if not pasta.is_dir():
        return None
    executable = str(dados.get('LaunchExecutable') or '').strip().replace('/', os.sep)
    exe_path = str(pasta / executable) if executable else ''
    if not exe_path or not Path(exe_path).is_file():
        exe_path = localizar_executavel_na_pasta(str(pasta), str(dados.get('DisplayName') or app_name))
    registro = {
        'nome': str(dados.get('DisplayName') or app_name).strip(),
        'launcher': 'epic',
        'appid': app_name,
        'library_root': str(pasta.parent),
        'game_folder': str(pasta),
        'exe_name': Path(exe_path).name if exe_path else '',
        'exe_path': exe_path,
        'icon_path': '',
        'cover_path': '',
        'installed': True,
        'favorite': False,
        'last_scan': None,
        'hash': '',
    }
    return registro if is_valid_game_record(registro) else None


def listar_jogos_epic(raiz: str | None = None) -> list[dict]:
    """Lista somente jogos confirmados por manifests Epic existentes."""
    encontrados: dict[str, dict] = {}
    for diretorio in _manifest_dirs(raiz):
        if not diretorio.is_dir():
            continue
        for caminho in diretorio.glob('*.item'):
            registro = _ler_manifest(caminho)
            if registro:
                encontrados[registro['appid']] = registro
    return sorted(encontrados.values(), key=lambda item: item['nome'].casefold())


def abrir_epic_launcher(launcher_path: str | None = None, app_name: str | None = None) -> dict:
    """Abre o launcher oficial, opcionalmente apontando para um AppName."""
    launcher = detectar_epic_launcher(launcher_path)
    argumento = f'com.epicgames.launcher://apps/{app_name}?action=launch&silent=true' if app_name else ''
    try:
        if launcher:
            subprocess.Popen([launcher], cwd=str(Path(launcher).parent), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif os.name == 'nt' and argumento:
            os.startfile(argumento)
        else:
            return {'ok': False, 'error': 'Epic Games Launcher não encontrado.'}
        if argumento and launcher and os.name == 'nt':
            os.startfile(argumento)
        return {'ok': True}
    except (OSError, ValueError) as exc:
        return {'ok': False, 'error': f'Não foi possível abrir o Epic Games Launcher: {exc}'}