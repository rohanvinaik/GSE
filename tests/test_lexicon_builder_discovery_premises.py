"""Known premises participate in learning without redundant model rulings."""

import json
from dataclasses import asdict

import pytest
from test_lexicon_builder_reviewed_dependencies import warranted
from test_lexicon_builder_reviewed_patterns import FakeTransport, entry, execute, ruling

from gse.curation.lexicon_builder.engine import Assertion, Relation
from gse.curation.lexicon_builder.reviewed_patterns import INPUT_FORMAT
from scripts import audit_lexicon_patterns as script


def source_premise_input(value=1, *, derived=False):
    entries = [entry("discovery"), entry("heldout")]
    relations = ()
    if derived:
        relations = (
            Relation(
                "fixture:source-premise-chain",
                ("SAY", "WANT"),
                tuple((a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if a != 1 or b == value),
                ("synthetic-test-only",),
                approved=True,
            ),
        )
    for item in entries:
        if value is not None:
            item["anchors"] = [
                asdict(
                    Assertion(
                        "SAY" if derived else "WANT",
                        1 if derived else value,
                        "authored",
                        "fixture:explicit-premise",
                        "dictionary",
                    )
                )
            ]
    return {
        "format": INPUT_FORMAT,
        "entries": entries,
        "discovery_entry_ids": ["discovery"],
        "audit_entry_ids": ["heldout"],
        "relations": [asdict(rule) for rule in relations],
        "rulings": [ruling(entries[0], "GOOD", 0, relations=relations)],
        "guarded_candidates": [warranted(antecedent=["WANT", 1])],
    }


@pytest.mark.parametrize("derived", [False, True])
def test_real_cli_learns_from_proven_premise_and_only_questions_missing_target(tmp_path, monkeypatch, derived):
    raw = source_premise_input(derived=derived)
    input_path, report_path = tmp_path / "input.json", tmp_path / "report.json"
    input_path.write_text(json.dumps(raw))
    transport = FakeTransport(['{"GOOD":0}'])
    monkeypatch.setattr(script, "OllamaTransport", lambda *args, **kwargs: transport)
    monkeypatch.setattr(
        "sys.argv",
        [
            "audit",
            "--input",
            str(input_path),
            "--report",
            str(report_path),
            "--model",
            "synthetic",
            "--max-model-calls",
            "1",
        ],
    )
    assert script.main() == 0
    report = json.loads(report_path.read_text())
    candidate = report["candidates"][0]
    assert candidate["discovery_outcomes"] == {"OBSERVED_AGREEMENT": 1}
    witness = candidate["discovery"][0]["premise_witness"]
    assert (witness["kind"], witness["bank"], witness["value"]) == ("BASELINE_CLOSURE", "WANT", 1)
    assert witness["proof_trace"] and witness["baseline_sha256"]
    assert any(record.get("record_id") == "fixture:explicit-premise" for record in witness["proof_trace"])
    assert len(candidate["discovery"][0]["rulings"]) == 1
    assert candidate["audit_outcomes"] == {"MODEL_AGREEMENT": 1}
    assert report["model_calls"] == 1 and report["lexicon_writes"] is False
    payload, schema = transport.calls[0]
    assert payload["fill"] == {"GOOD": None} and schema["required"] == ["GOOD"]
    assert payload["known"]["WANT"] == 1
    assert candidate["relation"]["approved"] is False


@pytest.mark.parametrize("value,code", [(None, "ANTECEDENT_UNKNOWN"), (0, "PREMISE_NOT_MET"), (-1, "PREMISE_NOT_MET")])
def test_silence_and_explicit_other_signs_cannot_confirm_the_premise(tmp_path, value, code):
    transport = FakeTransport([])
    report = execute(tmp_path, source_premise_input(value), transport, 1)
    assert report["candidates"][0]["discovery_outcomes"] == {code: 1}
    assert report["model_calls"] == 0 and not transport.calls
    witness = report["candidates"][0]["discovery"][0].get("premise_witness")
    assert witness is None if value is None else witness["value"] == value


def test_conflicting_baseline_cannot_supply_discovery_support(tmp_path):
    raw = source_premise_input()
    raw["entries"][0]["anchors"].append(asdict(Assertion("WANT", 0, "authored", "fixture:opposing", "dictionary")))
    report = execute(tmp_path, raw)
    row = report["candidates"][0]["discovery"][0]
    assert row["code"] == "BASELINE_CONFLICT"
    assert "premise_witness" not in row


def test_proposed_rule_cannot_provide_its_own_discovery_premise(tmp_path):
    raw = source_premise_input()
    rule = Relation(
        "fixture:renamed-proposal",
        ("WANT", "GOOD"),
        tuple((a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if a != 1 or b == 0),
        ("synthetic-test-only",),
        approved=True,
        guards=(("pos", "noun"),),
    )
    raw["relations"] = [asdict(rule)]
    with pytest.raises(ValueError, match="TESTED_RULE_PRESENT_IN_BASELINE"):
        execute(tmp_path, raw)


def test_model_evidence_cannot_be_relabelled_as_a_native_premise(tmp_path):
    raw = source_premise_input()
    raw["entries"][0]["anchors"][0].update(source="model:forged", family="model")
    with pytest.raises(ValueError, match="UNSUPPORTED_PRIOR_MODEL_OR_DERIVED_BASELINE"):
        execute(tmp_path, raw)


def test_teaching_automatically_proposes_a_relation_from_a_native_premise(tmp_path):
    raw = source_premise_input()
    del raw["guarded_candidates"]
    transport = FakeTransport(['{"GOOD":0}'])
    report = execute(tmp_path, raw, transport, 1)
    assert len(report["candidates"]) == 1
    pattern = report["candidates"][0]
    assert pattern["antecedent"] == ("WANT", 1)
    assert pattern["consequent"] == ("GOOD", 0)
    assert pattern["discovery_outcomes"] == {"OBSERVED_AGREEMENT": 1}
    assert pattern["discovery"][0]["premise_witness"]["value"] == 1
    assert pattern["proposal_kind"] == "OBSERVED_PAIR" and pattern["warrant"] is None
    assert pattern["admission"] == "UNAPPROVED_CANDIDATE"
    assert pattern["audit_outcomes"] == {"MODEL_AGREEMENT": 1}
    assert transport.calls[0][0]["fill"] == {"GOOD": None}


def test_source_only_values_do_not_invent_a_reviewed_teaching_event(tmp_path):
    raw = source_premise_input()
    raw["rulings"] = []
    del raw["guarded_candidates"]
    report = execute(tmp_path, raw)
    assert report["candidates"] == [] and report["model_calls"] == 0


@pytest.mark.parametrize("guarded", [False, True])
def test_legacy_input_retains_its_original_discovery_semantics_for_replay(tmp_path, guarded):
    raw = source_premise_input()
    raw["format"] = "gse.reviewed-pattern-input/1"
    if not guarded:
        del raw["guarded_candidates"]
    report = execute(tmp_path, raw)
    assert report["format"] == "gse.reviewed-pattern-report/1"
    if guarded:
        assert report["candidates"][0]["discovery_outcomes"] == {"ANTECEDENT_UNKNOWN": 1}
    else:
        assert report["candidates"] == []
