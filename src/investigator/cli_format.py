from __future__ import annotations

from investigator.investigation_result import InvestigationResult


def format_result(result: InvestigationResult) -> str:
    """Format an InvestigationResult for terminal display."""
    if result.status == "known":
        return _format_known(result)
    return _format_unknown(result)


# ----------------------------------------------------------------- known

def _format_known(result: InvestigationResult) -> str:
    parsed = result.parsed_error
    inv = result.investigation

    # Invariant guarantees these are set when status="known".
    assert inv is not None

    lines: list[str] = []

    lines.append(f"Error: {parsed['error_type']}")
    lines.append("")

    lines.append("Summary:")
    lines.append(inv.summary)
    lines.append("")

    lines.append("Explanation:")
    lines.append(inv.explanation)
    lines.append("")

    if inv.common_causes:
        lines.append("Common Causes:")
        for cause in inv.common_causes:
            lines.append(f"- {cause}")
        lines.append("")

    if inv.fixes:
        lines.append("Fixes:")
        for fix in inv.fixes:
            lines.append(f"- {fix}")
        lines.append("")

    if inv.docs_url is not None:
        lines.append("Documentation:")
        lines.append(inv.docs_url)
        lines.append("")

    if inv.related_errors:
        lines.append("Related Errors:")
        for err in inv.related_errors:
            lines.append(f"- {err}")
        lines.append("")

    # Strip trailing blank line for a clean ending.
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


# --------------------------------------------------------------- unknown

def _format_unknown(result: InvestigationResult) -> str:
    parsed = result.parsed_error
    error_type = parsed["error_type"] if parsed["error_type"] else "(unrecognized)"

    lines = [
        f"Error: {error_type}",
        "",
        "Status: UNKNOWN",
        "",
        "The Knowledge Base does not contain information",
        "about this error.",
    ]
    return "\n".join(lines)