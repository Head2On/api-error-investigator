import typer

from investigator.cli_format import format_result
from investigator.investigator import investigate as run_investigation
from investigator.io_utils import capture_multiline

app = typer.Typer()


@app.callback()
def main() -> None:
    """AI API Error Investigator — a developer tool for investigating AI API errors."""


@app.command("investigate")
def investigate_command() -> None:
    """Investigate an error pasted from stdin."""
    raw_error = capture_multiline("\nPaste your error below.")

    if not raw_error:
        typer.secho(
            "\nNo error text captured. Exiting.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    result = run_investigation(raw_error)
    output = format_result(result)

    typer.echo("")
    typer.echo(output)


if __name__ == "__main__":
    app()