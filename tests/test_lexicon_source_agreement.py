"""Source agreement and sense collapse (founder correction, lexicon FC-2 and FC-3): the pure rules."""

from __future__ import annotations

from GSE.curation.lexicon_builder.source_agreement import agree, committed_signs, to_bank_signs, votes_for_pos
from GSE.curation.lexicon_builder.word_senses import Definition, collapse


def test_two_independent_families_that_agree_commit_the_sign():
    agreement = agree({"nrc_vad": {"GOOD": 1}, "sentiwordnet": {"GOOD": 1}})
    assert committed_signs(agreement) == {"GOOD": 1}
    assert agreement["GOOD"].state == "AGREED"


def test_one_family_alone_commits_nothing():
    assert committed_signs(agree({"nrc_vad": {"GOOD": 1}})) == {}


def test_correlated_sources_count_as_one_family():
    # VerbNet and FrameNet describe the same verbs' frames: one observation counted twice.
    agreement = agree({"verbnet": {"MOVE": 1}, "framenet": {"MOVE": 1}})
    assert committed_signs(agreement) == {}
    assert agreement["MOVE"].support == {1: ("verb_structure",)}


def test_opposition_leaves_the_bank_open_with_both_signs():
    agreement = agree({"nrc_vad": {"GOOD": 1}, "sentiwordnet": {"GOOD": 1}, "nrc_emotion": {"GOOD": -1}})
    assert committed_signs(agreement) == {}
    assert agreement["GOOD"].state == "OPPOSED"
    assert agreement["GOOD"].signs == {1, -1}


def test_negative_poles_fold_into_their_bank():
    assert to_bank_signs({"BAD": 1, "SMALL": 1, "DEAD": -1}) == {"GOOD": -1, "BIG": -1, "ALIVE": 1}


def test_a_source_contradicting_itself_on_a_bank_gives_no_sign():
    assert to_bank_signs({"GOOD": 1, "BAD": 1}) == {}


def test_families_vote_only_where_they_speak():
    votes = {"verbnet": {"DO": 1}, "wordnet_hierarchy": {"ALIVE": 1}, "nrc_vad": {"GOOD": 1}}
    assert set(votes_for_pos(votes, "verb", dominant=False)) == {"verbnet"}
    assert set(votes_for_pos(votes, "noun", dominant=True)) == {"wordnet_hierarchy", "nrc_vad"}
    assert set(votes_for_pos(votes, "adj", dominant=False)) == set()


def _definition(entry_id, **values):
    load_bearing = {bank: (value, 3.0, "wordnet_hierarchy", "ASSERTION") for bank, value in values.items()}
    return Definition(entry_id, 1, "noun", dict(values), load_bearing)


def test_the_main_sense_is_the_sources_agreement_and_refinements_join_it():
    animal = _definition("wordnet:dog:dog.n.01", ALIVE=1, SOMETHING=1)
    senses = collapse([animal], anchor={"ALIVE": 1, "SOMETHING": 1, "BODY": 1})
    assert len(senses) == 1 and senses[0].members == [animal]


def test_an_uncorroborated_added_value_is_a_different_meaning():
    # "dog" as "a man": SOMEONE+, which no word-level source asserts.
    person = _definition("wordnet:dog:chap.n.01", ALIVE=1, SOMETHING=1, SOMEONE=1)
    senses = collapse([person], anchor={"ALIVE": 1, "SOMETHING": 1, "BODY": 1}, corroboration={})
    assert len(senses) == 2 and senses[1].members == [person]


def test_a_corroborated_added_value_joins_the_main_sense():
    knowing = _definition("wordnet:know:know.v.01", KNOW=1)
    senses = collapse([knowing], anchor={"THINK": 1, "DO": 1}, corroboration={"KNOW": frozenset({1})})
    assert len(senses) == 1 and senses[0].core["KNOW"] == 1


def test_a_conflict_on_a_load_bearing_bank_splits_the_sense():
    alive, dead = _definition("a", ALIVE=1), _definition("b", ALIVE=-1)
    senses = collapse([alive, dead])
    assert len(senses) == 2


def test_a_definition_with_no_load_bearing_value_is_absorbed_not_a_sense():
    blank = Definition("wiktionary:dog:blank", 2, "noun", {"GOOD": 0}, {})
    senses = collapse([blank], anchor={"ALIVE": 1})
    assert len(senses) == 1 and senses[0].absorbed == [blank]
