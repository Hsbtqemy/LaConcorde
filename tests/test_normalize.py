"""Tests de normalisation."""

from laconcorde.normalize import norm_doi, norm_text


def test_norm_text_basic() -> None:
    # Espaces multiples → espace simple, lower, strip
    assert norm_text("  Hello  World  ") == "hello world"
    assert norm_text("  Hello  World  ", strip=True) == "hello world"


def test_norm_text_lower_strip() -> None:
    assert norm_text("  ABC  ", lower=True, strip=True) == "abc"
    assert norm_text("  ABC  ", lower=False, strip=True) == "ABC"


def test_norm_text_whitespace() -> None:
    assert norm_text("a\t\n  b") == "a b"
    assert norm_text("  ") == ""


def test_norm_text_nfkc() -> None:
    # NFKC normalise les caractères Unicode
    assert norm_text("café") == "café"
    assert norm_text("ﬁ") == "fi"  # ligature -> fi


def test_norm_text_remove_diacritics() -> None:
    assert norm_text("café", remove_diacritics=True) == "cafe"
    assert norm_text(" naïve ", remove_diacritics=True) == "naive"
    assert norm_text("Zürich", remove_diacritics=True) == "zurich"


def test_norm_text_none_nan() -> None:
    assert norm_text(None) == ""
    assert norm_text(float("nan")) == ""


def test_norm_doi_prefixes() -> None:
    assert norm_doi("https://doi.org/10.1234/abc") == "10.1234/abc"
    assert norm_doi("doi:10.1234/abc") == "10.1234/abc"
    assert norm_doi("http://dx.doi.org/10.1234/xyz") == "10.1234/xyz"


def test_norm_doi_query_params() -> None:
    assert norm_doi("https://doi.org/10.1234/abc?ref=xyz") == "10.1234/abc"
    assert norm_doi("10.1234/abc#section") == "10.1234/abc"


def test_norm_doi_url_encoding() -> None:
    assert norm_doi("10.1234%2Fabc") == "10.1234/abc"
    assert norm_doi("10.1234%2fabc") == "10.1234/abc"


def test_norm_doi_trailing_slash() -> None:
    assert norm_doi("10.1234/abc/") == "10.1234/abc"
    assert norm_doi("https://doi.org/10.1234/abc/") == "10.1234/abc"


def test_norm_doi_internal_spaces() -> None:
    assert norm_doi("10.1234 / abc") == "10.1234/abc"
    assert norm_doi("doi:  10.1234/abc") == "10.1234/abc"


def test_norm_doi_empty() -> None:
    assert norm_doi(None) == ""
    assert norm_doi("") == ""
