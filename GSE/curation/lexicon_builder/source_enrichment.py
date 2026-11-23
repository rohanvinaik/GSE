"""Add verified native context to a new candidate without changing any bank.

Old model decisions bind their exact native observations. This boundary refuses
affected active or rule-migration-archived chains: reconsideration is a separate
operation, never an incidental side effect of adding source context.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from collections import defaultdict
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from .evidence import Observation
from .interchange import read_json
from .model_receipts import read_model_receipts
from .storage import _json, store_observations
from .validation import validate_build

FORMAT = "gse.source-enrichment-input/1"


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _file_digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _identifier(value):
    return '"' + value.replace('"', '""') + '"'


def _inventory(conn, added_ids=frozenset()):
    """Fingerprint every schema object and table row, excluding only additions."""
    schema = [tuple(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")]
    tables = {}
    for kind, name, _, _ in schema:
        if kind != "table":
            continue
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info({_identifier(name)})")]
        order = ",".join(_identifier(column) for column in columns)
        count, digest = 0, hashlib.sha256()
        record_index = columns.index("record_id") if name == "source_observations" else None
        for row in conn.execute(f"SELECT * FROM {_identifier(name)} ORDER BY {order}"):
            if record_index is not None and row[record_index] in added_ids:
                continue
            encoded = _json(
                [{"sqlite_blob_hex": value.hex()} if isinstance(value, bytes) else value for value in row]
            ).encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
            count += 1
        tables[name] = {"rows": count, "sha256": digest.hexdigest()}
    return {"schema_sha256": _digest(schema), "tables": tables}


def _definition(conn, entry):
    row = conn.execute(
        "SELECT d.entry_id,l.lemma,l.pos,l.gloss FROM definition_states d "
        "JOIN lexemes l ON l.id=d.lexeme_id WHERE d.entry_id=?",
        (entry,),
    ).fetchone()
    if row is None:
        raise ValueError("ENRICHMENT_DEFINITION_NOT_FOUND")
    return dict(zip(("entry_id", "lemma", "pos", "definition"), row, strict=True))


def _observations(value):
    if type(value) is not dict or set(value) != {"format", "observations"} or value["format"] != FORMAT:
        raise ValueError("INVALID_SOURCE_ENRICHMENT_INPUT")
    if type(value["observations"]) is not list or not value["observations"]:
        raise ValueError("SOURCE_ENRICHMENT_REQUIRES_OBSERVATIONS")
    records = []
    for raw in value["observations"]:
        if (
            type(raw) is not dict
            or set(raw) != {"entry_id", "source", "record_id", "family", "features", "scope", "candidate_entry_ids"}
            or type(raw["candidate_entry_ids"]) is not list
        ):
            raise ValueError("INVALID_SOURCE_ENRICHMENT_OBSERVATION")
        observation = Observation(
            entry_id=raw["entry_id"],
            source=raw["source"],
            record_id=raw["record_id"],
            family=raw["family"],
            features=raw["features"],
            scope=raw["scope"],
            candidate_entry_ids=tuple(raw["candidate_entry_ids"]),
        )
        if observation.entry_id is None or observation.candidate_entry_ids != (observation.entry_id,):
            raise ValueError("ENRICHMENT_REQUIRES_EXACT_DEFINITION")
        if observation.scope != "lexical":
            raise ValueError("ENRICHMENT_REQUIRES_LEXICAL_CONTEXT")
        records.append(observation)
    if len({record.record_id for record in records}) != len(records):
        raise ValueError("DUPLICATE_ENRICHMENT_OBSERVATION")
    return tuple(records)


def _construct(conn, observation):
    """Validate structure and bind it to the candidate's original native root."""
    definition = _definition(conn, observation.entry_id)
    if observation.source == "wiktionary":
        from .evidence import native_reference_observation

        packet = observation.features.get("native_reference")
        expected = native_reference_observation(packet)
        root = packet["source_entry"]
        if any(root[key] != definition[key] for key in definition):
            raise ValueError("ENRICHMENT_NATIVE_ROOT_DEFINITION_MISMATCH")
        matches = [
            json.loads(row[0])
            for row in conn.execute(
                "SELECT payload FROM source_observations WHERE entry_id=? AND source='wiktionary'",
                (observation.entry_id,),
            )
        ]
        if not any(_json(record["features"]) == _json(root) for record in matches):
            raise ValueError("ENRICHMENT_ORIGINAL_NATIVE_ROOT_MISSING")
    elif observation.source == "wordnet_hierarchy":
        from .wordnet_identity import wordnet_identity_observation

        packet = observation.features.get("definition_identity")
        expected = wordnet_identity_observation(packet, definition)
        row = conn.execute(
            "SELECT payload FROM source_observations WHERE record_id=? AND entry_id=? AND source='wordnet_hierarchy'",
            (observation.entry_id, observation.entry_id),
        ).fetchone()
        if row is None:
            raise ValueError("ENRICHMENT_ORIGINAL_NATIVE_ROOT_MISSING")
        native = json.loads(row[0])["features"]
        if any(native.get(key) != definition[key] for key in ("lemma", "pos", "definition")):
            raise ValueError("ENRICHMENT_NATIVE_ROOT_DEFINITION_MISMATCH")
        if native.get("synset_name") != packet["native_synset"]["name"]:
            raise ValueError("ENRICHMENT_NATIVE_ROOT_SYNSET_MISMATCH")
        if any(native.get(key) != packet["native_synset"][key] for key in ("lemma_names", "lexname")):
            raise ValueError("ENRICHMENT_NATIVE_ROOT_WITNESS_MISMATCH")
        if "defining_ancestry" in packet:
            paths = native.get("hypernym_paths")
            if (
                type(paths) is not list
                or any(type(path) is not list or any(type(name) is not str for name in path) for path in paths)
                or sorted(map(_json, paths)) != sorted(map(_json, packet["defining_ancestry"]["paths"]))
            ):
                raise ValueError("ENRICHMENT_NATIVE_ROOT_ANCESTRY_MISMATCH")
    else:
        raise ValueError("UNSUPPORTED_SOURCE_ENRICHMENT")
    if _json(asdict(expected)) != _json(asdict(observation)):
        raise ValueError("ENRICHMENT_OBSERVATION_CONSTRUCTOR_MISMATCH")
    return definition


def _verify_wiktionary(observations, source):
    if not observations:
        return
    if source is None:
        raise ValueError("ENRICHMENT_WIKTIONARY_SOURCE_REQUIRED")
    from GSE.curation.external_sources.wiktionary import WiktionaryParser

    from .evidence import native_reference_observation

    parser = WiktionaryParser(data_path=Path(source))
    if not parser.load():
        raise ValueError("ENRICHMENT_WIKTIONARY_SOURCE_UNAVAILABLE")
    roots = {_json(record.features["native_reference"]["source_entry"]) for record in observations}
    words = tuple(sorted({record.features["native_reference"]["source_entry"]["word"] for record in observations}))
    entries = tuple(entry for entry in parser.get_definition_entries(words) if _json(asdict(entry)) in roots)
    if {_json(asdict(entry)) for entry in entries} != roots:
        raise ValueError("ENRICHMENT_WIKTIONARY_SOURCE_ROOT_MISMATCH")
    verified = {
        _json(asdict(native_reference_observation(dict(packet))))
        for packet in parser.get_definition_references(entries)
    }
    if any(_json(asdict(record)) not in verified for record in observations):
        raise ValueError("ENRICHMENT_WIKTIONARY_SOURCE_REFERENCE_MISMATCH")


def _verify_wordnet(observations, definitions):
    if not observations:
        return
    from nltk.corpus import wordnet

    from GSE.curation.external_sources.wordnet_hierarchy import WordNetHierarchyParser

    from .wordnet_identity import (
        DEFINING_CONTEXT_FORMAT,
        wordnet_defining_context,
        wordnet_identity_evidence,
        wordnet_identity_observation,
    )

    # Refuse unavailable local data before the legacy parser can download it.
    try:
        wordnet.ensure_loaded()
    except LookupError as error:
        raise ValueError("ENRICHMENT_LOCAL_WORDNET_UNAVAILABLE") from error
    parser = WordNetHierarchyParser()
    if not parser.load():
        raise ValueError("ENRICHMENT_LOCAL_WORDNET_UNAVAILABLE")
    for record in observations:
        definition = definitions[record.entry_id]
        packet = record.features["definition_identity"]
        synset = wordnet.synset(packet["native_synset"]["name"])
        constructor = wordnet_defining_context if packet["format"] == DEFINING_CONTEXT_FORMAT else wordnet_identity_evidence
        fresh = constructor(parser, definition["lemma"], synset, pos=definition["pos"])
        if _json(asdict(wordnet_identity_observation(fresh, definition))) != _json(asdict(record)):
            raise ValueError("ENRICHMENT_WORDNET_SOURCE_IDENTITY_MISMATCH")


def _refuse_bound_receipts(conn, entries):
    if set(read_model_receipts(conn)) & entries:
        raise ValueError("ENRICHMENT_REQUIRES_MODEL_RECONSIDERATION")
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='rule_migrations'").fetchone():
        for (payload,) in conn.execute("SELECT payload FROM rule_migrations"):
            event = json.loads(payload)
            if any(record["definition"]["entry_id"] in entries for record in event["archived"]):
                raise ValueError("ENRICHMENT_RULE_ARCHIVE_CONTEXT_BOUND")


def enrich_sources(source, output, input_path, *, wiktionary_source=None):
    """Create a separate replayed successor containing only new native context."""
    from GSE.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path

    source = Path(source).expanduser().resolve()
    requested = Path(output).expanduser().absolute()
    if requested.is_symlink() or requested.exists():
        raise ValueError("ENRICHMENT_OUTPUT_MUST_BE_NEW")
    output = requested.resolve()
    if not source.is_file():
        raise ValueError("BUILD_NOT_FOUND")
    if output.suffix != ".db":
        raise ValueError("ENRICHMENT_OUTPUT_REQUIRES_DATABASE_PATH")
    active = resolve_lexicon_path().resolve()
    if source == active or active.exists() and source.samefile(active) or output == active:
        raise ValueError("ENRICHMENT_CANDIDATE_MUST_NOT_BE_ACTIVE")
    if output == source or output == Path(input_path).resolve():
        raise ValueError("ENRICHMENT_PATH_COLLISION")
    pointer = ACTIVE_POINTER.read_bytes() if ACTIVE_POINTER.exists() else None
    raw = read_json(input_path)
    records = _observations(raw)
    source_hash = _file_digest(source)
    fd, name = tempfile.mkstemp(prefix=".gse-enrichment-", suffix=".db", dir=output.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
            revision = original.execute("PRAGMA data_version").fetchone()[0]
            original.execute("BEGIN")
            with closing(sqlite3.connect(temporary)) as conn:
                original.backup(conn)
            snapshot_hash = _file_digest(temporary)
            preflight = validate_build(temporary)
            if preflight["code"] != "REPLAY_VALIDATED" or not preflight["complete_search"]:
                raise ValueError("ENRICHMENT_REQUIRES_COMPLETE_REPLAY")
            with closing(sqlite3.connect(temporary)) as conn:
                definitions = {record.entry_id: _construct(conn, record) for record in records}
                _refuse_bound_receipts(conn, set(definitions))
                for record in records:
                    if conn.execute(
                        "SELECT 1 FROM source_observations WHERE record_id=?", (record.record_id,)
                    ).fetchone():
                        raise ValueError("ENRICHMENT_OBSERVATION_ALREADY_PRESENT")
                _verify_wiktionary(tuple(r for r in records if r.source == "wiktionary"), wiktionary_source)
                _verify_wordnet(tuple(r for r in records if r.source == "wordnet_hierarchy"), definitions)
                before = _inventory(conn)
                with conn:
                    store_observations(conn, records)
                after = _inventory(conn, frozenset(record.record_id for record in records))
                if before != after:
                    raise ValueError("ENRICHMENT_CHANGED_EXISTING_STATE")
            postflight = validate_build(temporary)
            if postflight["code"] != "REPLAY_VALIDATED" or not postflight["complete_search"]:
                raise ValueError("ENRICHMENT_POST_REPLAY_FAILED:" + _json(postflight.get("mismatch_counts")))
            original.rollback()
            if original.execute("PRAGMA data_version").fetchone()[0] != revision or _file_digest(source) != source_hash:
                raise ValueError("ENRICHMENT_SOURCE_CHANGED")
            if pointer != (ACTIVE_POINTER.read_bytes() if ACTIVE_POINTER.exists() else None):
                raise ValueError("ENRICHMENT_ACTIVE_POINTER_CHANGED")
            report = {
                "format": "gse.source-enrichment/1",
                "code": "ENRICHED_CANDIDATE",
                "source": str(source),
                "candidate": str(output),
                "source_file_sha256": source_hash,
                "source_snapshot_sha256": snapshot_hash,
                "candidate_sha256": _file_digest(temporary),
                "input_sha256": _digest(raw),
                "added_observations": [asdict(record) for record in records],
                "added_records": len(records),
                "affected_entries": sorted(definitions),
                "preexisting_state": before,
                "preexisting_state_unchanged": True,
                "preflight": preflight,
                "postflight": postflight,
                "model_calls": 0,
                "bank_changes": 0,
                "activation_performed": False,
                "active_pointer_unchanged": True,
            }
            # Same-filesystem exclusive install: no existing path can be replaced.
            os.link(temporary, output)
            return report
    finally:
        temporary.unlink(missing_ok=True)


def _refresh_unweighted_discovery(conn):
    """Rebuild native diagnostics after a source assertion changes."""
    from .completion import _set_metadata
    from .discovery import BankObservation, discover_relations
    from .storage import store_candidates
    from .validation import _metadata

    if conn.execute("SELECT 1 FROM candidate_evidence WHERE json_extract(payload,'$.weight') != 1 LIMIT 1").fetchone():
        raise ValueError("SOURCE_REVISION_REQUIRES_ORIGINAL_DISCOVERY_WEIGHTS")
    observations = tuple(
        BankObservation(entry, bank, value, source, record_id, family, scope=scope)
        for entry, bank, value, source, record_id, family, scope in conn.execute(
            """SELECT a.entry_id, json_extract(a.payload,'$.bank'),
                      json_extract(a.payload,'$.value'), o.source, o.record_id, o.family, o.scope
               FROM builder_assertions a JOIN source_observations o
                 ON o.record_id=json_extract(a.payload,'$.record_id')
                AND o.source=json_extract(a.payload,'$.source')
                AND o.entry_id=a.entry_id
               WHERE o.scope='lexical' AND o.family NOT IN ('model','derived')
                 AND o.source NOT LIKE 'model:%' AND o.source NOT LIKE 'rule:%' AND o.source NOT LIKE 'derived:%'"""
        )
    )
    candidates = discover_relations(observations, cross_source=True)
    conn.execute("DELETE FROM candidate_evidence")
    conn.execute("DELETE FROM candidate_relations")
    summary = store_candidates(conn, candidates)
    _set_metadata(conn, "candidate_relations", summary)
    report = _metadata(conn, "last_report")
    report["candidate_relations"] = summary["records"]
    _set_metadata(conn, "last_report", report)
    return summary


def revise_source_candidate(candidate, output, baseline, apply_revision, *, format_tag, metadata_key):
    """Replay a reviewed source transition on a private copy of a pinned baseline."""
    from GSE.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path

    from .completion import _refresh_coverage, _set_metadata
    from .sqlite_snapshot import copy_database

    candidate = Path(candidate).resolve(strict=True)
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or output.suffix != ".db":
        raise ValueError("SOURCE_REVISION_OUTPUT_MUST_BE_NEW_DATABASE")
    output = output.resolve()
    active = resolve_lexicon_path().resolve()
    if output == active or output == candidate:
        raise ValueError("SOURCE_REVISION_REQUIRES_SEPARATE_CANDIDATE")
    replay = baseline["replay"]
    source_hash = _file_digest(candidate)
    pointer_hash = _file_digest(ACTIVE_POINTER)
    if (
        source_hash != baseline["candidate_sha256"]
        or pointer_hash != baseline["active_pointer_sha256"]
        or replay["code"] != "REPLAY_VALIDATED"
        or not replay["complete_search"]
        or replay["entries_mismatched"]
        or replay["entries_validated"] != replay["entries_checked"]
    ):
        raise ValueError("SOURCE_REVISION_REQUIRES_PINNED_REPLAY")
    with tempfile.TemporaryDirectory(prefix=".gse-source-revision-", dir=output.parent) as directory:
        snapshot = Path(directory) / "snapshot.db"
        copy_database(candidate, snapshot)
        with closing(sqlite3.connect(snapshot.as_uri() + "?mode=rw", uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                changes = apply_revision(conn)
                discovery = _refresh_unweighted_discovery(conn)
                coverage = _refresh_coverage(conn)
                _set_metadata(
                    conn,
                    metadata_key,
                    {"format": format_tag, "baseline_sha256": source_hash, "changes": changes},
                )
        replayed = validate_build(snapshot)
        if (
            replayed["code"] != "REPLAY_VALIDATED"
            or not replayed["complete_search"]
            or replayed["entries_checked"] != replay["entries_checked"]
            or replayed["entries_mismatched"]
        ):
            raise ValueError("SOURCE_REVISION_REPLAY_FAILED:" + _json(replayed["mismatch_counts"]))
        if _file_digest(candidate) != source_hash or _file_digest(ACTIVE_POINTER) != pointer_hash:
            raise ValueError("SOURCE_REVISION_INPUT_CHANGED")
        candidate_hash = _file_digest(snapshot)
        os.link(snapshot, output)
    return {
        "format": format_tag,
        "code": "SOURCE_PROJECTION_REVISED_AND_REPLAYED",
        "candidate": str(output),
        "candidate_sha256": candidate_hash,
        "baseline_sha256": source_hash,
        "active_pointer_sha256": pointer_hash,
        "activation_performed": False,
        "changes": changes,
        "discovery": discovery,
        "coverage": coverage["cells"],
        "replay": replayed,
    }


def wiktionary_projection_scope(conn, bank, *, pending_only=False):
    """Collect the exact native noun records for a supported source projection."""
    from .evidence import Definition, wiktionary_definition_projection

    scope = defaultdict(list)
    for identity, lemma, gloss, raw in conn.execute(
        """SELECT d.entry_id, l.lemma, l.gloss, o.payload
           FROM definition_states d JOIN lexemes l ON l.id=d.lexeme_id
           JOIN source_observations o ON o.entry_id=d.entry_id
           WHERE l.pos='noun' AND o.source='wiktionary' AND o.family='wiktionary' AND o.scope='lexical'
             AND json_array_length(o.payload,'$.features.native_sense.glosses')=1
             AND (? != 'BODY' OR EXISTS (
                 SELECT 1 FROM json_each(o.payload,'$.features.native_sense.topics') WHERE value='anatomy'
             ))
             AND (NOT ? OR NOT EXISTS (
                 SELECT 1 FROM builder_assertions a WHERE a.entry_id=d.entry_id
                   AND json_extract(a.payload,'$.source')='wiktionary'
                   AND json_extract(a.payload,'$.bank')=?
                   AND json_extract(a.payload,'$.record_id')=o.record_id
             ))
           ORDER BY d.entry_id,o.record_id""",
        (bank, pending_only, bank),
    ):
        source = json.loads(raw)
        definition = Definition(identity, lemma, "noun", gloss, (source["record_id"],))
        if wiktionary_definition_projection(definition, source["features"]).get(bank) == 1:
            scope[identity].append(source)
    return scope


def forecast_wiktionary_projection(conn, scope, bank, *, apply=False):
    """Reclose the exact scope with native evidence and reject an unsafe transition."""
    from .completion import _contexts, _entry, _prepare_context_index
    from .engine import Assertion
    from .foundation import BANKS, lexical_context
    from .resolution import resolve_dictionary
    from .rule_history import digest
    from .storage import store_entry
    from .validation import _metadata, _relations

    _refuse_bound_receipts(conn, set(scope))
    for table in ("model_rule_versions", "model_reconsideration_archive"):
        if conn.execute(
            f"SELECT 1 FROM {table} WHERE entry_id IN (SELECT value FROM json_each(?)) LIMIT 1",
            (json.dumps(list(scope)),),
        ).fetchone():
            raise ValueError("WIKTIONARY_HISTORICAL_MODEL_CONTEXT_BOUND")
    _prepare_context_index(conn)
    observations, relevance = _contexts(conn, tuple(scope), indexed=True)
    relations = _relations(_metadata(conn, "relations"))
    changes = []
    for entry_id, sources in scope.items():
        definition, assertions, restrictions, hierarchy = _entry(conn, entry_id)
        [raw] = conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (entry_id,)).fetchone()
        old = json.loads(raw)
        additions = tuple(Assertion(bank, 1, "wiktionary", source["record_id"], "wiktionary") for source in sources)
        if any(a in assertions for a in additions) or 1 not in old[bank]:
            raise ValueError("WIKTIONARY_PROJECTION_REQUIRES_REVIEW:" + entry_id)
        state = resolve_dictionary(
            BANKS,
            assertions + additions,
            relations,
            lexical_context(definition, observations[entry_id], relations),
            evidence_banks=tuple(sorted(relevance[entry_id])),
            domain_restrictions=restrictions,
        )
        new = {name: sorted(values) for name, values in state.domains.items()}
        if (
            state.code == "CONFLICT"
            or any(row["kind"] in {"SOLVER_LIMIT", "CONDITIONAL_EXCEPTION"} for row in state.trace)
            or new[bank] != [1]
            or any(not set(new[name]).issubset(old[name]) for name in BANKS)
        ):
            raise ValueError("WIKTIONARY_CLOSURE_REQUIRES_REVIEW:" + entry_id)
        changes.append(
            {
                "entry_id": entry_id,
                "source_sha256": [digest(source) for source in sources],
                "assertions": [asdict(assertion) for assertion in additions],
                "domains": [
                    {"bank": name, "before": old[name], "after": new[name]} for name in BANKS if old[name] != new[name]
                ],
            }
        )
        if apply:
            store_entry(conn, definition, state, assertions + additions, hierarchy, domain_restrictions=restrictions)
    return changes
