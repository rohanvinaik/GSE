"""Contraction resolution — the spell-check pipeline's first validation case."""

import pytest

from gse.nlp.contractions import (
    POSSESSIVE,
    candidates,
    resolve_apostrophe_s,
    resolve_contraction,
)
from gse.nlp.native import NativeNLP


@pytest.fixture(scope="module")
def nlp():
    return NativeNLP()


def _following(nlp, sentence, frag):
    toks = list(nlp(sentence))
    for i, t in enumerate(toks):
        if t.text.lower() == frag:
            return toks[i + 1] if i + 1 < len(toks) else None
    return None


def test_error_model_candidates():
    assert candidates("'d") == ["would", "had"]
    assert candidates("'s") == ["is", "has"]
    assert candidates("n't") == ["not"]
    assert candidates("xyz") == []


def test_unambiguous_resolve():
    assert resolve_contraction("n't", None) == "not"
    assert resolve_contraction("'ve", None) == "have"
    assert resolve_contraction("'re", None) == "are"
    # ambiguous with no context → the default expansion
    assert resolve_contraction("'d", None) == "would"


@pytest.mark.parametrize("sentence,frag,truth", [
    ("She'd gone home.", "'d", "had"),      # 'd + past-participle → perfect
    ("She'd go home.", "'d", "would"),      # 'd + base → modal
    ("They'd left early.", "'d", "had"),
    ("It's gone.", "'s", "has"),            # 's + participle → perfect
    ("It's mine.", "'s", "is"),             # 's + nominal → copula
    ("He's eaten.", "'s", "has"),
])
def test_context_disambiguation(nlp, sentence, frag, truth):
    # the FOLLOWING token's inflection (GSE's own lemmatization) is the signal.
    assert resolve_contraction(frag, _following(nlp, sentence, frag)) == truth


# --- the integrated three-way 's voice-mode (is / has / possessive) -------------

@pytest.mark.parametrize("sentence,verb_after,truth", [
    ("The fire's too big.", False, "is"),                 # copula: nothing else predicates
    ("It's a sublease.", False, "is"),
    ("The fire's gone.", True, "has"),                    # following participle → perfect
    ("White's suggestion flattered.", True, POSSESSIVE),  # a verb follows → possessive
    ("Brenner's voice was oily.", True, POSSESSIVE),      # copula 'was' follows → possessive
])
def test_apostrophe_s_three_way(nlp, sentence, verb_after, truth):
    assert resolve_apostrophe_s(_following(nlp, sentence, "'s"), verb_after) == truth


def test_apostrophe_s_front_end_retag(nlp):
    """The front-end re-tags a verbal 's to its copula/perfect verb; possessive 's
    stays a PART (so the working possessive path handles it)."""
    def s_tok(sentence):
        return next(t for t in nlp(sentence) if t.text == "'s")
    assert s_tok("The fire's too big.").lemma_ == "be"            # copula
    assert s_tok("The fire's gone.").lemma_ == "have"             # perfect
    assert s_tok("White's suggestion flattered.").pos_ == "PART"  # possessive — untouched
