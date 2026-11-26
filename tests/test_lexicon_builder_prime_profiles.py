"""The authored prime profiles reconstruct through the ordinary solver (F148, F158 section 3, F159)."""

import pytest

from GSE.curation.lexicon_builder.engine import EMPTY
from GSE.curation.lexicon_builder.prime_profiles import coordinate, load_laws, load_profiles, reconstruct

LAWS = load_laws()
PROFILES = {p["prime"]: p for p in load_profiles()}
LEXICAL = sorted(name for name in PROFILES if coordinate(name))


STATE = {"empty": EMPTY, "0": 0, "+1": 1, "-1": -1}


@pytest.mark.parametrize("prime", LEXICAL)
def test_every_prime_reproduces_its_authored_decisions(prime):
    from GSE.curation.lexicon_builder.foundation import BANKS
    from GSE.curation.lexicon_builder.prime_profiles import authored_decisions

    _closed, final = reconstruct(PROFILES[prime], LAWS)
    assert final.code != "CONFLICT", final.conflicts
    bank, sign = coordinate(prime)
    assert final.assignments[bank] == sign
    for decision in authored_decisions(PROFILES[prime]):
        for coordinate_ in decision["coordinates"]:
            if coordinate_ in BANKS:
                assert final.domains[coordinate_] == {STATE[decision["state"]]}, (coordinate_, decision["decision_id"])


def test_good_is_its_own_pole_a_graded_evaluator_and_a_modifier_head():
    closed, final = reconstruct(PROFILES["GOOD"], LAWS)
    assert final.assignments["GOOD"] == 1 and final.assignments["INTENSITY"] == 1
    assert final.assignments["BIG"] == 0  # F067: an own evaluator is an explicit size absence
    assert all(final.assignments[b] == 0 for b in ("I", "YOU", "SOMEONE", "PEOPLE", "BODY", "KIND", "PART"))
    assert (
        final.assignments["SOMETHING"] == 0
    )  # a modifier lacks independent objectness, not "GOOD qualifies SOMETHING"
    assert "FEEL" in final.silent and "FEEL" not in closed.silent  # silence only from the declared silence decision


def test_bad_is_the_same_coordinate_with_the_opposite_sign():
    _closed, final = reconstruct(PROFILES["BAD"], LAWS)
    assert final.assignments["GOOD"] == -1 and final.assignments["BIG"] == 0


def test_must_carries_its_asserted_components():
    _closed, final = reconstruct(PROFILES["MUST"], LAWS)
    assert final.assignments["CAN"] == 1 and final.assignments["NOT"] == 1


def test_removing_a_warrant_changes_exactly_its_cell():
    degree = next(c["claim_id"] for c in PROFILES["GOOD"]["claims"] if c["kind"] == "ESTABLISHES_DEGREE_DOMAIN")
    _c, full = reconstruct(PROFILES["GOOD"], LAWS)
    _c, ablated = reconstruct(PROFILES["GOOD"], LAWS, frozenset({degree}))
    changed = {b for b in full.domains if full.domains[b] != ablated.domains[b]}
    assert changed == {"INTENSITY"} and len(ablated.domains["INTENSITY"]) > 1  # F158: the cell reopens, not silent


def test_removing_the_silence_declaration_reopens_exactly_its_cells():
    from GSE.curation.lexicon_builder.engine import propagate
    from GSE.curation.lexicon_builder.foundation import BANKS
    from GSE.curation.lexicon_builder.prime_profiles import declared_silence, inputs
    from GSE.curation.lexicon_builder.silence import starting_domains

    assertions, context = inputs(PROFILES["GOOD"])
    open_ = propagate(BANKS, assertions, LAWS, context, initial_domains=starting_domains(BANKS))
    reopened = {b for b, d in open_.domains.items() if len(d) > 1}
    assert reopened == set(declared_silence(PROFILES["GOOD"]))


STRUCTURAL = {
    e["reading_id"]: e
    for e in __import__("GSE.curation.lexicon_builder.prime_profiles", fromlist=["load_structural"]).load_structural()
}


@pytest.mark.parametrize("reading", sorted(STRUCTURAL))
def test_every_function_word_has_a_decided_home(reading):
    from GSE.curation.lexicon_builder.prime_profiles import reconstruct_structural

    status, final = reconstruct_structural(STRUCTURAL[reading], LAWS)
    assert status in ("LEXICAL_PROJECTION", "CONSTRUCTION_ONLY") and final.code != "CONFLICT", final.conflicts


def test_function_words_carry_only_their_own_components():
    from GSE.curation.lexicon_builder.prime_profiles import reconstruct_structural

    status, well = reconstruct_structural(STRUCTURAL["construction:well"], LAWS)
    assert status == "LEXICAL_PROJECTION" and well.assignments == {"GOOD": 1}
    status, often = reconstruct_structural(STRUCTURAL["construction:often"], LAWS)
    assert often.assignments == {"QUANTITY": 1, "WHEN": 1}
    status, article = reconstruct_structural(STRUCTURAL["construction:indefinite"], LAWS)
    assert (
        status == "CONSTRUCTION_ONLY" and article.assignments == {} and article.silent == ()
    )  # nothing declared silent
