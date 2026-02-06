"""Modèle pour les candidats top-k d'une ligne cible."""

from __future__ import annotations

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from laconcorde.matching.schema import MatchCandidate, MatchResult


_HEADERS: dict[str, str] = {
    "rank": "Proposition",
    "source_row": "Ligne source",
    "score": "Similarité (%)",
}


def _friendly_col_name(col: str) -> str:
    """Libellé lisible pour une colonne."""
    if col.startswith("src_"):
        return col[4:].replace("_", " ").title()
    if col.startswith("det_"):
        key = col[4:]
        return key.replace(":", " → ") if ":" in key else key
    return _HEADERS.get(col, col)


class CandidatesModel(QAbstractTableModel):
    """Modèle pour afficher les candidats d'un MatchResult sélectionné."""

    def __init__(
        self,
        result: MatchResult | None = None,
        df_source: pd.DataFrame | None = None,
        preview_cols: list[str] | None = None,
        parent: QAbstractTableModel | None = None,
    ) -> None:
        super().__init__(parent)
        self._result = result
        self._df_source = df_source if df_source is not None else pd.DataFrame()
        self._preview_cols = preview_cols or []
        self._build_table()

    def _build_table(self) -> None:
        """Construit la table des candidats (Proposition, Ligne source, Similarité, Aperçu)."""
        self._rows: list[dict[str, str | int | float]] = []
        self._columns = ["rank", "source_row", "score"]
        if not self._result:
            return
        for rank, c in enumerate(self._result.candidates, 1):
            row: dict[str, str | int | float] = {
                "rank": rank,
                "source_row": c.source_row_id + 1,  # 1-based pour l'utilisateur
                "score": c.score,
            }
            for col in self._preview_cols:
                if col in self._df_source.columns and c.source_row_id < len(self._df_source):
                    val = self._df_source.iloc[c.source_row_id][col]
                    row[f"src_{col}"] = "" if pd.isna(val) else str(val)[:100]
                    if f"src_{col}" not in self._columns:
                        self._columns.append(f"src_{col}")
            row["_tooltip"] = ", ".join(f"{k}: {v:.0f}" for k, v in c.details.items())
            self._rows.append(row)

    def set_result(
        self,
        result: MatchResult | None,
        df_source: pd.DataFrame,
        preview_cols: list[str] | None = None,
    ) -> None:
        """Met à jour le résultat affiché."""
        self.beginResetModel()
        self._result = result
        self._df_source = df_source
        self._preview_cols = preview_cols or []
        self._build_table()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | int | float | None:
        if not index.isValid():
            return None
        row_idx, col_idx = index.row(), index.column()
        if row_idx < 0 or row_idx >= len(self._rows) or col_idx < 0 or col_idx >= len(self._columns):
            return None
        col = self._columns[col_idx]
        val = self._rows[row_idx].get(col, "")

        if role == Qt.ItemDataRole.ToolTipRole:
            tooltip = self._rows[row_idx].get("_tooltip", "")
            if tooltip:
                return f"Similarité par champ (règles de matching): {tooltip}"
            return None

        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if isinstance(val, float):
            return f"{val:.1f}" if col == "score" else val
        if col == "rank":
            return f"#{val}"
        if col == "source_row":
            return f"Ligne {val}"
        return val

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and section < len(self._columns):
            return _friendly_col_name(self._columns[section])
        if orientation == Qt.Orientation.Vertical:
            return str(section + 1)
        return None

    def get_candidate_at_row(self, row: int) -> MatchCandidate | None:
        """Retourne le MatchCandidate à la ligne donnée."""
        if self._result and 0 <= row < len(self._result.candidates):
            return self._result.candidates[row]
        return None
