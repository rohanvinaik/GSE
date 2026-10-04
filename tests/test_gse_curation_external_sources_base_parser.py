"""Manual contract tests for gse.curation.external_sources.base_parser."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.base_parser import (
    BaseExternalParser,
    ParserConfig,
)


class FakeParser(BaseExternalParser):
    """Concrete subclass for testing the abstract interface."""

    def __init__(self, config=None, vocab=None):
        super().__init__(config)
        self._vocab = vocab or ["dog", "cat", "Run"]

    def load(self) -> bool:
        for w in self._vocab:
            self.entries[w.lower()] = {"GOOD": 1}
        self._loaded = True
        return True

    def to_primitives(self, word):
        return self.entries.get(word.lower(), {})

    def get_all_words(self):
        return list(self.entries.keys())


# ---------- ParserConfig ----------


class TestParserConfig:
    def test_defaults(self):
        c = ParserConfig(name="x")
        assert c.name == "x"
        assert c.data_path is None
        assert c.lazy_load is True
        assert c.cache_size == 10000
        assert c.memory_limit_mb == 500

    def test_custom_values(self):
        c = ParserConfig(
            name="y",
            data_path=Path("/tmp"),
            lazy_load=False,
            cache_size=42,
            memory_limit_mb=10,
        )
        assert c.name == "y"
        assert c.data_path == Path("/tmp")
        assert c.lazy_load is False
        assert c.cache_size == 42
        assert c.memory_limit_mb == 10


# ---------- BaseExternalParser.__init__ ----------


class TestInit:
    def test_default_config_uses_class_name(self):
        p = FakeParser()
        assert p.config.name == "FakeParser"

    def test_custom_config_kept(self):
        cfg = ParserConfig(name="custom")
        p = FakeParser(config=cfg)
        assert p.config is cfg

    def test_initial_entries_empty(self):
        assert FakeParser().entries == {}

    def test_initial_loaded_false(self):
        assert FakeParser()._loaded is False

    def test_initial_memory_zero(self):
        assert FakeParser()._memory_usage == 0


# ---------- get_metadata ----------


class TestGetMetadata:
    def test_unloaded(self):
        meta = FakeParser().get_metadata()
        assert meta["loaded"] is False
        assert meta["entry_count"] == 0
        assert meta["memory_mb"] == 0
        assert meta["name"] == "FakeParser"

    def test_loaded(self):
        p = FakeParser()
        p.load()
        meta = p.get_metadata()
        assert meta["loaded"] is True
        assert meta["entry_count"] == 3
        assert meta["name"] == "FakeParser"

    def test_memory_mb_computation(self):
        p = FakeParser()
        p._memory_usage = 1024 * 1024 * 5  # 5 MB
        assert p.get_metadata()["memory_mb"] == 5.0

    def test_memory_mb_zero_when_no_usage(self):
        # When _memory_usage is 0, returns 0 (short-circuit branch)
        p = FakeParser()
        p._memory_usage = 0
        assert p.get_metadata()["memory_mb"] == 0


# ---------- get_new_words ----------


class TestGetNewWords:
    def test_returns_only_new(self):
        p = FakeParser()
        p.load()
        existing = {"dog"}
        new = p.get_new_words(existing)
        assert "dog" not in new
        assert "cat" in new

    def test_auto_loads(self):
        p = FakeParser()
        assert p._loaded is False
        p.get_new_words(set())
        assert p._loaded is True

    def test_empty_when_all_exist(self):
        p = FakeParser()
        p.load()
        assert p.get_new_words({"dog", "cat", "run"}) == []

    def test_returns_list(self):
        p = FakeParser()
        assert isinstance(p.get_new_words(set()), list)


# ---------- has_word ----------


class TestHasWord:
    def test_present(self):
        p = FakeParser()
        p.load()
        assert p.has_word("dog") is True

    def test_absent(self):
        p = FakeParser()
        p.load()
        assert p.has_word("ZZZ") is False

    def test_case_insensitive(self):
        p = FakeParser()
        p.load()
        assert p.has_word("DOG") is True
        assert p.has_word("Dog") is True

    def test_auto_loads(self):
        p = FakeParser()
        assert p._loaded is False
        p.has_word("dog")
        assert p._loaded is True


# ---------- close ----------


class TestClose:
    def test_clears_entries(self):
        p = FakeParser()
        p.load()
        assert p.entries  # non-empty
        p.close()
        assert p.entries == {}

    def test_resets_loaded(self):
        p = FakeParser()
        p.load()
        p.close()
        assert p._loaded is False


# ---------- context manager ----------


class TestContextManager:
    def test_enter_loads(self):
        p = FakeParser()
        with p as ctx:
            assert ctx is p
            assert p._loaded is True

    def test_exit_closes(self):
        p = FakeParser()
        with p:
            pass
        assert p._loaded is False
        assert p.entries == {}

    def test_exit_returns_false(self):
        p = FakeParser()
        # Calling __exit__ directly to check return value
        p.load()
        result = p.__exit__(None, None, None)
        assert result is False


# ---------- ABC enforcement ----------


class TestAbstractInterface:
    def test_cannot_instantiate_base_directly(self):
        with pytest.raises(TypeError):
            BaseExternalParser()  # abstract


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
