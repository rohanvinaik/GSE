"""Symbolic constraints from already typed source predicates.

No text is parsed. Event forms and roles below are literal fields of the
native VerbNet contract. Multiple participant bindings stay separate.
"""

from __future__ import annotations

from collections import defaultdict
from functools import partial
from typing import TypedDict

from gse.lexicon_builder.core import Cell, Law, Observation, canonical_pole, legal_domain
from gse.lexicon_builder.model import OllamaSelector
from gse.lexicon_builder.perception import PERCEPTION_RULE, perception_constraints
from gse.lexicon_builder.reading import Construction, ReadingSeed, construct_reading
from gse.lexicon_builder.tail import attach_tail

EVENT_FORMS = {root: (root, "whole") for root in ("E", "E0", "E1")}
EVENT_FORMS.update(
    {f"{phase}({root})": (root, phase) for root in ("E", "E0", "E1") for phase in ("start", "during", "end", "result")}
)
# A predicate refused as a wrong-sense or out-of-scope join is never the change a cause brings about.
_REFUSED_JOINS = {"UNALIGNED_AFFECTIVE_READING", "OUTSIDE_RULE_CLASS_SCOPE", "PARTICIPANT_EXISTENCE_PRESUPPOSITION"}
_UNDERGOER_EVENTS = {"motion", "transfer", "emotional_state"}
_ASPECTUAL_CHANGES = {"begin", "end"}


class BindingProjection(TypedDict):
    coordinate: str
    event: str
    roles: list[str]
    allowed: list[str]
    selected_predicates: list[int]
    rule_ids: list[str]
    prior_positive: bool
    negated_only: bool
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


def _existence_is_content(frame: dict, roles: tuple[str, ...]) -> bool:
    """A static participant presupposition is not the verb's existence content."""
    if frame.get("class", "").startswith("exist-47.1"):
        return True
    states: dict[str, dict[str, set[bool]]] = defaultdict(lambda: defaultdict(set))
    for predicate in frame["predicates"]:
        if predicate["predicate"]["value"] != "exist":
            continue
        binding = tuple(a["value"].removeprefix("?") for a in predicate["arguments"] if a["type"] == "ThemRole")
        if binding != roles:
            continue
        events = [a["value"] for a in predicate["arguments"] if a["type"] == "Event"]
        if len(events) == 1 and events[0] in EVENT_FORMS:
            event, phase = EVENT_FORMS[events[0]]
            states[event][phase].add(predicate["predicate"].get("bool") == "!")
    return any(
        any(before != after for before in phases["start"] for phase in ("end", "result") for after in phases[phase])
        for phases in states.values()
    )


def _roles(predicate: dict) -> set[str]:
    return {a["value"].removeprefix("?") for a in predicate["arguments"] if a["type"] == "ThemRole"}


def _native_nodes(tree: dict):
    yield tree
    for child in tree.get("children", []):
        yield from _native_nodes(child)


def caused_change_status(frame: dict, cause_index: int, refused: set[int]) -> dict:
    """NSM's causative event: someone does something, and because of this something happens to another (GW16).

    The caused event must assert something happening to a participant other than the causer: a
    state or relation at its end or result, that participant's motion, transfer or emotional state
    during it, or its aspectual beginning or ending. A speech act's effect is only wanted ('this
    someone wanted something to happen because of it', GW2014 ch. 7), so saying is not causing.
    """
    cause = frame["predicates"][cause_index]
    if cause["predicate"].get("bool") not in (None, "!"):
        return {
            "code": "NO_CHANGE_TO_ANOTHER_PARTICIPANT",
            "blocked_evidence": ["UNSUPPORTED_NATIVE_POLARITY"],
        }
    causers = _roles(cause)
    caused_root = EVENT_FORMS[[a["value"] for a in cause["arguments"] if a["type"] == "Event"][-1]][0]
    declared = {r["role"] for r in frame.get("role_restrictions", [])}
    uncertain = {
        r["role"]
        for r in frame.get("role_restrictions", [])
        for tree in r.get("restrictions", [])
        for node in _native_nodes(tree)
        if node.get("attributes", {}).get("type") == "body_part" and node.get("attributes", {}).get("Value") == "+"
    }
    for tree in frame.get("syntax", []):
        for node in _native_nodes(tree):
            if node.get("tag") == "NP" and any(
                c.get("attributes", {}).get("type") == "refl" and c.get("attributes", {}).get("Value") == "+"
                for c in _native_nodes(node)
            ):
                uncertain.add(node.get("attributes", {}).get("value"))
    blocked = set()
    for index, predicate in enumerate(frame["predicates"]):
        name = predicate["predicate"]["value"]
        if index == cause_index or name == "cause" or index in refused:
            continue
        events = [a["value"] for a in predicate["arguments"] if a["type"] == "Event"]
        if len(events) != 1 or events[0] not in EVENT_FORMS:
            continue
        root, phase = EVENT_FORMS[events[0]]
        # Subevents E0 and E1 are parts of a caused E; a caused subevent must match exactly.
        if caused_root != "E" and root != caused_root:
            continue
        affected = _roles(predicate) - causers
        if not affected:
            continue
        # Pred is a result supplied by a construction (e.g. walk oneself tired),
        # not an independently asserted lexical outcome of the verb.
        if name == "Pred":
            blocked.add("CONSTRUCTION_RESULT_PLACEHOLDER")
            continue
        bound = affected - uncertain
        if "role_restrictions" in frame:
            bound &= declared
        if not bound:
            blocked.add("AFFECTED_PARTICIPANT_IDENTITY_UNCONFIRMED")
            continue
        polarity = predicate["predicate"].get("bool")
        if polarity not in (None, "!"):
            blocked.add("UNSUPPORTED_NATIVE_POLARITY")
            continue
        positive = polarity != "!"
        if (
            phase in {"end", "result"}
            or (positive and phase == "during" and name in _UNDERGOER_EVENTS)
            or (positive and phase == "whole" and name in _ASPECTUAL_CHANGES)
        ):
            return {"code": "BOUND_CAUSED_CHANGE", "predicate_index": index, "affected_roles": sorted(bound)}
    return {"code": "NO_CHANGE_TO_ANOTHER_PARTICIPANT", "blocked_evidence": sorted(blocked)}


def _bound_assertions(
    frame: dict, rules: dict[str, dict], native: dict | None = None, contracts: dict[str, dict] | None = None
) -> tuple[list[dict], list[dict]]:
    assertions, unmapped, causes = ([], [], [])
    for index, predicate in enumerate(frame["predicates"]):
        name = predicate["predicate"]["value"]
        rule = rules.get(name)
        # The join conditions come from the predicate's rule record whether or not that rule is admitted.
        contract = (contracts or {}).get(name, rule)
        if contract is None:
            unmapped.append({"predicate_index": index, "code": "UNMAPPED_NATIVE_PREDICATE", "native": predicate})
            continue
        if contract.get("requires_verb_emotion_tag"):
            tags = [
                tag
                for record in (native or {}).get("usas", {}).get("records", [])
                if record["values"]["pos"] == "VERB"
                for alternative in record["values"]["alternatives"]
                for tag in alternative.split("/")
            ]
            if not any(tag.startswith("E") for tag in tags):
                unmapped.append({"predicate_index": index, "code": "UNALIGNED_AFFECTIVE_READING", "native": predicate})
                continue
        class_number = frame.get("class", "").partition("-")[2]
        if "class_number_prefix" in contract and not class_number.startswith(contract["class_number_prefix"]):
            unmapped.append({"predicate_index": index, "code": "OUTSIDE_RULE_CLASS_SCOPE", "native": predicate})
            continue
        if predicate["predicate"].get("bool") not in (None, "!"):
            unmapped.append({"predicate_index": index, "code": "UNSUPPORTED_NATIVE_POLARITY", "native": predicate})
            continue
        event_values = [a["value"] for a in predicate["arguments"] if a["type"] == "Event"]
        event_causer = name == "cause" and len(event_values) == 2 and all(e in EVENT_FORMS for e in event_values)
        if (len(event_values) != 1 and not event_causer) or not event_values or event_values[-1] not in EVENT_FORMS:
            unmapped.append({"predicate_index": index, "code": "UNSUPPORTED_EVENT_FORM", "native": predicate})
            continue
        event, phase = EVENT_FORMS[event_values[-1]]
        roles = tuple((a["value"].removeprefix("?") for a in predicate["arguments"] if a["type"] == "ThemRole"))
        if contract.get("requires_existence_change") and not _existence_is_content(frame, roles):
            unmapped.append(
                {"predicate_index": index, "code": "PARTICIPANT_EXISTENCE_PRESUPPOSITION", "native": predicate}
            )
            continue
        if rule is None:  # a withheld rule: its join holds, but it writes nothing
            unmapped.append({"predicate_index": index, "code": "UNMAPPED_NATIVE_PREDICATE", "native": predicate})
            continue
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
        if name == "cause" and predicate["predicate"].get("bool") != "!" and "Agent" in roles:
            assertions.append({**assertions[-1], "coordinate": "DO", "prime": "DO"})
        elif name == "cause" and predicate["predicate"].get("bool") != "!" and event_causer:
            assertions.append({**assertions[-1], "coordinate": "HAPPEN", "prime": "HAPPEN"})
        if (
            name == "cause"
            and predicate["predicate"].get("bool") != "!"
            and rule.get("requires_change_to_another_participant")
        ):
            causes.append((index, rule["rule_id"]))
    refused = {u["predicate_index"] for u in unmapped if u["code"] in _REFUSED_JOINS}
    for index, rule_id in causes:
        outcome = caused_change_status(frame, index, refused)
        if outcome["code"] == "BOUND_CAUSED_CHANGE":
            continue
        # No caused change: neither CAUSE nor its DO/HAPPEN companion is written; the predicate stays in the derivation.
        assertions = [a for a in assertions if not (a["predicate_index"] == index and a["rule_id"] == rule_id)]
        unmapped.append({"predicate_index": index, **outcome, "native": frame["predicates"][index]})
    unmapped.sort(key=lambda u: u["predicate_index"])
    return (assertions, unmapped)


def frame_constraints(frame: dict, rulebook: dict, native: dict | None = None) -> dict:
    """Project lexical content and reviewed result poles, preserving scopes."""
    rules = {r["predicate"]: r for r in rulebook["native_predicate_rules"]}
    contracts = {
        r["predicate"]: r for r in rulebook.get("native_predicate_contracts", rulebook["native_predicate_rules"])
    }
    assertions, unmapped = _bound_assertions(frame, rules, native, contracts)
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
                "negated_only": component and not any(not v["negative"] for v in values),
                "all_phase_evidence": values,
            }
        )
    coordinate_groups: dict[str, list[BindingProjection]] = defaultdict(list)
    for assertion in projected:
        # A binding that only negates an unpaired relation writes nothing, never 0 (row 10): the source
        # does not say the word's definition lacks the relation. It stays in the derivation.
        if not assertion["negated_only"]:
            coordinate_groups[assertion["coordinate"]].append(assertion)
    laws, collisions, facts = ([], [], [])
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
        if coordinate == "MOVE" and allowed == {"+1"}:
            facts.append(("own_predicate", "physical_change_of_place"))
            continue
        laws.append(
            Law(
                "NATIVE:" + "+".join(sorted({rid for v in values for rid in v["rule_ids"]})),
                (coordinate,),
                tuple(((Cell(v),) for v in sorted(allowed))),
                (),
                "Native predicate, polarity and phase contract; roles preserved in derivation",
                "CONDITIONAL",
            )
        )
    return {"laws": tuple(laws), "facts": facts, "bindings": projected, "unmapped": unmapped, "collisions": collisions}


def _verb_record(
    word: str, reading_id: str, origin: dict, annotation: dict, constraints: dict, c: Construction
) -> dict:
    unresolved_scopes = list(constraints["collisions"])
    return {
        "word": word,
        "reading_id": reading_id,
        "code": "SOURCE_CONFLICT"
        if any((c_["code"] == "SOURCE_CONFLICT_ONE_BINDING" for c_ in constraints["collisions"]))
        else "PARTIAL_PROJECTION_SCOPE"
        if unresolved_scopes
        else c.state.code,
        "production_eligible": False,
        "source_scope": "NATIVE_CLASS_FRAME",
        "premise_record_ids": sorted(origin["memberships"]),
        "annotation_origin": annotation,
        "symbolic_before": c.initial.to_json(),
        "after_selection": c.state.to_json(),
        "bindings": constraints["bindings"],
        "unmapped": constraints["unmapped"],
        "collisions": constraints["collisions"],
        "unresolved_projection_scopes": unresolved_scopes,
        "model_calls": c.calls,
        "decisions": c.decisions,
        "candidate_vector": c.candidate,
        "coverage_gap": "Unmapped predicates and other source channels still require symbolic resolution; no default mask closure.",
    }


def frame_origins(native: dict) -> list[tuple[tuple[str, int], dict]]:
    """Each VerbNet frame once, at the class that defines it, with every membership that inherits it."""
    origins: dict[tuple[str, int], dict] = {}
    for record in native["verbnet"]["records"]:
        for frame in record["values"]["frames"]:
            key = (frame["class"], frame["frame_index"])
            origin = origins.setdefault(key, {"frame": frame, "memberships": set()})
            if origin["frame"] != frame:
                raise ValueError("inconsistent inherited native frame")
            origin["memberships"].add(record["record_id"])
    return sorted(origins.items())


def withheld_frame_writes(word: str, native: dict, withheld: dict) -> list[dict]:
    """What unadmitted VerbNet and perception rules would write, without applying it or asking a model."""
    states = {
        r["rule_id"]: r["review_state"]
        for family in ("native_predicate_rules", "native_residual_rules")
        for r in withheld.get(family, [])
    }
    out = []
    for (class_id, index), origin in frame_origins(native):
        reading_id = f"{word}:VERB:{class_id}:frame-{index}"
        constraints = frame_constraints(origin["frame"], withheld, native)
        for law in constraints["laws"]:
            rule_ids = law.rule_id.removeprefix("NATIVE:").split("+")
            out.append(
                {
                    "family": "native_predicate_rules",
                    "reading_id": reading_id,
                    "rule_ids": rule_ids,
                    "review_states": [states[r] for r in rule_ids],
                    "would_write": {law.coordinates[0]: [row[0].value for row in law.allowed]},
                }
            )
        for collision in constraints["collisions"]:
            out.append({"family": "native_predicate_rules", "reading_id": reading_id, "collision": collision})
        if constraints["facts"]:
            out.append(
                {
                    "family": "native_predicate_rules",
                    "reading_id": reading_id,
                    "rule_ids": ["VN_EVENT_MOTION"],
                    "review_states": [states["VN_EVENT_MOTION"]],
                    "would_assert": constraints["facts"],
                    "would_write": {"MOVE": ["+1"]},
                }
            )
        # selector=None: an unadmitted perception rule never spends a model call.
        perception = perception_constraints(word, origin["frame"], native, withheld, None, {})
        for decision in perception["decisions"]:
            out.append(
                {
                    "family": "native_residual_rules",
                    "reading_id": reading_id,
                    "rule_ids": [PERCEPTION_RULE],
                    "review_states": [states[PERCEPTION_RULE]],
                    "would_write": {} if decision["coordinate"] is None else {decision["coordinate"]: "+1"},
                    "mode": decision["mode"],
                    "model_decision_withheld": decision["mode"] == "UNRESOLVED",
                }
            )
    return out


def native_readings(
    word: str,
    native: dict,
    rulebook: dict,
    selector: OllamaSelector | None = None,
    tail_tasks: list[dict] | None = None,
    exceptions: tuple = (),
) -> list[dict]:
    """One native class/frame reading, with inheritance deduplicated by origin."""
    result = []
    scope_cache = {}
    for (class_id, index), origin in frame_origins(native):
        constraints = frame_constraints(origin["frame"], rulebook, native)
        perception = perception_constraints(
            word, origin["frame"], native, rulebook, selector if tail_tasks is None else None, scope_cache
        )
        if (
            not constraints["laws"]
            and not constraints["facts"]
            and (not constraints["collisions"])
            and (not perception["decisions"])
        ):
            continue
        reading_id = f"{word}:VERB:{class_id}:frame-{index}"
        # A perception mode settled by the sources is a source law. One chosen by the local model
        # is made once at word scope (identical payloads share one call) and applied as a chosen law.
        settled_by_sources = not perception["calls"]
        seed = ReadingSeed(
            word=word,
            reading_id=reading_id,
            observations=tuple(
                Observation(reading_id, "verbnet", "+".join(sorted(origin["memberships"])), field, value, True)
                for field, value in [("own_role", "lexical_predicate"), *constraints["facts"]]
            ),
            laws=list(constraints["laws"]) + (list(perception["laws"]) if settled_by_sources else []),
            layout=partial(_verb_record, word, reading_id, origin, {"class": class_id, "frame": index}, constraints),
            chosen_laws=[] if settled_by_sources else list(perception["laws"]),
            chosen_calls=list(perception["calls"]),
            chosen_records=list(perception["decisions"]),
            exportable=False,  # verb export is a stage-1b contract change, not part of this refactor
            exceptions=exceptions,
        )
        if tail_tasks is not None:
            seed = attach_tail(seed, tail_tasks)
        result.append(construct_reading(seed, rulebook, selector))
    return result
