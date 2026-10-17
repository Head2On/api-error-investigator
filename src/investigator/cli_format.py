"""Terminal presentation and formatting for investigation results."""

from __future__ import annotations

import textwrap

from investigator.investigation_result import InvestigationResult

# Consistent wrap width for all body text (explanations, bullets).
# Fixed rather than terminal-derived so output is deterministic and testable.
WRAP_WIDTH = 88

# Short bullet indent: "  - " -> 4 chars. Continuation lines align under text.
_BULLET_INDENT = 4


def format_result(result: InvestigationResult) -> str:
    """Format an InvestigationResult for terminal display.

    Never raises. Unknown results are formatted without fabrication.
    """
    if result.status == "known":
        return _format_known(result)
    return _format_unknown(result)


#  helpers

def _wrap(text: str, width: int = WRAP_WIDTH, subsequent_indent: str = "") -> list[str]:
    """Word-aware wrap. Never breaks a word/URL; long tokens overflow intact."""
    return textwrap.wrap(
        text,
        width=width,
        subsequent_indent=subsequent_indent,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]


def _format_bullets(items: list[str]) -> list[str]:
    """Render a list of bullet items with hanging indent, word-wrapped."""
    lines: list[str] = []
    for item in items:
        wrapped = textwrap.wrap(
            item,
            width=WRAP_WIDTH,
            initial_indent="- ",
            subsequent_indent=" " * _BULLET_INDENT,
            break_long_words=False,
            break_on_hyphens=False,
        )
        lines.extend(wrapped or ["- "])
    return lines


def _section(title: str, body_lines: list[str]) -> list[str]:
    """Assemble a titled section followed by its body lines and a blank line."""
    return [f"{title}:", *body_lines, ""]


def _strip_trailing_blanks(lines: list[str]) -> list[str]:
    while lines and lines[-1] == "":
        lines.pop()
    return lines


#  known

def _format_known(result: InvestigationResult) -> str:
    """Format a known investigation result into human-readable sections."""
    parsed = result.parsed_error
    inv = result.investigation

    # Invariant guarantees these are set when status="known".
    assert inv is not None

    lines: list[str] = []

    lines.append(f"Error: {parsed['error_type']}")
    lines.append("Status: KNOWN")
    lines.append("")

    lines.extend(_section("Summary", _wrap(inv.summary)))

    lines.extend(_section("Explanation", _wrap(inv.explanation)))

    if inv.common_causes:
        lines.extend(_section("Common Causes", _format_bullets(inv.common_causes)))

    if inv.fixes:
        lines.extend(_section("Fixes", _format_bullets(inv.fixes)))

    if inv.docs_url is not None:
        # URLs are never wrapped or truncated.
        lines.extend(_section("Documentation", [inv.docs_url]))

    if inv.related_errors:
        lines.extend(_section("Related Errors", _format_bullets(inv.related_errors)))

    return "\n".join(_strip_trailing_blanks(lines))


#  unknown

def _format_unknown(result: InvestigationResult) -> str:
    """Format an unknown investigation result for terminal display."""
    parsed = result.parsed_error
    error_type = parsed["error_type"] if parsed["error_type"] else "(unrecognized)"

    lines: list[str] = []

    lines.append(f"Error: {error_type}")
    lines.append("Status: UNKNOWN")
    lines.append("")

    lines.extend(
        _wrap(
            "The Knowledge Base has no matching entry for this error. "
            "No diagnosis was produced."
        )
    )

    return "\n".join(_strip_trailing_blanks(lines))