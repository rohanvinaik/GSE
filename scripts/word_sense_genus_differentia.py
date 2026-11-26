"""Close the whole lexicon under genus plus differentia, as a derived channel beside a release (2026-11-26).

The release is opened read-only. The output is a private copy of it (an APFS clone where the
filesystem allows) with three added tables: ``genus_differentia_closure`` (each definition the
closure narrowed: its derived domains, the cells it settled, its edge and its solver receipts),
``genus_differentia_contradictions`` (each typed contradiction with both causes) and
``genus_differentia_run`` (the run's identity). No release table is written, so the release's
replay is the output's replay; ``verify`` proves every release table row-for-row identical.

    .venv/bin/python scripts/word_sense_genus_differentia.py edges --candidate IN.db --edges EDGES.json.gz
    .venv/bin/python scripts/word_sense_genus_differentia.py close --candidate IN.db --edges EDGES.json.gz \\
        --output OUT.db --report CLOSE.json
    .venv/bin/python scripts/word_sense_genus_differentia.py measure --candidate IN.db --output OUT.db --report MEASURE.json
    .venv/bin/python scripts/word_sense_genus_differentia.py verify --candidate IN.db --output OUT.db --report VERIFY.json

Switching ``data/lexicon_active.json`` is a separate, owner-approved step; this never touches it.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import sqlite3
import sys
import tempfile
import time
from collections import Counter, defaultdict
from contextlib import closing
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from GSE.curation.lexicon_builder import word_sense_genus_differentia as gd  # noqa: E402
from GSE.curation.lexicon_builder.foundation import BANKS  # noqa: E402

TABLES = ("genus_differentia_closure", "genus_differentia_contradictions", "genus_differentia_run")
SCHEMA = """
CREATE TABLE genus_differentia_closure (
    entry_id TEXT PRIMARY KEY, pass INTEGER NOT NULL, domains TEXT NOT NULL,
    settled TEXT NOT NULL, edge TEXT NOT NULL, receipts TEXT NOT NULL
);
CREATE TABLE genus_differentia_contradictions (
    ordinal INTEGER PRIMARY KEY, entry_id TEXT NOT NULL, kind TEXT NOT NULL, bank TEXT, payload TEXT NOT NULL
);
CREATE TABLE genus_differentia_run (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _code_identity() -> dict:
    files = (ROOT / "GSE/curation/lexicon_builder/word_sense_genus_differentia.py", Path(__file__).resolve())
    return {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def _read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve(strict=True).as_uri() + "?mode=ro", uri=True)


def _log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


# ---------------------------------------------------------------------------------------------
# edges
# ---------------------------------------------------------------------------------------------


def _parse(job):
    lemma, pos, gloss = job
    return gd.parse_gloss(lemma, pos, gloss)


def _hypernyms(name):
    return name, gd.wordnet_genus(name)


def edges(candidate: Path, target: Path) -> dict:
    from GSE.curation.external_sources.wordnet_hierarchy import _WARRANTED_ROOT_PRIMITIVES

    if target.exists():
        raise ValueError("GENUS_DIFFERENTIA_EDGES_MUST_BE_NEW")
    _log("hashing the release")
    digest = _sha256(candidate)
    with closing(_read_only(candidate)) as conn:
        rows = conn.execute(
            "SELECT d.entry_id, l.lemma, l.pos, l.gloss FROM definition_states d JOIN lexemes l ON l.id=d.lexeme_id "
            "ORDER BY d.entry_id"
        ).fetchall()
        forms = defaultdict(set)
        for entry_id, form_of, alt_of in conn.execute(
            "SELECT entry_id, json_extract(payload,'$.features.native_sense.form_of'), "
            "json_extract(payload,'$.features.native_sense.alt_of') FROM source_observations "
            "WHERE source='wiktionary' AND scope='lexical' AND (json_extract(payload,'$.features.native_sense.form_of') "
            "IS NOT NULL OR json_extract(payload,'$.features.native_sense.alt_of') IS NOT NULL)"
        ):
            for raw in (form_of, alt_of):
                for item in json.loads(raw) if raw else ():
                    if isinstance(item, dict) and item.get("word"):
                        forms[entry_id].add(item["word"])
        (raw,) = conn.execute("SELECT value FROM builder_metadata WHERE key='prime_entries'").fetchone()
    linked = {
        gd.synset_of(entry) for entries in json.loads(raw).values() for entry in entries if entry.startswith("wordnet:")
    }
    from nltk.corpus import wordnet

    linked_synsets = {name for name in linked if name.split(".")[-2] in ("n", "v")}
    withdrawn = frozenset(name for name in linked_synsets if name not in _WARRANTED_ROOT_PRIMITIVES)
    wordnet.ensure_loaded()
    index = gd.Index.build((entry_id, lemma, pos) for entry_id, lemma, pos, _ in rows)
    jobs = sorted(
        {
            (lemma, pos, gloss or "")
            for entry_id, lemma, pos, gloss in rows
            if pos in gd.CONTENT_POS
            and (entry_id.startswith("wiktionary:") and entry_id not in forms or entry_id.startswith("wordnet:"))
        }
    )
    synsets = sorted({gd.synset_of(entry_id) for entry_id, _, _, _ in rows if entry_id.startswith("wordnet:")})
    synsets = [name for name in synsets if name.split(".")[-2] in ("n", "v")]
    _log(f"parsing {len(jobs)} glosses and {len(synsets)} hypernym sets")
    started = time.time()
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        hypernyms = dict(pool.imap(_hypernyms, synsets, chunksize=500))
        parsed = {}
        for done, (job, result) in enumerate(zip(jobs, pool.imap(_parse, jobs, chunksize=200)), 1):
            parsed[job] = result
            if done % 20000 == 0:
                _log(f"  {done}/{len(jobs)} {time.time() - started:.0f}s")
    skipped = Counter()
    built = []
    for entry_id, lemma, pos, gloss in rows:
        edge, reason = gd.build_edge(
            entry_id,
            lemma,
            pos,
            parsed.get((lemma, pos, gloss or "")),
            index,
            hypernyms=hypernyms.get(gd.synset_of(entry_id), ()) if entry_id.startswith("wordnet:") else (),
            form_of=tuple(sorted(forms.get(entry_id, ()))),
            withdrawn=withdrawn,
        )
        if edge is None:
            skipped[reason.split(":")[0] if reason.startswith("NO_GENUS") else reason] += 1
            if reason.startswith("NO_GENUS"):
                skipped[reason] += 1
        else:
            built.append(edge)
    header = {
        "format": gd.FORMAT + "#edges",
        "candidate": str(candidate),
        "candidate_sha256": digest,
        "code": _code_identity(),
        "definitions": len(rows),
        "edges": len(built),
        "templates": dict(Counter(edge.template for edge in built)),
        "no_edge": dict(sorted(skipped.items())),
        "withdrawn_prime_roots": sorted(withdrawn),
        "seconds": round(time.time() - started),
    }
    temporary = target.with_name(target.name + ".partial")
    with gzip.open(temporary, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps(header, sort_keys=True) + "\n")
        for edge in built:
            stream.write(json.dumps(edge.as_json(), sort_keys=True) + "\n")
    os.link(temporary, target)
    temporary.unlink()
    header["edges_sha256"] = _sha256(target)
    return header


def _load_edges(path: Path) -> tuple[dict, dict[str, gd.Edge]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        header = json.loads(next(stream))
        loaded = {}
        for line in stream:
            edge = gd.Edge.from_json(json.loads(line))
            loaded[edge.entry_id] = edge
    return header, loaded


# ---------------------------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------------------------


def _stored(conn) -> tuple[dict[str, int], dict[str, str], dict[str, str]]:
    stored, pos_of, lemma_of = {}, {}, {}
    for entry_id, lemma, pos, domains in conn.execute(
        "SELECT d.entry_id, l.lemma, l.pos, d.domains FROM definition_states d JOIN lexemes l ON l.id=d.lexeme_id"
    ):
        stored[entry_id] = gd.pack(json.loads(domains))
        pos_of[entry_id], lemma_of[entry_id] = pos, lemma
    return stored, pos_of, lemma_of


def _trace(conn, entry_id) -> list[dict]:
    (raw,) = conn.execute("SELECT trace FROM definition_states WHERE entry_id=?", (entry_id,)).fetchone()
    return json.loads(raw)


def _stated_cause(trace, bank) -> list[dict]:
    """The stored derivation of one bank: the assertions and rules that narrowed it."""
    return [
        {key: row.get(key) for key in ("kind", "source", "record_id", "rule_id", "value", "remaining")}
        for row in trace
        if row.get("bank") == bank
        and row.get("kind") in ("ASSERTION", "RELATION", "DOMAIN_RESTRICTION", "JOINT_SUPPORT")
    ]


def close(candidate: Path, edges_path: Path, output: Path, report_path: Path) -> dict:
    from GSE.curation.lexicon_builder.sqlite_snapshot import copy_database
    from GSE.curation.lexicon_builder.validation import _metadata, _relations
    from GSE.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path

    output = output.absolute()
    if output.exists() or report_path.exists() or output.suffix != ".db":
        raise ValueError("GENUS_DIFFERENTIA_OUTPUT_MUST_BE_NEW_DATABASE")
    if output.resolve() == resolve_lexicon_path().resolve() or output.resolve() == candidate.resolve():
        raise ValueError("GENUS_DIFFERENTIA_REQUIRES_SEPARATE_CANDIDATE")
    pointer = _sha256(ACTIVE_POINTER)
    header, edge_map = _load_edges(edges_path)
    _log("hashing the release")
    digest = _sha256(candidate)
    if digest != header["candidate_sha256"]:
        raise ValueError("GENUS_DIFFERENTIA_EDGES_FROM_ANOTHER_RELEASE")
    started = time.time()
    with closing(_read_only(candidate)) as conn:
        stored, pos_of, lemma_of = _stored(conn)
        rules = _relations(_metadata(conn, "relations"))
        axioms = gd.axiom_entries(conn)
        exceptions_cache: dict[str, tuple[str, ...]] = {}

        def stored_exceptions(entry_id):
            if entry_id not in exceptions_cache:
                exceptions_cache[entry_id] = tuple(
                    rule
                    for row in _trace(conn, entry_id)
                    if row.get("kind") == "CONDITIONAL_EXCEPTION"
                    for rule in row["rule_ids"]
                )
            return exceptions_cache[entry_id]

        _log(f"closing {len(edge_map)} edges, {len(axioms)} axioms")
        closure = gd.close(stored, pos_of, edge_map, axioms, rules, stored_exceptions, progress=lambda p: _log(str(p)))
        for record in closure.contradictions:  # name the stated side's own derivation
            if record["bank"] in BANKS and record["kind"].endswith("STORED_CONFLICT"):
                record["stated"]["derivation"] = _stated_cause(_trace(conn, record["entry_id"]), record["bank"])
        census = gd.open_census(closure, edge_map)
    changed = sorted(closure.changed_in)
    settled_by_bank, settled_values = Counter(), Counter()
    rows = []
    for entry_id in changed:
        before, after = stored[entry_id], closure.state[entry_id]
        settled = {}
        for i, bank in enumerate(BANKS):
            values = gd.bank_values(after, i)
            if len(values) == 1 and len(gd.bank_values(before, i)) > 1:
                settled[bank] = values[0]
                settled_by_bank[bank] += 1
                settled_values["zero" if values[0] == 0 else "nonzero"] += 1
        edge = edge_map.get(entry_id)
        rows.append(
            (
                entry_id,
                closure.changed_in[entry_id],
                json.dumps(gd.unpack(after), sort_keys=True),
                json.dumps(settled, sort_keys=True),
                json.dumps(edge.as_json() if edge else {"template": "axiom"}, sort_keys=True),
                json.dumps(closure.traces[entry_id], sort_keys=True, default=list),
            )
        )
    contradiction_kinds = Counter(record["kind"] for record in closure.contradictions)
    run = {
        "format": gd.FORMAT,
        "channel": gd.CHANNEL,
        "candidate": str(candidate),
        "candidate_sha256": digest,
        "edges_sha256": _sha256(edges_path),
        "code": _code_identity(),
        "passes": closure.passes,
        "definitions_narrowed": len(changed),
        "cells_settled": sum(settled_by_bank.values()),
        "contradictions": dict(contradiction_kinds),
    }
    _log("writing the output beside the release")
    with tempfile.TemporaryDirectory(prefix=".gse-genus-differentia-", dir=output.parent) as directory:
        snapshot = Path(directory) / "snapshot.db"
        copy_database(candidate, snapshot)
        with closing(sqlite3.connect(snapshot)) as out, out:
            existing = {row[0] for row in out.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if existing & set(TABLES):
                raise ValueError("GENUS_DIFFERENTIA_TABLES_ALREADY_PRESENT")
            out.executescript(SCHEMA)
            out.executemany("INSERT INTO genus_differentia_closure VALUES (?,?,?,?,?,?)", rows)
            out.executemany(
                "INSERT INTO genus_differentia_contradictions VALUES (?,?,?,?,?)",
                [
                    (n, r["entry_id"], r["kind"], r["bank"], json.dumps(r, sort_keys=True, default=list))
                    for n, r in enumerate(closure.contradictions)
                ],
            )
            out.executemany(
                "INSERT INTO genus_differentia_run VALUES (?,?)",
                [(key, json.dumps(value, sort_keys=True)) for key, value in sorted(run.items())],
            )
        if _sha256(candidate) != digest or _sha256(ACTIVE_POINTER) != pointer:
            raise ValueError("GENUS_DIFFERENTIA_INPUT_CHANGED")
        os.link(snapshot, output)
    report = {
        **run,
        "output": str(output),
        "output_sha256": _sha256(output),
        "active_pointer_sha256": pointer,
        "activation_performed": False,
        "edges_header": header,
        "settled_by_bank": dict(settled_by_bank.most_common()),
        "settled_values": dict(settled_values),
        "contradiction_examples": {
            kind: [r for r in closure.contradictions if r["kind"] == kind][:5] for kind in sorted(contradiction_kinds)
        },
        "open_census": census,
        "seconds": round(time.time() - started),
    }
    _record(report_path, report)
    return report


def _record(path: Path, value) -> None:
    from GSE.curation.lexicon_builder.epoch import record

    record(path, json.loads(json.dumps(value, default=list)))


# ---------------------------------------------------------------------------------------------
# measure
# ---------------------------------------------------------------------------------------------


def measure(candidate: Path, output: Path, report_path: Path) -> dict:
    """H (sum of log2 |domain|), the exact joint count where the solver's receipts allow, and the
    singletons gained per SUBTLEX spelling-frequency bucket, before and after."""
    from build_word_senses import subtlex_counts

    from GSE.curation.lexicon_builder.specification import BUCKETS, frequency_buckets, measure_space

    with closing(_read_only(output)) as out:
        derived = {
            entry_id: (json.loads(domains), json.loads(receipts))
            for entry_id, domains, receipts in out.execute(
                "SELECT entry_id, domains, receipts FROM genus_differentia_closure"
            )
        }
    totals = {side: Counter() for side in ("before", "after")}
    bits = {side: defaultdict(float) for side in ("before", "after")}
    gains = {name: Counter() for name in BUCKETS}
    with closing(_read_only(candidate)) as conn:
        lemmas = [row[0] for row in conn.execute("SELECT DISTINCT lemma FROM lexemes")]
        buckets = frequency_buckets(lemmas, subtlex_counts())
        for entry_id, lemma, code, domains, trace in conn.execute(
            "SELECT d.entry_id, l.lemma, d.code, d.domains, d.trace FROM definition_states d "
            "JOIN lexemes l ON l.id=d.lexeme_id"
        ):
            before_domains = json.loads(domains)
            before = measure_space(before_domains, json.loads(trace), conflicted=code == "CONFLICT")
            after = before
            if entry_id in derived:
                after_domains, receipts = derived[entry_id]
                after = measure_space(after_domains, receipts)
                bucket = buckets[gd_spelling(lemma)]
                for bank, values in after_domains.items():
                    if len(values) == 1 and len(before_domains[bank]) > 1:
                        gains[bucket]["zero" if values[0] == 0 else "nonzero"] += 1
            for side, state in (("before", before), ("after", after)):
                totals[side]["definitions"] += 1
                totals[side][state["code"]] += 1
                for key in ("filled_banks", "explicit_zero_banks", "unresolved_banks"):
                    totals[side][key] += state[key]
                bits[side]["domain_potential_bits"] += state["domain_potential_bits"] or 0.0
                if state["specification_bits"] is not None:
                    bits[side]["exact_subset_specification_bits"] += state["specification_bits"]
    report = {
        "format": gd.FORMAT + "#measure",
        "candidate": str(candidate),
        "output": str(output),
        "bucket_policy": "specification.frequency_buckets over SUBTLEX counts (build_word_senses.subtlex_counts); "
        "'unranked' is a spelling SUBTLEX does not count (absent)",
        "before": {**dict(totals["before"]), **dict(bits["before"])},
        "after": {**dict(totals["after"]), **dict(bits["after"])},
        "H_reduction_bits": bits["before"]["domain_potential_bits"] - bits["after"]["domain_potential_bits"],
        "singleton_gains_by_bucket": {name: dict(gains[name]) for name in BUCKETS},
        "banks_per_definition": {
            side: totals[side]["filled_banks"] / totals[side]["definitions"] for side in ("before", "after")
        },
    }
    for side in ("before", "after"):
        exact = report[side].get("EXACT", 0)
        report[side]["joint_count_complete"] = exact == report[side]["definitions"]
        report[side]["H_bits_per_definition"] = report[side]["domain_potential_bits"] / report[side]["definitions"]
    report["max_H_bits"] = report["before"]["definitions"] * len(BANKS) * math.log2(3)
    _record(report_path, report)
    return report


def gd_spelling(lemma: str) -> str:
    from GSE.curation.lexicon_builder.specification import normalized_spelling

    return normalized_spelling(lemma)


# ---------------------------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------------------------


def _table_digest(job):
    path, table = job
    digest, count = hashlib.sha256(), 0
    with closing(_read_only(Path(path))) as conn:
        for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid'):
            encoded = repr(row).encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
            count += 1
    return path, table, count, digest.hexdigest()


def verify(candidate: Path, output: Path, report_path: Path) -> dict:
    """Every table of the release is row-for-row identical in the output, and its schema unchanged."""
    with closing(_read_only(candidate)) as conn:
        schema_in = conn.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name").fetchall()
    with closing(_read_only(output)) as conn:
        schema_out = conn.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name").fetchall()
    tables = sorted(name for kind, name, _, _ in schema_in if kind == "table")
    added = sorted({row[1] for row in schema_out} - {row[1] for row in schema_in})
    jobs = [(str(path), table) for table in tables for path in (candidate, output)]
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        results = pool.map(_table_digest, jobs)
    by_table = defaultdict(dict)
    for path, table, count, digest in results:
        by_table[table]["input" if path == str(candidate) else "output"] = {"rows": count, "sha256": digest}
    differing = sorted(table for table, sides in by_table.items() if sides["input"] != sides["output"])
    report = {
        "format": gd.FORMAT + "#verify",
        "candidate": str(candidate),
        "output": str(output),
        "release_schema_unchanged": [row for row in schema_out if row[1] not in added] == schema_in,
        "added_objects": added,
        "tables_compared": len(tables),
        "tables_differing": differing,
        "tables": dict(by_table),
        "code": "RELEASE_TABLES_IDENTICAL" if not differing else "RELEASE_TABLES_CHANGED",
    }
    _record(report_path, report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("edges", "close", "measure", "verify"))
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--edges", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if args.command == "edges":
        result = edges(args.candidate, args.edges)
        print(json.dumps({k: result[k] for k in ("edges", "templates", "no_edge", "edges_sha256")}, sort_keys=True))
    elif args.command == "close":
        result = close(args.candidate, args.edges, args.output, args.report)
        summary = ("passes", "definitions_narrowed", "cells_settled", "contradictions", "output_sha256")
        print(json.dumps({k: result[k] for k in summary}, sort_keys=True))
    elif args.command == "measure":
        result = measure(args.candidate, args.output, args.report)
        keys = ("H_reduction_bits", "singleton_gains_by_bucket", "banks_per_definition")
        print(json.dumps({k: result[k] for k in keys}, sort_keys=True))
    else:
        result = verify(args.candidate, args.output, args.report)
        print(json.dumps({k: result[k] for k in ("code", "tables_compared", "tables_differing", "added_objects")}))
        return 0 if result["code"] == "RELEASE_TABLES_IDENTICAL" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
