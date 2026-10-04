"""
Symbolic evaluator over OperationTrace.

Per ``sentence_architecture.md`` line 164: the API for engaging with the
system should be pure Python / order of operations / set theory — not
direct vector math. This package lifts encoder traces into typed ASTs
and applies the set-theory semantics of each compositional operator
symbolically.

Sub-packages:

* :mod:`expression` — the AST (Atom, Phrase, Negation, Op) + builder
  ``from_trace`` that turns an :class:`gse.api.trace.OperationTrace`
  into an :class:`Expression`.
* :mod:`resolution` *(planned, B5)* — multi-word entity grouping and
  within-sentence reference binding.
* :mod:`operators` *(planned, B2)* — pure-Python implementations of
  SET_DIFF, BIND_EQ, etc.
* :mod:`queries` *(planned, B3)* — consumer interface: entities(),
  predicates(), is_logically_equal_to(), etc.
* :mod:`templating` *(planned, B6)* — structural substitution.

See ``docs/PHASE_B_SCOPE.md`` for the live scope.
"""

from gse.symbolic.expression import (
    Atom,
    Expression,
    Negation,
    Op,
    Phrase,
    from_trace,
)
from gse.symbolic.operators import (
    OPERATION_DISPATCH,
    UnknownOperation,
    evaluate,
    evaluate_tree,
)
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
    TypeAssertion,
    TypeQuery,
)
from gse.symbolic.queries import (
    axis_of_comparison,
    clauses,
    entities,
    entity_lemmas,
    is_argument_swap_of,
    is_logically_equal_to,
    predicates,
)
from gse.symbolic.emit import (
    CONTRACT_VERSION,
    emit,
    emit_contract,
    emit_json,
)
from gse.symbolic.genealogy_store import GenealogyStore
from gse.symbolic.inference import Derivation, KnowledgeBase
from gse.symbolic.grounding import (
    GenealogyProvider,
    GroundingFlag,
    NullGenealogy,
    TriageResult,
    grounding_flags,
    resolve_document,
    resolve_references,
    triage_flags,
)
from gse.symbolic.resolution import Coordination, Entity, resolve
from gse.symbolic.serialization import (
    SerializationError,
    from_dict,
    from_json,
    to_dict,
    to_json,
)
from gse.symbolic.templating import substitute

__all__ = [
    # AST
    "Atom", "Expression", "Negation", "Op", "Phrase", "from_trace",
    # Predicates
    "BoundaryCase", "Causation", "ClauseCoordination", "Comparison", "Conditional", "Contrast", "Control",
    "DegreeQuery", "Equality", "Event", "MinimalSufficiency", "Predicate",
    "RelativeRestriction", "SetRestriction", "TypeAssertion", "TypeQuery",
    # Dispatch
    "OPERATION_DISPATCH", "UnknownOperation", "evaluate", "evaluate_tree",
    # Emit contract (Genesis-facing §5 envelope)
    "CONTRACT_VERSION", "emit", "emit_contract", "emit_json",
    # Resolution
    "Coordination", "Entity", "resolve",
    # Reference resolution (entity ids + type threads) + document scope
    "GenealogyProvider", "NullGenealogy", "resolve_references", "resolve_document",
    "GenealogyStore",
    # Abstention signal (grounding confidence flags) + persist triage
    "GroundingFlag", "grounding_flags", "TriageResult", "triage_flags",
    # Logical inference (transitive closure over the clause graph)
    "KnowledgeBase", "Derivation",
    # Queries
    "axis_of_comparison", "clauses", "entities", "entity_lemmas",
    "is_argument_swap_of", "is_logically_equal_to", "predicates",
    # Serialization
    "SerializationError", "from_dict", "from_json", "to_dict", "to_json",
    # Templating
    "substitute",
]
