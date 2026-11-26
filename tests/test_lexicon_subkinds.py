"""Sub-kind inheritance (word_sense_subkinds): a kind of X takes X's decided values; parents that disagree leave it."""

from GSE.curation.lexicon_builder.word_sense_subkinds import Hierarchy


def test_a_decision_reaches_every_kind_below_it():
    hierarchy = Hierarchy({"wordnet:animal:animal.n.01": {"MOVE": 1}})
    assert hierarchy.inherited("dog.n.01")["MOVE"] == (1, "animal.n.01")
    assert hierarchy.inherited("poodle.n.01")["MOVE"][0] == 1


def test_a_nearer_decision_stands_over_a_farther_one():
    hierarchy = Hierarchy({"wordnet:animal:animal.n.01": {"MOVE": 1}, "wordnet:canine:canine.n.02": {"MOVE": -1}})
    assert hierarchy.inherited("wolf.n.01")["MOVE"] == (-1, "canine.n.02")


def test_parents_that_disagree_leave_the_bank_open():
    # dog.n.01 is a kind of canine.n.02 and of domestic_animal.n.01; the second only inherits animal's +1.
    hierarchy = Hierarchy({"wordnet:animal:animal.n.01": {"MOVE": 1}, "wordnet:canine:canine.n.02": {"MOVE": -1}})
    assert "MOVE" not in hierarchy.inherited("dog.n.01")


def test_nothing_is_inherited_across_unrelated_kinds():
    hierarchy = Hierarchy({"wordnet:animal:animal.n.01": {"MOVE": 1}})
    assert "MOVE" not in hierarchy.inherited("hammer.n.02")


def test_declared_defeaters_cut_the_misfiled_branches_and_nothing_else():
    hierarchy = Hierarchy({"wordnet:part:part.n.01": {"PART": 1}, "wordnet:move:move.v.02": {"MOVE": 1}})
    assert "PART" not in hierarchy.inherited("thiouracil.n.01")  # matter filed under part.n.01
    assert "MOVE" not in hierarchy.inherited("fund.v.03")  # change of ownership entails move.v.02
    assert hierarchy.inherited("hinge.n.01").get("PART", (None,))[0] in (1, None)  # other kinds of part still inherit
