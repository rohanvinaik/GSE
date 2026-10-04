"""Induced-mistag measurement harness for the tier-1 enumeration repair.

OFF-PIPELINE. Two passes:

  main()          gold-by-construction cases (transitive/intransitive/copula
                  built from real Genesis verbs x entities). Gold is known by
                  construction, so we score recovery AND the false-clean blind
                  spot (a partial mistag that completes a valid-but-wrong frame).

  natural_pass()  descriptive run over real corpus sentences, INCLUDING complex
                  clauses tier-1 doesn't target — to see where its scope ends.

Categories: CORRECT_CLEAN / CORRECT_REPAIR / FALSE_CLEAN / WRONG_REPAIR /
BIFURCATE / FALLBACK.
"""

from __future__ import annotations

import os
import re
import zipfile
from collections import Counter, defaultdict

from gse.demo.enum_repair import Tier1Repair

# Real Genesis verbs (present -s) and proper-noun entities, recombined.
TRANS_VERBS = [
    "murders",
    "compliments",
    "rewards",
    "attacks",
    "astonishes",
    "punishes",
    "insults",
    "curses",
    "executes",
    "invites",
    "stabs",
    "helps",
    "trusts",
    "predicts",
    "defeats",
    "kills",
    "fights",
    "loves",
    "betrays",
    "praises",
]
PAIRS = [("Macbeth", "Duncan"), ("Duncan", "Macbeth"), ("Barry", "Katya"), ("Macduff", "Cawdor"), ("David", "Goliath")]
INTRANS = [
    ("Goliath", "falls"),
    ("Macbeth", "sleeps"),
    ("Duncan", "flees"),
    ("Macduff", "hallucinates"),
    ("Barry", "dreams"),
    ("Malcolm", "kneels"),
]
COPULA = [("Duncan", "king"), ("Macbeth", "thane"), ("Cawdor", "traitor"), ("Goliath", "giant"), ("Barry", "soldier")]

JAR = os.path.expanduser("~/Genesis/genesis.jar")
SLICE = os.path.expanduser("~/Genesis/slice_demo.txt")
STORY_MEMBERS = [
    "priyaKalluri/OldStories/Priya Macbeth plot.txt",
    "stories/Genesis/DavidGoliath.txt",
    "olgaShestopalova/stories/align/archer_revenge.txt",
    "stories/Cyberwar/Estonia plot.txt",
]
SUBORD = re.compile(r"\b(because|that|leads|order|after|when|if|but|will|wants|with)\b", re.I)


def _eq(a, b):
    return a is not None and b is not None and a.lower() == b.lower()


def _extract(out):
    if out["verdict"] == "clean":
        r = out.get("roles", {})
        return out["frame"], r.get("SYN_SUBJ"), r.get("SYN_OBJ")
    if out["verdict"] in ("commit", "bifurcate"):
        r = out["candidates"][0]["roles"]
        return out["candidates"][0]["frame"], r.get("SYN_SUBJ"), r.get("SYN_OBJ")
    return None, None, None


def _classify(out, gold_frame, gold_subj, gold_obj):
    frame, subj, obj = _extract(out)
    roles_ok = _eq(subj, gold_subj) and (gold_obj is None or _eq(obj, gold_obj))
    good = (frame == gold_frame) and roles_ok
    v = out["verdict"]
    if v == "clean":
        return "CORRECT_CLEAN" if good else "FALSE_CLEAN"
    if v == "commit":
        return "CORRECT_REPAIR" if good else "WRONG_REPAIR"
    if v == "bifurcate":
        return "BIFURCATE"
    return "FALLBACK"


def main() -> None:
    rep = Tier1Repair()
    cases = []
    for v in TRANS_VERBS:
        for s, o in PAIRS:
            cases.append(("EVENT_TRANS", s, v, o, f"{s} {v} {o}."))
    for s, v in INTRANS:
        cases.append(("EVENT_INTRANS", s, v, None, f"{s} {v}."))
    for s, k in COPULA:
        cases.append(("COPULA", s, k, None, f"{s} is a {k}."))

    tally: Counter = Counter()
    by_verb = defaultdict(Counter)
    failures = []
    for gold_frame, subj, verb, obj, sent in cases:
        out = rep.repair(sent)
        cat = _classify(out, gold_frame, subj, obj)
        tally[cat] += 1
        by_verb[verb][cat] += 1
        if not cat.startswith("CORRECT"):
            failures.append((cat, sent, out["verdict"]))

    print("=== per-verb (transitive only) — C=clean R=repair F=false-clean W=wrong ===")
    for v in TRANS_VERBS:
        c = by_verb[v]
        print(f"   {v:13} C={c['CORRECT_CLEAN']} R={c['CORRECT_REPAIR']} F={c['FALSE_CLEAN']} W={c['WRONG_REPAIR']}")

    print("\n=== failures ===")
    for cat, sent, verdict in failures:
        print(f"   {cat:14} {verdict:16} {sent}")

    n = len(cases)
    correct = tally["CORRECT_CLEAN"] + tally["CORRECT_REPAIR"]
    needed = n - tally["CORRECT_CLEAN"]
    recovered = tally["CORRECT_REPAIR"]
    wrong = tally["FALSE_CLEAN"] + tally["WRONG_REPAIR"]
    print("\n=== tally ===")
    for k in ["CORRECT_CLEAN", "CORRECT_REPAIR", "FALSE_CLEAN", "WRONG_REPAIR", "BIFURCATE", "FALLBACK"]:
        print(f"   {k:16} {tally[k]}")
    print(f"\n   total                 {n}")
    print(f"   overall correct       {correct}/{n}  ({correct / n:.0%})")
    if needed:
        print(f"   repair recovery       {recovered}/{needed} of degraded ({recovered / needed:.0%})")
    print(
        f"   wrong-frame cost      {wrong}/{n}  ({wrong / n:.0%})  "
        f"[false-clean {tally['FALSE_CLEAN']}, wrong-repair {tally['WRONG_REPAIR']}]"
    )


def _corpus_sentences():
    out = []
    if os.path.exists(SLICE):
        out += [l.strip() for l in open(SLICE) if l.strip()]
    if os.path.exists(JAR):
        with zipfile.ZipFile(JAR) as z:
            for m in STORY_MEMBERS:
                try:
                    text = z.read(m).decode("utf-8", "ignore")
                except KeyError:
                    continue
                for raw in text.splitlines():
                    for s in re.split(r"(?<=\.)\s+", raw.strip()):
                        s = s.strip()
                        if s and not s.startswith(("//", "Insert", "Start", "Set", "The end")) and s.endswith("."):
                            out.append(s)
    # dedup, drop one-word
    seen, uniq = set(), []
    for s in out:
        if s not in seen and len(s.split()) >= 2:
            seen.add(s)
            uniq.append(s)
    return uniq


def natural_pass() -> None:
    rep = Tier1Repair()
    sents = _corpus_sentences()
    simple = [s for s in sents if len(s.split()) <= 5 and not SUBORD.search(s)]
    complex_ = [s for s in sents if s not in simple]
    print("\n\n########## NATURAL CORPUS (descriptive, no gold) ##########")
    for label, group in [("SIMPLE (in tier-1 scope)", simple), ("COMPLEX (out of scope)", complex_)]:
        dist: Counter = Counter()
        examples = defaultdict(list)
        for s in group:
            v = rep.repair(s)["verdict"]
            dist[v] += 1
            if len(examples[v]) < 3:
                examples[v].append(s)
        print(f"\n=== {label}  (n={len(group)}) ===")
        for v, c in dist.most_common():
            print(f"   {v:16} {c:3}   e.g. {examples[v]}")


if __name__ == "__main__":
    main()
    natural_pass()
