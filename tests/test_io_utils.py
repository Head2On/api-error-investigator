import io
import sys

import pytest

from investigator.io_utils import capture_multiline


# ---------------------------------------------------------------- helpers

class _FakeStdin:
    """Minimal stdin replacement that reports a chosen isatty() value
    and yields chosen content for read()."""
    def __init__(self, content: str, is_tty: bool):
        self._content = content
        self._is_tty = is_tty

    def isatty(self) -> bool:
        return self._is_tty

    def read(self) -> str:
        return self._content


# ============================================================ interactive mode

class TestInteractiveMode:
    """When stdin is a TTY, capture_multiline prompts and honors DONE."""

    def test_prompts_are_printed(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", _FakeStdin("", is_tty=True))
        # Simulate the user typing DONE immediately.
        monkeypatch.setattr("builtins.input", lambda *a, **k: "DONE")

        capture_multiline("Paste your error below.")

        out = capsys.readouterr().out
        assert "Paste your error below." in out
        assert "DONE" in out

    def test_multi_line_until_done(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", _FakeStdin("", is_tty=True))
        lines = iter(["line one", "line two", "line three", "DONE"])
        monkeypatch.setattr("builtins.input", lambda *a, **k: next(lines))

        result = capture_multiline("prompt")

        assert result == "line one\nline two\nline three"

    def test_empty_interactive_returns_empty_string(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", _FakeStdin("", is_tty=True))
        monkeypatch.setattr("builtins.input", lambda *a, **k: "DONE")

        result = capture_multiline("prompt")
        assert result == ""

    def test_eof_interactive_returns_captured(self, monkeypatch):
        """If input() raises EOFError before DONE, return what we have."""
        monkeypatch.setattr(sys, "stdin", _FakeStdin("", is_tty=True))
        lines = iter(["first", "second"])

        def feed(*a, **k):
            try:
                return next(lines)
            except StopIteration:
                raise EOFError

        monkeypatch.setattr("builtins.input", feed)
        result = capture_multiline("prompt")
        assert result == "first\nsecond"


# ================================================================== pipe mode

class TestPipeMode:
    """When stdin is not a TTY, capture_multiline reads silently."""

    def test_piped_content_captured(self, monkeypatch, capsys):
        monkeypatch.setattr(
            sys, "stdin",
            _FakeStdin("Traceback (most recent call last):\nValueError: bad\n", is_tty=False),
        )

        result = capture_multiline("Paste your error below.")

        assert result == "Traceback (most recent call last):\nValueError: bad"

    def test_no_prompts_in_pipe_mode(self, monkeypatch, capsys):
        monkeypatch.setattr(
            sys, "stdin",
            _FakeStdin("some error text\n", is_tty=False),
        )

        capture_multiline("Paste your error below.")

        out = capsys.readouterr().out
        assert out == "", f"pipe mode must not write to stdout, got: {out!r}"

    def test_done_sentinel_not_required_in_pipe_mode(self, monkeypatch):
        """DONE is only a terminal convention. Piped input ends at EOF."""
        monkeypatch.setattr(
            sys, "stdin",
            _FakeStdin("line one\nline two\nDONE\nline four\n", is_tty=False),
        )

        result = capture_multiline("prompt")

        # DONE is treated as ordinary content in pipe mode.
        assert result == "line one\nline two\nDONE\nline four"

    def test_outer_whitespace_trimmed_in_pipe_mode(self, monkeypatch):
        monkeypatch.setattr(
            sys, "stdin",
            _FakeStdin("\n\n  error text  \n\n", is_tty=False),
        )

        result = capture_multiline("prompt")
        assert result == "error text"

    def test_empty_pipe_returns_empty_string(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", _FakeStdin("", is_tty=False))

        result = capture_multiline("prompt")
        assert result == ""

    def test_inner_content_preserved_unchanged(self, monkeypatch):
        """Multi-line, indented, blank-line-containing content survives intact."""
        content = (
            "Traceback (most recent call last):\n"
            '  File "app/main.py", line 10, in main\n'
            "    do_work()\n"
            "\n"
            "ValueError: bad input\n"
        )
        monkeypatch.setattr(sys, "stdin", _FakeStdin(content, is_tty=False))

        result = capture_multiline("prompt")

        assert result == content.rstrip()
        assert "\n\n" in result  
        assert "  File" in result 


# ==================================================== cross-mode equivalence

class TestEmptyBehaviorEquivalence:
    """Empty input produces empty string in both modes."""

    def test_empty_interactive(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", _FakeStdin("", is_tty=True))
        monkeypatch.setattr("builtins.input", lambda *a, **k: "DONE")
        assert capture_multiline("p") == ""

    def test_empty_pipe(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", _FakeStdin("", is_tty=False))
        assert capture_multiline("p") == ""


# ==================================================== public surface check

class TestModuleSurface:
    """A-022 Part 5 — after display_snippet removal, io_utils exposes
    exactly one public function: capture_multiline."""

    def test_io_utils_exports_only_capture_multiline(self):
        import investigator.io_utils as io_utils
        public = {
            name for name in dir(io_utils)
            if not name.startswith("_")
            and callable(getattr(io_utils, name))
            and getattr(io_utils, name).__module__ == io_utils.__name__
        }
        assert public == {"capture_multiline"}