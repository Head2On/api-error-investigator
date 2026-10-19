"""Tests for the programmatic Python SDK (investigator.sdk)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from investigator.investigation_result import InvestigationResult
from investigator.sdk import (
    KnowledgeEntryError,
    capture_exception,
    investigate_exception,
)


# ---------------------------------------------------------------------------
# investigate_exception
# ---------------------------------------------------------------------------

def test_investigate_exception_known_error():
    """investigate_exception returns a known result for a registered error."""
    try:
        int("invalid")
    except ValueError as exc:
        result = investigate_exception(exc)

    assert isinstance(result, InvestigationResult)
    assert result.status == "known"
    assert result.parsed_error["error_type"] == "ValueError"
    assert result.investigation is not None
    assert "ValueError" in result.investigation.summary or len(result.investigation.fixes) > 0


def test_investigate_exception_unknown_error():
    """investigate_exception returns an unknown result for an uncataloged error."""
    try:
        raise RuntimeError("something unexpected")
    except RuntimeError as exc:
        result = investigate_exception(exc)

    assert result.status == "unknown"
    assert result.parsed_error["error_type"] == "RuntimeError"
    assert result.knowledge is None
    assert result.investigation is None


def test_investigate_exception_unraised_exception():
    """investigate_exception accepts an unraised exception with no __traceback__."""
    exc = ValueError("unraised literal value")
    assert exc.__traceback__ is None

    result = investigate_exception(exc)
    assert result.status == "known"
    assert result.parsed_error["error_type"] == "ValueError"
    assert result.parsed_error["message"] == "unraised literal value"


def test_investigate_exception_pure_no_stdout_or_stderr(capsys):
    """investigate_exception produces no side effects on stdout or stderr."""
    exc = ValueError("silent test")
    investigate_exception(exc)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


class CustomAppError(Exception):
    pass


def test_investigate_exception_with_valid_custom_kb(tmp_path: Path):
    """investigate_exception uses custom knowledge base directory when passed."""
    custom_kb = tmp_path / "kb"
    custom_kb.mkdir()
    entry = (
        f"error_type: {CustomAppError.__module__}.CustomAppError\n"
        "aliases:\n"
        "  - CustomAppError\n"
        "category: app\n"
        "summary: Custom app error summary.\n"
        "explanation: Custom app error explanation.\n"
        "common_causes:\n"
        "  - Bad state\n"
        "fixes:\n"
        "  - Reset state\n"
        "related_errors: []\n"
    )
    (custom_kb / "custom_error.yaml").write_text(entry, encoding="utf-8")

    res = investigate_exception(CustomAppError("boom"), kb_dir=custom_kb)
    assert res.status == "known"
    assert res.investigation is not None
    assert res.investigation.summary == "Custom app error summary."


def test_investigate_exception_with_invalid_kb_propagates_error(tmp_path: Path):
    """investigate_exception raises KnowledgeEntryError on bad custom kb_dir."""
    nonexistent = tmp_path / "does_not_exist"
    with pytest.raises(KnowledgeEntryError):
        investigate_exception(ValueError("boom"), kb_dir=nonexistent)


# ---------------------------------------------------------------------------
# capture_exception: Context Manager
# ---------------------------------------------------------------------------

def test_capture_exception_context_manager_no_error(capsys):
    """Normal execution inside capture_exception block emits nothing."""
    with capture_exception():
        x = 1 + 1

    assert x == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_capture_exception_context_manager_reraises_by_default(capsys):
    """By default, capture_exception prints diagnosis to stderr and re-raises."""
    with pytest.raises(ValueError, match="invalid value"):
        with capture_exception():
            raise ValueError("invalid value")

    captured = capsys.readouterr()
    assert "Error: ValueError" in captured.err
    assert "Status: KNOWN" in captured.err


def test_capture_exception_context_manager_suppress_when_reraise_false(capsys):
    """When reraise=False, capture_exception suppresses the error after printing."""
    executed_after = False
    with capture_exception(reraise=False):
        raise ValueError("suppressed value")
    executed_after = True

    assert executed_after is True
    captured = capsys.readouterr()
    assert "Error: ValueError" in captured.err
    assert "Status: KNOWN" in captured.err


def test_capture_exception_context_manager_custom_sink(capsys):
    """When a custom sink is provided, diagnosis is passed to sink without printing."""
    collected: list[InvestigationResult] = []

    def my_sink(result: InvestigationResult) -> None:
        collected.append(result)

    with pytest.raises(KeyError):
        with capture_exception(sink=my_sink):
            raise KeyError("missing_key")

    captured = capsys.readouterr()
    assert captured.err == ""
    assert len(collected) == 1
    assert collected[0].status == "known"
    assert collected[0].parsed_error["error_type"] == "KeyError"


def test_capture_exception_context_manager_passthrough_keyboard_interrupt(capsys):
    """KeyboardInterrupt propagates untouched and is not intercepted by the SDK."""
    collected: list[InvestigationResult] = []

    with pytest.raises(KeyboardInterrupt):
        with capture_exception(sink=collected.append):
            raise KeyboardInterrupt()

    assert len(collected) == 0
    captured = capsys.readouterr()
    assert captured.err == ""


def test_capture_exception_context_manager_passthrough_system_exit(capsys):
    """SystemExit propagates untouched and is not intercepted by the SDK."""
    collected: list[InvestigationResult] = []

    with pytest.raises(SystemExit) as exc_info:
        with capture_exception(sink=collected.append):
            sys.exit(42)

    assert exc_info.value.code == 42
    assert len(collected) == 0
    captured = capsys.readouterr()
    assert captured.err == ""


# ---------------------------------------------------------------------------
# capture_exception: Decorator
# ---------------------------------------------------------------------------

def test_capture_exception_bare_decorator_success():
    """@capture_exception allows successful calls to return normally."""
    @capture_exception
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    assert add(3, 4) == 7
    assert add(3, 4) == 7 
    assert add.__name__ == "add"
    assert add.__doc__ == "Add two numbers."


def test_capture_exception_bare_decorator_failure(capsys):
    """@capture_exception catches error, prints diagnosis, and re-raises."""
    @capture_exception
    def faulty():
        raise ValueError("faulty call")

    with pytest.raises(ValueError, match="faulty call"):
        faulty()

    captured = capsys.readouterr()
    assert "Error: ValueError" in captured.err
    assert "Status: KNOWN" in captured.err


def test_capture_exception_parameterized_decorator_with_parens(capsys):
    """@capture_exception() without arguments works identically to bare decorator."""
    @capture_exception()
    def faulty():
        raise KeyError("faulty call")

    with pytest.raises(KeyError):
        faulty()

    captured = capsys.readouterr()
    assert "Error: KeyError" in captured.err


def test_capture_exception_parameterized_decorator_suppressed():
    """@capture_exception(reraise=False) suppresses exception and returns None."""
    sunk: list[InvestigationResult] = []

    @capture_exception(reraise=False, sink=sunk.append)
    def calculate(a: int, b: int) -> int:
        return a // b

    assert calculate(10, 2) == 5
    assert calculate(10, 0) is None
    assert len(sunk) == 1
    assert sunk[0].parsed_error["error_type"] == "ZeroDivisionError"
    assert sunk[0].status == "unknown"


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

def test_sdk_module_reexports_knowledge_entry_error():
    """investigator.sdk re-exports KnowledgeEntryError."""
    import investigator.sdk as sdk

    assert hasattr(sdk, "KnowledgeEntryError")
    assert sdk.KnowledgeEntryError is KnowledgeEntryError
    assert set(sdk.__all__) == {
        "investigate_exception",
        "capture_exception",
        "KnowledgeEntryError",
    }
