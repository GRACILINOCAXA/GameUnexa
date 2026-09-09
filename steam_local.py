"""Leitura oficial de bibliotecas Steam a partir de arquivos locais.

Este módulo detecta instalações da Steam e appmanifest_*.acf sem depender
de scraping ou da página pública do perfil.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)
STEAM_LOCAL_INDEX_CACHE = CACHE_DIR / "steam_local_index.json"


def _normalizar_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(path)) if path else ""


def _buscar_steam_executavel() -> str | None:
    candidatos = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Steam\steam.exe"),
        os.path.expandvars(r"%ProgramFiles%\Steam\steam.exe"),
        r"C:\Program Files (x86)\Steam\steam.exe",
        r"C:\Program Files\Steam\steam.exe",
        r"D:\Steam\steam.exe",
        r"E:\Steam\steam.exe",
    ]
    for candidato in candidatos:
        if os.path.exists(candidato):
            return candidato
    if os.name == 'nt':
        try:
            import winreg

            for hive, subkey in (
                (winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam'),
                (winreg.HKEY_LOCAL_MACHINE, r'Software\Valve\Steam'),
                (winreg.HKEY_LOCAL_MACHINE, r'Software\WOW6432Node\Valve\Steam'),
            ):
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        install_path, _ = winreg.QueryValueEx(key, 'InstallPath')
                    executavel = Path(str(install_path)) / 'steam.exe'
                    if executavel.exists():
                        return str(executavel)
                except (FileNotFoundError, OSError):
                    continue
        except ImportError:
            pass
    return None


def _ler_libraryfolders_vdf(steam_root: str) -> List[str]:
    if not steam_root:
        return []

    libraryfolders = Path(steam_root) / "steamapps" / "libraryfolders.vdf"
    if not libraryfolders.exists():
        return [steam_root]

    try:
        texto = libraryfolders.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return [steam_root]

    bibliotecas: List[str] = []
    for match in re.finditer(r'"([A-Za-z]:\\[^"\n]+)"', texto):
        bibliotecas.append(match.group(1).replace('\\\\', '\\'))
    if not bibliotecas:
        bibliotecas.append(steam_root)
    return bibliotecas


def localizar_bibliotecas_steam() -> List[Dict[str, str]]:
    steam_exe = _buscar_steam_executavel()
    bibliotecas: List[Dict[str, str]] = []
    if steam_exe:
        steam_root = str(Path(steam_exe).parent)
        for biblioteca in _ler_libraryfolders_vdf(steam_root):
            bibliotecas.append({"root": biblioteca, "type": "steam"})
    else:
        bibliotecas.append({"root": r"C:\Program Files (x86)\Steam", "type": "steam"})

    vistas = set()
    resultado: List[Dict[str, str]] = []
    for biblioteca in bibliotecas:
        chave = _normalizar_path(biblioteca["root"])
        if chave in vistas:
            continue
        vistas.add(chave)
        resultado.append(biblioteca)
    return resultado


def _ler_manifest_steam(manifest_path: Path) -> Dict[str, str]:
    try:
        texto = manifest_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}

    appid_match = re.search(r'"appid"\s+"(\d+)"', texto)
    name_match = re.search(r'"name"\s+"([^\n]+)"', texto)
    installdir_match = re.search(r'"installdir"\s+"([^\n]+)"', texto)
    if not appid_match:
        return {}

    appid = appid_match.group(1)
    nome = name_match.group(1).strip() if name_match else f"App {appid}"
    install_dir = installdir_match.group(1).strip() if installdir_match else ""
    return {
        "appid": appid,
        "name": nome,
        "install_dir": install_dir,
        "manifest": str(manifest_path),
        "instalado": True,
    }


def construir_indice_steam_local(steam_root: str | None = None) -> List[Dict[str, str]]:
    bibliotecas = []
    if steam_root:
        raiz = Path(steam_root).expanduser()
        if raiz.name.casefold() == 'common' and raiz.parent.name.casefold() == 'steamapps':
            raiz = raiz.parent.parent
        elif raiz.name.casefold() == 'steamapps':
            raiz = raiz.parent
        bibliotecas.append(str(raiz))
    else:
        bibliotecas = [biblioteca["root"] for biblioteca in localizar_bibliotecas_steam()]

    jogos: List[Dict[str, str]] = []
    vistos: set[str] = set()
    for root in bibliotecas:
        steamapps = Path(root) / "steamapps"
        if not steamapps.exists():
            continue

        for manifest in sorted(steamapps.glob("appmanifest_*.acf")):
            dados = _ler_manifest_steam(manifest)
            if not dados:
                continue

            install_dir = dados.get("install_dir") or ""
            install_path = str(steamapps / "common" / install_dir) if install_dir else ""
            entrada = {
                "appid": dados.get("appid") or "",
                "name": dados.get("name") or "",
                "install_dir": install_dir,
                "path": install_path,
                "manifest": dados.get("manifest") or str(manifest),
                "library": str(Path(root)),
                "instalado": True,
            }
            chave = f"{entrada['appid']}::{entrada['name']}::{entrada['path']}"
            if chave in vistos:
                continue
            vistos.add(chave)
            jogos.append(entrada)

    return jogos


def carregar_indice_steam_local(steam_root: str | None = None, force: bool = False) -> List[Dict[str, str]]:
    cache_root = _normalizar_path(steam_root or '')
    if not force and STEAM_LOCAL_INDEX_CACHE.exists():
        try:
            payload = json.loads(STEAM_LOCAL_INDEX_CACHE.read_text(encoding="utf-8"))
            payload_root = _normalizar_path(payload.get("root", "")) if isinstance(payload, dict) else ""
            if isinstance(payload, dict) and payload.get("timestamp") and payload.get("data") and payload_root == cache_root:
                if time.time() - float(payload["timestamp"]) < 300:
                    return payload["data"]
        except Exception:
            pass

    indice = construir_indice_steam_local(steam_root)
    try:
        STEAM_LOCAL_INDEX_CACHE.write_text(json.dumps({"timestamp": time.time(), "root": steam_root or "", "data": indice}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return indice


def listar_jogos_instalados(steam_root: str | None = None, force: bool = False) -> List[Dict[str, str]]:
    return carregar_indice_steam_local(steam_root=steam_root, force=force)
