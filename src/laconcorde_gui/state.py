"""État global de l'application GUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from laconcorde.matching.schema import MatchResult


@dataclass
class AppState:
    """État central de l'application."""

    # Fichiers et feuilles
    source_file: str = ""
    target_file: str = ""
    single_file: str = ""
    source_sheet: str | None = None
    target_sheet: str | None = None
    source_sheet_in_single: str | None = None
    target_sheet_in_single: str | None = None
    source_header_row: int = 1
    target_header_row: int = 1

    # DataFrames (preview ou complets)
    df_source: pd.DataFrame | None = None
    df_target: pd.DataFrame | None = None

    # Configuration (dict pour UI, avant validation)
    config_dict: dict[str, Any] = field(default_factory=dict)

    # Résultats du matching
    results: list[MatchResult] = field(default_factory=list)
    linker: Any = None  # Linker instance
    config: Any = None  # Config validée

    # Décisions utilisateur (target_row_id -> source_row_id ou None)
    choices: dict[int, int | None] = field(default_factory=dict)

    # Historique pour undo (pile de (target_row_id, ancien_chosen))
    undo_stack: list[tuple[int, int | None]] = field(default_factory=list)

    def build_config_dict(self) -> dict[str, Any]:
        """Construit le config_dict à partir de l'état actuel."""
        d: dict[str, Any] = {}
        if self.single_file:
            d["single_file"] = self.single_file
            d["source_sheet_in_single"] = self.source_sheet_in_single
            d["target_sheet_in_single"] = self.target_sheet_in_single
        else:
            d["source_file"] = self.source_file
            d["target_file"] = self.target_file
            d["source_sheet"] = self.source_sheet
            d["target_sheet"] = self.target_sheet
        d["source_header_row"] = self.source_header_row
        d["target_header_row"] = self.target_header_row
        d.update(self.config_dict)
        return d
