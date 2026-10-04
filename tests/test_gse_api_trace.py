"""Manual contract tests for gse.api.trace.

LintGate classified 19 of 20 functions as manual_contract (dataclass
serialization + logical equality methods). These tests exercise each
behavior directly, not through pipeline integration.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json

import pytest

from gse.api.trace import (
    AttributeExtraction,
    DecodedSemantics,
    EntityExtraction,
    OperationTrace,
    OperatorTrace,
    RelationExtraction,
    SimilarityResult,
    TokenTrace,
)


def make_token(position=0, token="word", lemma="word", pos="n"):
    return TokenTrace(
        token=token,
        lemma=lemma,
        pos=pos,
        position=position,
        word_primitives={"FEEL": 1},
        sent_primitives={"SYN_SUBJ": 1},
        word_vec_nnz=10,
        sent_vec_nnz=5,
        full_vec_nnz=15,
    )


def make_operator(primitive="COMP_THAN", operation="SET_DIFF", position=3,
                  arg1_lemmas=("dog",), arg2_lemmas=("cat",)):
    return OperatorTrace(
        primitive=primitive,
        operation=operation,
        position=position,
        arity=2,
        arg1_tokens=list(range(len(arg1_lemmas))),
        arg2_tokens=[position + 1 + i for i in range(len(arg2_lemmas))],
        arg1_lemmas=list(arg1_lemmas),
        arg2_lemmas=list(arg2_lemmas),
        result_nnz=20,
    )


def make_trace(input_text="dog is cuter than cat",
               tokens=None, operators=None,
               final_nnz=100, sparsity=0.012,
               vector_hash="abc123"):
    return OperationTrace(
        input_text=input_text,
        tokens=[make_token(0, "dog", "dog"), make_token(4, "cat", "cat")] if tokens is None else tokens,
        operators=[make_operator()] if operators is None else operators,
        final_nnz=final_nnz,
        sparsity=sparsity,
        word_primitive_activations={"FEEL": 0.7},
        sent_primitive_activations={"SYN_SUBJ": 1.0},
        vector_hash=vector_hash,
    )


# ============================================================
# TokenTrace
# ============================================================

class TestTokenTraceToDict:
    def test_returns_dict_with_all_fields(self):
        t = make_token(position=2, token="hello", lemma="hello", pos="n")
        d = t.to_dict()
        assert d["token"] == "hello"
        assert d["lemma"] == "hello"
        assert d["pos"] == "n"
        assert d["position"] == 2
        assert d["word_primitives"] == {"FEEL": 1}
        assert d["sent_primitives"] == {"SYN_SUBJ": 1}
        assert d["word_vec_nnz"] == 10
        assert d["sent_vec_nnz"] == 5
        assert d["full_vec_nnz"] == 15
        assert d["is_operator"] is False
        assert d["comp_primitive"] is None
        assert d["comp_operation"] is None
        assert d["comp_arity"] == 0

    def test_operator_token_serializes_op_fields(self):
        t = TokenTrace(
            token="than", lemma="than", pos="prep", position=3,
            word_primitives={}, sent_primitives={"COMP_THAN": 1},
            word_vec_nnz=0, sent_vec_nnz=8, full_vec_nnz=8,
            is_operator=True, comp_primitive="COMP_THAN",
            comp_operation="SET_DIFF", comp_arity=2,
        )
        d = t.to_dict()
        assert d["is_operator"] is True
        assert d["comp_primitive"] == "COMP_THAN"
        assert d["comp_operation"] == "SET_DIFF"
        assert d["comp_arity"] == 2


# ============================================================
# OperatorTrace
# ============================================================

class TestOperatorTraceToDict:
    def test_returns_dict_with_all_fields(self):
        op = make_operator(
            primitive="COMP_BUT", operation="CONTRAST", position=2,
            arg1_lemmas=("dog", "ran"), arg2_lemmas=("cat", "slept"),
        )
        d = op.to_dict()
        assert d["primitive"] == "COMP_BUT"
        assert d["operation"] == "CONTRAST"
        assert d["position"] == 2
        assert d["arity"] == 2
        assert d["arg1_lemmas"] == ["dog", "ran"]
        assert d["arg2_lemmas"] == ["cat", "slept"]
        assert d["result_nnz"] == 20


class TestGetContentArgs:
    def test_filters_function_words(self):
        op = make_operator(arg1_lemmas=("the", "dog", "is"), arg2_lemmas=("a", "cat"))
        a1, a2 = op.get_content_args()
        assert a1 == ("dog",)
        assert a2 == ("cat",)

    def test_keeps_non_function_words(self):
        op = make_operator(arg1_lemmas=("dog", "ran"), arg2_lemmas=("cat", "slept"))
        a1, a2 = op.get_content_args()
        assert a1 == ("dog", "ran")
        assert a2 == ("cat", "slept")

    def test_empty_when_all_function_words(self):
        op = make_operator(arg1_lemmas=("the", "a"), arg2_lemmas=("is", "are"))
        a1, a2 = op.get_content_args()
        assert a1 == ()
        assert a2 == ()

    def test_returns_tuples_not_lists(self):
        op = make_operator()
        a1, a2 = op.get_content_args()
        assert isinstance(a1, tuple)
        assert isinstance(a2, tuple)


class TestGetEntityArgs:
    def test_filters_function_words_and_properties(self):
        op = make_operator(arg1_lemmas=("the", "dog", "cute"),
                           arg2_lemmas=("a", "cat", "small"))
        a1, a2 = op.get_entity_args()
        assert a1 == ("dog",)
        assert a2 == ("cat",)

    def test_filters_evaluative_properties(self):
        op = make_operator(arg1_lemmas=("dog", "good"), arg2_lemmas=("cat", "bad"))
        a1, a2 = op.get_entity_args()
        assert a1 == ("dog",)
        assert a2 == ("cat",)

    def test_filters_more_less(self):
        op = make_operator(arg1_lemmas=("more", "dog"), arg2_lemmas=("less", "cat"))
        a1, a2 = op.get_entity_args()
        assert a1 == ("dog",)
        assert a2 == ("cat",)


class TestStructurallyEquals:
    def test_identical_operators_equal(self):
        op1 = make_operator(operation="SET_DIFF", arg1_lemmas=("dog",), arg2_lemmas=("cat",))
        op2 = make_operator(operation="SET_DIFF", arg1_lemmas=("dog",), arg2_lemmas=("cat",))
        assert op1.structurally_equals(op2)

    def test_different_operations_not_equal(self):
        op1 = make_operator(operation="SET_DIFF")
        op2 = make_operator(operation="CONTRAST")
        assert not op1.structurally_equals(op2)

    def test_different_args_not_equal(self):
        op1 = make_operator(arg1_lemmas=("dog",), arg2_lemmas=("cat",))
        op2 = make_operator(arg1_lemmas=("bird",), arg2_lemmas=("fish",))
        assert not op1.structurally_equals(op2)

    def test_function_words_ignored_in_comparison(self):
        op1 = make_operator(arg1_lemmas=("the", "dog"), arg2_lemmas=("cat",))
        op2 = make_operator(arg1_lemmas=("dog",), arg2_lemmas=("the", "cat"))
        assert op1.structurally_equals(op2)


class TestOperatorIsArgumentSwapOf:
    def test_swap_detected(self):
        forward = make_operator(arg1_lemmas=("dog",), arg2_lemmas=("cat",))
        swapped = make_operator(arg1_lemmas=("cat",), arg2_lemmas=("dog",))
        assert forward.is_argument_swap_of(swapped)

    def test_same_args_not_swap(self):
        a = make_operator(arg1_lemmas=("dog",), arg2_lemmas=("cat",))
        b = make_operator(arg1_lemmas=("dog",), arg2_lemmas=("cat",))
        assert not a.is_argument_swap_of(b)

    def test_different_operations_never_swap(self):
        a = make_operator(operation="SET_DIFF", arg1_lemmas=("dog",), arg2_lemmas=("cat",))
        b = make_operator(operation="CONTRAST", arg1_lemmas=("cat",), arg2_lemmas=("dog",))
        assert not a.is_argument_swap_of(b)

    def test_properties_filtered_for_swap_detection(self):
        # "dog cuter than cat" is swap of "cat cuter than dog"
        # cuter is a property; should be filtered
        a = make_operator(arg1_lemmas=("dog", "cute"), arg2_lemmas=("cat",))
        b = make_operator(arg1_lemmas=("cat", "cute"), arg2_lemmas=("dog",))
        assert a.is_argument_swap_of(b)


# ============================================================
# OperationTrace
# ============================================================

class TestOperationTraceToDict:
    def test_returns_dict_with_all_fields(self):
        t = make_trace()
        d = t.to_dict()
        assert d["input_text"] == "dog is cuter than cat"
        assert d["version"] == "1.0"
        assert d["deterministic"] is True
        assert d["final_nnz"] == 100
        assert d["sparsity"] == 0.012
        assert d["vector_hash"] == "abc123"
        assert isinstance(d["tokens"], list)
        assert isinstance(d["operators"], list)
        assert "word_primitive_activations" in d
        assert "sent_primitive_activations" in d

    def test_tokens_serialized_as_dicts(self):
        t = make_trace()
        d = t.to_dict()
        for tok in d["tokens"]:
            assert isinstance(tok, dict)
            assert "token" in tok

    def test_operators_serialized_as_dicts(self):
        t = make_trace()
        d = t.to_dict()
        for op in d["operators"]:
            assert isinstance(op, dict)
            assert "primitive" in op

    def test_vector_field_excluded(self):
        t = make_trace()
        t.vector = "fake_vector_object"
        d = t.to_dict()
        assert "vector" not in d
        assert "_vector" not in d


class TestOperationTraceToJson:
    def test_returns_valid_json_string(self):
        t = make_trace()
        s = t.to_json()
        assert isinstance(s, str)
        parsed = json.loads(s)
        assert parsed["input_text"] == "dog is cuter than cat"

    def test_indent_param_applied(self):
        t = make_trace()
        s = t.to_json(indent=4)
        # 4-space indent should appear
        assert "    " in s


class TestOperationTraceFromDict:
    def test_roundtrip(self):
        original = make_trace()
        d = original.to_dict()
        restored = OperationTrace.from_dict(d)
        assert restored.input_text == original.input_text
        assert len(restored.tokens) == len(original.tokens)
        assert len(restored.operators) == len(original.operators)
        assert restored.final_nnz == original.final_nnz
        assert restored.vector_hash == original.vector_hash

    def test_version_default_applied(self):
        original = make_trace()
        d = original.to_dict()
        del d["version"]
        restored = OperationTrace.from_dict(d)
        assert restored.version == "1.0"

    def test_deterministic_default_applied(self):
        original = make_trace()
        d = original.to_dict()
        del d["deterministic"]
        restored = OperationTrace.from_dict(d)
        assert restored.deterministic is True


class TestOperationTraceFromJson:
    def test_roundtrip(self):
        original = make_trace()
        s = original.to_json()
        restored = OperationTrace.from_json(s)
        assert restored.input_text == original.input_text
        assert restored.vector_hash == original.vector_hash


class TestOperationTraceLogicalEquals:
    def test_identical_traces_equal(self):
        t1 = make_trace()
        t2 = make_trace()
        assert t1.logical_equals(t2)

    def test_different_operator_count_not_equal(self):
        t1 = make_trace(operators=[make_operator()])
        t2 = make_trace(operators=[])
        assert not t1.logical_equals(t2)

    def test_different_operator_operation_not_equal(self):
        t1 = make_trace(operators=[make_operator(operation="SET_DIFF")])
        t2 = make_trace(operators=[make_operator(operation="CONTRAST")])
        assert not t1.logical_equals(t2)


class TestOperationTraceIsArgumentSwapOf:
    def test_identical_traces_not_swap(self):
        t1 = make_trace()
        t2 = make_trace()
        assert not t1.is_argument_swap_of(t2)

    def test_different_operator_count_not_swap(self):
        t1 = make_trace(operators=[make_operator(), make_operator()])
        t2 = make_trace(operators=[make_operator()])
        assert not t1.is_argument_swap_of(t2)

    def test_swapped_args_detected(self):
        t1 = make_trace(operators=[make_operator(arg1_lemmas=("dog",), arg2_lemmas=("cat",))])
        t2 = make_trace(operators=[make_operator(arg1_lemmas=("cat",), arg2_lemmas=("dog",))])
        assert t1.is_argument_swap_of(t2)


class TestOperationTraceVectorProperty:
    def test_default_none(self):
        t = make_trace()
        assert t.vector is None

    def test_setter_stores_value(self):
        t = make_trace()
        sentinel = object()
        t.vector = sentinel
        assert t.vector is sentinel

    def test_setter_then_to_dict_excludes(self):
        t = make_trace()
        t.vector = "fake_vec"
        d = t.to_dict()
        assert "vector" not in d


# ============================================================
# EntityExtraction / AttributeExtraction / RelationExtraction
# ============================================================

class TestEntityExtractionToDict:
    def test_dict_contains_all_fields(self):
        e = EntityExtraction(lemma="dog", pos="n", confidence=0.85,
                             primitives=["SOMEONE", "ANIMATE"])
        d = e.to_dict()
        assert d["lemma"] == "dog"
        assert d["pos"] == "n"
        assert d["confidence"] == 0.85
        assert d["primitives"] == ["SOMEONE", "ANIMATE"]


class TestAttributeExtractionToDict:
    def test_dict_contains_all_fields(self):
        a = AttributeExtraction(attribute="positive_quality", polarity=1,
                                intensity=0.8, source_primitive="GOOD")
        d = a.to_dict()
        assert d["attribute"] == "positive_quality"
        assert d["polarity"] == 1
        assert d["intensity"] == 0.8
        assert d["source_primitive"] == "GOOD"


class TestRelationExtractionToDict:
    def test_dict_contains_all_fields(self):
        r = RelationExtraction(relation="COMP_THAN", confidence=0.7,
                               operation="SET_DIFF",
                               arg1_candidates=["dog"], arg2_candidates=["cat"])
        d = r.to_dict()
        assert d["relation"] == "COMP_THAN"
        assert d["confidence"] == 0.7
        assert d["operation"] == "SET_DIFF"
        assert d["arg1_candidates"] == ["dog"]
        assert d["arg2_candidates"] == ["cat"]


# ============================================================
# DecodedSemantics
# ============================================================

class TestDecodedSemanticsToDict:
    def test_aggregates_all_extractions(self):
        ds = DecodedSemantics(
            entities=[EntityExtraction("dog", "n", 0.9, ["SOMEONE"])],
            attributes=[AttributeExtraction("size", 1, 0.5, "BIG")],
            relations=[RelationExtraction("COMP_THAN", 0.7, "SET_DIFF", ["dog"], ["cat"])],
            nearest_lexemes=[("dog", 0.95)],
            bank_activations={"SUBSTANTIVES": 0.9},
            primitive_activations={"SOMEONE": 0.85},
        )
        d = ds.to_dict()
        assert len(d["entities"]) == 1
        assert d["entities"][0]["lemma"] == "dog"
        assert len(d["attributes"]) == 1
        assert d["attributes"][0]["attribute"] == "size"
        assert len(d["relations"]) == 1
        assert d["nearest_lexemes"] == [("dog", 0.95)]
        assert d["bank_activations"] == {"SUBSTANTIVES": 0.9}
        assert d["primitive_activations"] == {"SOMEONE": 0.85}

    def test_empty_extractions(self):
        ds = DecodedSemantics(
            entities=[], attributes=[], relations=[],
            nearest_lexemes=[], bank_activations={}, primitive_activations={},
        )
        d = ds.to_dict()
        assert d["entities"] == []
        assert d["attributes"] == []
        assert d["relations"] == []


class TestDecodedSemanticsToJson:
    def test_valid_json(self):
        ds = DecodedSemantics(
            entities=[], attributes=[], relations=[],
            nearest_lexemes=[], bank_activations={}, primitive_activations={},
        )
        s = ds.to_json()
        parsed = json.loads(s)
        assert "entities" in parsed


# ============================================================
# SimilarityResult
# ============================================================

class TestSimilarityResultToDict:
    def test_all_fields(self):
        sr = SimilarityResult(
            sentence1="dog runs", sentence2="cat sleeps",
            cosine=0.3, alignment=0.5, opposition=0.2, orthogonality=0.3,
            shared_primitives=["ACTION"], different_primitives=["SOMEONE"],
        )
        d = sr.to_dict()
        assert d["sentence1"] == "dog runs"
        assert d["sentence2"] == "cat sleeps"
        assert d["cosine"] == 0.3
        assert d["alignment"] == 0.5
        assert d["opposition"] == 0.2
        assert d["orthogonality"] == 0.3
        assert d["shared_primitives"] == ["ACTION"]
        assert d["different_primitives"] == ["SOMEONE"]


class TestSimilarityResultToJson:
    def test_valid_json(self):
        sr = SimilarityResult(
            sentence1="a", sentence2="b",
            cosine=0.0, alignment=0.0, opposition=0.0, orthogonality=1.0,
            shared_primitives=[], different_primitives=[],
        )
        s = sr.to_json()
        parsed = json.loads(s)
        assert parsed["sentence1"] == "a"


# ============================================================
# Filter-set mutation killers
# ============================================================

class TestContentArgsFilterMembership:
    """Each function-word in the filter set must be tested explicitly so
    VALUE mutations that replace a set member with something else get killed.
    """

    @pytest.mark.parametrize("function_word", [
        "the", "a", "an", "be", "is", "are", "was", "were",
    ])
    def test_each_function_word_filtered(self, function_word):
        op = make_operator(arg1_lemmas=(function_word, "dog"), arg2_lemmas=("cat",))
        a1, a2 = op.get_content_args()
        assert function_word not in a1
        assert a1 == ("dog",)

    @pytest.mark.parametrize("not_function_word", ["dog", "cat", "ran", "felt"])
    def test_content_words_not_filtered(self, not_function_word):
        op = make_operator(arg1_lemmas=(not_function_word,), arg2_lemmas=("x",))
        a1, _ = op.get_content_args()
        assert not_function_word in a1


class TestEntityArgsFilterMembership:
    """Each non-entity word must be explicitly tested for VALUE mutation killing."""

    @pytest.mark.parametrize("non_entity", [
        "the", "a", "an", "be", "is", "are", "was", "were",
        "cut", "cute", "big", "small", "tall", "short",
        "fast", "slow", "good", "bad", "more", "less",
    ])
    def test_each_non_entity_filtered(self, non_entity):
        op = make_operator(arg1_lemmas=(non_entity, "dog"), arg2_lemmas=("cat",))
        a1, a2 = op.get_entity_args()
        assert non_entity not in a1
        assert a1 == ("dog",)


class TestLogicalEqualsAsymmetric:
    """Tests that catch SWAP / VALUE mutations on logical_equals."""

    def test_different_arg_lemmas_break_equality(self):
        t1 = make_trace(operators=[make_operator(arg1_lemmas=("dog",), arg2_lemmas=("cat",))])
        t2 = make_trace(operators=[make_operator(arg1_lemmas=("dog",), arg2_lemmas=("bird",))])
        assert not t1.logical_equals(t2)

    def test_operator_position_doesnt_break_equality(self):
        """logical_equals checks structure, not position."""
        t1 = make_trace(operators=[make_operator(position=2)])
        t2 = make_trace(operators=[make_operator(position=5)])
        assert t1.logical_equals(t2)


class TestIsArgumentSwapAsymmetric:
    """Tests that catch SWAP/VALUE mutations on is_argument_swap_of."""

    def test_partial_swap_not_full_swap(self):
        """If one entity matches but the other doesn't, not a swap."""
        t1 = make_trace(operators=[make_operator(arg1_lemmas=("dog",), arg2_lemmas=("cat",))])
        t2 = make_trace(operators=[make_operator(arg1_lemmas=("cat",), arg2_lemmas=("bird",))])
        assert not t1.is_argument_swap_of(t2)

    def test_three_operators_all_swapped(self):
        t1 = make_trace(operators=[
            make_operator(arg1_lemmas=("dog",), arg2_lemmas=("cat",)),
            make_operator(arg1_lemmas=("a",), arg2_lemmas=("b",)),
            make_operator(arg1_lemmas=("x",), arg2_lemmas=("y",)),
        ])
        t2 = make_trace(operators=[
            make_operator(arg1_lemmas=("cat",), arg2_lemmas=("dog",)),
            make_operator(arg1_lemmas=("b",), arg2_lemmas=("a",)),
            make_operator(arg1_lemmas=("y",), arg2_lemmas=("x",)),
        ])
        assert t1.is_argument_swap_of(t2)

    def test_three_operators_one_not_swapped(self):
        t1 = make_trace(operators=[
            make_operator(arg1_lemmas=("dog",), arg2_lemmas=("cat",)),
            make_operator(arg1_lemmas=("a",), arg2_lemmas=("b",)),
        ])
        t2 = make_trace(operators=[
            make_operator(arg1_lemmas=("cat",), arg2_lemmas=("dog",)),
            make_operator(arg1_lemmas=("a",), arg2_lemmas=("b",)),  # not swapped
        ])
        assert not t1.is_argument_swap_of(t2)


class TestStructurallyEqualsValueMutation:
    """Catch the VALUE mutation that survives structurally_equals."""

    def test_same_operation_different_content_args(self):
        op1 = make_operator(operation="SET_DIFF", arg1_lemmas=("dog",), arg2_lemmas=("cat",))
        op2 = make_operator(operation="SET_DIFF", arg1_lemmas=("bird",), arg2_lemmas=("cat",))
        assert not op1.structurally_equals(op2)

    def test_arg2_difference_caught(self):
        op1 = make_operator(arg1_lemmas=("dog",), arg2_lemmas=("cat",))
        op2 = make_operator(arg1_lemmas=("dog",), arg2_lemmas=("bird",))
        assert not op1.structurally_equals(op2)


class TestOperatorIsArgumentSwapLogical:
    """Catch the LOGICAL mutation on OperatorTrace.is_argument_swap_of."""

    def test_partial_entity_match_not_swap(self):
        """First entity matches forward, second doesn't — not a swap."""
        a = make_operator(arg1_lemmas=("dog",), arg2_lemmas=("cat",))
        b = make_operator(arg1_lemmas=("dog",), arg2_lemmas=("bird",))
        assert not a.is_argument_swap_of(b)

    def test_reverse_only_first_entity(self):
        a = make_operator(arg1_lemmas=("dog",), arg2_lemmas=("cat",))
        b = make_operator(arg1_lemmas=("bird",), arg2_lemmas=("dog",))
        # b.arg1=bird (not in a.arg2=cat) so not a swap
        assert not a.is_argument_swap_of(b)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
