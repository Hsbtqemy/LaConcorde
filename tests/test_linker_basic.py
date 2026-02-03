"""Tests de base du linker."""

import pandas as pd
import pytest

from laconcorde.config import Config, FieldRule
from laconcorde.matching.linker import Linker


@pytest.fixture
def mini_source() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "auteur": ["Dupont", "Martin", "Bernard"],
            "titre": ["Introduction", "Méthodes", "Conclusion"],
            "annee": ["2020", "2021", "2020"],
        }
    )


@pytest.fixture
def mini_target() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "author": ["Dupont", "Martin"],
            "title": ["Introduction", "Methodes"],
            "year": ["2020", "2021"],
        }
    )


@pytest.fixture
def mini_config() -> Config:
    return Config(
        source_file="",
        target_file="",
        rules=[
            FieldRule("auteur", "author", 1.0, "fuzzy_ratio", True),
            FieldRule("titre", "title", 1.0, "fuzzy_ratio", True),
            FieldRule("annee", "year", 1.0, "exact", True),
        ],
        transfer_columns=[],
        auto_accept_score=95.0,
        top_k=3,
        ambiguity_delta=5.0,
        blocker="year_or_initial",
    )


def test_linker_exact_match(mini_source: pd.DataFrame, mini_target: pd.DataFrame, mini_config: Config) -> None:
    linker = Linker(mini_config)
    results = linker.run(mini_source, mini_target)
    assert len(results) == 2
    assert results[0].status == "auto"
    assert results[0].chosen_source_row_id == 0
    assert results[0].best_score >= 95


def test_linker_fuzzy_match(mini_source: pd.DataFrame, mini_target: pd.DataFrame, mini_config: Config) -> None:
    linker = Linker(mini_config)
    results = linker.run(mini_source, mini_target)
    # Martin / Methodes vs Martin / Méthodes : fuzzy devrait matcher
    assert results[1].best_score > 80
    assert results[1].chosen_source_row_id == 1
