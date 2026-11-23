"""Final small patches: contradiction C27 (CAUSE scope) and an ellipsis in the QUANTITY quotation.

Edits only /tmp/gse-subagents/adaptation-facts/parts/*.json.
"""

import json
from pathlib import Path

PARTS = Path("/tmp/gse-subagents/adaptation-facts/parts")


def load(name):
    return json.loads((PARTS / name).read_text(encoding="utf-8"))


def save(name, data):
    (PARTS / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---- QUANTITY: the quotation omitted the line "*such* -> LIKE;" without marking it.
data = load("20_coords_a.json")
old = '*a lot* → QUANTITY, with INTENSITY for "very"; / *everywhere* → QUANTITY and WHERE;'
new = '*a lot* → QUANTITY, with INTENSITY for "very"; / … / *everywhere* → QUANTITY and WHERE;'
fixed = 0
for statement in data["QUANTITY"]["statements"]:
    if old in statement["quote"]:
        statement["quote"] = statement["quote"].replace(old, new)
        fixed += 1
if fixed != 1:
    raise SystemExit("expected one QUANTITY quotation to fix, found %d" % fixed)
save("20_coords_a.json", data)

# ---- C27
data = load("40_contradictions.json")
if any(c["id"] == "C27" for c in data["contradictions"]):
    raise SystemExit("C27 already present")
data["contradictions"].append(
    {
        "id": "C27",
        "topic": "Whether VerbNet cause(...) writes CAUSE +1 unconditionally, or only when the caused event changes another participant",
        "coordinates": ["CAUSE"],
        "sides": [
            {
                "loc": "docs/verification/lexicon-rebuild/closeout-2026-10-25/rule_decisions.json:23",
                "who": "AGENT_DOC",
                "quote": "\"OPTION_B\": \"the CAUSE decision taken as option B: VerbNet cause(...) writes CAUSE +1, with DO +1 for an agent causer or HAPPEN +1 for an event causer; BECAUSE stays the reason / thought-to-feeling link\",",
                "note": "The decision record F144 approved (rule_decisions.json:9-20).",
            },
            {
                "loc": "docs/verification/lexicon-rebuild/closeout-2026-10-25/rule_decisions.json:273",
                "who": "AGENT_DOC",
                "quote": "\"proposed_change\": \"Decide with row 26, on its own. Option B (recommended; design 7.3 expects distinct contracts): VerbNet cause(...) writes CAUSE +1, with DO +1 for an agent causer or HAPPEN +1 for an event causer; BECAUSE stays the reason / thought-to-feeling link. …\"",
            },
            {
                "loc": "docs/verification/lexicon-rebuild/closeout-2026-10-25/NSM_RESOLUTIONS.md:214",
                "who": "AGENT_DOC",
                "quote": "- **Row 25 becomes:** VerbNet's `cause(...)` writes CAUSE +1, with DO +1 for an agent causer and HAPPEN +1 for an event causer.",
            },
            {
                "loc": "docs/verification/lexicon-rebuild/closeout-2026-10-25/RULE_REVIEW.md:259",
                "who": "AGENT_DOC",
                "quote": "- **Row 25 writes** CAUSE +1 for a frame's `cause(...)`, with DO +1 for an agent causer and HAPPEN +1 for an event causer. Row 26 is dropped.",
            },
            {
                "loc": "docs/verification/lexicon-rebuild/foundation-2026-10-25/REPLAY.md:76",
                "who": "AGENT_DOC",
                "quote": "Option B defines CAUSE as the word's own causative event: \"a causer's DO or HAPPEN brings about a change in another participant\" (NSM_RESOLUTIONS §6, F144). Saying changes no one.",
                "note": "The framing REPLAY.md gives for the narrowing (lines 71-97).",
            },
            {
                "loc": "gse/lexicon_builder/bank_laws.json:1630 (file as of mtime 19:28:07)",
                "who": "CODE_CURRENT",
                "quote": "So VerbNet cause(...) writes CAUSE +1 only when the caused event asserts something happening to a participant other than the causer: a state or relation at its end or result, that participant's motion, transfer or emotional state during it, or its aspectual beginning or ending.",
            },
            {
                "loc": "openspec/changes/lexicon-symbolic-foundation/specs/lexicon-construction/spec.md:75",
                "who": "AGENT_DOC",
                "quote": "A native `cause(...)` predicate SHALL write CAUSE +1, with DO +1 for an Agent causer or HAPPEN +1 for an event causer, only when the caused event asserts something happening to a participant other than the causer",
            },
            {
                "loc": "docs/verification/lexicon-rebuild/foundation-2026-10-25/REPLAY.md:89-97",
                "who": "AGENT_DOC",
                "quote": "VerbNet `cause(...)` writes CAUSE +1 only when the caused event asserts something happening to a participant other than the causer: … DO and HAPPEN are written only with CAUSE. - A frame that fails the test leaves CAUSE and DO unresolved, never 0, and records `NO_CHANGE_TO_ANOTHER_PARTICIPANT`.",
            },
        ],
        "note": "The approved statements carry no condition on the caused event; the later statements add one. The sources disagree on this scope as written; the contradiction records both texts without a verdict.",
    }
)
save("40_contradictions.json", data)

# ---- CAUSE entry cites C27 by hand as well (the merge would add it anyway).
data = load("21_coords_b.json")
ids = data["CAUSE"]["contradiction_ids"]
if "C27" not in ids:
    ids.append("C27")
save("21_coords_b.json", data)

# ---- layout text in the meta: C01-C27
meta = load("00_meta.json")
layout = meta["meta"]["layout_of_this_file"]
layout["contradictions"] = "C01-C27, both sides quoted, no verdict"
save("00_meta.json", meta)
print("final patches applied")
