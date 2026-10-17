"""Tests for investigator.cli."""

from typer.testing import CliRunner

from investigator.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Error Investigator" in result.output


def test_cli_investigate_known_error_piped():
    result = runner.invoke(
        app,
        [],
        input="ValueError: invalid literal for int() with base 10: 'abc'\n",
    )
    assert result.exit_code == 0
    assert "Error: ValueError" in result.output
    assert "Summary:" in result.output
    assert "Explanation:" in result.output


def test_cli_investigate_unknown_error_piped():
    result = runner.invoke(
        app,
        [],
        input="TotallyUnknownError: something broke\n",
    )
    assert result.exit_code == 0
    assert "Error: TotallyUnknownError" in result.output
    assert "Status: UNKNOWN" in result.output


def test_cli_investigate_empty_input_exits_with_code_1():
    result = runner.invoke(app, [], input="")
    assert result.exit_code == 1
    assert "No error text captured. Exiting." in result.output


def test_cli_investigate_interactive(monkeypatch):
    monkeypatch.setattr(
        "investigator.cli.capture_multiline",
        lambda prompt: "ValueError: invalid input",
    )
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Error: ValueError" in result.output


def test_cli_main_callback():
    result = runner.invoke(app, [], input="")
    assert result.exit_code == 1
    assert "No error text captured. Exiting." in result.output