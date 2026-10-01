from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import yaml

class KnowledgeEntry(TypedDict):

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

def load_all_entries() -> list[KnowledgeEntry]:
    entries: list[KnowledgeEntry] = []

    if not _KNOWLEDGE_DIR.exists():
        return entries

    for path in sorted(_KNOWLEDGE_DIR.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise KnowledgeEntryError(f"{path.name}: invalid YAML — {exc}") from exc

        if not isinstance(raw, dict):
            raise KnowledgeEntryError(
                f"{path.name}: top-level content must be a mapping, "
                f"got {type(raw).__name__}"
            )

        entries.append(_validate_entry(path, raw))

    return entries