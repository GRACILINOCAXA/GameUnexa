from __future__ import annotations

import os
import re
from difflib import SequenceMatcher
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

NOMES_GENERICO = {
    'game.exe',
    'play.exe',
    'client.exe',
    'shipping.exe',
    'win64.exe',
    'ue4game.exe',
    'launcher.exe',
}


def classify_executable(exe_path: str, folder_name: str = '', manifest: bool = False) -> dict:
    nome = os.path.basename(exe_path or '').lower()
    base = Path(nome).stem
    contexto = f'{base} {Path(folder_name or "").name}'.lower()
    if not exe_path or not os.path.isfile(exe_path) or nome in IGNORAR_NOMES:
        return {'classification': 'NON_GAME', 'confidence': 100, 'reason': 'GAME_AUXILIARY'}
    if any(token in contexto for token in (
        'obs studio', 'obs-browser', 'discord', 'chrome', 'spotify', 'wallpaper engine',
        'trainer', 'trainerby', 'cheat', 'mod manager', 'dedicated server', 'server tool',
    )):
        return {'classification': 'NON_GAME', 'confidence': 98, 'reason': 'KNOWN_NON_GAME'}
    if any(token in base for token in (
        'unitycrashhandler', 'crashreport', 'crashreportclient', 'uninstall', 'unins',
        'easyanticheat', 'eaclauncher', 'battleye', 'unrealcefsubprocess', 'helper',
        'updater', 'update', 'setup', 'install', 'dxsetup', 'vcredist', 'dotnet',
        'redistributable', 'runtime', 'service', 'report', 'steamworks',
    )):
        return {'classification': 'NON_GAME', 'confidence': 100, 'reason': 'GAME_AUXILIARY'}
    if nome in NOMES_GENERICO:
        if manifest:
            return {'classification': 'GAME', 'confidence': 92, 'reason': 'STEAM_MANIFEST'}
        return {'classification': 'UNKNOWN', 'confidence': 25, 'reason': 'GENERIC_EXECUTABLE'}
    folder_key = _normalizar_texto_busca(Path(folder_name or '').name)
    exe_key = _normalizar_texto_busca(base)
    if manifest:
        return {'classification': 'GAME', 'confidence': 98, 'reason': 'STEAM_MANIFEST'}
    if folder_key and (folder_key in exe_key or SequenceMatcher(None, folder_key, exe_key).ratio() >= 0.6):
        return {'classification': 'GAME', 'confidence': 80, 'reason': 'FOLDER_EXECUTABLE_MATCH'}
    return {'classification': 'UNKNOWN', 'confidence': 35, 'reason': 'INSUFFICIENT_IDENTITY'}


def _normalizar_texto_busca(texto: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (texto or '').lower())


def _deve_ignorar_path(path: str) -> bool:
    if not path:
        return True
    partes = [parte.lower() for parte in Path(path).parts]
    if not partes:
        return True
    for parte in partes:
        if parte in IGNORAR_PASTAS:
            return True
        if parte.startswith('launcher'):
            return True
    return False


def score_exe(exe_path: str, folder_name: str) -> tuple[int, str]:
    nome_arquivo = Path(exe_path).stem.lower()
    folder = (folder_name or '').lower()
    score = 0
    size = os.path.getsize(exe_path) if os.path.exists(exe_path) else 0
    score += min(size // 1_000_000, 50)

    if folder and folder in nome_arquivo:
        score += 100
    if nome_arquivo == folder:
        score += 150
    if 'shipping' in nome_arquivo:
        score += 40
    if 'win64' in nome_arquivo:
        score += 25
    if 'game' in nome_arquivo:
        score += 15
    if 'launcher' in nome_arquivo or 'updater' in nome_arquivo or 'crash' in nome_arquivo:
        score -= 200
    return score, nome_arquivo


def detect_executable(game_folder: str, game_name: str | None = None) -> str:
    if not game_folder or not os.path.isdir(game_folder):
        return ''

    candidatos: list[tuple[int, str, str]] = []
    nome_jogo = (game_name or os.path.basename(game_folder) or '').strip()
    nome_busca = _normalizar_texto_busca(nome_jogo)
    for raiz, dirs, arquivos in os.walk(game_folder):
        dirs[:] = [d for d in dirs if not _deve_ignorar_path(os.path.join(raiz, d))]
        for arquivo in sorted(arquivos):
            nome_baixo = arquivo.lower()
            if not nome_baixo.endswith('.exe'):
                continue
            if nome_baixo in IGNORAR_NOMES:
                continue
            caminho = os.path.join(raiz, arquivo)
            if not os.path.exists(caminho):
                continue
            if _deve_ignorar_path(caminho):
                continue

            score, _ = score_exe(caminho, nome_jogo)
            if not nome_busca:
                if score > 0 or not candidatos:
                    candidatos.append((score, arquivo, caminho))
                continue

            base_busca = _normalizar_texto_busca(os.path.splitext(arquivo)[0])
            if nome_busca in base_busca or SequenceMatcher(None, nome_busca, base_busca).ratio() > 0.45:
                score += 25
            if score > 0 or not candidatos:
                candidatos.append((score, arquivo, caminho))

    if not candidatos:
        return ''

    candidatos.sort(key=lambda item: (item[0], os.path.getsize(item[2]), item[1]), reverse=True)
    return candidatos[0][2]
