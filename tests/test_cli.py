"""Tests for investigator.cli."""

from typer.testing import CliRunner

from investigator.cli import app, main

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "AI API Error Investigator" in result.output
    assert "investigate" in result.output


def test_cli_investigate_help():
    result = runner.invoke(app, ["investigate", "--help"])
    assert result.exit_code == 0
    assert "Investigate an error pasted from stdin." in result.output


def test_cli_investigate_known_error_piped():
    result = runner.invoke(
        app,
        ["investigate"],
        input="ValueError: invalid literal for int() with base 10: 'abc'\n",
    )
    assert result.exit_code == 0
    assert "Error: ValueError" in result.output
    assert "Summary:" in result.output
    assert "Explanation:" in result.output


def test_cli_investigate_unknown_error_piped():
    result = runner.invoke(
        app,
        ["investigate"],
        input="TotallyUnknownError: something broke\n",
    )
    assert result.exit_code == 0
    assert "Error: TotallyUnknownError" in result.output
    assert "Status: UNKNOWN" in result.output


def test_cli_investigate_empty_input_exits_with_code_1():
    result = runner.invoke(app, ["investigate"], input="")
    assert result.exit_code == 1
    assert "No error text captured. Exiting." in result.output


def test_cli_investigate_interactive(monkeypatch):
    monkeypatch.setattr(
        "investigator.cli.capture_multiline",
        lambda prompt: "ValueError: invalid input",
    )
    result = runner.invoke(app, ["investigate"])
    assert result.exit_code == 0
    assert "Error: ValueError" in result.output


def test_cli_main_callback():
    assert main() is None
