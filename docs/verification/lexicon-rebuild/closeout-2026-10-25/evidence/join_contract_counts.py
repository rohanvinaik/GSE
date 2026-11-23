"""Reach of the revised USAS-FrameNet join for review rows 6, 7, 8 and 19-21. Complete lists.

Contract table (same-category pairs certify; a generic frame needs the typed discriminator):
  A5.1 +/- with Desirability             same category (quality)           CERTIFIED
  N3.2 +/- with Size                     same category (size)              CERTIFIED
  N3.2 +/- with Dimension only           measurement-with-number units     NOT JOINED
  E5- or E6- with Fear                   fear frame inside that scale side CERTIFIED
  any slice E tag with a generic frame   Emotion_directed, Experiencer_focus, Emotions_by_stimulus
                                         (any emotional response)          DISCRIMINATOR
Rows 19-21 come from emotion_population.json; rows 6-8 from the whole USAS lexicon.
"""

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from gse.lexicon_builder.sources import NativeSources  # noqa: E402

USAS = Path("data/external/usas/semantic_lexicon_en.tsv")
POPULATION = Path(__file__).parent / "emotion_population.json"


def adjective_rows() -> dict:
    tagged: dict[str, list[str]] = {}
    with USAS.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["pos"] == "ADJ":
                tagged.setdefault(row["lemma"], []).extend(row["semantic_tags"].split())
    wanted = {w for w, tags in tagged.items() if any(re.fullmatch(r"(A5\.1|N3\.2|E4\.1)[+-]+", t) for t in tags)}
    sources = NativeSources(sorted(wanted), Path("data/external"), Path.home() / "nltk_data/corpora")
    out = {"6": [], "7_size": [], "7_dimension_only": [], "8": []}
    for word in sorted(wanted):
        frames = {r["values"]["frame"] for r in sources.for_word(word)["framenet"]["records"] if r["values"]["pos"] == "a"}
        tags = tagged[word]
        if any(re.fullmatch(r"A5\.1[+-]+", t) for t in tags) and "Desirability" in frames:
            out["6"].append(word)
        if any(re.fullmatch(r"N3\.2[+-]+", t) for t in tags):
            if "Size" in frames:
                out["7_size"].append(word)
            elif "Dimension" in frames:
                out["7_dimension_only"].append(word)
        if any(re.fullmatch(r"E4\.1[+-]+", t) for t in tags) and "Emotion_directed" in frames:
            out["8"].append(word)
    return out


FAMILY_POS = {"19_adjective": "a", "20_verb": "v", "21_noun": "n"}


def slice_rows() -> dict:
    population = json.loads(POPULATION.read_text())["population"]
    out = {}
    for family, entries in population.items():
        certified, discriminated, e5_without_fear = [], [], []
        for e in entries:
            # A frame counts only under the family's own part of speech: a noun is not certified by an adjective's unit.
            frames = {f.rsplit(".", 1)[0] for f in e["framenet_frames"] if f.rsplit(".", 1)[1] == FAMILY_POS[family]}
            fear_side = any(t.startswith(("E5-", "E6-")) for t in e["matching_tags"])
            if family != "20_verb" and fear_side and "Fear" in frames:
                certified.append(e["word"])
            else:
                discriminated.append(e["word"])
            if all(t.startswith("E5-") for t in e["matching_tags"]) and "Fear" not in frames:
                e5_without_fear.append(e["word"])
        out[family] = {
            "certified": certified,
            "discriminator": discriminated,
            "only_E5_minus_and_no_Fear_frame": e5_without_fear,
        }
    return out


def main() -> int:
    adjectives = adjective_rows()
    slices = slice_rows()
    report = {
        "counts": {
            **{f"row_{k}": len(v) for k, v in adjectives.items()},
            **{f"{k}_{part}": len(v[part]) for k, v in slices.items() for part in ("certified", "discriminator")},
        },
        "rows_6_to_8": adjectives,
        "rows_19_to_21": slices,
    }
    Path(sys.argv[1]).write_text(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
