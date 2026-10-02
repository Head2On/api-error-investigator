"""Tests for investigator.investigation_result.InvestigationResult."""

import pytest

from investigator.investigation_result import InvestigationResult, KnowledgeEntry
from investigator.error_parser import ParsedError

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


#  known result

def test_known_result_can_be_created_via_factory():
    result = InvestigationResult.known(_parsed(), _knowledge())
    assert result.status == "known"
    assert result.knowledge is not None


def test_known_result_preserves_parsed_error():
    parsed = _parsed()
    result = InvestigationResult.known(parsed, _knowledge())
    assert result.parsed_error == parsed


def test_known_result_has_knowledge_entry():
    knowledge = _knowledge()
    result = InvestigationResult.known(_parsed(), knowledge)
    assert result.knowledge == knowledge


#  unknown result

def test_unknown_result_can_be_created_via_factory():
    result = InvestigationResult.unknown(_parsed())
    assert result.status == "unknown"
    assert result.knowledge is None


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
        )


def test_known_without_knowledge_is_rejected():
    with pytest.raises(ValueError, match="status='known' requires"):
        InvestigationResult(
            status="known",
            parsed_error=_parsed(),
            knowledge=None,
        )


def test_unknown_with_knowledge_is_rejected():
    with pytest.raises(ValueError, match="status='unknown' requires"):
        InvestigationResult(
            status="unknown",
            parsed_error=_parsed(),
            knowledge=_knowledge(),
        )


#  non-mutation check

def test_result_does_not_mutate_inputs():
    parsed = _parsed()
    knowledge = _knowledge()
    parsed_snapshot = dict(parsed)
    knowledge_snapshot = dict(knowledge)

    InvestigationResult.known(parsed, knowledge)

    assert parsed == parsed_snapshot
    assert knowledge == knowledge_snapshot