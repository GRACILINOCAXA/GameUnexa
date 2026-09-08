import re
from typing import List, Dict

DEFAULT_BLOCKED_TERMS = [
    "racismo",
    "xingamento",
    "preconceito",
    "sexo",
    "violência",
    "autolesão",
    "droga",
    "pornografia",
    "terrorismo",
    "assédio",
]


def _normalize_text(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower())


def moderate_text(text: str, blocked_terms: List[str] = None) -> Dict[str, object]:
    """Verifica se o texto contém termos bloqueados."""
    if blocked_terms is None:
        blocked_terms = DEFAULT_BLOCKED_TERMS

    normalized = _normalize_text(text)
    matches = []

    for term in blocked_terms:
        pattern = rf"\b{re.escape(term.lower())}\b"
        if re.search(pattern, normalized):
            matches.append(term)

    return {
        "allowed": len(matches) == 0,
        "blocked_terms": sorted(set(matches)),
        "original_text": text,
    }


def is_allowed(text: str, blocked_terms: List[str] = None) -> bool:
    return moderate_text(text, blocked_terms)["allowed"]


if __name__ == "__main__":
    sample = input("Texto para moderação: ")
    result = moderate_text(sample)
    if result["allowed"]:
        print("Conteúdo permitido.")
    else:
        print("Conteúdo bloqueado. Termos encontrados:", ", ".join(result["blocked_terms"]))
