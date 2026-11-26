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


def test_no_sense_is_ranked_or_made_a_default():
    # Rohan, 2026-11-25: senses are the coherent groups of the whole set; grammar and context choose among them.
    animal = [_definition(f"wordnet:dog:dog.n.0{i}", ALIVE=1, SOMETHING=1) for i in (1, 2)]
    person = [_definition(f"wordnet:dog:chap.n.0{i}", SOMEONE=1, SOMETHING=1) for i in (1, 2, 3)]
    senses = collapse([*person, *animal], anchor={"ALIVE": 1, "SOMETHING": 1})
    assert sorted(tuple(d.entry_id for d in s.members) for s in senses) == sorted(
        [tuple(d.entry_id for d in animal), tuple(d.entry_id for d in person)]
    )


def test_an_uncorroborated_added_value_is_a_different_meaning():
    # "dog" as "a man": SOMEONE+, which no word-level source asserts.
    animal = _definition("wordnet:dog:dog.n.01", ALIVE=1, SOMETHING=1)
    person = _definition("wordnet:dog:chap.n.01", ALIVE=1, SOMETHING=1, SOMEONE=1)
    senses = collapse([animal, person], anchor={"ALIVE": 1, "SOMETHING": 1}, corroboration={})
    assert sorted([s.members for s in senses], key=lambda m: m[0].entry_id) == [[person], [animal]]


def test_a_different_load_bearing_encoding_is_a_different_sense():
    # Rohan 03:28: the same sense iff the same encoding on the load-bearing banks; corroboration does not merge.
    thinking = _definition("wordnet:know:know.v.02", THINK=1)
    knowing = _definition("wordnet:know:know.v.01", THINK=1, KNOW=1)
    corroboration = {"KNOW": {1: frozenset({"nrc_emotion"})}}
    senses = collapse([thinking, knowing], anchor={"THINK": 1}, corroboration=corroboration)
    assert len(senses) == 2


def test_the_unit_of_length_does_not_join_the_fastener():
    fastener = _definition("wordnet:nail:nail.n.02", SOMETHING=1)
    unit = _definition("wordnet:nail:nail.n.03", SOMETHING=1, QUANTITY=1)
    senses = collapse([fastener, unit])
    assert len(senses) == 2 and all("QUANTITY" not in s.core for s in senses if fastener in s.members)


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


def test_a_definition_without_evidence_joins_no_core():
    # "buy": the purchase definition carries no load-bearing value, so it shapes no sense's core.
    purchase = Definition("wordnet:buy:buy.v.01", 1, "verb", {}, {})
    believe = _definition("wordnet:buy:buy.v.05", THINK=1)
    senses = collapse([purchase, believe])
    assert [s.members for s in senses] == [[believe]] and senses[0].core == {"THINK": 1}
    assert purchase in senses[0].absorbed  # listed for identity only


def test_coherent_definitions_form_a_sense_without_any_anchor():
    blank = Definition("wordnet:give:give.v.01", 1, "verb", {}, {})
    transfer = [_definition(f"wordnet:give:give.v.0{i}", DO=1) for i in (3, 4, 5)]
    senses = collapse([blank, *transfer])
    assert [s.members for s in senses] == [transfer] and senses[0].core == {"DO": 1}


def test_a_word_that_causes_a_feeling_is_not_a_feeling():
    assert measured_signs("lancaster_sensorimotor", _Ratings(interoceptive=3.2), "dangerous") == {}
    assert measured_signs("lancaster_sensorimotor", _Ratings(interoceptive=4.36), "afraid") == {"FEEL": 1}
