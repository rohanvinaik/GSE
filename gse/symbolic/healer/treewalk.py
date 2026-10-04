"""Shared predicate-tree walkers for the structural lenses (vp_coord, matrix_collapse, participial…).

Kept here, not duplicated per lens. Uses the system's own field spec (`emit._PRED_SPEC`) so the walk
tracks the predicate schema rather than a hand-maintained copy.
"""

from __future__ import annotations

from typing import List, Optional

from gse.symbolic.emit import _PRED_SPEC
from gse.symbolic.expression import Atom
from gse.symbolic.predicates import Event
from gse.symbolic.resolution import Coordination

from .envelope import _has_verb_sense


def children(node) -> List:
    """The structural children of a predicate node, via the shared field spec."""
    name = type(node).__name__
    spec = _PRED_SPEC.get(name)
    if spec:
        return [getattr(node, f) for f in spec[1] if getattr(node, f, None) is not None]
    if name == "Entity":
        return [
            x
            for x in (getattr(node, "head", None), getattr(node, "modifier", None), getattr(node, "possessor", None))
            if x is not None
        ]
    if name == "Coordination":
        return list(getattr(node, "members", []) or [])
    if name == "Phrase":
        return list(getattr(node, "atoms", []) or [])
    if name == "Negation":
        op = getattr(node, "operand", None)
        return [op] if op is not None else []
    if name == "Op":
        return list(getattr(node, "args", []) or [])
    return []


def walk(node):
    yield node
    for c in children(node):
        yield from walk(c)


def has_event(node) -> bool:
    return any(isinstance(n, Event) for n in walk(node))


def free_verbs(node, under_coord: bool = False, boundary=frozenset()) -> List[Atom]:
    """Tagged-VERB Atoms not already inside a Coordination — i.e. a stranded/orphaned finite verb
    (the vp_coord signature: a verb left dangling when its conjunct mis-collapsed).

    ``boundary`` = predicate type-names NOT to descend into. VP-coordination is between *matrix*
    clause heads, so a caller passes the subordinate-clause containers (RelativeRestriction, Control,
    Conditional, Temporal, Causation) to exclude their verbs — those are not VP-coordinate heads."""
    out: List[Atom] = []
    if type(node).__name__ in boundary:
        return out
    is_co = isinstance(node, Coordination)
    if (
        isinstance(node, Atom)
        and getattr(node, "pos", None) == "VERB"
        and _has_verb_sense((node.lemma or "").lower())
        and not under_coord
    ):
        out.append(node)
    for c in children(node):
        out += free_verbs(c, under_coord or is_co, boundary)
    return out


def subject_operand(node):
    """The agent Operand of the first Event under ``node`` whose agent heads a nominal — the
    shared subject a sibling conjunct inherits."""
    for n in walk(node):
        if isinstance(n, Event):
            agent = getattr(n, "agent", None)
            head = getattr(agent, "head", None) or agent
            if agent is not None and getattr(head, "pos", None) in ("NOUN", "PROPN", "PRON"):
                return agent
    return None


def first_event_verb(node) -> Optional[str]:
    for n in walk(node):
        if isinstance(n, Event):
            return getattr(n, "verb", None)
    return None


def clean_subject(operand) -> bool:
    """A real, resolved subject — not the parser's ``?`` placeholder. (Animacy NOT required —
    a participial adjunct can take an inanimate concurrent actor: "hair, rippling".)"""
    if operand is None:
        return False
    head = getattr(operand, "head", None) or operand
    lemma = getattr(head, "lemma", None) or ""
    return bool(lemma) and lemma.isalpha() and lemma != "?"


def event_verbs(predicates) -> set:
    """The set of EVENT verb lemmas already present across a list of predicates (so an additive lens
    does not re-emit a predication that already surfaced)."""
    out = set()
    for p in predicates:
        for n in walk(p):
            if isinstance(n, Event):
                out.add((getattr(n, "verb", "") or "").lower())
    return out


def main_subject(predicates):
    """The main-clause subject for an utterance: the agent of the first Event (over all predicates)
    that resolves to a clean entity. The anchor a participial adjunct's recovered event shares."""
    for p in predicates:
        subj = subject_operand(p)
        if subj is not None and clean_subject(subj):
            return subj
    return None


_ANIMATE_PRON = frozenset({"i", "we", "you", "he", "she", "they", "me", "us", "him", "her", "them"})


def entity_role(operand) -> str:
    """The NSM semantic role of a resolved entity via GSE's OWN ``narrative.classify`` over its
    ``word_primitives`` (+ ``thread`` if present) — agent / experiencer / object / evaluation / '?'.
    The register-INVARIANT animacy/role signal that replaces the WordNet ``_is_person`` proxy: it
    keys on semantic primitives (the 8 NSM banks), so it holds across registers (the robustness path)."""
    if operand is None:
        return "?"
    head = getattr(operand, "head", None) or operand
    prims = getattr(head, "word_primitives", None) or {}
    if not prims:
        return "?"
    thread = getattr(head, "thread", None) or ()
    try:
        from gse.symbolic.narrative import classify

        role, _elig, _banks = classify(prims, tuple(thread))
        return role
    except Exception:
        return "?"


def animate_subject(operand) -> bool:
    """A plausible agent. ORTHOGONAL-EVIDENCE, additive (the 'enhanced signal, don't break' design):

    LEXICAL animacy is checked FIRST and is authoritative — it is reliable exactly where the NSM role
    is not: personal pronouns and animals (`classify` wrongly objects 'he'/'horse', which fire only
    SUBSTANTIVES). Then the bank role is consulted as a pure ADD: only ``role=="agent"`` (classify's
    one reliable animate call — man/dick) can promote a content noun the lexical check missed. The
    noisy NSM calls — ``experiencer`` (swagger), ``object`` (he/horse) — are NOT consulted, so the gate
    is provably ≥ the lexical baseline; the semantic source can only help, never regress."""
    if operand is not None:
        head = getattr(operand, "head", None) or operand
        lemma = (getattr(head, "lemma", "") or "").lower()
        pos = getattr(head, "pos", None)
        if pos == "PRON" and lemma in _ANIMATE_PRON:
            return True
        if pos == "PROPN":
            return True
        try:
            from gse.symbolic.grounding import _is_person

            if _is_person(lemma) is True:
                return True
        except Exception:
            pass
    return entity_role(operand) == "agent"  # additive: classify can only ADD an agent, never reject


def main_animate_subject(predicates):
    """The first Event agent that is a clean, ANIMATE entity — the reliable attachment anchor."""
    for p in predicates:
        subj = subject_operand(p)
        if subj is not None and clean_subject(subj) and animate_subject(subj):
            return subj
    return None


def candidate_subjects(predicates):
    """Every clean Event-agent operand across an utterance — the candidate attachment anchors a
    fold-informed lens chooses among. ``fold_reader.best_subject`` picks the highest-SIGNIFICANCE one
    (the recurring protagonist over a one-shot nearby noun) — the disambiguator that un-buckets the
    L3/L7 subject-attachment wall, where ``main_animate_subject`` (first-clean-animate) grabbed the
    wrong nearby noun (swagger/flight)."""
    out, seen = [], set()
    for p in predicates:
        for n in walk(p):
            if isinstance(n, Event):
                a = getattr(n, "agent", None)
                if a is not None and clean_subject(a) and id(a) not in seen:
                    seen.add(id(a))
                    out.append(a)
    return out
