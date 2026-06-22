"""Torch-free runtime inference for the nested Society-of-Mind register router.

The router is *trained* offline with torch (``scripts/train_register_router.py
--nested``) and serialized by :meth:`gse.discourse.nested_router.NestedRouter.save`
to a portable pickled-numpy artifact. This module loads that artifact and runs the
**identical** forward pass + confidence-gated descent in pure numpy, so the encoder
venv carries no torch (GSE's no-GPU design: the SoM is the one learned component, and
even it stays a few KB of matrices + a numpy forward at runtime).

The forward mirrors :class:`gse.discourse.router.RegisterRouter` exactly — bank
specialists (``Linear → LayerNorm → GELU`` on the bank, ``Linear → GELU`` on the full
profile, concatenated through a linear head) trust-weighted by a softmax orchestrator
— and the descent mirrors :meth:`NestedRouter.predict_paths`. Parity with the torch
model is asserted by ``scripts/verify_router_parity`` over the training corpus.
"""
from __future__ import annotations

import pickle
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.special import erf

from gse.discourse.registers import ROOT

_LN_EPS = 1e-5   # torch nn.LayerNorm default


def _linear(x: np.ndarray, w: np.ndarray, b: np.ndarray) -> np.ndarray:
    return x @ w.T + b


def _gelu(x: np.ndarray) -> np.ndarray:
    # torch nn.GELU default (approximate='none'): exact erf form.
    return 0.5 * x * (1.0 + erf(x / np.sqrt(2.0)))


def _layernorm(x: np.ndarray, w: np.ndarray, b: np.ndarray) -> np.ndarray:
    m = x.mean(axis=-1, keepdims=True)
    v = x.var(axis=-1, keepdims=True)        # population variance, as torch LayerNorm
    return (x - m) / np.sqrt(v + _LN_EPS) * w + b


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


class _NumpyRegisterRouter:
    """One taxonomy node's RegisterRouter, forward-only, in numpy."""

    def __init__(self, weights: Dict[str, np.ndarray], scaler_mean: np.ndarray,
                 scaler_scale: np.ndarray, labels: Sequence[str], sizes: Sequence[int]):
        self.W = weights
        self.mean = scaler_mean
        self.scale = scaler_scale
        self.labels = list(labels)
        self.sizes = list(sizes)
        self.bnd = np.cumsum([0] + self.sizes)
        self.n_spec = len(self.sizes)

    def _logits(self, x_full: np.ndarray) -> np.ndarray:
        """Trust-weighted sum of per-bank specialist logits. ``x_full`` is the SCALED
        profile vector [full_dim]; returns logits over this node's labels [G]."""
        W = self.W
        ctx = _gelu(_linear(x_full, W["orch_ctx.0.weight"], W["orch_ctx.0.bias"]))
        trust = _softmax(_linear(ctx, W["trust_head.weight"], W["trust_head.bias"]))  # [S]
        spec = np.empty((self.n_spec, len(self.labels)), dtype=np.float64)
        for i in range(self.n_spec):
            bank_x = x_full[self.bnd[i]:self.bnd[i + 1]]
            be = _linear(bank_x, W[f"specialists.{i}.bank_enc.0.weight"],
                         W[f"specialists.{i}.bank_enc.0.bias"])
            be = _layernorm(be, W[f"specialists.{i}.bank_enc.1.weight"],
                            W[f"specialists.{i}.bank_enc.1.bias"])
            be = _gelu(be)
            ce = _gelu(_linear(x_full, W[f"specialists.{i}.ctx_enc.0.weight"],
                               W[f"specialists.{i}.ctx_enc.0.bias"]))
            h = np.concatenate([be, ce])
            spec[i] = _linear(h, W[f"specialists.{i}.head.weight"],
                              W[f"specialists.{i}.head.bias"])
        return (trust[:, None] * spec).sum(axis=0)

    def predict(self, profile_vec: np.ndarray) -> Tuple[str, float]:
        """Returns (child label, max-softmax confidence) for one raw profile vector."""
        x = (np.asarray(profile_vec, dtype=np.float64) - self.mean) / self.scale
        probs = _softmax(self._logits(x))
        i = int(probs.argmax())
        return self.labels[i], float(probs[i])


class NumpyNestedRouter:
    """Torch-free twin of :class:`gse.discourse.nested_router.NestedRouter`.

    Loads a ``NestedRouter.save`` artifact and resolves a single text's feature
    profile to a label at a chosen level via confidence-gated descent from ROOT —
    the same honest behavior as the torch router: a profile the signal cannot
    sub-classify resolves to a shallower node (and the caller reads it as abstention)
    rather than guessing a deep label."""

    def __init__(self, sizes: Sequence[int], full_dim: int,
                 tree: Dict[str, List[str]], nodes: Dict[str, _NumpyRegisterRouter]):
        self.sizes = list(sizes)
        self.full_dim = int(full_dim)
        self.tree = tree
        self.nodes = nodes

    @classmethod
    def load(cls, path) -> "NumpyNestedRouter":
        with open(path, "rb") as f:
            blob = pickle.load(f)
        if blob.get("format") != "gse-nested-router/1":
            raise ValueError(f"{path}: not a gse-nested-router artifact ({blob.get('format')})")
        nodes = {
            node: _NumpyRegisterRouter(
                d["weights"], d["scaler_mean"], d["scaler_scale"], d["labels"], blob["sizes"])
            for node, d in blob["nodes"].items()
        }
        return cls(blob["sizes"], blob["full_dim"], blob["tree"], nodes)

    def predict_path(self, profile_vec: np.ndarray, gate: float = 0.0
                     ) -> List[Tuple[str, float]]:
        """Confidence-gated descent from ROOT for one profile. Returns the resolved
        chain as (label, confidence) pairs; descent stops at a leaf, a router-less
        node (single child), or the first node below ``gate``."""
        path: List[Tuple[str, float]] = []
        node = ROOT
        seen = set()
        while node not in seen:
            seen.add(node)
            if node in self.nodes:
                child, conf = self.nodes[node].predict(profile_vec)
                if conf < gate:
                    break
                path.append((child, conf))
                if child in self.tree and child != node:
                    node = child
                    continue
                break
            else:                                   # no router: deterministic pass-through
                children = self.tree.get(node, [])
                if len(children) != 1:
                    break
                only = children[0]
                path.append((only, 1.0))
                if only in self.tree and only != node:
                    node = only
                    continue
                break
        return path

    def predict_at(self, profile_vec: np.ndarray, level: str, gate: float = 0.0
                   ) -> Tuple[Optional[str], float]:
        """Resolve to a label at ``level`` ('register_class'|'super_register'|'genre').
        Mirrors :meth:`NestedRouter.predict_at`: returns the label at ``level``, or the
        deepest reached when the branch is shallower (``path[-1]``), or (None, 0.0) for
        an empty path. For honest *abstention* (did the descent actually reach this
        level?) use :meth:`resolve_at`, which the runtime genre detector uses."""
        depth = {"register_class": 0, "super_register": 1, "genre": 2}[level]
        path = self.predict_path(profile_vec, gate=gate)
        if len(path) > depth:
            return path[depth]
        return path[-1] if path else (None, 0.0)

    def resolve_at(self, profile_vec: np.ndarray, level: str, gate: float = 0.0
                   ) -> Tuple[Optional[str], float]:
        """Like :meth:`predict_at` but returns (None, conf) when the gated descent did
        NOT reach ``level`` — the honest abstention the runtime dispatcher wants (a
        text the signal can't classify to this granularity resolves to *nothing* at
        this level, not to a shallower label coerced into the slot)."""
        depth = {"register_class": 0, "super_register": 1, "genre": 2}[level]
        path = self.predict_path(profile_vec, gate=gate)
        if len(path) > depth:
            return path[depth]
        return (None, path[-1][1] if path else 0.0)
