"""Stage 4: assemble noun_facts.json and text renderings from the stage 1-3 outputs.

Read-only against the data and the repo; writes only under /tmp/gse-subagents/noun-facts/.
"""

import sys

sys.dont_write_bytecode = True

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path("/tmp/gse-subagents/noun-facts")
ROOT = Path("/Users/rohanvinaik/Projects/gse/data/external")
NLTK = Path("/Users/rohanvinaik/nltk_data/corpora")
FN = NLTK / "framenet_v17"
VN = NLTK / "verbnet"

A = json.loads((OUT / "adapter_raw.json").read_text(encoding="utf-8"))
UF = json.loads((OUT / "usas_framenet.json").read_text(encoding="utf-8"))
WN = json.loads((OUT / "wordnet.json").read_text(encoding="utf-8"))
WORDS = A["words"]


def local(tag):
    return tag.rsplit("}", 1)[-1]


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ semTypes.xml
st_root = ET.parse(FN / "semTypes.xml").getroot()
semtypes_all = {}
for st in st_root:
    if local(st.tag) != "semType":
        continue
    d, sups = None, []
    for c in st:
        if local(c.tag) == "definition":
            d = c.text
        elif local(c.tag) == "superType":
            sups.append(c.attrib.get("superTypeName"))
    semtypes_all[st.attrib["name"]] = {
        "ID": st.attrib["ID"],
        "abbrev": st.attrib.get("abbrev"),
        "definition_verbatim": d,
        "superTypes": sups,
    }

referenced = {}  # name -> where


def note(name, where):
    referenced.setdefault(name, [])
    if where not in referenced[name]:
        referenced[name].append(where)


for fname, fr in UF["framenet"]["noun_frames"].items():
    for s in fr["frame_semTypes"]:
        note(s["name"], f"frame:{fname}")
    for fe in fr["frame_elements"]:
        for s in fe["semTypes"]:
            note(s["name"], f"FE:{fname}.{fe['name']}")
for w in WORDS:
    for e in UF["per_word"][w]["framenet_noun_records"]:
        for s in e["this_lexUnit_as_listed_in_frame_file__not_retained_by_adapter"]["semTypes"]:
            note(s["name"], f"LU:{e['record_id']}")
semtypes_referenced = {
    name: {**semtypes_all[name], "referenced_by": referenced[name]} for name in sorted(referenced) if name in semtypes_all
}
semtypes_unresolved = sorted(n for n in referenced if n not in semtypes_all)

# ------------------------------------------------------------------ VerbNet member attributes (present in file, not retained)
vn_members = {}
for w in WORDS:
    lst = []
    for rec in A["adapter"][w]["verbnet"]["records"]:
        rid = rec["record_id"]
        file_part, frag = rid.split("#", 1)
        fname = file_part.split("nltk:verbnet/", 1)[1]
        cls = frag.split("class=", 1)[1].split("&member=", 1)[0]
        member = frag.split("&member=", 1)[1]
        root = ET.parse(VN / fname).getroot()
        found = None
        for node in root.iter():
            if local(node.tag) in ("VNCLASS", "VNSUBCLASS") and node.attrib.get("ID") == cls:
                for m in node.findall("./MEMBERS/MEMBER"):
                    if m.attrib.get("name") == member:
                        found = dict(m.attrib)
        lst.append({"record_id": rid, "member_element_attributes_in_file__not_retained_by_adapter": found})
    vn_members[w] = lst

# ------------------------------------------------------------------ field documentation (local sources only)
man = {m["source"]: m for m in A["manifest"]}
hdr = A["headers"]
fn_readme = (FN / "README.txt").read_text(encoding="utf-8")
vn_readme = (VN / "README").read_text(encoding="utf-8")
wn_docs = WN["availability"]["wordnet_zip_small_documentation_members"]

field_documentation = {
    "rule": "Only statements found in local files are quoted. Where a source has no local documentation beyond its header row and the builder's units string, that is stated and nothing is supplied from memory.",
    "concreteness": {
        "builder_scope": man["concreteness"]["scope"],
        "builder_units_string": man["concreteness"]["units"],
        "file": hdr["concreteness"]["file"],
        "header_columns": hdr["concreteness"]["columns_in_file"],
        "adapter_retains": hdr["concreteness"]["columns_retained_by_adapter"],
        "adapter_does_not_retain": hdr["concreteness"]["columns_not_retained_by_adapter"],
        "local_documentation": "none beyond the header row and the builder's units string",
    },
    "lancaster": {
        "builder_scope": man["lancaster"]["scope"],
        "builder_units_string": man["lancaster"]["units"],
        "file": hdr["lancaster"]["file"],
        "header_columns": hdr["lancaster"]["columns_in_file"],
        "adapter_retains": hdr["lancaster"]["columns_retained_by_adapter"],
        "local_documentation": "none beyond the header row and the builder's units string",
    },
    "vad": {
        "builder_scope": man["vad"]["scope"],
        "builder_units_string": man["vad"]["units"],
        "file": hdr["vad"]["file"],
        "header_columns": hdr["vad"]["columns_in_file"],
        "adapter_retains": hdr["vad"]["columns_retained_by_adapter"],
        "local_documentation": "none beyond the header row and the builder's units string",
    },
    "emotion": {
        "builder_scope": man["emotion"]["scope"],
        "builder_units_string": man["emotion"]["units"],
        "file": str(ROOT / "nrc_emotion.txt"),
        "file_shape": "no header row; tab-separated word, category, 0-or-1 (first line is %r)" % (A["nrc_emotion_first_row_no_header"],),
        "adapter_record": "one record per word: values maps each category to 0/1; record_id is the file line of the word's first row",
        "local_documentation": "none beyond the file shape and the builder's units string",
    },
    "usas": {
        "builder_scope": man["usas"]["scope"],
        "builder_units_string": man["usas"]["units"],
        "file": hdr["usas"]["file"],
        "header_columns": hdr["usas"]["columns_in_file"],
        "adapter_retains": hdr["usas"]["columns_retained_by_adapter"],
        "pos_values_in_whole_file": A["usas_pos_counts_whole_file"],
        "category_labels_file": UF["usas"]["semtags_file"],
        "category_labels_file_sha256": UF["usas"]["semtags_sha256"],
        "category_labels_file_shape": "one line per category: tag, TAB, label (%d entries); the file lists categories only" % UF["usas"]["semtags_n_entries"],
        "marker_strings_observed_on_noun_records": UF["usas"]["noun_marker_strings_observed"],
        "marker_documentation": "none locally: semtags.txt has no entry for '+', '-', 'm', 'f', 'n', 'c', '@' or '%', and no other local file explains them. The only local statements about the tag string are the builder's units string ('spaces=alternatives, slash=joint') and the +/- instruction given with this task (strip +/- to find the category).",
        "label_irregularities_in_semtags_txt": "verbatim labels are kept in the JSON: I3.2 reads 'Work and employmeny: Professionalism' (as in the file); A6.2 and N1 labels carry a trailing space in the file",
    },
    "framenet": {
        "builder_scope": man["framenet"]["scope"],
        "builder_units_string": man["framenet"]["units"],
        "adapter_record_fields": {
            "pos": "text after the last '.' in the luIndex.xml lu name (for example 'hand.n' gives 'n')",
            "frame": "luIndex.xml lu attribute frameName",
            "frame_id": "luIndex.xml lu attribute frameID",
            "record_id": "luIndex.xml path plus '#lu=' plus the lu ID attribute",
        },
        "luIndex_lu_element_attributes_declared_in_luIndex_xsd": ["ID", "name", "status", "frameName", "frameID", "hasAnnotation", "numAnnotInstances"],
        "luIndex_status_legend_verbatim": UF["framenet"]["luIndex_legend_statusType"],
        "frame_file_lexUnit_attributes_declared_in_commonTypes_xsd": ["ID", "name", "POS", "incorporatedFE", "status", "cDate", "cBy", "lemmaID"],
        "POS_enumeration_commonTypes_xsd": ["A", "ADV", "ART", "AVP", "C", "CCON", "IDIO", "INTJ", "N", "NUM", "PREP", "PRON", "SCON", "V"],
        "FE_coreType_enumeration_commonTypes_xsd": ["Core", "Peripheral", "Extra-Thematic", "Core-Unexpressed"],
        "coreType_meaning_in_schema_files": "none: commonTypes.xsd lists the four values and gives no description of them",
        "R1.5XMLDocumentation_txt_statements_quoted": [
            "Frame and FE definitions in the XML contain all the information in our database.",
            "Coreness Set, or CoreSet, information, which was not available in earlier XML formats, has been added to the frame XML report.",
            "FE elements may now optionally contain <requiresFE> and <excludesFE> elements which encode the requires and excludes relations between FEs in the same frame.",
            "Rather than outlining the structure of each of the XML document types here, we refer users to the XML Schema files provided with this release.",
        ],
        "README_txt_verbatim": fn_readme,
        "local_documents_not_read": [
            "docs/book.pdf (FrameNet II: Extended Theory and Practice, annotator's manual, 129 pages)",
            "docs/GeneralReleaseNotes1.7.pdf",
        ],
    },
    "verbnet": {
        "builder_scope": man["verbnet"]["scope"],
        "builder_units_string": man["verbnet"]["units"],
        "adapter_record_fields": {
            "record_id": "file path plus '#class=<class or subclass ID>&member=<MEMBER name>'",
            "values.class": "ID of the VNCLASS or VNSUBCLASS holding the MEMBER",
            "values.frames": "that class's FRAMES plus every inherited ancestor class's FRAMES, each with its SEMANTICS/PRED predicates and ARG attributes",
        },
        "README_verbatim": vn_readme,
        "dtd_statements": "vn_class-3.dtd declares structure only; MEMBER has attributes name and wn; PRED has bool and value; ARG type is one of Event, ThemRole, VerbSpecific, Constant",
        "note": "Every VerbNet MEMBER is a verb lemma; a noun-form word has a VerbNet record only because the same lemma is also a verb member.",
    },
    "wordnet": {
        "directory_corpora_wordnet": WN["availability"]["directory_corpora_wordnet"],
        "directory_exists": WN["availability"]["directory_corpora_wordnet_exists"],
        "archives_present": WN["availability"]["archives"],
        "read_from": "wordnet.zip, read in place by NLTK (nothing unzipped); reader reports version %s; NLTK %s" % (
            WN["availability"]["wordnet_version_reported_by_reader"], WN["availability"]["nltk_version"]),
        "lexnames_member_verbatim": wn_docs.get("wordnet/lexnames"),
        "README_member_verbatim": wn_docs.get("wordnet/README"),
        "local_documentation_of_lexname_meaning": "none: the lexnames member lists lexicographer file names with numbers only",
    },
}

# ------------------------------------------------------------------ per-word assembly
words = {}
for w in WORDS:
    words[w] = {
        "native_sources_via_NativeSources_for_word": A["adapter"][w],
        "usas_parsed": {
            "NOUN_records": UF["per_word"][w]["usas_NOUN_records_parsed"],
            "PROPN_records": UF["per_word"][w]["usas_PROPN_records_parsed"],
            "other_pos_records": UF["per_word"][w]["usas_other_pos_records_parsed"],
        },
        "framenet": {
            "noun_lexical_unit_records": UF["per_word"][w]["framenet_noun_records"],
            "other_pos_lexical_unit_records": UF["per_word"][w]["framenet_other_pos_records"],
            "frame_definitions": "see top-level framenet.noun_frames[<frame name>]",
        },
        "verbnet_member_attributes_present_in_file": vn_members[w],
        "wordnet_noun_synsets": WN["per_word"][w],
    }

facts = {
    "meta": {
        "purpose": "Fact-gathering only for the noun-head contract: what the local native sources contain for 33 nouns, and what each field is documented to mean. No head, prime or rule is decided or suggested here.",
        "words": WORDS,
        "interpreter": "/Users/rohanvinaik/Projects/gse/.claude/worktrees/lexicon-builder/gse/.venv/bin/python (run with -I -B)",
        "worktree": A["worktree"],
        "sources_py_used": A["sources_py"],
        "data_root": A["root"],
        "nltk_root": A["nltk_root"],
        "adapter": "gse.lexicon_builder.sources.NativeSources(words, root, nltk_root).for_word(word); output stored unaltered under words.<word>.native_sources_via_NativeSources_for_word",
        "scripts": ["stage1_adapter.py", "stage2_usas_framenet.py", "stage3_wordnet.py", "stage4_assemble.py"],
        "labelled_derivations": [
            "usas_parsed: each alternative split on '/', category = leading letter+digits(.digits)*, markers = the remainder, verbatim; category label looked up exactly in semtags.txt (no parent fallback)",
            "framenet frame definitions: definition_raw is the XML text as parsed (still carrying FrameNet markup); *_stripped_* are regex markup removals labelled as such",
            "wordnet: wn.synsets(word, 'n') applies morphy; exact_word_in_lemma_names marks synsets whose lemma_names contain the word itself",
        ],
    },
    "source_manifest": A["manifest"],
    "field_documentation": field_documentation,
    "usas": UF["usas"],
    "framenet": {
        **UF["framenet"],
        "semTypes_referenced_by_noun_frames_FEs_and_noun_LUs": semtypes_referenced,
        "semTypes_referenced_but_not_found_in_semTypes_xml": semtypes_unresolved,
        "semTypes_xml_file": str(FN / "semTypes.xml"),
        "semTypes_xml_sha256": sha256(FN / "semTypes.xml"),
    },
    "wordnet_availability": WN["availability"],
    "words": words,
}
(OUT / "noun_facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
print("noun_facts.json bytes:", (OUT / "noun_facts.json").stat().st_size)
print("semTypes referenced:", sorted(semtypes_referenced), "| unresolved:", semtypes_unresolved)

# ------------------------------------------------------------------ text renderings
CORE_ABBR = {"Core": "C", "Peripheral": "P", "Extra-Thematic": "X", "Core-Unexpressed": "CU"}


def rid_short(rid):
    for prefix, tag in (
        ("external:concreteness.csv:", "c"),
        ("external:lancaster_sensorimotor.csv:", "l"),
        ("external:nrc_vad.txt:", "v"),
        ("external:usas/semantic_lexicon_en.tsv:", "u"),
        ("external:nrc_emotion.txt:", "e"),
        ("nltk:framenet_v17/luIndex.xml#lu=", "lu"),
    ):
        if rid.startswith(prefix):
            return f"{tag}{rid[len(prefix):]}"
    return rid


LANC = [
    ("Auditory.mean", "Aud"), ("Gustatory.mean", "Gus"), ("Haptic.mean", "Hap"), ("Interoceptive.mean", "Int"),
    ("Olfactory.mean", "Olf"), ("Visual.mean", "Vis"), ("Foot_leg.mean", "Foot"), ("Hand_arm.mean", "Hand"),
    ("Head.mean", "Head"), ("Mouth.mean", "Mouth"), ("Torso.mean", "Torso"),
]
lines = []
for w in WORDS:
    src = A["adapter"][w]
    lines.append(w)

    def one(name):
        recs = src[name]["records"]
        return recs[0] if recs else None

    c, v, e, l = one("concreteness"), one("vad"), one("emotion"), one("lancaster")
    parts = []
    parts.append(f"conc mean={c['values']['mean']!r} [{rid_short(c['record_id'])}]" if c else f"conc {src['concreteness']['status']}")
    parts.append(
        f"VAD valence={v['values']['valence']!r} arousal={v['values']['arousal']!r} dominance={v['values']['dominance']!r} [{rid_short(v['record_id'])}]"
        if v else f"VAD {src['vad']['status']}"
    )
    if e:
        ones = [k for k, x in e["values"].items() if x == 1]
        parts.append(f"emotion {'=1: ' + ', '.join(ones) if ones else 'all ten = 0'} [{rid_short(e['record_id'])}]")
    else:
        parts.append(f"emotion {src['emotion']['status']}")
    lines.append("  " + " | ".join(parts))
    if l:
        lines.append(
            f"  Lancaster [{rid_short(l['record_id'])}] " + ", ".join(f"{ab} {l['values'][k]!r}" for k, ab in LANC)
        )
    else:
        lines.append(f"  Lancaster {src['lancaster']['status']}")
    up = UF["per_word"][w]
    ulines = []
    for key, label in (("usas_NOUN_records_parsed", "NOUN"), ("usas_PROPN_records_parsed", "PROPN"), ("usas_other_pos_records_parsed", None)):
        for rec in up[key]:
            tags = " | ".join(alt["raw"] for alt in rec["alternatives_in_file_order"])
            lab = label or rec["pos"]
            extra = f" lemma={rec['lemma']!r}" if rec["lemma"] != w else ""
            ulines.append(f"{lab}{extra} [{rid_short(rec['record_id'])}]: {tags}")
    lines.append("  USAS " + " ;; ".join(ulines))
    fn_n = [f"{e['frame']}#{e['frame_id']} [{rid_short(e['record_id'])}]" for e in up["framenet_noun_records"]]
    fn_o = [f"{e['pos']} {e['frame']}#{e['frame_id']} [{rid_short(e['record_id'])}]" for e in up["framenet_other_pos_records"]]
    lines.append("  FrameNet n: " + ("; ".join(fn_n) if fn_n else "(no noun LU)") + (" ;; other: " + "; ".join(fn_o) if fn_o else ""))
    vn = [r["record_id"].split("nltk:verbnet/", 1)[1] for r in src["verbnet"]["records"]]
    lines.append("  VerbNet: " + ("; ".join(vn) if vn else src["verbnet"]["status"]))
(OUT / "render_per_word.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

ucat = []
for cat, info in UF["usas"]["noun_categories_observed"].items():
    uses = ", ".join(f"{o['word']}({o['tag_raw']})" for o in info["occurrences"])
    ucat.append(
        f"{cat} | {info['label_verbatim']!r} | semtags.txt line {info['semtags_txt_line']} | markers seen: {info['markers_seen_on_noun_records']} | {uses}"
    )
(OUT / "render_usas_categories.txt").write_text("\n".join(ucat) + "\n", encoding="utf-8")

fl = []
for name, fr in UF["framenet"]["noun_frames"].items():
    ws = ", ".join(f"{x['word']}" for x in fr["words_with_noun_lexical_unit_in_this_frame"])
    fes = ", ".join(f"{fe['name']} ({CORE_ABBR.get(fe['coreType'], fe['coreType'])})" for fe in fr["frame_elements"])
    sts = ", ".join(s["name"] for s in fr["frame_semTypes"]) or "none"
    fl.append(f"{name} (frame ID {fr['frame_id']}) | noun LUs for: {ws} | frame semType: {sts}")
    fl.append(f"  definition (raw XML text): {fr['definition_raw']!r}")
    fl.append(f"  definition (markup removed): {fr['definition_stripped_markup_removed']!r}")
    fl.append(f"  FEs: {fes}")
(OUT / "render_framenet_frames.txt").write_text("\n".join(fl) + "\n", encoding="utf-8")

wl = []
for w in WORDS:
    pw = WN["per_word"][w]
    seq = []
    for e in pw["synsets"]:
        seq.append(e["lexname"] + ("" if e["exact_word_in_lemma_names"] else "*"))
    wl.append(f"{w}: {pw['n_noun_synsets']} noun synsets (in NLTK order): " + ", ".join(seq))
(OUT / "render_wordnet_lexnames.txt").write_text("\n".join(wl) + "\n", encoding="utf-8")
print("renderings written")
