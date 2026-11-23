"""Audit every native VerbNet annotation origin once before lexical expansion."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from gse.lexicon_builder.core import resolve
from gse.lexicon_builder.native_constraints import frame_constraints
from gse.lexicon_builder.registry import RULEBOOK, load_rulebook
from gse.lexicon_builder.sources import NativeSources, sha256


def audit_native(sources: NativeSources, rulebook: dict) -> dict:
    origins = {}
    memberships = 0
    for word in sorted(sources.words):
        for record in sources.for_word(word)["verbnet"]["records"]:
            for frame in record["values"]["frames"]:
                memberships += 1
                key = (frame["class"], frame["frame_index"])
                value = origins.setdefault(key, {"frame": frame, "words": set(), "records": set()})
                if value["frame"] != frame:
                    raise ValueError("one annotation origin has inconsistent native values")
                value["words"].add(word)
                value["records"].add(record["record_id"])
    records, outcomes, predicates = [], Counter(), Counter()
    for (class_id, frame_index), item in sorted(origins.items()):
        constraints = frame_constraints(item["frame"], rulebook)
        for predicate in item["frame"]["predicates"]:
            predicates[predicate["predicate"]["value"]] += 1
        reading_id = f"VerbNet:{class_id}:frame-{frame_index}"
        result = resolve(reading_id, laws=constraints["laws"])
        if any(c["code"] == "SOURCE_CONFLICT_ONE_BINDING" for c in constraints["collisions"]):
            code = "SOURCE_CONFLICT"
        elif constraints["collisions"]:
            code = "UNRESOLVED_PROJECTION_SCOPE"
        else:
            code = "PARTIAL_CONSTRAINED" if constraints["laws"] else "UNMAPPED"
        outcomes[code] += 1
        records.append(
            {
                "reading_id": reading_id,
                "code": code,
                "native": item["frame"],
                "words": sorted(item["words"]),
                "membership_record_ids": sorted(item["records"]),
                "resolution": result.to_json(),
                "bindings": constraints["bindings"],
                "unmapped": constraints["unmapped"],
                "collisions": constraints["collisions"],
            }
        )
    return {
        "schema_version": 1,
        "scope": "NATIVE_ANNOTATION_ORIGINS; not completed word definitions",
        "word_count": len(sources.words),
        "word_class_frame_memberships": memberships,
        "annotation_origins": len(origins),
        "outcomes": dict(outcomes),
        "predicate_inventory": dict(sorted(predicates.items())),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("symbolic-audit",))
    parser.add_argument("--sources", type=Path, default=Path("data/external"))
    parser.add_argument("--nltk", type=Path, default=Path.home() / "nltk_data/corpora")
    parser.add_argument("--rulebook", type=Path, default=RULEBOOK)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = sorted((args.nltk / "verbnet").glob("*.xml"))
    words = sorted({m.attrib["name"] for p in paths for m in ET.parse(p).getroot().iter("MEMBER")})
    if not words:
        parser.error("no native VerbNet members available")
    sources = NativeSources(words, args.sources, args.nltk)
    report = audit_native(sources, load_rulebook(args.rulebook))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output / "manifest.json").write_text(
        json.dumps(
            {
                "sources": sources.manifest,
                "rulebook": str(args.rulebook),
                "rulebook_sha256": sha256(args.rulebook),
                "implementation": {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")},
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {k: report[k] for k in ("word_count", "word_class_frame_memberships", "annotation_origins", "outcomes")},
            indent=2,
        )
    )
    return 0
