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
    .venv/bin/python scripts/word_sense_genus_differentia.py sample --candidate IN.db --output OUT.db --report SAMPLE.json
    .venv/bin/python scripts/word_sense_genus_differentia.py witness --candidate IN.db --output OUT.db --report WITNESS.json

Round 2 (2026-11-26): ``close`` also takes the identity banks (NSM categories), the catalog's own
banks for prime-linked definitions and the anchor table's root axioms, and reports each root and
catalog axiom with its warrant (``root_axiom_table``, ``catalog_axiom_table``).

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
    roots = frozenset(name for name in _WARRANTED_ROOT_PRIMITIVES if name not in index.by_synset)
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
            roots=roots,
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
        "anchor_roots_not_in_release": sorted(roots),
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


def _axiom_inputs(conn, stored: dict, pos_of: dict) -> dict:
    """Round 2's inputs, each from a source table: the identity banks (NSM categories), the catalog's
    own banks for prime-linked definitions, and the anchor table's root axioms. ``stored`` and
    ``pos_of`` gain the anchor roots the release has no definition of."""
    from nltk.corpus import wordnet

    from GSE.curation.external_sources.wordnet_hierarchy import _WARRANTED_ROOT_PRIMITIVES
    from GSE.curation.lexicon_builder.catalog import catalog_inventory

    table = ROOT / gd.CATEGORY_TABLE
    units = catalog_inventory()["units"]
    identity = gd.identity_banks(table.read_text(encoding="utf-8"), units)
    signs = gd.catalog_signs(units)
    (raw,) = conn.execute("SELECT value FROM builder_metadata WHERE key='prime_entries'").fetchone()
    prime_entries = json.loads(raw)
    own_signs, bound = {}, {}
    for unit_id, entries in sorted(prime_entries.items()):
        for entry in entries:
            if entry.startswith("wordnet:"):
                bound[gd.synset_of(entry)] = unit_id
            if unit_id in signs:
                bank, sign, code, note = signs[unit_id]
                own_signs[entry] = (bank, sign, {"unit": unit_id, "catalog": code, "note": note})
    index = gd.Index.build((entry_id, "", pos) for entry_id, pos in pos_of.items())
    roots, table_rows = {}, []
    for name in sorted(_WARRANTED_ROOT_PRIMITIVES):
        banks = tuple(sorted(_WARRANTED_ROOT_PRIMITIVES[name], key=BANKS.index))
        warrant = {
            "anchor": "GSE.curation.external_sources.wordnet_hierarchy._WARRANTED_ROOT_PRIMITIVES",
            "synset": name,
            "gloss": wordnet.synset(name).definition(),
            "prime_binding": bound.get(name),
        }
        entries = index.by_synset.get(name, ())
        if not entries:
            virtual = gd.ROOT_PREFIX + name
            stored[virtual] = gd.pack({bank: [1] for bank in banks})
            pos_of[virtual] = "noun" if ".n." in name else "verb"
        for entry in entries:
            roots[entry] = (banks, warrant)
        table_rows.append({**warrant, "banks": {bank: 1 for bank in banks}, "release_entries": list(entries)})
    unsettled_units = sorted(
        unit_id
        for unit_id, entries in prime_entries.items()
        for entry in entries
        if entry in stored and not gd._settles_nonzero(stored[entry]) and not entry.startswith("gse_closed_class:")
    )
    return {
        "identity": identity,
        "identity_mask": gd.mask(identity),
        "category_table": {"path": gd.CATEGORY_TABLE, "sha256": _sha256(table)},
        "own_signs": own_signs,
        "roots": roots,
        "root_table": table_rows,
        "catalog_table": [
            {
                "unit": unit_id,
                "entry": entry,
                "bank": own_signs[entry][0] if entry in own_signs else None,
                "sign": own_signs[entry][1] if entry in own_signs else None,
                "catalog": own_signs[entry][2]["catalog"] if entry in own_signs else "NO_CATALOG_SIGN",
                "note": own_signs[entry][2]["note"] if entry in own_signs else None,
            }
            for unit_id in unsettled_units
            for entry in prime_entries[unit_id]
        ],
    }


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
        release_entries = set(stored)
        rules = _relations(_metadata(conn, "relations"))
        axioms = gd.axiom_entries(conn)
        inputs = _axiom_inputs(conn, stored, pos_of)
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
        closure = gd.close(
            stored,
            pos_of,
            edge_map,
            axioms,
            rules,
            stored_exceptions,
            progress=lambda p: _log(str(p)),
            identity=inputs["identity_mask"],
            own_signs=inputs["own_signs"],
            roots=inputs["roots"],
        )
        for record in closure.contradictions:  # name the stated side's own derivation
            if record["bank"] in BANKS and record["kind"].endswith("STORED_CONFLICT"):
                record["stated"]["derivation"] = _stated_cause(_trace(conn, record["entry_id"]), record["bank"])
        census = gd.open_census(closure, edge_map, identity=inputs["identity_mask"])
    changed = sorted(entry for entry in closure.changed_in if entry in release_entries)
    for row in inputs["root_table"]:
        row["entries_narrowed"] = sorted(
            e for e in row["release_entries"] if closure.axioms.get(e, {}).get("kind") == "wordnet_root"
        )
        row["cells_settled"] = sum(len(closure.axioms[e]["settled"]) for e in row["entries_narrowed"])
        row["contradictions"] = [
            r
            for r in closure.contradictions
            if r["entry_id"] in row["release_entries"] and r["kind"].startswith("ROOT_AXIOM")
        ]
    for row in inputs["catalog_table"]:
        record = closure.axioms.get(row["entry"], {})
        row["settled"] = record.get("settled", {}) if record.get("kind") == "nsm_catalog" else {}
        row["contradictions"] = [r for r in closure.contradictions if r["entry_id"] == row["entry"]]
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
        record = edge.as_json() if edge else {"template": "axiom"}
        if entry_id in closure.axioms:
            record["axiom"] = closure.axioms[entry_id]
        rows.append(
            (
                entry_id,
                closure.changed_in[entry_id],
                json.dumps(gd.unpack(after), sort_keys=True),
                json.dumps(settled, sort_keys=True),
                json.dumps(record, sort_keys=True),
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
        "identity_banks": inputs["identity"],
        "category_table": inputs["category_table"],
        "axioms": dict(Counter(record["kind"] for record in closure.axioms.values())),
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
        "root_axiom_table": inputs["root_table"],
        "catalog_axiom_table": inputs["catalog_table"],
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
            entry_id: (json.loads(domains), json.loads(receipts), json.loads(edge).get("axiom", {}).get("settled", {}))
            for entry_id, domains, receipts, edge in out.execute(
                "SELECT entry_id, domains, receipts, edge FROM genus_differentia_closure"
            )
        }
    totals = {side: Counter() for side in ("before", "after")}
    bits = {side: defaultdict(float) for side in ("before", "after")}
    gains = {name: Counter() for name in BUCKETS}
    split = {name: Counter() for name in BUCKETS}
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
                after_domains, receipts, axiom_cells = derived[entry_id]
                after = measure_space(after_domains, receipts)
                bucket = buckets[gd_spelling(lemma)]
                for bank, values in after_domains.items():
                    if len(values) == 1 and len(before_domains[bank]) > 1:
                        sign = "zero" if values[0] == 0 else "nonzero"
                        gains[bucket][sign] += 1
                        split[bucket][("axiom_" if bank in axiom_cells else "propagated_") + sign] += 1
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
        "singleton_gains_axiom_vs_propagated": {name: dict(split[name]) for name in BUCKETS},
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


# ---------------------------------------------------------------------------------------------
# sample: newly settled cells with their full chains, for review (reads only; admits nothing)
# ---------------------------------------------------------------------------------------------

SAMPLE_PLAN = (("propagated", 1, 3), ("propagated", 0, 2), ("axiom", None, 1))  # per bucket: (origin, nonzero?, count)


def _chain(entry_id, bank, state, records, glosses, depth=0, seen=None) -> dict:
    """Why ``entry_id`` holds its value on ``bank``: its axiom, or its genus edge and differentia,
    followed down the genus that holds the value until a stored value or an axiom."""
    seen = (seen or set()) | {entry_id}
    i = BANKS.index(bank)
    record = records.get(entry_id)
    step = {"entry": entry_id, "gloss": glosses(entry_id), "values": list(gd.bank_values(state(entry_id), i))}
    if record is None:
        step["from"] = "stored (release)" if not entry_id.startswith(gd.ROOT_PREFIX) else "anchor root (identity only)"
        return step
    edge = record["edge"]
    if bank in edge.get("axiom", {}).get("settled", {}):
        step["from"] = {"axiom": {k: v for k, v in edge["axiom"].items() if k != "settled"}}
        return step
    if bank not in record["settled"]:
        step["from"] = "stored (release)"
        return step

    def union(entries):
        return sorted({v for e in entries for v in gd.bank_values(state(e), i)}) if entries else [-1, 0, 1]

    step["from"] = {
        "template": edge["template"],
        "genus": [
            {"label": label, "entries": len(entries), "values": union(entries)} for label, entries in edge["genus"]
        ],
        "differentia": [
            {"word": word, "entries": len(entries), "values": union(entries)} for word, entries in edge["differentia"]
        ],
    }
    if depth < 12:
        for label, entries in edge["genus"]:
            holder = next(
                (e for e in entries if e not in seen and gd.bank_values(state(e), i) == tuple(step["values"])), None
            )
            if holder is None:
                holder = next(
                    (e for e in entries if e not in seen and set(step["values"]) <= set(gd.bank_values(state(e), i))),
                    None,
                )
            if holder is not None:
                step["genus_chain"] = _chain(holder, bank, state, records, glosses, depth + 1, seen)
                break
    return step


def sample(candidate: Path, output: Path, report_path: Path) -> dict:
    from build_word_senses import subtlex_counts

    from GSE.curation.lexicon_builder.specification import BUCKETS, frequency_buckets

    with closing(_read_only(output)) as out:
        records = {
            entry: {"settled": json.loads(settled), "edge": json.loads(edge), "domains": json.loads(domains)}
            for entry, settled, edge, domains in out.execute(
                "SELECT entry_id, settled, edge, domains FROM genus_differentia_closure"
            )
        }
        meta = {
            row[0]: (row[1], row[2], row[3])
            for row in out.execute(
                "SELECT d.entry_id, l.lemma, l.pos, l.gloss FROM definition_states d JOIN lexemes l ON l.id=d.lexeme_id"
            )
        }
        stored_cache: dict[str, int] = {}
        (raw,) = out.execute("SELECT value FROM genus_differentia_run WHERE key='identity_banks'").fetchone()
        identity = set(json.loads(raw))

        def state(entry):
            if entry in records:
                return gd.pack(records[entry]["domains"])
            if entry.startswith(gd.ROOT_PREFIX):
                return gd.FULL  # shown with its anchor; its identity bank is in the root table
            if entry not in stored_cache:
                row = out.execute("SELECT domains FROM definition_states WHERE entry_id=?", (entry,)).fetchone()
                stored_cache[entry] = gd.pack(json.loads(row[0])) if row else gd.FULL
            return stored_cache[entry]

        def glosses(entry):
            lemma, pos, gloss = meta.get(entry, ("", "", ""))
            return f"{lemma} ({pos}): {gloss}"

        buckets = frequency_buckets(sorted({lemma for lemma, _, _ in meta.values()}), subtlex_counts())
        cells = defaultdict(list)
        for entry, record in records.items():
            axiom = record["edge"].get("axiom", {}).get("settled", {})
            bucket = buckets[gd_spelling(meta[entry][0])]
            for bank, value in record["settled"].items():
                origin = "axiom" if bank in axiom else "propagated"
                key = hashlib.sha256(f"{entry}|{bank}".encode()).hexdigest()
                cells[(bucket, origin, value != 0)].append((key, entry, bank, value))
        picked = []
        for bucket in BUCKETS:
            for origin, nonzero, count in SAMPLE_PLAN:
                pool = sorted(
                    cell
                    for key, cells_ in cells.items()
                    if key[:2] == (bucket, origin) and (nonzero is None or key[2] == bool(nonzero))
                    for cell in cells_
                )
                for _, entry, bank, value in pool[:count]:
                    picked.append(
                        {
                            "bucket": bucket,
                            "origin": origin,
                            "cell": f"{entry} {bank}",
                            "value": value,
                            "identity_bank": bank in identity,
                            "chain": _chain(entry, bank, state, records, glosses),
                        }
                    )
    report = {
        "format": gd.FORMAT + "#sample",
        "selection": "per frequency bucket: 3 propagated nonzero, 2 propagated zero, 1 axiom cell; the first by "
        "sha256(entry|bank) in each group (a review sample; it admits nothing)",
        "cells": picked,
    }
    _record(report_path, report)
    return report


# ---------------------------------------------------------------------------------------------
# witness: the encoder's reading of fixed sentences on the output and on the live lexicon
# ---------------------------------------------------------------------------------------------

WITNESS_SENTENCES = (
    "The happy dog runs to his mother.",
    "She gave the boy a big lock.",
    "I want to know what you see.",
    "The sad man cut the rope.",
    "My friend loves the beautiful house.",
)


def _readings(db_path) -> dict:
    from GSE.api.encoder import GSEEncoder

    found = {}
    with GSEEncoder(db_path=db_path) as encoder:
        for sentence in WITNESS_SENTENCES:
            trace = encoder.encode(sentence)
            found[sentence] = [
                {
                    "token": token.token,
                    "pos": token.pos,
                    "values": {bank: value for bank, value in sorted(token.word_primitives.items()) if value},
                    "zeros": sorted(bank for bank, value in token.word_primitives.items() if not value),
                }
                for token in trace.tokens
                if token.pos != "PUNCT"
            ]
    return found


def witness(output: Path, report_path: Path) -> dict:
    from GSE.lexicon_resource import resolve_lexicon_path

    live = resolve_lexicon_path()
    after, before = _readings(output), _readings(live)
    report = {"format": gd.FORMAT + "#witness", "output": str(output), "live": str(live), "sentences": {}}
    for sentence in WITNESS_SENTENCES:
        rows = []
        for new, old in zip(after[sentence], before[sentence]):
            rows.append(
                {
                    **new,
                    "live_values": old["values"],
                    "zeros_gained": sorted(set(new["zeros"]) - set(old["zeros"])),
                    "changed": new["values"] != old["values"],
                }
            )
        report["sentences"][sentence] = rows
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
    parser.add_argument("command", choices=("edges", "close", "measure", "verify", "sample", "witness"))
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
        keys = ("H_reduction_bits", "singleton_gains_axiom_vs_propagated", "banks_per_definition")
        print(json.dumps({k: result[k] for k in keys}, sort_keys=True))
    elif args.command == "sample":
        result = sample(args.candidate, args.output, args.report)
        print(json.dumps({"cells": len(result["cells"])}))
    elif args.command == "witness":
        result = witness(args.output, args.report)
        for sentence, rows in result["sentences"].items():
            print(sentence, json.dumps({row["token"]: row["values"] for row in rows}))
    else:
        result = verify(args.candidate, args.output, args.report)
        print(json.dumps({k: result[k] for k in ("code", "tables_compared", "tables_differing", "added_objects")}))
        return 0 if result["code"] == "RELEASE_TABLES_IDENTICAL" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
