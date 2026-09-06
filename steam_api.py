"""Integração oficial com a Steam Web API.

Este módulo centraliza todas as chamadas oficiais da Steam e evita depender
completamente da página pública do perfil para montar a biblioteca do usuário.
"""

from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote
from urllib.request import Request, urlopen
from paths import CACHE_DIR


def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.json"


def _read_cache(name: str, max_age_seconds: int = 900) -> Any | None:
    _ensure_cache_dir()
    path = _cache_path(name)
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict) and "timestamp" in payload and "data" in payload:
            if time.time() - payload["timestamp"] <= max_age_seconds:
                return payload["data"]
    except Exception:
        return None

    return None


def _write_cache(name: str, data: Any) -> None:
    _ensure_cache_dir()
    path = _cache_path(name)
    payload = {"timestamp": time.time(), "data": data}
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _steam_fetch_json(
    url: str,
    timeout: int = 15,
    cache_key: str | None = None,
    cache_ttl: int = 900,
    force_refresh: bool = False,
) -> Any:
    if cache_key and not force_refresh:
        cached = _read_cache(cache_key, cache_ttl)
        if cached is not None:
            return cached

    request = Request(
        url,
        headers={
            "User-Agent": "GameUnexa/2.0",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://store.steampowered.com/",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as resposta:
            corpo = resposta.read().decode("utf-8", errors="replace")
            dados = json.loads(corpo)
            if cache_key:
                _write_cache(cache_key, dados)
            return dados
    except Exception:
        if cache_key:
            cached = _read_cache(cache_key, 0)
            if cached is not None:
                return cached
        return {}


def _steam_fetch_text(url: str, cache_key: str, cache_ttl: int, force_refresh: bool = False) -> str:
    if not force_refresh:
        cached = _read_cache(cache_key, cache_ttl)
        if isinstance(cached, str):
            return cached

    request = Request(
        url,
        headers={
            "User-Agent": "GameUnexa/2.0",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=15) as resposta:
            texto = resposta.read().decode("utf-8", errors="replace")
            _write_cache(cache_key, texto)
            return texto
    except Exception:
        return ""


def _obter_playtime_publico(steam_id64: str, appid: int, force_refresh: bool = False) -> int | None:
    xml = _steam_fetch_text(
        f"https://steamcommunity.com/profiles/{quote(steam_id64)}/games?xml=1",
        cache_key=f"public_games_{steam_id64}",
        cache_ttl=900,
        force_refresh=force_refresh,
    )
    if not xml:
        return None
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None
    for game in root.findall(".//game"):
        appid_node = game.find("appID")
        if appid_node is None or appid_node.text != str(appid):
            continue
        minutes_node = game.find("hoursOnRecord")
        if minutes_node is None or not minutes_node.text:
            return 0
        try:
            return max(0, int(round(float(minutes_node.text) * 60)))
        except ValueError:
            return None
    return None


def _obter_conquistas_publicas(steam_id64: str, appid: int, force_refresh: bool = False) -> Dict[str, Any] | None:
    html = _steam_fetch_text(
        f"https://steamcommunity.com/profiles/{quote(steam_id64)}/stats/{appid}/?tab=achievements",
        cache_key=f"public_achievements_{steam_id64}_{appid}",
        cache_ttl=1800,
        force_refresh=force_refresh,
    )
    if not html:
        return None
    if "login/home" in html.lower() or "sign in" in html.lower():
        return {"private": True}
    patterns = (
        r"(\d+)\s+of\s+(\d+)\s+\((\d+(?:\.\d+)?)%\)\s+achievements earned",
        r"(\d+)\s+de\s+(\d+)\s+\((\d+(?:\.\d+)?)%\).*?conquistas",
    )
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            unlocked, total, percentage = int(match.group(1)), int(match.group(2)), float(match.group(3))
            return {
                "unlocked": min(unlocked, total),
                "total": total,
                "percentage": percentage,
            }
    if "private" in html.lower() or "this profile is private" in html.lower():
        return {"private": True}
    return None


def _aplicar_snapshot_stats(resultado: Dict[str, Any], steam_id64: str, appid: int) -> Dict[str, Any]:
    cache_key = f"stats_snapshot_steam_{steam_id64}_{appid}"
    dados_validos = {
        "playtime_minutes": resultado.get("playtime_minutes"),
        "achievements": resultado.get("achievements"),
    }
    if dados_validos["playtime_minutes"] is not None or dados_validos["achievements"] is not None:
        _write_cache(cache_key, dados_validos)
        return resultado

    snapshot = _read_cache(cache_key, 604800)
    if isinstance(snapshot, dict):
        resultado.update(snapshot)
        resultado["status"] = "stale"
        resultado["stale"] = True
    return resultado


def obter_perfil(steam_id64: str, api_key: str = "") -> Dict[str, Any]:
    if not steam_id64:
        return {}

    if not api_key:
        return {"steamid": steam_id64, "personaname": "Steam", "avatar": "", "profileurl": f"https://steamcommunity.com/profiles/{steam_id64}"}

    url = (
        "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?"
        f"key={quote(api_key)}&steamids={quote(steam_id64)}&format=json"
    )
    dados = _steam_fetch_json(url, cache_key=f"profile_{steam_id64}", cache_ttl=1800)
    players = (dados.get("response", {}) or {}).get("players", []) or []
    if not players:
        return {"steamid": steam_id64, "personaname": "Steam", "avatar": "", "profileurl": f"https://steamcommunity.com/profiles/{steam_id64}"}

    player = players[0]
    return {
        "steamid": player.get("steamid", steam_id64),
        "personaname": player.get("personaname") or "Steam",
        "avatar": player.get("avatarfull") or player.get("avatar") or "",
        "profileurl": player.get("profileurl") or f"https://steamcommunity.com/profiles/{steam_id64}",
        "personastate": player.get("personastate"),
        "gameextrainfo": player.get("gameextrainfo"),
        "gameid": player.get("gameid"),
    }


def obter_jogos(steam_id64: str, api_key: str = "", force_refresh: bool = False) -> List[Dict[str, Any]]:
    if not steam_id64:
        return []

    if not api_key:
        xml = _steam_fetch_text(
            f"https://steamcommunity.com/profiles/{quote(steam_id64)}/games?xml=1",
            cache_key=f"public_games_{steam_id64}",
            cache_ttl=900,
            force_refresh=force_refresh,
        )
        if not xml:
            return []
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return []

        resultado_publico: List[Dict[str, Any]] = []
        for jogo in root.findall(".//game"):
            appid = jogo.findtext("appID")
            if not str(appid or "").isdigit():
                continue
            horas = jogo.findtext("hoursOnRecord") or "0"
            try:
                minutos = int(round(float(horas) * 60))
            except ValueError:
                minutos = 0
            resultado_publico.append({
                "appid": int(appid),
                "name": jogo.findtext("name") or f"App {appid}",
                "playtime_forever": max(0, minutos),
                "playtime_2weeks": 0,
                "img_icon_url": jogo.findtext("logo") or "",
                "img_logo_url": jogo.findtext("logo") or "",
            })
        return resultado_publico

    url = (
        "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?"
        f"key={quote(api_key)}&steamid={quote(steam_id64)}"
        "&include_appinfo=1&include_played_free_games=1&format=json"
    )
    dados = _steam_fetch_json(url, cache_key=f"owned_games_{steam_id64}", cache_ttl=1800, force_refresh=force_refresh)
    jogos = (dados.get("response", {}) or {}).get("games", []) or []
    resultado: List[Dict[str, Any]] = []
    for jogo in jogos:
        appid = jogo.get("appid")
        if not appid:
            continue
        resultado.append(
            {
                "appid": int(appid),
                "name": jogo.get("name") or f"App {appid}",
                "playtime_forever": int(jogo.get("playtime_forever") or 0),
                "playtime_2weeks": int(jogo.get("playtime_2weeks") or 0),
                "img_icon_url": jogo.get("img_icon_url") or "",
                "img_logo_url": jogo.get("img_logo_url") or "",
            }
        )
    return resultado


def obter_status(steam_id64: str, api_key: str = "") -> Dict[str, Any]:
    perfil = obter_perfil(steam_id64, api_key)
    if not perfil:
        return {"online": False, "game": "", "appid": None}

    personastate = int(perfil.get("personastate") or 0)
    return {
        "online": personastate != 0,
        "game": perfil.get("gameextrainfo") or "",
        "appid": int(perfil.get("gameid") or 0) if perfil.get("gameid") else None,
        "personaname": perfil.get("personaname") or "Steam",
        "avatar": perfil.get("avatar") or "",
    }


def obter_horas(steam_id64: str, api_key: str = "") -> int:
    jogos = obter_jogos(steam_id64, api_key)
    return int(sum(int(j.get("playtime_forever") or 0) for j in jogos) / 60)


def obter_avatar(steam_id64: str, api_key: str = "") -> str:
    perfil = obter_perfil(steam_id64, api_key)
    return perfil.get("avatar") or ""


def obter_conquistas(steam_id64: str, api_key: str, appid: int) -> Dict[str, Any]:
    if not steam_id64 or not api_key or not appid:
        return {}

    url = (
        "https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/?"
        f"key={quote(api_key)}&steamid={quote(steam_id64)}&appid={appid}&l=pt-BR"
    )
    dados = _steam_fetch_json(url, cache_key=f"achievements_{steam_id64}_{appid}", cache_ttl=1800)
    return dados.get("playerstats", {}) or {}


def obter_estatisticas(steam_id64: str, api_key: str, appid: int) -> Dict[str, Any]:
    if not steam_id64 or not api_key or not appid:
        return {}

    url = (
        "https://api.steampowered.com/ISteamUserStats/GetUserStatsForGame/v2/?"
        f"key={quote(api_key)}&steamid={quote(steam_id64)}&appid={appid}&l=pt-BR"
    )
    dados = _steam_fetch_json(url, cache_key=f"stats_{steam_id64}_{appid}", cache_ttl=1800)
    return dados.get("playerstats", {}) or {}


def formatar_playtime(minutos: int) -> str:
    minutos = max(0, int(minutos))
    horas, minutos_restantes = divmod(minutos, 60)
    if horas:
        return f"{horas}h {minutos_restantes}min" if minutos_restantes else f"{horas}h"
    return f"{minutos}min" if minutos else "0h"


def obter_estatisticas_jogo(
    steam_id64: str,
    api_key: str,
    appid: int,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Obtém estatísticas reais do usuário para um AppID Steam específico."""
    resultado: Dict[str, Any] = {
        "source": "steam",
        "playtime_minutes": None,
        "achievements": None,
        "status": "unavailable",
    }
    if not steam_id64 or not appid:
        resultado["status"] = "not_configured"
        return resultado

    if not api_key:
        resultado["playtime_minutes"] = _obter_playtime_publico(steam_id64, int(appid), force_refresh)
        conquistas_publicas = _obter_conquistas_publicas(steam_id64, int(appid), force_refresh)
        if conquistas_publicas and conquistas_publicas.get("private"):
            resultado["status"] = "private"
            return resultado
        resultado["achievements"] = conquistas_publicas
        resultado["status"] = "public_synced" if resultado["playtime_minutes"] is not None or conquistas_publicas else "unavailable"
        return _aplicar_snapshot_stats(resultado, steam_id64, int(appid))

    jogos_url = (
        "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?"
        f"key={quote(api_key)}&steamid={quote(steam_id64)}&include_appinfo=1"
        "&include_played_free_games=1&format=json"
    )
    jogos = _steam_fetch_json(
        jogos_url,
        cache_key=f"owned_games_{steam_id64}",
        cache_ttl=1800,
        force_refresh=force_refresh,
    )
    jogos_lista = (jogos.get("response", {}) or {}).get("games", []) or []
    if not isinstance(jogos_lista, list):
        jogos_lista = []
    jogo = next(
        (item for item in jogos_lista if int(item.get("appid") or 0) == int(appid)),
        None,
    )
    if jogo is not None and "playtime_forever" in jogo:
        resultado["playtime_minutes"] = max(0, int(jogo.get("playtime_forever") or 0))

    player_url = (
        "https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/?"
        f"key={quote(api_key)}&steamid={quote(steam_id64)}&appid={appid}&l=pt-BR"
    )
    schema_url = (
        "https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/?"
        f"key={quote(api_key)}&appid={appid}&l=pt-BR"
    )
    player = _steam_fetch_json(
        player_url,
        cache_key=f"achievements_{steam_id64}_{appid}",
        cache_ttl=1800,
        force_refresh=force_refresh,
    )
    schema = _steam_fetch_json(
        schema_url,
        cache_key=f"schema_{appid}",
        cache_ttl=86400,
        force_refresh=force_refresh,
    )
    playerstats = player.get("playerstats", {}) or {}
    error_text = str(playerstats.get("error") or "").lower()
    if "private" in error_text:
        resultado["status"] = "private"
        return resultado
    schema_achievements = (
        ((schema.get("game", {}) or {}).get("availableGameStats", {}) or {}).get("achievements", [])
        or []
    )
    player_achievements = playerstats.get("achievements")
    if isinstance(player_achievements, list) and schema_achievements:
        unlocked = sum(
            1
            for item in player_achievements
            if int(item.get("achieved") or 0) == 1
        )
        total = len(schema_achievements)
        resultado["achievements"] = {
            "unlocked": min(unlocked, total),
            "total": total,
            "percentage": round((min(unlocked, total) / total) * 100, 1) if total else 0,
        }
    resultado["status"] = "synced" if jogo is not None or resultado["achievements"] is not None else "unavailable"
    return _aplicar_snapshot_stats(resultado, steam_id64, int(appid))


def obter_amigos(steam_id64: str, api_key: str = "") -> List[Dict[str, Any]]:
    if not steam_id64 or not api_key:
        return []

    url = (
        "https://api.steampowered.com/ISteamUser/GetFriendList/v1/?"
        f"key={quote(api_key)}&steamid={quote(steam_id64)}&relationship=friend"
    )
    dados = _steam_fetch_json(url, cache_key=f"friends_{steam_id64}", cache_ttl=1800)
    amigos = (dados.get("friendslist", {}) or {}).get("friends", []) or []
    return amigos


def obter_jogo(appid: int) -> Dict[str, Any]:
    if not appid:
        return {}

    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=br&l=pt"
    dados = _steam_fetch_json(url, cache_key=f"store_{appid}", cache_ttl=86400)
    item = (dados or {}).get(str(appid), {}) or {}
    if not item.get("success"):
        return {}
    dados_jogo = item.get("data", {}) or {}
    return {
        "appid": int(appid),
        "name": dados_jogo.get("name") or f"App {appid}",
        "header_image": dados_jogo.get("header_image") or "",
        "capsule_image": dados_jogo.get("capsule_image") or "",
        "background": dados_jogo.get("background") or "",
        "short_description": dados_jogo.get("short_description") or "",
        "genres": dados_jogo.get("genres") or [],
    }
