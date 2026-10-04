from __future__ import annotations

from investigator.error_parser import ParsedError, parse_error
from investigator.investigation import Investigation
from investigator.investigation_result import InvestigationResult
from investigator.knowledge_lookup import lookup


def investigate(raw_error: str) -> InvestigationResult:
    parsed: ParsedError = parse_error(raw_error)

    knowledge = lookup(parsed)

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