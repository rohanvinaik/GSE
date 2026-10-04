"""Tests for the Tier 0 definitional dispatch.

The dispatch must:
- Be exhaustive over PRIMITIVE_REGISTRY (no hand-authored list — it reads the
  system's table of truth).
- Exclude the 5 hierarchy operators that aren't English lemmas.
- Normalize multi-word phrases (long time → LONG_TIME) and pronouns (i → I).
"""

from gse.curation.external_sources.tier_0_dispatch import (
    TIER_0_PRIMITIVES,
    canonical_decomposition,
    is_tier_0,
)
from gse.primitives_v2 import PRIMITIVE_REGISTRY


class TestCanonical:
    def test_good_returns_identity(self):
        assert canonical_decomposition("good") == {"GOOD": 1}

    def test_bad_returns_identity(self):
        assert canonical_decomposition("bad") == {"BAD": 1}

    def test_case_insensitive(self):
        assert canonical_decomposition("GOOD") == canonical_decomposition("good")

    def test_pronoun_i(self):
        assert canonical_decomposition("i") == {"I": 1}

    def test_pronoun_you(self):
        assert canonical_decomposition("you") == {"YOU": 1}

    def test_long_time_phrase_form(self):
        assert canonical_decomposition("long time") == {"LONG_TIME": 1}

    def test_short_time_hyphenated_form(self):
        assert canonical_decomposition("short-time") == {"SHORT_TIME": 1}

    def test_non_primitive_returns_none(self):
        assert canonical_decomposition("happy") is None
        assert canonical_decomposition("dog") is None
        assert canonical_decomposition("blorp") is None


class TestExclusions:
    def test_hier_plus_excluded(self):
        assert canonical_decomposition("hier_plus") is None

    def test_hier_minus_excluded(self):
        assert canonical_decomposition("hier_minus") is None

    def test_intensity_excluded(self):
        # INTENSITY is a hierarchy ANCHOR, not an English lemma
        assert canonical_decomposition("intensity") is None

    def test_certainty_excluded(self):
        assert canonical_decomposition("certainty") is None

    def test_quantity_excluded(self):
        # QUANTITY is the base for the QUANTITY hierarchy
        assert canonical_decomposition("quantity") is None


class TestExhaustiveness:
    def test_tier_0_set_excludes_only_hierarchy_ops(self):
        # Read from the system, don't hand-author
        expected_excluded = {
            name for name, info in PRIMITIVE_REGISTRY.items() if info.is_hierarchy_marker or info.is_hierarchy_base
        }
        actual_excluded = set(PRIMITIVE_REGISTRY) - TIER_0_PRIMITIVES
        assert actual_excluded == expected_excluded

    def test_all_bipolar_primitives_in_tier_0(self):
        # The headline use case: every canonical bipolar word resolves
        # via Tier 0 to its definitional decomposition
        for primitive_name, info in PRIMITIVE_REGISTRY.items():
            if info.is_bipolar:
                assert primitive_name in TIER_0_PRIMITIVES, f"{primitive_name} is bipolar but not in Tier 0"

    def test_count_matches_registry_minus_5_hierarchy_ops(self):
        # 73 primitives total, 5 hierarchy ops excluded → 68 Tier 0 entries
        assert len(TIER_0_PRIMITIVES) == len(PRIMITIVE_REGISTRY) - 5

    def test_is_tier_0_consistent_with_canonical_decomposition(self):
        for name in PRIMITIVE_REGISTRY:
            decomp = canonical_decomposition(name)
            if is_tier_0(name):
                assert decomp == {name: 1}
            else:
                assert decomp is None
