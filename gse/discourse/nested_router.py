"""The nested Society-of-Mind register router — the recursive recognizer.

The flat :class:`~gse.discourse.router.RegisterRouter` forces one weight-set to
separate the whole taxonomy at one depth, so the hard sub-decisions (the prose
triad — narrative vs reportorial vs essayistic) collapse against the easy ones
(poetry / list / reference) they share a softmax with.

The fix is the recursive form the taxonomy already implies: a specialist per
INTERNAL node, each a ``RegisterRouter`` classifying only among that node's
children. Inference is **confidence-gated descent** (the k-line activation) — start
at ROOT, take the child the node is confident in, descend; stop at the deepest node
whose prediction clears the gate. So "is this prose?" (register_class, ~95%) and
"which prose?" (a specialist trained *only* on the speech branch) are separate
decisions at their own levels, and a document the signal can't sub-classify simply
resolves to a shallower node rather than guessing — the honest behavior.

Each node reads the *same* GSE activation profile (the ``text_profile`` banks); the
specialists are just defined and trained on the already-labeled corpus, recursively.
Recognition depth IS resolution granularity — the seam a per-node rule-ground
(Genesis-style inheritance) plugs into later.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from gse.discourse.registers import ROOT, child_on_path, taxonomy_tree
from gse.discourse.router import RegisterRouter


def _slices(t, sizes: Sequence[int]):
    """Split a [B, full_dim] tensor into per-bank tensors (RegisterRouter's input)."""
    bnd = np.cumsum([0] + list(sizes))
    return [t[:, bnd[i]:bnd[i + 1]] for i in range(len(sizes))]


def train_router(Xtr, ytr, n_labels: int, sizes: Sequence[int], full_dim: int):
    """The three-stage SoM curriculum (specialists → frozen-orchestrator → joint),
    factored out so the flat trainer and every nested node share one recipe — the
    SAME fixed-epoch recipe the flat router has always used (this is a diagnostic
    flywheel run, not a production training run). Returns ``(model, scaler)``."""
    import torch
    import torch.nn as nn
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler().fit(Xtr)
    xt = torch.tensor(scaler.transform(Xtr), dtype=torch.float32)
    yt = torch.tensor(ytr)
    bx = _slices(xt, sizes)
    m = RegisterRouter(sizes, full_dim, n_labels)
    ce = nn.CrossEntropyLoss()

    def run(params, lr, epochs, stage):
        opt = torch.optim.AdamW(params, lr=lr, weight_decay=1e-3)
        for _ in range(epochs):
            opt.zero_grad()
            if stage == 1:
                spec = m.specialist_logits(bx, xt)            # [B,S,G]
                loss = sum(ce(spec[:, s], yt) for s in range(len(sizes)))
            else:
                loss = ce(m(bx, xt), yt)
            loss.backward()
            opt.step()

    run(m.specialists.parameters(), 3e-3, 250, 1)
    m.freeze_specialists(True)
    run([p for p in m.parameters() if p.requires_grad], 3e-3, 150, 2)
    m.freeze_specialists(False)
    run(m.parameters(), 3e-4, 150, 3)
    return m, scaler


class NestedRouter:
    """A ``RegisterRouter`` per internal taxonomy node; descend to resolve.

    Built over exactly the genres present in the training labels. A node with a
    single present child needs no router (deterministic pass-through)."""

    def __init__(self, sizes: Sequence[int], full_dim: int):
        self.sizes = list(sizes)
        self.full_dim = full_dim
        self.tree: Dict[str, List[str]] = {}
        self.nodes: Dict[str, dict] = {}     # node -> {model, scaler, labels}

    def fit(self, X: np.ndarray, genres: Sequence[str]) -> "NestedRouter":
        self.tree = taxonomy_tree(genres)
        for node, children in self.tree.items():
            if len(children) < 2:
                continue                      # deterministic; no decision to learn
            idx, ys = [], []
            for i, g in enumerate(genres):
                c = child_on_path(node, g)
                if c is not None:
                    idx.append(i)
                    ys.append(children.index(c))
            if len(set(ys)) < 2:
                continue                      # only one child present in the data
            model, scaler = train_router(
                X[idx], np.array(ys), len(children), self.sizes, self.full_dim)
            self.nodes[node] = {"model": model, "scaler": scaler, "labels": children}
        return self

    def _predict_node(self, node: str, X: np.ndarray) -> Tuple[List[str], np.ndarray]:
        """Child label + max-softmax confidence per row, at one node."""
        import torch
        d = self.nodes[node]
        d["model"].eval()
        xt = torch.tensor(d["scaler"].transform(X), dtype=torch.float32)
        bx = _slices(xt, self.sizes)
        with torch.no_grad():
            probs = torch.softmax(d["model"](bx, xt), dim=-1).numpy()
        pred = probs.argmax(1)
        return [d["labels"][i] for i in pred], probs.max(1)

    def _only_child(self, node: str) -> Optional[str]:
        ch = self.tree.get(node, [])
        return ch[0] if len(ch) == 1 else None

    def predict_paths(self, X: np.ndarray, gate: float = 0.0) -> List[List[str]]:
        """Confidence-gated descent from ROOT. Each row's path is the chain of
        resolved nodes; descent stops at a leaf, at a node with no router, or when
        the node's confidence is below ``gate`` (the deepest-confident-node rule;
        ``gate=0`` forces full descent for apples-to-apples evaluation)."""
        paths: List[List[str]] = [[] for _ in range(len(X))]
        active = list(range(len(X)))
        node_of = {i: ROOT for i in active}
        while active:
            by_node: Dict[str, List[int]] = {}
            for i in active:
                by_node.setdefault(node_of[i], []).append(i)
            active = []
            for node, rows in by_node.items():
                if node in self.nodes:
                    labels, conf = self._predict_node(node, X[rows])
                    for k, i in enumerate(rows):
                        if conf[k] < gate:
                            continue          # stop here: deepest confident node
                        child = labels[k]
                        paths[i].append(child)
                        # descend only into a DEEPER internal node. ``child != node``
                        # guards the self-named singletons (super-register ``poetry``
                        # whose only genre child is also ``poetry`` → tree["poetry"]
                        # == ["poetry"]); without it the descent cycles forever.
                        if child in self.tree and child != node:
                            node_of[i] = child
                            active.append(i)
                else:                          # no router: pass through if single child
                    only = self._only_child(node)
                    for i in rows:
                        if only is None:
                            continue
                        paths[i].append(only)
                        if only in self.tree and only != node:
                            node_of[i] = only
                            active.append(i)
        return paths

    def predict_at(self, X: np.ndarray, level: str) -> List[Optional[str]]:
        """Resolve each row to a label at ``level`` ('register_class' |
        'super_register' | 'genre') by forced full descent. The path elements are
        [register_class, super_register, genre]; return the one at ``level`` (or the
        deepest reached, when the branch is shallower)."""
        depth = {"register_class": 0, "super_register": 1, "genre": 2}[level]
        out: List[Optional[str]] = []
        for path in self.predict_paths(X, gate=0.0):
            out.append(path[depth] if len(path) > depth else (path[-1] if path else None))
        return out

    def save(self, path) -> None:
        """Serialize to a TORCH-FREE artifact (pickled numpy): per-node specialist +
        orchestrator weights as plain ndarrays, the node's StandardScaler stats, its
        child labels, and the taxonomy tree — everything :mod:`gse.discourse.infer`
        needs to run the gated descent with **no torch at load time**. Training stays
        offline-with-torch; runtime inference is pure numpy, honoring GSE's no-GPU
        design (the SoM is the one learned component, and even it need not drag torch
        into the encoder venv). Pairs with :meth:`NumpyNestedRouter.load`."""
        import pickle

        nodes = {}
        for node, d in self.nodes.items():
            d["model"].eval()
            weights = {k: v.detach().cpu().numpy().astype("float32")
                       for k, v in d["model"].state_dict().items()}
            nodes[node] = {
                "weights": weights,
                "scaler_mean": np.asarray(d["scaler"].mean_, dtype="float32"),
                "scaler_scale": np.asarray(d["scaler"].scale_, dtype="float32"),
                "labels": list(d["labels"]),
            }
        blob = {
            "format": "gse-nested-router/1",
            "sizes": list(self.sizes),
            "full_dim": int(self.full_dim),
            "tree": {k: list(v) for k, v in self.tree.items()},
            "nodes": nodes,
        }
        with open(path, "wb") as f:
            pickle.dump(blob, f, protocol=4)
