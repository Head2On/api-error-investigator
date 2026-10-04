from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Investigation:
    """Deterministic investigation content for a known error."""

    summary: str
    explanation: str
    common_causes: list[str]
    fixes: list[str]
    docs_url: str | None
    related_errors: list[str]