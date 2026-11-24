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
import sqlite3
import subprocess
from dataclasses import asdict, replace
from pathlib import Path

from GSE.curation.lexicon_builder.completion import _contexts, _entry, _set_metadata
from GSE.curation.lexicon_builder.epoch import fingerprint, make_questions, read, record
from GSE.curation.lexicon_builder.evidence import _closed_class_definitions
from GSE.curation.lexicon_builder.foundation import BANKS, load_manifest
from GSE.curation.lexicon_builder.reconsideration import _apply_plan, _archive_schema, _plan_report, _prepare
from GSE.curation.lexicon_builder.residual import _read_value
from GSE.curation.lexicon_builder.resolution import resolve_dictionary
from GSE.curation.lexicon_builder.rule_migration import _refresh_catalog
from GSE.curation.lexicon_builder.source_enrichment import _refuse_bound_receipts, revise_source_candidate
from GSE.curation.lexicon_builder.storage import store_entry, store_observations
from GSE.curation.lexicon_builder.validation import _metadata, _observations, _relations, _stored_context
from GSE.lexicon_resource import ACTIVE_POINTER
from GSE.namespace import identity_form

HISTORICAL_STORAGE = "67c49b04ff01c6764c056b77b2678e8d3986ccf5"


def observation_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def auxiliary_review(candidate):
    """Inventory the exact old/new native AUX rows; do not write lexical data."""
    from GSE.curation.external_sources.gse_closed_class import GSEClosedClassParser

    definitions, observations, assertions = _closed_class_definitions(GSEClosedClassParser())
    claims = []
    with sqlite3.connect(candidate.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        for entry, definition in sorted(definitions.items()):
            if not entry.startswith("gse_closed_class:auxiliary:"):
                continue
            old_definition, old_assertions, _, _ = _entry(conn, entry)
            rows = conn.execute(
                "SELECT payload FROM source_observations WHERE entry_id=? AND source='gse_closed_class'", (entry,)
            ).fetchall()
            if len(rows) != 1:
                raise ValueError("AUXILIARY_REVISION_NATIVE_ROW_COUNT")
            before = json.loads(rows[0][0])
            after = asdict(observations[definition.source_ids[0]])
            # JSON shapes, not tuple/list serialization, are the review boundary.
            after = json.loads(json.dumps(after))
            old_features, new_features = dict(before["features"]), dict(after["features"])
            old_content = old_features.pop("primitives")
            new_content = new_features.pop("primitives")
            old_features.pop("definition")
            new_features.pop("definition")
            bank = {"be": "BE", "do": "DO", "have": "HAVE"}[new_features["grammatical_features"]["lemma"]]
            if (
                identity_form(old_features) != identity_form(new_features)
                or old_content != {bank: 1}
                or new_content != {}
                or before["candidate_entry_ids"] != [entry]
                or before["scope"] != "lexical"
                or old_definition.definition != before["features"]["definition"]
                or old_definition.pos != definition.pos
                or old_definition.lemma != definition.lemma
                or any(a.record_id == after["record_id"] for a in assertions)
            ):
                raise ValueError("AUXILIARY_REVISION_NOT_EXACT_GRAMMATICAL_RETRACTION:" + entry)
            # Retain the original stored provenance bytes across the known
            # namespace rename; only definition text and projected content change.
            for key in ("native_encodings", "provenance"):
                after["features"][key] = before["features"][key]
            native_assertions = [asdict(a) for a in old_assertions if a.source == "gse_closed_class"]
            if native_assertions != [
                {
                    "bank": bank,
                    "value": 1,
                    "source": "gse_closed_class",
                    "record_id": before["record_id"],
                    "family": "gse_curated_grammar",
                    "scope": "lexical",
                }
            ]:
                raise ValueError("AUXILIARY_REVISION_UNEXPECTED_SOURCE_ASSERTIONS:" + entry)
            models = conn.execute(
                "SELECT request_id FROM accepted_model_receipts WHERE entry_id=? ORDER BY ordinal", (entry,)
            ).fetchall()
            claims.append(
                {
                    "entry_id": entry,
                    "before": before,
                    "after": after,
                    "retired_source_assertions": native_assertions,
                    "retired_model_requests": [row[0] for row in models],
                }
            )
    if len(claims) != 19:
        raise ValueError("AUXILIARY_REVISION_INCOMPLETE_COHORT")
    adapter = Path("GSE/curation/external_sources/gse_closed_class.py")
    return {
        "format": "GSE.auxiliary-own-content-source-review/1",
        "baseline": {"path": str(candidate), "sha256": fingerprint(candidate)},
        "adapter": {"path": str(adapter), "sha256": fingerprint(adapter)},
        "scope": "EXACT_AUXILIARY_BE_DO_HAVE_NATIVE_DEFINITIONS_ONLY",
        "warrant": "Grammatical auxiliary/copula operation is not own stative BE, action DO or possession HAVE. "
        "Native role AUX and catalog auxiliary identify this use independently of spelling. "
        "Legacy encoding origins remain provenance, not semantic authority for the different grammatical use.",
        "unknown_policy": "Withdraw unsupported source assertions and reclose; no zero assertions or main-verb changes.",
        "model_context_policy": "Archive all bound accepted rulings through existing reconsideration before replacing native context.",
        "claims": claims,
    }


def apply_auxiliary_revision(conn, review, baseline_replay):
    """Retire context-bound model receipts, then replace only reviewed native rows.

    The caller's immutable, computed full baseline replay is the preflight. The
    existing source revision transaction performs the mandatory full postflight;
    the existing reconsideration mechanism archives/replays each retired suffix.
    """
    from GSE.curation.external_sources.gse_closed_class import GSEClosedClassParser

    if (
        review["scope"] != "EXACT_AUXILIARY_BE_DO_HAVE_NATIVE_DEFINITIONS_ONLY"
        or fingerprint(Path(review["adapter"]["path"])) != review["adapter"]["sha256"]
    ):
        raise ValueError("AUXILIARY_REVISION_REVIEW_CHANGED")
    definitions, native, _ = _closed_class_definitions(GSEClosedClassParser())
    claims = review["claims"]
    expected = {entry for entry in definitions if entry.startswith("gse_closed_class:auxiliary:")}
    if len(claims) != len(expected) or {claim["entry_id"] for claim in claims} != expected:
        raise ValueError("AUXILIARY_REVISION_COHORT_CHANGED")
    retirements = []
    for claim in claims:
        entry = claim["entry_id"]
        rows = conn.execute(
            "SELECT request_id FROM accepted_model_receipts WHERE entry_id=? ORDER BY ordinal", (entry,)
        ).fetchall()
        if [row[0] for row in rows] != claim["retired_model_requests"]:
            raise ValueError("AUXILIARY_REVISION_MODEL_SCOPE_CHANGED")
        if rows:
            plan = _prepare(conn, rows[0][0])
            convention = "AUXILIARY_OWN_CONTENT_SOURCE_CORRECTION"
            reason = "Native grammatical definition context changes; preserve original ruling only in its exact historical archive."
            report = _plan_report(plan, convention, reason, baseline_replay, {})
            _archive_schema(conn)
            _apply_plan(conn, plan, report, convention, reason)
            retirements.append(report)
    _refuse_bound_receipts(conn, expected)
    relations = _relations(_metadata(conn, "relations"))
    prepared = []
    for claim in claims:
        entry = claim["entry_id"]
        definition, assertions, restrictions, hierarchy = _entry(conn, entry)
        new_definition = definitions[entry]
        observation = native[new_definition.source_ids[0]]
        rows = conn.execute(
            "SELECT payload FROM source_observations WHERE entry_id=? AND source='gse_closed_class'", (entry,)
        ).fetchall()
        if (
            len(rows) != 1
            or json.loads(rows[0][0]) != claim["before"]
            or identity_form(json.loads(json.dumps(asdict(observation)))) != identity_form(claim["after"])
            or definition.definition != claim["before"]["features"]["definition"]
            or definition.pos != new_definition.pos
            or definition.lemma != new_definition.lemma
        ):
            raise ValueError("AUXILIARY_REVISION_SOURCE_CHANGED:" + entry)
        retired = tuple(a for a in assertions if a.source == "gse_closed_class")
        if [asdict(a) for a in retired] != claim["retired_source_assertions"] or len(retired) != 1:
            raise ValueError("AUXILIARY_REVISION_ASSERTIONS_CHANGED:" + entry)
        retained = tuple(a for a in assertions if a not in retired)
        before = json.loads(
            conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (entry,)).fetchone()[0]
        )
        observation = replace(observation, features=claim["after"]["features"])
        conn.execute("DELETE FROM source_observations WHERE record_id=?", (claim["before"]["record_id"],))
        store_observations(conn, (observation,))
        prepared.append((claim, new_definition, retained, restrictions, hierarchy, before))
    # Reconstruct every affected context in one complete source scan after all
    # replacements, never from the obsolete entries' resolved vectors.
    _, relevance = _contexts(conn, tuple(sorted(expected)))
    changes = []
    for claim, new_definition, retained, restrictions, hierarchy, before in prepared:
        entry = claim["entry_id"]
        resolution = resolve_dictionary(
            BANKS,
            retained,
            relations,
            _stored_context(conn, new_definition, relations),
            evidence_banks=tuple(sorted(relevance[entry])),
            domain_restrictions=restrictions,
        )
        if resolution.code == "CONFLICT":
            raise ValueError("AUXILIARY_REVISION_RETAINED_CONFLICT")
        store_entry(conn, new_definition, resolution, retained, hierarchy, domain_restrictions=restrictions)
        changes.append(
            {
                "entry_id": entry,
                "before_native": claim["before"],
                "after_native": claim["after"],
                "retired_source_assertions": claim["retired_source_assertions"],
                "before_domains": before,
                "after_domains": {bank: sorted(values) for bank, values in resolution.domains.items()},
            }
        )
    return {
        "source_changes": changes,
        "model_reconsiderations": retirements,
        "model_calls": 0,
        "zero_assertions_added": 0,
    }


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
        old = subprocess.check_output(["git", "show", HISTORICAL_STORAGE + ":" + str(path)])
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
            or (native["family"], native["scope"])
            != {
                "wordnet_hierarchy": ("wordnet", "lexical"),
                "nsm_chart": ("nsm_primary_chart", "source_structure"),
            }.get(claim["native_source"])
            or (
                claim["native_source"] == "nsm_chart"
                and (
                    native["features"].get("definition_kind") != "LEXICAL_UNIT"
                    or native["features"].get("unit_id") != claim["unit_id"]
                )
            )
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


def run(
    review_path,
    directory,
    baseline_report,
    baseline_source_certificate,
    output,
    manifest,
    result,
    auxiliary_review_path=None,
):
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
            "auxiliary_review_sha256": fingerprint(auxiliary_review_path) if auxiliary_review_path else None,
            "reservations": reservations,
            "semantic_authority": "REVIEWED_EXACT_DEFINITION_BASIS_CORRESPONDENCE_NOT_MODEL_MAJORITY_OR_SPELLING",
        },
    )
    auxiliary = read(auxiliary_review_path) if auxiliary_review_path else None
    if auxiliary and auxiliary["baseline"] != review["baseline"]:
        raise ValueError("AUXILIARY_REVISION_BASELINE_CHANGED")

    def apply_group(conn):
        auxiliary_changes = apply_auxiliary_revision(conn, auxiliary, baseline["replay"]) if auxiliary else None
        return {"auxiliary": auxiliary_changes, "canonical": apply_projection(conn, claims, manifest)}

    report = revise_source_candidate(
        Path(review["baseline"]["path"]),
        output,
        {
            "candidate_sha256": baseline["candidate_sha256"],
            "active_pointer_sha256": fingerprint(ACTIVE_POINTER),
            "replay": baseline["replay"],
        },
        apply_group,
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
            "auxiliary_review_sha256": fingerprint(auxiliary_review_path) if auxiliary_review_path else None,
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
    parser.add_argument("--auxiliary-review-path", type=Path)
    run(**vars(parser.parse_args()))
