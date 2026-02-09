"""Écran Règles : éditeur de règles, paramètres, colonnes à transférer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from laconcorde.config import (
    VALID_BLOCKERS,
    VALID_METHODS,
    VALID_OVERWRITE_MODES,
)

if TYPE_CHECKING:
    from laconcorde_gui.state import AppState


class _ConcatSourceWidget(QWidget):
    """Widget d'une source concaténée (colonne + préfixe)."""

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


class _ConcatTransferEditor(QGroupBox):
    """Éditeur d'une concaténation vers une colonne cible."""

    def __init__(
        self,
        source_cols: list[str],
        target_cols: list[str],
        on_remove: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Concaténation")
        self._source_cols = list(source_cols)
        self._target_cols = list(target_cols)
        layout = QVBoxLayout(self)

        header_row = QHBoxLayout()
        self._target_combo = QComboBox()
        self._target_combo.setEditable(True)
        self._target_combo.setMinimumWidth(180)
        self._target_combo.setToolTip(
            "Sélectionnez une colonne cible existante ou saisissez un nouveau nom."
        )
        if self._target_combo.lineEdit():
            self._target_combo.lineEdit().setPlaceholderText("Colonne cible (nom)")
        self.refresh_target_cols(self._target_cols)
        self._separator_edit = QLineEdit("; ")
        self._separator_edit.setPlaceholderText("Séparateur")
        self._join_existing_edit = QLineEdit()
        self._join_existing_edit.setPlaceholderText("Séparateur existant (optionnel)")
        self._join_existing_edit.setToolTip(
            "Séparateur entre contenu existant et nouveau bloc (append/prepend). "
            "Vide = utiliser le séparateur principal."
        )
        self._mode_combo = QComboBox()
        # Affiche "replace" plutôt que "always" dans l'UI.
        ui_modes = ["if_empty", "replace", "append", "prepend"]
        self._mode_combo.addItems(ui_modes)
        self._mode_combo.setCurrentText("if_empty")
        self._skip_empty_cb = QCheckBox("Ignorer vides")
        self._skip_empty_cb.setChecked(True)
        remove_btn = QPushButton("Supprimer")
        if on_remove:
            remove_btn.clicked.connect(on_remove)
        header_row.addWidget(QLabel("Cible:"))
        header_row.addWidget(self._target_combo, 2)
        header_row.addWidget(QLabel("Séparateur:"))
        header_row.addWidget(self._separator_edit, 1)
        header_row.addWidget(QLabel("Sep. existant:"))
        header_row.addWidget(self._join_existing_edit, 1)
        header_row.addWidget(QLabel("Mode:"))
        header_row.addWidget(self._mode_combo, 1)
        header_row.addWidget(self._skip_empty_cb, 0)
        header_row.addStretch()
        header_row.addWidget(remove_btn)
        layout.addLayout(header_row)

        src_header = QHBoxLayout()
        src_header.addWidget(QLabel("Colonnes source (ordre)"), 2)
        src_header.addWidget(QLabel("Préfixe"), 3)
        layout.addLayout(src_header)

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

    def refresh_source_columns(self, source_cols: list[str]) -> None:
        self._source_cols = list(source_cols)
        for i in range(self._sources_list.count()):
            item = self._sources_list.item(i)
            widget = self._sources_list.itemWidget(item)
            if isinstance(widget, _ConcatSourceWidget):
                widget.refresh_source_cols(self._source_cols)

    def refresh_target_cols(self, target_cols: list[str], current: str | None = None) -> None:
        self._target_cols = list(target_cols)
        cur = current if current is not None else self._target_combo.currentText()
        items = list(self._target_cols)
        if cur and cur not in items:
            items.insert(0, cur)
        self._target_combo.clear()
        self._target_combo.addItems(items)
        if cur:
            self._target_combo.setCurrentText(cur)

    def load_from_dict(self, d: dict) -> None:
        self.refresh_target_cols(self._target_cols, current=str(d.get("target_col", "")).strip())
        self._separator_edit.setText(str(d.get("separator", "; ")))
        mode = str(d.get("overwrite_mode", "if_empty"))
        if mode == "always":
            mode = "replace"
        self._mode_combo.setCurrentText(mode)
        self._skip_empty_cb.setChecked(bool(d.get("skip_empty", True)))
        if "join_with_existing" in d:
            self._join_existing_edit.setText(str(d.get("join_with_existing", "")))
        else:
            self._join_existing_edit.setText("")
        self._sources_list.clear()
        for src in d.get("sources", []):
            col = str(src.get("col", ""))
            prefix = str(src.get("prefix", ""))
            self._add_source_row(col=col, prefix=prefix)

    def to_dict(self) -> dict:
        sources = []
        for i in range(self._sources_list.count()):
            item = self._sources_list.item(i)
            widget = self._sources_list.itemWidget(item)
            if isinstance(widget, _ConcatSourceWidget):
                col, prefix = widget.get_data()
                if col:
                    sources.append({"col": col, "prefix": prefix})
        data = {
            "target_col": self._target_combo.currentText().strip(),
            "separator": self._separator_edit.text(),
            "overwrite_mode": self._mode_combo.currentText(),
            "skip_empty": self._skip_empty_cb.isChecked(),
            "sources": sources,
        }
        join_sep = self._join_existing_edit.text()
        if join_sep != "":
            data["join_with_existing"] = join_sep
        return data


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
        self._rules_table.setColumnCount(7)
        self._rules_table.setHorizontalHeaderLabels(
            ["Col. source", "Col. cible", "Poids", "Méthode", "Normaliser", "Sans diacritiques", "Sans extension"]
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
        self._overwrite_combo.setToolTip(
            "if_empty: ne remplit que les cellules vides (ne touche pas aux données existantes)\n"
            "always: écrase toujours\n"
            "never: crée une nouvelle colonne avec suffixe"
        )
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
        transfer_hint = QLabel(
            "Cochez les colonnes source à transférer. "
            "Choisissez la colonne cible (→) : existante = complète les vides, nouvelle = crée la colonne."
        )
        transfer_hint.setWordWrap(True)
        transfer_hint.setStyleSheet("color: #555; font-size: 11px;")
        transfer_layout.addWidget(transfer_hint)
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
        params_transfer_row.addWidget(transfer_group, 3)
        layout.addLayout(params_transfer_row)

        # Concaténation vers colonne cible
        concat_group = QGroupBox("Concaténation vers colonne cible")
        concat_layout = QVBoxLayout()
        concat_hint = QLabel(
            "Combine plusieurs colonnes source dans une colonne cible avec un séparateur et des préfixes optionnels."
        )
        concat_hint.setWordWrap(True)
        concat_hint.setStyleSheet("color: #555; font-size: 11px;")
        concat_layout.addWidget(concat_hint)

        self._concat_editors: list[_ConcatTransferEditor] = []
        self._concat_scroll = QScrollArea()
        self._concat_scroll.setWidgetResizable(True)
        self._concat_container = QWidget()
        self._concat_container_layout = QVBoxLayout(self._concat_container)
        self._concat_container_layout.setContentsMargins(0, 0, 0, 0)
        self._concat_container_layout.setSpacing(8)
        self._concat_container_layout.addStretch()
        self._concat_scroll.setWidget(self._concat_container)
        concat_layout.addWidget(self._concat_scroll)

        concat_btns = QHBoxLayout()
        add_concat_btn = QPushButton("Ajouter concaténation")
        add_concat_btn.clicked.connect(self._add_concat_editor)
        concat_btns.addWidget(add_concat_btn)
        concat_btns.addStretch()
        concat_layout.addLayout(concat_btns)

        concat_group.setLayout(concat_layout)
        layout.addWidget(concat_group)

        # Bouton matching
        self._match_btn = QPushButton("Lancer matching")
        self._match_btn.clicked.connect(self._on_matching_clicked)
        layout.addWidget(self._match_btn)

    def refresh_from_state(self) -> None:
        """Rafraîchit l'UI depuis l'état (colonnes source/cible)."""
        self._refresh_rules_combos()
        self._refresh_transfer_columns()
        self._refresh_concat_editors()

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
        df_tgt = getattr(self._state, "df_target", None)
        src_cols = list(df_src.columns) if df_src is not None else []
        tgt_cols = list(df_tgt.columns) if df_tgt is not None else []
        config_dict = getattr(self._state, "config_dict", {})
        transfer_cols = set(config_dict.get("transfer_columns", []))
        rename_dict = config_dict.get("transfer_column_rename", {})
        for col in src_cols:
            row = QHBoxLayout()
            cb = QCheckBox(col)
            cb.setChecked(col in transfer_cols)
            row.addWidget(cb)
            target_combo = QComboBox()
            target_combo.setEditable(True)
            target_combo.addItem("")  # Vide = garder le nom source
            target_combo.addItems(tgt_cols)
            target_combo.setMinimumWidth(180)
            target_combo.setToolTip(
                "Sélectionnez une colonne cible existante ou saisissez un nouveau nom. "
                "Avec 'Overwrite: if_empty', les cellules déjà remplies ne sont pas écrasées."
            )
            if col in rename_dict:
                target_combo.setCurrentText(rename_dict[col])
            row.addWidget(QLabel("→"))
            row.addWidget(target_combo)
            self._transfer_layout.addLayout(row)

    def _add_concat_editor(self, preset: dict | None = None) -> None:
        """Ajoute un éditeur de concaténation."""
        df_src = getattr(self._state, "df_source", None)
        df_tgt = getattr(self._state, "df_target", None)
        src_cols = list(df_src.columns) if df_src is not None else []
        tgt_cols = list(df_tgt.columns) if df_tgt is not None else []

        editor = _ConcatTransferEditor(
            src_cols,
            tgt_cols,
            on_remove=lambda: self._remove_concat_editor(editor),
        )
        if preset:
            editor.load_from_dict(preset)
        self._concat_editors.append(editor)
        insert_at = max(0, self._concat_container_layout.count() - 1)
        self._concat_container_layout.insertWidget(insert_at, editor)

    def _remove_concat_editor(self, editor: _ConcatTransferEditor) -> None:
        """Supprime un éditeur de concaténation."""
        if editor in self._concat_editors:
            self._concat_editors.remove(editor)
        editor.setParent(None)
        editor.deleteLater()

    def _refresh_concat_editors(self) -> None:
        """Met à jour les colonnes source des éditeurs de concaténation."""
        df_src = getattr(self._state, "df_source", None)
        df_tgt = getattr(self._state, "df_target", None)
        src_cols = list(df_src.columns) if df_src is not None else []
        tgt_cols = list(df_tgt.columns) if df_tgt is not None else []
        if self._concat_editors:
            for editor in self._concat_editors:
                editor.refresh_source_columns(src_cols)
                editor.refresh_target_cols(tgt_cols)
            return
        config_dict = getattr(self._state, "config_dict", {})
        for preset in config_dict.get("concat_transfers", []):
            self._add_concat_editor(preset=preset)

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
        ext_cb = QCheckBox()
        self._rules_table.setCellWidget(row, 0, src_combo)
        self._rules_table.setCellWidget(row, 1, tgt_combo)
        self._rules_table.setCellWidget(row, 2, weight_spin)
        self._rules_table.setCellWidget(row, 3, method_combo)
        self._rules_table.setCellWidget(row, 4, norm_cb)
        self._rules_table.setCellWidget(row, 5, diac_cb)
        self._rules_table.setCellWidget(row, 6, ext_cb)

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
            ext_cb = self._rules_table.cellWidget(row, 6)
            if not all([src_combo, tgt_combo, weight_spin, method_combo, norm_cb, diac_cb, ext_cb]):
                continue
            rules.append({
                "source_col": src_combo.currentText(),
                "target_col": tgt_combo.currentText(),
                "weight": weight_spin.value(),
                "method": method_combo.currentText(),
                "normalize": norm_cb.isChecked(),
                "remove_diacritics": diac_cb.isChecked(),
                "strip_file_extensions": ext_cb.isChecked(),
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
            target_combo = inner.itemAt(2).widget() if inner.count() >= 3 else None
            if isinstance(cb, QCheckBox) and cb.isChecked():
                col = cb.text()
                transfer_cols.append(col)
                if target_combo and isinstance(target_combo, QComboBox):
                    tgt_name = target_combo.currentText().strip()
                    if tgt_name:
                        rename_dict[col] = tgt_name
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
        concat_transfers = []
        for editor in self._concat_editors:
            data = editor.to_dict()
            if data["target_col"] and data["sources"]:
                concat_transfers.append(data)
        base["concat_transfers"] = concat_transfers
        return base

    def _on_matching_clicked(self) -> None:
        """Valide et lance le matching."""
        config_dict = self.get_config_dict()
        if not config_dict.get("rules"):
            QMessageBox.warning(self, "Attention", "Ajoutez au moins une règle de matching.")
            return
        self._state.config_dict = config_dict
        self._on_matching_requested()
