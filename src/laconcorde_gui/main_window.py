"""Fenêtre principale : navigation et orchestration."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from laconcorde_gui.controllers import PipelineController, SessionController
from laconcorde_gui.screens import ExportScreen, ProjectScreen, RulesScreen, ValidationScreen
from laconcorde_gui.state import AppState
from laconcorde_gui.workers import ExportWorker, MatchingWorker


class MainWindow(QMainWindow):
    """Fenêtre principale avec navigation entre écrans."""

    SCREEN_PROJECT = 0
    SCREEN_RULES = 1
    SCREEN_VALIDATION = 2
    SCREEN_EXPORT = 3

    def __init__(self) -> None:
        super().__init__()
        self._state = AppState()
        self._session_ctrl = SessionController(self._state)
        self._matching_worker: MatchingWorker | None = None
        self._export_worker: ExportWorker | None = None
        self._progress: QProgressDialog | None = None
        self._setup_ui()
        self._connect_screens()

    def _setup_ui(self) -> None:
        self.setWindowTitle("LaConcorde - Record Linkage")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        central = QWidget()
        layout = QVBoxLayout(central)

        nav = QHBoxLayout()
        btn_proj = QPushButton("1. Projet")
        btn_proj.clicked.connect(lambda: self._go_to(self.SCREEN_PROJECT))
        btn_rules = QPushButton("2. Règles")
        btn_rules.clicked.connect(lambda: self._go_to(self.SCREEN_RULES))
        btn_valid = QPushButton("3. Validation")
        btn_valid.clicked.connect(lambda: self._go_to(self.SCREEN_VALIDATION))
        btn_export = QPushButton("4. Export")
        btn_export.clicked.connect(lambda: self._go_to(self.SCREEN_EXPORT))
        nav.addWidget(btn_proj)
        nav.addWidget(btn_rules)
        nav.addWidget(btn_valid)
        nav.addWidget(btn_export)
        nav.addStretch()
        layout.addLayout(nav)

        self._stack = QStackedWidget()
        self._project_screen = ProjectScreen(self._state)
        self._rules_screen = RulesScreen(self._state, on_matching_requested=self._run_matching)
        self._validation_screen = ValidationScreen(
            self._state, on_finalize_requested=self._on_validation_finalized
        )
        self._export_screen = ExportScreen(self._state, on_export_requested=self._run_export)

        self._stack.addWidget(self._project_screen)
        self._stack.addWidget(self._rules_screen)
        self._stack.addWidget(self._validation_screen)
        self._stack.addWidget(self._export_screen)

        layout.addWidget(self._stack)
        self.setCentralWidget(central)

    def _connect_screens(self) -> None:
        """Connecte les écrans à la navigation."""
        pass

    def _go_to(self, index: int) -> None:
        """Change d'écran."""
        if index == self.SCREEN_RULES:
            self._rules_screen.refresh_from_state()
        elif index == self.SCREEN_VALIDATION and self._state.results:
            self._validation_screen.refresh_data()
        self._stack.setCurrentIndex(index)

    def _run_matching(self) -> None:
        """Lance le matching dans un worker."""
        config_dict = self._state.build_config_dict()
        base_dir = Path(".")
        if self._state.source_file:
            base_dir = Path(self._state.source_file).parent
        elif self._state.single_file:
            base_dir = Path(self._state.single_file).parent

        self._progress = QProgressDialog("Matching en cours...", "Annuler", 0, 0, self)
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.canceled.connect(self._on_matching_canceled)

        self._matching_worker = MatchingWorker(config_dict, base_dir, self)
        self._matching_worker.finished.connect(self._on_matching_finished)
        self._matching_worker.error.connect(self._on_matching_error)
        self._matching_worker.start()
        self._progress.show()

    def _on_matching_canceled(self) -> None:
        if self._matching_worker:
            self._matching_worker.request_cancel()

    def _on_matching_finished(
        self, df_source, df_target, results, linker
    ) -> None:
        if self._progress:
            self._progress.close()
            self._progress = None
        try:
            self._state.df_source = df_source
            self._state.df_target = df_target
            self._state.results = results
            self._state.linker = linker
            self._state.config = linker.config
            self._state.choices = {}
            self._state.undo_stack = []
            self._go_to(self.SCREEN_VALIDATION)
            self._validation_screen.refresh_data()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'afficher les résultats ({len(results)} lignes).\n\n{e}\n\n"
                "Essayez un filtre plus restrictif ou vérifiez la mémoire disponible.",
            )

    def _on_matching_error(self, msg: str) -> None:
        if self._progress:
            self._progress.close()
            self._progress = None
        QMessageBox.critical(self, "Erreur matching", msg)

    def _on_validation_finalized(self) -> None:
        """Appelle resolve_pending et passe à l'export."""
        linker = self._state.linker
        if linker and self._state.results:
            PipelineController.resolve_pending(
                linker, self._state.results, self._state.choices
            )
        self._go_to(self.SCREEN_EXPORT)

    def _run_export(self, xlsx_path: str, csv_path: str | None) -> None:
        """Lance l'export dans un worker."""
        config = self._state.config
        if not config:
            QMessageBox.critical(self, "Erreur", "Configuration manquante. Relancez le matching.")
            return
        if self._state.df_source is None or self._state.df_target is None:
            QMessageBox.critical(self, "Erreur", "Données manquantes.")
            return

        out_csv = csv_path
        if not out_csv:
            out_csv = str(Path(xlsx_path).parent / "mapping.csv")

        self._progress = QProgressDialog("Export en cours...", "Annuler", 0, 0, self)
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.canceled.connect(self._on_export_canceled)

        self._export_worker = ExportWorker(
            config,
            self._state.df_source,
            self._state.df_target,
            self._state.results,
            xlsx_path,
            out_csv,
            self,
        )
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.error.connect(self._on_export_error)
        self._export_worker.start()
        self._progress.show()

    def _on_export_canceled(self) -> None:
        if self._export_worker:
            self._export_worker.request_cancel()

    def _on_export_finished(self, xlsx_path: str, csv_path: str, report_df) -> None:
        if self._progress:
            self._progress.close()
            self._progress = None
        stats = f"Lignes: {len(report_df)}" if report_df is not None else ""
        self._export_screen.set_success(xlsx_path, csv_path, stats)

    def _on_export_error(self, msg: str) -> None:
        if self._progress:
            self._progress.close()
            self._progress = None
        QMessageBox.critical(self, "Erreur export", msg)
