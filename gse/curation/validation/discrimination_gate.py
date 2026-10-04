"""The discrimination / orthogonality gate — the lexicon quality contract.

Phase 0a of the clean-lexicon rebuild (see plan). The degenerate lexicon's
failure mode is that category is *not recoverable from prime-space*: `dog`,
`king`, `knife` carry the same `DO/CAUSE/MOVE` as `murder/kill/run`. This gate is
the acceptance test that nothing enters the new lexicon without passing, and the
standing coherence check (mirrors the orthogonality contract in the
persistent-knowledge architecture).

A decomposition set PASSES iff all three hold:
  (a) CATEGORY SEPARATION — noun / verb / adjective centroids are distinguishable
      in prime-space (mean cross-category cosine well below mean within-category).
  (b) PAIR DISCRIMINATION — representative must-differ pairs (dog≠murder, …) have
      cosine below a threshold.
  (c) SPARSITY — decompositions are "mostly-negative": few +1 banks per word, not
      everything lit (the dense degeneracy signature).

The gate takes a ``decomp_fn(word) -> dict[primitive, value] | None`` so it runs
against any lexicon (the current degenerate DB for the baseline, or the new clean
DB for acceptance).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

# Labeled probe set — obvious-category common words. Kept small + unambiguous so
# the gate measures category recoverability, not edge-case POS.
GOLD_CATEGORIES: Dict[str, List[str]] = {
    "noun": [
        "dog",
        "king",
        "knife",
        "house",
        "water",
        "tree",
        "stone",
        "child",
        "mountain",
        "river",
        "bird",
        "book",
        "hand",
        "door",
        "horse",
    ],
    "verb": [
        "murder",
        "kill",
        "run",
        "eat",
        "give",
        "break",
        "think",
        "walk",
        "throw",
        "build",
        "carry",
        "speak",
        "fall",
        "push",
        "cut",
    ],
    "adj": [
        "happy",
        "red",
        "big",
        "cold",
        "fast",
        "good",
        "old",
        "heavy",
        "bright",
        "soft",
        "loud",
        "empty",
        "sharp",
        "wet",
        "clean",
    ],
}
MUST_DISCRIMINATE = [
    ("dog", "murder"),
    ("knife", "kill"),
    ("king", "run"),
    ("tree", "think"),
    ("house", "eat"),
    ("stone", "give"),
]

# Thresholds (provisional — tune against the clean build's distribution).
MAX_CROSS_CATEGORY_COSINE = 0.55  # cross-category mean must be below this
MIN_SEPARATION_MARGIN = 0.15  # within-cat mean minus cross-cat mean
MAX_PAIR_COSINE = 0.6  # a must-differ pair must be below this
MAX_MEAN_DENSITY = 0.35  # avg fraction of nonzero primes per word


@dataclass
class GateReport:
    passed: bool
    cross_category_cosine: float
    within_category_cosine: float
    separation_margin: float
    failing_pairs: List[tuple]
    mean_density: float
    n_resolved: int
    detail: str


def _vec(decomp: Dict[str, int], primitives: List[str]) -> List[float]:
    return [float(decomp.get(p, 0)) for p in primitives]


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def run_gate(
    decomp_fn: Callable[[str], Optional[Dict[str, int]]],
    primitives: List[str],
) -> GateReport:
    """Score a lexicon (via decomp_fn) against the three discrimination criteria."""
    vecs: Dict[str, Dict[str, List[float]]] = {c: {} for c in GOLD_CATEGORIES}
    densities: List[float] = []
    n = 0
    for cat, words in GOLD_CATEGORIES.items():
        for w in words:
            d = decomp_fn(w)
            if not d:
                continue
            v = _vec(d, primitives)
            vecs[cat][w] = v
            densities.append(sum(1 for x in v if x != 0) / len(primitives))
            n += 1

    # (a) category separation: within- vs cross-category mean cosine
    within, cross = [], []
    cats = list(vecs)
    for ci, c in enumerate(cats):
        items = list(vecs[c].values())
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                within.append(_cosine(items[i], items[j]))
        for c2 in cats[ci + 1 :]:
            for v1 in vecs[c].values():
                for v2 in vecs[c2].values():
                    cross.append(_cosine(v1, v2))
    within_mean = sum(within) / len(within) if within else 0.0
    cross_mean = sum(cross) / len(cross) if cross else 0.0
    margin = within_mean - cross_mean

    # (b) pair discrimination
    flat = {w: v for cat in vecs.values() for w, v in cat.items()}
    failing = [
        (a, b, round(_cosine(flat[a], flat[b]), 3))
        for a, b in MUST_DISCRIMINATE
        if a in flat and b in flat and _cosine(flat[a], flat[b]) > MAX_PAIR_COSINE
    ]

    # (c) sparsity
    density = sum(densities) / len(densities) if densities else 1.0

    passed = (
        cross_mean <= MAX_CROSS_CATEGORY_COSINE
        and margin >= MIN_SEPARATION_MARGIN
        and not failing
        and density <= MAX_MEAN_DENSITY
    )
    return GateReport(
        passed=passed,
        cross_category_cosine=round(cross_mean, 3),
        within_category_cosine=round(within_mean, 3),
        separation_margin=round(margin, 3),
        failing_pairs=failing,
        mean_density=round(density, 3),
        n_resolved=n,
        detail=(
            f"separation_ok={cross_mean <= MAX_CROSS_CATEGORY_COSINE and margin >= MIN_SEPARATION_MARGIN}, "
            f"pairs_ok={not failing}, sparsity_ok={density <= MAX_MEAN_DENSITY}"
        ),
    )


def _baseline_on_current_lexicon() -> GateReport:
    """Run the gate against the live (degenerate) lexicon to establish the baseline."""
    from gse.api import GSEEncoder

    enc = GSEEncoder()
    cur = enc.cursor
    cur.execute("SELECT DISTINCT primitive FROM primitive_values")
    primitives = sorted(r[0] for r in cur.fetchall())

    def decomp_fn(word: str) -> Optional[Dict[str, int]]:
        cur.execute("SELECT id FROM lexemes WHERE lemma=? LIMIT 1", (word,))
        r = cur.fetchone()
        if not r:
            return None
        cur.execute("SELECT primitive, value FROM primitive_values WHERE lexeme_id=? AND value!=0", (r[0],))
        return {p: v for p, v in cur.fetchall()}

    return run_gate(decomp_fn, primitives)


if __name__ == "__main__":
    rep = _baseline_on_current_lexicon()
    print("=== DISCRIMINATION GATE — baseline on CURRENT (degenerate) lexicon ===")
    print(f"  resolved words:        {rep.n_resolved}")
    print(f"  within-category cos:   {rep.within_category_cosine}")
    print(f"  cross-category cos:    {rep.cross_category_cosine}  (must be <= {MAX_CROSS_CATEGORY_COSINE})")
    print(f"  separation margin:     {rep.separation_margin}  (must be >= {MIN_SEPARATION_MARGIN})")
    print(f"  mean density:          {rep.mean_density}  (must be <= {MAX_MEAN_DENSITY})")
    print(f"  failing pairs:         {rep.failing_pairs}")
    print(f"  PASSED: {rep.passed}   ({rep.detail})")
