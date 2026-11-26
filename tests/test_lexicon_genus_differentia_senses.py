"""Word senses read the genus/differentia closure as member evidence (Rohan, 2026-11-26, decision 1).

Derived cells fill banks no stated member value and no agreed sign speaks to; they are never
load-bearing, never a source vote, and never contest or override a stated value.
"""

from __future__ import annotations

import json
import sqlite3

from GSE.curation.lexicon_builder import word_senses as ws
from GSE.curation.lexicon_builder.engine import Relation

DO_HAPPEN = Relation(
    "r:do-happen",
    ("DO", "HAPPEN"),
    ((1, 1), (0, -1), (0, 0), (0, 1), (-1, -1), (-1, 0), (-1, 1)),
    ("test",),
    authority="foundational",
    approved=True,
)
NO_DO = Relation("r:no-do", ("DO",), ((0,), (-1,)), ("test",), authority="foundational", approved=True)


def definition(entry_id, resolved=None, derived=None, load_bearing=None):
    return ws.Definition(entry_id, 1, "verb", resolved or {}, load_bearing or {}, {}, derived or {})


def sense(*definitions):
    return ws.Sense(core={}, members=list(definitions))


def test_derived_cells_fill_open_banks_with_their_own_warrant_and_rules_follow():
    row = ws.close_sense("run", "verb", 0, sense(definition("a", {"GOOD": 0}, {"DO": 1})), {}, [DO_HAPPEN])
    assert row["assignments"] == {"GOOD": 0, "DO": 1, "HAPPEN": 1}
    assert row["provenance"]["GOOD"] == {"from": "members", "entries": ["a"]}
    assert row["provenance"]["DO"] == {"from": "genus-differentia", "entries": ["a"]}
    assert row["provenance"]["HAPPEN"]["from"] == "rules"


def test_a_stated_value_or_an_agreed_sign_always_wins_over_a_derived_one():
    stated = sense(definition("a", {"DO": 0}), definition("b", {}, {"DO": 1}))
    row = ws.close_sense("x", "verb", 0, stated, {}, [])
    assert row["assignments"] == {"DO": 0} and row["provenance"]["DO"]["from"] == "members"
    agreed = ws.close_sense("x", "verb", 0, sense(definition("b", {}, {"FEEL": 0})), {"FEEL": 1}, [])
    assert agreed["assignments"] == {"FEEL": 1} and agreed["provenance"]["FEEL"]["from"] == "source-agreement"


def test_a_derived_value_fills_a_sense_only_when_every_definition_holds_it():
    minor = definition("wordnet:run:run.v.26", {}, {"CAUSE": 1, "MOVE": 1})
    main = definition("wordnet:run:run.v.01", {}, {"MOVE": 1})
    row = ws.close_sense("run", "verb", 0, sense(main, minor), {}, [])
    assert row["assignments"] == {"MOVE": 1}  # the minor definition's CAUSE is not the sense's
    assert row["provenance"]["MOVE"]["entries"] == ["wordnet:run:run.v.01", "wordnet:run:run.v.26"]


def test_derived_values_the_definitions_disagree_on_stay_open_and_a_rule_conflict_is_blocked():
    row = ws.close_sense(
        "x", "verb", 0, sense(definition("a", {}, {"BIG": 1}), definition("b", {}, {"BIG": 0})), {}, []
    )
    assert "BIG" not in row["assignments"] and row["open"]["BIG"] == [0, 1]
    blocked = ws.close_sense("x", "verb", 0, sense(definition("a", {}, {"DO": 1})), {}, [NO_DO])
    assert "DO" not in blocked["assignments"] and blocked["blocked"]["DO"]["cause"] == "DERIVED_RULE_CONFLICT"


def test_derived_values_are_never_load_bearing_so_they_never_split_or_merge_senses():
    plain = definition("a", {}, {"DO": 1})
    other = definition("b", {}, {"DO": -1})
    senses = ws.collapse([plain, other])
    assert len(senses) == 1 and senses[0].members == [] and len(senses[0].absorbed) == 2


def test_a_feeling_noun_takes_no_derived_good():
    hatred = ws.Definition("n", 1, "noun", {}, {}, {}, {"GOOD": 0, "FEEL": 1})
    row = ws.close_sense("hatred", "noun", 0, ws.Sense(members=[hatred]), {}, [], feeling_noun=True)
    assert row["assignments"] == {"FEEL": 1}


def test_read_definitions_reads_only_the_cells_the_closure_settled():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        "CREATE TABLE lexemes (id INTEGER, lemma TEXT, pos TEXT);"
        "CREATE TABLE definition_states (entry_id TEXT, lexeme_id INTEGER, trace TEXT);"
        "CREATE TABLE primitive_values (lexeme_id INTEGER, primitive TEXT, value INTEGER);"
        "INSERT INTO lexemes VALUES (1, 'run', 'verb');"
        "INSERT INTO definition_states VALUES ('wordnet:run:run.v.01', 1, '[]');"
        "INSERT INTO primitive_values VALUES (1, 'GOOD', 0);"
    )
    assert ws.read_definitions(conn, "run", {})["verb"][0].derived == {}  # no closure table: nothing derived
    conn.execute("CREATE TABLE genus_differentia_closure (entry_id TEXT PRIMARY KEY, settled TEXT)")
    conn.execute(
        "INSERT INTO genus_differentia_closure VALUES (?, ?)", ("wordnet:run:run.v.01", json.dumps({"MOVE": 1}))
    )
    assert ws.read_definitions(conn, "run", {})["verb"][0].derived == {"MOVE": 1}
