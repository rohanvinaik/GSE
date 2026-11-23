"""Stage 5: add the locally documented meanings read from framenet_v17/docs/book.pdf, and the frame-file
verification result, to noun_facts.json. Run after stage 4. Writes only under /tmp/gse-subagents/noun-facts/.
"""

import sys

sys.dont_write_bytecode = True

import json
from pathlib import Path

OUT = Path("/tmp/gse-subagents/noun-facts")
path = OUT / "noun_facts.json"
facts = json.loads(path.read_text(encoding="utf-8"))

BOOK = "/Users/rohanvinaik/nltk_data/corpora/framenet_v17/docs/book.pdf"
fd = facts["field_documentation"]["framenet"]
fd["local_documents_not_read"] = [
    "docs/GeneralReleaseNotes1.7.pdf",
    "docs/book.pdf except printed pages 1-4 (title, contents), 23-25, 30-31 and 43-46",
]
fd["book_pdf"] = {
    "file": BOOK,
    "title": "FrameNet II: Extended Theory and Practice (Ruppenhofer, Ellsworth, Petruck, Johnson, Baker, Scheffczyk), revised November 1, 2016",
    "how_read": "Read tool, PDF page images; the sentences below were transcribed by eye from those images and should be checked against the PDF before being relied on verbatim",
    "pages_read": "PDF pages 1-4, 23-25, 30-31, 43-46 (printed page number equals PDF page number for these)",
    "coreType_meaning_section": "3.2.1 Coreness, printed pages 23-25",
    "coreType_statements": {
        "p23_three_levels": "We classify frame elements in terms of how central they are to a particular frame, distinguishing three levels: core, peripheral, and extra-thematic. A fourth possible value for this attribute, called core-unexpressed is also discussed below.",
        "p23_core": "A core frame element is one that instantiates a conceptually necessary component of a frame, while making the frame unique and different from other frames.",
        "p24_peripheral": "Frame elements that do not introduce additional, independent or distinct events from the main reported event are characterized as peripheral. Peripheral FEs mark such notions as Time, Place, Manner, Means, Degree, and the like. They do not uniquely characterize a frame, and can be instantiated in any semantically appropriate frame.",
        "p24_extra_thematic": "Extra-thematic frame elements situate an event against a backdrop of another state of affairs, either of an actual event or state of the same type, as illustrated with Iteration, or by evoking a larger frame within which the reported state of affairs is embedded, as shown for Containing_event.",
        "p25_core_unexpressed": "The value \"Core-Unexpressed\" is a special notational shorthand. It is assigned to FEs that behave like core frame elements in the frame where they are marked as Core-unexpressed but which, counter to expectation, may not be used for annotation in descendants of that frame.",
        "p25_artifacts_and_natural_kinds": "Coreness marking makes the most sense for event and state frames, and in these frames we use all three statuses. Coreness marking is done at the level of the frame and is intended to be consistent for all lexical units in a frame. In frames whose LUs are artifacts or natural kinds, we only use a two-way distinction (core and peripheral), noting that the values do not have exactly the same meaning as with events. In such cases, typically there is just one core frame element which is marked on the target word. For instance, in the Clothing frame the FE Clothing is core, and all other FEs are peripheral.",
    },
    "incorporatedFE_meaning_section": "3.2.4 Incorporation, printed page 30",
    "incorporatedFE_statements": {
        "p30_definition": "There are many frames containing verbs which generally involve a particular of frame element, but where some of the verbs incorporate information about that frame element in their definition.",
        "p30_examples_given_are_verbs": "the section's examples are verbs: wagging a tail, arching brows, smile/grimace/frown/pout/scowl, and in the Placing frame the verbs bag.v, bin.v, bottle.v, box.v, cage.v, crate.v, file.v, garage.v incorporating the Goal FE",
        "p30_where_recorded": "In defining a new LU, one can specify an incorporated FE; the information as to what FE is incorporated in each LU is recorded in both the frame XML file and the LU XML file, and is displayed in the lexical entry report.",
    },
    "documentation_not_found_in_pages_read": [
        "a fuller explanation of the semantic type 'Transparent Noun' (semTypes.xml gives only the definition 'Transparent noun.'); pages 43-46 cover support verbs, copulas, existential sentences and controllers instead",
    ],
    "documentation_vs_data_difference": "book p.25 says that in the Clothing frame 'the FE Clothing is core'; framenet_v17/frame/Clothing.xml has no FE named Clothing and its single Core FE is Garment (all ten others are Peripheral).",
}

facts["meta"]["frame_file_verification"] = (
    "All 42 noun-frame files under /Users/rohanvinaik/nltk_data/corpora/framenet_v17/frame/ were read in full with the Read tool "
    "(Leadership, Natural_features, Containers and Clothing in two chunks each because of the per-read size cap). In every file the frame "
    "definition text, the FE names and each FE coreType agreed with the ElementTree extraction stored in framenet.noun_frames. No discrepancy was found."
)
facts["meta"]["scripts"] = [
    "stage1_adapter.py", "stage2_usas_framenet.py", "stage3_wordnet.py", "stage4_assemble.py", "stage5_patch_docs.py",
]
for name, fr in facts["framenet"]["noun_frames"].items():
    fr["file_read_in_full_with_Read_tool"] = True

path.write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")

check = json.loads(path.read_text(encoding="utf-8"))
print("noun_facts.json bytes:", path.stat().st_size)
print("top-level keys:", list(check))
print("words:", len(check["words"]), "| noun frames:", len(check["framenet"]["noun_frames"]), "| usas noun categories:", len(check["usas"]["noun_categories_observed"]))
print("frames flagged read:", sum(1 for f in check["framenet"]["noun_frames"].values() if f.get("file_read_in_full_with_Read_tool")))
