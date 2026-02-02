"""Calcul des scores de similarité par champ."""

from __future__ import annotations

import pandas as pd
from rapidfuzz import fuzz

from concordx.config import FieldRule
from concordx.normalize import norm_doi, norm_text


def score_field(
    source_val: str,
    target_val: str,
    rule: FieldRule,
) -> float:
    """
    Calcule le score (0-100) pour un champ selon la méthode de la règle.

    Args:
        source_val: Valeur source.
        target_val: Valeur cible.
        rule: Règle de matching.

    Returns:
        Score entre 0 et 100.
    """
    # Colonnes DOI : normalisation spécifique (match exact sur nom "doi")
    is_doi_col = rule.source_col.lower() == "doi" or rule.target_col.lower() == "doi"
    if is_doi_col:
        s = norm_doi(source_val)
        t = norm_doi(target_val)
    else:
        if rule.normalize:
            s = norm_text(
                source_val,
                remove_diacritics=rule.remove_diacritics,
            )
            t = norm_text(
                target_val,
                remove_diacritics=rule.remove_diacritics,
            )
        else:
            s = str(source_val) if source_val is not None else ""
            t = str(target_val) if target_val is not None else ""

    if not s and not t:
        return 100.0  # Les deux vides = match parfait
    if not s or not t:
        return 0.0

    method = rule.method or "fuzzy_ratio"

    if method == "exact":
        return 100.0 if s == t else 0.0

    if method == "normalized_exact":
        return 100.0 if s == t else 0.0

    if method == "fuzzy_ratio":
        return float(fuzz.ratio(s, t))

    if method == "token_set":
        return float(fuzz.token_set_ratio(s, t))

    if method == "contains":
        if s in t or t in s:
            return 100.0
        return float(fuzz.partial_ratio(s, t))

    return float(fuzz.ratio(s, t))


def score_row_pair(
    source_row: pd.Series,
    target_row: pd.Series,
    rules: list[FieldRule],
) -> tuple[float, dict[str, float]]:
    """
    Calcule le score global (pondéré) entre une ligne source et une ligne cible.

    Returns:
        (score_global, {field: score})
    """
    total_weight = 0.0
    weighted_sum = 0.0
    details: dict[str, float] = {}

    for rule in rules:
        src_col = rule.source_col
        tgt_col = rule.target_col
        if src_col not in source_row.index or tgt_col not in target_row.index:
            continue
        src_val = source_row[src_col]
        tgt_val = target_row[tgt_col]
        sc = score_field(
            str(src_val) if src_val is not None else "",
            str(tgt_val) if tgt_val is not None else "",
            rule,
        )
        w = rule.weight
        total_weight += w
        weighted_sum += sc * w
        details[f"{src_col}:{tgt_col}"] = sc

    if total_weight == 0:
        return 0.0, details
    return weighted_sum / total_weight, details
