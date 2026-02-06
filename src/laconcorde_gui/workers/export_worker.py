"""Worker pour exécuter l'export dans un thread."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

import pandas as pd

from laconcorde.config import Config
from laconcorde.matching.schema import MatchResult
from laconcorde.report import build_report_df
from laconcorde.transfer import build_mapping_csv, transfer_columns


class ExportWorker(QThread):
    """Thread exécutant transfer_columns + save_xlsx + build_mapping_csv."""

    finished = Signal(str, str, object)  # out_xlsx, out_csv, report_df
    error = Signal(str)
    cancel_requested = False

    def __init__(
        self,
        config: Config,
        df_source: pd.DataFrame,
        df_target: pd.DataFrame,
        results: list[MatchResult],
        out_xlsx: str | Path,
        out_csv: str | Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._df_source = df_source
        self._df_target = df_target
        self._results = results
        self._out_xlsx = Path(out_xlsx)
        self._out_csv = Path(out_csv) if out_csv else self._out_xlsx.parent / "mapping.csv"

    def request_cancel(self) -> None:
        self.cancel_requested = True

    def run(self) -> None:
        self.cancel_requested = False
        try:
            from laconcorde.io_excel import save_xlsx

            df_enriched = transfer_columns(
                self._df_target,
                self._df_source,
                self._results,
                self._config.transfer_columns,
                transfer_column_rename=self._config.transfer_column_rename or None,
                overwrite_mode=self._config.overwrite_mode,
                create_missing_cols=self._config.create_missing_cols,
                suffix_on_collision=self._config.suffix_on_collision,
            )
            if self.cancel_requested:
                self.error.emit("Annulation demandée")
                return
            report_df = build_report_df(self._results, self._config)
            save_xlsx(self._out_xlsx, {"Target": df_enriched, "REPORT": report_df})
            build_mapping_csv(self._results, str(self._out_csv))
            if self.cancel_requested:
                self.error.emit("Annulation demandée")
                return
            self.finished.emit(str(self._out_xlsx), str(self._out_csv), report_df)
        except Exception as e:
            self.error.emit(str(e))
