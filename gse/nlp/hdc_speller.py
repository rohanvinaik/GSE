"""Keyboard-spatial HDC speller — an ORTHOGONAL error model for the deterministic
spell-corrector, native to GSE's sparse-ternary HDC stack (gse.vectors_v2).

Edit-distance (gse.nlp.spellcheck) is strong on insert/delete/transpose typos but is
capped at edit-2 + a confusion table; it ABSTAINS on far, length-preserving multi-key
slips ("ecifentky" -> "evidently"). This module recovers exactly that residue.

How it works (HDC-native, validated on Rohan's real ~/.claude typo corpus):
  - each KEY -> a sparse-ternary hypervector, keyboard-BLURRED so adjacent keys overlap
    (a slip to a neighbor barely moves the vector);
  - a WORD -> a bundle of its keys bound to FRACTIONAL position (roll by i/(n-1)), with
    BOOKEND emphasis (first/last letters weighted) and order-robust BIGRAM binds;
  - recover a typo by cosine vs a holographic lexicon of common words, restricted to a
    length band (typos ~preserve length) with a tiny frequency tiebreak.

Design contract: this is a candidate SOURCE, never an authority. The caller fires it
ONLY when edit-distance abstains, and gates the result through grounding + shape checks,
so the system's "never destroy a valid word" guarantee is preserved.

The recipe constants below are not free knobs — they are the operating point measured to
recover the hard residue (7/10 hard targets incl. ecifentky/psychological) on the real
corpus. See scratchpad probes / docs/SPELLCHECK.md.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional, Tuple

import numpy as np

from gse.vectors_v2 import D, SparseVector, permute, bind, weighted_bundle

# ---- operating point (measured, not tuned-to-taste) -----------------------------
_DENSITY = 0.10            # base key-vector sparsity (nnz ~ 0.10*D)
_SIGMA = 1.0              # keyboard Gaussian blur width (in key units)
_ROLLSCALE = 16          # fractional-position resolution (roll = round(i/(n-1)*ROLLSCALE))
_W_END = 2.0             # bookend (first/last letter) weight
_W_BIGRAM = 0.6          # order-robust bigram-bind weight
_BAND = 1               # length band: |len(cand)-len(typo)| <= BAND
_BETA = 0.02            # frequency-prior tiebreak strength
_SEED = 0               # base-key RNG seed — MUST match between cache build and query

# Commit/offer gates, CALIBRATED on real typos vs garbage (cosines don't cleanly separate
# them, so a single threshold is unsafe — see scratchpad/calibrate_threshold.py):
#   - real typo recoveries span cos ~0.565..0.807; garbage non-words top out at ~0.687.
#   - COMMIT=0.75 sits above ALL observed garbage -> safe to auto-apply (gets ecifentky 0.755).
#   - OFFER=0.55 surfaces harder recoveries as "did you mean" suggestions, never auto-applied.
# These govern typo-vs-garbage precision only; the "never destroy a valid word" bound is
# preserved separately (HDC fires only on tokens that DON'T ground).
HDC_COMMIT_COS = 0.75
HDC_OFFER_COS = 0.55

# Tiebreak gates for the AMBIGUOUS case (edit-distance found >=2 grounded candidates but
# didn't decisively commit). HDC confirms among THOSE candidates — never the whole lexicon —
# committing the single common-English candidate only when it independently ranks #1 with a
# clear cosine margin. CALIBRATED on the real ambiguous corpus (scratchpad/calibrate_tiebreak2.py):
# at these gates, 100% precision over the committed set, ZERO jargon false-commits.
HDC_TIEBREAK_COS = 0.55
HDC_TIEBREAK_MARGIN = 0.05

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CACHE_PATH = os.path.join(_REPO_ROOT, "data", "hdc_speller.npz")

# QWERTY key centroids (x, y); row stagger approximated — adjacency is what matters.
_ROWS = [("qwertyuiop", 0.0), ("asdfghjkl", 0.5), ("zxcvbnm", 1.0)]
_XOFF = {0: 0.0, 1: 0.25, 2: 0.75}
_COORD = {}
for _r, (_row, _y) in enumerate(_ROWS):
    for _i, _ch in enumerate(_row):
        _COORD[_ch] = (_i + _XOFF[_r], _y)


@lru_cache(maxsize=1)
def _key_vectors() -> dict:
    """Deterministic sparse-ternary, keyboard-blurred key hypervectors (seed-fixed so the
    cached lexicon matrix and live queries share the same basis)."""
    rng = np.random.default_rng(_SEED)
    k = int(D * _DENSITY)
    base = {}
    for ch in _COORD:
        idx = rng.choice(D, size=2 * k, replace=False)
        base[ch] = SparseVector(
            dimension=D,
            positive_indices=idx[:k].astype(np.uint16),
            negative_indices=idx[k:].astype(np.uint16),
        )
    keyvec = {}
    for a, (ax, ay) in _COORD.items():
        vs, ws = [], []
        for b, (bx, by) in _COORD.items():
            w = float(np.exp(-((ax - bx) ** 2 + (ay - by) ** 2) / (2 * _SIGMA ** 2)))
            if w > 0.02:
                vs.append(base[b])
                ws.append(w)
        keyvec[a] = weighted_bundle(vs, ws)
    return keyvec


def encode(word: str) -> SparseVector:
    """Encode a word into its sparse-ternary keyboard-HDC hypervector."""
    kv = _key_vectors()
    w = word.lower()
    n = len(w)
    vecs: List[SparseVector] = []
    wts: List[float] = []
    for i, ch in enumerate(w):
        if ch not in kv:
            continue
        pos = 0 if n <= 1 else round(i / (n - 1) * _ROLLSCALE)
        vecs.append(permute(kv[ch], pos))
        wts.append(_W_END if (i == 0 or i == n - 1) else 1.0)
    for i in range(n - 1):
        a, b = w[i], w[i + 1]
        if a in kv and b in kv:
            vecs.append(bind(kv[a], permute(kv[b], 1)))
            wts.append(_W_BIGRAM)
    if not vecs:
        return SparseVector.zeros(D)
    return weighted_bundle(vecs, wts)


def _encode_dense_unit(word: str) -> np.ndarray:
    """Encode -> dense ternary -> L2-normalized (for fast cosine via matmul)."""
    v = SparseVector.to_dense(encode(word)).astype(np.float32)
    nrm = np.linalg.norm(v)
    return v / nrm if nrm else v


def score_words(token: str, words: List[str]) -> List[Tuple[str, float]]:
    """Keyboard-HDC cosine of `token` against each given `word`, ranked high-to-low.

    Unlike HDCSpeller.candidates (which searches the cached lexicon), this scores an
    arbitrary candidate set — e.g. the edit-distance corrector's ranked candidates — so
    HDC can act as a TIEBREAKER among them without introducing a new word. No cache needed.
    """
    q = encode(token)
    scored = [(w, round(q.cosine(encode(w)), 4)) for w in words]
    scored.sort(key=lambda x: -x[1])
    return scored


class HDCSpeller:
    """Holographic keyboard speller over a cached common-word lexicon.

    recover(token) returns (word, cosine) for the best length-banded match, or None.
    Pure recovery — applies NO grounding/shape gating; the caller owns that policy.
    """

    def __init__(self, cache_path: str = _CACHE_PATH):
        data = np.load(cache_path, allow_pickle=False)
        self.words: List[str] = list(data["words"])
        self._M: np.ndarray = data["matrix"].astype(np.float32)   # rows already unit-norm
        self._len = np.array([len(w) for w in self.words])
        rank = data["rank"].astype(float)
        logp = -np.log(rank + 10)
        self._zprior = (logp - logp.mean()) / (logp.std() + 1e-9)

    def candidates(self, token: str, k: int = 5, band: int = _BAND) -> List[Tuple[str, float]]:
        q = _encode_dense_unit(token)
        sims = self._M @ q
        score = sims + _BETA * self._zprior
        if band is not None:
            score = np.where(np.abs(self._len - len(token)) <= band, score, -1e9)
        idx = np.argsort(-score)[:k]
        return [(self.words[i], round(float(sims[i]), 4)) for i in idx]

    def recover(self, token: str, min_cosine: float) -> Optional[Tuple[str, float]]:
        """Best length-banded match if its cosine clears `min_cosine`, else None.

        `min_cosine` is the caller's confidence gate; there is no default, because the
        right threshold depends on whether the caller will OFFER or COMMIT the result.
        """
        cands = self.candidates(token, k=1)
        if cands and cands[0][1] >= min_cosine:
            return cands[0]
        return None


@lru_cache(maxsize=1)
def default_speller() -> Optional["HDCSpeller"]:
    """Process-wide speller, or None if the lexicon cache hasn't been built yet
    (run `python -m gse.curation.build_hdc_speller`). Lets callers degrade gracefully."""
    if not os.path.exists(_CACHE_PATH):
        return None
    return HDCSpeller()
