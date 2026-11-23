"""Mine signed rule hypotheses while retaining their independent evidence roots."""

from collections import defaultdict
from itertools import combinations, product

SIGNS = (-1, 0, 1)
MAX_PREMISES = 3


def implication_rows(premises, consequent):
    """All ternary rows except violations of the declared signed implication."""
    required = tuple(value for _, value in premises)
    return tuple(
        row for row in product(SIGNS, repeat=len(required) + 1) if row[:-1] != required or row[-1] == consequent[1]
    )


def forward_implication(rule):
    """Recognize a total forward implication from its table, with no direction guess."""
    if not rule.approved or not 2 <= len(rule.banks) <= MAX_PREMISES + 1:
        return None
    missing = sorted(set(product(SIGNS, repeat=len(rule.banks))) - set(rule.allowed_rows))
    if len(missing) != 2:
        return None
    changed = [index for index, (a, b) in enumerate(zip(*missing, strict=True)) if a != b]
    if len(changed) != 1:
        return None
    [target] = changed
    [sign] = sorted(set(SIGNS) - {row[target] for row in missing})
    return (
        tuple((bank, missing[0][i]) for i, bank in enumerate(rule.banks) if i != target),
        (rule.banks[target], sign),
    )


def grounded_chains(trace, relations, assignments):
    """Propose compositions of actual forward proof steps with lexical roots."""
    rules = {rule.rule_id: rule for rule in relations}
    proofs = {}
    proposals = []
    for step in trace:
        if step["kind"] == "ASSERTION":
            if step.get("scope") != "lexical" or step.get("family") == "model" or step["source"].startswith("model:"):
                continue
            bank, value = step["bank"], step["value"]
            if assignments.get(bank) == value:
                proofs[bank, value] = (
                    {(bank, value, step["source"], step["record_id"])},
                    (),
                )
            continue
        if step["kind"] != "RELATION" or len(step["remaining"]) != 1:
            continue
        rule = rules.get(step["rule_id"])
        implication = forward_implication(rule) if rule is not None else None
        if implication is None:
            continue
        premises, target = implication
        if (
            target != (step["bank"], step["remaining"][0])
            or assignments.get(target[0]) != target[1]
            or any(
                tuple(step["domains_before"].get(bank, ())) != (value,) or (bank, value) not in proofs
                for bank, value in premises
            )
        ):
            continue
        roots = set().union(*(proofs[literal][0] for literal in premises))
        chain = tuple(dict.fromkeys((*(r for literal in premises for r in proofs[literal][1]), step["rule_id"])))
        if target in {(bank, value) for bank, value, _, _ in roots}:
            continue
        proofs[target] = (roots, chain)
        if len(chain) < 2:
            continue
        proposals.append(
            {
                "code": "GROUNDED_CHAIN_HYPOTHESIS",
                "premises": sorted({(bank, value) for bank, value, _, _ in roots}),
                "consequent": target,
                "evidence_roots": sorted(roots),
                "rule_ids": list(chain),
                "guards": sorted({guard for rule_id in chain for guard in rules[rule_id].guards}),
                "absent_evidence": sorted({bank for rule_id in chain for bank in rules[rule_id].absent_evidence}),
                "authority": "OBSERVED_PROOF_COMPOSITION_REQUIRES_INDEPENDENT_AUDIT",
            }
        )
    return proposals


def observed_conjunctions(examples, *, max_premises=MAX_PREMISES):
    """Enumerate bounded signed conjunctions from baseline and reviewed targets.

    A missing premise supplies no support. Proper-subset opposition is recorded
    only where an independent reviewed target is actually available.
    """
    if type(max_premises) is not int or not 2 <= max_premises <= MAX_PREMISES:
        raise ValueError("INVALID_CONJUNCTION_WIDTH")
    candidates = defaultdict(list)
    for example in examples:
        bank, value = example["consequent"]
        if bank in example["baseline"]:
            continue
        literals = sorted(example["baseline"].items())
        for width in range(2, max_premises + 1):
            for premises in combinations(literals, width):
                candidates[premises, bank, value].append(example)
    reports = []
    for (premises, bank, value), support in sorted(candidates.items()):
        oppositions, subset_oppositions = [], []
        for example in examples:
            other, observed = example["consequent"]
            if other != bank or observed == value or bank in example["baseline"]:
                continue
            matched = tuple(literal for literal in premises if example["baseline"].get(literal[0]) == literal[1])
            receipt = {"entry_id": example["entry_id"], "matched_premises": matched, "value": observed}
            if matched == premises:
                oppositions.append(receipt)
            elif matched:
                subset_oppositions.append(receipt)
        reports.append(
            {
                "code": "OBSERVED_CONJUNCTION",
                "premises": premises,
                "consequent": (bank, value),
                "support": support,
                "counterexamples": oppositions,
                "proper_subset_counterexamples": subset_oppositions,
                "authority": "REVIEWED_OBSERVATION_REQUIRES_DEFINITIONAL_WARRANT",
            }
        )
    return reports


def discover_reviewed_groundings(raw, premise_banks, *, max_premises=MAX_PREMISES):
    """Replay a reviewed export and separate grounded premises from teaching labels."""
    from .foundation import BANKS
    from .resolution import resolve_dictionary
    from .reviewed_patterns import _baseline_witness, _definition_input, _relation, reviewed_rulings

    relations = tuple(_relation(record) for record in raw["relations"])
    discovery = set(raw["discovery_entry_ids"])
    entries = {
        record["definition"]["entry_id"]: _definition_input(record, relations)
        for record in raw["entries"]
        if record["definition"]["entry_id"] in discovery
    }
    examples, chains = [], []
    for entry_id, entry in entries.items():
        state = resolve_dictionary(
            BANKS,
            entry.assertions,
            relations,
            entry.context,
            evidence_banks=entry.evidence_banks,
            domain_restrictions=entry.restrictions,
        )
        if state.code == "CONFLICT" or any(row["kind"] == "SOLVER_LIMIT" for row in state.trace):
            raise ValueError("GROUNDED_DISCOVERY_REQUIRES_COMPLETE_CLOSURE")
        chains.extend(
            {"entry_id": entry_id, **item} for item in grounded_chains(state.trace, relations, state.assignments)
        )
        baseline = {bank: value for bank, value in state.assignments.items() if bank in premise_banks}
        witnesses = [_baseline_witness(state, bank, relations) for bank in sorted(baseline)]
        for ruling in reviewed_rulings(raw["rulings"]):
            if ruling.entry_id != entry_id or ruling.bank in state.assignments:
                continue
            examples.append(
                {
                    "entry_id": entry_id,
                    "consequent": (ruling.bank, ruling.value),
                    "baseline": baseline,
                    "premise_proofs": witnesses,
                    "reviewed_receipt_sha256": ruling.receipt_sha256,
                }
            )
    return {"chains": chains, "conjunctions": observed_conjunctions(examples, max_premises=max_premises)}
