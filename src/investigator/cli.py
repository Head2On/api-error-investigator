"""CLI commands and entry point for error-investigator."""

from pathlib import Path

import typer

from investigator.cli_format import format_result
from investigator.investigator import investigate as run_investigation
from investigator.io_utils import capture_multiline
from investigator.knowledge_loader import KnowledgeEntryError

app = typer.Typer()


def _run_workflow(kb_dir: Path | None = None) -> None:
    """Capture an error, investigate it, and print the formatted result."""
    if kb_dir is not None:
        if not kb_dir.exists():
            typer.secho(
                f"\nKnowledge base error: knowledge directory does not exist: {kb_dir}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        if not kb_dir.is_dir():
            typer.secho(
                f"\nKnowledge base error: knowledge directory is not a directory: {kb_dir}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

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


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    kb_dir: Path | None = typer.Option(
        None,
        "--kb-dir",
        help="Path to a custom knowledge base directory.",
        exists=False,
    ),
) -> None:
    """Error Investigator — a CLI developer tool for investigating Python and API errors"""
    if ctx.invoked_subcommand is None:
        _run_workflow(kb_dir)


if __name__ == "__main__":
    app()