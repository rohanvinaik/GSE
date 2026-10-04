"""Manual contract tests for gse.api.encoder."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.api.encoder import (
    DEP_TO_SYNTACTIC,
    MORPH_TO_TAM,
    GSEEncoder,
)
from gse.api.errors import OOVError, PrimitiveError
from gse.api.trace import OperationTrace, OperatorTrace, TokenTrace
from gse.vectors_v2 import SparseVector


@pytest.fixture(scope="module")
def lexicon_db():
    """Create lexicon DB with sample data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name

    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE lexemes (
            id INTEGER PRIMARY KEY,
            lemma TEXT,
            pos TEXT,
            comp_primitive TEXT,
            comp_arity INTEGER,
            comp_operation TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE primitive_values (
            lexeme_id INTEGER,
            primitive TEXT,
            value INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE sentence_primitive_values (
            lexeme_id INTEGER,
            primitive TEXT,
            value INTEGER
        )
    """)

    # Plain noun
    conn.execute("INSERT INTO lexemes (id, lemma, pos) VALUES (1, 'dog', 'NOUN')")
    conn.execute("INSERT INTO primitive_values VALUES (1, 'ALIVE', 1)")
    conn.execute("INSERT INTO primitive_values VALUES (1, 'SOMETHING', 1)")
    conn.execute("INSERT INTO sentence_primitive_values VALUES (1, 'SYN_SUBJ', 1)")

    # Adjective
    conn.execute("INSERT INTO lexemes (id, lemma, pos) VALUES (2, 'good', 'ADJ')")
    conn.execute("INSERT INTO primitive_values VALUES (2, 'GOOD', 1)")

    # Comparative operator
    conn.execute("""INSERT INTO lexemes
        (id, lemma, pos, comp_primitive, comp_arity, comp_operation)
        VALUES (3, 'than', 'ADP', 'COMP_THAN', 2, 'SET_DIFF')""")

    conn.commit()
    conn.close()
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def encoder(lexicon_db):
    """Create non-strict encoder."""
    enc = GSEEncoder(db_path=lexicon_db, strict=False)
    yield enc
    enc.close()


@pytest.fixture
def strict_encoder(lexicon_db):
    """Create strict encoder."""
    enc = GSEEncoder(db_path=lexicon_db, strict=True)
    yield enc
    enc.close()


class TestRoleMappings:
    def test_dep_to_syntactic_has_core_args(self):
        assert DEP_TO_SYNTACTIC["nsubj"] == "SYN_SUBJ"
        assert DEP_TO_SYNTACTIC["dobj"] == "SYN_OBJ"
        assert DEP_TO_SYNTACTIC["ROOT"] == "SYN_PRED"

    def test_dep_to_syntactic_has_modifiers(self):
        assert DEP_TO_SYNTACTIC["amod"] == "SYN_ADJ_MOD"
        assert DEP_TO_SYNTACTIC["advmod"] == "SYN_ADV_MOD"
        assert DEP_TO_SYNTACTIC["det"] == "SYN_DET"

    def test_morph_to_tam_has_tense(self):
        assert MORPH_TO_TAM["Tense=Past"] == "SYN_TENSE_PAST"
        assert MORPH_TO_TAM["Tense=Pres"] == "SYN_TENSE_PRES"


class TestInit:
    def test_default_non_strict(self, lexicon_db):
        enc = GSEEncoder(db_path=lexicon_db)
        assert enc.strict is False
        assert enc.db_path == Path(lexicon_db)
        enc.close()

    def test_strict_flag(self, lexicon_db):
        enc = GSEEncoder(db_path=lexicon_db, strict=True)
        assert enc.strict is True
        enc.close()

    def test_loads_bases(self, lexicon_db):
        enc = GSEEncoder(db_path=lexicon_db)
        assert enc.word_basis is not None
        assert enc.sent_basis is not None
        enc.close()


class TestLookupLexeme:
    def test_known_word_returns_primitives(self, encoder):
        word, sent, comp = encoder._lookup_lexeme("dog")
        assert word == {"ALIVE": 1, "SOMETHING": 1}
        assert sent == {"SYN_SUBJ": 1}
        assert comp == {}

    def test_oov_returns_empty_when_not_strict(self, encoder):
        word, sent, comp = encoder._lookup_lexeme("xyzzy_unknown")
        assert word == {}
        assert sent == {}
        assert comp == {}

    def test_oov_raises_when_strict(self, strict_encoder):
        with pytest.raises(OOVError):
            strict_encoder._lookup_lexeme("xyzzy_unknown")

    def test_compositional_lexeme_returns_comp_meta(self, encoder):
        word, sent, comp = encoder._lookup_lexeme("than")
        assert comp["comp_primitive"] == "COMP_THAN"
        assert comp["comp_arity"] == 2
        assert comp["comp_operation"] == "SET_DIFF"


class TestEncodeWordPrimitives:
    def test_empty_returns_zero(self, encoder):
        vec = encoder._encode_word_primitives({})
        assert vec.nnz == 0

    def test_known_primitive(self, encoder):
        vec = encoder._encode_word_primitives({"GOOD": 1})
        assert vec.nnz > 0

    def test_unknown_primitive_skipped_silent(self, encoder):
        # Non-strict: silently skips
        vec = encoder._encode_word_primitives({"XYZZY_UNK": 1})
        assert vec.nnz == 0

    def test_unknown_primitive_raises_strict(self, strict_encoder):
        with pytest.raises(PrimitiveError):
            strict_encoder._encode_word_primitives({"XYZZY_UNK": 1})

    def test_negative_value_negates(self, encoder):
        pos_vec = encoder._encode_word_primitives({"GOOD": 1})
        neg_vec = encoder._encode_word_primitives({"GOOD": -1})
        assert pos_vec.cosine(neg_vec) < 0.5


class TestEncodeSentPrimitives:
    def test_empty_returns_zero(self, encoder):
        vec = encoder._encode_sent_primitives({})
        assert vec.nnz == 0

    def test_known_primitive(self, encoder):
        vec = encoder._encode_sent_primitives({"SYN_SUBJ": 1})
        assert vec.nnz > 0

    def test_unknown_silent_non_strict(self, encoder):
        vec = encoder._encode_sent_primitives({"NOT_A_SYN_PRIM": 1})
        assert vec.nnz == 0

    def test_unknown_raises_strict(self, strict_encoder):
        with pytest.raises(PrimitiveError):
            strict_encoder._encode_sent_primitives({"NOT_A_SYN_PRIM": 1})


class TestExtractDynamicPrimitives:
    def test_known_dep_label_maps_to_syn(self, encoder):
        # Use a fake token with dep='nsubj'
        class FakeTok:
            dep_ = "nsubj"
            morph = ""

        prims = encoder._extract_dynamic_primitives(FakeTok())
        assert prims["SYN_SUBJ"] == 1

    def test_unknown_dep_label_ignored(self, encoder):
        class FakeTok:
            dep_ = "totally_unknown_label"
            morph = ""

        prims = encoder._extract_dynamic_primitives(FakeTok())
        # Only morph would contribute; no morph means empty
        assert prims == {}

    def test_morph_tense_past(self, encoder):
        class FakeTok:
            dep_ = ""
            morph = "Tense=Past|VerbForm=Fin"

        prims = encoder._extract_dynamic_primitives(FakeTok())
        assert prims["SYN_TENSE_PAST"] == 1

    def test_combined_dep_and_morph(self, encoder):
        class FakeTok:
            dep_ = "ROOT"
            morph = "Tense=Past"

        prims = encoder._extract_dynamic_primitives(FakeTok())
        assert prims["SYN_PRED"] == 1
        assert prims["SYN_TENSE_PAST"] == 1


class TestComputePrimitiveActivations:
    def test_zero_vector_no_activations(self, encoder):
        zero = SparseVector.zeros(encoder.word_basis.dimension)
        result = encoder._compute_primitive_activations(zero, encoder.word_basis)
        assert result == {}

    def test_self_activates_strongly(self, encoder):
        good = encoder.word_basis.get_primitive("GOOD")
        result = encoder._compute_primitive_activations(good, encoder.word_basis)
        assert "GOOD" in result
        assert result["GOOD"] > 0.9


class TestHashVector:
    def test_returns_sha256_prefix(self, encoder):
        v = encoder.word_basis.get_primitive("GOOD")
        h = encoder._hash_vector(v)
        assert h.startswith("sha256:")
        # 16-char hex digest after prefix
        assert len(h) == len("sha256:") + 16

    def test_deterministic(self, encoder):
        v = encoder.word_basis.get_primitive("GOOD")
        assert encoder._hash_vector(v) == encoder._hash_vector(v)

    def test_different_vectors_different_hash(self, encoder):
        good = encoder.word_basis.get_primitive("GOOD")
        bad = encoder.word_basis.get_primitive("BAD")
        # GOOD and BAD have different positive/negative indices
        assert encoder._hash_vector(good) != encoder._hash_vector(bad)


class TestResolveOperator:
    def test_no_primitive_returns_none(self, encoder):
        result, vec = encoder._resolve_operator(0, {}, [], [])
        assert result is None
        assert vec is None

    def test_set_diff_with_args(self, encoder):
        # Build operator context: arg1 at idx 0, op at idx 1, arg2 at idx 2
        good_vec = encoder.word_basis.get_primitive("GOOD")
        bad_vec = encoder.word_basis.get_primitive("BAD")
        op_meta = {
            "comp_primitive": "COMP_THAN",
            "comp_operation": "SET_DIFF",
            "comp_arity": 2,
        }
        token_vectors = [
            (0, good_vec, {}),
            (1, SparseVector.zeros(good_vec.dimension), op_meta),
            (2, bad_vec, {}),
        ]
        token_traces = [
            TokenTrace(token="a", lemma="a", pos="N", position=0,
                       word_primitives={}, sent_primitives={},
                       word_vec_nnz=good_vec.nnz, sent_vec_nnz=0,
                       full_vec_nnz=good_vec.nnz, is_operator=False),
            TokenTrace(token="than", lemma="than", pos="ADP", position=1,
                       word_primitives={}, sent_primitives={},
                       word_vec_nnz=0, sent_vec_nnz=0, full_vec_nnz=0,
                       is_operator=True, comp_primitive="COMP_THAN",
                       comp_operation="SET_DIFF", comp_arity=2),
            TokenTrace(token="b", lemma="b", pos="N", position=2,
                       word_primitives={}, sent_primitives={},
                       word_vec_nnz=bad_vec.nnz, sent_vec_nnz=0,
                       full_vec_nnz=bad_vec.nnz, is_operator=False),
        ]
        op_trace, result_vec = encoder._resolve_operator(
            1, op_meta, token_vectors, token_traces
        )
        assert isinstance(op_trace, OperatorTrace)
        assert op_trace.primitive == "COMP_THAN"
        assert op_trace.operation == "SET_DIFF"
        assert 0 in op_trace.arg1_tokens
        assert 2 in op_trace.arg2_tokens
        assert result_vec is not None
        assert result_vec.nnz > 0


class TestEncode:
    def test_returns_operation_trace(self, encoder):
        trace = encoder.encode("dog")
        assert isinstance(trace, OperationTrace)
        assert trace.input_text == "dog"
        assert len(trace.tokens) >= 1

    def test_empty_text_handled(self, encoder):
        trace = encoder.encode("")
        # Empty doc → no tokens → empty trace
        assert trace.input_text == ""

    def test_oov_word_strict_raises(self, strict_encoder):
        # Unknown word in strict mode raises
        with pytest.raises(OOVError):
            strict_encoder.encode("xyzzy_neverword")

    def test_oov_word_silent_non_strict(self, encoder):
        # Non-strict: OOV word produces empty trace, no error
        trace = encoder.encode("xyzzy_neverword")
        # Tokens still exist but with empty primitives
        assert len(trace.tokens) >= 1


class TestEncodeBatch:
    def test_returns_list_of_traces(self, encoder):
        traces = encoder.encode_batch(["dog", "good"])
        assert len(traces) == 2
        assert all(isinstance(t, OperationTrace) for t in traces)

    def test_empty_batch(self, encoder):
        assert encoder.encode_batch([]) == []


class TestContextManager:
    def test_enter_returns_self(self, encoder):
        assert encoder.__enter__() is encoder

    def test_exit_closes_db(self, lexicon_db):
        enc = GSEEncoder(db_path=lexicon_db)
        enc.__exit__(None, None, None)
        with pytest.raises(sqlite3.ProgrammingError):
            enc.cursor.execute("SELECT 1")

    def test_context_manager_protocol(self, lexicon_db):
        with GSEEncoder(db_path=lexicon_db) as enc:
            assert enc is not None
        with pytest.raises(sqlite3.ProgrammingError):
            enc.cursor.execute("SELECT 1")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
