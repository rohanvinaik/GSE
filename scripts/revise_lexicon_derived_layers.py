"""Install the derived layers into the one production state, through the source-revision path (Rohan, 2026-11-26).

The meter and the SSL controller read the stored definition states, so a value kept in a side layer is invisible to
both. This revision writes three derived channels into the definitions as typed, replayable evidence:

* ``subkind-inheritance`` and ``form-of`` (``word_sense_subkinds``): the inherited defaults admitted by constraint
  closure, read from the candidate's derived table; their strict consequences re-derive under the release's rules;
* ``nsm-molecule`` (``word_sense_nsm_molecules``): a bound NSM category explication's components on its kinds;
* ``nsm-valency`` (``valency_absence``): confident zeros for persons-only predicates on non-living things, times and
  places.

Each definition gains one source observation per channel (record ``derived:<channel>:<entry>``, family ``derived``,
scope lexical) and the matching assertions; replay validates every one (``validation`` recomputes the molecule and
valency witnesses and checks the inheritance payload). Family ``derived`` never confirms anything: significance
weighting counts only stated facts. A definition bound by a model receipt is left untouched, a contradiction or a
change to a settled value is recorded and not stored, and the whole release is replayed before the candidate exists.

    .venv/bin/python scripts/revise_lexicon_derived_layers.py --candidate IN.db --output OUT.db \\
        --baseline-replay BASELINE.json --report REPORT.json
"""

import argparse
import json
from pathlib import Path

from GSE.curation.lexicon_builder.completion import _contexts, _entry, _prepare_context_index
from GSE.curation.lexicon_builder.engine import Assertion
from GSE.curation.lexicon_builder.epoch import read, record
from GSE.curation.lexicon_builder.foundation import BANKS, lexical_context
from GSE.curation.lexicon_builder.resolution import resolve_dictionary
from GSE.curation.lexicon_builder.source_enrichment import revise_source_candidate
from GSE.curation.lexicon_builder.storage import store_entry
from GSE.curation.lexicon_builder.validation import _metadata, _relations

FAMILY = "derived"
CONSEQUENCE = "strict consequence of the inherited defaults"


def _additions(conn):
    """entry -> channel -> (bank values, features for its observation)."""
    from GSE.curation.lexicon_builder.valency_absence import absent_banks, nonliving_root
    from GSE.curation.lexicon_builder.word_sense_nsm_molecules import inherited

    held = {
        entry: {b for b, v in json.loads(raw).items() if len(v) == 1}
        for entry, raw in conn.execute("SELECT entry_id, domains FROM definition_states")
    }
    out: dict[str, dict[str, tuple[dict, dict]]] = {}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='genus_differentia_closure'").fetchone():
        for entry, settled, edge in conn.execute("SELECT entry_id, settled, edge FROM genus_differentia_closure"):
            edge = json.loads(edge)
            values = {
                b: v
                for b, v in json.loads(settled).items()
                if edge["origins"].get(b) != CONSEQUENCE and b not in held.get(entry, ())
            }
            if values:
                channel = "form-of" if edge["template"] == "form-of" else "subkind-inheritance"
                out.setdefault(entry, {})[channel] = (values, {"values": values, "edge": edge})
    for entry in held:
        if not (entry.startswith("wordnet:") and ".n." in entry):
            continue
        synset = entry.rsplit(":", 1)[1]
        molecule = {b: v for b, (v, _w) in inherited(synset).items() if b not in held[entry]}
        if molecule:
            warrants = {b: w for b, (_v, w) in inherited(synset).items() if b in molecule}
            out.setdefault(entry, {})["nsm-molecule"] = (molecule, {"values": molecule, "warrants": warrants})
        zeros = {b: 0 for b in absent_banks(entry) if b not in held[entry]}
        if zeros:
            out.setdefault(entry, {})["nsm-valency"] = (zeros, {"values": zeros, "root": nonliving_root(synset)})
    return out


def _receipt_bound(conn) -> set[str]:
    """Every definition a model receipt pins, live or archived: a receipt pins the observations its definition had
    when it was asked, so a new observation on it would break that receipt's replay (MODEL_OBSERVATIONS_MISMATCH)."""
    from GSE.curation.lexicon_builder.rule_history import read_history
    from GSE.curation.lexicon_builder.validation import _relations

    bound = {row[0] for row in conn.execute("SELECT DISTINCT entry_id FROM accepted_model_receipts")}
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "model_reconsideration_archive" in tables:
        bound |= {row[0] for row in conn.execute("SELECT DISTINCT entry_id FROM model_reconsideration_archive")}
    history = read_history(conn, _relations(_metadata(conn, "relations")))
    for event in (history or {}).get("events", []):
        for archived in event["archived"]:
            bound.add(archived["definition"]["entry_id"])
    return bound


def revise_entries(conn):
    additions = _additions(conn)
    bound = _receipt_bound(conn)
    _prepare_context_index(conn)
    rules = _relations(_metadata(conn, "relations"))
    entries = tuple(sorted(e for e in additions if e not in bound))
    changes, conflicts = [], [{"entry_id": e, "code": "MODEL_RECEIPT_BOUND"} for e in sorted(set(additions) & bound)]
    for start in range(0, len(entries), 500):  # SQLite bounds the variables in one statement
        batch = entries[start : start + 500]
        contexts, relevance = _contexts(conn, batch, indexed=True)
        for entry_id in batch:
            definition, assertions, restrictions, hierarchy = _entry(conn, entry_id)
            [raw] = conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (entry_id,)).fetchone()
            old = json.loads(raw)
            added, observations = [], []
            for channel, (values, features) in sorted(additions[entry_id].items()):
                record_id = f"derived:{channel}:{entry_id}"
                payload = {
                    "entry_id": entry_id,
                    "source": channel,
                    "record_id": record_id,
                    "family": FAMILY,
                    "features": features,
                    "scope": "lexical",
                    "candidate_entry_ids": [],
                }
                observations.append(
                    (record_id, entry_id, channel, FAMILY, "lexical", json.dumps(payload, sort_keys=True))
                )
                added += [Assertion(b, v, channel, record_id, FAMILY) for b, v in sorted(values.items())]
            state = resolve_dictionary(
                BANKS,
                tuple(assertions) + tuple(added),
                rules,
                lexical_context(definition, tuple(contexts[entry_id]), rules),
                evidence_banks=tuple(sorted(relevance[entry_id])),
                domain_restrictions=restrictions,
            )
            after = {name: sorted(values) for name, values in state.domains.items()}
            if state.code == "CONFLICT" or any(row["kind"] == "SOLVER_LIMIT" for row in state.trace):
                conflicts.append({"entry_id": entry_id, "code": state.code})
                continue
            if any(len(old[name]) == 1 and old[name] != after[name] for name in BANKS):
                conflicts.append({"entry_id": entry_id, "code": "WOULD_CHANGE_SETTLED"})
                continue
            conn.executemany("INSERT OR REPLACE INTO source_observations VALUES (?,?,?,?,?,?)", observations)
            store_entry(
                conn, definition, state, tuple(assertions) + tuple(added), hierarchy, domain_restrictions=restrictions
            )
            settled = {name: after[name][0] for name in BANKS if len(old[name]) > 1 and len(after[name]) == 1}
            changes.append({"entry_id": entry_id, "channels": sorted(additions[entry_id]), "settled": settled})
    _recompute_catalog(conn, rules)
    return {
        "revised": len(changes),
        "settled_cells": sum(len(c["settled"]) for c in changes),
        "conflicts": conflicts,
        "changes": changes,
    }


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
        raise ValueError("IDENTITY_REVISION_CATALOG_REPLAY_FAILED:" + json.dumps(replay["mismatch_counts"]))
    catalog = replay.pop("proposed_catalog")
    report = _metadata(conn, "last_report")
    report["foundation_readiness"] = catalog["readiness"]
    report["prime_coverage"] = catalog["coverage_counts"]
    for key, value in (("catalog", catalog), ("last_report", report)):
        conn.execute("INSERT OR REPLACE INTO builder_metadata VALUES (?,?)", (key, _canonical(value)))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-replay", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise ValueError("DERIVED_REVISION_REPORT_MUST_BE_NEW")
    report = revise_source_candidate(
        args.candidate,
        args.output,
        read(args.baseline_replay),
        revise_entries,
        format_tag="GSE.derived-layers-revision/1",
        metadata_key="derived_layers_revision",
    )
    record(args.report, report)
    changes = report["changes"]
    print(
        json.dumps(
            {
                "code": report["code"],
                "revised": changes["revised"],
                "settled_cells": changes["settled_cells"],
                "conflicts": len(changes["conflicts"]),
                "coverage": report.get("coverage"),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
