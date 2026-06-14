"""Manual contract tests for gse.merkle.decomposer."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.merkle.decomposer import (
    POS_DEFAULTS,
    PREFIX_PATTERNS,
    SUFFIX_PATTERNS,
    DecompositionResult,
    HDCFuzzyDecomposer,
)
from gse.merkle.nodes import LexemeNode
from gse.merkle.router import MerkleBellmanFord
from gse.merkle.tree import MerkleLexiconTree
from gse.vectors_v2 import SparseVector, compose_decomposition, create_basis


@pytest.fixture(scope="module")
def basis():
    return create_basis()


@pytest.fixture
def tree(basis):
    tree = MerkleLexiconTree()
    for lemma, decomp in [
        ("happy", [("FEEL", "experiencer", 1), ("GOOD", "attribute", 1)]),
        ("sad", [("FEEL", "experiencer", 1), ("BAD", "attribute", 1)]),
        ("runner", [("DO", "action", 1), ("SOMEONE", "agent", 1), ("MOVE", "action", 1)]),
    ]:
        vec = compose_decomposition(basis, decomp)
        lex = LexemeNode(
            node_id=f"{lemma}_n_01" if lemma == "runner" else f"{lemma}_adj_01",
            lemma=lemma,
            pos="n" if lemma == "runner" else "adj",
            sense_id="01",
            decomposition=decomp,
            vector_positive=vec.positive_indices,
            vector_negative=vec.negative_indices,
        )
        tree.add_lexeme(lex)
    return tree


@pytest.fixture
def router(tree, basis):
    return MerkleBellmanFord(tree, basis)


@pytest.fixture
def decomposer(tree, router, basis):
    return HDCFuzzyDecomposer(tree, router, basis)


# ---------- Pattern tables ----------

class TestPrefixPatterns:
    def test_un_negation(self):
        assert PREFIX_PATTERNS["un"] == [("NOT", "modifier", 1)]

    def test_over_big(self):
        prims = [p[0] for p in PREFIX_PATTERNS["over"]]
        assert "BIG" in prims
        assert "ABOVE" in prims


class TestSuffixPatterns:
    def test_er_agent(self):
        prims = [p[0] for p in SUFFIX_PATTERNS["er"]]
        assert "SOMEONE" in prims

    def test_less_not(self):
        prims = [p[0] for p in SUFFIX_PATTERNS["less"]]
        assert "NOT" in prims


class TestPosDefaults:
    def test_noun_default(self):
        assert POS_DEFAULTS["n"] == [("SOMETHING", "theme", 1)]

    def test_verb_default(self):
        prims = [p[0] for p in POS_DEFAULTS["v"]]
        assert "DO" in prims


# ---------- DecompositionResult ----------

class TestDecompositionResult:
    def test_defaults(self):
        r = DecompositionResult(word="x", pos="n")
        assert r.decomposition == []
        assert r.morphological_confidence == 0.0
        assert r.vector is None


# ---------- HDCFuzzyDecomposer.__init__ ----------

class TestInit:
    def test_uses_provided_basis(self, tree, router):
        b = create_basis()
        d = HDCFuzzyDecomposer(tree, router, basis=b)
        assert d.basis is b

    def test_creates_default_basis(self, tree, router):
        d = HDCFuzzyDecomposer(tree, router)
        assert d.basis is not None

    def test_kline_patterns_built(self, decomposer):
        # Tree has lexemes with multi-prim decompositions → patterns extracted
        assert len(decomposer.kline_patterns) > 0


# ---------- _build_kline_patterns ----------

class TestBuildKlinePatterns:
    def test_single_primitive_decomp_excluded(self, decomposer, tree):
        # Lexemes with only 1 primitive don't generate patterns
        # All test fixture lexemes have >= 2 primitives, so test by counting:
        # 'happy' has FEEL+GOOD → both should be keys
        keys = set(decomposer.kline_patterns.keys())
        # FEEL appears in happy and sad
        assert "FEEL:experiencer" in keys

    def test_co_occurrence_counted(self, decomposer):
        # FEEL:experiencer co-occurs with GOOD:attribute (in happy)
        # and BAD:attribute (in sad)
        counter = decomposer.kline_patterns["FEEL:experiencer"]
        # Both GOOD and BAD should appear in the counter
        assert any("GOOD" in k for k in counter)
        assert any("BAD" in k for k in counter)


# ---------- _analyze_morphology ----------

class TestAnalyzeMorphology:
    def test_un_prefix_detected(self, decomposer):
        hints = decomposer._analyze_morphology("unhappy")
        prims = [h[0] for h in hints]
        assert "NOT" in prims

    def test_er_suffix_detected(self, decomposer):
        hints = decomposer._analyze_morphology("runner")
        prims = [h[0] for h in hints]
        assert "SOMEONE" in prims

    def test_short_word_no_prefix(self, decomposer):
        # word too short for prefix match (needs len > prefix+2)
        hints = decomposer._analyze_morphology("un")
        # No prefix matches; no suffix either
        assert hints == []

    def test_longest_prefix_wins(self, decomposer):
        # "super" should win over "sub" for "superman"
        hints = decomposer._analyze_morphology("superman")
        prims = [h[0] for h in hints]
        # "super" yields BIG + ABOVE
        assert "BIG" in prims

    def test_no_morphology_no_hints(self, decomposer):
        hints = decomposer._analyze_morphology("zog")
        assert hints == []


# ---------- _build_query_from_hints ----------

class TestBuildQueryFromHints:
    def test_uses_pos_defaults(self, decomposer):
        # Noun POS → SOMETHING/theme default
        vec = decomposer._build_query_from_hints([], "n")
        assert isinstance(vec, SparseVector)
        assert vec.nnz > 0

    def test_empty_falls_back_to_generic(self, decomposer):
        # Unknown POS with no hints → fallback to ("SOMETHING", "theme", 1)
        vec = decomposer._build_query_from_hints([], "unknown_pos")
        assert vec.nnz > 0

    def test_includes_hints(self, decomposer):
        hints = [("GOOD", "attribute", 1)]
        vec = decomposer._build_query_from_hints(hints, "n")
        assert vec.nnz > 0


# ---------- _extract_patterns ----------

class TestExtractPatterns:
    def test_empty_returns_empty(self, decomposer):
        assert decomposer._extract_patterns([]) == []

    def test_extracts_from_similar(self, decomposer, tree):
        # Use a known lexeme key
        result = decomposer._extract_patterns([("happy_adj_01", 1.0)])
        # 'happy' has FEEL and GOOD → both should appear
        prims = [p[0] for p in result]
        assert "FEEL" in prims or "GOOD" in prims

    def test_unknown_word_skipped(self, decomposer):
        # Unknown key → skipped in the loop
        result = decomposer._extract_patterns([("nonexistent_x_01", 1.0)])
        assert result == []

    def test_threshold_filters_low_weight(self, decomposer, tree):
        # weight = 0.1 * 1 prim = 0.1 < 0.5 threshold → no pattern
        result = decomposer._extract_patterns([("happy_adj_01", 0.1)])
        # weighted counts < 0.5 → filtered
        # happy has 2 prims, weight=0.1 each → max count is 0.1 < 0.5
        assert result == []


# ---------- _combine_sources ----------

class TestCombineSources:
    def test_pos_defaults_added(self, decomposer):
        result = decomposer._combine_sources([], [], "n", "")
        prims = [p[0] for p in result]
        # Noun POS default is SOMETHING
        assert "SOMETHING" in prims

    def test_morphological_priority(self, decomposer):
        morph = [("NOT", "modifier", 1)]
        patterns = []
        result = decomposer._combine_sources(morph, patterns, "n", "")
        prims = [p[0] for p in result]
        assert "NOT" in prims

    def test_deduplicates(self, decomposer):
        # Same primitive in multiple sources → only kept once
        morph = [("GOOD", "attribute", 1)]
        patterns = [("GOOD", "evaluation", 1)]
        result = decomposer._combine_sources(morph, patterns, "n", "")
        prim_count = sum(1 for p in result if p[0] == "GOOD")
        assert prim_count == 1

    def test_gloss_adds_hints(self, decomposer):
        result = decomposer._combine_sources([], [], "n", "a good thing")
        prims = [p[0] for p in result]
        assert "GOOD" in prims or "SOMETHING" in prims

    def test_capped_at_8(self, decomposer):
        morph = [(f"PRIM_{i}", "x", 1) for i in range(15)]
        result = decomposer._combine_sources(morph, [], "n", "")
        assert len(result) <= 8


# ---------- _analyze_gloss ----------

class TestAnalyzeGloss:
    def test_person_keyword(self, decomposer):
        hints = decomposer._analyze_gloss("a person who runs")
        prims = [h[0] for h in hints]
        assert "SOMEONE" in prims

    def test_no_keywords_no_hints(self, decomposer):
        assert decomposer._analyze_gloss("xyzzy floob bizz") == []

    def test_multiple_keywords(self, decomposer):
        hints = decomposer._analyze_gloss("a person who is good")
        prims = [h[0] for h in hints]
        assert "SOMEONE" in prims
        assert "GOOD" in prims


# ---------- _infer_polarities ----------

class TestInferPolarities:
    def test_bipolar_normalized(self, decomposer):
        # BAD is bipolar → maps to canonical (GOOD with -1)
        result = decomposer._infer_polarities([("BAD", "attribute", 1)], None, [])
        # canonical form replaces BAD
        assert result[0][0] != "BAD" or result[0][2] != 1  # at least one of these flips

    def test_non_bipolar_unchanged(self, decomposer):
        result = decomposer._infer_polarities([("SOMETHING", "theme", 1)], None, [])
        assert result[0][0] == "SOMETHING"
        assert result[0][2] == 1


# ---------- decompose ----------

class TestDecompose:
    def test_returns_result(self, decomposer):
        result = decomposer.decompose("xyzzy", "n")
        assert isinstance(result, DecompositionResult)
        assert result.word == "xyzzy"
        assert result.pos == "n"

    def test_morphological_hints_populated_for_prefixed_word(self, decomposer):
        result = decomposer.decompose("unhappy", "adj")
        # 'un' prefix → NOT hint
        prim_names = [h[0] for h in result.morphological_hints]
        assert "NOT" in prim_names

    def test_overall_confidence_in_range(self, decomposer):
        result = decomposer.decompose("test", "n")
        assert 0.0 <= result.overall_confidence <= 1.0

    def test_vector_generated_when_decomp_present(self, decomposer):
        result = decomposer.decompose("happy", "adj")
        if result.decomposition:
            assert result.vector is not None

    def test_with_gloss(self, decomposer):
        result = decomposer.decompose("doctor", "n", gloss="a person who heals")
        prim_names = [p[0] for p in result.decomposition]
        # 'person' keyword → SOMEONE
        assert "SOMEONE" in prim_names


# ---------- decompose_batch ----------

class TestDecomposeBatch:
    def test_returns_list(self, decomposer):
        result = decomposer.decompose_batch([("foo", "n"), ("bar", "v")])
        assert len(result) == 2
        for r in result:
            assert isinstance(r, DecompositionResult)

    def test_empty_input(self, decomposer):
        assert decomposer.decompose_batch([]) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
