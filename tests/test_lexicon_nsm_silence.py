"""NSM silence (rule 8 of `nsm.py`; the lead's ruling of 2026-11-27).

An explication is a complete reductive paraphrase of its sense, so on the explicated sense every expressible bank it
neither mentions nor reaches through its molecules is SILENT. Every clause here is written for the test.
"""

from __future__ import annotations

from GSE.curation.lexicon_builder import nsm
from GSE.curation.lexicon_builder.cells import BANKS, NEG, POS, SILENT, ZERO
from GSE.curation.lexicon_builder.inventory import Reading

WEATHER = ["a. bad weather can happen"]
WARM = ["a. people can feel it", "b. owls can see it"]


def _record(start: int, title: str, lines: list[str], kind: str = "explication") -> nsm.Record:
    text = "\n".join([f"[{chr(64 + start % 26 or 1)}] {title}", *lines])
    return nsm.Record("T", start, start + len(lines), title, kind, text)


def _readings(*pairs) -> tuple[Reading, ...]:
    out = []
    for lemma, pos, n in pairs:
        out.extend(Reading(f"test:{lemma}:{pos}:{i}", lemma, pos, "") for i in range(n))
    return tuple(out)


def _written(compiled, row) -> dict[str, int]:
    return {BANKS[c]: int(m) for r, c, m in zip(compiled.rows, compiled.cols, compiled.allowed) if r == row}


def test_an_unmentioned_expressible_bank_is_silent_on_a_restricted_explicated_reading():
    readings = _readings(("grim", "adj", 1), ("warm", "adj", 1))
    compiled = nsm.compile_records(
        (_record(1, "This thing is grim.", WEATHER), _record(5, "This thing is warm.", WARM)), readings
    )
    grim = _written(compiled, 0)
    assert grim["GOOD"] == NEG and grim["CAN"] == POS and grim["HAPPEN"] == POS  # its content, unchanged
    assert grim["FEEL"] == SILENT and grim["SEE"] == SILENT  # expressible (warm writes them), unmentioned by grim
    assert ZERO not in grim.values()  # zero is never written this way
    assert next(e for e in compiled.receipt if e["lemma"] == "grim")["silent"] == ["FEEL", "SEE"]


def test_an_inexpressible_bank_stays_open():
    readings = _readings(("grim", "adj", 1), ("warm", "adj", 1))
    compiled = nsm.compile_records(
        (_record(1, "This thing is grim.", WEATHER), _record(5, "This thing is warm.", WARM)), readings
    )
    expressible = nsm.expressible_banks(
        (_record(1, "This thing is grim.", WEATHER), _record(5, "This thing is warm.", WARM))
    )
    assert "CAUSE" not in expressible and "WITH" not in expressible
    grim = _written(compiled, 0)
    assert "CAUSE" not in grim and "WITH" not in grim and "TRUE" not in grim


def test_a_molecules_content_is_not_silenced():
    readings = _readings(("gadget", "noun", 1), ("widget", "noun", 1), ("warm", "adj", 1))
    records = (
        _record(1, "gadgets", ["something", "nerds want them like jewels"], "molecule"),
        _record(3, "widgets", ["a. something small", "b. nerds hide these gadgets [m] at night"]),
        _record(6, "This thing is warm.", WARM),
    )
    compiled = nsm.compile_records(records, readings)
    widget = _written(compiled, 1)
    assert "WANT" not in widget and "LIKE" not in widget  # reached through the gadget molecule it names
    assert widget["FEEL"] == SILENT and widget["SEE"] == SILENT


def test_nothing_is_silenced_on_an_untyped_obligations_rows():
    readings = _readings(("bleak", "adj", 3), ("warm", "adj", 1))
    compiled = nsm.compile_records(
        (_record(1, "This thing is bleak.", WEATHER), _record(5, "This thing is warm.", WARM)), readings
    )
    bleak = next(e for e in compiled.receipt if e["lemma"] == "bleak")
    assert bleak["disposition"] == "UNTYPED" and bleak["silent"] == []
    assert not {0, 1, 2} & set(compiled.rows.tolist())
    assert all(SILENT not in o.states for o in compiled.obligations)


def test_a_verbs_head_law_banks_are_the_laws_absence_not_silence():
    # PART and BODY are expressible (the lump's head line writes them) and the verb never mentions them; the verb
    # head law gives a verb no substantive head (an explicit 0), so they are not silenced. FEEL is.
    readings = _readings(("walk", "verb", 1), ("lump", "noun", 1), ("warm", "adj", 1))
    records = (
        _record(1, "Someone walked.", ["a. someone did something", "b. this someone wanted it"]),
        _record(4, "lumps", ["a. parts of a body", "b. these are small"]),
        _record(7, "This thing is warm.", WARM),
    )
    compiled = nsm.compile_records(records, readings)
    walk = next(e for e in compiled.receipt if e.get("lemma") == "walk")
    assert walk["disposition"] == "RESTRICTION"
    assert {"PART", "BODY"} <= nsm.expressible_banks(records)
    assert not {"PART", "BODY"} & set(walk["silent"]) and "FEEL" in walk["silent"]


def test_an_explication_naming_an_unexplicated_molecule_silences_nothing():
    readings = _readings(("widget", "noun", 1), ("warm", "adj", 1))
    records = (
        _record(1, "widgets", ["a. something small", "b. nerds hide these gizmos [m] at night"]),
        _record(5, "This thing is warm.", WARM),
    )
    compiled = nsm.compile_records(records, readings)
    widget = next(e for e in compiled.receipt if e["lemma"] == "widget")
    assert widget["silence_withheld"] == "MOLECULE_NOT_EXPLICATED:gizmos" and widget["silent"] == []
    assert SILENT not in _written(compiled, 0).values()


def test_typed_candidates_carry_silence_inside_the_joint_obligation():
    readings = tuple(Reading(f"wordnet:hand:{s}", "hand", "noun", "") for s in ("hand.n.01", "hand.n.13"))
    readings += (Reading("wordnet:part:part.n.03", "part", "noun", ""), Reading("test:warm:adj:0", "warm", "adj", ""))
    records = (
        _record(1, "hands", ["a. bony parts of a big body", "b. these can move"]),
        _record(5, "This thing is warm.", WARM),
    )
    compiled = nsm.compile_records(records, readings)
    hand = next(e for e in compiled.receipt if e["lemma"] == "hand")
    assert hand["disposition"] == "OBLIGATION" and "FEEL" in hand["silent"]
    (joint,) = [o for o in compiled.obligations if o.joint and o.rule_id == hand["rule_id"]]
    states = dict(zip(joint.banks, joint.states))
    assert states["FEEL"] == SILENT and states["MOVE"] == POS and joint.rows.tolist() == [0, 1]
