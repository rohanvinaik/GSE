"""Orthogonal cells (`orthogonality.py`; Rohan 2026-11-25 17:56). The relations and readings are written for the test;
they are not lexical laws."""

from __future__ import annotations

import numpy as np

from GSE.curation.lexicon_builder import cells, orthogonality
from GSE.curation.lexicon_builder import inheritance as inh
from GSE.curation.lexicon_builder.cells import NEG, POS, SILENT, ZERO, State
from GSE.curation.lexicon_builder.closure import Derivations, close
from GSE.curation.lexicon_builder.obligations import Batch, Obligation
from GSE.curation.lexicon_builder.relations import Relation, excludes, implies

B = cells.BANK_INDEX
# Written for the test: a reading that feels nothing (FEEL 0) has no content on SEE.
NO_SEEING = excludes("t:no-seeing", "FEEL", ZERO, "SEE", POS | NEG, "test")


def _state(n):
    return State.opening([f"r{i}" for i in range(n)])


def _get(state, row, bank):
    return int(state.masks[row, B[bank]])


def _closed(n=2):
    s = _state(n)
    s.masks[0, B["FEEL"]] = ZERO
    close(s, [NO_SEEING])
    return s


def test_content_eliminated_by_a_relation_becomes_zero_and_is_recorded():
    s = _closed()
    assert _get(s, 0, "SEE") == ZERO | SILENT
    record = Derivations()
    out = orthogonality.apply(s, [NO_SEEING], derivations=record)
    assert _get(s, 0, "SEE") == ZERO and out["cells"] == 1
    arrays = record.arrays()
    assert arrays["rule_ids"][arrays["rules"]].tolist() == ["orthogonal"]
    assert (arrays["rows"].tolist(), arrays["cols"].tolist(), arrays["removed"].tolist()) == ([0], [B["SEE"]], [SILENT])


def test_a_cell_whose_content_is_still_legal_is_untouched():
    s = _closed()
    before = s.masks.copy()
    orthogonality.apply(s, [NO_SEEING])
    changed = np.argwhere(s.masks != before).tolist()
    assert changed == [[0, B["SEE"]]]  # every other cell, row 1 included, keeps its content states
    assert _get(s, 1, "SEE") == int(cells.START[B["SEE"]])


def test_an_unpaired_bank_at_its_starting_mask_is_untouched():
    s = _state(1)
    assert int(cells.START[B["MOVE"]]) == POS | ZERO | SILENT
    assert orthogonality.orthogonal(s)[0].size == 0


def test_a_warranted_silence_stays_silent():
    s = _closed()
    s.masks[1, B["HEAR"]] = SILENT  # a decided silence is never touched
    warranted = np.zeros(s.masks.shape, dtype=bool)
    warranted[0, B["SEE"]] = True  # a silence warrant covers the orthogonal cell
    out = orthogonality.apply(s, [NO_SEEING], silence_warranted=warranted)
    assert out["cells"] == 0
    assert _get(s, 0, "SEE") == ZERO | SILENT and _get(s, 1, "HEAR") == SILENT


def test_a_zero_written_wakes_the_laws():
    then_no_hearing = implies("t:then-no-hearing", "SEE", ZERO, "HEAR", ZERO, "test")
    s = _closed()
    close(s, [NO_SEEING, then_no_hearing])
    orthogonality.apply(s, [NO_SEEING, then_no_hearing])
    assert _get(s, 0, "SEE") == ZERO and _get(s, 0, "HEAR") == ZERO


def test_silence_warrants_come_from_authored_domains_and_silent_obligations():
    domain = Relation("t:domain", ("TOUCH",), ((ZERO,), (SILENT,)), "test", scope="some")
    open_domain = Relation("t:open", ("TOUCH",), ((POS,), (ZERO,), (SILENT,)), "test")
    batch = Batch.of([Obligation("t:nsm-silence", "WANT", SILENT, [2, 3])])
    scopes = {"some": np.array([True, False, False, False])}
    out = orthogonality.silence_warrants(4, [domain, open_domain, NO_SEEING], scopes, batch)
    assert np.argwhere(out).tolist() == [[0, B["TOUCH"]], [2, B["WANT"]], [3, B["WANT"]]]


def test_both_layers_keep_their_standing_and_a_known_zero_suspends_an_interpolated_silence():
    # r0 (node a) has SEE content eliminated in the known layer; r1 (node w) is SILENT on SEE, and a proposed
    # alignment carries that SILENT onto r0 in the interpolated layer only. r2 loses SEE content only by interpolation.
    s = _state(3)
    s.masks[0, B["FEEL"]] = ZERO
    s.masks[1, B["SEE"]] = SILENT
    s.masks[2, B["SEE"]] = POS | ZERO | SILENT
    graph = inh.build(
        {"a": [0], "w": [1], "z": [2], "hub": []},
        [("aligned", "w", "a"), ("aligned", "a", "w")],
    )
    settled = inh.settle(s, graph, relations=[NO_SEEING], classes=np.array([0, 0, 2]))
    assert _get(settled.known, 0, "SEE") == ZERO | SILENT and _get(settled.state, 0, "SEE") == SILENT
    settled.state.masks[2, B["SEE"]] = ZERO | SILENT  # as if a default had eliminated its content
    out = orthogonality.apply_settlement(settled, [NO_SEEING])
    assert _get(settled.known, 0, "SEE") == ZERO and _get(settled.state, 0, "SEE") == ZERO
    assert [r.tolist() for r in out["interpolated_suspended"]] == [[0], [B["SEE"]]]
    assert _get(settled.known, 2, "SEE") == POS | ZERO | SILENT and _get(settled.state, 2, "SEE") == ZERO
    summary = orthogonality.summary(out["known"], [type("R", (), {"pos": "noun"})()] * 3)
    assert summary == {"cells": 1, "by_bank": {"SEE": 1}, "by_pos": {"noun": 1}}
