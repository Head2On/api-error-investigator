"""Tests for investigator.error_parser.parse_error."""

from investigator.error_parser import parse_error


def test_simple_python_error():
    """A bare 'ErrorType: message' line should still be parsed."""
    result = parse_error("ValueError: invalid value")

    assert result["error_type"] == "ValueError"
    assert result["message"] == "invalid value"
    assert result["file"] is None
    assert result["line"] is None
    assert result["function"] is None


def test_keyerror():
    """KeyError with quoted key should parse cleanly."""
    result = parse_error("KeyError: 'username'")

    assert result["error_type"] == "KeyError"
    assert result["message"] == "'username'"


def test_full_traceback():
    """A full traceback should extract the deepest frame and the error."""
    sample = (
        "Traceback (most recent call last):\n"
        '  File "patient/service.py", line 84, in create_patient\n'
        "    db.add(patient)\n"
        "sqlalchemy.exc.IntegrityError: duplicate key violates unique constraint"
    )
    result = parse_error(sample)

    assert result["error_type"] == "sqlalchemy.exc.IntegrityError"
    assert result["message"] == "duplicate key violates unique constraint"
    assert result["file"] == "patient/service.py"
    assert result["line"] == 84
    assert result["function"] == "create_patient"


def test_empty_input():
    """Empty input must not invent data."""
    result = parse_error("")

    assert result["error_type"] is None
    assert result["message"] is None
    assert result["file"] is None
    assert result["line"] is None
    assert result["function"] is None
    assert result["stack_trace"] == ""


def test_garbage_text():
    """Non-error text must not be misread as an error."""
    result = parse_error("Hello this is not an error")

    assert result["error_type"] is None
    assert result["message"] is None
    assert result["stack_trace"] == "Hello this is not an error"


def test_multiline_non_error_text():
    """Multi-line plain text must not be misread as an error."""
    sample = (
        "Database connection failed\n"
        "Could not connect to PostgreSQL\n"
        "Please check configuration"
    )
    result = parse_error(sample)

    assert result["error_type"] is None
    assert result["message"] is None
    assert result["file"] is None
    assert result["line"] is None
    assert result["function"] is None
    assert result["stack_trace"] == sample