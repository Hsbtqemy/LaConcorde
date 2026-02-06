"""QAbstractTableModel pour afficher un pandas DataFrame."""

from __future__ import annotations

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class DataFrameModel(QAbstractTableModel):
    """Modèle Qt pour afficher un DataFrame pandas en lecture seule."""

    def __init__(self, df: pd.DataFrame | None = None, parent: QAbstractTableModel | None = None) -> None:
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()

    def set_dataframe(self, df: pd.DataFrame) -> None:
        """Remplace le DataFrame et notifie la vue."""
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def dataframe(self) -> pd.DataFrame:
        return self._df

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._df)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._df.columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        row, col = index.row(), index.column()
        if row < 0 or row >= len(self._df) or col < 0 or col >= len(self._df.columns):
            return None
        try:
            val = self._df.iat[row, col]
            if pd.isna(val):
                return ""
            return str(val)
        except (IndexError, KeyError):
            return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if section < len(self._df.columns):
                return str(self._df.columns[section])
        else:
            return str(section + 1)
        return None
