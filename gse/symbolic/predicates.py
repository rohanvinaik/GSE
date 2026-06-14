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

from gse.symbolic.expression import Expression


@dataclass(frozen=True)
class Comparison:
    """X > Y or X < Y on some axis. Produced by COMP_THAN / SET_DIFF.

    ``sign`` is ``+1`` if lhs > rhs, ``-1`` if lhs < rhs.
    """
    lhs: Expression
    rhs: Expression
    sign: int = +1
    axis: Optional[str] = None


@dataclass(frozen=True)
class Equality:
    """X ≈ Y on some axis. Produced by COMP_AS / BIND_EQ.

    Symmetric, non-directional. Asserts equivalence on the implicit axis.
    """
    lhs: Expression
    rhs: Expression
    axis: Optional[str] = None


@dataclass(frozen=True)
class TypeQuery:
    """Query the SUBSTANTIVES-bank decomposition of an entity. COMP_WHAT."""
    entity: Expression


@dataclass(frozen=True)
class DegreeQuery:
    """Query the degree of an entity on the surrounding axis. COMP_HOW.

    Per architecture line 145, HOW is a conditional operation on the
    following independent clause; the axis is read from that clause's
    content.
    """
    entity: Expression
    axis: Optional[str] = None


@dataclass(frozen=True)
class MinimalSufficiency:
    """X has just enough Y. COMP_JUST / CARD_LOWER.

    v1 simplification of the architecture's cartesian-product cardinality
    example. The two args are the threshold thing and the purpose.
    """
    threshold: Expression
    purpose: Expression


@dataclass(frozen=True)
class SetRestriction:
    """∀Y: predicate(Y) → Y = X. COMP_ONLY / SET_RESTRICT.

    The arg of the operator is the lone surviving member (``member``);
    the predicate is the surrounding sentence context (``predicate``).
    """
    member: Expression
    predicate: Expression


@dataclass(frozen=True)
class BoundaryCase:
    """Inert placeholder for COMP_EVEN / SCALAR_EXTREME.

    Per user decision 2026-05-23: EVEN's "scalar extreme + universal over
    more-expected cases" semantics require hierarchical network traversal
    coherence math, not a 1st-order semantic function. v1 records the
    operation without asserting the universal.

    Future work tracked in ``docs/PHASE_B_SCOPE.md``.
    """
    entity: Expression
    predicate: Expression
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
    left: Expression
    right: Expression


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
    cause: Expression
    effect: Expression
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
    entity: Expression
    kind: Expression


# A Predicate is any one of the semantic output types.
Predicate = Union[
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
]
