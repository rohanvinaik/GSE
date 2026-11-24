"""Apply one already approved definition anchor through the existing source revision.

This is checkpoint orchestration, not a new constructor or a population rule.
The validated input stays immutable. No model request is made.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from GSE.curation.lexicon_builder.completion import _contexts, _entry, _set_metadata
from GSE.curation.lexicon_builder.evaluation import evaluate_build
from GSE.curation.lexicon_builder.foundation import BANKS, load_manifest
from GSE.curation.lexicon_builder.resolution import resolve_dictionary
from GSE.curation.lexicon_builder.rule_migration import _refresh_catalog
from GSE.curation.lexicon_builder.source_enrichment import _refuse_bound_receipts, revise_source_candidate
from GSE.curation.lexicon_builder.storage import _json, store_entry
from GSE.curation.lexicon_builder.validation import _metadata, _observations, _relations, _stored_context
from GSE.lexicon_resource import ACTIVE_POINTER

ENTRY = "wordnet:self:self.n.02"
GLOSS = "a person considered as a unique individual"
APPROVAL = "First-/second-person reference only; generic self is I=0, YOU=0"
CONTROLS = {"gse_closed_class:pronoun:i": ("I", 1), "gse_closed_class:pronoun:you": ("YOU", 1)}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def checked_anchors(manifest, warrant):
    review = json.loads(Path(warrant).read_text())
    if (
        review["owner_approval_verbatim"] != APPROVAL
        or review["entry_id"] != ENTRY
        or review["definition"] != GLOSS
        or review["evaluation_lineage"] != "EXPOSED_DEVELOPMENT_NOT_FINAL_HOLDOUT"
    ):
        raise ValueError("GENERIC_SELF_APPROVAL_OBJECT_CHANGED")
    relations, anchors, hierarchy = load_manifest(manifest)
    raw = json.loads(Path(manifest).read_text())
    if relations or hierarchy or set(anchors) != {ENTRY} or raw.get("definitions") or raw.get("prime_entries"):
        raise ValueError("GENERIC_SELF_MANIFEST_SCOPE_CHANGED")
    records = anchors[ENTRY]
    expected = [
        {
            "bank": bank,
            "value": 0,
            "source": "founder_approved:person_reference_boundary",
            "record_id": f"founder:generic-self:{sha(warrant)}:{bank}",
            "family": "founder",
            "scope": "lexical",
        }
        for bank in ("I", "YOU")
    ]
    if [asdict(record) for record in records] != expected:
        raise ValueError("GENERIC_SELF_MANIFEST_AUTHORITY_CHANGED")
    return records


def apply_boundary(conn, manifest, warrant):
    requested = checked_anchors(manifest, warrant)
    _refuse_bound_receipts(conn, {ENTRY})
    definition, assertions, restrictions, hierarchy = _entry(conn, ENTRY)
    if definition.lemma != "self" or definition.pos != "noun" or definition.definition != GLOSS:
        raise ValueError("GENERIC_SELF_NATIVE_DEFINITION_CHANGED")
    rows = conn.execute(
        "SELECT payload FROM source_observations WHERE entry_id=? AND source='wordnet_hierarchy'", (ENTRY,)
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("GENERIC_SELF_NATIVE_WITNESS_MISSING")
    native = json.loads(rows[0][0])
    features = native["features"]
    if (
        native["entry_id"] != ENTRY
        or native["record_id"] != ENTRY
        or native["scope"] != "lexical"
        or features["synset_name"] != "self.n.02"
        or features["lemma"] != "self"
        or features["pos"] != "noun"
        or features["definition"] != GLOSS
    ):
        raise ValueError("GENERIC_SELF_NATIVE_WITNESS_CHANGED")
    anchors = _metadata(conn, "anchors")
    if ENTRY in anchors:
        raise ValueError("GENERIC_SELF_ANCHOR_ALREADY_PRESENT")
    before = json.loads(conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (ENTRY,)).fetchone()[0])
    if any(before[bank] != [-1, 0, 1] for bank in ("I", "YOU")):
        raise ValueError("GENERIC_SELF_BOUNDARY_NOT_OPEN")
    relations = _relations(_metadata(conn, "relations"))
    _, relevance = _contexts(conn, (ENTRY,))
    resolution = resolve_dictionary(
        BANKS,
        assertions + requested,
        relations,
        _stored_context(conn, definition, relations),
        evidence_banks=tuple(sorted(relevance[ENTRY])),
        domain_restrictions=restrictions,
    )
    after = {bank: sorted(values) for bank, values in resolution.domains.items()}
    expected = {**before, "I": [0], "YOU": [0]}
    if resolution.code == "CONFLICT" or after != expected:
        raise ValueError("GENERIC_SELF_UNEXPECTED_CLOSURE_OR_CONFLICT")
    store_entry(conn, definition, resolution, assertions + requested, hierarchy, domain_restrictions=restrictions)
    anchors[ENTRY] = [asdict(record) for record in requested]
    _set_metadata(conn, "anchors", anchors)
    mismatches = []
    native_index, _, bank_relevance = _observations(
        conn,
        {row[0] for row in conn.execute("SELECT entry_id FROM definition_states")},
        lambda *args, **kwargs: mismatches.append((args, kwargs)),
    )
    if mismatches:
        raise ValueError("GENERIC_SELF_SOURCE_OBSERVATIONS_INVALID")
    _refresh_catalog(conn, relations, native_index, bank_relevance)
    return {
        "entry_id": ENTRY,
        "definition": asdict(definition),
        "native_witness": native,
        "manifest_sha256": sha(manifest),
        "founder_decision_sha256": sha(warrant),
        "assertions_added": [asdict(record) for record in requested],
        "assertions_preserved": [asdict(record) for record in assertions],
        "before": before,
        "after": after,
        "all_other_coordinate_domains_unchanged": True,
        "scope": "EXACT_DEFINITION_ONLY_NOT_POPULATION_OR_SPELLING",
        "model_service_calls": 0,
    }


def run(candidate, output, manifest, warrant, baseline_replay, gold, result):
    baseline = {
        "candidate_sha256": sha(candidate),
        "active_pointer_sha256": sha(ACTIVE_POINTER),
        "replay": json.loads(Path(baseline_replay).read_text()),
    }
    # Bind the reused computation to the immutable head it actually validated.
    replay_phase = json.loads((Path(baseline_replay).parent / "postwriter-validation.json").read_text())
    if (
        replay_phase["candidate_sha256"] != baseline["candidate_sha256"]
        or replay_phase["replay"]["sha256"] != sha(baseline_replay)
        or any(sha(record["path"]) != record["sha256"] for record in replay_phase["builder_source_pins"])
    ):
        raise ValueError("GENERIC_SELF_BASELINE_REPLAY_HEAD_CHANGED")
    report = revise_source_candidate(
        candidate,
        output,
        baseline,
        lambda conn: apply_boundary(conn, manifest, warrant),
        format_tag="GSE.founder-generic-self-boundary/1",
        metadata_key="founder_generic_self_boundary",
    )
    audit = evaluate_build(output, gold)
    if audit["outcomes"]["IDENTIFIED_CORRECT"] != 4 or any(
        value for key, value in audit["outcomes"].items() if key != "IDENTIFIED_CORRECT"
    ):
        raise ValueError("GENERIC_SELF_DEVELOPMENT_BOUNDARY_AUDIT_FAILED")
    with closing(sqlite3.connect(Path(output).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        for entry, (bank, value) in CONTROLS.items():
            before_conn = sqlite3.connect(Path(candidate).resolve().as_uri() + "?mode=ro", uri=True)
            try:
                before = before_conn.execute(
                    "SELECT domains FROM definition_states WHERE entry_id=?", (entry,)
                ).fetchone()[0]
            finally:
                before_conn.close()
            after = conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (entry,)).fetchone()[0]
            if before != after or json.loads(after)[bank] != [value]:
                raise ValueError("GENERIC_SELF_CHANGED_REFERENCE_CONTROL")
    report["development_boundary_audit"] = audit
    report["evaluation_lineage"] = "EXPOSED_DEVELOPMENT_NOT_FINAL_HOLDOUT"
    Path(result).write_text(_json(report) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "output", "manifest", "warrant", "baseline_replay", "gold", "result"):
        parser.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    args = parser.parse_args()
    run(**vars(args))
