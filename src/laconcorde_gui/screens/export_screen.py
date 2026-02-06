"""Écran Export : chemin sortie, options, exécution."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from laconcorde_gui.state import AppState


class ExportScreen(QWidget):
    """Écran d'export : choix chemins et lancement."""

    def __init__(
        self,
        state: object,
        on_export_requested: Callable[[str, str | None], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._on_export_requested = on_export_requested or (lambda x, y: None)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        out_group = QGroupBox("Fichiers de sortie")
        out_layout = QFormLayout()
        self._xlsx_edit = QLineEdit()
        self._xlsx_edit.setPlaceholderText("Chemin fichier xlsx de sortie...")
        xlsx_row = QHBoxLayout()
        xlsx_row.addWidget(self._xlsx_edit)
        browse_xlsx = QPushButton("Parcourir")
        browse_xlsx.clicked.connect(self._browse_xlsx)
        xlsx_row.addWidget(browse_xlsx)
        out_layout.addRow("xlsx:", xlsx_row)

        self._csv_edit = QLineEdit()
        self._csv_edit.setPlaceholderText("Optionnel (défaut: mapping.csv dans même dossier)")
        csv_row = QHBoxLayout()
        csv_row.addWidget(self._csv_edit)
        browse_csv = QPushButton("Parcourir")
        browse_csv.clicked.connect(self._browse_csv)
        csv_row.addWidget(browse_csv)
        out_layout.addRow("mapping.csv:", csv_row)

        out_group.setLayout(out_layout)
        layout.addWidget(out_group)

        self._export_btn = QPushButton("Exporter")
        self._export_btn.clicked.connect(self._on_export_clicked)
        layout.addWidget(self._export_btn)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        layout.addStretch()

    def _browse_xlsx(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Fichier xlsx de sortie", "", "Excel (*.xlsx)")
        if path:
            self._xlsx_edit.setText(path)

    def _browse_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Fichier mapping CSV", "", "CSV (*.csv)")
        if path:
            self._csv_edit.setText(path)

    def _on_export_clicked(self) -> None:
        xlsx_path = self._xlsx_edit.text().strip()
        if not xlsx_path:
            QMessageBox.warning(self, "Attention", "Indiquez le chemin du fichier xlsx de sortie.")
            return
        if not xlsx_path.endswith(".xlsx"):
            xlsx_path += ".xlsx"
        csv_path = self._csv_edit.text().strip() or None
        self._on_export_requested(xlsx_path, csv_path)

    def set_status(self, text: str) -> None:
        """Affiche un message de statut."""
        self._status_label.setText(text)

    def set_success(self, xlsx_path: str, csv_path: str, stats: str = "") -> None:
        """Affiche le succès de l'export."""
        msg = f"Export réussi:\n- {xlsx_path}\n- {csv_path}"
        if stats:
            msg += f"\n\n{stats}"
        self._status_label.setText(msg)
        QMessageBox.information(self, "Export", msg)
