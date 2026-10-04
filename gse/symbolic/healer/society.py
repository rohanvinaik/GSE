"""The Society of Mind — the statement-healer orchestrator at the ``from_document(repair=)`` seam.

Runs over the WIDE statement set (all collected predicates, still structurally intact, before the
compaction collapse). For each ``(t, predicate)`` it looks up that utterance's envelope and lets the
ONE lens whose law claims the node repair-or-abstain — no cross-talk, one law per node. Repairs and
holes are recorded with provenance. An empty roster is an inert pass-through, so the seam is safe to
wire before any law has landed.

The hook contract matches ``NarrativeGraph.from_document(repair=...)``: ``[(t, predicate), ...] ->
[(t, predicate), ...]``. The per-utterance envelopes ride in via the closure (``make_repair_hook``),
not the predicate tuple — the parse-time mark carried forward to the trace-less seam.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, List, Optional

from .lens import AdditiveLens, Hole, Repair
from .fold_reader import read_fold


@dataclass
class HealReport:
    """Provenance of one heal pass — what fired, what abstained, over how many statements."""
    seen: int = 0
    repairs: List[tuple] = field(default_factory=list)   # (t, lens, note)
    holes: List[tuple] = field(default_factory=list)     # (t, lens, reason)

    def summary(self) -> dict:
        from collections import Counter
        by_lens = Counter(l for _t, l, _n in self.repairs)
        by_hole = Counter(l for _t, l, _r in self.holes)
        return {"seen": self.seen, "repaired": len(self.repairs), "holes": len(self.holes),
                "by_lens": dict(by_lens), "by_hole": dict(by_hole)}


class Society:
    """The roster of law-grounded lenses + the repair pass over the wide statement set."""

    def __init__(self, roster, memory=None, genealogy=None):
        self.roster = list(roster)
        self.memory = memory
        self.genealogy = genealogy        # the GenealogyStore — the world strand for Layer 2 (optional)
        self.report = HealReport()
        self.folds = {}                   # last pass's fold map (audit/inspection)

    def _env(self, envelopes, t):
        return envelopes[t] if (envelopes and 0 <= t < len(envelopes)) else None

    def repair_timed(self, timed: List[tuple], envelopes: Optional[List[Any]]) -> List[tuple]:
        node_lenses = [l for l in self.roster if not isinstance(l, AdditiveLens)]
        add_lenses = [l for l in self.roster if isinstance(l, AdditiveLens)]

        # PHASE 0 — LAYER 2: read the multi-strand fold map over the WHOLE document, so the structural
        # lenses can consult the document-scale semantic resolution (e.g. subject disambiguation by
        # significance — "shape from the field"). Built once per heal pass; never fabricates structure.
        try:
            folds = read_fold(timed, envelopes, self.genealogy)
        except Exception:
            folds = {}
        self.folds = folds

        # PHASE 1 — node-local transforms (a wrong node → its repair, 1:1; one law per node).
        out: List[tuple] = []
        for t, pred in timed:
            self.report.seen += 1
            env = self._env(envelopes, t)
            node = pred
            for lens in node_lenses:
                try:
                    if not lens.claims(pred, env, folds):
                        continue
                except Exception:
                    continue            # a lens that errors on a node simply does not claim it
                res = lens.apply(pred, env, folds)
                if isinstance(res, Repair):
                    node = res.node
                    self.report.repairs.append((t, res.lens, res.note))
                elif isinstance(res, Hole):
                    self.report.holes.append((t, res.lens, res.reason))
                break                   # one law per node — no cross-talk (inverse-brittleness)
            out.append((t, node))

        # PHASE 2 — utterance-level additive lenses (a MISSING predication → emit the recovery).
        if add_lenses:
            by_t = defaultdict(list)
            for t, p in out:
                by_t[t].append(p)
            for t, preds in by_t.items():
                env = self._env(envelopes, t)
                for lens in add_lenses:
                    try:
                        emitted = lens.emit(preds, env, folds) or []
                    except Exception:
                        continue
                    for res in emitted:
                        if isinstance(res, Repair):
                            out.append((t, res.node))
                            self.report.repairs.append((t, res.lens, res.note))
        return out


def make_repair_hook(envelopes: Optional[List[Any]], roster=None, memory=None, genealogy=None):
    """Build the ``repair=`` callable for ``NarrativeGraph.from_document``.

    ``envelopes`` is the per-utterance ``StatementMeta`` list, indexed by timestep ``t`` (= tree
    index). ``genealogy`` (the GenealogyStore, available at the call site) is the Layer-2 world strand —
    pass it to enable sparse-wiki grounding in the fold map; omit it and the other three strands still
    resolve. The returned hook carries them in its closure and exposes ``.society`` for the report.
    """
    from .lenses import default_roster
    society = Society(roster if roster is not None else default_roster(), memory, genealogy)

    def hook(timed: List[tuple]) -> List[tuple]:
        return society.repair_timed(timed, envelopes)

    hook.society = society
    return hook
