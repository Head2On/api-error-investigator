import typer
from investigator.io_utils import capture_multiline, display_snippet

app = typer.Typer()

@app.callback()
def main() -> None:
    """AI API Error Investigator — a developer tool for investigating AI API errors."""
    

@app.command()
def investigate() -> None:
    """Investigate an error (API route or database)."""
    typer.echo("What would you like to do?")
    typer.echo("1: Investigate API Route Error")
    typer.echo("2: Investigate Database/SQLAlchemy Error")

    choice = typer.prompt("Choose an option (1 or 2)", type=int)

    if choice not in [1, 2]:
        typer.secho("Invalid choice. Please run again and select 1 or 2.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    raw_error = capture_multiline("\nPaste your multi-line error below.")

    if not raw_error:
        typer.secho("\nNo error text captured. Exiting.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho("\n✅ SUCCESS: ERROR CAPTURED SUCCESSFULLY", fg=typer.colors.GREEN, bold=True)

    typer.echo("\n--- Debug Info ---")
    typer.echo(f"Selected Mode: {choice}")
    typer.echo("Snippet of captured text:")

    display_snippet(raw_error)