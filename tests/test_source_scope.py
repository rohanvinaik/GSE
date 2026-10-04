"""Tests for per-source primitive scope restriction."""

from gse.curation.external_sources.source_scope import (
    SOURCE_PRIMITIVE_SCOPE,
    WORD_SCALE_EXCLUDED_PRIMITIVES,
    filter_votes_by_scope,
    in_scope,
)
from gse.primitives_v2 import SENTENCE_SCALE


class TestWordScaleBoundary:
    def test_sentence_scale_primitives_excluded(self):
        # All 24 SYN_* / COMP_* primitives are blocked
        for name in SENTENCE_SCALE.primitive_registry:
            assert name in WORD_SCALE_EXCLUDED_PRIMITIVES, (
                f"{name} is sentence-scale but not in WORD_SCALE_EXCLUDED_PRIMITIVES"
            )

    def test_hierarchy_ops_excluded(self):
        # 5 hierarchy ops: HIER_PLUS, HIER_MINUS, INTENSITY, CERTAINTY, QUANTITY
        for name in ("HIER_PLUS", "HIER_MINUS", "INTENSITY", "CERTAINTY", "QUANTITY"):
            assert name in WORD_SCALE_EXCLUDED_PRIMITIVES

    def test_normal_primitives_not_excluded(self):
        # Word-scale semantic primitives stay allowed
        for name in ("GOOD", "BAD", "BIG", "SMALL", "FEEL", "THINK", "MOVE", "BODY"):
            assert name not in WORD_SCALE_EXCLUDED_PRIMITIVES

    def test_unrestricted_source_still_blocked_from_excluded(self):
        # Wiktionary v2 is unrestricted by per-source scope, but the word-
        # scale boundary still applies.
        votes = {
            "GOOD": (1, 0.9),
            "INTENSITY": (1, 0.7),  # hierarchy base — blocked
            "SYN_TENSE_PAST": (1, 0.5),  # sentence-scale — blocked
        }
        out = filter_votes_by_scope("wiktionary_v2", votes)
        assert out == {"GOOD": (1, 0.9)}

    def test_scoped_source_also_blocked_from_excluded(self):
        # The boundary applies BEFORE per-source scope
        votes = {
            "GOOD": (1, 0.9),  # in nrc_vad scope
            "INTENSITY": (1, 0.8),  # would pass scope (it's not), but blocked by boundary
        }
        out = filter_votes_by_scope("nrc_vad", votes)
        assert "INTENSITY" not in out


class TestFilterVotesByScope:
    def test_unscoped_source_passes_through(self):
        # wiktionary_v2 not in scope map → unrestricted (within the word-scale
        # boundary). Use only primitives that are NOT in WORD_SCALE_EXCLUDED.
        votes = {"GOOD": (1, 0.9), "MUST": (-1, 0.5), "BODY": (1, 0.7)}
        out = filter_votes_by_scope("wiktionary_v2", votes)
        assert out == votes

    def test_scoped_source_drops_out_of_domain(self):
        # nrc_vad: scope = {GOOD, BAD, FEEL, WANT}
        # The pre-fix bug: arousal → INTENSITY, dominance → MUST. Even if
        # those somehow re-appear, scope catches them.
        votes = {"GOOD": (1, 0.9), "INTENSITY": (1, 0.7), "MUST": (1, 0.6)}
        out = filter_votes_by_scope("nrc_vad", votes)
        assert out == {"GOOD": (1, 0.9)}

    def test_scoped_source_keeps_in_domain(self):
        votes = {"GOOD": (1, 0.9), "BAD": (-1, 0.8), "FEEL": (1, 0.6)}
        out = filter_votes_by_scope("nrc_vad", votes)
        assert out == votes

    def test_empty_votes_returns_empty(self):
        assert filter_votes_by_scope("nrc_vad", {}) == {}

    def test_explicit_scope_override(self):
        # Caller-supplied scope wins over the default map
        votes = {"GOOD": (1, 0.9), "WHATEVER": (1, 0.5)}
        out = filter_votes_by_scope("nrc_vad", votes, scope={"nrc_vad": {"WHATEVER"}})
        assert out == {"WHATEVER": (1, 0.5)}


class TestInScope:
    def test_unscoped_source_returns_true_for_anything(self):
        assert in_scope("wiktionary_v2", "INTENSITY")
        assert in_scope("wiktionary_v2", "BAD")

    def test_scoped_source_blocks_out_of_domain(self):
        assert not in_scope("nrc_vad", "INTENSITY")
        assert not in_scope("nrc_vad", "MUST")

    def test_scoped_source_allows_in_domain(self):
        assert in_scope("nrc_vad", "GOOD")
        assert in_scope("nrc_vad", "FEEL")


class TestEmpiricalScopeMap:
    def test_nrc_vad_excludes_logical_bank_primitives(self):
        for prim in ("INTENSITY", "MUST", "CAN", "MAYBE", "NOT", "CAUSE"):
            assert prim not in SOURCE_PRIMITIVE_SCOPE["nrc_vad"]

    def test_sentiwordnet_is_eval_only(self):
        assert SOURCE_PRIMITIVE_SCOPE["sentiwordnet"] == {"GOOD", "BAD"}

    def test_lancaster_covers_sensory_motor(self):
        scope = SOURCE_PRIMITIVE_SCOPE["lancaster_sensorimotor"]
        assert "SEE" in scope and "HEAR" in scope and "TOUCH" in scope
        assert "BODY" in scope and "MOVE" in scope

    def test_wiktionary_v2_unrestricted(self):
        # Empirically broad-coverage; deliberately omitted from the map
        assert "wiktionary_v2" not in SOURCE_PRIMITIVE_SCOPE
