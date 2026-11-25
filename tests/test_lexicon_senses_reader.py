"""The runtime reads a word's senses (founder correction, lexicon FC-6)."""

from __future__ import annotations

import json
import sqlite3

from GSE.lexicon.senses import read_senses


def _lexicon(rows):
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE word_senses (lemma TEXT, pos TEXT, sense INTEGER, code TEXT, core TEXT, members TEXT,"
        " absorbed TEXT, assignments TEXT, open TEXT, provenance TEXT, blocked TEXT)"
    )
    for lemma, pos, sense, assignments, open_, members in rows:
        conn.execute(
            "INSERT INTO word_senses VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                lemma,
                pos,
                sense,
                "PARTIAL",
                "{}",
                json.dumps(members),
                "[]",
                json.dumps(assignments),
                json.dumps(open_),
                "{}",
                "{}",
            ),
        )
    return conn


DOG = [
    ("dog", "noun", 0, {"ALIVE": 1, "SOMETHING": 1, "BODY": 1}, {}, ["wordnet:dog:dog.n.01"]),
    ("dog", "noun", 1, {"ALIVE": 1, "SOMETHING": 1, "SOMEONE": 1}, {}, ["wordnet:dog:chap.n.01"]),
    ("dog", "verb", 0, {"MOVE": 1}, {}, ["wordnet:dog:chase.v.01"]),
]


def test_a_lexicon_without_senses_keeps_its_old_behaviour():
    assert read_senses(sqlite3.connect(":memory:"), "dog", "NOUN") is None


def test_the_sentences_part_of_speech_selects_the_senses():
    reading = read_senses(_lexicon(DOG), "dog", "VERB")
    assert reading["pos"] == "verb" and reading["assignments"] == {"MOVE": 1}


def test_the_reading_is_the_main_sense_with_the_others_as_alternatives():
    reading = read_senses(_lexicon(DOG), "dog", "NOUN")
    assert reading["assignments"] == {"ALIVE": 1, "SOMETHING": 1, "BODY": 1}
    assert reading["alternatives"] == [{"sense": 1, "assignments": {"ALIVE": 1, "SOMETHING": 1, "SOMEONE": 1}}]


def test_banks_where_another_sense_differs_carry_their_possible_signs():
    rows = [
        ("fair", "adj", 0, {"GOOD": 1}, {}, ["a"]),
        ("fair", "adj", 1, {"GOOD": 0}, {}, ["b"]),
    ]
    reading = read_senses(_lexicon(rows), "fair", "ADJ")
    assert reading["assignments"] == {"GOOD": 1} and reading["differs"] == {"GOOD": [0, 1]}


def test_an_identified_definition_reads_its_own_sense():
    reading = read_senses(_lexicon(DOG), "dog", "NOUN", entry_id="wordnet:dog:chap.n.01")
    assert reading["assignments"]["SOMEONE"] == 1 and reading["basis"] == "IDENTIFIED_DEFINITION"


def test_an_unknown_part_of_speech_falls_back_to_the_dominant_one():
    reading = read_senses(_lexicon(DOG), "dog", None)
    assert reading["pos"] == "noun" and reading["basis"] == "DOMINANT_PART_OF_SPEECH"
