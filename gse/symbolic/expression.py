"""
Symbolic Expression AST for the Phase B evaluator.

Lifts an :class:`gse.api.trace.OperationTrace` into a typed tree of:

* :class:`Atom` — one token resolved to its lemma + word_primitives + role.
* :class:`Phrase` — an unresolved span of multiple tokens. B5 (argument
  resolution) is what collapses Phrases into single Atoms with grouped
  entities; for B1 we keep the span explicit so resolution can refine.
* :class:`Negation` — explicit ``-1`` direction per ``sentence_architecture.md``
  lines 27, 60. "Did not run" → ``Negation(Atom(run))``.
* :class:`Op` — a compositional operator with operation label and args.
  "Mike is taller than Rex" → ``Op("SET_DIFF", arity=2, args=[lhs, rhs])``.

This module is **pure structural transformation** — no semantics yet.
SET_DIFF doesn't *do* anything here; it's a label that downstream B2/B3
will dispatch on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Union

from gse.api.trace import OperationTrace, OperatorTrace, TokenTrace


@dataclass(frozen=True)
class Atom:
    """A single token with its resolved primitive content.

    Args:
        lemma: spaCy-lemmatized form (``ran`` → ``run``).
        word_primitives: token's word-scale primitive activations.
        role: optional grammatical role string (e.g., ``subject``).
        position: token index in the original sentence.
        pos: spaCy part-of-speech tag (e.g., ``PROPN``, ``NOUN``, ``PRON``,
            ``VERB``). Used by Phase B5 argument resolution to distinguish
            entity tokens from predicate tokens; defaults to ``None`` for
            atoms not built from a TokenTrace.
    """
    lemma: str
    word_primitives: Dict[str, int] = field(default_factory=dict)
    role: Optional[str] = None
    position: int = 0
    pos: Optional[str] = None

    def __hash__(self) -> int:
        # word_primitives is unhashable; hash on lemma+position
        return hash((self.lemma, self.position, self.role))


@dataclass(frozen=True)
class Phrase:
    """An unresolved span — a list of Atoms B5 will collapse into entities.

    For "Mike's dog", this is a Phrase of two Atoms ("mike", "dog") that
    B5 will refine into an Atom representing the composite entity.
    """
    atoms: List[Atom]

    def __hash__(self) -> int:
        return hash(tuple(a.lemma for a in self.atoms))


@dataclass(frozen=True)
class Negation:
    """An operand with a ``-1`` sign direction.

    Per ``sentence_architecture.md`` line 27, NOT is a directional
    argument, not an operator: ``Negation`` carries the sign so
    downstream queries see the operand and the flipped polarity.
    """
    operand: "Expression"


@dataclass(frozen=True)
class Op:
    """A compositional operator from the trace, lifted into the AST.

    Args:
        primitive: the COMP_* name (e.g., ``COMP_THAN``).
        operation: the operation label from COMP_METADATA (e.g.,
            ``SET_DIFF``). This is what B2 dispatches on.
        arity: 1 or 2 — number of arguments the operator consumes.
        args: the lifted argument expressions.
    """
    primitive: str
    operation: str
    arity: int
    args: List["Expression"]


# A symbolic Expression is one of the four node types above. Recursive.
Expression = Union[Atom, Phrase, Negation, Op]


# ---------------------------------------------------------------------------
# Builder: OperationTrace → Expression
# ---------------------------------------------------------------------------

# Lemmas that mean "negate the following operand" per the architecture's
# treatment of NOT as a sign-direction argument (lines 22-46, 60).
_NEGATION_LEMMAS = frozenset({"not", "no", "never", "neither", "nor", "nothing"})


def _atom_from_token(token: TokenTrace, role: Optional[str] = None) -> Atom:
    """Build a single Atom from a TokenTrace."""
    return Atom(
        lemma=token.lemma,
        word_primitives=dict(token.word_primitives),
        role=role,
        position=token.position,
        pos=token.pos or None,
    )


def _build_arg_expression(
    token_positions: Sequence[int],
    tokens: Sequence[TokenTrace],
    operator_positions: Sequence[int],
) -> Expression:
    """Build the Expression for one argument span.

    Strategy:
    * Skip token positions that are themselves operator positions
      (operators are wrapped at the parent level, not embedded as args).
    * If the remaining span has a NOT-like token followed by content,
      wrap the content in Negation.
    * If the span has exactly one content token, return its Atom.
    * Otherwise return a Phrase to be refined by B5 (argument resolution).
    """
    operator_set = set(operator_positions)
    filtered = [
        tokens[p] for p in token_positions
        if p < len(tokens) and p not in operator_set
    ]
    if not filtered:
        # No content tokens — return an empty phrase as a placeholder.
        return Phrase(atoms=[])

    # Look for negation: leading NOT-like token wraps the rest.
    negate = False
    body_tokens: List[TokenTrace] = []
    for tok in filtered:
        if not body_tokens and tok.lemma in _NEGATION_LEMMAS:
            negate = True
            continue
        body_tokens.append(tok)

    if not body_tokens:
        # The span was just a negation marker — produce a Phrase of the
        # negation atom alone; B5 may rebind it.
        result: Expression = Phrase(atoms=[_atom_from_token(filtered[0])])
    elif len(body_tokens) == 1:
        result = _atom_from_token(body_tokens[0])
    else:
        result = Phrase(atoms=[_atom_from_token(t) for t in body_tokens])

    if negate:
        result = Negation(operand=result)
    return result


# Encoder syntactic-role primitives that mark the copula type-assertion
# pattern "X is a Y". No COMP_* operator is emitted for the copula "be",
# so the type assertion is synthesized here from these role tags.
_COPULA_SUBJECT = "SYN_SUBJ"
_COPULA_PREDICATE = "SYN_PRED"
_COPULA_COMPLEMENT = "SYN_COMPL"
_COPULA_LEMMA = "be"
_NOMINAL_POS = frozenset({"NOUN", "PROPN"})


def _try_copula_type_assertion(tokens: Sequence[TokenTrace]) -> Optional[Op]:
    """Synthesize a TYPE_ASSERT ``Op`` from a copula "X is a Y" sentence.

    The encoder tags the subject (SYN_SUBJ), the copula "be" (SYN_PRED),
    and the predicate-nominal complement (SYN_COMPL) but emits no COMP_*
    operator for "is", so no predicate would otherwise be produced. When
    the full pattern is present with a *nominal* complement — not an
    adjective, since "X is cute" is a property, not a type — build
    ``Op("TYPE_ASSERT", args=[subject_span, complement_span])``; resolve()
    collapses each span into an Entity. Returns ``None`` when the pattern
    does not hold, so callers fall through to the default phrase build.
    """
    copula = next(
        (t for t in tokens
         if _COPULA_PREDICATE in t.sent_primitives and t.lemma == _COPULA_LEMMA),
        None,
    )
    if copula is None:
        return None
    has_subject = any(_COPULA_SUBJECT in t.sent_primitives for t in tokens)
    has_nominal_complement = any(
        _COPULA_COMPLEMENT in t.sent_primitives and t.pos in _NOMINAL_POS
        for t in tokens
    )
    if not (has_subject and has_nominal_complement):
        return None

    subject_atoms = [
        _atom_from_token(t) for t in tokens if t.position < copula.position
    ]
    complement_atoms = [
        _atom_from_token(t) for t in tokens if t.position > copula.position
    ]
    if not subject_atoms or not complement_atoms:
        return None
    return Op(
        primitive="COPULA",
        operation="TYPE_ASSERT",
        arity=2,
        args=[Phrase(atoms=subject_atoms), Phrase(atoms=complement_atoms)],
    )


def from_trace(trace: OperationTrace) -> Expression:
    """Build a symbolic Expression from an OperationTrace.

    The top-level Expression is:

    * If there are no compositional operators, the sentence's content
      atoms as a Phrase (or a single Atom for one-word inputs).
    * If there's exactly one operator, that ``Op`` node with its
      arguments built from ``arg{1,2}_tokens``.
    * If there are multiple operators, they are nested left-to-right by
      position: the leftmost becomes the innermost args of the next one
      (a conservative left-fold reflecting that operators "look back"
      for their left arg per architecture line 35).
    """
    tokens = trace.tokens
    operators = sorted(trace.operators, key=lambda o: o.position)

    if not operators:
        # No COMP_* operator, but a copula "X is a Y" carries a synthesized
        # TYPE_ASSERT from the encoder's syntactic-role tags.
        copula_op = _try_copula_type_assertion(tokens)
        if copula_op is not None:
            return copula_op
        # No operators — fold every content token into a Phrase / Atom.
        content_atoms = [_atom_from_token(t) for t in tokens]
        if len(content_atoms) == 1:
            return content_atoms[0]
        return Phrase(atoms=content_atoms)

    operator_positions = [op.position for op in operators]

    def _build_one_operator(op: OperatorTrace) -> Op:
        args: List[Expression] = []
        if op.arity >= 1:
            args.append(_build_arg_expression(
                op.arg1_tokens, tokens, operator_positions
            ))
        if op.arity >= 2:
            args.append(_build_arg_expression(
                op.arg2_tokens, tokens, operator_positions
            ))
        return Op(
            primitive=op.primitive,
            operation=op.operation,
            arity=op.arity,
            args=args,
        )

    built_ops = [_build_one_operator(op) for op in operators]
    if len(built_ops) == 1:
        return built_ops[0]

    # Multiple operators: left-fold conservative nesting. The leftmost
    # operator becomes arg1 of the next-leftmost, etc. Reflects the
    # state-based left-to-right order of operations from line 35.
    expr: Expression = built_ops[0]
    for next_op in built_ops[1:]:
        new_args = list(next_op.args)
        if new_args:
            new_args[0] = expr
        expr = Op(
            primitive=next_op.primitive,
            operation=next_op.operation,
            arity=next_op.arity,
            args=new_args,
        )
    return expr
