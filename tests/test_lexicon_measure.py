"""Measurement over the population (`measure.py`, design E9). The relations, readings and counts are written for the
test; they are not lexical laws or SUBTLEX counts."""

from __future__ import annotations

import math

import numpy as np

from GSE.curation.lexicon_builder import cells, measure
from GSE.curation.lexicon_builder import inheritance as inh
from GSE.curation.lexicon_builder.cells import NEG, POS, SILENT, ZERO, State
from GSE.curation.lexicon_builder.inventory import Reading
from GSE.curation.lexicon_builder.relations import Relation, implies

B = cells.BANK_INDEX
ONE_HOT = Relation(
    "t:one-hot",
    ("SEE", "HEAR", "TOUCH"),
    ((POS, ZERO, ZERO), (ZERO, POS, ZERO), (ZERO, ZERO, POS)),
    "test",
    scope="first",
)


def _state(n):
    return State.opening([f"r{i}" for i in range(n)])


def _open(state, row, *banks):
    for bank in banks:
        state.masks[row, B[bank]] = POS | ZERO


def test_the_joint_count_is_exact_within_a_component_and_marginal_elsewhere():
    s = _state(2)
    for row in (0, 1):
        _open(s, row, "SEE", "HEAR", "TOUCH")
    out = measure.joint(s, [ONE_HOT], {"first": np.array([True, False])})
    assert out["marginal_bits"] == s.bits()
    # Row 0: three legal joint states instead of 2**3; row 1 is outside the relation's scope.
    assert math.isclose(out["marginal_bits"] - out["joint_bits"], 3 - math.log2(3))
    assert out["exact"] and out["readings_without_configuration"] == 0
    [component] = out["components"]
    assert component["banks"] == ["SEE", "HEAR", "TOUCH"] and component["legal_joint_states"] == 3


def test_disconnected_components_multiply_and_coupled_relations_join():
    pair = Relation("t:pair", ("GOOD", "BIG"), ((POS, ZERO), (ZERO, POS)), "test")
    chain = Relation("t:chain", ("BIG", "FAR"), ((POS, POS), (ZERO, ZERO), (ZERO, POS)), "test")
    s = _state(1)
    _open(s, 0, "SEE", "HEAR", "TOUCH", "GOOD", "BIG", "FAR")
    out = measure.joint(s, [ONE_HOT, pair, chain], {"first": np.array([True])})
    # {SEE, HEAR, TOUCH}: 3 states; {GOOD, BIG, FAR} joined: (+,0,0), (+,0,+), (0,+,+): 3 states.
    free = sum(
        math.log2(cells._POPCOUNT[m])
        for c, m in enumerate(s.masks[0])
        if cells.BANKS[c] not in {"SEE", "HEAR", "TOUCH", "GOOD", "BIG", "FAR"}
    )
    assert math.isclose(out["joint_bits"], free + 2 * math.log2(3))
    assert sorted(len(c["banks"]) for c in out["components"]) == [3, 3]


def test_a_reading_no_joint_state_fits_earns_no_bits_and_is_counted():
    s = _state(2)
    _open(s, 0, "SEE", "HEAR", "TOUCH")
    s.masks[0, B["SEE"]] = ZERO
    s.masks[0, B["HEAR"]] = ZERO
    s.masks[0, B["TOUCH"]] = ZERO  # every bank 0: the one-hot law has no state for it
    s.masks[1, B["MOVE"]] = 0  # an empty mask
    out = measure.joint(s, [ONE_HOT], {"first": np.array([True, True])})
    assert out["readings_without_configuration"] == 2 and out["joint_bits"] == 0.0


def test_a_component_too_large_to_count_is_reported_as_a_bound(monkeypatch):
    monkeypatch.setattr(measure, "EXACT_JOIN_ROWS", 1)
    pair = Relation("t:pair", ("GOOD", "BIG"), ((POS, ZERO), (ZERO, POS)), "test")
    chain = Relation("t:chain", ("BIG", "FAR"), ((POS, POS), (ZERO, ZERO), (ZERO, POS)), "test")
    s = _state(1)
    _open(s, 0, "GOOD", "BIG", "FAR")
    out = measure.joint(s, [pair, chain])
    assert not out["exact"] and out["readings_with_a_bound"] == 1
    assert out["joint_bits"] == out["marginal_bits"]  # the bound is the marginal, never an estimate
    assert out["components"][0]["bounded"] and out["components"][0]["legal_joint_states"] is None


def test_the_census_accounts_for_every_cell_by_bank_pos_and_source():
    s = _state(3)
    s.masks[0, B["GOOD"]] = POS
    s.masks[1, B["GOOD"]] = NEG
    s.masks[2, B["SEE"]] = SILENT
    s.masks[2, B["HEAR"]] = 0
    out = measure.census(s.masks, pos=["verb", "noun", "noun"], source=["wordnet", "wordnet", "wiktionary"])
    assert sum(out["by_state"].values()) == out["cells"] == 3 * len(cells.BANKS)
    assert out["by_bank"]["GOOD"]["+1"] == 1 and out["by_bank"]["GOOD"]["-1"] == 1
    assert out["by_pos"]["noun"]["rows"] == 2 and out["by_pos"]["noun"]["conflict"] == 1
    assert out["by_source"]["wiktionary"]["SILENT"] == 1


def test_frequency_cohorts_rank_spellings_and_keep_every_definition():
    lemmas = ["the", "the", "dog", "aardvark", "florble"]
    counts = {"the": 1000, "dog": 50, "aardvark": 5}
    s = _state(5)
    s.masks[0, :] = ZERO  # a decided row
    buckets = measure.bucket_of(lemmas, counts)
    assert buckets.tolist() == ["1-500", "1-500", "1-500", "1-500", "absent"]
    out = measure.frequency_buckets(s.masks, lemmas, counts)
    assert out["1-500"]["definitions"] == 4 and out["1-500"]["spellings"] == 3
    assert out["absent"]["definitions"] == 1
    assert out["1-500"]["mean_unresolved_banks"] == (0 + 3 * len(cells.BANKS)) / 4
    ranked = measure.bucket_of([f"w{i}" for i in range(6000)], {f"w{i}": 6000 - i for i in range(6000)})
    assert [ranked[i] for i in (0, 499, 500, 1499, 1500, 4999, 5000)] == [
        "1-500",
        "1-500",
        "501-1500",
        "501-1500",
        "1501-5000",
        "1501-5000",
        "5001+",
    ]


def test_subtlex_counts_are_read_from_the_norms(tmp_path):
    path = tmp_path / "norms.csv"
    path.write_text(
        "Word,Bigram,Conc.M,Conc.SD,Unknown,Total,Percent_known,SUBTLEX\na,0,1,1,0,1,1,99\nIce Cream,1,4,1,0,1,1,7\n"
    )
    assert measure.subtlex_counts(path) == {"a": 99, "ice cream": 7}


def test_rule_reach_is_leave_one_out_and_overlap_is_credited_to_no_rule():
    # Two rules decide the same cell; a third decides one alone; the one-hot law cuts the joint count only.
    a = implies("t:a", "FEEL", POS, "ALIVE", POS, "test")
    b = implies("t:b", "FEEL", POS, "ALIVE", POS, "test")
    c = implies("t:c", "FEEL", POS, "BODY", POS, "test")
    s = _state(1)
    s.masks[0, B["FEEL"]] = POS
    _open(s, 0, "SEE", "HEAR", "TOUCH")
    scopes = {"first": np.array([True])}
    out = measure.rule_reach(s, [a, b, c, ONE_HOT], scopes)
    by = {e["rule"]: e for e in out["rules"]}
    assert by["t:a"]["cells_decided"] == 0 and by["t:b"]["cells_narrowed"] == 0  # each is covered by the other
    assert by["t:c"]["cells_decided"] == 1 and by["t:c"]["decided_states"] == {"+1": 1}
    assert by["t:one-hot"]["marginal_bits"] == 0.0
    assert math.isclose(by["t:one-hot"]["kappa_joint_bits"], 3 - math.log2(3))
    assert out["bits_in_overlap"] == 2.0  # ALIVE from four states to one, which a and b each make


def test_the_receipt_measures_both_layers_of_a_settlement():
    readings = [Reading("wordnet:x:x.n.01", "x", "noun", ""), Reading("wiktionary:y:1", "y", "verb", "")]
    s = State.opening([r.reading_id for r in readings])
    s.masks[0, B["MOVE"]] = POS
    graph = inh.build({"x.n.01": [0], "wiktionary:y:1": [1]}, [("hypernym", "x.n.01", "wiktionary:y:1")])
    settled = inh.settle(s, graph)
    out = measure.receipt(settled, readings, [], premises=s, counts={"x": 10})
    known, interpolated = out["layers"]["known"], out["layers"]["interpolated"]
    assert known["census"]["by_state"]["+1"] == 1 and interpolated["census"]["by_state"]["+1"] == 2
    assert interpolated["H"]["marginal_bits"] < known["H"]["marginal_bits"]
    assert known["frequency"]["1-500"]["definitions"] == 1 and known["frequency"]["absent"]["definitions"] == 1
    assert out["rules"]["rules"] == []
