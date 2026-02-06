"""Écran Règles : éditeur de règles, paramètres, colonnes à transférer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from laconcorde.config import VALID_BLOCKERS, VALID_METHODS, VALID_OVERWRITE_MODES

if TYPE_CHECKING:
    from laconcorde_gui.state import AppState


class RulesScreen(QWidget):
    """Écran de configuration des règles et paramètres de matching."""

    def __init__(
        self,
        state: object,
        on_matching_requested: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._on_matching_requested = on_matching_requested or (lambda: None)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Règles
        rules_group = QGroupBox("Règles de matching")
        rules_layout = QVBoxLayout()
        self._rules_table = QTableWidget()
        self._rules_table.setColumnCount(6)
        self._rules_table.setHorizontalHeaderLabels(
            ["Col. source", "Col. cible", "Poids", "Méthode", "Normaliser", "Sans diacritiques"]
        )
        self._rules_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        rules_btns = QHBoxLayout()
        add_btn = QPushButton("Ajouter règle")
        add_btn.clicked.connect(self._add_rule)
        remove_btn = QPushButton("Supprimer règle")
        remove_btn.clicked.connect(self._remove_rule)
        rules_btns.addWidget(add_btn)
        rules_btns.addWidget(remove_btn)
        rules_layout.addWidget(self._rules_table)
        rules_layout.addLayout(rules_btns)
        rules_group.setLayout(rules_layout)
        layout.addWidget(rules_group)

        # Paramètres globaux
        params_group = QGroupBox("Paramètres")
        params_layout = QFormLayout()
        self._overwrite_combo = QComboBox()
        self._overwrite_combo.addItems(sorted(VALID_OVERWRITE_MODES))
        self._overwrite_combo.setCurrentText("if_empty")
        params_layout.addRow("Overwrite mode:", self._overwrite_combo)

        self._create_missing_cb = QCheckBox()
        self._create_missing_cb.setChecked(True)
        params_layout.addRow("Créer colonnes manquantes:", self._create_missing_cb)

        self._suffix_edit = QLineEdit("_src")
        self._suffix_edit.setPlaceholderText("Suffixe en cas de collision")
        params_layout.addRow("Suffixe collision:", self._suffix_edit)

        self._min_score_spin = QDoubleSpinBox()
        self._min_score_spin.setRange(0, 100)
        self._min_score_spin.setValue(0)
        params_layout.addRow("Score minimum:", self._min_score_spin)

        self._auto_accept_spin = QDoubleSpinBox()
        self._auto_accept_spin.setRange(0, 100)
        self._auto_accept_spin.setValue(95)
        params_layout.addRow("Auto-accept score:", self._auto_accept_spin)

        self._top_k_spin = QSpinBox()
        self._top_k_spin.setRange(1, 20)
        self._top_k_spin.setValue(5)
        params_layout.addRow("Top K candidats:", self._top_k_spin)

        self._ambiguity_delta_spin = QDoubleSpinBox()
        self._ambiguity_delta_spin.setRange(0, 100)
        self._ambiguity_delta_spin.setValue(5)
        params_layout.addRow("Delta ambiguïté:", self._ambiguity_delta_spin)

        self._blocker_combo = QComboBox()
        self._blocker_combo.addItems(sorted(VALID_BLOCKERS))
        self._blocker_combo.setCurrentText("year_or_initial")
        params_layout.addRow("Blocker:", self._blocker_combo)

        params_group.setLayout(params_layout)

        # Colonnes à transférer
        transfer_group = QGroupBox("Colonnes à transférer")
        transfer_layout = QVBoxLayout()
        self._transfer_scroll = QScrollArea()
        self._transfer_scroll.setWidgetResizable(True)
        self._transfer_container = QWidget()
        self._transfer_layout = QVBoxLayout(self._transfer_container)
        self._transfer_scroll.setWidget(self._transfer_container)
        transfer_layout.addWidget(self._transfer_scroll)
        transfer_group.setLayout(transfer_layout)

        # Paramètres et Colonnes à transférer côte à côte
        params_transfer_row = QHBoxLayout()
        params_transfer_row.addWidget(params_group, 1)
        params_transfer_row.addWidget(transfer_group, 1)
        layout.addLayout(params_transfer_row)

        # Bouton matching
        self._match_btn = QPushButton("Lancer matching")
        self._match_btn.clicked.connect(self._on_matching_clicked)
        layout.addWidget(self._match_btn)

    def refresh_from_state(self) -> None:
        """Rafraîchit l'UI depuis l'état (colonnes source/cible)."""
        self._refresh_rules_combos()
        self._refresh_transfer_columns()

    def _refresh_rules_combos(self) -> None:
        """Met à jour les combos des règles existantes avec les colonnes disponibles."""
        df_src = getattr(self._state, "df_source", None)
        df_tgt = getattr(self._state, "df_target", None)
        src_cols = list(df_src.columns) if df_src is not None else []
        tgt_cols = list(df_tgt.columns) if df_tgt is not None else []
        for row in range(self._rules_table.rowCount()):
            src_combo = self._rules_table.cellWidget(row, 0)
            tgt_combo = self._rules_table.cellWidget(row, 1)
            if isinstance(src_combo, QComboBox):
                current = src_combo.currentText()
                src_combo.clear()
                src_combo.addItems(src_cols)
                idx = src_combo.findText(current)
                if idx >= 0:
                    src_combo.setCurrentIndex(idx)
            if isinstance(tgt_combo, QComboBox):
                current = tgt_combo.currentText()
                tgt_combo.clear()
                tgt_combo.addItems(tgt_cols)
                idx = tgt_combo.findText(current)
                if idx >= 0:
                    tgt_combo.setCurrentIndex(idx)

    def _refresh_transfer_columns(self) -> None:
        """Reconstruit la liste des colonnes à transférer."""
        while self._transfer_layout.count():
            item = self._transfer_layout.takeAt(0)
            if item and item.layout():
                layout = item.layout()
                while layout.count():
                    sub = layout.takeAt(0)
                    if sub and sub.widget():
                        sub.widget().deleteLater()
        df_src = getattr(self._state, "df_source", None)
        src_cols = list(df_src.columns) if df_src is not None else []
        for col in src_cols:
            row = QHBoxLayout()
            cb = QCheckBox(col)
            row.addWidget(cb)
            rename = QLineEdit()
            rename.setPlaceholderText(f"Renommer (optionnel)")
            rename.setMaximumWidth(200)
            row.addWidget(rename)
            self._transfer_layout.addLayout(row)

    def _add_rule(self) -> None:
        """Ajoute une ligne vide dans la table des règles."""
        row = self._rules_table.rowCount()
        self._rules_table.insertRow(row)
        df_src = getattr(self._state, "df_source", None)
        df_tgt = getattr(self._state, "df_target", None)
        src_cols = list(df_src.columns) if df_src is not None else []
        tgt_cols = list(df_tgt.columns) if df_tgt is not None else []
        src_combo = QComboBox()
        src_combo.addItems(src_cols)
        tgt_combo = QComboBox()
        tgt_combo.addItems(tgt_cols)
        weight_spin = QDoubleSpinBox()
        weight_spin.setRange(0.01, 10)
        weight_spin.setValue(1.0)
        method_combo = QComboBox()
        method_combo.addItems(sorted(VALID_METHODS))
        method_combo.setCurrentText("fuzzy_ratio")
        norm_cb = QCheckBox()
        norm_cb.setChecked(True)
        diac_cb = QCheckBox()
        self._rules_table.setCellWidget(row, 0, src_combo)
        self._rules_table.setCellWidget(row, 1, tgt_combo)
        self._rules_table.setCellWidget(row, 2, weight_spin)
        self._rules_table.setCellWidget(row, 3, method_combo)
        self._rules_table.setCellWidget(row, 4, norm_cb)
        self._rules_table.setCellWidget(row, 5, diac_cb)

    def _remove_rule(self) -> None:
        """Supprime la ligne sélectionnée."""
        row = self._rules_table.currentRow()
        if row >= 0:
            self._rules_table.removeRow(row)

    def get_config_dict(self) -> dict:
        """Construit le config_dict à partir de l'UI."""
        base = self._state.build_config_dict()
        rules = []
        for row in range(self._rules_table.rowCount()):
            src_combo = self._rules_table.cellWidget(row, 0)
            tgt_combo = self._rules_table.cellWidget(row, 1)
            weight_spin = self._rules_table.cellWidget(row, 2)
            method_combo = self._rules_table.cellWidget(row, 3)
            norm_cb = self._rules_table.cellWidget(row, 4)
            diac_cb = self._rules_table.cellWidget(row, 5)
            if not all([src_combo, tgt_combo, weight_spin, method_combo, norm_cb, diac_cb]):
                continue
            rules.append({
                "source_col": src_combo.currentText(),
                "target_col": tgt_combo.currentText(),
                "weight": weight_spin.value(),
                "method": method_combo.currentText(),
                "normalize": norm_cb.isChecked(),
                "remove_diacritics": diac_cb.isChecked(),
            })
        transfer_cols = []
        rename_dict = {}
        for i in range(self._transfer_layout.count()):
            layout_item = self._transfer_layout.itemAt(i)
            if layout_item is None:
                continue
            inner = layout_item.layout()
            if inner is None or inner.count() < 2:
                continue
            cb = inner.itemAt(0).widget()
            rename = inner.itemAt(1).widget()
            if isinstance(cb, QCheckBox) and cb.isChecked():
                col = cb.text()
                transfer_cols.append(col)
                if rename and isinstance(rename, QLineEdit) and rename.text().strip():
                    rename_dict[col] = rename.text().strip()
        base["rules"] = rules
        base["transfer_columns"] = transfer_cols
        base["transfer_column_rename"] = rename_dict
        base["overwrite_mode"] = self._overwrite_combo.currentText()
        base["create_missing_cols"] = self._create_missing_cb.isChecked()
        base["suffix_on_collision"] = self._suffix_edit.text().strip() or "_src"
        base["min_score"] = self._min_score_spin.value()
        base["auto_accept_score"] = self._auto_accept_spin.value()
        base["top_k"] = self._top_k_spin.value()
        base["ambiguity_delta"] = self._ambiguity_delta_spin.value()
        base["blocker"] = self._blocker_combo.currentText()
        return base

    def _on_matching_clicked(self) -> None:
        """Valide et lance le matching."""
        config_dict = self.get_config_dict()
        if not config_dict.get("rules"):
            QMessageBox.warning(self, "Attention", "Ajoutez au moins une règle de matching.")
            return
        self._state.config_dict = config_dict
        self._on_matching_requested()
