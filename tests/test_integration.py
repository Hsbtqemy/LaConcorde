"""Test d'intégration du pipeline LaConcorde."""

import json
from pathlib import Path

import pandas as pd

from laconcorde.cli import cmd_run


def test_full_pipeline_dry_run(tmp_path: Path) -> None:
    """Exécute le pipeline complet en mode dry-run avec fichiers créés à la volée."""
    src = tmp_path / "source.xlsx"
    tgt = tmp_path / "target.xlsx"
    config_path = tmp_path / "config.json"
    mapping_path = tmp_path / "mapping.csv"

    # Créer des données de test
    df_src = pd.DataFrame(
        {
            "auteur": ["Dupont", "Martin", "Bernard"],
            "titre": ["Introduction", "Méthodes", "Conclusion"],
            "annee": ["2020", "2021", "2020"],
            "notes": ["n1", "n2", "n3"],
        }
    )
    df_tgt = pd.DataFrame(
        {
            "author": ["Dupont", "Martin"],
            "title": ["Introduction", "Methodes"],
            "year": ["2020", "2021"],
        }
    )
    df_src.to_excel(src, index=False, engine="openpyxl")
    df_tgt.to_excel(tgt, index=False, engine="openpyxl")

    src_str = src.as_posix()
    tgt_str = tgt.as_posix()
    config_content = f'''{{
        "source_file": "{src_str}",
        "target_file": "{tgt_str}",
        "rules": [
            {{"source_col": "auteur", "target_col": "author", "weight": 1.0,
              "method": "fuzzy_ratio", "normalize": true}},
            {{"source_col": "titre", "target_col": "title", "weight": 1.0,
              "method": "fuzzy_ratio", "normalize": true}},
            {{"source_col": "annee", "target_col": "year", "weight": 1.0,
              "method": "exact", "normalize": true}}
        ],
        "transfer_columns": ["notes"],
        "auto_accept_score": 95.0,
        "blocker": "year_or_initial"
    }}'''
    config_path.write_text(config_content, encoding="utf-8")

    exit_code = cmd_run(
        str(config_path),
        None,
        dry_run=True,
        interactive=False,
        mapping_path=str(mapping_path),
    )
    assert exit_code == 0
    assert mapping_path.exists()
    mapping_df = pd.read_csv(mapping_path)
    assert len(mapping_df) == 2
    assert "target_row_id" in mapping_df.columns
    assert "source_row_id" in mapping_df.columns
    assert "status" in mapping_df.columns


def test_full_pipeline_with_output(tmp_path: Path) -> None:
    """Exécute le pipeline avec écriture du fichier de sortie."""
    src = tmp_path / "source.xlsx"
    tgt = tmp_path / "target.xlsx"
    out = tmp_path / "output.xlsx"
    config_path = tmp_path / "config.json"

    df_src = pd.DataFrame(
        {
            "auteur": ["Dupont"],
            "titre": ["Intro"],
            "annee": ["2020"],
            "notes": ["ma note"],
        }
    )
    df_tgt = pd.DataFrame(
        {
            "author": ["Dupont"],
            "title": ["Intro"],
            "year": ["2020"],
        }
    )
    df_src.to_excel(src, index=False, engine="openpyxl")
    df_tgt.to_excel(tgt, index=False, engine="openpyxl")

    src_str = src.as_posix()
    tgt_str = tgt.as_posix()
    config_content = f'''{{
        "source_file": "{src_str}",
        "target_file": "{tgt_str}",
        "rules": [
            {{"source_col": "auteur", "target_col": "author", "weight": 1.0, "method": "exact", "normalize": true}},
            {{"source_col": "annee", "target_col": "year", "weight": 1.0, "method": "exact", "normalize": true}}
        ],
        "transfer_columns": ["notes"],
        "auto_accept_score": 90.0,
        "blocker": "year_or_initial"
    }}'''
    config_path.write_text(config_content, encoding="utf-8")

    exit_code = cmd_run(str(config_path), str(out), dry_run=False, interactive=False)
    assert exit_code == 0
    assert out.exists()

    xl = pd.ExcelFile(out, engine="openpyxl")
    assert "Target" in xl.sheet_names
    assert "REPORT" in xl.sheet_names
    df_target = pd.read_excel(out, sheet_name="Target")
    assert "notes" in df_target.columns
    assert df_target.iloc[0]["notes"] == "ma note"


def test_mapping_path_priority(tmp_path: Path) -> None:
    """--mapping prime sur le chemin déduit de --output."""
    src = tmp_path / "source.xlsx"
    tgt = tmp_path / "target.xlsx"
    out = tmp_path / "out" / "output.xlsx"
    custom_mapping = tmp_path / "custom_dir" / "mapping.csv"
    out.parent.mkdir()
    custom_mapping.parent.mkdir()
    config_path = tmp_path / "config.json"

    pd.DataFrame({"auteur": ["A"], "annee": ["2020"]}).to_excel(src, index=False, engine="openpyxl")
    pd.DataFrame({"author": ["A"], "year": ["2020"]}).to_excel(tgt, index=False, engine="openpyxl")
    config = {
        "source_file": str(src),
        "target_file": str(tgt),
        "rules": [
            {
                "source_col": "auteur",
                "target_col": "author",
                "weight": 1.0,
                "method": "exact",
                "normalize": True,
            },
            {
                "source_col": "annee",
                "target_col": "year",
                "weight": 1.0,
                "method": "exact",
                "normalize": True,
            },
        ],
        "transfer_columns": [],
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    exit_code = cmd_run(
        str(config_path),
        str(out),
        dry_run=False,
        mapping_path=str(custom_mapping),
    )
    assert exit_code == 0
    assert custom_mapping.exists()
    assert not (out.parent / "mapping.csv").exists()
