"""Input capture utilities for interactive and piped terminal input."""

import sys

import typer


def capture_multiline(prompt: str) -> str:
    """Capture multiline input from stdin (supports both interactive TTY and pipes)."""

    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

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
