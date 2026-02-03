"""Génération du rapport et onglet REPORT."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from laconcorde import __version__
from laconcorde.config import Config
from laconcorde.matching.schema import MatchResult


def build_report_df(
    results: list[MatchResult],
    config: Config,
) -> pd.DataFrame:
    """
    Construit le DataFrame pour l'onglet REPORT.

    Contient : nb lignes cible, nb auto, nb accepted, nb rejected, nb ambiguous,
    nb skipped, paramètres, horodatage, version.
    """
    n_total = len(results)
    n_auto = sum(1 for r in results if r.status == "auto")
    n_accepted = sum(1 for r in results if r.status == "accepted")
    n_rejected = sum(1 for r in results if r.status == "rejected")
    n_pending = sum(1 for r in results if r.status == "pending")
    n_ambiguous = sum(1 for r in results if r.is_ambiguous)
    n_skipped = sum(1 for r in results if r.status == "skipped")

    rows = [
        ("Metric", "Value"),
        ("nb_target_rows", n_total),
        ("nb_auto", n_auto),
        ("nb_accepted", n_accepted),
        ("nb_rejected_no_match", n_rejected),
        ("nb_pending", n_pending),
        ("nb_ambiguous", n_ambiguous),
        ("nb_skipped", n_skipped),
        ("", ""),
        ("Parameters", ""),
        ("min_score", config.min_score),
        ("auto_accept_score", config.auto_accept_score),
        ("top_k", config.top_k),
        ("ambiguity_delta", config.ambiguity_delta),
        ("blocker", config.blocker),
        ("overwrite_mode", config.overwrite_mode),
        ("", ""),
        ("Rules", ""),
    ]
    for i, r in enumerate(config.rules):
        rows.append((f"rule_{i}", f"{r.source_col}->{r.target_col} w={r.weight} m={r.method}"))

    transfer_info = ", ".join(config.transfer_columns)
    if config.transfer_column_rename:
        rename_str = ", ".join(f"{k}->{v}" for k, v in config.transfer_column_rename.items())
        transfer_info += f" (rename: {rename_str})"
    rows.extend(
        [
            ("", ""),
            ("Transfer columns", transfer_info),
            ("", ""),
            ("timestamp", datetime.now().isoformat()),
            ("version", __version__),
        ]
    )

    return pd.DataFrame(rows, columns=["Key", "Value"])


def print_report_console(results: list[MatchResult], config: Config) -> None:
    """Affiche un résumé du rapport en console."""
    n_total = len(results)
    n_auto = sum(1 for r in results if r.status == "auto")
    n_accepted = sum(1 for r in results if r.status == "accepted")
    n_rejected = sum(1 for r in results if r.status == "rejected")
    n_pending = sum(1 for r in results if r.status == "pending")
    n_ambiguous = sum(1 for r in results if r.is_ambiguous)
    n_skipped = sum(1 for r in results if r.status == "skipped")

    print("\n=== LaConcorde Report ===")
    print(f"  Lignes cible:     {n_total}")
    print(f"  Auto-acceptés:    {n_auto}")
    print(f"  Acceptés (user):  {n_accepted}")
    print(f"  Rejetés:          {n_rejected}")
    print(f"  En attente:       {n_pending}")
    print(f"  Ambigus:          {n_ambiguous}")
    print(f"  Skipped:          {n_skipped}")
    print(f"  Version:          {__version__}")
    print(f"  Timestamp:        {datetime.now().isoformat()}")
    print("======================\n")
