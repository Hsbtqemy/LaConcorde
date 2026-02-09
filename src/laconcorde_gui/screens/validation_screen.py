"""Écran Validation : file d'attente, détails, candidats, raccourcis clavier."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

import pandas as pd
from PySide6.QtCore import QModelIndex, Qt, QSortFilterProxyModel, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from laconcorde.matching.schema import MatchCandidate, MatchResult

from laconcorde_gui.models import CandidatesModel, ResultsQueueModel
from laconcorde_gui.validation_widgets import FieldComparisonView, ScoreProgressDelegate

if TYPE_CHECKING:
    from laconcorde_gui.state import AppState


class QueueFilterProxy(QSortFilterProxyModel):
    """Proxy pour filtrer la file d'attente par statut et recherche."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._status_filter = "auto"
        self._search_text = ""
        self._score_threshold = 80.0

    def set_status_filter(self, status: str) -> None:
        self._status_filter = status
        self.invalidateFilter()

    def set_search_text(self, text: str) -> None:
        self._search_text = text.strip().lower()
        self.invalidateFilter()

    def set_score_threshold(self, threshold: float) -> None:
        self._score_threshold = threshold
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if not model:
            return True
        if source_row < 0 or source_row >= model.rowCount():
            return False
        status = None
        if hasattr(model, "_columns") and "status" in model._columns:
            col = model._columns.index("status")
            idx = model.index(source_row, col)
            status = str(model.data(idx, Qt.ItemDataRole.DisplayRole))
        best_score = None
        if hasattr(model, "_columns") and "best_score" in model._columns:
            col = model._columns.index("best_score")
            idx = model.index(source_row, col)
            val = model.data(idx, Qt.ItemDataRole.DisplayRole)
            try:
                best_score = float(val)
            except (TypeError, ValueError):
                best_score = None
        if self._status_filter != "all":
            if self._status_filter == "review":
                if status != "pending":
                    return False
                if best_score is None or best_score < self._score_threshold:
                    return False
            elif self._status_filter == "low_score":
                if status != "pending":
                    return False
                if best_score is None or best_score >= self._score_threshold:
                    return False
            else:
                if status != self._status_filter:
                    return False
        if self._search_text:
            for c in range(model.columnCount()):
                idx = model.index(source_row, c)
                val = model.data(idx, Qt.ItemDataRole.DisplayRole)
                if self._search_text in str(val).lower():
                    return True
            return False
        return True


class ValidationScreen(QWidget):
    """Écran de validation interactive (3 panneaux)."""

    def __init__(
        self,
        state: object,
        on_finalize_requested: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._on_finalize = on_finalize_requested or (lambda: None)
        self._current_result: MatchResult | None = None
        self._current_candidate: MatchCandidate | None = None
        self._setup_ui()
        self._setup_shortcuts()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # (1) Header synthèse : badges + compteurs + recherche + filtre + toggle tech
        header = QFrame()
        header.setFrameShape(QFrame.Shape.StyledPanel)
        header.setStyleSheet("QFrame { background: #f8f8f8; border-radius: 4px; padding: 4px; }")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(12)
        self._badge_auto = QLabel("Auto: 0")
        self._badge_auto.setStyleSheet("color: #888; font-size: 11px;")
        self._badge_pending = QLabel("À valider: 0")
        self._badge_pending.setStyleSheet("color: #c67600; font-weight: 600; font-size: 11px;")
        self._badge_ambiguous = QLabel("Ambigus: 0")
        self._badge_ambiguous.setStyleSheet("color: #e65100; font-weight: 600; font-size: 11px;")
        self._badge_rejected = QLabel("Rejetés: 0")
        self._badge_rejected.setStyleSheet("color: #666; font-size: 11px;")
        self._badge_skipped = QLabel("Skippés: 0")
        self._badge_skipped.setStyleSheet("color: #666; font-size: 11px;")
        header_layout.addWidget(self._badge_auto)
        header_layout.addWidget(self._badge_pending)
        header_layout.addWidget(self._badge_ambiguous)
        header_layout.addWidget(self._badge_rejected)
        header_layout.addWidget(self._badge_skipped)
        header_layout.addSpacing(16)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Recherche…")
        self._search_edit.setMaximumWidth(180)
        self._search_edit.textChanged.connect(self._on_search_changed)
        header_layout.addWidget(self._search_edit)
        self._filter_combo = QComboBox()
        self._filter_combo.addItem("Tous", "all")
        self._filter_combo.addItem("Auto", "auto")
        self._filter_combo.addItem("Pending", "pending")
        self._filter_combo.addItem("À valider (≥seuil)", "review")
        self._filter_combo.addItem("Probable non-match (<seuil)", "low_score")
        self._filter_combo.addItem("Acceptés", "accepted")
        self._filter_combo.addItem("Rejetés", "rejected")
        self._filter_combo.addItem("Skippés", "skipped")
        self._filter_combo.setCurrentIndex(0)
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        header_layout.addWidget(self._filter_combo)
        self._triage_spin = QDoubleSpinBox()
        self._triage_spin.setRange(0, 100)
        self._triage_spin.setDecimals(1)
        self._triage_spin.setValue(80.0)
        self._triage_spin.setToolTip("Seuil pour À valider / Probable non-match")
        self._triage_spin.setMaximumWidth(60)
        self._triage_spin.valueChanged.connect(self._on_threshold_changed)
        header_layout.addWidget(QLabel("Seuil:"))
        header_layout.addWidget(self._triage_spin)
        self._tech_toggle = QCheckBox("Détails techniques")
        self._tech_toggle.setChecked(False)
        self._tech_toggle.toggled.connect(self._on_tech_toggle)
        header_layout.addWidget(self._tech_toggle)
        help_btn = QPushButton("?")
        help_btn.setFixedSize(24, 24)
        help_btn.setToolTip("Aide : règles, transfert, raccourcis")
        help_btn.clicked.connect(self._show_help_dialog)
        header_layout.addWidget(help_btn)
        header_layout.addStretch()
        layout.addWidget(header)

        # (3) Layout 30/70 : queue gauche, candidats+comparison droite
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Gauche (30%): file d'attente
        queue_group = QGroupBox("File d'attente")
        queue_layout = QVBoxLayout()
        self._queue_model = ResultsQueueModel()
        self._queue_proxy = QueueFilterProxy()
        self._queue_proxy.setSourceModel(self._queue_model)
        self._queue_table = QTableView()
        self._queue_table.setModel(self._queue_proxy)
        self._queue_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._queue_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._queue_table.selectionModel().selectionChanged.connect(self._on_queue_selection_changed)
        self._queue_table.doubleClicked.connect(self._on_queue_double_clicked)
        queue_layout.addWidget(self._queue_table)
        queue_btns = QHBoxLayout()
        select_all_btn = QPushButton("Tout sélectionner")
        select_all_btn.setToolTip("Coche toutes les lignes visibles (selon le filtre)")
        select_all_btn.clicked.connect(self._select_all_visible)
        clear_selection_btn = QPushButton("Tout désélectionner")
        clear_selection_btn.setToolTip("Décoche toutes les lignes")
        clear_selection_btn.clicked.connect(self._clear_selection)
        queue_btns.addWidget(select_all_btn)
        queue_btns.addWidget(clear_selection_btn)
        queue_btns.addStretch()
        queue_layout.addLayout(queue_btns)
        queue_group.setLayout(queue_layout)
        main_splitter.addWidget(queue_group)

        # Droite (70%): candidats + comparaison champ-par-champ
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        candidates_group = QGroupBox("Correspondances proposées")
        candidates_layout = QVBoxLayout()
        self._candidates_model = CandidatesModel()
        self._candidates_table = QTableView()
        self._candidates_table.setModel(self._candidates_model)
        self._candidates_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._candidates_table.doubleClicked.connect(self._on_candidate_double_clicked)
        self._candidates_table.selectionModel().selectionChanged.connect(self._on_candidate_selection_changed)
        self._candidates_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._candidates_table.customContextMenuRequested.connect(self._on_candidates_context_menu)
        self._candidates_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._candidates_table.horizontalHeader().setStretchLastSection(True)
        candidates_layout.addWidget(self._candidates_table)
        self._top1_info_label = QLabel("")
        self._top1_info_label.setStyleSheet("font-size: 11px; color: #555;")
        candidates_layout.addWidget(self._top1_info_label)
        accept_btn = QPushButton("✓ Valider (Enter)")
        accept_btn.clicked.connect(self._accept_selected_candidate)
        candidates_layout.addWidget(accept_btn)
        candidates_group.setLayout(candidates_layout)
        right_layout.addWidget(candidates_group)

        # (4) FieldComparisonView : comparaison champ-par-champ (cible vs source)
        self._field_comparison = FieldComparisonView()
        right_layout.addWidget(self._field_comparison)

        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([300, 700])

        # (2) Drawer détails techniques (repliable, fermé par défaut)
        self._tech_drawer = QFrame()
        self._tech_drawer.setFrameShape(QFrame.Shape.StyledPanel)
        self._tech_drawer.setVisible(False)
        tech_layout = QVBoxLayout(self._tech_drawer)
        self._tech_status = QLabel("")
        self._tech_status.setWordWrap(True)
        self._tech_scores = QLabel("")
        self._tech_scores.setWordWrap(True)
        self._tech_ambiguity = QLabel("")
        self._tech_ambiguity.setWordWrap(True)
        self._tech_candidate = QLabel("")
        self._tech_candidate.setWordWrap(True)
        self._tech_thresholds = QLabel("")
        self._tech_thresholds.setWordWrap(True)
        self._tech_explanation = QLabel("")
        self._tech_explanation.setWordWrap(True)
        tech_layout.addWidget(self._tech_status)
        tech_layout.addWidget(self._tech_scores)
        tech_layout.addWidget(self._tech_ambiguity)
        tech_layout.addWidget(self._tech_candidate)
        tech_layout.addWidget(self._tech_thresholds)
        tech_layout.addWidget(self._tech_explanation)
        layout.addWidget(self._tech_drawer)

        layout.addWidget(main_splitter)

        # Actions
        actions = QHBoxLayout()
        self._accept1_btn = QPushButton("A - Accepter #1")
        self._accept1_btn.setToolTip("Accepter la proposition #1 (meilleur match)")
        self._accept1_btn.clicked.connect(lambda: self._accept_candidate(0))
        self._reject_btn = QPushButton("R - Rejeter")
        self._reject_btn.setToolTip("Aucune des propositions ne correspond")
        self._reject_btn.clicked.connect(self._reject_current)
        self._skip_btn = QPushButton("S - Skipped")
        self._skip_btn.clicked.connect(self._skip_current)
        self._undo_btn = QPushButton("U - Undo")
        self._undo_btn.clicked.connect(self._undo_last)
        self._auto100_btn = QPushButton("Auto-valider 100%")
        self._auto100_btn.setToolTip(
            "Accepte le meilleur candidat si le score est 100%. "
            "Si des cases sont cochées, ne traite que celles-ci."
        )
        self._auto100_btn.clicked.connect(self._auto_accept_100)
        self._accept_auto_btn = QPushButton("Valider auto")
        self._accept_auto_btn.setToolTip(
            "Bascule les résultats auto en acceptés. "
            "Si des cases sont cochées, ne traite que celles-ci."
        )
        self._accept_auto_btn.clicked.connect(self._accept_auto)
        self._bulk_spin = QDoubleSpinBox()
        self._bulk_spin.setRange(0, 100)
        self._bulk_spin.setValue(95)
        bulk_btn = QPushButton("Bulk accept >= X")
        bulk_btn.setToolTip(
            "Accepte le meilleur candidat si le score ≥ seuil. "
            "Si des cases sont cochées, ne traite que celles-ci."
        )
        bulk_btn.clicked.connect(self._bulk_accept)
        actions.addWidget(self._accept1_btn)
        actions.addWidget(self._reject_btn)
        actions.addWidget(self._skip_btn)
        actions.addWidget(self._undo_btn)
        actions.addWidget(self._auto100_btn)
        actions.addWidget(self._accept_auto_btn)
        actions.addWidget(QLabel("Seuil:"))
        actions.addWidget(self._bulk_spin)
        actions.addWidget(bulk_btn)
        layout.addLayout(actions)

        self._finalize_btn = QPushButton("Finaliser validation")
        self._finalize_btn.clicked.connect(self._on_finalize_clicked)
        layout.addWidget(self._finalize_btn)

    def _setup_shortcuts(self) -> None:
        from PySide6.QtGui import QKeySequence, QShortcut
        shortcuts = [
            QShortcut(QKeySequence("A"), self, self._focus_accept1),
            QShortcut(QKeySequence("R"), self, self._reject_current),
            QShortcut(QKeySequence("S"), self, self._skip_current),
            QShortcut(QKeySequence("U"), self, self._undo_last),
        ]
        for i in range(1, 10):
            shortcuts.append(QShortcut(QKeySequence(str(i)), self, lambda idx=i - 1: self._accept_candidate(idx)))
        enter_shortcut = QShortcut(QKeySequence("Return"), self, self._on_enter_accept)
        enter_shortcut.setAutoRepeat(False)
        shortcuts.append(enter_shortcut)
        for s in shortcuts:
            s.setAutoRepeat(False)
        select_all_shortcut = QShortcut(QKeySequence("Ctrl+A"), self, self._select_all_visible)
        select_all_shortcut.setAutoRepeat(False)

    def _focus_accept1(self) -> None:
        self._accept_candidate(0)

    def _on_enter_accept(self) -> None:
        """Enter = accepter candidat sélectionné ou #1 si rien sélectionné."""
        idx = self._candidates_table.currentIndex()
        if idx.isValid():
            self._accept_candidate(idx.row())
        else:
            self._accept_candidate(0)

    def _safe_get_df(self, attr: str) -> pd.DataFrame:
        """Récupère un DataFrame de l'état sans évaluer sa vérité (évite ValueError pandas)."""
        try:
            val = getattr(self._state, attr, None)
        except ValueError:
            return pd.DataFrame()
        return val if val is not None else pd.DataFrame()

    def refresh_data(self) -> None:
        """Rafraîchit les modèles depuis l'état."""
        results = getattr(self._state, "results", [])
        df_target = self._safe_get_df("df_target")
        df_source = self._safe_get_df("df_source")
        preview_cols = self._get_preview_cols()
        config = getattr(self._state, "config", None)
        cfg = getattr(self._state, "config_dict", {})
        auto_acc = config.auto_accept_score if config else cfg.get("auto_accept_score", 95.0)
        amb_delta = config.ambiguity_delta if config else cfg.get("ambiguity_delta", 5.0)
        min_sc = config.min_score if config else cfg.get("min_score", 0.0)
        self._queue_model.set_data(
            results, df_target, preview_cols,
            auto_accept_score=auto_acc, ambiguity_delta=amb_delta, min_score=min_sc,
        )
        # Éviter resizeColumnsToContents sur gros volumes (très lent, peut faire planter)
        if len(results) < 500:
            self._queue_table.resizeColumnsToContents()
        self._queue_proxy.setFilterKeyColumn(-1)
        self._queue_proxy.set_score_threshold(self._triage_spin.value())
        self._on_filter_changed(self._filter_combo.currentText())
        self._update_badges()
        # Sélection différée pour laisser l'UI se mettre à jour (évite freeze/crash)
        def _select_first() -> None:
            if self._queue_proxy.rowCount() > 0:
                self._queue_table.setCurrentIndex(self._queue_proxy.index(0, 0))
        QTimer.singleShot(0, _select_first)

    def _get_rules(self) -> list:
        config = getattr(self._state, "config", None)
        if config is not None and getattr(config, "rules", None) is not None:
            return list(config.rules)
        config_dict = getattr(self._state, "config_dict", {})
        return config_dict.get("rules", [])

    def _get_rule_columns(self) -> tuple[list[str], list[str]]:
        src_cols: list[str] = []
        tgt_cols: list[str] = []
        for rule in self._get_rules():
            if hasattr(rule, "source_col"):
                src = rule.source_col
                tgt = rule.target_col
            else:
                src = rule.get("source_col", "")
                tgt = rule.get("target_col", "")
            if src and src not in src_cols:
                src_cols.append(src)
            if tgt and tgt not in tgt_cols:
                tgt_cols.append(tgt)
        return src_cols, tgt_cols

    def _format_rules_summary(self) -> str:
        rules = self._get_rules()
        if not rules:
            return "Aucune règle définie."
        parts: list[str] = []
        for rule in rules:
            if hasattr(rule, "source_col"):
                src = rule.source_col
                tgt = rule.target_col
                method = getattr(rule, "method", "")
            else:
                src = rule.get("source_col", "")
                tgt = rule.get("target_col", "")
                method = rule.get("method", "")
            if not src or not tgt:
                continue
            suffix = f" ({method})" if method else ""
            parts.append(f"{src} ↔ {tgt}{suffix}")
        return "; ".join(parts) if parts else "Aucune règle définie."

    def _format_transfer_summary(self) -> str:
        config = getattr(self._state, "config", None)
        if config is not None:
            cols = list(getattr(config, "transfer_columns", []) or [])
            rename = getattr(config, "transfer_column_rename", {}) or {}
            concat = list(getattr(config, "concat_transfers", []) or [])
        else:
            config_dict = getattr(self._state, "config_dict", {})
            cols = list(config_dict.get("transfer_columns", []) or [])
            rename = config_dict.get("transfer_column_rename", {}) or {}
            concat = list(config_dict.get("concat_transfers", []) or [])
        parts: list[str] = []
        if cols:
            base = ", ".join(cols)
            if rename:
                renames = ", ".join(f"{k}→{v}" for k, v in rename.items())
                parts.append(f"{base} (renommage: {renames})")
            else:
                parts.append(base)
        concat_parts: list[str] = []
        for c in concat:
            if hasattr(c, "target_col"):
                target = c.target_col
                sources = c.sources
            else:
                target = c.get("target_col", "")
                sources = c.get("sources", [])
            src_cols: list[str] = []
            for s in sources:
                if hasattr(s, "col"):
                    col = s.col
                else:
                    col = s.get("col", "")
                if col:
                    src_cols.append(col)
            if target and src_cols:
                concat_parts.append(f"{target} ← " + " + ".join(src_cols))
        if concat_parts:
            parts.append("Concat: " + "; ".join(concat_parts))
        if not parts:
            return "Aucune colonne à transférer."
        return " | ".join(parts)

    def _show_help_dialog(self) -> None:
        rules_text = self._format_rules_summary()
        transfer_text = self._format_transfer_summary()
        help_html = (
            "<p><b>Ce que vous validez</b><br>"
            "Vous associez une <b>ligne source</b> à une <b>ligne cible</b> pour enrichir le fichier cible.</p>"
            f"<p><b>Comparé (règles)</b><br>{rules_text}</p>"
            f"<p><b>Transféré</b><br>{transfer_text}</p>"
            "<p><b>Comment décider</b><br>"
            "Choisissez la proposition qui correspond réellement à la ligne cible. "
            "Si aucune ne convient, utilisez <b>Rejeter</b>.</p>"
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("Aide - Validation")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(help_html)
        msg.exec()

    def _get_preview_cols(self) -> list[str]:
        """Colonnes à afficher en aperçu pour la file d'attente (df_target)."""
        df = self._safe_get_df("df_target")
        if len(df.columns) == 0:
            return []
        preferred = ["auteur", "author", "titre", "title", "annee", "year"]
        found = [p for p in preferred if p in df.columns]
        return found[:3] if found else list(df.columns[:3])

    def _get_source_preview_cols(self) -> list[str]:
        """Colonnes à afficher en aperçu pour les candidats (df_source)."""
        df = self._safe_get_df("df_source")
        if len(df.columns) == 0:
            return []
        preferred = ["auteur", "author", "titre", "title", "annee", "year"]
        found = [p for p in preferred if p in df.columns]
        return found[:3] if found else list(df.columns[:3])

    def _on_filter_changed(self, text: str) -> None:
        """Applique le filtre de statut."""
        status = self._filter_combo.currentData() or "all"
        self._queue_proxy.set_status_filter(status)
        self._apply_sort(status)

    def _on_tech_toggle(self, checked: bool) -> None:
        """Ouvre/ferme le drawer des détails techniques."""
        self._tech_drawer.setVisible(checked)

    def _on_search_changed(self, text: str) -> None:
        """Applique la recherche texte."""
        self._queue_proxy.set_search_text(text)

    def _on_candidates_context_menu(self, pos: Any) -> None:
        """Menu contextuel : Copier la valeur sélectionnée."""
        idx = self._candidates_table.indexAt(pos)
        if not idx.isValid():
            return
        val = self._candidates_model.data(idx, Qt.ItemDataRole.DisplayRole)
        text = str(val) if val is not None else ""
        if not text:
            return
        menu = QMenu(self)
        copy_act = menu.addAction("Copier")
        if menu.exec(self._candidates_table.mapToGlobal(pos)) == copy_act:
            QApplication.clipboard().setText(text)

    def _select_all_visible(self) -> None:
        """Coche toutes les lignes actuellement visibles (selon le filtre)."""
        visible_ids = self._get_visible_target_ids()
        if visible_ids:
            self._queue_model.select_visible_ids(visible_ids)

    def _clear_selection(self) -> None:
        """Décoche toutes les lignes."""
        self._queue_model.clear_selection()

    def _get_visible_target_ids(self) -> list[int]:
        """Retourne les target_row_id visibles dans la file (selon le filtre)."""
        visible_ids: list[int] = []
        for proxy_row in range(self._queue_proxy.rowCount()):
            src_idx = self._queue_proxy.mapToSource(self._queue_proxy.index(proxy_row, 0))
            if src_idx.isValid():
                result = self._queue_model.get_result_at_row(src_idx.row())
                if result is not None:
                    visible_ids.append(result.target_row_id)
        return visible_ids

    def _on_threshold_changed(self, _value: float | None = None) -> None:
        """Met à jour le seuil de triage."""
        self._queue_proxy.set_score_threshold(self._triage_spin.value())
        self._update_badges()
        status = self._filter_combo.currentData()
        if status:
            self._apply_sort(status)

    def _apply_sort(self, status: str | None) -> None:
        if not status:
            return
        n = self._queue_model.rowCount()
        if n > 2000:
            # Désactiver le tri auto sur gros volumes (lent, peut bloquer)
            self._queue_table.setSortingEnabled(False)
            return
        if not self._queue_table.isSortingEnabled():
            self._queue_table.setSortingEnabled(True)
        best_col = self._queue_model.get_column_index("best_score")
        if best_col is None:
            return
        if status == "review":
            self._queue_table.sortByColumn(best_col, Qt.SortOrder.DescendingOrder)
        elif status == "low_score":
            self._queue_table.sortByColumn(best_col, Qt.SortOrder.AscendingOrder)

    def _update_badges(self) -> None:
        """Met à jour les badges de synthèse (Auto, À valider, Ambigus, etc.)."""
        results = getattr(self._state, "results", [])
        n_auto = sum(1 for r in results if r.status == "auto")
        n_pending = sum(1 for r in results if r.status == "pending")
        n_ambiguous = sum(1 for r in results if r.is_ambiguous and r.status == "pending")
        n_rejected = sum(1 for r in results if r.status == "rejected")
        n_skipped = sum(1 for r in results if r.status == "skipped")
        self._badge_auto.setText(f"Auto: {n_auto}")
        self._badge_pending.setText(f"À valider: {n_pending}")
        self._badge_ambiguous.setText(f"Ambigus: {n_ambiguous}")
        self._badge_rejected.setText(f"Rejetés: {n_rejected}")
        self._badge_skipped.setText(f"Skippés: {n_skipped}")

    def _on_queue_selection_changed(self) -> None:
        """Met à jour les détails et candidats quand la sélection change."""
        idx = self._queue_table.currentIndex()
        if not idx.isValid():
            self._candidates_model.set_result(None, pd.DataFrame(), [])
            self._current_result = None
            self._current_candidate = None
            self._field_comparison.set_comparison(None, None, pd.DataFrame(), pd.DataFrame(), [])
            self._top1_info_label.setText("")
            self._update_tech_panel(None, None)
            return
        src_row = self._queue_proxy.mapToSource(idx).row()
        result = self._queue_model.get_result_at_row(src_row)
        if result:
            df_src = self._safe_get_df("df_source")
            self._candidates_model.set_result(result, df_src, self._get_source_preview_cols())
            score_col = self._candidates_model._columns.index("score") if "score" in self._candidates_model._columns else -1
            if score_col >= 0:
                self._candidates_table.setItemDelegateForColumn(score_col, ScoreProgressDelegate(self))
            self._candidates_table.resizeColumnsToContents()
            self._current_result = result
            if self._candidates_model.rowCount() > 0:
                self._candidates_table.setCurrentIndex(self._candidates_model.index(0, 0))
                best_candidate = self._candidates_model.get_candidate_at_row(0)
                self._current_candidate = best_candidate
                self._update_field_comparison(result, best_candidate)
                self._update_top1_info(result, best_candidate)
                self._update_tech_panel(result, best_candidate)
            else:
                self._current_candidate = None
                self._field_comparison.set_comparison(None, None, pd.DataFrame(), pd.DataFrame(), [])
                self._top1_info_label.setText("")
                self._update_tech_panel(result, None)
        else:
            self._candidates_model.set_result(None, pd.DataFrame(), [])
            self._current_result = None
            self._current_candidate = None
            self._field_comparison.set_comparison(None, None, pd.DataFrame(), pd.DataFrame(), [])
            self._top1_info_label.setText("")
            self._update_tech_panel(None, None)

    def _on_queue_double_clicked(self, index: QModelIndex) -> None:
        """Double-clic sur la file d'attente : accepter le premier candidat."""
        self._accept_candidate(0)

    def _on_candidate_double_clicked(self, index: QModelIndex) -> None:
        """Double-clic sur un candidat : accepter + next."""
        self._accept_candidate(index.row())

    def _advance_to_next(self) -> None:
        """Sélectionne la prochaine ligne selon le filtre (auto-advance)."""
        idx = self._queue_table.currentIndex()
        if not idx.isValid():
            return
        proxy_row = idx.row()
        next_row = proxy_row + 1
        if next_row < self._queue_proxy.rowCount():
            self._queue_table.setCurrentIndex(self._queue_proxy.index(next_row, 0))
        else:
            QMessageBox.information(self, "Fin", "Plus de lignes dans la vue actuelle.")

    def _on_candidate_selection_changed(self) -> None:
        """Met à jour la comparaison champ-par-champ au clic sur un candidat."""
        idx = self._candidates_table.currentIndex()
        if not idx.isValid() or self._current_result is None:
            return
        candidate = self._candidates_model.get_candidate_at_row(idx.row())
        if candidate is None:
            self._update_tech_panel(self._current_result, None)
            return
        self._current_candidate = candidate
        self._update_field_comparison(self._current_result, candidate)
        self._update_top1_info(self._current_result, candidate)
        self._update_tech_panel(self._current_result, candidate)

    def _update_field_comparison(self, result: MatchResult, candidate: MatchCandidate) -> None:
        """Met à jour la vue comparaison champ-par-champ."""
        df_tgt = self._safe_get_df("df_target")
        df_src = self._safe_get_df("df_source")
        rules = self._get_rules()
        self._field_comparison.set_comparison(result, candidate, df_tgt, df_src, rules)

    def _update_top1_info(self, result: MatchResult, candidate: MatchCandidate | None) -> None:
        """Affiche Top1, Top2, Δ dans la barre d'info."""
        if not result or not result.candidates:
            self._top1_info_label.setText("")
            return
        top1 = result.candidates[0].score
        top2 = result.candidates[1].score if len(result.candidates) > 1 else None
        delta = (top1 - top2) if top2 is not None else None
        parts = [f"Top1: {top1:.0f}"]
        if top2 is not None:
            parts.append(f"Top2: {top2:.0f}")
        if delta is not None:
            parts.append(f"Δ: {delta:.0f}")
        self._top1_info_label.setText(" · ".join(parts))

    def _accept_selected_candidate(self) -> None:
        """Accepter le candidat sélectionné dans la table."""
        idx = self._candidates_table.currentIndex()
        if idx.isValid():
            self._accept_candidate(idx.row())

    def _accept_candidate(self, rank: int) -> None:
        """Accepte le candidat au rang donné (0-based)."""
        idx = self._queue_table.currentIndex()
        if not idx.isValid():
            return
        src_row = self._queue_proxy.mapToSource(idx).row()
        result = self._queue_model.get_result_at_row(src_row)
        if not result or rank >= len(result.candidates):
            return
        chosen = result.candidates[rank].source_row_id
        self._apply_decision(result.target_row_id, chosen)

    def _reject_current(self) -> None:
        """Rejette la ligne sélectionnée."""
        idx = self._queue_table.currentIndex()
        if not idx.isValid():
            return
        src_row = self._queue_proxy.mapToSource(idx).row()
        result = self._queue_model.get_result_at_row(src_row)
        if result:
            self._apply_decision(result.target_row_id, None)

    def _skip_current(self) -> None:
        """Marque comme skipped."""
        idx = self._queue_table.currentIndex()
        if not idx.isValid():
            return
        src_row = self._queue_proxy.mapToSource(idx).row()
        result = self._queue_model.get_result_at_row(src_row)
        if result:
            self._apply_decision_skipped(result.target_row_id)

    def _apply_decision(self, target_row_id: int, chosen_source_row_id: int | None) -> None:
        """Applique une décision (accept/reject)."""
        from laconcorde_gui.controllers import SessionController
        results = getattr(self._state, "results", [])
        for r in results:
            if r.target_row_id == target_row_id:
                old = r.chosen_source_row_id
                SessionController.push_undo(self._state, target_row_id, old)
                choices = getattr(self._state, "choices", {})
                choices[target_row_id] = chosen_source_row_id
                self._queue_model.update_result(target_row_id, chosen_source_row_id)
                r.chosen_source_row_id = chosen_source_row_id
                r.status = "rejected" if chosen_source_row_id is None else "accepted"
                r.explanation = "No match (user)" if chosen_source_row_id is None else "User accepted"
                self._update_badges()
                self._advance_to_next()
                break

    def _apply_decision_skipped(self, target_row_id: int) -> None:
        """Marque comme skipped."""
        from laconcorde_gui.controllers import SessionController
        results = getattr(self._state, "results", [])
        for r in results:
            if r.target_row_id == target_row_id:
                old = r.chosen_source_row_id
                SessionController.push_undo(self._state, target_row_id, old)
                choices = getattr(self._state, "choices", {})
                choices[target_row_id] = None
                r.chosen_source_row_id = None
                r.status = "skipped"
                r.explanation = "Skipped (user)"
                self._queue_model.update_result(target_row_id, None, status="skipped")
                self._update_badges()
                self._advance_to_next()
                break

    def _undo_last(self) -> None:
        """Annule la dernière décision."""
        from laconcorde_gui.controllers import SessionController
        undone = SessionController.pop_undo(self._state)
        if undone is None:
            return
        target_row_id, old_chosen = undone
        choices = getattr(self._state, "choices", {})
        choices[target_row_id] = old_chosen
        results = getattr(self._state, "results", [])
        for r in results:
            if r.target_row_id == target_row_id:
                r.chosen_source_row_id = old_chosen
                r.status = "pending" if old_chosen is None else "accepted"
                r.explanation = "Reverted" if old_chosen is None else "User accepted"
                self._queue_model.update_result(target_row_id, old_chosen)
                self._on_queue_selection_changed()
                self._update_badges()
                break

    def _bulk_accept(self) -> None:
        """Accepte en masse les pending non ambigus au-dessus du seuil (avec confirmation)."""
        threshold = self._bulk_spin.value()
        results = getattr(self._state, "results", [])
        status_filter = self._filter_combo.currentData() or "all"
        selected_ids = set(self._queue_model.get_selected_target_ids())
        apply_selected = len(selected_ids) > 0
        to_accept: list[tuple[int, int]] = []
        for r in results:
            if apply_selected and r.target_row_id not in selected_ids:
                continue
            if r.status != "pending" or r.is_ambiguous:
                continue
            if not r.candidates or r.candidates[0].score < threshold:
                continue
            if status_filter != "all" and status_filter not in ("pending", "review"):
                continue
            if status_filter == "review" and (r.best_score < self._triage_spin.value()):
                continue
            if status_filter == "low_score" and (r.best_score >= self._triage_spin.value()):
                continue
            to_accept.append((r.target_row_id, r.candidates[0].source_row_id))
        if not to_accept:
            QMessageBox.information(self, "Bulk accept", "Aucune ligne à traiter.")
            return
        reply = QMessageBox.question(
            self,
            "Bulk accept",
            f"Appliquer à {len(to_accept)} lignes "
            f"({ 'sélection' if apply_selected else 'vue' }, pending, score ≥ {threshold:.0f}) ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        choices = getattr(self._state, "choices", {})
        from laconcorde_gui.controllers import SessionController
        for target_row_id, chosen in to_accept:
            for r in results:
                if r.target_row_id == target_row_id:
                    old = r.chosen_source_row_id
                    SessionController.push_undo(self._state, target_row_id, old)
                    break
            choices[target_row_id] = chosen
            for r in results:
                if r.target_row_id == target_row_id:
                    r.chosen_source_row_id = chosen
                    r.status = "accepted"
                    r.explanation = "Bulk accept"
                    break
            self._queue_model.update_result(target_row_id, chosen)
        QMessageBox.information(self, "Bulk accept", f"{len(to_accept)} lignes acceptées.")
        self._update_badges()

    def _auto_accept_100(self) -> None:
        """Auto-valide les pending dont le meilleur score est 100%."""
        from laconcorde_gui.controllers import SessionController
        results = getattr(self._state, "results", [])
        choices = getattr(self._state, "choices", {})
        selected_ids = set(self._queue_model.get_selected_target_ids())
        apply_selected = len(selected_ids) > 0
        # Collecter toutes les mises à jour avant de les appliquer (évite les effets de bord)
        to_apply: list[tuple[int, int]] = []
        for r in results:
            if r.status != "pending":
                continue
            if apply_selected and r.target_row_id not in selected_ids:
                continue
            if not r.candidates:
                continue
            best = r.candidates[0].score
            if best < 99.99:  # Tolérance float pour 100%
                continue
            chosen = r.candidates[0].source_row_id
            to_apply.append((r.target_row_id, chosen))
        # Appliquer toutes les décisions
        for target_row_id, chosen in to_apply:
            for r in results:
                if r.target_row_id == target_row_id:
                    old = r.chosen_source_row_id
                    SessionController.push_undo(self._state, target_row_id, old)
                    break
            choices[target_row_id] = chosen
            for r in results:
                if r.target_row_id == target_row_id:
                    r.chosen_source_row_id = chosen
                    r.status = "accepted"
                    r.explanation = "Auto-accept 100%"
                    break
            self._queue_model.update_result(target_row_id, chosen)
        if to_apply:
            QMessageBox.information(self, "Auto-accept 100%", f"{len(to_apply)} lignes acceptées.")
        self._update_badges()

    def _accept_auto(self) -> None:
        """Bascule les résultats auto en acceptés (avec confirmation)."""
        results = getattr(self._state, "results", [])
        selected_ids = set(self._queue_model.get_selected_target_ids())
        apply_selected = len(selected_ids) > 0
        visible_ids = None

        to_apply: list[tuple[int, int]] = []
        for r in results:
            if r.status != "auto":
                continue
            if apply_selected and r.target_row_id not in selected_ids:
                continue
            if r.chosen_source_row_id is None:
                continue
            to_apply.append((r.target_row_id, r.chosen_source_row_id))
        if not to_apply:
            QMessageBox.information(self, "Valider auto", "Aucune ligne à traiter.")
            return

        scope = "sélection" if apply_selected else "tout"
        reply = QMessageBox.question(
            self,
            "Valider auto",
            f"Basculer {len(to_apply)} lignes (auto → accepté, {scope}) ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        choices = getattr(self._state, "choices", {})
        for target_row_id, chosen in to_apply:
            choices[target_row_id] = chosen
            self._queue_model.update_result(target_row_id, chosen, status="accepted")
        QMessageBox.information(self, "Valider auto", f"{len(to_apply)} lignes validées.")
        self._update_badges()

    def _on_finalize_clicked(self) -> None:
        """Finalise la validation et appelle resolve_pending."""
        self._on_finalize()

    def _update_tech_panel(self, result: MatchResult | None, candidate: MatchCandidate | None) -> None:
        if result is None:
            self._tech_status.setText("Sélectionnez une ligne pour voir les détails techniques.")
            self._tech_scores.setText("")
            self._tech_ambiguity.setText("")
            self._tech_candidate.setText("")
            self._tech_thresholds.setText("")
            self._tech_explanation.setText("")
            return
        best = result.candidates[0].score if result.candidates else None
        second = result.candidates[1].score if len(result.candidates) > 1 else None
        delta = best - second if best is not None and second is not None else None
        best_txt = f"{best:.1f}" if isinstance(best, (int, float)) else "—"
        second_txt = f"{second:.1f}" if isinstance(second, (int, float)) else "—"
        delta_txt = f"{delta:.1f}" if isinstance(delta, (int, float)) else "—"
        self._tech_status.setText(
            f"<b>Statut:</b> {result.status} | <b>Meilleur score:</b> {best_txt} | "
            f"<b>Candidats:</b> {len(result.candidates)}"
        )
        self._tech_scores.setText(f"<b>Top1:</b> {best_txt} · <b>Top2:</b> {second_txt}")
        self._tech_ambiguity.setText(
            f"<b>Ambigu:</b> {'Oui' if result.is_ambiguous else 'Non'} | "
            f"<b>Δ (top1-top2):</b> {delta_txt}"
        )
        if candidate is not None:
            self._tech_candidate.setText(
                f"<b>Candidat sélectionné:</b> ligne source {candidate.source_row_id + 1}, score {candidate.score:.1f}"
            )
        else:
            self._tech_candidate.setText("<b>Candidat sélectionné:</b> —")
        config = getattr(self._state, "config", None)
        if config is not None:
            self._tech_thresholds.setText(
                f"<b>Seuils:</b> auto-accept={config.auto_accept_score:.1f} · "
                f"ambiguïté={config.ambiguity_delta:.1f} · min_score={config.min_score:.1f} · "
                f"top_k={config.top_k} · triage={self._triage_spin.value():.1f}"
            )
        else:
            self._tech_thresholds.setText(f"<b>Seuil triage:</b> {self._triage_spin.value():.1f}")
        self._tech_explanation.setText(f"<b>Explication:</b> {result.explanation}")
