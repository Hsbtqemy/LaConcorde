"""Tests des cas d'erreur."""

import sys
from pathlib import Path

import pytest

from laconcorde.config import Config, ConfigFileError
from laconcorde.io_excel import ExcelFileError, load_sheet


def test_config_load_file_not_found(tmp_path: Path) -> None:
    """Config.load() lève ConfigFileError si le fichier n'existe pas."""
    missing = tmp_path / "inexistant.json"
    with pytest.raises(ConfigFileError, match="introuvable"):
        Config.load(missing)


def test_config_load_invalid_json(tmp_path: Path) -> None:
    """Config.load() lève ConfigFileError si le JSON est invalide."""
    bad_json = tmp_path / "config.json"
    bad_json.write_text("{ invalid json }", encoding="utf-8")
    with pytest.raises(ConfigFileError, match="JSON invalide"):
        Config.load(bad_json)


def test_config_load_not_dict(tmp_path: Path) -> None:
    """Config.load() lève ConfigFileError si le JSON n'est pas un objet."""
    bad_config = tmp_path / "config.json"
    bad_config.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ConfigFileError, match="objet JSON"):
        Config.load(bad_config)


def test_load_sheet_file_not_found(tmp_path: Path) -> None:
    """load_sheet() lève ExcelFileError si le fichier n'existe pas."""
    missing = tmp_path / "inexistant.xlsx"
    with pytest.raises(ExcelFileError, match="introuvable"):
        load_sheet(missing)


def test_load_sheet_missing_sheet(tmp_path: Path) -> None:
    """load_sheet() lève ExcelFileError si la feuille n'existe pas."""
    import pandas as pd

    xlsx = tmp_path / "test.xlsx"
    pd.DataFrame({"a": [1]}).to_excel(xlsx, sheet_name="Feuille1", index=False, engine="openpyxl")
    with pytest.raises(ExcelFileError, match="Feuille 'Inexistante' introuvable"):
        load_sheet(xlsx, sheet_name="Inexistante")


def test_cli_config_error_exit_code() -> None:
    """La CLI retourne 1 et affiche un message en cas d'erreur."""
    from laconcorde.cli import main

    # Simuler une commande run avec config inexistante
    old_argv = sys.argv
    try:
        sys.argv = ["laconcorde", "run", "--config", "/chemin/inexistant.json", "--dry-run"]
        exit_code = main()
        assert exit_code == 1
    finally:
        sys.argv = old_argv
