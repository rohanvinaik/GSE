"""Behavioral spec for the deterministic spell-corrector (gse/nlp/spellcheck*.py).

These lock down the four properties that *define* the system — the ones a statistical
or neural checker cannot guarantee:
  1. it corrects genuine typos,
  2. it NEVER alters a word that is already valid,
  3. it abstains (no commit) rather than guess when nothing/too-little is decisive,
  4. it is deterministic and never suggests a non-word,
plus the empirical confusion-table overlay (injection + decisive bias), which must
operate *within* the symbolic frame (every suggestion still grounds)."""
import pytest

from gse.nlp.spellcheck import correct, suggest, propose, _DEFAULT_LEXICON as LX


# ---- 1. corrects genuine everyday typos -----------------------------------------
@pytest.mark.parametrize("typo,gold", [
    ("recieve", "receive"), ("seperate", "separate"), ("goverment", "government"),
    ("beleive", "believe"), ("teh", "the"),
])
def test_corrects_common_typo(typo, gold):
    assert correct(typo).committed == gold


# ---- 2. NEVER alters a word that already grounds ---------------------------------
@pytest.mark.parametrize("word", ["dog", "the", "because", "run", "anser"])
def test_real_word_is_never_corrected(word):
    r = correct(word)
    assert r.fired is False          # trigger never engages on a valid word
    assert r.committed == word.lower()


# ---- 3. abstains rather than guess ----------------------------------------------
def test_no_grounded_candidate_abstains():
    r = correct("xqzptv")
    assert r.fired is True
    assert r.committed is None        # nothing grounds nearby -> honest abstention


def test_suggest_empty_for_real_word():
    assert suggest("dog") == []


# ---- 4. deterministic + never fabricates ----------------------------------------
def test_deterministic():
    for w in ["recieve", "wierd", "maintainance", "teh"]:
        runs = {correct(w).committed for _ in range(3)}
        assert len(runs) == 1


def test_every_suggestion_grounds():
    for w in ["recieve", "wierd", "seperate", "adress", "thier"]:
        for cand in suggest(w, n=8):
            assert LX.grounds(cand.word), f"{cand.word!r} suggested but does not ground"


def test_committed_word_always_grounds():
    for w in ["recieve", "maintainance", "wierd", "goverment"]:
        c = correct(w).committed
        if c is not None:
            assert LX.grounds(c)


# ---- 5. confusion table: injection + decisive bias, still grounding-gated --------
def test_confusion_injects_beyond_edit2():
    # maintainance->maintenance is a 4-edit fix the edit-1/2 generator alone misses;
    # the table injects it AND it must still be a real word.
    r = correct("maintainance")
    assert r.committed == "maintenance"
    seen = [c for c in r.ranked if c.confusion_pos >= 0]
    assert any(c.word == "maintenance" for c in seen)


def test_confusion_tips_ambiguous_to_commit():
    # wierd is one edit from both weird and wired; the observed-correction bias makes
    # weird decisive instead of an abstention — but wired is still surfaced.
    r = correct("wierd")
    assert r.committed == "weird"
    assert "wired" in [c.word for c in r.ranked]


def test_injected_candidate_must_ground():
    # propose only ever returns grounded candidates, table-injected included.
    for c in propose("maintainance"):
        assert LX.grounds(c.word)


# ---- 6. sentence / MCP integration (context layer) ------------------------------
def test_spell_suggest_sentence_corrects_tokens():
    from gse.mcp.spell_server import spell_suggest
    out = spell_suggest("she recieved a seperate goverment notice", n=3)
    assert out["corrected"] == "she received a separate government notice"


def test_spell_suggest_marks_real_word_not_misspelled():
    from gse.mcp.spell_server import spell_suggest
    out = spell_suggest("the dog runs", n=3)
    assert all(t["misspelled"] is False for t in out["tokens"])
    assert out["corrected"] == "the dog runs"
