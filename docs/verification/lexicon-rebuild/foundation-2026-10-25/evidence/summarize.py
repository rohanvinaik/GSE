"""Summarize the foundation receipt from the real CLI's outputs; nothing here is hand-entered.

python docs/verification/lexicon-rebuild/foundation-2026-10-25/evidence/summarize.py <receipt-dir> [<gate-build-dir>]
"""

import json
import sys
from collections import Counter
from pathlib import Path

receipt = Path(sys.argv[1])
proof = json.loads((receipt / "prime_proof.json").read_text())
examined, drafts = {}, {}
for r in proof["records"]:
    if r["definition_review"] == "EXAMINED":
        decisions = r["definition_axiom"]["decisions"]
        examined[r["prime"]] = {
            "code": r["code"],
            "definition_check": r["definition_check"],
            "written": {
                d["decision_id"]: {
                    "coordinates": d["coordinates"],
                    "state": d["state"],
                    "derived_by": d["derived_by"],
                    "authority": d["authority"],
                    "check": r["decision_checks"][d["decision_id"]],
                }
                for d in decisions
                if d["state"] != "empty"
            },
            "boundary": {d["decision_id"]: len(d["coordinates"]) for d in decisions if d["state"] == "empty"},
            "examined_lines": [[e["box"], e["line"], e["judgment"]] for e in r["definition_axiom"]["examination"]],
        }
    else:
        drafts[r["prime"]] = dict(Counter(r["vector"].values()))
summary = {
    "code": proof["code"],
    "definition_checks": proof["definition_checks"],
    "examined": examined,
    "draft_cell_states": drafts,
    "draft_totals": dict(sum((Counter(v) for v in drafts.values()), Counter())),
}
(receipt / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")

if len(sys.argv) > 2:
    build = Path(sys.argv[2])
    origins, complete, structural, head_reach = Counter(), [], 0, Counter()
    head_laws = ("SUBSTANTIVE_HEAD_IS_ONE_HOT", "TIME_PLACE_HEADS_NO_SUBSTANTIVE")
    for line in (build / "words.jsonl").read_text().splitlines():
        record = json.loads(line)
        structural += bool(record["structural_entries"])
        for reading in record["readings"]:
            scope, rid = reading.get("source_scope", "SOURCE_CONTRACT_PROJECTION"), reading["reading_id"]
            for law in head_laws:
                if law in reading["after_selection"]["fired_rules"]:
                    head_reach[f"{law}|{'prime' if rid.startswith('prime:') else 'non-prime'}"] += 1
            origin = (
                "prime_profile"
                if rid.startswith("prime:")
                else ("head:" + rid.split(":")[1] if scope == "LEMMA_POS_HEAD_CONTRACT" else scope)
            )
            origins[f"{origin}|{reading['code']}"] += 1
            if reading["code"] == "CANDIDATE_COMPLETE":
                complete.append(f"{record['word']} -> {rid}")
    breakdown = {
        "summary": json.loads((build / "summary.json").read_text()),
        "readings_by_origin_and_code": dict(sorted(origins.items())),
        "complete_readings": complete,
        "words_with_structural_entries": structural,
        "head_record_law_reach": dict(sorted(head_reach.items())),
    }
    (receipt / "gate" / "build_breakdown.json").write_text(json.dumps(breakdown, indent=1) + "\n")
print(
    json.dumps(
        {
            "code": summary["code"],
            "definition_checks": summary["definition_checks"],
            "draft_totals": summary["draft_totals"],
        },
        indent=1,
    )
)
