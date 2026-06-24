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
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Union

from gse.api.trace import ClauseSpan, OperationTrace, OperatorTrace, TokenTrace

if TYPE_CHECKING:
    from gse.symbolic.predicates import Predicate


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
    # Grammatical number ("sing" | "plur" | None) — for a noun, recovered from the
    # surface vs the (singular) lemma, since the lemmatizer drops plurality. Used by
    # document-scope pronoun coreference (they → a plural antecedent). None when unknown.
    number: Optional[str] = None
    # Whether an adjective is comparative/superlative ("fattest" vs "fat"), recovered
    # from surface ≠ lemma. A graded adjective is descriptive, never part of a fixed
    # lexicalized compound — so demi-word promotion skips it ("fattest hen" ≠ the plant
    # "fat hen"). False/None for non-adjectives or the base form.
    graded: bool = False

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
    args: List["Operand"]


# A symbolic Expression is one of the four structural node types above.
Expression = Union[Atom, Phrase, Negation, Op]

# An Operand is anything an operator can take as an argument. At runtime,
# evaluate_tree already feeds evaluated Predicates back in as operands to
# clause-linking operators (a clause-predicate nested in another), so the
# operand type is wider than Expression. "Predicate" is a forward reference
# (predicates.py imports from this module) — kept as a string to avoid the cycle.
Operand = Union[Atom, Phrase, Negation, "Op", "Predicate"]


# ---------------------------------------------------------------------------
# Builder: OperationTrace → Expression
# ---------------------------------------------------------------------------

# Lemmas that mean "negate the following operand" per the architecture's
# treatment of NOT as a sign-direction argument (lines 22-46, 60).
_NEGATION_LEMMAS = frozenset({"not", "no", "never", "neither", "nor", "nothing"})


def _atom_from_token(token: TokenTrace, role: Optional[str] = None) -> Atom:
    """Build a single Atom from a TokenTrace."""
    # Recover grammatical number for nouns: the lemmatizer strips plurality (nobles →
    # noble), but the surface is still on the trace token, so a surface ≠ lemma noun is
    # plural. (Pronoun number is read from a table in the coref binder, not here.)
    number = None
    graded = False
    pos = token.pos or None
    surface = (getattr(token, "token", "") or "")
    if pos in ("NOUN", "PROPN"):
        number = "plur" if surface.lower() != (token.lemma or "").lower() else "sing"
    elif pos == "ADJ":
        # comparative/superlative ("fattest"/"older") → surface differs from base lemma
        graded = surface.lower() != (token.lemma or "").lower()
    return Atom(
        lemma=token.lemma,
        word_primitives=dict(token.word_primitives),
        role=role,
        position=token.position,
        pos=pos,
        number=number,
        graded=graded,
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
# A predicate complement after the copula: a nominal (type membership — "X is a
# king") OR an adjective (property attribution — "X is callous"). Per design
# decision A (2026-06-20, flywheel worklist #2): both are the same "entity ≡ the
# complement's primitive decomposition" binding, so both fold to ONE TypeAssertion
# form. Predicate adjectives previously fell through to a bare-nominal collapse,
# which silently dropped the clause's negation ("X is not callous" → "X callous").
_COMPLEMENT_POS = frozenset({"NOUN", "PROPN", "ADJ"})
# The object of a predicate adjective's PP complement ("loyal to *Corwin*").
_PP_OBJECT_POS = frozenset({"NOUN", "PROPN", "PRON"})


def _try_copula_type_assertion(tokens: Sequence[TokenTrace]) -> Optional[Expression]:
    """Synthesize a TYPE_ASSERT ``Op`` from a copula "X is a Y" / "X is ADJ" clause.

    The encoder tags the subject (SYN_SUBJ), the copula "be" (SYN_PRED), and the
    predicate complement (SYN_COMPL) but emits no COMP_* operator for "is", so no
    predicate would otherwise be produced. When the full pattern is present with a
    nominal OR adjective complement (:data:`_COMPLEMENT_POS`), build
    ``Op("TYPE_ASSERT", args=[subject_span, complement_span])``; resolve() collapses
    each span into an Entity. Only reached when the clause has NO operator (so
    "X is taller than Y" stays a Comparison via COMP_THAN). A predicate adjective is
    the same binding as a predicate nominal — the entity takes on the complement's
    decomposition. Returns ``None`` when the pattern does not hold.
    """
    copula = next(
        (t for t in tokens
         if _COPULA_PREDICATE in t.sent_primitives and t.lemma == _COPULA_LEMMA),
        None,
    )
    if copula is None:
        return None
    # SYN_SUBJ marks the subject in a main clause. In a subordinate clause
    # ("…because Doran is loyal to Maeve") the encoder may tag that subject
    # SYN_OBJ instead, so also accept any entity token before the copula — the
    # same positional subject the spans below already build from. Without this
    # the subordinate copula bails here and collapses to a demi-word nominal.
    has_subject = (
        any(_COPULA_SUBJECT in t.sent_primitives for t in tokens)
        or any(t.position < copula.position and t.pos in _PP_OBJECT_POS
               for t in tokens)
    )
    has_complement = any(
        _COPULA_COMPLEMENT in t.sent_primitives and t.pos in _COMPLEMENT_POS
        for t in tokens
    )
    if not (has_subject and has_complement):
        return None

    # Negated type assertion ("X is not a Y"): drop the marker, wrap in Negation.
    negated = any(t.lemma in _NEGATION_LEMMAS for t in tokens)
    subject_atoms = [
        _atom_from_token(t) for t in tokens
        if t.position < copula.position and t.lemma not in _NEGATION_LEMMAS
    ]
    if not subject_atoms:
        return None

    # Relational predicate adjective — "X is ADJ ADP Y" ("loyal to Y", "angry
    # at Y"). The PP complement makes this a RELATION between X and the PP's
    # object, not the bare property attribution decision A handles: folding
    # "loyal to Corwin" into one kind nominal drops both the preposition and Y,
    # and (as a `because` cause clause) silently defeats rule learning. Build an
    # EVENT keyed on the adjective so ADJ(X, Y) survives with both arguments.
    after = [
        t for t in tokens
        if t.position > copula.position
        and t.lemma not in _NEGATION_LEMMAS and t.pos != "PUNCT"
    ]
    adj_i = next((i for i, t in enumerate(after) if t.pos == "ADJ"), None)
    if adj_i is not None:
        rest = after[adj_i + 1:]
        if rest and rest[0].pos == "ADP":
            pp_object = [t for t in rest[1:] if t.pos in _PP_OBJECT_POS]
            if pp_object:
                event = Op(
                    primitive=after[adj_i].lemma,
                    operation="EVENT",
                    arity=2,
                    args=[
                        Phrase(atoms=subject_atoms),
                        Phrase(atoms=[_atom_from_token(t) for t in pp_object]),
                    ],
                )
                return Negation(operand=event) if negated else event

    complement_atoms = [
        _atom_from_token(t) for t in tokens
        if t.position > copula.position and t.lemma not in _NEGATION_LEMMAS
    ]
    if not complement_atoms:
        return None
    assertion = Op(
        primitive="COPULA",
        operation="TYPE_ASSERT",
        arity=2,
        args=[Phrase(atoms=subject_atoms), Phrase(atoms=complement_atoms)],
    )
    return Negation(operand=assertion) if negated else assertion


def _try_event(tokens: Sequence[TokenTrace],
               shared_subject: Optional[Sequence] = None) -> Optional[Expression]:
    """Synthesize an EVENT ``Op`` from a plain verb clause "X verbs Y".

    The base case the operator set was missing: a clause with an ordinary content
    verb (not the copula "be", not a COMP_* operator token) and no other
    operator. Mirrors :func:`_try_copula_type_assertion` — the verb is detected by
    POS (so it works for sub-clause verbs that aren't the sentence ROOT, e.g. the
    ``became`` of "…because Duncan became happy"); subject = tokens before it,
    object/complement = tokens after. Returns ``None`` when no content verb is
    present, so callers fall through to the default phrase build.

    The verb lemma rides on ``Op.primitive``; ``operators.event`` reads it back.
    """
    verb = next(
        (t for t in tokens
         if t.pos == "VERB" and t.lemma != _COPULA_LEMMA and not t.is_operator),
        None,
    )
    if verb is None:
        return None
    # Clausal negation ("X does not harm Y"): NOT is a sign-direction argument
    # (sentence_architecture.md), so drop the marker from the argument spans and
    # wrap the synthesized EVENT in a Negation — the same node the in-span path
    # (_build_arg_expression) and the emitter already understand.
    negated = any(t.lemma in _NEGATION_LEMMAS for t in tokens)
    _ordered = sorted(tokens, key=lambda t: t.position)

    def _prep_governed(tok) -> bool:
        """Is ``tok`` the object of a preposition? Walk back over its own determiner/adjective
        premodifiers (only — NOT other nominals, so a fronted PP's object is not confused with
        the following subject head); if the governing token is a preposition, ``tok`` is a PP
        oblique. Catches a FRONTED adverbial before the subject ("In the daytime I ran" →
        daytime governed, I not) — the subject-side twin of the post-verb object/oblique split,
        so a fronted PP no longer blobs into the subject ("daytime i"). Text-agnostic."""
        for t in reversed([x for x in _ordered if x.position < tok.position]):
            if t.pos in ("DET", "ADJ"):
                continue
            return t.pos == "ADP"
        return False

    subject_atoms = [_atom_from_token(t) for t in tokens
                     if t.position < verb.position
                     and t.pos != "PUNCT" and t.lemma not in _NEGATION_LEMMAS
                     and not _prep_governed(t)]
    fronted_obliques = [_atom_from_token(t, "SYN_OBL") for t in tokens
                        if t.position < verb.position and t.pos != "PUNCT"
                        and t.lemma not in _NEGATION_LEMMAS and _prep_governed(t)]
    # Direct object vs PP obliques. The clause's direct object is the post-verb nominal
    # span UP TO the first preposition; tokens from the first preposition on are PP
    # obliques ("for months", "with this result", "to Macbeth"). Without this split the
    # object accretes every trailing PP nominal into one blobbed entity (the demi-word
    # span — "penny she month this result"). The obliques are RESOLVED as a typed
    # SYN_OBL constituent rather than merged or discarded; the narrative spine's
    # set-operation keeps them off the protagonist backbone. (Text-agnostic: the boundary
    # is the preposition POS, not any story-specific word.)
    post_verb = [t for t in tokens
                 if t.position > verb.position
                 and t.pos != "PUNCT" and t.lemma not in _NEGATION_LEMMAS]
    first_prep = next((idx for idx, t in enumerate(post_verb) if t.pos == "ADP"), None)
    obj_tokens = post_verb if first_prep is None else post_verb[:first_prep]
    obl_tokens = [] if first_prep is None else post_verb[first_prep:]
    object_atoms = [_atom_from_token(t) for t in obj_tokens]
    oblique_atoms = fronted_obliques + [_atom_from_token(t, "SYN_OBL") for t in obl_tokens]
    if not subject_atoms:
        # VP-coordination with an elided shared subject ("Bertran [betrayed Aldric] and
        # [murdered him]") — inherit the prior conjunct's subject so the 2nd event survives
        # instead of collapsing to its bare object. Only fires when the clause has no subject.
        if not shared_subject:
            return None
        subject_atoms = list(shared_subject)
    args: List[Operand] = [Phrase(atoms=subject_atoms)]
    if object_atoms:
        args.append(Phrase(atoms=object_atoms))
        # Carry obliques only BEHIND a real object, so a bare PP after an intransitive
        # ("stood by the window") never slides into the patient slot (args[1]).
        if oblique_atoms:
            args.append(Phrase(atoms=oblique_atoms))
    event = Op(primitive=verb.lemma, operation="EVENT", arity=len(args), args=args)
    return Negation(operand=event) if negated else event


def _build_operator_op(
    op: OperatorTrace,
    tokens: Sequence[TokenTrace],
    operator_positions: Sequence[int],
) -> Op:
    """Build one ``Op`` node from an OperatorTrace, args from its token spans."""
    args: List[Operand] = []
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


def _left_fold_operators(
    built_ops: Sequence[Op],
) -> Expression:
    """Nest operators left-to-right: leftmost becomes arg1 of the next.

    Reflects the state-based left-to-right order of operations from
    ``sentence_architecture.md`` line 35. Used *within* a single clause, where
    surface order is the right nesting; cross-clause nesting is handled by tier
    in :func:`from_trace`, not here.
    """
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


def _build_clause_expr(
    clause: ClauseSpan,
    tokens: Sequence[TokenTrace],
    operators: Sequence[OperatorTrace],
    operator_positions: Sequence[int],
    excluded: Optional[set] = None,
    drop_relativizers: bool = False,
    shared_subject: Optional[Sequence] = None,
) -> Expression:
    """Build the Expression for one clause span.

    A clause resolves through the *existing* single-clause logic: its
    within-clause operators (if any) are built and left-folded; otherwise the
    clause's content tokens fold into a copula TYPE_ASSERT or a Phrase / Atom.

    ``excluded`` token positions are dropped (an embedded child clause's tokens
    are excluded from the parent). ``drop_relativizers`` strips a leading
    who/which/that pronoun — used when building a relative clause's restriction.
    """
    excluded = excluded or set()
    clause_tokens = [
        t for t in tokens
        if clause.token_start <= t.position < clause.token_end
        and t.position not in excluded
        and not (drop_relativizers and _is_relativizer(t))
    ]
    clause_ops = [operators[i] for i in clause.operator_indices]

    if not clause_ops:
        copula_op = _try_copula_type_assertion(clause_tokens)
        if copula_op is not None:
            return copula_op
        event_op = _try_event(clause_tokens, shared_subject=shared_subject)
        if event_op is not None:
            return event_op
        atoms = [_atom_from_token(t) for t in clause_tokens]
        if not atoms:
            return Phrase(atoms=[])
        if len(atoms) == 1:
            return atoms[0]
        return Phrase(atoms=atoms)

    built = [_build_operator_op(op, tokens, operator_positions) for op in clause_ops]
    if len(built) == 1:
        return built[0]
    return _left_fold_operators(built)


# Relativizer pronouns introducing a relative clause (dropped from the
# restriction, which is asserted of the antecedent, not of the relativizer).
_RELATIVIZER_LEMMAS = frozenset({"that", "who", "whom", "which", "whose"})


def _is_relativizer(token: TokenTrace) -> bool:
    return token.pos == "PRON" and token.lemma in _RELATIVIZER_LEMMAS


def _wrap_antecedent(
    expr: Expression, position: int, restriction: Operand,
    operation: str = "REL_RESTRICT", primitive: str = "REL",
) -> "tuple[Expression, bool]":
    """Wrap the node containing ``position`` in an embedding operator.

    Finds the Atom or Phrase that contains the antecedent / controller token and
    replaces it with ``Op(operation, [<that node>, restriction])``, so the
    embedded clause composes with whatever main-clause operator the node is also
    an argument of. Used for both REL_RESTRICT (relative clauses) and CONTROL
    ('to' complements). Returns ``(new_expr, wrapped)``; only the first match
    wraps.
    """
    def _rel_op(node: Operand) -> Op:
        return Op(primitive=primitive, operation=operation, arity=2,
                  args=[node, restriction])

    if isinstance(expr, Atom):
        if expr.position == position:
            return _rel_op(expr), True
        return expr, False
    if isinstance(expr, Phrase):
        if any(a.position == position for a in expr.atoms):
            return _rel_op(expr), True
        return expr, False
    if isinstance(expr, Op):
        new_args: List[Operand] = []
        wrapped = False
        for a in expr.args:
            if not wrapped and isinstance(a, (Atom, Phrase, Negation, Op)):
                na, w = _wrap_antecedent(
                    a, position, restriction, operation, primitive
                )
                new_args.append(na)
                wrapped = wrapped or w
            else:
                new_args.append(a)
        return Op(primitive=expr.primitive, operation=expr.operation,
                  arity=expr.arity, args=new_args), wrapped
    if isinstance(expr, Negation):
        inner, w = _wrap_antecedent(
            expr.operand, position, restriction, operation, primitive
        )
        return Negation(operand=inner), w
    return expr, False


def _is_all_punct(node: Operand) -> bool:
    """True for a Phrase/Atom made only of punctuation. A trailing '.' parses as
    an object/arg and must not be read as a real participant (controller, patient)."""
    if isinstance(node, Atom):
        return not any(c.isalnum() for c in node.lemma)
    if isinstance(node, Phrase):
        return bool(node.atoms) and all(_is_all_punct(a) for a in node.atoms)
    return False


def _build_control(
    matrix: Expression,
    emb: ClauseSpan,
    tokens: Sequence[TokenTrace],
    operators: Sequence[OperatorTrace],
    operator_positions: Sequence[int],
) -> Expression:
    """Lift a control construction into ``CONTROL(verb, subject, controller, inner)``.

    The matrix clause (xcomp excluded) was already built — for object/subject
    control it is an ``EVENT`` Op, e.g. ``EVENT(persuade; LadyMacbeth, Macbeth)``.
    We read the matrix verb + subject + controller off it, build the inner
    infinitival as an Event **whose agent is the controller** (the "to" dropped),
    and assemble a single CONTROL Op ``[subject, controller, inner]`` (verb on
    ``primitive``). When the matrix isn't a clean Event, fall back to the
    in-place wrap (degraded — controller + inner only).
    """
    inner_tokens = [
        t for t in tokens
        if emb.token_start <= t.position < emb.token_end
        and not (t.pos == "PART" and t.lemma == "to")
    ]
    inner_verb = next(
        (t for t in inner_tokens if t.pos == "VERB" and not t.is_operator), None
    )
    if inner_verb is None or not (isinstance(matrix, Op) and matrix.operation == "EVENT"):
        inner_expr = _build_clause_expr(emb, tokens, operators, operator_positions)
        return _wrap_antecedent(
            matrix, emb.attaches_to_token, inner_expr,
            operation="CONTROL", primitive="CTRL",
        )[0]

    # Drop a punctuation-only arg the matrix picked up (trailing '.'), so the
    # controller is the real object (object control) or the subject (subject
    # control), not the period.
    clean_args = [a for a in matrix.args if not _is_all_punct(a)] or list(matrix.args)
    subject = clean_args[0]
    controller = clean_args[1] if len(clean_args) > 1 else clean_args[0]
    inner_obj = [
        _atom_from_token(t) for t in inner_tokens if t.position > inner_verb.position
    ]
    inner_args: List[Operand] = [controller]
    if inner_obj:
        inner_args.append(Phrase(atoms=inner_obj))
    inner_event = Op(
        primitive=inner_verb.lemma, operation="EVENT",
        arity=len(inner_args), args=inner_args,
    )
    return Op(
        primitive=matrix.primitive, operation="CONTROL", arity=3,
        args=[subject, controller, inner_event],
    )


def _build_complement(
    matrix: Expression,
    emb: ClauseSpan,
    tokens: Sequence[TokenTrace],
    operators: Sequence[OperatorTrace],
    operator_positions: Sequence[int],
) -> Expression:
    """Inject a clausal complement as the reporting verb's patient.

    "The witches predicted that Macbeth would become king" → the matrix
    EVENT(predict; witches) gains the complement proposition EVENT(become;
    Macbeth, king) as its patient. The complement carries its own subject, so it
    builds as a normal event once the 'that' mark and modal auxiliaries are
    dropped (the copula "be" is kept). Falls back to the matrix unchanged when it
    isn't a clean EVENT (e.g. an already-nested matrix), losing nothing vs today.
    """
    content = [
        t for t in tokens
        if emb.token_start <= t.position < emb.token_end
        and not (t.pos == "SCONJ" and t.lemma == "that")
        and not (t.pos == "AUX" and t.lemma != _COPULA_LEMMA)
    ]
    inner = _try_copula_type_assertion(content) or _try_event(content)
    if inner is None:
        inner = _build_clause_expr(emb, tokens, operators, operator_positions)
    if isinstance(matrix, Op) and matrix.operation == "EVENT":
        # Drop a punctuation-only arg the matrix may have picked up (the trailing
        # "." parses as an object), so the complement is the clean patient.
        base_args = [a for a in matrix.args if not _is_all_punct(a)]
        return Op(
            primitive=matrix.primitive, operation="EVENT",
            arity=len(base_args) + 1, args=base_args + [inner],
        )
    return matrix


def _build_relative_restriction(
    emb: ClauseSpan,
    tokens: Sequence[TokenTrace],
    operators: Sequence[OperatorTrace],
    operator_positions: Sequence[int],
) -> Expression:
    """Build a relative clause's restriction with the antecedent bound into the
    relativizer's gap (``emb.gap_role``, from the encoder).

    "Macbeth who trusted the witches" → EVENT(trust; Macbeth, witches) [subject
    gap]; "the king whom Macbeth murdered" → EVENT(murder; Macbeth, king) [object
    gap]. Falls back to the plain build when the gap role is unknown or the clause
    has no content verb (e.g. the copular relative "who was the king", already
    handled correctly by the default path).
    """
    inner_tokens = [
        t for t in tokens
        if emb.token_start <= t.position < emb.token_end and not _is_relativizer(t)
    ]
    verb = next(
        (t for t in inner_tokens
         if t.pos == "VERB" and t.lemma != _COPULA_LEMMA and not t.is_operator),
        None,
    )
    if (verb is None or emb.gap_role not in ("subject", "object")
            or emb.attaches_to_token is None):
        return _build_clause_expr(
            emb, tokens, operators, operator_positions, drop_relativizers=True
        )

    antecedent = _atom_from_token(tokens[emb.attaches_to_token])
    before = [_atom_from_token(t) for t in inner_tokens if t.position < verb.position]
    after = [_atom_from_token(t) for t in inner_tokens if t.position > verb.position]
    if emb.gap_role == "object":
        agent_atoms, patient_atoms = before, [antecedent]
    else:  # subject gap — antecedent is the agent
        agent_atoms, patient_atoms = [antecedent], after

    if not agent_atoms:
        return _build_clause_expr(
            emb, tokens, operators, operator_positions, drop_relativizers=True
        )
    args: List[Operand] = [Phrase(atoms=agent_atoms)]
    if patient_atoms:
        args.append(Phrase(atoms=patient_atoms))
    return Op(primitive=verb.lemma, operation="EVENT", arity=len(args), args=args)


def from_trace(trace: OperationTrace) -> Expression:
    """Build a symbolic Expression from an OperationTrace.

    Single-clause (``trace.clauses`` empty):

    * No operators → content atoms as a Phrase (or a single Atom), with a
      copula "X is a Y" synthesized into a TYPE_ASSERT.
    * One operator → that ``Op`` with args from ``arg{1,2}_tokens``.
    * Multiple operators → left-folded by position.

    Multi-clause (``trace.clauses`` populated): each clause span is resolved by
    the single-clause logic above, then the **clause-linking** operators
    (CONSEQUENCE, CAUSAL_SOURCE, …) are folded over the clause results in
    surface order. This is what gives correct nesting — e.g. "Rex barks because
    the dog is cuter than the cat" builds ``CAUSAL_SOURCE(rex-barks,
    SET_DIFF(dog, cat))`` rather than the positional inversion. See
    ``docs/COMPLEX_SENTENCE_DESIGN.md`` §0.
    """
    tokens = trace.tokens
    operators = sorted(trace.operators, key=lambda o: o.position)
    operator_positions = [op.position for op in operators]

    if trace.clauses:
        return _from_trace_segmented(trace, tokens, operator_positions)

    if not operators:
        # No COMP_* operator, but a copula "X is a Y" carries a synthesized
        # TYPE_ASSERT from the encoder's syntactic-role tags.
        copula_op = _try_copula_type_assertion(tokens)
        if copula_op is not None:
            return copula_op
        event_op = _try_event(tokens)
        if event_op is not None:
            return event_op
        # No operators — fold every content token into a Phrase / Atom.
        content_atoms = [_atom_from_token(t) for t in tokens]
        if len(content_atoms) == 1:
            return content_atoms[0]
        return Phrase(atoms=content_atoms)

    built_ops = [
        _build_operator_op(op, tokens, operator_positions) for op in operators
    ]
    if len(built_ops) == 1:
        return built_ops[0]
    return _left_fold_operators(built_ops)


def _event_subject_atoms(expr: Expression) -> Optional[Sequence]:
    """The subject atoms of a built EVENT clause — for VP-coordination subject sharing."""
    node = expr.operand if isinstance(expr, Negation) else expr
    if isinstance(node, Op) and node.operation == "EVENT" and node.args:
        first = node.args[0]
        if isinstance(first, Phrase):
            return list(first.atoms)
        if isinstance(first, Atom):
            return [first]
    return None


def _from_trace_segmented(
    trace: OperationTrace,
    tokens: Sequence[TokenTrace],
    operator_positions: Sequence[int],
) -> Expression:
    """Tier-aware build for a segmented (multi-clause) trace.

    Each clause span is resolved independently; clause-linking operators (those
    not owned by any clause span) are folded over the clause results in surface
    order. ``trace.operators`` is indexed positionally to match the indices
    stored in each ``ClauseSpan.operator_indices``.
    """
    operators = trace.operators
    all_clauses = sorted(trace.clauses, key=lambda c: c.clause_id)
    sequential = [c for c in all_clauses if c.kind == "sequential"]
    embedded = [c for c in all_clauses if c.kind != "sequential"]

    # Tokens owned by embedded clauses are excluded from their parent's build.
    embedded_tokens = set()
    for emb in embedded:
        embedded_tokens.update(range(emb.token_start, emb.token_end))

    # Build sequential clauses in surface order, carrying the subject forward: a
    # subject-less coordinated clause ("…and murdered him") inherits the prior conjunct's
    # subject (VP-coordination), so its event survives instead of collapsing to its object.
    clause_exprs = []
    shared_subject = None
    for c in sequential:
        cx = _build_clause_expr(
            c, tokens, operators, operator_positions, excluded=embedded_tokens,
            shared_subject=shared_subject,
        )
        clause_exprs.append(cx)
        subj = _event_subject_atoms(cx)
        if subj:
            shared_subject = subj

    owned = {i for c in all_clauses for i in c.operator_indices}
    linking_ops = sorted(
        (op for i, op in enumerate(operators) if i not in owned),
        key=lambda o: o.position,
    )

    # Fold clause-linking operators over the sequential clause expressions in
    # surface order: c0 [op0] c1 [op1] c2 …
    expr: Expression = clause_exprs[0]
    for k, op in enumerate(linking_ops):
        right: Operand = (
            clause_exprs[k + 1] if k + 1 < len(clause_exprs) else Phrase(atoms=[])
        )
        expr = Op(
            primitive=op.primitive,
            operation=op.operation,
            arity=op.arity,
            args=[expr, right],
        )

    # Attach each embedded clause to its antecedent / controller in-place.
    for emb in embedded:
        if emb.attaches_to_token is None:
            continue
        if emb.kind == "relative":
            inner = _build_relative_restriction(
                emb, tokens, operators, operator_positions
            )
            expr, _ = _wrap_antecedent(expr, emb.attaches_to_token, inner)
        elif emb.kind == "control":
            expr = _build_control(expr, emb, tokens, operators, operator_positions)
        elif emb.kind == "complement":
            expr = _build_complement(expr, emb, tokens, operators, operator_positions)

    return expr
