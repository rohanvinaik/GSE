"""The source lenses write only what each source's authored contract declares (rebuild-lexicon-symbolic-closure task 3).

Every record here is hand-built for the test: VerbNet frames, USAS tags, FrameNet units and ratings are fixtures, not
source data, and no gloss is read.
"""

from __future__ import annotations

import json

import numpy as np

from GSE.curation.external_sources.framenet import FrameNetEntry
from GSE.curation.external_sources.usas import USASEntry
from GSE.curation.external_sources.verbnet import VerbNetEntry
from GSE.curation.lexicon_builder import guards, laws, obligations
from GSE.curation.lexicon_builder.cells import BANK_INDEX, BANKS, NEG, POS, SILENT, START, ZERO, State
from GSE.curation.lexicon_builder.closure import close
from GSE.curation.lexicon_builder.inventory import Reading
from GSE.curation.lexicon_builder.projection import (
    Restrictions,
    Sources,
    closure_round,
    competence,
    domain_audit,
    label,
    project,
    reading_id,
    settled_round,
)

MOTION = ("motion", ("Event", "during(E)"), ("ThemRole", "Theme"))
LOCATION = ("location", ("Event", "end(E)"), ("ThemRole", "Theme"), ("ThemRole", "Destination"))


def _pred(name, *args, negated=False):
    return {
        "predicate_value": name,
        "negated": negated,
        "polarity": "!" if negated else "",
        "arguments": [{"type": t, "value": v} for t, v in args],
    }


def _frame(*predicates):
    return {
        "native": {},
        "semantics": [_pred(*p[:-1], negated=True) if p[-1] == "!" else _pred(*p) for p in predicates],
    }


def _role(name):
    return {"tag": "THEMROLE", "attributes": {"type": name}, "text": "", "tail": "", "children": []}


def _entry(word, class_id, frames, keys, roles=("Agent", "Theme")):
    return VerbNetEntry(
        word=word,
        verb_class=class_id,
        thematic_roles=list(roles),
        wordnet_sense_keys=list(keys),
        member_attributes={"name": word},
        class_context=[{"class_id": class_id, "thematic_roles": [_role(r) for r in roles], "frames": frames}],
    )


def _links(synsets):
    """A stand-in for the exact WordNet sense-key lookup: key -> synset, anything else is invalid."""
    return lambda entry: [
        {"code": "LINKED", "sense_key": k, "synset_name": synsets[k]}
        if k in synsets
        else {"code": "INVALID_SENSE_KEY", "sense_key": k}
        for k in entry.wordnet_sense_keys
    ]


def _verb(lemma, synset):
    return Reading(reading_id(lemma, synset), lemma, "verb", "")


def _cells(lens):
    r = lens.restrictions
    return {
        (int(row), int(col), int(mask), r.rule_ids[rule])
        for row, col, mask, rule in zip(r.rows, r.cols, r.allowed, r.rules)
    }


def _unit(word, pos, frame):
    return FrameNetEntry(word=word, pos=pos, frame_name=frame, frame_id=0, core_fes=[], is_core_lu=True)


def test_a_motion_predicate_in_every_frame_gives_move_and_in_only_some_gives_nothing():
    readings = (_verb("roll", "roll.v.01"), _verb("slide", "slide.v.02"))
    sources = Sources(
        verbnet={
            "roll": [_entry("roll", "roll-51.3.1", [_frame(MOTION), _frame(MOTION, LOCATION)], ["roll%2:38:00"])],
            "slide": [_entry("slide", "slide-11.2", [_frame(MOTION), _frame(LOCATION)], ["slide%2:38:01"])],
        },
        links=_links({"roll%2:38:00": "roll.v.01", "slide%2:38:01": "slide.v.02"}),
    )
    lens = project(readings, sources)
    assert _cells(lens) == {(0, BANK_INDEX["MOVE"], POS, "VN_EVENT_MOTION")}
    assert lens.facts["own_predicate=physical_change_of_place"].tolist() == [True, False]
    assert lens.dispositions["verbnet"]["withheld"]["NOT_IN_EVERY_FRAME:VN_EVENT_MOTION"] == 1
    state = closure_round(readings, lens)
    assert state["laws_and_lens"]["+1"] == state["laws_only"]["+1"] + 1


def test_end_is_the_negative_start_pole_only_inside_its_class_number():
    end = ("end", ("Event", "E"), ("ThemRole", "Theme"))
    readings = (_verb("stop", "stop.v.01"), _verb("rush", "rush.v.01"))
    sources = Sources(
        verbnet={
            "stop": [_entry("stop", "stop-55.4", [_frame(end)], ["stop%2:38:00"])],
            "rush": [_entry("rush", "rush-53.2", [_frame(end)], ["rush%2:38:00"])],
        },
        links=_links({"stop%2:38:00": "stop.v.01", "rush%2:38:00": "rush.v.01"}),
    )
    lens = project(readings, sources)
    assert _cells(lens) == {(0, BANK_INDEX["START"], NEG, "VN_END")}
    assert lens.dispositions["verbnet"]["refused"] == {"OUTSIDE_RULE_CLASS_SCOPE": 1}


def test_vitality_lost_after_it_held_is_the_dead_pole_and_its_cause_needs_another_participant():
    frame = _frame(
        ("cause", ("ThemRole", "Agent"), ("Event", "E")),
        ("alive", ("Event", "start(E)"), ("ThemRole", "Patient")),
        ("alive", ("Event", "result(E)"), ("ThemRole", "Patient"), "!"),
    )
    readings = (_verb("kill", "kill.v.01"),)
    sources = Sources(
        verbnet={"kill": [_entry("kill", "murder-42.1", [frame], ["kill%2:35:00"], roles=("Agent", "Patient"))]},
        links=_links({"kill%2:35:00": "kill.v.01"}),
    )
    cells = _cells(project(readings, sources))
    assert (0, BANK_INDEX["ALIVE"], NEG, "VN_VITALITY") in cells
    assert {(0, BANK_INDEX[b], POS, "VN_CAUSATION") for b in ("CAUSE", "DO")} <= cells


def test_an_emotional_state_without_a_verb_emotion_tag_is_refused_and_supports_no_cause():
    frame = _frame(
        ("cause", ("ThemRole", "Stimulus"), ("Event", "E")),
        ("emotional_state", ("Event", "result(E)"), ("ThemRole", "Emotion"), ("ThemRole", "Experiencer")),
    )
    roles = ("Stimulus", "Experiencer", "Emotion")
    readings = (_verb("amuse", "amuse.v.01"), _verb("throw", "confuse.v.02"))
    sources = Sources(
        verbnet={
            "amuse": [_entry("amuse", "amuse-31.1", [frame], ["amuse%2:41:00"], roles)],
            "throw": [_entry("throw", "amuse-31.1", [frame], ["throw%2:31:00"], roles)],
        },
        links=_links({"amuse%2:41:00": "amuse.v.01", "throw%2:31:00": "confuse.v.02"}),
        usas={"amuse": [USASEntry("amuse", "VERB", ["E4.1+"])], "throw": [USASEntry("throw", "VERB", ["M2"])]},
    )
    cells = _cells(project(readings, sources))
    assert {(0, BANK_INDEX["FEEL"], POS, "VN_AFFECTIVE_STATE"), (0, BANK_INDEX["CAUSE"], POS, "VN_CAUSATION")} <= cells
    assert not any(row == 1 for row, *_ in cells)


def test_a_word_level_tag_on_a_lemma_of_several_readings_is_an_obligation_not_a_restriction():
    readings = (
        Reading("wordnet:dreadful:awful.s.02", "dreadful", "adj", ""),
        Reading("wiktionary:dreadful-adj-1:x", "dreadful", "adj", ""),
        Reading("wiktionary:dreadful-noun-1:x", "dreadful", "noun", ""),
    )
    sources = Sources(
        usas={"dreadful": [USASEntry("dreadful", "ADJ", ["A5.1-"])]},
        framenet={"dreadful": [_unit("dreadful", "a", "Desirability")]},
    )
    lens = project(readings, sources)
    assert len(lens.restrictions) == 0
    assert not lens.facts
    [obligation] = lens.obligations
    assert (obligation.rule_id, obligation.bank, obligation.allowed) == ("USAS_OWN_QUALITY_POLE", "GOOD", NEG)
    assert obligation.rows.tolist() == [0, 1]
    assert obligation.facts == ("own_degree_domain=graded_property", "own_semantic_kind=evaluator")
    assert lens.dispositions["usas"]["withheld"]["GUARD_ON_LOCATED_READING:own_semantic_kind=evaluator"] == 1


def test_a_coordinate_and_its_companions_are_obliged_of_one_and_the_same_reading():
    readings = (
        Reading("wordnet:afraid:afraid.a.01", "afraid", "adj", ""),
        Reading("wiktionary:afraid-adj-1:x", "afraid", "adj", ""),
    )
    sources = Sources(
        usas={"afraid": [USASEntry("afraid", "ADJ", ["E5-", "E5+"])]},
        framenet={"afraid": [_unit("afraid", "a", "Fear")]},
    )
    lens = project(readings, sources)
    assert {o.bank for o in lens.obligations} == {"GOOD", "THINK", "LIKE", "WHEN", "BECAUSE", "CAN", "HAPPEN"}
    assert len({o.witness for o in lens.obligations}) == 1
    assert lens.dispositions["usas"]["refused"] == {"SIGN_OUTSIDE_RULE": 1}


def test_a_single_reading_lemma_gives_a_restriction_and_its_guards_wake_the_laws():
    readings = (Reading("wordnet:excellent:excellent.s.01", "excellent", "adj", ""),)
    sources = Sources(
        usas={"excellent": [USASEntry("excellent", "ADJ", ["A5.1+++"])]},
        framenet={"excellent": [_unit("excellent", "a", "Desirability")]},
    )
    lens = project(readings, sources)
    assert _cells(lens) == {(0, BANK_INDEX["GOOD"], POS, "USAS_OWN_QUALITY_POLE")}
    assert not lens.obligations
    assert lens.facts["own_semantic_kind=evaluator"].tolist() == [True]
    result = closure_round(readings, lens)
    assert result["removals_by_rule"]["law:EVALUATOR_EXCLUDES_SIZE"] >= 1
    assert result["removals_by_rule"]["law:OWN_DEGREE_BEARING_CONTENT"] >= 1


def test_slash_and_unsigned_tags_fix_no_pole():
    readings = (Reading("wordnet:medium:medium.s.01", "medium", "adj", ""),)
    sources = Sources(
        usas={"medium": [USASEntry("medium", "ADJ", ["N3.2", "N3.2+/A2.1"])]},
        framenet={"medium": [_unit("medium", "a", "Size")]},
    )
    lens = project(readings, sources)
    assert len(lens.restrictions) == 0 and not lens.obligations and not lens.facts
    assert lens.dispositions["usas"]["refused"] == {"SLASH_TAG_JOINT_MEMBERSHIP": 1, "UNSIGNED_TAG_NO_POLE": 1}


def test_perception_mode_needs_the_predicate_and_the_tag_on_the_same_reading():
    perceive = ("perceive", ("Event", "during(E)"), ("ThemRole", "Experiencer"), ("ThemRole", "Stimulus"))
    roles = ("Experiencer", "Stimulus")
    readings = (
        _verb("overhear", "catch.v.14"),
        _verb("glimpse", "glimpse.v.01"),
        Reading("wiktionary:glimpse-verb-1:x", "glimpse", "verb", ""),
    )
    sources = Sources(
        verbnet={
            "overhear": [_entry("overhear", "sight-30.2", [_frame(perceive)], ["overhear%2:39:00"], roles)],
            "glimpse": [_entry("glimpse", "sight-30.2", [_frame(perceive)], ["glimpse%2:39:00"], roles)],
        },
        links=_links({"overhear%2:39:00": "catch.v.14", "glimpse%2:39:00": "glimpse.v.01"}),
        usas={
            "overhear": [USASEntry("overhear", "VERB", ["X3.2"])],
            "glimpse": [USASEntry("glimpse", "VERB", ["X3.4"])],
        },
    )
    lens = project(readings, sources)
    assert _cells(lens) == {(0, BANK_INDEX["HEAR"], POS, "VN_USAS_PERCEPTION_MODE")}
    assert lens.dispositions["VN_USAS_PERCEPTION_MODE"]["unbound"] == {"USAS_BINDS_A_LEMMA_POS_OF_SEVERAL_READINGS": 1}


def test_a_rating_source_writes_nothing():
    readings = (Reading("wordnet:happy:happy.a.01", "happy", "adj", ""),)
    sources = Sources(ratings={"nrc_vad": {"happy": 1}, "conceptnet": {"happy": 3}})
    lens = project(readings, sources)
    assert len(lens.restrictions) == 0 and not lens.obligations and not lens.facts
    policy = json.loads(laws.LAWS.read_text())["association_policy"]
    assert lens.dispositions["nrc_vad"] == {"recorded_only": {policy["NRC_VAD"]: 1}}
    assert sum(lens.dispositions["conceptnet"]["recorded_only"].values()) == 3
    state = closure_round(readings, lens)
    assert state["laws_and_lens"]["bits"] == state["laws_only"]["bits"]


def test_an_unbound_record_is_counted_as_unbound():
    readings = (_verb("roll", "roll.v.01"),)
    sources = Sources(
        verbnet={"roll": [_entry("roll", "roll-51.3.1", [_frame(MOTION)], ["roll%2:38:00", "roll%2:38:09"])]},
        links=_links({"roll%2:38:00": "roll.v.03"}),
        usas={"ramble": [USASEntry("ramble", "ADJ", ["A5.1+"])]},
        framenet={"ramble": [_unit("ramble", "a", "Desirability")]},
    )
    lens = project(readings, sources)
    assert len(lens.restrictions) == 0
    assert lens.dispositions["verbnet"]["unbound"] == {"INVALID_SENSE_KEY": 1, "READING_NOT_IN_COHORT": 1}
    assert lens.dispositions["usas"]["unbound"] == {"NO_READING_FOR_LEMMA_POS": 1}


def test_every_restriction_is_inside_its_rules_published_competence_and_ratings_may_write_nothing():
    book = json.loads(laws.LAWS.read_text())
    published = competence()
    authored = book["native_predicate_rules"] + book["source_rules"] + book["native_residual_rules"]
    assert all(published[rule["rule_id"]]["writes"] for rule in authored)
    assert all(
        not published[s]["writes"] for s in ("nrc_emotion", "nrc_vad", "lancaster", "concreteness", "conceptnet")
    )
    kill = _frame(
        ("cause", ("ThemRole", "Agent"), ("Event", "E")),
        ("alive", ("Event", "start(E)"), ("ThemRole", "Patient")),
        ("alive", ("Event", "result(E)"), ("ThemRole", "Patient"), "!"),
    )
    readings = (_verb("kill", "kill.v.01"), Reading("wordnet:afraid:afraid.a.01", "afraid", "adj", ""))
    sources = Sources(
        verbnet={"kill": [_entry("kill", "murder-42.1", [kill], ["kill%2:35:00"], roles=("Agent", "Patient"))]},
        links=_links({"kill%2:35:00": "kill.v.01"}),
        usas={"afraid": [USASEntry("afraid", "ADJ", ["E5-"])]},
        framenet={"afraid": [_unit("afraid", "a", "Fear")]},
    )
    lens = project(readings, sources)
    assert len(lens.restrictions) == 3 + 7
    for _, col, mask, rule in _cells(lens):
        assert set(label(mask).split("|")) <= set(published[rule]["writes"][BANKS[col]].split("|"))


def test_a_bipolar_predicate_negated_in_every_frame_only_excludes_its_pole():
    not_begin = ("begin", ("Event", "E"), ("ThemRole", "Theme"), "!")
    not_moving = ("motion", ("Event", "during(E)"), ("ThemRole", "Theme"), "!")
    readings = (_verb("halt", "halt.v.01"), _verb("idle", "idle.v.01"))
    sources = Sources(
        verbnet={
            "halt": [_entry("halt", "x-55.9", [_frame(not_begin, not_moving), _frame(not_begin)], ["halt%2:38:00"])],
            "idle": [_entry("idle", "y-55.9", [_frame(not_begin), _frame(LOCATION)], ["idle%2:38:00"])],
        },
        links=_links({"halt%2:38:00": "halt.v.01", "idle%2:38:00": "idle.v.01"}),
    )
    lens = project(readings, sources)
    # source_polarity: "A negated bipolar pole only excludes that pole"; a negated unpaired MOVE writes nothing.
    assert _cells(lens) == {(0, BANK_INDEX["START"], NEG | ZERO | SILENT, "VN_BEGIN:NEGATED_POLE")}
    result = closure_round(readings, lens)
    assert result["laws_and_lens"]["-1"] == result["laws_only"]["-1"]


def test_a_located_obligation_gives_its_reading_the_rules_guards_and_wakes_their_laws():
    readings = (
        Reading("wordnet:dreadful:awful.s.02", "dreadful", "adj", ""),
        Reading("wiktionary:dreadful-adj-1:x", "dreadful", "adj", ""),
    )
    sources = Sources(
        usas={"dreadful": [USASEntry("dreadful", "ADJ", ["A5.1-"])]},
        framenet={"dreadful": [_unit("dreadful", "a", "Desirability")]},
    )
    lens = project(readings, sources)
    state = State.opening([r.reading_id for r in readings])
    state.masks[1, BANK_INDEX["GOOD"]] = ZERO  # the other reading evaluates nothing, so the bad one is row 0
    forcing = obligations.force(state, obligations.Batch.of(lens.obligations))
    assert state.masks[0, BANK_INDEX["GOOD"]] == NEG
    rels = laws.compile_laws()
    scopes = guards.scopes(readings, {r.scope for r in rels})
    obligations.wake(scopes, forcing.facts)
    close(state, rels, scopes)
    assert state.masks[0, BANK_INDEX["BIG"]] == ZERO  # EVALUATOR_EXCLUDES_SIZE, on the located reading only
    assert state.masks[0, BANK_INDEX["INTENSITY"]] == POS  # OWN_DEGREE_BEARING_CONTENT
    assert state.masks[1, BANK_INDEX["BIG"]] == START[BANK_INDEX["BIG"]]


def test_the_settled_round_locates_an_obligation_and_reports_the_facts_and_laws_it_wakes():
    readings = (
        Reading("wordnet:dreadful:awful.s.02", "dreadful", "adj", ""),
        Reading("wiktionary:dreadful-adj-1:x", "dreadful", "adj", ""),
    )
    sources = Sources(
        usas={"dreadful": [USASEntry("dreadful", "ADJ", ["A5.1-"])]},
        framenet={"dreadful": [_unit("dreadful", "a", "Desirability")]},
    )
    lens = project(readings, sources)
    assert settled_round(readings, lens, links=[])["known"]["obligation_groups_by_candidates"] == {"2": 1}
    # A stand-in for another source stating that the second reading evaluates nothing.
    lens.restrictions = Restrictions(
        rows=np.array([1]),
        cols=np.array([BANK_INDEX["GOOD"]]),
        allowed=np.array([ZERO], dtype=np.uint8),
        rules=np.array([0], dtype=np.int32),
        premises=np.array([0], dtype=np.int32),
        rule_ids=("t:no-evaluation",),
        warrants=("test",),
        premise_ids=("test",),
        rule_sources=("test",),
    )
    known = settled_round(readings, lens, links=[])["known"]
    assert known["obligation_groups_by_candidates"] == {"1": 1}
    assert known["facts_located"] == {"own_degree_domain=graded_property": 1, "own_semantic_kind=evaluator": 1}
    assert known["laws_woken"] == {"law:EVALUATOR_EXCLUDES_SIZE": 1, "law:OWN_DEGREE_BEARING_CONTENT": 1}


def test_the_domain_audit_lists_a_key_whose_lexname_no_other_class_member_has_and_changes_nothing():
    readings = (_verb("send", "send.v.01"), _verb("ship", "ship.v.01"), _verb("pass", "communicate.v.01"))
    frames = [_frame(MOTION)]
    sources = Sources(
        verbnet={w: [_entry(w, "send-11.1-1", frames, [f"{w}%2:38:00"])] for w in ("send", "ship", "pass")}
        | {"wink": [_entry("wink", "wink-40.3.1", frames, ["wink%2:29:00"])]},
        links=_links(
            {
                "send%2:38:00": "send.v.01",
                "ship%2:38:00": "ship.v.01",
                "pass%2:38:00": "communicate.v.01",
                "wink%2:29:00": "wink.v.01",
            }
        ),
    )
    lens = project(readings, sources)
    files = {
        "send.v.01": "verb.motion",
        "ship.v.01": "verb.motion",
        "communicate.v.01": "verb.communication",
        "wink.v.01": "verb.body",
    }
    audit = domain_audit(readings, sources, lens, lexname=files.get)
    assert [(a["member"], a["lexname"], a["sole_member"]) for a in audit] == [
        ("pass", "verb.communication", False),
        ("wink", "verb.body", True),
    ]
    assert audit[0]["other_members_lexnames"] == {"verb.motion": 2}
    assert audit[0]["lens_writes"] == ["MOVE:+1"]
    assert len(project(readings, sources).restrictions) == len(lens.restrictions) == 3
