"""Janus — two-face pragmatics comparator (Tier 0): irony / sarcasm as a grounded valence discord.

Design: ``docs/JANUS_MODULE_DESIGN.md``. Some semantic signals are not properties of the text nor of
the world, but of the *relationship* between two faces:

  * **Face A — literal** (bottom-up): what the grounded words say — per-token GOOD − BAD valence, the
    exact signal ``discourse/profile.py`` aggregates (``_lookup_lexeme``). The **sarcasm channel.**
  * **Face B — expected** (top-down): what the situation/frame says should be here. Tier 0, composed
    from built substrate only: an explicit ``frame`` span's valence when given (paragraph-scale), else
    the utterance's own **situational trough** (the negative-valence content the affirmative clashes
    with — irony's within-utterance form).

The output is the *disagreement*: a valence **sign-flip** (Face A GOOD, Face B BAD) is sarcasm/irony
(JANUS §4). The discord magnitude IS the surprise ``S_sem`` (SSL ``05``: the "unknown knowns" regime —
a violation of expectation whose very violation is the information). Discrete valence only — NO cosine,
no embedding, no LLM (an embedding is negation-blind, Proof Packet §8, and cannot represent the flip).

This is the Tier-0 comparator over already-built substrate. The Tier-1 *learned register-expectation*
Face B is deliberately left to a DIFFERENT learning framework (classical/statistical) — the explicit
seam is a clean statement of where this substrate-grounded theory ends and another begins.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import List, Optional

from gse.discourse.profile import _CONTENT_POS, split_sentences


@dataclass(frozen=True)
class JanusReading:
    """The relationship between the two faces — a graded relational reading, not a bare label."""

    face_a: float  # literal affirmative valence (GOOD − BAD)
    face_b: float  # expected / situational valence
    discord: float  # S_sem — the surprise magnitude (0 when the faces agree)
    figure: str  # keyed to figures.py: 'sarcasm' | 'verbal_irony' | 'sincere'
    confidence: float  # min(|A|, |B|) normalized — both faces must be committed for strong irony
    n_content: int  # grounded content tokens seen (0 ⇒ abstain: no signal)


def _token_valences(encoder, text: str) -> List[int]:
    """Per-content-token GOOD − BAD over GSE's lexicon — the exact signal profile.py aggregates."""
    vals: List[int] = []
    for s in split_sentences(text):
        try:
            tr = encoder.encode(s)
        except Exception:
            continue
        for t in tr.tokens:
            if t.pos in _CONTENT_POS:
                wp, _sp, _m = encoder._lookup_lexeme(t.lemma)
                if wp:
                    vals.append(int(wp.get("GOOD", 0)) - int(wp.get("BAD", 0)))
    return vals


def _world_valence(encoder, store, text: str):
    """Face B via sparse-wiki world-EPA — the world's *expected* valence of the utterance's referents,
    ORTHOGONAL to the lexicon (word-affect ⟂ world-salience; the trilogy's encyclopedia leg, Proof
    Packet §7). Confidence-weighted mean of the EPA evaluation over content lemmas with a world entry.
    Deterministic, ternary, no cosine, no learned model. Returns (valence, n_referents_with_world_epa)."""
    evs, ws = [], []
    for s in split_sentences(text):
        try:
            tr = encoder.encode(s)
        except Exception:
            continue
        for t in tr.tokens:
            if t.pos in _CONTENT_POS:
                e = store.epa(t.lemma)
                if e and e.get("evaluation", 0) != 0:
                    evs.append(float(e["evaluation"]))
                    ws.append(float(e.get("confidence", 1.0)))
    if not evs:
        return 0.0, 0
    wsum = sum(ws) or 1.0
    return sum(ev * w for ev, w in zip(evs, ws)) / wsum, len(evs)


def read(encoder, target: str, frame: Optional[str] = None, store=None) -> JanusReading:
    """Compare the two faces over ``target``.

    Face B source (top-down expectation), in order of specification class:
      * ``store`` given → **sparse-wiki world-EPA** (Tier 3): the world's expected valence of the
        referents — the orthogonal encyclopedia leg. Face A stays the lexical affirmative peak.
      * ``frame`` given → the frame span's valence (paragraph scale).
      * neither → the utterance's own situational trough (Tier 0, within-utterance).

    The discord is the sign-opposition strength: large only when a genuinely POSITIVE literal face
    co-occurs with a NEGATIVE expectation face — the sarcasm sign-flip. Agreement ⇒ 0 (sincere).
    No grounded content / no world referents ⇒ abstain (discord 0)."""
    ta = _token_valences(encoder, target)
    if not ta:
        return JanusReading(0.0, 0.0, 0.0, "sincere", 0.0, 0)

    if store is not None:
        # Tier 3 — the orthogonal WORLD leg (sparse-wiki EPA) supplies the expectation face.
        pos = [v for v in ta if v > 0]
        fa = float(max(pos)) if pos else mean(ta)
        fb, n_world = _world_valence(encoder, store, target)
        discord = min(abs(fa), abs(fb)) if (fa > 0 > fb or fa < 0 < fb) else 0.0
    elif frame is not None:
        fa = mean(ta)
        fb_vals = _token_valences(encoder, frame)
        fb = mean(fb_vals) if fb_vals else 0.0
        discord = min(abs(fa), abs(fb)) if (fa > 0 > fb or fa < 0 < fb) else 0.0
    else:
        pos = [v for v in ta if v > 0]
        neg = [v for v in ta if v < 0]
        fa = float(max(pos)) if pos else 0.0
        fb = float(min(neg)) if neg else 0.0
        discord = float(min(fa, -fb))

    if fa > 0 and fb < 0 and discord > 0:
        figure = "sarcasm"
    elif fa < 0 and fb > 0 and discord > 0:
        figure = "verbal_irony"
    else:
        figure = "sincere"

    denom = max(abs(fa), abs(fb), 1.0)
    return JanusReading(fa, fb, discord, figure, discord / denom, len(ta))
