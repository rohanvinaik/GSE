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


def test_entailment_carries_content_not_zero_and_cause_carries_content_but_never_cause():
    # The lead's ruling of 2026-11-27 (native_predicate_policy.lexical_component): kill takes die's ALIVE -1; the
    # link writes no CAUSE, and the effect's zeros stay with the effect.
    s = _state(4)
    _set(s, 0, "BODY", +1)
    _set(s, 0, "MOVE", 0)
    _set(s, 2, "ALIVE", -1)
    _set(s, 2, "CAUSE", +1)
    _set(s, 2, "HEAR", 0)
    groups = {"sleep": [0], "snore": [1], "die": [2], "kill": [3]}
    out = _settle(s, groups, [("entails", "sleep", "snore"), ("causes", "die", "kill")])
    assert _get(out.state, 1, "BODY") == POS
    assert _get(out.state, 1, "MOVE") == _start("MOVE")
    assert _get(out.state, 3, "ALIVE") == NEG
    assert _get(out.state, 3, "CAUSE") == _start("CAUSE")
    assert _get(out.state, 3, "HEAR") == _start("HEAR")


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


def test_a_fact_located_by_an_obligation_wakes_the_law_it_guards():
    # The law is written for the test: an evaluator is not a size (GOOD +1 -> BIG 0), guarded by a reading fact.
    law = implies("t:evaluator-size", "GOOD", POS, "BIG", ZERO, "test", scope="own_semantic_kind=evaluator")
    s = _state(2)
    _set(s, 0, "GOOD", 0)
    evaluator = np.zeros(2, dtype=bool)
    batch = Batch.of([Obligation("t:good", "GOOD", POS, [0, 1], witness=1, facts=("own_semantic_kind=evaluator",))])
    scopes = {"own_semantic_kind=evaluator": evaluator}
    out = _settle(s, {}, [], relations=[law], scopes=scopes, obligations=batch)
    assert _get(out.known, 1, "GOOD") == POS and _get(out.known, 1, "BIG") == ZERO
    assert out.known_scopes["own_semantic_kind=evaluator"].tolist() == [False, True]
    assert not evaluator.any()  # the caller's scopes are not modified
    assert out.receipt["known"]["facts_woken"] == 1


def test_a_quality_pole_forced_onto_one_reading_makes_it_an_evaluator_and_the_authored_law_fires():
    # The shape of USAS_OWN_QUALITY_POLE on "excellent": one reading is GOOD +1 and is an evaluator. The other
    # reading is excluded, so the group is located on r1, and EVALUATOR_EXCLUDES_SIZE (bank_laws.json) then
    # leaves BIG only 0 there; r0, which is not an evaluator, keeps its BIG.
    from GSE.curation.lexicon_builder import laws

    [law] = [r for r in laws.compile_laws() if r.rule_id == "law:EVALUATOR_EXCLUDES_SIZE"]
    s = _state(2)
    _set(s, 0, "GOOD", -1)
    pole = Obligation("t:quality-pole", "GOOD", POS, [0, 1], witness=9, facts=(law.scope,))
    out = _settle(s, {}, [], relations=[law], scopes={law.scope: np.zeros(2, dtype=bool)}, obligations=Batch.of([pole]))
    assert _get(out.known, 1, "GOOD") == POS and _get(out.known, 1, "BIG") == ZERO
    assert _get(out.known, 0, "BIG") == _start("BIG")
    assert out.known_scopes[law.scope].tolist() == [False, True]


def test_every_carried_value_records_its_origin_and_last_hop():
    s = _state(6)
    _set(s, 0, "MOVE", +1)
    _set(s, 5, "MOVE", +1)
    _set(s, 4, "FEEL", +1)
    groups = {"hub": [0, 1], "kind": [2], "kk": [3, 4], "other": [5]}
    links = [
        ("hypernym", "hub", "transit"),
        ("hypernym", "transit", "kind"),
        ("hypernym", "kind", "kk"),
        ("entails", "other", "kk"),
    ]
    out = _settle(s, groups, links)
    keys, o = out.graph.keys, out.origins()
    found = {
        (out.state.readings[r], cells.BANKS[c], keys[g], keys[p], int(f), keys[first])
        for r, c, g, p, f, first in zip(o["rows"], o["cols"], o["origin"], o["parent"], o["family"], o["first"])
    }
    hypernym, entails = 0, 3
    assert ("r2", "MOVE", "hub", "transit", hypernym, "transit") in found
    assert ("r3", "MOVE", "hub", "kind", hypernym, "transit") in found
    assert ("r3", "MOVE", "other", "other", entails, "kk") in found  # a second origin, by entailment
    assert ("r1", "MOVE", "hub", "hub", inh.SYNONYM_HOP, "hub") in found  # a synonym's statement
    assert ("r3", "FEEL", "kk", "kk", inh.SYNONYM_HOP, "kk") in found
    entry = next(
        int(e) for r, c, g, e in zip(o["rows"], o["cols"], o["origin"], o["entry"]) if (r, keys[g]) == (3, "hub")
    )
    assert [keys[out.lineage.node[j]] for j in out.lineage.path(entry)] == ["transit", "kind", "kk"]


def _audit_fixture():
    s = _state(6)
    _set(s, 0, "MOVE", +1)
    _set(s, 0, "GOOD", -1)
    _set(s, 0, "HEAR", 0)
    groups = {"hub": [0], "mid": [1], "cut": [2], "slide": [3], "c1": [4], "c2": [5]}
    links = [
        ("hypernym", "hub", "mid"),
        ("hypernym", "mid", "cut"),
        ("hypernym", "hub", "slide"),
        ("hypernym", "mid", "c1"),
    ]
    return _settle(s, groups, links)


def test_the_audit_reports_a_disagreement_with_its_path_and_candidate_link():
    out = _audit_fixture()
    exps = [
        inh.Explication("T1:10-14", "cut", "verb", np.array([2]), {"DO": POS, "GOOD": NEG}),  # no MOVE: disagrees
        inh.Explication("T1:20-24", "slide", "verb", np.array([3]), {"MOVE": POS, "GOOD": POS}),  # GOOD opposite
    ]
    audit = inh.audit_against_nsm(out, exps)
    assert audit["disagreements"] == 2 and audit["confirmations"] == 2  # cut GOOD -1 and slide MOVE +1 agree
    [cut] = [d for d in audit["details"] if d["lemma"] == "cut"]
    assert cut["bank"] == "MOVE" and cut["readings"][0]["kind"] == inh.DISAGREE_UNMENTIONED
    [origin] = cut["readings"][0]["origins"]
    assert origin["origin"] == "hub" and origin["origin_stated"]
    assert origin["path"] == [("hypernym", "mid"), ("hypernym", "cut")]
    assert origin["candidate"] == {"family": "hypernym", "from": "hub", "to": "mid"}
    [slide] = [d for d in audit["details"] if d["lemma"] == "slide"]
    assert slide["bank"] == "GOOD" and slide["readings"][0]["kind"] == inh.DISAGREE_OPPOSITE
    first = audit["candidates"][0]
    assert first["link"] == {"family": "hypernym", "from": "hub", "to": "mid"} and first["bank"] == "MOVE"
    assert first["warrant"] == "NSM T1:10-14"
    assert first["inherited_cells_resting_on_it"] == 3  # mid, cut and c1 carry MOVE through hub -> mid
    assert audit["by_word_and_bank"] == {"cut (verb) MOVE": 1, "slide (verb) GOOD": 1}
    # A carried 0 on a bank the explication does not mention says nothing.
    assert all(d["bank"] != "HEAR" for d in audit["details"])


def test_an_explication_over_several_candidates_disagrees_only_if_every_candidate_does():
    out = _audit_fixture()
    both = inh.Explication("T2:1-5", "x", "verb", np.array([2, 4]), {"DO": POS})  # cut and c1 both carry MOVE
    one = inh.Explication("T2:6-9", "y", "verb", np.array([2, 5]), {"DO": POS})  # c2 carries nothing
    audit = inh.audit_against_nsm(out, [both, one], expressible={"DO", "MOVE"})
    assert [d["explication"] for d in audit["details"] if d["bank"] == "MOVE"] == ["T2:1-5"]
    assert {"explication": "T2:6-9", "lemma": "y", "pos": "verb", "bank": "MOVE"} in audit["undetermined_cells"]
    [cond] = [d for d in audit["conditional"]["details"] if d["explication"] == "T2:6-9" and d["bank"] == "MOVE"]
    assert cond["reading"] == "r2" and cond["candidates"] == 2
    assert audit["conditional"]["candidates"][0]["link"] == {"family": "hypernym", "from": "hub", "to": "mid"}


def test_explications_are_read_from_the_nsm_compiler_output():
    from types import SimpleNamespace

    receipt = (
        {
            "kind": "explication",
            "pos": "verb",
            "rule_id": "nsm:G1:3-9",
            "disposition": "RESTRICTION",
            "reading": 4,
            "lemma": "cut",
            "source": "G1",
            "start_line": 3,
            "end_line": 9,
            "banks": {"DO": "+1", "GOOD": "+1|-1"},
        },
        {
            "kind": "explication",
            "pos": "noun",
            "rule_id": "nsm:G1:10-12",
            "disposition": "OBLIGATION",
            "lemma": "dog",
            "source": "G1",
            "start_line": 10,
            "end_line": 12,
            "banks": {"MOVE": "+1"},
        },
        {"kind": "template", "pos": "verb", "disposition": "TEMPLATE"},
        {"kind": "explication", "pos": "adj", "rule_id": "nsm:G1:13-14", "disposition": "RESTRICTION", "reading": 1},
    )
    obligations = (SimpleNamespace(rule_id="nsm:G1:10-12", rows=np.array([7, 8])),)
    exps = inh.explications_from_nsm(SimpleNamespace(receipt=receipt, obligations=obligations))
    assert [(e.key, e.lemma, e.rows.tolist(), e.states) for e in exps] == [
        ("G1:3-9", "cut", [4], {"DO": POS, "GOOD": POS | NEG}),
        ("G1:10-12", "dog", [7, 8], {"MOVE": POS}),
    ]


def test_a_bank_no_nsm_record_can_write_is_not_judged():
    out = _audit_fixture()
    cut = inh.Explication("T1:10-14", "cut", "verb", np.array([2]), {"DO": POS, "GOOD": NEG})
    audit = inh.audit_against_nsm(out, [cut], expressible={"DO", "GOOD"})
    assert audit["disagreements"] == 0 and audit["confirmations"] == 1
    assert audit["not_judged"]["carried_cells"] == {"MOVE": 1, "HEAR": 1}
