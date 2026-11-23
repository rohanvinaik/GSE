"""Audit outcomes distinguish unknown evidence from observed contradictions."""

import json

import pytest

from GSE.curation.lexicon_builder.evidence import EvidenceBundle, collect_evidence, load_local_sources
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from scripts.audit_lexicon_runtime import (
    ORDINAL_ANCHOR_RECORD,
    anchor_outcome,
    audit_runtime,
    main,
    ordinal_anchor_isolation,
)


@pytest.mark.parametrize(
    "assignments,hierarchy,expected",
    [
        ({}, {}, "ABSTAINED"),
        ({"INTENSITY": 1}, {}, "ABSTAINED"),
        ({"INTENSITY": 0}, {}, "WRONG"),
        ({"INTENSITY": -1}, {"INTENSITY": 1}, "WRONG"),
        ({}, {"INTENSITY": 2}, "WRONG"),
        ({"INTENSITY": 1}, {"INTENSITY": 2}, "WRONG"),
        ({"INTENSITY": 1}, {"INTENSITY": 1}, "IDENTIFIED"),
    ],
)
def test_anchor_outcome_distinguishes_silence_zero_and_wrong_degree(assignments, hierarchy, expected):
    selected = {"code": "IDENTIFIED", "selected": {"assignments": assignments, "hierarchy": hierarchy}}
    assert anchor_outcome(selected, "INTENSITY", 1, 1) == expected


@pytest.mark.parametrize("code", ["AMBIGUOUS", "NOT_FOUND", "CONFLICT"])
def test_unselected_definition_is_reported_as_abstention(code):
    assert anchor_outcome({"code": code, "selected": None}, "WANT", 1, None) == "ABSTAINED"


def test_report_cannot_overwrite_the_input_database(tmp_path):
    database = tmp_path / "lexicon.db"
    database.write_bytes(b"preserve this file")
    with pytest.raises(SystemExit):
        main(["--lexicon-db", str(database), "--report", str(database)])
    assert database.read_bytes() == b"preserve this file"


def test_audit_exercises_approved_degree_vectors_and_leaves_database_unchanged(tmp_path):
    from pathlib import Path

    manifest = Path(__file__).resolve().parents[1] / "docs/program/LEXICON_APPROVED_ANCHORS_2026-10-29.json"
    path = tmp_path / "anchors.db"
    parsers, diagnostics = load_local_sources(("gse_closed_class", "nsm_chart", "wordnet_hierarchy"))
    assert all(record["code"] == "LOADED" for record in diagnostics)
    native = collect_evidence(parsers, words=("extremely",))
    build_dictionary(native, path, manifest=manifest)
    before = path.read_bytes()
    report = audit_runtime(path)
    assert path.read_bytes() == before
    assert report["scope"]["world_grounding"] == "UNVERIFIED"
    for name in (
        "want_positive",
        "want_negative",
        "this_object",
        "very_degree",
        "extremely_degree",
        "degree_vector_distinction",
    ):
        assert report["by_class"][name] == {"IDENTIFIED": 1}
    assert report["by_class"]["other_very_senses_anchor_isolation"] == {"IDENTIFIED": 3}
    for name in (
        "not_very_scope",
        "very_not_scope",
        "repeated_extreme_equivalence",
        "degree_scope_distinction",
        "ordinal_distinction",
    ):
        assert report["by_class"][name] == {"IDENTIFIED": 1}
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("value", [-1, 0, 1])
def test_sense_isolation_allows_independent_completion_but_rejects_copied_anchor(value):
    entry = {
        "entry_id": "wordnet:very:very.r.02",
        "assignments": {"INTENSITY": value},
        "domains": {"INTENSITY": [value]},
        "trace": [{"kind": "ASSERTION", "bank": "INTENSITY", "value": value, "record_id": "independent:exact-sense"}],
    }
    assert ordinal_anchor_isolation(entry)["outcome"] == "IDENTIFIED"
    entry["trace"][0]["record_id"] = ORDINAL_ANCHOR_RECORD
    assert ordinal_anchor_isolation(entry)["outcome"] == "WRONG"


def test_runtime_audit_accepts_justified_this_have_zero(tmp_path):
    from pathlib import Path

    from GSE.curation.lexicon_builder.completion import complete_dictionary

    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "docs/program/LEXICON_APPROVED_ANCHORS_2026-10-29.json").read_text()
    )
    # A deliberately small fixture retains only the authored THIS definition.
    manifest["definitions"] = [d for d in manifest["definitions"] if d["entry_id"] == "gse:prime:this"]
    manifest["anchors"] = {"gse:prime:this": manifest["anchors"]["gse:prime:this"]}
    manifest["prime_entries"] = {"nsm:v20:this": ["gse:prime:this"]}
    manifest["hierarchy"] = {}
    rules = tmp_path / "this-rules.json"
    rules.write_text(json.dumps(manifest))
    path = tmp_path / "this.db"
    build_dictionary(EvidenceBundle((), (), (), ()), path, manifest=rules)
    complete_dictionary(path, lambda payload, schema: '{"HAVE":0}', 1, entry_ids=("gse:prime:this",), banks=("HAVE",))
    report = audit_runtime(path)
    this = next(record for record in report["records"] if record["class"] == "this_object")
    assert this["have_domain"] == [0]
    assert this["outcome"] == "IDENTIFIED"
