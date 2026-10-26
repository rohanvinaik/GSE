"""Authored 72-prime and function-word contracts, exercised by the shared constructor."""

from __future__ import annotations

import copy
import json
import subprocess
import sys

import pytest

from gse.lexicon_builder.basis import OPPOSITE_POLES, PRIMES
from gse.lexicon_builder.core import CANONICAL_COORDINATES, canonical_pole
from gse.lexicon_builder.foundation import (
    definition_status,
    examination_status,
    foundation_readings,
    load_foundation,
    reconstruct_profile,
    structural_entries,
)
from gse.lexicon_builder.registry import load_rulebook


@pytest.fixture(scope="module")
def foundation():
    return load_foundation()


@pytest.fixture(scope="module")
def rulebook():
    return load_rulebook()


@pytest.mark.parametrize("prime", PRIMES)
def test_each_located_prime_rebuilds_its_authored_58_cell_definition(prime, foundation, rulebook):
    profile = next(p for p in foundation["profiles"] if p["prime"] == prime)
    assert profile["lexical_sense"] and profile["scope"].startswith("LOCATED_PRIME_READING_ONLY")
    assert definition_status(profile["definition_axiom"]) == "VALID_EXAMINED"
    assert examination_status(profile["definition_axiom"]["examination"], profile["claims"]) == "VALID_EXAMINATION"
    rebuilt = reconstruct_profile(profile, rulebook)
    assert rebuilt["code"] == "CANDIDATE_COMPLETE", (prime, rebuilt["decision_checks"])
    assert rebuilt["definition_check"] == "RECONSTRUCTED", (prime, rebuilt["decision_checks"])
    assert set(rebuilt["vector"]) == set(CANONICAL_COORDINATES)
    assert not {"unresolved", "conflict"} & set(rebuilt["vector"].values())
    assert not rebuilt["model_calls"]


def test_real_prime_proof_entry_point_requires_all_72(tmp_path):
    output = tmp_path / "proof.json"
    subprocess.run(
        [sys.executable, "-m", "gse.lexicon_builder", "prime-proof", "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    proof = json.loads(output.read_text())
    assert proof["code"] == "RECONSTRUCTED_PRIME_FOUNDATION"
    assert proof["definition_checks"] == {"RECONSTRUCTED": 72}
    assert proof["canonical_coordinates"] == 58 and proof["number_is_lexical_prime"] is False


@pytest.mark.parametrize("prime", ["FAR", "NEAR", "LONG_TIME", "SHORT_TIME"])
def test_new_degree_warrant_ablation_reopens_applicability_only(prime, foundation, rulebook):
    profile = next(p for p in foundation["profiles"] if p["prime"] == prime)
    kept = {c["claim_id"] for c in profile["claims"] if c["kind"] != "ESTABLISHES_DEGREE_DOMAIN"}
    whole = reconstruct_profile(profile, rulebook)
    ablated = reconstruct_profile(profile, rulebook, retained_claims=kept)
    assert whole["vector"]["INTENSITY"] == "+1"
    assert ablated["vector"]["INTENSITY"] == "unresolved"
    assert {c for c in CANONICAL_COORDINATES if whole["vector"][c] != ablated["vector"][c]} == {"INTENSITY"}


@pytest.mark.parametrize("prime", ["YOU", "WORDS", "INFER", "MUST", "CERTAINTY"])
def test_new_boundaries_are_independent_authored_inputs(prime, foundation, rulebook):
    profile = next(p for p in foundation["profiles"] if p["prime"] == prime)
    decisions = profile["definition_axiom"]["decisions"]
    boundary = next(d for d in decisions if d["state"] == "empty")
    kept = {d["decision_id"] for d in decisions if d is not boundary}
    whole = reconstruct_profile(profile, rulebook)
    reopened = reconstruct_profile(profile, rulebook, retained_decisions=kept)
    assert {c for c, v in reopened["vector"].items() if v == "unresolved"} == set(boundary["coordinates"])
    assert all(
        reopened["vector"][c] == whole["vector"][c] for c in CANONICAL_COORDINATES if c not in boundary["coordinates"]
    )


def test_all_aliases_retain_separate_profiles_and_one_canonical_pole(foundation, rulebook):
    profiles = {p["prime"]: p for p in foundation["profiles"]}
    for positive, negative in OPPOSITE_POLES:
        positive_coordinate, positive_direction = canonical_pole(positive)
        negative_coordinate, negative_direction = canonical_pole(negative)
        assert positive_coordinate == negative_coordinate and positive_direction == -negative_direction
        assert profiles[positive]["reading_id"] != profiles[negative]["reading_id"]
        assert reconstruct_profile(profiles[positive], rulebook)["vector"][positive_coordinate] == "+1"
        assert reconstruct_profile(profiles[negative], rulebook)["vector"][positive_coordinate] == "-1"


def test_words_keeps_a_linguistic_head_without_invented_person_or_thing_content(foundation, rulebook):
    words = next(p for p in foundation["profiles"] if p["prime"] == "WORDS")
    rebuilt = reconstruct_profile(words, rulebook)
    assert rebuilt["vector"]["WORDS"] == "+1"
    assert {rebuilt["vector"][c] for c in ("I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY", "KIND", "PART")} == {
        "empty"
    }
    assert "SUBSTANTIVE_HEAD_IS_ONE_HOT" not in rebuilt["after_selection"]["fired_rules"]
    assert not {"OPERATOR_HEADS_NO_SUBSTANTIVE", "VERB_HEADS_NO_SUBSTANTIVE"} & set(
        rebuilt["after_selection"]["fired_rules"]
    )


def test_possession_existence_and_be_keep_their_distinct_source_frames(foundation, rulebook):
    profiles = {p["prime"]: p for p in foundation["profiles"]}
    have_boxes = {line["box"] for line in profiles["HAVE"]["definition_axiom"]["examination"]}
    exist_boxes = {line["box"] for line in profiles["EXIST"]["definition_axiom"]["examination"]}
    part_boxes = {line["box"] for line in profiles["PART"]["definition_axiom"]["examination"]}
    assert have_boxes == {"(IS) MINE"}
    assert exist_boxes == {"THERE IS"}
    assert part_boxes == {"(HAVE) PARTS"}
    assert {frame["sense"] for frame in profiles["BE"]["construction_alternatives"]} == {
        "LOCATION",
        "SPECIFICATION",
    }
    have = reconstruct_profile(profiles["HAVE"], rulebook)
    exist = reconstruct_profile(profiles["EXIST"], rulebook)
    assert have["vector"]["HAVE"] == "+1" and have["vector"]["BE"] == "empty"
    assert have["vector"]["PART"] == "0"  # possession is a predicate, not the part-whole head
    assert exist["vector"]["EXIST"] == "+1" and exist["vector"]["BE"] == "empty"
    assert exist["vector"]["WHERE"] == "empty"  # the location argument does not become content


def test_necessity_retains_negation_scope_without_asserting_the_required_event(foundation, rulebook):
    must = next(p for p in foundation["profiles"] if p["prime"] == "MUST")
    expression = must["construction"]["expression"]
    assert expression == {
        "operator": "NOT",
        "scope": {"operator": "CAN", "bearer": "$bearer", "scope": {"operator": "NOT", "scope": "$necessary_act"}},
    }
    rebuilt = reconstruct_profile(must, rulebook)
    assert {rebuilt["vector"][c] for c in ("MUST", "CAN", "NOT")} == {"+1"}
    assert rebuilt["vector"]["DO"] == rebuilt["vector"]["HAPPEN"] == "empty"
    kept = {c["claim_id"] for c in must["claims"] if c.get("coordinate") != "CAN"}
    ablated = reconstruct_profile(must, rulebook, retained_claims=kept)
    assert ablated["vector"]["CAN"] == "unresolved"
    assert ablated["vector"]["NOT"] == "+1"


@pytest.mark.parametrize(
    ("prime", "forbidden_companions"),
    [
        ("INFER", ["KNOW", "TRUE", "THINK"]),
        ("TOWARD", ["MOVE", "DO"]),
        ("AWAY", ["MOVE", "DO"]),
        ("DEAD", ["START", "HAPPEN"]),
        ("THEN", ["BEFORE", "WHEN"]),
        ("CERTAINTY", ["KNOW", "TRUE", "MAYBE", "INTENSITY"]),
        ("CAUSE", ["DO", "HAPPEN", "BECAUSE"]),
        ("BECAUSE", ["CAUSE"]),
    ],
)
def test_adaptations_do_not_inherit_associated_content(prime, forbidden_companions, foundation, rulebook):
    profile = next(p for p in foundation["profiles"] if p["prime"] == prime)
    rebuilt = reconstruct_profile(profile, rulebook)
    assert all(rebuilt["vector"][c] == "empty" for c in forbidden_companions)


def test_direction_is_not_marker_count_base_or_calibrated_gain(foundation, rulebook):
    for prime, direction in (("HIER_PLUS", "UP"), ("HIER_MINUS", "DOWN")):
        profile = next(p for p in foundation["profiles"] if p["prime"] == prime)
        assert profile["construction"]["direction"] == direction
        assert profile["construction"]["marker_count_is_lexical_value"] is False
        rebuilt = reconstruct_profile(profile, rulebook)
        assert rebuilt["vector"][prime] == "+1"
        assert {rebuilt["vector"][c] for c in ("QUANTITY", "INTENSITY", "CERTAINTY")} == {"empty"}
        assert all(d["state"] in {"empty", "0", "+1", "-1"} for d in profile["definition_axiom"]["decisions"])


def test_common_function_words_have_explicit_structural_homes(foundation, rulebook):
    for word in (
        "a",
        "an",
        "the",
        "this",
        "these",
        "we",
        "us",
        "he",
        "she",
        "my",
        "in",
        "at",
        "of",
        "about",
    ):
        homes = structural_entries(word, foundation)
        assert homes and all(e["requires"] and e["operation"] for e in homes), word
        assert all(e["lexical_projection"]["code"] == "CONSTRUCTION_ONLY" for e in homes), word
        assert all(not e["claims"] for e in homes), word
    assert {e["operation"] for e in structural_entries("they", foundation)} == {
        "RESOLVE_PLURAL_REFERENCE",
        "RESOLVE_SINGULAR_PERSON_REFERENCE",
        "RESOLVE_SELECTED_REFERENCE_PORTMANTEAU",
    }
    assert structural_entries("this", foundation)[0]["basis_gaps"] == ["THIS"]
    assert not foundation_readings("a", rulebook, foundation)
    assert not foundation_readings("the", rulebook, foundation)


def test_reference_portmanteaus_keep_lexical_alternatives_and_dummy_it(foundation, rulebook):
    it = {r["reading_id"]: r for r in foundation_readings("it", rulebook, foundation)}
    assert set(it) == {"construction:it_reference"}
    assert it["construction:it_reference"]["after_selection"]["forced"]["SOMETHING"] == "+1"
    assert any(
        "DUMMY_SUBJECT" in e.get("alternatives", []) and not e["claims"] for e in structural_entries("it", foundation)
    )
    they = {r["reading_id"]: r for r in foundation_readings("they", rulebook, foundation)}
    assert set(they) == {
        "construction:singular_they",
        "construction:they_people",
        "construction:they_things",
    }
    for reading_id, coordinate in (
        ("construction:singular_they", "SOMEONE"),
        ("construction:they_people", "PEOPLE"),
        ("construction:they_things", "SOMETHING"),
    ):
        assert they[reading_id]["after_selection"]["forced"][coordinate] == "+1"
        assert they[reading_id]["code"] == "PARTIAL"
    assert all(e["basis_gaps"] == ["THIS"] for e in structural_entries("they", foundation))


@pytest.mark.parametrize(
    ("word", "components"),
    [
        ("well", {"GOOD"}),
        ("such", {"LIKE"}),
        ("everywhere", {"QUANTITY", "WHERE"}),
        ("sometimes", {"QUANTITY", "WHEN"}),
        ("always", {"QUANTITY", "WHEN"}),
        ("never", {"QUANTITY", "WHEN"}),
        ("few", {"QUANTITY", "INTENSITY"}),
        ("a lot", {"QUANTITY", "INTENSITY"}),
    ],
)
def test_portmanteau_components_are_partial_and_do_not_inherit_prime_closure(word, components, foundation, rulebook):
    (reading,) = foundation_readings(word, rulebook, foundation)
    forced = reading["after_selection"]["forced"]
    assert all(forced[c] == "+1" for c in components)
    assert reading["code"] == "PARTIAL" and reading["candidate_vector"] is None
    assert not any(r.startswith("PRIME_BOUNDARY:") for r in reading["after_selection"]["fired_rules"])
    assert any(len(d) > 1 for d in reading["after_selection"]["domains"].values())


def test_quantifier_truth_conditions_survive_the_shared_quantity_projection(foundation):
    entries = {e["reading_id"]: e for e in foundation["structural_entries"]}
    assert entries["construction:quantifier:all"]["scope"]["universal"] is True
    assert (
        entries["construction:quantifier:some"]["scope"]["coverage"]
        == "NONEMPTY_INDEFINITE_SUBDOMAIN; NOT_ALL_IS_NOT_ENTAILED"
    )
    assert (
        entries["construction:quantifier:most"]["scope"]["coverage"]
        == "GREATER_THAN_HALF_OF_BOUND_DOMAIN; NOT_ALL_ENTAILED"
    )
    assert entries["construction:never"]["scope"]["cardinality"] == "ZERO"
    assert entries["construction:quantifier:few"]["scope"]["existential"] is None
    assert entries["construction:quantifier:any"]["alternatives"] == ["FREE_CHOICE", "POLARITY_SENSITIVE_EXISTENTIAL"]


def test_a_forged_component_conflicts_with_the_authored_boundary(foundation, rulebook):
    two = copy.deepcopy(next(p for p in foundation["profiles"] if p["prime"] == "TWO"))
    two["claims"].append(
        {
            "claim_id": "COUNTEREXAMPLE:KNOW_IN_TWO",
            "kind": "ASSERTS_COMPONENT",
            "source": "GSE_BASIS_CONTRACT",
            "location": "adversarial witness",
            "warrant": "A deliberately false component must not disappear behind the authored boundary.",
            "coordinate": "KNOW",
            "state": "+1",
        }
    )
    assert reconstruct_profile(two, rulebook)["definition_check"] == "CONFLICT"
