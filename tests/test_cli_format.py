from investigator.cli_format import format_result
from investigator.error_parser import ParsedError
from investigator.investigation import Investigation
from investigator.investigation_result import InvestigationResult


# ---------------------------------------------------------------- fixtures

def _parsed(error_type: str | None = "ValueError") -> ParsedError:
    return {
        "error_type": error_type,
        "message": "invalid value",
        "file": "app/service.py",
        "line": 42,
        "function": "handle",
        "stack_trace": "ValueError: invalid value",
    }


def _investigation(
    *,
    common_causes: list[str] | None = None,
    fixes: list[str] | None = None,
    docs_url: str | None = "https://example.com/docs",
    related_errors: list[str] | None = None,
) -> Investigation:
    return Investigation(
        summary="A short summary.",
        explanation="A longer explanation.",
        common_causes=common_causes if common_causes is not None else ["Cause A"],
        fixes=fixes if fixes is not None else ["Fix A"],
        docs_url=docs_url,
        related_errors=related_errors if related_errors is not None else ["OtherError"],
    )

def _knowledge() -> dict:
    return {
        "error_type": "ValueError",
        "aliases": [],
        "category": "python",
        "subcategory": "data_validation",
        "summary": "A short summary.",
        "explanation": "A longer explanation.",
        "common_causes": ["Cause A"],
        "fixes": ["Fix A"],
        "docs_url": "https://example.com/docs",
        "related_errors": ["OtherError"],
    }

# ----------------------------------------------------------------- known

def test_known_output_includes_all_sections_when_present():
    result = InvestigationResult.known(_parsed(), _knowledge(), _investigation())  # type: ignore[arg-type]
    output = format_result(result)

    assert "Error: ValueError" in output
    assert "Summary:" in output
    assert "A short summary." in output
    assert "Explanation:" in output
    assert "A longer explanation." in output
    assert "Common Causes:" in output
    assert "- Cause A" in output
    assert "Fixes:" in output
    assert "- Fix A" in output
    assert "Documentation:" in output
    assert "https://example.com/docs" in output
    assert "Related Errors:" in output
    assert "- OtherError" in output


def test_known_output_skips_missing_docs_url():
    result = InvestigationResult.known(
        _parsed(), {}, _investigation(docs_url=None)  # type: ignore[arg-type]
    )
    output = format_result(result)
    assert "Documentation:" not in output


def test_known_output_skips_empty_common_causes():
    result = InvestigationResult.known(
        _parsed(), {}, _investigation(common_causes=[])  # type: ignore[arg-type]
    )
    output = format_result(result)
    assert "Common Causes:" not in output


def test_known_output_skips_empty_fixes():
    result = InvestigationResult.known(
        _parsed(), {}, _investigation(fixes=[])  # type: ignore[arg-type]
    )
    output = format_result(result)
    assert "Fixes:" not in output


def test_known_output_skips_empty_related_errors():
    result = InvestigationResult.known(
        _parsed(), {}, _investigation(related_errors=[])  # type: ignore[arg-type]
    )
    output = format_result(result)
    assert "Related Errors:" not in output


# --------------------------------------------------------------- unknown

def test_unknown_output_states_status_and_no_data():
    result = InvestigationResult.unknown(_parsed("SomeFakeError"))
    output = format_result(result)

    assert "Error: SomeFakeError" in output
    assert "Status: UNKNOWN" in output
    assert "The Knowledge Base does not contain information" in output


def test_unknown_output_with_missing_error_type():
    """Garbage input has no error_type; format must not print 'None'."""
    result = InvestigationResult.unknown(_parsed(None))
    output = format_result(result)

    assert "Error: (unrecognized)" in output
    assert "None" not in output


def test_unknown_output_does_not_invent_content():
    result = InvestigationResult.unknown(_parsed("SomeFakeError"))
    output = format_result(result)

    assert "Summary:" not in output
    assert "Fixes:" not in output
    assert "Common Causes:" not in output
    assert "Documentation:" not in output