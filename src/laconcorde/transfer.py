"""Transfert de colonnes de la source vers la cible."""

from __future__ import annotations

import pandas as pd

from laconcorde.config import ConcatTransfer
from laconcorde.matching.schema import MatchResult


def transfer_columns(
    df_target: pd.DataFrame,
    df_source: pd.DataFrame,
    results: list[MatchResult],
    transfer_columns: list[str],
    *,
    transfer_column_rename: dict[str, str] | None = None,
    overwrite_mode: str = "if_empty",
    create_missing_cols: bool = True,
    suffix_on_collision: str = "_src",
    concat_transfers: list[ConcatTransfer] | None = None,
) -> pd.DataFrame:
    """
    Transfère les colonnes de la source vers la cible selon le mapping validé.

    Args:
        df_target: DataFrame cible (copie, non modifié).
        df_source: DataFrame source.
        results: Résultats de matching avec chosen_source_row_id.
        transfer_columns: Colonnes à transférer depuis la source.
        transfer_column_rename: Optionnel. Mapping {nom_source: nom_cible} pour renommer.
        overwrite_mode: never, if_empty, always.
        create_missing_cols: Créer les colonnes si absentes de la cible.
        suffix_on_collision: Suffixe si colonne existe et overwrite=never.
        concat_transfers: Concaténations multi-colonnes vers une colonne cible.

    Returns:
        Nouveau DataFrame cible enrichi.
    """
    out = df_target.copy()
    source_cols = set(df_source.columns)
    rename = transfer_column_rename or {}

    for col in transfer_columns:
        if col not in source_cols:
            continue

        target_col_name = rename.get(col, col)
        if target_col_name in out.columns and overwrite_mode == "never":
            target_col_name = target_col_name + suffix_on_collision

        if target_col_name not in out.columns and create_missing_cols:
            out[target_col_name] = pd.NA

        col_idx = out.columns.get_loc(target_col_name) if target_col_name in out.columns else None
        if col_idx is None:
            continue

        for r in results:
            if r.chosen_source_row_id is None:
                continue
            tgt_idx = r.target_row_id
            src_idx = r.chosen_source_row_id
            val = df_source.iloc[src_idx][col]

            existing = out.iat[tgt_idx, col_idx]  # type: ignore[index]
            do_write = False
            if overwrite_mode == "always":
                do_write = True
            elif overwrite_mode == "if_empty":
                do_write = pd.isna(existing) or str(existing).strip() == ""
            elif overwrite_mode == "never":
                do_write = True  # On écrit dans la nouvelle colonne _src

            if do_write:
                out.iat[tgt_idx, col_idx] = val  # type: ignore[index]

    if concat_transfers:
        _apply_concat_transfers(
            out,
            df_source,
            results,
            concat_transfers,
            create_missing_cols=create_missing_cols,
        )

    return out


def _apply_concat_transfers(
    out: pd.DataFrame,
    df_source: pd.DataFrame,
    results: list[MatchResult],
    concat_transfers: list[ConcatTransfer],
    *,
    create_missing_cols: bool,
) -> None:
    """Applique les concaténations sur le DataFrame cible (in-place)."""
    source_cols = set(df_source.columns)

    def _is_empty(val: object) -> bool:
        return pd.isna(val) or str(val).strip() == ""

    for cfg in concat_transfers:
        target_col = cfg.target_col
        if target_col not in out.columns and create_missing_cols:
            out[target_col] = pd.NA
        if target_col not in out.columns:
            continue
        col_idx = out.columns.get_loc(target_col)
        mode = cfg.overwrite_mode
        if mode == "replace":
            mode = "always"
        join_sep = cfg.join_with_existing if cfg.join_with_existing is not None else cfg.separator

        for r in results:
            if r.chosen_source_row_id is None:
                continue
            tgt_idx = r.target_row_id
            src_idx = r.chosen_source_row_id

            parts: list[str] = []
            for src in cfg.sources:
                if src.col not in source_cols or src_idx >= len(df_source):
                    continue
                val = df_source.iloc[src_idx][src.col]
                text = "" if pd.isna(val) else str(val)
                if cfg.skip_empty and text.strip() == "":
                    continue
                part = f"{src.prefix}{text}" if src.prefix else text
                parts.append(part)

            if not parts:
                continue
            new_text = cfg.separator.join(parts)

            existing = out.iat[tgt_idx, col_idx]  # type: ignore[index]
            if mode == "if_empty":
                if _is_empty(existing):
                    out.iat[tgt_idx, col_idx] = new_text  # type: ignore[index]
            elif mode == "always":
                out.iat[tgt_idx, col_idx] = new_text  # type: ignore[index]
            elif mode == "append":
                if _is_empty(existing):
                    out.iat[tgt_idx, col_idx] = new_text  # type: ignore[index]
                else:
                    out.iat[tgt_idx, col_idx] = f"{existing}{join_sep}{new_text}"  # type: ignore[index]
            elif mode == "prepend":
                if _is_empty(existing):
                    out.iat[tgt_idx, col_idx] = new_text  # type: ignore[index]
                else:
                    out.iat[tgt_idx, col_idx] = f"{new_text}{join_sep}{existing}"  # type: ignore[index]


def build_mapping_csv(
    results: list[MatchResult],
    output_path: str,
) -> None:
    """
    Génère mapping.csv avec target_row_id, source_row_id, score, status, explanation.
    """
    rows = []
    for r in results:
        rows.append(
            {
                "target_row_id": r.target_row_id,
                "source_row_id": r.chosen_source_row_id if r.chosen_source_row_id is not None else "",
                "score": r.best_score,
                "status": r.status,
                "explanation": r.explanation,
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8")
