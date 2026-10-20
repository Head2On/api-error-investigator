"""Tests for knowledge base expansion (C-019)."""

from __future__ import annotations

from pathlib import Path

import pytest

from investigator.investigator import investigate
from investigator.knowledge_loader import load_all_entries

NEW_ERROR_TYPES = [
    "AttributeError",
    "TypeError",
    "IndexError",
    "FileNotFoundError",
    "PermissionError",
    "ModuleNotFoundError",
    "ConnectionError",
    "TimeoutError",
    "requests.exceptions.ConnectionError",
    "requests.exceptions.Timeout",
    "httpx.ConnectError",
    "json.JSONDecodeError",
    "pydantic.ValidationError",
    "sqlalchemy.exc.NoResultFound",
    "sqlalchemy.exc.MultipleResultsFound",
]


@pytest.mark.parametrize("error_type", NEW_ERROR_TYPES)
def test_kb_contains_entry(error_type: str) -> None:
    """The built-in knowledge base contains each new error type."""
    entries = load_all_entries()
    types = {e["error_type"] for e in entries}
    assert error_type in types


@pytest.mark.parametrize("error_type", NEW_ERROR_TYPES)
def test_entry_investigates_as_known(error_type: str) -> None:
    """Each new error type investigates cleanly with Status: KNOWN."""
    result = investigate(f"{error_type}: test")
    assert result.status == "known"
    assert result.investigation is not None
    assert result.investigation.summary


def test_kb_has_twenty_entries() -> None:
    """The built-in knowledge catalog has exactly 20 entries."""
    assert len(load_all_entries()) == 20


def test_no_em_dashes_in_kb() -> None:
    """No YAML entries contain unicode em-dashes (\u2014) for terminal encoding safety."""
    kb_dir = Path(__file__).parent.parent / "src" / "investigator" / "knowledge"
    for path in kb_dir.glob("*.yaml"):
        assert "\u2014" not in path.read_text(encoding="utf-8"), f"em-dash in {path.name}"


def test_import_error_unregistered_is_unknown() -> None:
    """ImportError is not aliased to ModuleNotFoundError and honestly returns UNKNOWN."""
    result = investigate("ImportError: cannot import name 'foo' from 'bar'")
    assert result.status == "unknown"
    assert result.knowledge is None
    assert result.investigation is None


def test_bare_validation_error_unregistered_is_unknown() -> None:
    """Bare ValidationError is not aliased to pydantic.ValidationError and returns UNKNOWN."""
    result = investigate("ValidationError: 1 validation error for Model")
    assert result.status == "unknown"
    assert result.knowledge is None
    assert result.investigation is None


@pytest.mark.parametrize("alias", ["NoResultFound", "MultipleResultsFound"])
def test_sqlalchemy_aliases_resolve_as_known(alias: str) -> None:
    """SQLAlchemy ORM query result aliases resolve to Status: KNOWN."""
    result = investigate(f"{alias}: test query")
    assert result.status == "known"
    assert result.investigation is not None
