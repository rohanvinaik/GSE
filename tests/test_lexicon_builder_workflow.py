"""Positive intent and MUST-NOT specifications for the actual constructor."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from gse.lexicon_builder.build import build, construct, source_matches
from gse.lexicon_builder.core import CANONICAL_COORDINATES
from gse.lexicon_builder.model import OllamaSelector, selection_status
from gse.lexicon_builder.registry import candidate_id, export_candidates, load_rulebook
from gse.lexicon_builder.sources import NativeSources
from tests.lexicon_rulebook import admitted_rulebook, certify_rule
from tests.lexicon_sources import requires_lexicon_sources

# Row 3b (F144): an adjective's own reading heads no substantive, so these are explicit absence.
HEADS_NO_SUBSTANTIVE = {c: "0" for c in ("I", "YOU", "SOMEONE", "PEOPLE", "BODY", "KIND", "PART")}


@pytest.fixture
def quality_native():
    native = {
        s: {"scope": "WORD", "units": "native", "status": "NO_RECORD", "records": []}
        for s in ("usas", "framenet", "vad", "emotion", "lancaster", "concreteness")
    }
    native["usas"]["records"] = [
        {"record_id": "USAS:1", "values": {"lemma": "excellent", "pos": "ADJ", "alternatives": ["A5.1+++"]}}
    ]
    native["framenet"]["records"] = [{"record_id": "FN:1", "values": {"pos": "a", "frame": "Desirability"}}]
    return native


class RecordedSelector:
    def __init__(self, values=None, missing="NONE"):
        self.values = values or {}
        self.missing = missing
        self.calls = []

    def select(self, payload, options):
        self.calls.append((payload, options))
        if payload["operation"] == "BANK_OMISSION_REVIEW":
            answer = {
                key: "MISSING" if self.missing in payload["bank_accounts"][key]["coordinate_domains"] else "ACCOUNTED"
                for key in options
            }
        elif payload["operation"] == "LOCATE_BANK_OMISSION":
            answer = {key: self.missing if self.missing in values else "UNRESOLVED" for key, values in options.items()}
        else:
            answer = {key: self.values.get(key, "+1") for key in options}
        assert selection_status(options, answer) == "VALID_SELECTION"
        return {"request_sha256": f"test-{len(self.calls)}", "answer": answer}


def test_selection_requires_an_actual_nonempty_decision():
    assert selection_status({}, {}) == "EMPTY_DECISION"


def test_selection_accepts_only_the_exact_remaining_enum():
    assert selection_status({"FEEL": ["+1", "empty"]}, {"FEEL": "+1"}) == "VALID_SELECTION"
    assert selection_status({"FEEL": ["+1", "empty"]}, {"FEEL": "empty"}) == "VALID_SELECTION"


def test_selection_never_accepts_unpaired_minus_or_written_zero_without_a_domain():
    assert selection_status({"FEEL": ["+1", "empty"]}, {"FEEL": "-1"}) == "ILLEGAL_VALUE"
    assert selection_status({"FEEL": ["+1", "empty"]}, {"FEEL": "0"}) == "ILLEGAL_VALUE"
    assert selection_status({"FEEL": ["+1", "empty"]}, {"FEEL": 1}) == "ILLEGAL_VALUE"


def test_selection_never_accepts_extra_missing_or_substituted_fields():
    assert selection_status({"FEEL": ["+1"]}, {}) == "FIELD_MISMATCH"
    assert selection_status({"FEEL": ["+1"]}, {"FEEL": "+1", "GOOD": "+1"}) == "FIELD_MISMATCH"
    assert selection_status({"FEEL": ["+1"]}, {"GOOD": "+1"}) == "FIELD_MISMATCH"


def test_symbolic_sources_combine_but_association_cannot_become_a_prime(quality_native):
    book = load_rulebook()
    matches = source_matches(quality_native, book)
    assert len(matches) == 1
    first = construct("excellent", matches[0], quality_native, book, None)
    changed = copy.deepcopy(quality_native)
    changed["emotion"]["records"] = [
        {"record_id": "NRC:unrelated", "values": {"anger": 1, "disgust": 1, "negative": 1}}
    ]
    second = construct("excellent", source_matches(changed, book)[0], changed, book, None)
    assert first["symbolic_before"] == second["symbolic_before"]
    assert first["symbolic_before"]["forced"] == {
        "GOOD": "+1",
        "BIG": "0",
        "SOMETHING": "0",
        "INTENSITY": "+1",
        **HEADS_NO_SUBSTANTIVE,
    }
    assert first["candidate_vector"] is None
    assert first["code"] == "PARTIAL"


def test_removing_either_typed_premise_reopens_the_source_projection(quality_native):
    book = load_rulebook()
    no_frame = copy.deepcopy(quality_native)
    no_frame["framenet"]["records"] = []
    assert source_matches(no_frame, book) == []
    no_tag = copy.deepcopy(quality_native)
    no_tag["usas"]["records"] = []
    assert source_matches(no_tag, book) == []
    noun = copy.deepcopy(quality_native)
    noun["usas"]["records"][0]["values"]["pos"] = "NOUN"
    assert source_matches(noun, book) == []


def test_joint_membership_and_alternative_readings_are_not_dropped(quality_native):
    book = load_rulebook()
    quality_native["usas"]["records"][0]["values"]["alternatives"] = ["A5.1+++/E4.1+", "E3-"]
    assert source_matches(quality_native, book) == []


def test_degree_presence_is_symbolic_and_candidate_mask_status_stays_provisional(quality_native):
    book = load_rulebook()
    match = source_matches(quality_native, book)[0]
    selector = RecordedSelector()
    result = construct("excellent", match, quality_native, book, selector, bank_review=True)
    assert result["code"] == "PARTIAL"
    assert result["candidate_vector"] is None
    assert result["completion_status"] == "UNPROVEN_COVERAGE"
    assert result["production_eligible"] is False
    assert result["decisions"] == []
    assert result["symbolic_before"]["forced"]["INTENSITY"] == "+1"
    assert "OWN_DEGREE_BEARING_CONTENT" in result["symbolic_before"]["fired_rules"]
    assert len(result["provisional_vector"]["states"]) == 58
    assert result["provisional_vector"]["states"]["GOOD"] == "+1"
    assert result["provisional_vector"]["states"]["FEEL"] == "empty"
    assert "FEEL" in result["provisional_vector"]["provisional_silence"]
    assert result["after_closure"] is None
    assert len(selector.calls) == 2
    assert list(selector.calls[0][1]) == ["BANK_0", "BANK_1", "BANK_2", "BANK_3", "BANK_4"]
    assert result["coverage_review"]["code"] == "BANKS_ACCOUNTED"
    assert len(result["coverage_review"]["rounds"][0]["accounts"]) == 8
    assert result["number_scale"]["numeric_gain"] is None


def test_bank_review_is_opt_in_and_cannot_change_an_exported_vector(quality_native):
    # Deliberate stage-0 behavior change: the review's accounts cannot license
    # silence, so a default build spends no model calls on it.
    book = load_rulebook()
    match = source_matches(quality_native, book)[0]
    selector = RecordedSelector()
    default = construct("excellent", match, quality_native, book, selector)
    reviewed = construct("excellent", match, quality_native, book, RecordedSelector(), bank_review=True)
    assert selector.calls == []
    assert default["coverage_review"]["code"] == "NOT_CHECKED"
    assert default["provisional_vector"] is None
    assert reviewed["coverage_review"]["code"] == "BANKS_ACCOUNTED"
    assert default["candidate_vector"] is reviewed["candidate_vector"] is None
    assert default["after_selection"] == reviewed["after_selection"]


def test_missing_component_challenge_must_prevent_complete_candidate(quality_native):
    book = load_rulebook()
    result = construct(
        "excellent",
        source_matches(quality_native, book)[0],
        quality_native,
        book,
        RecordedSelector(missing="THINK"),
        bank_review=True,
    )
    assert result["code"] == "PARTIAL"
    assert result["candidate_vector"] is None
    assert result["omission_challenge"] == "THINK"


def test_one_model_choice_can_force_another_field_without_a_second_selection(quality_native):
    # Mechanism-only relation, explicitly not a proposed English law.
    book = load_rulebook()
    book["source_rules"][0]["residual"] = ["THINK", "WANT"]
    book["source_rules"][0]["model_selection_policy"] = {
        "task_type": "SYNTHETIC_COUPLED_CHOICE",
        "status": "ADMITTED",
        "coordinates": ["THINK", "WANT"],
        "reason": "Mechanics fixture; not a production lexical acceptance claim",
        "evidence_refs": ["tests/test_lexicon_builder_workflow.py"],
    }
    certify_rule(book["source_rules"][0])
    book["laws"].append(
        certify_rule(
            {
                "rule_id": "SYNTHETIC_EQUAL_COMPONENTS",
                "review_state": "FOUNDER_APPROVED",
                "coordinates": ["THINK", "WANT"],
                "allowed": [["+1", "+1"], ["empty", "empty"]],
                "guard": [],
                "warrant": "synthetic propagation witness",
            }
        )
    )
    selector = RecordedSelector()
    result = construct(
        "excellent", source_matches(quality_native, book)[0], quality_native, book, selector, bank_review=True
    )
    assert result["after_selection"]["forced"]["WANT"] == "+1"
    assert [d["selected"] for d in result["decisions"]] == [{"THINK": "+1"}]
    assert len(selector.calls) == 3  # one selection, two batches reviewing all eight banks
    assert any(
        s["rule"] == "SYNTHETIC_EQUAL_COMPONENTS" and s["coordinate"] == "WANT"
        for s in result["after_selection"]["trace"]
    )


def test_decoder_receives_the_schema_and_only_structured_input(monkeypatch):
    requests = []

    def request(self, route, payload=None):
        if route == "/api/tags":
            return {"models": [{"name": "qwen3.5:4b", "digest": "test-pin"}]}
        requests.append(payload)
        return {"message": {"content": '{"INTENSITY":"+1"}'}}

    monkeypatch.setattr(OllamaSelector, "_request", request)
    record = OllamaSelector("qwen3.5:4b").select(
        {"word": "excellent", "fields": {"INTENSITY": None}}, {"INTENSITY": ["empty", "+1"]}
    )
    request = requests[0]
    assert request["format"]["properties"]["INTENSITY"]["enum"] == ["empty", "+1"]
    assert request["format"]["additionalProperties"] is False
    assert all(isinstance(json.loads(m["content"]), dict) for m in request["messages"])
    assert record["model"]["digest"] == "test-pin"


def test_coherence_catalog_never_self_promotes_to_lexical_law(tmp_path):
    relation = {
        "antecedents": ["emotion:disgust=1"],
        "consequent": "vad:valence_sign=negative",
        "all_counterexamples": ["counterexample"],
        "overall": {"support": 10},
    }
    path = tmp_path / "results.json"
    path.write_text(
        json.dumps(
            {
                "pair_relations": [relation],
                "conjunction_relations": [],
                "script_sha256": "pin",
                "candidate_policy": {},
                "sources": [],
            }
        )
    )
    manifest = export_candidates(path, tmp_path / "registry")
    saved = json.loads(Path(manifest["catalog"]).read_text())
    assert saved["rule_id"] == candidate_id(relation)
    assert saved["may_write_lexical_cells"] is False
    assert saved["relation"]["all_counterexamples"] == ["counterexample"]


@requires_lexicon_sources
def test_actual_native_word_records_feed_the_same_builder():
    sources = NativeSources(["excellent", "furious"], Path("data/external"), Path.home() / "nltk_data/corpora")
    records = list(build(["excellent", "furious"], sources, admitted_rulebook("USAS_OWN_QUALITY_POLE"), None))
    assert records[0]["readings"][0]["symbolic_before"]["forced"]["GOOD"] == "+1"
    assert records[1]["readings"][0]["source_scope"] == "LEMMA_POS_HEAD_CONTRACT"
    assert "FEEL" not in records[1]["readings"][0]["symbolic_before"]["forced"]
    assert "GOOD" not in records[1]["readings"][0]["symbolic_before"]["forced"]
    assert records[1]["native"]["emotion"]["records"][0]["values"]["disgust"] == 1
    assert records[1]["code"] == "CONSTRUCTED_READINGS"
    assert len(CANONICAL_COORDINATES) == 58


@requires_lexicon_sources
def test_affective_category_assigns_degree_domain_and_propagates_kind_without_story_components():
    sources = NativeSources(["delighted"], Path("data/external"), Path.home() / "nltk_data/corpora")
    selector = RecordedSelector()
    book = admitted_rulebook("USAS_OWN_HAPPY_SAD_STATE")
    record = list(build(["delighted"], sources, book, selector, bank_review=True))[0]
    reading = record["readings"][0]
    assert reading["symbolic_before"]["forced"] == {
        "GOOD": "+1",
        "FEEL": "+1",
        "SOMETHING": "0",
        "INTENSITY": "+1",
        **HEADS_NO_SUBSTANTIVE,
    }
    assert reading["code"] == "PARTIAL"
    assert reading["candidate_vector"] is None
    assert reading["provisional_vector"]["states"]["INTENSITY"] == "+1"
    assert list(selector.calls[0][1]) == ["BANK_0", "BANK_1", "BANK_2", "BANK_3", "BANK_4"]
    assert len(selector.calls) == 2
    assert reading["after_closure"] is None
    assert reading["provisional_closure"]["code"] == "RESOLVED"
    assert "FEELING_DENOTATUM_IS_NOT_A_CATEGORY" in reading["after_selection"]["fired_rules"]
    assert "THINK" not in reading["after_selection"]["forced"]
    assert "WANT" not in reading["after_selection"]["forced"]


@requires_lexicon_sources
def test_affective_omission_keeps_the_vector_open_instead_of_underencoding():
    sources = NativeSources(["delighted"], Path("data/external"), Path.home() / "nltk_data/corpora")
    book = admitted_rulebook("USAS_OWN_HAPPY_SAD_STATE")
    reading = list(build(["delighted"], sources, book, RecordedSelector(missing="THINK"), bank_review=True))[0][
        "readings"
    ][0]
    assert reading["code"] == "PARTIAL"
    assert reading["candidate_vector"] is None
    assert reading["after_closure"] is None
    assert reading["after_selection"]["forced"]["FEEL"] == "+1"


def test_unavailable_source_and_observed_zero_remain_different(tmp_path):
    (tmp_path / "nrc_emotion.txt").write_text("example\tdisgust\t0\n")
    sources = NativeSources(["example", "absent"], tmp_path, tmp_path / "nltk")
    native = sources.for_word("example")
    assert native["emotion"]["status"] == "OBSERVED"
    assert native["emotion"]["records"][0]["values"]["disgust"] == 0
    assert native["usas"]["status"] == "UNAVAILABLE"
    assert sources.for_word("absent")["emotion"]["status"] == "NO_RECORD"
    assert source_matches(native, load_rulebook()) == []


def test_a_fully_constrained_problem_can_still_complete_via_one_bounded_choice(quality_native):
    # Mechanism-only closed problem. This is NOT a proposed English definition.
    book = load_rulebook()
    book["source_rules"][0]["residual"] = ["THINK", "WANT"]
    book["source_rules"][0]["model_selection_policy"] = {
        "task_type": "SYNTHETIC_COUPLED_CHOICE",
        "status": "ADMITTED",
        "coordinates": ["THINK", "WANT"],
        "reason": "Mechanics fixture; not a production lexical acceptance claim",
        "evidence_refs": ["tests/test_lexicon_builder_workflow.py"],
    }
    certify_rule(book["source_rules"][0])
    book["laws"].append(
        certify_rule(
            {
                "rule_id": "TEST_COUPLED_CHOICE",
                "review_state": "FOUNDER_APPROVED",
                "coordinates": ["THINK", "WANT"],
                "allowed": [["+1", "+1"], ["empty", "empty"]],
                "guard": [],
                "warrant": "Synthetic closed-problem intent fixture",
            }
        )
    )
    for c in CANONICAL_COORDINATES:
        if c not in {"GOOD", "BIG", "SOMETHING", "INTENSITY", "THINK", "WANT", *HEADS_NO_SUBSTANTIVE}:
            book["laws"].append(
                certify_rule(
                    {
                        "rule_id": "TEST_SILENCE_" + c,
                        "review_state": "FOUNDER_APPROVED",
                        "coordinates": [c],
                        "allowed": [["empty"]],
                        "guard": [],
                        "warrant": "Explicit fixture declaration, never a missing-data default",
                    }
                )
            )
    selector = RecordedSelector()
    result = construct("fixture", source_matches(quality_native, book)[0], quality_native, book, selector)
    assert result["code"] == "CANDIDATE_COMPLETE"
    assert result["completion_status"] == "CONSTRAINT_RESOLVED"
    assert result["candidate_vector"]["states"]["THINK"] == "+1"
    assert result["candidate_vector"]["states"]["WANT"] == "+1"
    assert result["candidate_vector"]["provisional_silence"] == []
    assert len(selector.calls) == 1
    assert selector.calls[0][1] == {"THINK": ["+1", "empty", "ABSTAIN"]}
