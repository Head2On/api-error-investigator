import typer

def capture_multiline(prompt: str) -> str:
    
    typer.secho(prompt, fg=typer.colors.CYAN)
    typer.secho("(Type 'DONE' on a new blank line and press Enter to submit):\n", fg=typer.colors.YELLOW)
    
    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == "DONE":
                break
            lines.append(line)
        except EOFError:
            break
            
    return "\n".join(lines).strip()

def display_snippet(text: str, max_lines: int = 3) -> None:
    """Print the first N lines of text, with a truncation marker if longer."""
    lines = text.splitlines()
    
    typer.echo("----------------------------------------")
    snippet = "\n".join(lines[:max_lines])
    typer.echo(snippet)
    
    if len(lines) > max_lines:
        typer.echo("... [truncated]")
        
    typer.echo("----------------------------------------")