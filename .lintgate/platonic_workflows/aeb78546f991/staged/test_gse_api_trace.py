"""Tests for trace."""

from __future__ import annotations

import pytest
from gse.api.trace import AttributeExtraction, DecodedSemantics, EntityExtraction, OperationTrace, OperatorTrace, RelationExtraction, SimilarityResult, TokenTrace

        # TODO: Assert state changed correctly


def test_AttributeExtraction_to_dict_round_trip():
    """ROUND_TRIP: mutation property"""
    # Precondition: OperationTrace.to_dict ↔ OperationTrace.from_dict
    from gse.api.trace import OperationTrace
    original = OperationTrace(input_text=None, tokens=[TokenTrace(token="test", lemma="test", pos="test", position=1, word_primitives="test", sent_primitives="test", word_vec_nnz=1, sent_vec_nnz=1, full_vec_nnz=1)], operators=[OperatorTrace(primitive="test", operation="test", position=1, arity=1, arg1_tokens="test", arg2_tokens="test", arg1_lemmas="test", arg2_lemmas="test", result_nnz=1)], final_nnz=None, sparsity=None, word_primitive_activations={}, sent_primitive_activations={}, vector_hash=None, version=None, deterministic=None, _vector=None)
    serialized = original.to_dict()
    reconstructed = OperationTrace.from_dict(serialized)
    assert reconstructed.input_text == original.input_text, "input_text mismatch"
    assert reconstructed.tokens == original.tokens, "tokens mismatch"
    assert reconstructed.operators == original.operators, "operators mismatch"
    assert reconstructed.final_nnz == original.final_nnz, "final_nnz mismatch"
    assert reconstructed.sparsity == original.sparsity, "sparsity mismatch"
    assert reconstructed.word_primitive_activations == original.word_primitive_activations, "word_primitive_activations mismatch"
    assert reconstructed.sent_primitive_activations == original.sent_primitive_activations, "sent_primitive_activations mismatch"
    assert reconstructed.vector_hash == original.vector_hash, "vector_hash mismatch"
    assert reconstructed.version == original.version, "version mismatch"
    assert reconstructed.deterministic == original.deterministic, "deterministic mismatch"
    assert reconstructed._vector == original._vector, "_vector mismatch"

