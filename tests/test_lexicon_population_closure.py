"""The population state and its closure (rebuild-lexicon-symbolic-closure tasks 2.1 and 2.3).

The relations here are written for the test; they are not lexical laws.
"""

from __future__ import annotations

import numpy as np
import pytest

from GSE.curation.lexicon_builder import cells
from GSE.curation.lexicon_builder.cells import NEG, POS, SILENT, ZERO, State
from GSE.curation.lexicon_builder.closure import Derivations, close
from GSE.curation.lexicon_builder.relations import at_least_one, excludes, from_predicate, implies, states


def _state(n=3):
    return State.opening([f"r{i}" for i in range(n)])


def _set(state, row, bank, value):
    state.masks[row, cells.BANK_INDEX[bank]] = cells.bit(value)


def _get(state, row, bank):
    return int(state.masks[row, cells.BANK_INDEX[bank]])


def test_the_four_states_round_trip_and_the_census_accounts_for_every_cell():
    s = _state(1)
    _set(s, 0, "GOOD", +1)
    _set(s, 0, "BIG", -1)
    _set(s, 0, "FEEL", 0)
    _set(s, 0, "SEE", "SILENT")
    s.masks[0, cells.BANK_INDEX["HEAR"]] = 0
    c = s.census()
    assert (c["+1"], c["-1"], c["0"], c["SILENT"], c["conflict"]) == (1, 1, 1, 1, 1)
    assert c["+1"] + c["-1"] + c["0"] + c["SILENT"] + c["residual"] + c["conflict"] == c["cells"] == 56


def test_an_unpaired_bank_cannot_start_negative_and_a_bipolar_bank_can():
    s = _state(1)
    assert not _get(s, 0, "FEEL") & NEG
    assert _get(s, 0, "GOOD") & NEG


def test_a_single_bank_consequence_fires_only_in_scope():
    s = _state(2)
    _set(s, 0, "SOMEONE", +1)
    _set(s, 1, "SOMEONE", +1)
    rel = implies("t:someone-alive", "SOMEONE", POS, "ALIVE", POS, "test", scope="people")
    close(s, [rel], {"people": np.array([True, False])})
    assert _get(s, 0, "ALIVE") == POS
    assert _get(s, 1, "ALIVE") != POS


def test_two_premises_together_remove_a_state_neither_removes_alone():
    # BODY is 0 when both QUANTITY is +1 and WANT is 0 (the shape of the conventional-duration rule).
    rel = from_predicate(
        "t:duration-body",
        ("QUANTITY", "WANT", "BODY"),
        lambda q, w, b: not (q & POS and w & ZERO) or bool(b & ZERO),
        "test",
    )
    one = _state(1)
    _set(one, 0, "QUANTITY", +1)
    close(one, [rel])
    assert _get(one, 0, "BODY") & POS
    both = _state(1)
    _set(both, 0, "QUANTITY", +1)
    _set(both, 0, "WANT", 0)
    close(both, [rel])
    assert _get(both, 0, "BODY") == ZERO


def test_a_value_that_must_go_somewhere_is_forced_where_it_alone_fits():
    s = _state(1)
    _set(s, 0, "SEE", 0)
    _set(s, 0, "HEAR", "SILENT")
    rel = at_least_one("t:some-sense", ("SEE", "HEAR", "TOUCH"), POS, "test")
    close(s, [rel])
    assert _get(s, 0, "TOUCH") == POS


def test_closure_is_independent_of_order_and_records_every_removal():
    rels = [
        implies("t:a", "FEEL", POS, "ALIVE", POS, "test"),
        excludes("t:b", "GOOD", POS | NEG, "BIG", POS | NEG, "test"),
        implies("t:c", "ALIVE", POS, "BODY", POS | ZERO, "test"),
        at_least_one("t:d", ("GOOD", "BIG"), POS | NEG, "test"),
    ]
    results = []
    for order in (rels, rels[::-1], rels[1:] + rels[:1]):
        s = _state(2)
        _set(s, 0, "FEEL", +1)
        _set(s, 1, "BIG", +1)
        d = Derivations()
        close(s, order, derivations=d)
        results.append(s.masks.copy())
        before = _state(2).masks
        before[0, cells.BANK_INDEX["FEEL"]] = POS
        before[1, cells.BANK_INDEX["BIG"]] = POS
        removed = (before & ~s.masks).astype(np.uint8)
        a = d.arrays()
        recorded = np.zeros_like(removed)
        np.bitwise_or.at(recorded, (a["rows"], a["cols"]), a["removed"])
        assert (recorded == removed).all()
    assert all((r == results[0]).all() for r in results)


def test_a_conflicted_reading_is_left_alone_and_bits_fall():
    s = _state(2)
    s.masks[0, cells.BANK_INDEX["FEEL"]] = 0
    _set(s, 1, "FEEL", +1)
    rel = implies("t:a", "FEEL", POS, "ALIVE", POS, "test")
    receipt = close(s, [rel])
    assert _get(s, 0, "ALIVE") == int(cells.START[cells.BANK_INDEX["ALIVE"]])
    assert _get(s, 1, "ALIVE") == POS
    assert receipt["bits_after"] < receipt["bits_before"]


def test_an_unknown_scope_is_refused():
    with pytest.raises(ValueError, match="UNKNOWN_SCOPES"):
        close(_state(1), [implies("t", "FEEL", POS, "ALIVE", POS, "test", scope="nowhere")])


def test_states_builds_masks():
    assert states(+1, 0) == POS | ZERO
    assert states("SILENT") == SILENT
