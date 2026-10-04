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

from gse.symbolic.expression import Negation, Op, Operand
from gse.symbolic.predicates import (
    BoundaryCase,
    Causation,
    ClauseCoordination,
    Comparison,
    Conditional,
    Contrast,
    Control,
    DegreeQuery,
    Equality,
    Event,
    MinimalSufficiency,
    Predicate,
    RelativeRestriction,
    SetRestriction,
    Temporal,
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


def _require_min_arity(op: Op, minimum: int) -> None:
    """Unary operators tolerate an over-grabbed span: they use ``args[0]`` and
    ignore extras (raising only on *zero* args), rather than crashing on the
    bounded-register tail. Surfaced by the L2 parse audit: "even"/"what" in some
    positions attach a second arg (e.g. "Even if all these operations …")."""
    if len(op.args) < minimum:
        raise ValueError(
            f"{op.operation} expects ≥{minimum} arg(s), got {len(op.args)}")


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
    _require_min_arity(op, 1)
    return DegreeQuery(entity=op.args[0])


def type_query(op: Op) -> TypeQuery:
    """COMP_WHAT / TYPE_QUERY — query the SUBSTANTIVES-bank decomposition.

    User spec: "What is X?" returns X's KIND/SOMEONE/SOMETHING/PEOPLE/BODY
    primitive activations from its word_primitives.
    """
    _require_min_arity(op, 1)
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
    _require_min_arity(op, 1)
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
    _require_min_arity(op, 1)
    return BoundaryCase(entity=op.args[0], predicate=op.args[0])


def contrast(op: Op) -> Contrast:
    """COMP_BUT / CONTRAST — both X and Y are asserted.

    User spec: "X but Y" asserts both, with Y violating X's expectation.
    v1 carries the contrast tag; doesn't model the pragmatic implicature
    beyond storing it.
    """
    _require_arity(op, 2)
    return Contrast(left=op.args[0], right=op.args[1])


def clause_coordination(op: Op) -> ClauseCoordination:
    """CLAUSE_COORD — two coordinate clauses, both asserted independently.

    "X verbed Y and Z verbed W" → ``ClauseCoordination(left=X-clause, right=Y-clause)``.
    The coordinate analogue of CONTRAST; clause-level (distinct from the NP-level
    ``resolution.Coordination`` set-union). Folded in ``from_trace`` like the other
    clause-linking operators.
    """
    _require_arity(op, 2)
    return ClauseCoordination(left=op.args[0], right=op.args[1], conjunction="and")


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
    if op.arity >= 3:
        return Control(
            controller=op.args[1], inner=op.args[2],
            verb=op.primitive, subject=op.args[0],
        )
    _require_arity(op, 2)  # degraded fall-back (non-Event matrix)
    return Control(controller=op.args[0], inner=op.args[1])


def event(op: Op) -> Event:
    """EVENT — a verb roleframe over its arguments (the base-case predicate).

    "Duncan rewarded Macbeth" → ``Event(verb="reward", agent=duncan,
    patient=macbeth)``. Synthesized in ``from_trace`` from a plain verb clause;
    the verb lemma rides on ``Op.primitive``, arg0 = subject, arg1 = object (when
    present, else intransitive).
    """
    if not op.args:
        raise ValueError(f"EVENT expects ≥1 arg, got {op.arity}")
    # Args beyond agent+patient are the SECONDARY constituents the role-split peeled off a
    # ditransitive / object+complement (resolution's ArgSplit flattened them in). Preserve
    # them as latent `themes` — the clean primary read (agent, patient) is unchanged; themes
    # ride along, dropped from the default analysis but revivable.
    return Event(
        verb=op.primitive,
        agent=op.args[0],
        patient=op.args[1] if len(op.args) > 1 else None,
        themes=tuple(op.args[2:]) if len(op.args) > 2 else (),
    )


def causal_source(op: Op) -> Causation:
    """COMP_BECAUSE / CAUSAL_SOURCE — left is effect, right is cause.

    User spec: "X because Y" → cause = Y (right), effect = X (left).
    Equivalent to CONSEQUENCE with args swapped.
    """
    _require_arity(op, 2)
    return Causation(cause=op.args[1], effect=op.args[0], conjunction="because")


def conditional(op: Op) -> Conditional:
    """COMP_IF / IMPLIES — antecedent ⇒ consequent.

    Like CAUSAL_SOURCE, the *subordinate* clause (the if-clause) is the arg1/right
    operand in both readings — "Y if X" (medial) and "If X then Y" (fronted, where
    the encoder presents the clauses as ``[consequent, antecedent]``). So the
    if-clause is always the antecedent: antecedent = arg1, consequent = arg0.
    """
    _require_arity(op, 2)
    return Conditional(antecedent=op.args[1], consequent=op.args[0])


def temporal(op: Op) -> Temporal:
    """TEMPORAL — when/while/after/before X, Y → both clauses asserted, temporal link.

    Like CAUSAL_SOURCE / IMPLIES, the *subordinate* (when-)clause is the arg1/right
    operand in both readings — "Y when X" (medial) and "When X, Y" (fronted, where the
    encoder presents the clauses as ``[main, dependent]``). So the when-clause is always
    the setting: setting = arg1, event = arg0.
    """
    _require_arity(op, 2)
    return Temporal(setting=op.args[1], event=op.args[0])


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
    "CLAUSE_COORD":   clause_coordination,
    "CONSEQUENCE":    consequence,
    "CAUSAL_SOURCE":  causal_source,
    "IMPLIES":        conditional,
    "TEMPORAL":       temporal,
    "REL_RESTRICT":   rel_restrict,
    "CONTROL":        control,
    "EVENT":          event,
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
        # Preserve the sign around WHATEVER the operand evaluates to — including a
        # Predicate (a negated event/type-assertion, "X does not harm Y"). The old
        # guard kept the wrapper only around leaves/Ops and dropped it for
        # Predicates, silently losing clausal negation; emit_contract already
        # turns a Negation(Predicate) into {"op": "NOT", ...}.
        return Negation(operand=evaluate_tree(expr.operand))
    return expr
