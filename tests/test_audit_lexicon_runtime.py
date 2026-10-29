"""Audit outcomes distinguish unknown evidence from observed contradictions."""

import json

import pytest

from gse.curation.lexicon_builder.evidence import Definition, EvidenceBundle
from gse.curation.lexicon_builder.pipeline import build_dictionary
from scripts.audit_lexicon_runtime import anchor_outcome, audit_runtime, main


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
    definitions = (
        Definition("wordnet:want:desire.v.01", "want", "verb", "feel or have a desire for; want strongly"),
        Definition("wordnet:very:very.r.01", "very", "adverb", "used as intensifiers"),
        Definition("wordnet:extremely:extremely.r.02", "extremely", "adverb", "to an extreme degree"),
        Definition("wordnet:very:identical.s.02", "very", "adjective", "being the exact same one; not any other"),
        Definition("wordnet:very:very.r.02", "very", "adverb", "precisely so"),
        Definition("wordnet:very:very.s.01", "very", "adjective", "precisely as stated"),
    )
    path = tmp_path / "anchors.db"
    build_dictionary(EvidenceBundle(definitions, (), (), ()), path, manifest=manifest)
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
    assert report["by_class"]["other_very_senses_unknown"] == {"IDENTIFIED": 3}
    assert report["by_class"]["not_very_scope"] == {"WRONG": 1}
    json.dumps(report, allow_nan=False)
