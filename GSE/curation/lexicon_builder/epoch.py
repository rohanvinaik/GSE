"""Persistent, budgeted rule-learning epochs over exact lexical evidence."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from GSE.namespace import current_id, identity_form

from .completion import _contexts, _entry, _priority_source, complete_dictionary
from .definition_frames import NATIVE_FRAME_PREFIX, WIKTIONARY_ANATOMY_FRAME_PREFIX
from .engine import Assertion, Relation
from .evidence import Definition
from .foundation import BANKS, lexical_context, native_frame_source, validate_lexical_guards
from .grounded_rules import MAX_PREMISES, discover_reviewed_groundings, grounded_chains, implication_rows
from .learning_state import LearningState, mechanism_id
from .model_receipts import read_model_receipts
from .publication import publication_readiness
from .residual import ModelTransportError, _read_value, _request_id, build_request
from .resolution import resolve_dictionary
from .reviewed_export import export_reviewed_input
from .reviewed_patterns import run_workflow_input
from .rule_admission import admit_records
from .rule_history import digest
from .rule_migration import migrate_revision
from .rule_revisions import FORMAT as REVISION_FORMAT
from .rule_revisions import exception_source, touches_scope
from .specification import CONTRACT, compare_measurements, measure_dictionary, measure_resolution, space_delta
from .validation import _context_observations, _metadata, _relations, validate_build

FORMAT = "GSE.lexicon-epoch-plan/1"
POLICIES = ("closure", "zipf")
SIGNS = (-1, 0, 1)


def fingerprint(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def record(path, value):
    """Install an immutable JSON checkpoint, or verify an existing one."""
    payload = json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8") as temporary:
        temporary.write(payload)
        temporary.flush()
        os.fsync(temporary.fileno())
        try:
            os.link(temporary.name, path)
        except FileExistsError:
            if path.read_text() != payload:
                raise ValueError("EPOCH_CHECKPOINT_CHANGED:" + path.name) from None


def connect(path):
    return sqlite3.connect(path.resolve(strict=True).as_uri() + "?mode=ro", uri=True)


def snapshot_copy(source, target):
    if target.exists():
        return
    from .sqlite_snapshot import copy_database

    with tempfile.TemporaryDirectory(dir=target.parent) as directory:
        temporary = Path(directory) / "snapshot.db"
        copy_database(source, temporary)
        os.link(temporary, target)


@dataclass(frozen=True)
class Family:
    id: str
    antecedent: tuple[str, int] | None
    consequent: tuple[str, int]
    guards: tuple[tuple[str, str], ...]
    holdouts: tuple[str, ...]
    warrant: dict
    premises: tuple[tuple[str, int], ...] = ()
    allowed_values: tuple[int, ...] = ()

    @property
    def antecedents(self):
        return self.premises or ((self.antecedent,) if self.antecedent is not None else ())

    @property
    def allowed_consequents(self):
        return self.allowed_values or (self.consequent[1],)

    def proposal(self):
        return {
            **(
                {"premises": [list(pair) for pair in self.premises]}
                if self.premises
                else {"antecedent": list(self.antecedent) if self.antecedent is not None else None}
            ),
            "consequent": list(self.consequent),
            "guards": [list(pair) for pair in self.guards],
            "absent_evidence": [],
            "warrant": self.warrant,
            **({"allowed_values": list(self.allowed_values)} if self.allowed_values else {}),
        }

    def relation(self):
        return Relation(
            "epoch-stage:" + self.id,
            tuple(bank for bank, _ in (*self.antecedents, self.consequent)),
            tuple(
                sorted(
                    {
                        row
                        for value in self.allowed_consequents
                        for row in implication_rows(self.antecedents, (self.consequent[0], value))
                    }
                )
            ),
            ("epoch-proposal:" + self.id,),
            "conditional",
            True,
            self.guards,
        )


def parse_plan(raw):
    from .learning_curriculum import FORMAT as DYNAMIC_FORMAT
    from .learning_curriculum import curriculum

    required = {"format", "baseline_sha256", "active_pointer_sha256", "epochs", "audits_per_epoch", "families"}
    if (
        type(raw) is not dict
        or not required <= raw.keys()
        or raw.keys() - required - {"evaluation_holdout", "teaching_entry_ids", "curriculum"}
        or current_id(raw["format"]) not in {FORMAT, DYNAMIC_FORMAT}
    ):
        raise ValueError("INVALID_EPOCH_PLAN")
    if "evaluation_holdout" in raw:
        holdout = raw["evaluation_holdout"]
        if type(holdout) is not dict or holdout.keys() != {"entries", "lemmas"}:
            raise ValueError("INVALID_EPOCH_EVALUATION_HOLDOUT")
        for items in holdout.values():
            if (
                type(items) is not list
                or not items
                or any(type(item) is not str or not item for item in items)
                or len(set(items)) != len(items)
            ):
                raise ValueError("INVALID_EPOCH_EVALUATION_HOLDOUT")
    if "teaching_entry_ids" in raw:
        teaching = raw["teaching_entry_ids"]
        if (
            type(teaching) is not list
            or not teaching
            or any(type(i) is not str or not i for i in teaching)
            or len(set(teaching)) != len(teaching)
        ):
            raise ValueError("INVALID_EPOCH_TEACHING_CURRICULUM")
    for field in ("baseline_sha256", "active_pointer_sha256"):
        if type(raw[field]) is not str or len(raw[field]) != 64 or any(c not in "0123456789abcdef" for c in raw[field]):
            raise ValueError("INVALID_EPOCH_PLAN_DIGEST")
    if any(type(raw[key]) is not int or raw[key] < 1 for key in ("epochs", "audits_per_epoch")):
        raise ValueError("INVALID_EPOCH_BUDGET")
    dynamic = current_id(raw["format"]) == DYNAMIC_FORMAT
    if dynamic:
        curriculum(raw)
    elif "curriculum" in raw:
        raise ValueError("CURRICULUM_REQUIRES_VERSIONED_LEARNING_PLAN")
    if type(raw["families"]) is not list or not raw["families"] and not dynamic:
        raise ValueError("EMPTY_EPOCH_RULE_FAMILIES")
    families, holdouts = {}, set()
    for item in raw["families"]:
        required_family = {"id", "consequent", "guards", "holdouts", "warrant"}
        if (
            type(item) is not dict
            or not required_family <= item.keys()
            or (item.keys() - required_family - {"allowed_values"}) not in ({"antecedent"}, {"premises"})
        ):
            raise ValueError("INVALID_EPOCH_RULE_FAMILY")
        identity = item["id"]
        if type(identity) is not str or not identity or identity in families or identity.startswith("curriculum:"):
            raise ValueError("INVALID_EPOCH_RULE_IDENTITY")
        left = item.get("antecedent")
        premises = item.get("premises", [] if left is None else [left])
        if type(premises) is not list or not (2 if "premises" in item else 0) <= len(premises) <= MAX_PREMISES:
            raise ValueError("INVALID_EPOCH_PREMISES")
        for pair in [*premises, item["consequent"]]:
            if (
                type(pair) is not list
                or len(pair) != 2
                or pair[0] not in BANKS
                or type(pair[1]) is not int
                or pair[1] not in SIGNS
            ):
                raise ValueError("INVALID_EPOCH_LITERAL")
        held = item["holdouts"]
        allowed = item.get("allowed_values", [])
        if "allowed_values" in item and (
            type(allowed) is not list
            or not 1 <= len(allowed) <= 2
            or any(type(v) is not int or v not in SIGNS for v in allowed)
            or len(set(allowed)) != len(allowed)
            or item["consequent"][1] not in allowed
        ):
            raise ValueError("INVALID_EPOCH_ALLOWED_CONSEQUENTS")
        if (
            type(held) is not list
            or len(held) != raw["audits_per_epoch"]
            or any(type(value) is not str or not value for value in held)
            or len(set(held)) != len(held)
            or holdouts.intersection(held)
        ):
            raise ValueError("INVALID_EPOCH_HOLDOUT_BUDGET_OR_OVERLAP")
        holdouts.update(held)
        family = Family(
            identity,
            tuple(left) if left is not None else None,
            tuple(item["consequent"]),
            tuple(tuple(guard) for guard in item["guards"]),
            tuple(held),
            item["warrant"],
            tuple(tuple(pair) for pair in premises) if "premises" in item else (),
            tuple(allowed),
        )
        validate_lexical_guards((family.relation(),))
        native_frame = any(
            k.startswith((NATIVE_FRAME_PREFIX, WIKTIONARY_ANATOMY_FRAME_PREFIX)) for k, _ in family.guards
        )
        wordnet_scope = (
            any(k.startswith("wordnet_ancestor:") for k, _ in family.guards)
            and ("wordnet_native_lemma", "true") in family.guards
        )
        if len({bank for bank, _ in (*family.antecedents, family.consequent)}) != len(premises) + 1 or not (
            native_frame or wordnet_scope
        ):
            raise ValueError("EPOCH_REQUIRES_WITNESSED_NATIVE_SCOPE")
        families[identity] = family
    return families


def census(baseline, families):
    """Find all stored exact native witnesses for the declared scope language."""
    by_id = {key: family.relation() for key, family in families.items()}
    native_frames = {
        key: rule
        for key, rule in by_id.items()
        if any(k.startswith((NATIVE_FRAME_PREFIX, WIKTIONARY_ANATOMY_FRAME_PREFIX)) for k, _ in rule.guards)
    }
    ancestry = {key: rule for key, rule in by_id.items() if key not in native_frames}
    guards = tuple(ancestry.values())
    ancestors = sorted(
        {
            k.removeprefix("wordnet_ancestor:")
            for rule in guards
            for k, _ in rule.guards
            if k.startswith("wordnet_ancestor:")
        }
    )
    result = {key: [] for key in families}
    with closing(connect(baseline)) as conn:
        for entry, lemma, pos, gloss, raw in conn.execute(
            "SELECT d.entry_id,l.lemma,l.pos,l.gloss,o.payload FROM definition_states d "
            "JOIN source_observations o ON o.record_id=d.entry_id "
            "JOIN lexemes l ON l.id=d.lexeme_id "
            "WHERE o.source='wordnet_hierarchy' AND o.scope='lexical' AND EXISTS ("
            "SELECT 1 FROM json_tree(o.payload,'$.features.hypernym_paths') "
            "WHERE type='text' AND atom IN (SELECT value FROM json_each(?))) ORDER BY d.entry_id",
            (json.dumps(ancestors),),
        ):
            definition = {"entry_id": entry, "lemma": lemma, "pos": pos, "definition": gloss}
            observation = json.loads(raw)
            context = lexical_context(definition, (observation,), guards)
            for identity, rule in ancestry.items():
                if touches_scope((rule,), context):
                    result[identity].append(
                        {
                            "entry_id": entry,
                            "lemma": lemma,
                            "synset": observation["features"]["synset_name"],
                            "source_sha256": digest({"definition": definition, "observation": observation}),
                        }
                    )
        _append_native_frame_scopes(conn, native_frames, result)
    for key, family in families.items():
        rows = {row["entry_id"]: row for row in result[key]}
        if not set(family.holdouts) <= rows.keys():
            raise ValueError("EPOCH_HOLDOUT_OUTSIDE_SCOPE:" + key)
        if len({_sense_group(rows[i]) for i in family.holdouts}) != len(family.holdouts):
            raise ValueError("EPOCH_HOLDOUT_ALIAS_OVERLAP:" + key)
    return result


def _sense_group(row):
    return row["sense_group"] if "sense_group" in row else row["synset"]


def _append_native_frame_scopes(conn, framed, inventory):
    if not framed:
        return
    requested = tuple(framed.values())
    for entry, lemma, pos, gloss in conn.execute(
        "SELECT d.entry_id,l.lemma,l.pos,l.gloss FROM definition_states d "
        "JOIN lexemes l ON l.id=d.lexeme_id WHERE l.pos='noun' ORDER BY d.entry_id"
    ):
        if not isinstance(gloss, str):
            continue
        definition = Definition(entry, lemma, pos, gloss)
        observations = _context_observations(conn, entry, requested, definition)
        witnessed = [(row, native_frame_source(definition, row)) for row in observations]
        exact = [(row, group) for row, group in witnessed if group is not None]
        if not exact:
            continue
        if len({group for _, group in exact}) != 1:
            raise ValueError("AMBIGUOUS_EPOCH_NATIVE_FRAME_WITNESS:" + entry)
        observation, group = exact[0]
        context = lexical_context(definition, (observation,), requested)
        for identity, rule in framed.items():
            if touches_scope((rule,), context):
                inventory[identity].append(
                    {
                        "entry_id": entry,
                        "lemma": lemma,
                        "sense_group": group,
                        "source_record_id": observation["record_id"],
                        "source_sha256": digest(
                            {
                                "definition": {"entry_id": entry, "lemma": lemma, "pos": pos, "definition": gloss},
                                "observation": observation,
                            }
                        ),
                    }
                )


def _domains(state):
    return {name: sorted(values) for name, values in state.domains.items()}


def _resolve(row, rules, *, retire_models=False):
    definition, assertions, restrictions, observation, _ = row
    if retire_models:
        assertions = tuple(a for a in assertions if a.family != "model" and not a.source.startswith("model:"))
    # The exact WordNet records in the v1 scope are unclassified. An
    # unclassified record already makes all banks evidence-relevant.
    if "bank_relevance" in observation["features"]:
        raise ValueError("EPOCH_SCOPE_REQUIRES_FULL_RELEVANCE")
    return resolve_dictionary(
        BANKS,
        assertions,
        rules,
        lexical_context(definition, (observation,), rules),
        evidence_banks=tuple(sorted(BANKS)),
        domain_restrictions=restrictions,
    )


def scope_rows(candidate, inventory):
    with closing(connect(candidate)) as conn:
        rules = _relations(_metadata(conn, "relations"))
        rows = {}
        for item in inventory:
            identity = item["entry_id"]
            if "source_record_id" in item:
                definition, assertions, restrictions, _ = _entry(conn, identity)
                source_row = conn.execute(
                    "SELECT payload FROM source_observations WHERE record_id=? AND entry_id=?",
                    (item["source_record_id"], identity),
                ).fetchone()
                if source_row is None:
                    raise ValueError("EPOCH_SCOPE_WITNESS_CHANGED:" + identity)
                observation = json.loads(source_row[0])
                if native_frame_source(definition, observation) != _sense_group(item):
                    raise ValueError("EPOCH_SCOPE_WITNESS_CHANGED:" + identity)
                source = {
                    "definition": {key: getattr(definition, key) for key in ("entry_id", "lemma", "pos", "definition")},
                    "observation": observation,
                }
            else:
                source = exception_source(conn, identity)
                definition, assertions, restrictions, _ = _entry(conn, identity)
            if digest(source) != item["source_sha256"]:
                raise ValueError("EPOCH_SCOPE_WITNESS_CHANGED:" + identity)
            [raw] = conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (identity,)).fetchone()
            rows[identity] = (definition, assertions, restrictions, source["observation"], json.loads(raw))
    return rules, rows


def mine_scope_chains(candidate, inventory):
    """Collect exact proof compositions in the frozen portfolio."""
    unique = {row["entry_id"]: row for members in inventory.values() for row in members}
    rules, rows = scope_rows(candidate, unique.values())
    grouped = {}
    for identity, row in rows.items():
        state = _resolve(row, rules)
        if _domains(state) != row[-1] or state.code == "CONFLICT":
            raise ValueError("CHAIN_MINING_REPLAY_MISMATCH:" + identity)
        for hypothesis in grounded_chains(state.trace, rules, state.assignments):
            roots = hypothesis.pop("evidence_roots")
            key = digest(hypothesis)
            report = grouped.setdefault(key, {**hypothesis, "witnesses": []})
            report["witnesses"].append(
                {
                    "entry_id": identity,
                    "source_sha256": unique[identity]["source_sha256"],
                    "evidence_roots": roots,
                }
            )
    return {
        "format": "GSE.lexicon-grounded-chains/1",
        "definitions_checked": len(rows),
        "proposals": [grouped[key] for key in sorted(grouped)],
    }


def forecast(rows, rules, proposals):
    """Simulate the same model retirement and closure as an additive revision."""
    changes, conflicts, space_changes = [], [], []
    for identity, row in rows.items():
        definition, _, _, observation, before = row
        scope = lexical_context(definition, (observation,), proposals)
        if not touches_scope(proposals, scope):
            continue
        original = _resolve(row, rules)
        if _domains(original) != before or original.code == "CONFLICT":
            raise ValueError("EPOCH_BASELINE_REPLAY_MISMATCH:" + identity)
        retained = _resolve(row, rules, retire_models=True)
        new = _resolve(row, rules + proposals, retire_models=True)
        before_exceptions = {digest(x) for x in retained.trace if x["kind"] == "CONDITIONAL_EXCEPTION"}
        issues = [x for x in new.trace if x["kind"] == "CONDITIONAL_EXCEPTION" and digest(x) not in before_exceptions]
        if (
            new.code == "CONFLICT"
            or issues
            or any(new.assignments.get(k) != v for k, v in retained.assignments.items())
        ):
            conflicts.append(
                {
                    "code": "CONDITIONAL_CONFLICT" if issues else "HARD_CONTRADICTION",
                    "entry_id": identity,
                    "definition": {key: getattr(definition, key) for key in ("entry_id", "lemma", "pos", "definition")},
                    "observation": observation,
                    "context": scope,
                    "issues": issues,
                    "conflicts": new.conflicts,
                    "retained_domains": _domains(retained),
                    "proposed_domains": _domains(new),
                    "retained_derivations": retained.trace,
                    "proposed_derivations": new.trace,
                    "remedy": "REVIEW_IDENTITY_PROJECTION_CONDITION_OR_EXACT_EXCEPTION",
                }
            )
            continue
        before_space, after_space = measure_resolution(retained), measure_resolution(new)
        delta = space_delta(before_space, after_space)
        if delta["code"] != "UNCHANGED":
            space_changes.append({"entry_id": identity, "before": before_space, "after": after_space, **delta})
        for bank, after in _domains(new).items():
            if before[bank] != after:
                changes.append({"entry_id": identity, "bank": bank, "before": before[bank], "after": after})
    unavailable = sum(row["code"] == "UNAVAILABLE" for row in space_changes)
    bits = sum(row["specification_gain_bits"] or 0 for row in space_changes)
    return {
        "changes": changes,
        "contradictions": conflicts,
        "space_changes": space_changes,
        "specification_gain_bits": None if unavailable else bits,
        "progress_code": "CONTRADICTION"
        if conflicts
        else "UNAVAILABLE"
        if unavailable
        else "CONTRACTION"
        if bits > 0
        else "UNCHANGED",
        "contract": CONTRACT,
    }


def gains(report):
    return {(r["entry_id"], r["bank"]) for r in report["changes"] if len(r["before"]) > 1 and len(r["after"]) == 1}


def question_effects(row, rules, bank):
    """Simulate every surviving answer through the same joint closure, without writing."""
    baseline = _resolve(row, rules)
    known = baseline.assignments
    old_exceptions = {digest(r) for r in baseline.trace if r["kind"] == "CONDITIONAL_EXCEPTION"}
    before = measure_resolution(baseline)
    effects = []
    for value in sorted(baseline.domains[bank]):
        definition, assertions, restrictions, observation, domains = row
        hypothetical = Assertion(bank, value, "counterfactual:question-planning", definition.entry_id, "hypothetical")
        after = _resolve((definition, assertions + (hypothetical,), restrictions, observation, domains), rules)
        challenges = [
            r for r in after.trace if r["kind"] == "CONDITIONAL_EXCEPTION" and digest(r) not in old_exceptions
        ]
        if after.code == "CONFLICT" or challenges or any(after.assignments.get(k) != v for k, v in known.items()):
            effects.append(
                {"value": value, "code": "CONSTRAINT_CHALLENGE", "conflicts": after.conflicts, "exceptions": challenges}
            )
        else:
            measured = measure_resolution(after)
            effects.append({"value": value, **space_delta(before, measured), "remaining": measured})
    return effects


def choose(
    candidate,
    inventory,
    families,
    done,
    used_synsets,
    policy,
    frequencies,
    evaluation_holdout=None,
    teaching_entry_ids=None,
):
    """Rank eligible exact questions by Zipf or marginal closure plus bridge gain."""
    if not any(key not in done for key in families):
        return None
    everyone = {row["entry_id"]: row for group in inventory.values() for row in group}
    rules, rows = scope_rows(candidate, everyone.values())
    held = {_sense_group(everyone[i]) for family in families.values() for i in family.holdouts}
    held_spellings = {everyone[i]["lemma"].casefold() for family in families.values() for i in family.holdouts}
    if evaluation_holdout:
        held.update(_sense_group(everyone[i]) for i in evaluation_holdout["entries"] if i in everyone)
        held_spellings.update(lemma.casefold() for lemma in evaluation_holdout["lemmas"])
    remaining = {key: rule for key, rule in families.items() if key not in done}
    projections = {key: forecast(rows, rules, (family.relation(),)) for key, family in remaining.items()}
    # Evaluate the complete declared hypothesis portfolio and leave-one-out
    # consequences. This includes chains/conjunctions of any portfolio depth;
    # the older pair diagnostics below are retained only as explanatory detail.
    portfolio = forecast(rows, rules, tuple(family.relation() for family in remaining.values()))
    conditional_reach = {}
    for key in remaining:
        other_keys = [other for other in remaining if other != key]
        without = (
            projections[other_keys[0]]
            if len(other_keys) == 1
            else forecast(rows, rules, tuple(remaining[other].relation() for other in other_keys))
        )
        available = (
            not portfolio["contradictions"]
            and not without["contradictions"]
            and portfolio["specification_gain_bits"] is not None
            and without["specification_gain_bits"] is not None
        )
        conditional_reach[key] = {
            "code": "EXACT_DECLARED_PORTFOLIO" if available else "UNAVAILABLE_OR_CHALLENGED",
            "families": sorted(remaining),
            "with_all_bits": portfolio["specification_gain_bits"],
            "without_this_bits": without["specification_gain_bits"],
            "marginal_bits": portfolio["specification_gain_bits"] - without["specification_gain_bits"]
            if available
            else None,
            "contradictions": portfolio["contradictions"],
        }
    options, answer_cache = [], {}
    for key, family in remaining.items():
        right, _ = family.consequent
        if any(
            not premises_proved(rows[i][-1], family.antecedents) or len(rows[i][-1][right]) < 2 for i in family.holdouts
        ):
            continue
        projection = projections[key]
        immediate = gains(projection)
        bridges: list[dict[str, Any]] = []
        for other, neighbor in remaining.items():
            if other == key or not any(
                (family.consequent[0], value) in neighbor.antecedents for value in family.allowed_consequents
            ):
                continue
            pair = forecast(rows, rules, (family.relation(), neighbor.relation()))
            changes = {(r["entry_id"], r["bank"]): r["after"] for r in projection["changes"]}
            enabled = all(
                all(changes.get((i, b), rows[i][-1][b]) == [v] for b, v in neighbor.antecedents)
                and not premises_proved(rows[i][-1], neighbor.antecedents)
                for i in neighbor.holdouts
            )
            if not pair["contradictions"] and enabled:
                joint = gains(pair) - immediate - gains(projections[other])
                pair_bits = pair["specification_gain_bits"]
                own_bits, other_bits = (
                    projection["specification_gain_bits"],
                    projections[other]["specification_gain_bits"],
                )
                synergy = (
                    pair_bits - own_bits - other_bits
                    if all(v is not None for v in (pair_bits, own_bits, other_bits))
                    else None
                )
                if joint or (synergy is not None and synergy > 0):
                    bridges.append({"family": other, "joint_only": len(joint), "complementary_bits": synergy})
        for item in inventory[key]:
            identity, sense_group = item["entry_id"], _sense_group(item)
            state = rows[identity][-1]
            if (
                sense_group in held
                or teaching_entry_ids is not None
                and identity not in teaching_entry_ids
                or item["lemma"].casefold() in held_spellings
                or sense_group in used_synsets
                or not premises_proved(state, family.antecedents)
                or len(state[right]) < 2
            ):
                continue
            support = _resolve(rows[identity], rules)
            answer_key = (identity, right)
            if answer_key not in answer_cache:
                answer_cache[answer_key] = question_effects(rows[identity], rules, right)
            options.append(
                {
                    "family": key,
                    "entry_id": identity,
                    **({"sense_group": sense_group} if "sense_group" in item else {"synset": sense_group}),
                    "bank": right,
                    "subtlex": frequencies.get(item["lemma"].casefold(), 0),
                    "singletons": len(immediate),
                    "specification_gain_bits": projection["specification_gain_bits"],
                    "progress_code": projection["progress_code"],
                    "per_answer_closure": answer_cache[answer_key],
                    "portfolio_reach": conditional_reach[key],
                    "contract": CONTRACT,
                    "contradictions": len(projection["contradictions"]),
                    "bridge_options": sorted(bridges, key=lambda b: (-b["joint_only"], b["family"])),
                    **(
                        {"premises": [list(p) for p in family.premises]}
                        if family.premises
                        else {"premise": list(family.antecedent) if family.antecedent is not None else None}
                    ),
                    "premise_proof": support.trace,
                }
            )
    if not options:
        return None

    def key(option):
        if policy == "zipf":
            return (-option["subtlex"], option["entry_id"], option["bank"], option["family"])
        measured = option["specification_gain_bits"]
        conditional = option["portfolio_reach"]["marginal_bits"]
        reach = max(measured or 0, conditional or 0)
        answers = option["per_answer_closure"]
        local = [answer.get("specification_gain_bits") for answer in answers]
        complete_answers = bool(local) and all(value is not None for value in local)
        guaranteed = min(local) if complete_answers else 0
        return (
            option["contradictions"],
            measured is None,
            -reach,
            not complete_answers,
            -guaranteed,
            -option["singletons"],
            -option["subtlex"],
            option["entry_id"],
            option["family"],
        )

    return min(options, key=key)


def premises_proved(domains, premises):
    return all(domains[bank] == [value] for bank, value in premises)


class EpochTransportRefusal(RuntimeError):
    @property
    def code(self):
        return str(self)


class JournaledTransport:
    """Charge a typed question before execution, then replay the recorded reply."""

    def __init__(self, transport, directory, label, limit, lock_path, *, context_store=None):
        self.transport = transport
        self.identity = transport.identity
        self.directory = directory
        self.label = label
        self.limit = limit
        self.lock_path = lock_path
        self.context_store = context_store

    def __call__(self, payload, schema):
        request_id = _request_id(payload)
        stem = self.label + "-" + request_id
        intent, result = (self.directory / (stem + suffix + ".json") for suffix in (".intent", ".result"))
        expected = {"request_id": request_id, "transport": self.identity, "schema": schema}
        if intent.exists():
            saved = read(intent)
            if (
                type(saved) is not dict
                or set(saved) not in (set(expected), set(expected) | {"request_archive"})
                or {key: saved[key] for key in expected} != expected
            ):
                raise ValueError("EPOCH_QUESTION_IDENTITY_CHANGED")
            if "request_archive" in saved:
                if self.context_store is None:
                    raise ValueError("EPOCH_QUESTION_ARCHIVE_REQUIRED")
                archived = self.context_store.request(saved["request_archive"])
                if (
                    archived["request_id"] != request_id
                    or archived["transport"] != self.identity
                    or archived["schema"] != schema
                ):
                    raise ValueError("EPOCH_QUESTION_ARCHIVE_CHANGED")
            elif self.context_store is not None:
                raise ValueError("EPOCH_QUESTION_ARCHIVE_MISSING")
        elif result.exists():
            raise ValueError("EPOCH_QUESTION_INTENT_MISSING")
        if result.exists():
            response = read(result)
            if "raw_output" not in response:
                raise ModelTransportError(response["code"])
            return response["raw_output"]
        if intent.exists():
            raise EpochTransportRefusal("EPOCH_INTERRUPTED_MODEL_ATTEMPT")
        if self.count() >= self.limit:
            raise EpochTransportRefusal("EPOCH_MODEL_BUDGET_EXHAUSTED")
        with self.lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self.context_store is not None:
                expected = {
                    **expected,
                    "request_archive": self.context_store.archive_request(payload, schema, self.identity),
                }
            record(intent, expected)
            try:
                raw = self.transport(payload, schema)
            except ModelTransportError as error:
                record(result, {"code": error.code})
                raise
            record(result, {"raw_output": raw})
        return raw

    def count(self):
        return sum(1 for _ in self.directory.glob(self.label + "-*.intent.json"))


def make_question(candidate, identity, bank):
    [request] = make_questions(candidate, ((identity, bank),))
    return request


def make_questions(candidate, coordinates):
    """Prepare independent questions from a single read snapshot and evidence scan."""
    coordinates = tuple(coordinates)
    requests = []
    with closing(connect(candidate)) as conn:
        conn.execute("BEGIN")
        rules = _relations(_metadata(conn, "relations"))
        observations, evidence = _contexts(conn, tuple(identity for identity, _ in coordinates))
        for identity, bank in coordinates:
            definition, assertions, restrictions, _ = _entry(conn, identity)
            context = lexical_context(definition, observations[identity], rules)
            state = resolve_dictionary(
                BANKS,
                assertions,
                rules,
                context,
                evidence_banks=tuple(sorted(evidence[identity])),
                domain_restrictions=restrictions,
            )
            requests.append(
                build_request(
                    identity,
                    bank,
                    state,
                    tuple(observations[identity]),
                    definition=definition,
                    relations=rules,
                    context=context,
                )
            )
    return tuple(requests)


def teach(base, working, selected, family, transport, directory):
    receipt_file = directory / "teaching.json"
    if receipt_file.exists():
        return read(receipt_file)
    identity, bank = selected["entry_id"], selected["bank"]
    request = make_question(base, identity, bank)
    try:
        raw = transport(request.payload(), request.output_schema())
    except (ModelTransportError, EpochTransportRefusal) as error:
        result = {"code": "TEACHING_TRANSPORT_REFUSAL", "reason": error.code, "request_id": request.request_id}
        record(receipt_file, result)
        return result
    try:
        value = _read_value(raw, request)
    except (ValueError, TypeError) as error:
        result = {
            "code": "TEACHING_INVALID_OUTPUT",
            "reason": str(error),
            "request_id": request.request_id,
        }
        record(receipt_file, result)
        return result
    if value is None:
        result = {"code": "TEACHING_ABSTAINED", "request_id": request.request_id}
        record(receipt_file, result)
        return result
    snapshot_copy(base, working)

    def accepted_receipt():
        with closing(connect(working)) as conn:
            return next(
                (r for r in read_model_receipts(conn).get(identity, ()) if r["request_id"] == request.request_id), None
            )

    receipt = accepted_receipt()
    if receipt is None:
        written = complete_dictionary(
            working,
            transport,
            1,
            entry_bank_questions=((identity, bank),),
            continue_cohorts=True,
            max_calls_per_entry=1,
            max_entries_per_pass=1,
            priority="zipf",
            progress=lambda item: print(json.dumps(item), flush=True),
        )
        record(directory / "typed-writer.json", written)
        receipt = accepted_receipt()
        if written["outcomes"] != {"ASSIGNED": 1} or receipt is None:
            result = {
                "code": "TEACHING_WRITER_REFUSED",
                "outcomes": written["outcomes"],
                "request_id": request.request_id,
            }
            record(receipt_file, result)
            return result
    if identity_form(receipt["request"]) != identity_form(request.payload()) or receipt["assertion"]["value"] != value:
        raise ValueError("EPOCH_TEACHING_RECEIPT_CHANGED")
    result = {
        "code": "TYPED_TEACHING"
        if family is None
        else "REVIEWED_TEACHING"
        if value in family.allowed_consequents
        else "REVIEWED_TEACHING_COUNTEREXAMPLE",
        "request_id": request.request_id,
        "receipt_sha256": _request_id(receipt),
        "value": value,
        "proposal_outcome": "NO_PROPOSED_ANSWER"
        if family is None
        else "AGREEMENT"
        if value in family.allowed_consequents
        else "COUNTEREXAMPLE",
    }
    record(receipt_file, result)
    return result


def reviewed_input(candidate, family, selected, taught, *, prefix_reviews=()):
    warrant = family.warrant
    selection = {
        "format": "GSE.reviewed-pattern-selection/1",
        "discovery_entry_ids": [selected["entry_id"]],
        "audit_entry_ids": list(family.holdouts),
        "guarded_candidates": [family.proposal()],
        "reviews": [
            {
                "request_id": taught["request_id"],
                "review": {
                    "code": "ACCEPTED",
                    "receipt_sha256": taught["receipt_sha256"],
                    "review_id": f"epoch:{family.id}:{selected['entry_id']}",
                    "reviewer": warrant["reviewer"],
                    "source_refs": warrant["source_refs"],
                    "rationale": warrant["statement"],
                },
            },
            *prefix_reviews,
        ],
    }
    exported = export_reviewed_input(candidate, selection)
    # Explicit reviews of the exact prior model prefix are required. A new
    # law's warrant is not independent review of arbitrary earlier answers.
    target = next((row for row in exported["inventory"] if row["request_id"] == taught["request_id"]), None)
    if target is None:
        raise ValueError("LEARNING_TEACHING_RECEIPT_NOT_ACTIVE")
    reviewed = {row["request_id"] for row in selection["reviews"]}
    required = set(target["dependency_request_ids"])
    if not required <= reviewed:
        raise ValueError("LEARNING_MODEL_PREFIX_REVIEW_REQUIRED:" + ",".join(sorted(required - reviewed)))
    return exported["input"]


def pair_discovery(raw, family):
    discovery = {key: value for key, value in raw.items() if key not in {"guarded_candidates", "candidates"}}
    report = run_workflow_input({**discovery, "audit_entry_ids": []})
    [observed] = [
        candidate
        for candidate in report["candidates"]
        if candidate["antecedent"] == family.antecedent and candidate["consequent"] == family.consequent
    ]
    if observed["proposal_kind"] != "OBSERVED_PAIR" or observed["discovery_outcomes"] != {"OBSERVED_AGREEMENT": 1}:
        raise ValueError("EPOCH_TEACHING_DID_NOT_DISCOVER_RULE")
    return {**observed, "observed_candidates_generated": len(report["candidates"])}


def epoch_discovery(raw, family, families):
    relevant_banks = {bank for item in families.values() for bank, _ in item.antecedents}
    report = discover_reviewed_groundings(raw, relevant_banks)
    if family.allowed_values:
        [observed] = run_workflow_input({**raw, "audit_entry_ids": []})["candidates"]
        if observed["discovery_outcomes"] != {"OBSERVED_AGREEMENT": 1}:
            raise ValueError("EPOCH_TEACHING_DID_NOT_DISCOVER_EXCLUSION")
        return report, observed
    if family.premises:
        required = set(family.premises)
        matches = [
            candidate
            for candidate in report["conjunctions"]
            if set(candidate["premises"]) == required and candidate["consequent"] == family.consequent
        ]
        if len(matches) != 1 or matches[0]["counterexamples"]:
            raise ValueError("EPOCH_TEACHING_DID_NOT_DISCOVER_CONJUNCTION")
        return report, matches[0]
    if family.antecedent is None:
        [observed] = run_workflow_input({**raw, "audit_entry_ids": []})["candidates"]
        if observed["discovery_outcomes"] != {"OBSERVED_AGREEMENT": 1}:
            raise ValueError("EPOCH_TEACHING_DID_NOT_DISCOVER_GUARDED_RULE")
        return report, observed
    return report, pair_discovery(raw, family)


def exact_delta(before, after):
    with closing(connect(after)) as conn:
        conn.execute("ATTACH DATABASE ? AS prior", (before.resolve().as_uri() + "?mode=ro",))
        conn.execute("BEGIN")
        n, m, shared = conn.execute(
            "SELECT (SELECT count(*) FROM main.definition_states),"
            "(SELECT count(*) FROM prior.definition_states),count(*) "
            "FROM main.definition_states JOIN prior.definition_states USING(entry_id)"
        ).fetchone()
        if n != m or n != shared:
            raise ValueError("EPOCH_DEFINITION_POPULATION_CHANGED")
        changes = []
        for entry, old, new in conn.execute(
            "SELECT a.entry_id,b.domains,a.domains FROM main.definition_states a "
            "JOIN prior.definition_states b USING(entry_id) WHERE a.domains<>b.domains ORDER BY a.entry_id"
        ):
            old, new = json.loads(old), json.loads(new)
            changes.extend(
                {"entry_id": entry, "bank": bank, "before": old[bank], "after": new[bank]}
                for bank in BANKS
                if old[bank] != new[bank]
            )
    return n, changes


def premise_dependencies(candidate, inventory, selected, admitted):
    identity = selected["entry_id"]
    premises = selected.get("premises", [] if selected.get("premise") is None else [selected["premise"]])
    if not premises:
        return []
    rules, rows = scope_rows(candidate, (inventory[identity],))
    row = rows[identity]
    if not premises_proved(row[-1], premises):
        raise ValueError("EPOCH_PREMISE_NO_LONGER_PROVED")
    return [
        previous
        for previous in admitted
        if not premises_proved(
            _domains(_resolve(row, tuple(rule for rule in rules if rule.rule_id != previous["rule_id"]))), premises
        )
    ]


def admit_and_migrate(working, output, directory, raw, audited, family, staged):
    [candidate] = audited["candidates"]
    warrant = family.warrant
    review = {
        "rule_id": candidate["relation"]["rule_id"],
        "warrant_sha256": candidate["warrant_sha256"],
        "review_id": f"epoch-admission:{family.id}",
        "reviewer": warrant["reviewer"],
        "decision": "APPROVE_DEFINITIONAL_RULE",
        "source_refs": warrant["source_refs"],
        "rationale": warrant["statement"],
    }
    admission = admit_records(raw, audited, review)
    record(directory / "admission-review.json", review)
    migration_file = directory / "migration.json"
    if not output.exists():
        report = migrate_revision(
            working,
            output,
            {
                "format": REVISION_FORMAT,
                "baseline_version": admission["baseline_version"],
                "admissions": [admission],
                "retirements": [],
                "exceptions": [],
            },
        )
        record(migration_file, report)
    if migration_file.exists():
        replay = read(migration_file)["postflight"]
    else:
        # Output publication is atomic. If interrupted after installing the
        # copy, reconstruct the replay receipt from the installed snapshot.
        replay = validate_build(output)
        record(directory / "recovered-replay.json", replay)
    if replay["code"] != "REPLAY_VALIDATED" or not replay["complete_search"]:
        raise ValueError("EPOCH_MIGRATION_REPLAY_FAILED")
    with closing(connect(output)) as conn:
        rules = _relations(_metadata(conn, "relations"))
        [expected] = _relations(json.loads(json.dumps([admission["relation"]])))
        if expected not in rules:
            raise ValueError("EPOCH_MIGRATION_RULE_MISSING")
    count, observed = exact_delta(working, output)

    def by_cell(rows):
        return {(r["entry_id"], r["bank"]): r for r in rows}

    if by_cell(observed) != by_cell(staged["changes"]):
        raise ValueError("EPOCH_MIGRATION_DELTA_DIFFERS_FROM_STAGE")
    return {
        "rule_id": expected.rule_id,
        "definitions_replayed": count,
        "replay": replay,
        "symbolic_new_cells": len(gains({"changes": observed})),
    }


def run_arm(plan, baseline, active_pointer, directory, inventory, policy, transport, lock_path):
    from .learning_curriculum import (
        choose_open,
        curriculum,
        refresh_reviews,
        retain_discoveries,
        reviewed_choice,
    )

    families = parse_plan(plan)
    inventory = dict(inventory)
    opening_inventory_keys = set(inventory)
    dynamic = curriculum(plan)
    if policy not in POLICIES:
        raise ValueError("INVALID_EPOCH_POLICY")
    if fingerprint(baseline) != plan["baseline_sha256"] or fingerprint(active_pointer) != plan["active_pointer_sha256"]:
        raise ValueError("EPOCH_FROZEN_INPUT_MISMATCH")
    directory.mkdir(exist_ok=True)
    priority, frequencies = _priority_source("zipf", None)
    configuration = {
        "policy": policy,
        "contract": CONTRACT,
        "plan_sha256": digest(plan),
        "inventory_sha256": digest(inventory),
        "frequency_sha256": priority["sha256"],
        "transport": transport.identity,
    }
    if dynamic:
        from .learning_refinement import provider_identity

        configuration["learning_protocol"] = {
            "files": {
                str(path.relative_to(Path(__file__).parents[2])): fingerprint(path)
                for path in (*sorted(Path(__file__).parent.glob("*.py")), Path(__file__).parents[2] / "namespace.py")
            },
            "guard_imputer": provider_identity(),
        }
    record(directory / "arm.json", configuration)
    report_path = directory / "arm-result.json"
    if report_path.exists():
        result = read(report_path)
        if (
            result["plan_sha256"] != digest(plan)
            or result["policy"] != policy
            or fingerprint(Path(result["candidate"])) != result["candidate_sha256"]
            or fingerprint(active_pointer) != plan["active_pointer_sha256"]
            or fingerprint(baseline) != plan["baseline_sha256"]
            or result["replay"]["code"] != "REPLAY_VALIDATED"
            or not result["replay"]["complete_search"]
        ):
            raise ValueError("EPOCH_RESULT_SNAPSHOT_CHANGED")
        return result
    learning = LearningState(directory / "learning.sqlite", configuration)
    if dynamic:
        learning.initialize_head(baseline, plan["baseline_sha256"])
        head = learning.head()
        if fingerprint(Path(head["candidate"])) != head["candidate_sha256"]:
            raise ValueError("LEARNING_WORKING_HEAD_CHANGED")
    completed = {row["epoch"]: row for row in learning.epochs()} if dynamic else {}
    for item in plan["families"]:
        family = families[item["id"]]
        identity = learning.propose(family.relation(), {"warrant": family.warrant}, origin="DECLARED_CURRICULUM")
        learning.review(identity, family.relation(), item)
    used, done, challenged, reports, admitted = set(), set(), set(), [], []
    base = baseline
    waiting_review = False
    frontier_exhausted = False
    everyone = {row["entry_id"]: row for group in inventory.values() for row in group}
    holdout = plan.get("evaluation_holdout")
    if holdout:
        held_lemmas = {lemma.casefold() for lemma in holdout["lemmas"]}
        held_senses = {_sense_group(everyone[entry]) for entry in holdout["entries"] if entry in everyone}
        if any(
            everyone[entry]["lemma"].casefold() in held_lemmas or _sense_group(everyone[entry]) in held_senses
            for family in families.values()
            for entry in family.holdouts
        ):
            raise ValueError("EPOCH_AUDIT_OVERLAPS_EVALUATION_HOLDOUT")
    question_holdout = holdout
    if dynamic:
        reserved = set(dynamic["audit_entry_ids"])
        if any(not set(family.holdouts) <= reserved for family in families.values()):
            raise ValueError("LEARNING_AUDIT_OUTSIDE_RESERVED_POOL")
        if not reserved <= everyone.keys():
            raise ValueError("LEARNING_RESERVED_AUDIT_IDENTITY_MISSING")
        if holdout and any(
            everyone[i]["lemma"].casefold() in held_lemmas or _sense_group(everyone[i]) in held_senses for i in reserved
        ):
            raise ValueError("LEARNING_AUDIT_OVERLAPS_EVALUATION_HOLDOUT")
        question_holdout = {
            "entries": sorted(reserved | set((holdout or {}).get("entries", ()))),
            "lemmas": list((holdout or {}).get("lemmas", ())),
        }
    for epoch in range(1, plan["epochs"] + 1):
        refresh_reviews(plan, baseline, directory, learning, families, inventory)
        everyone = {row["entry_id"]: row for group in inventory.values() for row in group}
        if dynamic and not set(dynamic["audit_entry_ids"]) <= everyone.keys():
            raise ValueError("LEARNING_RESERVED_AUDIT_IDENTITY_MISSING")
        phase = directory / f"epoch-{epoch:02d}"
        phase.mkdir(exist_ok=True)
        finished = phase / "result.json"
        outcome: dict[str, Any]
        if epoch in completed:
            # Historical phase databases may already have been retired. The
            # content-addressed ledger, not their old byte paths, is authority.
            outcome = completed[epoch]
            if finished.exists() and read(finished) != outcome:
                raise ValueError("LEARNING_EPOCH_FILE_CHANGED")
        elif finished.exists():
            outcome = read(finished)
        else:
            pick_file = phase / "selection.json"
            ready = {row["mechanism_id"] for row in learning.ready()}
            pending_review = {key for key, family in families.items() if mechanism_id(family.relation()) not in ready}
            if pick_file.exists():
                selected = read(pick_file)
            else:
                if dynamic:
                    from .learning_feedback import refresh_intake, revision_choice

                    refresh_intake(directory, learning)
                    selected = revision_choice(base, learning)
                else:
                    selected = None
                selected = selected or (
                    reviewed_choice(base, learning, families, inventory, done | challenged, policy, frequencies)
                    if dynamic
                    else None
                )
                if selected is None:
                    selected = choose(
                        base,
                        inventory,
                        families,
                        done | challenged | pending_review,
                        used,
                        policy,
                        frequencies,
                        question_holdout,
                        plan.get("teaching_entry_ids"),
                    )
                if selected is None and dynamic:
                    attempted = {
                        (report["selected"]["entry_id"], report["selected"]["bank"])
                        for report in reports
                        if report.get("selected", {}).get("entry_id")
                    }
                    selected = choose_open(base, plan, inventory, families, attempted, policy, frequencies)
            if selected is None and dynamic and learning.pending():
                # Do not seal an empty epoch or a completed arm while an
                # observed mechanism awaits warrant/refinement. The same frozen
                # run can receive reviews and continue from this boundary.
                waiting_review = True
                break
            if selected is None and dynamic:
                frontier_exhausted = True
                break
            record(pick_file, selected)
            if selected is None:
                outcome = {"code": "NO_ELIGIBLE_QUESTION", "epoch": epoch, "candidate": str(base)}
            else:
                outcome = run_epoch(
                    plan,
                    base,
                    phase,
                    inventory,
                    everyone,
                    families,
                    selected,
                    admitted,
                    transport,
                    lock_path,
                    question_store=learning if dynamic else None,
                )
                outcome["epoch"] = epoch
            outcome["candidate_sha256"] = fingerprint(Path(outcome["candidate"]))
            record(finished, outcome)
        if dynamic:
            if epoch not in completed:
                current = learning.head()
                candidate = Path(outcome["candidate"])
                if fingerprint(candidate) != outcome["candidate_sha256"]:
                    raise ValueError("LEARNING_WORKING_HEAD_CHANGED")
                staging = [
                    {"path": str(path.absolute()), "sha256": fingerprint(path)}
                    for name in ("teaching.db", "candidate.db")
                    if (path := phase / name).is_file()
                ]
                learning.advance_head(
                    outcome,
                    {
                        "format": "GSE.lexicon-learning-transition/1",
                        "epoch": epoch,
                        "prior_head": current,
                        "candidate": outcome["candidate"],
                        "candidate_sha256": outcome["candidate_sha256"],
                        "outcome_sha256": digest(outcome),
                        "staging": staging,
                    },
                )
        else:
            learning.record_epoch(epoch, outcome)
        retain_discoveries(learning, outcome)
        if dynamic:
            from .learning_feedback import retain_feedback

            retain_feedback(learning, outcome)
        base = Path(outcome["candidate"])
        if (not dynamic or epoch == learning.head()["epoch"]) and fingerprint(base) != outcome["candidate_sha256"]:
            raise ValueError("EPOCH_RESULT_SNAPSHOT_CHANGED")
        if outcome.get("selected", {}).get("entry_id"):
            lemma = everyone[outcome["selected"]["entry_id"]]["lemma"].casefold()
            used.update(_sense_group(row) for row in everyone.values() if row["lemma"].casefold() == lemma)
        if outcome["code"] == "RULE_ADMITTED":
            done.add(outcome["selected"]["family"])
            admitted.append({"epoch": epoch, "family": outcome["selected"]["family"], "rule_id": outcome["rule_id"]})
            learning.disposition(
                mechanism_id(families[outcome["selected"]["family"]].relation()),
                "ADMITTED",
                {"epoch": epoch, "rule_id": outcome["rule_id"]},
            )
            if dynamic:
                child = mechanism_id(families[outcome["selected"]["family"]].relation())
                dispositions = {row["mechanism_id"]: row["disposition"] for row in learning.reviewed()}
                for witness in learning.witnesses(child):
                    parent = witness["evidence"].get("parent_mechanism_id")
                    if parent and dispositions.get(parent) in {"NEEDS_REFINEMENT", "AWAITING_AUDIT_REVIEW"}:
                        learning.disposition(
                            parent,
                            "RETIRED",
                            {
                                "code": "UNADMITTED_PARENT_REPLACED",
                                "child": child,
                                "epoch": epoch,
                                "rule_id": outcome["rule_id"],
                            },
                        )
        elif outcome["code"] in {
            "RULE_CHALLENGED_BY_TEACHING",
            "RULE_WITHHELD_SCOPE_CONTRADICTION",
            "RULE_WITHHELD_INDEPENDENT_AUDIT",
        }:
            challenged.add(outcome["selected"]["family"])
            learning.disposition(
                mechanism_id(families[outcome["selected"]["family"]].relation()),
                "AWAITING_AUDIT_REVIEW" if outcome["code"] == "RULE_WITHHELD_INDEPENDENT_AUDIT" else "NEEDS_REFINEMENT",
                {"epoch": epoch, "code": outcome["code"], "outcome_sha256": digest(outcome)},
            )
        elif outcome["code"] == "RULE_AWAITING_MODEL_PREFIX_REVIEW":
            learning.disposition(
                mechanism_id(families[outcome["selected"]["family"]].relation()),
                "AWAITING_PREFIX_REVIEW",
                {"epoch": epoch, "reason": outcome["reason"]},
            )
        if outcome.get("selected", {}).get("task") == "REVIEWED_RULE_REVISION":
            learning.finish_work(
                outcome["selected"]["work_sha256"], {"epoch": epoch, "outcome_sha256": digest(outcome)}
            )
        reports.append(outcome)
        if dynamic and epoch == learning.head()["epoch"]:
            from .retention import retire_learning_stages

            retire_learning_stages(learning, baseline, plan["baseline_sha256"])
        print(
            json.dumps(
                {
                    "policy": policy,
                    "epoch": epoch,
                    "code": outcome["code"],
                    "family": outcome.get("selected", {}).get("family"),
                    "symbolic_new_cells": outcome.get("symbolic_new_cells", 0),
                }
            ),
            flush=True,
        )
    if not reports or reports[-1]["code"] != "RULE_ADMITTED":
        replay = validate_build(base)
    else:
        replay = reports[-1]["replay"]
    if replay["code"] != "REPLAY_VALIDATED" or not replay["complete_search"]:
        raise ValueError("EPOCH_FINAL_REPLAY_FAILED")
    definitions, changes = exact_delta(baseline, base)
    if fingerprint(active_pointer) != plan["active_pointer_sha256"] or fingerprint(baseline) != plan["baseline_sha256"]:
        raise ValueError("EPOCH_FROZEN_INPUT_CHANGED")
    final_grounding = mine_scope_chains(base, inventory)
    grounding_path = directory / (
        "grounded-chains-observation-" + digest(final_grounding) + ".json"
        if waiting_review
        else "grounded-chains-final.json"
    )
    record(grounding_path, final_grounding)
    result = {
        "format": "GSE.lexicon-epoch-arm/1",
        **(
            {
                "code": "LEARNING_REVIEW_REQUIRED"
                if waiting_review
                else "LEARNING_DECLARED_FRONTIER_EXHAUSTED"
                if frontier_exhausted
                else "LEARNING_EPOCH_LIMIT_REACHED"
            }
            if dynamic
            else {}
        ),
        "policy": policy,
        "candidate": str(base),
        "candidate_sha256": fingerprint(base),
        "definitions_compared": definitions,
        "plan_sha256": digest(plan),
        "active_pointer_sha256": plan["active_pointer_sha256"],
        "epochs": reports,
        "admitted": admitted,
        "pending_challenges": [
            {"epoch": report["epoch"], "family": report["selected"]["family"], "code": report["code"]}
            for report in reports
            if report.get("selected", {}).get("family") in challenged
        ],
        "learning_state": {"format": "GSE.lexicon-learning-state/1", "pending": learning.pending()},
        **(
            {
                "learned_inventory": {
                    key: {
                        "sha256": digest(rows),
                        "path": str(directory / ("inventory-" + mechanism_id(families[key].relation()) + ".json")),
                    }
                    for key, rows in inventory.items()
                    if key not in opening_inventory_keys
                },
                "semantic_reviews": sum(
                    row["family"]["id"] not in {item["id"] for item in plan["families"]} for row in learning.reviewed()
                ),
            }
            if dynamic
            else {}
        ),
        "grounded_chain_proposals": len(final_grounding["proposals"]),
        "changes": changes,
        "new_cells": len(gains({"changes": changes})),
        "reopened_cells": sum(len(row["before"]) == 1 and len(row["after"]) > 1 for row in changes),
        "typed_question_budget": plan["epochs"] * (1 + plan["audits_per_epoch"]),
        "typed_questions_used": sum(report.get("typed_questions_used", 0) for report in reports),
        "replay": replay,
        "publication": publication_readiness(base),
        "activation_performed": False,
    }
    if waiting_review:
        record(directory / ("review-pending-" + digest(result) + ".json"), result)
        return result
    record(report_path, result)
    return read(report_path)


def learn_reviewed_rule(
    plan, working, output, phase, inventory, families, selected, taught, auditing, *, prefix_reviews=()
):
    """Discover and independently audit the proposed rule after confirming teaching."""
    family = families[selected["family"]]
    outcome = {"code": "RULE_WITHHELD", "candidate": str(working)}
    raw_file = phase / "reviewed-input.json"
    try:
        raw = (
            read(raw_file)
            if raw_file.exists()
            else reviewed_input(working, family, selected, taught, prefix_reviews=prefix_reviews)
        )
    except ValueError as error:
        if str(error).startswith(("LEARNING_MODEL_PREFIX_REVIEW_REQUIRED:", "LEARNING_TEACHING_RECEIPT_NOT_ACTIVE")):
            return {**outcome, "code": "RULE_AWAITING_MODEL_PREFIX_REVIEW", "reason": str(error)}
        raise
    record(raw_file, raw)
    grounding, observed = epoch_discovery(raw, family, families)
    record(phase / "grounded-discovery.json", grounding)
    discovery_kind = "conjunction" if family.premises else "pair" if family.antecedent is not None else "guard"
    record(phase / f"observed-{discovery_kind}.json", observed)
    rules, rows = scope_rows(working, inventory[family.id])
    staged = forecast(rows, rules, (family.relation(),))
    record(phase / "staged.json", staged)
    if staged["contradictions"]:
        outcome["code"] = "RULE_WITHHELD_SCOPE_CONTRADICTION"
        outcome["scope_surprises"] = staged["contradictions"]
    elif staged["progress_code"] == "CONTRACTION":
        audit_file = phase / "audit.json"
        audited = (
            read(audit_file)
            if audit_file.exists()
            else run_workflow_input(raw, auditing, max_calls=plan["audits_per_epoch"])
        )
        record(audit_file, audited)
        [report] = audited["candidates"]
        outcome["audit_outcomes"] = report["audit_outcomes"]
        if report["audit_outcomes"] == {"MODEL_AGREEMENT": plan["audits_per_epoch"]} and all(
            row["code"] == "STAGED_ONLY" for row in report["staging"]
        ):
            migration = admit_and_migrate(working, output, phase, raw, audited, family, staged)
            outcome.update(migration, code="RULE_ADMITTED", candidate=str(output))
        else:
            outcome["code"] = "RULE_WITHHELD_INDEPENDENT_AUDIT"
    return outcome


def run_epoch(
    plan, base, phase, inventory, everyone, families, selected, admitted, transport, lock_path, *, question_store=None
):
    from .learning_curriculum import discover_teaching

    if selected.get("task") == "REVIEWED_RULE_REVISION":
        from .learning_feedback import apply_revision

        return apply_revision(base, phase, selected)

    family = families.get(selected["family"])
    parents = premise_dependencies(base, everyone, selected, admitted)
    outcome = {
        "code": "TEACHING_NOT_ACCEPTED",
        "selected": selected,
        "candidate": str(base),
        "premise_depends_on": parents,
    }
    teaching = JournaledTransport(transport, phase, "teach", 1, lock_path, context_store=question_store)
    auditing = JournaledTransport(
        transport, phase, "audit", plan["audits_per_epoch"], lock_path, context_store=question_store
    )
    working, output = (phase / name for name in ("teaching.db", "candidate.db"))
    if selected.get("reviewed_teaching"):
        working = base
    baseline_measurement_path = phase / "space-baseline.json"
    if not baseline_measurement_path.exists():
        record(baseline_measurement_path, measure_dictionary(base))
    baseline_measurement = read(baseline_measurement_path)
    taught = selected.get("reviewed_teaching") or teach(base, working, selected, family, teaching, phase)
    outcome["teaching"] = taught
    teaching_measurement = baseline_measurement
    if taught["code"] in {"TYPED_TEACHING", "REVIEWED_TEACHING", "REVIEWED_TEACHING_COUNTEREXAMPLE"}:
        teaching_measurement_path = phase / "space-post-teaching.json"
        if not teaching_measurement_path.exists():
            record(teaching_measurement_path, measure_dictionary(working))
        teaching_measurement = read(teaching_measurement_path)
        outcome["candidate"] = str(working)
        if not selected.get("reviewed_teaching"):
            outcome["discoveries"] = discover_teaching(base, plan, inventory, selected, taught)
            record(phase / "teaching-discovery.json", outcome["discoveries"])
            if plan.get("curriculum"):
                limit = plan["curriculum"]["candidate_limit"]
                outcome["discovery_search"] = {
                    "language": "SCOPED_UNARY_AND_SIGNED_CONJUNCTIONS_UP_TO_THREE_PREMISES",
                    "candidate_limit": limit,
                    "candidates": len(outcome["discoveries"]),
                    "code": "BOUND_REACHED_NOT_SEMANTIC_EXHAUSTION"
                    if len(outcome["discoveries"]) == limit
                    else "DECLARED_LANGUAGE_ENUMERATED_FOR_THIS_OBSERVATION",
                }
        if family is None:
            outcome["code"] = "TEACHING_RETAINED_FOR_DISCOVERY"
        elif taught["code"] == "REVIEWED_TEACHING_COUNTEREXAMPLE":
            surprise = {
                "code": "TEACHING_COUNTEREXAMPLE_REQUIRES_REFINEMENT",
                "entry_id": selected["entry_id"],
                "bank": selected["bank"],
                "expected_values": list(family.allowed_consequents),
                "observed_value": taught["value"],
                "request_id": taught["request_id"],
                "receipt_sha256": taught["receipt_sha256"],
                "parent": family.proposal(),
                "authority": "BOUNDED_MODEL_EVIDENCE_REQUIRES_SCOPE_REVIEW",
            }
            record(phase / "teaching-counterexample.json", surprise)
            outcome.update(code="RULE_CHALLENGED_BY_TEACHING", surprise=surprise)
        else:
            prefix_reviews = selected.get("prefix_reviews", ())
            if question_store is not None:
                prefix_reviews = [
                    {"request_id": row["payload"]["receipt"]["request_id"], "review": row["payload"]["review"]}
                    for row in question_store.work(kind="MODEL_PREFIX_REVIEW", disposition="READY")
                    if row["payload"]["receipt"]["entry_id"] == selected["entry_id"]
                    and row["payload"]["receipt"]["request_id"] != taught["request_id"]
                ]
            outcome.update(
                learn_reviewed_rule(
                    plan,
                    working,
                    output,
                    phase,
                    inventory,
                    families,
                    selected,
                    taught,
                    auditing,
                    prefix_reviews=prefix_reviews,
                )
            )
            if outcome["code"] == "RULE_WITHHELD_INDEPENDENT_AUDIT" and plan.get("curriculum"):
                from .learning_refinement import propose_refinements

                refined = propose_refinements(
                    read(phase / "reviewed-input.json"),
                    read(phase / "audit.json"),
                    family,
                    selected,
                    taught,
                    everyone[selected["entry_id"]],
                )
                record(phase / "guard-refinement.json", refined)
                outcome["refinement"] = refined
                outcome.setdefault("discoveries", []).extend(refined["candidates"])
    final_measurement = teaching_measurement
    if outcome["code"] == "RULE_ADMITTED":
        revision_measurement_path = phase / "space-post-revision.json"
        if not revision_measurement_path.exists():
            record(revision_measurement_path, measure_dictionary(output))
        final_measurement = read(revision_measurement_path)
    outcome["specification_learning"] = {
        "contract": CONTRACT,
        "baseline": baseline_measurement,
        "post_teaching": teaching_measurement,
        "post_revision": final_measurement,
        "direct_teaching": compare_measurements(baseline_measurement, teaching_measurement),
        "rule_revision": compare_measurements(teaching_measurement, final_measurement),
        "total": compare_measurements(baseline_measurement, final_measurement),
    }
    outcome["typed_questions_used"] = teaching.count() + auditing.count()
    return outcome
