"""Coherence among independent sources (rebuild-lexicon-symbolic-closure task 8.1).

Every population here is written for the test. The banks are real bank names, but the facts are not lexical
claims.
"""

from __future__ import annotations

import numpy as np
import pytest

from GSE.curation.lexicon_builder.cells import BANK_INDEX, POS, SILENT, START, ZERO, State
from GSE.curation.lexicon_builder.coherence import (
    Candidate,
    Derivation,
    Observation,
    Types,
    apply,
    evidence,
    identity_root,
    near_miss_conjunctions,
    pair_candidates,
    settle,
)


def _readings(n):
    return tuple(f"t:{i}" for i in range(n))


def _obs(row, bank, states, root, generalizes=True):
    return Observation(f"t:{row}", bank, states, "test", root, generalizes)


def test_agreeing_sources_settle_their_intersection_and_disagreement_is_a_conflict_that_changes_nothing():
    readings = _readings(2)
    s = settle(
        [
            _obs(0, "FEEL", POS | ZERO, "a"),
            _obs(0, "FEEL", POS, "b"),
            _obs(1, "FEEL", POS, "a"),
            _obs(1, "FEEL", ZERO, "b"),
        ],
        readings,
    )
    assert s.stated.within("FEEL", POS).tolist() == [0]
    (conflict,) = s.conflicts
    assert (conflict.reading, conflict.bank, conflict.roots) == ("t:1", "FEEL", ("a", "b"))
    state = State.opening(readings)
    apply(state, s)
    assert state.masks[0, BANK_INDEX["FEEL"]] == POS
    assert state.masks[1, BANK_INDEX["FEEL"]] == START[BANK_INDEX["FEEL"]]
    assert 1 not in s.stated.stated("FEEL").tolist()


def test_a_derivation_cannot_enter_the_postings():
    with pytest.raises(TypeError, match="STATED_OBSERVATIONS_ONLY"):
        settle([Derivation("t:0", "ALIVE", POS, "law:x")], _readings(1))


def test_a_derivation_that_contradicts_a_stated_cell_is_a_conflict_and_the_cell_is_left_alone():
    readings = _readings(1)
    s = settle([_obs(0, "SOMEONE", POS, "row")], readings)
    state = State.opening(readings)
    (conflict,) = apply(state, s, [Derivation("t:0", "SOMEONE", ZERO, "law:no-substantive", ("row",))])
    assert conflict.rules == ("law:no-substantive",) and conflict.roots == ("row",)
    assert state.masks[0, BANK_INDEX["SOMEONE"]] == START[BANK_INDEX["SOMEONE"]]


def test_a_stated_cell_in_conflict_with_a_derivation_neither_confirms_nor_refutes():
    readings = _readings(2)
    s = settle(
        [_obs(0, "SOMETHING", POS, "wordnet:x"), _obs(0, "BODY", POS, "profile:x"), _obs(1, "SOMETHING", POS, "w1")],
        readings,
    )
    types = Types.build(2, {"t:entity": np.arange(2)})
    cand = Candidate((("SOMETHING", POS),), "BODY", POS, ("t:entity",))
    assert evidence(cand, s, types).witnesses.tolist() == [0]
    state = State.opening(readings)
    conflicts = apply(state, s, [Derivation("t:0", "SOMETHING", ZERO, "law:one-hot", ("profile:x",))])
    s = s.excluding(conflicts)
    ev = evidence(cand, s, types)
    assert not ev.witnesses.size and 0 not in ev.antecedent.tolist()
    assert 0 not in s.stated.stated("SOMETHING").tolist()


def test_duplicate_roots_count_once():
    readings = _readings(1)
    s = settle([_obs(0, "FEEL", POS, "row"), _obs(0, "FEEL", POS, "row")], readings)
    assert s.roots_of(0, BANK_INDEX["FEEL"]) == ("row",)
    col = s.stated.column("FEEL")
    assert col.lo.tolist() == col.hi.tolist()


def test_one_record_stating_both_banks_does_not_confirm_their_relation_and_an_independent_root_does():
    readings = _readings(2)
    types = Types.build(2, {"t:modal": np.array([0, 1])})
    cand = Candidate((("CAN", POS),), "NOT", POS, ("t:modal",))
    one_row = settle([_obs(0, "CAN", POS, "catalog:cannot"), _obs(0, "NOT", POS, "catalog:cannot")], readings)
    ev = evidence(cand, one_row, types)
    assert not ev.witnesses.size and ev.co_encoded.tolist() == [0]
    two = settle(
        [
            _obs(0, "CAN", POS, "catalog:cannot"),
            _obs(0, "NOT", POS, "catalog:cannot"),
            _obs(0, "NOT", POS, "profile:cannot"),
        ],
        readings,
    )
    ev = evidence(cand, two, types)
    assert ev.witnesses.tolist() == [0] and not ev.co_encoded.size


def test_unknowns_are_neither_confirmations_nor_counterexamples():
    readings = _readings(3)
    s = settle(
        [
            _obs(0, "MOVE", POS, "a0"),
            _obs(0, "ALIVE", POS, "b0"),
            _obs(1, "MOVE", POS, "a1"),
            _obs(2, "ALIVE", POS, "b2"),
        ],
        readings,
    )
    types = Types.build(3, {"t:animal": np.arange(3)})
    ev = evidence(Candidate((("MOVE", POS),), "ALIVE", POS, ("t:animal",)), s, types)
    assert ev.witnesses.tolist() == [0]
    assert ev.unknown.tolist() == [1]
    assert not ev.counterexamples.size
    assert not ev.exposed


def test_a_single_record_refutes_even_though_it_cannot_confirm():
    readings = _readings(2)
    s = settle(
        [
            _obs(0, "MOVE", POS, "a0"),
            _obs(0, "ALIVE", POS, "b0"),
            _obs(1, "MOVE", POS, "row1"),
            _obs(1, "ALIVE", ZERO, "row1"),
        ],
        readings,
    )
    types = Types.build(2, {"t:entity": np.arange(2)})
    ev = evidence(Candidate((("MOVE", POS),), "ALIVE", POS, ("t:entity",)), s, types)
    assert ev.counterexamples.tolist() == [1] and ev.exposed


def test_a_statement_confined_to_its_reading_refutes_but_never_confirms():
    readings = _readings(2)
    s = settle(
        [
            _obs(0, "SOMEONE", POS, "row0"),
            _obs(0, "FEEL", SILENT, "profile0", generalizes=False),
            _obs(1, "SOMEONE", POS, "row1"),
            _obs(1, "FEEL", POS, "profile1", generalizes=False),
        ],
        readings,
    )
    types = Types.build(2, {"t:prime": np.arange(2)})
    ev = evidence(Candidate((("SOMEONE", POS),), "FEEL", SILENT, ("t:prime",)), s, types)
    assert not ev.witnesses.size
    assert ev.counterexamples.tolist() == [1]


def test_the_separating_types_are_every_type_held_by_all_witnesses_and_no_counterexample():
    types = Types.build(
        6,
        {
            "t:entity": np.arange(6),
            "t:animal": np.array([0, 1, 2]),
            "t:mammal": np.array([0, 1]),
            "t:pet": np.array([1, 4]),
        },
    )
    assert types.separating(np.array([0, 1]), np.array([4])) == ("t:animal", "t:mammal")
    assert types.separating(np.array([0, 1]), np.array([2])) == ("t:mammal",)
    assert types.separating(np.array([1]), np.array([4])) == ("t:animal", "t:mammal")


def test_pair_candidates_pose_each_stated_pair_in_each_type_holding_a_witness():
    readings = _readings(3)
    s = settle(
        [
            _obs(0, "MOVE", POS, "a0"),
            _obs(0, "ALIVE", POS, "b0"),
            _obs(1, "MOVE", POS, "a1"),
            _obs(2, "MOVE", POS, "a2"),
            _obs(2, "ALIVE", ZERO, "b2"),
        ],
        readings,
    )
    types = Types.build(3, {"t:entity": np.arange(3), "t:animal": np.array([0, 1])})
    ids = {c.rule_id for c in pair_candidates(s, types)}
    assert "coherence:implication:[t:animal]:MOVE{+1}=>ALIVE{+1}" in ids
    assert "coherence:implication:[t:entity]:MOVE{+1}=>ALIVE{+1}" in ids
    assert "coherence:implication:[t:entity]:MOVE{+1}=>ALIVE{+1|0}" in ids


def test_a_near_miss_seeds_the_conjunction_its_witnesses_share():
    readings = _readings(3)
    s = settle(
        [
            _obs(0, "MOVE", POS, "a0"),
            _obs(0, "ALIVE", POS, "b0"),
            _obs(0, "FEEL", POS, "c0"),
            _obs(1, "MOVE", POS, "a1"),
            _obs(1, "ALIVE", ZERO, "b1"),
            _obs(1, "FEEL", ZERO, "c1"),
        ],
        readings,
    )
    types = Types.build(3, {"t:entity": np.arange(3)})
    cand = Candidate((("MOVE", POS),), "ALIVE", POS, ("t:entity",))
    (conj,) = near_miss_conjunctions(cand, evidence(cand, s, types), s)
    assert conj.if_terms == (("MOVE", POS), ("FEEL", POS))
    ev = evidence(conj, s, types)
    assert ev.witnesses.tolist() == [0] and not ev.counterexamples.size


def test_identity_root_of_a_wordnet_reading_is_its_synset():
    assert identity_root("wordnet:domestic_dog:dog.n.01") == "wordnet:dog.n.01"
    assert identity_root("gse_closed_class:modal:cannot") == "gse_closed_class:modal:cannot"


def test_an_observation_outside_the_banks_legal_states_is_refused():
    with pytest.raises(ValueError, match="ILLEGAL"):
        Observation("t:0", "FEEL", 2, "test", "row")
