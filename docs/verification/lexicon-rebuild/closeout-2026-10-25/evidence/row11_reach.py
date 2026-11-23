"""Every gate word that review row 11 (VN_AFFECTIVE_STATE) would give FEEL +1, with the same verb's typed evidence.

Complete list, no sampling. For each VerbNet class (or subclass) whose frames carry a positive
emotional_state predicate, every member that is a gate word is listed with its USAS verb
alternatives, its indexed FrameNet verb frames, and the WordNet sense keys VerbNet records for
that member. Nothing here writes a cell; it is evidence for the row's guard.
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from gse.lexicon_builder.sources import NativeSources, word_key  # noqa: E402

VERBNET = Path.home() / "nltk_data/corpora/verbnet"
GATE_WORDS = Path("docs/verification/lexicon-rebuild/closeout-2026-10-25/gate/gate_words.txt")


def affective_members() -> dict[str, list[dict]]:
    """member word -> [{class, wn}] for each class node whose own or inherited frames assert emotional_state."""
    members: dict[str, list[dict]] = {}

    def visit(node: ET.Element, inherited: bool) -> None:
        own = any(
            p.attrib.get("value") == "emotional_state" and p.attrib.get("bool") != "!"
            for p in node.findall("./FRAMES/FRAME/SEMANTICS/PRED")
        )
        active = inherited or own
        if active:
            for m in node.findall("./MEMBERS/MEMBER"):
                members.setdefault(word_key(m.attrib["name"]), []).append(
                    {"class": node.attrib["ID"], "wn": m.attrib.get("wn", "")}
                )
        for child in node.findall("./SUBCLASSES/VNSUBCLASS"):
            visit(child, active)

    for path in sorted(VERBNET.glob("*.xml")):
        visit(ET.parse(path).getroot(), False)
    return members


def main() -> int:
    gate = [w for w in GATE_WORDS.read_text().split("\n") if w.strip()]
    members = affective_members()
    reached = sorted({word_key(w) for w in gate} & set(members))
    sources = NativeSources(reached, Path("data/external"), Path.home() / "nltk_data/corpora")
    rows = []
    for word in reached:
        native = sources.for_word(word)
        usas = [r["values"]["alternatives"] for r in native["usas"]["records"] if r["values"]["pos"] == "VERB"]
        tags = [t for alternatives in usas for t in alternatives]
        rows.append(
            {
                "word": word,
                "verbnet": members[word],
                "usas_verb_alternatives": usas,
                "usas_verb_has_E_tag": any(part.startswith("E") for t in tags for part in t.split("/")),
                "framenet_verb_frames": sorted({r["values"]["frame"] for r in native["framenet"]["records"] if r["values"]["pos"] == "v"}),
            }
        )
    report = {
        "scope": "gate words that are members of a VerbNet class whose frames assert a positive emotional_state",
        "gate_words": len(gate),
        "affective_classes": sorted({e["class"] for entries in members.values() for e in entries}),
        "reached": len(rows),
        "reached_without_any_usas_E_verb_tag": [r["word"] for r in rows if not r["usas_verb_has_E_tag"]],
        "rows": rows,
    }
    Path(sys.argv[1]).write_text(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
