from __future__ import annotations

from investigator.error_parser import ParsedError, parse_error
from investigator.investigation_result import InvestigationResult
from investigator.knowledge_lookup import lookup


def investigate(raw_error: str) -> InvestigationResult:
    parsed: ParsedError = parse_error(raw_error)

    knowledge = lookup(parsed)

    if knowledge is not None:
        return InvestigationResult.known(parsed, knowledge)

    return InvestigationResult.unknown(parsed)