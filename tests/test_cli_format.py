"""Tests for investigator.cli_format."""

from investigator.cli_format import WRAP_WIDTH, format_result
from investigator.investigation import Investigation
from investigator.investigation_result import InvestigationResult

# --------------------------------------------------------------- fixtures

def _investigation(**overrides) -> Investigation:
    defaults = dict(
        summary="A database constraint was violated.",
        explanation="SQLAlchemy issued an INSERT that the database rejected.",
        common_causes=["Duplicate unique column."],
        fixes=["Check the constraint name."],
        docs_url="https://docs.sqlalchemy.org/en/20/orm/exceptions.html",
        related_errors=["sqlalchemy.exc.OperationalError"],
    )
    defaults.update(overrides)
    return Investigation(**defaults)


def _known(**overrides) -> InvestigationResult:
    return InvestigationResult(
        status="known",
        parsed_error={"error_type": "sqlalchemy.exc.IntegrityError"},
        knowledge={},
        investigation=_investigation(**overrides),
    )


def _unknown(error_type: str | None = "TotallyUnknownError") -> InvestigationResult:
    return InvestigationResult(
        status="unknown",
        parsed_error={"error_type": error_type},
        knowledge=None,
        investigation=None,
    )


# ------------------------------------------------------------------ known

def test_known_output_includes_all_sections_when_present():
    out = format_result(_known())
    assert "Error: sqlalchemy.exc.IntegrityError" in out
    assert "Status: KNOWN" in out
    assert "Summary:" in out
    assert "Explanation:" in out
    assert "Common Causes:" in out
    assert "Fixes:" in out
    assert "Documentation:" in out
    assert "Related Errors:" in out


def test_known_output_omits_empty_optional_sections():
    out = format_result(
        _known(common_causes=[], fixes=[], docs_url=None, related_errors=[])
    )
    assert "Common Causes:" not in out
    assert "Fixes:" not in out
    assert "Documentation:" not in out
    assert "Related Errors:" not in out
    # Required sections still present.
    assert "Summary:" in out
    assert "Explanation:" in out


def test_known_output_has_no_trailing_blank_line():
    out = format_result(_known())
    assert not out.endswith("\n")
    assert not out.endswith("\n\n")


def test_known_output_is_deterministic():
    assert format_result(_known()) == format_result(_known())


# ---------------------------------------------------------------- unknown

def test_unknown_output_states_status_and_no_data():
    out = format_result(_unknown())
    assert "Error: TotallyUnknownError" in out
    assert "Status: UNKNOWN" in out
    assert "no matching entry" in out.lower()


def test_unknown_output_unrecognized_error_type():
    out = format_result(_unknown(error_type=None))
    assert "Error: (unrecognized)" in out
    assert "Status: UNKNOWN" in out


def test_unknown_output_has_no_trailing_blank_line():
    out = format_result(_unknown())
    assert not out.endswith("\n")


# ---------------------------------------------------------------- wrapping

def test_long_explanation_wraps_at_width_without_breaking_words():
    long_word = "a" * (WRAP_WIDTH + 20)  # single token longer than width
    explanation = (
        "This explanation is intentionally long so that it exceeds the "
        f"configured wrap width of {WRAP_WIDTH} characters and must wrap. "
        f"Here is a single unbreakable token: {long_word}"
    )
    out = format_result(_known(explanation=explanation))
    lines = out.splitlines()

    # The unbreakable token must appear intact on exactly one line.
    token_lines = [ln for ln in lines if long_word in ln]
    assert len(token_lines) == 1

    # No line containing the prose portion should exceed WRAP_WIDTH.
    prose_lines = [
        ln for ln in lines
        if ln and not ln.endswith(":") and long_word not in ln
    ]
    for ln in prose_lines:
        assert len(ln) <= WRAP_WIDTH, f"line exceeds width: {ln!r}"


def test_long_bullet_wraps_with_hanging_indent():
    long_item = (
        "Inserting a row that duplicates a unique column such as email or "
        "username, which often happens under concurrent requests and needs "
        "explicit handling."
    )
    out = format_result(_known(fixes=[long_item], common_causes=[]))
    lines = out.splitlines()

    # Find the bullet block: first line starts with "- ".
    start = next(i for i, ln in enumerate(lines) if ln.startswith("- "))
    bullet_block = []
    for ln in lines[start:]:
        if ln == "" or ln.endswith(":"):
            break
        bullet_block.append(ln)

    assert len(bullet_block) >= 2, "long bullet should wrap"
    assert bullet_block[0].startswith("- ")
    for ln in bullet_block[1:]:
        assert ln.startswith("    "), "continuation must be indented"
        assert len(ln) <= WRAP_WIDTH


def test_documentation_url_is_never_wrapped_or_truncated():
    long_url = "https://example.com/" + ("x" * (WRAP_WIDTH + 40))
    out = format_result(_known(docs_url=long_url))
    assert long_url in out
    # Exactly one line carries the full URL.
    assert sum(1 for ln in out.splitlines() if ln == long_url) == 1