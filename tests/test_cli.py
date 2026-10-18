"""Tests for investigator.cli."""

import runpy
import sys
import pytest
from typer.testing import CliRunner

from investigator.cli import app

runner = CliRunner()

# Text that must never appear in output for expected user/config errors.
_NO_TRACEBACK = ("Traceback", "raise ", "Traceback (most recent call last)")


def _assert_no_traceback(output: str) -> None:
    for marker in _NO_TRACEBACK:
        assert marker not in output, f"unexpected traceback marker: {marker!r}"


def _write_valid_entry(dir_, error_type: str = "MyCustomError") -> None:
    (dir_ / "custom.yaml").write_text(
        f"error_type: {error_type}\n"
        "aliases: []\n"
        "category: custom\n"
        "summary: custom summary\n"
        "explanation: custom explanation\n"
        "common_causes: [c1]\n"
        "fixes: [f1]\n"
        "related_errors: []\n",
        encoding="utf-8",
    )


# ------------------------------------------------------------------ help

def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Error Investigator" in result.output
    # Single-command CLI: stops advertising COMMAND it doesn't have.
    assert "Usage: investigate [OPTIONS]" in result.output
    assert "COMMAND" not in result.output
    # The new flag must be documented.
    assert "--kb-dir" in result.output


# ------------------------------------------------------------------ piped

def test_cli_investigate_known_error_piped():
    result = runner.invoke(
        app,
        [],
        input="ValueError: invalid literal for int() with base 10: 'abc'\n",
    )
    assert result.exit_code == 0
    assert "Error: ValueError" in result.output
    assert "Status: KNOWN" in result.output
    assert "Summary:" in result.output
    assert "Explanation:" in result.output
    # Piped input must not trigger the interactive prompt or instructions.
    assert "Paste your error below" not in result.output
    assert "Type 'DONE'" not in result.output


def test_cli_investigate_unknown_error_piped():
    result = runner.invoke(
        app,
        [],
        input="TotallyUnknownError: something broke\n",
    )
    assert result.exit_code == 0
    assert "Error: TotallyUnknownError" in result.output
    assert "Status: UNKNOWN" in result.output
    assert "Paste your error below" not in result.output
    assert "Type 'DONE'" not in result.output


def test_cli_investigate_empty_input_exits_with_code_1():
    result = runner.invoke(app, [], input="")
    assert result.exit_code == 1
    assert "No error text captured. Exiting." in result.output
    _assert_no_traceback(result.output)


def test_cli_investigate_whitespace_input_exits_with_code_1():
    result = runner.invoke(app, [], input="   \n\t  \n  \n")
    assert result.exit_code == 1
    assert "No error text captured. Exiting." in result.output
    _assert_no_traceback(result.output)


def test_cli_investigate_garbage_text_piped():
    result = runner.invoke(
        app,
        [],
        input="2026-10-18 12:00:00 [INFO] System is normal\n",
    )
    assert result.exit_code == 0
    assert "Status: UNKNOWN" in result.output
    _assert_no_traceback(result.output)


def test_cli_investigate_multiline_traceback_piped():
    traceback_text = (
        "Traceback (most recent call last):\n"
        '  File "app/service.py", line 42, in process_item\n'
        "    item = db.query(Item).filter_by(id=item_id).one()\n"
        '  File "sqlalchemy/orm/query.py", line 2800, in one\n'
        "    raise NoResultFound()\n"
        "sqlalchemy.exc.IntegrityError: duplicate key value violates unique constraint\n"
    )
    result = runner.invoke(app, [], input=traceback_text)
    assert result.exit_code == 0
    assert "Status: KNOWN" in result.output
    assert "Error: sqlalchemy.exc.IntegrityError" in result.output
    assert "Summary:" in result.output
    assert "Paste your error below" not in result.output


def test_cli_investigate_unicode_and_crlf_piped():
    raw = "ValueError: invalid character '§' in field '名前'\r\n"
    result = runner.invoke(app, [], input=raw)
    assert result.exit_code == 0
    assert "Status: KNOWN" in result.output
    assert "Error: ValueError" in result.output


# ---------------------------------------------------- interactive flow (TTY)

def test_cli_investigate_interactive_flow(monkeypatch):
    monkeypatch.setattr("typer.testing._NamedTextIOWrapper.isatty", lambda self: True)
    result = runner.invoke(
        app,
        [],
        input="ValueError: invalid input\nDONE\n",
    )
    assert result.exit_code == 0
    assert "Paste your error below" in result.output
    assert "Type 'DONE'" in result.output
    assert "Error: ValueError" in result.output
    assert "Status: KNOWN" in result.output


def test_cli_investigate_interactive_case_insensitive_done(monkeypatch):
    monkeypatch.setattr("typer.testing._NamedTextIOWrapper.isatty", lambda self: True)
    result = runner.invoke(
        app,
        [],
        input="ValueError: invalid input\ndone\n",
    )
    assert result.exit_code == 0
    assert "Status: KNOWN" in result.output


def test_cli_investigate_interactive_immediate_done_exits_with_code_1(monkeypatch):
    monkeypatch.setattr("typer.testing._NamedTextIOWrapper.isatty", lambda self: True)
    result = runner.invoke(app, [], input="DONE\n")
    assert result.exit_code == 1
    assert "Paste your error below" in result.output
    assert "No error text captured. Exiting." in result.output
    _assert_no_traceback(result.output)


def test_cli_investigate_interactive_eof(monkeypatch):
    monkeypatch.setattr("typer.testing._NamedTextIOWrapper.isatty", lambda self: True)
    result = runner.invoke(app, [], input="ValueError: bad input\n")
    assert result.exit_code == 0
    assert "Error: ValueError" in result.output
    assert "Status: KNOWN" in result.output


# ----------------------------------------------------------------- callback

def test_cli_main_callback():
    result = runner.invoke(app, [], input="")
    assert result.exit_code == 1
    assert "No error text captured. Exiting." in result.output


# --------------------------------------------------------------- --kb-dir

def test_cli_custom_kb_dir_known_piped(tmp_path):
    _write_valid_entry(tmp_path)
    result = runner.invoke(
        app,
        ["--kb-dir", str(tmp_path)],
        input="MyCustomError: something went wrong\n",
    )
    assert result.exit_code == 0
    assert "Error: MyCustomError" in result.output
    assert "Status: KNOWN" in result.output
    assert "Summary:" in result.output


def test_cli_custom_kb_dir_relative_path(tmp_path, monkeypatch):
    _write_valid_entry(tmp_path)
    monkeypatch.chdir(tmp_path.parent)
    rel_path = tmp_path.name
    result = runner.invoke(
        app,
        ["--kb-dir", rel_path],
        input="MyCustomError: boom\n",
    )
    assert result.exit_code == 0
    assert "Error: MyCustomError" in result.output
    assert "Status: KNOWN" in result.output


def test_cli_custom_kb_dir_nonexistent(tmp_path):
    missing_dir = tmp_path / "nonexistent"
    result = runner.invoke(app, ["--kb-dir", str(missing_dir)])
    assert result.exit_code == 1
    assert "knowledge directory does not exist" in result.output
    _assert_no_traceback(result.output)


def test_cli_custom_kb_dir_file(tmp_path):
    file_path = tmp_path / "some_file.txt"
    file_path.write_text("hello", encoding="utf-8")
    result = runner.invoke(app, ["--kb-dir", str(file_path)])
    assert result.exit_code == 1
    assert "knowledge directory is not a directory" in result.output
    _assert_no_traceback(result.output)


def test_cli_custom_kb_dir_empty(tmp_path):
    """An explicit directory with no YAML entries must fail loudly."""
    result = runner.invoke(
        app,
        ["--kb-dir", str(tmp_path)],
        input="ValueError: invalid input\n",
    )
    assert result.exit_code == 1
    assert "contains no entries" in result.output
    _assert_no_traceback(result.output)


def test_cli_custom_kb_dir_malformed_yaml(tmp_path):
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("invalid: [yaml\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["--kb-dir", str(tmp_path)],
        input="ValueError: invalid input\n",
    )
    assert result.exit_code == 1
    assert "Knowledge base error:" in result.output
    assert "invalid YAML" in result.output
    _assert_no_traceback(result.output)


def test_cli_custom_kb_dir_collision(tmp_path):
    _write_valid_entry(tmp_path, error_type="DupError")
    (tmp_path / "dup.yaml").write_text(
        "error_type: DupError\n"
        "aliases: []\n"
        "category: custom\n"
        "summary: custom summary 2\n"
        "explanation: custom explanation 2\n"
        "common_causes: []\n"
        "fixes: []\n"
        "related_errors: []\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        ["--kb-dir", str(tmp_path)],
        input="DupError: test\n",
    )
    assert result.exit_code == 1
    assert "Knowledge base error:" in result.output
    assert "collision on identifier" in result.output
    _assert_no_traceback(result.output)


# ---------------------------------------------------- invocation errors

def test_cli_invalid_option():
    result = runner.invoke(app, ["--nonexistent-option"])
    assert result.exit_code == 2
    _assert_no_traceback(result.output)


def test_cli_extraneous_argument_or_old_subcommand():
    result = runner.invoke(app, ["investigate"])
    assert result.exit_code == 2
    assert "unexpected extra argument" in result.output.lower()
    assert "no such command" not in result.output.lower()
    _assert_no_traceback(result.output)


# --------------------------------------------------- __main__ execution

def test_cli_module_main_execution(monkeypatch):
    monkeypatch.setattr("sys.argv", ["investigate", "--help"])
    monkeypatch.delitem(sys.modules, "investigator.cli", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("investigator.cli", run_name="__main__")
    assert exc_info.value.code == 0

def test_cli_custom_kb_dir_empty_fails_before_prompt(tmp_path):
    """Empty explicit dir must fail before prompting the user for input."""
    result = runner.invoke(app, ["--kb-dir", str(tmp_path)])  # no input=
    assert result.exit_code == 1
    assert "contains no entries" in result.output
    assert "Paste your error below" not in result.output
    _assert_no_traceback(result.output)


def test_cli_custom_kb_dir_malformed_fails_before_prompt(tmp_path):
    (tmp_path / "bad.yaml").write_text("invalid: [yaml\n", encoding="utf-8")
    result = runner.invoke(app, ["--kb-dir", str(tmp_path)])  # no input=
    assert result.exit_code == 1
    assert "invalid YAML" in result.output
    assert "Paste your error below" not in result.output
    _assert_no_traceback(result.output)


def test_cli_custom_kb_dir_collision_fails_before_prompt(tmp_path):
    _write_valid_entry(tmp_path, error_type="DupError")
    (tmp_path / "dup.yaml").write_text(
        "error_type: DupError\n"
        "aliases: []\n"
        "category: custom\n"
        "summary: custom summary 2\n"
        "explanation: custom explanation 2\n"
        "common_causes: []\n"
        "fixes: []\n"
        "related_errors: []\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["--kb-dir", str(tmp_path)])  # no input=
    assert result.exit_code == 1
    assert "collision on identifier" in result.output
    assert "Paste your error below" not in result.output
    _assert_no_traceback(result.output)


def test_cli_default_kb_corrupted_raises(monkeypatch, tmp_path):
    import investigator.knowledge_loader as loader
    import investigator.knowledge_lookup as lookup_mod
    monkeypatch.setattr(loader, "_KNOWLEDGE_DIR", tmp_path)
    lookup_mod.reset_cache()
    (tmp_path / "bad.yaml").write_text("invalid: [yaml\n", encoding="utf-8")
    result = runner.invoke(app, [], input="ValueError: err\n")
    assert result.exit_code == 1
    assert "Knowledge base error:" in result.output
    _assert_no_traceback(result.output)