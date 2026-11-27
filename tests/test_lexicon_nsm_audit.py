"""The audit of inherited values against NSM explications (`nsm_audit.py`). The nodes, links and explications are
written for the test; they are not NSM records."""

from __future__ import annotations

import numpy as np

from GSE.curation.lexicon_builder import cells, nsm_audit
from GSE.curation.lexicon_builder import inheritance as inh
from GSE.curation.lexicon_builder.cells import NEG, POS, State

B = cells.BANK_INDEX


def _state(n):
    return State.opening([f"r{i}" for i in range(n)])


def _set(state, row, bank, value):
    state.masks[row, B[bank]] = cells.bit(value)


def _settle(state, groups, links, **kw):
    return inh.settle(state, inh.build(groups, links), **kw)


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
        nsm_audit.Explication("T1:10-14", "cut", "verb", np.array([2]), {"DO": POS, "GOOD": NEG}),  # no MOVE: disagrees
        nsm_audit.Explication("T1:20-24", "slide", "verb", np.array([3]), {"MOVE": POS, "GOOD": POS}),  # GOOD opposite
    ]
    audit = nsm_audit.audit_against_nsm(out, exps)
    assert audit["disagreements"] == 2 and audit["confirmations"] == 2  # cut GOOD -1 and slide MOVE +1 agree
    [cut] = [d for d in audit["details"] if d["lemma"] == "cut"]
    assert cut["bank"] == "MOVE" and cut["readings"][0]["kind"] == nsm_audit.DISAGREE_UNMENTIONED
    [origin] = cut["readings"][0]["origins"]
    assert origin["origin"] == "hub" and origin["origin_stated"]
    assert origin["path"] == [("hypernym", "mid"), ("hypernym", "cut")]
    assert origin["candidate"] == {"family": "hypernym", "from": "hub", "to": "mid"}
    [slide] = [d for d in audit["details"] if d["lemma"] == "slide"]
    assert slide["bank"] == "GOOD" and slide["readings"][0]["kind"] == nsm_audit.DISAGREE_OPPOSITE
    first = audit["candidates"][0]
    assert first["link"] == {"family": "hypernym", "from": "hub", "to": "mid"} and first["bank"] == "MOVE"
    assert first["warrant"] == "NSM T1:10-14"
    assert first["inherited_cells_resting_on_it"] == 3  # mid, cut and c1 carry MOVE through hub -> mid
    assert audit["by_word_and_bank"] == {"cut (verb) MOVE": 1, "slide (verb) GOOD": 1}
    # A carried 0 on a bank the explication does not mention says nothing.
    assert all(d["bank"] != "HEAR" for d in audit["details"])


def test_an_explication_over_several_candidates_disagrees_only_if_every_candidate_does():
    out = _audit_fixture()
    both = nsm_audit.Explication("T2:1-5", "x", "verb", np.array([2, 4]), {"DO": POS})  # cut and c1 both carry MOVE
    one = nsm_audit.Explication("T2:6-9", "y", "verb", np.array([2, 5]), {"DO": POS})  # c2 carries nothing
    audit = nsm_audit.audit_against_nsm(out, [both, one], expressible={"DO", "MOVE"})
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
    exps = nsm_audit.explications_from_nsm(SimpleNamespace(receipt=receipt, obligations=obligations))
    assert [(e.key, e.lemma, e.rows.tolist(), e.states) for e in exps] == [
        ("G1:3-9", "cut", [4], {"DO": POS, "GOOD": POS | NEG}),
        ("G1:10-12", "dog", [7, 8], {"MOVE": POS}),
    ]


def test_a_bank_no_nsm_record_can_write_is_not_judged():
    out = _audit_fixture()
    cut = nsm_audit.Explication("T1:10-14", "cut", "verb", np.array([2]), {"DO": POS, "GOOD": NEG})
    audit = nsm_audit.audit_against_nsm(out, [cut], expressible={"DO", "GOOD"})
    assert audit["disagreements"] == 0 and audit["confirmations"] == 1
    assert audit["not_judged"]["carried_cells"] == {"MOVE": 1, "HEAR": 1}
