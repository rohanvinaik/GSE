"""Behavioral spec for the keyboard-HDC orthogonal recovery path (gse/nlp/hdc_speller.py
+ its abstain-branch wiring in gse/mcp/spell_server.py).

The defining properties:
  1. it recovers the FAR, length-preserving multi-key-slip residue edit-distance abstains
     on ("ecifentky" -> "evidently") — the case the noisy-channel corrector cannot reach;
  2. it is deterministic and every committed recovery grounds;
  3. it fires ONLY when edit-distance abstains, behind grounding + shape gates, so it never
     touches valid words, learned jargon, acronyms/code, or genuine garbage.

Requires the cached lexicon (python -m gse.curation.build_hdc_speller); skipped if absent."""
import pytest

from gse.nlp.hdc_speller import default_speller, HDC_COMMIT_COS

pytestmark = pytest.mark.skipif(default_speller() is None,
                                reason="HDC speller lexicon cache not built")


# ---- 1. recovers the residue edit-distance can't reach --------------------------
def test_recovers_far_multikey_slip():
    # the flagship: a real, recurring, far multi-key slip edit-distance genuinely abstains
    # on (unreachable within edit-2 + confusion table) -> only keyboard-HDC recovers it.
    from gse.nlp.spellcheck import correct
    assert correct("ecifentky").committed is None
    from gse.mcp.spell_server import spell_suggest
    assert spell_suggest("ecifentky")["corrected"] == "evidently"


def test_recovers_in_sentence_context():
    from gse.mcp.spell_server import spell_suggest
    out = spell_suggest("as far as ecifentky the test passed")
    assert "evidently" in out["corrected"] and "ecifentky" not in out["corrected"]


# ---- 2. deterministic + committed recovery grounds ------------------------------
def test_deterministic():
    sp = default_speller()
    runs = {sp.candidates("ecifentky", k=1)[0][0] for _ in range(3)}
    assert len(runs) == 1


def test_committed_recovery_grounds():
    from gse.nlp.spellcheck import _DEFAULT_LEXICON as LX
    sp = default_speller()
    word, cos = sp.candidates("ecifentky", k=1)[0]
    assert cos >= HDC_COMMIT_COS and LX.grounds(word)


# ---- 3. fires ONLY on the abstain residue, behind the gates ---------------------
def test_garbage_abstains():
    # a non-word with no real recovery is left alone (cos below commit / not grounded)
    from gse.mcp.spell_server import spell_suggest
    assert spell_suggest("xqzptv")["corrected"] == "xqzptv"


def test_learned_jargon_never_reaches_hdc():
    # grounding words skip HDC entirely -> numpy/coref (learned) are untouched
    from gse.mcp.spell_server import spell_suggest
    assert spell_suggest("we use numpy and coref here")["corrected"] == \
        "we use numpy and coref here"


def test_acronym_not_hdc_recovered():
    # shape gate blocks HDC on acronyms/code, even though edit-distance abstains
    from gse.mcp.spell_server import _hdc_recover
    assert _hdc_recover("GSE") is None
    assert _hdc_recover("XQZT") is None


def test_real_word_input_not_touched():
    # a grounding word never enters the abstain branch
    from gse.mcp.spell_server import spell_suggest
    assert spell_suggest("the development cycle")["corrected"] == "the development cycle"


# ---- 4. HDC tiebreak: confirm an ambiguous edit-distance candidate, never jargon --------
def test_tiebreak_confirms_ambiguous_common_candidate():
    # edit-distance is ambiguous on 'aparently' (didn't commit); HDC confirms the single
    # common candidate 'apparently' decisively -> committed.
    from gse.nlp.spellcheck import correct
    assert correct("aparently").committed is None     # edit-distance abstains
    from gse.mcp.spell_server import spell_suggest
    assert spell_suggest("aparently")["corrected"] == "apparently"


def test_tiebreak_leaves_jargon_with_no_common_candidate():
    # ambiguous jargon (candidates all rare/garbage, no common word) -> never committed
    from gse.mcp.spell_server import spell_suggest
    assert spell_suggest("pptx")["corrected"] == "pptx"


def test_tiebreak_only_confirms_existing_candidates():
    # _hdc_tiebreak returns one of the supplied candidates or None — never a new word
    from gse.mcp.spell_server import _hdc_tiebreak
    rec = _hdc_tiebreak("aparently", ["apparently", "apariently"])
    assert rec is None or rec[0] in ("apparently", "apariently")
