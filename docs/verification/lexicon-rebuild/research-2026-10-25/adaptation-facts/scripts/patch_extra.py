"""Add the late-arriving sources and the drift record to the part files.

Edits only /tmp/gse-subagents/adaptation-facts/parts/*.json.
"""

import json
from pathlib import Path

PARTS = Path("/tmp/gse-subagents/adaptation-facts/parts")


def load(name):
    return json.loads((PARTS / name).read_text(encoding="utf-8"))


def save(name, data):
    (PARTS / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


PACKET_NOTE = (
    "A research packet of facts about NSM primes ('they decide nothing', research-2026-10-25/README.md:3), filed at 19:17, "
    "after this pass began. Only this one file of the packet was read."
)

# ------------------------------------------------------------ INTENSITY and HIER_PLUS
coords = load("22_coords_c.json")
coords["INTENSITY"]["statements"].append(
    {
        "loc": "docs/verification/lexicon-rebuild/research-2026-10-25/nsm-prime-facts/parts/very_more_evidence.json:2,40",
        "who": "AGENT_DOC",
        "quote": (
            "Curated list of every place found where VERY or MORE (including the anymore allolex) is combined with one of the "
            "41 primes, in the parts read. … (line 2) / Found in the parts read: the chart's VERY box lists very big, very "
            "small, very good, very bad and 'I want it very much (=very)'; the LITTLE~FEW box has 'very little, very few'; "
            "GW2014 pp.34-35 'very small', 'very few things', 'very bad things'; GW2014 pp.174-176 'something very good'; "
            "GW2014 p.136 'Does it hurt very much?'; LFH22 pp.11 and 13 'something very bad'. (line 40)"
        ),
        "note": PACKET_NOTE,
    }
)
coords["HIER_PLUS"]["statements"].append(
    {
        "loc": "docs/verification/lexicon-rebuild/research-2026-10-25/nsm-prime-facts/parts/very_more_evidence.json:2,41",
        "who": "AGENT_DOC",
        "quote": (
            "Curated list of every place found where VERY or MORE (including the anymore allolex) is combined with one of the "
            "41 primes, in the parts read. … (line 2) / Found in the parts read: the chart's MORE~ANYMORE box has 'someone "
            "wants more' and 'not living anymore'; the MUCH~MANY box has 'much more, many more'. (line 41)"
        ),
        "note": PACKET_NOTE,
    }
)
save("22_coords_c.json", coords)

# ------------------------------------------------------------ cross-cutting
cross = load("10_cross_cutting.json")
cross["cross_cutting_basis_facts"].append(
    {
        "loc": "docs/verification/lexicon-rebuild/research-2026-10-25/README.md:3,8",
        "who": "AGENT_DOC",
        "quote": (
            "Facts gathered by sub-agents for the work after the first checkpoint (F160). They state what the sources say, with "
            "locations; they decide nothing. (3) / For the 41 remaining NSM-mapped primes: their chart box lines and quoted "
            "statements from G12, LFH22 and GW2014 (with page and line), how the sources separate the primes GSE merges "
            "(SAME/OTHER, the two BE primes, HAVE and PART, THERE IS), and where VERY and MORE combine. (8)"
        ),
        "note": (
            "NSM-side material filed at 19:17-19:18, after this pass began. It covers the 41 NSM-mapped primes, not the GSE "
            "adaptations; only nsm-prime-facts/parts/very_more_evidence.json was read."
        ),
    }
)
save("10_cross_cutting.json", cross)

# ------------------------------------------------------------ meta
meta = load("00_meta.json")
full = meta["files_read"]["other_files_read_in_full"]
full.append(
    "docs/verification/lexicon-rebuild/foundation-2026-10-25/REPLAY.md (new at 19:20), research-2026-10-25/README.md, "
    "research-2026-10-25/nsm-prime-facts/parts/very_more_evidence.json; REPORT.md re-read as revision 3; "
    "LEXICON_CONSTRUCTION_DESIGN.md, bank_laws.json, native_constraints.py, registry.py and openspec tasks.md re-read after "
    "their 19:14-19:26 edits"
)
not_read = meta["files_read"]["listed_but_not_read"]
not_read.append(
    "docs/verification/lexicon-rebuild/research-2026-10-25/nsm-prime-facts/prime_facts.json and its other parts, "
    "noun-facts/*; docs/verification/lexicon-rebuild/foundation-2026-10-25/replay/* (comparison data, scripts)"
)
meta["meta"]["state_of_tree"] = (
    "The worktree has uncommitted changes (foundation.json, foundation.py, tail.py, surprise.py and others are untracked or "
    "modified), and it was still being edited while this pass ran. Line numbers describe the files as last read; the "
    "source_snapshot key records the size and modification time of each cited file at the end of the pass."
)
meta["meta"]["drift_during_pass"] = {
    "explanation": (
        "Another actor edited the worktree while this pass ran. The files below were read once before their edit and again "
        "after it; statements about them quote the later text, and where the change touches a coordinate's meaning (CAUSE) "
        "the earlier text is kept and labelled."
    ),
    "files_changed_after_first_reading": {
        "gse/lexicon_builder/bank_laws.json": "19:14 (VN_CAUSATION rewritten; version 2026-10-25.7)",
        "gse/lexicon_builder/native_constraints.py": "19:26 (CAUSE now requires a change to another participant)",
        "gse/lexicon_builder/registry.py": "19:25 (native_predicate_contracts)",
        "docs/program/LEXICON_CONSTRUCTION_DESIGN.md": "19:16 (lines 3, 178, 282, 288 changed)",
        "docs/verification/lexicon-rebuild/foundation-2026-10-25/REPORT.md": "19:20 (revision 3; line numbers shifted)",
        "docs/verification/lexicon-rebuild/foundation-2026-10-25/REPLAY.md": "19:20 (new)",
        "openspec/changes/lexicon-symbolic-foundation/tasks.md": "19:21 (one task ticked; line numbers shifted by one)",
        "docs/verification/lexicon-rebuild/research-2026-10-25/": "19:17-19:18 (new)",
    },
    "modification_times_at_the_end_of_the_pass_were_18:26_or_earlier_for": "gse/lexicon_builder/{basis,core,fill,foundation,build,reading,sources,artifact,tail,surprise,audit,coverage,model,perception,number,atomics}.py and foundation.json (18:25 or earlier), the founder record and REFERENCE_MANIFEST.json (18:25), NSM_RESOLUTIONS.md, RULE_REVIEW.md, EMOTION_SLICE_DRAFT.md and rule_decisions.json (13:43-13:45), gse/primitives_v2.py and the legacy curation, lexicon and symbolic files and docs (08:34 on Oct 25), the chart text (Oct 23) and the papers folder (Mar-Jun).",
}
save("00_meta.json", meta)
print("extra patches applied")
