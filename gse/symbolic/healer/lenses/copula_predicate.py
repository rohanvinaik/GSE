"""L1 — copula_predicate: a predicate ADJECTIVE under a copula miscast as an Event.

Carved one-shot from the corpus minimal pair (94 near-miss / 159 gold):
  GOLD       "the dog is happy"      → TYPE_ASSERT(dog, happy)
  NEAR-MISS  "the face was bloodless" → EVENT(face){verb='bloodless'}   ← the lesion

LAW
  must-not : an ``Event`` whose verb is a predicate adjective under a copula (the verb word is
             ADJ-tagged in this sentence, has an adjective WordNet sense, and has NO verb reading —
             read from the envelope, premise-complete, no trace).
  must     : rebuild as ``TypeAssertion(entity=agent, kind=<adjective>)`` — the native GOLD shape.
  abstain  : if the agent is not a cleanly-resolved entity (the ``?`` / unbound cases) — never
             fabricate a subject (clean-or-hole).
"""

from __future__ import annotations

from gse.symbolic.expression import Atom
from gse.symbolic.predicates import Event, TypeAssertion

from ..lens import Hole, Lens, Repair


def _clean_entity(operand) -> bool:
    """A real, resolved subject — not the parser's ``?`` placeholder or an empty filler.
    Deictic/pronoun subjects (i/you) are allowed through; L8 deictic_bind binds them later."""
    if operand is None:
        return False
    head = getattr(operand, "head", None) or operand
    lemma = getattr(head, "lemma", None) or ""
    return bool(lemma) and lemma.isalpha() and lemma != "?"


class CopulaPredicate(Lens):
    name = "copula_predicate"
    law = (
        "must-not: an Event's verb is a predicate ADJECTIVE under a copula; "
        "must: rebuild as TYPE_ASSERT(agent, adj); abstain if the agent is not a clean entity."
    )

    def claims(self, node, env, folds=None) -> bool:
        if env is None or not env.has_copula:
            return False
        if not isinstance(node, Event):
            return False
        return env.is_predicate_adjective(getattr(node, "verb", ""))

    def apply(self, node, env, folds=None):
        agent = getattr(node, "agent", None)
        if not _clean_entity(agent):
            return Hole(self.name, "agent_unresolved")
        adj = (getattr(node, "verb", "") or "").lower()
        kind = Atom(lemma=adj, pos="ADJ")
        return Repair(
            TypeAssertion(entity=agent, kind=kind),
            self.name,
            note=f"copula predicate-adjective: EVENT{{{adj}}} → TYPE_ASSERT(_, {adj})",
        )
