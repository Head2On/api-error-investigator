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
