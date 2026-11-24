"""Exact founder-anchor scope guards; full corpus replay is a separate gate."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
N = ROOT / "docs/readings/2026-11-13-ssl-explicit-genera"
SPEC = importlib.util.spec_from_file_location("checkpoint_self_boundary", N / "ssl_api_checkpoint_self_boundary.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def manifest(tmp_path):
    warrant = N / "ssl-api-controller-generic-self-founder-decision.json"
    records = [
        {
            "bank": bank,
            "value": 0,
            "source": "founder_approved:person_reference_boundary",
            "record_id": f"founder:generic-self:{MODULE.sha(warrant)}:{bank}",
            "family": "founder",
            "scope": "lexical",
        }
        for bank in ("I", "YOU")
    ]
    payload = {"format": "GSE.lexicon-rules/1", "anchors": {MODULE.ENTRY: records}}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload))
    return path, warrant, payload


def test_exact_approved_boundary_only(tmp_path):
    path, warrant, _ = manifest(tmp_path)
    assert [(record.bank, record.value) for record in MODULE.checked_anchors(path, warrant)] == [("I", 0), ("YOU", 0)]


@pytest.mark.parametrize("mutation", ["spelling", "positive", "other_bank", "extra_definition", "no_citation"])
def test_boundary_refuses_scope_or_authority_changes(tmp_path, mutation):
    path, warrant, payload = manifest(tmp_path)
    records = payload["anchors"][MODULE.ENTRY]
    if mutation == "spelling":
        payload["anchors"]["self"] = payload["anchors"].pop(MODULE.ENTRY)
    elif mutation == "positive":
        records[0]["value"] = 1
    elif mutation == "other_bank":
        records[0]["bank"] = "BODY"
    elif mutation == "extra_definition":
        payload["definitions"] = {"unreviewed": {}}
    else:
        records[0]["record_id"] = "uncited"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        MODULE.checked_anchors(path, warrant)
