"""Every frame predicate (mapped or unmapped) in readings where NATIVE:VN_CAUSATION fired,
with argument types kept, so event arguments are told apart from role arguments."""
import json
import sys
from collections import Counter, defaultdict

def role_args(native):
    return {a["value"].lstrip("?") for a in native.get("arguments", []) if a.get("type") == "ThemRole"}

rows = []
with open(sys.argv[1]) as handle:
    for line in handle:
        record = json.loads(line)
        for reading in record.get("readings", []):
            sel = reading.get("after_selection") or {}
            if "NATIVE:VN_CAUSATION" not in sel.get("fired_rules", []):
                continue
            preds = []
            causers = set()
            for binding in reading.get("bindings", []):
                for ev in binding.get("all_phase_evidence", []):
                    native = ev.get("native", {})
                    name = native.get("predicate", {}).get("value")
                    if ev.get("rule_id") == "VN_CAUSATION":
                        causers |= role_args(native)
                    preds.append((ev.get("predicate_index"), name, tuple(sorted(role_args(native))), ev.get("rule_id")))
            for u in reading.get("unmapped", []):
                native = u.get("native", {})
                preds.append((u.get("predicate_index"), native.get("predicate", {}).get("value"), tuple(sorted(role_args(native))), u.get("code")))
            unique = sorted(set(preds), key=lambda p: (p[0] if p[0] is not None else -1, p[1] or ""))
            non_cause = [p for p in unique if p[1] != "cause"]
            touches_other = [p for p in non_cause if set(p[2]) - causers]
            rows.append({
                "word": record["word"],
                "reading_id": reading["reading_id"],
                "class": reading["reading_id"].split(":")[2],
                "causers": sorted(causers),
                "non_cause_predicates": [[p[1], list(p[2]), p[3]] for p in non_cause],
                "touches_non_causer": bool(touches_other),
            })

print("readings:", len(rows))
print("with a non-cause predicate naming a non-causer role:", sum(r["touches_non_causer"] for r in rows))
print()
print("readings with no non-cause predicate naming a non-causer role:")
for r in rows:
    if not r["touches_non_causer"]:
        print(" ", r["reading_id"], "causers", r["causers"], "other predicates", r["non_cause_predicates"])
print()
family = Counter()
family_words = defaultdict(set)
for r in rows:
    top = r["class"].split("-")[1].split(".")[0] if "-" in r["class"] else "?"
    family[top] += 1
    family_words[top].add(r["word"])
print("readings by VerbNet top-level class number (first number after the class name):")
for top, count in sorted(family.items(), key=lambda kv: -kv[1]):
    print(f"  {top}: {count} readings; {len(family_words[top])} words: {sorted(family_words[top])[:25]}")
json.dump(rows, open(sys.argv[2], "w"), indent=1)
