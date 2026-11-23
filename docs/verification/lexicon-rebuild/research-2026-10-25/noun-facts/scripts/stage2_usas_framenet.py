"""Stage 2: USAS tag parsing against semtags.txt, and FrameNet frame / lexical-unit facts.

Reads adapter_raw.json (the unaltered NativeSources output from stage 1). Read-only against the
data and the repo; writes only under /tmp/gse-subagents/noun-facts/.
"""

import sys

sys.dont_write_bytecode = True

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path("/tmp/gse-subagents/noun-facts")
ROOT = Path("/Users/rohanvinaik/Projects/gse/data/external")
FN = Path("/Users/rohanvinaik/nltk_data/corpora/framenet_v17")

raw = json.loads((OUT / "adapter_raw.json").read_text())
WORDS = raw["words"]


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- USAS semtags.txt
semtags_path = ROOT / "usas/semtags.txt"
semtags = {}
for lineno, line in enumerate(semtags_path.read_text(encoding="utf-8").split("\n"), 1):
    if not line:
        continue
    tag, label = line.split("\t", 1)
    assert tag not in semtags, f"duplicate tag {tag}"
    semtags[tag] = {"label": label, "label_stripped": label.strip(), "semtags_txt_line": lineno}

CAT = re.compile(r"^([A-Z]\d+(?:\.\d+)*)(.*)$")


def parse_part(part: str) -> dict:
    m = CAT.match(part)
    if not m:
        return {"raw": part, "category": None, "markers": None, "parse": "UNPARSED"}
    category, markers = m.groups()
    in_semtags = category in semtags
    return {
        "raw": part,
        "category": category,
        "markers": markers,
        "scale_markers_plus_minus": "".join(c for c in markers if c in "+-"),
        "other_marker_characters": "".join(c for c in markers if c not in "+-"),
        "category_in_semtags_txt": in_semtags,
        "category_label": semtags[category]["label_stripped"] if in_semtags else None,
        "category_label_verbatim": semtags[category]["label"] if in_semtags else None,
    }


def parse_usas_record(rec: dict) -> dict:
    v = rec["values"]
    return {
        "record_id": rec["record_id"],
        "lemma": v["lemma"],
        "pos": v["pos"],
        "alternatives_in_file_order": [
            {"alternative_index": i, "raw": alt, "joint_parts": [parse_part(p) for p in alt.split("/")]}
            for i, alt in enumerate(v["alternatives"])
        ],
    }


def cat_sort_key(cat: str):
    m = re.match(r"^([A-Z])(\d+(?:\.\d+)*)$", cat)
    return (m.group(1), tuple(int(x) for x in m.group(2).split("."))) if m else (cat, ())


words_out = {}
usas_noun_categories = {}  # category -> info
usas_noun_markers_seen = set()
usas_pos_by_word = {}

for w in WORDS:
    usas_block = raw["adapter"][w]["usas"]
    noun, propn, other = [], [], []
    for rec in usas_block["records"]:
        parsed = parse_usas_record(rec)
        (noun if parsed["pos"] == "NOUN" else propn if parsed["pos"] == "PROPN" else other).append(parsed)
        if parsed["pos"] == "NOUN":
            for alt in parsed["alternatives_in_file_order"]:
                for part in alt["joint_parts"]:
                    cat = part["category"]
                    info = usas_noun_categories.setdefault(
                        cat,
                        {
                            "category": cat,
                            "in_semtags_txt": part["category_in_semtags_txt"],
                            "label": part["category_label"],
                            "label_verbatim": part["category_label_verbatim"],
                            "semtags_txt_line": semtags[cat]["semtags_txt_line"] if cat in semtags else None,
                            "markers_seen_on_noun_records": [],
                            "occurrences": [],
                        },
                    )
                    if part["markers"] not in info["markers_seen_on_noun_records"]:
                        info["markers_seen_on_noun_records"].append(part["markers"])
                    usas_noun_markers_seen.add(part["markers"])
                    info["occurrences"].append(
                        {
                            "word": w,
                            "record_id": parsed["record_id"],
                            "alternative_raw": alt["raw"],
                            "tag_raw": part["raw"],
                            "markers": part["markers"],
                        }
                    )
    words_out[w] = {
        "usas_NOUN_records_parsed": noun,
        "usas_PROPN_records_parsed": propn,
        "usas_other_pos_records_parsed": other,
    }

usas_noun_categories = dict(sorted(usas_noun_categories.items(), key=lambda kv: cat_sort_key(kv[0])))

# Every category on any record (any pos) that is missing from semtags.txt.
missing_from_semtags = sorted(
    {
        part["category"]
        for w in WORDS
        for key in ("usas_NOUN_records_parsed", "usas_PROPN_records_parsed", "usas_other_pos_records_parsed")
        for rec in words_out[w][key]
        for alt in rec["alternatives_in_file_order"]
        for part in alt["joint_parts"]
        if part["category"] is None or not part["category_in_semtags_txt"]
    },
    key=lambda c: str(c),
)

# ---------------------------------------------------------------- FrameNet
lu_index_path = FN / "luIndex.xml"
lu_root = ET.parse(lu_index_path).getroot()
lu_legend = []
for child in lu_root:
    if local(child.tag) == "legend":
        for st in child:
            lu_legend.append(dict(st.attrib))
lu_attrs = {}
needed_lu_ids = set()
for w in WORDS:
    for rec in raw["adapter"][w]["framenet"]["records"]:
        needed_lu_ids.add(rec["record_id"].rsplit("lu=", 1)[1])
for node in lu_root:
    if local(node.tag) == "lu" and node.attrib["ID"] in needed_lu_ids:
        lu_attrs[node.attrib["ID"]] = dict(node.attrib)
assert set(lu_attrs) == needed_lu_ids, (needed_lu_ids - set(lu_attrs))

frame_cache = {}


def parse_frame(name: str) -> dict:
    if name in frame_cache:
        return frame_cache[name]
    path = FN / "frame" / f"{name}.xml"
    if not path.exists():
        frame_cache[name] = {"status": "UNAVAILABLE", "frame": name, "path": str(path)}
        return frame_cache[name]
    root = ET.parse(path).getroot()
    assert local(root.tag) == "frame"
    info = {
        "status": "AVAILABLE",
        "frame": root.attrib["name"],
        "frame_id": root.attrib["ID"],
        "frame_attributes": dict(root.attrib),
        "file": str(path),
        "file_size_bytes": path.stat().st_size,
        "file_sha256": sha256(path),
        "definition_raw": None,
        "frame_semTypes": [],
        "frame_elements": [],
        "FEcoreSets": [],
        "frameRelations": [],
        "n_lexUnits_in_frame_file": 0,
        "_lexunits": {},
    }
    for child in root:
        t = local(child.tag)
        if t == "definition":
            info["definition_raw"] = child.text or ""
        elif t == "semType":
            info["frame_semTypes"].append(dict(child.attrib))
        elif t == "FE":
            fe = {
                "name": child.attrib["name"],
                "coreType": child.attrib["coreType"],
                "abbrev": child.attrib.get("abbrev"),
                "ID": child.attrib.get("ID"),
                "definition_raw": None,
                "semTypes": [],
                "requiresFE": [],
                "excludesFE": [],
            }
            for sub in child:
                st = local(sub.tag)
                if st == "definition":
                    fe["definition_raw"] = sub.text or ""
                elif st == "semType":
                    fe["semTypes"].append(dict(sub.attrib))
                elif st == "requiresFE":
                    fe["requiresFE"].append(sub.attrib.get("name"))
                elif st == "excludesFE":
                    fe["excludesFE"].append(sub.attrib.get("name"))
            info["frame_elements"].append(fe)
        elif t == "FEcoreSet":
            info["FEcoreSets"].append([m.attrib.get("name") for m in child])
        elif t == "frameRelation":
            info["frameRelations"].append(
                {"type": child.attrib.get("type"), "relatedFrames": [rf.text for rf in child]}
            )
        elif t == "lexUnit":
            info["n_lexUnits_in_frame_file"] += 1
            lu = {
                "attributes": dict(child.attrib),
                "definition_raw": None,
                "sentenceCount": None,
                "lexemes": [],
                "semTypes": [],
            }
            for sub in child:
                st = local(sub.tag)
                if st == "definition":
                    lu["definition_raw"] = sub.text or ""
                elif st == "sentenceCount":
                    lu["sentenceCount"] = dict(sub.attrib)
                elif st == "lexeme":
                    lu["lexemes"].append({**sub.attrib, "text": sub.text})
                elif st == "semType":
                    lu["semTypes"].append(dict(sub.attrib))
            info["_lexunits"][child.attrib["ID"]] = lu
    frame_cache[name] = info
    return info


TAG = re.compile(r"<[^>]+>")
EX = re.compile(r"<ex>.*?</ex>", re.DOTALL)


def strip_markup(text):
    return None if text is None else re.sub(r"[ \t]+", " ", TAG.sub("", text)).strip()


def without_examples(text):
    return None if text is None else strip_markup(EX.sub("", text))


noun_frames = {}  # frame -> info (with words)
for w in WORDS:
    n_recs, other_recs = [], []
    for rec in raw["adapter"][w]["framenet"]["records"]:
        v = rec["values"]
        lu_id = rec["record_id"].rsplit("lu=", 1)[1]
        entry = {
            "record_id": rec["record_id"],
            "lu_id": lu_id,
            "pos": v["pos"],
            "frame": v["frame"],
            "frame_id": v["frame_id"],
            "luIndex_xml_attributes_for_this_lu": lu_attrs[lu_id],
        }
        if v["pos"] == "n":
            fr = parse_frame(v["frame"])
            entry["frame_file"] = fr["file"] if fr["status"] == "AVAILABLE" else None
            entry["frame_file_status"] = fr["status"]
            lu = fr.get("_lexunits", {}).get(lu_id)
            entry["this_lexUnit_as_listed_in_frame_file__not_retained_by_adapter"] = (
                None
                if lu is None
                else {
                    **lu,
                    "definition_stripped": strip_markup(lu["definition_raw"]),
                }
            )
            n_recs.append(entry)
            nf = noun_frames.setdefault(v["frame"], {"words": []})
            nf["words"].append({"word": w, "record_id": rec["record_id"], "lu_id": lu_id})
        else:
            other_recs.append(entry)
    words_out[w]["framenet_noun_records"] = n_recs
    words_out[w]["framenet_other_pos_records"] = other_recs

frames_out = {}
for name in sorted(noun_frames, key=lambda s: s.lower()):
    fr = parse_frame(name)
    if fr["status"] != "AVAILABLE":
        frames_out[name] = {"status": "UNAVAILABLE", "path": fr["path"], "words": noun_frames[name]["words"]}
        continue
    out = {k: v for k, v in fr.items() if k != "_lexunits"}
    out["definition_stripped_markup_removed"] = strip_markup(fr["definition_raw"])
    out["definition_stripped_examples_removed"] = without_examples(fr["definition_raw"])
    for fe in out["frame_elements"]:
        fe["definition_stripped_markup_removed"] = strip_markup(fe["definition_raw"])
    out["words_with_noun_lexical_unit_in_this_frame"] = noun_frames[name]["words"]
    frames_out[name] = out

result = {
    "usas": {
        "semtags_file": str(semtags_path),
        "semtags_sha256": sha256(semtags_path),
        "semtags_n_entries": len(semtags),
        "semtags": semtags,
        "noun_categories_observed": usas_noun_categories,
        "noun_marker_strings_observed": sorted(usas_noun_markers_seen),
        "categories_on_any_checked_record_missing_from_semtags": missing_from_semtags,
    },
    "framenet": {
        "luIndex_file": str(lu_index_path),
        "luIndex_legend_statusType": lu_legend,
        "noun_frames": frames_out,
        "n_noun_frames": len(frames_out),
    },
    "per_word": words_out,
}
(OUT / "usas_framenet.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))

# ---------------------------------------------------------------- compact view to stdout
print("semtags entries:", len(semtags), "| sha256", sha256(semtags_path))
print("luIndex legend:", json.dumps(lu_legend, ensure_ascii=False))
print("\nUSAS NOUN categories observed (category | label_verbatim | markers seen | n occurrences):")
for cat, info in usas_noun_categories.items():
    print(
        f"  {cat!s:8} | {info['label_verbatim']!r} | markers={info['markers_seen_on_noun_records']} | n={len(info['occurrences'])}"
    )
print("\nmarker strings seen on NOUN records:", sorted(usas_noun_markers_seen))
print("categories missing from semtags.txt (any pos):", missing_from_semtags)

print("\nUSAS PROPN / other-pos records:")
for w in WORDS:
    for key in ("usas_PROPN_records_parsed", "usas_other_pos_records_parsed"):
        for rec in words_out[w][key]:
            tags = [alt["raw"] for alt in rec["alternatives_in_file_order"]]
            print(f"  {w:9} {rec['pos']:5} lemma={rec['lemma']!r} {rec['record_id']} {tags}")

print("\nFrameNet noun frames (frame | id | words | n FEs | n LUs in file | file size):")
for name, fr in frames_out.items():
    if fr["status"] != "AVAILABLE":
        print("  ", name, "UNAVAILABLE")
        continue
    ws = [x["word"] for x in fr["words_with_noun_lexical_unit_in_this_frame"]]
    print(
        f"  {name:28} id={fr['frame_id']:5} words={ws} FEs={len(fr['frame_elements'])} LUs={fr['n_lexUnits_in_frame_file']} size={fr['file_size_bytes']}"
        f" def_raw_len={len(fr['definition_raw'])} semTypes={fr['frame_semTypes']}"
    )

print("\nNoun LUs not found inside their frame file:")
for w in WORDS:
    for e in words_out[w]["framenet_noun_records"]:
        if e["this_lexUnit_as_listed_in_frame_file__not_retained_by_adapter"] is None:
            print("  ", w, e["record_id"], e["frame"])
print("done")
