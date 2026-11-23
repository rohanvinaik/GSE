"""One-off patch of line references in the part files after the repository changed during the pass.

Edits only /tmp/gse-subagents/adaptation-facts/parts/*.json. Each rule states how many replacements to expect.
"""

from pathlib import Path

PARTS = Path("/tmp/gse-subagents/adaptation-facts/parts")

RULES = {
    "10_cross_cutting.json": [
        ("REPORT.md:116-119", "REPORT.md:123-126", 2),
        ("tasks.md:17", "tasks.md:18", 1),
    ],
    "20_coords_a.json": [
        ("REPORT.md:117 and openspec/changes/lexicon-symbolic-foundation/tasks.md:17", "REPORT.md:124 and openspec/changes/lexicon-symbolic-foundation/tasks.md:18", 1),
        ("bank_laws.json:1645-1654", "bank_laws.json:1651-1659", 1),
        ("native_constraints.py:37-49", "native_constraints.py:41-53", 1),
        ("REPORT.md:116-119", "REPORT.md:123-126", 1),
        ("REPORT.md:53", "REPORT.md:58", 2),
    ],
    "21_coords_b.json": [
        ("REPORT.md:117 lists", "REPORT.md:124 lists", 1),
    ],
    "22_coords_c.json": [
        ("REPORT.md:117; openspec/changes/lexicon-symbolic-foundation/tasks.md:17", "REPORT.md:124; openspec/changes/lexicon-symbolic-foundation/tasks.md:18", 2),
        ("(REPORT.md:117)", "(REPORT.md:124)", 1),
        ("REPORT.md:117 list it", "REPORT.md:124 list it", 1),
        ("REPORT.md:26,47-51", "REPORT.md:31,52-56", 1),
        ("foundation-2026-10-25/REPORT.md:47-51", "foundation-2026-10-25/REPORT.md:52-56", 1),
    ],
    "40_contradictions.json": [
        ("tasks.md:17", "tasks.md:18", 1),
        ("foundation-2026-10-25/REPORT.md:117", "foundation-2026-10-25/REPORT.md:124", 1),
    ],
}

for name, rules in RULES.items():
    path = PARTS / name
    text = path.read_text(encoding="utf-8")
    for old, new, expected in rules:
        found = text.count(old)
        if found != expected:
            print("MISMATCH", name, repr(old), "expected", expected, "found", found)
            continue
        text = text.replace(old, new)
        print("ok", name, repr(old), "->", repr(new), "x", found)
    path.write_text(text, encoding="utf-8")
