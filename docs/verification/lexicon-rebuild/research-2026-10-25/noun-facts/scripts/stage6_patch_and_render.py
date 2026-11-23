"""Stage 6: wording corrections and LU-level fields in noun_facts.json, plus v2 text renderings.

Reads noun_facts.json (stages 4-5), usas_framenet.json (stage 2), adapter_raw.json (stage 1).
Read-only against data and repo; writes only under /tmp/gse-subagents/noun-facts/.
"""

import sys

sys.dont_write_bytecode = True

import json
import re
from pathlib import Path

OUT = Path("/tmp/gse-subagents/noun-facts")
facts = json.loads((OUT / "noun_facts.json").read_text(encoding="utf-8"))
UF = json.loads((OUT / "usas_framenet.json").read_text(encoding="utf-8"))
A = json.loads((OUT / "adapter_raw.json").read_text(encoding="utf-8"))
WORDS = A["words"]

# ------------------------------------------------------------------ JSON corrections
fd = facts["field_documentation"]

fd["verbnet"]["note"] = (
    "The README (quoted verbatim in README_verbatim) describes VerbNet as 'the largest on-line verb lexicon currently available for English'. "
    "The adapter (sources.py) keys each VerbNet record by the MEMBER name alone and keeps no part-of-speech field, so a noun-form word "
    "receives a record whenever a class lists that name as a MEMBER."
)
fd["usas"]["marker_documentation"] = (
    "none in the local files read (semtags.txt, the USAS TSV header, the builder's units string): semtags.txt has no entry for "
    "'+', '-', 'm', 'f', 'n', 'c', '@' or '%'. The only local statements about the tag string are the builder's units string "
    "('spaces=alternatives, slash=joint') and the +/- instruction given with this task (strip +/- to find the category)."
)
facts["usas"]["parse_note"] = (
    "The task said to strip +/- markers to find the category. On the NOUN records of these words most tags carry further trailing "
    "characters (m, f, n, c, @, %), and semtags.txt has no entry for any marker, so stripping +/- alone leaves tags such as S2mf, L2mfn, "
    "A4.1c, S5+c, K5.1@ and B3% unmatched. The parse therefore treats everything after the numeric code (a letter, digits, optional .digits) "
    "as markers, kept verbatim and unglossed; scale_markers_plus_minus and other_marker_characters are separated in the per-word parse. "
    "Category labels are exact semtags.txt lookups with no parent fallback; no category was missing."
)
facts["meta"]["method_disclosure"] = (
    "Records come from gse.lexicon_builder.sources.NativeSources run through Python (-I -B). Further derivations used Python csv, ElementTree, "
    "a regex tag split (USAS marker split; FrameNet markup stripping) and NLTK (WordNet read in place from wordnet.zip). "
    "No shell text search or cut tools were used. All 42 noun-frame files and the documents listed under field_documentation were also read in full with the Read tool."
)
facts["meta"]["scripts"] = [
    "stage1_adapter.py", "stage2_usas_framenet.py", "stage3_wordnet.py", "stage4_assemble.py", "stage5_patch_docs.py",
    "stage6_patch_and_render.py", "show_lu_details.py", "show_wn_docs.py",
]
facts["meta"]["record_id_notes"] = (
    "Record ids are the adapter's record_id strings. For the CSV/TSV sources the number is the file line number with the header row as line 1; "
    "for nrc_emotion.txt (no header) it is the line of the word's first row out of its ten rows; FrameNet ids end in '#lu=<luIndex lu ID>'. "
    "Numeric values are the adapter's parsed floats, not the raw file strings."
)
fd["wordnet"]["zip_sha256"] = facts["wordnet_availability"]["archives"]["wordnet.zip"]["sha256"]

# LU-level fields from the frame files, per word
lu_fields = {}
for w in WORDS:
    rows = []
    for e in UF["per_word"][w]["framenet_noun_records"]:
        lu = e["this_lexUnit_as_listed_in_frame_file__not_retained_by_adapter"]
        rows.append(
            {
                "record_id": e["record_id"],
                "frame": e["frame"],
                "LU_name": lu["attributes"].get("name"),
                "incorporatedFE": lu["attributes"].get("incorporatedFE"),
                "LU_semTypes": [s["name"] for s in lu["semTypes"]],
                "LU_status": lu["attributes"].get("status"),
                "LU_definition_verbatim": lu["definition_raw"],
            }
        )
    lu_fields[w] = rows
facts["framenet"]["noun_LU_fields_in_frame_file_not_retained_by_NativeSources"] = lu_fields

(OUT / "noun_facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
json.loads((OUT / "noun_facts.json").read_text(encoding="utf-8"))  # re-parse check
print("noun_facts.json rewritten and re-parsed OK; bytes:", (OUT / "noun_facts.json").stat().st_size)

# ------------------------------------------------------------------ renderings v2


def rid(r):
    for prefix, tag in (
        ("external:concreteness.csv:", "c"),
        ("external:lancaster_sensorimotor.csv:", "l"),
        ("external:nrc_vad.txt:", "v"),
        ("external:usas/semantic_lexicon_en.tsv:", "u"),
        ("external:nrc_emotion.txt:", "e"),
        ("nltk:framenet_v17/luIndex.xml#lu=", "lu"),
    ):
        if r.startswith(prefix):
            return f"{tag}{r[len(prefix):]}"
    return r


LANC_P = ["Auditory.mean", "Gustatory.mean", "Haptic.mean", "Interoceptive.mean", "Olfactory.mean", "Visual.mean"]
LANC_A = ["Foot_leg.mean", "Hand_arm.mean", "Head.mean", "Mouth.mean", "Torso.mean"]

lines = []
for w in WORDS:
    src = A["adapter"][w]
    lines.append(w)
    c = src["concreteness"]["records"][0]
    v = src["vad"]["records"][0]
    l = src["lancaster"]["records"][0]
    em = src["emotion"]["records"]
    if em:
        ones = [k for k, x in em[0]["values"].items() if x == 1]
        etxt = ("=1: " + ", ".join(ones)) if ones else "all ten 0"
        etxt += f" [{rid(em[0]['record_id'])}]"
    else:
        etxt = "NO_RECORD"
    lines.append(
        f"  conc {c['values']['mean']!r} [{rid(c['record_id'])}] | VAD {v['values']['valence']!r}/{v['values']['arousal']!r}/{v['values']['dominance']!r} [{rid(v['record_id'])}] | emotion {etxt}"
    )
    lines.append(
        f"  Lancaster [{rid(l['record_id'])}] "
        + ",".join(repr(l["values"][k]) for k in LANC_P)
        + " | "
        + ",".join(repr(l["values"][k]) for k in LANC_A)
    )
    up = UF["per_word"][w]
    parts = []
    for key, label in (("usas_NOUN_records_parsed", "NOUN"), ("usas_PROPN_records_parsed", "PROPN"), ("usas_other_pos_records_parsed", None)):
        for rec in up[key]:
            tags = " | ".join(alt["raw"] for alt in rec["alternatives_in_file_order"])
            lab = label or rec["pos"]
            extra = f" lemma={rec['lemma']!r}" if rec["lemma"] != w else ""
            parts.append(f"{lab}{extra} [{rid(rec['record_id'])}]: {tags}")
    lines.append("  USAS " + " ;; ".join(parts))
    fn = []
    for e in up["framenet_noun_records"]:
        lu = e["this_lexUnit_as_listed_in_frame_file__not_retained_by_adapter"]
        bits = [f"lu{e['lu_id']}"]
        if lu["attributes"].get("incorporatedFE"):
            bits.append("incFE=" + lu["attributes"]["incorporatedFE"])
        if lu["semTypes"]:
            bits.append("LUsemType=" + "+".join(s["name"] for s in lu["semTypes"]))
        fn.append(f"{e['frame']}#{e['frame_id']} [{'; '.join(bits)}]")
    other = [f"{e['pos']} {e['frame']}#{e['frame_id']} [{rid(e['record_id'])}]" for e in up["framenet_other_pos_records"]]
    lines.append("  FrameNet n: " + ("; ".join(fn) if fn else "(no noun LU)") + (" ;; other: " + "; ".join(other) if other else ""))
    vn = [r["record_id"].split("nltk:verbnet/", 1)[1] for r in src["verbnet"]["records"]]
    lines.append("  VerbNet: " + ("; ".join(vn) if vn else src["verbnet"]["status"]))
(OUT / "render_per_word_v2.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

# USAS categories: occurrences shown as word(alternative as written in the file)
ucat = []
for cat, info in UF["usas"]["noun_categories_observed"].items():
    seen = []
    for o in info["occurrences"]:
        item = f"{o['word']}({o['alternative_raw']})"
        if item not in seen:
            seen.append(item)
    ucat.append(f"{cat} | {info['label_verbatim'].strip()!r} | markers on NOUN tags: {info['markers_seen_on_noun_records']} | {', '.join(seen)}")
(OUT / "render_usas_categories_v2.txt").write_text("\n".join(ucat) + "\n", encoding="utf-8")

# FrameNet frames: examples removed, markup removed, whitespace collapsed
ABBR = {"Core": "C", "Peripheral": "P", "Extra-Thematic": "X", "Core-Unexpressed": "CU"}
fl = []
for name, fr in UF["framenet"]["noun_frames"].items():
    text = re.sub(r"\s+", " ", fr["definition_stripped_examples_removed"]).strip()
    fes = ", ".join(f"{fe['name']} {ABBR[fe['coreType']]}" for fe in fr["frame_elements"])
    core_st = [f"{fe['name']}={'+'.join(s['name'] for s in fe['semTypes'])}" for fe in fr["frame_elements"] if fe["coreType"] == "Core" and fe["semTypes"]]
    sts = ", ".join(s["name"] for s in fr["frame_semTypes"])
    ws = ", ".join(sorted({x["word"] for x in fr["words_with_noun_lexical_unit_in_this_frame"]}, key=WORDS.index))
    head = f"{name} (#{fr['frame_id']}) <{ws}>"
    if sts:
        head += f" [frame semType: {sts}]"
    fl.append(head)
    fl.append(f"  def: {text}")
    fl.append(f"  FEs: {fes}" + (f"  || Core-FE semTypes: {'; '.join(core_st)}" if core_st else ""))
(OUT / "render_framenet_frames_v2.txt").write_text("\n".join(fl) + "\n", encoding="utf-8")

# semType glossary for the semTypes cited above
ST = facts["framenet"]["semTypes_referenced_by_noun_frames_FEs_and_noun_LUs"]
gl = []
for name, info in ST.items():
    d = re.sub(r"\s+", " ", (info["definition_verbatim"] or "")).strip()
    gl.append(f"{name} (ID {info['ID']}; super: {', '.join(info['superTypes']) or 'none'}): {d}")
(OUT / "render_semtype_glossary.txt").write_text("\n".join(gl) + "\n", encoding="utf-8")
print("renderings v2 written")
