"""In-scope population for the drafted emotion rules (rows 19-21) and every bank signal its words carry.

Complete lists, no sampling. A signal is a lead for review: a USAS tag, FrameNet frame or VerbNet
predicate of the same word that names content in a bank the draft's row 23 would certify silent.
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from gse.lexicon_builder.sources import NativeSources  # noqa: E402

SIGNED = {"E4.1": "+-", "E4.2": "+-", "E2": "+-", "E3": "-", "E5": "-", "E6": "-"}
ADJ_FRAMES = {"Emotion_directed", "Fear", "Emotions_by_stimulus"}
NOUN_FRAMES = {"Experiencer_focus", "Emotion_directed", "Fear"}
BANK_SIGNALS = {
    "time bank": ("T1", "T2", "T3", "T4"),
    "space bank": ("M6", "M7", "N3.3"),
    "quantity bank": ("N1", "N5"),
    "BIG": ("N3.2",),
    "SEE/HEAR": ("X3",),
    "SAY/WORDS": ("Q1", "Q2", "Q3", "Q4"),
    "MOVE": ("M1", "M2", "M3", "M4", "M5"),
    "HAVE": ("A9",),
    "BE/EXIST": ("A3",),
    "ALIVE": ("L1",),
    "MAYBE/MUST/CERTAINTY": ("A7",),
    "CAUSE": ("A2.2",),
    "LIKE/SAME": ("A6.1",),
    "TRUE": ("A5.2",),
    "PEOPLE/SOMEONE": ("S2",),
    "BODY": ("B1",),
    "social (WITH/WITHOUT, OTHER)": ("S1", "S3", "S5"),
}


def signed_emotion(tag: str) -> str | None:
    if "/" in tag:
        return None
    m = re.fullmatch(r"(E\d(?:\.\d)?)([+-]+)", tag)
    return m.group(1) + m.group(2)[0] if m and m.group(2)[0] in SIGNED.get(m.group(1), "") else None


def bank_leads(tags: list[str]) -> dict[str, list[str]]:
    leads = defaultdict(list)
    for tag in tags:
        for part in tag.split("/"):
            for bank, prefixes in BANK_SIGNALS.items():
                if any(part == p or part.startswith(p) for p in prefixes):
                    leads[bank].append(tag)
    return dict(leads)


def main() -> int:
    lemmas = set()
    with open("data/external/usas/semantic_lexicon_en.tsv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if any(signed_emotion(t) for t in row["semantic_tags"].split()):
                lemmas.add(row["lemma"])
    sources = NativeSources(sorted(lemmas), Path("data/external"), Path.home() / "nltk_data/corpora")
    population = {"19_adjective": [], "20_verb": [], "21_noun": []}
    for lemma in sorted({w for w in sources.words}):
        native = sources.for_word(lemma)
        fn = {(r["values"]["pos"], r["values"]["frame"]) for r in native["framenet"]["records"]}
        vn = native["verbnet"]["records"]
        for record in native["usas"]["records"]:
            pos, tags = record["values"]["pos"], record["values"]["alternatives"]
            emotion = [t for t in tags if signed_emotion(t)]
            if not emotion:
                continue
            entry = {
                "word": lemma,
                "matching_tags": emotion,
                "first_tag": tags[0],
                "all_tags": tags,
                "bank_leads_from_usas": bank_leads(tags),
                "framenet_frames": sorted(f"{fr}.{p}" for p, fr in fn),
            }
            if pos == "ADJ" and any(p == "a" and fr in ADJ_FRAMES for p, fr in fn):
                population["19_adjective"].append(entry)
            if pos == "VERB" and any(r["values"]["class"].startswith("admire-31.2") for r in vn):
                classes = sorted({r["values"]["class"] for r in vn})
                predicates = sorted({p["predicate"]["value"] for r in vn for fr in r["values"]["frames"] for p in fr["predicates"]})
                population["20_verb"].append({**entry, "verbnet_classes": classes, "verbnet_predicates": predicates})
            if pos == "NOUN" and any(p == "n" and fr in NOUN_FRAMES for p, fr in fn):
                population["21_noun"].append(entry)
    leads_by_bank = defaultdict(lambda: defaultdict(list))
    for family, entries in population.items():
        for e in entries:
            for bank in e["bank_leads_from_usas"]:
                leads_by_bank[bank][family].append(e["word"])
    report = {
        "scope": "words passing the drafted identification guards of rows 19-21, over the whole USAS lexicon",
        "counts": {k: len(v) for k, v in population.items()},
        "usas_bank_leads_by_bank": {b: dict(f) for b, f in sorted(leads_by_bank.items())},
        "population": population,
    }
    Path(sys.argv[1]).write_text(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
