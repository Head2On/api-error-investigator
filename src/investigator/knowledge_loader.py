"""Knowledge base YAML file loader and schema validator."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import yaml


class KnowledgeEntry(TypedDict):
    """Schema for a curated knowledge base entry."""

    error_type: str
    aliases: list[str]
    category: str
    subcategory: str | None
    summary: str
    explanation: str
    common_causes: list[str]
    fixes: list[str]
    docs_url: str | None
    related_errors: list[str]

# Required keys and their types 
_REQUIRED: dict[str, type] = {
    "error_type": str,
    "aliases": list,
    "category": str,
    "summary": str,
    "explanation": str,
    "common_causes": list,
    "fixes": list,
    "related_errors": list,
}

# Optional keys and their types
_OPTIONAL: dict[str, type] = {
    "subcategory": str,
    "docs_url": str,
}

_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

class KnowledgeEntryError(Exception):
    """Raised when a knowledge entry file is malformed."""


def _validate_entry(path: Path, raw: dict) -> KnowledgeEntry:
    """Validate a parsed YAML dict against KnowledgeEntry schema constraints."""
    for key, expected_type in _REQUIRED.items():
        if key not in raw:
            raise KnowledgeEntryError(
                f"{path.name}: missing required field '{key}'"
            )
        if not isinstance(raw[key], expected_type):
            raise KnowledgeEntryError(
                f"{path.name}: field '{key}' must be {expected_type.__name__}, "
                f"got {type(raw[key]).__name__}"
            )

    for key, expected_type in _OPTIONAL.items():
        if key in raw and raw[key] is not None and not isinstance(raw[key], expected_type):
            raise KnowledgeEntryError(
                f"{path.name}: field '{key}' must be {expected_type.__name__} or null, "
                f"got {type(raw[key]).__name__}"
            )

    for key in _OPTIONAL:
        raw.setdefault(key, None)

    return raw  # type: ignore


def _check_collisions(entries: list[KnowledgeEntry]) -> None:
    """Raise if any identifier appears as error_type or alias of more than one entry."""
    seen: dict[str, tuple[str, str]] = {}
    for entry in entries:
        primary = entry["error_type"]
        if primary in seen:
            other_type, other_kind = seen[primary]
            raise KnowledgeEntryError(
                f"collision on identifier {primary!r}: "
                f"appears as {other_kind} of {other_type!r} "
                f"and as error_type of {primary!r}"
            )
        seen[primary] = (primary, "error_type")
        for alias in entry["aliases"]:
            if alias in seen:
                other_type, other_kind = seen[alias]
                raise KnowledgeEntryError(
                    f"collision on identifier {alias!r}: "
                    f"appears as {other_kind} of {other_type!r} "
                    f"and as alias of {primary!r}"
                )
            seen[alias] = (primary, "alias")


def load_all_entries(path: Path | str | None = None) -> list[KnowledgeEntry]:
    """Load and validate all knowledge base YAML entries.

    If ``path`` is provided, entries are loaded from that directory and validated.
    Raises ``KnowledgeEntryError`` if the custom directory does not exist, is not
    a directory, contains no YAML entries, or contains malformed entries.
    If ``path`` is None, entries are loaded from the default knowledge directory.
    """
    explicit = path is not None
    if isinstance(path, str):
        path = Path(path)
    directory = path if explicit and path is not None else _KNOWLEDGE_DIR

    if explicit:
        if not directory.exists():
            raise KnowledgeEntryError(
                f"knowledge directory does not exist: {directory}"
            )
        if not directory.is_dir():
            raise KnowledgeEntryError(
                f"knowledge directory is not a directory: {directory}"
            )
    else:
        if not directory.exists() or not directory.is_dir():
            return []

    entries: list[KnowledgeEntry] = []

    for file_path in sorted(directory.glob("*.yaml")):
        try:
            raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise KnowledgeEntryError(f"{file_path.name}: invalid YAML — {exc}") from exc

        if not isinstance(raw, dict):
            raise KnowledgeEntryError(
                f"{file_path.name}: top-level content must be a mapping, "
                f"got {type(raw).__name__}"
            )

        entries.append(_validate_entry(file_path, raw))

    if explicit and not entries:
        raise KnowledgeEntryError(
            f"knowledge directory contains no entries: {directory}"
        )

    _check_collisions(entries)
    return entries