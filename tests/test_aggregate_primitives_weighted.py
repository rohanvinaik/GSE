"""Integration tests for ExternalSourcesIntegrator.aggregate_primitives_weighted.

These mock the parser layer so the tests don't need to load real external
sources (which costs 30-60 seconds).
"""

from unittest.mock import MagicMock

import pytest

from gse.curation.external_sources.integrator import ExternalSourcesIntegrator


def _parser_returning(prim_dict, per_vote_conf=None):
    """A fake parser exposing both classic and confidence-aware methods.

    The integrator's weighted path now uses ``to_primitives_with_confidence``.
    Default per-vote confidence is 1.0 so source priors govern (matching
    the production fallback for parsers that don't override the method).
    """
    p = MagicMock()
    p.to_primitives = MagicMock(return_value=prim_dict)
    confidences = per_vote_conf or {k: 1.0 for k in prim_dict}
    p.to_primitives_with_confidence = MagicMock(return_value={k: (v, confidences[k]) for k, v in prim_dict.items()})
    return p


@pytest.fixture
def integrator():
    inst = ExternalSourcesIntegrator(None)
    inst._loaded = True  # skip real source loading
    yield inst


class TestVotingPath:
    def test_single_source_single_primitive(self, integrator):
        # Use a non-Tier-0 lemma so the aggregation path runs.
        # "happy" decomposes via the GOOD axis but isn't itself a primitive label.
        integrator.parsers = {"src_a": _parser_returning({"GOOD": 1})}
        data = integrator.aggregate_primitives_weighted("happy")
        assert data.primitives == {"GOOD": 1}
        assert data.sources == ["src_a"]
        assert data.suppressions == []

    def test_three_sources_agreeing(self, integrator):
        integrator.parsers = {
            "src_a": _parser_returning({"GOOD": 1}),
            "src_b": _parser_returning({"GOOD": 1}),
            "src_c": _parser_returning({"GOOD": 1}),
        }
        data = integrator.aggregate_primitives_weighted("happy")
        assert data.primitives == {"GOOD": 1}
        # Three contributing sources → all in the sources list
        assert set(data.sources) == {"src_a", "src_b", "src_c"}
        # Confidence boosted by cross-source agreement
        assert data.confidence_scores["GOOD"] > 0.9

    def test_per_source_prior_overrides_default(self, integrator):
        integrator.parsers = {
            "trusted": _parser_returning({"GOOD": 1}),
            "untrusted": _parser_returning({"GOOD": -1}),
        }
        priors = {"trusted": 0.9, "untrusted": 0.1}
        data = integrator.aggregate_primitives_weighted("x", source_confidence=priors)
        # Trusted (0.9) beats untrusted (0.1) → +1 wins on confidence
        assert data.primitives == {"GOOD": 1}
        # Both sources are recorded in provenance — provenance captures
        # who voted, not just who won. The audit trail needs to know that
        # 'untrusted' disagreed.
        assert set(data.sources) == {"trusted", "untrusted"}


class TestBipolarExclusionPath:
    def test_both_poles_voted_active_one_suppressed(self, integrator):
        integrator.parsers = {
            "src_a": _parser_returning({"GOOD": 1}),
            "src_b": _parser_returning({"BAD": 1}),  # contradicts: both poles active
        }
        data = integrator.aggregate_primitives_weighted("contested")
        # Both have default conf 1.0 → tie → positive (GOOD) wins
        assert data.primitives == {"GOOD": 1}
        assert "BAD" not in data.primitives
        assert len(data.suppressions) == 1
        s = data.suppressions[0]
        assert s["kept"] == "GOOD"
        assert s["dropped"] == "BAD"

    def test_no_suppression_when_only_one_pole_active(self, integrator):
        # Non-Tier-0 lemma so aggregation runs
        integrator.parsers = {
            "src_a": _parser_returning({"GOOD": 1, "FEEL": 1}),
            "src_b": _parser_returning({"GOOD": 1}),
        }
        data = integrator.aggregate_primitives_weighted("happy")
        assert data.primitives == {"GOOD": 1, "FEEL": 1}
        assert data.suppressions == []

    def test_the_near_anomaly_resolution(self, integrator):
        # The exact pattern that produced SPATIAL cos=+0.365 in the
        # investigation: a parser voting both NEAR and AWAY on a word.
        # After enforcement, AWAY drops. Tested via a non-Tier-0 lemma
        # since "near" itself is now Tier 0.
        integrator.parsers = {
            "old_llm": _parser_returning({"NEAR": 1, "AWAY": 1, "TOWARD": 1, "WITH": 1, "WITHOUT": 1}),
            "validator": _parser_returning({"NEAR": 1, "TOWARD": 1, "WITH": 1}),
        }
        data = integrator.aggregate_primitives_weighted("nearby")
        # Validator only voted NEAR/TOWARD/WITH — those should survive
        # without competition from their opposites. The old_llm's
        # contradictory AWAY/WITHOUT lose because NEAR/TOWARD/WITH have
        # 2 votes while AWAY/WITHOUT have only 1.
        assert "NEAR" in data.primitives
        assert "AWAY" not in data.primitives
        assert "WITH" in data.primitives
        assert "WITHOUT" not in data.primitives


class TestEmptyInput:
    def test_no_sources_returns_empty(self, integrator):
        integrator.parsers = {}
        data = integrator.aggregate_primitives_weighted("nothing")
        assert data.primitives == {}
        assert data.sources == []

    def test_sources_with_no_match_returns_empty(self, integrator):
        integrator.parsers = {
            "src_a": _parser_returning({}),
            "src_b": _parser_returning({}),
        }
        data = integrator.aggregate_primitives_weighted("nothing")
        assert data.primitives == {}
        assert data.sources == []


class TestBackwardsCompat:
    def test_aggregate_primitives_unchanged_for_classic_callers(self, integrator):
        # The pre-existing aggregate_primitives still works and ignores
        # the new weighted/exclusion path
        integrator.parsers = {"src_a": _parser_returning({"GOOD": 1, "BAD": 1})}
        data = integrator.aggregate_primitives("contested")
        # Classic path doesn't enforce exclusion — both stay
        assert data.primitives.get("GOOD") == 1
        assert data.primitives.get("BAD") == 1
        # suppressions field exists but is empty in classic path
        assert data.suppressions == []


class TestTier0ShortCircuit:
    def test_canonical_bipolar_label_uses_tier_0(self, integrator):
        # No matter what sources say, "good" gets the definitional decomp
        integrator.parsers = {
            "noisy_source": _parser_returning({"BIG": -1, "SMALL": 1, "BAD": 1}),
        }
        data = integrator.aggregate_primitives_weighted("good")
        assert data.primitives == {"GOOD": 1}
        assert data.sources == ["tier_0_definitional"]

    def test_tier_0_skips_aggregation_entirely(self, integrator):
        # Sources whose to_primitives would error out don't get called
        # for Tier 0 words — the dispatch short-circuits first
        integrator.parsers = {}  # no parsers at all
        data = integrator.aggregate_primitives_weighted("near")
        # No parsers → if Tier 0 weren't short-circuiting, we'd get an
        # empty result. Tier 0 returns the canonical decomposition anyway.
        assert data.primitives == {"NEAR": 1}

    def test_non_tier_0_lemma_falls_through(self, integrator):
        # "happy" is not a primitive label → aggregation runs as before
        integrator.parsers = {"src_a": _parser_returning({"GOOD": 1, "FEEL": 1})}
        data = integrator.aggregate_primitives_weighted("happy")
        assert data.sources == ["src_a"]  # not 'tier_0_definitional'
