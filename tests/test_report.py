"""Tests du module report."""

import pytest

from laconcorde.config import Config, FieldRule
from laconcorde.matching.schema import MatchCandidate, MatchResult
from laconcorde.report import build_report_df, print_report_console


@pytest.fixture
def sample_results() -> list[MatchResult]:
    return [
        MatchResult(0, [MatchCandidate(0, 98, {})], 98, False, "auto", 0, "Auto-accept"),
        MatchResult(1, [MatchCandidate(1, 85, {})], 85, False, "accepted", 1, "User accepted"),
        MatchResult(2, [], 0, False, "rejected", None, "No match"),
        MatchResult(
            3,
            [MatchCandidate(2, 90, {}), MatchCandidate(3, 88, {})],
            90,
            True,
            "pending",
            None,
            "Ambiguous",
        ),
    ]


@pytest.fixture
def sample_config() -> Config:
    return Config(
        rules=[FieldRule("a", "b", 1.0, "fuzzy_ratio", True)],
        transfer_columns=["notes"],
        min_score=0.0,
        auto_accept_score=95.0,
        top_k=5,
        ambiguity_delta=5.0,
        blocker="year_or_initial",
        overwrite_mode="if_empty",
    )


def test_build_report_df_counts(sample_results: list[MatchResult], sample_config: Config) -> None:
    df = build_report_df(sample_results, sample_config)
    assert "nb_target_rows" in df["Key"].values
    assert df[df["Key"] == "nb_target_rows"]["Value"].values[0] == 4
    assert df[df["Key"] == "nb_auto"]["Value"].values[0] == 1
    assert df[df["Key"] == "nb_accepted"]["Value"].values[0] == 1
    assert df[df["Key"] == "nb_rejected_no_match"]["Value"].values[0] == 1
    assert df[df["Key"] == "nb_pending"]["Value"].values[0] == 1
    assert df[df["Key"] == "nb_ambiguous"]["Value"].values[0] == 1


def test_build_report_df_contains_params(sample_results: list[MatchResult], sample_config: Config) -> None:
    df = build_report_df(sample_results, sample_config)
    keys = df["Key"].tolist()
    assert "auto_accept_score" in keys
    assert "blocker" in keys
    assert "version" in keys
    assert "timestamp" in keys


def test_print_report_console_no_error(
    sample_results: list[MatchResult], sample_config: Config, capsys: pytest.CaptureFixture
) -> None:
    print_report_console(sample_results, sample_config)
    out = capsys.readouterr().out
    assert "LaConcorde Report" in out
    assert "Lignes cible" in out
    assert "4" in out
