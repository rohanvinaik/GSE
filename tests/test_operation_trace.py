"""
Tests for OperationTrace integration in GSEPipeline.encode_sentence.

Verifies that with_trace=True produces a well-formed OperationTrace
suitable for Tier 2 experiments (logical-structure auditing).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.api.trace import OperationTrace
from gse.pipeline_v2 import GSEPipeline


@pytest.fixture(scope="module")
def pipeline():
    return GSEPipeline()


class TestTraceDefault:
    def test_no_trace_by_default(self, pipeline):
        result = pipeline.encode_sentence("the cat sat")
        assert result.trace is None

    def test_with_trace_populates_trace(self, pipeline):
        result = pipeline.encode_sentence("the cat sat", with_trace=True)
        assert isinstance(result.trace, OperationTrace)


class TestTokenTraces:
    def test_one_token_trace_per_word(self, pipeline):
        result = pipeline.encode_sentence("the cat sat on the mat", with_trace=True)
        assert len(result.trace.tokens) == 6

    def test_token_trace_positions_sequential(self, pipeline):
        result = pipeline.encode_sentence("dog is big", with_trace=True)
        positions = [t.position for t in result.trace.tokens]
        assert positions == [0, 1, 2]

    def test_token_trace_lemma_is_lowercase(self, pipeline):
        result = pipeline.encode_sentence("THE Cat Sat", with_trace=True)
        lemmas = [t.lemma for t in result.trace.tokens]
        assert lemmas == ["the", "cat", "sat"]

    def test_token_trace_pos_assigned(self, pipeline):
        result = pipeline.encode_sentence("the cat ran", with_trace=True)
        for t in result.trace.tokens:
            assert t.pos != ""


class TestOperatorDetection:
    def test_than_detected_as_comp_than(self, pipeline):
        result = pipeline.encode_sentence("dog is cuter than cat", with_trace=True)
        than_tokens = [t for t in result.trace.tokens if t.token == "than"]
        assert len(than_tokens) == 1
        assert than_tokens[0].is_operator
        assert than_tokens[0].comp_primitive == "COMP_THAN"
        assert than_tokens[0].comp_operation == "SET_DIFF"
        assert than_tokens[0].comp_arity == 2

    def test_because_detected(self, pipeline):
        result = pipeline.encode_sentence("dog ran because cat chased", with_trace=True)
        ops = result.trace.operators
        assert len(ops) == 1
        assert ops[0].primitive == "COMP_BECAUSE"
        assert ops[0].operation == "CAUSAL_SOURCE"

    def test_non_operator_not_flagged(self, pipeline):
        result = pipeline.encode_sentence("the cat sat", with_trace=True)
        for t in result.trace.tokens:
            assert not t.is_operator

    def test_operators_list_matches_token_flags(self, pipeline):
        result = pipeline.encode_sentence("dog runs but cat sleeps", with_trace=True)
        flagged = sum(1 for t in result.trace.tokens if t.is_operator)
        assert flagged == len(result.trace.operators)


class TestOperatorArgs:
    def test_arg_resolution_for_than(self, pipeline):
        result = pipeline.encode_sentence("dog is cuter than cat", with_trace=True)
        op = result.trace.operators[0]
        # before "than": positions 0,1,2 — "dog", "is", "cuter"
        assert op.arg1_lemmas == ["dog", "is", "cuter"]
        # after "than": position 4 — "cat"
        assert op.arg2_lemmas == ["cat"]

    def test_argument_swap_distinct_from_identical(self, pipeline):
        forward = pipeline.encode_sentence("dog runs but cat sleeps", with_trace=True).trace
        identical = pipeline.encode_sentence("dog runs but cat sleeps", with_trace=True).trace
        # Identical sentences are not argument-swaps of each other
        # (entities sit in the same positions)
        assert not forward.is_argument_swap_of(identical)
        # But they are logically equal
        assert forward.logical_equals(identical)


class TestVectorStats:
    def test_final_nnz_matches_vector(self, pipeline):
        result = pipeline.encode_sentence("the cat sat", with_trace=True)
        assert result.trace.final_nnz >= 0

    def test_sparsity_in_range(self, pipeline):
        result = pipeline.encode_sentence("the cat sat", with_trace=True)
        assert 0.0 <= result.trace.sparsity <= 1.0

    def test_vector_hash_deterministic(self, pipeline):
        r1 = pipeline.encode_sentence("the cat sat", with_trace=True)
        r2 = pipeline.encode_sentence("the cat sat", with_trace=True)
        assert r1.trace.vector_hash == r2.trace.vector_hash

    def test_different_sentences_different_hash(self, pipeline):
        r1 = pipeline.encode_sentence("the cat sat", with_trace=True)
        r2 = pipeline.encode_sentence("the dog ran", with_trace=True)
        assert r1.trace.vector_hash != r2.trace.vector_hash


class TestTraceSerialization:
    def test_trace_to_json(self, pipeline):
        result = pipeline.encode_sentence("dog is cuter than cat", with_trace=True)
        js = result.trace.to_json()
        assert "input_text" in js
        assert "COMP_THAN" in js

    def test_trace_roundtrip(self, pipeline):
        result = pipeline.encode_sentence("dog is cuter than cat", with_trace=True)
        js = result.trace.to_json()
        restored = OperationTrace.from_json(js)
        assert restored.input_text == result.trace.input_text
        assert len(restored.tokens) == len(result.trace.tokens)
        assert len(restored.operators) == len(result.trace.operators)
        assert restored.vector_hash == result.trace.vector_hash


class TestLogicalStructure:
    def test_logical_equals_identical(self, pipeline):
        t1 = pipeline.encode_sentence("dog is cuter than cat", with_trace=True).trace
        t2 = pipeline.encode_sentence("dog is cuter than cat", with_trace=True).trace
        assert t1.logical_equals(t2)

    def test_logical_inequals_different_operator(self, pipeline):
        t1 = pipeline.encode_sentence("dog is cuter than cat", with_trace=True).trace
        t2 = pipeline.encode_sentence("dog is cuter but cat ran", with_trace=True).trace
        assert not t1.logical_equals(t2)


class TestEmptyInput:
    def test_empty_string(self, pipeline):
        result = pipeline.encode_sentence("", with_trace=True)
        # Empty sentence returns early — no trace built
        assert result.trace is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
