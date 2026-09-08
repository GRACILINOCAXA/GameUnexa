from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path


def normalize_game_name(texto: str) -> str:
    texto = (texto or '').strip()
    texto = texto.replace('_', ' ')
    texto = texto.replace(':', ' ')
    texto = re.sub(r'\s+', ' ', texto)
    return re.sub(r'[^a-z0-9]+', '', texto.lower())


def tokens_from_text(texto: str) -> list[str]:
    return re.findall(r'[a-z0-9]+', (texto or '').lower())


def normalized_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_norm = normalize_game_name(a)
    b_norm = normalize_game_name(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def names_match(expected: str, actual: str) -> bool:
    if not expected or not actual:
        return False
    if normalize_game_name(expected) == normalize_game_name(actual):
        return True
    if normalized_similarity(expected, actual) >= 0.55:
        return True
    expected_tokens = set(tokens_from_text(expected))
    actual_tokens = set(tokens_from_text(actual))
    overlap = len(expected_tokens & actual_tokens)
    if overlap and overlap >= max(1, min(len(expected_tokens), len(actual_tokens)) - 1):
        return True
    return False


def infer_game_label(folder_name: str, exe_name: str | None = None) -> str:
    candidates = [folder_name, exe_name or '']
    for value in candidates:
        if value and value.strip():
            return str(value).strip()
    return ''


def build_aliases(name: str) -> set[str]:
    aliases = set()
    text = (name or '').strip()
    if not text:
        return aliases
    aliases.add(text)
    aliases.add(text.replace(':', ' '))
    aliases.add(normalize_game_name(text))
    for token in tokens_from_text(text):
        aliases.add(token)
    return {item for item in aliases if item}
