"""L7 — vp_coord_conjunct: VP-coordination where one conjunct's verb was stranded.

LIVE — runs in ``default_roster()``, revived after the downgrade recorded below (the roster's
docstring in ``lenses/__init__.py`` holds the record). ``apply`` meets the subject wall itself: the
good conjunct's structural subject, nulled when inanimate or fold-judged ineligible, else K-line
recollective recall at confidence ≥ ``_THETA`` (``GENESIS_HEALER_THETA_VP``), else an honest Hole.

History — DOWNGRADED (2026-06-24), since superseded by the revival: NOT then a formal roster law; a
soft routing FILTER for the chum bucket only. Validated at the seam, precision plateaued ~55% after
four principled gates: the structural fixes (`expression.py` 14e0ed9) already recovered the tractable
VP-coordinations, so the residual is a degraded tail with no structural feature left to separate ~6
true recoveries from ~5 spine-polluting false fires. It was kept (built, tested) for a bespoke /
cordoned-residual pass and removed from `default_roster()` until the revival above.


Carved one-shot from the corpus minimal pair (post structural-fixes: 61 near-miss / 3354 gold):
  GOLD       "ran to the house and came back"  → CLAUSE_COORD(EVENT{run}, EVENT{come})
  NEAR-MISS  the second VP mis-collapsed, its finite verb left orphaned in a non-event sibling
             (CONTRAST / EQUALITY / TYPE_ASSERT…), so its predication is LOST.

LAW
  must-not : a ClauseCoordination with exactly ONE Event conjunct and a sibling carrying a stranded
             finite verb (an Atom, VERB-tagged, with a verb sense, not inside a Coordination).
  must     : recover the lost predication as EVENT(shared_subject, …){verb=orphan}, with the subject
             shared from the good conjunct. The container contributes no graph edge itself, so the
             lens REPLACES it with the recovered Event — the good conjunct stays (its own list entry),
             the inert bad conjunct stays inert; net, the orphan's edge is added.
  abstain  : no shared subject; orphan not unambiguously inflected; predicate-ADJECTIVE under a
             linking verb (L1's territory — adjective coordination, not VP coordination); gerund-noun.
"""

from __future__ import annotations

import os

from gse.symbolic.predicates import ClauseCoordination, Event

from ..lens import Hole, Lens, Repair
from ..treewalk import animate_subject, clean_subject, free_verbs, has_event, subject_operand, walk

# Subordinate-clause containers: their verbs are NOT VP-coordinate heads, so the orphan search
# must not descend into them (a relative-clause verb like "who founded …" is not a coordinated VP).
_SUBORD_BOUNDARY = frozenset({"RelativeRestriction", "Control", "Conditional", "Temporal", "Causation"})

# Recollective-recall confidence gate for the thin vp_coord residual (the no-shared-subject case).
_THETA = float(os.environ.get("GENESIS_HEALER_THETA_VP", "0.88"))


def _lemma(operand) -> str:
    head = getattr(operand, "head", None) or operand
    return getattr(head, "lemma", None) or "?"


def _operand_for_lemma(lemma, node):
    """Find a clean subject operand inside the coordination matching a recalled lemma (never fabricate)."""
    if not lemma:
        return None
    for n in walk(node):
        if clean_subject(n) and _lemma(n).lower() == lemma:
            return n
    return None


class VpCoord(Lens):
    name = "vp_coord_conjunct"
    law = (
        "must-not: a ClauseCoordination with one Event conjunct + a sibling holding a stranded "
        "finite verb; must: recover EVENT(shared_subject, ){verb=orphan}; abstain on no-subject / "
        "uninflected orphan / predicate-adjective / gerund-noun."
    )

    def claims(self, node, env, folds=None) -> bool:
        if env is None or not isinstance(node, ClauseCoordination):
            return False
        le, re = has_event(node.left), has_event(node.right)
        if le == re:  # both events (gold) or neither → not my territory
            return False
        bad = node.right if le else node.left
        return bool(free_verbs(bad, boundary=_SUBORD_BOUNDARY))

    def apply(self, node, env, folds=None):
        # HIGH PRECISION (user 2026-06-24): fire only on an unambiguous coordinated FINITE verb;
        # abstain on everything doubtful (the chum bucket / later laws catch it). A wrong recovered
        # Event pollutes the spine; an honest hole is free.
        if getattr(node, "conjunction", "and") not in ("and", "or"):
            return Hole(self.name, "not_and_or")  # only parallel coordination
        le = has_event(node.left)
        good = node.left if le else node.right
        bad = node.right if le else node.left
        # Find the stranded orphan FIRST — its position is needed for both recovery and recall.
        orphans = free_verbs(bad, boundary=_SUBORD_BOUNDARY)
        if not orphans:
            return Hole(self.name, "orphan_subordinate_only")  # only subordinate-clause verbs, not a VP head
        orphan = orphans[0]
        pos = getattr(orphan, "position", None)
        if pos is None or not env.is_inflected_verb(pos):
            return Hole(self.name, "orphan_not_inflected")
        senses = env.senses.get(pos, {})
        surf = (env.surface.get(pos, orphan.lemma) or "").lower()
        prev_lemma = env.prev.get(pos, ("", ""))[0]
        # the false-fire families, each killed by a tag the envelope already carries:
        if senses.get("a"):
            return Hole(self.name, "adjectival_orphan")  # jagged/situated/down/chosen — attributive/particle
        if surf.endswith("ing"):
            return Hole(self.name, "ing_form")  # gerund/participial → L3 / gerund-noun, not finite VP
        if prev_lemma in ("be", "being", "been"):
            return Hole(self.name, "passive_participle")  # "may be used" — passive, not a stranded VP verb

        # SUBJECT: the structural shared subject (from the good conjunct) first; null it if inanimate or
        # fold-judged a non-referent, then fall back to recollective recall (the thin degraded residual).
        subj = subject_operand(good)
        if subj is not None and not animate_subject(subj):
            subj = None  # mauve/performance can't be an agent → try recall
        if subj is not None and folds is not None:
            f = folds.get(getattr(subj, "entity_id", None))
            if f is not None and not f.eligible:
                subj = None
        note = f"vp_coord: stranded '{orphan.lemma}' → EVENT({_lemma(subj)}, {orphan.lemma})"
        if subj is None:
            from ..recollect import default_memory, envelope_query

            mem = default_memory(name="baseline")  # the ONE Brown-baseline library
            if mem is not None:
                q = envelope_query(env, pos, "vpcoord")  # superposition: firing-pattern tag
                if q is not None:
                    key_syms, cand_descs = q
                    rec = mem.recall(key_syms, [d for _, d in cand_descs])
                    if rec.index is not None and rec.confidence >= _THETA:
                        subj = _operand_for_lemma(cand_descs[rec.index][0], node)
                        if subj is not None:
                            note = (
                                f"vp_coord: stranded '{orphan.lemma}' → EVENT({_lemma(subj)}, "
                                f"{orphan.lemma}) via k-line recall (conf {rec.confidence:.2f})"
                            )
        if subj is None:
            return Hole(self.name, "no_shared_subject")
        recovered = Event(verb=orphan.lemma, agent=subj, patient=None)
        return Repair(recovered, self.name, note=note)
