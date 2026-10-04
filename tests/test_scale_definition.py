"""
Tests for ScaleDefinition Genesis Atom and multi-scale consistency.

Verifies:
1. ScaleDefinition produces correct registries, enums, and lookups
2. Backward-compat exports match ScaleDefinition instances
3. Sentence-scale exact within-bank orthogonality (cos=0.0)
4. All four scales have correct primitive counts and bank structure
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.primitives_v2 import (
    DIMS_PER_BANK,
    N_BANKS,
    PARAGRAPH_PRIMITIVE_REGISTRY,
    PARAGRAPH_PRIMITIVES,
    # Paragraph-scale
    PARAGRAPH_SCALE,
    SENTENCE_PRIMITIVE_REGISTRY,
    SENTENCE_PRIMITIVES,
    # Sentence-scale
    SENTENCE_SCALE,
    TEXT_BANK_NAMES,
    TEXT_PRIMITIVE_REGISTRY,
    TEXT_PRIMITIVES,
    # Text-scale
    TEXT_SCALE,
    D,
    ParagraphBank,
    # Word-scale backward-compat
    SentenceBank,
    TextBank,
    get_compositional_metadata,
    get_paragraph_primitive_info,
    get_sentence_bank_primitives,
    get_sentence_primitive_info,
    get_text_bank_primitives,
    get_text_primitive_info,
    is_compositional_operator,
)
from gse.scale_definition import BankDef, PrimitiveInfo, ScaleDefinition
from gse.vectors_v2 import SentenceScaleBasis

# =============================================================================
# SCALE DEFINITION CORE
# =============================================================================


class TestScaleDefinitionCore:
    """Test ScaleDefinition building blocks."""

    def test_bankdef_frozen(self):
        b = BankDef("TEST", ["A", "B"])
        with pytest.raises(AttributeError):
            b.name = "CHANGED"

    def test_primitive_info_frozen(self):
        p = PrimitiveInfo(name="X", bank_index=0, bank_name="TEST", scale="word")
        with pytest.raises(AttributeError):
            p.name = "Y"

    def test_minimal_scale(self):
        scale = ScaleDefinition(
            name="test",
            banks=[BankDef("BANK_A", ["P1", "P2"]), BankDef("BANK_B", ["P3"])],
        )
        assert len(scale.primitive_registry) == 3
        assert len(scale.banks) == 2
        assert scale.bank_names == {0: "BANK_A", 1: "BANK_B"}

    def test_bank_enum_generated(self):
        scale = ScaleDefinition(
            name="demo",
            banks=[BankDef("ALPHA", ["X"]), BankDef("BETA", ["Y"])],
        )
        assert scale.bank_enum["ALPHA"] == 0
        assert scale.bank_enum["BETA"] == 1

    def test_get_primitive_info_returns_correct_bank(self):
        scale = ScaleDefinition(
            name="demo",
            banks=[BankDef("FIRST", ["A"]), BankDef("SECOND", ["B", "C"])],
        )
        info = scale.get_primitive_info("B")
        assert info is not None
        assert info.bank_index == 1
        assert info.bank_name == "SECOND"
        assert info.scale == "demo"

    def test_get_primitive_info_missing(self):
        scale = ScaleDefinition(name="demo", banks=[BankDef("X", ["A"])])
        assert scale.get_primitive_info("NONEXISTENT") is None

    def test_get_bank_primitives(self):
        scale = ScaleDefinition(
            name="demo",
            banks=[BankDef("A", ["P1", "P2"]), BankDef("B", ["P3"])],
        )
        assert set(scale.get_bank_primitives(0)) == {"P1", "P2"}
        assert scale.get_bank_primitives(1) == ["P3"]

    def test_empty_bank_allowed(self):
        scale = ScaleDefinition(
            name="demo",
            banks=[BankDef("FILLED", ["X"]), BankDef("EMPTY", [])],
        )
        assert scale.get_bank_primitives(1) == []
        assert len(scale.primitive_registry) == 1

    def test_count_primitives(self):
        scale = ScaleDefinition(
            name="demo",
            banks=[BankDef("A", ["P1", "P2"]), BankDef("B", ["P3"])],
        )
        counts = scale.count_primitives()
        assert counts["total"] == 3
        assert counts["bank_0_a"] == 2
        assert counts["bank_1_b"] == 1

    def test_all_primitive_names_order(self):
        scale = ScaleDefinition(
            name="demo",
            banks=[BankDef("A", ["P1", "P2"]), BankDef("B", ["P3"])],
        )
        assert scale.all_primitive_names == ["P1", "P2", "P3"]

    def test_metadata_passed_through(self):
        scale = ScaleDefinition(
            name="demo",
            banks=[BankDef("OPS", ["OP1"], metadata={"OP1": {"arity": 2}})],
        )
        info = scale.get_primitive_info("OP1")
        assert info.metadata == {"arity": 2}

    def test_repr(self):
        scale = ScaleDefinition(name="test", banks=[BankDef("A", ["X", "Y"])])
        r = repr(scale)
        assert "test" in r
        assert "primitives=2" in r


# =============================================================================
# TEXT SCALE
# =============================================================================


class TestTextScale:
    """Verify TEXT_SCALE structure and backward-compat exports."""

    def test_primitive_count(self):
        assert len(TEXT_PRIMITIVES) == 12

    def test_bank_count(self):
        assert len(TEXT_SCALE.banks) == 8

    def test_filled_banks(self):
        assert len(TEXT_SCALE.get_bank_primitives(0)) == 4  # GENRE
        assert len(TEXT_SCALE.get_bank_primitives(1)) == 4  # REGISTER
        assert len(TEXT_SCALE.get_bank_primitives(2)) == 4  # DOMAIN

    def test_empty_banks(self):
        for i in range(3, 8):
            assert len(TEXT_SCALE.get_bank_primitives(i)) == 0

    def test_bank_enum_export(self):
        assert TextBank["GENRE"] == 0
        assert TextBank["REGISTER"] == 1
        assert TextBank["DOMAIN"] == 2

    def test_bank_names_export(self):
        assert TEXT_BANK_NAMES[0] == "GENRE"
        assert TEXT_BANK_NAMES[1] == "REGISTER"

    def test_registry_matches_scale(self):
        assert TEXT_PRIMITIVE_REGISTRY is TEXT_SCALE.primitive_registry

    def test_lookup_function(self):
        info = get_text_primitive_info("NARRATIVE")
        assert info is not None
        assert info.bank_name == "GENRE"

    def test_bank_primitives_function(self):
        prims = get_text_bank_primitives(0)
        assert "NARRATIVE" in prims

    def test_hub_primitives(self):
        assert "NARRATIVE" in TEXT_SCALE.hub_primitives
        assert "FORMAL" in TEXT_SCALE.hub_primitives
        assert "ACADEMIC" in TEXT_SCALE.hub_primitives

    def test_families(self):
        assert "genre" in TEXT_SCALE.families
        assert TEXT_SCALE.families["genre"]["hub"] == "NARRATIVE"


# =============================================================================
# PARAGRAPH SCALE
# =============================================================================


class TestParagraphScale:
    """Verify PARAGRAPH_SCALE structure and backward-compat exports."""

    def test_primitive_count(self):
        assert len(PARAGRAPH_PRIMITIVES) == 15

    def test_bank_count(self):
        assert len(PARAGRAPH_SCALE.banks) == 8

    def test_filled_banks(self):
        assert len(PARAGRAPH_SCALE.get_bank_primitives(0)) == 4  # RHETORICAL
        assert len(PARAGRAPH_SCALE.get_bank_primitives(1)) == 2  # CAUSAL
        assert len(PARAGRAPH_SCALE.get_bank_primitives(2)) == 2  # EXEMPLIFICATION
        assert len(PARAGRAPH_SCALE.get_bank_primitives(3)) == 4  # FLOW
        assert len(PARAGRAPH_SCALE.get_bank_primitives(4)) == 3  # INTENTIONAL

    def test_empty_banks(self):
        for i in range(5, 8):
            assert len(PARAGRAPH_SCALE.get_bank_primitives(i)) == 0

    def test_bank_enum_export(self):
        assert ParagraphBank["RHETORICAL"] == 0
        assert ParagraphBank["CAUSAL"] == 1

    def test_registry_matches_scale(self):
        assert PARAGRAPH_PRIMITIVE_REGISTRY is PARAGRAPH_SCALE.primitive_registry

    def test_lookup_function(self):
        info = get_paragraph_primitive_info("ELABORATION")
        assert info is not None
        assert info.bank_name == "RHETORICAL"

    def test_hub_primitives(self):
        assert "ELABORATION" in PARAGRAPH_SCALE.hub_primitives
        assert "CAUSE" in PARAGRAPH_SCALE.hub_primitives


# =============================================================================
# SENTENCE SCALE
# =============================================================================


class TestSentenceScale:
    """Verify SENTENCE_SCALE structure and backward-compat exports."""

    def test_primitive_count(self):
        assert len(SENTENCE_PRIMITIVES) == 24

    def test_bank_count(self):
        assert len(SENTENCE_SCALE.banks) == 8

    def test_core_structure_bank(self):
        prims = get_sentence_bank_primitives(0)
        assert set(prims) == {"SYN_SUBJ", "SYN_PRED", "SYN_OBJ", "SYN_COMPL"}

    def test_tam_bank(self):
        prims = get_sentence_bank_primitives(2)
        assert "SYN_TENSE_PAST" in prims
        assert "SYN_ASPECT_PERF" in prims
        assert len(prims) == 7

    def test_reserved_bank_empty(self):
        assert len(SENTENCE_SCALE.get_bank_primitives(7)) == 0

    def test_bank_enum_export(self):
        assert SentenceBank["CORE_STRUCTURE"] == 0
        assert SentenceBank["TAM"] == 2
        assert SentenceBank["DISCOURSE"] == 6

    def test_sentence_primitive_registry_enriched(self):
        info = get_sentence_primitive_info("COMP_THAN")
        assert info is not None
        assert info.is_compositional is True
        assert info.comp_arity == 2
        assert info.comp_operation == "SET_DIFF"

    def test_non_compositional_primitive(self):
        info = get_sentence_primitive_info("SYN_SUBJ")
        assert info is not None
        assert info.is_compositional is False
        assert info.comp_arity == 0

    def test_is_compositional_operator(self):
        assert is_compositional_operator("COMP_THAN") is True
        assert is_compositional_operator("COMP_BECAUSE") is True
        assert is_compositional_operator("SYN_SUBJ") is False
        assert is_compositional_operator("NONEXISTENT") is False

    def test_get_compositional_metadata(self):
        meta = get_compositional_metadata("COMP_BECAUSE")
        assert meta == (2, "CAUSAL_SOURCE")

        assert get_compositional_metadata("SYN_SUBJ") is None

    def test_all_comp_operators_have_metadata(self):
        for name, info in SENTENCE_PRIMITIVE_REGISTRY.items():
            if info.is_compositional:
                assert info.comp_arity > 0, f"{name} missing arity"
                assert info.comp_operation is not None, f"{name} missing operation"


# =============================================================================
# SENTENCE-SCALE EXACT ORTHOGONALITY
# =============================================================================


class TestSentenceOrthogonality:
    """Verify sentence-scale uses partition-based Hadamard for exact orthogonality."""

    @pytest.fixture(scope="class")
    def sentence_basis(self):
        return SentenceScaleBasis().generate()

    def test_within_bank_exact_orthogonality(self, sentence_basis):
        for bank in range(N_BANKS):
            bank_prims = [
                (name, vec)
                for name, vec in sentence_basis.primitives.items()
                if SENTENCE_PRIMITIVE_REGISTRY[name].bank == bank
            ]
            for i, (name_i, vec_i) in enumerate(bank_prims):
                for name_j, vec_j in bank_prims[i + 1 :]:
                    cos = vec_i.cosine(vec_j)
                    assert cos == 0.0, f"Sentence bank {bank}: {name_i}/{name_j} cosine = {cos}, expected exact 0.0"

    def test_all_sentence_primitives_generated(self, sentence_basis):
        for name in SENTENCE_PRIMITIVES:
            assert name in sentence_basis.primitives, f"Missing sentence primitive: {name}"

    def test_sentence_vectors_correct_dimension(self, sentence_basis):
        for name, vec in sentence_basis.primitives.items():
            assert vec.dimension == D

    def test_sentence_vectors_confined_to_bank(self, sentence_basis):
        for name, vec in sentence_basis.primitives.items():
            info = SENTENCE_PRIMITIVE_REGISTRY[name]
            bank = info.bank
            start = bank * DIMS_PER_BANK
            end = start + DIMS_PER_BANK
            for idx in vec.positive_indices:
                assert start <= idx < end, f"{name} pos idx {idx} outside bank {bank}"
            for idx in vec.negative_indices:
                assert start <= idx < end, f"{name} neg idx {idx} outside bank {bank}"

    def test_cross_bank_exact_zero(self, sentence_basis):
        bank_samples = {}
        for name, vec in sentence_basis.primitives.items():
            bank = SENTENCE_PRIMITIVE_REGISTRY[name].bank
            if bank not in bank_samples:
                bank_samples[bank] = (name, vec)

        banks = sorted(bank_samples.keys())
        for i, b1 in enumerate(banks):
            for b2 in banks[i + 1 :]:
                name1, vec1 = bank_samples[b1]
                name2, vec2 = bank_samples[b2]
                cos = vec1.cosine(vec2)
                assert cos == 0.0, (
                    f"Cross-bank {name1}(bank {b1})/{name2}(bank {b2}) cosine = {cos}, expected exact 0.0"
                )


# =============================================================================
# CROSS-SCALE CONSISTENCY
# =============================================================================


class TestCrossScaleConsistency:
    """Verify all four scales share structural invariants."""

    @pytest.mark.parametrize(
        "scale,expected_banks",
        [
            (TEXT_SCALE, 8),
            (PARAGRAPH_SCALE, 8),
            (SENTENCE_SCALE, 8),
        ],
    )
    def test_all_scales_have_8_banks(self, scale, expected_banks):
        assert len(scale.banks) == expected_banks

    @pytest.mark.parametrize(
        "scale,expected_dim",
        [
            (TEXT_SCALE, D),
            (PARAGRAPH_SCALE, D),
            (SENTENCE_SCALE, D),
        ],
    )
    def test_all_scales_share_dimension(self, scale, expected_dim):
        assert scale.dimension == expected_dim

    @pytest.mark.parametrize(
        "scale,expected_count",
        [
            (TEXT_SCALE, 12),
            (PARAGRAPH_SCALE, 15),
            (SENTENCE_SCALE, 24),
        ],
    )
    def test_primitive_counts(self, scale, expected_count):
        assert len(scale.get_all_primitives()) == expected_count

    def test_no_primitive_name_collisions_across_scales(self):
        text_prims = set(TEXT_SCALE.get_all_primitives())
        para_prims = set(PARAGRAPH_SCALE.get_all_primitives())
        sent_prims = set(SENTENCE_SCALE.get_all_primitives())

        assert text_prims.isdisjoint(para_prims), f"Text/paragraph overlap: {text_prims & para_prims}"
        assert text_prims.isdisjoint(sent_prims), f"Text/sentence overlap: {text_prims & sent_prims}"
        assert para_prims.isdisjoint(sent_prims), f"Paragraph/sentence overlap: {para_prims & sent_prims}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
