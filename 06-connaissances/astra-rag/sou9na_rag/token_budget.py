"""Compte localement les tokens E5 sans téléchargement au moment des recherches."""

import hashlib
from functools import lru_cache
from pathlib import Path

from tokenizers import Tokenizer

# Marge de 32 tokens face au plafond 512 du fournisseur NVIDIA.
MAX_TOKENS = 480
TOKENIZER_SHA256 = "5fd1c882abbd30517dced455a2c9768945ec726b96727927e4959348d9de550b"


@lru_cache(maxsize=1)
def tokenizer() -> Tokenizer:
    """Charge le tokenizer du modèle E5 parent, dont l'intégrité est vérifiée."""
    path = Path(__file__).parent / "assets" / "e5_tokenizer.json"
    if hashlib.sha256(path.read_bytes()).hexdigest() != TOKENIZER_SHA256:
        raise ValueError("TOKENIZER_INTEGRITY_ERROR")
    result = Tokenizer.from_file(str(path))
    result.no_truncation()
    return result


def token_count(text: str) -> int:
    """Inclut les tokens spéciaux du tokenizer local."""
    return len(tokenizer().encode(text).ids)


def fit_budget(text: str, prefix: str = "") -> list[str]:
    """Scinde les passages trop longs sans jeter leur fin, avec contexte de question."""
    candidate = text if not prefix or text.startswith(prefix) else f"{prefix}\n{text}"
    if token_count(candidate) <= MAX_TOKENS:
        return [candidate]
    if len(text) < 20 or token_count(prefix) >= MAX_TOKENS - 20:
        raise ValueError("QUESTION_EXCEEDS_TOKEN_BUDGET")
    cut = text.rfind(" ", 0, len(text) // 2)
    if cut < len(text) // 4:
        cut = len(text) // 2
    overlap = min(80, len(text) // 8)
    start_right = max(0, cut - overlap)
    boundary = text.rfind(" ", start_right, cut)
    start_right = boundary + 1 if boundary >= 0 else start_right
    return fit_budget(text[:cut].strip(), prefix) + fit_budget(text[start_right:].strip(), prefix)
