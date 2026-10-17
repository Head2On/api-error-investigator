"""CLI commands and entry point for error-investigator."""

import typer

from investigator.cli_format import format_result
from investigator.investigator import investigate as run_investigation
from investigator.io_utils import capture_multiline

app = typer.Typer()


def _run_workflow() -> None:
    """Capture an error, investigate it, and print the formatted result."""
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


@app.callback(invoke_without_command=True)
def main(ctx:typer.Context) -> None:
    """Error Investigator — a CLI developer tool for investigating Python and API errors"""

    if ctx.invoked_subcommand is None:
        _run_workflow()


if __name__ == "__main__":
    app()