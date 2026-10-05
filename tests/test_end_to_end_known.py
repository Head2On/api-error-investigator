from investigator.cli_format import format_result
from investigator.investigator import investigate


def test_integrity_error_end_to_end():
    raw = (
        "Traceback (most recent call last):\n"
        '  File "patient/service.py", line 84, in create_patient\n'
        "    db.add(patient)\n"
        "sqlalchemy.exc.IntegrityError: duplicate key violates unique constraint"
    )

    result = investigate(raw)

    #  result level 
    assert result.status == "known"
    assert result.parsed_error["error_type"] == "sqlalchemy.exc.IntegrityError"
    assert result.knowledge is not None
    assert result.investigation is not None
    assert result.investigation.summary.strip()

    #  output level 
    output = format_result(result)
    assert "sqlalchemy.exc.IntegrityError" in output
    assert "race condition" in output.lower()
    assert "upsert" in output.lower()



def test_operational_error_end_to_end():
    raw = (
        "Traceback (most recent call last):\n"
        '  File "app/db.py", line 52, in get_session\n'
        "    connection = engine.connect()\n"
        "sqlalchemy.exc.OperationalError: could not connect to server: Connection refused"
    )

    result = investigate(raw)

    #  result level 
    assert result.status == "known"
    assert result.parsed_error["error_type"] == "sqlalchemy.exc.OperationalError"
    assert result.knowledge is not None
    assert result.investigation is not None

    #  output level 
    output = format_result(result)
    assert "sqlalchemy.exc.OperationalError" in output
    assert "pool" in output.lower()
    assert "connection" in output.lower()



def test_value_error_end_to_end():
    raw = (
        "Traceback (most recent call last):\n"
        '  File "app/parsing.py", line 18, in parse_age\n'
        '    age = int(user_input)\n'
        "ValueError: invalid literal for int() with base 10: 'abc'"
    )

    result = investigate(raw)

    #  result level 
    assert result.status == "known"
    assert result.parsed_error["error_type"] == "ValueError"
    assert result.knowledge is not None
    assert result.investigation is not None

    #  output level 
    output = format_result(result)
    assert "ValueError" in output
    assert "int(" in output
    assert "pydantic" in output.lower() or "validate" in output.lower()


def test_known_result_never_has_empty_summary():
    samples = [
        "sqlalchemy.exc.IntegrityError: duplicate key violates unique constraint",
        "sqlalchemy.exc.OperationalError: could not connect to server",
        "ValueError: invalid literal for int() with base 10: 'abc'",
    ]

    for raw in samples:
        result = investigate(raw)
        assert result.status == "known", f"expected known for: {raw}"
        assert result.investigation is not None
        assert result.investigation.summary.strip(), (
            f"empty summary for: {raw}"
        )

def test_data_error_end_to_end():
    """Real traceback -> known result -> useful output for a DB data-validation error."""
    raw = (
        "Traceback (most recent call last):\n"
        '  File "app/users.py", line 61, in create_user\n'
        "    session.add(user)\n"
        "sqlalchemy.exc.DataError: value too long for type character varying(50)"
    )

    result = investigate(raw)

    #  result level 
    assert result.status == "known"
    assert result.parsed_error["error_type"] == "sqlalchemy.exc.DataError"
    assert result.knowledge is not None
    assert result.investigation is not None

    #  output level 
    output = format_result(result)
    assert "sqlalchemy.exc.DataError" in output
    # Content unique to the DataError KB entry:
    assert "varchar" in output.lower() or "column" in output.lower()
    assert "coerce" in output.lower() or "validate" in output.lower()

def test_key_error_end_to_end():
    """Real traceback -> known result -> useful output for a Python lookup error."""
    raw = (
        "Traceback (most recent call last):\n"
        '  File "app/handlers.py", line 27, in handle_response\n'
        '    email = response["user"]["email"]\n'
        "KeyError: 'email'"
    )

    result = investigate(raw)

    #  result level 
    assert result.status == "known"
    assert result.parsed_error["error_type"] == "KeyError"
    assert result.knowledge is not None
    assert result.investigation is not None

    #  output level 
    output = format_result(result)
    assert "KeyError" in output
    # Content unique to the KeyError KB entry:
    assert ".get(" in output or "get(key" in output.lower()
    assert "defaultdict" in output.lower() or "keys()" in output