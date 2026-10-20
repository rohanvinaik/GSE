"""GSE #66: the periphrastic modals carry the primes ``docs/NSM_GRAMMAR_MAPPING.md`` routes them through.

Through the real entry point (the encoder), a modal auxiliary's word primitives: could -> CAN (can's past and
conditional form), should -> MUST (the weak deontic), would -> MAYBE (the hypothetical), and shall, a
future like will, informational zero. may, might, can and must keep the primes they already had.
"""

import logging
import sqlite3

import pytest

from gse.api import GSEEncoder
from gse.curation.build_clean_closed_class import CLEAN_DB, plan, targets


@pytest.fixture(scope="module")
def encoder():
    logging.disable(logging.CRITICAL)
    yield GSEEncoder()
    logging.disable(logging.NOTSET)


@pytest.mark.parametrize(
    ("sentence", "word", "primes"),
    [
        ("We could test this claim.", "could", {"CAN": 1}),
        ("You should read the paper.", "should", {"MUST": 1}),
        ("It would help the reader.", "would", {"MAYBE": 1}),
        ("We shall see the result.", "shall", {}),
        ("It might help the reader.", "might", {"MAYBE": 1}),
        ("It may help the reader.", "may", {"MAYBE": 1}),
        ("We can test this claim.", "can", {"CAN": 1}),
        ("We must test this claim.", "must", {"MUST": 1}),
    ],
)
def test_table_modal_primes_through_the_encoder(encoder, sentence, word, primes):
    tokens = [t for t in encoder.encode(sentence).tokens if t.token == word]
    assert tokens, f"{word!r} not tokenized in {sentence!r}"
    assert tokens[0].pos == "AUX"
    assert dict(tokens[0].word_primitives) == primes


def test_table_the_layer_routes_the_modals():
    owned = targets()
    assert owned["could"] == {"CAN": 1}
    assert owned["should"] == {"MUST": 1}
    assert owned["would"] == {"MAYBE": 1}
    assert owned["shall"] == {}


def test_guard_the_built_lexicon_needs_no_further_step():
    con = sqlite3.connect(CLEAN_DB)
    try:
        pending = [(word, act) for word, act, _current, _target in plan(con) if act != "keep"]
    finally:
        con.close()
    assert pending == []
