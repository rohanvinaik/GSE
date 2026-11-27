"""The homonym and coherence collapse (rebuild task 10.0; design E10). The words and facts are synthetic."""

from __future__ import annotations

import numpy as np

from GSE.curation.lexicon_builder import senses
from GSE.curation.lexicon_builder.cells import BANK_INDEX, NEG, POS, START, ZERO
from GSE.curation.lexicon_builder.inventory import Reading

CLASS_NAMES = (
    "untouched",
    "stated",
    "profile_derivation",
    "law",
    "lens",
    "nsm",
    "forced_obligation",
    "admitted",
    "inherited",
    "inherited_consequence",
    "stated_identity",
)
POS_LAW = "law:VERB_HEADS_NO_SUBSTANTIVE"  # selected by the part of speech alone


class World:
    """A synthetic round: readings with known cells (and their warrants) and interpolated cells."""

    def __init__(self):
        self.readings, self.known, self.interp, self.cls, self.rule = [], [], [], [], []
        self.rule_ids = [POS_LAW, "stated:t"]

    def add(self, lemma, pos, known=None, inherited=None, pos_law=None):
        row = len(self.readings)
        self.readings.append(Reading(f"t:{lemma}:{pos}:{row:03d}", lemma, pos, ""))
        k, c, r = START.copy(), np.zeros(len(START), np.uint8), np.full(len(START), -1, np.int32)
        for bank, state in (known or {}).items():
            k[BANK_INDEX[bank]], c[BANK_INDEX[bank]], r[BANK_INDEX[bank]] = state, 1, 1
        for bank, state in (pos_law or {}).items():
            k[BANK_INDEX[bank]], c[BANK_INDEX[bank]], r[BANK_INDEX[bank]] = state, 3, 0
        i = k.copy()
        for bank, state in (inherited or {}).items():
            i[BANK_INDEX[bank]] = state
        self.known.append(k), self.interp.append(i), self.cls.append(c), self.rule.append(r)
        return row

    def collapse(self):
        rnd = senses.Round(
            readings=tuple(self.readings),
            known=np.array(self.known),
            interpolated=np.array(self.interp),
            known_class=np.array(self.cls),
            known_rule=np.array(self.rule),
            rule_ids=tuple(self.rule_ids),
            class_names=CLASS_NAMES,
        )
        return senses.collapse(rnd)


def _word(result, lemma, pos):
    return next(w for w in result.words if (w.lemma, w.pos) == (lemma, pos))


def _sense(result, sense_id):
    return next(s for s in result.senses if s.sense_id == sense_id)


def _members(result, sense_id, world):
    return {world.readings[r].reading_id for r in _sense(result, sense_id).members}


def test_a_word_with_many_definitions_collapses_to_its_homonyms():
    w = World()
    hair = [w.add("lock", "noun", {"BODY": POS, "PART": POS}), w.add("lock", "noun", {"BODY": POS})]
    fastener = [w.add("lock", "noun", {"BODY": ZERO, "TOUCH": POS}), w.add("lock", "noun", {"BODY": ZERO})]
    canal = w.add("lock", "noun", {"BODY": ZERO, "WHERE": POS})  # fits the fastener's state on BODY only
    verbs = [w.add("lock", "verb", pos_law={"SOMEONE": ZERO}) for _ in range(3)]
    result = w.collapse()
    noun = _word(result, "lock", "noun")
    assert len(noun.senses) == 2 and not noun.exceptions and not noun.residuals
    groups = {frozenset(_sense(result, s).members) for s in noun.senses}
    assert groups == {frozenset(hair), frozenset(fastener + [canal])}
    assert all(_sense(result, s).splits == {o: ["BODY"] for o in noun.senses if o != s} for s in noun.senses)
    verb = _word(result, "lock", "verb")
    assert len(verb.senses) == 1 and set(_sense(result, verb.senses[0]).members) == set(verbs)


def test_an_unlinked_definition_joins_its_core_without_changing_it():
    w = World()
    linked = [w.add("widget", "noun", {"MOVE": POS}), w.add("widget", "noun", {"MOVE": POS, "TOUCH": POS})]
    alone = World()
    for r in linked:
        alone.add(
            "widget", "noun", {b: w.known[r][BANK_INDEX[b]] for b in ("MOVE", "TOUCH") if w.cls[r][BANK_INDEX[b]]}
        )
    unlinked = w.add("widget", "noun")
    result, without = w.collapse(), alone.collapse()
    (sense_id,) = _word(result, "widget", "noun").senses
    sense = _sense(result, sense_id)
    assert unlinked in sense.members and unlinked not in sense.evidenced
    assert np.array_equal(sense.known, without.senses[0].known)


def test_an_interfering_pair_separates_with_the_bank_named():
    w = World()
    a, b = w.add("bank", "noun", {"GOOD": POS}), w.add("bank", "noun", {"GOOD": NEG})
    result = w.collapse()
    word = _word(result, "bank", "noun")
    assert len(word.senses) == 2 and not word.exceptions  # two definitions, neither a core: two homonyms
    first, second = word.senses
    assert _sense(result, first).splits == {second: ["GOOD"]}
    assert {_sense(result, s).members for s in word.senses} == {(a,), (b,)}


def test_an_out_of_variance_definition_is_kept_apart_and_not_averaged_in():
    w = World()
    core = [w.add("fob", "noun", {"SAME": POS, "TOUCH": POS}) for _ in range(3)]
    odd = w.add("fob", "noun", {"SAME": NEG})
    result = w.collapse()
    word = _word(result, "fob", "noun")
    assert len(word.senses) == 1 and len(word.exceptions) == 1
    exception = _sense(result, word.exceptions[0])
    assert exception.members == (odd,) and exception.kind == "exception" and exception.against_core == ["SAME"]
    kept = _sense(result, word.senses[0])
    assert set(kept.members) == set(core)
    assert kept.known[BANK_INDEX["SAME"]] == POS  # the core keeps its state; nothing is averaged


def test_a_part_of_speech_with_only_evidence_free_definitions_keeps_one_sense():
    w = World()
    rows = [w.add("zing", "verb", pos_law={"SOMEONE": ZERO}), w.add("zing", "verb")]
    result = w.collapse()
    (sense_id,) = _word(result, "zing", "verb").senses
    sense = _sense(result, sense_id)
    assert set(sense.members) == set(rows) and not sense.evidenced
    assert sense.known[BANK_INDEX["SOMEONE"]] == ZERO  # what the rules establish, closed under the laws
    assert sense.known[BANK_INDEX["SOMETHING"]] == ZERO  # the verb head law, applied to the sense


def test_a_definition_that_fits_several_homonyms_is_a_residual_not_a_choice():
    w = World()
    w.add("pin", "noun", {"GOOD": POS}), w.add("pin", "noun", {"GOOD": NEG})
    both = w.add("pin", "noun", {"TOUCH": POS})
    free = w.add("pin", "noun")
    result = w.collapse()
    word = _word(result, "pin", "noun")
    reasons = {x["reading"]: (x["reason"], tuple(x["candidates"])) for x in word.residuals}
    assert reasons[w.readings[both].reading_id] == ("FITS_SEVERAL_HOMONYMS", tuple(word.senses))
    assert reasons[w.readings[free].reading_id] == ("NO_EVIDENCE_AND_NO_CORE", tuple(word.senses))
    assert result.sense_of[both] == -1 and result.sense_of[free] == -1


def test_inherited_values_never_separate_homonyms_and_their_disagreement_is_a_conflict():
    w = World()
    w.add("tor", "noun", inherited={"GOOD": POS}), w.add("tor", "noun", inherited={"GOOD": NEG})
    result = w.collapse()
    (sense_id,) = _word(result, "tor", "noun").senses
    sense = _sense(result, sense_id)
    assert "GOOD" in sense.conflicts["interpolated"] and sense.interpolated[BANK_INDEX["GOOD"]] == 0
    assert result.receipt["senses_by_pos"] == {"noun": 1}


def test_the_senses_persist_for_the_artifact_writer(tmp_path):
    import json

    w = World()
    w.add("bank", "noun", {"GOOD": POS}), w.add("bank", "noun", {"GOOD": NEG}), w.add("bank", "verb")
    result = w.collapse()
    out = senses.persist(result, w.readings, tmp_path / "senses.npz", tmp_path / "senses.jsonl")
    data = np.load(tmp_path / "senses.npz", allow_pickle=True)
    assert out["senses"] == len(data["sense_ids"]) == 3
    assert np.array_equal(data["known"], result.known.masks) and data["sense_of"].tolist() == result.sense_of.tolist()
    lines = [json.loads(x) for x in (tmp_path / "senses.jsonl").read_text().splitlines()]
    assert {x["type"] for x in lines} == {"sense", "word"}
    assert next(x for x in lines if x["type"] == "word")["senses"] == ["sense:bank:noun:1", "sense:bank:noun:2"]
