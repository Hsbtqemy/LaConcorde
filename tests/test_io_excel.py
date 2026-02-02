"""Tests du module I/O Excel."""

from pathlib import Path

import pandas as pd

from concordx.config import Config
from concordx.io_excel import list_sheets, load_sheet, load_source_target, save_xlsx


def test_list_sheets(tmp_path: Path) -> None:
    path = tmp_path / "test.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        pd.DataFrame({"a": [1]}).to_excel(w, sheet_name="Feuille1", index=False)
        pd.DataFrame({"x": [1]}).to_excel(w, sheet_name="Feuille2", index=False)
    sheets = list_sheets(path)
    assert "Feuille1" in sheets
    assert "Feuille2" in sheets


def test_load_sheet_default_first(tmp_path: Path) -> None:
    path = tmp_path / "test.xlsx"
    pd.DataFrame({"col": ["a", "b"]}).to_excel(path, index=False, engine="openpyxl")
    df = load_sheet(path)
    assert len(df) == 2
    assert "col" in df.columns


def test_save_xlsx(tmp_path: Path) -> None:
    path = tmp_path / "out.xlsx"
    save_xlsx(path, {"Sheet1": pd.DataFrame({"a": [1]}), "Sheet2": pd.DataFrame({"b": [2]})})
    xl = pd.ExcelFile(path, engine="openpyxl")
    assert "Sheet1" in xl.sheet_names
    assert "Sheet2" in xl.sheet_names
    xl.close()


def test_load_source_target_two_files(tmp_path: Path) -> None:
    src = tmp_path / "source.xlsx"
    tgt = tmp_path / "target.xlsx"
    pd.DataFrame({"a": [1]}).to_excel(src, index=False, engine="openpyxl")
    pd.DataFrame({"b": [2]}).to_excel(tgt, index=False, engine="openpyxl")
    config = Config(source_file=str(src), target_file=str(tgt))
    df_src, df_tgt = load_source_target(config)
    assert "a" in df_src.columns
    assert "b" in df_tgt.columns
