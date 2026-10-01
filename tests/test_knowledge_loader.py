
import pytest
import investigator.knowledge_loader as loader
from investigator.knowledge_loader import (
    KnowledgeEntryError,
    load_all_entries,
)


def test_loads_the_integrity_error_entry():
    entries = load_all_entries()

    assert len(entries) >= 1

    integrity = next(
        (e for e in entries if e["error_type"] == "sqlalchemy.exc.IntegrityError"),
        None,
    )
    assert integrity is not None, "IntegrityError entry not loaded"

    # Required fields present and correct type
    assert integrity["category"] == "database"
    assert isinstance(integrity["aliases"], list)
    assert "IntegrityError" in integrity["aliases"]
    assert isinstance(integrity["fixes"], list) and len(integrity["fixes"]) > 0
    assert isinstance(integrity["common_causes"], list)

    # Optional fields filled with default (None) when present in file
    assert integrity["subcategory"] == "constraint_violation"
    assert integrity["docs_url"] is not None, "docs_url should not be None"
    assert integrity["docs_url"].startswith("https://")


def test_optional_fields_default_to_none(monkeypatch, tmp_path):
    entry_yaml = tmp_path / "dummy.yaml"
    entry_yaml.write_text(
        "error_type: test.FakeError\n"
        "aliases: []\n"
        "category: test\n"
        "summary: fake\n"
        "explanation: fake\n"
        "common_causes: []\n"
        "fixes: []\n"
        "related_errors: []\n",
        encoding="utf-8",
    )

    
    monkeypatch.setattr(loader, "_KNOWLEDGE_DIR", tmp_path)

    entries = loader.load_all_entries()
    assert len(entries) == 1
    assert entries[0]["subcategory"] is None
    assert entries[0]["docs_url"] is None


def test_missing_required_field_raises(monkeypatch, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("error_type: x\n", encoding="utf-8")  # missing everything else

    monkeypatch.setattr(loader, "_KNOWLEDGE_DIR", tmp_path)

    with pytest.raises(KnowledgeEntryError, match="missing required field"):
        loader.load_all_entries()


def test_wrong_type_raises(monkeypatch, tmp_path):
    bad = tmp_path / "bad_type.yaml"
    bad.write_text(
        "error_type: 123\n"
        "aliases: []\n"
        "category: test\n"
        "summary: s\n"
        "explanation: e\n"
        "common_causes: []\n"
        "fixes: []\n"
        "related_errors: []\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(loader, "_KNOWLEDGE_DIR", tmp_path)

    with pytest.raises(KnowledgeEntryError, match="must be str"):
        loader.load_all_entries()

def test_all_starter_entries_load_and_validate():
    entries = load_all_entries()
    by_type = {e["error_type"]: e for e in entries}

    expected_types = {
        "sqlalchemy.exc.IntegrityError",
        "sqlalchemy.exc.OperationalError",
        "sqlalchemy.exc.DataError",
        "ValueError",
        "KeyError",
    }
    assert expected_types.issubset(by_type.keys()), (
        f"missing entries: {expected_types - by_type.keys()}"
    )

    for error_type, entry in by_type.items():
        assert entry["summary"].strip(), f"{error_type}: empty summary"
        assert entry["explanation"].strip(), f"{error_type}: empty explanation"
        assert len(entry["common_causes"]) >= 1, f"{error_type}: no common_causes"
        assert len(entry["fixes"]) >= 1, f"{error_type}: no fixes"