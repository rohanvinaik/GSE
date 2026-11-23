"""Stage 1: run the builder's own NativeSources adapter for the word set and save its output unaltered.

Read-only against the repo and the data. Writes only under /tmp/gse-subagents/noun-facts/.
"""

import sys

sys.dont_write_bytecode = True

WORKTREE = "/Users/rohanvinaik/Projects/gse/.claude/worktrees/lexicon-builder/gse"
sys.path.insert(0, WORKTREE)

import csv
import json
from collections import Counter
from pathlib import Path

from gse.lexicon_builder import sources

expected = Path(WORKTREE, "gse/lexicon_builder/sources.py").resolve()
actual = Path(sources.__file__).resolve()
assert actual == expected, f"imported the wrong sources.py: {actual}"
print("sources module file:", actual)

OUT = Path("/tmp/gse-subagents/noun-facts")
ROOT = Path("/Users/rohanvinaik/Projects/gse/data/external")
NLTK_ROOT = Path("/Users/rohanvinaik/nltk_data/corpora")

WORDS = [
    "box", "dog", "cat", "teacher", "person", "child", "crowd", "family", "team", "group",
    "hand", "arm", "finger", "head", "glove", "wheel", "handle", "door",
    "kind", "type", "species", "category", "idea", "love", "freedom", "truth",
    "time", "place", "house", "water", "body", "part", "people",
]
assert len(WORDS) == 33 and len(set(WORDS)) == 33

ns = sources.NativeSources(WORDS, ROOT, NLTK_ROOT)

adapter = {w: ns.for_word(w) for w in WORDS}

# Header rows of each tabular source file, with the columns the adapter keeps.
headers = {}
for source, filename, delimiter, key in (
    ("concreteness", "concreteness.csv", ",", "Word"),
    ("lancaster", "lancaster_sensorimotor.csv", ",", "Word"),
    ("vad", "nrc_vad.txt", "\t", "term"),
    ("usas", "usas/semantic_lexicon_en.tsv", "\t", "lemma"),
):
    path = ROOT / filename
    with path.open(encoding="utf-8-sig", newline="") as f:
        fieldnames = csv.DictReader(f, delimiter=delimiter).fieldnames
    if source == "usas":
        kept = {"lemma": "values.lemma", "pos": "values.pos", "semantic_tags": "values.alternatives (split on whitespace)"}
    elif source == "concreteness":
        kept = {"Conc.M": "values.mean"}
    else:
        kept = {k: f"values.{k}" for k in fieldnames if k != key}
    headers[source] = {
        "file": str(path),
        "key_column": key,
        "columns_in_file": fieldnames,
        "columns_retained_by_adapter": kept,
        "columns_not_retained_by_adapter": [c for c in fieldnames if c not in kept],
    }

# Whole-file USAS pos inventory, so "noun" can be chosen from literal values.
usas_pos_counts = Counter()
with (ROOT / "usas/semantic_lexicon_en.tsv").open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        usas_pos_counts[row["pos"]] += 1

# nrc_emotion.txt has no header; show its first row's shape for the record.
with (ROOT / "nrc_emotion.txt").open() as f:
    first_emotion_row = next(csv.reader(f, delimiter="\t"))

payload = {
    "words": WORDS,
    "root": str(ROOT),
    "nltk_root": str(NLTK_ROOT),
    "worktree": WORKTREE,
    "sources_py": str(actual),
    "manifest": ns.manifest,
    "headers": headers,
    "nrc_emotion_first_row_no_header": first_emotion_row,
    "usas_pos_counts_whole_file": dict(usas_pos_counts),
    "adapter": adapter,
}
(OUT / "adapter_raw.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))

# ---- compact stdout view ----
print("\nMANIFEST (source, status, scope, units, file ids):")
for m in ns.manifest:
    ids = [f["id"] for f in m["files"]]
    shown = ids if len(ids) <= 3 else ids[:1] + [f"... {len(ids)} files ..."]
    print(" ", m["source"], m["status"], m["scope"], "|", m["units"], "|", shown)

print("\nHEADERS:")
for s, h in headers.items():
    print(" ", s, "columns:", h["columns_in_file"])
    print("     retained:", list(h["columns_retained_by_adapter"]))
    print("     not retained:", h["columns_not_retained_by_adapter"])
print("  nrc_emotion first row (no header):", first_emotion_row)

print("\nUSAS pos inventory (whole file):", dict(usas_pos_counts))
pos_seen = Counter()
for w in WORDS:
    for r in adapter[w]["usas"]["records"]:
        pos_seen[r["values"]["pos"]] += 1
print("USAS pos seen on the 33 words:", dict(pos_seen))

for w in WORDS:
    print(f"\n=== {w} ===")
    for s, block in adapter[w].items():
        recs = block["records"]
        if s == "verbnet":
            print(f"  {s}: {block['status']} n={len(recs)}")
            for r in recs:
                print("     ", r["record_id"], "| class:", r["values"]["class"], "| frames:", len(r["values"]["frames"]))
        else:
            print(f"  {s}: {block['status']} n={len(recs)}")
            for r in recs:
                print("     ", json.dumps(r, ensure_ascii=False))
