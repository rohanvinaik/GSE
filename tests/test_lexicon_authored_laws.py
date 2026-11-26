"""The authored laws compile into relations and fire only on warranted guards (rebuild tasks 4-5)."""

from __future__ import annotations

from GSE.curation.lexicon_builder import guards, laws
from GSE.curation.lexicon_builder.cells import POS, ZERO, State, bit
from GSE.curation.lexicon_builder.closure import close
from GSE.curation.lexicon_builder.inventory import Reading


def test_every_authored_law_compiles_with_its_warrant():
    rels = laws.compile_laws()
    assert len(rels) == 16
    assert all(r.warrant and r.rule_id.startswith("law:") for r in rels)


def test_a_verb_and_an_adjective_have_no_substantive_head_and_a_noun_is_untouched():
    readings = (
        Reading("wordnet:run:run.v.01", "run", "verb", "move fast"),
        Reading("wordnet:big:big.a.01", "big", "adj", "above average in size"),
        Reading("wordnet:dog:dog.n.01", "dog", "noun", "a domesticated animal"),
    )
    rels = laws.compile_laws()
    s = State.opening([r.reading_id for r in readings])
    close(s, rels, guards.scopes(readings, {r.scope for r in rels}))
    from GSE.curation.lexicon_builder.cells import BANK_INDEX

    assert s.masks[0, BANK_INDEX["SOMEONE"]] == ZERO
    assert s.masks[1, BANK_INDEX["SOMETHING"]] == ZERO
    assert s.masks[2, BANK_INDEX["SOMEONE"]] & POS


def test_an_unwarranted_guard_selects_nothing():
    readings = (Reading("wordnet:love:love.n.01", "love", "noun", "a strong positive emotion"),)
    masks = guards.scopes(readings, {"own_denotatum=affective_feeling"})
    assert not masks["own_denotatum=affective_feeling"].any()
    assert bit(0) == ZERO
