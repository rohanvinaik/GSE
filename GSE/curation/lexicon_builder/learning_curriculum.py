"""Open-bank questions and unapproved discoveries for the existing epoch runner.

Curriculum scopes carry no sign. They select exact native definitions; only the
ordinary typed writer can retain an answer, and only ordinary rule admission can
turn a separately warranted and audited hypothesis into a law.
"""

from dataclasses import dataclass
from itertools import combinations

from GSE.namespace import current_id

from .engine import Relation
from .foundation import BANKS, lexical_context, validate_lexical_guards
from .grounded_rules import MAX_PREMISES, grounded_chains
from .rule_history import digest
from .scheduling import pending_banks, spelling_cohort

FORMAT = "GSE.lexicon-epoch-plan/2"
REVIEW_FORMAT = "GSE.lexicon-learning-reviews/1"


@dataclass(frozen=True)
class CurriculumScope:
    id: str
    guards: tuple[tuple[str, str], ...]
    holdouts: tuple[str, ...] = ()

    def relation(self):
        # A tautology is a scope carrier, never a proposed answer or admitted law.
        return Relation(self.id, (sorted(BANKS)[0],), ((-1,), (0,), (1,)), (), guards=self.guards)


def curriculum(plan):
    if current_id(plan["format"]) != FORMAT:
        return None
    raw = plan.get("curriculum")
    required = {"banks", "scopes", "frontier_limit", "banks_per_entry", "candidate_limit", "audit_entry_ids"}
    if type(raw) is not dict or raw.keys() != required:
        raise ValueError("INVALID_LEARNING_CURRICULUM")
    for key in ("frontier_limit", "banks_per_entry", "candidate_limit"):
        if type(raw[key]) is not int or raw[key] < 1:
            raise ValueError("INVALID_LEARNING_SEARCH_BOUND")
    for key in ("banks", "audit_entry_ids"):
        values = raw[key]
        if (
            type(values) is not list
            or not values
            or any(type(value) is not str or not value for value in values)
            or len(set(values)) != len(values)
        ):
            raise ValueError("INVALID_LEARNING_CURRICULUM_IDENTITIES")
    if not set(raw["banks"]) <= set(BANKS):
        raise ValueError("UNKNOWN_LEARNING_BANK")
    if type(raw["scopes"]) is not list or not raw["scopes"]:
        raise ValueError("EMPTY_LEARNING_SCOPES")
    seen = set()
    for item in raw["scopes"]:
        if (
            type(item) is not dict
            or item.keys() != {"id", "guards"}
            or type(item["id"]) is not str
            or not item["id"].startswith("curriculum:")
            or item["id"] in seen
            or type(item["guards"]) is not list
        ):
            raise ValueError("INVALID_LEARNING_SCOPE")
        if any(
            type(guard) is not list or len(guard) != 2 or any(type(value) is not str for value in guard)
            for guard in item["guards"]
        ):
            raise ValueError("INVALID_LEARNING_SCOPE_GUARD")
        scope = CurriculumScope(item["id"], tuple(tuple(guard) for guard in item["guards"]))
        validate_lexical_guards((scope.relation(),))
        # Match the existing family boundary: a native predicate, not POS alone.
        from .definition_frames import NATIVE_FRAME_PREFIX, WIKTIONARY_ANATOMY_FRAME_PREFIX

        if not (
            any(k.startswith((NATIVE_FRAME_PREFIX, WIKTIONARY_ANATOMY_FRAME_PREFIX)) for k, _ in scope.guards)
            or ("wordnet_native_lemma", "true") in scope.guards
            and any(k.startswith("wordnet_ancestor:") for k, _ in scope.guards)
        ):
            raise ValueError("LEARNING_REQUIRES_WITNESSED_NATIVE_SCOPE")
        seen.add(scope.id)
    return raw


def curriculum_scopes(plan):
    config = curriculum(plan)
    return (
        {
            item["id"]: CurriculumScope(item["id"], tuple(tuple(guard) for guard in item["guards"]))
            for item in config["scopes"]
        }
        if config
        else {}
    )


def plan_inventory(baseline, plan):
    from .epoch import census, parse_plan

    return census(baseline, {**parse_plan(plan), **curriculum_scopes(plan)})


def choose_open(candidate, plan, inventory, families, attempted, policy, frequencies):
    """Rank a bounded Zipf frontier without assuming any answer or rule family."""
    import json
    from contextlib import closing

    from .epoch import _resolve, _sense_group, connect, question_effects, scope_rows

    config = curriculum(plan)
    if config is None:
        return None
    everyone = {row["entry_id"]: row for group in inventory.values() for row in group}
    reserved = set(config["audit_entry_ids"]) | {entry for family in families.values() for entry in family.holdouts}
    holdout = plan.get("evaluation_holdout", {"entries": [], "lemmas": []})
    reserved.update(holdout["entries"])
    held_senses = {_sense_group(everyone[i]) for i in reserved if i in everyone}
    held_spellings = {everyone[i]["lemma"].casefold() for i in reserved if i in everyone}
    held_spellings.update(lemma.casefold() for lemma in holdout["lemmas"])
    selected_ids = plan.get("teaching_entry_ids")
    pool = {
        row["entry_id"]: row
        for key in curriculum_scopes(plan)
        for row in inventory[key]
        if _sense_group(row) not in held_senses
        and row["lemma"].casefold() not in held_spellings
        and (selected_ids is None or row["entry_id"] in selected_ids)
        and any((row["entry_id"], bank) not in attempted for bank in config["banks"])
    }
    # Filter resolved coordinates before bounding the frontier; a resolved
    # frequent spelling must not conceal unresolved less-frequent definitions.
    with closing(connect(candidate)) as conn:
        eligible = {
            identity
            for identity, encoded in conn.execute("SELECT entry_id,domains FROM definition_states")
            if identity in pool
            and any(
                len(values) > 1 and bank in config["banks"] and (identity, bank) not in attempted
                for bank, values in json.loads(encoded).items()
            )
        }
    pool = {identity: row for identity, row in pool.items() if identity in eligible}
    frontier, limited = spelling_cohort(
        (
            ((-frequencies.get(row["lemma"].casefold(), 0), identity), row["lemma"].casefold())
            for identity, row in pool.items()
        ),
        config["frontier_limit"],
    )
    rules, rows = scope_rows(candidate, (pool[identity] for _, identity in frontier))
    options, unavailable = [], []
    for identity, row in rows.items():
        state = _resolve(row, rules)
        if state.code == "CONFLICT" or any(step["kind"] == "SOLVER_LIMIT" for step in state.trace):
            unavailable.append(identity)
            continue
        definition, _, _, observation, _ = row
        ordered = pending_banks(
            state,
            config["banks"],
            {b for i, b in attempted if i == identity},
            policy="evidence",
            observations=(observation,),
            relations=rules,
            context=lexical_context(definition, (observation,), rules),
        )
        for bank in ordered[: config["banks_per_entry"]]:
            options.append(
                {
                    "task": "OPEN_BANK_TEACHING",
                    "family": None,
                    "entry_id": identity,
                    "bank": bank,
                    "sense_group": _sense_group(pool[identity]),
                    "subtlex": frequencies.get(pool[identity]["lemma"].casefold(), 0),
                    "per_answer_closure": question_effects(row, rules, bank),
                    "search": {
                        "frontier_limit": config["frontier_limit"],
                        "frontier_limited": limited,
                        "banks_considered": len(ordered[: config["banks_per_entry"]]),
                        "banks_remaining": len(ordered),
                        "scope": "DECLARED_NATIVE_CURRICULUM",
                    },
                }
            )

    def rank(option):
        frequency = (-option["subtlex"], option["entry_id"], option["bank"])
        if policy == "zipf":
            return frequency
        values = [row.get("specification_gain_bits") for row in option["per_answer_closure"]]
        exact = bool(values) and all(value is not None for value in values)
        return (not exact, -min(values) if exact else 0, *frequency)

    if not options and unavailable:
        raise ValueError("LEARNING_FRONTIER_CLOSURE_UNAVAILABLE:" + ",".join(unavailable))
    return min(options, key=rank) if options else None


def discover_teaching(base, plan, inventory, selected, taught):
    """Nominate scoped unary/pair/conjunctive laws; no nomination is an approval."""
    from .epoch import Family, _resolve, scope_rows

    config = curriculum(plan)
    if config is None:
        return []
    identity, bank, value = selected["entry_id"], selected["bank"], taught["value"]
    scopes = curriculum_scopes(plan)
    reports = []
    for scope_id, scope in scopes.items():
        witness = next((row for row in inventory[scope_id] if row["entry_id"] == identity), None)
        if witness is None:
            continue
        rules, rows = scope_rows(base, (witness,))
        state = _resolve(rows[identity], rules)
        chains = grounded_chains(state.trace, rules, state.assignments)
        literals = sorted((b, v) for b, v in state.assignments.items() if b != bank)
        for width in range(MAX_PREMISES + 1):
            for premises in combinations(literals, width):
                proposal = Family(
                    "discovered",
                    premises[0] if width == 1 else None,
                    (bank, value),
                    scope.guards,
                    (),
                    {},
                    premises if width > 1 else (),
                )
                reports.append(
                    {
                        "proposal": proposal.proposal(),
                        "evidence": {
                            "entry_id": identity,
                            "source_sha256": witness["source_sha256"],
                            "scope_id": scope_id,
                            "taught": taught,
                            "baseline_proof_sha256": digest(state.trace),
                            "grounded_chains": chains,
                            "premises": [list(pair) for pair in premises],
                        },
                        "authority": "TYPED_TEACHING_HYPOTHESIS_REQUIRES_WARRANT_AND_INDEPENDENT_AUDIT",
                    }
                )
                if len(reports) == config["candidate_limit"]:
                    return reports
    return reports


def hypothesis_relation(proposal):
    from .epoch import Family

    premises = tuple(tuple(pair) for pair in proposal.get("premises", ()))
    left = proposal.get("antecedent")
    return Family(
        "discovered",
        tuple(left) if left else None,
        tuple(proposal["consequent"]),
        tuple(tuple(guard) for guard in proposal["guards"]),
        (),
        {},
        premises,
        tuple(proposal.get("allowed_values", ())),
    ).relation()


def retain_discoveries(learning, outcome):
    for candidate in outcome.get("discoveries", ()):
        learning.propose(
            hypothesis_relation(candidate["proposal"]),
            candidate["evidence"],
            origin=candidate.get("origin", "TYPED_TEACHING_HYPOTHESIS"),
        )


def refresh_reviews(plan, baseline, directory, learning, families, inventory):
    """Consume append-only warranted reviews without changing the frozen plan."""
    from .epoch import census, parse_plan, read, record
    from .learning_state import mechanism_id

    config = curriculum(plan)
    if config is None:
        return
    path = directory / "reviews.json"
    intake = []
    if path.exists():
        raw = read(path)
        if (
            type(raw) is not dict
            or raw.keys() != {"format", "records"}
            or raw["format"] != REVIEW_FORMAT
            or type(raw["records"]) is not list
        ):
            raise ValueError("INVALID_LEARNING_REVIEW_INTAKE")
        for review in raw["records"]:
            if type(review) is not dict or review.keys() != {"mechanism_id", "family"}:
                raise ValueError("INVALID_LEARNING_REVIEW_RECORD")
            [family] = parse_plan({**plan, "families": [review["family"]]}).values()
            warrant = family.warrant
            if (
                type(warrant) is not dict
                or any(
                    type(warrant.get(key)) is not str or not warrant[key]
                    for key in ("reviewer", "statement", "warrant_id", "review_id", "kind")
                )
                or type(warrant.get("source_refs")) is not list
                or not warrant["source_refs"]
                or any(type(ref) is not str or not ref for ref in warrant["source_refs"])
            ):
                raise ValueError("LEARNING_REVIEW_REQUIRES_EXPLICIT_WARRANT")
            if not set(family.holdouts) <= set(config["audit_entry_ids"]):
                raise ValueError("LEARNING_AUDIT_OUTSIDE_RESERVED_POOL")
            intake.append((review["mechanism_id"], family.relation(), review["family"]))
    reviewed = learning.reviewed()
    by_mechanism = {row["mechanism_id"]: row["family"] for row in reviewed}
    by_mechanism.update({identity: item for identity, _, item in intake})
    parsed = parse_plan({**plan, "families": list(by_mechanism.values())})
    new_scopes = {}
    for identity, item in by_mechanism.items():
        family = parsed[item["id"]]
        if mechanism_id(family.relation()) != identity:
            raise ValueError("LEARNING_REVIEW_MECHANISM_CHANGED")
        if family.id not in families:
            new_scopes[identity] = census(baseline, {family.id: family})[family.id]
    learning.review_many(intake)
    for identity, observed in new_scopes.items():
        family = parsed[by_mechanism[identity]["id"]]
        record(directory / ("inventory-" + identity + ".json"), observed)
        inventory[family.id] = observed
        families[family.id] = family


def reviewed_choice(candidate, learning, families, inventory, done, policy, frequencies):
    """Use original teaching evidence to audit a newly warranted candidate."""
    from .epoch import _sense_group, forecast, premises_proved, scope_rows

    options = []
    for row in learning.ready():
        family = families[row["family"]["id"]]
        if family.id in done:
            continue
        members = {item["entry_id"]: item for item in inventory[family.id]}
        rules, states = scope_rows(candidate, members.values())
        if any(
            not premises_proved(states[i][-1], family.antecedents) or len(states[i][-1][family.consequent[0]]) < 2
            for i in family.holdouts
        ):
            continue
        audit_senses = {_sense_group(members[i]) for i in family.holdouts}
        audit_spellings = {members[i]["lemma"].casefold() for i in family.holdouts}
        for witness in learning.witnesses(row["mechanism_id"]):
            evidence = witness["evidence"]
            if (
                witness["origin"] not in {"TYPED_TEACHING_HYPOTHESIS", "COUNTEREXAMPLE_GUARD_IMPUTATION"}
                or "taught" not in evidence
            ):
                continue
            identity, taught = evidence["entry_id"], evidence["taught"]
            if identity not in members or taught["value"] not in family.allowed_consequents:
                continue
            if (
                evidence["source_sha256"] != members[identity]["source_sha256"]
                or _sense_group(members[identity]) in audit_senses
                or members[identity]["lemma"].casefold() in audit_spellings
            ):
                raise ValueError("LEARNING_DISCOVERY_AUDIT_IDENTITY_OVERLAP_OR_CHANGE")
            staged = forecast(states, rules, (family.relation(),))
            options.append(
                {
                    "task": "AUDIT_DISCOVERED_MECHANISM",
                    "family": family.id,
                    "entry_id": identity,
                    "bank": family.consequent[0],
                    "sense_group": _sense_group(members[identity]),
                    "reviewed_teaching": taught,
                    "specification_gain_bits": staged["specification_gain_bits"],
                    "subtlex": frequencies.get(members[identity]["lemma"].casefold(), 0),
                }
            )
            break

    def rank(option):
        frequency = (-option["subtlex"], option["entry_id"], option["bank"], option["family"])
        if policy == "zipf":
            return frequency
        gain = option["specification_gain_bits"]
        return (gain is None, -gain if gain is not None else 0, *frequency)

    return min(options, key=rank) if options else None
