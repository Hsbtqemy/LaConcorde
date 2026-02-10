"""Worker pour exécuter l'export Template Builder dans un thread."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from laconcorde.template_builder import TemplateBuilderConfig, export_output


class TemplateBuilderWorker(QThread):
    """Thread exécutant le build/export du Template Builder."""

    finished = Signal(str)  # output_path
    error = Signal(str)
    cancel_requested = False

    def __init__(
        self,
        config_dict: dict,
        out_xlsx: str | Path,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config_dict = config_dict
        self._out_xlsx = Path(out_xlsx)

    def request_cancel(self) -> None:
        self.cancel_requested = True

    def run(self) -> None:
        self.cancel_requested = False
        try:
            config = TemplateBuilderConfig.from_dict(self._config_dict)
            if self.cancel_requested:
                self.error.emit("Annulation demandée")
                return
            export_output(config, self._out_xlsx)
            if self.cancel_requested:
                self.error.emit("Annulation demandée")
                return
            self.finished.emit(str(self._out_xlsx))
        except Exception as e:
            self.error.emit(str(e))
