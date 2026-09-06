"""Gerenciador unificado de biblioteca Steam/Hydra.

Este módulo é a fonte de verdade para descoberta, validação e persistência da
biblioteca do Jogar. A interface não deve procurar executáveis em tempo real;
ela só consulta registros válidos já persistidos aqui.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List

from steam_api import obter_jogos, obter_perfil, obter_status, obter_jogo
from steam_local import listar_jogos_instalados
from game_matcher import names_match, normalize_game_name
from game_validator import is_valid_game_record, should_ignore_path

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
    'unitycrashhandler.exe',
    'eac.exe',
}


def _normalizar_texto_busca(texto: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (texto or '').lower())


def _tokens_do_texto(texto: str) -> list[str]:
    return re.findall(r'[a-z0-9]+', (texto or '').lower())


def _similaridade_textos(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, _normalizar_texto_busca(a), _normalizar_texto_busca(b)).ratio()


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


def _candidate_score(exe_path: str, folder_name: str) -> tuple[int, str]:
    nome_arquivo = Path(exe_path).stem.lower()
    folder = (folder_name or '').lower()
    score = 0
    size = os.path.getsize(exe_path) if os.path.exists(exe_path) else 0
    score += min(size // 1_000_000, 50)

    similaridade = _similaridade_textos(folder, nome_arquivo)
    if similaridade > 0.45:
        score += int(similaridade * 120)

    tokens_pasta = set(_tokens_do_texto(folder))
    tokens_arquivo = set(_tokens_do_texto(nome_arquivo))
    overlap = len(tokens_pasta & tokens_arquivo)
    if overlap:
        score += overlap * 35

    if 'shipping' in nome_arquivo:
        score += 40
    if 'win64' in nome_arquivo:
        score += 25
    if 'game' in nome_arquivo:
        score += 15
    if 'launcher' in nome_arquivo or 'updater' in nome_arquivo or 'crash' in nome_arquivo:
        score -= 200
    return score, nome_arquivo


def localizar_executavel_na_pasta(pasta_base: str, nome_jogo: str | None = None) -> str:
    if not pasta_base or not os.path.isdir(pasta_base):
        return ''

    candidatos: list[tuple[int, str, str]] = []
    for raiz, dirs, arquivos in os.walk(pasta_base):
        dirs[:] = [d for d in dirs if not _deve_ignorar_path(os.path.join(raiz, d))]
        for nome_arquivo in sorted(arquivos):
            if not nome_arquivo.lower().endswith('.exe'):
                continue
            if nome_arquivo.lower() in IGNORAR_NOMES:
                continue
            caminho = os.path.join(raiz, nome_arquivo)
            if not os.path.exists(caminho):
                continue
            if _deve_ignorar_path(caminho):
                continue
            score, _ = _candidate_score(caminho, nome_jogo or os.path.basename(pasta_base))
            if score > 0 or not candidatos:
                candidatos.append((score, nome_arquivo, caminho))

    if not candidatos:
        return ''

    candidatos.sort(key=lambda item: (item[0], os.path.getsize(item[2]), item[1]), reverse=True)
    return candidatos[0][2]


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


def scan_library_root(root: str, launcher: str = 'steam') -> list[dict]:
    registros: list[dict] = []
    for base_dir in _resolver_roots_da_biblioteca(root, launcher):
        for entrada in sorted(Path(base_dir).iterdir(), key=lambda p: p.name.lower()):
            if not entrada.is_dir():
                continue
            if should_ignore_path(str(entrada)):
                continue

            exe_path = localizar_executavel_na_pasta(str(entrada), entrada.name)
            if not exe_path:
                continue

            nome_jogo = re.sub(r'\s+', ' ', (entrada.name or '').replace('_', ' ').strip())
            registro = {
                'nome': nome_jogo,
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
            }
            if is_valid_game_record(registro):
                registros.append(registro)
    return registros


def persistir_registros_instalados(email: str, registros: list[dict], launcher: str) -> int:
    from database import get_connection

    conn = get_connection()
    try:
        for item in registros:
            nome_jogo = (item.get('nome') or '').strip()
            if not nome_jogo:
                continue
            launcher_norm = (launcher or 'manual').strip().lower()
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
                    email,
                    nome_jogo,
                    launcher_norm,
                    item.get('appid') or '',
                    item.get('library_root') or '',
                    item.get('game_folder') or '',
                    item.get('exe_name') or '',
                    item.get('exe_path') or '',
                    item.get('icon_path') or '',
                    item.get('cover_path') or '',
                    1 if item.get('installed') else 0,
                    1 if item.get('favorite') else 0,
                    item.get('last_scan') or '',
                    item.get('hash') or '',
                ),
            )
        conn.commit()
        return len(registros)
    finally:
        conn.close()


def unificar_biblioteca(steam_id64: str, api_key: str = "") -> List[Dict[str, object]]:
    if not steam_id64:
        return []

    jogos_api = obter_jogos(steam_id64, api_key)
    jogos_instalados = listar_jogos_instalados()

    mapa: Dict[int, Dict[str, object]] = {}
    for jogo in jogos_api:
        appid = int(jogo.get("appid") or 0)
        if not appid:
            continue
        mapa[appid] = {
            "source": "steam_api",
            "appid": appid,
            "name": jogo.get("name") or f"App {appid}",
            "playtime_forever": int(jogo.get("playtime_forever") or 0),
            "installed": False,
            "cover_url": "",
            "banner_url": "",
            "header_url": "",
            "launcher": "steam",
            "path": "",
            "library": "",
            "origin": "steam",
            "favorited": False,
            "last_played": None,
            "platform": "PC",
            "steam_id64": steam_id64,
        }

    for jogo_local in jogos_instalados:
        appid = int(jogo_local.get("appid") or 0)
        if not appid:
            continue
        entrada = mapa.get(appid)
        if entrada is None:
            mapa[appid] = {
                "source": "steam_local",
                "appid": appid,
                "name": jogo_local.get("name") or f"App {appid}",
                "playtime_forever": 0,
                "installed": True,
                "cover_url": "",
                "banner_url": "",
                "header_url": "",
                "launcher": "steam",
                "path": jogo_local.get("path") or "",
                "library": jogo_local.get("library") or "",
                "origin": "steam",
                "favorited": False,
                "last_played": None,
                "platform": "PC",
                "steam_id64": steam_id64,
            }
        else:
            entrada["installed"] = True
            entrada["path"] = jogo_local.get("path") or entrada.get("path") or ""
            entrada["library"] = jogo_local.get("library") or entrada.get("library") or ""

    for appid, entrada in mapa.items():
        dados_loja = obter_jogo(int(appid))
        if dados_loja:
            entrada["cover_url"] = dados_loja.get("header_image") or entrada.get("cover_url") or ""
            entrada["banner_url"] = dados_loja.get("background") or entrada.get("banner_url") or ""
            entrada["header_url"] = dados_loja.get("header_image") or entrada.get("header_url") or ""
            entrada["name"] = dados_loja.get("name") or entrada.get("name")

    perfil = obter_perfil(steam_id64, api_key) if api_key else {}
    status = obter_status(steam_id64, api_key) if api_key else {"online": False, "game": "", "appid": None}

    resultado = list(mapa.values())
    resultado.sort(key=lambda item: (int(item.get("playtime_forever") or 0), str(item.get("name") or "")), reverse=True)
    return resultado
