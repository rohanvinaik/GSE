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


def portable_id(root_tag: str, root: Path, path: Path) -> str:
    """A source file's identity without a machine path: its root tag and path within that root."""
    return f"{root_tag}:{path.relative_to(root).as_posix()}"


def _children(node: ET.Element, name: str) -> list[ET.Element]:
    """Direct children, including the namespaced FrameNet distribution."""
    return [child for child in node if child.tag.rsplit("}", 1)[-1] == name]


def _definition(node: ET.Element) -> str:
    return "".join(_children(node, "definition")[0].itertext()) if _children(node, "definition") else ""


def _native_tree(node: ET.Element) -> dict:
    """Preserve native AND/OR trees and syntactic roles without interpreting them."""
    return {
        "tag": node.tag.rsplit("}", 1)[-1],
        "attributes": dict(node.attrib),
        "text": node.text.strip() if node.text else "",
        "children": [_native_tree(child) for child in node],
    }


class NativeSources:
    """Batch lookup with source absence, alternatives and native units intact."""

    def __init__(self, words: list[str] | None, root: Path, nltk_root: Path):
        self.collect_all = words is None
        self.words = {word_key(w) for w in words or []}
        if (not self.collect_all and not self.words) or "" in self.words:
            raise ValueError("nonempty words are required")
        self.records: dict[str, dict[str, list[dict]]] = {w: defaultdict(list) for w in self.words}
        self.manifest: list[dict] = []
        self._tables(root)
        self._frames(nltk_root)

    def _accept(self, word: str) -> bool:
        if self.collect_all and word:
            self.words.add(word)
            self.records.setdefault(word, defaultdict(list))
        return word in self.words

    def _pin(self, source: str, paths: list[Path], units: str, scope: str, root_tag: str, root: Path) -> None:
        self.manifest.append(
            {
                "source": source,
                "units": units,
                "scope": scope,
                "status": "AVAILABLE" if paths else "UNAVAILABLE",
                "files": [{"path": str(p), "id": portable_id(root_tag, root, p), "sha256": sha256(p)} for p in paths],
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
            self._pin(
                source,
                [path] if path.exists() else [],
                units,
                "LEMMA_POS" if source == "usas" else "WORD",
                "external",
                root,
            )
            if not path.exists():
                continue
            file_id = portable_id("external", root, path)
            with path.open(encoding="utf-8-sig", newline="") as f:
                for i, row in enumerate(csv.DictReader(f, delimiter=delimiter), 2):
                    word = word_key(row[key])
                    if not self._accept(word):
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
                    self.records[word][source].append({"record_id": f"{file_id}:{i}", "values": values})

        path = root / "nrc_emotion.txt"
        self._pin(
            "emotion",
            [path] if path.exists() else [],
            "association 0/1; never definitional presence/absence",
            "WORD",
            "external",
            root,
        )
        grouped: dict[str, dict] = {}
        if path.exists():
            file_id = portable_id("external", root, path)
            with path.open() as f:
                for i, (raw_word, category, value) in enumerate(csv.reader(f, delimiter="\t"), 1):
                    word = word_key(raw_word)
                    if not self._accept(word):
                        continue
                    if value not in {"0", "1"}:
                        raise ValueError("invalid emotion association")
                    record = grouped.setdefault(word, {"record_id": f"{file_id}:{i}", "values": {}})
                    record["values"][category] = int(value)
        for word, record in grouped.items():
            self.records[word]["emotion"].append(record)

    def _frames(self, root: Path) -> None:
        self._framenet(root)
        paths = sorted((root / "verbnet").glob("*.xml"))
        self._pin(
            "verbnet",
            paths,
            "native classes/alternative frame predicates, roles and restriction trees",
            "CLASS_FRAME",
            "nltk",
            root,
        )

        def visit(
            node: ET.Element, inherited: tuple[dict, ...], inherited_roles: dict[str, dict], file_id: str
        ) -> None:
            roles = dict(inherited_roles)
            for role in node.findall("./THEMROLES/THEMROLE"):
                roles[role.attrib["type"]] = {
                    "role": role.attrib["type"],
                    "defined_in": node.attrib["ID"],
                    "record_id": f"{file_id}#class={node.attrib['ID']}&role={role.attrib['type']}",
                    "restrictions": [_native_tree(child) for child in role],
                }
            frames = tuple(
                {
                    "class": node.attrib["ID"],
                    "frame_index": i,
                    "record_id": f"{file_id}#class={node.attrib['ID']}&frame={i}",
                    "role_restrictions": list(roles.values()),
                    "description": [dict(d.attrib) for d in frame.findall("./DESCRIPTION")],
                    "examples": ["".join(e.itertext()) for e in frame.findall("./EXAMPLES/EXAMPLE")],
                    "syntax": [_native_tree(s) for s in frame.findall("./SYNTAX")],
                    "predicates": [
                        {"predicate": dict(p.attrib), "arguments": [dict(a.attrib) for a in p.findall("./ARGS/ARG")]}
                        for p in frame.findall("./SEMANTICS/PRED")
                    ],
                }
                for i, frame in enumerate(node.findall("./FRAMES/FRAME"))
            )
            all_frames = inherited + frames
            for member in node.findall("./MEMBERS/MEMBER"):
                word = word_key(member.attrib["name"])
                if self._accept(word):
                    self.records[word]["verbnet"].append(
                        {
                            "record_id": f"{file_id}#class={node.attrib['ID']}&member={member.attrib['name']}",
                            "values": {
                                "class": node.attrib["ID"],
                                "member": dict(member.attrib),
                                "frames": list(all_frames),
                                "effective_role_restrictions": list(roles.values()),
                            },
                        }
                    )
            for child in node.findall("./SUBCLASSES/VNSUBCLASS"):
                visit(child, all_frames, roles, file_id)

        for path in paths:
            visit(ET.parse(path).getroot(), (), {}, portable_id("nltk", root, path))

    def _framenet(self, root: Path) -> None:
        """Locate lexical facts; frame participants are not lexical components.

        The frame file supplies the native LU definition, incorporated FE and
        semantic types. A noun LU's DEN valences are independent target-role
        evidence; incorporation alone is not identity (child incorporates Age).
        """
        corpus = root / "framenet_v17"
        path = corpus / "luIndex.xml"
        used: set[Path] = {path} if path.exists() else set()
        frames: dict[str, tuple[ET.Element, str] | None] = {}
        semtypes_path = corpus / "semTypes.xml"
        semtypes: dict[str, dict] = {}
        if path.exists() and semtypes_path.exists():
            used.add(semtypes_path)
            semtypes_id = portable_id("nltk", root, semtypes_path)
            for node in ET.parse(semtypes_path).getroot():
                if node.tag.rsplit("}", 1)[-1] == "semType":
                    semtypes[node.attrib["ID"]] = {
                        **node.attrib,
                        "definition": _definition(node),
                        "supertypes": [dict(s.attrib) for s in _children(node, "superType")],
                        "record_id": f"{semtypes_id}#semType={node.attrib['ID']}",
                    }

        def types(node: ET.Element) -> list[dict]:
            return [{**t.attrib, **semtypes.get(t.attrib.get("ID", ""), {})} for t in _children(node, "semType")]

        if path.exists():
            file_id = portable_id("nltk", root, path)
            for node in ET.parse(path).getroot():
                if node.tag.rsplit("}", 1)[-1] != "lu":
                    continue
                name, pos = node.attrib["name"].rsplit(".", 1)
                word = word_key(name)
                if self._accept(word):
                    frame_name = node.attrib["frameName"]
                    if frame_name not in frames:
                        frame_path = corpus / "frame" / f"{frame_name}.xml"
                        if frame_path.exists():
                            used.add(frame_path)
                            frames[frame_name] = (ET.parse(frame_path).getroot(), portable_id("nltk", root, frame_path))
                        else:
                            frames[frame_name] = None
                    detail = frames[frame_name]
                    values = {
                        "pos": pos,
                        "lu_id": node.attrib["ID"],
                        "frame": frame_name,
                        "frame_id": node.attrib["frameID"],
                        "detail_status": "FRAME_DETAIL_UNAVAILABLE",
                        "source_record_ids": [f"{file_id}#lu={node.attrib['ID']}"],
                        "semantic_types": [],
                        "incorporated_fes": [],
                        "target_role_evidence": [],
                        "frame_elements": [],
                    }
                    if detail is not None:
                        frame, frame_id = detail
                        values.update(
                            frame_definition=_definition(frame),
                            frame_semantic_types=types(frame),
                            frame_elements=[
                                {
                                    **fe.attrib,
                                    "definition": _definition(fe),
                                    "semantic_types": types(fe),
                                    "record_id": f"{frame_id}#FE={fe.attrib['ID']}",
                                }
                                for fe in _children(frame, "FE")
                            ],
                            detail_status="LU_DETAIL_UNAVAILABLE",
                        )
                        values["source_record_ids"].append(f"{frame_id}#frame={frame.attrib['ID']}")
                        for lu in _children(frame, "lexUnit"):
                            if lu.attrib["ID"] != node.attrib["ID"]:
                                continue
                            lu_id = f"{frame_id}#lexUnit={lu.attrib['ID']}"
                            values.update(
                                definition=_definition(lu),
                                semantic_types=types(lu),
                                incorporated_fes=[lu.attrib["incorporatedFE"]] if lu.get("incorporatedFE") else [],
                                detail_status="AVAILABLE",
                            )
                            values["source_record_ids"].append(lu_id)
                            if lu.get("incorporatedFE"):
                                values["target_role_evidence"].append(
                                    {
                                        "kind": "INCORPORATED_FE",
                                        "frame_element": lu.attrib["incorporatedFE"],
                                        "record_id": lu_id,
                                    }
                                )
                            break
                    # DEN identifies denotation in the native valence schema. It
                    # is not inferred from the presence of an FE in a frame.
                    lu_path = corpus / "lu" / f"lu{node.attrib['ID']}.xml"
                    if pos.casefold() == "n" and lu_path.exists():
                        used.add(lu_path)
                        lu_file_id = portable_id("nltk", root, lu_path)
                        for _, element in ET.iterparse(lu_path, events=("end",)):
                            if element.tag.rsplit("}", 1)[-1] != "valences":
                                continue
                            for i, realization in enumerate(element):
                                for j, pattern in enumerate(_children(realization, "pattern")):
                                    for k, unit in enumerate(_children(pattern, "valenceUnit")):
                                        if unit.get("PT") == "DEN":
                                            values["target_role_evidence"].append(
                                                {
                                                    "kind": "DEN_VALENCE",
                                                    "frame_element": unit.attrib["FE"],
                                                    "attributes": dict(unit.attrib),
                                                    "record_id": f"{lu_file_id}#valences/{i}/pattern/{j}/unit/{k}",
                                                }
                                            )
                            break
                        values["source_record_ids"].append(lu_file_id)
                    self.records[word]["framenet"].append(
                        {
                            "record_id": f"{file_id}#lu={node.attrib['ID']}",
                            "values": values,
                        }
                    )
        self._pin(
            "framenet",
            sorted(used),
            "native lexical-unit alternatives, semantic types, incorporated FEs and denotation valences",
            "LEXICAL_UNIT",
            "nltk",
            root,
        )

    def for_word(self, word: str) -> dict:
        key = word_key(word)
        records = self.records.get(key, {})
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
