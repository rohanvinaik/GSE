"""
Per-operator semantic functions for Phase B2.

Each function consumes an :class:`gse.symbolic.expression.Op` node and
returns a :class:`gse.symbolic.predicates.Predicate` representing the
operator's symbolic semantics. Specs are user-authored — see
``docs/PHASE_B_SCOPE.md``. Per architecture document line 164: pure
Python, no HDC vector math.

Public API:

* :func:`evaluate` — dispatch a single Op to its semantic function.
* :func:`evaluate_tree` — walk an Expression tree, evaluating every Op
  encountered, producing a tree of Expressions + Predicates.
"""

from __future__ import annotations

from typing import Callable, Dict

from gse.symbolic.expression import Atom, Negation, Op, Operand, Phrase
from gse.symbolic.predicates import (
    BoundaryCase,
    Causation,
    Comparison,
    Contrast,
    Control,
    DegreeQuery,
    Equality,
    MinimalSufficiency,
    Predicate,
    RelativeRestriction,
    SetRestriction,
    TypeAssertion,
    TypeQuery,
)


class UnknownOperation(ValueError):
    """Raised when an Op carries an operation label with no dispatch."""


def _require_arity(op: Op, expected: int) -> None:
    if op.arity != expected or len(op.args) != expected:
        raise ValueError(
            f"{op.operation} expects arity {expected}, "
            f"got op.arity={op.arity}, len(args)={len(op.args)}"
        )


# ---------------------------------------------------------------------------
# Per-operator semantic functions
# ---------------------------------------------------------------------------


def set_diff(op: Op) -> Comparison:
    """COMP_THAN / SET_DIFF — sign-aware set difference.

    Architecture line 141: ``[MIKE'S DOG]*[-1]set_diff{[CUTE]*[REX]}>0``.
    Maps "X is more-Y than Z" to ``Comparison(lhs=X, rhs=Z, sign=+1)``.
    """
    _require_arity(op, 2)
    return Comparison(lhs=op.args[0], rhs=op.args[1], sign=+1)


def bind_eq(op: Op) -> Equality:
    """COMP_AS / BIND_EQ — symmetric equivalence on the implicit axis.

    User spec: "X is as Y as Z" binds X and Z as having equivalent value
    on the Y axis. Non-directional.
    """
    _require_arity(op, 2)
    return Equality(lhs=op.args[0], rhs=op.args[1])


def degree_query(op: Op) -> DegreeQuery:
    """COMP_HOW / DEGREE_QUERY — query the degree of an entity.

    Architecture line 145: HOW is a conditional operation on the
    following independent clause ending at clause-terminating punctuation.
    arity=1: the entity being queried.
    """
    _require_arity(op, 1)
    return DegreeQuery(entity=op.args[0])


def type_query(op: Op) -> TypeQuery:
    """COMP_WHAT / TYPE_QUERY — query the SUBSTANTIVES-bank decomposition.

    User spec: "What is X?" returns X's KIND/SOMEONE/SOMETHING/PEOPLE/BODY
    primitive activations from its word_primitives.
    """
    _require_arity(op, 1)
    return TypeQuery(entity=op.args[0])


def type_assert(op: Op) -> TypeAssertion:
    """COPULA / TYPE_ASSERT — declarative "X is a Y" type membership.

    The assertion counterpart to TYPE_QUERY. Synthesized in ``from_trace``
    from the copula pattern (SYN_SUBJ + SYN_PRED[be] + SYN_COMPL) since no
    COMP_* operator token exists for "is". arity=2: the entity and the
    asserted kind.
    """
    _require_arity(op, 2)
    return TypeAssertion(entity=op.args[0], kind=op.args[1])


def card_lower(op: Op) -> MinimalSufficiency:
    """COMP_JUST / CARD_LOWER — minimal sufficiency.

    Architecture line 146: "We have just enough mustard for Ben" example.
    v1 simplification: record (threshold, purpose); don't expand to the
    full cartesian-product cardinality form.
    """
    _require_arity(op, 2)
    return MinimalSufficiency(threshold=op.args[0], purpose=op.args[1])


def set_restrict(op: Op) -> SetRestriction:
    """COMP_ONLY / SET_RESTRICT — restrict set to lone member.

    User spec: "Only X [predicate]" → ∀Y: predicate(Y) → Y = X. The
    arity-1 arg is the lone member; the predicate is the surrounding
    sentence context. For v1 we represent the predicate as the Op's
    arg with a note that the surrounding context is implicit.
    """
    _require_arity(op, 1)
    # The arg of ONLY is the lone member (e.g., "Mike" in "Only Mike sings").
    # The predicate ("sings") is in the rest of the sentence — for v1 we
    # carry the arg as both member and predicate-context; a future B5/B3
    # iteration can split these once arg resolution lands.
    return SetRestriction(member=op.args[0], predicate=op.args[0])


def scalar_extreme(op: Op) -> BoundaryCase:
    """COMP_EVEN / SCALAR_EXTREME — v1 inert placeholder.

    Per user decision 2026-05-23: not a 1st-order primitive. Records the
    operation without asserting the scalar-extreme universal. Deferred
    to future hierarchical-network-traversal work.
    """
    _require_arity(op, 1)
    return BoundaryCase(entity=op.args[0], predicate=op.args[0])


def contrast(op: Op) -> Contrast:
    """COMP_BUT / CONTRAST — both X and Y are asserted.

    User spec: "X but Y" asserts both, with Y violating X's expectation.
    v1 carries the contrast tag; doesn't model the pragmatic implicature
    beyond storing it.
    """
    _require_arity(op, 2)
    return Contrast(left=op.args[0], right=op.args[1])


def consequence(op: Op) -> Causation:
    """COMP_SO / CONSEQUENCE — left is cause, right is effect.

    User spec: "X so Y" → cause = X (left), effect = Y (right).
    """
    _require_arity(op, 2)
    return Causation(cause=op.args[0], effect=op.args[1], conjunction="so")


def rel_restrict(op: Op) -> RelativeRestriction:
    """REL_RESTRICT — antecedent entity restricted by a relative clause.

    "The dog that barks" → ``RelativeRestriction(head=dog, restriction=barks)``.
    Synthesized in ``from_trace`` from an embedded relative ClauseSpan; arity=2,
    arg0 = the antecedent entity, arg1 = the relative clause's content.
    """
    _require_arity(op, 2)
    return RelativeRestriction(head=op.args[0], restriction=op.args[1])


def control(op: Op) -> Control:
    """CONTROL — controller entity carries out the inner infinitival clause.

    "Mike wants to leave" → ``Control(controller=Mike, inner=leave)``.
    Synthesized in ``from_trace`` from an embedded control ClauseSpan; arity=2,
    arg0 = the controller entity, arg1 = the inner clause's content.
    """
    _require_arity(op, 2)
    return Control(controller=op.args[0], inner=op.args[1])


def causal_source(op: Op) -> Causation:
    """COMP_BECAUSE / CAUSAL_SOURCE — left is effect, right is cause.

    User spec: "X because Y" → cause = Y (right), effect = X (left).
    Equivalent to CONSEQUENCE with args swapped.
    """
    _require_arity(op, 2)
    return Causation(cause=op.args[1], effect=op.args[0], conjunction="because")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


OPERATION_DISPATCH: Dict[str, Callable[[Op], Predicate]] = {
    "SET_DIFF":       set_diff,
    "BIND_EQ":        bind_eq,
    "DEGREE_QUERY":   degree_query,
    "TYPE_QUERY":     type_query,
    "TYPE_ASSERT":    type_assert,
    "CARD_LOWER":     card_lower,
    "SET_RESTRICT":   set_restrict,
    "SCALAR_EXTREME": scalar_extreme,
    "CONTRAST":       contrast,
    "CONSEQUENCE":    consequence,
    "CAUSAL_SOURCE":  causal_source,
    "REL_RESTRICT":   rel_restrict,
    "CONTROL":        control,
}


def evaluate(op: Op) -> Predicate:
    """Dispatch a single Op to its semantic function."""
    func = OPERATION_DISPATCH.get(op.operation)
    if func is None:
        raise UnknownOperation(
            f"No semantic function for operation {op.operation!r} "
            f"on primitive {op.primitive!r}"
        )
    return func(op)


def evaluate_tree(expr: Operand):
    """Walk an Expression tree, evaluating every Op into a Predicate.

    Returns:
        Either an unchanged leaf (Atom, Phrase, Negation of leaf) or a
        Predicate (for Op nodes). Nested Ops are evaluated recursively:
        each Op's args are evaluated before the Op itself, so the result
        is a tree of Predicates with Expression leaves.
    """
    if isinstance(expr, Op):
        # Recurse into args first so nested Ops become Predicates before
        # the parent dispatch sees them.
        evaluated_args = [evaluate_tree(a) for a in expr.args]
        return evaluate(Op(
            primitive=expr.primitive,
            operation=expr.operation,
            arity=expr.arity,
            args=evaluated_args,
        ))
    if isinstance(expr, Negation):
        inner = evaluate_tree(expr.operand)
        return Negation(operand=inner) if isinstance(inner, (Atom, Phrase, Negation, Op)) else inner
    return expr
