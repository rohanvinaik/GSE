"""Stage the installed relation semantics, including local exception survival."""

import hashlib
import json
from copy import deepcopy

import pytest

from gse.curation.lexicon_builder.engine import Assertion
from gse.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from gse.curation.lexicon_builder.pipeline import build_dictionary
from scripts import stage_lexicon_coherence as script


def proposal(name, left, right):
    return {
        "id": name,
        "antecedent": list(left),
        "consequent": list(right),
        "source_refs": ["synthetic-contract-test-only"],
        "guards": [],
    }


def candidate(tmp_path, monkeypatch, cases):
    definitions, observations, assertions = [], [], []
    for identity, values in cases.items():
        definitions.append(Definition(identity, identity, "noun", "synthetic mechanism fixture"))
        observations.append(Observation(identity, "fixture", identity, "fixture", {}, "lexical"))
        assertions.extend(Assertion(bank, value, "fixture", identity, "fixture") for bank, value in values.items())
    path = tmp_path / "candidate.db"
    build_dictionary(EvidenceBundle(tuple(definitions), tuple(observations), tuple(assertions), ()), path)
    pointer = tmp_path / "active.json"
    pointer.write_text('{"path":"unmodified-active.db"}\n')
    monkeypatch.setattr(script, "ACTIVE_POINTER", pointer)
    monkeypatch.setattr(script, "resolve_lexicon_path", lambda: tmp_path / "unmodified-active.db")
    monkeypatch.setattr(script, "_priority_source", lambda *args: ({"fixture": True}, {}))
    return path, pointer


def manifest(path, proposals, semantics="RELATIONAL_CONSTRAINT"):
    return {
        "format": "gse.coherence-stage-input/2",
        "baseline_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "semantics": semantics,
        "proposals": proposals,
        "scope_challenges": [],
    }


def test_real_cli_stages_reverse_pruning_and_preserves_candidate_and_active_pointer(tmp_path, monkeypatch):
    path, pointer = candidate(tmp_path, monkeypatch, {"unknown-premise": {"DO": 0}})
    spec = proposal("action", ("SAY", 1), ("DO", 1))
    data = manifest(path, [spec])
    input_path, report_path = tmp_path / "input.json", tmp_path / "report.json"
    input_path.write_text(json.dumps(data))
    before, active_before = path.read_bytes(), pointer.read_bytes()
    monkeypatch.setattr(
        "sys.argv", ["stage", "--candidate", str(path), "--manifest", str(input_path), "--report", str(report_path)]
    )
    script.main()
    report = json.loads(report_path.read_text())
    assert report["semantics"] == "RELATIONAL_CONSTRAINT"
    assert report["migration_compatibility"] == "RELATIONAL_EFFECTS_STAGED_UNADMITTED"
    assert report["joint"]["narrowed_but_unresolved"] == 1
    assert report["changes"][0]["changes"] == {"SAY": {"before": [-1, 0, 1], "after": [-1, 0]}}
    assert path.read_bytes() == before and pointer.read_bytes() == active_before
    assert report["authority"] == "UNADMITTED_READ_ONLY_STAGE" and report["lexicon_writes"] is False
    forward = script.stage(path, manifest(path, [spec], "FORWARD_PRIOR"))
    assert forward["changes"] == []
    assert forward["migration_compatibility"] == "FORWARD_ONLY_REQUIRES_SEPARATE_RELATIONAL_AUDIT"


def test_local_conflict_retains_independent_gain_and_exact_review_record(tmp_path, monkeypatch):
    path, _ = candidate(tmp_path, monkeypatch, {"conflict": {"SAY": 1, "QUANTITY": 1}})
    specs = [
        proposal("action", ("SAY", 1), ("DO", 1)),
        proposal("neutral", ("SAY", 1), ("DO", 0)),
        proposal("independent", ("QUANTITY", 1), ("WANT", 0)),
    ]
    report = script.stage(path, manifest(path, specs))
    assert report["joint"]["new_singletons"] == 1
    assert report["changes"][0]["changes"] == {"WANT": {"before": [-1, 0, 1], "after": [0]}}
    assert report["changes"][0]["review_required"] is True
    surprise = report["contradictions"][0]
    assert surprise["attempted"]["DO"] == [-1, 0, 1]
    assert surprise["disposition"] == "SUPPORTED_COMPONENT_GAINS_RETAINED"
    assert surprise["retained_changes"] == report["changes"][0]["changes"]
    assert any(
        item["reason"] == "CONDITIONAL_COMPONENT_CONFLICT"
        and {"action", "neutral"} <= set(item["rule_ids"])
        and "independent" not in item["rule_ids"]
        for item in surprise["issues"]
    )
    reverse = script.stage(path, manifest(path, list(reversed(specs))))
    assert reverse["joint"] == report["joint"]
    assert reverse["contradictions"][0]["attempted"] == surprise["attempted"]


def test_unknown_guard_excludes_the_relation_and_unknown_values_stay_unknown(tmp_path, monkeypatch):
    path, _ = candidate(tmp_path, monkeypatch, {"silent": {}})
    spec = proposal("guarded", ("SAY", 1), ("DO", 1))
    spec["guards"] = [["wordnet_ancestor:state.v.01", "true"]]
    report = script.stage(path, manifest(path, [spec]))
    assert not report["changes"] and not report["contradictions"]
    assert report["population"]["unknown"] > 0


def test_v1_report_remains_forward_only_and_rejects_silent_semantics_change(tmp_path, monkeypatch):
    path, _ = candidate(tmp_path, monkeypatch, {"old": {"DO": 0}})
    data = manifest(path, [proposal("action", ("SAY", 1), ("DO", 1))])
    data["format"] = "gse.coherence-stage-input/1"
    with pytest.raises(ValueError, match="COHERENCE_SEMANTICS_REQUIRES_VERSION_TWO"):
        script.stage(path, data)
    del data["semantics"]
    report = script.stage(path, data)
    assert report["format"] == "gse.coherence-stage-report/1" and report["changes"] == []


@pytest.mark.parametrize("semantics", [None, "", True, "MOSTLY_FORWARD", [], {}, 1.0])
def test_invalid_semantics_cannot_change_candidate(tmp_path, monkeypatch, semantics):
    path, _ = candidate(tmp_path, monkeypatch, {"silent": {}})
    data = manifest(path, [proposal("action", ("SAY", 1), ("DO", 1))], semantics)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="INVALID_COHERENCE_SEMANTICS"):
        script.stage(path, data)
    assert path.read_bytes() == before


def test_relational_population_evidence_is_loaded_in_bounded_chunks(tmp_path, monkeypatch):
    path, _ = candidate(tmp_path, monkeypatch, {f"silent:{i}": {} for i in range(513)})
    actual, sizes = script._contexts, []

    def observed_contexts(conn, selected, *, indexed=False):
        sizes.append(len(selected))
        assert indexed is True
        return actual(conn, selected, indexed=indexed)

    monkeypatch.setattr(script, "_contexts", observed_contexts)
    spec = proposal("inapplicable", ("SAY", 1), ("DO", 1))
    spec["guards"] = [["pos", "verb"]]
    report = script.stage(path, manifest(path, [spec]))
    assert report["population"]["definitions"] == 513
    assert sizes == [512, 1]


def test_stage_refuses_stale_snapshot_before_any_conclusions(tmp_path, monkeypatch):
    path, _ = candidate(tmp_path, monkeypatch, {"silent": {}})
    data = manifest(path, [proposal("action", ("SAY", 1), ("DO", 1))])
    changed = deepcopy(data)
    changed["baseline_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="COHERENCE_BASELINE_HASH_MISMATCH"):
        script.stage(path, changed)
