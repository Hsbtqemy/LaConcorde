"""Écran Projet : sélection fichiers, feuilles, aperçus."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from laconcorde.io_excel import SUPPORTED_INPUT_FILTER, list_sheets, load_sheet
from laconcorde_gui.models import DataFrameModel


class ProjectScreen(QWidget):
    """Écran de configuration du projet (fichiers source/cible)."""

    PREVIEW_ROWS = 200

    def __init__(self, state: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Mode single file
        self._single_file_cb = QCheckBox("Un seul fichier (2 feuilles)")
        self._single_file_cb.toggled.connect(self._on_single_file_toggled)
        layout.addWidget(self._single_file_cb)

        # Groupe fichiers
        file_group = QGroupBox("Fichiers")
        file_layout = QFormLayout()

        self._source_file_edit = QLineEdit()
        self._source_file_edit.setPlaceholderText("Chemin fichier source...")
        self._source_browse = QPushButton("Parcourir")
        self._source_browse.clicked.connect(lambda: self._browse_file("source"))
        src_row = QHBoxLayout()
        src_row.addWidget(self._source_file_edit)
        src_row.addWidget(self._source_browse)
        file_layout.addRow("Source xlsx:", src_row)

        self._source_sheet_combo = QComboBox()
        self._source_sheet_combo.setMinimumWidth(150)
        file_layout.addRow("Feuille source:", self._source_sheet_combo)
        self._source_header_spin = QSpinBox()
        self._source_header_spin.setRange(1, 10000)
        self._source_header_spin.setValue(getattr(self._state, "source_header_row", 1))
        self._source_header_spin.setToolTip("Numéro de ligne (1 = première) contenant les en-têtes.")
        file_layout.addRow("Ligne d'en-tête source:", self._source_header_spin)

        self._target_file_edit = QLineEdit()
        self._target_file_edit.setPlaceholderText("Chemin fichier cible...")
        self._target_browse = QPushButton("Parcourir")
        self._target_browse.clicked.connect(lambda: self._browse_file("target"))
        tgt_row = QHBoxLayout()
        tgt_row.addWidget(self._target_file_edit)
        tgt_row.addWidget(self._target_browse)
        file_layout.addRow("Cible xlsx:", tgt_row)

        self._target_sheet_combo = QComboBox()
        file_layout.addRow("Feuille cible:", self._target_sheet_combo)
        self._target_header_spin = QSpinBox()
        self._target_header_spin.setRange(1, 10000)
        self._target_header_spin.setValue(getattr(self._state, "target_header_row", 1))
        self._target_header_spin.setToolTip("Numéro de ligne (1 = première) contenant les en-têtes.")
        file_layout.addRow("Ligne d'en-tête cible:", self._target_header_spin)

        self._single_file_edit = QLineEdit()
        self._single_file_edit.setPlaceholderText("Chemin fichier unique...")
        self._single_browse = QPushButton("Parcourir")
        self._single_browse.clicked.connect(self._browse_single_file)
        single_row = QHBoxLayout()
        single_row.addWidget(self._single_file_edit)
        single_row.addWidget(self._single_browse)
        file_layout.addRow("Fichier unique:", single_row)

        self._single_src_sheet_combo = QComboBox()
        file_layout.addRow("Feuille source (single):", self._single_src_sheet_combo)
        self._single_tgt_sheet_combo = QComboBox()
        file_layout.addRow("Feuille cible (single):", self._single_tgt_sheet_combo)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # Bouton charger
        self._load_btn = QPushButton("Charger aperçus")
        self._load_btn.clicked.connect(self._load_previews)
        layout.addWidget(self._load_btn)

        # Aperçus
        preview_group = QGroupBox("Aperçus")
        preview_layout = QVBoxLayout()
        self._source_label = QLabel("Source: —")
        self._target_label = QLabel("Cible: —")
        preview_layout.addWidget(self._source_label)
        self._source_table = QTableView()
        self._source_table.setModel(DataFrameModel())
        self._source_table.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self._source_table)
        preview_layout.addWidget(self._target_label)
        self._target_table = QTableView()
        self._target_table.setModel(DataFrameModel())
        self._target_table.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self._target_table)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        self._on_single_file_toggled(False)

    def _on_single_file_toggled(self, checked: bool) -> None:
        self._source_file_edit.setEnabled(not checked)
        self._source_browse.setEnabled(not checked)
        self._source_sheet_combo.setEnabled(not checked)
        self._target_file_edit.setEnabled(not checked)
        self._target_browse.setEnabled(not checked)
        self._target_sheet_combo.setEnabled(not checked)
        self._single_file_edit.setEnabled(checked)
        self._single_browse.setEnabled(checked)
        self._single_src_sheet_combo.setEnabled(checked)
        self._single_tgt_sheet_combo.setEnabled(checked)

    def _browse_file(self, which: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Sélectionner fichier tableur", "", SUPPORTED_INPUT_FILTER)
        if path:
            if which == "source":
                self._source_file_edit.setText(path)
                self._update_sheet_combo(self._source_sheet_combo, path)
            else:
                self._target_file_edit.setText(path)
                self._update_sheet_combo(self._target_sheet_combo, path)

    def _browse_single_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Sélectionner fichier tableur", "", SUPPORTED_INPUT_FILTER)
        if path:
            self._single_file_edit.setText(path)
            sheets = self._update_sheet_combo(self._single_src_sheet_combo, path)
            self._single_tgt_sheet_combo.clear()
            self._single_tgt_sheet_combo.addItems(sheets)

    def _update_sheet_combo(self, combo: QComboBox, path: str) -> list[str]:
        combo.clear()
        try:
            sheets = list_sheets(path)
            combo.addItems(sheets)
            return sheets
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de lire les feuilles: {e}")
            return []

    def _load_previews(self) -> None:
        try:
            if self._single_file_cb.isChecked():
                path = self._single_file_edit.text().strip()
                if not path:
                    QMessageBox.warning(self, "Attention", "Sélectionnez un fichier.")
                    return
                src_sheet = self._single_src_sheet_combo.currentText() or None
                tgt_sheet = self._single_tgt_sheet_combo.currentText() or None
                src_header = self._source_header_spin.value()
                tgt_header = self._target_header_spin.value()
                df_src = load_sheet(path, src_sheet, header_row=src_header).head(self.PREVIEW_ROWS)
                df_tgt = load_sheet(path, tgt_sheet, header_row=tgt_header).head(self.PREVIEW_ROWS)
                self._state.single_file = path
                self._state.source_sheet_in_single = src_sheet
                self._state.target_sheet_in_single = tgt_sheet
                self._state.source_file = ""
                self._state.target_file = ""
                self._state.source_header_row = src_header
                self._state.target_header_row = tgt_header
            else:
                src_path = self._source_file_edit.text().strip()
                tgt_path = self._target_file_edit.text().strip()
                if not src_path or not tgt_path:
                    QMessageBox.warning(self, "Attention", "Sélectionnez les deux fichiers.")
                    return
                src_sheet = self._source_sheet_combo.currentText() or None
                tgt_sheet = self._target_sheet_combo.currentText() or None
                src_header = self._source_header_spin.value()
                tgt_header = self._target_header_spin.value()
                df_src = load_sheet(src_path, src_sheet, header_row=src_header).head(self.PREVIEW_ROWS)
                df_tgt = load_sheet(tgt_path, tgt_sheet, header_row=tgt_header).head(self.PREVIEW_ROWS)
                self._state.source_file = src_path
                self._state.target_file = tgt_path
                self._state.source_sheet = src_sheet
                self._state.target_sheet = tgt_sheet
                self._state.single_file = ""
                self._state.source_header_row = src_header
                self._state.target_header_row = tgt_header

            self._state.df_source = df_src
            self._state.df_target = df_tgt
            self._source_table.model().set_dataframe(df_src)
            self._target_table.model().set_dataframe(df_tgt)
            self._source_label.setText(f"Source: {df_src.shape[0]} lignes × {df_src.shape[1]} colonnes")
            self._target_label.setText(f"Cible: {df_tgt.shape[0]} lignes × {df_tgt.shape[1]} colonnes")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))
