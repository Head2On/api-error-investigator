import pytest

from investigator.cli_format import format_result
from investigator.error_parser import parse_error
from investigator.investigator import investigate

import investigator.knowledge_loader as loader
import investigator.knowledge_lookup as lookup_mod

#  1. empty / whitespace

class TestEmptyAndWhitespace:
    """Assumption: empty or whitespace input is handled without crashing."""

    def test_empty_string_returns_unknown(self):
        result = investigate("")
        assert result.status == "unknown"
        assert result.parsed_error["error_type"] is None
        assert result.parsed_error["stack_trace"] == ""

    def test_whitespace_only_returns_unknown(self):
        result = investigate("   \n\t  \n  ")
        assert result.status == "unknown"
        assert result.parsed_error["error_type"] is None

    def test_newlines_only_returns_unknown(self):
        result = investigate("\n\n\n\n")
        assert result.status == "unknown"

    def test_format_does_not_crash_on_empty_input(self):
        result = investigate("")
        output = format_result(result)
        assert "Status: UNKNOWN" in output
        assert "Error: (unrecognized)" in output


#  2. malformed traceback

class TestMalformedTraceback:
    """Assumption: partial tracebacks are handled without crashing."""

    def test_frames_without_error_line(self):
        raw = (
            "Traceback (most recent call last):\n"
            '  File "app/main.py", line 10, in main\n'
            "    do_work()\n"
            '  File "app/work.py", line 20, in do_work\n'
            "    inner()\n"
        )
        result = investigate(raw)
        assert result.status == "unknown"
        assert result.parsed_error["error_type"] is None

    def test_error_line_without_traceback_header(self):
        """Some tools emit just the error line without a Traceback header."""
        raw = "ValueError: something went wrong"
        result = investigate(raw)
        assert result.status == "known"
        assert result.parsed_error["error_type"] == "ValueError"

    def test_truncated_traceback_missing_last_line(self):
        """Traceback cut off mid-frame."""
        raw = (
            "Traceback (most recent call last):\n"
            '  File "app/main.py", line 10, in main\n'
            "    do_work()\n"
            '  File "app/work.py", line 20, in do_work\n'
        )
        result = investigate(raw)
        assert result.status == "unknown"
        assert result.parsed_error["stack_trace"] == raw

    def test_header_alone(self):
        result = investigate("Traceback (most recent call last):")
        assert result.status == "unknown"


#  3. error with missing message

class TestMissingMessage:
    """Assumption: error_type without a message is still recognized."""

    def test_error_type_without_message(self):
        """'ValueError' alone — no colon, no message."""
        result = investigate("ValueError")
    
        if result.status == "known":
            assert result.parsed_error["error_type"] == "ValueError"
            assert result.parsed_error["message"] is None

    def test_error_type_with_empty_message(self):
        result = investigate("ValueError:")
        if result.status == "known":
            assert result.parsed_error["error_type"] == "ValueError"
            assert result.parsed_error["message"] in (None, "")

    def test_error_type_with_only_whitespace_message(self):
        result = investigate("ValueError:    ")
        assert result.status in ("known", "unknown")


#  4. unusual multiline

class TestUnusualMultiline:
    """Assumption: odd-but-valid multiline input doesn't confuse the pipeline."""

    def test_very_long_single_line(self):
        raw = "ValueError: " + ("x" * 100_000)
        result = investigate(raw)
        assert result.status == "known"
        assert result.parsed_error["error_type"] == "ValueError"

    def test_many_lines(self):
        """Traceback with 500 frames."""
        lines = ["Traceback (most recent call last):"]
        for i in range(500):
            lines.append(f'  File "app/file{i}.py", line {i}, in func{i}')
            lines.append(f"    call_{i}()")
        lines.append("RuntimeError: boom")
        result = investigate("\n".join(lines))
        assert result.status == "unknown"
        assert result.parsed_error["error_type"] == "RuntimeError"
        assert result.parsed_error["function"] == "func499"

    def test_carriage_returns(self):
        """Windows-style line endings."""
        raw = "Traceback (most recent call last):\r\n" \
              '  File "app/main.py", line 5, in main\r\n' \
              "    x()\r\n" \
              "ValueError: bad\r\n"
        result = investigate(raw)
        assert result.status == "known"
        assert result.parsed_error["error_type"] == "ValueError"
        assert result.parsed_error["file"] == "app/main.py"

    def test_leading_and_trailing_whitespace_around_traceback(self):
        raw = (
            "\n\n   \n"
            "Traceback (most recent call last):\n"
            '  File "app/main.py", line 5, in main\n'
            "ValueError: bad\n"
            "\n\n   \n"
        )
        result = investigate(raw)
        assert result.status == "known"
        assert result.parsed_error["error_type"] == "ValueError"


#  5. parser recognizes, KB doesn't

class TestParserKnownButKbUnknown:
    """Assumption: parser success + KB miss yields unknown, not a crash."""

    def test_real_python_error_not_in_kb(self):
        result = investigate("RuntimeError: something broke")
        assert result.status == "unknown"
        # Parser still extracted it:
        assert result.parsed_error["error_type"] == "RuntimeError"
        # KB had nothing:
        assert result.knowledge is None
        assert result.investigation is None

    def test_custom_exception_not_in_kb(self):
        result = investigate("app.errors.MyCustomError: boom")
        assert result.status == "unknown"
        assert result.parsed_error["error_type"] == "app.errors.MyCustomError"

    def test_format_of_known_shape_but_unknown(self):
        result = investigate("RuntimeError: boom")
        output = format_result(result)
        assert "Error: RuntimeError" in output
        assert "Status: UNKNOWN" in output
        # Must not fabricate sections:
        assert "Summary:" not in output


#  6. optional KB fields missing

class TestOptionalKbFieldsMissing:
    """Assumption: KB entries with missing optional fields still work."""

    def test_kb_entry_with_empty_related_errors_formats_cleanly(self, monkeypatch, tmp_path):

        entry = (
            "error_type: test.EmptyListsError\n"
            "aliases: []\n"
            "category: test\n"
            "subcategory: null\n"
            "summary: Test summary.\n"
            "explanation: Test explanation.\n"
            "common_causes: []\n"
            "fixes: []\n"
            "docs_url: null\n"
            "related_errors: []\n"
        )
        (tmp_path / "test_empty_lists.yaml").write_text(entry, encoding="utf-8")

        monkeypatch.setattr(loader, "_KNOWLEDGE_DIR", tmp_path)
        lookup_mod.reset_cache()

        try:
            raw = "test.EmptyListsError: something"
            result = investigate(raw)
            assert result.status == "known"
            assert result.investigation is not None
            assert result.investigation.common_causes == []
            assert result.investigation.fixes == []
            assert result.investigation.related_errors == []

            output = format_result(result)
            assert "Summary:" in output
            assert "Explanation:" in output
            assert "Common Causes:" not in output
            assert "Fixes:" not in output
            assert "Documentation:" not in output
            assert "Related Errors:" not in output
        finally:
            lookup_mod.reset_cache()


#  7. unusual error-type shapes

class TestUnusualErrorTypes:
    """Assumption: parser doesn't over-match or under-match odd names."""

    def test_very_deep_dotted_name(self):
        result = investigate("a.b.c.d.e.f.DeepError: boom")
        assert result.parsed_error["error_type"] == "a.b.c.d.e.f.DeepError"

    def test_name_with_unicode(self):
        raw = "Module.ÜnicodeError: boom"
        result = investigate(raw)

        assert result.status in ("known", "unknown")

    def test_error_type_with_trailing_whitespace(self):
        result = investigate("ValueError  :  something")
       
        assert result.status in ("known", "unknown")

    def test_error_type_lowercase(self):
        """'valueError: boom' — parser regex accepts any [A-Za-z_] start."""
        result = investigate("valueError: boom")
        
        if result.parsed_error["error_type"] is not None:
            assert result.parsed_error["error_type"] == "valueError"


#  8. format boundary conditions

class TestFormatBoundaries:
    """Assumption: format_result never crashes on any valid result."""

    def test_format_of_unknown_with_none_error_type(self):
        result = investigate("not an error")
        output = format_result(result)
        assert "Error: (unrecognized)" in output
        assert "Status: UNKNOWN" in output

    def test_format_output_never_contains_literal_none(self):
        """'None' must never appear as a user-facing value in unknown output."""
        for raw in ["", "   ", "not an error", "garbage\nmore garbage"]:
            result = investigate(raw)
            output = format_result(result)
            assert "Error: None" not in output
            assert "Summary: None" not in output
            assert "Explanation: None" not in output


#  9. idempotency / caching

class TestIdempotency:
    """Assumption: repeated calls give identical results (no cache surprises)."""

    def test_repeated_known_calls_are_stable(self):
        raw = (
            "Traceback (most recent call last):\n"
            '  File "app/db.py", line 10, in save\n'
            "    db.commit()\n"
            "sqlalchemy.exc.IntegrityError: duplicate key"
        )
        first = investigate(raw)
        for _ in range(50):
            again = investigate(raw)
            assert again.status == first.status
            assert again.parsed_error == first.parsed_error
            assert again.knowledge == first.knowledge

    def test_alternating_known_unknown_is_stable(self):
        known = "ValueError: bad"
        unknown = "TotallyFakeError: boom"
        for _ in range(20):
            assert investigate(known).status == "known"
            assert investigate(unknown).status == "unknown"