"""Tests du module config."""

from pathlib import Path

import pytest

from laconcorde.config import Config, ConfigError, FieldRule


def test_config_resolve_paths(tmp_path: Path) -> None:
    """Les chemins relatifs sont résolus par rapport au dossier du fichier config."""
    config_dir = tmp_path / "mon_projet"
    config_dir.mkdir()
    (config_dir / "data").mkdir()

    config = Config(
        source_file="data/source.xlsx",
        target_file="data/target.xlsx",
        rules=[],
    )
    config.resolve_paths(config_dir)

    assert Path(config.source_file).name == "source.xlsx"
    assert "data" in config.source_file
    assert Path(config.source_file).parent.parent == config_dir.resolve()


def test_config_load_resolves_paths(tmp_path: Path) -> None:
    """Config.load() résout automatiquement les chemins relatifs."""
    (tmp_path / "data").mkdir()
    config_path = tmp_path / "config.json"
    config_path.write_text(
        """
        {
            "source_file": "data/source.xlsx",
            "target_file": "data/target.xlsx",
            "rules": []
        }
    """,
        encoding="utf-8",
    )

    config = Config.load(config_path)
    assert Path(config.source_file).is_absolute()
    assert "data" in config.source_file


def test_config_validation_invalid_method() -> None:
    with pytest.raises(ConfigError, match="method invalide"):
        FieldRule.from_dict({"source_col": "a", "target_col": "b", "method": "invalid"})


def test_config_validation_weight_zero() -> None:
    with pytest.raises(ConfigError, match="weight doit être > 0"):
        FieldRule.from_dict({"source_col": "a", "target_col": "b", "weight": 0})


def test_config_validation_missing_files() -> None:
    with pytest.raises(ConfigError, match="source_file et target_file requis"):
        Config.from_dict({"rules": []})


def test_config_validation_invalid_overwrite_mode() -> None:
    with pytest.raises(ConfigError, match="overwrite_mode invalide"):
        Config.from_dict(
            {
                "source_file": "a.xlsx",
                "target_file": "b.xlsx",
                "overwrite_mode": "invalid",
                "rules": [],
            }
        )


def test_config_validation_score_out_of_range() -> None:
    with pytest.raises(ConfigError, match="auto_accept_score"):
        Config.from_dict(
            {
                "source_file": "a.xlsx",
                "target_file": "b.xlsx",
                "auto_accept_score": 150,
                "rules": [],
            }
        )
