"""Compare unadmitted forward priors or relational constraints on a pinned snapshot."""

import argparse
import hashlib
import json
import math
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import asdict
from itertools import batched, product
from pathlib import Path
from urllib.parse import unquote

from GSE.curation.lexicon_builder.completion import _contexts, _entry, _prepare_context_index, _priority_source
from GSE.curation.lexicon_builder.engine import TERNARY, Relation
from GSE.curation.lexicon_builder.foundation import BANKS, lexical_context, validate_lexical_guards
from GSE.curation.lexicon_builder.interchange import read_json
from GSE.curation.lexicon_builder.resolution import resolve_dictionary
from GSE.curation.lexicon_builder.rule_history import digest, relation_records
from GSE.curation.lexicon_builder.validation import _metadata, _read_json, _relations, _schema
from GSE.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path


def _digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _relation(spec):
    left, x = spec["antecedent"]
    right, y = spec["consequent"]
    if left == right or any(bank not in BANKS for bank in (left, right)):
        raise ValueError("INVALID_COHERENCE_BANK_PAIR")
    if any(type(sign) is not int or sign not in TERNARY for sign in (x, y)):
        raise ValueError("INVALID_COHERENCE_SIGN")
    return Relation(
        spec["id"],
        (left, right),
        tuple((a, b) for a, b in product(sorted(TERNARY), repeat=2) if a != x or b == y),
        tuple(spec["source_refs"]),
        "conditional",
        True,
        tuple(map(tuple, spec["guards"])),
    )


def _exceptions(resolution):
    return [e for e in resolution.trace if e["kind"] in {"CONDITIONAL_EXCEPTION", "SOLVER_LIMIT"}]


def _issues(baseline, staged):
    issues = [e for e in _exceptions(staged) if e not in _exceptions(baseline)]
    if staged.code == "CONFLICT":
        issues.append({"kind": "STAGED_CONFLICT", "conflicts": staged.conflicts})
    for bank, old in baseline.domains.items():
        if not staged.domains[bank] <= old:
            issues.append(
                {
                    "kind": "BASELINE_DOMAIN_EXPANDED_OR_CHANGED",
                    "bank": bank,
                    "before": sorted(old),
                    "after": sorted(staged.domains[bank]),
                }
            )
    return issues


def _forward(baseline, proposals, solve):
    """Require witnessed singleton premises. Reclose with all fired rules together."""
    current = baseline
    fired = []
    pending = list(proposals)
    while pending:
        ready = [
            (spec, rule) for spec, rule in pending if current.domains[spec["antecedent"][0]] == {spec["antecedent"][1]}
        ]
        if not ready:
            break
        fired.extend(rule for _, rule in ready)
        pending = [item for item in pending if item not in ready]
        current = solve(tuple(fired))
        if _issues(baseline, current):
            break
    return current, [rule.rule_id for rule in fired], _issues(baseline, current)


def _evaluate(baseline, proposals, solve, semantics):
    if semantics == "FORWARD_PRIOR":
        return _forward(baseline, proposals, solve)
    if semantics != "RELATIONAL_CONSTRAINT":
        raise ValueError("INVALID_COHERENCE_SEMANTICS")
    rules = tuple(rule for _, rule in proposals)
    after = solve(rules)
    return after, [rule.rule_id for rule in rules], _issues(baseline, after)


def _surviving_delta(before, after, issues):
    """Conditional exception receipts withdraw their own component's rules.

    Reuse the resolver's surviving domains. Hard conflicts, incomplete support
    checks, or reopened baseline domains still prohibit counting any gain.
    """
    if after.code == "CONFLICT" or any(issue["kind"] != "CONDITIONAL_EXCEPTION" for issue in issues):
        return {}
    if any(record["kind"] == "SOLVER_LIMIT" for record in after.trace):
        return {}
    return _delta(before, after)


def _delta(before, after):
    return {
        bank: {"before": sorted(old), "after": sorted(after.domains[bank])}
        for bank, old in before.domains.items()
        if after.domains[bank] < old
    }


def _metrics(counts, changes, weight):
    for value in changes.values():
        old, new = value["before"], value["after"]
        bits = math.log2(len(old) / len(new))
        counts["narrowed_cells"] += 1
        counts["domain_potential_bits"] += bits
        counts["subtlex_weighted_domain_potential"] += weight * bits
        if len(new) == 1:
            counts["new_singletons"] += 1
            counts[f"new_value_{new[0]}"] += 1
        else:
            counts["narrowed_but_unresolved"] += 1


def _indexed_challenges(manifest):
    by_synset = {}
    for item in manifest["scope_challenges"]:
        by_synset.setdefault(item["native_synset"], []).append(item)
    return by_synset


def _cohort(conn, proposals, challenges, *, relational=False):
    candidates, population, spelling_counts, premises = [], Counter(), Counter(), Counter()
    for entry, lemma, raw in conn.execute(
        "SELECT d.entry_id,l.lemma,d.domains FROM definition_states d JOIN lexemes l ON d.lexeme_id=l.id ORDER BY d.entry_id"
    ):
        domains = _read_json(raw)
        if set(domains) != set(BANKS):
            raise ValueError("INVALID_BASELINE_DOMAIN_BASIS")
        population["definitions"] += 1
        population["cells"] += len(domains)
        population["unknown"] += sum(len(domain) > 1 for domain in domains.values())
        population["explicit_zero"] += sum(domain == [0] for domain in domains.values())
        spelling_counts[lemma.casefold()] += 1
        matching = [spec["id"] for spec, _ in proposals if domains[spec["antecedent"][0]] == [spec["antecedent"][1]]]
        premises.update(matching)
        synset = unquote(entry.rsplit(":", 1)[1]) if entry.startswith("wordnet:") else None
        review = challenges.get(synset, ())
        if relational or matching or review:
            candidates.append((entry, raw if relational else domains, review))
    return candidates, population, spelling_counts, premises


def _contextual_rows(conn, rows, *, indexed):
    """Keep source evidence bounded while evaluating the complete population."""
    chunks = batched(rows, 512) if indexed else (rows,)
    for chunk in chunks:
        observations, relevance = _contexts(conn, tuple(entry for entry, _, _ in chunk), indexed=indexed)
        for entry, persisted, challenges in chunk:
            domains = _read_json(persisted) if isinstance(persisted, str) else persisted
            yield entry, domains, challenges, observations[entry], tuple(sorted(relevance[entry]))


def _scan(conn, manifest, proposals):
    _schema(conn)
    base = _relations(_metadata(conn, "relations"))
    if {r.rule_id for _, r in proposals} & {r.rule_id for r in base}:
        raise ValueError("COHERENCE_RULE_ID_ALREADY_PRESENT")
    all_rules = base + tuple(r for _, r in proposals)
    validate_lexical_guards(all_rules)
    semantics = manifest.get("semantics", "FORWARD_PRIOR")
    relational = semantics == "RELATIONAL_CONSTRAINT"
    version_two = manifest["format"] == "gse.coherence-stage-input/2"
    rows, population, spelling_counts, premise_counts = _cohort(
        conn, proposals, _indexed_challenges(manifest), relational=relational
    )
    priority, freq = _priority_source("zipf", None)
    summaries = {spec["id"]: Counter({"corpus_premise_matches": premise_counts[spec["id"]]}) for spec, _ in proposals}
    joint = Counter()
    staged_changes, contradictions, scope_reviews = [], [], []
    for entry, persisted, challenges, records, relevant in _contextual_rows(conn, rows, indexed=relational):
        definition, assertions, restrictions, _ = _entry(conn, entry)
        context = lexical_context(definition, records, all_rules)
        lexical = [r for r in records if r["scope"] == "lexical" and r["entry_id"] == entry]
        for challenge in challenges:
            premise, value = challenge["antecedent"]
            if persisted[premise] == [value]:
                scope_reviews.append(
                    {
                        "code": "SOURCE_SCOPE_CHALLENGE",
                        "definition": asdict(definition),
                        "challenge": challenge,
                        "domains": persisted,
                        "assertions": [asdict(a) for a in assertions],
                        "observations": lexical,
                    }
                )
        eligible = tuple((spec, r) for spec, r in proposals if all(context.get(k) == v for k, v in r.guards))
        if (
            not eligible
            or not relational
            and not any(persisted[spec["antecedent"][0]] == [spec["antecedent"][1]] for spec, _ in eligible)
        ):
            continue

        def solve(extra):
            return resolve_dictionary(
                BANKS, assertions, base + extra, context, evidence_banks=relevant, domain_restrictions=restrictions
            )

        before = solve(())
        if {k: sorted(v) for k, v in before.domains.items()} != persisted or before.code == "CONFLICT":
            raise ValueError("STAGING_BASELINE_MISMATCH:" + entry)
        weight = freq.get(definition.lemma.casefold(), 0) / spelling_counts[definition.lemma.casefold()]
        isolated = {}
        for item in eligible:
            spec, rule = item
            after, fired, issues = _evaluate(before, (item,), solve, semantics)
            if not fired:
                continue
            counts = summaries[rule.rule_id]
            counts["standalone_fired"] += 1
            changes = (
                _surviving_delta(before, after, issues) if version_two else _delta(before, after) if not issues else {}
            )
            _metrics(counts, changes, weight)
            if issues:
                counts["standalone_review_definitions"] += 1
            isolated[rule.rule_id] = {"changes": changes, "issues": issues, "trace": after.trace}
        after, fired, issues = _evaluate(before, eligible, solve, semantics)
        joint["definitions_with_fired_rules"] += 1
        for rule in fired:
            summaries[rule]["joint_fired"] += 1
        needs_review = bool(issues or any(case["issues"] for case in isolated.values()))
        changes = (
            _surviving_delta(before, after, issues)
            if version_two
            else _delta(before, after)
            if not needs_review
            else {}
        )
        if needs_review:
            joint["review_definitions"] += 1
            contradictions.append(
                {
                    "definition": asdict(definition),
                    "context": context,
                    "fired": fired,
                    "issues": issues,
                    "before": persisted,
                    "attempted": {k: sorted(v) for k, v in after.domains.items()},
                    "assertions": [asdict(a) for a in assertions],
                    "observations": lexical,
                    "baseline_trace": before.trace,
                    "joint_trace": after.trace,
                    "isolated": isolated,
                    "disposition": "SUPPORTED_COMPONENT_GAINS_RETAINED"
                    if changes
                    else "NO_STAGED_VALUES_COUNTED_FOR_THIS_DEFINITION",
                    **({"retained_changes": changes} if version_two else {}),
                }
            )
            if not version_two:
                continue
        _metrics(joint, changes, weight)
        solo = {b for case in isolated.values() for b, value in case["changes"].items() if len(value["after"]) == 1}
        resolved = {b for b, value in changes.items() if len(value["after"]) == 1}
        joint["joint_only_singletons"] += len(resolved - solo)
        joint["standalone_union_singletons"] += len(solo)
        if changes:
            staged_changes.append(
                {
                    "definition": asdict(definition),
                    "fired": fired,
                    "changes": changes,
                    "trace": [e for e in after.trace if e.get("bank") in changes],
                    **({"review_required": needs_review} if version_two else {}),
                }
            )
    return {
        "population": population,
        "rules": summaries,
        "joint": joint,
        "changes": staged_changes,
        "contradictions": contradictions,
        "scope_reviews": scope_reviews,
        "zipf": priority,
        "definitions_selected_for_context": len(rows),
        "rule_version": digest(relation_records(base)),
    }


def stage(candidate, manifest):
    candidate = candidate.resolve(strict=True)
    active = resolve_lexicon_path()
    if active.exists() and candidate.samefile(active):
        raise ValueError("COHERENCE_REQUIRES_SEPARATE_CANDIDATE")
    version_two = manifest["format"] == "gse.coherence-stage-input/2"
    if (
        manifest["format"] not in {"gse.coherence-stage-input/1", "gse.coherence-stage-input/2"}
        or not manifest["proposals"]
    ):
        raise ValueError("INVALID_COHERENCE_STAGE_INPUT")
    if version_two:
        if type(manifest.get("semantics")) is not str or manifest["semantics"] not in {
            "FORWARD_PRIOR",
            "RELATIONAL_CONSTRAINT",
        }:
            raise ValueError("INVALID_COHERENCE_SEMANTICS")
    elif "semantics" in manifest:
        raise ValueError("COHERENCE_SEMANTICS_REQUIRES_VERSION_TWO")
    proposals = tuple((spec, _relation(spec)) for spec in manifest["proposals"])
    if len({rule.rule_id for _, rule in proposals}) != len(proposals):
        raise ValueError("DUPLICATE_COHERENCE_RULE_ID")
    pointer = ACTIVE_POINTER.read_bytes()
    digest = _digest(candidate)
    if digest != manifest["baseline_sha256"]:
        raise ValueError("COHERENCE_BASELINE_HASH_MISMATCH")
    with closing(sqlite3.connect(candidate.as_uri() + "?mode=ro", uri=True)) as conn:
        if manifest.get("semantics") == "RELATIONAL_CONSTRAINT":
            _prepare_context_index(conn)
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        report = _scan(conn, manifest, proposals)
    if _digest(candidate) != digest or ACTIVE_POINTER.read_bytes() != pointer:
        raise ValueError("COHERENCE_STAGE_SNAPSHOT_CHANGED")
    return {
        **report,
        "format": "gse.coherence-stage-report/2" if version_two else "gse.coherence-stage-report/1",
        **(
            {
                "semantics": manifest["semantics"],
                "migration_compatibility": "RELATIONAL_EFFECTS_STAGED_UNADMITTED"
                if manifest["semantics"] == "RELATIONAL_CONSTRAINT"
                else "FORWARD_ONLY_REQUIRES_SEPARATE_RELATIONAL_AUDIT",
            }
            if version_two
            else {}
        ),
        "candidate": str(candidate),
        "candidate_sha256": digest,
        "active_pointer_sha256": hashlib.sha256(pointer).hexdigest(),
        "proposals": manifest["proposals"],
        "authority": "UNADMITTED_READ_ONLY_STAGE",
        "lexicon_writes": False,
        "unknown_semantics": "MULTIVALUED_DOMAIN_DISTINCT_FROM_EXPLICIT_ZERO",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        raise ValueError("COHERENCE_REPORT_MUST_BE_NEW")
    report = stage(args.candidate, read_json(args.manifest))
    with args.report.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({key: report[key] for key in ("population", "joint", "lexicon_writes")}))


if __name__ == "__main__":
    main()
