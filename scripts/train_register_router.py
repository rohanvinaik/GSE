#!/usr/bin/env python3
"""Train + evaluate the SoM register router on the L2 corpus.

Three-stage curriculum (per the SoM design): specialists → frozen-specialist
orchestrator → joint fine-tune. Stratified k-fold cross-validation (the corpus is
classical-AI-scale — small/curated), reporting:

  * a baseline (logistic regression on the raw profile) — the signal-quality floor;
  * specialists-alone vs the composed router — the compositionality gain;
  * register_class (speech/non_speech) accuracy — the coarse axis;
  * the most-confused genre pairs — which registers to grow the corpus on next.

A final model trained on all data is saved for the runtime dispatcher.

Usage: python scripts/train_register_router.py [--corpus data/l2_corpus.jsonl] [--folds 4]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "data" / "l2_corpus.jsonl"))
    ap.add_argument("--folds", type=int, default=4)
    ap.add_argument("--level", default="super_register",
                    choices=["genre", "super_register", "register_class"])
    ap.add_argument("--out", default=str(ROOT / "data" / "register_router.pt"))
    ap.add_argument("--nested", action="store_true",
                    help="train the hierarchical/nested SoM (a specialist per taxonomy "
                         "node, confidence-gated descent) instead of the flat per-level "
                         "model; reports register_class + super_register + genre accuracy")
    args = ap.parse_args()

    import numpy as np
    import torch
    import torch.nn as nn
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler

    from gse.discourse import register_class_of, super_register_of
    from gse.discourse.router import BANKS, RegisterRouter

    torch.manual_seed(0)
    np.random.seed(0)

    levelfn = {"genre": lambda g: g, "super_register": super_register_of,
               "register_class": register_class_of}[args.level]
    rows = [json.loads(l) for l in open(args.corpus)]
    labels = sorted({levelfn(r["genre"]) for r in rows})
    li = {lab: i for i, lab in enumerate(labels)}
    X = np.array([r["vector"] for r in rows], dtype=np.float32)
    y = np.array([li[levelfn(r["genre"])] for r in rows])
    # bank slice boundaries (BANKS order, keys sorted — matches TextProfile.vector()).
    sizes = [len(rows[0]["banks"][b]) for b in BANKS]
    bnd = np.cumsum([0] + sizes)
    print(f"corpus: {len(rows)} docs | level={args.level} → {len(labels)} classes "
          f"| {X.shape[1]}-dim ({'+'.join(map(str, sizes))} banks)")

    if args.nested:
        # Hierarchical SoM: a specialist per taxonomy node, evaluated by confidence-
        # gated descent. Stratify folds on super_register (the comparison level).
        from gse.discourse.nested_router import NestedRouter
        genres = np.array([r["genre"] for r in rows])
        sup = np.array([super_register_of(g) for g in genres])
        rc = np.array([register_class_of(g) for g in genres])
        sup_labels = sorted(set(sup))
        y_strat = np.array([sup_labels.index(s) for s in sup])
        skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=0)
        rc_acc, sup_acc, gen_acc = [], [], []
        confusion = defaultdict(int)
        for tr, te in skf.split(X, y_strat):
            nr = NestedRouter(sizes, X.shape[1]).fit(X[tr], list(genres[tr]))
            p_rc = nr.predict_at(X[te], "register_class")
            p_sup = nr.predict_at(X[te], "super_register")
            p_gen = nr.predict_at(X[te], "genre")
            rc_acc.append(np.mean([a == b for a, b in zip(p_rc, rc[te])]))
            sup_acc.append(np.mean([a == b for a, b in zip(p_sup, sup[te])]))
            gen_acc.append(np.mean([a == b for a, b in zip(p_gen, genres[te])]))
            for a, b in zip(p_sup, sup[te]):
                if a != b:
                    confusion[tuple(sorted((b, a)))] += 1
        def _fmt(v):
            return f"{np.mean(v):.3f} ± {np.std(v):.3f}"
        print(f"\n  HIERARCHICAL SoM — {len(sup_labels)} super-registers, "
              f"{len(set(genres))} genres, {len(nr.nodes)} node-specialists")
        print(f"  register_class (root)            = {_fmt(rc_acc)}")
        print(f"  super_register (descent)         = {_fmt(sup_acc)}   <- vs flat 0.713")
        print(f"  genre (full descent)             = {_fmt(gen_acc)}   (leaf; sparse/fold)")
        print(f"\n  most-confused super_register pairs (post-cascade):")
        for (a, b), n in sorted(confusion.items(), key=lambda kv: -kv[1])[:8]:
            print(f"    {n}×  {a} ~ {b}")
        return 0

    def slices(t):  # full tensor -> list of per-bank tensors
        return [t[:, bnd[i]:bnd[i + 1]] for i in range(len(BANKS))]

    def train_fold(Xtr, ytr):
        scaler = StandardScaler().fit(Xtr)
        xt = torch.tensor(scaler.transform(Xtr), dtype=torch.float32)
        yt = torch.tensor(ytr)
        bx = slices(xt)
        m = RegisterRouter(sizes, X.shape[1], len(labels))
        ce = nn.CrossEntropyLoss()

        def run(params, lr, epochs):
            opt = torch.optim.AdamW(params, lr=lr, weight_decay=1e-3)
            for _ in range(epochs):
                opt.zero_grad()
                spec = m.specialist_logits(bx, xt)            # [B,S,G]
                if stage == 1:
                    loss = sum(ce(spec[:, s], yt) for s in range(len(BANKS)))
                else:
                    loss = ce(m(bx, xt), yt)
                loss.backward(); opt.step()

        stage = 1; run(m.specialists.parameters(), 3e-3, 250)          # specialists
        m.freeze_specialists(True)
        stage = 2; run([p for p in m.parameters() if p.requires_grad], 3e-3, 150)
        m.freeze_specialists(False)
        stage = 3; run(m.parameters(), 3e-4, 150)                       # joint
        return m, scaler

    skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=0)
    base_acc, spec_acc, comp_acc, rc_acc = [], [], [], []
    confusion = defaultdict(int)
    for tr, te in skf.split(X, y):
        # baseline
        base = LogisticRegression(max_iter=2000, C=1.0).fit(
            StandardScaler().fit_transform(X[tr]), y[tr])
        sc0 = StandardScaler().fit(X[tr])
        base_acc.append((base.predict(sc0.transform(X[te])) == y[te]).mean())
        # SoM
        m, scaler = train_fold(X[tr], y[tr])
        m.eval()
        with torch.no_grad():
            xte = torch.tensor(scaler.transform(X[te]), dtype=torch.float32)
            bxe = slices(xte)
            spec = m.specialist_logits(bxe, xte)              # [B,S,G]
            comp = m(bxe, xte).argmax(1).numpy()
            specm = spec.mean(1).argmax(1).numpy()            # specialists alone (no trust)
        spec_acc.append((specm == y[te]).mean())
        comp_acc.append((comp == y[te]).mean())
        # coarse register_class agreement (poetry/reference/list = non_speech).
        nonsp = {"poetry", "reference", "list"}
        coarse = lambda lab: "non_speech" if lab in nonsp else "speech"
        rc_acc.append(np.mean([coarse(labels[p]) == coarse(labels[t])
                               for p, t in zip(comp, y[te])]))
        for p, t in zip(comp, y[te]):
            if p != t:
                confusion[tuple(sorted((labels[t], labels[p])))] += 1

    def pm(a): return f"{np.mean(a):.3f} ± {np.std(a):.3f}"
    print(f"\n  random baseline (1/{len(labels)})      = {1/len(labels):.3f}")
    print(f"  logistic-regression baseline    = {pm(base_acc)}   (signal-quality floor)")
    print(f"  SoM specialists alone (no trust)= {pm(spec_acc)}")
    print(f"  SoM composed (trust orchestr.)  = {pm(comp_acc)}   <- compositional gain")
    print(f"  register_class (speech/nonsp.)  = {pm(rc_acc)}   (coarse axis)")
    print(f"\n  most-confused {args.level} pairs (grow the corpus here):")
    for (a, b), n in sorted(confusion.items(), key=lambda kv: -kv[1])[:8]:
        print(f"    {n}×  {a} ~ {b}")

    # Final model on all data, saved for the runtime dispatcher.
    m, scaler = train_fold(X, y)
    torch.save({"state_dict": m.state_dict(), "labels": labels, "level": args.level,
                "bank_sizes": sizes, "full_dim": X.shape[1],
                "scaler_mean": scaler.mean_.tolist(),
                "scaler_scale": scaler.scale_.tolist()}, args.out)
    print(f"\n[saved] final router → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
