"""The artifact writer writes what the runtime reads (rebuild-lexicon-symbolic-closure task 10.1, design E11).

The definitions here are hand-written for the test; the tables, the format and the readers are the real ones.
"""

from __future__ import annotations

import json
import sqlite3

import numpy as np
import pytest

from GSE.curation.lexicon_builder import store
from GSE.curation.lexicon_builder.cells import BANK_INDEX, BANKS, NEG, POS, SILENT, START, ZERO
from GSE.curation.lexicon_builder.inventory import Reading
from GSE.lexicon.definitions import VERSION, read_entries, runtime_lookup
from GSE.lexicon.senses import has_senses, read_senses


def _kind(tmp_path):
    return store.fixture(
        tmp_path / "lexicon.db",
        [
            store.FixtureEntry(
                "fixture:kind", "kind", "adj", "a test gloss", {"GOOD": 1, "SOMETHING": 0, "SEE": "SILENT"}
            ),
            store.FixtureEntry("fixture:bank:1", "bank", "noun", "first", {"GOOD": 1}),
            store.FixtureEntry("fixture:bank:2", "bank", "noun", "second", {"GOOD": -1}),
        ],
    )


def test_definitions_read_back_with_decided_signs_silence_as_empty_and_residuals_as_their_signs(tmp_path):
    conn = sqlite3.connect(_kind(tmp_path))
    assert json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='format'").fetchone()[0]) == VERSION
    [kind] = read_entries(conn, "kind")
    assert set(kind["domains"]) == set(BANKS)
    assert kind["domains"]["GOOD"] == [1] and kind["domains"]["SOMETHING"] == [0] and kind["domains"]["SEE"] == []
    assert kind["domains"]["FEEL"] == [0, 1]  # an unpaired bank never allows -1 (F040)
    assert kind["domains"]["BIG"] == [-1, 0, 1]
    assert kind["assignments"] == {"GOOD": 1, "SOMETHING": 0}
    assert kind["code"] == "PARTIAL"
    assert runtime_lookup(conn, "bank")["code"] == "AMBIGUOUS"


def test_the_four_state_masks_are_kept_losslessly(tmp_path):
    conn = sqlite3.connect(_kind(tmp_path))
    raw = conn.execute("SELECT masks FROM definition_states WHERE entry_id='fixture:kind'").fetchone()[0]
    masks = np.array([int(c, 16) for c in raw], dtype=np.uint8)
    expected = START.copy()
    expected[BANK_INDEX["GOOD"]], expected[BANK_INDEX["SOMETHING"]], expected[BANK_INDEX["SEE"]] = POS, ZERO, SILENT
    assert (masks == expected).all()


def test_codes_follow_the_masks():
    resolved = np.full(len(BANKS), ZERO, dtype=np.uint8)
    assert store.code(resolved) == "RESOLVED"
    resolved[0] = 0
    assert store.code(resolved) == "CONFLICT"
    assert store.code(START) == "PARTIAL"
    assert store.signs(POS | NEG | SILENT) == [-1, 1]


def test_an_existing_artifact_is_never_overwritten(tmp_path):
    path = _kind(tmp_path)
    with pytest.raises(FileExistsError):
        store.fixture(path, [])


def test_the_sense_table_always_exists_and_reads_nothing_until_senses_are_written(tmp_path):
    conn = sqlite3.connect(_kind(tmp_path))
    assert has_senses(conn)
    assert read_senses(conn, "kind") is None


def test_senses_are_written_in_the_columns_the_runtime_reads(tmp_path):
    sense = {
        "lemma": "bank",
        "pos": "noun",
        "sense": 0,
        "code": "PARTIAL",
        "core": {"GOOD": 1},
        "members": ["fixture:bank:1"],
        "absorbed": [],
        "assignments": {"GOOD": 1},
        "open": {},
        "provenance": {},
        "blocked": {},
    }
    path = store.fixture(
        tmp_path / "s.db", [store.FixtureEntry("fixture:bank:1", "bank", "noun", "g", {"GOOD": 1})], senses=[sense]
    )
    reading = read_senses(sqlite3.connect(path), "bank", "NOUN")
    assert reading["assignments"] == {"GOOD": 1}


def test_a_round_state_publishes_interpolated_values_with_their_standing_and_keeps_the_known_layer(tmp_path):
    readings = (Reading("w:a", "a", "noun", "ga"), Reading("w:b", "b", "verb", "gb"))
    known = np.tile(START, (2, 1))
    known[0, BANK_INDEX["MOVE"]] = POS
    interpolated = known.copy()
    interpolated[1, BANK_INDEX["FEEL"]] = POS
    rule = np.full(known.shape, -1, dtype=np.int32)
    rule[0, BANK_INDEX["MOVE"]] = 0
    cls = np.where(rule >= 0, 0, -1)
    i_rule = rule.copy()
    i_rule[1, BANK_INDEX["FEEL"]] = 1
    np.savez_compressed(
        tmp_path / "round.npz",
        readings=np.array(["w:a", "w:b"], dtype=object),
        banks=np.array(BANKS, dtype=object),
        known_masks=known,
        interpolated_masks=interpolated,
        known_class=cls,
        known_rule=rule,
        interpolated_class=np.where(i_rule >= 0, 1, -1),
        interpolated_rule=i_rule,
        rule_ids=np.array(["lens:VN_EVENT_MOTION", "inherit:hypernym"], dtype=object),
        classes=np.array(["direct", "inherited"], dtype=object),
    )
    entries, _ = store.from_round(tmp_path / "round.npz", readings)
    receipt = store.write_artifact(tmp_path / "art.db", entries)
    conn = sqlite3.connect(tmp_path / "art.db")
    a, b = read_entries(conn, "a")[0], read_entries(conn, "b")[0]
    assert a["assignments"] == {"MOVE": 1}
    assert a["trace"] == [{"bank": "MOVE", "class": "direct", "rule": "lens:VN_EVENT_MOTION", "standing": "known"}]
    # Ruling A: the interpolated layer is published, labelled with its standing and never passed off as known.
    assert b["assignments"] == {"FEEL": 1}
    assert b["trace"] == [
        {"bank": "FEEL", "class": "inherited", "rule": "inherit:hypernym", "standing": "interpolated"}
    ]
    assert store.values(conn, "w:b") == {"FEEL": 1} and store.values(conn, "w:b", layer="known") == {}
    assert store.masks(conn, "w:b", layer="known")[BANK_INDEX["FEEL"]] == START[BANK_INDEX["FEEL"]]
    rows = [tuple(r) for r in conn.execute("SELECT entry_id, bank, layer, class, rule FROM cell_warrants ORDER BY 1")]
    assert rows == [
        ("w:a", "MOVE", "known", "direct", "lens:VN_EVENT_MOTION"),
        ("w:b", "FEEL", "interpolated", "inherited", "inherit:hypernym"),
    ]
    assert receipt["primitive_values"] == {"known": 1, "interpolated": 1}
    with pytest.raises(ValueError, match="UNKNOWN_LAYER"):
        store.values(conn, "w:b", layer="defaults")


def test_the_encoder_reads_a_fixture_artifact(tmp_path):
    from GSE.api.encoder import GSEEncoder

    with GSEEncoder(str(_kind(tmp_path))) as encoder:
        record = encoder.lexical_lookup("kind")["selected_record"]
        assert record["assignments"]["SOMETHING"] == 0
        assert -1 not in record["domains"]["FEEL"]


def test_the_acceptance_witnesses_run_through_the_real_encoder_on_the_artifact(tmp_path):
    path = store.fixture(
        tmp_path / "witness.db",
        [
            store.FixtureEntry("fixture:lock:noun", "lock", "noun", "a fastener", {"SOMETHING": 1}),
            store.FixtureEntry("fixture:lock:verb", "lock", "verb", "to fasten", {"DO": 1}),
        ],
    )
    result = store.acceptance(path)
    assert set(result) == set(store.WITNESSES)
    lock = next(t for t in result["lock_noun"]["tokens"] if t["token"] == "lock")
    assert lock["candidates"] == 2
    florbles = next(t for t in result["florbles"]["tokens"] if t["token"] == "florbles")
    assert florbles["lexicon_status"] == "unknown" and not florbles["primitives"]


def test_persisted_senses_become_the_rows_the_runtime_reads(tmp_path):
    known = np.tile(START, (2, 1))
    known[0, BANK_INDEX["GOOD"]] = POS
    known[0, BANK_INDEX["BIG"]] = POS | SILENT  # still allows silence: never an open constraint
    known[1, BANK_INDEX["GOOD"]] = NEG
    known[1, BANK_INDEX["FEEL"]] = POS | ZERO
    np.savez_compressed(
        tmp_path / "senses.npz",
        sense_ids=np.array(["sense:bank:noun:1", "sense:bank:noun:2"], dtype=object),
        known=known,
        interpolated=known,
        banks=np.array(BANKS, dtype=object),
    )
    lines = [
        {
            "type": "sense",
            "sense": f"sense:bank:noun:{n}",
            "lemma": "bank",
            "pos": "noun",
            "kind": "sense",
            "members": members,
            "evidenced": evidenced,
            "load_bearing": ["GOOD"],
            "known": {},
            "interpolated": {},
            "conflicts": {},
            "splits": {},
            "against_core": [],
        }
        for n, members, evidenced in ((1, ["f:1", "f:3"], ["f:1"]), (2, ["f:2"], ["f:2"]))
    ]
    lines.append(
        {
            "type": "word",
            "lemma": "bank",
            "pos": "noun",
            "senses": [],
            "exceptions": [],
            "search": "exact",
            "residuals": [
                {"reading": "f:4", "candidates": ["sense:bank:noun:1", "sense:bank:noun:2"], "reason": "NO_EVIDENCE"}
            ],
        }
    )
    (tmp_path / "senses.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines))
    rows, residuals = store.sense_rows(tmp_path / "senses.npz", tmp_path / "senses.jsonl")
    first = next(r for r in rows if r["sense"] == 0)
    assert (first["members"], first["absorbed"]) == (["f:1"], ["f:3"])
    assert first["assignments"] == {"GOOD": 1} and "BIG" not in first["open"]
    assert next(r for r in rows if r["sense"] == 1)["open"] == {"FEEL": [0, 1]}
    entries = [store.FixtureEntry(f"f:{i}", "bank", "noun", "g") for i in (1, 2, 3, 4)]
    path = store.fixture(tmp_path / "a.db", entries, senses=rows)
    conn = sqlite3.connect(path)
    store.write_residuals(conn, residuals)
    conn.commit()
    reading = read_senses(conn, "bank", "NOUN")
    assert {s["sense"] for s in reading["senses"]} == {0, 1}
    assert conn.execute("SELECT entry_id FROM sense_residuals").fetchall() == [("f:4",)]


def test_the_closed_class_catalog_is_written_as_stated_definitions_the_runtime_accepts(tmp_path):
    from GSE.curation.lexicon_builder import native_records

    entries, records = store.closed_class_fixtures()
    assert len(entries) == len(records) == 213
    readings = tuple(Reading(e.entry_id, e.lemma, e.pos, e.gloss) for e in entries)
    assert native_records.validate(readings, records) == {"gse_closed_class": {"ACCEPTED": 213}}
    path = store.fixture(tmp_path / "grammar.db", entries, records)
    conn = sqlite3.connect(path)
    [below] = [e for e in entries if e.values.get("ABOVE") == -1]  # a declared BELOW is ABOVE at -1
    assert read_entries(conn, below.lemma, below.entry_id)[0]["assignments"]["ABOVE"] == -1
    assert runtime_lookup(conn, "can", "gse_closed_class:modal:can")["code"] == "IDENTIFIED"


def test_a_proved_silent_cell_is_read_as_silence_not_as_a_conflict(tmp_path):
    from GSE.api.encoder import GSEEncoder

    path = store.fixture(
        tmp_path / "silent.db",
        [
            store.FixtureEntry("f:happy", "happy", "adj", "g", {"GOOD": 1, "FEEL": 1}),
            store.FixtureEntry("f:unhappy", "unhappy", "adj", "g", {"GOOD": "SILENT", "FEEL": 1}),
        ],
    )
    selection = runtime_lookup(sqlite3.connect(path), "unhappy")
    assert selection["code"] == "IDENTIFIED" and selection["selected"]["code"] == "PARTIAL"
    assert selection["selected"]["domains"]["GOOD"] == [] and "GOOD" not in selection["selected"]["assignments"]
    with GSEEncoder(str(path)) as encoder:
        token = encoder.encode("unhappy").tokens[0]
    # The stored definition is silent on GOOD, so a composed NOT(happy) value there is refused and the stored reading
    # kept; the encoder names that outcome a domain conflict with the composition, not a conflicted definition.
    assert token.negation_evidence["admission"]["decision"] == "preserve"
    assert dict(token.word_primitives) == {"FEEL": 1}
