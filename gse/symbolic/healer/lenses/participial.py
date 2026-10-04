"""L3 — participial_adjunct: a secondary-predicate participle whose event was dropped.

LIVE — runs in ``default_roster()``, revived after the downgrade recorded below (the roster's
docstring in ``lenses/__init__.py`` holds the record). ``emit`` meets the subject-attachment wall with
``fold_reader.best_subject``: the recurring, significant agent — with a confidence gate that ABSTAINS
rather than bind a one-shot nearby noun — falling back to the lexical main animate subject when no
fold map is supplied.

History — DOWNGRADED (2026-06-24), since superseded by the revival: NOT then a formal roster law;
soft filter for the chum bucket. It is a RECOVER-AND-ATTACH law (reconstruct a missing event + bind a
subject), and validated at ~50% precision: the residual wrong fires (`EVENT(swagger, twirl)`,
`EVENT(flight, pant)`) are SUBJECT-ATTACHMENT errors — the parse's resolved "main subject" is itself a
wrong nearby noun — which no animacy gate (lexical, NSM, or additive) fixes, because it is
attachment, not animacy. (The additive-lens ARCHITECTURE it proved is sound and reused.)


The defect is a MISSING predication, so this is an ADDITIVE lens (no wrong node to claim). A
comma-bounded or fronted present participle — `, throwing stones` / `, staggering,` / fronted
`Trying doors,` — is a CONCURRENT action of the main subject; when the parse drops it, the event is
simply absent. The lens recovers it as a second event sharing the main-clause subject.

Carved from the corpus (viability harvest: 939 lost / 283 clean — a large, regular, untapped
territory; the structural fixes never touched participials, so it is not pre-absorbed like vp_coord):
  GOLD       "Della ran, panting"          → … EVENT(della, pant)
  NEAR-MISS  the participle's event dropped → recover it.

LAW
  must     : for each comma-bounded/fronted -ing VERB whose lemma is not already an emitted event,
             emit EVENT(main_subject, participle).
  abstain  : -ing ADJECTIVE (interesting/boiling — adj WordNet sense) or GERUND-NOUN (the singing);
             no clean main-clause subject. Emit nothing rather than fabricate (clean-or-hole).
"""
from __future__ import annotations

import os

from gse.symbolic.predicates import Event

from ..lens import AdditiveLens, Repair
from ..treewalk import candidate_subjects, event_verbs, main_animate_subject
from ..fold_reader import best_subject

# Preceding-token POS that signals the -ing is a NOMINAL gerund, not a participial adjunct:
# "good lodging" (ADJ), "their muttering" (PRON poss.), "the singing" (DET), "night's drinking" (PART 's).
_NOMINAL_PREV = frozenset({"ADJ", "DET", "PRON", "PART"})

# The recollective-recall confidence gate (the abstention censor). The composite shows clean binds
# concentrate at conf ≥ 0.90 and the junk (inanimate/non-nominal leaks) sits lower, so the censor —
# not a hand stoplist over GSE's POS — is what rejects them. Env-tunable for the precision sweep.
# Below it ⇒ honest hole, never a fabricated bind.
_THETA = float(os.environ.get("GENESIS_HEALER_THETA", "0.88"))


def _subject_for_lemma(lemma, predicates):
    """Bridge the recalled candidate LEMMA back to a resolved Event-agent operand (the same pool
    ``best_subject`` chose from). No match ⇒ None (abstain) — never fabricate a node."""
    if not lemma:
        return None
    for op in candidate_subjects(predicates):
        if _lemma(op).lower() == lemma:
            return op
    return None


def _lemma(operand) -> str:
    head = getattr(operand, "head", None) or operand
    return getattr(head, "lemma", None) or "?"


class ParticipialAdjunct(AdditiveLens):
    name = "participial_adjunct"
    law = ("must: a comma-bounded/fronted -ing participle is a secondary predicate of the main "
           "subject → emit EVENT(main_subject, participle); abstain on -ing adjective / gerund-noun "
           "/ no clean subject.")

    def emit(self, predicates, env, folds=None):
        if env is None:
            return []
        cands = env.participial_adjuncts()
        if not cands:
            return []
        # LAYER-2 REVIVAL: pick the subject by document-scale SIGNIFICANCE ("shape from the field" —
        # the recurring protagonist over a one-shot nearby noun), the disambiguator for the attachment
        # wall. Falls back to the lexical first-clean-animate anchor when no fold map is supplied.
        subj = best_subject(candidate_subjects(predicates), folds) if folds else main_animate_subject(predicates)
        already = event_verbs(predicates)
        mem = None
        mem_loaded = False                             # lazy: load the warm memory only on abstain
        out = []
        for pos, lemma in cands:
            if not lemma or lemma in already:
                continue                              # already surfaced as an event
            senses = env.senses.get(pos, {})
            if senses.get("a"):
                continue                              # -ing ADJECTIVE (interesting/boiling), not an adjunct
            prev_pos = env.prev.get(pos, ("", ""))[1]
            if senses.get("n") and (env.prev_func.get(pos) or prev_pos in _NOMINAL_PREV):
                continue                              # GERUND-NOUN ("good lodging" / "their muttering")

            anchor = subj
            note = f"participial adjunct → EVENT({_lemma(subj)}, {lemma})" if subj is not None else ""
            if anchor is None:
                # the fold abstained (no recurring agent) → RECOLLECTIVE RECALL by resemblance, the
                # residual the trained K-line memory owns (Law-as-Architecture §6).
                if not mem_loaded:
                    from ..recollect import default_memory
                    mem = default_memory(name="baseline")    # the ONE Brown-baseline library
                    mem_loaded = True
                if mem is not None:
                    from ..recollect import envelope_query
                    q = envelope_query(env, pos, "participial")   # superposition: firing-pattern tag
                    if q is not None:
                        key_syms, cand_descs = q
                        rec = mem.recall(key_syms, [d for _, d in cand_descs])
                        if rec.index is not None and rec.confidence >= _THETA:
                            anchor = _subject_for_lemma(cand_descs[rec.index][0], predicates)
                            note = (f"participial adjunct → EVENT({_lemma(anchor)}, {lemma}) "
                                    f"via k-line recall (conf {rec.confidence:.2f})")
            if anchor is None:
                continue                              # no eligible anchor → honest hole (clean-or-hole)
            out.append(Repair(Event(verb=lemma, agent=anchor, patient=None), self.name, note=note))
            already.add(lemma)
        return out
