"""The closed-class layer puts grammatical words in their documented homes (#8, #9)."""

import shutil
import sqlite3
from pathlib import Path

import pytest

from gse.curation import build_clean_closed_class as cc

LEXICON = Path(__file__).resolve().parents[1] / "data" / "lexicon_clean.db"


def _primes(con, word):
    row = con.execute("SELECT id FROM lexemes WHERE lemma=?", (word,)).fetchone()
    if row is None:
        return None
    return dict(con.execute("SELECT primitive, value FROM primitive_values WHERE lexeme_id=?", (row[0],)).fetchall())


@pytest.mark.parametrize(
    "has_row, current, target, expected",
    [
        (False, {}, {}, "keep"),
        (False, {}, {"SOMEONE": 1}, "add"),
        (True, {"SOMEONE": 1}, {"SOMEONE": 1}, "keep"),
        (True, {"SOMETHING": 1}, {"SOMEONE": 1}, "set"),
        (True, {"SOMETHING": 1}, {}, "clear"),
        (True, {}, {}, "keep"),
    ],
)
def test_action(has_row, current, target, expected):
    assert cc.action(has_row, current, target) == expected


def test_targets_keep_the_held_words_out_and_zero_words_empty():
    t = cc.targets()
    assert not (cc.HELD & t.keys())
    assert all(t[w] == {} for w in cc.ZERO)
    assert t["she"] == {"SOMEONE": 1} and t["itself"] == {"SOMETHING": 1}
    assert t["cannot"] == {"CAN": 1, "NOT": 1}


@pytest.fixture
def lexicon_copy(tmp_path):
    copy = tmp_path / "lexicon_clean.db"
    shutil.copy(LEXICON, copy)
    return copy


def test_layer_on_a_copy_of_the_lexicon_then_a_second_run_changes_nothing(lexicon_copy):
    cc.main(str(lexicon_copy))
    con = sqlite3.connect(lexicon_copy)
    assert _primes(con, "he") == {"SOMEONE": 1}
    assert _primes(con, "she") == {"SOMEONE": 1}
    assert _primes(con, "are") == {"BE": 1}
    assert _primes(con, "does") == {"DO": 1}
    assert _primes(con, "like") == {"LIKE": 1}
    assert _primes(con, "however") == {}  # cleared, row kept for the spellchecker
    assert _primes(con, "that") is None  # held: no row added
    assert _primes(con, "i") == {"I": 1}  # held: tier-0 untouched
    con.close()
    assert cc.main(str(lexicon_copy)) == {"keep": len(cc.targets())}


def test_the_built_lexicon_carries_the_layer():
    """Pins data/lexicon_clean.db itself: the build ran the closed-class layer last."""
    from gse.api import GSEEncoder

    enc = GSEEncoder()
    prims = {t.token: t.word_primitives for t in enc.encode("She saw him in the box.").tokens}
    assert prims["She"] == {"SOMEONE": 1}
    assert prims["him"] == {"SOMEONE": 1}
    assert prims["in"] == {}
    he = {t.token: t.word_primitives for t in enc.encode("He killed the king.").tokens}["He"]
    assert he == {"SOMEONE": 1}
