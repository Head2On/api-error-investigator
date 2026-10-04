"""Tests for investigator.investigation.Investigation."""

from investigator.investigation import Investigation


def test_investigation_can_be_constructed():
    inv = Investigation(
        summary="s",
        explanation="e",
        common_causes=["c"],
        fixes=["f"],
        docs_url="https://example.com",
        related_errors=["OtherError"],
    )
    assert inv.summary == "s"
    assert inv.explanation == "e"
    assert inv.common_causes == ["c"]
    assert inv.fixes == ["f"]
    assert inv.docs_url == "https://example.com"
    assert inv.related_errors == ["OtherError"]


def test_investigation_allows_none_docs_url():
    inv = Investigation(
        summary="s",
        explanation="e",
        common_causes=[],
        fixes=[],
        docs_url=None,
        related_errors=[],
    )
    assert inv.docs_url is None


def test_investigation_allows_empty_lists():
    inv = Investigation(
        summary="s",
        explanation="e",
        common_causes=[],
        fixes=[],
        docs_url=None,
        related_errors=[],
    )
    assert inv.common_causes == []
    assert inv.fixes == []
    assert inv.related_errors == []


def test_investigation_equality():
    """Two investigations with the same field values must be equal."""
    a = Investigation(
        summary="s",
        explanation="e",
        common_causes=["c"],
        fixes=["f"],
        docs_url=None,
        related_errors=[],
    )
    b = Investigation(
        summary="s",
        explanation="e",
        common_causes=["c"],
        fixes=["f"],
        docs_url=None,
        related_errors=[],
    )
    assert a == b