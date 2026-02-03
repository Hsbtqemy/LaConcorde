"""Normalisation de texte et DOI."""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import unquote


def _remove_diacritics(s: str) -> str:
    """Retire les diacritiques (accents) d'une chaîne."""
    nfd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def norm_text(
    s: str | float | int | None,
    *,
    lower: bool = True,
    strip: bool = True,
    remove_diacritics: bool = False,
) -> str:
    """
    Normalise un texte : NFKC, espaces multiples → espace simple, lower, strip.

    Args:
        s: Valeur à normaliser (convertie en str si numérique).
        lower: Mettre en minuscules.
        strip: Supprimer espaces en début/fin.
        remove_diacritics: Supprimer les accents.

    Returns:
        Chaîne normalisée.
    """
    if s is None or (isinstance(s, float) and (s != s or s == float("inf"))):
        return ""
    text = str(s).strip() if strip else str(s)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    if strip:
        text = text.strip()
    if lower:
        text = text.lower()
    if remove_diacritics:
        text = _remove_diacritics(text)
    return text


def norm_doi(s: str | float | int | None) -> str:
    """
    Normalise un DOI pour comparaison fiable entre tableurs.

    Gère :
    - Préfixes URL (https://doi.org/, dx.doi.org, doi:)
    - Paramètres d'URL (?ref=xyz) et fragments (#anchor)
    - Encodage URL (%2F → /)
    - Slash final, espaces multiples, espaces autour du /
    - Casse (lower)

    Args:
        s: Valeur contenant potentiellement un DOI.

    Returns:
        DOI normalisé ou chaîne vide.
    """
    if s is None or (isinstance(s, float) and (s != s or s == float("inf"))):
        return ""
    text = str(s).strip().lower()
    text = unicodedata.normalize("NFKC", text)

    # Décoder l'encodage URL (%2F → /, %20 → espace, etc.)
    try:
        text = unquote(text)
    except Exception:
        pass

    # Retirer paramètres et fragments (?... #...)
    text = re.sub(r"[?#].*$", "", text)

    # Retirer préfixes courants
    prefixes = [
        r"^https?://(?:dx\.)?doi\.org/",
        r"^doi\s*:?\s*",
        r"^https?://[^/]*doi\.org/",
    ]
    for pat in prefixes:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)

    # Espaces multiples → espace unique, retirer espaces autour de /
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*/\s*", "/", text)
    text = text.strip()

    # Slash final
    text = text.rstrip("/")

    return text.strip()


def safe_str(val: Any) -> str:
    """Convertit une valeur en chaîne pour affichage/stockage."""
    if val is None or (isinstance(val, float) and (val != val or val == float("inf"))):
        return ""
    return str(val)
