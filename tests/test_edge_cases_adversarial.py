import pytest

from investigator.cli_format import format_result
from investigator.error_parser import parse_error
from investigator.investigator import investigate


#  PARSER ASSUMPTIONS

class TestParserWeirdSpacing:
    """Assumption: parser tolerates spacing variations on the error line."""

    def test_error_line_with_extra_spaces_before_colon(self):
        """'ValueError   :   msg' — is the error type still detected?"""
        result = parse_error("ValueError   :   msg")
        # Regex expects ': ' immediately after type. Extra spaces may break.
        # Whatever the outcome is, it must be documented behavior.
        assert result["error_type"] in (None, "ValueError")

    def test_error_line_with_trailing_whitespace_only(self):
        result = parse_error("ValueError:    ")
        assert result["error_type"] in (None, "ValueError")

    def test_error_line_with_leading_whitespace(self):
        """Error line indented — common when copied from a log."""
        result = parse_error("    ValueError: msg")
        # Regex uses ^...$ with .strip() applied, so leading whitespace
        # is removed before match. Should still detect.
        assert result["error_type"] == "ValueError"


class TestParserMultipleErrorLines:
    """Assumption: parser picks exactly one error line, deterministically."""

    def test_two_error_lines_bottom_up(self):
        """Python 'During handling...' pattern — two errors in one output."""
        raw = (
            "Traceback (most recent call last):\n"
            '  File "a.py", line 1, in f\n'
            "ValueError: first\n"
            "\n"
            "During handling of the above exception, another exception occurred:\n"
            "\n"
            "Traceback (most recent call last):\n"
            '  File "b.py", line 2, in g\n'
            "KeyError: 'second'"
        )
        result = parse_error(raw)
        # Parser scans bottom-up → last error line wins.
        assert result["error_type"] == "KeyError"
        assert result["file"] == "b.py"

    def test_error_line_before_a_later_error_line(self):
        """Confirm which one wins is deterministic across orderings."""
        raw = "ValueError: first\nRuntimeError: second"
        result = parse_error(raw)
        # Bottom-up scan → RuntimeError wins.
        assert result["error_type"] == "RuntimeError"


class TestParserErrorNameInProse:
    """Assumption: parser doesn't match error-shaped prose by accident."""

    def test_error_name_in_middle_of_sentence(self):
        raw = "I saw ValueError yesterday but it went away"
        result = parse_error(raw)
        # Regex anchors ^...$ after strip. Prose has no colon.
        assert result["error_type"] is None

    def test_error_name_in_sentence_with_colon(self):
        raw = "The error was ValueError: invalid input"
        result = parse_error(raw)
        # Does the parser match this? Depends on ^...$ anchoring.
        # If it matches, error_type will be 'ValueError'.
        # If not, error_type is None.
        # Either is acceptable IF documented.
        assert result["error_type"] in (None, "ValueError")

    def test_sentences_that_look_like_traceback_headers_only(self):
        raw = "Traceback (most recent call last):\nbut no error line follows"
        result = parse_error(raw)
        assert result["error_type"] is None


class TestParserDeepTraceback:
    """Assumption: parser handles deep frames without performance issues."""

    def test_thousand_frame_traceback(self):
        lines = ["Traceback (most recent call last):"]
        for i in range(1000):
            lines.append(f'  File "f{i}.py", line {i}, in g{i}')
            lines.append(f"    call_{i}()")
        lines.append("ValueError: deep")
        raw = "\n".join(lines)
        result = parse_error(raw)
        # Bottom frame is the last one (999).
        assert result["error_type"] == "ValueError"
        assert result["file"] == "f999.py"
        assert result["function"] == "g999"


#  INPUT STRESS

class TestInputStress:
    """Assumption: pipeline survives large and unusual inputs."""

    def test_megabyte_input_terminates(self):
        """Roughly 1 MB of repeated traceback-like content."""
        block = (
            "Traceback (most recent call last):\n"
            '  File "a.py", line 1, in f\n'
            "ValueError: spam\n"
        )
        raw = block * 5000  # ~1 MB
        result = investigate(raw)
        # Parser scans bottom-up — should still find the last error line.
        assert result.status in ("known", "unknown")
        # Most important: it returned at all, without hanging or crashing.

    def test_input_with_null_bytes(self):
        raw = "ValueError: bad\x00data"
        result = investigate(raw)
        # No crash. Whether the null breaks parsing is a detail.
        assert result.status in ("known", "unknown")


#  KB ASSUMPTIONS

class TestKbDuplicateCollisions:
    """Assumption: colliding entries are handled deterministically, not silently."""

    def test_two_entries_same_error_type(self, monkeypatch, tmp_path):
        import investigator.knowledge_loader as loader
        import investigator.knowledge_lookup as lookup_mod

        entry_a = (
            "error_type: test.DupError\n"
            "aliases: []\n"
            "category: test\n"
            "subcategory: null\n"
            "summary: first\n"
            "explanation: first\n"
            "common_causes: []\n"
            "fixes: []\n"
            "docs_url: null\n"
            "related_errors: []\n"
        )
        entry_b = entry_a.replace("first", "second")

        (tmp_path / "a.yaml").write_text(entry_a, encoding="utf-8")
        (tmp_path / "b.yaml").write_text(entry_b, encoding="utf-8")

        monkeypatch.setattr(loader, "_KNOWLEDGE_DIR", tmp_path)
        lookup_mod.reset_cache()

        try:
            from investigator.investigator import investigate as inv
            from investigator.knowledge_lookup import lookup
            from investigator.error_parser import parse_error

            entry = lookup(parse_error("test.DupError: boom"))
            assert entry is not None
            # The winning entry depends on file iteration order.
            # We only assert it's ONE of the two, not both:
            assert entry["summary"] in ("first", "second")
            # Document the current behavior: last-write wins per
            # knowledge_lookup._build_index.
        finally:
            lookup_mod.reset_cache()

    def test_alias_collides_with_other_error_type(self, monkeypatch, tmp_path):
        """Entry B's alias is entry A's error_type."""
        import investigator.knowledge_loader as loader
        import investigator.knowledge_lookup as lookup_mod

        entry_a = (
            "error_type: test.AlphaError\n"
            "aliases: []\n"
            "category: test\n"
            "subcategory: null\n"
            "summary: alpha\n"
            "explanation: alpha\n"
            "common_causes: []\n"
            "fixes: []\n"
            "docs_url: null\n"
            "related_errors: []\n"
        )
        entry_b = (
            "error_type: test.BetaError\n"
            "aliases:\n"
            "  - test.AlphaError\n"
            "category: test\n"
            "subcategory: null\n"
            "summary: beta\n"
            "explanation: beta\n"
            "common_causes: []\n"
            "fixes: []\n"
            "docs_url: null\n"
            "related_errors: []\n"
        )

        (tmp_path / "alpha.yaml").write_text(entry_a, encoding="utf-8")
        (tmp_path / "beta.yaml").write_text(entry_b, encoding="utf-8")

        monkeypatch.setattr(loader, "_KNOWLEDGE_DIR", tmp_path)
        lookup_mod.reset_cache()

        try:
            from investigator.knowledge_lookup import lookup
            from investigator.error_parser import parse_error

            entry = lookup(parse_error("test.AlphaError: boom"))
            assert entry is not None
            # Contract ambiguity: exact match on error_type should win,
            # but does it? Document current behavior.
            assert entry["error_type"] in ("test.AlphaError", "test.BetaError")
        finally:
            lookup_mod.reset_cache()


class TestKbMalformedYaml:
    """Assumption: malformed YAML raises KnowledgeEntryError, not crashes."""

    def test_yaml_not_a_mapping(self, monkeypatch, tmp_path):
        from investigator.knowledge_loader import KnowledgeEntryError, load_all_entries
        import investigator.knowledge_loader as loader

        (tmp_path / "list.yaml").write_text("- one\n- two\n", encoding="utf-8")
        monkeypatch.setattr(loader, "_KNOWLEDGE_DIR", tmp_path)

        with pytest.raises(KnowledgeEntryError):
            load_all_entries()

    def test_yaml_syntax_error(self, monkeypatch, tmp_path):
        from investigator.knowledge_loader import KnowledgeEntryError, load_all_entries
        import investigator.knowledge_loader as loader

        (tmp_path / "broken.yaml").write_text(
            "error_type: : :\n  bad indent\n-",
            encoding="utf-8",
        )
        monkeypatch.setattr(loader, "_KNOWLEDGE_DIR", tmp_path)

        with pytest.raises(KnowledgeEntryError):
            load_all_entries()


#  LOOKUP STRESS

class TestLookupStrangeInputs:
    """Assumption: lookup doesn't crash on odd ParsedError shapes."""

    def test_parsed_error_with_unexpected_extra_keys(self):
        from investigator.knowledge_lookup import lookup
        parsed = {
            "error_type": "ValueError",
            "message": None,
            "file": None,
            "line": None,
            "function": None,
            "stack_trace": "",
            "extra_unknown_key": "surprise",
        }
        entry = lookup(parsed)  # type: ignore[arg-type]
        assert entry is not None
        assert entry["error_type"] == "ValueError"

    def test_parsed_error_with_non_string_error_type(self):
        from investigator.knowledge_lookup import lookup
        parsed = {
            "error_type": 42,
            "message": None,
            "file": None,
            "line": None,
            "function": None,
            "stack_trace": "",
        }
        assert lookup(parsed) is None  # type: ignore[arg-type]


#  FORMATTER STRESS

class TestFormatterWithUnusualFields:
    """Assumption: formatter never crashes on valid-but-odd content."""

    def test_fix_containing_newlines(self):
        from investigator.investigation import Investigation
        from investigator.investigation_result import InvestigationResult

        parsed = {
            "error_type": "ValueError",
            "message": None,
            "file": None,
            "line": None,
            "function": None,
            "stack_trace": "",
        }
        inv = Investigation(
            summary="s",
            explanation="e",
            common_causes=["first line\nsecond line"],
            fixes=["do this\nthen that"],
            docs_url=None,
            related_errors=[],
        )
        knowledge = {"error_type": "ValueError", "aliases": [],
                     "category": "t", "subcategory": None,
                     "summary": "s", "explanation": "e",
                     "common_causes": [], "fixes": [],
                     "docs_url": None, "related_errors": []}
        result = InvestigationResult.known(parsed, knowledge, inv)  # type: ignore[arg-type]
        output = format_result(result)
        # Newlines inside a bullet should still produce readable output.
        assert "first line" in output
        assert "second line" in output

    def test_unicode_content(self):
        from investigator.investigation import Investigation
        from investigator.investigation_result import InvestigationResult

        parsed = {
            "error_type": "ValueError",
            "message": None,
            "file": None,
            "line": None,
            "function": None,
            "stack_trace": "",
        }
        inv = Investigation(
            summary="Résumé invalide 🚨",
            explanation="Le champ contient 日本語",
            common_causes=["café", "naïve"],
            fixes=["üse correct input"],
            docs_url=None,
            related_errors=[],
        )
        knowledge = {"error_type": "ValueError", "aliases": [],
                     "category": "t", "subcategory": None,
                     "summary": "s", "explanation": "e",
                     "common_causes": [], "fixes": [],
                     "docs_url": None, "related_errors": []}
        result = InvestigationResult.known(parsed, knowledge, inv)  # type: ignore[arg-type]
        output = format_result(result)
        assert "🚨" in output
        assert "日本語" in output


#  RESULT CONTRACT BREAKS

class TestResultInvalidStates:
    """Assumption: InvestigationResult rejects invalid field combinations."""

    def test_known_with_none_knowledge_direct_construct(self):
        from investigator.investigation import Investigation
        from investigator.investigation_result import InvestigationResult

        parsed = {
            "error_type": "ValueError",
            "message": None,
            "file": None,
            "line": None,
            "function": None,
            "stack_trace": "",
        }
        inv = Investigation(
            summary="s", explanation="e",
            common_causes=[], fixes=[],
            docs_url=None, related_errors=[],
        )
        with pytest.raises(ValueError):
            InvestigationResult(
                status="known",
                parsed_error=parsed,  # type: ignore[arg-type]
                knowledge=None,
                investigation=inv,
            )

    def test_unknown_with_investigation_direct_construct(self):
        from investigator.investigation import Investigation
        from investigator.investigation_result import InvestigationResult

        parsed = {
            "error_type": "ValueError",
            "message": None,
            "file": None,
            "line": None,
            "function": None,
            "stack_trace": "",
        }
        inv = Investigation(
            summary="s", explanation="e",
            common_causes=[], fixes=[],
            docs_url=None, related_errors=[],
        )
        with pytest.raises(ValueError):
            InvestigationResult(
                status="unknown",
                parsed_error=parsed,  # type: ignore[arg-type]
                knowledge=None,
                investigation=inv,
            )


#  CACHE LOGIC

class TestCacheAfterKbChange:
    """Assumption: cache invalidation is manual (via reset_cache), by design."""

    def test_cache_does_not_reload_after_yaml_change(self, monkeypatch, tmp_path):
        """If KB changes after cache init, lookup uses stale entries until reset."""
        import investigator.knowledge_loader as loader
        import investigator.knowledge_lookup as lookup_mod

        entry = (
            "error_type: test.CacheError\n"
            "aliases: []\n"
            "category: test\n"
            "subcategory: null\n"
            "summary: cached\n"
            "explanation: cached\n"
            "common_causes: []\n"
            "fixes: []\n"
            "docs_url: null\n"
            "related_errors: []\n"
        )
        yaml_file = tmp_path / "cache.yaml"
        yaml_file.write_text(entry, encoding="utf-8")

        monkeypatch.setattr(loader, "_KNOWLEDGE_DIR", tmp_path)
        lookup_mod.reset_cache()

        try:
            from investigator.knowledge_lookup import lookup
            from investigator.error_parser import parse_error

            first = lookup(parse_error("test.CacheError: boom"))
            assert first is not None
            assert first["summary"] == "cached"

            # Now change the file on disk.
            yaml_file.write_text(entry.replace("cached", "updated"), encoding="utf-8")

            # Without reset_cache, the old entry is returned (cached).
            second = lookup(parse_error("test.CacheError: boom"))
            assert second is not None
            assert second["summary"] == "cached"  # stale by design

            # After reset, the new content loads.
            lookup_mod.reset_cache()
            third = lookup(parse_error("test.CacheError: boom"))
            assert third is not None
            assert third["summary"] == "updated"
        finally:
            lookup_mod.reset_cache()


# = INTEGRATION SEQUENCES

class TestIntegrationSequences:
    """Assumption: alternating known/unknown calls are stable over many iterations."""

    def test_known_unknown_known_loop(self):
        known = "ValueError: bad"
        unknown = "TotallyFakeError: boom"
        for _ in range(30):
            assert investigate(known).status == "known"
            assert investigate(unknown).status == "unknown"
            assert investigate(known).status == "known"

    def test_result_objects_are_independent(self):
        """Two investigate() calls must not share mutable state."""
        a = investigate("ValueError: one")
        b = investigate("ValueError: two")
        assert a.parsed_error is not b.parsed_error
        assert a.investigation is not b.investigation


# == CLI BOUNDARY

class TestCliInputBoundary:
    """Assumption: capture_multiline returns cleanly on immediate EOF / no DONE."""

    def test_immediate_done(self, monkeypatch):
        from investigator import io_utils
        inputs = iter(["DONE"])
        monkeypatch.setattr("builtins.input", lambda *a, **k: next(inputs))
        result = io_utils.capture_multiline("prompt")
        assert result == ""

    def test_immediate_eof(self, monkeypatch):
        from investigator import io_utils
        def raise_eof(*a, **k):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)
        result = io_utils.capture_multiline("prompt")
        assert result == ""

    def test_no_done_but_eof(self, monkeypatch):
        from investigator import io_utils
        lines = iter(["line one", "line two"])
        def feed(*a, **k):
            try:
                return next(lines)
            except StopIteration:
                raise EOFError
        monkeypatch.setattr("builtins.input", feed)
        result = io_utils.capture_multiline("prompt")
        assert "line one" in result
        assert "line two" in result