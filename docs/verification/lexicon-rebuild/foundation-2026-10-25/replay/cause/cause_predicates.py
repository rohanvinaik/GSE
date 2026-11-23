"""Inventory of the native predicates that co-occur with cause(...) in the 861 CAUSE readings:
predicate name, whether it names a non-causer role, its phase argument, and the classes it occurs in."""
import json
import sys
from collections import defaultdict

def phase_of(native):
    for a in native.get("arguments", []):
        if a.get("type") == "Event":
            v = a["value"]
            return v.split("(")[0] if "(" in v else "whole"
    return "none"

def role_args(native):
    return [a["value"].lstrip("?") for a in native.get("arguments", []) if a.get("type") == "ThemRole"]

inv = defaultdict(lambda: {"readings": 0, "names_non_causer": 0, "names_causer": 0, "phases": defaultdict(int), "classes": set()})
with open(sys.argv[1]) as handle:
    for line in handle:
        record = json.loads(line)
        for reading in record.get("readings", []):
            sel = reading.get("after_selection") or {}
            if "NATIVE:VN_CAUSATION" not in sel.get("fired_rules", []):
                continue
            natives = []
            causers = set()
            for binding in reading.get("bindings", []):
                for ev in binding.get("all_phase_evidence", []):
                    natives.append((ev.get("predicate_index"), ev.get("native", {})))
                    if ev.get("rule_id") == "VN_CAUSATION":
                        causers |= set(role_args(ev.get("native", {})))
            for u in reading.get("unmapped", []):
                natives.append((u.get("predicate_index"), u.get("native", {})))
            seen = {}
            for index, native in natives:
                seen[(index, json.dumps(native, sort_keys=True))] = native
            vn_class = reading["reading_id"].split(":")[2]
            for native in seen.values():
                name = (native.get("predicate", {}) or {}).get("value")
                if name == "cause":
                    continue
                neg = (native.get("predicate", {}) or {}).get("bool") == "!"
                key = ("!" if neg else "") + str(name)
                entry = inv[key]
                entry["readings"] += 1
                roles = set(role_args(native))
                entry["names_non_causer"] += bool(roles - causers)
                entry["names_causer"] += bool(roles & causers)
                entry["phases"][phase_of(native)] += 1
                entry["classes"].add(vn_class.split("-")[0])
rows = sorted(inv.items(), key=lambda kv: -kv[1]["readings"])
print(f"{'predicate':34} {'occ':>5} {'nonCauser':>9} {'causer':>6}  phases | classes")
for name, e in rows:
    print(f"{name:34} {e['readings']:5} {e['names_non_causer']:9} {e['names_causer']:6}  {dict(e['phases'])} | {sorted(e['classes'])[:10]}")
