"""Second drift update: VN_CAUSATION was edited again at 19:28 and the openspec spec gained a CAUSE requirement.

Edits only /tmp/gse-subagents/adaptation-facts/parts/*.json.
"""

import json
from pathlib import Path

PARTS = Path("/tmp/gse-subagents/adaptation-facts/parts")


def load(name):
    return json.loads((PARTS / name).read_text(encoding="utf-8"))


def save(name, data):
    (PARTS / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


data = load("21_coords_b.json")
cause = data["CAUSE"]
statements = cause["statements"]


def find(prefix):
    matches = [i for i, s in enumerate(statements) if s["loc"].startswith(prefix)]
    if len(matches) != 1:
        raise SystemExit("expected one statement starting %r, found %d" % (prefix, len(matches)))
    return matches[0]


# Current rule text (file mtime 19:28:07).
i = find("gse/lexicon_builder/bank_laws.json:1621-1647")
statements[i]["quote"] = (
    '"rule_id": "VN_CAUSATION", "predicate": "cause", "prime": "CAUSE", … "review_state": "SOURCE_JUSTIFIED", '
    '"tier": "CONDITIONAL", "projection_kind": "LEXICAL_COMPONENT", "requires_change_to_another_participant": true, '
    '"warrant": "F144 option B: CAUSE is the word\'s own causative event, a causer\'s DO or HAPPEN bringing about a change '
    "in another participant. NSM writes that event as a doing followed by 'because of this, something happened to this "
    "someone else at the same time' (GW16, hit); the frames of cut, grind, dig, kick and kill and the outcomes of put, "
    "throw, push, make and build have the same shape, HAPPEN's undergoer frame (GW2014 Table 1.2). So VerbNet cause(...) "
    "writes CAUSE +1 only when the caused event asserts something happening to a participant other than the causer: a "
    "state or relation at its end or result, that participant's motion, transfer or emotional state during it, or its "
    "aspectual beginning or ending. A speech act's effect is only wanted ('this someone wanted something to happen because "
    "of it', GW2014 ch. 7), so say, tell, ask and talk get no CAUSE and no DO: their head is SAY. A typed Agent causer "
    "establishes DO; an event causer establishes HAPPEN; an unknown causer type establishes neither. A predicate refused "
    'as a wrong-sense or out-of-scope join never counts. BECAUSE is not an alias.", … "scope": '
    '"ONE_NATIVE_EVENT_AND_CAUSER_BINDING"'
)
statements[i]["note"] = (
    "Text of the file as of mtime 19:28:07 (54,014 bytes). Lines: review_state 1626, tier 1627, "
    "requires_change_to_another_participant 1629, warrant 1630, scope 1636, source_refs 1638-1643 ('FOUNDER:F144 (option B)', "
    "'GW16 sections 2.4-2.7', 'GW2014 Table 1.2 (p.14) and chapter 7 (pp.156-183)'). The rule was rewritten twice during this "
    "pass (see the next entries)."
)

# Earlier texts of the same warrant.
i = find("gse/lexicon_builder/bank_laws.json, VN_CAUSATION as first read")
statements[i]["loc"] = (
    "gse/lexicon_builder/bank_laws.json, VN_CAUSATION as read before 19:28 (two earlier texts of the same warrant)"
)
statements[i]["quote"] = (
    "As first read (file mtime 18:05, rule at lines 1621-1642, warrant at line 1629): \"warrant\": \"F144 option B: native "
    "causation is CAUSE. A typed Agent causer also establishes DO; an explicitly event-valued causer establishes HAPPEN. "
    "Unknown causer type establishes neither companion. BECAUSE is not an alias.\" / As read after the 19:14 edit (rule at "
    "lines 1621-1647): the same first two sentences as the current text, then \"NSM writes that event as 'X did something "
    "(to Y); because of this, something happened to Y' (GW16: the frames of cut, grind, dig, hit, kick and kill and the "
    "outcomes of put, throw, push, make and build), HAPPEN's undergoer frame (GW2014 Table 1.2).\""
)
statements[i]["note"] = (
    "Earlier texts of the same rule, read before the file changed. Superseded by the current entry and kept for provenance."
)

# openspec spec.md requirement (new at 19:28).
i = find("gse/lexicon_builder/native_constraints.py:23-26")
statements[i]["note"] = (
    "Text of the file as of mtime 19:28:36 (lines 23-26, 81-112 and 175-193 are the same in the 19:26 and 19:28 versions). "
    "Its first reading (before 19:26) had the DO and HAPPEN companions at lines 126-129 and no _changes_another_participant test."
)
statements.insert(
    i + 1,
    {
        "loc": "openspec/changes/lexicon-symbolic-foundation/specs/lexicon-construction/spec.md:74-87",
        "who": "AGENT_DOC",
        "quote": (
            "### Requirement: CAUSE records a change brought about in another participant / A native `cause(...)` predicate "
            "SHALL write CAUSE +1, with DO +1 for an Agent causer or HAPPEN +1 for an event causer, only when the caused "
            "event asserts something happening to a participant other than the causer (NSM's causative frame: \"because of "
            "this, something happened to this someone else at the same time\", GW16). Otherwise CAUSE and DO SHALL stay "
            "unresolved, and the predicate SHALL stay in the derivation. (74-75) / #### Scenario: Saying causes nothing - "
            "**WHEN** a frame asserts only that the causer passes information to someone (say, tell, ask) - **THEN** neither "
            "CAUSE nor DO is written, and the predicate is recorded as `NO_CHANGE_TO_ANOTHER_PARTICIPANT` (77-79) / #### "
            "Scenario: A change to another participant is caused - **WHEN** a frame asserts that another participant stops "
            "living, moves, or ends in a new state - **THEN** CAUSE is +1, with DO +1 when the causer is an Agent (81-83)"
        ),
        "note": "spec.md changed at 19:28; the requirement was not in the text first read.",
    },
)
cause["note_on_drift"] = (
    "bank_laws.json (19:14 and again 19:28), native_constraints.py (19:26 and 19:28), LEXICON_CONSTRUCTION_DESIGN.md (19:16 and "
    "19:27), REPORT.md (19:20), REPLAY.md (19:20 and 19:29) and openspec spec.md (19:28) changed while this pass ran. This entry "
    "quotes them as re-read after those times and keeps the earlier text of VN_CAUSATION."
)
save("21_coords_b.json", data)

# C07 note.
data = load("40_contradictions.json")
c07 = [c for c in data["contradictions"] if c["id"] == "C07"][0]
for side in c07["sides"]:
    if side["loc"] == "gse/lexicon_builder/bank_laws.json:1630":
        side["note"] = (
            "File as of mtime 19:28:07. The first reading (mtime 18:05, warrant at line 1629) had: 'F144 option B: native "
            "causation is CAUSE. A typed Agent causer also establishes DO; an explicitly event-valued causer establishes HAPPEN.'"
        )
save("40_contradictions.json", data)

# Meta drift record.
meta = load("00_meta.json")
changed = meta["meta"]["drift_during_pass"]["files_changed_after_first_reading"]
changed["gse/lexicon_builder/bank_laws.json"] = "19:14 and again 19:28:07 (VN_CAUSATION rewritten twice; version 2026-10-25.7)"
changed["gse/lexicon_builder/native_constraints.py"] = "19:26 and 19:28:36 (CAUSE now requires a change to another participant)"
changed["docs/program/LEXICON_CONSTRUCTION_DESIGN.md"] = "19:16 and 19:27:53 (lines 3, 178, 282, 288 differ from the first reading)"
changed["docs/verification/lexicon-rebuild/foundation-2026-10-25/REPLAY.md"] = "new at 19:20, edited again 19:29"
changed["openspec/changes/lexicon-symbolic-foundation/specs/lexicon-construction/spec.md"] = "19:28 (a CAUSE requirement added at lines 74-87)"
save("00_meta.json", meta)
print("second drift update applied")
