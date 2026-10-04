"""Tests for investigator.investigation_result.InvestigationResult."""

import pytest

from investigator.error_parser import ParsedError
from investigator.investigation import Investigation
from investigator.investigation_result import InvestigationResult
from investigator.knowledge_loader import KnowledgeEntry
#  fixtures

def _parsed() -> ParsedError:
    return {
        "error_type": "ValueError",
        "message": "invalid value",
        "file": "app/service.py",
        "line": 42,
        "function": "handle",
        "stack_trace": "ValueError: invalid value",
    }


def _knowledge() -> KnowledgeEntry:
    return {
        "error_type": "ValueError",
        "aliases": [],
        "category": "python",
        "subcategory": "data_validation",
        "summary": "summary text",
        "explanation": "explanation text",
        "common_causes": ["cause one"],
        "fixes": ["fix one"],
        "docs_url": None,
        "related_errors": [],
    }

def _investigation() -> Investigation:
    return Investigation(
        summary="summary text",
        explanation="explanation text",
        common_causes=["cause one"],
        fixes=["fix one"],
        docs_url=None,
        related_errors=[],
    )

#  known result

def test_known_result_can_be_created_via_factory():
    result = InvestigationResult.known(_parsed(), _knowledge(), _investigation())
    assert result.status == "known"
    assert result.knowledge is not None


def test_known_result_preserves_parsed_error():
    parsed = _parsed()
    result = InvestigationResult.known(parsed, _knowledge(), _investigation())
    assert result.parsed_error == parsed


def test_known_result_has_knowledge_entry():
    knowledge = _knowledge()
    result = InvestigationResult.known(_parsed(), knowledge, _investigation())
    assert result.knowledge == knowledge

def test_known_result_has_investigation():
    investigation = _investigation()
    result = InvestigationResult.known(_parsed(), _knowledge(), investigation)
    assert result.investigation is investigation

#  unknown result

def test_unknown_result_can_be_created_via_factory():
    result = InvestigationResult.unknown(_parsed())
    assert result.status == "unknown"
    assert result.knowledge is None
    assert result.investigation is None
 

def test_unknown_result_preserves_parsed_error():
    parsed = _parsed()
    result = InvestigationResult.unknown(parsed)
    assert result.parsed_error == parsed


#  invariant: status

def test_invalid_status_is_rejected():
    with pytest.raises(ValueError, match="status must be"):
        InvestigationResult(
            status="banana",  # type: ignore[arg-type]
            parsed_error=_parsed(),
            knowledge=None,
            investigation=None,
        )


def test_known_without_knowledge_is_rejected():
    with pytest.raises(ValueError, match="status='known' requires a knowledge entry"):
        InvestigationResult(
            status="known",
            parsed_error=_parsed(),
            knowledge=None,
            investigation=_investigation()
        )

def test_known_without_investigation_is_rejected():
    with pytest.raises(ValueError, match="status='known' requires an investigation"):
        InvestigationResult(
            status="known",
            parsed_error=_parsed(),
            knowledge=_knowledge(),
            investigation=None,
        )

def test_unknown_with_knowledge_is_rejected():
    with pytest.raises(ValueError, match="status='unknown' requires knowledge=None"):
        InvestigationResult(
            status="unknown",
            parsed_error=_parsed(),
            knowledge=_knowledge(),
            investigation=None
        )

def test_unknown_with_investigation_is_rejected():
    with pytest.raises(ValueError, match="status='unknown' requires investigation=None"):
        InvestigationResult(
            status="unknown",
            parsed_error=_parsed(),
            knowledge=None,
            investigation=_investigation(),
        )

#  non-mutation check

def test_result_does_not_mutate_inputs():
    parsed = _parsed()
    knowledge = _knowledge()
    investigation = _investigation()
    parsed_snapshot = dict(parsed)
    knowledge_snapshot = dict(knowledge)
    

    InvestigationResult.known(parsed, knowledge, investigation)

    assert parsed == parsed_snapshot
    assert knowledge == knowledge_snapshot