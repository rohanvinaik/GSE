"""Find atomic WordNet guard candidates for a reviewed bank-pair proposal.

Run with Regenesis on PYTHONPATH. This is a population screen over replayed
domains. Admission still requires a definitional warrant, disjoint withheld
audits, and full closure under the revised rule set.
"""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from GSE.curation.lexicon_builder.foundation import _attested_wordnet_lemma, _exact_wordnet_ancestry
from GSE.curation.lexicon_builder.interchange import read_json
from GSE.curation.lexicon_builder.reviewed_export import export_reviewed_input
from GSE.curation.lexicon_builder.reviewed_patterns import run_workflow_input
from GSE.curation.lexicon_builder.rule_history import digest
from GSE.namespace import current_id


def _fingerprint(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _filler(entry_id, types):
    return SimpleNamespace(name=entry_id, bundle=[SimpleNamespace(types=types)])


def _type_evidence(definition, observation):
    if observation is None:
        return frozenset(), False
    types = _exact_wordnet_ancestry(definition, observation)
    return types, bool(types) and _attested_wordnet_lemma(definition, observation)


def _disposition(code, premise, target, expected_premise, expected_target):
    if code not in {"PARTIAL", "RESOLVED"}:
        return "BASELINE_REQUIRES_REVIEW"
    if premise != [expected_premise]:
        return "PREMISE_UNRESOLVED" if expected_premise in premise else "PREMISE_EXCLUDED"
    if expected_target not in target:
        return "CONTRADICTION"
    if target == [expected_target]:
        return "ALREADY_SUPPORTED"
    return "PROVISIONAL_FORWARD_FILL"


def _scan(conn, parent, discovery_ids):
    """Count the exact forward scope and keep opposition and type evidence."""
    premise_bank, premise_sign = parent["antecedent"]
    target_bank, target_sign = parent["consequent"]
    model_entries = {row[0] for row in conn.execute("SELECT DISTINCT entry_id FROM accepted_model_receipts")}
    counts = Counter()
    types_by_entry = {}
    typed_opposition, counterexamples = [], []
    scoped_counts = defaultdict(Counter)
    observations = conn.execute(
        "SELECT d.entry_id,l.lemma,l.pos,l.gloss,d.code,json_extract(d.domains,?),"
        "json_extract(d.domains,?),o.payload "
        "FROM definition_states d JOIN lexemes l ON l.id=d.lexeme_id "
        "LEFT JOIN source_observations o ON o.record_id=d.entry_id AND o.source='wordnet_hierarchy' "
        "ORDER BY d.entry_id",
        ("$." + premise_bank, "$." + target_bank),
    )
    for entry_id, lemma, pos, gloss, code, premise_json, target_json, payload in observations:
        definition = dict(entry_id=entry_id, lemma=lemma, pos=pos, definition=gloss)
        premise, target = json.loads(premise_json), json.loads(target_json)
        status = _disposition(code, premise, target, premise_sign, target_sign)
        counts[status] += 1
        observation = json.loads(payload) if payload is not None else None
        types, native = _type_evidence(definition, observation)
        if entry_id in discovery_ids:
            if status != "ALREADY_SUPPORTED" or not types or not native or pos != "noun":
                raise ValueError("REFINEMENT_DISCOVERY_EVIDENCE_CHANGED:" + entry_id)
            types_by_entry[entry_id] = types
        if native and pos == "noun":
            for name in types:
                scoped_counts[name][status] += 1
        if status != "CONTRADICTION":
            continue
        independent = entry_id not in model_entries
        if types and independent:
            typed_opposition.append(_filler(entry_id, types))
        counterexamples.append(
            {
                "definition": definition,
                "domains": {premise_bank: premise, target_bank: target},
                "type_evidence": "EXACT_WORDNET_PATHS" if types else "GUARD_MEMBERSHIP_UNKNOWN",
                "types": sorted(types),
                "native_lemma": native,
                "proof_ref": {"table": "definition_states", "entry_id": entry_id, "field": "trace"},
                "model_receipt_present": not independent,
            }
        )
    return counts, types_by_entry, typed_opposition, counterexamples, scoped_counts


def refine(candidate, selection, *, antecedent, consequent):
    from regenesis import induction, promotion_ledger

    path = Path(candidate).resolve(strict=True)
    snapshot = _fingerprint(path)
    reviewed_input = export_reviewed_input(path, selection)["input"]
    proposal = run_workflow_input(reviewed_input)
    parents = [
        item
        for item in proposal["candidates"]
        if item["proposal_kind"] == "OBSERVED_PAIR"
        and tuple(item["antecedent"]) == tuple(antecedent)
        and tuple(item["consequent"]) == tuple(consequent)
    ]
    if len(parents) != 1:
        raise ValueError("REFINEMENT_REQUIRES_OBSERVED_PAIR")
    parent = parents[0]
    discovery = frozenset(parent["discovery_entry_ids"])
    if not discovery or any(row["code"] != "OBSERVED_AGREEMENT" for row in parent["discovery"]):
        raise ValueError("REFINEMENT_REQUIRES_REVIEWED_AGREEMENTS")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        counts, witnessed, opposition, counterexamples, scoped_counts = _scan(conn, parent, discovery)
        if witnessed.keys() != discovery:
            raise ValueError("REFINEMENT_DISCOVERY_MISSING")
    if snapshot != _fingerprint(path):
        raise ValueError("REFINEMENT_CANDIDATE_CHANGED")
    confirming = [_filler(key, witnessed[key]) for key in sorted(discovery)]
    guards = promotion_ledger.impute_guard_candidates(confirming, opposition)
    return {
        "format": "GSE.lexicon-atomic-refinement/1",
        "code": "ATOMIC_GUARDS_PROPOSED"
        if guards
        else ("NO_SEPARATING_ATOMIC_GUARD" if opposition else "NO_TYPED_INDEPENDENT_OPPOSITION"),
        "candidate_sha256": snapshot,
        "selection_sha256": digest(selection),
        "reviewed_input_sha256": digest(reviewed_input),
        "learner_sha256": {
            module.__name__: _fingerprint(Path(module.__file__)) for module in (induction, promotion_ledger)
        },
        "parent": parent,
        "parent_population": dict(counts),
        "definitions_scanned": sum(counts.values()),
        "counterexamples": counterexamples,
        "typed_independent_counterexamples": len(opposition),
        "confirming_types": {key: sorted(types) for key, types in witnessed.items()},
        "candidates": [
            {
                "guards": [["pos", "noun"], ["wordnet_native_lemma", "true"], ["wordnet_ancestor:" + name, "true"]],
                "population": dict(scoped_counts[name]),
                "authority": "UNADMITTED_SCOPE_HYPOTHESIS",
            }
            for name in guards
        ],
        "search": "EXHAUSTIVE_POSITIVE_ATOMIC_ANCESTRY_IN_EXACT_NATIVE_NOUN_SCOPE",
        "measurement": "FORWARD_DOMAIN_SCREEN_REQUIRES_RELATIONAL_REPLAY",
    }


def prepare_audit(candidate, selection, refinement, review):
    """Turn one reviewed, strictly narrowed proposal into a withheld audit."""
    path = Path(candidate).resolve(strict=True)
    snapshot = _fingerprint(path)
    if (
        current_id(refinement["format"]) != "GSE.lexicon-atomic-refinement/1"
        or refinement["code"] != "ATOMIC_GUARDS_PROPOSED"
        or refinement["candidate_sha256"] != snapshot
        or refinement["selection_sha256"] != digest(selection)
    ):
        raise ValueError("REFINEMENT_REVIEW_SNAPSHOT_MISMATCH")
    if set(review) != {"ancestor", "audit_entry_ids", "warrant"}:
        raise ValueError("INVALID_REFINEMENT_REVIEW")
    guard = ["wordnet_ancestor:" + review["ancestor"], "true"]
    matches = [item for item in refinement["candidates"] if guard in item["guards"]]
    if len(matches) != 1:
        raise ValueError("REFINEMENT_GUARD_NOT_PROPOSED")
    child = matches[0]
    if any(child["population"].get(code) for code in ("CONTRADICTION", "BASELINE_REQUIRES_REVIEW")):
        raise ValueError("REFINEMENT_HAS_IN_SCOPE_OPPOSITION")
    fired = ("ALREADY_SUPPORTED", "PROVISIONAL_FORWARD_FILL", "CONTRADICTION")
    child_reach = sum(child["population"].get(code, 0) for code in fired)
    parent_reach = sum(refinement["parent_population"].get(code, 0) for code in fired)
    if not 0 < child_reach < parent_reach or not child["population"].get("PROVISIONAL_FORWARD_FILL"):
        raise ValueError("REFINEMENT_REQUIRES_STRICT_NARROWING_WITH_GAIN")
    parent = refinement["parent"]
    warrant = {
        **review["warrant"],
        "source_refs": [
            *review["warrant"]["source_refs"],
            "refinement:sha256:" + digest(refinement),
            "parent:" + parent["relation"]["rule_id"],
        ],
    }
    refined_selection = {
        "format": selection["format"],
        "discovery_entry_ids": selection["discovery_entry_ids"],
        "audit_entry_ids": review["audit_entry_ids"],
        "reviews": selection["reviews"],
        "guarded_candidates": [
            {
                "antecedent": list(parent["antecedent"]),
                "consequent": list(parent["consequent"]),
                "guards": child["guards"],
                "absent_evidence": [],
                "warrant": warrant,
            }
        ],
    }
    raw = export_reviewed_input(path, refined_selection)["input"]
    synsets = []
    for entry in raw["entries"]:
        exact = [
            obs["features"]["synset_name"]
            for obs in entry["observations"]
            if _exact_wordnet_ancestry(entry["definition"], obs)
        ]
        if len(exact) != 1:
            raise ValueError("REFINEMENT_AUDIT_REQUIRES_EXACT_WORDNET_IDENTITY")
        synsets.extend(exact)
    if len(set(synsets)) != len(synsets):
        raise ValueError("REFINEMENT_DISCOVERY_AUDIT_ALIAS_OVERLAP")
    [dry] = run_workflow_input(raw)["candidates"]
    if (
        not dry["audits"]
        or any(row["code"] != "OBSERVED_AGREEMENT" for row in dry["discovery"])
        or any(row["code"] != "STAGED_ONLY" for row in dry["staging"])
        or any(row["code"] != "AUDIT_CALL_BUDGET_EXHAUSTED" for row in dry["audits"])
    ):
        raise ValueError("REFINEMENT_AUDIT_NOT_READY")
    if snapshot != _fingerprint(path):
        raise ValueError("REFINEMENT_CANDIDATE_CHANGED")
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    screen = commands.add_parser("screen")
    screen.add_argument("--antecedent", nargs=2, required=True)
    screen.add_argument("--consequent", nargs=2, required=True)
    audit = commands.add_parser("prepare-audit")
    audit.add_argument("--refinement", type=Path, required=True)
    audit.add_argument("--review", type=Path, required=True)
    for command in (screen, audit):
        command.add_argument("--candidate", type=Path, required=True)
        command.add_argument("--selection", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("REFINEMENT_OUTPUT_MUST_BE_NEW")
    selection = read_json(args.selection)
    if args.command == "screen":
        left, right = args.antecedent, args.consequent
        result = refine(
            args.candidate, selection, antecedent=(left[0], int(left[1])), consequent=(right[0], int(right[1]))
        )
        summary = {key: result[key] for key in ("code", "definitions_scanned", "parent_population", "candidates")}
    else:
        result = prepare_audit(args.candidate, selection, read_json(args.refinement), read_json(args.review))
        summary = {"code": "REFINEMENT_AUDIT_READY", "audit_entry_ids": result["audit_entry_ids"]}
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
