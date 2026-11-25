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


def test_the_group_closest_to_the_sources_agreement_is_the_main_sense():
    animal = [_definition(f"wordnet:dog:dog.n.0{i}", ALIVE=1, SOMETHING=1) for i in (1, 2)]
    person = [_definition(f"wordnet:dog:chap.n.0{i}", SOMEONE=1, SOMETHING=1) for i in (1, 2, 3)]
    senses = collapse([*person, *animal], anchor={"ALIVE": 1, "SOMETHING": 1})
    assert senses[0].members == animal


def test_an_uncorroborated_added_value_is_a_different_meaning():
    # "dog" as "a man": SOMEONE+, which no word-level source asserts.
    animal = _definition("wordnet:dog:dog.n.01", ALIVE=1, SOMETHING=1)
    person = _definition("wordnet:dog:chap.n.01", ALIVE=1, SOMETHING=1, SOMEONE=1)
    senses = collapse([animal, person], anchor={"ALIVE": 1, "SOMETHING": 1}, corroboration={})
    assert len(senses) == 2 and senses[0].members == [animal] and senses[1].members == [person]


def test_a_corroborated_added_value_joins_the_main_sense():
    thinking = _definition("wordnet:know:know.v.02", THINK=1)
    knowing = _definition("wordnet:know:know.v.01", THINK=1, KNOW=1)
    corroboration = {"KNOW": {1: frozenset({"nrc_emotion"})}}
    senses = collapse([thinking, knowing], anchor={"THINK": 1}, corroboration=corroboration)
    assert len(senses) == 1 and senses[0].core["KNOW"] == 1


def test_a_family_cannot_corroborate_its_own_value():
    moving = _definition("wordnet:run:run.v.01", MOVE=1)
    causative = Definition("wordnet:run:run.v.04", 3, "verb", {"CAUSE": 1}, {"CAUSE": (1, 3.0, "verbnet", "ASSERTION")})
    corroboration = {"CAUSE": {1: frozenset({"verb_structure"})}}
    senses = collapse([moving, causative], anchor={"MOVE": 1}, corroboration=corroboration)
    assert len(senses) == 2 and senses[0].members == [moving]


def test_a_conflict_on_a_load_bearing_bank_splits_the_sense():
    alive, dead = _definition("a", ALIVE=1), _definition("b", ALIVE=-1)
    senses = collapse([alive, dead])
    assert len(senses) == 2


def test_a_definition_with_no_load_bearing_value_is_absorbed_not_a_sense():
    blank = Definition("wiktionary:dog:blank", 2, "noun", {"GOOD": 0}, {})
    senses = collapse([blank], anchor={"ALIVE": 1})
    assert len(senses) == 1 and senses[0].absorbed == [blank]


def test_loose_families_agreeing_commit_nothing():
    # Lancaster's hand/arm rating and a topical tag both say BODY for "lock": association, not meaning.
    agreement = agree({"lancaster_sensorimotor": {"BODY": 1, "DO": 1}, "usas": {"BODY": 1, "DO": 1}})
    assert committed_signs(agreement) == {}
    assert agreement["BODY"].state == "UNMEASURED"


def test_one_measuring_family_and_one_loose_family_commit_nothing():
    # NRC's anticipation->WANT is an association; with a topical tag it is still not two measurements.
    agreement = agree({"nrc_emotion": {"WANT": 1, "GOOD": 1}, "usas": {"WANT": 1}, "sentiwordnet": {"GOOD": 1}})
    assert committed_signs(agreement) == {"GOOD": 1}


def test_without_agreement_the_most_shared_encoding_is_the_main_sense():
    # "give": many transfer definitions share DO+; one heavier definition adds SAY+ ("give a speech").
    transfer = [_definition(f"wordnet:give:give.v.{i:02d}", DO=1) for i in range(1, 4)]
    speech = _definition("wordnet:give:give.v.30", DO=1, SAY=1, THINK=1)
    senses = collapse([speech, *transfer])
    assert senses[0].members == transfer and "SAY" not in senses[0].core
    assert senses[1].members == [speech]
