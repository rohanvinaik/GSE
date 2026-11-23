"""Exact native ancestry scopes review; fixtures supply no linguistic authority."""

from copy import deepcopy

import pytest
from test_lexicon_builder_reviewed_dependencies import warranted
from test_lexicon_builder_reviewed_patterns import FakeTransport, execute, ruling

from GSE.curation.lexicon_builder.engine import Assertion, Relation
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.foundation import lexical_context
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.reviewed_export import SELECTION_FORMAT, export_reviewed_input
from GSE.curation.lexicon_builder.reviewed_patterns import INPUT_FORMAT, run_workflow_input
from GSE.curation.lexicon_builder.rule_history import digest, relation_records

ANCESTOR = "wordnet_ancestor:linear_unit.n.01"


def native_entry(lemma, *, unit=True):
    synset = f"{lemma}.n.01" if unit else f"{lemma}.n.02"
    identity = f"wordnet:{lemma}:{synset}"
    definition = "synthetic length-unit fixture" if unit else "synthetic physical-object fixture"
    path = ["entity.n.01", "unit_of_measurement.n.01", "linear_unit.n.01", synset] if unit else ["entity.n.01", synset]
    return {
        "definition": {"entry_id": identity, "lemma": lemma, "pos": "noun", "definition": definition},
        "assertions": [],
        "anchors": [],
        "domain_restrictions": [],
        "context": {"pos": "noun"},
        "observations": [
            {
                "entry_id": identity,
                "record_id": identity,
                "source": "wordnet_hierarchy",
                "family": "wordnet",
                "scope": "lexical",
                "candidate_entry_ids": [identity],
                "features": {
                    "lemma": lemma,
                    "pos": "noun",
                    "definition": definition,
                    "synset_name": synset,
                    "lemma_names": [lemma],
                    "hypernym_paths": [path],
                    "examples": [],
                    "lexname": "noun.quantity" if unit else "noun.object",
                    "taxonomy_proposals": [],
                    "native_records": [{"word": lemma, "pos": "noun", "synset_name": synset}],
                },
            }
        ],
    }


def source_input():
    discovery, heldout, nonexample = native_entry("discovery"), native_entry("heldout"), native_entry("heldout", unit=False)
    candidate = warranted(guards=[["pos", "noun"], [ANCESTOR, "true"]])
    candidate["consequent"] = ["WANT", 0]
    return {
        "format": INPUT_FORMAT,
        "entries": [discovery, heldout, nonexample],
        "discovery_entry_ids": [discovery["definition"]["entry_id"]],
        "audit_entry_ids": [heldout["definition"]["entry_id"], nonexample["definition"]["entry_id"]],
        "rulings": [ruling(discovery, "WANT", 0)],
        "relations": [],
        "guarded_candidates": [candidate],
    }


def blocked_baseline_rule():
    return Relation(
        "synthetic:blocked-ancestry-baseline",
        ("BE",),
        ((0,),),
        ("synthetic:test-only",),
        approved=True,
        guards=(("pos", "verb"), (ANCESTOR, "true")),
    )


def test_exact_native_guard_stages_and_audits_without_changing_baseline_question(tmp_path):
    raw = source_input()
    transport = FakeTransport(['{"WANT":0}'])
    report = execute(tmp_path, raw, transport, 2)
    proposal = report["candidates"][0]
    assert proposal["discovery_outcomes"] == {"OBSERVED_AGREEMENT": 1}
    assert proposal["audit_outcomes"] == {"MODEL_AGREEMENT": 1, "GUARD_NOT_MET": 1}
    assert proposal["staging"][0]["changed_domains"]["WANT"] == {"before": [-1, 0, 1], "after": [0]}
    assert report["model_calls"] == 1
    request = transport.calls[0][0]
    assert request["scaffold"]["context"] == {"pos": "noun"}
    assert request["scaffold"]["approved_relations"] == []
    assert request["known"] == {}
    assert request["observations"] == raw["entries"][1]["observations"]
    assert proposal["relation"]["approved"] is False
    assert report["lexicon_writes"] is False


@pytest.mark.parametrize("mutation", ["missing", "candidate_only", "malformed_path", "wrong_scope", "wrong_source"])
def test_missing_or_ineligible_native_ancestry_never_activates_proposal(tmp_path, mutation):
    raw = source_input()
    heldout = raw["entries"][1]
    observation = heldout["observations"][0]
    if mutation == "missing":
        heldout["observations"] = []
    elif mutation == "candidate_only":
        observation["entry_id"] = None
    elif mutation == "malformed_path":
        observation["features"]["hypernym_paths"] = ["linear_unit.n.01"]
    elif mutation == "wrong_scope":
        observation["scope"] = "world"
    else:
        observation["source"] = "websters1913"
        observation["family"] = "dictionary"
    report = execute(tmp_path, raw, FakeTransport([]), 2)
    assert report["candidates"][0]["audit_outcomes"] == {"GUARD_NOT_MET": 2}
    assert all(stage["code"] == "GUARD_NOT_MET" for stage in report["candidates"][0]["staging"])
    assert report["model_calls"] == 0


@pytest.mark.parametrize(
    "guard",
    [
        ["wordnet_ancestor:", "true"],
        ["wordnet_ancestor:linear_unit", "true"],
        ["wordnet_ancestor:linear_unit.n.01", "false"],
        ["wordnet_ancestor:linear_unit.n.01", "TRUE"],
        ["wordnet_ancestor:linear_unit.x.01", "true"],
        ["wordnet_ancestor:linear_unit.n.01:invented", "true"],
        ["ancestor", "linear_unit.n.01"],
    ],
)
def test_guard_schema_refuses_fake_fields_and_values(tmp_path, guard):
    raw = source_input()
    raw["guarded_candidates"][0]["guards"] = [guard]
    with pytest.raises(ValueError, match="UNSUPPORTED_PATTERN_CONTEXT"):
        execute(tmp_path, raw)


@pytest.mark.parametrize("mutation", ["proposal_context_leak", "stale_baseline", "forged_ancestry"])
def test_declared_context_must_equal_source_derived_baseline_context(tmp_path, mutation):
    raw = source_input()
    if mutation == "proposal_context_leak":
        raw["entries"][1]["context"][ANCESTOR] = "true"
    else:
        rule = blocked_baseline_rule()
        raw["relations"] = relation_records((rule,))
        for item in raw["entries"]:
            item["context"] = lexical_context(item["definition"], item["observations"], (rule,))
        if mutation == "stale_baseline":
            raw["entries"][1]["context"].pop(ANCESTOR)
        else:
            raw["entries"][2]["context"][ANCESTOR] = "true"
    with pytest.raises(ValueError, match="UNSUPPORTED_PATTERN_CONTEXT"):
        execute(tmp_path, raw)


def test_export_uses_baseline_source_context_not_proposed_guard(tmp_path):
    raw = source_input()
    definitions = tuple(Definition(**item["definition"]) for item in raw["entries"])
    observations = tuple(
        Observation(**{**row, "candidate_entry_ids": tuple(row["candidate_entry_ids"])})
        for item in raw["entries"]
        for row in item["observations"]
    )
    candidate = tmp_path / "candidate.db"
    build_dictionary(EvidenceBundle(definitions, observations, (), ()), candidate)
    selection = {
        "format": SELECTION_FORMAT,
        "discovery_entry_ids": raw["discovery_entry_ids"],
        "audit_entry_ids": raw["audit_entry_ids"],
        "reviews": [],
        "guarded_candidates": raw["guarded_candidates"],
    }
    before = candidate.read_bytes()
    exported = export_reviewed_input(candidate, selection)
    assert all(item["context"] == {"pos": "noun"} for item in exported["input"]["entries"])
    report = run_workflow_input(exported["input"], FakeTransport(['{"WANT":0}']), max_calls=1)
    assert report["candidates"][0]["audit_outcomes"] == {"MODEL_AGREEMENT": 1, "GUARD_NOT_MET": 1}
    assert candidate.read_bytes() == before


def historical_source_input():
    raw = source_input()
    heldout = raw["entries"][1]
    first = ruling(heldout, "SEE", 0)
    rule = blocked_baseline_rule()
    raw["relations"] = relation_records((rule,))
    for item in raw["entries"]:
        item["context"] = lexical_context(item["definition"], item["observations"], (rule,))
    second = ruling(heldout, "WANT", 1, previous=(Assertion(**first["receipt"]["assertion"]),), relations=(rule,))
    raw["rulings"] = [first, second]
    raw["guarded_candidates"][0].update(antecedent=["WANT", 1], consequent=["GOOD", 0])
    current, previous = digest(raw["relations"]), digest([])
    raw["rule_history"] = {
        "format": "GSE.reviewed-pattern-history/1",
        "current_version": current,
        "versions": [{"version": previous, "relations": []}, {"version": current, "relations": deepcopy(raw["relations"])}],
        "bindings": [
            {
                "request_id": first["receipt"]["request_id"],
                "entry_id": heldout["definition"]["entry_id"],
                "version": previous,
                "receipt_sha256": digest(first["receipt"]),
            }
        ],
    }
    return raw


def test_historical_prefix_uses_original_source_context_then_current_context(tmp_path):
    raw = historical_source_input()
    first, second = raw["rulings"]
    assert first["receipt"]["request"]["scaffold"]["context"] == {"pos": "noun"}
    assert second["receipt"]["request"]["scaffold"]["context"] == {"pos": "noun", ANCESTOR: "true"}
    transport = FakeTransport(['{"GOOD":0}'])
    report = execute(tmp_path, raw, transport, 1)
    assert report["candidates"][0]["audit_outcomes"] == {"MODEL_AGREEMENT": 1, "GUARD_NOT_MET": 1}
    assert transport.calls[0][0]["known"] == {"SEE": 0, "WANT": 1}
    assert transport.calls[0][0]["scaffold"]["context"] == {"pos": "noun", ANCESTOR: "true"}


def test_historical_receipt_in_new_ancestry_scope_cannot_survive_by_using_old_context(tmp_path):
    raw = historical_source_input()
    raw["relations"][0]["guards"] = [[ANCESTOR, "true"]]
    current = digest(raw["relations"])
    raw["rule_history"]["current_version"] = current
    raw["rule_history"]["versions"][1] = {"version": current, "relations": deepcopy(raw["relations"])}
    with pytest.raises(ValueError, match="HISTORICAL_MODEL_CONTEXT_AFFECTED"):
        execute(tmp_path, raw)


@pytest.mark.parametrize("value", [-1, 0, 1])
def test_symbolic_conclusion_seeds_discovery_but_never_answers_open_audit(value):
    raw = source_input()
    raw["rulings"] = []
    discovery = raw["entries"][0]
    discovery["anchors"] = [{
        "bank": "SOMETHING", "value": 1, "source": "synthetic:anchor", "record_id": "seed", "family": "anchor"
    }]
    prior = Relation(
        "synthetic:prior-law", ("SOMETHING", "WANT"),
        tuple((left, right) for left in (-1, 0, 1) for right in (-1, 0, 1) if left != 1 or right == value),
        ("synthetic:source",), approved=True, guards=(("pos", "noun"),),
    )
    raw["relations"] = relation_records((prior,))
    raw["guarded_candidates"][0]["consequent"] = ["WANT", value]
    transport = FakeTransport(['{"WANT":' + str(value) + '}'])
    report = run_workflow_input(raw, transport, max_calls=1)
    candidate = report["candidates"][0]
    assert candidate["discovery_outcomes"] == {"OBSERVED_AGREEMENT": 1}
    [observed] = candidate["discovery"]
    assert observed["rulings"] == []
    assert observed["consequent_witness"]["kind"] == "BASELINE_CLOSURE"
    assert observed["consequent_witness"]["value"] == value
    assert observed["consequent_witness"]["proof_trace"]
    assert candidate["audit_outcomes"] == {"MODEL_AGREEMENT": 1, "GUARD_NOT_MET": 1}
    assert "WANT" not in transport.calls[0][0]["known"]
    assert report["model_calls"] == 1


@pytest.mark.parametrize("values,expected", [([], "CONSEQUENT_UNKNOWN"), ([1], "OBSERVED_COUNTEREXAMPLE"), ([-1, 1], "BASELINE_CONFLICT")])
def test_symbolic_seed_unknown_disagreement_and_conflict_remain_distinct(values, expected):
    raw = source_input()
    raw["rulings"] = []
    raw["entries"][0]["anchors"] = [
        {"bank": "WANT", "value": value, "source": "synthetic:anchor", "record_id": str(value), "family": "anchor"}
        for value in values
    ]
    report = run_workflow_input(raw)
    assert report["candidates"][0]["discovery_outcomes"] == {expected: 1}
    assert report["model_calls"] == 0


def test_symbolic_seed_does_not_bypass_audit_abstention_or_admission():
    from GSE.curation.lexicon_builder.rule_admission import admit_records

    raw = source_input()
    raw["rulings"] = []
    raw["entries"][0]["anchors"] = [
        {"bank": "WANT", "value": 0, "source": "synthetic:anchor", "record_id": "seed", "family": "anchor"}
    ]
    report = run_workflow_input(raw, FakeTransport(['{"WANT":null}']), max_calls=1)
    candidate = report["candidates"][0]
    assert candidate["discovery_outcomes"] == {"OBSERVED_AGREEMENT": 1}
    assert candidate["audit_outcomes"] == {"MODEL_ABSTAINED": 1, "GUARD_NOT_MET": 1}
    review = {
        "rule_id": candidate["relation"]["rule_id"], "warrant_sha256": candidate["warrant_sha256"],
        "review_id": "synthetic:review", "reviewer": "synthetic:reviewer", "decision": "APPROVE_DEFINITIONAL_RULE",
        "source_refs": ["synthetic:test-source"], "rationale": "Synthetic contract test only.",
    }
    with pytest.raises(ValueError, match="RULE_ADMISSION_AUDIT_INCOMPLETE"):
        admit_records(raw, report, review)


def test_symbolic_conclusion_keeps_legacy_discovery_semantics():
    from GSE.curation.lexicon_builder.reviewed_patterns import LEGACY_INPUT_FORMAT

    raw = source_input()
    raw["format"] = LEGACY_INPUT_FORMAT
    raw["rulings"] = []
    raw["entries"][0]["anchors"] = [
        {"bank": "WANT", "value": 0, "source": "synthetic:anchor", "record_id": "seed", "family": "anchor"}
    ]
    report = run_workflow_input(raw)
    assert report["candidates"][0]["discovery_outcomes"] == {"CONSEQUENT_UNKNOWN": 1}


def test_conjunctive_discovery_reuses_conclusion_proof_and_still_audits_target():
    raw = source_input()
    raw["rulings"] = []
    candidate = raw["guarded_candidates"][0]
    candidate.pop("antecedent")
    candidate["premises"] = [["SOMETHING", 1], ["CAN", 1]]
    for item in raw["entries"]:
        item["anchors"] = [
            {"bank": bank, "value": 1, "source": "synthetic:anchor", "record_id": bank, "family": "anchor"}
            for bank in ("SOMETHING", "CAN")
        ]
    raw["entries"][0]["anchors"].append(
        {"bank": "WANT", "value": 0, "source": "synthetic:anchor", "record_id": "seed", "family": "anchor"}
    )
    transport = FakeTransport(['{"WANT":0}'])
    report = run_workflow_input(raw, transport, max_calls=1)
    [observed] = report["candidates"][0]["discovery"]
    assert observed["code"] == "OBSERVED_AGREEMENT"
    assert observed["consequent_witness"]["value"] == 0
    assert len(observed["premise_witnesses"]) == 2
    assert transport.calls[0][0]["known"] == {"SOMETHING": 1, "CAN": 1}
    assert report["candidates"][0]["audit_outcomes"] == {"MODEL_AGREEMENT": 1, "GUARD_NOT_MET": 1}


def test_symbolically_seeded_rule_admission_replays_the_independent_audit():
    from GSE.curation.lexicon_builder.rule_admission import admit_records

    raw = source_input()
    raw["audit_entry_ids"] = raw["audit_entry_ids"][:1]
    raw["rulings"] = []
    raw["entries"][0]["anchors"] = [
        {"bank": "WANT", "value": 0, "source": "synthetic:anchor", "record_id": "seed", "family": "anchor"}
    ]
    report = run_workflow_input(raw, FakeTransport(['{"WANT":0}']), max_calls=1)
    [candidate] = report["candidates"]
    review = {
        "rule_id": candidate["relation"]["rule_id"], "warrant_sha256": candidate["warrant_sha256"],
        "review_id": "synthetic:review", "reviewer": "synthetic:reviewer", "decision": "APPROVE_DEFINITIONAL_RULE",
        "source_refs": ["synthetic:test-source"], "rationale": "Synthetic contract test only.",
    }
    admission = admit_records(raw, report, review)
    assert admission["code"] == "EXPLICIT_REVIEWED_RULE"
    assert admission["relation"]["approved"] is True
    assert admission["input"]["rulings"] == []
    assert admission["audit"]["model_calls"] == 1
