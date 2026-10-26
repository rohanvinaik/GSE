"""Independent rule witnesses: scope, admission and exact local retraction."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from gse.lexicon_builder.build import construct, source_matches
from gse.lexicon_builder.conditionals import (
    CatalogError,
    catalog_entry_status,
    catalog_report,
    compile_catalog,
    evaluate_catalog,
    load_catalog,
    native_feature_evidence,
)
from gse.lexicon_builder.core import (
    LEGACY_APPROVAL_CONTRACTS,
    Cell,
    Law,
    Observation,
    RuleException,
    RuleExceptionError,
    admitted_laws,
    law_admission_status,
    law_application_id,
    resolve,
    rule_admission_reason,
    rule_contract_digest,
)
from gse.lexicon_builder.native_constraints import frame_constraints
from gse.lexicon_builder.registry import admission_report, candidate_id, load_rulebook, split_by_admission
from tests.lexicon_rulebook import certify_rule

SUBSTANTIVES = ("I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY", "KIND", "PART")
HEAD_ROLES = (
    ("VERB_HEADS_NO_SUBSTANTIVE", "lexical_predicate"),
    ("OPERATOR_HEADS_NO_SUBSTANTIVE", "non_substantive_operator"),
    ("TIME_PLACE_HEADS_NO_SUBSTANTIVE", "time_or_place_relation"),
    ("FEELING_NOUN_HEAD", "feeling_substantive"),
)


def fact(field: str, value: str, reading_id: str = "fixture") -> Observation:
    return Observation(reading_id, "independent-native-source", "source:located-reading", field, value, True)


def one_rule(rule_id: str) -> tuple[Law, ...]:
    return tuple(law for law in admitted_laws(load_rulebook()) if law.rule_id == rule_id)


@pytest.mark.parametrize(("rule_id", "role"), HEAD_ROLES)
def test_head_rules_write_the_located_head_contract(rule_id, role):
    result = resolve("fixture", (fact("own_role", role),), laws=one_rule(rule_id))
    expected = {c: Cell.PLUS if role == "feeling_substantive" and c == "SOMETHING" else Cell.ZERO for c in SUBSTANTIVES}
    assert result.forced() == expected
    assert result.fired_rules == (rule_id,)


@pytest.mark.parametrize(("rule_id", "role"), HEAD_ROLES)
def test_head_rules_do_not_infer_a_head_from_pos_or_another_reading(rule_id, role):
    laws = one_rule(rule_id)
    assert len(laws) == 1  # the negative control is not vacuous
    unrelated = (fact("pos", "NOUN"), fact("own_role", role, "other-reading"))
    assert resolve("fixture", unrelated, laws=laws).forced() == {}
    assert resolve("fixture", (fact("own_role", "substantive"),), laws=laws).forced() == {}


def test_substantive_one_hot_requires_a_located_prime_identity():
    observations = (fact("own_role", "substantive"), fact("lexical_unit_kind", "PRIME"))
    result = resolve("fixture", observations, seed="I", laws=one_rule("SUBSTANTIVE_HEAD_IS_ONE_HOT"))
    assert result.forced() == {c: Cell.PLUS if c == "I" else Cell.ZERO for c in SUBSTANTIVES}


def test_substantive_one_hot_never_closes_an_ordinary_noun():
    laws = one_rule("SUBSTANTIVE_HEAD_IS_ONE_HOT")
    assert len(laws) == 1
    result = resolve("fixture", (fact("own_role", "substantive"),), seed="SOMETHING", laws=laws)
    assert result.forced() == {"SOMETHING": Cell.PLUS}
    assert "SUBSTANTIVE_HEAD_IS_ONE_HOT" not in result.fired_rules


@pytest.mark.parametrize(
    ("rule_id", "kind", "prime", "absent"),
    [
        ("EVALUATOR_EXCLUDES_SIZE", "evaluator", "GOOD", "BIG"),
        ("SIZE_DESCRIPTOR_EXCLUDES_EVALUATION", "size_descriptor", "BIG", "GOOD"),
    ],
)
def test_evaluator_and_size_exclusions_follow_the_own_head(rule_id, kind, prime, absent):
    result = resolve("fixture", (fact("own_semantic_kind", kind),), seed=prime, laws=one_rule(rule_id))
    assert result.forced()[absent] == Cell.ZERO


@pytest.mark.parametrize(
    ("rule_id", "prime", "unresolved"),
    [("EVALUATOR_EXCLUDES_SIZE", "GOOD", "BIG"), ("SIZE_DESCRIPTOR_EXCLUDES_EVALUATION", "BIG", "GOOD")],
)
def test_component_presence_does_not_classify_the_head(rule_id, prime, unresolved):
    laws = one_rule(rule_id)
    assert len(laws) == 1
    result = resolve("fixture", (fact("own_valence_domain", "signed_felt_pole"),), seed=prime, laws=laws)
    assert unresolved not in result.forced()


def test_fear_aversion_requires_both_components_in_the_fear_scope():
    roots = (
        Law("INDEPENDENT_FEEL", ("FEEL",), ((Cell.PLUS,),), (), "source fact"),
        Law("INDEPENDENT_THINK", ("THINK",), ((Cell.PLUS,),), (), "source fact"),
    )
    result = resolve("fixture", (fact("source_frame_family", "Fear"),), laws=one_rule("FEAR_AVERSION") + roots)
    assert result.forced()["WANT"] == result.forced()["NOT"] == Cell.PLUS


def test_fear_aversion_never_turns_arbitrary_feeling_or_negation_into_want():
    rule = one_rule("FEAR_AVERSION")
    assert len(rule) == 1
    feel = Law("FEEL_SOURCE", ("FEEL",), ((Cell.PLUS,),), (), "source fact")
    think = Law("THINK_SOURCE", ("THINK",), ((Cell.PLUS,),), (), "source fact")
    assert "WANT" not in resolve("fixture", laws=rule + (feel, think)).forced()
    assert "WANT" not in resolve("fixture", (fact("source_frame_family", "Fear"),), laws=rule + (feel,)).forced()


def test_signed_felt_domain_excludes_zero_but_does_not_choose_a_pole():
    result = resolve(
        "fixture", (fact("own_valence_domain", "signed_felt_pole"),), laws=one_rule("SIGNED_FELT_VALENCE_DOMAIN")
    )
    assert set(result.domains["GOOD"]) == {Cell.MINUS, Cell.PLUS}
    assert "GOOD" not in result.forced()


def test_unsigned_feeling_and_emotion_association_do_not_exclude_zero():
    laws = one_rule("SIGNED_FELT_VALENCE_DOMAIN")
    assert len(laws) == 1
    result = resolve("fixture", (fact("emotion:negative", "1"),), seed="FEEL", laws=laws)
    assert Cell.ZERO in result.domains["GOOD"] and Cell.SILENT in result.domains["GOOD"]


def fear_native(pos: str) -> dict:
    return {
        "usas": {"records": [{"record_id": "usas:fear", "values": {"pos": pos, "alternatives": ["E5-"]}}]},
        "framenet": {
            "records": [{"record_id": "fn:fear", "values": {"pos": "n" if pos == "NOUN" else "v", "frame": "Fear"}}]
        },
    }


def test_fear_noun_template_constructs_a_feeling_head_through_the_real_builder():
    book, _ = split_by_admission(load_rulebook())
    native = fear_native("NOUN")
    matches = [m for m in source_matches(native, book) if m["rule"]["rule_id"] == "EMOTION_FEAR_NOUN"]
    assert len(matches) == 1
    reading = construct("fixture", matches[0], native, book, None)
    forced = reading["after_selection"]["forced"]
    assert forced["SOMETHING"] == "+1" and forced["GOOD"] == "-1"
    assert forced["WANT"] == forced["NOT"] == "+1"


def test_fear_noun_template_does_not_claim_a_verb_or_an_unaligned_frame():
    book, _ = split_by_admission(load_rulebook())
    native = fear_native("VERB")
    assert not any(m["rule"]["rule_id"] == "EMOTION_FEAR_NOUN" for m in source_matches(native, book))
    native = fear_native("NOUN")
    native["framenet"]["records"][0]["values"]["frame"] = "Desirability"
    assert not any(m["rule"]["rule_id"] == "EMOTION_FEAR_NOUN" for m in source_matches(native, book))


def native_predicate(name: str, event: str, role: str, negative: bool = False) -> dict:
    return {
        "predicate": {"value": name, **({"bool": "!"} if negative else {})},
        "arguments": [{"type": "Event", "value": event}, {"type": "ThemRole", "value": role}],
    }


def test_typed_affective_and_existence_projections_write_their_own_content():
    book, _ = split_by_admission(load_rulebook())
    affect = {"predicates": [native_predicate("emotional_state", "during(E)", "Experiencer")]}
    native = {"usas": {"records": [{"values": {"pos": "VERB", "alternatives": ["E5-"]}}]}}
    assert resolve("fixture", laws=frame_constraints(affect, book, native)["laws"]).forced()["FEEL"] == Cell.PLUS
    existence = {"class": "exist-47.1", "predicates": [native_predicate("exist", "during(E)", "Theme")]}
    assert resolve("fixture", laws=frame_constraints(existence, book)["laws"]).forced()["EXIST"] == Cell.PLUS


def test_affective_join_and_participant_existence_never_invent_lexical_content():
    book, _ = split_by_admission(load_rulebook())
    affect = {"predicates": [native_predicate("emotional_state", "during(E)", "Experiencer")]}
    projected = frame_constraints(affect, book)
    assert "FEEL" not in resolve("fixture", laws=projected["laws"]).forced()
    assert any(r["code"] == "UNALIGNED_AFFECTIVE_READING" for r in projected["unmapped"])
    static = {"class": "kill-42.1", "predicates": [native_predicate("exist", "during(E)", "Patient")]}
    projected = frame_constraints(static, book)
    assert "EXIST" not in resolve("fixture", laws=projected["laws"]).forced()
    assert any(r["code"] == "PARTICIPANT_EXISTENCE_PRESUPPOSITION" for r in projected["unmapped"])


def test_validation_receipt_pins_every_contract_field_except_itself():
    record = certify_rule(
        {
            "rule_id": "FIXTURE",
            "kind": "SCOPED_BANK_RELATION",
            "guard": [],
            "coordinates": ["KNOW"],
            "allowed": [["+1"]],
        }
    )
    assert rule_admission_reason(record) == "ADMITTED_VALIDATED"
    baseline = rule_contract_digest(record)
    record["validation"]["positive"].append(
        "tests/test_lexicon_conditional_rules.py::test_validation_receipt_pins_every_contract_field_except_itself"
    )
    assert rule_contract_digest(record) == baseline
    for key, value in (
        ("allowed", [["0"]]),
        ("guard", [["own_role", "substantive"]]),
        ("authority", {"kind": "NSM", "refs": ["changed"]}),
    ):
        changed = copy.deepcopy(record)
        changed[key] = value
        assert rule_admission_reason(changed) == "STALE_RULE_VALIDATION"


def test_review_stamps_correlations_and_truthy_metadata_cannot_grant_admission():
    assert (
        rule_admission_reason({"rule_id": "NEW", "review_state": "FOUNDER_APPROVED"}) == "UNRECORDED_FOUNDER_APPROVAL"
    )
    candidate = certify_rule({"rule_id": "NATIVE", "kind": "NATIVE_ASSOCIATION", "may_write_lexical_cells": False})
    assert rule_admission_reason(candidate) == "NON_LEXICAL_RULE"
    candidate["may_write_lexical_cells"] = "yes"
    assert rule_admission_reason(candidate) == "MALFORMED_RULE"
    empirical = certify_rule({"rule_id": "EMPIRICAL", "tier": "FOUNDATIONAL"})
    empirical["authority"]["kind"] = "EMPIRICAL"
    assert rule_admission_reason(empirical) == "EMPIRICAL_REQUIRES_CONDITIONAL"
    for malformed in (None, [], {"rule_id": []}, {"rule_id": "bad", "review_state": []}):
        assert law_admission_status(malformed) == "NOT_ADMITTED"


def test_live_admission_report_preserves_frozen_legacy_and_validated_paths():
    book = load_rulebook()
    report = admission_report(book)
    assert report["reason_counts"]["ADMITTED_LEGACY_APPROVAL"] == len(LEGACY_APPROVAL_CONTRACTS)
    assert report["reason_counts"]["ADMITTED_VALIDATED"] >= 12
    current = {r["rule_id"]: r for r in report["records"]}
    assert current["USAS_OWN_HAPPY_SAD_STATE"]["reason"] == "UNREVIEWED_RULE"
    assert current["VN_AFFECTIVE_STATE"]["reason"] == current["VN_EXISTENCE"]["reason"] == "ADMITTED_VALIDATED"


def conditional(application: str, coordinate: str = "FEEL") -> Law:
    return Law("RULE", (coordinate,), ((Cell.PLUS,),), (), "independent source contract", "CONDITIONAL", application)


def test_exception_retracts_one_exact_application_and_preserves_an_independent_warrant():
    first, second = conditional("source:1"), conditional("source:2")
    exception = RuleException("fixture", "RULE", "nsm", "counterexample:1", "narrower guard", application_id="source:1")
    retained = resolve("fixture", laws=(first, second), exceptions=(exception,))
    assert retained.forced()["FEEL"] == Cell.PLUS
    assert retained.fired_rules == ("RULE",)
    assert retained.trace[0]["application_id"] == "source:1"
    assert "FEEL" not in resolve("fixture", laws=(first,), exceptions=(exception,)).forced()
    assert resolve("other", laws=(first,), exceptions=(exception,)).forced()["FEEL"] == Cell.PLUS


def test_a_correction_without_application_scope_never_retracts_multiple_applications():
    with pytest.raises(RuleExceptionError) as refusal:
        resolve(
            "fixture",
            laws=(conditional("a"), conditional("b")),
            exceptions=(RuleException("fixture", "RULE", "nsm", "counterexample", "scope"),),
        )
    assert refusal.value.code == "AMBIGUOUS_RULE_EXCEPTION"
    assert law_application_id(conditional("a")) == "a"


def test_exception_recomputes_downstream_cells_and_keeps_other_readings_intact():
    root = conditional("source:1", "THINK")
    implication = Law(
        "IMPLICATION",
        ("THINK", "KNOW"),
        ((Cell.PLUS, Cell.PLUS), (Cell.ZERO, Cell.ZERO), (Cell.SILENT, Cell.SILENT)),
        (),
        "relation",
    )
    exception = RuleException("fixture", "RULE", "reference", "counterexample", "scope", application_id="source:1")
    assert resolve("fixture", laws=(root, implication)).forced()["KNOW"] == Cell.PLUS
    after = resolve("fixture", laws=(root, implication), exceptions=(exception,))
    assert not {"THINK", "KNOW"} & after.forced().keys()
    assert resolve("unaffected", laws=(root, implication), exceptions=(exception,)).forced()["KNOW"] == Cell.PLUS


def test_foundational_constraints_and_builder_output_cannot_be_retracted_or_self_confirm():
    foundation = Law("FOUNDATION", ("FEEL",), ((Cell.PLUS,),), (), "source axiom")
    with pytest.raises(RuleExceptionError) as refusal:
        resolve(
            "fixture",
            laws=(foundation,),
            exceptions=(RuleException("fixture", "FOUNDATION", "nsm", "counterexample", "scope"),),
        )
    assert refusal.value.code == "FOUNDATIONAL_RULE_EXCEPTION"
    for source, record, kind in (
        ("builder", "value", "SOURCE_RECORD"),
        ("reference", "MODEL:answer", "SOURCE_RECORD"),
        ("reference", "value", "DERIVED_VECTOR"),
    ):
        with pytest.raises(RuleExceptionError) as refusal:
            RuleException("fixture", "RULE", source, record, "scope", kind)
        assert refusal.value.code == "NONINDEPENDENT_RULE_EXCEPTION"


def test_malformed_duplicate_and_inapplicable_exceptions_are_named_refusals():
    with pytest.raises(RuleExceptionError) as refusal:
        RuleException("fixture", "RULE", "nsm", "counterexample", [])
    assert refusal.value.code == "MALFORMED_RULE_EXCEPTION"
    exception = RuleException("fixture", "RULE", "nsm", "counterexample", "scope", application_id="source:1")
    with pytest.raises(RuleExceptionError) as refusal:
        resolve("fixture", laws=(conditional("source:2"),), exceptions=(exception,))
    assert refusal.value.code == "RULE_EXCEPTION_NOT_APPLICABLE"
    with pytest.raises(RuleExceptionError) as refusal:
        resolve("fixture", laws=(conditional("source:1"),), exceptions=(exception, exception))
    assert refusal.value.code == "DUPLICATE_RULE_EXCEPTION"


def association(antecedents=None, consequent="vad:valence_sign=negative") -> dict:
    relation = {
        "antecedents": antecedents or ["emotion:negative=1"],
        "consequent": consequent,
        "lineage": "SHARED_NRC_FAMILY",
    }
    return {
        "rule_id": candidate_id(relation),
        "kind": "NATIVE_ASSOCIATION",
        "may_write_lexical_cells": False,
        "relation": relation,
        "discovery_sha256": "a" * 64,
        "discovery_script_sha256": "b" * 64,
        "source_snapshots": [{"source": "emotion", "sha256": "c" * 64}],
    }


def channel(values: dict, record_id="source:record") -> dict:
    return {"status": "OBSERVED", "records": [{"record_id": record_id, "values": values}]}


def test_native_catalog_reports_corroboration_and_contradiction_without_cells():
    catalog = compile_catalog([association()])
    native = {"emotion": channel({"negative": 1}, "nrc:1"), "vad": channel({"valence": -0.6}, "vad:1")}
    original = copy.deepcopy(native)
    report = evaluate_catalog(native, catalog)
    (result,) = report["results"]
    assert result["code"] == "CORROBORATED_NATIVE_ASSOCIATION"
    assert result["antecedents"][0]["record_ids"] == ["nrc:1"]
    assert result["consequent"]["record_ids"] == ["vad:1"]
    assert result["lineage"] == "SHARED_NRC_FAMILY"
    assert report["scope"] == "WORD_ALTERNATIVE_UNION" and report["may_write_lexical_cells"] is False
    assert "cells" not in report and "laws" not in report and native == original
    native["vad"]["records"][0]["values"]["valence"] = 0.6
    (result,) = evaluate_catalog(native, catalog)["results"]
    assert result["code"] == "CONTRADICTED_NATIVE_ASSOCIATION"
    native["emotion"]["records"][0]["values"]["negative"] = 0
    (result,) = evaluate_catalog(native, catalog)["results"]
    assert result["code"] == "PREMISE_NOT_MET"


@pytest.mark.parametrize(
    ("target", "code"),
    [
        (None, "SOURCE_UNAVAILABLE"),
        ({"status": "UNAVAILABLE", "records": []}, "SOURCE_UNAVAILABLE"),
        ({"status": "NO_RECORD", "records": []}, "SOURCE_NO_RECORD"),
        (channel({"arousal": 0.3}), "SOURCE_UNOBSERVED"),
        ({"status": "OBSERVED", "records": []}, "SOURCE_STATUS_CONFLICT"),
        ({"status": "OBSERVED", "records": [{"record_id": [], "values": {}}]}, "MALFORMED_NATIVE_RECORD"),
    ],
)
def test_missing_or_malformed_native_evidence_is_never_a_counterexample(target, code):
    native = {"emotion": channel({"negative": 1}), "vad": target}
    (result,) = evaluate_catalog(native, compile_catalog([association()]))["results"]
    assert result["code"] == code and result["blocked_role"] == "CONSEQUENT"


def test_explicit_native_zero_differs_from_missing_and_never_means_lexical_absence():
    feature = "emotion:fear=0"
    assert native_feature_evidence({"emotion": channel({"fear": 0})}, feature)["code"] == "PRESENT"
    assert native_feature_evidence({"emotion": channel({"joy": 0})}, feature)["code"] == "SOURCE_UNOBSERVED"
    assert native_feature_evidence({"emotion": channel({"fear": 1})}, feature)["code"] == "ABSENT"
    assert native_feature_evidence({"emotion": channel({"fear": False})}, feature)["code"] == "SOURCE_UNOBSERVED"


def test_native_usas_features_preserve_joint_membership_and_pos_alternatives():
    native = {
        "usas": {
            "status": "OBSERVED",
            "records": [
                {"record_id": "usas:adj", "values": {"pos": "ADJ", "alternatives": ["A5.1+/E4.1+", "E3-"]}},
                {"record_id": "usas:noun", "values": {"pos": "NOUN", "alternatives": ["N3.2+"]}},
            ],
        }
    }
    assert native_feature_evidence(native, "usas:pos=ADJ&category=A5.1+")["code"] == "PRESENT"
    assert native_feature_evidence(native, "usas:category=E4.1+")["code"] == "PRESENT"
    assert native_feature_evidence(native, "usas:pos=ADJ&category=N3.2+")["code"] == "ABSENT"
    assert native_feature_evidence(native, "usas:single_alternative=E3-")["code"] == "ABSENT"


def test_native_predicates_roles_and_restrictions_are_mentions_not_lexical_implications():
    values = {
        "class": "child-1.1",
        "frames": [{"class": "parent-1", "predicates": [native_predicate("motion", "during(E)", "Theme")]}],
        "effective_role_restrictions": [
            {
                "role": "Theme",
                "restrictions": [
                    {
                        "tag": "SELRESTRS",
                        "attributes": {"logic": "or"},
                        "children": [
                            {"tag": "SELRESTR", "attributes": {"Value": "+", "type": "animate"}, "children": []},
                            {"tag": "SELRESTR", "attributes": {"Value": "+", "type": "concrete"}, "children": []},
                        ],
                    },
                ],
            }
        ],
    }
    native = {"verbnet": channel(values)}
    for feature in (
        "verbnet:class=parent-1",
        "verbnet:frame_predicate=motion",
        "verbnet:argument_role=Theme",
        "verbnet:argument_restriction=Theme:+animate",
    ):
        assert native_feature_evidence(native, feature)["code"] == "PRESENT"
    assert native_feature_evidence(native, "verbnet:class=missing-1")["code"] == "SOURCE_UNOBSERVED"
    values["class_ancestry"] = ["parent-1"]
    assert native_feature_evidence(native, "verbnet:class=missing-1")["code"] == "ABSENT"


def test_lancaster_ties_and_native_rating_signs_never_select_a_lexical_pole():
    fields = ("Auditory", "Gustatory", "Haptic", "Interoceptive", "Olfactory", "Visual")
    native = {"lancaster": channel({name + ".mean": 2.0 for name in fields})}
    assert native_feature_evidence(native, "lancaster:dominant_sense=TIE")["code"] == "PRESENT"
    assert native_feature_evidence(native, "lancaster:dominant_sense=Visual")["code"] == "ABSENT"
    assert (
        native_feature_evidence({"vad": channel({"valence": 2})}, "vad:valence_sign=positive")["code"]
        == "SOURCE_UNOBSERVED"
    )


def test_catalog_links_cannot_admit_an_association_or_a_foundational_exception():
    record = association()
    record["review_state"] = "FOUNDER_APPROVED"
    record["lexical_rule_id"] = "FEAR_AVERSION"
    catalog = compile_catalog([record])
    assert catalog_report(catalog, load_rulebook())["disposition_counts"] == {"LEXICAL_RULE_LINKED": 1}
    assert law_admission_status(record) == "NOT_ADMITTED"
    record["lexical_rule_id"] = "VERB_HEADS_NO_SUBSTANTIVE"
    assert catalog_report(compile_catalog([record]), load_rulebook())["disposition_counts"] == {
        "LEXICAL_RULE_LINK_UNADMITTED": 1
    }
    record["lexical_rule_id"] = "NO_SUCH_RULE"
    assert catalog_report(compile_catalog([record]), load_rulebook())["disposition_counts"] == {
        "LEXICAL_RULE_LINK_UNADMITTED": 1
    }


def test_catalog_schema_adversaries_are_reported_or_refused_without_a_crash(tmp_path):
    cases = [None, [], {"kind": "NATIVE_ASSOCIATION", "may_write_lexical_cells": False, "relation": []}]
    assert [r["code"] for r in evaluate_catalog({}, compile_catalog(cases))["results"]] == [
        "MALFORMED_CATALOG_ENTRY",
        "MALFORMED_CATALOG_ENTRY",
        "MALFORMED_NATIVE_RELATION",
    ]
    record = association()
    record["lifecycle"] = []
    assert catalog_entry_status(record) == "UNKNOWN_CATALOG_LIFECYCLE"
    record = association()
    record["gold"] = {"GOOD": "-1"}
    assert catalog_entry_status(record) == "PROHIBITED_DIAGNOSTIC_INPUT"
    record = association()
    record["relation"]["antecedents"] = [["emotion:negative=1"]]
    assert catalog_entry_status(record) == "UNSUPPORTED_NATIVE_FEATURE"
    with pytest.raises(CatalogError) as refusal:
        compile_catalog([association(), association()])
    assert refusal.value.code == "DUPLICATE_CATALOG_ID"
    path = tmp_path / "invalid.jsonl"
    path.write_text("{invalid}\n")
    with pytest.raises(CatalogError) as refusal:
        load_catalog(path)
    assert refusal.value.code == "MALFORMED_CATALOG_JSON"


def test_existing_648_native_relations_have_a_consumable_diagnostic_disposition():
    path = Path("docs/verification/lexicon-rebuild/rule-registry-2026-10-24/coherence_candidates.jsonl")
    catalog = load_catalog(path)
    report = catalog_report(catalog, load_rulebook())
    assert report["disposition_counts"] == {"DIAGNOSTIC_ONLY": 648}
    assert len(catalog.sha256) == 64 and report["may_write_lexical_cells"] is False


def test_resolve_cli_separates_reviewed_records_and_explicit_scratch_equations(tmp_path):
    raw = {
        "rule_id": "SCRATCH",
        "coordinates": ["KNOW"],
        "allowed": [["+1"]],
        "guard": [],
        "warrant": "scratch problem",
    }
    path, output = tmp_path / "problem.json", tmp_path / "result.json"
    command = [sys.executable, "-m", "gse.lexicon_builder", "resolve", "--input", str(path), "--output", str(output)]
    payload = {"reading_id": "fixture", "laws": [raw]}
    path.write_text(json.dumps(payload))
    refused = subprocess.run(command, capture_output=True, text=True)
    assert refused.returncode == 2 and "MISSING_LAW_CONTRACT" in refused.stderr
    payload["law_contract"] = "DIRECT_CONSTRAINTS"
    path.write_text(json.dumps(payload))
    subprocess.run(command, check=True, capture_output=True, text=True)
    assert json.loads(output.read_text())["constraint_mode"] == "DIRECT_CONSTRAINTS"
    assert json.loads(output.read_text())["forced"]["KNOW"] == "+1"
    raw["review_state"] = "CANDIDATE"
    path.write_text(json.dumps(payload))
    refused = subprocess.run(command, capture_output=True, text=True)
    assert refused.returncode == 2 and "DIRECT_CONSTRAINTS_WITH_REVIEW_METADATA" in refused.stderr
    payload.pop("law_contract")
    path.write_text(json.dumps(payload))
    subprocess.run(command, check=True, capture_output=True, text=True)
    report = json.loads(output.read_text())
    assert report["constraint_mode"] == "ADMITTED_RULEBOOK" and "KNOW" not in report["forced"]
    assert report["rule_admission"] == [{"rule_id": "SCRATCH", "reason": "UNREVIEWED_RULE"}]


def test_resolve_cli_retracts_only_the_application_id_it_previously_emitted(tmp_path):
    payload = {
        "reading_id": "fixture",
        "law_contract": "DIRECT_CONSTRAINTS",
        "laws": [
            {
                "rule_id": "SAME_RULE",
                "coordinates": [coordinate],
                "allowed": [["+1"]],
                "guard": [],
                "warrant": "independent located source",
                "tier": "CONDITIONAL",
            }
            for coordinate in ("FEEL", "KNOW")
        ],
    }
    path, output = tmp_path / "problem.json", tmp_path / "result.json"
    command = [sys.executable, "-m", "gse.lexicon_builder", "resolve", "--input", str(path), "--output", str(output)]
    path.write_text(json.dumps(payload))
    subprocess.run(command, check=True, capture_output=True, text=True)
    initial = json.loads(output.read_text())
    applications = initial["rule_applications"]
    assert len({app["application_id"] for app in applications}) == 2
    selected = next(app for app in applications if app["coordinates"] == ["FEEL"])
    payload["exceptions"] = [
        {
            "reading_id": "fixture",
            "rule_id": selected["rule_id"],
            "application_id": selected["application_id"],
            "source": "independent-reference",
            "record_id": "counterexample:1",
            "reason": "narrower application guard",
        }
    ]
    path.write_text(json.dumps(payload))
    subprocess.run(command, check=True, capture_output=True, text=True)
    corrected = json.loads(output.read_text())
    assert "FEEL" not in corrected["forced"] and corrected["forced"]["KNOW"] == "+1"
    assert corrected["trace"][0]["application_id"] == selected["application_id"]
    assert len(corrected["rule_applications"]) == 1 and corrected["rule_applications"][0]["coordinates"] == ["KNOW"]
    payload["exceptions"][0]["application_id"] = "not-an-emitted-application"
    path.write_text(json.dumps(payload))
    refused = subprocess.run(command, capture_output=True, text=True)
    assert refused.returncode != 0 and "RULE_EXCEPTION_NOT_APPLICABLE" in refused.stderr
