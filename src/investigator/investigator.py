"""Deterministic investigation orchestrator."""

from __future__ import annotations

from pathlib import Path

from investigator.error_parser import ParsedError, parse_error
from investigator.investigation import Investigation
from investigator.investigation_result import InvestigationResult
from investigator.knowledge_lookup import lookup


def investigate(
    raw_error: str,
    *,
    kb_dir: Path | str | None = None,
) -> InvestigationResult:
    """Investigate a raw traceback or error string deterministically.

    Args:
        raw_error: Raw error string or traceback.
        kb_dir: Optional path to a custom knowledge base directory.
    """
    parsed: ParsedError = parse_error(raw_error)

    knowledge = lookup(parsed, kb_dir=kb_dir)

    if knowledge is not None:
        investigation = Investigation(
            summary=knowledge["summary"],
            explanation=knowledge["explanation"],
            common_causes=knowledge["common_causes"],
            fixes=knowledge["fixes"],
            docs_url=knowledge["docs_url"],
            related_errors=knowledge["related_errors"],
        )
        return InvestigationResult.known(parsed, knowledge, investigation)

    return InvestigationResult.unknown(parsed)