"""Symbolic constraints from already typed source predicates.

No text is parsed. Event forms and roles below are literal fields of the
native VerbNet contract. Multiple participant bindings stay separate.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TypedDict

from gse.lexicon_builder.core import Cell, Law, canonical_pole, legal_domain, resolve
from gse.lexicon_builder.model import OllamaSelector
from gse.lexicon_builder.perception import perception_constraints

EVENT_FORMS = {root: (root, "whole") for root in ("E", "E0", "E1")}
EVENT_FORMS.update(
    {f"{phase}({root})": (root, phase) for root in ("E", "E0", "E1") for phase in ("start", "during", "end", "result")}
)


class BindingProjection(TypedDict):
    coordinate: str
    event: str
    roles: list[str]
    allowed: list[str]
    selected_predicates: list[int]
    rule_ids: list[str]
    prior_positive: bool
    all_phase_evidence: list[dict]


def predicate_domain(prime: str, negative: bool, prior_positive: bool = False) -> tuple[str, ...]:
    """A negative observation excludes a pole; it is not usually its antonym.

    The reviewed vitality transition additionally requires a prior alive state.
    """
    coordinate, direction = canonical_pole(prime)
    if not negative:
        return ("+1" if direction > 0 else "-1",)
    if Cell.MINUS not in legal_domain(coordinate):
        return ("0",)
    if prime == "ALIVE" and prior_positive:
        return ("-1",)
    return ("-1", "0") if direction > 0 else ("0", "+1")


def _bound_assertions(frame: dict, rules: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    assertions, unmapped = ([], [])
    for index, predicate in enumerate(frame["predicates"]):
        name = predicate["predicate"]["value"]
        rule = rules.get(name)
        if rule is None:
            unmapped.append({"predicate_index": index, "code": "UNMAPPED_NATIVE_PREDICATE", "native": predicate})
            continue
        if predicate["predicate"].get("bool") not in (None, "!"):
            unmapped.append({"predicate_index": index, "code": "UNSUPPORTED_NATIVE_POLARITY", "native": predicate})
            continue
        event_values = [a["value"] for a in predicate["arguments"] if a["type"] == "Event"]
        if len(event_values) != 1 or event_values[0] not in EVENT_FORMS:
            unmapped.append({"predicate_index": index, "code": "UNSUPPORTED_EVENT_FORM", "native": predicate})
            continue
        event, phase = EVENT_FORMS[event_values[0]]
        roles = tuple((a["value"].removeprefix("?") for a in predicate["arguments"] if a["type"] == "ThemRole"))
        coordinate, _ = canonical_pole(rule["prime"])
        assertions.append(
            {
                "coordinate": coordinate,
                "prime": rule["prime"],
                "rule_id": rule["rule_id"],
                "projection_kind": rule["projection_kind"],
                "event": event,
                "phase": phase,
                "roles": roles,
                "predicate_index": index,
                "negative": predicate["predicate"].get("bool") == "!",
                "native": predicate,
            }
        )
    return (assertions, unmapped)


def frame_constraints(frame: dict, rulebook: dict) -> dict:
    """Project lexical content and reviewed result poles, preserving scopes."""
    rules = {r["predicate"]: r for r in rulebook["native_predicate_rules"]}
    assertions, unmapped = _bound_assertions(frame, rules)
    bindings: dict[tuple, list[dict]] = defaultdict(list)
    for assertion in assertions:
        bindings[assertion["coordinate"], assertion["event"], assertion["roles"]].append(assertion)
    projected: list[BindingProjection] = []
    for (coordinate, event, roles), values in bindings.items():
        terminals = [v for v in values if v["phase"] in {"end", "result"}]
        component = all((v["projection_kind"] == "LEXICAL_COMPONENT" for v in values))
        selected = values if component else terminals or [v for v in values if v["phase"] in {"during", "whole"}]
        if not selected:
            continue
        prior_positive = any((v["phase"] == "start" and (not v["negative"]) for v in values))
        signs: dict[tuple, set[bool]] = defaultdict(set)
        for value in values:
            constants = tuple(
                (a["type"], a["value"]) for a in value["native"]["arguments"] if a["type"] not in {"Event", "ThemRole"}
            )
            signs[(value["prime"], value["phase"], constants)].add(value["negative"])
        if any(len(observed) > 1 for observed in signs.values()):
            allowed = set()
        elif component:
            allowed = (
                {"+1"} if any((not v["negative"] for v in values)) else set(predicate_domain(values[0]["prime"], True))
            )
        else:
            allowed = None
            for value in selected:
                domain = set(predicate_domain(value["prime"], value["negative"], prior_positive))
                allowed = domain if allowed is None else allowed & domain
        projected.append(
            {
                "coordinate": coordinate,
                "event": event,
                "roles": list(roles),
                "allowed": sorted(allowed or []),
                "selected_predicates": [v["predicate_index"] for v in selected],
                "rule_ids": sorted({v["rule_id"] for v in selected}),
                "prior_positive": prior_positive,
                "all_phase_evidence": values,
            }
        )
    coordinate_groups: dict[str, list[BindingProjection]] = defaultdict(list)
    for assertion in projected:
        coordinate_groups[assertion["coordinate"]].append(assertion)
    laws, collisions = ([], [])
    for coordinate, values in coordinate_groups.items():
        domains = [set(v["allowed"]) for v in values]
        component = all((e["projection_kind"] == "LEXICAL_COMPONENT" for v in values for e in v["all_phase_evidence"]))
        allowed = (
            set()
            if any(not domain for domain in domains)
            else {"+1"}
            if component and any(("+1" in domain for domain in domains))
            else set.intersection(*domains)
        )
        if not allowed:
            collisions.append(
                {
                    "coordinate": coordinate,
                    "code": "SOURCE_CONFLICT_ONE_BINDING"
                    if any((not v["allowed"] for v in values))
                    else "UNRESOLVED_PROJECTION_SCOPE",
                    "bindings": values,
                }
            )
            continue
        laws.append(
            Law(
                "NATIVE:" + "+".join(sorted({rid for v in values for rid in v["rule_ids"]})),
                (coordinate,),
                tuple(((Cell(v),) for v in sorted(allowed))),
                (),
                "Native predicate, polarity and phase contract; roles preserved in derivation",
            )
        )
    return {"laws": tuple(laws), "bindings": projected, "unmapped": unmapped, "collisions": collisions}


def native_readings(word: str, native: dict, rulebook: dict, selector: OllamaSelector | None = None) -> list[dict]:
    """One native class/frame reading, with inheritance deduplicated by origin."""
    origins: dict[tuple[str, int], dict] = {}
    for record in native["verbnet"]["records"]:
        for frame in record["values"]["frames"]:
            key = (frame["class"], frame["frame_index"])
            origin = origins.setdefault(key, {"frame": frame, "memberships": set()})
            if origin["frame"] != frame:
                raise ValueError("inconsistent inherited native frame")
            origin["memberships"].add(record["record_id"])
    result = []
    scope_cache = {}
    for (class_id, index), origin in sorted(origins.items()):
        constraints = frame_constraints(origin["frame"], rulebook)
        perception = perception_constraints(word, origin["frame"], native, rulebook, selector, scope_cache)
        if not constraints["laws"] and (not constraints["collisions"]) and (not perception["decisions"]):
            continue
        reading_id = f"{word}:VERB:{class_id}:frame-{index}"
        laws = list(constraints["laws"])
        source_laws = laws + ([] if perception["calls"] else perception["laws"])
        initial = resolve(reading_id, laws=tuple(source_laws))
        laws.extend(perception["laws"])
        state = resolve(reading_id, laws=tuple(laws))
        calls, decisions, unresolved_scopes = (
            list(perception["calls"]),
            list(perception["decisions"]),
            list(constraints["collisions"]),
        )
        result.append(
            {
                "word": word,
                "reading_id": reading_id,
                "code": "SOURCE_CONFLICT"
                if any((c["code"] == "SOURCE_CONFLICT_ONE_BINDING" for c in constraints["collisions"]))
                else "PARTIAL_PROJECTION_SCOPE"
                if unresolved_scopes
                else state.code,
                "production_eligible": False,
                "source_scope": "NATIVE_CLASS_FRAME",
                "premise_record_ids": sorted(origin["memberships"]),
                "annotation_origin": {"class": class_id, "frame": index},
                "symbolic_before": initial.to_json(),
                "after_selection": state.to_json(),
                "bindings": constraints["bindings"],
                "unmapped": constraints["unmapped"],
                "collisions": constraints["collisions"],
                "unresolved_projection_scopes": unresolved_scopes,
                "model_calls": calls,
                "decisions": decisions,
                "candidate_vector": None,
                "coverage_gap": "Unmapped predicates and other source channels still require symbolic resolution; no default mask closure.",
            }
        )
    return result
