"""Tests des stratégies de blocking."""

import pandas as pd

from concordx.config import FieldRule
from concordx.matching.blockers import (
    build_blocks,
    get_block_key_year_or_initial,
    get_candidate_source_indices,
)


def rules_with_year() -> list[FieldRule]:
    return [
        FieldRule("auteur", "author", 1.0, "fuzzy_ratio", True),
        FieldRule("annee", "year", 1.0, "exact", True),
    ]


def rules_without_year() -> list[FieldRule]:
    return [
        FieldRule("auteur", "author", 1.0, "fuzzy_ratio", True),
        FieldRule("titre", "title", 1.0, "fuzzy_ratio", True),
    ]


def test_block_key_year() -> None:
    df = pd.DataFrame({"annee": ["2020"], "auteur": ["Dupont"]})
    cols = set(df.columns)
    key = get_block_key_year_or_initial(df.iloc[0], rules_with_year(), cols, cols, df, is_source=True)
    assert key == "y_2020"


def test_block_key_initial_fallback() -> None:
    df = pd.DataFrame({"auteur": ["Martin"], "titre": ["Intro"]})
    cols = set(df.columns)
    key = get_block_key_year_or_initial(df.iloc[0], rules_without_year(), cols, cols, df, is_source=True)
    assert key == "i_m"


def test_block_key_default_empty() -> None:
    df = pd.DataFrame({"x": [""], "y": [""]})
    rules = [FieldRule("x", "y", 1.0, "exact", True)]
    cols = set(df.columns)
    key = get_block_key_year_or_initial(df.iloc[0], rules, cols, cols, df, is_source=True)
    assert key == "default"


def test_build_blocks_year() -> None:
    df = pd.DataFrame(
        {
            "annee": ["2020", "2021", "2020"],
            "auteur": ["A", "B", "C"],
        }
    )
    blocks = build_blocks(df, rules_with_year(), is_source=True)
    assert "y_2020" in blocks
    assert "y_2021" in blocks
    assert len(blocks["y_2020"]) == 2
    assert len(blocks["y_2021"]) == 1


def test_get_candidate_source_indices() -> None:
    df_source = pd.DataFrame(
        {
            "annee": ["2020", "2020", "2021"],
            "author": ["A", "B", "C"],
        }
    )
    df_target = pd.DataFrame(
        {
            "year": ["2020"],
            "author": ["A"],
        }
    )
    source_blocks = build_blocks(df_source, rules_with_year(), is_source=True)
    target_row = df_target.iloc[0]
    indices = get_candidate_source_indices(
        target_row,
        0,
        source_blocks,
        rules_with_year(),
        set(df_source.columns),
        set(df_target.columns),
        df_source,
        df_target,
    )
    assert indices == [0, 1]
    assert 2 not in indices
