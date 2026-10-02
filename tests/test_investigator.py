"""Tests for investigator.investigator.investigate."""

from investigator.investigator import investigate
from investigator.investigation_result import InvestigationResult


# ------------------------------------------------------------------ known

def test_known_integrity_error_returns_known_status():
    raw = (
        "Traceback (most recent call last):\n"
        '  File "patient/service.py", line 84, in create_patient\n'
        "    db.add(patient)\n"
        "sqlalchemy.exc.IntegrityError: duplicate key violates unique constraint"
    )
    result = investigate(raw)

    assert isinstance(result, InvestigationResult)
    assert result.status == "known"
    assert result.knowledge is not None
    assert result.knowledge["error_type"] == "sqlalchemy.exc.IntegrityError"


def test_known_alias_returns_known_status():
    """`IntegrityError` alone is a registered alias, not the full dotted name."""
    raw = (
        "Traceback (most recent call last):\n"
        '  File "patient/service.py", line 84, in create_patient\n'
        "    db.add(patient)\n"
        "IntegrityError: duplicate key violates unique constraint"
    )
    result = investigate(raw)

    assert result.status == "known"
    assert result.knowledge is not None
    assert result.knowledge["error_type"] == "sqlalchemy.exc.IntegrityError"


# ---------------------------------------------------------------- unknown

def test_unknown_error_returns_unknown_status():
    raw = "SomeErrorWeDoNotKnow: something went wrong"
    result = investigate(raw)

    assert isinstance(result, InvestigationResult)
    assert result.status == "unknown"
    assert result.knowledge is None


def test_garbage_text_returns_unknown_status():
    raw = "Hello this is not an error at all"
    result = investigate(raw)

    assert result.status == "unknown"
    assert result.knowledge is None


def test_empty_string_returns_unknown_status():
    result = investigate("")

    assert result.status == "unknown"
    assert result.knowledge is None


# ------------------------------------------------- parsed error preserved

def test_parsed_error_is_preserved_for_known():
    raw = "ValueError: invalid value"
    result = investigate(raw)

    assert result.parsed_error["error_type"] == "ValueError"
    assert result.parsed_error["message"] == "invalid value"
    assert result.parsed_error["stack_trace"] == raw


def test_parsed_error_is_preserved_for_unknown():
    raw = "Weird.Fake.Error: something happened"
    result = investigate(raw)

    # Even though the KB has no entry, the parser still did its job.
    assert result.parsed_error["error_type"] == "Weird.Fake.Error"
    assert result.parsed_error["message"] == "something happened"
    assert result.parsed_error["stack_trace"] == raw


def test_garbage_input_preserves_stack_trace():
    raw = "not an error\nbut multiline\ntext"
    result = investigate(raw)

    assert result.status == "unknown"
    assert result.parsed_error["stack_trace"] == raw
    assert result.parsed_error["error_type"] is None


# ------------------------------------------------- knowledge invariant

def test_knowledge_present_when_known():
    result = investigate("ValueError: bad")
    assert result.knowledge is not None
    assert result.knowledge["category"] == "python"


def test_knowledge_none_when_unknown():
    result = investigate("NopeError: not real")
    assert result.knowledge is None


# ------------------------------------------------------- non-mutation

def test_does_not_mutate_input():
    """investigate() is a pure function of its input string."""
    raw = "ValueError: invalid value"
    raw_copy = str(raw)  # strings are immutable, but keep the intent explicit

    result = investigate(raw)

    assert raw == raw_copy
    # Second call must give an equivalent result (no hidden state).
    result2 = investigate(raw)
    assert result.status == result2.status
    assert result.parsed_error == result2.parsed_error
    assert result.knowledge == result2.knowledge