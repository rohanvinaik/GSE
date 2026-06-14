"""Manual contract tests for gse.api.decoder."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.api.decoder import GSEDecoder
from gse.api.trace import (
    DecodedSemantics,
    SimilarityResult,
)
from gse.vectors_v2 import SparseVector


@pytest.fixture
def empty_db():
    """Create an empty lexicon DB with valid schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name

    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE lexemes (
            id INTEGER PRIMARY KEY,
            lemma TEXT,
            pos TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE primitive_values (
            lexeme_id INTEGER,
            primitive TEXT,
            value INTEGER
        )
    """)
    conn.commit()
    conn.close()
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def populated_db():
    """Create a lexicon DB with sample lexemes."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name

    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE lexemes (
            id INTEGER PRIMARY KEY,
            lemma TEXT,
            pos TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE primitive_values (
            lexeme_id INTEGER,
            primitive TEXT,
            value INTEGER
        )
    """)

    # Insert sample lexemes
    conn.execute("INSERT INTO lexemes VALUES (1, 'person', 'n')")
    conn.execute("INSERT INTO primitive_values VALUES (1, 'SOMEONE', 1)")
    conn.execute("INSERT INTO primitive_values VALUES (1, 'ALIVE', 1)")

    conn.execute("INSERT INTO lexemes VALUES (2, 'good', 'adj')")
    conn.execute("INSERT INTO primitive_values VALUES (2, 'GOOD', 1)")

    conn.commit()
    conn.close()
    yield path
    Path(path).unlink(missing_ok=True)


class TestInit:
    def test_creates_decoder(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        assert decoder.db_path == Path(empty_db)
        assert decoder.word_basis is not None
        assert decoder.sent_basis is not None
        decoder.close()

    def test_builds_lexeme_index(self, populated_db):
        decoder = GSEDecoder(db_path=populated_db)
        # Both lexemes have primitives, so both should be indexed
        assert "person" in decoder.lexeme_vectors
        assert "good" in decoder.lexeme_vectors
        decoder.close()


class TestEncodePrimitives:
    def test_empty_returns_zero_vector(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        vec = decoder._encode_primitives({})
        assert vec.nnz == 0
        decoder.close()

    def test_with_known_primitive(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        vec = decoder._encode_primitives({"GOOD": 1})
        # GOOD is a known primitive — vector should be non-empty
        assert vec.nnz > 0
        decoder.close()

    def test_unknown_primitive_skipped(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        vec = decoder._encode_primitives({"XYZZY_UNKNOWN": 1})
        # Unknown primitives are skipped — result is zero
        assert vec.nnz == 0
        decoder.close()

    def test_negative_value_negates(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        pos_vec = decoder._encode_primitives({"GOOD": 1})
        neg_vec = decoder._encode_primitives({"GOOD": -1})
        # Negated value should produce different vector
        assert pos_vec.cosine(neg_vec) < 0.5
        decoder.close()


class TestProbePrimitives:
    def test_zero_vector_no_activations(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        zero = SparseVector.zeros(decoder.word_basis.dimension)
        activations = decoder._probe_primitives(zero, decoder.word_basis)
        # Zero vector has no activations above threshold
        assert activations == {}
        decoder.close()

    def test_known_primitive_high_activation(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        good_vec = decoder.word_basis.get_primitive("GOOD")
        activations = decoder._probe_primitives(good_vec, decoder.word_basis)
        # GOOD should activate strongly on itself
        assert "GOOD" in activations
        assert activations["GOOD"] > 0.9

        decoder.close()


class TestExtractEntities:
    def test_no_entity_signal_returns_empty(self, populated_db):
        decoder = GSEDecoder(db_path=populated_db)
        # No entity primitive activations
        result = decoder._extract_entities(
            SparseVector.zeros(decoder.word_basis.dimension),
            {"GOOD": 0.5},
        )
        assert result == []
        decoder.close()

    def test_with_entity_signal_returns_candidates(self, populated_db):
        decoder = GSEDecoder(db_path=populated_db)
        # Build vector that includes SOMEONE primitive
        person_vec = decoder._encode_primitives({"SOMEONE": 1, "ALIVE": 1})
        result = decoder._extract_entities(
            person_vec,
            {"SOMEONE": 0.3, "ALIVE": 0.2},
        )
        # Should find 'person' as a candidate
        lemmas = [e.lemma for e in result]
        assert "person" in lemmas
        decoder.close()


class TestExtractAttributes:
    def test_no_evaluator_activation_returns_empty(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        result = decoder._extract_attributes({})
        assert result == []
        decoder.close()

    def test_good_activation_extracted_as_positive(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        result = decoder._extract_attributes({"GOOD": 0.5})
        assert len(result) == 1
        assert result[0].source_primitive == "GOOD"
        assert result[0].polarity == 1
        decoder.close()

    def test_negative_activation_flips_polarity(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        # Negative activation flips polarity
        result = decoder._extract_attributes({"GOOD": -0.5})
        assert result[0].polarity == -1
        decoder.close()

    def test_sorted_by_intensity(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        result = decoder._extract_attributes({"GOOD": 0.3, "BIG": 0.7})
        assert result[0].intensity > result[1].intensity
        decoder.close()


class TestExtractRelations:
    def test_no_relation_activation_returns_empty(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        result = decoder._extract_relations({})
        assert result == []
        decoder.close()

    def test_comp_than_extracted_as_set_diff(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        result = decoder._extract_relations({"COMP_THAN": 0.5})
        assert len(result) == 1
        assert result[0].relation == "COMP_THAN"
        assert result[0].operation == "SET_DIFF"
        decoder.close()

    def test_threshold_filters_low_activation(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        # Activation below 0.02 threshold
        result = decoder._extract_relations({"COMP_THAN": 0.01})
        assert result == []
        decoder.close()


class TestFindNearestLexemes:
    def test_empty_index_returns_empty(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        vec = decoder._encode_primitives({"GOOD": 1})
        result = decoder._find_nearest_lexemes(vec, top_k=5)
        # No lexemes indexed
        assert result == []
        decoder.close()

    def test_returns_matching_lexeme(self, populated_db):
        decoder = GSEDecoder(db_path=populated_db)
        good_vec = decoder._encode_primitives({"GOOD": 1})
        result = decoder._find_nearest_lexemes(good_vec, top_k=5)
        # 'good' lexeme should match
        lemmas = [r[0] for r in result]
        assert "good" in lemmas
        decoder.close()

    def test_top_k_limits(self, populated_db):
        decoder = GSEDecoder(db_path=populated_db)
        good_vec = decoder._encode_primitives({"GOOD": 1})
        result = decoder._find_nearest_lexemes(good_vec, top_k=1)
        assert len(result) <= 1
        decoder.close()


class TestComputeBankActivity:
    def test_zero_vector_empty(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        result = decoder._compute_bank_activity(
            SparseVector.zeros(decoder.word_basis.dimension)
        )
        assert result == {}
        decoder.close()

    def test_good_activates_evaluators(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        good_vec = decoder.word_basis.get_primitive("GOOD")
        result = decoder._compute_bank_activity(good_vec)
        # GOOD primitive represents Evaluators bank
        assert "Evaluators" in result
        decoder.close()


class TestDecode:
    def test_returns_decoded_semantics(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        vec = decoder._encode_primitives({"GOOD": 1})
        result = decoder.decode(vec)
        assert isinstance(result, DecodedSemantics)
        decoder.close()

    def test_zero_vector_returns_empty_extractions(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        zero = SparseVector.zeros(decoder.word_basis.dimension)
        result = decoder.decode(zero)
        assert result.entities == []
        assert result.attributes == []
        assert result.relations == []
        decoder.close()


class TestSimilarity:
    def test_identical_vectors_align(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        good = decoder.word_basis.get_primitive("GOOD")
        result = decoder.similarity(good, good)
        assert isinstance(result, SimilarityResult)
        assert result.cosine == pytest.approx(1.0)
        assert result.alignment == pytest.approx(1.0)
        assert result.opposition == 0.0
        decoder.close()

    def test_zero_vectors_orthogonal(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        zero1 = SparseVector.zeros(decoder.word_basis.dimension)
        zero2 = SparseVector.zeros(decoder.word_basis.dimension)
        result = decoder.similarity(zero1, zero2)
        assert result.orthogonality == 1.0
        decoder.close()

    def test_negated_vector_opposition(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        good = decoder.word_basis.get_primitive("GOOD")
        neg_good = good.negate()
        result = decoder.similarity(good, neg_good)
        # Opposite vectors → high opposition
        assert result.opposition > 0.9
        decoder.close()

    def test_sentence_strings_stored(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        good = decoder.word_basis.get_primitive("GOOD")
        result = decoder.similarity(good, good, sentence1="A", sentence2="B")
        assert result.sentence1 == "A"
        assert result.sentence2 == "B"
        decoder.close()


class TestContextManager:
    def test_enter_returns_self(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        assert decoder.__enter__() is decoder
        decoder.close()

    def test_exit_closes_connection(self, empty_db):
        decoder = GSEDecoder(db_path=empty_db)
        decoder.__exit__(None, None, None)
        # Connection should be closed; operating on it raises
        with pytest.raises(sqlite3.ProgrammingError):
            decoder.cursor.execute("SELECT 1")

    def test_context_manager_protocol(self, empty_db):
        with GSEDecoder(db_path=empty_db) as decoder:
            assert decoder is not None
        # After exit, connection is closed
        with pytest.raises(sqlite3.ProgrammingError):
            decoder.cursor.execute("SELECT 1")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
