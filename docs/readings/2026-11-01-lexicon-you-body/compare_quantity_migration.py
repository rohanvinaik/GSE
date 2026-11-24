#!/usr/bin/env python3
"""Read-only, factual isolation comparison; this does not admit a semantic rule.

Run only after the separately authorized migration. Unknown domains are never
converted to zero. The sole output is a new, atomically installed JSON report.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import sqlite3
import sys
import tempfile
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

from GSE.namespace import current_id, identity_form

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from GSE.curation.lexicon_builder.foundation import BANKS, _exact_wordnet_ancestry  # noqa: E402

INVENTORY = ROOT / "docs/readings/2026-11-01-lexicon-next-stage/quantity-unit-population-inventory.json"
INVENTORY_SHA256 = "5a392a773cef5cebd2e9d05df34258bf17c35307cddd82d46be9dbb8134ced79"
ACTIVE_POINTER = ROOT / "data/lexicon_active.json"
ANCESTOR = "linear_unit.n.01"


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(identity_form(value)).encode()).hexdigest()


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY:" + key)
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("NONFINITE_JSON_CONSTANT:" + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant)


def observe(path):
    """File observation only: a main DB hash is not a logical SQLite hash."""
    if not path.exists():
        return {"path": str(path), "exists": False}
    first = path.stat()
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            hasher.update(chunk)
    last = path.stat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    return {
        "path": str(path),
        "exists": True,
        "sha256": hasher.hexdigest(),
        "stat": {key: getattr(last, key) for key in fields},
        "stable_during_hash": all(getattr(first, key) == getattr(last, key) for key in fields),
    }


class Findings:
    def __init__(self):
        self.counts = Counter()
        self.details = []

    def add(self, code, **detail):
        self.counts[code] += 1
        if len(self.details) < 1000:
            self.details.append({"code": code, **detail})

    def report(self):
        return {
            "counts": dict(self.counts),
            "details": self.details,
            "omitted_details": sum(self.counts.values()) - len(self.details),
        }


def native_member(definition, source):
    if ANCESTOR not in _exact_wordnet_ancestry(definition, source):
        return False, False
    names = source["features"].get("lemma_names")
    eligible = (
        isinstance(names, (list, tuple))
        and bool(names)
        and all(isinstance(name, str) and name.strip() for name in names)
        and definition["lemma"].casefold().replace("_", " ") in {name.casefold().replace("_", " ") for name in names}
    )
    return True, bool(eligible)


def inventory_scope(findings):
    observation = observe(INVENTORY)
    if observation.get("sha256") != INVENTORY_SHA256:
        raise ValueError("INVENTORY_SHA256_MISMATCH")
    raw = INVENTORY.read_bytes()
    if hashlib.sha256(raw).hexdigest() != INVENTORY_SHA256:
        raise ValueError("INVENTORY_READ_SHA256_MISMATCH")
    data = strict_json(raw)
    if current_id(data.get("format")) != "GSE.quantity-native-population-inventory/1":
        raise ValueError("INVENTORY_FORMAT_MISMATCH")
    population, eligible, synsets = {}, set(), set()
    for sense in data["senses"]:
        for entry in sense["entries"]:
            member, admitted_spelling = native_member(entry["definition"], entry["source_record"])
            if not member:
                continue
            key = entry["entry_id"]
            if key in population:
                findings.add("INVENTORY_DUPLICATE_ENTRY", entry_id=key)
            population[key] = entry
            synsets.add(entry["source_synset"])
            if digest(entry["source_record"]) != entry["source_record_sha256"]:
                findings.add("INVENTORY_SOURCE_HASH_MISMATCH", entry_id=key)
            if admitted_spelling:
                eligible.add(key)
    expected = data["linear_population_counts"]
    if len(population) != expected["entries"] or len(synsets) != expected["distinct_synsets"]:
        findings.add("INVENTORY_POPULATION_COUNT_MISMATCH")
    return observation, population, eligible


def snapshot(path):
    # Immutable snapshots prevent SQLite from creating/writing a WAL/SHM sidecar.
    # main() refuses a nonempty WAL; start/end hashes detect file replacement.
    connection = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA temp_store=MEMORY")
    connection.execute("BEGIN")
    connection.execute("SELECT count(*) FROM definition_states").fetchone()
    return connection


def inspect_sources(connection, side, population, eligible, findings):
    seen, native_spellings = set(), set()
    rows = connection.execute("""
        SELECT d.entry_id,l.lemma,l.pos,l.gloss,s.payload,
               s.record_id,s.source,s.family,s.scope
        FROM source_observations s JOIN definition_states d ON s.entry_id=d.entry_id
        JOIN lexemes l ON l.id=d.lexeme_id
        WHERE s.source='wordnet_hierarchy' AND s.scope='lexical'
    """)
    for row in rows:
        definition = {"entry_id": row["entry_id"], "lemma": row["lemma"], "pos": row["pos"], "definition": row["gloss"]}
        source = strict_json(row["payload"])
        if not isinstance(source, dict):
            raise ValueError("SOURCE_PAYLOAD_NOT_OBJECT")
        if any(row[field] != source.get(field) for field in ("entry_id", "record_id", "source", "family", "scope")):
            findings.add("SOURCE_ENVELOPE_MISMATCH", side=side, entry_id=row["entry_id"])
        member, native_spelling = native_member(definition, source)
        if not member:
            continue
        key = row["entry_id"]
        seen.add(key)
        if native_spelling:
            native_spellings.add(key)
        if key in population:
            retained = population[key]
            if definition != retained["definition"]:
                findings.add("RETAINED_DEFINITION_MISMATCH", side=side, entry_id=key)
            if digest(source) != retained["source_record_sha256"]:
                findings.add("RETAINED_SOURCE_MISMATCH", side=side, entry_id=key)
    for code, actual, expected in (
        ("NATIVE_POPULATION_MISMATCH", seen, set(population)),
        ("NATIVE_SPELLING_POPULATION_MISMATCH", native_spellings, eligible),
    ):
        if actual != expected:
            findings.add(code, side=side, missing=sorted(expected - actual), extra=sorted(actual - expected))


def state_rows(connection, side, findings):
    primitives = iter(
        itertools.groupby(
            connection.execute("""
        SELECT d.entry_id,p.primitive,p.value FROM primitive_values p
        LEFT JOIN definition_states d ON d.lexeme_id=p.lexeme_id
        ORDER BY d.entry_id,p.primitive
    """),
            key=lambda row: row["entry_id"],
        )
    )
    current = next(primitives, None)
    if current is not None and current[0] is None:
        findings.add("ORPHAN_PRIMITIVE_ROWS", side=side, count=sum(1 for _ in current[1]))
        current = next(primitives, None)
    rows = connection.execute("""
        SELECT d.entry_id,d.lexeme_id,d.code,d.domains,l.lemma,l.pos,l.sense_id,l.gloss,l.source
        FROM definition_states d LEFT JOIN lexemes l ON l.id=d.lexeme_id ORDER BY d.entry_id
    """)
    for row in rows:
        key = row["entry_id"]
        values = {}
        if current is not None and current[0] == key:
            for value in current[1]:
                bank = value["primitive"]
                if bank in values:
                    findings.add("DUPLICATE_PRIMITIVE", side=side, entry_id=key, bank=bank)
                values[bank] = value["value"]
            current = next(primitives, None)
        domains = strict_json(row["domains"])
        valid = isinstance(domains, dict) and set(domains) == set(BANKS)
        if valid:
            valid = all(
                isinstance(domain, list)
                and bool(domain)
                and all(type(sign) is int and sign in {-1, 0, 1} for sign in domain)
                and domain == sorted(set(domain))
                for domain in domains.values()
            )
        if not valid:
            findings.add("MALFORMED_DOMAINS", side=side, entry_id=key)
        else:
            known = {bank: domain[0] for bank, domain in domains.items() if len(domain) == 1}
            if values != known:
                findings.add("PRIMITIVE_DOMAIN_MISMATCH", side=side, entry_id=key, expected=known, actual=values)
            expected_code = "RESOLVED" if len(known) == len(BANKS) else "PARTIAL"
            if row["code"] != expected_code:
                findings.add(
                    "RESOLUTION_CODE_MISMATCH", side=side, entry_id=key, expected=expected_code, actual=row["code"]
                )
        identity = {
            name: row[name] for name in ("entry_id", "lexeme_id", "lemma", "pos", "sense_id", "gloss", "source")
        }
        if row["sense_id"] != key:
            findings.add("DEFINITION_IDENTITY_MAPPING_INVALID", side=side, entry_id=key)
        yield key, identity, domains, values, valid
    if current is not None:
        findings.add("UNCONSUMED_PRIMITIVE_ENTRY", side=side, entry_id=current[0])
    orphan_count = connection.execute("""SELECT count(*) FROM lexemes l
        LEFT JOIN definition_states d ON d.lexeme_id=l.id WHERE d.entry_id IS NULL""").fetchone()[0]
    if orphan_count:
        findings.add("LEXEMES_WITHOUT_DEFINITION_STATE", side=side, count=orphan_count)


def compare_states(before, after, eligible, findings):
    left, right = iter(state_rows(before, "before", findings)), iter(state_rows(after, "after", findings))
    a, b = next(left, None), next(right, None)
    counts, changes, changed_ids, expected_ids, targeted_after = Counter(), [], set(), set(), set()
    while a is not None or b is not None:
        if b is None or (a is not None and a[0] < b[0]):
            findings.add("DEFINITION_REMOVED", entry_id=a[0])
            counts["before_entries"] += 1
            a = next(left, None)
            continue
        if a is None or b[0] < a[0]:
            findings.add("DEFINITION_ADDED", entry_id=b[0])
            counts["after_entries"] += 1
            b = next(right, None)
            continue
        key = a[0]
        counts.update({"before_entries": 1, "after_entries": 1, "entries_compared": 1})
        if a[1] != b[1]:
            findings.add("DEFINITION_IDENTITY_CHANGED", entry_id=key, before=a[1], after=b[1])
        if a[4] and b[4]:
            if key in eligible:
                targeted_after.add(key)
                if b[2]["QUANTITY"] != [1]:
                    findings.add("TARGET_QUANTITY_UNRESOLVED", entry_id=key, domain=b[2]["QUANTITY"])
                if len(a[2]["QUANTITY"]) > 1:
                    expected_ids.add(key)
            for bank in BANKS:
                old, new = a[2][bank], b[2][bank]
                counts["bank_cells_compared"] += 1
                if old == new:
                    continue
                change = {"entry_id": key, "bank": bank, "before": old, "after": new}
                counts["changed_cells"] += 1
                if len(changes) < 1000:
                    changes.append(change)
                allowed = key in eligible and bank == "QUANTITY" and len(old) > 1 and 1 in old and new == [1]
                if len(old) == 1:
                    findings.add("KNOWN_VALUE_OVERWRITTEN", **change)
                if not allowed:
                    findings.add("UNAUTHORIZED_CELL_CHANGE", **change)
                else:
                    changed_ids.add(key)
            for bank in set(a[3]) | set(b[3]):
                if a[3].get(bank) == b[3].get(bank) and (bank in a[3]) == (bank in b[3]):
                    continue
                if not (
                    key in eligible
                    and bank == "QUANTITY"
                    and bank not in a[3]
                    and b[3].get(bank) == 1
                    and len(a[2][bank]) > 1
                    and 1 in a[2][bank]
                ):
                    findings.add(
                        "UNAUTHORIZED_PRIMITIVE_CHANGE",
                        entry_id=key,
                        bank=bank,
                        before=a[3].get(bank),
                        after=b[3].get(bank),
                    )
        a, b = next(left, None), next(right, None)
    if targeted_after != eligible:
        findings.add("TARGET_DEFINITIONS_NOT_COMPARED", missing=sorted(eligible - targeted_after))
    if changed_ids != expected_ids:
        findings.add(
            "EXPECTED_CHANGED_IDS_MISMATCH",
            missing=sorted(expected_ids - changed_ids),
            extra=sorted(changed_ids - expected_ids),
        )
    return {
        "counts": dict(counts),
        "changes": changes,
        "omitted_change_details": counts["changed_cells"] - len(changes),
        "changed_entry_ids": sorted(changed_ids),
        "expected_changed_entry_ids": sorted(expected_ids),
    }


def new_report(path, report):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".quantity-comparison-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # Atomic no-clobber publication; never follow a destination symlink.
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--expected-before-sha256")
    args = parser.parse_args()
    before, after = args.before.resolve(strict=True), args.after.resolve(strict=True)
    report_path = args.report.absolute()
    protected = (before, after, INVENTORY, ACTIVE_POINTER)
    if report_path.suffix != ".json" or os.path.lexists(report_path):
        parser.error("--report must be a NEW .json file (including no existing symlink)")
    if not report_path.parent.is_dir() or report_path.resolve() in {path.resolve() for path in protected}:
        parser.error("--report must have an existing parent and cannot alias an input")
    if before.samefile(after):
        parser.error("--before and --after must be distinct snapshots")
    if args.expected_before_sha256 and (
        len(args.expected_before_sha256) != 64
        or any(char not in "0123456789abcdef" for char in args.expected_before_sha256)
    ):
        parser.error("--expected-before-sha256 must be 64 lowercase hexadecimal characters")
    findings = Findings()
    paths = {
        "before": before,
        "after": after,
        "before_wal": Path(str(before) + "-wal"),
        "after_wal": Path(str(after) + "-wal"),
        "active_pointer": ACTIVE_POINTER,
    }
    start = {name: observe(path) for name, path in paths.items()}
    report = {
        "format": "GSE.quantity-migration-isolation/1",
        "authority": "FACTUAL_ISOLATION_NOT_SEMANTIC_ADMISSION",
        "database_writes": 0,
        "model_calls": 0,
        "activation_performed": False,
        "hash_scope": "Filesystem observations of immutable, WAL-free snapshots; nonempty WAL refused; start/end hashes detect input changes.",
        "expected_before_sha256": args.expected_before_sha256,
        "start_observations": start,
    }
    report["implementation_observations"] = {
        "comparison_script": observe(Path(__file__).resolve()),
        "native_witness_validator": observe(ROOT / "GSE/curation/lexicon_builder/foundation.py"),
    }
    try:
        if not start["active_pointer"]["exists"]:
            raise ValueError("ACTIVE_POINTER_MISSING")
        if any(start[name].get("stat", {}).get("st_size", 0) for name in ("before_wal", "after_wal")):
            raise ValueError("NONEMPTY_WAL_REQUIRES_SEPARATE_FROZEN_SNAPSHOT")
        if args.expected_before_sha256 and start["before"].get("sha256") != args.expected_before_sha256:
            raise ValueError("EXPECTED_BEFORE_SHA256_MISMATCH")
        inventory_observation, population, eligible = inventory_scope(findings)
        report["inventory"] = inventory_observation
        report["scope"] = {
            "native_linear_unit_entries": len(population),
            "eligible_native_spellings": len(eligible),
            "eligible_entry_ids": sorted(eligible),
            "excluded_count": len(population) - len(eligible),
            "excluded_entry_ids": sorted(set(population) - eligible),
        }
        with ExitStack() as stack:
            first = snapshot(before)
            stack.callback(first.close)
            second = snapshot(after)
            stack.callback(second.close)
            connections = {"before": first, "after": second}
            versions = {
                side: connection.execute("PRAGMA data_version").fetchone()[0]
                for side, connection in connections.items()
            }
            for side, connection in connections.items():
                inspect_sources(connection, side, population, eligible, findings)
            report["comparison"] = compare_states(first, second, eligible, findings)
            for side, connection in connections.items():
                connection.rollback()
                if connection.execute("PRAGMA data_version").fetchone()[0] != versions[side]:
                    findings.add("CONCURRENT_DATABASE_CHANGE", side=side)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        findings.add("COMPARISON_COULD_NOT_COMPLETE", error_type=type(error).__name__, message=str(error))
    end = {name: observe(path) for name, path in paths.items()}
    report["end_observations"] = end
    for name in paths:
        if start[name] != end[name] or not start[name].get("stable_during_hash", True):
            findings.add("INPUT_CHANGED_DURING_COMPARISON", input=name)
    report["findings"] = findings.report()
    report["code"] = "ISOLATION_FAILED" if findings.counts else "ISOLATION_VERIFIED"
    new_report(report_path, report)
    print(json.dumps({"code": report["code"], "report": str(report_path), "failure_counts": dict(findings.counts)}))
    return 1 if findings.counts else 0


if __name__ == "__main__":
    raise SystemExit(main())
