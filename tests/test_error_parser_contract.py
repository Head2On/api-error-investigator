
import pytest
from investigator.error_parser import parse_error


#  error candidate:
# suffix rule (existing behavior preserved)

@pytest.mark.parametrize("name", [
    "ValueError",
    "RuntimeError",
    "SomeException",
    "DeprecationWarning",
    "SystemExit",
    "sqlalchemy.exc.IntegrityError",
    "sqlalchemy.exc.OperationalError",
])
def test_suffix_rule_accepts(name):
    result = parse_error(f"{name}: message")
    assert result["error_type"] == name


#  error candidate:
# capitalized final segment (new rule)

@pytest.mark.parametrize("name", [
    "foo.bar.Timeout",
    "httpx.ConnectTimeout",
    "google.api_core.exceptions.DeadlineExceeded",
    "KeyboardInterrupt",
    "StopIteration",
    "GeneratorExit",       # also matches Exit suffix, fine
    "SomeVariable",        # capital + no colon
])
def test_capitalized_rule_accepts(name):
    result = parse_error(f"{name}: message")
    assert result["error_type"] == name


#  non-candidates

@pytest.mark.parametrize("line", [
    "some.random.text: hello",
    "some.random.text",
    "this is a sentence: with a colon",
    "user_id: 42",
    "config.value: enabled",
])
def test_non_candidates_rejected(line):
    result = parse_error(line)
    assert result["error_type"] is None


#  boundary cases
# explicit per partner's request

def test_capitalized_but_ambiguous_is_candidate():
    """`some.random.Text` is structurally class-shaped → candidate.
    KB will return UNKNOWN for it, but parser accepts it."""
    result = parse_error("some.random.Text: hello")
    assert result["error_type"] == "some.random.Text"


def test_bare_capitalized_identifier_is_candidate():
    """A standalone capitalized identifier is accepted as a candidate."""
    result = parse_error("SomeVariable")
    assert result["error_type"] == "SomeVariable"


def test_bare_capitalized_identifier_uses_bottom_up_scan():
    """The identifier must be the last recognized candidate line,
    not any capitalized word earlier in the input."""
    raw = (
        "SomeVariable\n"
        "Then some more application output\n"
        "all lowercase lines follow\n"
    )
    result = parse_error(raw)

    assert result["error_type"] == "SomeVariable"


#  suffix fast path
# ensure suffix rule doesn't get shadowed by the capitalized rule

def test_suffix_rule_still_wins_for_lowercase_suffix():
    """A lowercase-named exception ending in Error still matches via suffix."""
    result = parse_error("my_module.myError: boom")
    assert result["error_type"] == "my_module.myError"


#  SyntaxError frames

def test_syntax_error_frame_without_function():
    """SyntaxError frame lines have no ', in <function>'."""
    raw = (
        '  File "foo.py", line 1\n'
        "    def f(:\n"
        "         ^\n"
        "SyntaxError: invalid syntax"
    )
    result = parse_error(raw)
    assert result["error_type"] == "SyntaxError"
    assert result["file"] == "foo.py"
    assert result["line"] == 1
    assert result["function"] is None


def test_normal_frame_still_parses_function():
    """Regression: adding optional ', in ...' must not break normal frames."""
    raw = (
        "Traceback (most recent call last):\n"
        '  File "app/service.py", line 84, in create_patient\n'
        "    db.add(patient)\n"
        "ValueError: bad input"
    )
    result = parse_error(raw)
    assert result["file"] == "app/service.py"
    assert result["line"] == 84
    assert result["function"] == "create_patient"


#  end-to-end
# parser through the pipeline

def test_httpx_timeout_flows_through_pipeline_as_unknown():
    """Real-world `httpx` error — candidate but not in KB → UNKNOWN."""
    from investigator.investigator import investigate

    raw = "httpx.ConnectTimeout: connection attempt timed out"
    result = investigate(raw)
    assert result.parsed_error["error_type"] == "httpx.ConnectTimeout"
    # KB has no entry for this → unknown, but parser did its job.
    assert result.status == "unknown"


def test_keyboard_interrupt_flows_through_pipeline_as_unknown():
    from investigator.investigator import investigate

    result = investigate("KeyboardInterrupt")
    assert result.parsed_error["error_type"] == "KeyboardInterrupt"
    assert result.status == "unknown"