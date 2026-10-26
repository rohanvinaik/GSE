"""Update the CAUSE entry and contradiction C07 after the repository changed during the pass.

Edits only /tmp/gse-subagents/adaptation-facts/parts/21_coords_b.json and 40_contradictions.json.
"""

import json
from pathlib import Path

PARTS = Path("/tmp/gse-subagents/adaptation-facts/parts")

# ---------------------------------------------------------------- CAUSE entry
path = PARTS / "21_coords_b.json"
data = json.loads(path.read_text(encoding="utf-8"))
cause = data["CAUSE"]
statements = cause["statements"]


def index_of(loc_prefix):
    matches = [i for i, s in enumerate(statements) if s["loc"].startswith(loc_prefix)]
    if len(matches) != 1:
        raise SystemExit("expected one statement starting %r, found %d" % (loc_prefix, len(matches)))
    return matches[0]


# 1. bank_laws.json VN_CAUSATION: current text, its witnesses, and the earlier text.
i = index_of("gse/lexicon_builder/bank_laws.json:1621-1642")
current_rule = {
    "loc": "gse/lexicon_builder/bank_laws.json:1621-1647",
    "who": "CODE_CURRENT",
    "quote": (
        '"rule_id": "VN_CAUSATION", "predicate": "cause", "prime": "CAUSE", … "review_state": "SOURCE_JUSTIFIED", '
        '"tier": "CONDITIONAL", "projection_kind": "LEXICAL_COMPONENT", "requires_change_to_another_participant": true, '
        '"warrant": "F144 option B: CAUSE is the word\'s own causative event, a causer\'s DO or HAPPEN bringing about a change '
        "in another participant. NSM writes that event as 'X did something (to Y); because of this, something happened to Y' "
        "(GW16: the frames of cut, grind, dig, hit, kick and kill and the outcomes of put, throw, push, make and build), "
        "HAPPEN's undergoer frame (GW2014 Table 1.2). So VerbNet cause(...) writes CAUSE +1 only when the caused event asserts "
        "something happening to a participant other than the causer: a state or relation at its end or result, that "
        "participant's motion, transfer or emotional state during it, or its aspectual beginning or ending. A speech act's "
        "effect is only wanted ('this someone wanted something to happen because of it', GW2014 ch. 7), so say, tell, ask and "
        "talk get no CAUSE and no DO: their head is SAY. A typed Agent causer establishes DO; an event causer establishes "
        "HAPPEN; an unknown causer type establishes neither. A predicate refused as a wrong-sense or out-of-scope join never "
        'counts. BECAUSE is not an alias.", … "scope": "ONE_NATIVE_EVENT_AND_CAUSER_BINDING"'
    ),
    "note": (
        "Text of the file as of mtime 19:14. Lines: review_state 1626, tier 1627, requires_change_to_another_participant "
        "1629, warrant 1630, scope 1636, source_refs 1638-1643 ('FOUNDER:F144 (option B)', 'GW16 sections 2.4-2.7', "
        "'GW2014 Table 1.2 (p.14) and chapter 7 (pp.156-183)')."
    ),
}
witnesses = {
    "loc": "gse/lexicon_builder/bank_laws.json:1644-1646",
    "who": "CODE_CURRENT",
    "quote": (
        '"positive": "kill (murder-42.1: not alive as the result), give (give-13.1: possession at the end), put (put-9.1: '
        "location at the end), build (build-26.1: existence as the result), frighten and amuse (amuse-31.1: the experiencer's "
        "emotional state), hit (hit-18.1, spank-18.3: contact at the end), throw (throw-17.1: the theme's motion), name "
        "(dub-29.3: designation as the result), start and end (begin-55.1, stop-55.4: the theme event begins or ends)\", "
        '"must_not": "say, tell, ask and talk (transfer_info only); seeing or knowing someone as something (characterize-29.2); '
        "learn and study (learn-14); focus (focus-87); continue (continue-55.3); hitting at something (hit-18.1: no contact); "
        'an emotional state refused as a wrong-sense join (interest, try and throw in amuse-31.1; matter in appeal-31.4)", '
        '"known_limits": "VerbNet gives \'Tom ran the soles off his shoes\' and \'We walked ourselves into a state of '
        "exhaustion' (run-51.3.2 frames 7 and 8) the same semantics, so the reflexive result passes as a change in another "
        "participant. The native adapter drops VerbNet's role restrictions, so the actor's own body part ('Linda winked her "
        "eye', wink-40.3.1, Patient +body_part) also passes. A frame that states no outcome (reflexive_appearance-48.1.2 "
        'appear) leaves CAUSE unresolved."'
    ),
}
earlier_rule = {
    "loc": "gse/lexicon_builder/bank_laws.json, VN_CAUSATION as first read (file then 52k, mtime 18:05, before the 19:14 edit; rule at lines 1621-1642, warrant at 1629)",
    "who": "CODE_CURRENT",
    "quote": (
        '"warrant": "F144 option B: native causation is CAUSE. A typed Agent causer also establishes DO; an explicitly '
        "event-valued causer establishes HAPPEN. Unknown causer type establishes neither companion. BECAUSE is not an "
        'alias."'
    ),
    "note": "Earlier text of the same rule, read before the file changed during this pass. Superseded by the entry above and kept for provenance.",
}
statements[i : i + 1] = [current_rule, witnesses, earlier_rule]

# 2. native_constraints.py: current code, and what the first reading saw.
i = index_of("gse/lexicon_builder/native_constraints.py:126-129")
statements[i] = {
    "loc": "gse/lexicon_builder/native_constraints.py:23-26,81-112,175-193",
    "who": "CODE_CURRENT",
    "quote": (
        "# A predicate refused as a wrong-sense or out-of-scope join is never the change a cause brings about. / "
        '_REFUSED_JOINS = {"UNALIGNED_AFFECTIVE_READING", "OUTSIDE_RULE_CLASS_SCOPE", "PARTICIPANT_EXISTENCE_PRESUPPOSITION"} / '
        '_UNDERGOER_EVENTS = {"motion", "transfer", "emotional_state"} / _ASPECTUAL_CHANGES = {"begin", "end"} … '
        'def _changes_another_participant(frame: dict, cause_index: int, refused: set[int]) -> bool: """NSM\'s causative event: '
        "someone does something, and because of this something happens to another (GW16). / The caused event must assert "
        "something happening to a participant other than the causer: a state or relation at its end or result, that "
        "participant's motion, transfer or emotional state during it, or its aspectual beginning or ending. A speech act's "
        "effect is only wanted ('this someone wanted something to happen because of it', GW2014 ch. 7), so saying is not "
        'causing."""  … if name == "cause" and predicate["predicate"].get("bool") != "!" and "Agent" in roles: / '
        'assertions.append({**assertions[-1], "coordinate": "DO", "prime": "DO"}) / elif name == "cause" and '
        'predicate["predicate"].get("bool") != "!" and event_causer: / assertions.append({**assertions[-1], "coordinate": '
        '"HAPPEN", "prime": "HAPPEN"}) … # No caused change: neither CAUSE nor its DO/HAPPEN companion is written; the '
        'predicate stays in the derivation. … {"predicate_index": index, "code": "NO_CHANGE_TO_ANOTHER_PARTICIPANT", '
        '"native": frame["predicates"][index]}'
    ),
    "note": (
        "Text of the file as of mtime 19:26. Its first reading (before 19:26) had the DO and HAPPEN companions at lines "
        "126-129 and no _changes_another_participant test."
    ),
}

# 3. Design section 7.3 item 3, current text.
i = index_of("docs/program/LEXICON_CONSTRUCTION_DESIGN.md:288")
statements[i] = {
    "loc": "docs/program/LEXICON_CONSTRUCTION_DESIGN.md:288",
    "who": "AGENT_DOC",
    "quote": (
        "Native causation and explanatory BECAUSE likewise need their distinct source-to-coordinate contracts, and F144 adopts "
        "them (option B of the CAUSE decision). CAUSE is the word's own causative event, a causer's DO or HAPPEN bringing about "
        "a change in another participant: VerbNet's `cause(...)` writes CAUSE +1, with DO +1 for an agent causer or HAPPEN +1 "
        "for an event causer, when the caused event asserts something happening to a participant other than the causer. That "
        "is NSM's causative frame: someone does something, and because of this something happens to another participant "
        '("someone X did something to someone else (at this time) / because of this, something happened to this someone else '
        'at the same time", *hit* in [GW16](../../data/external/references/goddard-wierzbicka-2016-doing-and-happening.pdf), '
        "whose §§2.4–2.7 verbs share the shape; HAPPEN's undergoer frame, GW2014 Table 1.2). VerbNet also puts "
        "`cause(Agent, E)` on agentive frames where nothing happens to anyone else, such as saying. A speech act's effect is "
        'only wanted ("this someone wanted something to happen because of it", GW2014 ch. 7), so *say*, *tell* and *ask* '
        "write neither CAUSE nor DO. BECAUSE is a reason or thought-to-feeling link inside the meaning. Published "
        'explications are projected by the same test, each NSM "because" sorted into one or the other.'
    ),
    "note": (
        "Text of the file as of mtime 19:16. Its first reading (before 19:16) ended the CAUSE sentence at 'HAPPEN +1 for an "
        "event causer' and had none of the text after it."
    ),
}
new_after_design = [
    {
        "loc": "docs/verification/lexicon-rebuild/foundation-2026-10-25/REPORT.md:7",
        "who": "AGENT_DOC",
        "quote": (
            "- **CAUSE corrected.** The review found that the draft's CAUSE rule wrote CAUSE +1 and DO +1 on every VerbNet "
            "`cause(...)`, including saying. Read through GW16 and GW2014 ch. 7, option B now requires something to happen to "
            "another participant: 861 CAUSE readings became 538, with none left in the communication classes."
        ),
        "note": "REPORT.md is 'revision 3', dated 19:20; the first reading was revision 2 and had no such line.",
    },
    {
        "loc": "docs/verification/lexicon-rebuild/foundation-2026-10-25/REPLAY.md:3,71-76,89-97,118-122",
        "who": "AGENT_DOC",
        "quote": (
            "The review found one rule that wrote CAUSE where the approved meaning of CAUSE rules it out; that rule was "
            "corrected from the NSM sources before the numbers below were taken. (3) / ## The CAUSE correction / **What was "
            "wrong.** - The draft wrote CAUSE +1, and DO +1 for an Agent, for every VerbNet `cause(...)`. - VerbNet puts "
            "`cause(Agent, E)` on most agentive frames, including saying (`transfer_info` only). So CAUSE reached 861 "
            "readings, 218 of them in the communication classes (*say*, *tell*, *ask*, *talk*). - Option B defines CAUSE as "
            "the word's own causative event: \"a causer's DO or HAPPEN brings about a change in another participant\" "
            "(NSM_RESOLUTIONS §6, F144). Saying changes no one. (71-76) / **The rule now.** - VerbNet `cause(...)` writes "
            "CAUSE +1 only when the caused event asserts something happening to a participant other than the causer: - a "
            "state or relation at the event's end or result; - that participant's motion, transfer or emotional state during "
            "it; - its aspectual beginning or ending. - A predicate the builder already refused as a wrong-sense or "
            "out-of-scope join never counts. - DO and HAPPEN are written only with CAUSE. - A frame that fails the test "
            "leaves CAUSE and DO unresolved, never 0, and records `NO_CHANGE_TO_ANOTHER_PARTICIPANT`. (89-97) / **Known "
            "limits.** - **Reflexive result.** … - **Own body part.** … - **No outcome phase.** … - **Membership.** … (118-122)"
        ),
        "note": "REPLAY.md is new (19:20); it did not exist at the first reading.",
    },
    {
        "loc": "docs/verification/lexicon-rebuild/foundation-2026-10-25/REPLAY.md:80",
        "who": "AGENT_DOC",
        "quote": (
            "Verbs that affect someone or something put the change in the frame. *hit*: \"someone X did something to someone "
            "else (at this time) / because of this, something happened to this someone else at the same time\"; *kick* "
            "(\"to something\") and *kill* (\"at this time\") have the same shape."
        ),
        "note": "REPLAY.md paraphrases GW16 here; GW16 itself was not read in this pass.",
    },
]
statements[i + 1 : i + 1] = new_after_design

# 4. Nearest primes, absences.
for item in cause["nearest_nsm_primes_named_by_sources"]:
    if "bank_laws.json:1629" in item.get("note", ""):
        item["note"] = item["note"].replace("bank_laws.json:1629", "bank_laws.json:1630")
cause["nearest_nsm_primes_named_by_sources"].append(
    {
        "primes": "DO, BECAUSE and HAPPEN as the causative frame ('X did something (to Y); because of this, something happened to Y')",
        "loc": "gse/lexicon_builder/bank_laws.json:1630; docs/verification/lexicon-rebuild/foundation-2026-10-25/REPLAY.md:80; docs/program/LEXICON_CONSTRUCTION_DESIGN.md:288",
        "who": "CODE_CURRENT / AGENT_DOC",
        "note": "These sources cite GW16 and GW2014 Table 1.2 for the frame; they do not name a prime for CAUSE itself.",
    }
)
cause["absences"] = (
    "Only VN_CAUSATION writes CAUSE (and the Fear templates leave it open). Since the 19:14 edit its rule requires a change to "
    "another participant; REPLAY.md:112 and REPORT.md:7 record 538 readings carrying CAUSE (861 before that correction). "
    "Rohan has no CAUSE statement other than the F144 blanket approval."
)
cause["note_on_drift"] = (
    "bank_laws.json (19:14), native_constraints.py (19:26), LEXICON_CONSTRUCTION_DESIGN.md (19:16), REPORT.md (19:20) and "
    "REPLAY.md (19:20, new) changed while this pass ran; this entry quotes them as re-read after those times and also keeps "
    "the earlier text of VN_CAUSATION."
)
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("CAUSE entry updated;", len(statements), "statements")

# ---------------------------------------------------------------- C07
path = PARTS / "40_contradictions.json"
data = json.loads(path.read_text(encoding="utf-8"))
c07 = [c for c in data["contradictions"] if c["id"] == "C07"]
if len(c07) != 1:
    raise SystemExit("C07 not found")
sides = c07[0]["sides"]
for k, side in enumerate(sides):
    if side["loc"] == "gse/lexicon_builder/bank_laws.json:1629":
        sides[k] = {
            "loc": "gse/lexicon_builder/bank_laws.json:1630",
            "who": "CODE_CURRENT",
            "quote": (
                "F144 option B: CAUSE is the word's own causative event, a causer's DO or HAPPEN bringing about a change in "
                "another participant. … A typed Agent causer establishes DO; an event causer establishes HAPPEN; an unknown "
                "causer type establishes neither. A predicate refused as a wrong-sense or out-of-scope join never counts. "
                "BECAUSE is not an alias."
            ),
            "note": "File as of mtime 19:14. Its first reading had: 'F144 option B: native causation is CAUSE. A typed Agent causer also establishes DO; an explicitly event-valued causer establishes HAPPEN.'",
        }
        break
else:
    raise SystemExit("C07 bank_laws side not found")
sides.append(
    {
        "loc": "docs/program/LEXICON_CONSTRUCTION_DESIGN.md:288",
        "who": "AGENT_DOC",
        "quote": (
            "VerbNet's `cause(...)` writes CAUSE +1, with DO +1 for an agent causer or HAPPEN +1 for an event causer, when the "
            "caused event asserts something happening to a participant other than the causer. … VerbNet also puts "
            "`cause(Agent, E)` on agentive frames where nothing happens to anyone else, such as saying."
        ),
    }
)
sides.append(
    {
        "loc": "gse/lexicon_builder/native_constraints.py:81-87",
        "who": "CODE_CURRENT",
        "quote": (
            "\"\"\"NSM's causative event: someone does something, and because of this something happens to another (GW16). / The "
            "caused event must assert something happening to a participant other than the causer …"
        ),
    }
)
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("C07 updated;", len(sides), "sides")
