"""Replay the VerbNet DO revision (2026-11-25): a doing verb, by NSM's DO valency, gains DO.

The WordNet hierarchy parser now carries identity from each prime's own concept to every kind below
it (``_WARRANTED_ROOT_PRIMITIVES``: an amount of time is WHEN, a point in space is WHERE, a group of
human beings is PEOPLE, an act is DO, ...), less reviewed branches (``REVIEWED_BRANCH_EXCLUSIONS``).
This script adds to each WordNet definition exactly the assertions the revised parser projects and the
release does not yet hold, re-resolves it with the production solver under the release's rules, and
stores it. A definition whose new identity contradicts its existing evidence, or whose resolution would
change an already settled value, is not changed; it is recorded as a conflict. The whole release is then
replayed by ``revise_source_candidate`` before the new candidate is installed beside the old one.

    .venv/bin/python scripts/revise_lexicon_wordnet_identity.py --candidate IN.db --output OUT.db \\
        --baseline-replay BASELINE.json --report REPORT.json
    .venv/bin/python scripts/revise_lexicon_wordnet_identity.py --write-baseline BASELINE.json --candidate IN.db
"""

import argparse
import hashlib
import json
from pathlib import Path

from GSE.curation.external_sources.verbnet import VerbNetEntry, VerbNetParser
from GSE.curation.lexicon_builder.completion import _contexts, _entry, _prepare_context_index
from GSE.curation.lexicon_builder.engine import Assertion
from GSE.curation.lexicon_builder.epoch import read, record
from GSE.curation.lexicon_builder.foundation import BANKS, lexical_context
from GSE.curation.lexicon_builder.resolution import resolve_dictionary
from GSE.curation.lexicon_builder.source_enrichment import revise_source_candidate
from GSE.curation.lexicon_builder.storage import store_entry
from GSE.curation.lexicon_builder.validation import _metadata, _relations, validate_build

SOURCE, FAMILY = "verbnet", "verb_structure"


def _projected_additions(conn, parser):
    """entry -> (record ids, the VerbNet signs the revised projection gives that the release lacks, by record)."""
    held = {}
    for entry_id, payload in conn.execute(
        "SELECT entry_id, payload FROM builder_assertions WHERE json_extract(payload,'$.source')=?", (SOURCE,)
    ):
        record_ = json.loads(payload)
        held.setdefault(entry_id, set()).add((record_["record_id"], record_["bank"], record_["value"]))
    additions = {}
    for entry_id, record_id, payload in conn.execute(
        "SELECT entry_id, record_id, payload FROM source_observations WHERE source=? AND entry_id LIKE 'wordnet:%'"
        " ORDER BY entry_id, record_id",
        (SOURCE,),
    ):
        native = {k: v for k, v in json.loads(payload)["features"]["native"].items() if k != "lemma"}
        projected = parser.to_primitives_for_entry(VerbNetEntry(**native))
        new = {b: v for b, v in projected.items() if (record_id, b, v) not in held.get(entry_id, set())}
        if new:
            additions.setdefault(entry_id, (entry_id, {}, set()))[1].update({(record_id, b): v for b, v in new.items()})
    return additions


def revise_entries(conn):
    parser = VerbNetParser()
    additions = _projected_additions(conn, parser)
    bound = {row[0] for row in conn.execute("SELECT DISTINCT entry_id FROM accepted_model_receipts")}
    _prepare_context_index(conn)
    contexts, relevance = {}, {}
    entries = tuple(additions)
    for start in range(0, len(entries), 500):  # SQLite bounds the variables in one statement
        batch_contexts, batch_relevance = _contexts(conn, entries[start : start + 500], indexed=True)
        contexts.update(batch_contexts)
        relevance.update(batch_relevance)
    rules = _relations(_metadata(conn, "relations"))
    changes, conflicts = [], []
    for entry_id, (synset, new, gone) in additions.items():
        if entry_id in bound:  # a model receipt was asked against the old evidence; leave it untouched
            conflicts.append(
                {
                    "entry_id": entry_id,
                    "synset": synset,
                    "added": {f"{b}@{r}": v for (r, b), v in new.items()},
                    "code": "MODEL_RECEIPT_BOUND",
                }
            )
            continue
        definition, assertions, restrictions, hierarchy = _entry(conn, entry_id)
        [raw] = conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (entry_id,)).fetchone()
        old = json.loads(raw)
        added = tuple(Assertion(bank, value, SOURCE, record, FAMILY) for (record, bank), value in sorted(new.items()))
        # A withdrawn projection leaves; every other assertion is kept as stored.
        assertions = tuple(a for a in assertions if not (a.source == SOURCE and (a.bank, a.value) in gone))
        state = resolve_dictionary(
            BANKS,
            assertions + added,
            rules,
            lexical_context(definition, contexts[entry_id], rules),
            evidence_banks=tuple(sorted(relevance[entry_id])),
            domain_restrictions=restrictions,
        )
        after = {name: sorted(values) for name, values in state.domains.items()}
        if state.code == "CONFLICT" or any(row["kind"] == "SOLVER_LIMIT" for row in state.trace):
            conflicts.append(
                {
                    "entry_id": entry_id,
                    "synset": synset,
                    "added": {f"{b}@{r}": v for (r, b), v in new.items()},
                    "code": state.code,
                }
            )
            continue
        withdrawn = {bank for bank, _value in gone}
        if any(len(old[name]) == 1 and old[name] != after[name] and name not in withdrawn for name in BANKS):
            conflicts.append(
                {
                    "entry_id": entry_id,
                    "synset": synset,
                    "added": {f"{b}@{r}": v for (r, b), v in new.items()},
                    "code": "WOULD_CHANGE_SETTLED",
                }
            )
            continue
        store_entry(conn, definition, state, assertions + added, hierarchy, domain_restrictions=restrictions)
        settled = {name: after[name][0] for name in BANKS if len(old[name]) > 1 and len(after[name]) == 1}
        reopened = sorted(name for name in withdrawn if old[name] != after[name])
        changes.append(
            {
                "entry_id": entry_id,
                "synset": synset,
                "added": {f"{b}@{r}": v for (r, b), v in new.items()},
                "settled": settled,
                "reopened": reopened,
            }
        )
    _recompute_catalog(conn, rules)
    return {"revised": len(changes), "conflicts": conflicts, "changes": changes}


def _recompute_catalog(conn, rules):
    """Install the prime catalog recomputed from the revised, validated state (as refresh_catalog does).

    The catalog records each prime unit's linked definitions and their evidence; identity revises
    prime-linked definitions (people, word, kind, body), so the stored catalog must be recomputed.
    """
    from GSE.curation.lexicon_builder.completion import _refresh_coverage
    from GSE.curation.lexicon_builder.source_enrichment import _refresh_unweighted_discovery
    from GSE.curation.lexicon_builder.validation import _canonical, _replay

    # The discovered candidates and coverage describe the assertions; refresh them first (the wrapper
    # repeats both, to the same result) so the catalog replay sees one consistent state.
    _refresh_unweighted_discovery(conn)
    _refresh_coverage(conn)
    links = {unit: tuple(entries) for unit, entries in _metadata(conn, "prime_entries").items()}
    replay = _replay(conn, rules, catalog_links=links)
    if replay["code"] != "REPLAY_VALIDATED" or not replay["complete_search"]:
        raise ValueError("VERBNET_DO_REVISION_CATALOG_REPLAY_FAILED:" + json.dumps(replay["mismatch_counts"]))
    catalog = replay.pop("proposed_catalog")
    report = _metadata(conn, "last_report")
    report["foundation_readiness"] = catalog["readiness"]
    report["prime_coverage"] = catalog["coverage_counts"]
    for key, value in (("catalog", catalog), ("last_report", report)):
        conn.execute("INSERT OR REPLACE INTO builder_metadata VALUES (?,?)", (key, _canonical(value)))


def revise(candidate, output, baseline_receipt):
    return revise_source_candidate(
        candidate,
        output,
        read(baseline_receipt),
        revise_entries,
        format_tag="GSE.verbnet-do-projection-revision/1",
        metadata_key="verbnet_do_projection_revision",
    )


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_baseline(candidate: Path, receipt: Path) -> dict:
    """The pinned replay a revision starts from: candidate digest, active pointer digest, full replay."""
    from GSE.lexicon_resource import ACTIVE_POINTER

    baseline = {
        "candidate": str(candidate),
        "candidate_sha256": _sha256(candidate),
        "active_pointer_sha256": _sha256(ACTIVE_POINTER),
        "replay": validate_build(candidate),
    }
    record(receipt, baseline)
    return baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline-replay", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--write-baseline", type=Path)
    args = parser.parse_args()
    if args.write_baseline:
        baseline = write_baseline(args.candidate, args.write_baseline)
        print(json.dumps({k: baseline["replay"].get(k) for k in ("code", "entries_checked", "entries_mismatched")}))
        return
    if args.report.exists() or args.report.resolve() == args.output.resolve():
        raise ValueError("VERBNET_DO_REVISION_REPORT_MUST_BE_NEW")
    report = revise(args.candidate, args.output, args.baseline_replay)
    record(args.report, report)
    summary = {k: report.get(k) for k in ("code", "candidate", "coverage")}
    summary["revised"] = report["changes"]["revised"]
    summary["conflicts"] = len(report["changes"]["conflicts"])
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
