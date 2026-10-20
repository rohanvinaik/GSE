"""Atomic claim decisions shared by readers and consumers.

These functions consume the existing proposition extraction; they do not parse
prose. A comparison key certifies only its explicitly named projection. In
particular, an unresolved surface lemma never certifies referent identity.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping

CLAIM_KEY_VERSION = "gse.claim/1"
_TRANSPARENT = frozenset({"asserted", "epistemic", "negated"})
_ATTITUDES = frozenset({"epistemic", "belief"})
_GENERIC_PRIMES = frozenset(
    {
        "DO",
        "HAPPEN",
        "SOMETHING",
        "SOMEONE",
        "BE",
        "KIND",
        "PART",
        "HAVE",
        "NUMBER",
        "QUANTITY",
        "INTENSITY",
        "CERTAINTY",
    }
)
_GENERIC_KINDS = frozenset({"thing", "something", "someone", "entity", "kind"})


@dataclass(frozen=True)
class Identity:
    state: str
    key: tuple | None
    lemma: str | None
    reason: str = ""


@dataclass(frozen=True)
class Polarity:
    state: str
    clause_sign: int | None
    lexical_sign: int | None
    sign: int | None
    base: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class ClaimKey:
    state: str
    key: tuple | None
    polarity: Polarity
    projection: str
    reason: str = ""


def _lemma(node: Any) -> str | None:
    head = getattr(node, "head", node)
    lemma = getattr(head, "lemma", None)
    return lemma if isinstance(lemma, str) and lemma else None


def identity(operand: Any, namespace: str | None = None) -> Identity:
    """Resolved referent identity, or an explicitly unresolved local candidate.

    ``namespace`` identifies the resolution document. An id without a namespace
    is only comparable inside the caller's existing resolution domain.
    """
    lemma = _lemma(operand)
    eid = getattr(operand, "entity_id", None)
    if isinstance(eid, str) and eid:
        return Identity("resolved", ("referent", namespace, eid), lemma)
    if lemma:
        position = getattr(getattr(operand, "head", operand), "position", None)
        return Identity("unresolved", ("local", lemma, position), lemma, "missing_resolved_referent")
    return Identity("unsupported", None, None, "not_an_entity_reference")


def _valid_negation(scope: Any) -> bool:
    operand = getattr(scope.owner, "operand", None)
    # NOT(P and Q) does not assert either not-P or not-Q. Negation over
    # containers therefore cannot be distributed by a fact consumer.
    return type(operand).__name__ in {"Event", "TypeAssertion", "Comparison", "Control", "Negation"}


def _negation_targets(scope: Any, node: Any) -> bool:
    operand = getattr(scope.owner, "operand", None)
    for _ in range(64):
        if type(operand).__name__ != "Negation":
            return operand is node
        operand = getattr(operand, "operand", None)
    return False


def _readable(proposition: Any) -> bool:
    if not hasattr(proposition, "node") or not isinstance(getattr(proposition, "scopes", None), (tuple, list)):
        return False
    if getattr(proposition, "state", "read") != "read":
        return False
    for scope in proposition.scopes:
        if not isinstance(getattr(scope, "mode", None), str) or not isinstance(getattr(scope, "field", None), str):
            return False
        if not isinstance(getattr(scope, "owner_kind", None), str):
            return False
        if getattr(scope, "owner", None) is None:
            return False
    node, kind = proposition.node, type(proposition.node).__name__
    required = {
        "Event": ("agent",),
        "TypeAssertion": ("entity", "kind"),
        "Comparison": ("lhs", "rhs"),
        "Conditional": ("antecedent", "consequent"),
    }
    if any(getattr(node, field, None) is None for field in required.get(kind, ())):
        return False
    if kind == "Event" and (not isinstance(getattr(node, "verb", None), str) or not node.verb):
        return False
    from gse.symbolic.predicates import OPERAND_FIELDS

    return kind in OPERAND_FIELDS


def commitment_modes(modes: tuple[str, ...], *, valid: bool = True, interrogative: bool = False) -> str:
    """Flat scope decision underneath the object adapter.

    post: __return__ in {'committed', 'non_committed', 'abstained', 'in_question', 'unresolved'}
    post: valid or __return__ == 'unresolved'
    post: not (valid and interrogative) or __return__ == 'in_question'
    """
    if not valid:
        return "unresolved"
    if interrogative or any(mode in {"question", "in_question"} for mode in modes):
        return "in_question"
    for index, mode in enumerate(modes):
        if mode == "abstained":
            return "abstained"
        if mode == "negated" and any(inner in _ATTITUDES for inner in modes[index + 1 :]):
            return "abstained"
    if any(mode not in _TRANSPARENT for mode in modes):
        return "non_committed"
    return "committed"


def commitment(proposition: Any, *, interrogative: bool = False) -> str:
    """Return committed/non_committed/abstained/in_question/unresolved.

    Every ordered scope is inspected. A possible negative is non_committed even
    though the legacy outermost-status projection says ``negated``.
    """
    if not _readable(proposition):
        return commitment_modes((), valid=False)
    scopes = getattr(proposition, "scopes", ())
    modes = tuple(scope.mode for scope in scopes)
    decision = commitment_modes(
        modes, interrogative=interrogative or type(proposition.node).__name__ in {"TypeQuery", "DegreeQuery"}
    )
    if decision == "committed" and any(scope.mode == "negated" and not _valid_negation(scope) for scope in scopes):
        return "non_committed"
    return decision


def polarity(proposition: Any) -> Polarity:
    """Compose clause NOT with verified lexical negation; reversal never flips.

    A negative primitive such as GOOD=-1 is lexical content, not by itself
    evidence of a negative-prefix operation or a denied clause.
    """
    if not _readable(proposition):
        return Polarity("unresolved", None, None, None, reason="unread_proposition")
    scopes = getattr(proposition, "scopes", ())
    if any(scope.mode == "negated" and not _valid_negation(scope) for scope in scopes):
        return Polarity("unsupported", None, None, None, reason="non_atomic_negation")
    owned_negations = sum(scope.mode == "negated" and _negation_targets(scope, proposition.node) for scope in scopes)
    # A denial of the matrix attitude is not a denial of its complement.
    # Its governing NOT remains available in scopes, and commitment abstains.
    clause = -1 if owned_negations % 2 else 1
    lexical, base = 1, None
    node = proposition.node
    if type(node).__name__ == "TypeAssertion":
        base = _lemma(node.kind)
        if base is None:
            return Polarity("unresolved", clause, None, None, reason="missing_kind")
        from gse.nlp import morphology

        try:
            evidence_record = morphology.negation_evidence(base)
            if evidence_record["state"] in {"unresolved", "unread"}:
                return Polarity("unresolved", clause, None, None, base, evidence_record["decision"])
            evidence = (evidence_record["base"], evidence_record["feature"])
        except (LookupError, OSError) as exc:
            return Polarity("unresolved", clause, None, None, base, type(exc).__name__)
        if evidence is not None and evidence[1] == morphology.NEGATION:
            base, lexical = evidence[0], -1
    return Polarity("read", clause, lexical, clause * lexical, base)


def _freeze(value: Any, depth: int = 0) -> Any:
    """Stable structural context without Python object ids or mutable maps."""
    if depth > 64:
        return ("unresolved", "depth_limit")
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else ("invalid_number", repr(value))
    if isinstance(value, Mapping):
        return tuple(sorted((str(k), _freeze(v, depth + 1)) for k, v in value.items()))
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(v, depth + 1) for v in value)
    if type(value).__name__ == "Entity":
        return (
            "Entity",
            identity(value).key,
            _freeze(getattr(value, "modifier", None), depth + 1),
            _freeze(getattr(value, "possessor", None), depth + 1),
        )
    if type(value).__name__ == "Atom":
        return ("Atom", value.lemma, _freeze(value.word_primitives, depth + 1))
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return (
            type(value).__name__,
            tuple((f.name, _freeze(getattr(value, f.name), depth + 1)) for f in dataclasses.fields(value)),
        )
    return ("unsupported", type(value).__name__)


def scope_signature(proposition: Any) -> tuple:
    """Ordered non-negation scopes, including owner and represented context.

    Syntactic negation is carried separately in Polarity. An attitude's owner,
    conditional arm, modal force and temporal context cannot disappear from a
    claim comparison. Factive context is retained even when it commits content.
    """
    if not _readable(proposition):
        return (("unresolved", "malformed_proposition"),)

    def owner_context(scope):
        owner = scope.owner
        if scope.field == "modal":
            return ("modal", tuple(getattr(owner, "modal", ())))
        if scope.owner_kind == "Event" and scope.field == "patient":
            return (
                owner.verb,
                _freeze(owner.agent),
                _freeze(getattr(owner, "themes", ())),
                tuple(getattr(owner, "modal", ())),
            )
        if scope.owner_kind == "Temporal":
            other = owner.setting if scope.field == "event" else owner.event
            return (owner.conjunction, _freeze(other))
        if scope.owner_kind == "Conditional":
            other = owner.antecedent if scope.field == "consequent" else owner.consequent
            return (owner.conjunction, _freeze(other))
        return _freeze(owner)

    return tuple(
        (scope.mode, scope.owner_kind, scope.field, owner_context(scope))
        for scope in proposition.scopes
        if scope.mode != "negated" or not _negation_targets(scope, proposition.node)
    )


def claim_key(
    proposition: Any,
    relation_primitives: Mapping[str, Any] | Callable[[str], Mapping[str, Any]] | None = None,
    *,
    namespace: str | None = None,
) -> ClaimKey:
    """Versioned comparison key for atomic Event/TypeAssertion/Comparison.

    Event primitive evidence must be supplied from the producer's selected
    lexical record. Empty or generic forms abstain. All represented theme roles
    participate, and unresolved identity yields only a candidate, never a key.
    """
    pol = polarity(proposition)
    projection = "resolved_roles_signed_primitives_context/1"
    if pol.state != "read":
        return ClaimKey(pol.state, None, pol, projection, pol.reason)
    node, kind = proposition.node, type(proposition.node).__name__
    roles: list[tuple[str, Any]] = []
    if kind == "Event":
        try:
            evidence = relation_primitives(node.verb) if callable(relation_primitives) else relation_primitives
        except Exception as exc:
            return ClaimKey("unread", None, pol, projection, f"relation_evidence_error:{type(exc).__name__}")
        if not isinstance(evidence, Mapping):
            return ClaimKey("unsupported", None, pol, projection, "missing_relation_primitive_evidence")
        from gse.primitives_v2 import ALL_HIERARCHY_LEVELS, PRIMITIVE_REGISTRY

        if any(not isinstance(p, str) or p not in PRIMITIVE_REGISTRY for p in evidence):
            return ClaimKey("unresolved", None, pol, projection, "unknown_relation_primitives")
        if any(
            not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in evidence.values()
        ):
            return ClaimKey("unresolved", None, pol, projection, "malformed_relation_primitives")
        form = tuple(sorted((str(p), v) for p, v in evidence.items() if v))
        semantic_names = {p for p, _ in form} - {"HIER_PLUS", "HIER_MINUS"} - set(ALL_HIERARCHY_LEVELS)
        if not form or semantic_names <= _GENERIC_PRIMES:
            return ClaimKey("unsupported", None, pol, projection, "generic_relation")
        relation = ("event", ("signed_primitives", form))
        roles = [("agent", node.agent)]
        if node.patient is not None:
            roles.append(("patient", node.patient))
        roles.extend((f"theme:{index}", operand) for index, operand in enumerate(getattr(node, "themes", ())))
    elif kind == "TypeAssertion":
        if pol.base in _GENERIC_KINDS:
            return ClaimKey("unsupported", None, pol, projection, "generic_kind")
        relation, roles = ("type", pol.base), [("entity", node.entity)]
    elif kind == "Comparison":
        if node.sign not in {-1, 1}:
            return ClaimKey("unresolved", None, pol, projection, "invalid_comparison_direction")
        axis = node.axis
        if axis is None:
            modifiers = {
                getattr(getattr(operand, "modifier", None), "lemma", None) for operand in (node.lhs, node.rhs)
            } - {None}
            if len(modifiers) > 1:
                return ClaimKey("unresolved", None, pol, projection, "ambiguous_comparison_axis")
            axis = next(iter(modifiers), None)
        relation = ("comparison", axis, node.sign)
        roles = [("lhs", node.lhs), ("rhs", node.rhs)]
    else:
        return ClaimKey("unsupported", None, pol, projection, "unsupported_predicate_kind")
    ids = [(role, identity(operand, namespace)) for role, operand in roles]
    if any(item.state != "resolved" for _, item in ids):
        return ClaimKey("unresolved", None, pol, projection, "unresolved_argument_identity")
    signature = scope_signature(proposition)

    def unresolved_context(value):
        if not isinstance(value, tuple):
            return False
        if value and value[0] in {"local", "unsupported", "unresolved"}:
            return True
        if len(value) > 1 and value[0] == "Entity" and value[1] is None:
            return True
        return any(unresolved_context(item) for item in value)

    if unresolved_context(signature):
        return ClaimKey("unresolved", None, pol, projection, "unresolved_scope_identity")
    key = (CLAIM_KEY_VERSION, relation, tuple((role, item.key) for role, item in ids), signature)
    return ClaimKey("supported", key, pol, projection)
