"""Real file entry point; synthetic reviewed rulings are not linguistic gold."""

import json
from copy import deepcopy
from dataclasses import asdict

import pytest

from gse.curation.lexicon_builder.engine import Assertion, Relation
from gse.curation.lexicon_builder.evidence import Definition, Observation
from gse.curation.lexicon_builder.foundation import BANKS
from gse.curation.lexicon_builder.relevance import observation_relevance
from gse.curation.lexicon_builder.residual import _request_id, build_request
from gse.curation.lexicon_builder.resolution import resolve_dictionary
from gse.curation.lexicon_builder.reviewed_patterns import INPUT_FORMAT, run_workflow
from scripts import audit_lexicon_patterns as script


def entry(identity):
    return {
        "definition": {
            "entry_id": identity,
            "lemma": identity,
            "pos": "noun",
            "definition": "synthetic test definition",
        },
        "assertions": [],
        "anchors": [],
        "observations": [],
        "domain_restrictions": [],
        "context": {"pos": "noun"},
    }


def ruling(data, bank, value, *, previous=(), relations=()):
    definition = Definition(**data["definition"])
    anchors = tuple(Assertion(**row) for row in data["anchors"] + data["assertions"])
    observations = tuple(
        Observation(
            row["entry_id"],
            row["source"],
            row["record_id"],
            row["family"],
            row["features"],
            row["scope"],
            tuple(row.get("candidate_entry_ids", ())),
        )
        for row in data["observations"]
    )
    relevant = tuple(sorted({bank for observation in observations for bank in observation_relevance(observation)}))
    before = resolve_dictionary(BANKS, anchors + previous, relations, data["context"], evidence_banks=relevant)
    request = build_request(
        definition.entry_id,
        bank,
        before,
        tuple(asdict(observation) for observation in observations),
        definition=definition,
        relations=relations,
        context=data["context"],
    )
    assertion = Assertion(bank, value, "model:synthetic-pinned", request.request_id, "model")
    receipt = {
        "entry_id": definition.entry_id,
        "assertion": asdict(assertion),
        "request_id": request.request_id,
        "code": "ASSIGNED",
        "request": request.payload(),
        "schema": request.output_schema(),
    }
    return {
        "receipt": receipt,
        "review": {
            "review_id": "review:" + request.request_id,
            "reviewer": "synthetic-test-review",
            "receipt_sha256": _request_id(receipt),
            "code": "ACCEPTED",
        },
    }


def fixture(audits=("heldout",)):
    discovery = entry("discovery")
    entries = [discovery, *(entry(identity) for identity in audits)]
    return {
        "format": INPUT_FORMAT,
        "rulings": [
            ruling(discovery, "WANT", 1),
            ruling(discovery, "GOOD", 0),
            *(ruling(item, "WANT", 1) for item in entries[1:]),
        ],
        "discovery_entry_ids": ["discovery"],
        "audit_entry_ids": list(audits),
        "entries": entries,
        "relations": [],
        "candidates": [["WANT", 1, "GOOD", 0]],
    }


def execute(tmp_path, data, transport=None, budget=0):
    file = tmp_path / "input.json"
    file.write_text(json.dumps(data))
    return run_workflow(file, transport, max_calls=budget)


class FakeTransport:
    identity = "synthetic-pinned-audit"

    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []
        self.pins = []

    def pin(self):
        self.pins.append("pinned")

    def __call__(self, payload, schema):
        self.calls.append((deepcopy(payload), deepcopy(schema)))
        return next(self.replies)


def test_real_cli_stages_and_audits_without_target_or_rule_leakage(tmp_path, monkeypatch):
    data = fixture(("agreement", "counterexample", "abstained"))
    file, report_path = tmp_path / "input.json", tmp_path / "report.json"
    file.write_text(json.dumps(data))
    before = file.read_bytes()
    transport = FakeTransport(['{"GOOD":null}', '{"GOOD":0}', '{"GOOD":1}'])
    monkeypatch.setattr(script, "OllamaTransport", lambda *args, **kwargs: transport)
    monkeypatch.setattr(
        "sys.argv",
        [
            "audit",
            "--input",
            str(file),
            "--report",
            str(report_path),
            "--model",
            "synthetic",
            "--max-model-calls",
            "3",
            "--no-thinking",
        ],
    )
    assert script.main() == 0
    report = json.loads(report_path.read_text())
    candidate = report["candidates"][0]
    assert transport.pins == ["pinned"]
    assert report["model_calls"] == len(transport.calls) == 3
    assert candidate["audit_outcomes"] == {"MODEL_ABSTAINED": 1, "MODEL_AGREEMENT": 1, "MODEL_COUNTEREXAMPLE": 1}
    assert candidate["relation"]["approved"] is False
    assert candidate["admission"] == "UNAPPROVED_CANDIDATE"
    assert report["lexicon_writes"] is False
    assert file.read_bytes() == before
    assert {path.name for path in tmp_path.iterdir()} == {"input.json", "report.json"}
    for stage in candidate["staging"]:
        assert stage["changed_domains"]["GOOD"] == {"before": [-1, 0, 1], "after": [0]}
    for payload, schema in transport.calls:
        assert payload["known"] == {"WANT": 1}
        assert payload["scaffold"]["domains"]["GOOD"] == [-1, 0, 1]
        assert payload["scaffold"]["approved_relations"] == []
        assert payload["fill"] == {"GOOD": None}
        assert "proposed_value" not in payload and "expected" not in payload
        assert schema["required"] == ["GOOD"]


def test_budget_remains_cell_bounded_and_zero_budget_never_calls(tmp_path):
    transport = FakeTransport(['{"GOOD":0}'])
    result = execute(tmp_path, fixture(("a", "b")), transport, 1)
    assert result["model_calls"] == 1
    assert result["candidates"][0]["audit_outcomes"] == {"MODEL_AGREEMENT": 1, "AUDIT_CALL_BUDGET_EXHAUSTED": 1}
    zero = execute(tmp_path, fixture(), transport, 0)
    assert zero["model_calls"] == 0
    assert len(transport.calls) == 1


def test_discovery_and_audit_identity_cannot_overlap(tmp_path):
    data = fixture()
    data["audit_entry_ids"].append("discovery")
    with pytest.raises(ValueError, match="DISCOVERY_AUDIT_ID_OVERLAP"):
        execute(tmp_path, data)


def test_heldout_ruling_does_not_enter_discovery_support(tmp_path):
    data = fixture()
    data["rulings"].append(ruling(data["entries"][1], "GOOD", -1))
    report = execute(tmp_path, data)
    candidate = report["candidates"][0]
    assert candidate["discovery_outcomes"] == {"OBSERVED_AGREEMENT": 1}
    assert [row["entry_id"] for row in candidate["discovery"]] == ["discovery"]


@pytest.mark.parametrize(
    "mutation,code", [("review", "STALE_RULING_REVIEW"), ("request", "REVIEWED_RULING_REQUEST_MISMATCH")]
)
def test_tampered_review_or_request_is_refused(tmp_path, mutation, code):
    data = fixture()
    record = data["rulings"][0]
    if mutation == "review":
        record["review"]["receipt_sha256"] = "0" * 64
    else:
        record["receipt"]["request"]["definition"]["definition"] = "changed definition"
        record["review"]["receipt_sha256"] = _request_id(record["receipt"])
    with pytest.raises(ValueError, match=code):
        execute(tmp_path, data)


def test_prior_model_dependency_is_named_and_never_asked_again(tmp_path):
    data = fixture()
    previous = (Assertion("SEE", 0, "model:earlier", "old-request", "model"),)
    data["rulings"][-1] = ruling(data["entries"][1], "WANT", 1, previous=previous)
    transport = FakeTransport([])
    result = execute(tmp_path, data, transport, 1)
    assert result["candidates"][0]["audit_outcomes"] == {"UNSUPPORTED_PRIOR_MODEL_DEPENDENCY": 1}
    assert transport.calls == []


def test_known_target_in_antecedent_request_is_leakage(tmp_path):
    data = fixture()
    data["entries"][1]["anchors"] = [asdict(Assertion("GOOD", 0, "authored", "anchor", "dictionary"))]
    data["rulings"][-1] = ruling(data["entries"][1], "WANT", 1)
    report = execute(tmp_path, data)
    assert report["candidates"][0]["audit_outcomes"] == {"TARGET_LEAKAGE_IN_ANTECEDENT_REQUEST": 1}


def test_staging_cannot_override_known_target_and_symbolic_result_is_not_model_confirmation(tmp_path):
    data = fixture()
    data["entries"][1]["anchors"] = [
        asdict(Assertion("WANT", 1, "authored", "left", "dictionary")),
        asdict(Assertion("GOOD", 1, "authored", "right", "dictionary")),
    ]
    report = execute(tmp_path, data)
    candidate = report["candidates"][0]
    assert candidate["staging"][0]["code"] == "STAGED_EXCEPTION"
    assert candidate["staging"][0]["changed_domains"] == {}
    assert candidate["audit_outcomes"] == {"SYMBOLICALLY_RESOLVED_PREEXISTING": 1}
    assert report["model_calls"] == 0


def test_tested_rule_under_different_name_and_reversed_banks_is_rejected(tmp_path):
    data = fixture()
    table = tuple((y, x) for x in (-1, 0, 1) for y in (-1, 0, 1) if x != 1 or y == 0)
    data["relations"] = [asdict(Relation("renamed", ("GOOD", "WANT"), table, ("reviewed",), approved=True))]
    with pytest.raises(ValueError, match="TESTED_RULE_PRESENT_IN_BASELINE"):
        execute(tmp_path, data)


def test_conflicting_discovery_rulings_remain_conflict_not_majority(tmp_path):
    data = fixture()
    data["rulings"].append(
        ruling(data["entries"][0], "GOOD", 1, previous=(Assertion("SEE", 0, "model:context", "context", "model"),))
    )
    report = execute(tmp_path, data)
    assert report["candidates"][0]["discovery_outcomes"] == {"CONSEQUENT_CONFLICT": 1}
    assert report["candidates"][0]["relation"]["approved"] is False


@pytest.mark.parametrize("raw", ['{"GOOD":true}', '{"GOOD":0,"WANT":0}', '{"GOOD":NaN}', "{}"])
def test_malformed_direct_answer_is_not_zero_or_confirmation(tmp_path, raw):
    report = execute(tmp_path, fixture(), FakeTransport([raw]), 1)
    audit = report["candidates"][0]["audits"][0]
    assert audit["code"] == "INVALID_OUTPUT"
    assert "value" not in audit


def test_model_assertion_cannot_be_smuggled_into_native_baseline(tmp_path):
    data = fixture()
    data["entries"][1]["anchors"] = [asdict(Assertion("WANT", 1, "model:fake", "r", "model"))]
    with pytest.raises(ValueError, match="UNSUPPORTED_PRIOR_MODEL_OR_DERIVED_BASELINE"):
        execute(tmp_path, data)


def test_strict_file_boundary_refuses_duplicate_fields_and_nonfinite(tmp_path):
    path = tmp_path / "malformed.json"
    for raw in ('{"format":1,"format":2}', '{"format":NaN}'):
        path.write_text(raw)
        with pytest.raises(ValueError, match="DUPLICATE_JSON_FIELD|NONFINITE_JSON_VALUE"):
            run_workflow(path)


def test_empty_discovery_does_not_invent_a_pattern(tmp_path):
    data = fixture()
    data["rulings"] = []
    del data["candidates"]
    result = execute(tmp_path, data)
    assert result["candidates"] == [] and result["model_calls"] == 0


def test_native_context_and_baseline_relations_are_preserved_exactly(tmp_path):
    data = fixture()
    heldout = data["entries"][1]
    heldout["observations"] = [
        {
            "entry_id": "heldout",
            "source": "websters1913",
            "record_id": "native:r",
            "family": "dictionary",
            "scope": "lexical",
            "candidate_entry_ids": [],
            "features": {
                "definition": "exact native definition including qualifications",
                "native_entry_text": "Full original entry, including native qualifications",
            },
        }
    ]
    heldout["anchors"] = [asdict(Assertion("SEE", 0, "authored", "explicit-anchor", "dictionary"))]
    relation = Relation(
        "baseline:see-hear",
        ("SEE", "HEAR"),
        tuple((x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if x != 0 or y == 0),
        ("authored-baseline",),
        approved=True,
    )
    data["relations"] = [asdict(relation)]
    data["rulings"][-1] = ruling(heldout, "WANT", 1, relations=(relation,))
    transport = FakeTransport(['{"GOOD":0}'])
    report = execute(tmp_path, data, transport, 1)
    assert report["candidates"][0]["audit_outcomes"] == {"MODEL_AGREEMENT": 1}
    payload = transport.calls[0][0]
    assert payload["observations"] == heldout["observations"]
    assert payload["scaffold"]["context"] == heldout["context"]
    assert payload["known"] == {"SEE": 0, "HEAR": 0, "WANT": 1}
    assert [record["rule_id"] for record in payload["scaffold"]["approved_relations"]] == [relation.rule_id]
    assert data["relations"] == [asdict(relation)]


def test_automatic_proposals_need_observed_joint_values_and_keep_silence_unknown(tmp_path):
    data = fixture()
    del data["candidates"]
    data["entries"].append(entry("silent-discovery"))
    data["discovery_entry_ids"].append("silent-discovery")
    report = execute(tmp_path, data)
    assert {(tuple(record["antecedent"]), tuple(record["consequent"])) for record in report["candidates"]} == {
        (("WANT", 1), ("GOOD", 0)),
        (("GOOD", 0), ("WANT", 1)),
    }
    assert all(
        record["discovery_outcomes"] == {"OBSERVED_AGREEMENT": 1, "ANTECEDENT_UNKNOWN": 1}
        for record in report["candidates"]
    )
    assert all(record["relation"]["approved"] is False for record in report["candidates"])


@pytest.mark.parametrize(
    "field,value", [("discovery_entry_ids", "discovery"), ("candidates", [["WANT", True, "GOOD", 0]])]
)
def test_malformed_scopes_or_boolean_candidate_values_are_refused(tmp_path, field, value):
    data = fixture()
    data[field] = value
    with pytest.raises(ValueError, match="INVALID_PATTERN"):
        execute(tmp_path, data)


def test_cli_cannot_overwrite_input(tmp_path, monkeypatch):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(fixture()))
    before = path.read_bytes()
    monkeypatch.setattr("sys.argv", ["audit", "--input", str(path), "--report", str(path)])
    with pytest.raises(ValueError, match="PATTERN_REPORT_CANNOT_OVERWRITE_INPUT"):
        script.main()
    assert path.read_bytes() == before


def test_existing_unrelated_exception_is_not_attributed_to_candidate(tmp_path):
    data = fixture()
    heldout = data["entries"][1]
    heldout["anchors"] = [asdict(Assertion(bank, 0, "authored", bank, "dictionary")) for bank in ("HEAR", "SEE")]
    relation = Relation(
        "baseline:excepted",
        ("SEE", "HEAR"),
        tuple((x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if x != 0 or y == 1),
        ("baseline-review",),
        approved=True,
    )
    data["relations"] = [asdict(relation)]
    data["rulings"][-1] = ruling(heldout, "WANT", 1, relations=(relation,))
    report = execute(tmp_path, data)
    stage = report["candidates"][0]["staging"][0]
    assert stage["code"] == "STAGED_ONLY"
    assert stage["conditional_exceptions"] == []
    assert stage["baseline_conditional_exceptions"][0]["rule_ids"] == (relation.rule_id,)


@pytest.mark.parametrize(
    "mutation",
    [
        "definition_pairs",
        "string_source_ids",
        "dict_guard",
        "dict_table_row",
        "string_banks",
        "observation_pairs",
        "string_candidate_ids",
        "assertion_pairs",
        "restriction_pairs",
        "string_restriction_values",
    ],
)
def test_nested_json_shapes_never_coerce_into_valid_semantic_records(tmp_path, mutation):
    data = fixture()
    definition = data["entries"][0]
    relation = json.loads(
        json.dumps(asdict(Relation("unrelated", ("SEE", "HEAR"), ((0, 0),), ("source",), approved=True)))
    )
    data["relations"] = [relation]
    observation = {
        "entry_id": "discovery",
        "source": "websters1913",
        "record_id": "r",
        "family": "dictionary",
        "scope": "lexical",
        "features": {"definition": "native"},
    }
    assertion = asdict(Assertion("SEE", 0, "authored", "r", "dictionary"))
    restriction = {
        "bank": "SEE",
        "allowed_values": [0, 1],
        "source": "authored",
        "record_id": "r",
        "family": "dictionary",
    }
    if mutation == "definition_pairs":
        definition["definition"] = list(definition["definition"].items())
    elif mutation == "string_source_ids":
        definition["definition"]["source_ids"] = "ab"
    elif mutation == "dict_guard":
        relation["guards"] = [{"pos": False, "noun": 999}]
    elif mutation == "dict_table_row":
        relation["allowed_rows"] = [{"0": 0, "1": 1}]
    elif mutation == "string_banks":
        relation["banks"] = "SEE"
    elif mutation == "observation_pairs":
        definition["observations"] = [list(observation.items())]
    elif mutation == "string_candidate_ids":
        definition["observations"] = [{**observation, "candidate_entry_ids": "discovery"}]
    elif mutation == "assertion_pairs":
        definition["anchors"] = [list(assertion.items())]
    elif mutation == "restriction_pairs":
        definition["domain_restrictions"] = [list(restriction.items())]
    else:
        definition["domain_restrictions"] = [{**restriction, "allowed_values": "01"}]
    transport = FakeTransport([])
    with pytest.raises(ValueError, match="INVALID_PATTERN"):
        execute(tmp_path, data, transport, 1)
    assert transport.calls == []


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("field", ["lemma", "pos", "definition"])
def test_every_reviewed_definition_must_match_current_exact_context(tmp_path, index, field):
    data = fixture()
    data["entries"][index]["definition"][field] = "unrelated changed value"
    if field == "pos":
        data["entries"][index]["context"] = {"pos": "unrelated changed value"}
    transport = FakeTransport([])
    with pytest.raises(ValueError, match="REVIEWED_RULING_DEFINITION_MISMATCH"):
        execute(tmp_path, data, transport, 1)
    assert transport.calls == []


def test_cli_hardlink_report_cannot_overwrite_input(tmp_path, monkeypatch):
    import os

    path, report = tmp_path / "input.json", tmp_path / "report.json"
    path.write_text(json.dumps(fixture()))
    os.link(path, report)
    before = path.read_bytes()
    monkeypatch.setattr("sys.argv", ["audit", "--input", str(path), "--report", str(report)])
    with pytest.raises(ValueError, match="PATTERN_REPORT_CANNOT_OVERWRITE_INPUT"):
        script.main()
    assert path.read_bytes() == report.read_bytes() == before


def test_identical_audit_questions_across_patterns_report_actual_duplicate_cost(tmp_path):
    data = fixture()
    data["candidates"].append(["WANT", 1, "GOOD", 1])
    transport = FakeTransport(['{"GOOD":0}', '{"GOOD":0}'])
    report = execute(tmp_path, data, transport, 2)
    assert report["model_calls"] == len(transport.calls) == 2
    assert len(report["repeated_audit_requests"]) == 1
    repeated = report["repeated_audit_requests"][0]
    assert repeated["code"] == "REPEATED_AUDIT_REQUEST"
    assert repeated["evaluations"] == repeated["model_calls"] == 2
    assert len(repeated["candidate_rule_ids"]) == 2
    assert transport.calls[0] == transport.calls[1]
