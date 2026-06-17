"""
Semantic Predicate types produced by Phase B2 operator evaluation.

Each operator function in :mod:`gse.symbolic.operators` consumes an
:class:`gse.symbolic.expression.Op` node and produces one of the types
below. These represent **what was asserted symbolically** — they don't
evaluate truth against any knowledge base (that's a downstream concern
out of scope per ``docs/PHASE_B_SCOPE.md``).

Axes are stored as ``Optional[str]`` and intentionally not extracted in
B2; the Expression arg carries the content. B3's query interface is
where ``axis_of_comparison()`` and similar extractors live.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from gse.symbolic.expression import Operand


@dataclass(frozen=True)
class Comparison:
    """X > Y or X < Y on some axis. Produced by COMP_THAN / SET_DIFF.

    ``sign`` is ``+1`` if lhs > rhs, ``-1`` if lhs < rhs.
    """
    lhs: Operand
    rhs: Operand
    sign: int = +1
    axis: Optional[str] = None


@dataclass(frozen=True)
class Equality:
    """X ≈ Y on some axis. Produced by COMP_AS / BIND_EQ.

    Symmetric, non-directional. Asserts equivalence on the implicit axis.
    """
    lhs: Operand
    rhs: Operand
    axis: Optional[str] = None


@dataclass(frozen=True)
class TypeQuery:
    """Query the SUBSTANTIVES-bank decomposition of an entity. COMP_WHAT."""
    entity: Operand


@dataclass(frozen=True)
class DegreeQuery:
    """Query the degree of an entity on the surrounding axis. COMP_HOW.

    Per architecture line 145, HOW is a conditional operation on the
    following independent clause; the axis is read from that clause's
    content.
    """
    entity: Operand
    axis: Optional[str] = None


@dataclass(frozen=True)
class MinimalSufficiency:
    """X has just enough Y. COMP_JUST / CARD_LOWER.

    v1 simplification of the architecture's cartesian-product cardinality
    example. The two args are the threshold thing and the purpose.
    """
    threshold: Operand
    purpose: Operand


@dataclass(frozen=True)
class SetRestriction:
    """∀Y: predicate(Y) → Y = X. COMP_ONLY / SET_RESTRICT.

    The arg of the operator is the lone surviving member (``member``);
    the predicate is the surrounding sentence context (``predicate``).
    """
    member: Operand
    predicate: Operand


@dataclass(frozen=True)
class BoundaryCase:
    """Inert placeholder for COMP_EVEN / SCALAR_EXTREME.

    Per user decision 2026-05-23: EVEN's "scalar extreme + universal over
    more-expected cases" semantics require hierarchical network traversal
    coherence math, not a 1st-order semantic function. v1 records the
    operation without asserting the universal.

    Future work tracked in ``docs/PHASE_B_SCOPE.md``.
    """
    entity: Operand
    predicate: Operand
    note: str = (
        "SCALAR_EXTREME / EVEN deferred — needs hierarchical network "
        "traversal coherence math; v1 records operation only."
    )


@dataclass(frozen=True)
class Contrast:
    """Both X and Y are asserted; Y violates X's expectation. COMP_BUT.

    v1 records the contrast metadata but doesn't model the pragmatic
    expectation-violation beyond the tag (per user note about not
    building for Yoda).
    """
    left: Operand
    right: Operand


@dataclass(frozen=True)
class Causation:
    """Cause → effect. Produced by COMP_SO and COMP_BECAUSE.

    The two share semantics but differ in directional reading:

    * ``conjunction == "so"``: ``cause`` is the left operand, ``effect``
      the right.
    * ``conjunction == "because"``: ``cause`` is the right operand,
      ``effect`` the left.

    The operator functions handle the inversion so the ``cause`` /
    ``effect`` fields always carry the semantically-correct directional
    content.
    """
    cause: Operand
    effect: Operand
    conjunction: str = "so"


@dataclass(frozen=True)
class TypeAssertion:
    """Entity asserted to be of a kind. Produced by the copula "X is a Y".

    The assertion counterpart to :class:`TypeQuery` ("What is X?"): a
    declarative "Spot is a dog" → ``TypeAssertion(entity=Spot, kind=dog)``.
    Grounded in the NSM ``KIND`` prime — "X is one kind of Y". The
    copula is recognized structurally from the encoder's syntactic-role
    primitives (SYN_SUBJ + SYN_PRED[be] + SYN_COMPL); no operator token is
    emitted for "is", so the synthesis happens in ``from_trace``.

    Args:
        entity: the subject being typed (e.g., ``Spot``, ``I``).
        kind: the asserted type/class (e.g., ``dog``, ``person``).
    """
    entity: Operand
    kind: Operand


@dataclass(frozen=True)
class RelativeRestriction:
    """An entity restricted by an embedded relative clause. REL_RESTRICT.

    "The dog that barks" → ``RelativeRestriction(head=Entity(dog),
    restriction=<barks>)``: the antecedent entity annotated with the predicate
    that the relative clause asserts of it. The relativizer (that/who/which) is
    dropped in ``from_trace``; the restriction is the relative clause's content,
    which may itself be a nested predicate ("the dog that is cuter than the
    cat"). The node wraps the antecedent *in place*, so it composes with any
    main-clause operator the antecedent also participates in.

    Args:
        head: the antecedent entity being restricted.
        restriction: the relative clause's asserted content over that entity.
    """
    head: Operand
    restriction: Operand


@dataclass(frozen=True)
class Control:
    """A control/raising construction — the controller performs the inner act.

    "Mike wants to leave" → ``Control(controller=Mike, inner=leave)`` (subject
    control). "Lady Macbeth persuaded Macbeth to kill the king" →
    ``Control(controller=Macbeth, inner=<kill the king>)`` (object control). The
    inner clause is the ``to``-complement; the infinitival "to" is a function
    word and drops out in resolution. v1 binds the controller by the
    object-else-subject heuristic; the matrix verb itself is not retained.

    Args:
        controller: the entity that carries out the inner action.
        inner: the embedded (infinitival) clause's content.
    """
    controller: Operand
    inner: Operand


@dataclass(frozen=True)
class Event:
    """A verb roleframe — the base-case predicate for a plain clause.

    "Duncan rewarded Macbeth" → ``Event(verb="reward", agent=duncan,
    patient=macbeth)``; "Rex barks" → ``Event(verb="bark", agent=rex)``. This is
    the predicate the operator set was missing: a clause with an ordinary
    transitive/intransitive verb and no comparison/type/causation operator. It
    maps 1:1 to Genesis's ``makeRoleFrame(subject, verb, object)`` — and, crucially,
    it is what lets a *sub*-clause survive as structure instead of collapsing to
    its salient entity (the cause/effect of a Causation, the inner act of a
    Control are Events, not bare nouns).

    Args:
        verb: the clause's verb lemma (the relation).
        agent: the subject filler.
        patient: the object/complement filler, or ``None`` for an intransitive.
    """
    verb: str
    agent: Operand
    patient: Optional[Operand] = None


# A Predicate is any one of the semantic output types.
Predicate = Union[
    Event,
    Comparison,
    Equality,
    TypeQuery,
    TypeAssertion,
    DegreeQuery,
    MinimalSufficiency,
    SetRestriction,
    BoundaryCase,
    Contrast,
    Causation,
    RelativeRestriction,
    Control,
]
