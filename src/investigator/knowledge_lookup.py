from __future__ import annotations

from investigator.error_parser import ParsedError
from investigator.knowledge_loader import KnowledgeEntry, load_all_entries


# Module level cache
_BY_TYPE: dict[str, KnowledgeEntry] | None = None
_BY_ALIAS: dict[str, KnowledgeEntry] | None = None

def _build_index() -> None:
    global _BY_TYPE, _BY_ALIAS

    by_type: dict[str, KnowledgeEntry] = {}
    by_alias: dict[str, KnowledgeEntry] = {}

    for entry in load_all_entries():
        by_type[entry["error_type"]] = entry
        for alias in entry["aliases"]:
            by_alias[alias] = entry

    _BY_TYPE = by_type
    _BY_ALIAS = by_alias

# for tests 
def reset_cache() -> None:
    global _BY_TYPE, _BY_ALIAS
    _BY_TYPE = None
    _BY_ALIAS = None


def lookup(parsed_error: ParsedError) -> KnowledgeEntry | None:
    """Return the KB entry for this parsed error, or None if unknown."""
    if _BY_TYPE is None or _BY_ALIAS is None:
        _build_index()

    if not isinstance(parsed_error, dict):
        return None
    error_type = parsed_error.get("error_type")

    if not isinstance(error_type,str) or not error_type.strip():
        return None
    
    assert _BY_TYPE is not None and _BY_ALIAS is not None

    # 1. Exact match on error_type
    entry = _BY_TYPE.get(error_type)
    if entry is not None:
        return entry

    # 2. Exact match on alias
    entry = _BY_ALIAS.get(error_type)
    if entry is not None:
        return entry

    return None
