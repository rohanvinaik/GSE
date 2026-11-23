"""Journal independent approved BODY questions while corpus replay runs.

The read-only baseline plus TEMP observation overlay is exactly the observation
relation of the proposed enriched snapshot. The epoch controller remains the
writer/admission authority: its later complete request hash, schema and model
identity must match each journal before any answer can be reused.
"""

import json
import sqlite3
from contextlib import closing
from importlib import import_module

from gse.curation.lexicon_builder.completion import _contexts, _entry
from gse.curation.lexicon_builder.epoch import JournaledTransport, read, record
from gse.curation.lexicon_builder.foundation import BANKS, lexical_context
from gse.curation.lexicon_builder.residual import OllamaTransport, build_request
from gse.curation.lexicon_builder.resolution import resolve_dictionary
from gse.curation.lexicon_builder.source_enrichment import _construct, _observations, _verify_wordnet
from gse.curation.lexicon_builder.validation import _metadata, _relations

round_ = import_module("docs.readings.2026-11-13-ssl-explicit-genera.vertebrate_021_approved")


def prepare_requests(baseline, raw):
    """Use existing loaders and closure on a read-only exact SQL overlay."""
    records = _observations({"format": "gse.source-enrichment-input/1", "observations": raw})
    identities = tuple(r.entry_id for r in records)
    requests = []
    with closing(sqlite3.connect(baseline.as_uri() + "?mode=ro", uri=True)) as conn:
        definitions = {r.entry_id: _construct(conn, r) for r in records}
        _verify_wordnet(records, definitions)
        conn.execute("CREATE TEMP TABLE added_context(record_id TEXT,entry_id TEXT,source TEXT,family TEXT,scope TEXT,payload TEXT)")
        conn.executemany("INSERT INTO added_context VALUES (?,?,?,?,?,?)", [
            (r["record_id"], r["entry_id"], r["source"], r["family"], r["scope"], json.dumps(r)) for r in raw
        ])
        conn.execute("CREATE TEMP VIEW source_observations AS SELECT * FROM main.source_observations UNION ALL SELECT * FROM added_context")
        indexed = bool(conn.execute("SELECT 1 FROM main.sqlite_master WHERE type='table' AND name='completion_context_targets'").fetchone())
        observations, evidence = _contexts(conn, identities, indexed=indexed)
        rules = _relations(_metadata(conn, "relations"))
        for identity in identities:
            definition, assertions, restrictions, _ = _entry(conn, identity)
            context = lexical_context(definition, observations[identity], rules)
            state = resolve_dictionary(BANKS, assertions, rules, context, evidence_banks=tuple(sorted(evidence[identity])), domain_restrictions=restrictions)
            requests.append(build_request(identity, "BODY", state, tuple(observations[identity]), definition=definition, relations=rules, context=context))
    return tuple(requests)


def run():
    round_.verify_sources()
    raw = read(round_.NOTES / "021-approved-source-context.json")["observations"]
    identities = ("wordnet:man:homo.n.02", *round_.HOLDOUTS)
    if [r["entry_id"] for r in raw] != list(identities):
        raise ValueError("PREFETCH_RESERVED_IDENTITIES_MISMATCH")
    requests = prepare_requests(round_.BASE, raw)
    phase = round_.WORK / "zipf/epoch-01"
    phase.mkdir(parents=True, exist_ok=True)
    record(round_.NOTES / "021-approved-prefetch-contract.json", {
        "code": "INDEPENDENT_QUESTIONS_FROM_READ_ONLY_EXACT_OBSERVATION_OVERLAY",
        "requests": [{"entry_id": r.entry_id, "request_id": r.request_id} for r in requests],
        "source_context": "021-approved-source-context.json", "writes_lexical_cells": False,
        "reuse_requires": "EXACT_LATER_CONTROLLER_REQUEST_SCHEMA_AND_TRANSPORT_IDENTITY",
    })
    native = OllamaTransport(round_.MODEL, context_tokens=81920, timeout=420, thinking=False, output_tokens=256)
    native.pin()
    if not native.identity.startswith(f"{round_.MODEL}#{round_.MODEL_DIGEST}@"):
        raise ValueError("PREFETCH_MODEL_CHANGED")
    for index, request in enumerate(requests):
        label, limit = ("teach", 1) if index == 0 else ("audit", 4)
        transport = JournaledTransport(native, phase, label, limit, round_.WORK / "model.lock")
        answer = transport(request.payload(), request.output_schema())
        print("PREFETCHED_APPROVED_BODY", request.entry_id, answer, flush=True)


if __name__ == "__main__":
    run()
