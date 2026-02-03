"""Tests du transfert de colonnes."""

import pandas as pd
import pytest

from laconcorde.matching.schema import MatchCandidate, MatchResult
from laconcorde.transfer import transfer_columns


@pytest.fixture
def df_source() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "auteur": ["A", "B", "C"],
            "notes": ["n1", "n2", "n3"],
            "categorie": ["cat1", "cat2", "cat3"],
        }
    )


@pytest.fixture
def df_target() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "author": ["A", "B"],
            "title": ["T1", "T2"],
        }
    )


@pytest.fixture
def results_simple() -> list[MatchResult]:
    return [
        MatchResult(0, [MatchCandidate(0, 100, {})], 100, False, "auto", 0, ""),
        MatchResult(1, [MatchCandidate(1, 100, {})], 100, False, "auto", 1, ""),
    ]


def test_transfer_if_empty(df_source: pd.DataFrame, df_target: pd.DataFrame, results_simple: list[MatchResult]) -> None:
    out = transfer_columns(
        df_target,
        df_source,
        results_simple,
        ["notes", "categorie"],
        overwrite_mode="if_empty",
        create_missing_cols=True,
    )
    assert "notes" in out.columns
    assert "categorie" in out.columns
    assert out.iloc[0]["notes"] == "n1"
    assert out.iloc[1]["notes"] == "n2"
    assert out.iloc[0]["categorie"] == "cat1"


def test_transfer_never_overwrite(
    df_source: pd.DataFrame, df_target: pd.DataFrame, results_simple: list[MatchResult]
) -> None:
    df_target["notes"] = ["existing1", "existing2"]
    out = transfer_columns(
        df_target,
        df_source,
        results_simple,
        ["notes"],
        overwrite_mode="never",
        create_missing_cols=True,
        suffix_on_collision="_src",
    )
    assert "notes_src" in out.columns
    assert out.iloc[0]["notes"] == "existing1"
    assert out.iloc[0]["notes_src"] == "n1"


def test_transfer_always_overwrite(
    df_source: pd.DataFrame, df_target: pd.DataFrame, results_simple: list[MatchResult]
) -> None:
    df_target["notes"] = ["old1", "old2"]
    out = transfer_columns(
        df_target,
        df_source,
        results_simple,
        ["notes"],
        overwrite_mode="always",
        create_missing_cols=True,
    )
    assert out.iloc[0]["notes"] == "n1"
    assert out.iloc[1]["notes"] == "n2"


def test_transfer_column_rename(
    df_source: pd.DataFrame, df_target: pd.DataFrame, results_simple: list[MatchResult]
) -> None:
    """transfer_column_rename renomme les colonnes lors du transfert."""
    out = transfer_columns(
        df_target,
        df_source,
        results_simple,
        ["notes", "categorie"],
        transfer_column_rename={"notes": "commentaires", "categorie": "cat"},
        overwrite_mode="if_empty",
        create_missing_cols=True,
    )
    assert "commentaires" in out.columns
    assert "cat" in out.columns
    assert "notes" not in out.columns
    assert "categorie" not in out.columns
    assert out.iloc[0]["commentaires"] == "n1"
    assert out.iloc[0]["cat"] == "cat1"
