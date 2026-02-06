"""Écran Validation : file d'attente, détails, candidats, raccourcis clavier."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pandas as pd
from PySide6.QtCore import QModelIndex, Qt, QSortFilterProxyModel, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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

        # Filtres
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(8)
        self._filter_combo = QComboBox()
        self._filter_combo.addItem("Auto", "auto")
        self._filter_combo.addItem("À valider (score ≥ seuil)", "review")
        self._filter_combo.addItem("Probable non-match (score < seuil)", "low_score")
        self._filter_combo.addItem("Tous", "all")
        self._filter_combo.addItem("Acceptés", "accepted")
        self._filter_combo.addItem("Rejetés", "rejected")
        self._filter_combo.addItem("Skippés", "skipped")
        self._filter_combo.addItem("En attente (brut)", "pending")
        self._filter_combo.setCurrentIndex(0)
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(QLabel("Filtre:"))
        filter_row.addWidget(self._filter_combo)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Recherche...")
        self._search_edit.textChanged.connect(self._on_search_changed)
        filter_row.addWidget(self._search_edit)
        self._triage_spin = QDoubleSpinBox()
        self._triage_spin.setRange(0, 100)
        self._triage_spin.setDecimals(1)
        self._triage_spin.setValue(80.0)
        self._triage_spin.setToolTip("Seuil utilisé pour 'À valider' et 'Probable non-match'")
        self._triage_spin.valueChanged.connect(self._on_threshold_changed)
        filter_row.addWidget(QLabel("Seuil:"))
        filter_row.addWidget(self._triage_spin)
        rules_details_btn = QPushButton("Détails")
        rules_details_btn.setToolTip("Voir le détail : règles, colonnes transférées, aide")
        rules_details_btn.clicked.connect(self._show_help_dialog)
        filter_row.addWidget(rules_details_btn)
        layout.addLayout(filter_row)
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(8)
        self._rules_summary_label = QLabel("")
        self._rules_summary_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._rules_summary_label.setStyleSheet("color: #555; font-size: 11px; padding: 0;")
        meta_row.addWidget(self._rules_summary_label)
        self._triage_stats = QLabel("")
        self._triage_stats.setStyleSheet("color: #555; font-size: 11px; padding: 0;")
        meta_row.addWidget(self._triage_stats)
        layout.addLayout(meta_row)

        # 3 panneaux (file d'attente + détails cible / correspondances / volet technique)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Gauche: file d'attente + détails cible (splitter vertical)
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        queue_group = QGroupBox("File d'attente (lignes cibles)")
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
        left_splitter.addWidget(queue_group)

        details_group = QGroupBox("Détails de la ligne cible sélectionnée")
        self._details_layout = QVBoxLayout()
        self._details_placeholder = QLabel("Sélectionnez une ligne dans la file d'attente à gauche.")
        self._details_layout.addWidget(self._details_placeholder)
        details_group.setLayout(self._details_layout)
        left_splitter.addWidget(details_group)
        left_splitter.setSizes([520, 180])
        splitter.addWidget(left_splitter)

        # Centre: correspondances (zone principale)
        candidates_group = QGroupBox("Correspondances proposées (fichier source)")
        candidates_layout = QVBoxLayout()
        explanation = QLabel(
            "Pour la <b>ligne cible</b> sélectionnée (centre), ce tableau affiche les <b>lignes du fichier source</b> "
            "que l'algorithme a identifiées comme potentiellement identiques. Chaque ligne = une proposition de match. "
            "Choisissez celle qui correspond (double-clic ou touche 1–9), ou rejetez si aucune ne convient."
        )
        explanation.setWordWrap(True)
        explanation.setTextFormat(Qt.TextFormat.RichText)
        explanation.setStyleSheet("color: #333; font-size: 11px; padding: 4px 0;")
        self._candidates_model = CandidatesModel()
        self._candidates_table = QTableView()
        self._candidates_table.setModel(self._candidates_model)
        self._candidates_table.setWordWrap(True)
        self._candidates_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._candidates_table.doubleClicked.connect(self._on_candidate_double_clicked)
        self._candidates_table.selectionModel().selectionChanged.connect(self._on_candidate_selection_changed)
        self._candidates_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._candidates_table.horizontalHeader().setStretchLastSection(True)
        self._candidates_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._candidates_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._candidates_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        accept_btn = QPushButton("✓ Valider la correspondance sélectionnée")
        accept_btn.setToolTip("Confirmer que la ligne source sélectionnée correspond à la ligne cible")
        accept_btn.clicked.connect(self._accept_selected_candidate)

        # Comparaison par règles
        self._rules_compare_group = QGroupBox("Comparaison (règles)")
        rules_layout = QVBoxLayout()
        self._rules_compare_hint = QLabel(
            "Sélectionnez une proposition pour voir la comparaison par règle (cible ↔ source)."
        )
        self._rules_compare_hint.setWordWrap(True)
        self._rules_compare_table = QTableWidget()
        self._rules_compare_table.setColumnCount(4)
        self._rules_compare_table.setHorizontalHeaderLabels(["Règle", "Cible", "Source", "Score"])
        self._rules_compare_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._rules_compare_table.verticalHeader().setVisible(False)
        self._rules_compare_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._rules_compare_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        rules_layout.addWidget(self._rules_compare_hint)
        rules_layout.addWidget(self._rules_compare_table)
        self._rules_compare_group.setLayout(rules_layout)

        # Détails source (ligne complète au clic)
        self._source_details_group = QGroupBox("Détails de la ligne source sélectionnée")
        source_layout = QVBoxLayout()
        self._source_details_scroll = QScrollArea()
        self._source_details_scroll.setWidgetResizable(True)
        self._source_details_container = QWidget()
        self._source_details_layout = QVBoxLayout(self._source_details_container)
        self._source_details_layout.addWidget(
            QLabel("Sélectionnez une proposition pour voir la ligne source complète.")
        )
        self._source_details_scroll.setWidget(self._source_details_container)
        source_layout.addWidget(self._source_details_scroll)
        self._source_details_group.setLayout(source_layout)
        candidates_splitter = QSplitter(Qt.Orientation.Vertical)
        candidates_top = QWidget()
        candidates_top_layout = QVBoxLayout(candidates_top)
        candidates_top_layout.setContentsMargins(0, 0, 0, 0)
        candidates_top_layout.addWidget(explanation)
        candidates_top_layout.addWidget(self._candidates_table)
        candidates_top_layout.addWidget(accept_btn)
        candidates_splitter.addWidget(candidates_top)
        candidates_splitter.addWidget(self._rules_compare_group)
        candidates_splitter.addWidget(self._source_details_group)
        candidates_splitter.setSizes([420, 160, 160])
        candidates_layout.addWidget(candidates_splitter)

        candidates_group.setLayout(candidates_layout)
        splitter.addWidget(candidates_group)

        # Volet technique (latéral)
        tech_group = QGroupBox("Volet technique")
        tech_layout = QVBoxLayout()
        self._tech_status = QLabel("Sélectionnez une ligne pour voir les détails techniques.")
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
        tech_group.setLayout(tech_layout)
        splitter.addWidget(tech_group)

        splitter.setSizes([340, 760, 240])
        layout.addWidget(splitter)

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
        self._bulk_spin = QDoubleSpinBox()
        self._bulk_spin.setRange(0, 100)
        self._bulk_spin.setValue(95)
        bulk_btn = QPushButton("Bulk accept >= X")
        bulk_btn.clicked.connect(self._bulk_accept)
        actions.addWidget(self._accept1_btn)
        actions.addWidget(self._reject_btn)
        actions.addWidget(self._skip_btn)
        actions.addWidget(self._undo_btn)
        actions.addWidget(self._auto100_btn)
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
        for s in shortcuts:
            s.setAutoRepeat(False)  # Évite les plantages quand on reste appuyé sur une touche
        select_all_shortcut = QShortcut(QKeySequence("Ctrl+A"), self, self._select_all_visible)
        select_all_shortcut.setAutoRepeat(False)

    def _focus_accept1(self) -> None:
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
        self._queue_model.set_data(results, df_target, preview_cols)
        # Éviter resizeColumnsToContents sur gros volumes (très lent, peut faire planter)
        if len(results) < 500:
            self._queue_table.resizeColumnsToContents()
        self._queue_proxy.setFilterKeyColumn(-1)
        self._queue_proxy.set_score_threshold(self._triage_spin.value())
        self._on_filter_changed(self._filter_combo.currentText())
        self._update_rules_summary()
        self._update_triage_stats()
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

    def _update_rules_summary(self) -> None:
        rules_text = self._format_rules_summary()
        summary = "Comparé: " + rules_text
        max_len = 140
        if len(summary) > max_len:
            display = summary[: max_len - 1] + "…"
        else:
            display = summary
        self._rules_summary_label.setText(display)
        self._rules_summary_label.setToolTip(summary)

    def _format_transfer_summary(self) -> str:
        config = getattr(self._state, "config", None)
        if config is not None:
            cols = list(getattr(config, "transfer_columns", []) or [])
            rename = getattr(config, "transfer_column_rename", {}) or {}
        else:
            config_dict = getattr(self._state, "config_dict", {})
            cols = list(config_dict.get("transfer_columns", []) or [])
            rename = config_dict.get("transfer_column_rename", {}) or {}
        if not cols:
            return "Aucune colonne à transférer."
        base = ", ".join(cols)
        if rename:
            renames = ", ".join(f"{k}→{v}" for k, v in rename.items())
            return f"{base} (renommage: {renames})"
        return base

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

    def _ordered_columns(self, df: pd.DataFrame, preferred: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for col in preferred:
            if col in df.columns and col not in seen:
                ordered.append(col)
                seen.add(col)
        for col in df.columns:
            if col not in seen:
                ordered.append(col)
        return ordered

    def _format_value(self, val: object, limit: int = 160) -> str:
        if val is None or (isinstance(val, float) and (val != val or val == float("inf"))):
            return ""
        text = str(val)
        return text if len(text) <= limit else text[:limit] + "..."

    def _get_cell_value(self, df: pd.DataFrame, row_idx: int, col: str) -> str:
        if col not in df.columns or row_idx < 0 or row_idx >= len(df):
            return ""
        val = df.iloc[row_idx][col]
        return self._format_value(val)

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

    def _on_search_changed(self, text: str) -> None:
        """Applique la recherche texte."""
        self._queue_proxy.set_search_text(text)

    def _select_all_visible(self) -> None:
        """Coche toutes les lignes actuellement visibles (selon le filtre)."""
        visible_ids: list[int] = []
        for proxy_row in range(self._queue_proxy.rowCount()):
            src_idx = self._queue_proxy.mapToSource(self._queue_proxy.index(proxy_row, 0))
            if src_idx.isValid():
                result = self._queue_model.get_result_at_row(src_idx.row())
                if result is not None:
                    visible_ids.append(result.target_row_id)
        if visible_ids:
            self._queue_model.select_visible_ids(visible_ids)

    def _clear_selection(self) -> None:
        """Décoche toutes les lignes."""
        self._queue_model.clear_selection()

    def _on_threshold_changed(self, _value: float | None = None) -> None:
        """Met à jour le seuil de triage."""
        self._queue_proxy.set_score_threshold(self._triage_spin.value())
        self._update_triage_stats()
        status = self._filter_combo.currentData()
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

    def _update_triage_stats(self) -> None:
        results = getattr(self._state, "results", [])
        pending = [r for r in results if r.status == "pending"]
        total = len(pending)
        threshold = self._triage_spin.value()
        review = sum(1 for r in pending if r.best_score >= threshold)
        low = total - review
        self._triage_stats.setText(
            f"En attente: {total} | À valider (≥{threshold:.1f}): {review} | Probable non-match (<{threshold:.1f}): {low}"
        )

    def _on_queue_selection_changed(self) -> None:
        """Met à jour les détails et candidats quand la sélection change."""
        idx = self._queue_table.currentIndex()
        if not idx.isValid():
            self._show_details(None)
            self._candidates_model.set_result(None, pd.DataFrame(), [])
            self._current_result = None
            self._current_candidate = None
            self._reset_candidate_panels()
            self._update_tech_panel(None, None)
            return
        src_row = self._queue_proxy.mapToSource(idx).row()
        result = self._queue_model.get_result_at_row(src_row)
        if result:
            self._show_details(result)
            df_src = self._safe_get_df("df_source")
            self._candidates_model.set_result(result, df_src, self._get_source_preview_cols())
            # Peu de candidats (top_k), resize OK
            self._candidates_table.resizeColumnsToContents()
            self._candidates_table.resizeRowsToContents()
            self._current_result = result
            # Sélection automatique du meilleur candidat (première ligne = plus fort score)
            if self._candidates_model.rowCount() > 0:
                self._candidates_table.setCurrentIndex(self._candidates_model.index(0, 0))
                best_candidate = self._candidates_model.get_candidate_at_row(0)
                self._current_candidate = best_candidate
                self._update_rules_comparison(result, best_candidate, 1)
                self._show_source_details(best_candidate.source_row_id)
                self._update_tech_panel(result, best_candidate)
            else:
                self._current_candidate = None
                self._reset_candidate_panels()
                self._update_tech_panel(result, None)
        else:
            self._show_details(None)
            self._candidates_model.set_result(None, pd.DataFrame(), [])
            self._current_result = None
            self._current_candidate = None
            self._reset_candidate_panels()
            self._update_tech_panel(None, None)

    def _show_details(self, result: MatchResult | None) -> None:
        """Affiche les détails de la ligne cible."""
        for i in reversed(range(self._details_layout.count())):
            w = self._details_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        if result is None:
            self._details_layout.addWidget(QLabel("Sélectionnez une ligne dans la file d'attente à gauche."))
            return
        df = self._safe_get_df("df_target")
        if result.target_row_id >= len(df):
            self._details_layout.addWidget(QLabel("Données indisponibles."))
            return
        row = df.iloc[result.target_row_id]
        grid = QGridLayout()
        _, rule_target_cols = self._get_rule_columns()
        cols = self._ordered_columns(df, rule_target_cols)
        for i, col in enumerate(cols):
            val = row[col]
            label = QLabel(str(col) + ":")
            if col in rule_target_cols:
                label.setStyleSheet("font-weight: 600;")
            value = QLabel("" if pd.isna(val) else self._format_value(val))
            value.setWordWrap(True)
            grid.addWidget(label, i, 0)
            grid.addWidget(value, i, 1)
        container = QWidget()
        container.setLayout(grid)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self._details_layout.addWidget(scroll)

    def _on_queue_double_clicked(self, index: QModelIndex) -> None:
        """Double-clic sur la file d'attente : accepter le premier candidat."""
        self._accept_candidate(0)

    def _on_candidate_double_clicked(self, index: QModelIndex) -> None:
        """Double-clic sur un candidat : l'accepter."""
        self._accept_candidate(index.row())

    def _on_candidate_selection_changed(self) -> None:
        """Met à jour la comparaison et les détails source au clic sur un candidat."""
        idx = self._candidates_table.currentIndex()
        if not idx.isValid() or self._current_result is None:
            self._reset_candidate_panels()
            return
        candidate = self._candidates_model.get_candidate_at_row(idx.row())
        if candidate is None:
            self._reset_candidate_panels()
            self._update_tech_panel(self._current_result, None)
            return
        self._current_candidate = candidate
        self._update_rules_comparison(self._current_result, candidate, idx.row() + 1)
        self._show_source_details(candidate.source_row_id)
        self._update_tech_panel(self._current_result, candidate)

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
                self._on_queue_selection_changed()
                self._update_triage_stats()
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
                self._on_queue_selection_changed()
                self._update_triage_stats()
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
                self._update_triage_stats()
                break

    def _bulk_accept(self) -> None:
        """Accepte en masse les pending non ambigus au-dessus du seuil."""
        threshold = self._bulk_spin.value()
        results = getattr(self._state, "results", [])
        choices = getattr(self._state, "choices", {})
        count = 0
        for r in results:
            if r.status != "pending" or r.is_ambiguous:
                continue
            if not r.candidates or r.candidates[0].score < threshold:
                continue
            chosen = r.candidates[0].source_row_id
            choices[r.target_row_id] = chosen
            r.chosen_source_row_id = chosen
            r.status = "accepted"
            r.explanation = "Bulk accept"
            self._queue_model.update_result(r.target_row_id, chosen)
            count += 1
        if count > 0:
            QMessageBox.information(self, "Bulk accept", f"{count} lignes acceptées.")
        self._update_triage_stats()

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
        self._update_triage_stats()

    def _on_finalize_clicked(self) -> None:
        """Finalise la validation et appelle resolve_pending."""
        self._on_finalize()

    def _reset_candidate_panels(self) -> None:
        """Réinitialise la comparaison et les détails source."""
        self._rules_compare_table.setRowCount(0)
        self._rules_compare_hint.setText(
            "Sélectionnez une proposition pour voir la comparaison par règle (cible ↔ source)."
        )
        self._reset_source_details("Sélectionnez une proposition pour voir la ligne source complète.")

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

    def _reset_source_details(self, text: str) -> None:
        for i in reversed(range(self._source_details_layout.count())):
            w = self._source_details_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        placeholder = QLabel(text)
        placeholder.setWordWrap(True)
        self._source_details_layout.addWidget(placeholder)

    def _update_rules_comparison(
        self, result: MatchResult, candidate, rank: int
    ) -> None:
        rules = self._get_rules()
        if not rules:
            self._rules_compare_table.setRowCount(0)
            self._rules_compare_hint.setText("Aucune règle définie.")
            return
        self._rules_compare_hint.setText(f"Comparaison pour la proposition #{rank}.")
        df_target = self._safe_get_df("df_target")
        df_source = self._safe_get_df("df_source")
        self._rules_compare_table.setRowCount(len(rules))
        for i, rule in enumerate(rules):
            if hasattr(rule, "source_col"):
                src = rule.source_col
                tgt = rule.target_col
            else:
                src = rule.get("source_col", "")
                tgt = rule.get("target_col", "")
            rule_label = f"{src} → {tgt}" if src or tgt else "—"
            tgt_val = self._get_cell_value(df_target, result.target_row_id, tgt)
            src_val = self._get_cell_value(df_source, candidate.source_row_id, src)
            score = candidate.details.get(f"{src}:{tgt}") if src and tgt else None
            score_text = f"{score:.1f}" if isinstance(score, (int, float)) else ""
            items = [
                QTableWidgetItem(rule_label),
                QTableWidgetItem(tgt_val),
                QTableWidgetItem(src_val),
                QTableWidgetItem(score_text),
            ]
            for col_idx, item in enumerate(items):
                if col_idx == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._rules_compare_table.setItem(i, col_idx, item)

    def _show_source_details(self, source_row_id: int) -> None:
        df = self._safe_get_df("df_source")
        if source_row_id < 0 or source_row_id >= len(df):
            self._reset_source_details("Données source indisponibles.")
            return
        row = df.iloc[source_row_id]
        rule_source_cols, _ = self._get_rule_columns()
        cols = self._ordered_columns(df, rule_source_cols)
        grid = QGridLayout()
        for i, col in enumerate(cols):
            val = row[col]
            label = QLabel(str(col) + ":")
            if col in rule_source_cols:
                label.setStyleSheet("font-weight: 600;")
            value = QLabel("" if pd.isna(val) else self._format_value(val))
            value.setWordWrap(True)
            grid.addWidget(label, i, 0)
            grid.addWidget(value, i, 1)
        for i in reversed(range(self._source_details_layout.count())):
            w = self._source_details_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        container = QWidget()
        container.setLayout(grid)
        self._source_details_layout.addWidget(container)
