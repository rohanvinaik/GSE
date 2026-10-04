"""L4 — infinitival_control: a ``to <verb>`` control/purpose complement whose event was dropped.

A RECOVER-AND-ATTACH law of the same shape as L3 participial — the dropped piece is a MISSING
predication (the infinitival act), so this is an ADDITIVE lens. Like L3, it is clean ONLY because
LAYER 2 supplies the controller: ``best_subject`` anchors the recovered act on the recurring
protagonist ("shape from the field") and ABSTAINS (clean-or-hole) when no confident subject exists —
never the global-topic fallback (the compaction-paper §4.1 false-spine trap).

  GOLD       "I was to start ... to make my fortune" → … EVENT(i, make)   (the purpose infinitival)
  NEAR-MISS  the infinitival's event dropped         → recover it, controller = the matrix subject.

LAW
  must     : for each ``to <verb>`` VERB token whose lemma is not already an emitted event, emit
             EVENT(controller, infinitival) with the controller = the fold-chosen recurring subject.
  abstain  : noun-homograph (sense n, not v); lemma already surfaced; no confident controller. Emit
             nothing rather than fabricate.
"""

from __future__ import annotations

import os

from gse.symbolic.predicates import Event

from ..fold_reader import best_subject
from ..lens import AdditiveLens, Repair
from ..treewalk import candidate_subjects, event_verbs, main_animate_subject

# The recollective-recall confidence gate (the abstention censor), mangle-specific. Env-tunable.
_THETA = float(os.environ.get("GENESIS_HEALER_THETA_INF", "0.88"))


def _lemma(operand) -> str:
    head = getattr(operand, "head", None) or operand
    return getattr(head, "lemma", None) or "?"


def _subject_for_lemma(lemma, predicates):
    """Bridge a recalled controller LEMMA back to a resolved Event-agent operand. No match ⇒ None."""
    if not lemma:
        return None
    for op in candidate_subjects(predicates):
        if _lemma(op).lower() == lemma:
            return op
    return None


class InfinitivalControl(AdditiveLens):
    name = "infinitival_control"
    law = (
        "must: a `to <verb>` control/purpose complement whose event dropped → emit "
        "EVENT(controller, infinitival), controller = the fold-chosen recurring subject; "
        "abstain on noun-homograph / already-emitted / no confident controller."
    )

    def emit(self, predicates, env, folds=None):
        if env is None:
            return []
        cands = env.infinitival_complements()
        if not cands:
            return []
        # LAYER-2: the controller is the recurring protagonist (shape from the field), else abstain.
        subj = best_subject(candidate_subjects(predicates), folds) if folds else main_animate_subject(predicates)
        already = event_verbs(predicates)
        mem = None
        mem_loaded = False  # lazy: load the warm memory only on abstain
        out = []
        for pos, lemma in cands:
            if not lemma or lemma in already:
                continue
            senses = env.senses.get(pos, {})
            if senses.get("n") and not senses.get("v"):
                continue  # noun-only homograph mis-tagged VERB → abstain

            anchor = subj
            note = f"infinitival → EVENT({_lemma(subj)}, {lemma})" if subj is not None else ""
            if anchor is None:
                # the fold abstained → RECOLLECTIVE RECALL of the controller binding (the residual the
                # trained infinitival K-line owns).
                if not mem_loaded:
                    from ..recollect import default_memory

                    mem = default_memory(name="baseline")  # the ONE Brown-baseline library
                    mem_loaded = True
                if mem is not None:
                    from ..recollect import envelope_query

                    q = envelope_query(env, pos, "infinitival")  # superposition: firing-pattern tag
                    if q is not None:
                        key_syms, cand_descs = q
                        rec = mem.recall(key_syms, [d for _, d in cand_descs])
                        if rec.index is not None and rec.confidence >= _THETA:
                            anchor = _subject_for_lemma(cand_descs[rec.index][0], predicates)
                            note = (
                                f"infinitival → EVENT({_lemma(anchor)}, {lemma}) "
                                f"via k-line recall (conf {rec.confidence:.2f})"
                            )
            if anchor is None:
                continue  # no eligible controller → honest hole
            out.append(Repair(Event(verb=lemma, agent=anchor, patient=None), self.name, note=note))
            already.add(lemma)
        return out
