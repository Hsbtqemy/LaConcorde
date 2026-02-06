"""Widgets et delegates pour l'écran Validation (UX refondue)."""

from __future__ import annotations

from typing import Any

import pandas as pd
from PySide6.QtCore import QModelIndex, Qt, QRect
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHeaderView,
    QLabel,
    QMenu,
    QProgressBar,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from laconcorde.matching.schema import MatchCandidate, MatchResult


def _norm_compare(a: str, b: str) -> bool:
    """Compare normalisée (strip, lower) pour détecter différences."""
    sa = str(a).strip().lower() if a is not None and not (isinstance(a, float) and pd.isna(a)) else ""
    sb = str(b).strip().lower() if b is not None and not (isinstance(b, float) and pd.isna(b)) else ""
    return sa != sb


class ScoreProgressDelegate(QStyledItemDelegate):
    """Delegate : affiche une progressbar pour la colonne Similarité."""

    def paint(self, painter: QPainter, option: Any, index: QModelIndex) -> None:
        model = index.model()
        if not model:
            return
        col_name = getattr(model, "_columns", [])
        col = index.column()
        if col >= len(col_name) or col_name[col] != "score":
            super().paint(painter, option, index)
            return
        val = model.data(index, Qt.ItemDataRole.DisplayRole)
        try:
            score = float(str(val).replace(",", ".").replace("%", ""))
        except (ValueError, TypeError):
            super().paint(painter, option, index)
            return
        r = option.rect.adjusted(2, 2, -2, -2)
        painter.save()
        painter.setPen(QColor(200, 200, 200))
        painter.setBrush(QColor(240, 240, 240))
        painter.drawRoundedRect(r, 2, 2)
        fill_w = int(r.width() * score / 100)
        if fill_w > 0:
            fill_r = QRect(r.x(), r.y(), fill_w, r.height())
            painter.setBrush(QColor(76, 175, 80))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(fill_r, 2, 2)
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(r, Qt.AlignmentFlag.AlignCenter, f"{score:.0f}%")
        painter.restore()


class ElideTextDelegate(QStyledItemDelegate):
    """Delegate : tronque le texte avec ellipsis, tooltip = texte complet."""

    def __init__(self, max_len: int = 60, parent: QStyledItemDelegate | None = None) -> None:
        super().__init__(parent)
        self._max_len = max_len

    def paint(self, painter: QPainter, option: Any, index: QModelIndex) -> None:
        super().paint(painter, option, index)

    def displayText(self, value: Any, locale: Any) -> str:
        text = str(value) if value is not None else ""
        if len(text) > self._max_len:
            return text[: self._max_len - 1] + "…"
        return text


class FieldComparisonView(QFrame):
    """
    Vue champ-par-champ CIBLE vs SOURCE avec surlignage des différences.
    Colonnes : Champ | Cible | Source | Score
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Champ", "Cible", "Source", "Score"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._explanation_label = QLabel("")
        self._explanation_label.setWordWrap(True)
        self._explanation_label.setStyleSheet("font-size: 11px; color: #555;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._explanation_label)
        layout.addWidget(self._table)

    def _on_context_menu(self, pos: Any) -> None:
        item = self._table.itemAt(pos)
        if not item or item.column() not in (1, 2):
            return
        text = item.text()
        if not text:
            return
        menu = QMenu(self)
        copy_act = menu.addAction("Copier")
        if menu.exec(self._table.mapToGlobal(pos)) == copy_act:
            QApplication.clipboard().setText(text)

    def set_comparison(
        self,
        result: MatchResult | None,
        candidate: MatchCandidate | None,
        df_target: pd.DataFrame,
        df_source: pd.DataFrame,
        rules: list[Any],
    ) -> None:
        """Met à jour la vue avec les données cible/source pour le candidat sélectionné."""
        self._table.setRowCount(0)
        self._explanation_label.setText("")
        if not result or not candidate or not rules:
            self._explanation_label.setText("Sélectionnez une proposition.")
            return
        tgt_idx = result.target_row_id
        src_idx = candidate.source_row_id
        details = candidate.details
        rows: list[tuple[str, str, str, float]] = []
        for rule in rules:
            if hasattr(rule, "source_col"):
                src_col = rule.source_col
                tgt_col = rule.target_col
            else:
                src_col = rule.get("source_col", "")
                tgt_col = rule.get("target_col", "")
            if not src_col or not tgt_col:
                continue
            tgt_val = ""
            if tgt_col in df_target.columns and tgt_idx < len(df_target):
                v = df_target.iloc[tgt_idx][tgt_col]
                tgt_val = "" if pd.isna(v) else str(v)
            src_val = ""
            if src_col in df_source.columns and src_idx < len(df_source):
                v = df_source.iloc[src_idx][src_col]
                src_val = "" if pd.isna(v) else str(v)
            key = f"{src_col}:{tgt_col}"
            score = details.get(key, 0.0)
            rows.append((f"{src_col}→{tgt_col}", tgt_val, src_val, score))
        parts: list[str] = []
        for _, _, _, sc in rows:
            parts.append(f"{sc:.0f}")
        self._explanation_label.setText("Scores: " + " + ".join(parts) + f" → {candidate.score:.1f}")
        self._table.setRowCount(len(rows))
        for i, (champ, tgt_val, src_val, score) in enumerate(rows):
            self._table.setItem(i, 0, QTableWidgetItem(champ))
            ti = QTableWidgetItem(tgt_val[:200] + ("…" if len(tgt_val) > 200 else ""))
            ti.setToolTip(tgt_val)
            self._table.setItem(i, 1, ti)
            si = QTableWidgetItem(src_val[:200] + ("…" if len(src_val) > 200 else ""))
            si.setToolTip(src_val)
            self._table.setItem(i, 2, si)
            self._table.setItem(i, 3, QTableWidgetItem(f"{score:.0f}"))
            if _norm_compare(tgt_val, src_val):
                for c in (1, 2):
                    it = self._table.item(i, c)
                    if it:
                        it.setBackground(QColor(255, 255, 200))
