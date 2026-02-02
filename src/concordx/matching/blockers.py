"""Stratégies de blocking pour réduire l'espace de recherche."""

from __future__ import annotations

import pandas as pd

from concordx.config import FieldRule
from concordx.normalize import norm_text


def get_block_key_year_or_initial(
    row: pd.Series,
    rules: list[FieldRule],
    source_cols: set[str],
    target_cols: set[str],
    df: pd.DataFrame,
    is_source: bool,
) -> str:
    """
    Génère une clé de bloc : année si présente, sinon première lettre normalisée.

    - Si une règle utilise une colonne "year" (ou similaire), on utilise l'année.
    - Sinon, on utilise la première lettre du champ auteur ou titre.
    """
    year_col = None
    fallback_col = None

    for r in rules:
        col = r.source_col if is_source else r.target_col
        cols = source_cols if is_source else target_cols
        if col not in cols:
            continue
        col_lower = col.lower()
        if "year" in col_lower or "annee" in col_lower or "année" in col_lower:
            year_col = col
            break
        if fallback_col is None:
            if "auteur" in col_lower or "author" in col_lower:
                fallback_col = col
            elif "titre" in col_lower or "title" in col_lower:
                fallback_col = col

    if year_col and year_col in row.index:
        val = row[year_col]
        if pd.notna(val) and str(val).strip():
            y = str(val).strip()[:4]  # Prendre les 4 premiers caractères (année)
            if y.isdigit():
                return f"y_{y}"

    if fallback_col and fallback_col in row.index:
        val = row[fallback_col]
        if pd.notna(val) and str(val).strip():
            norm = norm_text(str(val), remove_diacritics=True)
            if norm:
                return f"i_{norm[0]}"

    return "default"


def build_blocks(
    df: pd.DataFrame,
    rules: list[FieldRule],
    is_source: bool,
) -> dict[str, list[int]]:
    """
    Construit un index de blocs : block_key -> liste d'indices de lignes.

    Args:
        df: DataFrame source ou cible.
        rules: Règles de matching.
        is_source: True si df est la source, False si cible.

    Returns:
        Dict {block_key: [row_indices]}.
    """
    cols = set(df.columns)
    blocks: dict[str, list[int]] = {}

    for idx, row in df.iterrows():
        key = get_block_key_year_or_initial(row, rules, cols, cols, df, is_source=is_source)
        if key not in blocks:
            blocks[key] = []
        blocks[key].append(int(idx))  # type: ignore

    return blocks


def get_candidate_source_indices(
    target_row: pd.Series,
    target_idx: int,
    source_blocks: dict[str, list[int]],
    rules: list[FieldRule],
    source_cols: set[str],
    target_cols: set[str],
    df_source: pd.DataFrame,
    df_target: pd.DataFrame,
) -> list[int]:
    """
    Retourne les indices source candidats pour une ligne cible donnée.

    Utilise le blocking pour limiter la recherche.
    """
    key = get_block_key_year_or_initial(target_row, rules, source_cols, target_cols, df_target, is_source=False)
    if key in source_blocks:
        return source_blocks[key]
    if "default" in source_blocks:
        return source_blocks["default"]
    return list(range(len(df_source)))
