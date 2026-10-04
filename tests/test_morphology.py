"""The comparative/superlative morphological operation — the first word-scale
morphology slice (``docs/MORPHOLOGY_RESEARCH_BRIEF.md`` Part D).

The morphology ladder: regular → orthographic → suppletive → decline (false strip /
collision). Proves the propose→coherence-resolve operation end to end, and that the
token front-end consumes it (the lemma is the grounded base, never a mangled stem).
"""

import pytest

from gse.nlp.morphology import COMPARATIVE, SUPERLATIVE, resolve_degree
from gse.nlp.native import NativeNLP


@pytest.fixture(scope="module")
def nlp():
    return NativeNLP()


@pytest.mark.parametrize(
    "surface,base,feat",
    [
        # regular (bare concatenation)
        ("taller", "tall", COMPARATIVE),
        ("tallest", "tall", SUPERLATIVE),
        ("smarter", "smart", COMPARATIVE),
        # gemination (doubled consonant)
        ("bigger", "big", COMPARATIVE),
        ("biggest", "big", SUPERLATIVE),
        ("redder", "red", COMPARATIVE),
        # silent-e drop
        ("larger", "large", COMPARATIVE),
        ("nicer", "nice", COMPARATIVE),
        ("finer", "fine", COMPARATIVE),
        # y -> i
        ("earlier", "early", COMPARATIVE),
        ("happier", "happy", COMPARATIVE),
        ("angrier", "angry", COMPARATIVE),
        # suppletive (finite closed list)
        ("better", "good", COMPARATIVE),
        ("best", "good", SUPERLATIVE),
        ("worse", "bad", COMPARATIVE),
        ("worst", "bad", SUPERLATIVE),
    ],
)
def test_degree_resolves_to_grounded_base(surface, base, feat):
    assert resolve_degree(surface) == (base, feat)


@pytest.mark.parametrize(
    "surface",
    [
        "together",
        "whatsoever",
        "latter",  # end in -er, no grounding base (false strip)
        "water",
        "never",
        "however",  # non-morphemic -er
        "teacher",
        "writer",  # agentive derivation (-er collision): a verb
        # base, not a gradable adjective → declines
    ],
)
def test_non_degree_declines(surface):
    assert resolve_degree(surface) is None


def test_token_front_end_consumes_the_operation(nlp):
    """The lemmatizer yields the grounded base — never a mangled stem — and leaves
    real non-degree words intact. (Regular + orthographic comparatives: the L2
    flywheel finding, `larger`→`large` etc.)"""
    cases = [
        ("larger", "large"),
        ("earlier", "early"),
        ("bigger", "big"),
        ("nicer", "nice"),
        ("happier", "happy"),
        ("together", "together"),  # declines → stays a real word (not "togeth")
    ]
    for surface, base in cases:
        tok = list(nlp(surface))[0]
        assert tok.lemma_ == base, f"{surface!r} -> {tok.lemma_!r}, expected {base!r}"


def test_suppletive_degree_in_adjectival_position(nlp):
    """better/best/worse tag ADJ in adjectival position (the POS tagger consults the
    morphology operation as SSOT), so the operation fires → grounded base lemma."""
    assert list(nlp("a better plan"))[1].lemma_ == "good"  # attributive
    assert list(nlp("the best dog"))[1].lemma_ == "good"  # attributive
    assert list(nlp("this is worse"))[2].lemma_ == "bad"  # predicative


def test_suppletive_verb_reading_preserved(nlp):
    """In clearly verbal position the homographic verb wins (the guard) — "best" is
    not forced to the degree reading after a modal."""
    toks = list(nlp("they will best them"))
    assert toks[2].pos_ == "VERB"  # "best"
