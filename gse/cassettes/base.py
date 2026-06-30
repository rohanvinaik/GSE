"""The Cassette base — the SymbolicSpellCheck noisy-channel discipline, generalized from
word→sentence to in-frame-element→document.

A cassette resolves ONE focused question about an uncertain element by composing the four scales of a
``MultiScaleDoc`` until they converge — the exact move SymbolicSpellCheck makes (you cannot correct a
misspelled word from the word alone; the information is external, so you go UP a scale). The discipline
is non-negotiable and mirrors ``gse/nlp/spellcheck.py`` term-for-term:

  1. TRIGGER on a genuine gap only          ``gaps(doc)``      — never scan-and-rewrite valid output.
  2. PROPOSE from out-of-frame context      ``candidates(...)`` — higher scales, never the element alone.
  3. GROUND every candidate                 ``ground(...)``     — a candidate must itself ground (dict gate).
  4. SCORE by ORTHOGONAL strands            ``score(...)``      — word ⊥ sentence ⊥ paragraph ⊥ document.
  5. COMMIT by margin, else ABSTAIN         ``resolve(...)``    — decisive winner or honest hole.

The cardinal guarantee, measured at 0.00000% in SSC: a cassette NEVER destroys a correct value. Every
failure is confined to NON-RECOVERY (an abstention), never DESTRUCTION (overwriting a right answer).
A ``Resolution`` is frozen and always carries the full ranked set + trace; an abstention leaves the
original untouched. Validation is resolve-or-abstain-correctly across the ENTIRE pulled corpus — a fix
that works on one document and corrupts the others is, by that test, not built.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .multiscale import MultiScaleDoc


@dataclass(frozen=True)
class Scored:
    """One candidate answer with its per-strand scores — the orthogonal readings that must converge."""
    answer: Any
    strands: Dict[str, float]
    note: str = ""

    @property
    def total(self) -> float:
        return float(sum(self.strands.values()))


@dataclass(frozen=True)
class Resolution:
    """The outcome for one gap. ``committed`` is the answer ONLY on a decisive margin; otherwise it is
    None (an honest abstention) and the gap is left exactly as it was. ``ranked`` always carries the
    full candidate set so the decision is auditable; ``trace`` records the scale evidence."""
    cassette: str
    gap: Any
    committed: Optional[Any]
    ranked: Tuple[Scored, ...] = ()
    note: str = ""
    fired: bool = True            # did the trigger fire (a genuine gap)? False = surface already clean.

    @property
    def abstained(self) -> bool:
        return self.committed is None

    @property
    def confidence(self) -> float:
        """CONVERGENCE, not margin: how many independent strands actually agree (value > 0). A lone
        signal (one strand) is low-confidence even when it is the only candidate — the SSC principle
        that orthogonal readings must CONVERGE. The deck resolves high-confidence cassettes first."""
        if not self.ranked:
            return 0.0
        return float(sum(1 for v in self.ranked[0].strands.values() if v > 0.01))

    @property
    def locality(self) -> float:
        """The tightness/locality of the winning evidence — the deck's priority key for 'resolve the
        local anchors first, then propagate'. Highest single-strand confirmation (recency/proximity)."""
        if not self.ranked:
            return 0.0
        s = self.ranked[0].strands
        return float(max((v for k, v in s.items() if k in ("recency", "locality")), default=0.0))


class Cassette:
    """One domain-portable expert. Subclasses set ``name``/``question`` and implement ``gaps`` +
    ``candidates`` + ``ground`` + ``score``; ``resolve`` and ``run`` are the shared commit-or-abstain
    spine, so every cassette is disciplined identically."""

    name: str = "cassette"
    question: str = ""
    margin: float = 0.5           # the decisive-margin gate (mirrors WORD_COMMIT_MARGIN = 0.5)

    # -- the four hooks a subclass implements -------------------------------
    def gaps(self, doc: MultiScaleDoc) -> List[Any]:
        """The genuine gaps in ``doc`` — elements that do not ground / that the system flags uncertain.
        Returns [] when the document has no gap of this cassette's kind (the trigger stays silent)."""
        raise NotImplementedError

    def candidates(self, gap: Any, doc: MultiScaleDoc) -> List[Any]:
        """Propose answers for ``gap`` from OUT-OF-FRAME context (the ±2 window, the document fold, the
        world strand) — never from the gap element in isolation. May return [] (nothing to ground to)."""
        raise NotImplementedError

    def ground(self, answer: Any, gap: Any, doc: MultiScaleDoc) -> bool:
        """The grounding gate: is this candidate itself a real, grounded answer? A candidate that does
        not ground can never be committed (the SSC dictionary gate)."""
        raise NotImplementedError

    def score(self, answer: Any, gap: Any, doc: MultiScaleDoc) -> Dict[str, float]:
        """The orthogonal per-strand scores for one grounded candidate (word/sentence/paragraph/
        document). Each strand speaks only where it has signal; the answer is what they agree on."""
        raise NotImplementedError

    # -- the shared commit-or-abstain spine ---------------------------------
    def resolve(self, gap: Any, doc: MultiScaleDoc) -> Resolution:
        """Propose → ground-gate → score → commit-by-margin-or-ABSTAIN. The one place the cardinal
        discipline lives, so no subclass can accidentally violate it."""
        cands = [c for c in self.candidates(gap, doc) if self.ground(c, gap, doc)]
        if not cands:
            return Resolution(self.name, gap, None, (), "no grounded candidate: abstained")
        scored = sorted(
            (Scored(c, self.score(c, gap, doc)) for c in cands),
            key=lambda s: s.total, reverse=True,
        )
        best = scored[0]
        second = scored[1] if len(scored) > 1 else None
        decisive = (second is None) or (best.total - second.total >= self.margin)
        committed = best.answer if (decisive and best.total > 0) else None
        note = ("committed: decisive margin" if committed is not None
                else "no decisive winner: abstained")
        return Resolution(self.name, gap, committed, tuple(scored), note)

    def run(self, doc: MultiScaleDoc) -> List[Resolution]:
        """Resolve every gap this cassette finds in the document. The unit the corpus harness runs and
        the unit the cheat-sheet collects (committed resolutions only)."""
        return [self.resolve(g, doc) for g in self.gaps(doc)]
