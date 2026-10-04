"""The L2 text-profile extractor — deterministic genre-signal aggregation."""

import pytest

from gse.api import GSEEncoder
from gse.discourse import PROFILE_FIELDS, TextProfile, split_sentences, text_profile


@pytest.fixture(scope="module")
def enc():
    return GSEEncoder()


def test_split_sentences():
    assert split_sentences("A cat sat. A dog ran! Did it?") == ["A cat sat.", "A dog ran!", "Did it?"]
    assert split_sentences("   ") == []


def test_profile_shape(enc):
    p = text_profile(enc, "Macbeth murdered the king. Macduff fled.")
    assert isinstance(p, TextProfile)
    assert p.n_sentences == 2
    # every typed operation has an entry in the mix bank
    for op in ("EVENT", "CAUSAL_SOURCE", "IMPLIES", "REL_RESTRICT", "TYPE_ASSERT"):
        assert op in p.operator_mix
    # the flat vector is non-empty and numeric
    v = p.vector()
    assert v and all(isinstance(x, (int, float)) for x in v)
    assert len(PROFILE_FIELDS) > 10


def test_profile_discriminates(enc):
    # Narrative leans on EVENT; a conditional surfaces IMPLIES; the two profiles
    # are not equal — the signal the genre router learns over.
    narrative = text_profile(enc, "Macbeth murdered Duncan. Macduff killed Macbeth.")
    conditional = text_profile(enc, "If a person knows something then the person believes it.")
    assert narrative.operator_mix["EVENT"] > 0
    assert conditional.operator_mix["IMPLIES"] > 0
    assert narrative.vector() != conditional.vector()


def test_empty_text_is_safe(enc):
    p = text_profile(enc, "")
    assert p.n_sentences == 0
    assert p.vector()  # still a fixed-length vector (all zeros / defaults)
