"""Modèle pour la file d'attente des MatchResult (validation)."""

from __future__ import annotations

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from laconcorde.matching.schema import MatchResult


class ResultsQueueModel(QAbstractTableModel):
    """Modèle pour la liste des MatchResult avec colonnes cibles jointes."""

    def __init__(
        self,
        results: list[MatchResult] | None = None,
        df_target: pd.DataFrame | None = None,
        preview_cols: list[str] | None = None,
        parent: QAbstractTableModel | None = None,
    ) -> None:
        super().__init__(parent)
        self._results = results or []
        self._df_target = df_target if df_target is not None else pd.DataFrame()
        self._preview_cols = preview_cols or []
        self._selected_ids: set[int] = set()
        self._build_table()

    def _build_table(self) -> None:
        """Construit la table flattened."""
        rows: list[dict[str, str | int | float | bool]] = []
        for r in self._results:
            chosen = r.chosen_source_row_id if r.chosen_source_row_id is not None else -1
            row: dict[str, str | int | float | bool] = {
                "selected": r.target_row_id in self._selected_ids,
                "target_row_id": r.target_row_id,
                "best_score": r.best_score,
                "status": r.status,
                "is_ambiguous": r.is_ambiguous,
                "chosen_source_row_id": chosen,
                "explanation": r.explanation,
            }
            for col in self._preview_cols:
                if col in self._df_target.columns and r.target_row_id < len(self._df_target):
                    val = self._df_target.iloc[r.target_row_id][col]
                    row[f"tgt_{col}"] = "" if pd.isna(val) else str(val)[:50]
            rows.append(row)
        self._table = rows
        self._columns = (
            ["selected", "target_row_id", "best_score", "status", "is_ambiguous", "chosen_source_row_id", "explanation"]
            + [f"tgt_{c}" for c in self._preview_cols if c in (self._df_target.columns if len(self._df_target) > 0 else [])]
        )

    def set_data(
        self,
        results: list[MatchResult],
        df_target: pd.DataFrame,
        preview_cols: list[str] | None = None,
    ) -> None:
        """Met à jour les données."""
        self.beginResetModel()
        self._results = results
        if self._selected_ids:
            current_ids = {r.target_row_id for r in results}
            self._selected_ids = {rid for rid in self._selected_ids if rid in current_ids}
        self._df_target = df_target
        self._preview_cols = preview_cols or []
        self._build_table()
        self.endResetModel()

    def update_result(
        self, target_row_id: int, chosen_source_row_id: int | None, status: str | None = None
    ) -> None:
        """Met à jour un résultat et émet dataChanged."""
        for i, r in enumerate(self._results):
            if r.target_row_id == target_row_id:
                r.chosen_source_row_id = chosen_source_row_id
                r.status = status or ("rejected" if chosen_source_row_id is None else "accepted")
                r.explanation = (
                    "Skipped (user)" if status == "skipped"
                    else "No match (user)" if chosen_source_row_id is None
                    else "User accepted"
                )
                chosen_val = chosen_source_row_id if chosen_source_row_id is not None else -1
                self._table[i]["chosen_source_row_id"] = chosen_val
                self._table[i]["status"] = r.status
                self._table[i]["explanation"] = r.explanation
                top_left = self.index(i, 0)
                bottom_right = self.index(i, len(self._columns) - 1)
                self.dataChanged.emit(top_left, bottom_right)
                break

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._table)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | int | float | bool | None:
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if row < 0 or row >= len(self._table) or col < 0 or col >= len(self._columns):
            return None
        col_name = self._columns[col]
        if col_name == "selected":
            if role == Qt.ItemDataRole.CheckStateRole:
                return Qt.CheckState.Checked if self._table[row].get("selected", False) else Qt.CheckState.Unchecked
            if role == Qt.ItemDataRole.DisplayRole:
                return ""
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            val = self._table[row].get(col_name, "")
            if isinstance(val, bool):
                return "Oui" if val else "Non"
            return val
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        col_name = self._columns[index.column()]
        if col_name == "selected":
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def setData(self, index: QModelIndex, value: object, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False
        col_name = self._columns[index.column()]
        if col_name != "selected" or role != Qt.ItemDataRole.CheckStateRole:
            return False
        checked = value == Qt.CheckState.Checked
        row = index.row()
        if row < 0 or row >= len(self._table):
            return False
        target_row_id = self._table[row].get("target_row_id")
        if isinstance(target_row_id, int):
            if checked:
                self._selected_ids.add(target_row_id)
            else:
                self._selected_ids.discard(target_row_id)
            self._table[row]["selected"] = checked
            self.dataChanged.emit(index, index)
            return True
        return False

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and section < len(self._columns):
            return "✓" if self._columns[section] == "selected" else self._columns[section]
        if orientation == Qt.Orientation.Vertical:
            return str(section + 1)
        return None

    def get_result_at_row(self, row: int) -> MatchResult | None:
        """Retourne le MatchResult à la ligne donnée."""
        if 0 <= row < len(self._results):
            return self._results[row]
        return None

    def get_column_index(self, name: str) -> int | None:
        """Retourne l'index d'une colonne connue."""
        if name in self._columns:
            return self._columns.index(name)
        return None

    def get_selected_target_ids(self) -> list[int]:
        """Retourne la liste des target_row_id cochés."""
        return sorted(self._selected_ids)

    def select_all(self) -> None:
        """Coche toutes les lignes."""
        for r in self._results:
            self._selected_ids.add(r.target_row_id)
        for i, row in enumerate(self._table):
            row["selected"] = True
        if self._table:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._table) - 1, len(self._columns) - 1)
            self.dataChanged.emit(top_left, bottom_right)

    def select_visible_ids(self, target_ids: list[int]) -> None:
        """Coche les lignes correspondant aux target_row_id donnés."""
        for tid in target_ids:
            self._selected_ids.add(tid)
        for i, row in enumerate(self._table):
            if row.get("target_row_id") in self._selected_ids:
                row["selected"] = True
        if self._table:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._table) - 1, len(self._columns) - 1)
            self.dataChanged.emit(top_left, bottom_right)

    def clear_selection(self) -> None:
        """Décoche toutes les lignes."""
        self._selected_ids.clear()
        for row in self._table:
            row["selected"] = False
        if self._table:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._table) - 1, len(self._columns) - 1)
            self.dataChanged.emit(top_left, bottom_right)
