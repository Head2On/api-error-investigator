from investigator.cli_format import format_result
from investigator.investigator import investigate


#  scenario 1: error-shaped, unknown
def test_unknown_bare_error_type_end_to_end():
    raw = "SomeMadeUpError: something happened"

    result = investigate(raw)

    #  result level 
    assert result.status == "unknown"
    assert result.knowledge is None
    assert result.investigation is None
    assert result.parsed_error["error_type"] == "SomeMadeUpError"

    #  output level 
    output = format_result(result)
    assert "Error: SomeMadeUpError" in output
    assert "Status: UNKNOWN" in output
    assert "Summary:" not in output
    assert "Explanation:" not in output
    assert "Common Causes:" not in output
    assert "Fixes:" not in output
    assert "Documentation:" not in output
    assert "Related Errors:" not in output


def test_unknown_dotted_error_type_end_to_end():
    raw = (
        "Traceback (most recent call last):\n"
        '  File "app/flow.py", line 12, in run\n'
        "    do_something()\n"
        "sqlalchemy.exc.SomeUnknownError: an error we have no entry for"
    )

    result = investigate(raw)

    #  result level 
    assert result.status == "unknown"
    assert result.knowledge is None
    assert result.investigation is None
    assert result.parsed_error["error_type"] == "sqlalchemy.exc.SomeUnknownError"

    #  output level 
    output = format_result(result)
    assert "sqlalchemy.exc.SomeUnknownError" in output
    assert "Status: UNKNOWN" in output


# scenario 2: garbage / unrecognized
def test_garbage_single_line_end_to_end():
    raw = "Hello this is not an error at all"

    result = investigate(raw)

    #  result level 
    assert result.status == "unknown"
    assert result.knowledge is None
    assert result.investigation is None
    assert result.parsed_error["error_type"] is None

    #  output level 
    output = format_result(result)
    assert "Error: (unrecognized)" in output
    assert "Status: UNKNOWN" in output
    assert "Error: None" not in output


def test_garbage_multiline_end_to_end():
    raw = (
        "Database connection failed\n"
        "Could not connect to PostgreSQL\n"
        "Please check configuration"
    )

    result = investigate(raw)

    #  result level 
    assert result.status == "unknown"
    assert result.knowledge is None
    assert result.investigation is None
    assert result.parsed_error["error_type"] is None
    assert result.parsed_error["stack_trace"] == raw

    #  output level 
    output = format_result(result)
    assert "Error: (unrecognized)" in output
    assert "Status: UNKNOWN" in output
    assert "Error: None" not in output


#  cross-cutting invariants

def test_unknown_never_invents_diagnosis():
    samples = [
        "SomeMadeUpError: something happened",
        "sqlalchemy.exc.SomeUnknownError: nope",
        "Hello this is not an error",
        "Database connection failed\nPlease check configuration",
    ]

    for raw in samples:
        result = investigate(raw)
        assert result.status == "unknown", f"expected unknown for: {raw!r}"
        assert result.knowledge is None
        assert result.investigation is None

        output = format_result(result)
        assert "Summary:" not in output, f"fabricated Summary for: {raw!r}"
        assert "Explanation:" not in output
        assert "Common Causes:" not in output
        assert "Fixes:" not in output
        assert "Documentation:" not in output
        assert "Related Errors:" not in output