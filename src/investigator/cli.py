"""CLI commands and entry point for error-investigator."""

from pathlib import Path

import typer

from investigator.cli_format import format_result
from investigator.investigator import investigate as run_investigation
from investigator.io_utils import capture_multiline
from investigator.knowledge_loader import KnowledgeEntryError, load_all_entries

app = typer.Typer(name="investigate")


def _run_workflow(kb_dir: Path | None = None) -> None:
    """Capture an error, investigate it, and print the formatted result."""
    if kb_dir is not None:
        try:
            load_all_entries(kb_dir)
        except KnowledgeEntryError as exc:
            typer.secho(f"\nKnowledge base error: {exc}", fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc

    raw_error = capture_multiline("\nPaste your error below.")

    if not raw_error:
        typer.secho(
            "\nNo error text captured. Exiting.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    try:
        result = run_investigation(raw_error, kb_dir=kb_dir)
    except KnowledgeEntryError as exc:
        typer.secho(f"\nKnowledge base error: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    output = format_result(result)

    typer.echo("")
    typer.echo(output)


@app.command(name="investigate")
def main(
    kb_dir: Path | None = typer.Option(
        None,
        "--kb-dir",
        help="Path to a custom knowledge base directory.",
        exists=False,
    ),
) -> None:
    """Error Investigator — a CLI developer tool for investigating Python and API errors."""
    _run_workflow(kb_dir)


if __name__ == "__main__":
    app()