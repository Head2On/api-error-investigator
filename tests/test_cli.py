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


def test_cli_custom_kb_dir_known_piped(tmp_path):
    custom_yaml = tmp_path / "custom.yaml"
    custom_yaml.write_text(
        "error_type: MyCustomError\n"
        "aliases: []\n"
        "category: custom\n"
        "summary: custom summary\n"
        "explanation: custom explanation\n"
        "common_causes: [c1]\n"
        "fixes: [f1]\n"
        "related_errors: []\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        ["--kb-dir", str(tmp_path)],
        input="MyCustomError: something went wrong\n",
    )
    assert result.exit_code == 0
    assert "Error: MyCustomError" in result.output
    assert "Summary:" in result.output


def test_cli_custom_kb_dir_nonexistent(tmp_path):
    missing_dir = tmp_path / "nonexistent"
    result = runner.invoke(app, ["--kb-dir", str(missing_dir)])
    assert result.exit_code == 1
    assert "knowledge directory does not exist" in result.output


def test_cli_custom_kb_dir_file(tmp_path):
    file_path = tmp_path / "some_file.txt"
    file_path.write_text("hello", encoding="utf-8")
    result = runner.invoke(app, ["--kb-dir", str(file_path)])
    assert result.exit_code == 1
    assert "knowledge directory is not a directory" in result.output


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