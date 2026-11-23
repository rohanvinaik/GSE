"""Stage 3: WordNet noun synsets as facts, read in place from NLTK's wordnet.zip (nothing is unzipped).

The directory /Users/rohanvinaik/nltk_data/corpora/wordnet is checked first and its presence or
absence is recorded. Read-only; writes only under /tmp/gse-subagents/noun-facts/.
"""

import sys

sys.dont_write_bytecode = True

import hashlib
import json
import zipfile
from pathlib import Path

OUT = Path("/tmp/gse-subagents/noun-facts")
NLTK_DATA = Path("/Users/rohanvinaik/nltk_data")
CORPORA = NLTK_DATA / "corpora"

raw = json.loads((OUT / "adapter_raw.json").read_text())
WORDS = raw["words"]

avail = {
    "directory_corpora_wordnet": str(CORPORA / "wordnet"),
    "directory_corpora_wordnet_exists": (CORPORA / "wordnet").exists(),
    "archives": {},
}
for name in ("wordnet.zip", "wordnet31.zip", "wordnet2021.zip", "omw.zip", "omw-1.4.zip"):
    p = CORPORA / name
    if p.exists():
        avail["archives"][name] = {"path": str(p), "size_bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}

zpath = CORPORA / "wordnet.zip"
with zipfile.ZipFile(zpath) as z:
    avail["wordnet_zip_members"] = [{"name": i.filename, "size_bytes": i.file_size} for i in z.infolist()]
    # Small text members that may document the files (README, lexnames, citation).
    docs = {}
    for i in z.infolist():
        base = i.filename.rsplit("/", 1)[-1]
        if base in {"README", "LICENSE", "citation.bib", "lexnames"} and i.file_size < 20000:
            docs[i.filename] = z.read(i).decode("utf-8", "replace")
    avail["wordnet_zip_small_documentation_members"] = docs

import nltk

nltk.data.path[:] = [str(NLTK_DATA)]
from nltk.corpus import wordnet as wn

version = wn.get_version()
avail["nltk_version"] = nltk.__version__
avail["wordnet_version_reported_by_reader"] = version
avail["reader_root"] = str(wn.root)

per_word = {}
for w in WORDS:
    syns = wn.synsets(w, pos=wn.NOUN)
    entries = []
    for idx, s in enumerate(syns):
        names = s.lemma_names()
        entries.append(
            {
                "sense_list_index": idx,
                "synset": s.name(),
                "offset": s.offset(),
                "lexname": s.lexname(),
                "definition": s.definition(),
                "examples": s.examples(),
                "lemma_names": names,
                "exact_word_in_lemma_names": w.lower() in [n.lower() for n in names],
                "direct_hypernyms": [h.name() for h in s.hypernyms()],
                "direct_instance_hypernyms": [h.name() for h in s.instance_hypernyms()],
                "hypernym_paths_root_to_synset": [[x.name() for x in path] for path in s.hypernym_paths()],
            }
        )
    per_word[w] = {
        "morphy_base_form_noun": wn.morphy(w, wn.NOUN),
        "n_noun_synsets": len(entries),
        "n_with_exact_word_in_lemma_names": sum(e["exact_word_in_lemma_names"] for e in entries),
        "synsets": entries,
    }

(OUT / "wordnet.json").write_text(json.dumps({"availability": avail, "per_word": per_word}, ensure_ascii=False, indent=1))

print("directory exists:", avail["directory_corpora_wordnet_exists"])
print("archives:", {k: (v["size_bytes"], v["sha256"][:12]) for k, v in avail["archives"].items()})
print("reader root:", avail["reader_root"], "| version:", version, "| nltk", nltk.__version__)
print("zip members:", [m["name"] for m in avail["wordnet_zip_members"]])
print("zip docs members:", list(avail["wordnet_zip_small_documentation_members"]))
for w in WORDS:
    pw = per_word[w]
    print(f"\n=== {w}: n={pw['n_noun_synsets']} exact={pw['n_with_exact_word_in_lemma_names']} morphy={pw['morphy_base_form_noun']}")
    for e in pw["synsets"]:
        flag = "" if e["exact_word_in_lemma_names"] else "  [NOT EXACT WORD IN LEMMAS]"
        print(f"  {e['sense_list_index']:2} {e['synset']:28} {e['lexname']:16} {e['definition']}{flag}")
