from __future__ import annotations

import json
import os
from pathlib import Path

CACHE_PATH = Path(__file__).with_name('launcher_cache.json')


def carregar_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        with CACHE_PATH.open('r', encoding='utf-8') as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
    except Exception:
        return {}
    return {}


def salvar_cache(cache: dict) -> None:
    with CACHE_PATH.open('w', encoding='utf-8') as handle:
        json.dump(cache, handle, indent=2, ensure_ascii=False)


def obter_cache_jogo(nome_jogo: str) -> dict:
    cache = carregar_cache()
    return dict(cache.get((nome_jogo or '').strip(), {}))


def obter_exe_cache(nome_jogo: str) -> str:
    cache = obter_cache_jogo(nome_jogo)
    return str(cache.get('exe_path', '') or cache.get('exe', '') or '')


def salvar_exe_cache(nome_jogo: str, exe_path: str, game_folder: str = '', hash_value: str = '', validated: bool = True) -> None:
    cache = carregar_cache()
    key = (nome_jogo or '').strip()
    cache[key] = {
        'exe_path': exe_path or '',
        'game_folder': game_folder or '',
        'hash': hash_value or '',
        'validated': bool(validated),
    }
    salvar_cache(cache)


def limpar_cache_jogo(nome_jogo: str) -> None:
    cache = carregar_cache()
    key = (nome_jogo or '').strip()
    cache.pop(key, None)
    salvar_cache(cache)
