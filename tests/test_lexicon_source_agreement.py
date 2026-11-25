"""Source agreement and sense collapse (founder correction, lexicon FC-2 and FC-3): the pure rules."""

from __future__ import annotations

from GSE.curation.lexicon_builder.source_agreement import (
    agree,
    committed_signs,
    measured_signs,
    to_bank_signs,
    votes_for_pos,
)
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
    agreement = agree(
        {
            "nrc_vad": {"GOOD": 1},
            "sentiwordnet": {"GOOD": 1},
            "concreteness": {"SOMETHING": 1},
            "lancaster_sensorimotor": {"FEEL": 1},
            "nrc_emotion": {"FEEL": -1},
        }
    )
    assert "FEEL" not in committed_signs(agreement)
    assert agreement["FEEL"].state == "OPPOSED"
    assert agreement["FEEL"].signs == {1, -1}


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
    agreement = agree({"nrc_vad": {"WANT": 1, "GOOD": 1}, "usas": {"WANT": 1}, "sentiwordnet": {"GOOD": 1}})
    assert committed_signs(agreement) == {"GOOD": 1}


def test_without_agreement_the_most_shared_encoding_is_the_main_sense():
    # "give": many transfer definitions share DO+; one heavier definition adds SAY+ ("give a speech").
    transfer = [_definition(f"wordnet:give:give.v.{i:02d}", DO=1) for i in range(1, 4)]
    speech = _definition("wordnet:give:give.v.30", DO=1, SAY=1, THINK=1)
    senses = collapse([speech, *transfer])
    assert senses[0].members == transfer and "SAY" not in senses[0].core
    assert senses[1].members == [speech]


def test_nrc_emotion_and_nrc_vad_are_one_family():
    # Same lab, same association method: their agreement is one observation.
    assert committed_signs(agree({"nrc_emotion": {"GOOD": 1}, "nrc_vad": {"GOOD": 1}})) == {}


class _Ratings:
    def __init__(self, valence=None, emotions=None, **modalities):
        self._valence, self._emotions, self._modalities = valence, emotions or {}, modalities

    def get_vad(self, word):
        return type("V", (), {"valence": self._valence})() if self._valence is not None else None

    def get_emotions(self, word):
        return self._emotions

    def get_sensorimotor(self, word):
        return type("S", (), self._modalities)() if self._modalities else None


def test_only_strong_valence_measures_good():
    assert measured_signs("nrc_vad", _Ratings(valence=0.985), "happy") == {"GOOD": 1}
    assert measured_signs("nrc_vad", _Ratings(valence=0.438), "real") == {}
    # "learn" (0.666) passes the strength test but NRC alone cannot commit GOOD:
    assert committed_signs(agree({"nrc_vad": {"GOOD": 1}, "nrc_emotion": {"FEEL": 1}})) == {}
    assert measured_signs("nrc_vad", _Ratings(valence=-0.55), "sad") == {"GOOD": -1}


def test_only_a_genuine_emotion_or_felt_strength_measures_feel():
    assert measured_signs("nrc_emotion", _Ratings(emotions={"trust": 1, "positive": 1}), "real") == {}
    assert measured_signs("nrc_emotion", _Ratings(emotions={"joy": 1}), "happy") == {"FEEL": 1}
    hand_rated = _Ratings(visual=1.0, auditory=0.5, haptic=4.0, interoceptive=1.0)
    assert measured_signs("lancaster_sensorimotor", hand_rated, "lock") == {"TOUCH": 1}


def test_when_the_most_common_sense_has_no_evidence_the_main_sense_stays_unresolved():
    # "buy": its first sense (purchase) is unresolved; "accept as true" (THINK+) must not stand in.
    purchase = Definition("wordnet:buy:buy.v.01", 1, "verb", {}, {})
    believe = _definition("wordnet:buy:buy.v.05", THINK=1)
    senses = collapse([purchase, believe], first_entry="wordnet:buy:buy.v.01")
    assert senses[0].core == {} and purchase in senses[0].absorbed
    assert senses[1].members == [believe]


def test_several_coherent_definitions_carry_the_main_sense_even_when_the_first_is_unresolved():
    first = Definition("wordnet:give:give.v.01", 1, "verb", {}, {})
    transfer = [_definition(f"wordnet:give:give.v.0{i}", DO=1) for i in (3, 4, 5)]
    senses = collapse([first, *transfer], first_entry="wordnet:give:give.v.01")
    assert senses[0].members == transfer and first in senses[0].absorbed


def test_a_word_that_causes_a_feeling_is_not_a_feeling():
    assert measured_signs("lancaster_sensorimotor", _Ratings(interoceptive=3.2), "dangerous") == {}
    assert measured_signs("lancaster_sensorimotor", _Ratings(interoceptive=4.36), "afraid") == {"FEEL": 1}
