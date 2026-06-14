"""Manual contract tests for gse.scales.syntactic_structure."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.scales.syntactic_structure import (
    BANK_ALLOCATIONS,
    BANK_ASSIGNMENTS,
    SentenceSyntax,
    SyntacticAnnotation,
    SyntacticBank,
    SyntacticPrimitive,
    SyntacticPrimitiveEncoder,
)


def make_annotation(word="x", position=0, primitives=None, bank_weights=None):
    return SyntacticAnnotation(
        word=word, position=position,
        primitives=set([SyntacticPrimitive.SYN_SUBJ] if primitives is None else primitives),
        bank_weights=bank_weights or {SyntacticBank.CORE: 1.0,
                                       SyntacticBank.MODIFICATION: 1.0,
                                       SyntacticBank.TAM: 1.0},
    )


class TestSyntacticAnnotationGetBankPrimitives:
    def test_filters_by_bank(self):
        a = make_annotation(primitives=[
            SyntacticPrimitive.SYN_SUBJ,  # CORE
            SyntacticPrimitive.SYN_DET,   # MODIFICATION
        ])
        core = a.get_bank_primitives(SyntacticBank.CORE)
        assert core == {SyntacticPrimitive.SYN_SUBJ}
        mod = a.get_bank_primitives(SyntacticBank.MODIFICATION)
        assert mod == {SyntacticPrimitive.SYN_DET}

    def test_no_primitives_in_bank(self):
        a = make_annotation(primitives=[SyntacticPrimitive.SYN_SUBJ])
        assert a.get_bank_primitives(SyntacticBank.TAM) == set()

    def test_empty_primitives(self):
        a = make_annotation(primitives=[])
        assert a.get_bank_primitives(SyntacticBank.CORE) == set()


class TestSyntacticAnnotationIsContentWord:
    def test_subject_is_content(self):
        a = make_annotation(primitives=[SyntacticPrimitive.SYN_SUBJ])
        assert a.is_content_word

    def test_only_determiner_not_content(self):
        a = make_annotation(primitives=[SyntacticPrimitive.SYN_DET])
        assert not a.is_content_word

    def test_no_primitives_not_content(self):
        a = make_annotation(primitives=[])
        assert not a.is_content_word

    def test_subj_plus_det_is_content(self):
        a = make_annotation(primitives=[SyntacticPrimitive.SYN_SUBJ, SyntacticPrimitive.SYN_DET])
        assert a.is_content_word


class TestSentenceSyntax:
    def test_word_count(self):
        s = SentenceSyntax(annotations=[make_annotation(), make_annotation()], sentence_text="x")
        assert s.word_count == 2

    def test_get_subjects(self):
        s = SentenceSyntax(
            annotations=[
                make_annotation(primitives=[SyntacticPrimitive.SYN_SUBJ]),
                make_annotation(primitives=[SyntacticPrimitive.SYN_PRED]),
                make_annotation(primitives=[SyntacticPrimitive.SYN_SUBJ]),
            ],
            sentence_text="x",
        )
        assert len(s.get_subjects()) == 2

    def test_get_predicates(self):
        s = SentenceSyntax(
            annotations=[
                make_annotation(primitives=[SyntacticPrimitive.SYN_SUBJ]),
                make_annotation(primitives=[SyntacticPrimitive.SYN_PRED]),
            ],
            sentence_text="x",
        )
        assert len(s.get_predicates()) == 1

    def test_get_objects(self):
        s = SentenceSyntax(
            annotations=[
                make_annotation(primitives=[SyntacticPrimitive.SYN_OBJ]),
            ],
            sentence_text="x",
        )
        assert len(s.get_objects()) == 1


class TestSyntacticPrimitiveEncoder:
    def test_init_default_dims(self):
        e = SyntacticPrimitiveEncoder()
        assert e.D == 8192

    def test_init_custom_dims(self):
        e = SyntacticPrimitiveEncoder(total_dims=1024)
        assert e.D == 1024

    def test_deterministic_from_seed(self):
        e1 = SyntacticPrimitiveEncoder(seed=42)
        e2 = SyntacticPrimitiveEncoder(seed=42)
        v1 = e1._primitive_bases[SyntacticPrimitive.SYN_SUBJ]
        v2 = e2._primitive_bases[SyntacticPrimitive.SYN_SUBJ]
        assert np.array_equal(v1, v2)

    def test_different_seeds_different_bases(self):
        e1 = SyntacticPrimitiveEncoder(seed=1)
        e2 = SyntacticPrimitiveEncoder(seed=2)
        v1 = e1._primitive_bases[SyntacticPrimitive.SYN_SUBJ]
        v2 = e2._primitive_bases[SyntacticPrimitive.SYN_SUBJ]
        assert not np.array_equal(v1, v2)

    def test_each_primitive_has_basis(self):
        e = SyntacticPrimitiveEncoder()
        for prim in SyntacticPrimitive:
            assert prim in e._primitive_bases
            assert e._primitive_bases[prim].shape == (e.D,)

    def test_bases_normalized(self):
        e = SyntacticPrimitiveEncoder()
        for prim, basis in e._primitive_bases.items():
            norm = np.linalg.norm(basis)
            assert abs(norm - 1.0) < 1e-6


class TestEncodeWord:
    def test_returns_d_dim_vector(self):
        e = SyntacticPrimitiveEncoder()
        a = make_annotation(primitives=[SyntacticPrimitive.SYN_SUBJ])
        v = e.encode_word(a, 0, 1024)
        assert v.shape == (8192,)

    def test_zero_word_dims_returns_zeros(self):
        e = SyntacticPrimitiveEncoder()
        a = make_annotation(primitives=[SyntacticPrimitive.SYN_SUBJ])
        v = e.encode_word(a, 100, 100)  # start == end → zero dims
        assert np.all(v == 0)

    def test_negative_word_dims_returns_zeros(self):
        e = SyntacticPrimitiveEncoder()
        a = make_annotation(primitives=[SyntacticPrimitive.SYN_SUBJ])
        v = e.encode_word(a, 200, 100)
        assert np.all(v == 0)

    def test_nonzero_for_word_with_primitives(self):
        e = SyntacticPrimitiveEncoder()
        a = make_annotation(primitives=[SyntacticPrimitive.SYN_SUBJ])
        v = e.encode_word(a, 0, 1024)
        assert np.count_nonzero(v) > 0


class TestEncodeSentence:
    def test_empty_returns_zeros(self):
        e = SyntacticPrimitiveEncoder()
        s = SentenceSyntax(annotations=[], sentence_text="")
        v = e.encode_sentence(s)
        assert np.all(v == 0)

    def test_normalized_output(self):
        e = SyntacticPrimitiveEncoder()
        s = SentenceSyntax(
            annotations=[make_annotation(primitives=[SyntacticPrimitive.SYN_SUBJ])],
            sentence_text="x",
        )
        v = e.encode_sentence(s)
        assert abs(np.linalg.norm(v) - 1.0) < 1e-6

    def test_interrogative_adds_marker(self):
        e = SyntacticPrimitiveEncoder()
        s_no = SentenceSyntax(annotations=[make_annotation()], sentence_text="x")
        s_yes = SentenceSyntax(annotations=[make_annotation()], sentence_text="x?", is_interrogative=True)
        v_no = e.encode_sentence(s_no)
        v_yes = e.encode_sentence(s_yes)
        assert not np.array_equal(v_no, v_yes)


class TestBankAssignments:
    def test_core_primitives(self):
        core = [p for p, b in BANK_ASSIGNMENTS.items() if b == SyntacticBank.CORE]
        assert SyntacticPrimitive.SYN_SUBJ in core
        assert SyntacticPrimitive.SYN_PRED in core
        assert SyntacticPrimitive.SYN_OBJ in core
        assert SyntacticPrimitive.SYN_COMPL in core

    def test_modification_primitives(self):
        mod = [p for p, b in BANK_ASSIGNMENTS.items() if b == SyntacticBank.MODIFICATION]
        assert SyntacticPrimitive.SYN_ADJ_MOD in mod
        assert SyntacticPrimitive.SYN_ADV_MOD in mod
        assert SyntacticPrimitive.SYN_DET in mod

    def test_tam_primitives(self):
        tam = [p for p, b in BANK_ASSIGNMENTS.items() if b == SyntacticBank.TAM]
        assert SyntacticPrimitive.SYN_TENSE_PAST in tam
        assert SyntacticPrimitive.SYN_ASPECT_PERF in tam
        assert SyntacticPrimitive.SYN_MOOD_INTER in tam


class TestBankAllocations:
    def test_sum_to_one(self):
        total = sum(BANK_ALLOCATIONS.values())
        assert abs(total - 1.0) < 1e-6


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
