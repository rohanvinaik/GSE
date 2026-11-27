"""NSM explications compile into positive content (rebuild tasks 4-5).

Every clause here is written for the test. No four-word sequence of a record appears in this file except the
chart's own frames and the molecule formula "X [m] of one kind" that rule 5 names.
"""

from __future__ import annotations

import numpy as np

from GSE.curation.lexicon_builder import nsm, nsm_text
from GSE.curation.lexicon_builder.cells import BANK_INDEX, NEG, POS, State
from GSE.curation.lexicon_builder.closure import close
from GSE.curation.lexicon_builder.inventory import Reading

WEATHER = ["a. bad weather can happen"]


def _content(text: str, title: str, noun: bool) -> dict[str, int]:
    return nsm.read_content(nsm_text.read(text, title), noun=noun).masks()


def _record(start: int, title: str, lines: list[str], kind: str = "explication") -> nsm.Record:
    text = "\n".join([f"[{chr(64 + start % 26 or 1)}] {title}", *lines])
    return nsm.Record("T", start, start + len(lines), title, kind, text)


def _readings(*pairs) -> tuple[Reading, ...]:
    out = []
    for lemma, pos, n in pairs:
        out.extend(Reading(f"test:{lemma}:{pos}:{i}", lemma, pos, "") for i in range(n))
    return tuple(out)


def test_each_exponent_gives_its_bank_the_chart_pole():
    masks = _content(
        "This thing is grim.\na. bad wind can happen near ponds\nb. pebbles are small, puddles are not good",
        "This thing is grim.",
        noun=False,
    )
    assert masks["GOOD"] == POS | NEG  # "bad" and "good" both occur: content, sign open
    assert masks["BIG"] == NEG  # small
    assert masks["FAR"] == NEG  # near
    assert masks["CAN"] == POS and masks["HAPPEN"] == POS and masks["NOT"] == POS
    assert all(m in {POS, NEG, POS | NEG} for m in masks.values())  # rule 4: no zero, no silence


def test_substantives_come_only_from_a_nouns_head_line():
    noun = _content(
        "paws\na. someone's bony parts of a big body\nb. kittens see people\nc. a ribbon can touch something",
        "paws",
        noun=True,
    )
    assert noun["PART"] == POS and noun["BODY"] == POS and noun["BIG"] == POS
    assert "SOMEONE" not in noun  # a genitive on the head line is a participant
    assert "PEOPLE" not in noun and "SOMETHING" not in noun  # substantives off the head line are participants
    assert noun["SEE"] == POS and noun["TOUCH"] == POS
    verb = _content("Someone X is hopping.\nsomeone X did something somewhere", "Someone X is hopping.", False)
    assert not {"SOMEONE", "SOMETHING"} & set(verb)  # a predicate's head line names participants only
    assert verb["DO"] == POS and verb["WHERE"] == POS


def test_the_head_lines_category_formula_gives_nothing():
    masks = _content("toddlers\na. people of one kind\nb. one toddler can wobble", "toddlers", noun=True)
    assert masks["PEOPLE"] == POS
    assert "KIND" not in masks
    assert masks["ONE"] == POS and masks["CAN"] == POS  # from the second line, not from the formula
    head_only = _content("toddlers\na. people of one kind", "toddlers", noun=True)
    assert set(head_only) == {"PEOPLE"}


def test_like_this_is_like_and_deictic_this_and_the_copula_give_nothing():
    masks = _content("This thing is plain.\na. this pebble is like this:", "This thing is plain.", noun=False)
    assert masks == {"LIKE": POS}


def test_the_chart_units_read_as_sequences():
    masks = _content(
        "Someone X is napping.\na. pups nap for some time\nb. owls hoot a very short time later, after dusk, at the "
        "same time",
        "Someone X is napping.",
        noun=False,
    )
    assert masks["SAME"] == POS and masks["LONG_TIME"] == NEG and masks["INTENSITY"] == POS
    assert masks["BEFORE"] == NEG and masks["WHEN"] == POS  # "after"; the "time" of "at the same time"
    assert "QUANTITY" not in masks  # (FOR) SOME TIME is its own unit, not SOME
    point = _content("Someone X yelped.\na. at some time, foxes yelp", "Someone X yelped.", noun=False)
    assert point["QUANTITY"] == POS and point["WHEN"] == POS  # "at some time" is SOME and TIME


def test_dont_want_reads_as_not_and_want():
    masks = _content("He was glum.\na. he thought: I don't want this", "He was glum.", noun=False)
    assert masks["NOT"] == POS and masks["WANT"] == POS and masks["THINK"] == POS


def test_a_molecule_head_carries_the_molecules_content():
    readings = _readings(("gadget", "noun", 2), ("widget", "noun", 1))
    records = (
        _record(1, "gadgets", ["something", "engineers polish these, nerds want them like jewels"], "molecule"),
        _record(2, "widgets", ["a. gadgets [m] of one kind", "b. these gadgets [m] are small"]),
    )
    compiled = nsm.compile_records(records, readings)
    widget = next(e for e in compiled.receipt if e["lemma"] == "widget")
    assert widget["molecule"]["lemma"] == "gadget"
    assert widget["molecule"]["from"] == ["T:1-3"]
    assert widget["banks"]["SOMETHING"] == "+1"  # the gadget's head, carried
    assert widget["banks"]["WANT"] == "+1" and widget["banks"]["LIKE"] == "+1"
    assert widget["banks"]["BIG"] == "-1"  # the widget's own content
    assert widget["disposition"] == "RESTRICTION"
    row = readings.index(next(r for r in readings if r.lemma == "widget"))
    written = {nsm.BANKS[c]: int(m) for r, c, m in zip(compiled.rows, compiled.cols, compiled.allowed) if r == row}
    assert written["SOMETHING"] == POS and written["WANT"] == POS and written["BIG"] == NEG


def test_one_reading_gets_a_restriction_and_several_get_an_obligation():
    readings = _readings(("grim", "adj", 1), ("bleak", "adj", 3))
    records = (_record(1, "This thing is grim.", WEATHER), _record(5, "This thing is bleak.", WEATHER))
    compiled = nsm.compile_records(records, readings)
    by_lemma = {e["lemma"]: e for e in compiled.receipt}
    assert by_lemma["grim"]["disposition"] == "RESTRICTION"
    assert by_lemma["bleak"]["disposition"] == "OBLIGATION"
    assert set(compiled.rows.tolist()) == {0}  # only the single grim reading is restricted
    assert all(set(o.rows.tolist()) == {1, 2, 3} for o in compiled.obligations)  # never copied onto each
    assert {o.rule_id for o in compiled.obligations} == {"nsm:T:5-6"}


def test_an_unsupported_record_writes_nothing():
    readings = _readings(("grim", "adj", 1), ("zorbity", "noun", 2))
    records = (
        _record(1, "Flibber gnash wop.", WEATHER),
        _record(3, "This thing is grim. [Polish]", WEATHER),
        _record(5, "notes", ["bad weather can happen"], kind="other"),
        _record(7, "This thing is dour.", WEATHER),
        _record(9, "zorbity", ["a. it can glow when bad weather can happen"]),
    )
    compiled = nsm.compile_records(records, readings)
    assert len(compiled) == 0 and not compiled.obligations
    got = [(e["disposition"], e.get("reason")) for e in compiled.receipt]
    assert got == [
        ("UNSUPPORTED", "NO_FRAME"),
        ("CROSS_LINGUISTIC", None),
        ("OTHER", None),
        ("UNSUPPORTED", "NOT_IN_COHORT"),
        ("UNSUPPORTED", "POS_NOT_SHOWN"),  # a bare form whose head line is a clause
    ]
    assert compiled.receipt[-1]["sole_pos"] == "noun"  # recorded, not bound


def test_a_joint_obligation_has_its_banks_states_and_rows_and_a_single_obligation_per_bank():
    readings = _readings(("bleak", "adj", 2))
    compiled = nsm.compile_records((_record(1, "This thing is bleak.", [*WEATHER, "b. it is small"]),), readings)
    joint = [o for o in compiled.obligations if o.joint]
    single = [o for o in compiled.obligations if not o.joint]
    assert len(joint) == 1
    j = joint[0]
    assert isinstance(j.banks, tuple) and isinstance(j.states, tuple) and len(j.banks) == len(j.states) >= 2
    assert dict(zip(j.banks, j.states)) == {"BIG": NEG, "CAN": POS, "GOOD": NEG, "HAPPEN": POS}
    assert isinstance(j.rows, np.ndarray) and j.rows.tolist() == [0, 1]
    assert {(o.bank, o.allowed) for o in single} == set(zip(j.banks, j.states))
    assert {o.witness for o in single} == {j.witness}


def test_one_explication_published_twice_is_one_witness():
    readings = _readings(("bleak", "adj", 2))
    records = (_record(1, "This thing is bleak.", WEATHER), _record(5, "This thing is bleak.", WEATHER))
    compiled = nsm.compile_records(records, readings)
    assert compiled.receipt[1]["same_as"] == "nsm:T:1-2"
    assert len({o.witness for o in compiled.obligations}) == 1
    assert {o.rule_id for o in compiled.obligations} == {"nsm:T:1-2", "nsm:T:5-6"}


def test_a_template_goes_to_the_members_it_lists():
    readings = _readings(("hop", "verb", 2), ("skip", "verb", 1))
    text = "someone did a hop\nthen this kid moved a bit near ponds"
    template = nsm.Record("T", 1, 2, "Bouncing, e.g. hop, skip", "template", text)
    compiled = nsm.compile_records((template,), readings)
    entry = compiled.receipt[0]
    assert entry["disposition"] == "TEMPLATE" and entry["field_applied"] is False
    assert {m["lemma"]: m["disposition"] for m in entry["members"]} == {"hop": "OBLIGATION", "skip": "RESTRICTION"}
    assert entry["banks"] == {"DO": "+1", "FAR": "-1", "MOVE": "+1"}


def test_a_restriction_closes_as_a_one_bank_relation():
    readings = _readings(("grim", "adj", 1))
    compiled = nsm.compile_records((_record(1, "This thing is grim.", WEATHER),), readings)
    relations, scopes = nsm.restriction_relations(compiled, len(readings))
    state = State.opening([r.reading_id for r in readings])
    close(state, relations, scopes)
    assert state.masks[0, BANK_INDEX["GOOD"]] == NEG
    assert state.masks[0, BANK_INDEX["HAPPEN"]] == POS
