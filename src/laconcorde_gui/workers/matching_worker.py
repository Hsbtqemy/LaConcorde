"""Worker pour exécuter le matching dans un thread."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from laconcorde.config import Config
from laconcorde.io_excel import load_source_target
from laconcorde.matching.linker import Linker


class MatchingWorker(QThread):
    """Thread exécutant load_source_target + Linker.run()."""

    finished = Signal(object, object, object, object)  # df_source, df_target, results, linker
    error = Signal(str)
    cancel_requested = False

    def __init__(self, config_dict: dict, base_dir: Path | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config_dict = config_dict
        self._base_dir = base_dir or Path(".")

    def request_cancel(self) -> None:
        """Demande l'annulation (best-effort, Linker non interruptible)."""
        self.cancel_requested = True

    def run(self) -> None:
        """Exécute le matching."""
        self.cancel_requested = False
        try:
            config = Config.from_dict(self._config_dict)
            config.resolve_paths(self._base_dir)
            df_source, df_target = load_source_target(config)
            if self.cancel_requested:
                self.error.emit("Annulation demandée")
                return
            linker = Linker(config)
            results = linker.run(df_source, df_target)
            if self.cancel_requested:
                self.error.emit("Annulation demandée")
                return
            self.finished.emit(df_source, df_target, results, linker)
        except Exception as e:
            self.error.emit(str(e))
