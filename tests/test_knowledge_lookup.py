import pytest

import investigator.knowledge_lookup as lookup_mod
from investigator.knowledge_lookup import lookup
from investigator.error_parser import ParsedError

@pytest.fixture(autouse=True)
def _fresh_cache():
    """Rebuild the index for each test so tests are isolated."""
    lookup_mod.reset_cache()
    yield
    lookup_mod.reset_cache()


def _parsed(error_type: str | None) -> ParsedError:
    """Minimal ParsedError-shaped dict for lookup tests."""
    return {
        "error_type": error_type,
        "message": None,
        "file": None,
        "line": None,
        "function": None,
        "stack_trace": "",
    }


# ---------------------------------------------------------------- exact match

def test_exact_match_returns_entry():
    entry = lookup(_parsed("sqlalchemy.exc.IntegrityError"))
    assert entry is not None
    assert entry["error_type"] == "sqlalchemy.exc.IntegrityError"


def test_exact_match_other_entry():
    entry = lookup(_parsed("ValueError"))
    assert entry is not None
    assert entry["category"] == "python"


# ------------------------------------------------------------------- aliases

def test_alias_match_returns_entry():
    entry = lookup(_parsed("IntegrityError"))
    assert entry is not None
    assert entry["error_type"] == "sqlalchemy.exc.IntegrityError"


def test_alias_match_is_case_sensitive():
    """'integrityerror' is not the same as 'IntegrityError'."""
    assert lookup(_parsed("integrityerror")) is None


# --------------------------------------------------------------------- case

def test_error_type_is_case_sensitive():
    assert lookup(_parsed("valueerror")) is None
    assert lookup(_parsed("VALUEERROR")) is None
    assert lookup(_parsed("ValueError")) is not None


# ------------------------------------------------------------------ unknown

def test_unknown_error_returns_none():
    assert lookup(_parsed("SomeErrorThatDoesNotExist")) is None


def test_partial_match_is_not_a_match():
    """Prefix matching is not part of the contract."""
    assert lookup(_parsed("sqlalchemy.exc")) is None


# ------------------------------------------------------------------ invalid

def test_none_error_type_returns_none():
    assert lookup(_parsed(None)) is None


def test_empty_string_returns_none():
    assert lookup(_parsed("")) is None


def test_none_parsed_error_returns_none():
    assert lookup(None) is None  # type: ignore[arg-type]


def test_non_dict_input_returns_none():
    assert lookup("ValueError") is None  # type: ignore[arg-type]


# ------------------------------------------------------------ not-modifying

def test_lookup_does_not_mutate_input():
    parsed = _parsed("ValueError")
    snapshot = dict(parsed)
    lookup(parsed)
    assert parsed == snapshot


# ------------------------------------------------------- contract boundary

def test_unknown_does_not_invent_diagnosis():
    """A-013 must not fabricate. Unknown is None, nothing more."""
    result = lookup(_parsed("TotallyMadeUpError"))
    assert result is None


# ----------------------------------------------------------- custom kb_dir

def test_lookup_custom_kb_dir(tmp_path):
    entry_yaml = tmp_path / "custom.yaml"
    entry_yaml.write_text(
        "error_type: test.CustomError\n"
        "aliases: [CustomAlias]\n"
        "category: custom\n"
        "summary: custom summary\n"
        "explanation: custom explanation\n"
        "common_causes: [c1]\n"
        "fixes: [f1]\n"
        "related_errors: []\n",
        encoding="utf-8",
    )
    # Lookup using custom kb_dir as Path
    entry = lookup(_parsed("test.CustomError"), kb_dir=tmp_path)
    assert entry is not None
    assert entry["error_type"] == "test.CustomError"

    # Alias lookup using custom kb_dir as string
    entry_alias = lookup(_parsed("CustomAlias"), kb_dir=str(tmp_path))
    assert entry_alias is not None
    assert entry_alias["error_type"] == "test.CustomError"

    # Built-in errors are not in custom kb_dir
    assert lookup(_parsed("ValueError"), kb_dir=tmp_path) is None

    # Switching back to default kb_dir restores default knowledge
    entry_default = lookup(_parsed("ValueError"))
    assert entry_default is not None
    assert entry_default["error_type"] == "ValueError"


def test_lookup_custom_kb_dir_nonexistent_raises(tmp_path):
    missing_dir = tmp_path / "nonexistent"
    with pytest.raises(lookup_mod.KnowledgeEntryError, match="knowledge directory does not exist"):
        lookup(_parsed("ValueError"), kb_dir=missing_dir)


def test_lookup_custom_kb_dir_file_path_raises(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("not a dir", encoding="utf-8")
    with pytest.raises(lookup_mod.KnowledgeEntryError, match="knowledge directory is not a directory"):
        lookup(_parsed("ValueError"), kb_dir=file_path)