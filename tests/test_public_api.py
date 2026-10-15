import investigator


def test_public_api_exports_expected_names():
    assert set(investigator.__all__) == {
        "investigate",
        "InvestigationResult",
        "Investigation",
        "ParsedError",
        "KnowledgeEntry",
    }


def test_public_symbols_are_importable():
    from investigator import (  # noqa: F401
        Investigation,
        InvestigationResult,
        KnowledgeEntry,
        ParsedError,
        investigate,
    )


def test_investigate_is_callable_via_public_api():
    """The public investigate is the real function, not a re-export stub."""
    result = investigator.investigate("ValueError: bad input")
    assert result.status == "known"
    assert result.parsed_error["error_type"] == "ValueError"


def test_public_symbols_are_the_same_objects_as_internal_modules():
    """Sanity check: the exported names point at the real definitions."""
    from investigator.investigator import investigate as internal_investigate
    from investigator.investigation_result import (
        InvestigationResult as internal_InvestigationResult,
    )
    from investigator.investigation import Investigation as internal_Investigation
    from investigator.error_parser import ParsedError as internal_ParsedError
    from investigator.knowledge_loader import KnowledgeEntry as internal_KnowledgeEntry

    assert investigator.investigate is internal_investigate
    assert investigator.InvestigationResult is internal_InvestigationResult
    assert investigator.Investigation is internal_Investigation
    assert investigator.ParsedError is internal_ParsedError
    assert investigator.KnowledgeEntry is internal_KnowledgeEntry