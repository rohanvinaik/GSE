"""Replay the reviewed withdrawal of three unsupported WordNet SAY projections."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from gse.curation.external_sources.wordnet_hierarchy import REVIEWED_SAY_EXCLUSIONS, reviewed_say_exclusion
from gse.curation.lexicon_builder.completion import (
    _contexts,
    _entry,
    _prepare_context_index,
)
from gse.curation.lexicon_builder.epoch import read, record
from gse.curation.lexicon_builder.foundation import BANKS, lexical_context
from gse.curation.lexicon_builder.resolution import resolve_dictionary
from gse.curation.lexicon_builder.rule_history import digest
from gse.curation.lexicon_builder.rule_revisions import exception_source
from gse.curation.lexicon_builder.source_enrichment import _refuse_bound_receipts, revise_source_candidate
from gse.curation.lexicon_builder.storage import store_entry
from gse.curation.lexicon_builder.validation import _metadata, _relations


def revise_entries(conn):
    scopes = {
        entry_id: synset
        for entry_id, synset in conn.execute(
            """SELECT d.entry_id, json_extract(o.payload,'$.features.synset_name')
               FROM definition_states d JOIN source_observations o ON o.record_id=d.entry_id
               WHERE o.source='wordnet_hierarchy' AND o.scope='lexical'
                 AND json_extract(o.payload,'$.features.synset_name') IN (SELECT value FROM json_each(?))
               ORDER BY d.entry_id""",
            (json.dumps(list(REVIEWED_SAY_EXCLUSIONS)),),
        )
    }
    if set(scopes.values()) != set(REVIEWED_SAY_EXCLUSIONS):
        raise ValueError("SAY_REVISION_SOURCE_SCOPE_INCOMPLETE")
    _refuse_bound_receipts(conn, set(scopes))
    for table in ("model_rule_versions", "model_reconsideration_archive"):
        if conn.execute(
            f"SELECT 1 FROM {table} WHERE entry_id IN (SELECT value FROM json_each(?)) LIMIT 1",
            (json.dumps(list(scopes)),),
        ).fetchone():
            raise ValueError("SAY_REVISION_HISTORICAL_MODEL_CONTEXT_BOUND")
    _prepare_context_index(conn)
    contexts, relevance = _contexts(conn, tuple(scopes), indexed=True)
    rules = _relations(_metadata(conn, "relations"))
    changes = []
    for entry_id, synset in scopes.items():
        source = exception_source(conn, entry_id)
        features = source["observation"]["features"]
        root, bank = reviewed_say_exclusion(synset, source["definition"]["definition"])
        if not any(root in path for path in features["hypernym_paths"]):
            raise ValueError("SAY_REVISION_ANCESTOR_WITNESS_MISSING:" + entry_id)
        definition, assertions, restrictions, hierarchy = _entry(conn, entry_id)
        [raw] = conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (entry_id,)).fetchone()
        old = json.loads(raw)
        removed = [
            a
            for a in assertions
            if (a.bank, a.value, a.source, a.record_id, a.scope) == (bank, 1, "wordnet_hierarchy", entry_id, "lexical")
        ]
        if len(removed) != 1 or old[bank] != [1]:
            raise ValueError("SAY_REVISION_ASSERTION_WITNESS_MISSING:" + entry_id)
        retained = tuple(a for a in assertions if a not in removed)
        state = resolve_dictionary(
            BANKS,
            retained,
            rules,
            lexical_context(definition, contexts[entry_id], rules),
            evidence_banks=tuple(sorted(relevance[entry_id])),
            domain_restrictions=restrictions,
        )
        new = {name: sorted(values) for name, values in state.domains.items()}
        if (
            state.code == "CONFLICT"
            or any(row["kind"] == "SOLVER_LIMIT" for row in state.trace)
            or new[bank] != [-1, 0, 1]
            or any(old[name] != new[name] for name in BANKS if name != bank)
        ):
            raise ValueError("SAY_REVISION_REQUIRES_DOMAIN_CHANGE_REVIEW:" + entry_id)
        store_entry(conn, definition, state, retained, hierarchy, domain_restrictions=restrictions)
        changes.append(
            {
                "entry_id": entry_id,
                "synset": synset,
                "source_sha256": digest(source),
                "assertion": asdict(removed[0]),
                "before": old[bank],
                "after": new[bank],
            }
        )
    return changes


def revise(candidate, output, baseline_receipt):
    return revise_source_candidate(
        candidate,
        output,
        read(baseline_receipt),
        revise_entries,
        format_tag="gse.wordnet-say-projection-revision/1",
        metadata_key="wordnet_say_projection_revision",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-replay", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink() or args.report.resolve() == args.output.resolve():
        raise ValueError("SAY_REVISION_REPORT_MUST_BE_NEW")
    report = revise(args.candidate, args.output, args.baseline_replay)
    record(args.report, report)
    print(json.dumps({key: report[key] for key in ("code", "candidate", "coverage")}), flush=True)


if __name__ == "__main__":
    main()
