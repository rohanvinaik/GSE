"""Read-only review ledger for every lexical coordinate and every NSM unit."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

from GSE.curation.lexicon_builder.catalog import catalog_inventory
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.lexicon_resource import resolve_lexicon_path


def main():
    resource = resolve_lexicon_path()
    catalog = catalog_inventory()
    conn = sqlite3.connect(f"file:{resource}?mode=ro", uri=True)
    try:
        metadata = {key: json.loads(value) for key, value in conn.execute(
            "SELECT key,value FROM builder_metadata WHERE key IN ('prime_entries','rule_version','relations')")}
        units = []
        for unit in catalog["units"]:
            mapping = unit["mapping"]
            definitions = []
            identities = metadata["prime_entries"].get(unit["unit_id"])
            if not identities:
                raise ValueError("UNLINKED_FOUNDATION_UNIT:" + unit["unit_id"])
            for identity in identities:
                row = conn.execute("SELECT l.gloss,d.domains,d.code FROM definition_states d "
                                   "JOIN lexemes l ON l.id=d.lexeme_id WHERE d.entry_id=?", (identity,)).fetchone()
                if row is None:
                    raise ValueError("MISSING_FOUNDATION_IDENTITY:" + identity)
                domains = json.loads(row[1])
                bank = mapping["bank"]
                if bank is not None and bank not in domains:
                    raise ValueError("MISSING_FOUNDATION_BANK_DOMAIN:" + identity)
                definitions.append({"entry_id": identity, "definition": row[0], "code": row[2],
                                    "mapped_bank_domain": domains.get(bank) if bank is not None else None,
                                    "known_coordinates": sum(len(value) == 1 for value in domains.values()),
                                    "open_coordinates": sum(len(value) > 1 for value in domains.values())})
            value = mapping["value"]
            states = [d["mapped_bank_domain"] for d in definitions]
            status = ("CONSTRUCTION_OR_HIERARCHY_REVIEW" if value is None else
                      "ALREADY_SUPPORTED_ON_LINKED_DEFINITIONS" if all(d == [value] for d in states) else
                      "OPEN_PROPOSED_CORRESPONDENCE_REQUIRES_WARRANT" if all(isinstance(d, list) and len(d) > 1 for d in states) else
                      "MIXED_OR_OPPOSING_FOUNDATION_REVIEW")
            units.append({**unit, "review_status": status, "linked_definitions": definitions})
        counts = {bank: {-1: 0, 0: 0, 1: 0} for bank in BANKS}
        for bank, value, count in conn.execute("SELECT primitive,value,COUNT(*) FROM primitive_values "
                                                "GROUP BY primitive,value"):
            if bank in counts:
                counts[bank][value] = count
        banks = [{"bank": bank, "published_sign_counts": counts[bank],
                  "chart_units": [u["unit_id"] for u in catalog["units"] if u["mapping"]["bank"] == bank],
                  "constraint_rule_ids": [r["rule_id"] for r in metadata["relations"] if bank in r["banks"]],
                  "semantic_readiness": "NOT_INFERRED_FROM_CELL_COUNT"} for bank in BANKS]
        report = {"format": "GSE.checkpoint-foundation-review/1", "code": "REVIEW_LEDGER_NO_BANK_WRITES",
                  "resource": str(resource), "rule_version": metadata["rule_version"],
                  "basis_size": len(banks), "nsm_units": len(units),
                  "unit_review_counts": dict(Counter(u["review_status"] for u in units)),
                  "banks_with_no_published_assignment": [bank for bank in BANKS if not sum(counts[bank].values())],
                  "bank_assignments_written": 0, "model_calls": 0,
                  "measurement_boundary": "FOUNDATION_REVIEW_BEFORE_NEXT_METHOD_REVISION",
                  "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "banks": banks, "units": units}
    finally:
        conn.close()
    destination = Path(__file__).with_name("checkpoint-foundation-review.json")
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("code", "resource", "basis_size", "nsm_units",
                                                  "unit_review_counts", "banks_with_no_published_assignment")}, indent=2))


if __name__ == "__main__":
    main()
