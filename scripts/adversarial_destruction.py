"""Adversarial destruction bound: how often does the corrector make a RIGHT word WRONG?

Destruction = committing a *different* word for an input that is itself a valid word.
We take a clean English reference vocabulary, isolate the danger zone (valid words the
system does NOT recognize AND that the shape gate doesn't already protect), run the
corrector, and count how many get changed. This converts "as far as we can tell, it
never destroys real information" into a measured rate, with the actual failures listed.

Run:  python scripts/adversarial_destruction.py
"""

import sys
import time

sys.path.insert(0, "/Users/rohanvinaik/Projects/gse")
from gse.nlp.spellcheck import _DEFAULT_LEXICON as LX
from gse.nlp.spellcheck import WORD_COMMIT_MARGIN, Candidate, _edits1, looks_non_lexical

REF = "/usr/share/dict/web2"  # ~234k clean English words, independent of our build


def edit1_commit(w):
    """The word the corrector would COMMIT for ``w`` via the edit-1 path, or None.
    Mirrors correct()'s scoring + margin, edit-1 only — which is where destruction
    lives: an edit-2 correction costs >=3, fails the commit margin, and abstains. So
    this is the meaningful destruction bound, and it runs over the FULL danger zone
    without the edit-2 candidate explosion."""
    cands = [Candidate(c, ec, LX.prior(c)) for c, ec in _edits1(w).items() if LX.grounds(c)]
    if not cands:
        return None
    cands.sort(key=lambda c: (c.score, c.word))
    best = cands[0]
    second = cands[1] if len(cands) > 1 else None
    if second is None or (second.score - best.score) >= WORD_COMMIT_MARGIN:
        return best.word
    return None


def load_ref():
    out = set()
    for line in open(REF, encoding="latin-1"):
        w = line.strip().lower()
        if w.isalpha() and 3 <= len(w) <= 20:
            out.add(w)
    return sorted(out)


def main():
    ref = load_ref()
    # danger zone: a valid word the corrector neither recognizes nor shape-gates
    at_risk = [w for w in ref if not LX.grounds(w) and not looks_non_lexical(w)]
    print(f"reference (clean English, {REF}): {len(ref):,} words", flush=True)
    print(
        f"danger zone (valid, UNrecognized, ordinary-shaped): {len(at_risk):,} "
        f"({len(at_risk) / len(ref):.1%} of reference)",
        flush=True,
    )
    print(f"scanning ALL {len(at_risk):,} danger-zone words (edit-1 destruction)…", flush=True)

    t0 = time.time()
    sample = at_risk  # full coverage, no sampling
    destroyed = []
    for w in sample:
        c = edit1_commit(w)
        if c and c != w:
            destroyed.append((w, c))
    dz_rate = len(destroyed) / max(1, len(sample))  # destruction | in danger zone
    print(f"\nDESTROYED (valid word -> a DIFFERENT word): {len(destroyed):,} / {len(sample):,}", flush=True)
    print(f"  destruction rate WITHIN danger zone : {dz_rate:.2%}")
    print(
        f"  unweighted rate over ALL of web2    : {len(destroyed) / len(ref):.4%}"
        f"  (web2 = Webster's 1934, archaic-heavy)"
    )
    print(f"  (scanned {len(at_risk):,} danger-zone words in {time.time() - t0:.0f}s)")

    # frequency-WEIGHTED rate — the number that matters: destruction as a fraction of
    # real word-usage, not of dictionary entries. Obscure archaisms have ~0 weight.
    import sqlite3

    try:
        conn = sqlite3.connect("data/frequency.db")
        wt = {w.lower(): float(x) for w, x in conn.execute("SELECT word, weight FROM frequency")}
        destroyed_set = {w for w, _ in destroyed}
        denom = sum(wt.get(w, 0.0) for w in ref)
        numer = sum(wt.get(w, 0.0) for w in destroyed_set)
        print(f"\n  FREQUENCY-WEIGHTED destruction (by real usage): {numer / denom:.5%}  <- the real-world rate")
        in_freq = sum(1 for w, _ in destroyed if w in wt)
        print(f"  destroyed words that even appear in a real-usage frequency list: {in_freq}/{len(destroyed)}")
    except Exception as e:
        print("  (frequency weighting skipped:", e, ")")

    print("\n  sample destroyed pairs (note: obscure -> obscure):")
    for w, c in destroyed[:25]:
        print(f"    {w:<18} -> {c}")


if __name__ == "__main__":
    main()
