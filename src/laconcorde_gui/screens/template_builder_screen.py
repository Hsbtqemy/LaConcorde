"""Écran Template Builder : définition des zones et mapping vers un template."""

from __future__ import annotations

import json
import pandas as pd
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from laconcorde.io_excel import SUPPORTED_INPUT_FILTER, list_sheets, load_sheet, load_sheet_raw
from laconcorde.template_builder import TemplateBuilderConfig, build_output
from laconcorde_gui.models import DataFrameModel
from laconcorde_gui.workers import TemplateBuilderWorker


def _parse_int_list(text: str) -> list[int]:
    items: list[int] = []
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            items.append(int(part))
        except ValueError:
            continue
    return items


def _format_int_list(values: list[int]) -> str:
    return ", ".join(str(v) for v in values)


class _ConcatSourceWidget(QWidget):
    def __init__(self, source_cols: list[str], col: str = "", prefix: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._col_combo = QComboBox()
        self._prefix_edit = QLineEdit()
        self._prefix_edit.setPlaceholderText("Préfixe (optionnel)")
        layout.addWidget(self._col_combo, 2)
        layout.addWidget(self._prefix_edit, 3)
        self.refresh_source_cols(source_cols, current=col)
        if prefix:
            self._prefix_edit.setText(prefix)

    def refresh_source_cols(self, source_cols: list[str], current: str | None = None) -> None:
        cur = current if current is not None else self._col_combo.currentText()
        items = list(source_cols)
        if cur and cur not in items:
            items.insert(0, cur)
        self._col_combo.clear()
        self._col_combo.addItems(items)
        if cur:
            self._col_combo.setCurrentText(cur)

    def get_data(self) -> tuple[str, str]:
        return self._col_combo.currentText().strip(), self._prefix_edit.text()


class _ConcatDialog(QDialog):
    def __init__(
        self,
        source_cols: list[str],
        preset: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Concaténation")
        self._source_cols = list(source_cols)
        self._setup_ui()
        if preset:
            self._load_preset(preset)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._separator_edit = QLineEdit("; ")
        self._skip_empty_cb = QCheckBox("Ignorer vides")
        self._skip_empty_cb.setChecked(True)
        self._dedupe_cb = QCheckBox("Dédupliquer les valeurs")
        form.addRow("Séparateur:", self._separator_edit)
        form.addRow("", self._skip_empty_cb)
        form.addRow("", self._dedupe_cb)
        layout.addLayout(form)

        layout.addWidget(QLabel("Colonnes source (ordre)"))
        self._sources_list = QListWidget()
        self._sources_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._sources_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._sources_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._sources_list.setDragEnabled(True)
        self._sources_list.setAcceptDrops(True)
        self._sources_list.setDropIndicatorShown(True)
        layout.addWidget(self._sources_list)

        btns = QHBoxLayout()
        add_btn = QPushButton("Ajouter colonne")
        add_btn.clicked.connect(self._add_source_row)
        remove_btn = QPushButton("Supprimer colonne")
        remove_btn.clicked.connect(self._remove_selected_row)
        up_btn = QPushButton("↑")
        up_btn.clicked.connect(lambda: self._move_selected(-1))
        down_btn = QPushButton("↓")
        down_btn.clicked.connect(lambda: self._move_selected(1))
        btns.addWidget(add_btn)
        btns.addWidget(remove_btn)
        btns.addStretch()
        btns.addWidget(up_btn)
        btns.addWidget(down_btn)
        layout.addLayout(btns)

        action_row = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        action_row.addStretch()
        action_row.addWidget(ok_btn)
        action_row.addWidget(cancel_btn)
        layout.addLayout(action_row)

        self._add_source_row()

    def _add_source_row(self, col: str = "", prefix: str = "") -> None:
        item = QListWidgetItem()
        widget = _ConcatSourceWidget(self._source_cols, col=col, prefix=prefix)
        item.setSizeHint(widget.sizeHint())
        self._sources_list.addItem(item)
        self._sources_list.setItemWidget(item, widget)
        self._sources_list.setCurrentItem(item)

    def _remove_selected_row(self) -> None:
        row = self._sources_list.currentRow()
        if row >= 0:
            item = self._sources_list.item(row)
            widget = self._sources_list.itemWidget(item) if item else None
            self._sources_list.takeItem(row)
            if widget:
                widget.deleteLater()

    def _move_selected(self, delta: int) -> None:
        row = self._sources_list.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= self._sources_list.count():
            return
        item = self._sources_list.item(row)
        widget = self._sources_list.itemWidget(item) if item else None
        self._sources_list.takeItem(row)
        if widget:
            widget.setParent(None)
        self._sources_list.insertItem(new_row, item)
        if widget:
            self._sources_list.setItemWidget(item, widget)
        self._sources_list.setCurrentRow(new_row)

    def _load_preset(self, preset: dict[str, Any]) -> None:
        self._separator_edit.setText(str(preset.get("separator", "; ")))
        self._skip_empty_cb.setChecked(bool(preset.get("skip_empty", True)))
        self._dedupe_cb.setChecked(bool(preset.get("deduplicate", False)))
        sources = preset.get("sources", [])
        if sources:
            self._sources_list.clear()
            for src in sources:
                self._add_source_row(col=src.get("col", ""), prefix=src.get("prefix", ""))

    def get_data(self) -> dict[str, Any]:
        sources: list[dict[str, str]] = []
        for i in range(self._sources_list.count()):
            item = self._sources_list.item(i)
            widget = self._sources_list.itemWidget(item)
            if isinstance(widget, _ConcatSourceWidget):
                col, prefix = widget.get_data()
                if col:
                    sources.append({"col": col, "prefix": prefix})
        return {
            "separator": self._separator_edit.text(),
            "skip_empty": self._skip_empty_cb.isChecked(),
            "deduplicate": self._dedupe_cb.isChecked(),
            "sources": sources,
        }


class TemplateBuilderScreen(QWidget):
    PREVIEW_ROWS = 200

    def __init__(self, state: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._template_df_raw = None
        self._source_df = None
        self._zones: list[dict[str, Any]] = list(getattr(self._state, "template_builder_config", {}).get("zones", []))
        self._editing_zone_index: int | None = None
        self._current_mapping_cols: list[int] = []
        self._worker: TemplateBuilderWorker | None = None
        self._preview_frames: dict[str, Any] = {}
        self._preview_cache_key: str | None = None
        self._preview_cache_frames: dict[str, Any] = {}
        self._setup_ui()

    def refresh_from_state(self) -> None:
        config = getattr(self._state, "template_builder_config", {})
        self._zones = list(config.get("zones", []))
        if hasattr(self, "_multi_zone_rb") and len(self._zones) > 1:
            self._multi_zone_rb.setChecked(True)
        elif hasattr(self, "_single_zone_rb"):
            self._single_zone_rb.setChecked(True)
        self._refresh_zone_lists()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._step_names = ["Import", "Zones", "Mapping", "Agrégation", "Export"]
        stepper_row = QHBoxLayout()
        self._stepper_labels: list[QLabel] = []
        for i, name in enumerate(self._step_names):
            label = QLabel(name)
            self._stepper_labels.append(label)
            stepper_row.addWidget(label)
            if i < len(self._step_names) - 1:
                stepper_row.addWidget(QLabel("→"))
        stepper_row.addStretch()
        layout.addLayout(stepper_row)
        self._step_title = QLabel("Étape 1 — Import")
        layout.addWidget(self._step_title)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_import_page())
        self._stack.addWidget(self._build_zones_page())
        self._stack.addWidget(self._build_mapping_page())
        self._stack.addWidget(self._build_aggregation_page())
        self._stack.addWidget(self._build_export_page())
        layout.addWidget(self._stack)

        nav = QHBoxLayout()
        self._restart_btn = QPushButton("Recommencer")
        self._restart_btn.clicked.connect(self._restart_flow)
        self._back_btn = QPushButton("Retour")
        self._back_btn.clicked.connect(self._prev_step)
        self._next_btn = QPushButton("Suivant")
        self._next_btn.clicked.connect(self._next_step)
        nav.addWidget(self._restart_btn)
        nav.addWidget(self._back_btn)
        nav.addStretch()
        nav.addWidget(self._next_btn)
        layout.addLayout(nav)

        self._update_step_controls()

    def _build_import_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        group = QGroupBox("Import")
        form = QFormLayout()

        self._template_file_edit = QLineEdit()
        self._template_browse = QPushButton("Parcourir")
        self._template_browse.clicked.connect(self._browse_template)
        row = QHBoxLayout()
        row.addWidget(self._template_file_edit)
        row.addWidget(self._template_browse)
        form.addRow("Template:", row)

        self._template_sheet_combo = QComboBox()
        form.addRow("Feuille template:", self._template_sheet_combo)

        self._source_file_edit = QLineEdit()
        self._source_browse = QPushButton("Parcourir")
        self._source_browse.clicked.connect(self._browse_source)
        row2 = QHBoxLayout()
        row2.addWidget(self._source_file_edit)
        row2.addWidget(self._source_browse)
        form.addRow("Source:", row2)

        self._source_sheet_combo = QComboBox()
        form.addRow("Feuille source:", self._source_sheet_combo)
        self._source_header_spin = QSpinBox()
        self._source_header_spin.setRange(1, 10000)
        self._source_header_spin.setValue(1)
        form.addRow("Ligne d'en-tête source:", self._source_header_spin)

        group.setLayout(form)
        layout.addWidget(group)

        cfg_group = QGroupBox("Configuration")
        cfg_layout = QHBoxLayout()
        self._portable_cfg_cb = QCheckBox("Sans chemins (portable)")
        self._portable_cfg_cb.setToolTip("Enregistre la config sans chemins de fichiers.")
        self._load_cfg_btn = QPushButton("Charger config")
        self._load_cfg_btn.clicked.connect(self._load_config)
        self._save_cfg_btn = QPushButton("Enregistrer config")
        self._save_cfg_btn.clicked.connect(self._save_config)
        cfg_layout.addWidget(self._load_cfg_btn)
        cfg_layout.addWidget(self._save_cfg_btn)
        cfg_layout.addWidget(self._portable_cfg_cb)
        cfg_layout.addStretch()
        cfg_group.setLayout(cfg_layout)
        layout.addWidget(cfg_group)

        self._load_preview_btn = QPushButton("Charger aperçus")
        self._load_preview_btn.clicked.connect(self._load_previews)
        layout.addWidget(self._load_preview_btn)

        preview_group = QGroupBox("Aperçus")
        preview_layout = QVBoxLayout()
        self._template_label = QLabel("Template: —")
        self._template_table = QTableView()
        self._template_table.setModel(DataFrameModel())
        self._template_table.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self._template_label)
        preview_layout.addWidget(self._template_table)

        self._source_label = QLabel("Source: —")
        self._source_table = QTableView()
        self._source_table.setModel(DataFrameModel())
        self._source_table.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self._source_label)
        preview_layout.addWidget(self._source_table)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        layout.addStretch()
        return page

    def _build_zones_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)

        mode_row = QHBoxLayout()
        self._single_zone_rb = QRadioButton("Une seule zone")
        self._multi_zone_rb = QRadioButton("Plusieurs zones")
        self._single_zone_rb.setChecked(True)
        self._single_zone_rb.toggled.connect(self._on_zone_mode_changed)
        mode_row.addWidget(self._single_zone_rb)
        mode_row.addWidget(self._multi_zone_rb)
        mode_row.addStretch()
        outer.addLayout(mode_row)

        layout = QHBoxLayout()
        outer.addLayout(layout)

        left = QVBoxLayout()
        self._zones_list = QListWidget()
        self._zones_list.currentRowChanged.connect(self._load_zone_into_form)
        left.addWidget(QLabel("Zones"))
        left.addWidget(self._zones_list)
        add_btn = QPushButton("Ajouter zone")
        add_btn.clicked.connect(self._new_zone)
        remove_btn = QPushButton("Supprimer zone")
        remove_btn.clicked.connect(self._remove_zone)
        left.addWidget(add_btn)
        left.addWidget(remove_btn)
        left.addStretch()
        self._zones_panel = QWidget()
        self._zones_panel.setLayout(left)

        right = QVBoxLayout()
        form_group = QGroupBox("Définition de zone")
        form = QFormLayout()

        self._zone_name_edit = QLineEdit()
        form.addRow("Nom:", self._zone_name_edit)

        self._row_start_spin = QSpinBox()
        self._row_start_spin.setRange(1, 1000000)
        self._row_end_spin = QSpinBox()
        self._row_end_spin.setRange(1, 1000000)
        self._row_end_auto = QCheckBox("Auto-fin")
        self._row_end_auto.setChecked(True)
        self._row_end_auto.toggled.connect(lambda v: self._row_end_spin.setEnabled(not v))
        row_end_row = QHBoxLayout()
        row_end_row.addWidget(self._row_end_spin)
        row_end_row.addWidget(self._row_end_auto)
        form.addRow("Ligne début:", self._row_start_spin)
        form.addRow("Ligne fin:", row_end_row)

        self._col_start_spin = QSpinBox()
        self._col_start_spin.setRange(1, 1000000)
        self._col_end_spin = QSpinBox()
        self._col_end_spin.setRange(1, 1000000)
        self._col_end_auto = QCheckBox("Auto-fin")
        self._col_end_auto.setChecked(True)
        self._col_end_auto.toggled.connect(lambda v: self._col_end_spin.setEnabled(not v))
        col_end_row = QHBoxLayout()
        col_end_row.addWidget(self._col_end_spin)
        col_end_row.addWidget(self._col_end_auto)
        form.addRow("Colonne début:", self._col_start_spin)
        form.addRow("Colonne fin:", col_end_row)

        form.addRow(QLabel("Lignes à définir"))

        self._title_rows_cb = QCheckBox("Titres (template)")
        self._title_rows_edit = QLineEdit()
        self._title_rows_edit.setPlaceholderText("Ex: 1,2")
        self._title_rows_cb.toggled.connect(lambda v: self._title_rows_edit.setEnabled(v))
        title_row = QHBoxLayout()
        title_row.addWidget(self._title_rows_cb)
        title_row.addWidget(self._title_rows_edit, 1)
        form.addRow("", title_row)

        self._label_rows_cb = QCheckBox("Labels")
        self._label_rows_edit = QLineEdit()
        self._label_rows_edit.setPlaceholderText("Ex: 3")
        self._label_rows_cb.toggled.connect(lambda v: self._label_rows_edit.setEnabled(v))
        label_row = QHBoxLayout()
        label_row.addWidget(self._label_rows_cb)
        label_row.addWidget(self._label_rows_edit, 1)
        form.addRow("", label_row)

        self._tech_row_cb = QCheckBox("Champs cible")
        self._tech_row_cb.setChecked(True)
        self._tech_row_cb.setEnabled(False)
        self._tech_row_spin = QSpinBox()
        self._tech_row_spin.setRange(1, 1000000)
        self._detect_term_edit = QLineEdit()
        self._detect_term_edit.setPlaceholderText("Terme exact")
        self._detect_btn = QPushButton("Trouver ligne…")
        self._detect_btn.clicked.connect(self._auto_detect_tech_row)
        tech_row = QHBoxLayout()
        tech_row.addWidget(self._tech_row_cb)
        tech_row.addWidget(self._tech_row_spin)
        tech_row.addWidget(self._detect_term_edit, 2)
        tech_row.addWidget(self._detect_btn)
        form.addRow("", tech_row)

        self._prefix_row_cb = QCheckBox("Préfixes")
        self._prefix_row_spin = QSpinBox()
        self._prefix_row_spin.setRange(1, 1000000)
        self._prefix_row_cb.toggled.connect(lambda v: self._prefix_row_spin.setEnabled(v))
        prefix_row = QHBoxLayout()
        prefix_row.addWidget(self._prefix_row_cb)
        prefix_row.addWidget(self._prefix_row_spin)
        form.addRow("", prefix_row)

        self._data_start_spin = QSpinBox()
        self._data_start_spin.setRange(1, 1000000)
        self._data_start_auto = QCheckBox("Auto (après en-têtes)")
        self._data_start_auto.setChecked(True)
        self._data_start_auto.toggled.connect(lambda v: self._data_start_spin.setEnabled(not v))
        data_start_row = QHBoxLayout()
        data_start_row.addWidget(self._data_start_spin)
        data_start_row.addWidget(self._data_start_auto)
        form.addRow("Début données:", data_start_row)

        self._title_rows_cb.setChecked(False)
        self._title_rows_edit.setEnabled(False)
        self._label_rows_cb.setChecked(False)
        self._label_rows_edit.setEnabled(False)
        self._prefix_row_cb.setChecked(False)
        self._prefix_row_spin.setEnabled(False)

        form_group.setLayout(form)
        right.addWidget(form_group)

        preview_group = QGroupBox("Aperçu template (sélection)")
        preview_layout = QVBoxLayout()
        self._zone_preview_table = QTableView()
        self._zone_preview_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self._zone_preview_table.setModel(DataFrameModel())
        preview_layout.addWidget(self._zone_preview_table)
        select_btn = QPushButton("Utiliser la sélection")
        select_btn.clicked.connect(self._use_selection_for_zone)
        preview_layout.addWidget(select_btn)
        preview_group.setLayout(preview_layout)
        right.addWidget(preview_group)

        save_btn = QPushButton("Enregistrer la zone")
        save_btn.clicked.connect(self._save_zone)
        right.addWidget(save_btn)
        right.addStretch()

        layout.addWidget(self._zones_panel, 1)
        layout.addLayout(right, 3)
        self._zones_panel.setVisible(False)
        return page

    def _build_mapping_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)

        left = QVBoxLayout()
        self._mapping_zone_list = QListWidget()
        self._mapping_zone_list.currentRowChanged.connect(self._load_zone_mapping)
        left.addWidget(QLabel("Zones"))
        left.addWidget(self._mapping_zone_list)
        left.addStretch()

        right = QVBoxLayout()
        self._mapping_table = QTableWidget()
        self._mapping_table.setColumnCount(6)
        self._mapping_table.setHorizontalHeaderLabels(
            ["Col", "Label", "Mode", "Source", "Concat", "Résumé"]
        )
        self._mapping_table.horizontalHeader().setStretchLastSection(True)
        right.addWidget(self._mapping_table)
        right.addStretch()

        layout.addLayout(left, 1)
        layout.addLayout(right, 3)
        return page

    def _build_aggregation_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)

        left = QVBoxLayout()
        self._agg_zone_list = QListWidget()
        self._agg_zone_list.currentRowChanged.connect(self._load_zone_aggregation)
        left.addWidget(QLabel("Zones"))
        left.addWidget(self._agg_zone_list)
        left.addStretch()

        right = QVBoxLayout()
        group = QGroupBox("Agrégation")
        form = QFormLayout()
        self._agg_cb = QCheckBox("Agréger plusieurs lignes")
        self._agg_group_by = QComboBox()
        self._agg_cb.stateChanged.connect(self._apply_aggregation_current)
        self._agg_group_by.currentTextChanged.connect(self._apply_aggregation_current)
        form.addRow("", self._agg_cb)
        form.addRow("ID (group_by):", self._agg_group_by)
        group.setLayout(form)
        right.addWidget(group)
        right.addStretch()

        layout.addLayout(left, 1)
        layout.addLayout(right, 3)
        return page

    def _build_export_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        group = QGroupBox("Export")
        form = QFormLayout()
        self._output_mode_combo = QComboBox()
        self._output_mode_combo.addItems(["single", "multi"])
        self._output_sheet_edit = QLineEdit("Output")
        form.addRow("Mode:", self._output_mode_combo)
        form.addRow("Nom feuille (mode single):", self._output_sheet_edit)

        self._out_xlsx_edit = QLineEdit()
        browse_out = QPushButton("Parcourir")
        browse_out.clicked.connect(self._browse_output)
        out_row = QHBoxLayout()
        out_row.addWidget(self._out_xlsx_edit)
        out_row.addWidget(browse_out)
        form.addRow("Fichier xlsx/ods:", out_row)
        group.setLayout(form)
        layout.addWidget(group)

        self._export_btn = QPushButton("Exporter")
        self._export_btn.clicked.connect(self._export)
        layout.addWidget(self._export_btn)

        self._export_status = QLabel("")
        layout.addWidget(self._export_status)

        preview_group = QGroupBox("Prévisualisation")
        preview_layout = QVBoxLayout()
        preview_controls = QHBoxLayout()
        preview_controls.addWidget(QLabel("Zone:"))
        self._preview_zone_combo = QComboBox()
        preview_controls.addWidget(self._preview_zone_combo, 1)
        preview_controls.addWidget(QLabel("Feuille:"))
        self._preview_sheet_combo = QComboBox()
        self._preview_sheet_combo.currentTextChanged.connect(self._on_preview_sheet_changed)
        preview_controls.addWidget(self._preview_sheet_combo, 1)
        self._preview_current_zone_btn = QPushButton("Zone courante")
        self._preview_current_zone_btn.clicked.connect(self._preview_current_zone)
        preview_controls.addWidget(self._preview_current_zone_btn)
        self._preview_btn = QPushButton("Prévisualiser")
        self._preview_btn.clicked.connect(self._preview_output)
        preview_controls.addWidget(self._preview_btn)
        preview_layout.addLayout(preview_controls)
        preview_opts = QHBoxLayout()
        self._preview_header_only_cb = QCheckBox("En-têtes seulement")
        self._preview_header_only_cb.toggled.connect(
            lambda v: self._preview_data_rows_spin.setEnabled(not v)
        )
        self._preview_data_rows_spin = QSpinBox()
        self._preview_data_rows_spin.setRange(1, 1000000)
        self._preview_data_rows_spin.setValue(50)
        preview_opts.addWidget(self._preview_header_only_cb)
        preview_opts.addWidget(QLabel("Lignes de données:"))
        preview_opts.addWidget(self._preview_data_rows_spin)
        preview_opts.addStretch()
        preview_layout.addLayout(preview_opts)
        self._preview_label = QLabel("")
        preview_layout.addWidget(self._preview_label)
        self._preview_cache_label = QLabel("")
        self._preview_cache_label.setObjectName("previewCacheBadge")
        self._preview_cache_label.setStyleSheet(
            "QLabel#previewCacheBadge {"
            "background: #eef2f7;"
            "color: #394150;"
            "border: 1px solid #d5dbe3;"
            "border-radius: 8px;"
            "padding: 2px 8px;"
            "font-size: 11px;"
            "}"
        )
        preview_layout.addWidget(self._preview_cache_label)
        self._preview_table = QTableView()
        self._preview_table.setModel(DataFrameModel())
        self._preview_table.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self._preview_table)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        layout.addStretch()
        return page

    def _update_step_controls(self) -> None:
        idx = self._stack.currentIndex()
        self._back_btn.setEnabled(idx > 0)
        is_last = idx >= self._stack.count() - 1
        self._next_btn.setEnabled(not is_last)
        self._next_btn.setVisible(not is_last)
        if 0 <= idx < len(self._step_names):
            self._step_title.setText(f"Étape {idx + 1} — {self._step_names[idx]}")
            for i, label in enumerate(self._stepper_labels):
                if i == idx:
                    label.setStyleSheet("font-weight: 600; color: #111;")
                elif i < idx:
                    label.setStyleSheet("color: #444;")
                else:
                    label.setStyleSheet("color: #888;")

    def _next_step(self) -> None:
        idx = self._stack.currentIndex()
        if not self._validate_step(idx):
            return
        if idx < self._stack.count() - 1:
            self._stack.setCurrentIndex(idx + 1)
            self._update_step_controls()

    def _prev_step(self) -> None:
        idx = self._stack.currentIndex()
        if idx > 0:
            self._stack.setCurrentIndex(idx - 1)
            self._update_step_controls()

    def _validate_step(self, idx: int) -> bool:
        if idx == 0:
            if not self._template_file_edit.text().strip() or not self._source_file_edit.text().strip():
                QMessageBox.warning(self, "Attention", "Sélectionnez un template et une source.")
                return False
            if self._template_df_raw is None or self._source_df is None:
                self._load_previews()
            return True
        if idx == 1:
            if not self._zones:
                QMessageBox.warning(self, "Attention", "Définissez au moins une zone.")
                return False
            self._refresh_zone_lists()
        return True

    def _browse_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Sélectionner template", "", SUPPORTED_INPUT_FILTER)
        if path:
            self._template_file_edit.setText(path)
            self._update_sheet_combo(self._template_sheet_combo, path)

    def _browse_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Sélectionner source", "", SUPPORTED_INPUT_FILTER)
        if path:
            self._source_file_edit.setText(path)
            self._update_sheet_combo(self._source_sheet_combo, path)

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Fichier de sortie", "", "Excel/ODS (*.xlsx *.ods)"
        )
        if path:
            self._out_xlsx_edit.setText(path)

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
            template_path = self._template_file_edit.text().strip()
            source_path = self._source_file_edit.text().strip()
            if not template_path or not source_path:
                QMessageBox.warning(self, "Attention", "Sélectionnez un template et une source.")
                return
            template_sheet = self._template_sheet_combo.currentText() or None
            source_sheet = self._source_sheet_combo.currentText() or None
            src_header = self._source_header_spin.value()

            self._template_df_raw = load_sheet_raw(template_path, template_sheet)
            self._source_df = load_sheet(source_path, source_sheet, header_row=src_header)

            self._template_table.model().set_dataframe(self._template_df_raw.head(self.PREVIEW_ROWS))
            self._zone_preview_table.model().set_dataframe(self._template_df_raw.head(self.PREVIEW_ROWS))
            self._template_label.setText(
                f"Template: {self._template_df_raw.shape[0]} lignes × {self._template_df_raw.shape[1]} colonnes"
            )
            self._source_table.model().set_dataframe(self._source_df.head(self.PREVIEW_ROWS))
            self._source_label.setText(
                f"Source: {self._source_df.shape[0]} lignes × {self._source_df.shape[1]} colonnes"
            )

            self._agg_group_by.clear()
            self._agg_group_by.addItems(list(self._source_df.columns))
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    def _collect_config_dict(self, *, zones_override: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {
            "template_file": self._template_file_edit.text().strip(),
            "template_sheet": self._template_sheet_combo.currentText() or None,
            "source_file": self._source_file_edit.text().strip(),
            "source_sheet": self._source_sheet_combo.currentText() or None,
            "source_header_row": self._source_header_spin.value(),
            "zones": zones_override if zones_override is not None else self._zones,
            "output_mode": self._output_mode_combo.currentText(),
            "output_sheet_name": self._output_sheet_edit.text().strip() or "Output",
        }

    def _save_config(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer configuration", "", "JSON (*.json)")
        if not path:
            return
        if not path.endswith(".json"):
            path += ".json"
        config_dict = self._collect_config_dict()
        if self._portable_cfg_cb.isChecked():
            config_dict["template_file"] = ""
            config_dict["source_file"] = ""
            config_dict["portable"] = True
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Config", f"Configuration enregistrée:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'enregistrer: {e}")

    def _load_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Charger configuration", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de lire la config: {e}")
            return

        template_file = str(data.get("template_file", ""))
        source_file = str(data.get("source_file", ""))
        self._template_file_edit.setText(template_file)
        self._source_file_edit.setText(source_file)
        self._source_header_spin.setValue(int(data.get("source_header_row", 1)))
        portable = bool(data.get("portable")) or (not template_file and not source_file)
        self._portable_cfg_cb.setChecked(portable)

        if template_file:
            sheets = self._update_sheet_combo(self._template_sheet_combo, template_file)
            tpl_sheet = data.get("template_sheet")
            if tpl_sheet in sheets:
                self._template_sheet_combo.setCurrentText(tpl_sheet)

        if source_file:
            sheets = self._update_sheet_combo(self._source_sheet_combo, source_file)
            src_sheet = data.get("source_sheet")
            if src_sheet in sheets:
                self._source_sheet_combo.setCurrentText(src_sheet)

        self._output_mode_combo.setCurrentText(str(data.get("output_mode", "single")))
        self._output_sheet_edit.setText(str(data.get("output_sheet_name", "Output")))

        self._zones = list(data.get("zones", []))
        self._state.template_builder_config = data
        self._invalidate_preview_cache()
        self._refresh_zone_lists()

        if template_file and source_file:
            self._load_previews()
        QMessageBox.information(self, "Config", f"Configuration chargée:\n{path}")

    def _refresh_zone_lists(self, select_index: int | None = None) -> None:
        current_idx = self._zones_list.currentRow()
        self._zones_list.clear()
        self._mapping_zone_list.clear()
        self._agg_zone_list.clear()
        for zone in self._zones:
            name = zone.get("name") or "Zone"
            self._zones_list.addItem(name)
            self._mapping_zone_list.addItem(name)
            self._agg_zone_list.addItem(name)
        if self._zones:
            idx = current_idx if select_index is None else select_index
            if idx < 0 or idx >= len(self._zones):
                idx = 0
            self._zones_list.setCurrentRow(idx)
            self._mapping_zone_list.setCurrentRow(idx)
            self._agg_zone_list.setCurrentRow(idx)
        self._refresh_preview_zone_combo()

    def _on_zone_mode_changed(self) -> None:
        if self._single_zone_rb.isChecked():
            self._set_zone_mode("single")
        else:
            self._set_zone_mode("multi")

    def _set_zone_mode(self, mode: str) -> None:
        if mode == "single":
            if len(self._zones) > 1:
                reply = QMessageBox.question(
                    self,
                    "Zone unique",
                    "Passer en zone unique supprimera les zones supplémentaires. Continuer ?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    self._multi_zone_rb.setChecked(True)
                    return
                self._zones = [self._zones[0]]
            if not self._zones:
                self._new_zone()
            self._zones_panel.setVisible(False)
            self._refresh_zone_lists(select_index=0)
        else:
            self._zones_panel.setVisible(True)
            if not self._zones:
                self._new_zone()
            self._refresh_zone_lists(select_index=0)

    def _refresh_preview_zone_combo(self) -> None:
        if not hasattr(self, "_preview_zone_combo"):
            return
        current_data = self._preview_zone_combo.currentData()
        self._preview_zone_combo.blockSignals(True)
        self._preview_zone_combo.clear()
        self._preview_zone_combo.addItem("Toutes", None)
        for idx, zone in enumerate(self._zones):
            name = zone.get("name") or f"Zone {idx + 1}"
            self._preview_zone_combo.addItem(name, idx)
        if current_data is not None and 0 <= int(current_data) < len(self._zones):
            self._preview_zone_combo.setCurrentIndex(int(current_data) + 1)
        self._preview_zone_combo.blockSignals(False)

    def _new_zone(self) -> None:
        self._editing_zone_index = None
        self._zone_name_edit.setText(f"Zone {len(self._zones) + 1}")
        self._row_start_spin.setValue(1)
        self._row_end_spin.setValue(1)
        self._row_end_auto.setChecked(True)
        self._col_start_spin.setValue(1)
        self._col_end_spin.setValue(1)
        self._col_end_auto.setChecked(True)
        self._title_rows_edit.setText("")
        self._label_rows_edit.setText("")
        self._tech_row_spin.setValue(1)
        self._prefix_row_spin.setValue(1)
        self._title_rows_cb.setChecked(False)
        self._label_rows_cb.setChecked(False)
        self._prefix_row_cb.setChecked(False)
        self._data_start_spin.setValue(1)
        self._data_start_auto.setChecked(True)
        # Ajouter une zone par défaut pour la rendre visible immédiatement
        zone = self._collect_zone_form()
        if zone is None:
            return
        self._zones.append(zone)
        self._editing_zone_index = len(self._zones) - 1
        self._invalidate_preview_cache()
        self._refresh_zone_lists(select_index=self._editing_zone_index)

    def _remove_zone(self) -> None:
        row = self._zones_list.currentRow()
        if row < 0:
            return
        del self._zones[row]
        self._invalidate_preview_cache()
        self._refresh_zone_lists()

    def _clear_zone_form_defaults(self) -> None:
        self._zone_name_edit.setText("")
        self._row_start_spin.setValue(1)
        self._row_end_spin.setValue(1)
        self._row_end_auto.setChecked(True)
        self._col_start_spin.setValue(1)
        self._col_end_spin.setValue(1)
        self._col_end_auto.setChecked(True)
        self._title_rows_edit.setText("")
        self._label_rows_edit.setText("")
        self._tech_row_spin.setValue(1)
        self._prefix_row_spin.setValue(1)
        self._title_rows_cb.setChecked(False)
        self._label_rows_cb.setChecked(False)
        self._prefix_row_cb.setChecked(False)
        self._data_start_spin.setValue(1)
        self._data_start_auto.setChecked(True)

    def _collect_zone_form(self) -> dict[str, Any] | None:
        name = self._zone_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Attention", "Nom de zone requis.")
            return None
        row_start = self._row_start_spin.value()
        row_end = None if self._row_end_auto.isChecked() else self._row_end_spin.value()
        col_start = self._col_start_spin.value()
        col_end = None if self._col_end_auto.isChecked() else self._col_end_spin.value()
        title_rows = _parse_int_list(self._title_rows_edit.text()) if self._title_rows_cb.isChecked() else []
        label_rows = _parse_int_list(self._label_rows_edit.text()) if self._label_rows_cb.isChecked() else []
        tech_row = self._tech_row_spin.value()
        prefix_row = self._prefix_row_spin.value() if self._prefix_row_cb.isChecked() else None
        data_start = None if self._data_start_auto.isChecked() else self._data_start_spin.value()
        existing = self._zones[self._editing_zone_index] if self._editing_zone_index is not None else {}
        aggregate = bool(existing.get("aggregate", False))
        group_by = existing.get("group_by")
        return {
            "name": name,
            "row_start": row_start,
            "row_end": row_end,
            "col_start": col_start,
            "col_end": col_end,
            "data_start_row": data_start,
            "aggregate": aggregate,
            "group_by": group_by,
            "header": {
                "title_rows": title_rows,
                "label_rows": label_rows,
                "tech_row": tech_row,
                "prefix_row": prefix_row,
            },
            "field_mappings": self._get_current_zone_mappings(),
        }

    def _save_zone(self) -> None:
        zone = self._collect_zone_form()
        if zone is None:
            return
        is_single = hasattr(self, "_single_zone_rb") and self._single_zone_rb.isChecked()
        if is_single:
            if self._zones:
                self._zones[0] = zone
            else:
                self._zones.append(zone)
            self._editing_zone_index = 0
        else:
            if self._editing_zone_index is None:
                self._zones.append(zone)
                self._editing_zone_index = len(self._zones) - 1
            else:
                self._zones[self._editing_zone_index] = zone
        self._invalidate_preview_cache()
        self._refresh_zone_lists(select_index=self._editing_zone_index)

    def _load_zone_into_form(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._zones):
            return
        zone = self._zones[idx]
        self._editing_zone_index = idx
        self._zone_name_edit.setText(zone.get("name", ""))
        self._row_start_spin.setValue(int(zone.get("row_start", 1)))
        row_end = zone.get("row_end")
        if row_end is None:
            self._row_end_auto.setChecked(True)
        else:
            self._row_end_auto.setChecked(False)
            self._row_end_spin.setValue(int(row_end))
        self._col_start_spin.setValue(int(zone.get("col_start", 1)))
        col_end = zone.get("col_end")
        if col_end is None:
            self._col_end_auto.setChecked(True)
        else:
            self._col_end_auto.setChecked(False)
            self._col_end_spin.setValue(int(col_end))
        header = zone.get("header", {})
        title_rows = header.get("title_rows", [])
        label_rows = header.get("label_rows", [])
        self._title_rows_cb.setChecked(bool(title_rows))
        self._title_rows_edit.setEnabled(bool(title_rows))
        self._title_rows_edit.setText(_format_int_list(title_rows))
        self._label_rows_cb.setChecked(bool(label_rows))
        self._label_rows_edit.setEnabled(bool(label_rows))
        self._label_rows_edit.setText(_format_int_list(label_rows))
        self._tech_row_spin.setValue(int(header.get("tech_row", 1)))
        prefix_row = header.get("prefix_row")
        if prefix_row is None:
            self._prefix_row_cb.setChecked(False)
            self._prefix_row_spin.setEnabled(False)
        else:
            self._prefix_row_cb.setChecked(True)
            self._prefix_row_spin.setEnabled(True)
            self._prefix_row_spin.setValue(int(prefix_row))
        data_start = zone.get("data_start_row")
        if data_start is None:
            self._data_start_auto.setChecked(True)
        else:
            self._data_start_auto.setChecked(False)
            self._data_start_spin.setValue(int(data_start))

    def _use_selection_for_zone(self) -> None:
        sel = self._zone_preview_table.selectionModel().selectedIndexes()
        if not sel:
            QMessageBox.warning(self, "Attention", "Sélectionnez une plage dans l'aperçu.")
            return
        rows = [i.row() for i in sel]
        cols = [i.column() for i in sel]
        self._row_start_spin.setValue(min(rows) + 1)
        self._row_end_auto.setChecked(False)
        self._row_end_spin.setValue(max(rows) + 1)
        self._col_start_spin.setValue(min(cols) + 1)
        self._col_end_auto.setChecked(False)
        self._col_end_spin.setValue(max(cols) + 1)

    def _auto_detect_tech_row(self) -> None:
        term = self._detect_term_edit.text().strip()
        if not term:
            QMessageBox.warning(self, "Attention", "Indiquez un terme exact à rechercher.")
            return
        if self._template_df_raw is None:
            QMessageBox.warning(self, "Attention", "Chargez un template.")
            return
        df = self._template_df_raw
        row_start = self._row_start_spin.value() - 1
        row_end = (self._row_end_spin.value() - 1) if not self._row_end_auto.isChecked() else len(df) - 1
        col_start = self._col_start_spin.value() - 1
        col_end = (self._col_end_spin.value() - 1) if not self._col_end_auto.isChecked() else df.shape[1] - 1
        for r in range(row_start, min(row_end + 1, len(df))):
            row_vals = df.iloc[r, col_start : col_end + 1].tolist()
            for v in row_vals:
                if v is None:
                    continue
                if str(v).strip() == term:
                    self._tech_row_spin.setValue(r + 1)
                    return
        QMessageBox.information(self, "Info", "Aucun terme trouvé dans la zone.")

    def _load_zone_mapping(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._zones):
            self._mapping_table.setRowCount(0)
            return
        zone = self._zones[idx]
        targets = self._get_zone_target_columns(zone)
        self._current_mapping_cols = [t["col_index"] for t in targets]
        self._mapping_table.setRowCount(len(targets))
        source_cols = list(self._source_df.columns) if self._source_df is not None else []
        mapping_by_col = {m.get("col_index"): m for m in zone.get("field_mappings", [])}

        for row_idx, target in enumerate(targets):
            col_index = target["col_index"]
            label = target["label"]
            self._mapping_table.setItem(row_idx, 0, QTableWidgetItem(str(col_index + 1)))
            self._mapping_table.setItem(row_idx, 1, QTableWidgetItem(label))

            mode_combo = QComboBox()
            mode_combo.addItems(["ignore", "simple", "concat"])
            mapping = mapping_by_col.get(col_index)
            mode = mapping.get("mode", "ignore") if mapping else "ignore"
            mode_combo.setCurrentText(mode)
            mode_combo.currentTextChanged.connect(lambda text, r=row_idx: self._on_mode_changed(r, text))
            self._mapping_table.setCellWidget(row_idx, 2, mode_combo)

            source_combo = QComboBox()
            source_combo.addItems([""] + source_cols)
            if mapping and mapping.get("source_col"):
                source_combo.setCurrentText(mapping.get("source_col"))
            source_combo.currentTextChanged.connect(lambda text, r=row_idx: self._on_source_changed(r, text))
            self._mapping_table.setCellWidget(row_idx, 3, source_combo)

            concat_btn = QPushButton("Éditer")
            concat_btn.clicked.connect(lambda _=None, r=row_idx: self._edit_concat(r))
            self._mapping_table.setCellWidget(row_idx, 4, concat_btn)

            summary = QTableWidgetItem(self._format_concat_summary(mapping.get("concat")) if mapping else "")
            self._mapping_table.setItem(row_idx, 5, summary)

            self._apply_mapping_row_state(row_idx, mode)

        self._mapping_table.resizeColumnsToContents()

    def _apply_mapping_row_state(self, row_idx: int, mode: str) -> None:
        source_widget = self._mapping_table.cellWidget(row_idx, 3)
        concat_widget = self._mapping_table.cellWidget(row_idx, 4)
        if source_widget:
            source_widget.setEnabled(mode == "simple")
        if concat_widget:
            concat_widget.setEnabled(mode == "concat")

    def _on_mode_changed(self, row_idx: int, mode: str) -> None:
        self._apply_mapping_row_state(row_idx, mode)
        self._update_mapping_from_row(row_idx, mode_override=mode)

    def _on_source_changed(self, row_idx: int, source_col: str) -> None:
        self._update_mapping_from_row(row_idx, source_override=source_col)

    def _edit_concat(self, row_idx: int) -> None:
        zone = self._current_zone_for_mapping()
        if zone is None:
            return
        col_index = self._current_mapping_cols[row_idx]
        mapping = self._get_mapping_by_col(zone, col_index)
        preset = mapping.get("concat") if mapping else None
        source_cols = list(self._source_df.columns) if self._source_df is not None else []
        dlg = _ConcatDialog(source_cols, preset=preset, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            concat_data = dlg.get_data()
            if not concat_data.get("sources"):
                QMessageBox.warning(self, "Attention", "Ajoutez au moins une colonne source.")
                return
            self._update_mapping_from_row(row_idx, mode_override="concat", concat_override=concat_data)

    def _format_concat_summary(self, concat: dict[str, Any] | None) -> str:
        if not concat:
            return ""
        parts = []
        for src in concat.get("sources", []):
            col = src.get("col", "")
            prefix = src.get("prefix", "")
            if not col:
                continue
            parts.append(f"{prefix}{col}" if prefix else col)
        return " | ".join(parts)

    def _update_mapping_from_row(
        self,
        row_idx: int,
        *,
        mode_override: str | None = None,
        source_override: str | None = None,
        concat_override: dict[str, Any] | None = None,
    ) -> None:
        zone = self._current_zone_for_mapping()
        if zone is None:
            return
        col_index = self._current_mapping_cols[row_idx]
        mapping = self._get_mapping_by_col(zone, col_index)
        mode = mode_override or (mapping.get("mode") if mapping else "ignore")
        if mode == "ignore":
            self._remove_mapping(zone, col_index)
            self._invalidate_preview_cache()
            self._mapping_table.setItem(row_idx, 5, QTableWidgetItem(""))
            return

        if mode == "simple":
            source_col = source_override
            if source_col is None:
                source_widget = self._mapping_table.cellWidget(row_idx, 3)
                if isinstance(source_widget, QComboBox):
                    source_col = source_widget.currentText()
            data = {
                "col_index": col_index,
                "mode": "simple",
                "source_col": source_col or "",
            }
            self._set_mapping(zone, col_index, data)
            self._invalidate_preview_cache()
            self._mapping_table.setItem(row_idx, 5, QTableWidgetItem(""))
            return

        if mode == "concat":
            concat = concat_override
            if concat is None and mapping:
                concat = mapping.get("concat")
            data = {
                "col_index": col_index,
                "mode": "concat",
                "concat": concat or {},
            }
            self._set_mapping(zone, col_index, data)
            self._invalidate_preview_cache()
            self._mapping_table.setItem(row_idx, 5, QTableWidgetItem(self._format_concat_summary(concat)))

    def _get_mapping_by_col(self, zone: dict[str, Any], col_index: int) -> dict[str, Any] | None:
        for m in zone.get("field_mappings", []):
            if m.get("col_index") == col_index:
                return m
        return None

    def _set_mapping(self, zone: dict[str, Any], col_index: int, data: dict[str, Any]) -> None:
        mappings = list(zone.get("field_mappings", []))
        for i, m in enumerate(mappings):
            if m.get("col_index") == col_index:
                mappings[i] = data
                zone["field_mappings"] = mappings
                return
        mappings.append(data)
        zone["field_mappings"] = mappings

    def _remove_mapping(self, zone: dict[str, Any], col_index: int) -> None:
        mappings = [m for m in zone.get("field_mappings", []) if m.get("col_index") != col_index]
        zone["field_mappings"] = mappings

    def _current_zone_for_mapping(self) -> dict[str, Any] | None:
        idx = self._mapping_zone_list.currentRow()
        if idx < 0 or idx >= len(self._zones):
            return None
        return self._zones[idx]

    def _get_zone_target_columns(self, zone: dict[str, Any]) -> list[dict[str, Any]]:
        if self._template_df_raw is None:
            return []
        df = self._template_df_raw
        row_start = int(zone.get("row_start", 1)) - 1
        row_end = zone.get("row_end")
        row_end = (int(row_end) - 1) if row_end is not None else len(df) - 1
        col_start = int(zone.get("col_start", 1)) - 1
        col_end = zone.get("col_end")
        col_end = (int(col_end) - 1) if col_end is not None else df.shape[1] - 1
        header = zone.get("header", {})
        tech_row = int(header.get("tech_row", row_start + 1)) - 1
        tech_row = max(0, min(tech_row, len(df) - 1))
        labels = df.iloc[tech_row, col_start : col_end + 1].tolist()
        targets = []
        for idx, label in enumerate(labels):
            text = "" if label is None else str(label)
            targets.append({"col_index": idx, "label": text})
        return targets

    def _get_current_zone_mappings(self) -> list[dict[str, Any]]:
        if self._editing_zone_index is None:
            return []
        return self._zones[self._editing_zone_index].get("field_mappings", [])

    def _load_zone_aggregation(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._zones):
            return
        zone = self._zones[idx]
        self._agg_cb.setChecked(bool(zone.get("aggregate", False)))
        group_by = zone.get("group_by")
        if group_by:
            self._agg_group_by.setCurrentText(group_by)

    def _apply_aggregation_current(self, *_: object) -> None:
        idx = self._agg_zone_list.currentRow()
        if idx < 0 or idx >= len(self._zones):
            return
        zone = self._zones[idx]
        zone["aggregate"] = self._agg_cb.isChecked()
        zone["group_by"] = self._agg_group_by.currentText() or None
        self._invalidate_preview_cache()

    def _restart_flow(self) -> None:
        reply = QMessageBox.question(
            self,
            "Recommencer",
            "Cela effacera les zones et mappings actuels. Continuer ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._template_df_raw = None
        self._source_df = None
        self._zones = []
        self._editing_zone_index = None
        self._current_mapping_cols = []
        self._preview_frames = {}
        self._preview_cache_key = None
        self._preview_cache_frames = {}
        self._state.template_builder_config = {}

        self._template_file_edit.setText("")
        self._source_file_edit.setText("")
        self._template_sheet_combo.clear()
        self._source_sheet_combo.clear()
        self._source_header_spin.setValue(1)
        self._output_mode_combo.setCurrentText("single")
        self._output_sheet_edit.setText("Output")
        self._out_xlsx_edit.setText("")
        if hasattr(self, "_single_zone_rb"):
            self._single_zone_rb.setChecked(True)

        self._template_table.model().set_dataframe(pd.DataFrame())
        self._source_table.model().set_dataframe(pd.DataFrame())
        self._template_label.setText("Template: —")
        self._source_label.setText("Source: —")
        self._mapping_table.setRowCount(0)

        self._clear_zone_form_defaults()
        self._invalidate_preview_cache()
        self._refresh_zone_lists()
        self._stack.setCurrentIndex(0)
        self._update_step_controls()

    def _export(self) -> None:
        out_path = self._out_xlsx_edit.text().strip()
        if not out_path:
            QMessageBox.warning(self, "Attention", "Indiquez un fichier de sortie.")
            return
        if not out_path.lower().endswith((".xlsx", ".ods")):
            out_path += ".xlsx"
        config_dict = self._collect_config_dict()
        self._state.template_builder_config = config_dict
        self._export_status.setText("Export en cours...")
        self._export_btn.setEnabled(False)

        self._worker = TemplateBuilderWorker(config_dict, out_path, self)
        self._worker.finished.connect(self._on_export_finished)
        self._worker.error.connect(self._on_export_error)
        self._worker.start()

    def _on_export_finished(self, out_path: str) -> None:
        self._export_btn.setEnabled(True)
        self._export_status.setText(f"Export terminé: {out_path}")
        QMessageBox.information(self, "Export", f"Export réussi:\n{out_path}")

    def _on_export_error(self, msg: str) -> None:
        self._export_btn.setEnabled(True)
        self._export_status.setText(f"Erreur: {msg}")
        QMessageBox.critical(self, "Erreur export", msg)

    def _preview_output(self) -> None:
        self._refresh_preview_zone_combo()
        zone_idx = self._preview_zone_combo.currentData()
        zones = self._zones
        if zone_idx is not None and 0 <= int(zone_idx) < len(self._zones):
            zones = [self._zones[int(zone_idx)]]
        config_dict = self._collect_config_dict(zones_override=zones)
        config_dict["output_mode"] = "multi"
        self._state.template_builder_config = config_dict
        try:
            cache_key = self._make_preview_cache_key(config_dict)
            if cache_key == self._preview_cache_key and self._preview_cache_frames:
                self._preview_frames = self._preview_cache_frames
                self._preview_cache_label.setText("Cache: réutilisé")
            else:
                config = TemplateBuilderConfig.from_dict(config_dict)
                frames = build_output(config, max_source_rows=self.PREVIEW_ROWS)
                self._preview_frames = self._apply_preview_limits(frames, zones)
                self._preview_cache_key = cache_key
                self._preview_cache_frames = self._preview_frames
                self._preview_cache_label.setText("Cache: rafraîchi")
            self._preview_sheet_combo.blockSignals(True)
            self._preview_sheet_combo.clear()
            self._preview_sheet_combo.addItems(list(self._preview_frames.keys()))
            self._preview_sheet_combo.blockSignals(False)
            if self._preview_frames:
                first_sheet = self._preview_sheet_combo.currentText() or list(self._preview_frames.keys())[0]
                self._show_preview_sheet(first_sheet)
        except Exception as e:
            self._preview_cache_label.setText("")
            QMessageBox.critical(self, "Erreur preview", str(e))

    def _preview_current_zone(self) -> None:
        idx = -1
        if self._mapping_zone_list.currentRow() >= 0:
            idx = self._mapping_zone_list.currentRow()
        elif self._zones_list.currentRow() >= 0:
            idx = self._zones_list.currentRow()
        if idx < 0 or idx >= len(self._zones):
            QMessageBox.warning(self, "Attention", "Aucune zone sélectionnée.")
            return
        self._preview_zone_combo.setCurrentIndex(idx + 1)
        self._preview_output()

    def _on_preview_sheet_changed(self, sheet: str) -> None:
        if not sheet:
            return
        self._show_preview_sheet(sheet)

    def _show_preview_sheet(self, sheet: str) -> None:
        df = self._preview_frames.get(sheet)
        if df is None:
            return
        preview_df = df.head(self.PREVIEW_ROWS)
        self._preview_table.model().set_dataframe(preview_df)
        self._preview_label.setText(
            f"{sheet}: {df.shape[0]} lignes × {df.shape[1]} colonnes"
        )

    def _apply_preview_limits(
        self,
        frames: dict[str, Any],
        zones: list[dict[str, Any]],
    ) -> dict[str, Any]:
        header_only = self._preview_header_only_cb.isChecked()
        data_rows = self._preview_data_rows_spin.value()
        trimmed: dict[str, Any] = {}
        for idx, zone in enumerate(zones):
            name = (zone.get("name") or "").strip() or f"Zone {idx + 1}"
            df = frames.get(name)
            if df is None:
                continue
            header_rows = self._calc_header_rows(zone)
            if header_only:
                trimmed[name] = df.iloc[:header_rows, :].copy()
            else:
                trimmed[name] = df.iloc[: header_rows + data_rows, :].copy()

        if not trimmed:
            return frames

        if self._output_mode_combo.currentText() == "single" and len(trimmed) > 1:
            stacked = pd.concat(list(trimmed.values()), ignore_index=True)
            sheet_name = self._output_sheet_edit.text().strip() or "Output"
            return {sheet_name: stacked}
        return trimmed

    def _calc_header_rows(self, zone: dict[str, Any]) -> int:
        row_start = int(zone.get("row_start", 1))
        header = zone.get("header", {})
        rows = []
        rows.extend([int(x) for x in header.get("title_rows", [])])
        rows.extend([int(x) for x in header.get("label_rows", [])])
        tech_row = header.get("tech_row")
        if tech_row:
            rows.append(int(tech_row))
        prefix_row = header.get("prefix_row")
        if prefix_row:
            rows.append(int(prefix_row))
        header_end = max(rows) if rows else row_start
        data_start = zone.get("data_start_row")
        if data_start in (None, ""):
            data_start = header_end + 1
        return max(0, int(data_start) - row_start)

    def _make_preview_cache_key(self, config_dict: dict[str, Any]) -> str:
        payload = {
            "config": config_dict,
            "preview": {
                "header_only": self._preview_header_only_cb.isChecked(),
                "data_rows": self._preview_data_rows_spin.value(),
                "stack_mode": self._output_mode_combo.currentText(),
            },
        }
        return json.dumps(payload, sort_keys=True, default=str)

    def _invalidate_preview_cache(self) -> None:
        self._preview_cache_key = None
        self._preview_cache_frames = {}
        self._preview_frames = {}
        if hasattr(self, "_preview_cache_label"):
            self._preview_cache_label.setText("Cache: invalidé")
        if hasattr(self, "_preview_label"):
            self._preview_label.setText("Prévisualisation à refaire.")
        if hasattr(self, "_preview_sheet_combo"):
            self._preview_sheet_combo.blockSignals(True)
            self._preview_sheet_combo.clear()
            self._preview_sheet_combo.blockSignals(False)
        if hasattr(self, "_preview_table"):
            self._preview_table.model().set_dataframe(pd.DataFrame())
