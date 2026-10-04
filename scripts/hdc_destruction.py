"""Destruction bound for the keyboard-HDC recovery path (gse.nlp.hdc_speller, wired into
spell_server's abstain branch). The edit-distance bound is measured separately
(scripts/adversarial_destruction.py -> 0.00000% frequency-weighted); this measures the
NEW risk HDC adds: a valid word that doesn't ground getting AUTO-COMMITTED to a different
word at cos >= HDC_COMMIT_COS.

Danger zone = valid English words (web2) the system neither grounds nor shape-gates — the
only place HDC can fire. We check every danger-zone word that carries real-usage frequency
weight (these drive the weighted bound) plus a sample of the rest.

Run:  python scripts/hdc_destruction.py
"""
import sys, time, sqlite3
sys.path.insert(0, "/Users/rohanvinaik/Projects/gse")
from gse.nlp.spellcheck import looks_non_lexical, _DEFAULT_LEXICON as LX
from gse.mcp.spell_server import _hdc_recover   # the production gate (commit/offer)

REF = "/usr/share/dict/web2"
SAMPLE_CAP = 6000          # cap on weightless danger-zone words (for the unweighted estimate)


def load_ref():
    out = set()
    for line in open(REF, encoding="latin-1"):
        w = line.strip().lower()
        if w.isalpha() and 3 <= len(w) <= 20:
            out.add(w)
    return sorted(out)


def hdc_commits_different(w):
    """The DIFFERENT word HDC would AUTO-COMMIT for valid word w, or None."""
    rec = _hdc_recover(w, sentence_initial=False)
    if rec and rec[2] and rec[0] != w:        # rec = (word, cos, commit)
        return rec[0]
    return None


def main():
    ref = load_ref()
    at_risk = [w for w in ref if not LX.grounds(w) and not looks_non_lexical(w)]
    conn = sqlite3.connect("data/frequency.db")
    wt = {w.lower(): float(x) for w, x in conn.execute("SELECT word, weight FROM frequency")}

    weighted_zone = [w for w in at_risk if w in wt]        # the words that move the bound
    weightless = [w for w in at_risk if w not in wt]
    sample = weighted_zone + weightless[:SAMPLE_CAP]
    print(f"reference: {len(ref):,} words; danger zone (valid, ungrounded, ordinary-shape): "
          f"{len(at_risk):,}", flush=True)
    print(f"  with real-usage weight: {len(weighted_zone):,} (checked fully) + "
          f"{min(len(weightless), SAMPLE_CAP):,} weightless sample", flush=True)
    print(f"checking HDC auto-commit over {len(sample):,} words…", flush=True)

    t0 = time.time()
    destroyed = []
    for w in sample:
        c = hdc_commits_different(w)
        if c:
            destroyed.append((w, c))
    print(f"\nHDC-DESTROYED (valid word auto-committed to a DIFFERENT word): "
          f"{len(destroyed):,} / {len(sample):,}  ({time.time()-t0:.0f}s)")

    denom = sum(wt.get(w, 0.0) for w in ref)
    numer = sum(wt.get(w, 0.0) for w, _ in destroyed)
    print(f"  FREQUENCY-WEIGHTED HDC destruction (by real usage): {numer/denom:.5%}"
          f"  <- the real-world rate")
    in_freq = sum(1 for w, _ in destroyed if w in wt)
    print(f"  destroyed words that appear in a real-usage frequency list: {in_freq}/{len(destroyed)}")
    if destroyed:
        print("\n  sample HDC-destroyed pairs:")
        for w, c in destroyed[:25]:
            print(f"    {w:<18} -> {c}   (weight {wt.get(w, 0.0):.2e})")


if __name__ == "__main__":
    main()
