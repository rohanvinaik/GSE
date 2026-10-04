"""Evaluate the ALIAS-FREE entity leg against Wikipedia's misspelling-redirects.

The thesis measurement, entity edition: the correction path uses NO collated
error-pair data (gse/nlp/spellcheck_entity.py runs on canonical labels + the closed
edit model + the pagerank prior). Wikipedia's redirect table — humans collating
"the entity people actually mean when they mistype" — is held out and used ONLY
here, as the eval corpus: how much of what the collated data knows does pure
structure recover?

Eval slice (from genealogy.db world_thread src='alias' rows — never read at
correction time): single-token alphabetic aliases that (a) do NOT ground in the
entity dictionary (an alias that is itself a real name — "bosnia" — is an alternate
name, not a misspelling), (b) target an entity that has at least one name IN the
entity dictionary (misspellings of common-word articles — "aadvark"→aardvark — are
the WORD substrate's jurisdiction: the orthographic law assigns common words to the
word leg, so the entity leg cannot and should not recover them), and (c) sit within
Damerau edit-2 of one of the entity's names (the in-reach class; farther redirects
are phonetic/abbreviation rewrites, counted separately as beyond-reach).

Success = the leg commits a name whose canon is the redirect's target entity.

    python scripts/eval_entity_leg.py [N_SAMPLE]
"""
from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gse.nlp.spellcheck import _damerau  # noqa: E402
from gse.nlp.spellcheck_entity import (  # noqa: E402
    _DEFAULT_ENTITIES,
    correct_entity,
)

_REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
_GENEALOGY = os.path.join(_REPO_ROOT, "data", "genealogy.db")


def entity_names_of(canon: str) -> list:
    """The canon's names as the dictionary derives them (tokens >=4 alpha + the
    single-token label itself) — the in-reach targets a misspelling points at."""
    toks = [t for t in canon.split() if len(t) >= 4 and t.isalpha()]
    if " " not in canon and canon.isalpha():
        toks.append(canon)
    return toks


def main(n_sample: int = 4000) -> None:
    conn = sqlite3.connect(f"file:{_GENEALOGY}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT DISTINCT label, canon FROM world_thread"
        " WHERE src='alias' AND canon IS NOT NULL AND label != canon"
        " ORDER BY label"
    ).fetchall()
    conn.close()

    in_reach = []
    beyond = 0
    considered = 0
    for alias, canon in rows:
        if " " in alias or not alias.isalpha() or len(alias) < 4:
            continue
        if _DEFAULT_ENTITIES.grounds(alias):
            continue                          # a real alternate name, not a misspelling
        # jurisdiction: the target must be reachable IN the entity space
        names = [nm for nm in entity_names_of(canon) if _DEFAULT_ENTITIES.grounds(nm)]
        if not names:
            continue
        considered += 1
        d = min(_damerau(alias, nm) for nm in names)
        if d == 0:
            considered -= 1
            continue
        if d <= 2:
            in_reach.append((alias, canon))
        else:
            beyond += 1
        if considered >= n_sample:
            break

    committed_right = committed_wrong = abstained = offered_right = no_cands = 0
    wrong_examples = []
    for alias, canon in in_reach:
        r = correct_entity(alias)
        if not r.fired:
            continue
        if r.committed is None:
            if r.ranked:
                abstained += 1
                if any(c.canon == canon for c in r.ranked[:5]):
                    offered_right += 1
            else:
                no_cands += 1
            continue
        top = next(c for c in r.ranked if c.name == r.committed)
        if top.canon == canon or r.committed in entity_names_of(canon):
            committed_right += 1
        else:
            committed_wrong += 1
            if len(wrong_examples) < 12:
                wrong_examples.append((alias, r.committed, canon))

    n = len(in_reach)
    total_fired = committed_right + committed_wrong + abstained + no_cands
    print(f"misspelling-redirect slice: {considered} single-token non-name aliases; "
          f"{n} in edit-2 reach ({beyond} beyond reach — phonetic/abbrev rewrites)")
    print(f"  committed correct : {committed_right:5d}  ({committed_right/max(1,total_fired):6.1%})")
    print(f"  committed wrong   : {committed_wrong:5d}  ({committed_wrong/max(1,total_fired):6.1%})")
    print(f"  abstained         : {abstained:5d}  (right answer in top-5 offers: {offered_right})")
    print(f"  no candidate      : {no_cands:5d}")
    ok = committed_right + offered_right
    print(f"  recovered-or-offered: {ok/max(1,total_fired):6.1%}")
    if wrong_examples:
        print("  wrong commits (sample):")
        for a, got, want in wrong_examples:
            print(f"    {a} -> {got}  (redirect target: {want})")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4000)
