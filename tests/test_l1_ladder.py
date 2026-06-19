"""The L1 compositionality ladder.

A graded, ordered battery that is the *spine* keeping GSE's sentence-level
processing genuinely compositional: each rung adds one capacity, and every rung
must (a) recover the asserted structure with correctly *bound* arguments, (b) not
be flagged degraded by the coherence gate, and (c) for composed rungs, contain
the substructures of the lower rungs it is built from — so a new feature has to
be additive, not a parallel hand-built implementation that breaks its priors.

Frontier rungs (capacities not yet built) are ``xfail`` with their expected
structure; landing the feature flips the rung green. The ladder is the roadmap.
"""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import evaluate_tree
from gse.symbolic.coherence import coherence_report
from gse.symbolic.expression import from_trace
from gse.symbolic.resolution import resolve
from gse.symbolic.serialization import to_dict


@pytest.fixture(scope="module")
def enc():
    return GSEEncoder()


# --- structural search over the serialized tree ----------------------------

def _walk(d):
    if isinstance(d, dict):
        yield d
        for v in d.values():
            yield from _walk(v)
    elif isinstance(d, list):
        for v in d:
            yield from _walk(v)


def _tree(enc, text):
    return to_dict(resolve(from_trace(enc.encode(text))))


def _event(d, verb):
    """The EVENT Op for a given verb lemma, if present."""
    return next((n for n in _walk(d)
                 if n.get("_kind") == "Op" and n.get("operation") == "EVENT"
                 and n.get("primitive") == verb), None)


def _op(d, operation):
    return next((n for n in _walk(d)
                 if n.get("_kind") == "Op" and n.get("operation") == operation), None)


def _lemmas(d):
    return {n.get("lemma") for n in _walk(d) if n.get("_kind") == "Atom"}


def _event_binds(d, verb, *args):
    """An EVENT(verb) exists and the given lemmas all appear within it."""
    ev = _event(d, verb)
    return ev is not None and all(a in _lemmas(ev) for a in args)


def _degraded(enc, text):
    tr = enc.encode(text)
    return [r["clause"] for r in coherence_report(evaluate_tree(from_trace(tr)), tr)]


# ===========================================================================
# R1 — base predication
# ===========================================================================

def test_rung1_base_predication(enc):
    # SVO event (verb-POS repair recovers the subject), intransitive, copula.
    assert _event_binds(_tree(enc, "Macbeth murders Duncan."), "murder", "macbeth", "duncan")
    assert _event_binds(_tree(enc, "Goliath falls."), "fall", "goliath")
    assert _op(_tree(enc, "Duncan is a king."), "TYPE_ASSERT") is not None


# ===========================================================================
# R2 — within-clause operators
# ===========================================================================

def test_rung2_within_clause_operators(enc):
    assert _op(_tree(enc, "Mike is taller than Rex"), "SET_DIFF") is not None
    neg = next((n for n in _walk(_tree(enc, "Macbeth did not murder Duncan"))
                if n.get("_kind") == "Negation"), None)
    assert neg is not None and _event(neg, "murder") is not None


# ===========================================================================
# R3 — clause-linking
# ===========================================================================

def test_rung3_clause_linking(enc):
    so = _tree(enc, "Mike sang so Rex left")
    assert _op(so, "CONSEQUENCE") is not None
    assert _event_binds(so, "sing", "mike") and _event_binds(so, "leave", "rex")

    bc = _tree(enc, "Mike left because Rex sang")
    assert _op(bc, "CAUSAL_SOURCE") is not None
    assert _event_binds(bc, "leave", "mike") and _event_binds(bc, "sing", "rex")


# ===========================================================================
# R4 — embedded predication (A1 relatives, A2 complements)
# ===========================================================================

def test_rung4_relative_subject_gap(enc):  # A1
    d = _tree(enc, "Macbeth, who trusted the witches, murdered Duncan.")
    assert _op(d, "REL_RESTRICT") is not None
    assert _event_binds(d, "trust", "macbeth", "witch")   # gap bound to antecedent
    assert _event_binds(d, "murder", "duncan")


def test_rung4_relative_object_gap(enc):  # A1
    d = _tree(enc, "The king whom Macbeth murdered was Duncan.")
    assert _op(d, "REL_RESTRICT") is not None
    assert _event_binds(d, "murder", "macbeth", "king")   # both subject + object-gap bound


def test_rung4_complement(enc):  # A2
    d = _tree(enc, "The witches predicted that Macbeth would become king.")
    assert _event_binds(d, "predict", "witch")
    assert _event_binds(d, "become", "macbeth", "king")   # nested proposition recovered


# ===========================================================================
# R5 — composition (additivity): relative ∘ causation in one sentence
# ===========================================================================

def test_rung5_composition_relative_in_causation(enc):
    d = _tree(enc, "Macduff, who loved his country, fled because Macbeth murdered the king.")
    # the causation substructure (R3) AND the gap-bound relative (R4) both present
    assert _op(d, "CAUSAL_SOURCE") is not None
    assert _op(d, "REL_RESTRICT") is not None
    assert _event_binds(d, "love", "macduff")     # relative gap bound
    assert _event_binds(d, "flee", "macduff")
    assert _event_binds(d, "murder", "macbeth", "king")


# ===========================================================================
# Coherence oracle — no clean ladder sentence is flagged degraded
# ===========================================================================

@pytest.mark.parametrize("sentence", [
    "Macbeth murders Duncan.",
    "Duncan is a king.",
    "Mike sang so Rex left",
    "Macbeth, who trusted the witches, murdered Duncan.",
    "The king whom Macbeth murdered was Duncan.",
    "The witches predicted that Macbeth would become king.",
    "Macduff, who loved his country, fled because Macbeth murdered the king.",
])
def test_clean_rungs_not_degraded(enc, sentence):
    assert _degraded(enc, sentence) == []


# ===========================================================================
# Frontier — the roadmap. xfail until the feature lands, then flip to assert.
# ===========================================================================

@pytest.mark.xfail(reason="A3 control not built yet", strict=False)
def test_frontier_control(enc):  # A3
    d = _tree(enc, "Lady Macbeth wanted Macbeth to become king.")
    assert _op(d, "CONTROL") is not None
    assert _event_binds(d, "become", "macbeth", "king")


@pytest.mark.xfail(reason="B clause-level coordination not built yet", strict=False)
def test_frontier_clause_coordination(enc):  # B
    d = _tree(enc, "Macbeth murdered Duncan and Macduff killed Macbeth.")
    murder, kill = _event(d, "murder"), _event(d, "kill")
    assert murder is not None and kill is not None
    # the two clauses must be *coordinate*, not one swallowed into the other
    # (today: murder[macbeth, Coordination[kill...]] — the structural failure B fixes)
    assert _event(murder, "kill") is None and _event(kill, "murder") is None
    assert _event_binds(d, "murder", "macbeth", "duncan")
    assert _event_binds(d, "kill", "macduff", "macbeth")


@pytest.mark.xfail(reason="D conditionals not built yet", strict=False)
def test_frontier_conditional(enc):  # D
    d = _tree(enc, "If Macbeth murders Duncan then Macduff will flee.")
    assert _op(d, "IMPLIES") is not None
