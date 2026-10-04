#!/usr/bin/env python3
"""Locate the bulk→tail KNEE (H*) of the Semantic Completeness Equation — measured, not assumed.

`sigma_sem_learning.py` established the transition EXISTS (bulk C=2.44 → tail 0.03, 8/8 orders) but
split the curve at a fixed midpoint. This script LOCATES H*: it teaches facts in hub-first order and
records the per-fact marginal coverage Δ(t) = κ (new readings resolved), then finds the knee two
independent, principled ways:

  1. LintGate transition-step (the ported definition): H* = first t with Δ(t) < 2  (cluster threshold;
     the seam where each taught fact stops resolving a *cluster* and starts resolving ~one reading).
  2. Curvature knee (Kneedle-style): max-curvature point of the cumulative-coverage curve — an
     independent detector that assumes nothing about the threshold.

It also characterizes the coverage-degree distribution |cover(v)| (the hub-score): top-decile share,
Gini, and a Clauset-MLE power-law exponent γ — because a SHARP knee requires a heavy tail (a regular
graph gives a smooth slope, no knee, and the H* theorem would be vacuous). If the tail is light, that
is the honest finding and we report the smooth decline instead.

Discrete IS-A `_jaccard` only — NO cosine (composes the real GSE resolver; meaning is structure).
Hub-first order is by standalone |cover(v)| (the equation's cover(v)); gold is eval-only.

Usage: python scripts/sigma_sem_knee.py [--files N] [--max-sents-per-file M] [--out results.json]
"""

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _powerlaw_gamma(xs, xmin):
    """Clauset MLE exponent for a discrete power law above xmin: γ = 1 + n / Σ ln(x / (xmin-0.5))."""
    tail = [x for x in xs if x >= xmin]
    n = len(tail)
    if n < 10:
        return None, n
    s = sum(math.log(x / (xmin - 0.5)) for x in tail)
    if s <= 0:
        return None, n
    return 1.0 + n / s, n


def _gini(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0 or sum(xs) == 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return (2 * cum) / (n * sum(xs)) - (n + 1) / n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=15)
    ap.add_argument("--max-sents-per-file", type=int, default=30)
    ap.add_argument("--out", type=str, default=str(ROOT / "data" / "sigma_sem_knee.json"))
    args = ap.parse_args()

    import nltk

    for pkg, path in [("semcor", "corpora/semcor"), ("wordnet", "corpora/wordnet")]:
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(pkg, quiet=True)
    from nltk.corpus import semcor
    from nltk.corpus import wordnet as wn
    from nltk.corpus.reader.wordnet import Lemma

    from gse.symbolic import GenealogyStore
    from gse.symbolic.grounding import _jaccard

    store = GenealogyStore()
    print("[KNEE — locating H* on the real GSE coverage curve; discrete _jaccard, NO cosine]\n")

    # Same pool as sigma_sem_learning.py: (gold_nodes, [competitor_node_sets]) per polysemous gold noun.
    pool = []
    for fid in semcor.fileids()[: args.files]:
        for tsent in semcor.tagged_sents(fid, tag="sem")[: args.max_sents_per_file]:
            for chunk in tsent:
                if not (isinstance(chunk, nltk.Tree) and isinstance(chunk.label(), Lemma)):
                    continue
                syn = chunk.label().synset()
                if syn.pos() != "n":
                    continue
                lemma, gold = chunk.label().name().split("%")[0].lower(), syn.name()
                snames = [s.name() for s in wn.synsets(lemma, wn.NOUN)]
                if len(snames) < 2 or gold not in snames:
                    continue
                cands = [tuple(t) for t in store.candidates(lemma, "NOUN", False)]
                if len(cands) != len(snames):
                    continue
                gnodes = set(cands[snames.index(gold)])
                comps = [set(cands[i]) for i, s in enumerate(snames) if s != gold]
                if comps:
                    pool.append({"gold": gnodes, "comps": comps})

    total = len(pool)
    if total < 20:
        print("pool too small — increase --files")
        return 1
    H0 = sum(math.log2(1 + len(t["comps"])) for t in pool)

    def resolves(i, ctx):
        """Reading i resolves iff its gold strictly out-overlaps every competitor vs ctx."""
        gj = _jaccard(pool[i]["gold"], ctx)
        return all(_jaccard(c, ctx) < gj for c in pool[i]["comps"])

    def resolved_against(ctx):
        """Set of reading indices resolved vs ctx (standalone; used only for single-fact cover(v))."""
        return {i for i in range(total) if resolves(i, ctx)}

    # Standalone hub-score h(v) = |cover(v)| = readings v resolves alone (the equation's cover(v)).
    print(f"pool = {total} polysemous gold noun tokens; H₀ = {H0:.1f} bits")
    print("computing standalone cover(v) for all v ...")
    cover = [resolved_against(pool[v]["gold"]) for v in range(total)]
    hub = [len(cover[v]) for v in range(total)]

    # Coverage-degree distribution characterization (is the tail heavy enough for a sharp knee?)
    nz = [h for h in hub if h > 0]
    top_decile = sorted(hub, reverse=True)[: max(1, total // 10)]
    top_share = sum(top_decile) / max(1, sum(hub))
    gini = _gini(hub)
    xmin = max(2, (sorted(nz)[len(nz) // 2] if nz else 2))  # median of nonzero as a simple xmin
    gamma, n_tail = _powerlaw_gamma(nz, xmin)

    # Knee of the PROVED object: the submodular coverage function f(S) = |⋃_{v∈S} cover(v)| under the
    # GREEDY (max-marginal) order — this is exactly what `coverage_submodular`/`marginal_antitone` govern,
    # so its marginal Δ(t) = κ(v|S) IS antitone and the transition step is well-defined. (Greedy over the
    # precomputed standalone cover sets; stops when the union saturates = nothing left to add.)
    bits = [math.log2(1 + len(pool[i]["comps"])) for i in range(total)]
    reachable = set().union(*cover) if cover else set()
    union, remaining, deltas, cum, order, H_traj = set(), set(range(total)), [], [], [], []
    while remaining:
        v = max(remaining, key=lambda u: len(cover[u] - union))
        marg = len(cover[v] - union)
        if marg == 0:
            break  # union saturated — remaining facts add nothing
        union |= cover[v]
        remaining.discard(v)
        deltas.append(marg)
        cum.append(len(union))
        order.append(v)
        H_traj.append(sum(bits[i] for i in range(total) if i not in union))

    # H* locator 1 — LintGate transition step: first t with Δ(t) < 2 (cluster threshold).
    hstar_ts = next((t for t, d in enumerate(deltas) if d < 2), len(deltas))

    # H* locator 2 — curvature knee (Kneedle): normalize cum curve, max distance above the chord.
    n = len(cum)
    if n >= 3:
        ymax = cum[-1] or 1
        y = [c / ymax for c in cum]
        x = [i / (n - 1) for i in range(n)]
        dist = [y[i] - x[i] for i in range(n)]  # concave curve bows above the diagonal; knee = max gap
        hstar_knee = max(range(n), key=lambda i: dist[i])
    else:
        hstar_knee = n

    # Entropy still unresolved at H* (from the sticky trajectory), bulk/tail amplification either side.
    Hstar_bits = H_traj[hstar_ts] if hstar_ts < len(H_traj) else H_traj[-1]
    bulk = sum(deltas[:hstar_ts]) / max(1, hstar_ts)
    tail = sum(deltas[hstar_ts:]) / max(1, len(deltas) - hstar_ts)

    res = {
        "pool": total,
        "H0_bits": round(H0, 1),
        "hub_score": {
            "max": max(hub),
            "mean": round(sum(hub) / total, 2),
            "nonzero": len(nz),
            "top_decile_coverage_share": round(top_share, 3),
            "gini": round(gini, 3),
            "powerlaw_gamma": (round(gamma, 2) if gamma else None),
            "gamma_tail_n": n_tail,
            "xmin": xmin,
        },
        "Hstar_transition_step": hstar_ts,
        "Hstar_transition_frac": round(hstar_ts / total, 3),
        "Hstar_knee_curvature": hstar_knee,
        "Hstar_knee_frac": round(hstar_knee / total, 3),
        "Hstar_bits_unresolved": round(Hstar_bits, 1),
        "Hstar_over_H0": round(Hstar_bits / H0, 3) if H0 else None,
        "bulk_amp_per_fact": round(bulk, 2),
        "tail_amp_per_fact": round(tail, 2),
        "bulk_tail_ratio": round(bulk / tail, 1) if tail > 0 else None,
        "greedy_bulk_len": len(order),
        "reachable_coverage": len(reachable),
        "reachable_frac": round(len(reachable) / total, 3),
        "curve_deltas_head": deltas[:20],
        "cum_coverage_final": cum[-1] if cum else 0,
    }
    Path(args.out).write_text(json.dumps(res, indent=2))

    print(
        f"\nHUB-SCORE |cover(v)|: max={res['hub_score']['max']} mean={res['hub_score']['mean']} "
        f"top-decile share={top_share:.0%} Gini={gini:.2f} γ≈{res['hub_score']['powerlaw_gamma']} (n_tail={n_tail})"
    )
    heavy = top_share > 0.5 and gini > 0.5
    print(
        f"  → tail is {'HEAVY (sharp knee expected)' if heavy else 'LIGHT (expect a smooth decline, not a sharp knee)'}"
    )
    print(
        f"\nH*  transition-step (Δ<2): fact #{hstar_ts} ({100 * hstar_ts / total:.0f}% of curriculum), "
        f"= {Hstar_bits:.0f} bits unresolved ({100 * Hstar_bits / H0:.0f}% of H₀)"
    )
    print(
        f"H*  curvature knee       : fact #{hstar_knee} ({100 * hstar_knee / total:.0f}%)  "
        f"[{'AGREES' if abs(hstar_ts - hstar_knee) <= max(3, total // 20) else 'DIVERGES'} with transition-step]"
    )
    print(f"\nbulk amp = {bulk:.2f}/fact  →  tail amp = {tail:.2f}/fact   (ratio {res['bulk_tail_ratio']}×)")
    print(f"\nsaved → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
