import pytest

import investigator.knowledge_lookup as lookup_mod
from investigator.knowledge_lookup import lookup
from investigator.error_parser import ParsedError

@pytest.fixture(autouse=True)
def _fresh_cache():
    """Rebuild the index for each test so tests are isolated."""
    lookup_mod.reset_cache()
    yield
    lookup_mod.reset_cache()


def _parsed(error_type: str | None) -> ParsedError:
    """Minimal ParsedError-shaped dict for lookup tests."""
    return {
        "error_type": error_type,
        "message": None,
        "file": None,
        "line": None,
        "function": None,
        "stack_trace": "",
    }


# ---------------------------------------------------------------- exact match

def test_exact_match_returns_entry():
    entry = lookup(_parsed("sqlalchemy.exc.IntegrityError"))
    assert entry is not None
    assert entry["error_type"] == "sqlalchemy.exc.IntegrityError"


def test_exact_match_other_entry():
    entry = lookup(_parsed("ValueError"))
    assert entry is not None
    assert entry["category"] == "python"


# ------------------------------------------------------------------- aliases

def test_alias_match_returns_entry():
    entry = lookup(_parsed("IntegrityError"))
    assert entry is not None
    assert entry["error_type"] == "sqlalchemy.exc.IntegrityError"


def test_alias_match_is_case_sensitive():
    """'integrityerror' is not the same as 'IntegrityError'."""
    assert lookup(_parsed("integrityerror")) is None


# --------------------------------------------------------------------- case

def test_error_type_is_case_sensitive():
    assert lookup(_parsed("valueerror")) is None
    assert lookup(_parsed("VALUEERROR")) is None
    assert lookup(_parsed("ValueError")) is not None


# ------------------------------------------------------------------ unknown

def test_unknown_error_returns_none():
    assert lookup(_parsed("SomeErrorThatDoesNotExist")) is None


def test_partial_match_is_not_a_match():
    """Prefix matching is not part of the contract."""
    assert lookup(_parsed("sqlalchemy.exc")) is None


# ------------------------------------------------------------------ invalid

def test_none_error_type_returns_none():
    assert lookup(_parsed(None)) is None


def test_empty_string_returns_none():
    assert lookup(_parsed("")) is None


def test_none_parsed_error_returns_none():
    assert lookup(None) is None  # type: ignore[arg-type]


def test_non_dict_input_returns_none():
    assert lookup("ValueError") is None  # type: ignore[arg-type]


# ------------------------------------------------------------ not-modifying

def test_lookup_does_not_mutate_input():
    parsed = _parsed("ValueError")
    snapshot = dict(parsed)
    lookup(parsed)
    assert parsed == snapshot


# ------------------------------------------------------- contract boundary

def test_unknown_does_not_invent_diagnosis():
    """A-013 must not fabricate. Unknown is None, nothing more."""
    result = lookup(_parsed("TotallyMadeUpError"))
    assert result is None