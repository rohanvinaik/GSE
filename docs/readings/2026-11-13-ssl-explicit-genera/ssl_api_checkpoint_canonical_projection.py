"""One reviewed canonical-source transition through the ordinary revision/replay.

This checkpoint orchestrator installs only exact own-coordinate source anchors.
Independent typed witnesses are checked against their original immutable requests;
nulls are retained as reservations, never converted into lexical assertions.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from GSE.curation.lexicon_builder.completion import _contexts, _entry, _set_metadata
from GSE.curation.lexicon_builder.epoch import fingerprint, make_questions, read, record
from GSE.curation.lexicon_builder.foundation import BANKS, load_manifest
from GSE.curation.lexicon_builder.residual import _read_value
from GSE.curation.lexicon_builder.resolution import resolve_dictionary
from GSE.curation.lexicon_builder.rule_migration import _refresh_catalog
from GSE.curation.lexicon_builder.source_enrichment import _refuse_bound_receipts, revise_source_candidate
from GSE.curation.lexicon_builder.storage import store_entry
from GSE.curation.lexicon_builder.validation import _metadata, _observations, _relations, _stored_context
from GSE.lexicon_resource import ACTIVE_POINTER


def observation_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def checked_builder_pins(pins):
    """Recognize only the exact reader relocation, not arbitrary changed code.

    Root moved two unchanged readers and their unchanged format constant out of
    builder storage for the import-layer contract. All writing/solver functions
    must remain structurally identical to the actually pinned historical file.
    """
    current, relocations = [], []
    for pin in pins:
        path = Path(pin["path"])
        digest = fingerprint(path)
        current.append({"path": str(path), "sha256": digest})
        if digest == pin["sha256"]:
            continue
        if str(path) != "GSE/curation/lexicon_builder/storage.py":
            raise ValueError("CANONICAL_PROJECTION_BASELINE_BUILDER_CHANGED:" + str(path))
        old = subprocess.check_output(["git", "show", "HEAD:" + str(path)])
        if hashlib.sha256(old).hexdigest() != pin["sha256"]:
            raise ValueError("CANONICAL_PROJECTION_HISTORICAL_STORAGE_NOT_PINNED")
        old_tree, new_tree = ast.parse(old), ast.parse(path.read_text())
        reader_path = Path("GSE/lexicon/definitions.py")
        reader_tree = ast.parse(reader_path.read_text())
        moved = {"read_entries", "runtime_lookup"}

        def version(node):
            return isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "VERSION" for t in node.targets
            )

        def relocated(node):
            return version(node) or isinstance(node, ast.FunctionDef) and node.name in moved

        before = [node for node in old_tree.body if not relocated(node)]
        after = [
            node
            for node in new_tree.body
            if not isinstance(node, ast.ImportFrom) or node.module != "GSE.lexicon.definitions"
        ]
        old_moved = [node for node in old_tree.body if relocated(node)]
        new_moved = [node for node in reader_tree.body if relocated(node)]
        reader_dependencies = [node for node in reader_tree.body if not relocated(node)]
        allowed_dependencies = ast.parse('"reader documentation"\nimport json\nimport sqlite3\n').body
        if reader_dependencies and isinstance(reader_dependencies[0], ast.Expr):
            if isinstance(reader_dependencies[0].value, ast.Constant) and isinstance(
                reader_dependencies[0].value.value, str
            ):
                reader_dependencies = reader_dependencies[1:]
        allowed_dependencies = allowed_dependencies[1:]
        imports = [
            node
            for node in new_tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "GSE.lexicon.definitions"
        ]
        if (
            ast.dump(ast.Module(body=before, type_ignores=[])) != ast.dump(ast.Module(body=after, type_ignores=[]))
            or ast.dump(ast.Module(body=old_moved, type_ignores=[]))
            != ast.dump(ast.Module(body=new_moved, type_ignores=[]))
            or sorted((alias.name, alias.asname) for node in imports for alias in node.names)
            != [("VERSION", "VERSION"), ("read_entries", "read_entries"), ("runtime_lookup", "runtime_lookup")]
            or ast.dump(ast.Module(body=reader_dependencies, type_ignores=[]))
            != ast.dump(ast.Module(body=allowed_dependencies, type_ignores=[]))
        ):
            raise ValueError("CANONICAL_PROJECTION_STORAGE_NOT_IDENTICAL_RELOCATION")
        relocations.append(
            {
                "historical": pin,
                "current": current[-1],
                "reader": {"path": str(reader_path), "sha256": fingerprint(reader_path)},
                "proof": "FULL_STORAGE_AST_UNCHANGED_EXCEPT_EXACT_VERSION_AND_TWO_READER_REEXPORTS",
            }
        )
        current.append({"path": str(reader_path), "sha256": fingerprint(reader_path)})
    return current, relocations


def verify_witnesses(review_path, directory):
    review, audit = read(review_path), read(directory / "audit.json")
    baseline = Path(review["baseline"]["path"])
    if fingerprint(baseline) != review["baseline"]["sha256"] or audit["baseline"] != review["baseline"]:
        raise ValueError("CANONICAL_PROJECTION_BASELINE_CHANGED")
    if any(fingerprint(Path(path)) != digest for path, digest in review["source_pins"].items()):
        raise ValueError("CANONICAL_PROJECTION_REVIEWED_SOURCE_CHANGED")
    if (
        audit["code"] != "TYPED_WITNESSES_RECORDED_NOT_ADMISSION"
        or audit["review_sha256"] != fingerprint(review_path)
        or audit["questions_sha256"] != fingerprint(directory / "questions.json")
        or audit["answers_sha256"] != fingerprint(directory / "answers.json")
        or audit["bank_writes"] != 0
        or audit["is_final_holdout"] is not False
    ):
        raise ValueError("CANONICAL_PROJECTION_AUDIT_CHANGED")
    claims = review["claims"]
    coordinates = [(claim["entry_id"], claim["bank"]) for claim in claims]
    if not coordinates or len(set(coordinates)) != len(coordinates):
        raise ValueError("CANONICAL_PROJECTION_DUPLICATE_COORDINATE")
    requests = make_questions(baseline, coordinates)
    packet = read(directory / "questions.json")
    expected = {
        "format": "GSE.ssl-checkpoint-local-questions/1",
        "baseline_sha256": fingerprint(baseline),
        "coordinates": [list(pair) for pair in coordinates],
        "questions": [
            {"request_id": request.request_id, "request": request.payload(), "schema": request.output_schema()}
            for request in requests
        ],
    }
    answers = read(directory / "answers.json")
    if packet != expected or answers["questions_sha256"] != fingerprint(directory / "questions.json"):
        raise ValueError("CANONICAL_PROJECTION_ORIGINAL_REQUEST_CHANGED")
    if answers["transport"] != audit["transport"] or len(answers["answers"]) != len(requests):
        raise ValueError("CANONICAL_PROJECTION_ANSWER_AUTHORITY_CHANGED")
    selected, reservations, outcomes = [], [], []
    for claim, request, answer in zip(claims, requests, answers["answers"], strict=True):
        if answer["request_id"] != request.request_id:
            raise ValueError("CANONICAL_PROJECTION_ANSWER_ID_CHANGED")
        value = _read_value(answer["raw_output"], request)
        outcomes.append(
            {"entry_id": request.entry_id, "bank": request.bank, "value": value, "request_id": request.request_id}
        )
        if value is None:
            reservations.append({"entry_id": request.entry_id, "bank": request.bank, "reason": "EXPLICIT_NULL"})
        elif value != claim["value"]:
            raise ValueError("CANONICAL_PROJECTION_INDEPENDENT_DISAGREEMENT:" + request.entry_id + ":" + request.bank)
        else:
            if (
                claim["bank"] not in BANKS
                or type(claim["value"]) is not int
                or claim["value"] not in (-1, 1)
                or claim["scope"] != "EXACT_SOURCE_DEFINITION_AND_OWN_COORDINATE_ONLY"
                or not claim["derivation"]
            ):
                raise ValueError("CANONICAL_PROJECTION_UNREVIEWED_SCOPE")
            selected.append(claim)
    if outcomes != audit["records"]:
        raise ValueError("CANONICAL_PROJECTION_AUDIT_OUTCOMES_CHANGED")
    return review, selected, reservations


def manifest_payload(claims, review_sha, audit_sha):
    anchors = {}
    for claim in claims:
        anchors.setdefault(claim["entry_id"], []).append(
            {
                "bank": claim["bank"],
                "value": claim["value"],
                "source": "nsm_basis_correspondence:canonical-source-review-v1",
                "record_id": f"{claim['unit_id']}:{review_sha}:{audit_sha}:{claim['bank']}",
                "family": "nsm_basis_correspondence",
                "scope": "lexical",
            }
        )
    return {"format": "GSE.lexicon-rules/1", "anchors": anchors}


def apply_projection(conn, claims, manifest):
    relations_extra, requested, hierarchy_extra = load_manifest(manifest)
    if relations_extra or hierarchy_extra or set(requested) != {claim["entry_id"] for claim in claims}:
        raise ValueError("CANONICAL_PROJECTION_MANIFEST_SCOPE_CHANGED")
    _refuse_bound_receipts(conn, set(requested))
    anchors, links = _metadata(conn, "anchors"), _metadata(conn, "prime_entries")
    relations = _relations(_metadata(conn, "relations"))
    _, relevance = _contexts(conn, tuple(requested))
    changes = []
    for claim in claims:
        entry = claim["entry_id"]
        definition, assertions, restrictions, hierarchy = _entry(conn, entry)
        if definition.definition != claim["definition"] or definition.pos != claim["pos"]:
            raise ValueError("CANONICAL_PROJECTION_DEFINITION_CHANGED:" + entry)
        if links.get(claim["unit_id"]) != claim["identity_link"]["entry_ids"] or entry not in links[claim["unit_id"]]:
            raise ValueError("CANONICAL_PROJECTION_IDENTITY_CHANGED:" + entry)
        rows = conn.execute(
            "SELECT payload FROM source_observations WHERE entry_id=? AND source=?",
            (entry, claim["native_source"]),
        ).fetchall()
        if len(rows) != 1:
            raise ValueError("CANONICAL_PROJECTION_SOURCE_MISSING:" + entry)
        native = json.loads(rows[0][0])
        if (
            observation_digest(native) != claim["native_observation_sha256"]
            or native["entry_id"] != entry
            or native["record_id"] != claim["native_record_id"]
            or native["candidate_entry_ids"] != [entry]
            or native["scope"] != "lexical"
        ):
            raise ValueError("CANONICAL_PROJECTION_SOURCE_CHANGED:" + entry)
        before = json.loads(
            conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (entry,)).fetchone()[0]
        )
        added = requested[entry]
        if len(added) != 1 or added[0].bank != claim["bank"] or added[0].value != claim["value"]:
            raise ValueError("CANONICAL_PROJECTION_ANCHOR_CHANGED:" + entry)
        if len(before[claim["bank"]]) == 1 or claim["value"] not in before[claim["bank"]]:
            raise ValueError("CANONICAL_PROJECTION_TARGET_NOT_OPEN:" + entry)
        resolution = resolve_dictionary(
            BANKS,
            assertions + added,
            relations,
            _stored_context(conn, definition, relations),
            evidence_banks=tuple(sorted(relevance[entry])),
            domain_restrictions=restrictions,
        )
        after = {bank: sorted(values) for bank, values in resolution.domains.items()}
        if (
            resolution.code == "CONFLICT"
            or after[claim["bank"]] != [claim["value"]]
            or any(not set(after[bank]) <= set(before[bank]) for bank in before)
        ):
            raise ValueError("CANONICAL_PROJECTION_CONFLICT_OR_REOPEN:" + entry)
        store_entry(conn, definition, resolution, assertions + added, hierarchy, domain_restrictions=restrictions)
        anchors.setdefault(entry, []).extend(asdict(item) for item in added)
        changes.append(
            {
                "entry_id": entry,
                "unit_id": claim["unit_id"],
                "assertions_added": [asdict(x) for x in added],
                "before": before,
                "after": after,
            }
        )
    _set_metadata(conn, "anchors", anchors)
    mismatches = []
    native_index, _, bank_relevance = _observations(
        conn,
        {row[0] for row in conn.execute("SELECT entry_id FROM definition_states")},
        lambda *args, **kwargs: mismatches.append((args, kwargs)),
    )
    if mismatches:
        raise ValueError("CANONICAL_PROJECTION_SOURCE_VALIDATION_FAILED")
    _refresh_catalog(conn, relations, native_index, bank_relevance)
    return changes


def run(review_path, directory, baseline_report, baseline_source_certificate, output, manifest, result):
    review, claims, reservations = verify_witnesses(review_path, directory)
    if not claims:
        raise ValueError("CANONICAL_PROJECTION_NO_SIGNED_WITNESSES")
    baseline = read(baseline_report)
    certificate = read(baseline_source_certificate)
    builder_pins, relocations = checked_builder_pins(certificate["builder_source_pins"])
    if (
        baseline["candidate_sha256"] != review["baseline"]["sha256"]
        or baseline["code"] != "SOURCE_PROJECTION_REVISED_AND_REPLAYED"
    ):
        raise ValueError("CANONICAL_PROJECTION_BASELINE_CERTIFICATE_CHANGED")
    identity_sources = {}
    for claim in claims:
        path = Path(claim["identity_link"]["artifact"])
        if read(path)["prime_entries"].get(claim["unit_id"]) != claim["identity_link"]["entry_ids"]:
            raise ValueError("CANONICAL_PROJECTION_APPROVED_IDENTITY_CHANGED")
        identity_sources[str(path)] = fingerprint(path)
    audit_sha, review_sha = fingerprint(directory / "audit.json"), fingerprint(review_path)
    record(manifest, manifest_payload(claims, review_sha, audit_sha))
    record(
        manifest.with_suffix(".authority.json"),
        {
            "format": "GSE.canonical-source-projection-authority/1",
            "review_sha256": review_sha,
            "independent_audit_sha256": audit_sha,
            "identity_only_source_pins": identity_sources,
            "baseline_replay_report_sha256": fingerprint(baseline_report),
            "historical_baseline_builder_pins": certificate["builder_source_pins"],
            "builder_pins": builder_pins,
            "exact_reader_relocation_proofs": relocations,
            "manifest_sha256": fingerprint(manifest),
            "reservations": reservations,
            "semantic_authority": "REVIEWED_EXACT_DEFINITION_BASIS_CORRESPONDENCE_NOT_MODEL_MAJORITY_OR_SPELLING",
        },
    )
    report = revise_source_candidate(
        Path(review["baseline"]["path"]),
        output,
        {
            "candidate_sha256": baseline["candidate_sha256"],
            "active_pointer_sha256": fingerprint(ACTIVE_POINTER),
            "replay": baseline["replay"],
        },
        lambda conn: apply_projection(conn, claims, manifest),
        format_tag="GSE.canonical-source-projection/1",
        metadata_key="canonical_source_projection",
    )
    report.update(
        {
            "review_sha256": review_sha,
            "independent_audit_sha256": audit_sha,
            "manifest_sha256": fingerprint(manifest),
            "reservations": reservations,
            "is_final_holdout": False,
        }
    )
    record(result, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "review_path",
        "directory",
        "baseline_report",
        "baseline_source_certificate",
        "output",
        "manifest",
        "result",
    ):
        parser.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    run(**vars(parser.parse_args()))
