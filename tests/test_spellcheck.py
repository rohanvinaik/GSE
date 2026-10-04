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

from gse.nlp.spellcheck import _DEFAULT_LEXICON as LX
from gse.nlp.spellcheck import correct, propose, suggest


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


# ---- 7. shape gate: valid-but-non-dictionary tokens are NEVER mangled ------------
# The defining property is "never changed to a DIFFERENT word" — either abstained
# (committed is None) or recognized as valid and left as-is (committed == the token).
def _not_mangled(token):
    c = correct(token).committed
    return c is None or c == token.lower()


@pytest.mark.parametrize("token", ["GSE", "MCP", "HDC", "JSON"])
def test_acronym_never_mangled(token):
    assert _not_mangled(token)


@pytest.mark.parametrize("token", ["set-theory", "demi-words", "anti-pattern", "re-run"])
def test_hyphenated_compound_never_mangled(token):
    assert _not_mangled(token)


@pytest.mark.parametrize("token", ["don't", "let's", "Mike's"])
def test_contraction_never_mangled(token):
    assert _not_mangled(token)                     # no don't->donut


def test_proper_noun_word_level_not_mangled():
    assert _not_mangled("Claude")


# ---- 8. validity sources (Wiktionary + project allowlist) leave terms alone ------
@pytest.mark.parametrize("term", ["refactor", "regex", "dataclass"])   # Wiktionary
def test_tech_term_grounds_and_is_left_alone(term):
    assert LX.grounds(term)
    assert correct(term).fired is False


@pytest.mark.parametrize("term", ["innerese", "jsonl", "pytest", "lintgate"])  # allowlist
def test_project_allowlist_term_is_left_alone(term):
    assert LX.grounds(term)
    assert correct(term).fired is False


def test_clitic_rejoined_in_corrected_output():
    from gse.mcp.spell_server import spell_suggest
    out = spell_suggest("it's a wierd seperate thing")
    assert out["corrected"] == "it's a weird separate thing"   # no "it 's"


# ---- 9. rare-tail recovery: slot-gated, common-target-only, jargon-safe ----------
def test_rare_tail_recovered_in_predicate_slot():
    # 'cen' after a subject pronoun is in a verb slot it can't fill -> recovered to 'can'
    from gse.mcp.spell_server import spell_suggest
    out = spell_suggest("as far as we cen tell")
    assert "can" in out["corrected"].split() and "cen" not in out["corrected"]


def test_rare_tail_jargon_in_allowlist_untouched():
    # learn-spelling: project vocab is never reconsidered, even verbed after a pronoun
    from gse.mcp.spell_server import spell_suggest
    assert spell_suggest("we gse the data")["corrected"] == "we gse the data"
    assert spell_suggest("the gse encoder uses adj tags")["corrected"] == \
        "the gse encoder uses adj tags"


def test_rare_tail_acronym_protected():
    from gse.mcp.spell_server import spell_suggest
    assert "GSE" in spell_suggest("I refactored the GSE encoder")["corrected"]


def test_spell_learn_validates_and_is_idempotent():
    # 'Add to Dictionary' — non-mutating checks: rejects junk, no-ops on known words
    from gse.mcp.spell_server import spell_learn
    assert spell_learn("a1!")["ok"] is False
    r = spell_learn("gse")                       # already in the allowlist
    assert r["ok"] and r.get("already_known")
