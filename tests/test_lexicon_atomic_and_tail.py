"""Declared prime vectors, conditional bank laws, and the bounded model seam."""

import copy
from pathlib import Path

import pytest

from gse.lexicon_builder.atomics import atomic_proof
from gse.lexicon_builder.basis import OPPOSITE_POLES, PRIMES
from gse.lexicon_builder.core import CANONICAL_COORDINATES, Cell, Observation, resolve
from gse.lexicon_builder.foundation import load_foundation, profile_seed, reconstruct_profile
from gse.lexicon_builder.model import OllamaSelector
from gse.lexicon_builder.perception import perception_constraints
from gse.lexicon_builder.reading import ask, construct_reading
from gse.lexicon_builder.registry import compile_law, load_rulebook
from gse.lexicon_builder.sources import NativeSources
from tests.lexicon_rulebook import certify_rule
from tests.lexicon_sources import requires_lexicon_sources

EXAMINED = set(PRIMES)


def test_all_examined_primes_reconstruct_completely():
    result = atomic_proof()
    assert result["code"] == "RECONSTRUCTED_PRIME_FOUNDATION"
    assert result["definition_checks"] == {"RECONSTRUCTED": 72}
    assert len(result["records"]) == 72
    for record in result["records"]:
        assert set(record["vector"]) == set(CANONICAL_COORDINATES)
        assert record["reading_id"] == "prime:" + record["prime"]
        assert record["production_eligible"] is False
        assert record["prime"] in EXAMINED
        assert record["definition_review"] == "EXAMINED"
        assert record["code"] == "CANDIDATE_COMPLETE" and record["definition_check"] == "RECONSTRUCTED"
        assert set(record["decision_checks"].values()) == {"RECONSTRUCTED"}
        assert "unresolved" not in record["vector"].values()


def test_a_local_draft_fixture_never_applies_its_proposed_boundary():
    you = copy.deepcopy(next(p for p in load_foundation()["profiles"] if p["prime"] == "YOU"))
    boundary = next(d for d in you["definition_axiom"]["decisions"] if d["state"] == "empty")
    you["definition_axiom"] = {"review": "DRAFT", "unexamined_boundary_proposal": boundary["coordinates"]}
    you["profile_status"] = "SOURCED_PROFILE"
    you["remaining_cells"] = "UNRESOLVED_UNTIL_EXAMINED"
    rebuilt = reconstruct_profile(you, load_rulebook())
    assert rebuilt["definition_review"] == "DRAFT"
    assert rebuilt["code"] == "PARTIAL" and rebuilt["definition_check"] == "BOUNDARY_PENDING"
    assert not any(r.startswith("PRIME_BOUNDARY:") for r in rebuilt["after_selection"]["fired_rules"])
    assert "empty" not in rebuilt["vector"].values()
    assert {c for c, v in rebuilt["vector"].items() if v == "unresolved"} == set(boundary["coordinates"])


def test_opposite_poles_share_one_coordinate_with_opposite_signs():
    records = {r["prime"]: r for r in atomic_proof()["records"]}
    for positive, negative in OPPOSITE_POLES:
        assert records[positive]["vector"][positive] == "+1"
        assert records[negative]["vector"][positive] == "-1"
        if {positive, negative} <= EXAMINED:
            # Both poles examined: the rest of the definition is the same, sign for sign.
            assert {k: v for k, v in records[positive]["vector"].items() if k != positive} == {
                k: v for k, v in records[negative]["vector"].items() if k != positive
            }
    assert {p for pair in OPPOSITE_POLES for p in pair if {*pair} <= EXAMINED} == {
        p for pair in OPPOSITE_POLES for p in pair
    }


def test_a_sourced_profile_must_not_override_a_conflicting_bank_law():
    book = load_rulebook()
    book["laws"].append(
        certify_rule(
            {
                "rule_id": "TEST_CONTRARY_GOOD",
                "review_state": "SOURCE_JUSTIFIED",
                "coordinates": ["GOOD"],
                "allowed": [["0"]],
                "guard": [],
                "warrant": "mechanism-only negative witness",
            },
            positive="tests/test_lexicon_atomic_and_tail.py::test_a_sourced_profile_must_not_override_a_conflicting_bank_law",
            must_not="tests/test_lexicon_atomic_and_tail.py::test_a_sourced_profile_must_not_override_a_conflicting_bank_law",
        )
    )
    result = atomic_proof(book)
    assert result["code"] == "FOUNDATION_CONFLICT"
    assert next(r for r in result["records"] if r["prime"] == "GOOD")["code"] == "CONFLICT"


def test_removing_the_only_degree_warrant_reopens_intensity():
    book = load_rulebook()
    profile = next(p for p in load_foundation()["profiles"] if p["prime"] == "GOOD")
    retained = {c["claim_id"] for c in profile["claims"] if c["kind"] != "ESTABLISHES_DEGREE_DOMAIN"}
    record = construct_reading(profile_seed(profile, "good", retained), book, None)
    assert "INTENSITY" not in record["after_selection"]["forced"]
    assert len(record["after_selection"]["domains"]["INTENSITY"]) > 1
    # Provenance moves with the warrant: the degree law no longer fires and only its decision reopens.
    rebuilt = reconstruct_profile(profile, book, retained)
    assert "OWN_DEGREE_BEARING_CONTENT" not in rebuilt["after_selection"]["fired_rules"]
    assert rebuilt["definition_check"] == "UNRESOLVED"
    assert {k for k, v in rebuilt["decision_checks"].items() if v != "RECONSTRUCTED"} == {"GOOD:D2"}


def test_feeling_kind_relation_propagates_only_with_its_scope_and_antecedent():
    book = load_rulebook()
    relation = compile_law(next(r for r in book["laws"] if r["rule_id"] == "FEELING_DENOTATUM_IS_NOT_A_CATEGORY"))
    fact = Observation("love:feeling", "founder", "own-feeling-reading", "own_denotatum", "affective_feeling", True)
    before = resolve("love:feeling", (fact,), laws=(relation,))
    assert "KIND" not in before.forced()
    after = resolve("love:feeling", (fact,), seed="FEEL", laws=(relation,))
    assert after.forced()["KIND"] == Cell.ZERO
    without_scope = resolve("category-of-feelings", seed="FEEL", laws=(relation,))
    assert "KIND" not in without_scope.forced()


@requires_lexicon_sources
def test_native_perception_and_modality_are_complementary_views():
    sources = NativeSources(["overhear", "glimpse"], Path("data/external"), Path.home() / "nltk_data/corpora")
    book = load_rulebook()
    result = {}
    for word in ("overhear", "glimpse"):
        native = sources.for_word(word)
        frame = next(
            f
            for r in native["verbnet"]["records"]
            for f in r["values"]["frames"]
            if any(p["predicate"]["value"] == "perceive" for p in f["predicates"])
        )
        projection = perception_constraints(word, frame, native, book, None, {})
        result[word] = resolve(word, laws=tuple(projection["laws"])).forced()
    assert result["overhear"] == {"HEAR": Cell.PLUS}
    assert result["glimpse"] == {"SEE": Cell.PLUS}


def test_a_sound_tag_without_a_perception_function_cannot_assign_hear():
    native = {
        "usas": {"records": [{"record_id": "one", "values": {"pos": "VERB", "alternatives": ["X3.2"]}}]},
        "framenet": {"records": []},
    }
    projection = perception_constraints(
        "clang", {"predicates": [{"predicate": {"value": "emit"}, "arguments": []}]}, native, load_rulebook(), None, {}
    )
    assert projection["laws"] == []


def test_model_receives_one_typed_field_and_its_answer_is_propagated_once():
    class Selector(OllamaSelector):
        calls = 0

        def select(self, payload, options):
            self.calls += 1
            assert payload["decision"] == {"PERCEPTION_MODE": None}
            assert set(options) == {"PERCEPTION_MODE"}
            assert "typed_anchors" in payload
            return {"answer": {"PERCEPTION_MODE": "VISION"}, "request_sha256": "test-request"}

    frame = {"predicates": [{"predicate": {"value": "perceive"}, "arguments": []}]}
    native = {"usas": {"records": []}, "framenet": {"records": []}}
    selector, cache = Selector(), {}
    first = perception_constraints("test-word", frame, native, load_rulebook(), selector, cache)
    second = perception_constraints("test-word", copy.deepcopy(frame), native, load_rulebook(), selector, cache)
    assert selector.calls == 1
    assert second["calls"][0]["cache_hit"] is True
    result = resolve("test-word", laws=tuple(first["laws"]))
    assert result.forced() == {"SEE": Cell.PLUS}


def test_a_cached_answer_is_reused_only_for_the_same_field_and_legal_options():
    class Selector(OllamaSelector):
        calls = 0

        def select(self, payload, options):
            self.calls += 1
            return {"answer": {key: values[0] for key, values in options.items()}, "request_sha256": "test-request"}

    payload, selector, cache = {"schema": "TEST"}, Selector(), {}
    assert ask("MODE", ["VISION", "UNRESOLVED"], payload, selector, cache)["answer"] == {"MODE": "VISION"}
    # MUST-NOT: the same payload offering other legal options, or another field, cannot reuse that answer.
    assert ask("MODE", ["HEARING", "UNRESOLVED"], payload, selector, cache)["answer"] == {"MODE": "HEARING"}
    assert ask("OTHER", ["VISION", "UNRESOLVED"], payload, selector, cache)["answer"] == {"OTHER": "VISION"}
    assert selector.calls == 3
    # Positive control: the identical decision is asked once.
    assert ask("MODE", ["HEARING", "UNRESOLVED"], payload, selector, cache)["cache_hit"] is True
    assert selector.calls == 3


def test_a_cached_answer_outside_the_legal_options_is_refused():
    class Selector(OllamaSelector):
        def select(self, payload, options):
            return {"answer": {"MODE": "VISION"}, "request_sha256": "test-request"}

    cache = {}
    ask("MODE", ["VISION"], {"schema": "TEST"}, Selector(), cache)
    (key,) = cache
    cache[key]["answer"] = {"MODE": "HEARING"}
    with pytest.raises(ValueError, match="legal options"):
        ask("MODE", ["VISION"], {"schema": "TEST"}, Selector(), cache)
