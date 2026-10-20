"""Public structural measurements over GSE's serialized trees.

The vocabulary retains unknown operation labels rather than silently dropping
them. Depth counts embedded clause boundaries, not arbitrary dictionary nesting.
Diagnostics are preservation witnesses, never certificates of English meaning.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterator

_PREDICATE_OPERATIONS = {
    "Event": "EVENT",
    "TypeAssertion": "TYPE_ASSERT",
    "Comparison": "SET_DIFF",
    "Equality": "BIND_EQ",
    "DegreeQuery": "DEGREE_QUERY",
    "TypeQuery": "TYPE_QUERY",
    "MinimalSufficiency": "CARD_LOWER",
    "BoundaryCase": "SCALAR_EXTREME",
    "SetRestriction": "SET_RESTRICT",
    "Contrast": "CONTRAST",
    "Coordination": "COORDINATION",
    "ClauseCoordination": "CLAUSE_COORD",
    "Causation": "CAUSAL_SOURCE",
    "Conditional": "IMPLIES",
    "RelativeRestriction": "REL_RESTRICT",
    "Control": "CONTROL",
    "Temporal": "TEMPORAL",
}
OPERATION_VOCABULARY = tuple(sorted(set(_PREDICATE_OPERATIONS.values()) | {"CONSEQUENCE"}))
_EMBEDDED_FIELDS = {"Control": {"inner"}, "RelativeRestriction": {"restriction"}}


def _serialized(tree: Any):
    if isinstance(tree, (dict, list, tuple)) or tree is None:
        return tree
    from gse.symbolic.serialization import to_dict

    return to_dict(tree)


def _nodes(node: Any, path: tuple = ()) -> Iterator[tuple[tuple, dict]]:
    if isinstance(node, dict):
        if "_kind" in node:
            yield path, node
        for key, value in node.items():
            if isinstance(value, (dict, list, tuple)):
                yield from _nodes(value, path + (key,))
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            yield from _nodes(value, path + (index,))


def operation_counts(tree: Any) -> dict[str, int]:
    """Count typed operations, retaining every encountered label including temporal.

    Accepts either ``to_dict`` structure or a live GSE tree. The same node is
    counted once: an Op by its operation, an evaluated predicate by its kind.
    """
    counts: Counter[str] = Counter()
    for _path, node in _nodes(_serialized(tree)):
        operation = node.get("operation") if node.get("_kind") == "Op" else _PREDICATE_OPERATIONS.get(node.get("_kind"))
        if operation:
            if node.get("_kind") == "Causation" and node.get("conjunction") in {
                "so",
                "thus",
                "therefore",
                "hence",
                "consequently",
            }:
                operation = "CONSEQUENCE"
            counts[operation] += 1
    return dict(sorted(counts.items()))


def clause_depth(tree: Any) -> int:
    """Maximum number of embedded Control/relative/complement clause boundaries.

    Sequential coordination, contrast and temporal siblings do not add depth.
    Both typed predicates and pre-evaluation Op trees are accepted.

    post: __return__ >= 0
    """

    def visit(node: Any, depth: int) -> int:
        maximum = depth
        if isinstance(node, dict):
            kind = node.get("_kind")
            for key, value in node.items():
                embedded = key in _EMBEDDED_FIELDS.get(kind, set())
                if kind == "Event" and key == "patient" and isinstance(value, dict):
                    embedded = value.get("_kind") in _PREDICATE_OPERATIONS or value.get("_kind") in {"Negation", "Op"}
                if (
                    kind == "Op"
                    and key == "args"
                    and node.get("operation") in {"CONTROL", "REL_RESTRICT", "COMPLEMENT"}
                ):
                    # The first operand is the head/controller, the second embeds.
                    for index, child in enumerate(value or []):
                        maximum = max(maximum, visit(child, depth + int(index > 0)))
                    continue
                maximum = max(maximum, visit(value, depth + int(embedded)))
        elif isinstance(node, (list, tuple)):
            maximum = max([depth] + [visit(child, depth) for child in node])
        return maximum

    return visit(_serialized(tree), 0)


def structural_loss_evidence(
    trace: Any, tree: Any, *, utterance_id: str | None = None, boundary: str = "analysis"
) -> list[dict]:
    """Locate missing source predicates and empty operator operands.

    VERB tokens require an Event/Control verb or a preserved VERB Atom in a
    typed predicate. AUX/coplanar nominal readings are outside this witness.
    Repeated equal lemmas without head coordinates are reported as ambiguous.
    """
    serialized = _serialized(tree)
    nodes = list(_nodes(serialized))
    predicate_verbs = Counter(
        str(node["verb"]).lower()
        for _path, node in nodes
        if node.get("_kind") in {"Event", "Control"} and node.get("verb")
    )
    predicate_verbs.update(
        str(node["primitive"]).lower()
        for _path, node in nodes
        if node.get("_kind") == "Op" and node.get("operation") in {"EVENT", "CONTROL"} and node.get("primitive")
    )
    verb_container_paths = [
        path for path, node in nodes if node.get("_kind") == "Op" and node.get("operation") in {"EVENT", "CONTROL"}
    ]
    preserved_positions = {
        node.get("position")
        for _path, node in nodes
        if node.get("_kind") == "Atom"
        and node.get("pos") == "VERB"
        and any(_path[: len(parent)] == parent for parent in verb_container_paths)
    }
    findings: list[dict[str, Any]] = []
    tokens = trace.get("tokens", []) if isinstance(trace, dict) else getattr(trace, "tokens", [])
    source_verbs: Counter[str] = Counter()
    for token in tokens:
        data = token if isinstance(token, dict) else vars(token)
        if data.get("pos") == "VERB" and not data.get("is_operator"):
            source_verbs[str(data.get("lemma", "")).lower()] += 1
    for token in tokens:
        data = token if isinstance(token, dict) else vars(token)
        if data.get("pos") != "VERB" or data.get("is_operator"):
            continue
        lemma, position = str(data.get("lemma", "")).lower(), data.get("position")
        count = predicate_verbs[lemma]
        if not count and position not in preserved_positions:
            findings.append({"code": "missing_predicate", "position": position, "lemma": lemma})
        elif count and source_verbs[lemma] > count and position not in preserved_positions:
            findings.append({"code": "ambiguous_predicate_witness", "position": position, "lemma": lemma})
    for path, node in nodes:
        kind = node.get("_kind")
        if kind == "Phrase" and not node.get("atoms"):
            findings.append({"code": "empty_operand", "path": list(path)})
        if kind == "Op":
            args, arity = node.get("args", []), node.get("arity", 0)
            if len(args) != arity:
                findings.append(
                    {"code": "operand_arity_mismatch", "path": list(path), "expected": arity, "observed": len(args)}
                )
            for index, operand in enumerate(args):
                if operand is None:
                    findings.append(
                        {
                            "code": "empty_operand",
                            "path": list(path + ("args", index)),
                            "operation": node.get("operation"),
                        }
                    )
    for finding in findings:
        finding.update({"utterance_id": utterance_id, "boundary": boundary})
    return findings


def verb_head_evidence(trace: Any, tree: Any) -> list[dict]:
    """Locate represented verb heads as unique, ambiguous, or absent.

    Repeated equal verbs cannot be individually assigned from the current
    lemma-only Event representation; every candidate position remains visible.
    """
    tokens = trace.get("tokens", []) if isinstance(trace, dict) else getattr(trace, "tokens", [])
    positions: dict[str, list[int]] = {}
    for token in tokens:
        data = token if isinstance(token, dict) else vars(token)
        if data.get("pos") == "VERB":
            positions.setdefault(str(data.get("lemma", "")).lower(), []).append(data.get("position"))
    evidence = []
    for path, node in _nodes(_serialized(tree)):
        if node.get("_kind") in {"Event", "Control"}:
            verb = node.get("verb")
        elif node.get("_kind") == "Op" and node.get("operation") in {"EVENT", "CONTROL"}:
            verb = node.get("primitive")
        else:
            continue
        matches = positions.get(str(verb).lower(), []) if verb else []
        evidence.append(
            {
                "path": list(path),
                "verb": verb,
                "positions": matches,
                "state": "unique" if len(matches) == 1 else "ambiguous" if matches else "absent",
            }
        )
    return evidence


def clause_head_evidence(trace: Any, tree: Any) -> list[dict]:
    """Local Event subject/object heads with explicit ambiguity and trace checks.

    Run before document coreference: a rebound antecedent's Atom position belongs
    to its earlier utterance. No bare lemma or vector supplies a guessed head.
    """
    tokens = trace.get("tokens", []) if isinstance(trace, dict) else getattr(trace, "tokens", [])
    token_map = {}
    for token in tokens:
        data = token if isinstance(token, dict) else vars(token)
        token_map[data.get("position")] = data
    rows = []
    for path, node in _nodes(_serialized(tree)):
        if node.get("_kind") != "Event":
            continue
        sides = []
        mismatched = False
        for role in ("agent", "patient"):
            operand = node.get(role)
            heads = []
            members = (
                operand.get("members", [])
                if isinstance(operand, dict) and operand.get("_kind") == "Coordination"
                else [operand]
            )
            for member in members:
                if member is None:
                    continue
                if not isinstance(member, dict) or member.get("_kind") != "Entity":
                    mismatched = True
                    continue
                head = member.get("head", {})
                position = head.get("position")
                token = token_map.get(position)
                if token is None or str(token.get("lemma", "")).casefold() != str(head.get("lemma", "")).casefold():
                    mismatched = True
                else:
                    heads.append(position)
            sides.append(sorted(set(heads)))
        subject, obj = sides
        state = (
            "unsupported"
            if mismatched
            else "ambiguous"
            if len(subject) > 1 or len(obj) > 1
            else "supported"
            if subject and obj
            else "absent"
        )
        rows.append(
            {
                "path": list(path),
                "kind": "Event",
                "subject_positions": subject,
                "object_positions": obj,
                "state": state,
                "reason": "head_trace_mismatch"
                if mismatched
                else "missing_subject_or_object"
                if state == "absent"
                else "",
            }
        )
    return rows


def entity_source_evidence(trace: Any, source_tree: Any, resolved_tree: Any) -> dict:
    """Join source Entity occurrences to resolved IDs by exact structural path.

    Binding may replace a head or introduce an antecedent's nested structure.
    Only source occurrences are measured; newly copied antecedent children do
    not become fresh source mentions. No positional zip or lemma search binds
    an entity. A local trace witness certifies each source head's coordinate.
    """
    if source_tree is None:
        return {"state": "unread", "reason": "missing_source_tree", "mentions": [], "failures": []}
    tokens = trace.get("tokens", []) if isinstance(trace, dict) else getattr(trace, "tokens", [])
    token_map = {}
    for token in tokens:
        data = token if isinstance(token, dict) else vars(token)
        token_map[data.get("position")] = data
    resolved = dict(_nodes(_serialized(resolved_tree)))
    rows, failures = [], []
    for path, node in _nodes(_serialized(source_tree)):
        if node.get("_kind") != "Entity":
            continue
        head = node.get("head", {})
        target = resolved.get(path)
        token = token_map.get(head.get("position"))
        reason = (
            "source_head_trace_mismatch"
            if token is None or str(token.get("lemma", "")).casefold() != str(head.get("lemma", "")).casefold()
            else "source_entity_path_changed"
            if target is None or target.get("_kind") != "Entity"
            else ""
        )
        if reason:
            failures.append({"path": list(path), "reason": reason})
        target = target if target is not None and target.get("_kind") == "Entity" else {}
        rows.append(
            {
                "path": list(path),
                "state": "unread" if reason else "read",
                "reason": reason,
                "source_head": head,
                "surface": token.get("token") if token else None,
                "nominal_span": list(node.get("span", [])),
                "resolved_head": target.get("head"),
                "entity_id": target.get("entity_id") if not reason else None,
                "type_thread": target.get("type_thread", []),
                "role": node.get("role"),
            }
        )
    return {
        "state": "partial" if failures and rows else "unread" if failures else "read" if rows else "empty",
        "policy": "source-entity-field-paths/1",
        "mentions": rows,
        "failures": failures,
    }
