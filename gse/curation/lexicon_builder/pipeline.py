"""One executable path from native evidence to a partial, justified dictionary."""

import logging
from collections import Counter, defaultdict
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from .engine import Assertion, propagate
from .evidence import Definition, EvidenceBundle, Observation, collect_evidence, validate_assertion_competence
from .foundation import (
    BANKS,
    CONVENTION_VERSION,
    WANT_POLARITY,
    definition_context,
    load_manifest,
    load_manifest_extensions,
    projection_relations,
    representation_contract,
)
from .interchange import read_json
from .relevance import observation_relevance
from .resolution import resolve_dictionary
from .storage import _json, open_build, store_candidates, store_entry, store_observations, store_unresolved

logger = logging.getLogger(__name__)


def load_evidence(path: str | Path) -> EvidenceBundle:
    """Read the typed evidence interchange used for reproducible offline builds."""
    raw = read_json(path)
    if not isinstance(raw, dict) or raw.get("format") != "gse.lexicon-evidence/1":
        raise ValueError("INVALID_EVIDENCE_FORMAT")
    if set(raw) - {"format", "definitions", "observations", "assertions", "unresolved"}:
        raise ValueError("UNKNOWN_EVIDENCE_FIELD")
    for key in ("definitions", "observations", "assertions", "unresolved"):
        if not isinstance(raw.get(key, []), list):
            raise ValueError(f"INVALID_EVIDENCE_{key.upper()}")
    for key, permitted, sequences in (
        ("definitions", {"entry_id", "lemma", "pos", "definition", "source_ids"}, ("source_ids",)),
        (
            "observations",
            {"entry_id", "source", "record_id", "family", "features", "scope", "candidate_entry_ids"},
            ("candidate_entry_ids",),
        ),
    ):
        for record in raw.get(key, []):
            if not isinstance(record, dict) or set(record) - permitted:
                raise ValueError("INVALID_EVIDENCE_RECORD")
            if any(not isinstance(record.get(field, []), list) for field in sequences):
                raise ValueError("INVALID_EVIDENCE_SEQUENCE")
    try:
        definitions = tuple(
            Definition(r["entry_id"], r["lemma"], r["pos"], r["definition"], tuple(r.get("source_ids", [])))
            for r in raw["definitions"]
        )
        observations = tuple(
            Observation(
                r["entry_id"],
                r["source"],
                r["record_id"],
                r["family"],
                r["features"],
                r["scope"],
                tuple(r.get("candidate_entry_ids", [])),
            )
            for r in raw.get("observations", [])
        )
        assertions = tuple(Assertion(**r) for r in raw.get("assertions", []))
    except (TypeError, KeyError) as exc:
        raise ValueError("INVALID_EVIDENCE_RECORD") from exc
    return EvidenceBundle(definitions, observations, assertions, tuple(raw.get("unresolved", [])))


def build_dictionary(
    bundle: EvidenceBundle,
    output: str | Path,
    *,
    manifest=None,
    transport=None,
    max_model_calls: int = 0,
    weights=None,
    discover: bool = False,
) -> dict:
    """Propagate every definition, optionally complete bounded residuals, then store.

    The active lexicon is never overwritten through an implicit migration. The
    destination must be a new database or an existing versioned builder database.
    """
    if type(max_model_calls) is not int or max_model_calls < 0:
        raise ValueError("INVALID_MODEL_BUDGET")
    if not isinstance(bundle, EvidenceBundle):
        raise ValueError("INVALID_EVIDENCE_BUNDLE")
    for values, kind in (
        (bundle.definitions, Definition),
        (bundle.observations, Observation),
        (bundle.assertions, Assertion),
    ):
        if not isinstance(values, tuple) or any(not isinstance(value, kind) for value in values):
            raise ValueError("INVALID_EVIDENCE_BUNDLE")
        for value in values:
            value.__post_init__()
    if not isinstance(bundle.unresolved, tuple):
        raise ValueError("INVALID_SOURCE_DIAGNOSTICS")
    for record in bundle.unresolved:
        if not isinstance(record, dict) or not isinstance(record.get("code"), str):
            raise ValueError("INVALID_SOURCE_DIAGNOSTIC")
        _json(record)
    if weights is not None and not isinstance(weights, dict):
        raise ValueError("INVALID_FREQUENCY_WEIGHTS")
    weights = {} if weights is None else weights
    extra_relations, anchors, hierarchy = load_manifest(manifest)
    representation = representation_contract()
    authored_definitions, prime_entries = load_manifest_extensions(manifest)
    relations = projection_relations() + extra_relations
    # Validate even an empty corpus, before creating an output database.
    propagate(BANKS, (), relations)
    definitions = {d.entry_id: d for d in bundle.definitions}
    if len(definitions) != len(bundle.definitions):
        raise ValueError("DUPLICATE_DEFINITION_ID")
    authored_ids = set()
    for definition in authored_definitions:
        if definition.entry_id in authored_ids:
            raise ValueError("DUPLICATE_MANIFEST_DEFINITION")
        authored_ids.add(definition.entry_id)
        if definition.entry_id in definitions and definition != definitions[definition.entry_id]:
            raise ValueError("MANIFEST_DEFINITION_ID_COLLISION")
        definitions[definition.entry_id] = definition
    if set(weights) - definitions.keys():
        raise ValueError("UNKNOWN_WEIGHT_DEFINITION")
    if (set(anchors) | set(hierarchy)) - definitions.keys():
        raise ValueError("UNKNOWN_MANIFEST_DEFINITION")
    from .catalog import catalog_report

    catalog = catalog_report(anchors, tuple(definitions.values()), relations, prime_entries=prime_entries)
    links, observations, record_ids = {}, defaultdict(list), {}
    relevance_by_entry = {}
    for observation in bundle.observations:
        relevance = observation_relevance(observation)
        if observation.entry_id is not None and observation.entry_id not in definitions:
            raise ValueError("UNKNOWN_OBSERVATION_DEFINITION")
        key = (observation.source, observation.record_id)
        if observation.record_id in record_ids and record_ids[observation.record_id] != observation:
            raise ValueError("SOURCE_RECORD_ID_COLLISION")
        record_ids[observation.record_id] = observation
        if key in links and links[key] != observation:
            raise ValueError("AMBIGUOUS_RECORD_LINK")
        links[key] = observation
        targets = (observation.entry_id,) if observation.entry_id is not None else observation.candidate_entry_ids
        for target in targets:
            if target not in definitions:
                raise ValueError("UNKNOWN_CANDIDATE_DEFINITION")
            if transport is not None:
                observations[target].append(observation)
            previous = relevance_by_entry.get(target, frozenset())
            if len(previous) < len(BANKS):
                relevance_by_entry[target] = previous | relevance
    assertions_by_entry = defaultdict(list)
    for assertion in bundle.assertions:
        validate_assertion_competence(assertion)
        observation = links.get((assertion.source, assertion.record_id))
        if observation is None or observation.entry_id is None:
            raise ValueError("ASSERTION_REQUIRES_EXACT_DEFINITION_LINK")
        if observation.family != assertion.family or observation.scope != "lexical":
            raise ValueError("ASSERTION_PROVENANCE_MISMATCH")
        assertions_by_entry[observation.entry_id].append(assertion)

    outcomes, cells, per_pos, completion_codes = Counter(), Counter(), defaultdict(Counter), Counter()
    weighted = Counter()
    calls = 0
    model_completions = []
    logger.info(
        "Building %s definitions from %s native observations; %s unresolved source records",
        len(definitions),
        len(bundle.observations),
        len(bundle.unresolved),
    )
    conn = open_build(output)
    try:
        with conn:
            # A build is a complete snapshot of its requested corpus. Rebuilding
            # a versioned destination must not leave old, unreported definitions.
            for table in (
                "definition_states",
                "builder_assertions",
                "source_observations",
                "unresolved_sources",
                "candidate_evidence",
                "candidate_relations",
                "primitive_values",
                "sentence_primitive_values",
                "lexemes",
            ):
                conn.execute(f"DELETE FROM {table}")
            store_observations(conn, bundle.observations)
            logger.info("Native observations stored; propagating dictionary definitions")
            for entry_id, definition in sorted(definitions.items()):
                context = definition_context(definition.pos)
                assertions = tuple(assertions_by_entry[entry_id]) + anchors.get(entry_id, ())
                evidence_banks = tuple(sorted(relevance_by_entry.get(entry_id, ())))
                resolution = resolve_dictionary(BANKS, assertions, relations, context, evidence_banks=evidence_banks)
                if transport is not None:
                    from .residual import build_request, complete_bank

                    attempted = set()
                    while resolution.code == "PARTIAL" and calls < max_model_calls:
                        remaining = sorted(
                            (len(domain), bank)
                            for bank, domain in resolution.domains.items()
                            if len(domain) > 1 and bank not in attempted
                        )
                        if not remaining:
                            break
                        bank = remaining[0][1]
                        request = build_request(
                            entry_id,
                            bank,
                            resolution,
                            tuple(asdict(o) for o in observations[entry_id]),
                            definition=definition,
                        )
                        completion = complete_bank(
                            request, BANKS, assertions, relations, transport, context, evidence_banks=evidence_banks
                        )
                        calls += 1
                        attempted.add(bank)
                        completion_codes[completion.code] += 1
                        if completion.code == "ASSIGNED":
                            if completion.assertion is None or completion.resolution is None:
                                raise ValueError("INVALID_COMPLETION_RECEIPT")
                            assertions += (completion.assertion,)
                            resolution = completion.resolution
                            model_completions.append(
                                {
                                    "entry_id": entry_id,
                                    "assertion": asdict(completion.assertion),
                                    "request_id": request.request_id,
                                    "code": completion.code,
                                    "request": request.payload(),
                                    "schema": request.output_schema(),
                                }
                            )
                store_entry(conn, definition, resolution, assertions, hierarchy.get(entry_id))
                outcomes[resolution.code] += 1
                per_pos[context["pos"]][resolution.code] += 1
                weight = weights.get(entry_id, 0.0)
                if not isinstance(weight, (int, float)) or isinstance(weight, bool) or not (0 <= weight < float("inf")):
                    raise ValueError("INVALID_FREQUENCY_WEIGHT")
                weighted[resolution.code] += weight
                cells["assigned"] += len(resolution.assignments) if resolution.code != "CONFLICT" else 0
                cells["explicit_zero"] += (
                    sum(v == 0 for v in resolution.assignments.values()) if resolution.code != "CONFLICT" else 0
                )
                cells["unresolved"] += sum(len(d) > 1 for d in resolution.domains.values())
                cells["conflicted"] += sum(not d for d in resolution.domains.values())
            report = {
                "format": "gse.lexicon-build-report/1",
                "definitions": len(definitions),
                "outcomes": dict(outcomes),
                "cells": dict(cells),
                "per_pos": {p: dict(c) for p, c in per_pos.items()},
                "weighted_outcomes": dict(weighted) if weights else None,
                "source_observations": dict(Counter(o.source for o in bundle.observations)),
                "unresolved_source_records": len(bundle.unresolved),
                "model_calls": calls,
                "model_outcomes": dict(completion_codes),
                "coordinates": len(BANKS),
                "approved_relations": sum(r.approved for r in relations),
                "convention_version": CONVENTION_VERSION,
                "explicit_anchor_definitions": len(anchors),
                "foundation_status": "PARTIAL_PROJECTED_BASELINE",
                "foundation_readiness": catalog["readiness"],
                "prime_coverage": catalog["coverage_counts"],
                "gold_validation": "NOT_RUN_NO_GOLD_SUPPLIED",
            }
            conn.execute("INSERT OR REPLACE INTO builder_metadata VALUES ('last_report',?)", (_json(report),))
            conn.execute(
                "INSERT OR REPLACE INTO builder_metadata VALUES ('unresolved_sources',?)",
                (_json(store_unresolved(conn, bundle.unresolved)),),
            )
            conn.execute(
                "INSERT OR REPLACE INTO builder_metadata VALUES ('relations',?)",
                (_json([asdict(r) for r in relations]),),
            )
            for key, value in (
                ("anchors", {entry: [asdict(a) for a in records] for entry, records in anchors.items()}),
                ("model_completions", model_completions),
                ("requested_hierarchy", hierarchy),
                ("catalog", catalog),
                ("prime_entries", prime_entries),
                ("convention_version", CONVENTION_VERSION),
                ("want_polarity", WANT_POLARITY),
                ("representation_contract", representation),
            ):
                conn.execute("INSERT OR REPLACE INTO builder_metadata VALUES (?,?)", (key, _json(value)))
            if discover:
                from .discovery import discover_bundle

                candidates = discover_bundle(bundle, weights or None)
                report["candidate_relations"] = len(candidates)
                conn.execute(
                    "INSERT OR REPLACE INTO builder_metadata VALUES ('candidate_relations',?)",
                    (_json(store_candidates(conn, candidates)),),
                )
            else:
                conn.execute("DELETE FROM builder_metadata WHERE key='candidate_relations'")
            conn.execute("INSERT OR REPLACE INTO builder_metadata VALUES ('last_report',?)", (_json(report),))
        return report
    finally:
        conn.close()


def build_from_sources(output: str | Path, *, parsers: dict | None = None, words=None, **kwargs) -> dict:
    """The CLI and programmatic builds use this same native-source entry point."""
    diagnostics = None
    if parsers is None:
        from .evidence import load_local_sources

        parsers, diagnostics = load_local_sources()
    try:
        bundle = collect_evidence(parsers, tuple(words) if words is not None else None)
        report = build_dictionary(bundle, output, **kwargs)
    finally:
        if diagnostics is not None:
            for parser in parsers.values():
                connection = getattr(parser, "conn", None)
                if connection is not None:
                    connection.close()
    if diagnostics is not None:
        report["local_sources"] = diagnostics
        with closing(open_build(output)) as conn, conn:
            conn.execute("INSERT OR REPLACE INTO builder_metadata VALUES ('last_report',?)", (_json(report),))
    return report
