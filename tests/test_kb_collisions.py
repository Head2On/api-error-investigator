import pytest

import investigator.knowledge_loader as loader
import investigator.knowledge_lookup as lookup_mod
from investigator.knowledge_loader import KnowledgeEntryError


def _entry(
    error_type: str,
    aliases: list[str] | None = None,
    summary: str = "s",
) -> str:
    """Render a KB entry as YAML text for a test fixture."""
    alias_block = ""
    if aliases:
        alias_block = "aliases:\n" + "".join(f"  - {a}\n" for a in aliases)
    else:
        alias_block = "aliases: []\n"

    return (
        f"error_type: {error_type}\n"
        f"{alias_block}"
        "category: test\n"
        "subcategory: null\n"
        f"summary: {summary}\n"
        "explanation: e\n"
        "common_causes: []\n"
        "fixes: []\n"
        "docs_url: null\n"
        "related_errors: []\n"
    )


@pytest.fixture
def kb(tmp_path, monkeypatch):
    """Install a temporary KB directory and reset the lookup cache."""
    monkeypatch.setattr(loader, "_KNOWLEDGE_DIR", tmp_path)
    lookup_mod.reset_cache()
    yield tmp_path
    lookup_mod.reset_cache()


def _write(kb, filename: str, content: str) -> None:
    (kb / filename).write_text(content, encoding="utf-8")


# ============================================================ collision classes

def test_duplicate_error_type_fails(kb):
    """error_type ↔ error_type"""
    _write(kb, "a.yaml", _entry("test.DupError"))
    _write(kb, "b.yaml", _entry("test.DupError", summary="other"))

    with pytest.raises(KnowledgeEntryError, match="collision"):
        lookup_mod.reset_cache()
        lookup_mod.lookup({"error_type": "x", "message": None, "file": None,
                           "line": None, "function": None, "stack_trace": ""})


def test_duplicate_alias_fails(kb):
    """alias ↔ alias (across different entries)"""
    _write(kb, "a.yaml", _entry("test.AlphaError", aliases=["CommonAlias"]))
    _write(kb, "b.yaml", _entry("test.BetaError", aliases=["CommonAlias"]))

    with pytest.raises(KnowledgeEntryError, match="collision"):
        lookup_mod.lookup({"error_type": "x", "message": None, "file": None,
                           "line": None, "function": None, "stack_trace": ""})


def test_error_type_collides_with_alias(kb):
    """error_type ↔ alias (entry B's error_type equals entry A's alias)"""
    _write(kb, "a.yaml", _entry("test.AlphaError", aliases=["Shared"]))
    _write(kb, "b.yaml", _entry("Shared"))

    with pytest.raises(KnowledgeEntryError, match="collision"):
        lookup_mod.lookup({"error_type": "x", "message": None, "file": None,
                           "line": None, "function": None, "stack_trace": ""})


def test_alias_collides_with_error_type(kb):
    """alias ↔ error_type (entry A's alias equals entry B's error_type)"""
    _write(kb, "a.yaml", _entry("Shared"))
    _write(kb, "b.yaml", _entry("test.BetaError", aliases=["Shared"]))

    with pytest.raises(KnowledgeEntryError, match="collision"):
        lookup_mod.lookup({"error_type": "x", "message": None, "file": None,
                           "line": None, "function": None, "stack_trace": ""})


def test_duplicate_alias_within_same_entry_fails(kb):
    """A single entry listing the same alias twice is also invalid."""
    _write(kb, "a.yaml", _entry("test.AlphaError", aliases=["Same", "Same"]))

    with pytest.raises(KnowledgeEntryError, match="collision"):
        lookup_mod.lookup({"error_type": "x", "message": None, "file": None,
                           "line": None, "function": None, "stack_trace": ""})


def test_alias_equal_to_own_error_type_fails(kb):
    """An entry whose alias equals its own error_type is invalid."""
    _write(kb, "a.yaml", _entry("test.AlphaError", aliases=["test.AlphaError"]))

    with pytest.raises(KnowledgeEntryError, match="collision"):
        lookup_mod.lookup({"error_type": "x", "message": None, "file": None,
                           "line": None, "function": None, "stack_trace": ""})


# ============================================================ non-collisions

def test_distinct_entries_load_cleanly(kb):
    """Two entries with no overlapping identifiers load without error."""
    _write(kb, "a.yaml", _entry("test.AlphaError", aliases=["Alpha"]))
    _write(kb, "b.yaml", _entry("test.BetaError", aliases=["Beta"]))

    entry = lookup_mod.lookup({"error_type": "test.AlphaError", "message": None,
                               "file": None, "line": None, "function": None,
                               "stack_trace": ""})
    assert entry is not None
    assert entry["error_type"] == "test.AlphaError"


def test_empty_kb_loads_cleanly(kb):
    """No files → no collisions → lookup returns None."""
    entry = lookup_mod.lookup({"error_type": "anything", "message": None,
                               "file": None, "line": None, "function": None,
                               "stack_trace": ""})
    assert entry is None


# ============================================================ atomicity

def test_failed_build_does_not_populate_cache(kb):
    """If collision is detected, the module-level cache must stay empty.
    A subsequent successful fix must be able to rebuild cleanly."""
    _write(kb, "a.yaml", _entry("test.DupError"))
    _write(kb, "b.yaml", _entry("test.DupError"))

    with pytest.raises(KnowledgeEntryError):
        lookup_mod.lookup({"error_type": "x", "message": None, "file": None,
                           "line": None, "function": None, "stack_trace": ""})

    # Cache must NOT have been populated by the failed attempt.
    assert lookup_mod._BY_TYPE is None
    assert lookup_mod._BY_ALIAS is None

    # Now fix the KB and retry.
    (kb / "b.yaml").unlink()
    entry = lookup_mod.lookup({"error_type": "test.DupError", "message": None,
                               "file": None, "line": None, "function": None,
                               "stack_trace": ""})
    assert entry is not None