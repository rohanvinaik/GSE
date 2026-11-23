"""One reading from typed facts to a record: the constructor every source family shares.

A source family supplies a ReadingSeed: its typed facts, its source laws, any model laws already
chosen at word scope, the typed decisions still open, and its record layout. The constructor adds
the admitted bank laws, solves, asks the local model only about decisions that are still open
(solving again after each answer), runs the optional bank review, and offers a vector for export
only when every domain was resolved by constraints and the family's export contract allows it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from gse.lexicon_builder.core import (
    CANONICAL_COORDINATES,
    Cell,
    Law,
    Observation,
    Resolution,
    RuleException,
    admitted_laws,
    resolve,
)
from gse.lexicon_builder.coverage import review_banks
from gse.lexicon_builder.fill import BANK_COORDINATES, BANK_NAMES, open_fields
from gse.lexicon_builder.model import OllamaSelector, selection_status


def restriction(rule_id: str, coordinate: str, states: list[str], warrant: str, tier: str = "FOUNDATIONAL") -> Law:
    return Law(rule_id, (coordinate,), tuple((Cell(v),) for v in states), (), warrant, tier)


def ask(
    field_name: str, options: list[str], payload: dict, selector: OllamaSelector, cache: dict | None = None
) -> dict:
    """One typed local-model call. With a shared cache, an identical decision is not asked twice.

    A decision is the payload together with its field and legal options. A cached answer is reused
    only for that decision, and only after it is checked against those options again.
    """
    decision = {field_name: options}
    if cache is None:
        return selector.select(payload, decision)
    key = json.dumps({"payload": payload, "decision": decision}, sort_keys=True)
    if key in cache:
        status = selection_status(decision, cache[key]["answer"])
        if status != "VALID_SELECTION":
            raise ValueError(f"cached answer is outside the legal options of {field_name}: {status}")
        return {**cache[key], "cache_hit": True}
    call = {**selector.select(payload, decision), "cache_hit": False}
    cache[key] = call
    return call


def model_task_status(policy: object, coordinate: str) -> str:
    """Consume a reviewed task-type decision, never reference answers or scores.

    Admission permits statistical selection among surviving states; a source
    need not determine the answer. Evaluation and review own the admission
    record. An option list or a model's confidence cannot admit its own task.
    """
    if policy is None:
        return "UNREVIEWED_MODEL_TASK_TYPE"
    if not isinstance(policy, dict):
        return "MALFORMED_MODEL_TASK_POLICY"
    if any(not isinstance(policy.get(k), str) or not policy[k] for k in ("task_type", "reason")):
        return "MALFORMED_MODEL_TASK_POLICY"
    coordinates, refs = policy.get("coordinates"), policy.get("evidence_refs")
    if (
        not isinstance(coordinates, list)
        or not coordinates
        or any(not isinstance(c, str) or c not in CANONICAL_COORDINATES for c in coordinates)
        or not isinstance(refs, list)
        or not refs
        or any(not isinstance(r, str) or not r for r in refs)
    ):
        return "MALFORMED_MODEL_TASK_POLICY"
    if coordinate not in coordinates:
        return "OUTSIDE_MODEL_TASK_SCOPE"
    status = policy.get("status")
    if status == "WITHHELD":
        return "WITHHELD_MODEL_TASK_TYPE"
    if status == "ADMITTED":
        return "ADMITTED_MODEL_TASK_TYPE"
    return "UNREVIEWED_MODEL_TASK_TYPE"


@dataclass(frozen=True)
class CoordinateDecision:
    """An open coordinate the local model may settle; it is open while its domain has two or more states."""

    coordinate: str
    payload: Callable[[Resolution], dict]
    permitted: tuple[str, ...] | None = None
    task_id: str | None = None
    allow_abstain: bool = False

    def options(self, state: Resolution) -> list[str] | None:
        domain = state.domains[self.coordinate]
        values = [v.value for v in domain if self.permitted is None or v.value in self.permitted]
        return values if len(domain) > 1 and len(values) > 1 else None


@dataclass(frozen=True)
class ReviewContract:
    """The opt-in per-bank review a family allows, and the template its provisional closure names."""

    payload: Callable[[Resolution], dict]
    completion_domains: dict[str, list[str]]
    coverage_template: str


@dataclass
class ReadingSeed:
    """What one source family contributes to one reading."""

    word: str
    reading_id: str
    observations: tuple[Observation, ...]
    laws: list[Law]
    layout: Callable[[Construction], dict]
    chosen_laws: list[Law] = field(default_factory=list)
    chosen_calls: list[dict] = field(default_factory=list)
    chosen_records: list[dict] = field(default_factory=list)
    decisions: list[CoordinateDecision] = field(default_factory=list)
    review: ReviewContract | None = None
    exportable: bool = True
    fill: Callable[[Resolution, int, dict], dict] | None = None
    exceptions: tuple[RuleException, ...] = ()
    context: dict = field(default_factory=dict)
    completion_check: Callable[[Resolution], dict] | None = None
    selection_policy: dict | None = None


@dataclass
class Construction:
    """The shared results a family's layout turns into its record."""

    initial: Resolution
    state: Resolution
    decisions: list[dict]
    calls: list[dict]
    review: dict
    coverage: str
    candidate: dict | None
    closed: Resolution | None
    proposal: dict | None
    proposed_closure: Resolution | None
    definition_accounting: dict = field(default_factory=dict)


def _vector(state: Resolution, provisional: list[str]) -> dict:
    forced = state.forced()
    return {
        "states": {c: forced[c].value for c in CANONICAL_COORDINATES},
        "mask": [forced[c] != Cell.SILENT for c in CANONICAL_COORDINATES],
        "signs": [None if forced[c] == Cell.SILENT else int(forced[c]) for c in CANONICAL_COORDINATES],
        "provisional_silence": provisional,
        "trace": list(state.trace),
    }


def construct_reading(
    seed: ReadingSeed, rulebook: dict, selector: OllamaSelector | None, bank_review: bool = False
) -> dict:
    laws = list(admitted_laws(rulebook)) + list(seed.laws)
    initial = resolve(seed.reading_id, seed.observations, laws=tuple(laws), exceptions=seed.exceptions)
    laws.extend(seed.chosen_laws)
    state = resolve(seed.reading_id, seed.observations, laws=tuple(laws), exceptions=seed.exceptions)
    calls, decisions = list(seed.chosen_calls), list(seed.chosen_records)
    # Settle one open coordinate, close immediately, and recompute. A multi-coordinate
    # bank law can settle another open coordinate without a further call.
    for decision in seed.decisions:
        options = decision.options(state)
        disposition = {"task_id": decision.task_id, "coordinate": decision.coordinate}
        code = None
        if state.code == "CONFLICT":
            code = "SOURCE_CONFLICT"
        elif options is None:
            code = "ALREADY_RESOLVED"
        elif decision.task_id is not None and {v.value for v in state.domains[decision.coordinate]} != set(
            decision.permitted or ()
        ):
            code = "STALE_TASK_DOMAIN"
        elif selector is None:
            code = "SYMBOLIC_ONLY"
        elif model_task_status(seed.selection_policy, decision.coordinate) != "ADMITTED_MODEL_TASK_TYPE":
            code = model_task_status(seed.selection_policy, decision.coordinate)
        elif not getattr(selector, "available", True):
            code = "BUDGET_EXHAUSTED"
        if code is not None:
            if decision.task_id is not None or (selector is not None and code != "ALREADY_RESOLVED"):
                decisions.append({**disposition, "code": code})
            continue
        assert options is not None and selector is not None
        if decision.allow_abstain:
            options = [*options, "ABSTAIN"]
        try:
            call = ask(decision.coordinate, options, decision.payload(state), selector)
        except (OSError, TimeoutError, ValueError) as error:
            if decision.task_id is None:
                raise
            decisions.append({**disposition, "code": "MODEL_BACKEND_FAILURE", "detail": str(error)})
            continue
        calls.append(call)
        if call["answer"][decision.coordinate] == "ABSTAIN":
            decisions.append({**disposition, "code": "ABSTAINED", "request_sha256": call["request_sha256"]})
        else:
            laws.append(
                restriction(
                    "MODEL:" + call["request_sha256"],
                    decision.coordinate,
                    [call["answer"][decision.coordinate]],
                    "Typed local selection; candidate, not a new source fact",
                    "MODEL_CANDIDATE",
                )
            )
            previous = state
            state = resolve(seed.reading_id, seed.observations, laws=tuple(laws), exceptions=seed.exceptions)
            fields = [d.coordinate for d in seed.decisions if d.options(previous) is not None]
            decisions.append(
                {
                    **disposition,
                    "code": "SELECTED",
                    "selected": call["answer"],
                    "before": {c: [v.value for v in previous.domains[c]] for c in fields},
                    "after": {c: [v.value for v in state.domains[c]] for c in fields},
                    "forced_after": len(state.forced()),
                }
            )
    # Every cell the rules leave open goes to the local model, one bank per call (F078). Each answer is a
    # restriction; the reading is solved again before the next bank, so a law can settle a later cell.
    if selector is not None and seed.fill is not None:
        for bank in range(len(BANK_COORDINATES)):
            if state.code == "CONFLICT":
                break
            fields = open_fields(state, bank)
            if not fields:
                continue
            if any(model_task_status(seed.selection_policy, c) != "ADMITTED_MODEL_TASK_TYPE" for c in fields):
                decisions.append({"bank": BANK_NAMES[bank], "code": "UNADMITTED_BANK_FILL"})
                continue
            call = selector.select(seed.fill(state, bank, fields), fields)
            calls.append(call)
            for coordinate, value in call["answer"].items():
                laws.append(
                    restriction(
                        "FILL:" + call["request_sha256"] + ":" + coordinate,
                        coordinate,
                        [value],
                        "Typed local bank fill; candidate, not a new source fact",
                        "MODEL_CANDIDATE",
                    )
                )
            previous = state
            state = resolve(seed.reading_id, seed.observations, laws=tuple(laws), exceptions=seed.exceptions)
            decisions.append(
                {
                    "bank": BANK_NAMES[bank],
                    "selected": call["answer"],
                    "before": {c: [v.value for v in previous.domains[c]] for c in fields},
                    "after": {c: [v.value for v in state.domains[c]] for c in fields},
                    "forced_after": len(state.forced()),
                }
            )
    decisions_closed = all(d.options(state) is None for d in seed.decisions)
    review = {"code": "NOT_CHECKED", "rounds": [], "missing": []}
    # Opt-in: the known-omission control showed bank accounts cannot license
    # silence, and no recipe defines completion_domains yet, so these calls
    # cannot change an exported vector. They stay available as a diagnostic.
    if (
        bank_review
        and seed.review is not None
        and selector is not None
        and decisions_closed
        and state.code == "PARTIAL"
    ):
        review = review_banks(
            seed.reading_id,
            seed.observations,
            laws,
            state,
            seed.review.payload(state),
            selector,
            seed.review.completion_domains,
        )
        state, laws = review["state"], review["laws"]
        calls.extend(review["calls"])
        decisions.extend(review["decisions"])
    coverage = "NONE" if review["code"] == "BANKS_ACCOUNTED" else str(next(iter(review["missing"]), review["code"]))
    proposal, proposed_closure = None, None
    if seed.review is not None and decisions_closed and coverage == "NONE" and state.code != "CONFLICT":
        # The founder-approved provisional closure after an omission challenge (F049),
        # kept only as a reviewable proposal: the deletion control showed that an
        # all-ACCOUNTED review can miss a known component, so it never exports.
        provisional = []
        for coordinate in CANONICAL_COORDINATES:
            if len(state.domains[coordinate]) > 1:
                provisional.append(coordinate)
                laws.append(
                    restriction(
                        "PROVISIONAL_COVERAGE:" + seed.review.coverage_template,
                        coordinate,
                        ["empty"],
                        "Template coverage proposal + local omission challenge; requires Zipf audit",
                    )
                )
        proposed_closure = resolve(seed.reading_id, seed.observations, laws=tuple(laws), exceptions=seed.exceptions)
        if proposed_closure.code == "RESOLVED":
            proposal = _vector(proposed_closure, provisional)
    # Export only a vector whose domains were resolved by constraints before any blanket closure.
    accounting = seed.completion_check(state) if seed.completion_check is not None else {"code": "NO_FAMILY_ACCOUNT"}
    resolved = (
        seed.exportable and state.code == "RESOLVED" and accounting["code"] in {"NO_FAMILY_ACCOUNT", "FAMILY_ACCOUNTED"}
    )
    return seed.layout(
        Construction(
            initial=initial,
            state=state,
            decisions=decisions,
            calls=calls,
            review=review,
            coverage=coverage,
            candidate=_vector(state, []) if resolved else None,
            closed=state if resolved else None,
            proposal=proposal,
            proposed_closure=proposed_closure,
            definition_accounting=accounting,
        )
    )
