"""Text → GSE feature profile (the k-line pattern the L2 router matches on).

Runs the deterministic GSE pipeline over every sentence of a text and aggregates
the per-sentence signals into one feature vector — the *full combination* of what
GSE measures, grouped into named banks:

* **operator_mix** — rate of each typed clause operation (EVENT, CAUSAL_SOURCE,
  IMPLIES, REL_RESTRICT, …). The structural fingerprint: a philosophical treatise
  leans on IMPLIES/CAUSAL, a narrative on EVENT, a tweet on almost nothing.
* **complexity** — clauses / ops / tokens per sentence, embedded-clause rate.
* **coherence** — fraction of clauses the coherence gate flags as degraded
  (high for fragmentary / nonsense text).
* **affect** — valence (GOOD−BAD) mean, spread, and first-half→second-half *arc*.
* **register** — function-word density, OOV rate, mean content-lemma length.
* **primitives** — mean word-scale primitive activation per NSM prime (the
  72-prime signature; mental primes spike in analysis, action primes in narrative).

Deterministic and learning-free — this is the *signal layer*; the Society-of-Mind
genre router is trained separately over these vectors. See ``gse.discourse``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any, Dict, List, Sequence

from gse.symbolic import evaluate_tree, from_trace, resolve, to_dict
from gse.symbolic.coherence import coherence_report

# The typed clause operations GSE can emit (the structural alphabet).
_OPERATIONS: Sequence[str] = (
    "EVENT", "TYPE_ASSERT", "SET_DIFF", "BIND_EQ", "DEGREE_QUERY", "TYPE_QUERY",
    "CARD_LOWER", "SCALAR_EXTREME", "CONTRAST", "COORDINATION", "CLAUSE_COORD",
    "CAUSAL_SOURCE", "CONSEQUENCE", "IMPLIES", "REL_RESTRICT", "CONTROL",
)
_EMBED_KINDS = ("relative", "control", "complement")
_CONTENT_POS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> List[str]:
    """Deterministic sentence split on ``.!?`` boundaries (bounded register)."""
    return [s.strip() for s in _SENT_SPLIT.split(text.strip()) if s.strip()]


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


@dataclass
class TextProfile:
    """The aggregated feature profile of a text — the SoM router's input."""

    n_sentences: int
    operator_mix: Dict[str, float]
    complexity: Dict[str, float]
    coherence: Dict[str, float]
    affect: Dict[str, float]
    register: Dict[str, float]
    primitives: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_sentences": self.n_sentences,
            "operator_mix": self.operator_mix,
            "complexity": self.complexity,
            "coherence": self.coherence,
            "affect": self.affect,
            "register": self.register,
            "primitives": self.primitives,
        }

    def vector(self) -> List[float]:
        """Flatten to a fixed-order numeric vector (the SoM feature input)."""
        out: List[float] = []
        for bank in (self.operator_mix, self.complexity, self.coherence,
                     self.affect, self.register, self.primitives):
            out.extend(bank[k] for k in sorted(bank))
        return out


def text_profile(encoder, text: str, prime_basis: Sequence[str] | None = None) -> TextProfile:
    """Encode every sentence of ``text`` with ``encoder`` and aggregate the
    per-sentence GSE signals into a :class:`TextProfile`.

    ``prime_basis`` fixes the primitive-bank key order (defaults to the encoder's
    word basis) so profiles across texts share one vector layout.
    """
    sents = split_sentences(text)
    n = max(len(sents), 1)
    if prime_basis is None:
        prime_basis = sorted(encoder.word_basis.primitives.keys())

    op_counts: Dict[str, int] = {op: 0 for op in _OPERATIONS}
    n_clauses = n_embedded = n_tokens = n_content = n_func = n_oov = 0
    degraded = 0
    failures = 0
    lemma_lens: List[int] = []
    prim_sums: Dict[str, float] = {p: 0.0 for p in prime_basis}
    per_sentence_valence: List[float] = []
    valences: List[int] = []

    for s in sents:
        # Robust to the bounded register: a sentence GSE can't fully process must
        # not crash the whole profile — count it as a failure (itself a genre
        # signal: messy/long-tail registers fail more often) and move on.
        try:
            tr = encoder.encode(s)
            resolved = resolve(from_trace(tr))
            # Count operations off the resolved symbolic tree — EVENT / TYPE_ASSERT /
            # REL_RESTRICT / CONTROL are synthesized there, not in trace.operators.
            for node in _walk(to_dict(resolved)):
                if node.get("_kind") == "Op" and node.get("operation") in op_counts:
                    op_counts[node["operation"]] += 1
            n_clauses += max(len(tr.clauses), 1)
            n_embedded += sum(1 for c in tr.clauses if c.kind in _EMBED_KINDS)

            sent_val: List[int] = []
            for t in tr.tokens:
                n_tokens += 1
                if t.pos in _CONTENT_POS:
                    n_content += 1
                    lemma_lens.append(len(t.lemma))
                    wp, _sp, _m = encoder._lookup_lexeme(t.lemma)
                    if not wp:
                        n_oov += 1
                    else:
                        v = int(wp.get("GOOD", 0)) - int(wp.get("BAD", 0))
                        sent_val.append(v)
                        valences.append(v)
                elif t.pos != "PUNCT":
                    n_func += 1

            for p, act in tr.word_primitive_activations.items():
                if p in prim_sums:
                    prim_sums[p] += act
            per_sentence_valence.append(mean(sent_val) if sent_val else 0.0)
            degraded += len(coherence_report(evaluate_tree(resolved), tr))
        except Exception:
            failures += 1
            per_sentence_valence.append(0.0)
            continue

    half = max(len(per_sentence_valence) // 2, 1)
    arc = (mean(per_sentence_valence[half:]) - mean(per_sentence_valence[:half])
           if len(per_sentence_valence) >= 2 else 0.0)

    operator_mix = {op: op_counts[op] / n for op in _OPERATIONS}
    complexity = {
        "clauses_per_sent": n_clauses / n,
        "ops_per_sent": sum(op_counts.values()) / n,
        "tokens_per_sent": n_tokens / n,
        "embed_rate": n_embedded / n,
    }
    coherence = {"degraded_rate": degraded / max(n_clauses, 1)}
    affect = {
        "valence_mean": mean(valences) if valences else 0.0,
        "valence_spread": pstdev(valences) if len(valences) > 1 else 0.0,
        "valence_arc": arc,
    }
    register = {
        "func_word_ratio": n_func / max(n_content + n_func, 1),
        "oov_rate": n_oov / max(n_content, 1),
        "mean_lemma_len": mean(lemma_lens) if lemma_lens else 0.0,
    }
    primitives = {p: prim_sums[p] / n for p in prime_basis}

    return TextProfile(
        n_sentences=len(sents), operator_mix=operator_mix, complexity=complexity,
        coherence=coherence, affect=affect, register=register, primitives=primitives,
    )


# Ordered field names of ``TextProfile.vector()`` — the SoM's input layout.
PROFILE_FIELDS: List[str] = (
    [f"op:{op}" for op in sorted(_OPERATIONS)]
    + [f"cx:{k}" for k in sorted(("clauses_per_sent", "ops_per_sent",
                                  "tokens_per_sent", "embed_rate"))]
    + ["coh:degraded_rate"]
    + [f"aff:{k}" for k in sorted(("valence_mean", "valence_spread", "valence_arc"))]
    + [f"reg:{k}" for k in sorted(("func_word_ratio", "oov_rate", "mean_lemma_len"))]
)
