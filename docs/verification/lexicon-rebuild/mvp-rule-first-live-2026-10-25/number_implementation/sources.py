"""Read native records for requested words; never project them to prime signs.

The discovery script observes the whole population. This adapter retains the
individual records needed to construct and replay one word's definition.
"""

from __future__ import annotations

import csv
import hashlib
import math
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


def word_key(word: str) -> str:
    return unicodedata.normalize("NFC", word).strip().casefold()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NativeSources:
    """Batch lookup with source absence, alternatives and native units intact."""

    def __init__(self, words: list[str], root: Path, nltk_root: Path):
        self.words = {word_key(w) for w in words}
        if not self.words or "" in self.words:
            raise ValueError("nonempty words are required")
        self.records: dict[str, dict[str, list[dict]]] = {w: defaultdict(list) for w in self.words}
        self.manifest: list[dict] = []
        self._tables(root)
        self._frames(nltk_root)

    def _pin(self, source: str, paths: list[Path], units: str, scope: str) -> None:
        self.manifest.append(
            {
                "source": source,
                "units": units,
                "scope": scope,
                "status": "AVAILABLE" if paths else "UNAVAILABLE",
                "files": [{"path": str(p), "sha256": sha256(p)} for p in paths],
            }
        )

    def _tables(self, root: Path) -> None:
        for source, filename, delimiter, key, units in (
            ("concreteness", "concreteness.csv", ",", "Word", "mean 1..5"),
            ("lancaster", "lancaster_sensorimotor.csv", ",", "Word", "native means 0..5"),
            ("vad", "nrc_vad.txt", "\t", "term", "NRC v2 signed -1..1"),
            (
                "usas",
                "usas/semantic_lexicon_en.tsv",
                "\t",
                "lemma",
                "categorical tags; spaces=alternatives, slash=joint",
            ),
        ):
            path = root / filename
            self._pin(source, [path] if path.exists() else [], units, "LEMMA_POS" if source == "usas" else "WORD")
            if not path.exists():
                continue
            with path.open(encoding="utf-8-sig", newline="") as f:
                for i, row in enumerate(csv.DictReader(f, delimiter=delimiter), 2):
                    word = word_key(row[key])
                    if word not in self.words:
                        continue
                    if source == "usas":
                        values = {"lemma": row[key], "pos": row["pos"], "alternatives": row["semantic_tags"].split()}
                    else:
                        columns = {"Conc.M": "mean"} if source == "concreteness" else {k: k for k in row if k != key}
                        values = {label: float(row[k]) for k, label in columns.items()}
                        if any(not math.isfinite(v) for v in values.values()):
                            raise ValueError(f"nonfinite native rating: {source}:{word}")
                        lower, upper = (-1, 1) if source == "vad" else (1, 5) if source == "concreteness" else (0, 5)
                        if any(not lower <= v <= upper for v in values.values()):
                            raise ValueError(f"native rating outside scale: {source}:{word}")
                    self.records[word][source].append({"record_id": f"{path}:{i}", "values": values})

        path = root / "nrc_emotion.txt"
        self._pin(
            "emotion", [path] if path.exists() else [], "association 0/1; never definitional presence/absence", "WORD"
        )
        grouped: dict[str, dict] = {}
        if path.exists():
            with path.open() as f:
                for i, (raw_word, category, value) in enumerate(csv.reader(f, delimiter="\t"), 1):
                    word = word_key(raw_word)
                    if word not in self.words:
                        continue
                    if value not in {"0", "1"}:
                        raise ValueError("invalid emotion association")
                    record = grouped.setdefault(word, {"record_id": f"{path}:{i}", "values": {}})
                    record["values"][category] = int(value)
        for word, record in grouped.items():
            self.records[word]["emotion"].append(record)

    def _frames(self, root: Path) -> None:
        path = root / "framenet_v17/luIndex.xml"
        self._pin(
            "framenet", [path] if path.exists() else [], "native lexical-unit frame IDs; alternatives", "LEXICAL_UNIT"
        )
        if path.exists():
            for node in ET.parse(path).getroot():
                if node.tag.rsplit("}", 1)[-1] != "lu":
                    continue
                name, pos = node.attrib["name"].rsplit(".", 1)
                word = word_key(name)
                if word in self.words:
                    self.records[word]["framenet"].append(
                        {
                            "record_id": f"{path}#lu={node.attrib['ID']}",
                            "values": {
                                "pos": pos,
                                "frame": node.attrib["frameName"],
                                "frame_id": node.attrib["frameID"],
                            },
                        }
                    )
        paths = sorted((root / "verbnet").glob("*.xml"))
        self._pin("verbnet", paths, "native classes/alternative frame predicates and argument roles", "CLASS_FRAME")

        def visit(node: ET.Element, inherited: tuple[dict, ...], path: Path) -> None:
            # Retain predicate arguments, polarity, frame identity and inheritance;
            # a participant's property is not a word's lexical component.
            frames = tuple(
                {
                    "class": node.attrib["ID"],
                    "frame_index": i,
                    "predicates": [
                        {"predicate": p.attrib, "arguments": [a.attrib for a in p.findall("./ARGS/ARG")]}
                        for p in frame.findall("./SEMANTICS/PRED")
                    ],
                }
                for i, frame in enumerate(node.findall("./FRAMES/FRAME"))
            )
            all_frames = inherited + frames
            for member in node.findall("./MEMBERS/MEMBER"):
                word = word_key(member.attrib["name"])
                if word in self.words:
                    self.records[word]["verbnet"].append(
                        {
                            "record_id": f"{path}#class={node.attrib['ID']}&member={member.attrib['name']}",
                            "values": {"class": node.attrib["ID"], "frames": list(all_frames)},
                        }
                    )
            for child in node.findall("./SUBCLASSES/VNSUBCLASS"):
                visit(child, all_frames, path)

        for path in paths:
            visit(ET.parse(path).getroot(), (), path)

    def for_word(self, word: str) -> dict:
        key = word_key(word)
        records = self.records[key]
        return {
            source["source"]: {
                "status": "UNAVAILABLE"
                if source["status"] == "UNAVAILABLE"
                else "OBSERVED"
                if records.get(source["source"])
                else "NO_RECORD",
                "scope": source["scope"],
                "units": source["units"],
                "records": records.get(source["source"], []),
            }
            for source in self.manifest
        }
