"""Tests des scorers de similarité."""

import pandas as pd

from concordx.config import FieldRule
from concordx.matching.scorers import score_field, score_row_pair


def test_score_field_exact() -> None:
    rule = FieldRule("a", "b", 1.0, "exact", True)
    assert score_field("hello", "hello", rule) == 100.0
    assert score_field("hello", "world", rule) == 0.0


def test_score_field_exact_case_insensitive() -> None:
    rule = FieldRule("a", "b", 1.0, "exact", True)
    assert score_field("Hello", "hello", rule) == 100.0


def test_score_field_fuzzy_ratio() -> None:
    rule = FieldRule("a", "b", 1.0, "fuzzy_ratio", True)
    assert score_field("hello", "hello", rule) == 100.0
    assert score_field("hello", "helo", rule) > 80
    assert score_field("abc", "xyz", rule) < 50


def test_score_field_token_set() -> None:
    rule = FieldRule("a", "b", 1.0, "token_set", True)
    # Ordre des mots différent
    assert score_field("hello world", "world hello", rule) == 100.0


def test_score_field_contains() -> None:
    rule = FieldRule("a", "b", 1.0, "contains", True)
    assert score_field("hello", "hello world", rule) == 100.0
    assert score_field("world", "hello world", rule) == 100.0


def test_score_field_empty_both() -> None:
    rule = FieldRule("a", "b", 1.0, "exact", True)
    assert score_field("", "", rule) == 100.0


def test_score_field_empty_one() -> None:
    rule = FieldRule("a", "b", 1.0, "exact", True)
    assert score_field("hello", "", rule) == 0.0
    assert score_field("", "hello", rule) == 0.0


def test_score_field_doi_normalization() -> None:
    rule = FieldRule("doi", "doi", 2.0, "normalized_exact", True)
    assert score_field("https://doi.org/10.1234/abc", "10.1234/abc", rule) == 100.0


def test_score_field_doi_variants_match() -> None:
    """Formats DOI différents entre tableurs → même normalisation → match."""
    rule = FieldRule("doi", "doi", 2.0, "normalized_exact", True)
    assert score_field("https://doi.org/10.1234/abc?ref=xyz", "10.1234/abc", rule) == 100.0
    assert score_field("10.1234%2Fabc", "10.1234/abc", rule) == 100.0
    assert score_field("10.1234/abc/", "10.1234/abc", rule) == 100.0
    assert score_field("doi:  10.1234 / abc", "10.1234/abc", rule) == 100.0


def test_score_row_pair_weighted() -> None:
    rules = [
        FieldRule("a", "a", 1.0, "exact", True),
        FieldRule("b", "b", 2.0, "exact", True),
    ]
    source = pd.Series({"a": "x", "b": "y"})
    target = pd.Series({"a": "x", "b": "y"})
    score, details = score_row_pair(source, target, rules)
    assert score == 100.0
    assert "a:a" in details
    assert "b:b" in details


def test_score_row_pair_missing_col_skipped() -> None:
    rules = [FieldRule("missing", "missing", 1.0, "exact", True)]
    source = pd.Series({"other": "x"})
    target = pd.Series({"other": "x"})
    score, details = score_row_pair(source, target, rules)
    assert score == 0.0
    assert details == {}
