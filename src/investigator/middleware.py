"""FastAPI / Starlette middleware alias for Error Investigator."""

from __future__ import annotations

from investigator.fastapi import (
    InvestigatorMiddleware,
    sanitize_context,
    sanitize_result,
    sanitize_text,
    sanitize_url,
)

__all__ = [
    "InvestigatorMiddleware",
    "sanitize_context",
    "sanitize_result",
    "sanitize_text",
    "sanitize_url",
]
