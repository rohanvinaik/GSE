"""Merge the part files into adaptation_facts.json and cross-check them.

Reads /tmp/gse-subagents/adaptation-facts/parts/*.json and writes
/tmp/gse-subagents/adaptation-facts/adaptation_facts.json. It reads no repository file.
"""

import json
import re
from pathlib import Path

ROOT = Path("/tmp/gse-subagents/adaptation-facts")
PARTS = ROOT / "parts"
OUT = ROOT / "adaptation_facts.json"

ORDER = [
    "QUANTITY",
    "INFER",
    "ALIVE",
    "THEN",
    "START",
    "OUTSIDE",
    "TOWARD",
    "WITH",
    "MUST",
    "CAUSE",
    "TRUE",
    "HIER_PLUS",
    "HIER_MINUS",
    "INTENSITY",
    "CERTAINTY",
]
ALLOWED_WHO = {
    "ROHAN",
    "QUOTED_AGENT",
    "ROHAN_ENDORSEMENT",
    "AGENT_DOC",
    "CODE_CURRENT",
    "CODE_REGISTRY",
    "CODE_LEGACY",
    "DOC_JUNE2026",
    "ROHAN_PAPER",
    "NSM_CHART",
    "none",
}


def load(name):
    with open(PARTS / name, encoding="utf-8") as handle:
        return json.load(handle)


meta = load("00_meta.json")
cross = load("10_cross_cutting.json")
coords_a = load("20_coords_a.json")
coords_b = load("21_coords_b.json")
coords_c = load("22_coords_c.json")
number = load("30_number.json")
contradictions = load("40_contradictions.json")

shared = coords_c.pop("_HIER_PAIR_SHARED")

coords = {}
for source in (coords_a, coords_b, coords_c):
    for key, value in source.items():
        if key in coords:
            raise SystemExit("duplicate coordinate entry: " + key)
        coords[key] = value

missing = [k for k in ORDER if k not in coords]
extra = [k for k in coords if k not in ORDER]
if missing or extra:
    raise SystemExit("coordinate mismatch: missing=%s extra=%s" % (missing, extra))

# HIER_PLUS and HIER_MINUS begin with the statements they share.
for key in ("HIER_PLUS", "HIER_MINUS"):
    entry = coords[key]
    own = entry.get("statements", [])
    shared_statements = []
    for statement in shared["statements"]:
        copy = dict(statement)
        copy["shared_with"] = ["HIER_PLUS", "HIER_MINUS"]
        shared_statements.append(copy)
    entry["statements"] = shared_statements + own
    scale = []
    for statement in shared["scale_numeric_semantics"]:
        copy = dict(statement)
        copy["shared_with"] = ["HIER_PLUS", "HIER_MINUS"]
        scale.append(copy)
    scale.append(
        {
            "loc": "top-level key hier_number_intensity_relations",
            "who": "none",
            "quote": "Every statement relating HIER_PLUS/HIER_MINUS to NUMBER and INTENSITY is collected there (R01-R28).",
        }
    )
    entry["scale_numeric_semantics"] = scale
    entry["number_of_shared_statements"] = len(shared_statements)

# Reconcile contradiction ids in both directions.
contradiction_list = contradictions["contradictions"]
ids = [c["id"] for c in contradiction_list]
if len(ids) != len(set(ids)):
    raise SystemExit("duplicate contradiction id")
by_coordinate = {}
for item in contradiction_list:
    for name in item.get("coordinates", []):
        by_coordinate.setdefault(name, set()).add(item["id"])
reconciliation_notes = []
for key in ORDER:
    declared = set(coords[key].get("contradiction_ids", []))
    unknown = declared.difference(ids)
    if unknown:
        raise SystemExit("coordinate %s cites unknown contradiction ids %s" % (key, sorted(unknown)))
    computed = by_coordinate.get(key, set())
    union = sorted(declared.union(computed))
    added = sorted(set(union).difference(declared))
    if added:
        reconciliation_notes.append("%s: added %s from the contradictions' coordinate lists" % (key, added))
    coords[key]["contradiction_ids"] = union
number_declared = set(number["NUMBER"].get("contradiction_ids", []))
number_union = sorted(number_declared.union(by_coordinate.get("NUMBER", set())))
number["NUMBER"]["contradiction_ids"] = number_union
for item in contradiction_list:
    for name in item.get("coordinates", []):
        if name not in ORDER and name != "NUMBER":
            raise SystemExit("contradiction %s names unknown coordinate %s" % (item["id"], name))

# Check that every statement carries a location, a speaker tag and a quotation.
problems = []


def paper_caveat(loc):
    """Authorship caveat for a statement tagged ROHAN_PAPER (see attribution_key)."""
    parts = []
    if "GSE_V2.md" in loc:
        parts.append("GSE_V2.md is laid out as an implementation plan (phases, files to create)")
    if "pronouns_numbers.md" in loc:
        parts.append("pronouns_numbers.md is laid out as an implementation plan ('Key file to create')")
    if "sentence_architecture.md" in loc:
        if ":92" in loc:
            parts.append("line 92 is inside a pasted status report (lines 84-117)")
        else:
            parts.append("sentence_architecture.md is an idea-dump file with first-person passages")
    for name in ("GSE_HDC_architecture.md", "GSE_Novel_Contributions.md", "numerical_semantics_theory.md"):
        if name in loc:
            parts.append(name + " is an architecture or theory note")
    parts.append("authorship of individual lines is not established")
    return "; ".join(parts)


caveated = []


def add_caveats(label, statements):
    for index, statement in enumerate(statements):
        tokens = set(re.findall(r"[A-Z_0-9a-z]+", statement.get("who", "")))
        if "ROHAN_PAPER" in tokens:
            statement["authorship_caveat"] = paper_caveat(statement.get("loc", ""))
            caveated.append("%s[%d]" % (label, index))


def check_statements(label, statements):
    for index, statement in enumerate(statements):
        for field in ("loc", "who", "quote"):
            if field not in statement or not isinstance(statement[field], str) or not statement[field]:
                problems.append("%s[%d] lacks %s" % (label, index, field))
        tokens = set(re.findall(r"[A-Z_0-9a-z]+", statement.get("who", "")))
        if not tokens.intersection(ALLOWED_WHO):
            problems.append("%s[%d] has an unknown who tag: %r" % (label, index, statement.get("who")))
        # Nothing outside the founder record may carry the bare ROHAN tag.
        if "ROHAN" in tokens and "LEXICON_FOUNDER_WORDS" not in statement.get("loc", ""):
            problems.append("%s[%d] is tagged ROHAN but its loc is not the founder record: %r" % (label, index, statement.get("loc")))


for key in ORDER:
    add_caveats(key + ".statements", coords[key]["statements"])
    scale = coords[key].get("scale_numeric_semantics")
    if isinstance(scale, list):
        add_caveats(key + ".scale_numeric_semantics", scale)
add_caveats("NUMBER.statements", number["NUMBER"]["statements"])
add_caveats("NUMBER.scale_numeric_semantics", number["NUMBER"]["scale_numeric_semantics"])
for item in contradiction_list:
    add_caveats(item["id"] + ".sides", item["sides"])
add_caveats("hier_number_intensity_relations", number["hier_number_intensity_relations"]["entries"])

for key in ORDER:
    check_statements(key + ".statements", coords[key]["statements"])
    scale = coords[key].get("scale_numeric_semantics")
    if isinstance(scale, list):
        check_statements(key + ".scale_numeric_semantics", scale)
check_statements("NUMBER.statements", number["NUMBER"]["statements"])
check_statements("NUMBER.scale_numeric_semantics", number["NUMBER"]["scale_numeric_semantics"])
for item in contradiction_list:
    check_statements(item["id"] + ".sides", item["sides"])
for index, relation in enumerate(number["hier_number_intensity_relations"]["entries"]):
    for field in ("id", "pairs", "loc", "who", "quote"):
        if field not in relation:
            problems.append("hier_number_intensity_relations[%d] lacks %s" % (index, field))

document = {
    "meta": meta["meta"],
    "attribution_key": meta["attribution_key"],
    "files_read": meta["files_read"],
    "cross_cutting_basis_facts": cross["cross_cutting_basis_facts"],
    "inventories_of_gse_adaptation_coordinates_by_source": cross["inventories_of_gse_adaptation_coordinates_by_source"],
    "founder_record_index": cross["founder_record_index"],
    "coordinates": {key: coords[key] for key in ORDER},
    "NUMBER": number["NUMBER"],
    "hier_number_intensity_relations": number["hier_number_intensity_relations"],
    "contradictions_note": contradictions["contradictions_note"],
    "contradictions": contradiction_list,
}
snapshot_path = PARTS / "50_source_snapshot.json"
if snapshot_path.exists():
    document["source_snapshot"] = load("50_source_snapshot.json")
document["meta"]["contradiction_id_links"] = {
    "explanation": (
        "Each coordinate's contradiction_ids holds the ids cited by hand in its entry plus every id whose own "
        "coordinates list names it. The second kind of link was added mechanically by merge.py."
    ),
    "added_mechanically": reconciliation_notes,
}
document["meta"]["statements_with_authorship_caveat"] = len(caveated)
document["summary_counts"] = {
    "statements_per_coordinate": {key: len(coords[key]["statements"]) for key in ORDER},
    "number_statements": len(number["NUMBER"]["statements"]),
    "hier_number_intensity_relations": len(number["hier_number_intensity_relations"]["entries"]),
    "contradictions": len(contradiction_list),
    "founder_record_entries_indexed": len(cross["founder_record_index"]["entries"]),
}

with open(OUT, "w", encoding="utf-8") as handle:
    json.dump(document, handle, indent=2, ensure_ascii=False)
    handle.write("\n")

print("wrote", OUT)
print("summary_counts:", json.dumps(document["summary_counts"], sort_keys=True))
print("problems:", len(problems))
for line in problems:
    print("  PROBLEM", line)
print("reconciliation notes:", len(reconciliation_notes))
for line in reconciliation_notes:
    print("  NOTE", line)
