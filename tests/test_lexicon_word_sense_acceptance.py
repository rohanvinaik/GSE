"""Acceptance for the founder-corrected lexicon (openspec lexicon-symbolic-foundation, FC-4).

The expected banks below were written before the build ran, in Rohan's acceptance order (F070:
"demonstrate complete encoding of a few clear and obvious words" first). Each is a word's
obvious meaning on its load-bearing banks. The negatives guard against the failures the
correction names: blanket signs, signed function words, changed resolved values, proper names.

They read the built word-sense table of a release candidate, named by ``GSE_SENSE_CANDIDATE``,
and skip when none is built; the release is local data, not part of a checkout.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

CANDIDATE = os.environ.get("GSE_SENSE_CANDIDATE", "")

pytestmark = pytest.mark.skipif(
    not CANDIDATE or not Path(CANDIDATE).is_file(), reason="no word-sense candidate built (GSE_SENSE_CANDIDATE)"
)

# word, part of speech -> banks its primary sense must carry
EXPECTED = {
    ("happy", "adj"): {"GOOD": 1, "FEEL": 1},
    ("dog", "noun"): {"ALIVE": 1, "SOMETHING": 1},
    ("give", "verb"): {"DO": 1},
    ("big", "adj"): {"BIG": 1},
    ("mother", "noun"): {"SOMEONE": 1, "ALIVE": 1},
    ("lock", "noun"): {"SOMETHING": 1},
    ("want", "verb"): {"WANT": 1},
    ("know", "verb"): {"KNOW": 1},
}


def _senses(lemma: str, pos: str) -> list[dict]:
    with sqlite3.connect(Path(CANDIDATE).as_uri() + "?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "SELECT sense, assignments, members FROM word_senses WHERE lemma=? AND pos=? ORDER BY sense", (lemma, pos)
        ).fetchall()
    return [{"sense": s, "assignments": json.loads(a), "members": json.loads(m)} for s, a, m in rows]


@pytest.mark.parametrize(("word", "pos"), sorted(EXPECTED))
def test_obvious_word_carries_its_obvious_banks(word, pos):
    senses = _senses(word, pos)
    assert senses, f"{word} ({pos}) has no sense"
    # No sense is a default (design.md rule 3): the obvious meaning must be one of the word's coherent senses.
    expected = EXPECTED[(word, pos)]
    assert any(all(s["assignments"].get(bank) == value for bank, value in expected.items()) for s in senses), (
        f"{word} ({pos}): no sense carries {expected}"
    )


def test_nouns_keep_the_founder_evaluation_zero():
    # founder:noun-own-evaluation stays as it is until Rohan rules on F057 vs F066 (FC-7).
    for word in ("dog", "mother", "lock"):
        for sense in _senses(word, "noun"):
            assert sense["assignments"].get("GOOD") in (None, 0)


def test_function_words_gain_no_content_signs():
    with sqlite3.connect(Path(CANDIDATE).as_uri() + "?mode=ro", uri=True) as conn:
        for word in ("the", "of", "and"):
            for (assignments,) in conn.execute("SELECT assignments FROM word_senses WHERE lemma=?", (word,)):
                signed = {
                    b for b, v in json.loads(assignments).items() if v and b in {"GOOD", "FEEL", "BIG", "ALIVE", "BODY"}
                }
                assert not signed, f"{word} gained {signed}"


def test_proper_names_are_not_word_senses():
    with sqlite3.connect(Path(CANDIDATE).as_uri() + "?mode=ro", uri=True) as conn:
        assert conn.execute("SELECT COUNT(*) FROM word_senses WHERE pos='name'").fetchone()[0] == 0


def test_no_resolved_definition_value_changes():
    # Every value a member definition resolved survives unchanged in its sense's core, unless the
    # members disagree on that bank, in which case the sense carries it as contested (open).
    with sqlite3.connect(Path(CANDIDATE).as_uri() + "?mode=ro", uri=True) as conn:
        for word, pos in sorted(EXPECTED):
            for assignments, open_, members, absorbed in conn.execute(
                "SELECT assignments, open, members, absorbed FROM word_senses WHERE lemma=? AND pos=?", (word, pos)
            ):
                assignments, open_ = json.loads(assignments), json.loads(open_)
                for entry_id in json.loads(members) + json.loads(absorbed):
                    lexeme_id = conn.execute(
                        "SELECT lexeme_id FROM definition_states WHERE entry_id=?", (entry_id,)
                    ).fetchone()[0]
                    for bank, value in conn.execute(
                        "SELECT primitive, value FROM primitive_values WHERE lexeme_id=?", (lexeme_id,)
                    ):
                        if bank in open_:
                            assert value in open_[bank], f"{word} {entry_id} {bank}={value} lost"
                        else:
                            assert assignments.get(bank) == value, f"{word} {entry_id} {bank} changed"
