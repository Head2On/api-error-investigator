"""Knowledge base in-memory indexing and lookup engine."""

from __future__ import annotations

from pathlib import Path

import investigator.knowledge_loader as loader
from investigator.error_parser import ParsedError
from investigator.knowledge_loader import (
    KnowledgeEntry,
    KnowledgeEntryError,
    load_all_entries,
)

# Module level cache, keyed by the directory it was built from.
_BY_TYPE: dict[str, KnowledgeEntry] | None = None
_BY_ALIAS: dict[str, KnowledgeEntry] | None = None
_CACHED_DIR: Path | None = None


def _build_index(directory: Path | None = None) -> None:
    """Build in-memory indexes for ``directory`` (or default KB) and detect collisions."""
    global _BY_TYPE, _BY_ALIAS, _CACHED_DIR

    # Reset cache before building so any failure leaves cache clean.
    _BY_TYPE = None
    _BY_ALIAS = None
    _CACHED_DIR = None

    entries = load_all_entries(directory)

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

    by_type: dict[str, KnowledgeEntry] = {}
    by_alias: dict[str, KnowledgeEntry] = {}

    for entry in entries:
        by_type[entry["error_type"]] = entry
        for alias in entry["aliases"]:
            by_alias[alias] = entry

    _BY_TYPE = by_type
    _BY_ALIAS = by_alias
    _CACHED_DIR = (
        directory.resolve()
        if directory is not None
        else loader._KNOWLEDGE_DIR.resolve()
    )


def reset_cache() -> None:
    """Clear the in-memory lookup cache (intended for tests)."""
    global _BY_TYPE, _BY_ALIAS, _CACHED_DIR
    _BY_TYPE = None
    _BY_ALIAS = None
    _CACHED_DIR = None


def lookup(
    parsed_error: ParsedError,
    *,
    kb_dir: Path | str | None = None,
) -> KnowledgeEntry | None:
    """Return the KB entry for this parsed error, or None if unknown.

    ``kb_dir=None`` uses the built-in knowledge directory. An explicit
    directory is validated before the cache is consulted, so a cache built
    from a directory that has since disappeared cannot mask the problem.
    """
    if isinstance(kb_dir, str):
        kb_dir = Path(kb_dir)

    if kb_dir is not None:
        if not kb_dir.exists():
            raise KnowledgeEntryError(
                f"knowledge directory does not exist: {kb_dir}"
            )
        if not kb_dir.is_dir():
            raise KnowledgeEntryError(
                f"knowledge directory is not a directory: {kb_dir}"
            )

    target_dir = (
        kb_dir.resolve()
        if kb_dir is not None
        else loader._KNOWLEDGE_DIR.resolve()
    )

    if _BY_TYPE is None or _BY_ALIAS is None or _CACHED_DIR != target_dir:
        _build_index(kb_dir)

    if not isinstance(parsed_error, dict):
        return None
    error_type = parsed_error.get("error_type")

    if not isinstance(error_type, str) or not error_type.strip():
        return None

    assert _BY_TYPE is not None and _BY_ALIAS is not None

    entry = _BY_TYPE.get(error_type)
    if entry is not None:
        return entry

    entry = _BY_ALIAS.get(error_type)
    if entry is not None:
        return entry

    return None