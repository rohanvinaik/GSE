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

from dataclasses import dataclass, field
from statistics import mean, pstdev
from typing import Any, Dict, List, Sequence

from gse.discourse.intake import document_sentences
from gse.discourse.intake import split_sentences as _split_sentences
from gse.structure import OPERATION_VOCABULARY, clause_depth, operation_counts
from gse.symbolic.coherence import coherence_report

# The typed clause operations GSE can emit (the structural alphabet).
_OPERATIONS: Sequence[str] = (
    "EVENT",
    "TYPE_ASSERT",
    "SET_DIFF",
    "BIND_EQ",
    "DEGREE_QUERY",
    "TYPE_QUERY",
    "CARD_LOWER",
    "SCALAR_EXTREME",
    "CONTRAST",
    "COORDINATION",
    "CLAUSE_COORD",
    "CAUSAL_SOURCE",
    "CONSEQUENCE",
    "IMPLIES",
    "REL_RESTRICT",
    "CONTROL",
)
_EMBED_KINDS = ("relative", "control", "complement")
_CONTENT_POS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}


def split_sentences(text: str) -> List[str]:
    """Deterministic sentence split on ``.!?`` boundaries (bounded register)."""
    return _split_sentences(text)


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
    operator_mix: Dict[str, float | None]
    complexity: Dict[str, float | None]
    coherence: Dict[str, float | None]
    affect: Dict[str, float | None]
    register: Dict[str, float | None]
    primitives: Dict[str, float | None]
    version: str = "gse.profile/2"
    state: str = "unread"
    n_read: int = 0
    failures: List[dict] = field(default_factory=list)
    populations: Dict[str, dict] = field(default_factory=dict)
    operations: Dict[str, int] = field(default_factory=dict)
    embedding_depths: List[int] = field(default_factory=list)
    structural_loss: List[dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "state": self.state,
            "n_sentences": self.n_sentences,
            "n_read": self.n_read,
            "n_failed": len(self.failures),
            "failures": self.failures,
            "populations": self.populations,
            "operations": self.operations,
            "embedding_depths": self.embedding_depths,
            "structural_loss": self.structural_loss,
            "operator_mix": self.operator_mix,
            "complexity": self.complexity,
            "coherence": self.coherence,
            "affect": self.affect,
            "register": self.register,
            "primitives": self.primitives,
        }

    def vector(self) -> List[float]:
        """Compatibility alias for :meth:`legacy_vector` (layout gse.profile/1).

        This projection fills missing measurements with zero for historical
        classifiers only; it must not be used as an auditable reading record.
        """
        return self.legacy_vector()

    def legacy_vector(self, missing: float = 0.0) -> List[float]:
        """Explicit fixed-layout projection; unsupported operations are omitted."""
        out: List[float] = []
        for bank in (self.operator_mix, self.complexity, self.coherence, self.affect, self.register, self.primitives):
            for key in sorted(bank):
                value = bank[key]
                out.append(missing if value is None else value)
        return out


def text_profile(encoder, text: str, prime_basis: Sequence[str] | None = None) -> TextProfile:
    """Encode every sentence of ``text`` with ``encoder`` and aggregate the
    per-sentence GSE signals into a :class:`TextProfile`.

    ``prime_basis`` fixes the primitive-bank key order (defaults to the encoder's
    word basis) so profiles across texts share one vector layout.
    """
    from gse.discourse.speech import encode_document_utterance_events

    units = document_sentences(text)
    if prime_basis is None:
        prime_basis = sorted(encoder.word_basis.primitives.keys())
    op_counts: Dict[str, int] = {op: 0 for op in OPERATION_VOCABULARY}
    n_clauses = n_embedded = n_tokens = n_content = n_func = n_oov = 0
    n_past = 0
    degraded = 0
    failures: List[dict] = []
    read_ids: List[str] = []
    depths: List[int] = []
    losses: List[dict] = []
    lemma_lens: List[int] = []
    prim_sums: Dict[str, float] = {p: 0.0 for p in prime_basis}
    per_sentence_valence: List[float] = []
    valences: List[int] = []

    for event in encode_document_utterance_events(encoder, units):
        if event["type"] != "utterance":
            continue
        if event["state"] != "read":
            failures.append(
                {
                    "utterance_id": event["utterance_id"],
                    "source_sentence_id": event["source_sentence_id"],
                    "error": event["error"],
                }
            )
            continue
        tr = event["trace"]
        # Prepare a complete observation locally before committing accumulators.
        # An exception must never leave a partially counted sentence behind.
        try:
            counts = event.get("operations", operation_counts(event["tree"]))
            depth = event.get("embedding_depth", clause_depth(event["tree"]))
            content = func = oov = 0
            lengths = []
            sent_val: List[int] = []
            for t in tr.tokens:
                if t.pos in _CONTENT_POS:
                    content += 1
                    lengths.append(len(t.lemma))
                    wp, _sp, _m = encoder._lookup_lexeme(t.lemma)
                    if not wp:
                        oov += 1
                    elif "GOOD" in wp or "BAD" in wp:
                        v = int(wp.get("GOOD", 0)) - int(wp.get("BAD", 0))
                        sent_val.append(v)
                elif t.pos != "PUNCT":
                    func += 1
            degraded_count = len(coherence_report(event["tree"], tr))
            activations = {p: float(tr.word_primitive_activations.get(p, 0.0)) for p in prime_basis}
            clause_count = max(len(tr.clauses), 1)
            embedded_count = sum(1 for clause in tr.clauses if clause.kind in _EMBED_KINDS)
            token_count = len(tr.tokens)
            past = int(any("SYN_TENSE_PAST" in (getattr(token, "sent_primitives", None) or {}) for token in tr.tokens))
        except Exception as exc:
            failures.append(
                {
                    "utterance_id": event["utterance_id"],
                    "source_sentence_id": event["source_sentence_id"],
                    "error": {
                        "code": "profile_observation_error",
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    },
                }
            )
            continue
        for operation, count in counts.items():
            op_counts[operation] = op_counts.get(operation, 0) + count
        read_ids.append(event["utterance_id"])
        depths.append(depth)
        losses.extend(event.get("structural_loss", []))
        n_clauses += clause_count
        n_embedded += embedded_count
        n_tokens += token_count
        n_content += content
        n_func += func
        n_oov += oov
        lemma_lens.extend(lengths)
        valences.extend(sent_val)
        if sent_val:
            per_sentence_valence.append(mean(sent_val))
        n_past += past
        for prime, activation in activations.items():
            prim_sums[prime] += activation
        degraded += degraded_count

    n = len(read_ids)
    state = "empty" if not units else ("unread" if not n else ("partial" if failures else "read"))
    half = max(len(per_sentence_valence) // 2, 1)
    arc = (
        mean(per_sentence_valence[half:]) - mean(per_sentence_valence[:half])
        if len(per_sentence_valence) >= 2
        else None
    )

    def ratio(num, den):
        return num / den if den else None

    operator_mix = {op: ratio(op_counts.get(op, 0), n) for op in _OPERATIONS}
    complexity = {
        "clauses_per_sent": ratio(n_clauses, n),
        "ops_per_sent": ratio(sum(op_counts.get(op, 0) for op in _OPERATIONS), n),
        "tokens_per_sent": ratio(n_tokens, n),
        "embed_rate": ratio(n_embedded, n),
        "past_tense_rate": ratio(n_past, n),
    }
    coherence = {"degraded_rate": ratio(degraded, n_clauses)}
    affect = {
        "valence_mean": mean(valences) if valences else None,
        "valence_spread": pstdev(valences) if valences else None,
        "valence_arc": arc,
    }
    register = {
        "func_word_ratio": ratio(n_func, n_content + n_func),
        "oov_rate": ratio(n_oov, n_content),
        "mean_lemma_len": mean(lemma_lens) if lemma_lens else None,
    }
    primitives = {p: ratio(prim_sums[p], n) for p in prime_basis}
    populations = {}
    for name, count, definition in (
        ("structure", n, "successfully aggregated encoded utterances"),
        ("coherence", n_clauses, "clauses from successfully aggregated utterances"),
        ("affect", len(valences), "content tokens with explicit GOOD/BAD evidence"),
        ("affect_arc", len(per_sentence_valence), "utterances with explicit GOOD/BAD evidence"),
        ("content", n_content, "content-POS tokens from successfully aggregated utterances"),
    ):
        populations[name] = {
            "state": ("partial" if failures else "measured") if count else ("unread" if failures else "absent"),
            "n": count,
            "failed": len(failures),
            "support": "sufficient" if count >= 2 else ("thin" if count else "none"),
            "evidence": read_ids,
            "definition": definition,
        }
    return TextProfile(
        n_sentences=len(units),
        operator_mix=operator_mix,
        complexity=complexity,
        coherence=coherence,
        affect=affect,
        register=register,
        primitives=primitives,
        state=state,
        n_read=n,
        failures=failures,
        populations=populations,
        operations=op_counts,
        embedding_depths=depths,
        structural_loss=losses,
    )


# Ordered field names of ``TextProfile.vector()`` — the SoM's input layout.
PROFILE_FIELDS: List[str] = (
    [f"op:{op}" for op in sorted(_OPERATIONS)]
    + [
        f"cx:{k}"
        for k in sorted(("clauses_per_sent", "ops_per_sent", "tokens_per_sent", "embed_rate", "past_tense_rate"))
    ]
    + ["coh:degraded_rate"]
    + [f"aff:{k}" for k in sorted(("valence_mean", "valence_spread", "valence_arc"))]
    + [f"reg:{k}" for k in sorted(("func_word_ratio", "oov_rate", "mean_lemma_len"))]
)
