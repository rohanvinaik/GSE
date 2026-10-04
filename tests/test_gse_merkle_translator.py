"""Manual contract tests for gse.merkle.translator."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.merkle.nodes import LexemeNode
from gse.merkle.translator import SQLiteMerkleTranslator
from gse.merkle.tree import MerkleLexiconTree


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


def make_lexeme(lemma="happy", pos="adj", sense_id="01", decomposition=None, source="manual", confidence=0.9):
    return LexemeNode(
        node_id=f"{lemma}_{pos}_{sense_id}",
        lemma=lemma,
        pos=pos,
        sense_id=sense_id,
        gloss=f"definition of {lemma}",
        decomposition=decomposition if decomposition is not None else [("GOOD", "evaluation", 1)],
        vector_positive=np.array([1, 2, 3], dtype=np.uint16),
        vector_negative=np.array([10, 20], dtype=np.uint16),
        source=source,
        confidence=confidence,
        frequency=1.5,
    )


class TestTranslatorInit:
    def test_creates_schema(self, temp_db):
        SQLiteMerkleTranslator(temp_db)
        # Schema should be created
        import sqlite3

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor}
        assert "lexemes" in tables
        assert "decompositions" in tables
        assert "vectors" in tables
        assert "metadata" in tables

    def test_db_path_stored(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        assert str(translator.db_path) == temp_db


class TestImportExport:
    def test_export_then_import_roundtrip(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        tree = MerkleLexiconTree()
        lex = make_lexeme(lemma="happy")
        lex.compute_content_hash()
        tree.add_lexeme(lex)

        # Export
        translator.export_from_tree(tree)

        # Import
        new_tree = translator.import_to_tree()
        assert len(new_tree.lexemes) == 1
        key = "happy_adj_01"
        assert key in new_tree.lexemes
        imported = new_tree.lexemes[key]
        assert imported.lemma == "happy"
        assert imported.pos == "adj"
        assert imported.source == "manual"
        assert imported.decomposition == [("GOOD", "evaluation", 1)]

    def test_export_preserves_vectors(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        tree = MerkleLexiconTree()
        lex = make_lexeme()
        lex.compute_content_hash()
        tree.add_lexeme(lex)

        translator.export_from_tree(tree)
        new_tree = translator.import_to_tree()
        imported = new_tree.lexemes["happy_adj_01"]
        np.testing.assert_array_equal(imported.vector_positive, lex.vector_positive)
        np.testing.assert_array_equal(imported.vector_negative, lex.vector_negative)

    def test_export_writes_metadata(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        tree = MerkleLexiconTree()
        lex = make_lexeme()
        lex.compute_content_hash()
        tree.add_lexeme(lex)
        translator.export_from_tree(tree)

        metadata = translator.get_metadata()
        assert "root_hash" in metadata
        assert "total_lexemes" in metadata
        assert metadata["total_lexemes"] == "1"

    def test_export_replace_updates_existing(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        tree = MerkleLexiconTree()
        lex1 = make_lexeme(lemma="happy", confidence=0.5)
        lex1.compute_content_hash()
        tree.add_lexeme(lex1)
        translator.export_from_tree(tree)

        # Update lexeme
        lex2 = make_lexeme(lemma="happy", confidence=0.9)
        lex2.compute_content_hash()
        tree2 = MerkleLexiconTree()
        tree2.add_lexeme(lex2)
        translator.export_from_tree(tree2, replace=True)

        imported = translator.import_to_tree()
        assert imported.lexemes["happy_adj_01"].confidence == 0.9


class TestImportEmpty:
    def test_empty_db_imports_empty_tree(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        tree = translator.import_to_tree()
        assert len(tree.lexemes) == 0

    def test_import_into_existing_tree(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        existing = MerkleLexiconTree()
        result = translator.import_to_tree(tree=existing)
        assert result is existing


class TestImportIncremental:
    def test_added_lexemes_counted(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        # Export a lexeme
        tree = MerkleLexiconTree()
        lex = make_lexeme()
        lex.compute_content_hash()
        tree.add_lexeme(lex)
        translator.export_from_tree(tree)

        # Incrementally import into empty tree
        empty_tree = MerkleLexiconTree()
        added, modified, removed = translator.import_incremental(empty_tree)
        assert added == 1
        assert modified == 0
        assert removed == 0

    def test_no_changes(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        tree = MerkleLexiconTree()
        lex = make_lexeme()
        lex.compute_content_hash()
        tree.add_lexeme(lex)
        translator.export_from_tree(tree)

        # Import then re-import incrementally
        loaded = translator.import_to_tree()
        added, modified, removed = translator.import_incremental(loaded)
        assert added == 0
        assert modified == 0
        assert removed == 0

    def test_removed_lexemes_counted(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        # Tree with extra lexeme not in db
        tree = MerkleLexiconTree()
        lex = make_lexeme(lemma="extra")
        lex.compute_content_hash()
        tree.add_lexeme(lex)

        added, modified, removed = translator.import_incremental(tree)
        # Lexeme not in (empty) DB → removed
        assert removed >= 1


class TestStatistics:
    def test_empty_db_stats(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        stats = translator.get_statistics()
        assert stats["total_lexemes"] == 0
        assert stats["unique_primitives"] == 0

    def test_populated_db_stats(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        tree = MerkleLexiconTree()
        lex = make_lexeme(decomposition=[("GOOD", "eval", 1), ("FEEL", "state", 1)])
        lex.compute_content_hash()
        tree.add_lexeme(lex)
        translator.export_from_tree(tree)

        stats = translator.get_statistics()
        assert stats["total_lexemes"] == 1
        assert stats["unique_primitives"] == 2
        assert "by_pos" in stats
        assert stats["by_pos"].get("adj") == 1


class TestIterLexemes:
    def test_empty_iterates_zero(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        result = list(translator.iter_lexemes())
        assert result == []

    def test_iterates_all_lexemes(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        tree = MerkleLexiconTree()
        for i in range(5):
            lex = make_lexeme(lemma=f"word{i}")
            lex.compute_content_hash()
            tree.add_lexeme(lex)
        translator.export_from_tree(tree)

        all_lex = list(translator.iter_lexemes())
        assert len(all_lex) == 5

    def test_batch_size_doesnt_drop_items(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        tree = MerkleLexiconTree()
        for i in range(10):
            lex = make_lexeme(lemma=f"w{i}")
            lex.compute_content_hash()
            tree.add_lexeme(lex)
        translator.export_from_tree(tree)

        all_lex = list(translator.iter_lexemes(batch_size=3))
        assert len(all_lex) == 10


class TestDeleteLexeme:
    def test_delete_removes_lexeme(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        tree = MerkleLexiconTree()
        for lemma in ["a", "b", "c"]:
            lex = make_lexeme(lemma=lemma)
            lex.compute_content_hash()
            tree.add_lexeme(lex)
        translator.export_from_tree(tree)

        # Delete via export_incremental
        empty_tree = MerkleLexiconTree()
        translator.export_incremental(empty_tree, changes=["a_adj_01"])

        # 'a' should be gone, 'b' and 'c' remain
        loaded = translator.import_to_tree()
        assert "a_adj_01" not in loaded.lexemes
        assert "b_adj_01" in loaded.lexemes
        assert "c_adj_01" in loaded.lexemes


class TestLoadLexemeByKey:
    def test_known_key_loads(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        tree = MerkleLexiconTree()
        lex = make_lexeme()
        lex.compute_content_hash()
        tree.add_lexeme(lex)
        translator.export_from_tree(tree)

        with translator._get_connection() as conn:
            loaded = translator._load_lexeme_by_key(conn, "happy_adj_01")
        assert loaded is not None
        assert loaded.lemma == "happy"

    def test_unknown_key_returns_none(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        with translator._get_connection() as conn:
            assert translator._load_lexeme_by_key(conn, "xyzzy_n_01") is None

    def test_malformed_key_returns_none(self, temp_db):
        translator = SQLiteMerkleTranslator(temp_db)
        with translator._get_connection() as conn:
            assert translator._load_lexeme_by_key(conn, "malformed") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
