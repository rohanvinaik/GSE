"""Exact-definition discovery joins evidence and verifies it on replay."""

import json
import sqlite3

import pytest

from gse.curation.lexicon_builder.engine import Assertion
from gse.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from gse.curation.lexicon_builder.pipeline import build_dictionary
from gse.curation.lexicon_builder.validation import validate_build


@pytest.fixture
def discovered(tmp_path):
    definitions = tuple(Definition(name, name, "verb", "fixture definition") for name in ("supported", "conflicting"))
    observations, assertions = [], []
    for definition in definitions:
        for source, family, bank, value in (("left", "taxonomy", "THINK", 1), ("right", "lexical", "KNOW", 0)):
            record_id = f"{definition.entry_id}:{source}"
            observations.append(Observation(definition.entry_id, source, record_id, family, {}, "lexical"))
            assertions.append(Assertion(bank, value, source, record_id, family))
    observations.append(Observation("conflicting", "third", "conflicting:third", "independent", {}, "lexical"))
    assertions.append(Assertion("KNOW", 1, "third", "conflicting:third", "independent"))
    path = tmp_path / "joined.db"
    build_dictionary(EvidenceBundle(definitions, tuple(observations), tuple(assertions), ()), path, discover=True)
    return path


def test_cross_source_receipts_replay_with_genuine_family_incidence(discovered):
    report = validate_build(discovered)
    assert report["code"] == "REPLAY_VALIDATED", report
    with sqlite3.connect(discovered) as conn:
        summaries = [json.loads(row[0]) for row in conn.execute("SELECT summary FROM candidate_relations")]
        target = next(s for s in summaries if s["antecedent"] == ["THINK", 1])
        assert target["evidence_counts"]["support"] == target["evidence_counts"]["conflicting"] == 1
        assert target["by_family"]["taxonomy"]["support"] == 1
        assert target["by_family"]["lexical"]["support"] == 1
        assert target["relation"]["approved"] is False


@pytest.mark.parametrize("change", ["omit_disagreement", "wrong_entry", "fake_family", "fake_group"])
def test_cross_source_receipt_cannot_hide_or_relabel_evidence(discovered, change):
    with sqlite3.connect(discovered) as conn:
        for rule_id, category, ordinal, payload in conn.execute(
            "SELECT rule_id,category,ordinal,payload FROM candidate_evidence"
        ):
            record = json.loads(payload)
            if record["entry_id"] == "conflicting" and category == "conflicting":
                break
        else:
            pytest.fail("expected conflicting evidence")
        if change == "omit_disagreement":
            record["observations"] = [item for item in record["observations"] if item["source"] != "third"]
        elif change == "wrong_entry":
            record["observations"][0]["entry_id"] = "supported"
        elif change == "fake_family":
            record["observations"][0]["family"] = "fabricated"
        else:
            record["source"] = "definition:supported"
        conn.execute(
            "UPDATE candidate_evidence SET payload=? WHERE rule_id=? AND category=? AND ordinal=?",
            (json.dumps(record), rule_id, category, ordinal),
        )
    report = validate_build(discovered)
    assert report["code"] == "REPLAY_MISMATCH"
    assert "MALFORMED_CANDIDATE" in {item["code"] for item in report["mismatches"]}
