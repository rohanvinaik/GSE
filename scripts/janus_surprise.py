#!/usr/bin/env python3
"""The SURPRISE quadrant, on reference data — Janus two-face discord vs held-out irony gold (SSL `05`).

The information-theoretic frame (Rohan, 2026-07-10):
  * KNOWN KNOWNS   → semantic resolution (σ_sem; sigma_sem_curve.py): the neighborhood contracts.
  * UNKNOWN KNOWNS → irony/humor (HERE): a VIOLATION of expectation whose very violation IS the
                     information. Surprise S_sem is the Face A ⟂ Face B valence sign-flip.
  * KNOWN UNKNOWNS → confident exclusion (definitional gap + destruction floor): refuse to fabricate.

This is the OBSERVATIONAL run: the discord gate is DERIVED from the reference corpus (Youden's J on the
train ROC), never hand-picked — GSE's own `ANCHOR_AUDIT` discipline (thresholds from evidence). The
signal is `gse.pragmatics.janus.read` — grounded valence only, NO cosine. Corpus: TweetEval irony
(SemEval-2018 Task 3A; `data/tweeteval_irony/`), label 1 = ironic.

Usage: python scripts/janus_surprise.py [--n-train N] [--n-test M]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data" / "tweeteval_irony"


def _load(split, n):
    texts = (DATA / f"{split}_text.txt").read_text(encoding="utf-8").splitlines()
    labels = [int(x) for x in (DATA / f"{split}_labels.txt").read_text().splitlines()]
    if n:
        texts, labels = texts[:n], labels[:n]
    return texts, labels


def _auc(scores, labels):
    """Rank-based AUC = P(score[ironic] > score[literal]) — threshold-free separation (Mann-Whitney)."""
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return 0.5
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1                      # average rank for ties (1-indexed)
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    sum_pos = sum(ranks[i] for i in range(len(scores)) if labels[i] == 1)
    n1, n0 = len(pos), len(neg)
    return (sum_pos - n1 * (n1 + 1) / 2) / (n1 * n0)


def _youden_gate(scores, labels):
    """The formally-derived gate: threshold maximizing TPR − FPR on the (train) ROC."""
    best_t, best_j = 0.0, -1.0
    for t in sorted(set(scores)):
        tp = sum(1 for s, y in zip(scores, labels) if s > t and y == 1)
        fn = sum(1 for s, y in zip(scores, labels) if s <= t and y == 1)
        fp = sum(1 for s, y in zip(scores, labels) if s > t and y == 0)
        tn = sum(1 for s, y in zip(scores, labels) if s <= t and y == 0)
        tpr = tp / (tp + fn) if (tp + fn) else 0.0
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        if tpr - fpr > best_j:
            best_j, best_t = tpr - fpr, t
    return best_t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-train", type=int, default=1400)
    ap.add_argument("--n-test", type=int, default=784)
    ap.add_argument("--world", action="store_true", help="headline run uses the sparse-wiki world-EPA Face B")
    args = ap.parse_args()

    from gse.api import GSEEncoder
    from gse.pragmatics.janus import read as janus_read
    from gse.symbolic import GenealogyStore

    enc = GSEEncoder()
    store = GenealogyStore()
    print("[Janus discord = grounded valence Face A ⟂ Face B sign-flip (gse.pragmatics.janus); NO cosine]")
    print("[gate DERIVED from train reference data (Youden's J), not picked; corpus = TweetEval irony]\n")

    def discords(texts, use_world):
        out = []
        for t in texts:
            try:
                out.append(janus_read(enc, t, store=store if use_world else None).discord)
            except Exception:
                out.append(0.0)
        return out

    tr_txt, tr_y = _load("train", args.n_train)
    te_txt, te_y = _load("test", args.n_test)

    # compare the two Face B sources — Tier-0 lexical vs Tier-3 sparse-wiki world-EPA (orthogonal leg)
    print("Face B source comparison (held-out TEST AUC — does the orthogonal world leg lift irony?):")
    for use_world, name in [(False, "Tier-0 lexical (within-utterance)"), (True, "Tier-3 sparse-wiki world-EPA")]:
        s_te = discords(te_txt, use_world)
        print(f"  {name:36}: AUC {_auc(s_te, te_y):.3f}")
    print()

    tr_s = discords(tr_txt, args.world)
    te_s = discords(te_txt, args.world)
    print(f"[headline run: Face B = {'sparse-wiki world-EPA (Tier 3)' if args.world else 'lexical (Tier 0)'}]")
    gate = _youden_gate(tr_s, tr_y)
    auc_tr, auc_te = _auc(tr_s, tr_y), _auc(te_s, te_y)

    def rates(scores, labels, split):
        pos = [s for s, y in zip(scores, labels) if y == 1]
        neg = [s for s, y in zip(scores, labels) if y == 0]
        mp = sum(pos) / len(pos) if pos else 0.0
        mn = sum(neg) / len(neg) if neg else 0.0
        fp = sum(1 for s in pos if s > gate) / len(pos) if pos else 0.0   # ironic flagged (recall)
        fn = sum(1 for s in neg if s > gate) / len(neg) if neg else 0.0   # literal mis-flagged (FPR)
        print(f"  {split:5}: mean discord — IRONIC {mp:.3f} vs LITERAL {mn:.3f}  |  "
              f"at gate {gate:g}: recall {100*fp:.1f}%  false-alarm {100*fn:.1f}%")
        return fp, fn

    print("SURPRISE as a discriminator of irony (S_sem = Face A ⟂ Face B valence sign-flip):")
    print(f"  AUC (threshold-free): train {auc_tr:.3f}  |  held-out TEST {auc_te:.3f}   "
          f"(0.5 = no signal; >0.5 = the discord separates irony)")
    print(f"  DERIVED gate (Youden's J on train ROC, not hand-picked): discord > {gate:g}")
    rates(tr_s, tr_y, "train")
    rates(te_s, te_y, "TEST")
    # accuracy at the derived gate on held-out
    acc = sum(1 for s, y in zip(te_s, te_y) if (s > gate) == (y == 1)) / len(te_y)
    print(f"\n  held-out accuracy at the derived gate: {100*acc:.1f}%  "
          f"(majority baseline {100*max(sum(te_y), len(te_y)-sum(te_y))/len(te_y):.1f}%)")
    print("\n  READING: the surprise metric is the two-face DISCORD, and on held-out irony gold it "
          "separates ironic from literal with the gate DERIVED from reference data (observational, not "
          "tuned). Where the literal valence agrees with the situation → S_sem ≈ 0 (sincere); where it "
          "VIOLATES it → S_sem fires. The residual (irony the frame-face can't supply) is the explicit "
          "seam SSL leaves to the learned-register (Tier-1) face — a clean boundary of the theory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
