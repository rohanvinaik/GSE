"""Inheritance across readings (rebuild-lexicon-symbolic-closure task 6.1, design E8).

The nodes, links and relations here are written for the test; they are not lexical facts or laws. The last tests read
WordNet's own links through nltk.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from GSE.curation.lexicon_builder import cells
from GSE.curation.lexicon_builder import inheritance as inh
from GSE.curation.lexicon_builder.cells import NEG, POS, SILENT, ZERO, State
from GSE.curation.lexicon_builder.obligations import Batch, Obligation
from GSE.curation.lexicon_builder.relations import implies

B = cells.BANK_INDEX


def _state(n):
    return State.opening([f"r{i}" for i in range(n)])


def _set(state, row, bank, value):
    state.masks[row, B[bank]] = cells.bit(value)


def _get(state, row, bank):
    return int(state.masks[row, B[bank]])


def _start(bank):
    return int(cells.START[B[bank]])


def _settle(state, groups, links, **kw):
    defeaters = kw.pop("defeaters", ())
    return inh.settle(state, inh.build(groups, links, defeaters=defeaters), **kw)


def test_a_hubs_values_reach_its_kinds_through_a_synset_with_no_reading():
    # "creatures": something like this can move, can feel something (MOVE +1, FEEL +1 on the hub).
    s = _state(6)
    for bank in ("MOVE", "FEEL"):
        _set(s, 0, bank, +1)
    groups = {"hub": [0, 1], "kind": [2], "kind_of_kind": [3, 4], "elsewhere": [5]}
    links = [
        ("hypernym", "hub", "transit"),
        ("hypernym", "transit", "kind"),
        ("instance_hypernym", "kind", "kind_of_kind"),
    ]
    out = _settle(s, groups, links)
    for row in (1, 2, 3, 4):
        assert _get(out.state, row, "MOVE") == POS and _get(out.state, row, "FEEL") == POS
        assert out.interpolated[row, B["MOVE"]] and out.inherited[row, B["FEEL"]]
    assert _get(out.state, 5, "MOVE") == _start("MOVE")
    assert not out.interpolated[0].any() and not out.interpolated[5].any()
    assert _get(out.known, 2, "MOVE") == _start("MOVE")  # the known layer holds no default
    assert (s.masks[2] == cells.START).all()  # the premises are untouched


def test_a_hubs_silence_never_reaches_a_kind_and_its_explicit_zero_does():
    s = _state(2)
    _set(s, 0, "SEE", "SILENT")
    _set(s, 0, "HEAR", 0)
    out = _settle(s, {"hub": [0], "kind": [1]}, [("hypernym", "hub", "kind")])
    assert _get(out.state, 1, "SEE") == _start("SEE")
    assert _get(out.state, 1, "HEAR") == ZERO


def test_a_kind_using_a_prime_its_hub_never_mentions_does_not_inherit_silence():
    s = _state(2)
    _set(s, 0, "SEE", "SILENT")
    _set(s, 1, "SEE", +1)
    out = _settle(s, {"hub": [0], "kind": [1]}, [("hypernym", "hub", "kind")])
    assert _get(out.state, 1, "SEE") == POS
    assert out.reasons[out.graph.keys.index("kind"), B["SEE"]] == 0


def test_two_parents_that_disagree_are_suspended_and_neither_is_chosen():
    s = _state(4)
    _set(s, 0, "GOOD", +1)
    _set(s, 1, "GOOD", -1)
    groups = {"p1": [0], "p2": [1], "child": [2], "grandchild": [3]}
    links = [("hypernym", "p1", "child"), ("hypernym", "p2", "child"), ("hypernym", "child", "grandchild")]
    out = _settle(s, groups, links)
    assert _get(out.state, 2, "GOOD") == _start("GOOD")
    assert _get(out.state, 3, "GOOD") == _start("GOOD")
    found = {(x["node"], x["bank"]): x for x in out.suspensions()}
    assert found[("child", "GOOD")]["reasons"] == ["defaults disagree"]
    assert {g["from"] for g in found[("child", "GOOD")]["givers"]} == {"p1", "p2"}
    assert ("grandchild", "GOOD") in found


def test_values_that_reach_one_child_at_different_depths_both_suspend():
    s = _state(5)
    _set(s, 0, "GOOD", +1)
    _set(s, 1, "GOOD", -1)
    groups = {"near": [0], "far": [1], "mid1": [2], "mid2": [3], "child": [4]}
    links = [
        ("hypernym", "near", "child"),
        ("hypernym", "far", "mid1"),
        ("hypernym", "mid1", "transit"),
        ("hypernym", "transit", "mid2"),
        ("hypernym", "mid2", "child"),
    ]
    out = _settle(s, groups, links)
    assert _get(out.state, 3, "GOOD") == NEG  # the far value reaches its own kinds
    assert _get(out.state, 4, "GOOD") == _start("GOOD")
    assert out.reasons[out.graph.keys.index("child"), B["GOOD"]] & inh.DISAGREE


def test_a_default_against_the_known_state_is_suspended_and_the_kinds_own_value_is_inherited():
    s = _state(3)
    _set(s, 0, "MOVE", +1)
    _set(s, 1, "MOVE", 0)
    groups = {"hub": [0], "kind": [1], "sub": [2]}
    out = _settle(s, groups, [("hypernym", "hub", "kind"), ("hypernym", "kind", "sub")])
    assert _get(out.state, 1, "MOVE") == ZERO
    assert _get(out.state, 2, "MOVE") == ZERO  # the kind's own value is what its kinds inherit
    assert out.reasons[out.graph.keys.index("kind"), B["MOVE"]] == inh.KNOWN


def test_a_defeated_link_carries_nothing_and_defeats_only_what_depended_on_it():
    s = _state(4)
    _set(s, 0, "FEEL", +1)
    _set(s, 1, "MOVE", +1)
    groups = {"h1": [0], "h2": [1], "c": [2], "g": [3]}
    links = [("hypernym", "h1", "c"), ("hypernym", "h2", "c"), ("hypernym", "c", "g")]
    misfiling = inh.Defeater(parent="h2", child="c", reason="test: c is misfiled under h2")
    out = _settle(s, groups, links, defeaters=(misfiling,))
    for row in (2, 3):
        assert _get(out.state, row, "FEEL") == POS
        assert _get(out.state, row, "MOVE") == _start("MOVE")
    assert out.graph.defeated == (("hypernym", "h2", "c", "test: c is misfiled under h2"),)
    undefeated = _settle(s, groups, links)
    assert _get(undefeated.state, 3, "MOVE") == POS


def test_a_defeated_origin_carries_nothing_out_of_it():
    s = _state(4)
    _set(s, 0, "MOVE", +1)
    _set(s, 1, "CAUSE", +1)
    groups = {"hub": [0], "origin": [1], "kind": [2], "sibling": [3]}
    links = [("hypernym", "hub", "origin"), ("hypernym", "origin", "kind"), ("hypernym", "hub", "sibling")]
    out = _settle(s, groups, links, defeaters=(inh.Defeater(parent="origin", reason="test: no genus for its kinds"),))
    assert _get(out.state, 1, "MOVE") == POS  # the origin still inherits from its own hub
    assert _get(out.state, 2, "MOVE") == _start("MOVE") and _get(out.state, 2, "CAUSE") == _start("CAUSE")
    assert _get(out.state, 3, "MOVE") == POS


def test_a_defeater_that_matches_no_link_is_refused():
    with pytest.raises(ValueError, match="DEFEATER_MATCHES_NO_LINK"):
        inh.build({"a": [0]}, [], defeaters=(inh.Defeater(parent="a", child="b", reason="test"),))


def test_a_cycle_terminates_and_carries_each_way_its_families_allow():
    # breathe.v.01 entails inhale.v.02, and inhale.v.02 is a kind of breathe.v.01.
    s = _state(2)
    _set(s, 0, "MOVE", +1)
    _set(s, 1, "BODY", +1)
    _set(s, 1, "HEAR", 0)
    links = [("entails", "inhale", "breathe"), ("hypernym", "breathe", "inhale")]
    out = _settle(s, {"breathe": [0], "inhale": [1]}, links)
    assert _get(out.state, 1, "MOVE") == POS  # kind-of: breathe -> inhale
    assert _get(out.state, 0, "BODY") == POS  # entailment: inhale -> breathe
    assert _get(out.state, 0, "HEAR") == _start("HEAR")  # entailment does not carry a zero


def test_synonymy_carries_every_state_both_ways():
    s = _state(2)
    _set(s, 0, "SEE", "SILENT")
    _set(s, 1, "GOOD", +1)
    out = _settle(s, {"synset": [0, 1]}, [])
    assert _get(out.state, 1, "SEE") == SILENT
    assert _get(out.state, 0, "GOOD") == POS
    assert out.inherited[0, B["GOOD"]] and out.inherited[1, B["SEE"]]


def test_synonyms_whose_known_states_disagree_are_not_equalized():
    s = _state(2)
    _set(s, 0, "GOOD", +1)
    _set(s, 1, "GOOD", -1)
    out = _settle(s, {"synset": [0, 1]}, [])
    assert (_get(out.state, 0, "GOOD"), _get(out.state, 1, "GOOD")) == (POS, NEG)
    assert out.reasons[0, B["GOOD"]] == inh.SYNONYMS


def test_entailment_carries_content_not_zero_and_cause_carries_nothing():
    s = _state(4)
    _set(s, 0, "BODY", +1)
    _set(s, 0, "MOVE", 0)
    _set(s, 2, "ALIVE", -1)
    groups = {"sleep": [0], "snore": [1], "die": [2], "kill": [3]}
    out = _settle(s, groups, [("entails", "sleep", "snore"), ("causes", "die", "kill")])
    assert _get(out.state, 1, "BODY") == POS
    assert _get(out.state, 1, "MOVE") == _start("MOVE")
    assert (out.state.masks[3] == cells.START).all()


def test_a_joint_conflict_under_a_law_suspends_both_defaults():
    law = implies("t:feel-alive", "FEEL", POS, "ALIVE", POS, "test")
    s = _state(3)
    _set(s, 0, "FEEL", +1)
    _set(s, 1, "ALIVE", 0)
    groups = {"p1": [0], "p2": [1], "child": [2]}
    out = _settle(s, groups, [("hypernym", "p1", "child"), ("hypernym", "p2", "child")], relations=[law])
    assert _get(out.state, 2, "FEEL") == _start("FEEL")
    assert _get(out.state, 2, "ALIVE") == _start("ALIVE")
    child = out.graph.keys.index("child")
    assert out.reasons[child, B["FEEL"]] & inh.JOINT and out.reasons[child, B["ALIVE"]] & inh.JOINT
    assert (out.state.masks != 0).all()


def test_a_conflict_that_appears_after_a_law_narrows_a_kind_retracts_what_had_landed():
    # The intermediate gets ALIVE +1 only as a consequence of its inherited FEEL +1 (a law scoped to it), and gives
    # it on; the child had already taken ALIVE 0 from its other parent.
    law = implies("t:feel-alive", "FEEL", POS, "ALIVE", POS, "test", scope="mid")
    s = _state(4)
    _set(s, 0, "FEEL", +1)
    _set(s, 1, "ALIVE", 0)
    groups = {"hub": [0], "zero": [1], "mid": [2], "child": [3]}
    links = [("hypernym", "hub", "mid"), ("hypernym", "mid", "child"), ("hypernym", "zero", "child")]
    out = _settle(s, groups, links, relations=[law], scopes={"mid": np.array([False, False, True, False])})
    assert _get(out.state, 2, "ALIVE") == POS
    assert _get(out.state, 3, "ALIVE") == _start("ALIVE")
    assert _get(out.state, 3, "FEEL") == POS
    assert out.reasons[out.graph.keys.index("child"), B["ALIVE"]] & inh.DISAGREE
    assert out.receipt["rounds"][0]["replay"] and not out.receipt["rounds"][-1]["replay"]


def test_the_result_does_not_depend_on_the_order_of_links_or_relations():
    laws = [
        implies("t:feel-alive", "FEEL", POS, "ALIVE", POS, "test"),
        implies("t:alive-body", "ALIVE", POS, "BODY", POS | ZERO, "test"),
    ]
    s = _state(7)
    _set(s, 0, "FEEL", +1)
    _set(s, 1, "ALIVE", 0)
    _set(s, 2, "GOOD", -1)
    _set(s, 3, "GOOD", +1)
    groups = {f"n{i}": [i] for i in range(7)}
    links = [
        ("hypernym", "n0", "n4"),
        ("hypernym", "n1", "n5"),
        ("hypernym", "n4", "n6"),
        ("hypernym", "n5", "n6"),
        ("entails", "n2", "n4"),
        ("hypernym", "n3", "n5"),
        ("similar_to", "n0", "n5"),
    ]
    results = []
    rng = random.Random(7)
    for _ in range(6):
        order = links[:]
        rng.shuffle(order)
        out = _settle(s, groups, order, relations=rng.sample(laws, len(laws)))
        results.append((out.state.masks.copy(), out.held.copy()))
    assert all((m == results[0][0]).all() and (h == results[0][1]).all() for m, h in results)


def test_one_pass_returns_what_it_changed():
    s = _state(3)
    _set(s, 0, "MOVE", +1)
    graph = inh.build({"hub": [0], "kind": [1, 2]}, [("hypernym", "hub", "kind")])
    before = s.masks.copy()
    step = inh.carry(s, graph)
    assert step.changed == 2
    assert sorted(step.rows.tolist()) == [1, 2] and set(step.cols.tolist()) == {B["MOVE"]}
    assert (step.old == before[step.rows, step.cols]).all() and (step.new == POS).all()
    assert (s.masks[step.rows, step.cols] == step.new).all()
    assert inh.carry(s, graph).changed == 0


def test_an_obligation_forces_from_an_inherited_exclusion_and_its_conflict_suspends_the_defaults():
    s = _state(4)
    _set(s, 0, "MOVE", 0)
    groups = {"hub": [0], "a": [1], "b": [2], "c": [3]}
    # One of the lemma's readings (a, b) moves; a inherits the hub's explicit zero, so b is forced.
    forced = _settle(
        s, groups, [("hypernym", "hub", "a")], obligations=Batch.of([Obligation("t:one-moves", "MOVE", POS, [1, 2])])
    )
    assert _get(forced.state, 2, "MOVE") == POS
    assert forced.interpolated[2, B["MOVE"]] and not forced.inherited[2, B["MOVE"]]
    # Both readings inherit the zero, which the known obligation forbids: the defaults are suspended.
    links = [("hypernym", "hub", "b"), ("hypernym", "hub", "c")]
    clash = _settle(s, groups, links, obligations=Batch.of([Obligation("t:one-moves", "MOVE", POS, [2, 3])]))
    assert _get(clash.state, 2, "MOVE") == _start("MOVE") and _get(clash.state, 3, "MOVE") == _start("MOVE")
    assert clash.reasons[clash.graph.keys.index("b"), B["MOVE"]] & inh.JOINT
    assert clash.interpolated_conflicts == []


def test_the_known_layer_closes_obligations_to_a_fixed_point():
    s = _state(3)
    _set(s, 0, "MOVE", 0)
    chain = Batch.of([Obligation("t:a", "MOVE", POS, [0, 1]), Obligation("t:b", "MOVE", ZERO | SILENT, [1, 2])])
    out = _settle(s, {}, [], obligations=chain)
    assert _get(out.known, 1, "MOVE") == POS
    assert _get(out.known, 2, "MOVE") == ZERO | SILENT
    assert out.receipt["known"]["sweeps"] == 3


def test_build_refuses_unknown_families_and_a_reading_in_two_nodes():
    with pytest.raises(ValueError, match="UNKNOWN_FAMILIES"):
        inh.build({}, [("meronym", "a", "b")])
    with pytest.raises(ValueError, match="READING_IN_TWO_NODES"):
        inh.build({"a": [0], "b": [0]}, [])


def _wordnet():
    try:
        from nltk.corpus import wordnet as wn

        wn.synset("dog.n.01")
    except LookupError:
        pytest.skip("WordNet data is not installed")
    return wn


def test_wordnet_links_run_in_the_declared_directions():
    links = set(inh.wordnet_links(_wordnet()))
    assert ("hypernym", "canine.n.02", "dog.n.01") in links
    assert ("instance_hypernym", "national_capital.n.01", "paris.n.01") in links
    assert ("similar_to", "wet.a.01", "damp.s.01") in links
    assert ("similar_to", "damp.s.01", "wet.a.01") not in links
    assert ("entails", "sleep.v.01", "snore.v.01") in links
    assert ("causes", "die.v.01", "kill.v.01") in links


def test_wordnet_groups_read_the_synset_from_the_reading_id():
    readings = [
        "wordnet:animal:animal.n.01",
        "wordnet:creatures:animal.n.01",
        "wiktionary:x:1",
        "wordnet:a%20b:a_b.n.01",
    ]
    assert inh.wordnet_groups(readings) == {"animal.n.01": [0, 1], "a_b.n.01": [3]}
