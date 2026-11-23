"""Would the 16 Problem-status FrameNet units in the closeout frames change any rule's reach?

For each such unit, every USAS record of the same lemma and part of speech, with the rows whose
identification guard it would newly satisfy if the adapter read frame files instead of luIndex.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from gse.lexicon_builder.sources import NativeSources  # noqa: E402

UNITS = {
    "Emotion_directed": ["annoyed.a", "fascinated.a", "irritated.a", "shocked.a"],
    "Experiencer_focus": [
        "afraid.a", "dread.n", "empathetic.a", "empathize.v", "enjoy.v", "enjoyment.n",
        "luxuriate.v", "relish.v", "savour.v", "scared.a", "terrified.a",
    ],
    "Dimension": ["grand.a"],
}
USAS_POS = {"a": "ADJ", "n": "NOUN", "v": "VERB"}
SIGNED = {"E4.1": "+-", "E4.2": "+-", "E2": "+-", "E3": "-", "E5": "-", "E6": "-"}


def signed_emotion(tag: str) -> bool:
    m = re.fullmatch(r"(E\d(?:\.\d)?)([+-]+)", tag)
    return bool(m and m.group(2)[0] in SIGNED.get(m.group(1), ""))


def main() -> int:
    lemmas = sorted({u.rsplit(".", 1)[0] for units in UNITS.values() for u in units})
    sources = NativeSources(lemmas, Path("data/external"), Path.home() / "nltk_data/corpora")
    rows = []
    for frame, units in UNITS.items():
        for unit in units:
            lemma, pos = unit.rsplit(".", 1)
            native = sources.for_word(lemma)
            usas = [r["values"]["alternatives"] for r in native["usas"]["records"] if r["values"]["pos"] == USAS_POS[pos]]
            tags = [t for alternatives in usas for t in alternatives]
            indexed = sorted({f"{r['values']['frame']}.{r['values']['pos']}" for r in native["framenet"]["records"]})
            newly = []
            if frame == "Emotion_directed" and pos == "a" and any(signed_emotion(t) for t in tags):
                newly.append("19 (not already reached)" if not any(f in indexed for f in ("Emotion_directed.a", "Fear.a", "Emotions_by_stimulus.a")) else "19 (already reached through another indexed unit)")
            if frame == "Emotion_directed" and pos == "a" and any(re.fullmatch(r"E4\.1[+-]+", t) for t in tags):
                newly.append("8")
            if frame == "Experiencer_focus" and pos == "n" and any(signed_emotion(t) for t in tags):
                newly.append("21 (not already reached)" if not any(f in indexed for f in ("Experiencer_focus.n", "Emotion_directed.n", "Fear.n")) else "21 (already reached through another indexed unit)")
            if frame == "Dimension" and pos == "a" and any(re.fullmatch(r"N3\.2[+-]+", t) for t in tags):
                newly.append("7")
            rows.append({"unit": unit, "frame": frame, "usas_same_pos": usas, "indexed_frames": indexed, "rows_affected": newly})
    Path(sys.argv[1]).write_text(json.dumps(rows, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
