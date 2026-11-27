"""Word-level obligations (rebuild-lexicon-symbolic-closure, F073: a value that must go somewhere).

The obligations here are written for the test; they are not source facts.
"""

from __future__ import annotations

import numpy as np

from GSE.curation.lexicon_builder import cells
from GSE.curation.lexicon_builder.cells import NEG, POS, SILENT, ZERO, State
from GSE.curation.lexicon_builder.obligations import (
    ALL_EXCLUDED,
    DISJOINT_FORCINGS,
    Batch,
    Obligation,
    force,
    wake,
)

B = cells.BANK_INDEX


def _state(n):
    return State.opening([f"r{i}" for i in range(n)])


def _set(state, row, bank, value):
    state.masks[row, B[bank]] = cells.bit(value)


def _get(state, row, bank):
    return int(state.masks[row, B[bank]])


def test_the_last_reading_not_excluded_is_forced():
    s = _state(3)
    _set(s, 0, "MOVE", 0)
    _set(s, 1, "MOVE", "SILENT")
    out = force(s, Batch.of([Obligation("t:one-moves", "MOVE", POS, np.array([0, 1, 2]))]))
    assert _get(s, 2, "MOVE") == POS
    assert (out.rows.tolist(), out.cols.tolist(), out.by.tolist()) == ([2], [B["MOVE"]], [0])
    assert out.new.tolist() == [POS] and out.old.tolist() == [int(cells.START[B["MOVE"]])]
    assert out.conflicts.size == 0


def test_every_reading_excluded_is_a_conflict_and_no_mask_changes():
    s = _state(2)
    _set(s, 0, "GOOD", -1)
    _set(s, 1, "GOOD", 0)
    before = s.masks.copy()
    batch = Batch.of([Obligation("t:one-good", "GOOD", POS, [0, 1])])
    out = force(s, batch)
    assert (s.masks == before).all() and out.changed == 0
    assert out.conflicts.tolist() == [0] and out.reasons.tolist() == [ALL_EXCLUDED]
    assert out.described(batch, s)[0]["readings"] == ["r0", "r1"]


def test_nothing_changes_while_two_readings_still_allow_the_states():
    s = _state(3)
    _set(s, 0, "FEEL", 0)
    before = s.masks.copy()
    out = force(s, Batch.of([Obligation("t:one-feels", "FEEL", POS, [0, 1, 2])]))
    assert (s.masks == before).all() and out.changed == 0 and out.conflicts.size == 0


def test_a_batch_is_applied_at_once_and_disjoint_forcings_on_one_cell_are_both_conflicts():
    s = _state(6)
    _set(s, 0, "BIG", 0)
    _set(s, 2, "BIG", 0)
    _set(s, 4, "SEE", 0)
    s.masks[5, B["HEAR"]] = 0  # a conflicted cell
    batch = Batch.of(
        [
            Obligation("t:big", "BIG", POS, [0, 1]),  # forces r1 BIG +1 ...
            Obligation("t:small", "BIG", NEG, [2, 1]),  # ... and r1 BIG -1: disjoint, no write
            Obligation("t:see", "SEE", POS | SILENT, [3, 4]),  # forces r3 SEE to {+1, SILENT}
            Obligation("t:hear", "HEAR", POS, [5, 3]),  # over a conflicted cell: left alone
            Obligation("t:same", "BIG", POS | ZERO, [1, 1]),  # duplicate rows are one reading
        ]
    )
    out = force(s, batch)
    assert _get(s, 1, "BIG") == int(cells.START[B["BIG"]])
    assert _get(s, 3, "SEE") == POS | SILENT
    assert _get(s, 3, "HEAR") == int(cells.START[B["HEAR"]])
    assert dict(zip(out.conflicts.tolist(), out.reasons.tolist())) == {
        0: DISJOINT_FORCINGS,
        1: DISJOINT_FORCINGS,
        4: DISJOINT_FORCINGS,
    }
    assert out.blocked.tolist() == [3]
    assert (out.rows.tolist(), out.cols.tolist()) == ([3], [B["SEE"]])


def test_an_obligation_over_no_reading_is_a_conflict():
    s = _state(1)
    out = force(s, Batch.of([Obligation("t:none", "MOVE", POS, np.zeros(0, dtype=np.int64))]))
    assert out.conflicts.tolist() == [0] and out.reasons.tolist() == [ALL_EXCLUDED]


def test_obligations_sharing_a_witness_are_satisfied_by_one_reading():
    # One source observation: one of the two readings is bad (GOOD -1) AND thinks (THINK +1).
    s = _state(2)
    _set(s, 0, "THINK", 0)
    together = [
        Obligation("t:bad", "GOOD", NEG, [0, 1], witness=7),
        Obligation("t:thinks", "THINK", POS, [0, 1], witness=7),
    ]
    out = force(s, Batch.of(together))
    assert (_get(s, 1, "GOOD"), _get(s, 1, "THINK")) == (NEG, POS)
    assert sorted(out.by.tolist()) == [0, 1]
    apart = _state(2)
    _set(apart, 0, "THINK", 0)
    force(apart, Batch.of([Obligation(o.rule_id, o.bank, o.allowed, o.rows) for o in together]))
    assert _get(apart, 1, "GOOD") == int(cells.START[B["GOOD"]])
    assert _get(apart, 1, "THINK") == POS


def test_a_joint_group_is_forced_onto_the_one_reading_that_allows_all_of_it_and_returns_its_facts():
    # "happy (adj) is GOOD +1 and FEEL +1": some reading has both. r0 cannot be GOOD +1, r1 cannot feel; only r2
    # allows both, so the group is located on r2, though r0 and r1 each allow one of its banks.
    s = _state(3)
    _set(s, 0, "GOOD", 0)
    _set(s, 1, "FEEL", 0)
    group = [
        Obligation(
            "t:good",
            "GOOD",
            POS,
            [0, 1, 2],
            witness=1,
            premises=("usas:happy",),
            facts=("own_semantic_kind=evaluator",),
        ),
        Obligation("t:feel", "FEEL", POS, [0, 1, 2], witness=1, premises=("usas:happy",)),
    ]
    out = force(s, Batch.of(group))
    assert (_get(s, 2, "GOOD"), _get(s, 2, "FEEL")) == (POS, POS)
    assert _get(s, 0, "FEEL") == int(cells.START[B["FEEL"]]) and _get(s, 1, "GOOD") == int(cells.START[B["GOOD"]])
    assert out.located_rows.tolist() == [2]
    assert {k: v.tolist() for k, v in out.facts.items()} == {"own_semantic_kind=evaluator": [2]}
    # Without the witness each obligation still has two readings open, and nothing is forced or located.
    apart = _state(3)
    _set(apart, 0, "GOOD", 0)
    _set(apart, 1, "FEEL", 0)
    lone = force(apart, Batch.of([Obligation(o.rule_id, o.bank, o.allowed, o.rows, facts=o.facts) for o in group]))
    assert lone.changed == 0 and lone.located_rows.size == 0 and lone.facts == {}


def test_a_group_no_reading_can_satisfy_jointly_is_a_conflict_without_facts():
    s = _state(2)
    _set(s, 0, "GOOD", 0)
    _set(s, 1, "FEEL", 0)
    before = s.masks.copy()
    group = [
        Obligation("t:good", "GOOD", POS, [0, 1], witness=3, facts=("own_semantic_kind=evaluator",)),
        Obligation("t:feel", "FEEL", POS, [0, 1], witness=3),
    ]
    out = force(s, Batch.of(group))
    assert (s.masks == before).all() and out.facts == {}
    assert out.conflicts.tolist() == [0, 1] and out.reasons.tolist() == [ALL_EXCLUDED, ALL_EXCLUDED]


def test_one_group_requiring_disjoint_states_on_one_bank_excludes_every_reading():
    s = _state(2)
    group = [Obligation("t:a", "GOOD", POS, [0, 1], witness=4), Obligation("t:b", "GOOD", NEG, [0, 1], witness=4)]
    out = force(s, Batch.of(group))
    assert out.changed == 0 and out.conflicts.tolist() == [0, 1]


def test_wake_adds_located_facts_to_single_and_conjunctive_scopes():
    scopes = {
        "own_semantic_kind=evaluator": np.array([False, False, False]),
        "own_role=lexical_predicate": np.array([False, True, False]),
        "own_role=lexical_predicate&own_semantic_kind=evaluator": np.array([False, False, False]),
    }
    added = wake(scopes, {"own_semantic_kind=evaluator": np.array([1, 2])})
    assert scopes["own_semantic_kind=evaluator"].tolist() == [False, True, True]
    assert scopes["own_role=lexical_predicate&own_semantic_kind=evaluator"].tolist() == [False, True, False]
    assert added == 3 and wake(scopes, {"own_semantic_kind=evaluator": np.array([1, 2])}) == 0


def test_the_source_lenses_produce_this_obligation_type():
    from GSE.curation.lexicon_builder import obligations, projection

    assert projection.Obligation is obligations.Obligation


def test_no_facts_are_acquired_while_two_readings_can_still_satisfy_the_group():
    s = _state(3)
    _set(s, 0, "GOOD", 0)  # r1 and r2 both still allow GOOD +1 and FEEL +1
    before = s.masks.copy()
    group = [
        Obligation("t:good", "GOOD", POS, [0, 1, 2], witness=5, facts=("own_semantic_kind=evaluator",)),
        Obligation("t:feel", "FEEL", POS, [0, 1, 2], witness=5),
    ]
    out = force(s, Batch.of(group))
    assert (s.masks == before).all() and out.located_rows.size == 0 and out.facts == {}
    assert out.conflicts.size == 0
