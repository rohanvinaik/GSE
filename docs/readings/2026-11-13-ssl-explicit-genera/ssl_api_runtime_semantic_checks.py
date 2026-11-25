"""Post-inspection DEVELOPMENT checks over retained real consumer outcomes.

No production operation, model request, lexical assertion or source rewrite is
performed here. A nonempty tree is not counted as a meaning-preservation check.
These checks supplement, and never replace, the original failed witnesses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def nodes(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from nodes(item)


def event(predicate, verb, arguments=None):
    return any(
        n.get("op") == "EVENT"
        and n.get("features", {}).get("verb") == verb
        and (arguments is None or n.get("args") == arguments)
        for n in nodes(predicate)
    )


def semantic_checks(report):
    """Return finite positive/MUST-NOT checks with the actual retained evidence."""
    checks = []

    def check(operation, ident, required, actual, passed):
        checks.append(dict(operation=operation, id=ident, required=required, actual=actual, passed=bool(passed)))

    operations = report["operations"]
    cases = {c["id"]: c for c in operations["sentence"]}
    predicates = {k: c["contract"]["predicate"] for k, c in cases.items()}
    for ident, verb, arguments in [
        ("do-main", "do", ["nora", "work"]),
        ("have-main", "have", ["nora", "bicycle"]),
        ("have-aux", "repair", ["nora", "bicycle"]),
        ("imperative-main-do", "do", ["you", "work"]),
        ("imperative-pronoun-do", "do", ["you", "it"]),
        ("inverted-do", "repair", ["nora", "bicycle"]),
        ("inverted-pronoun-do", "work", ["it"]),
        ("aux-have-possession-leak", "eat", ["i"]),
        ("aux-be-state-leak", "run", ["she"]),
    ]:
        p = predicates[ident]
        check("sentence", ident + "-roles", [verb, arguments], p, p.get("op") == "EVENT" and event(p, verb, arguments))
    for ident in ("imperative-main-do", "imperative-pronoun-do"):
        p = predicates[ident]
        check(
            "sentence",
            ident + "-directive",
            "imperative, not asserted past fact",
            p,
            "IMPERATIVE" in p.get("features", {}).get("modal", []),
        )
    for ident in ("inverted-do", "inverted-pronoun-do"):
        claims = cases[ident]["contract"]["claim_semantics"]["claims"]
        states = [c["commitment"] for c in claims]
        check(
            "sentence",
            ident + "-question",
            "question, not asserted event",
            states,
            bool(states) and all(s == "in_question" for s in states),
        )

    for ident, anchor, subject, verb in [
        ("above", "cliff", "eagle", "fly"),
        ("below", "cliff", "eagle", "fly"),
        ("before", "sunrise", "traveler", "depart"),
    ]:
        p = predicates[ident]
        check(
            "sentence",
            ident + "-relation-anchor",
            "distinct relation wraps intransitive event; anchor is not its patient",
            p,
            p.get("features", {}).get("verb") == ident
            and p.get("args", [None])[-1] == anchor
            and event(p, verb, [subject]),
        )
    check(
        "sentence",
        "opposite-spatial-relations",
        "above and below remain distinct",
        [predicates["above"], predicates["below"]],
        predicates["above"] != predicates["below"],
    )
    p = predicates["topic-about"]
    check(
        "sentence",
        "topic-not-event",
        "think(i), about door as topic, no about event",
        p,
        event(p, "think", ["i"])
        and not event(p, "about")
        and "about the door" in p.get("features", {}).get("themes", []),
    )
    for ident, verb, patient in [("see-qualified", "see", "bright lamp"), ("hear-qualified", "hear", "ringing bell")]:
        p = predicates[ident]
        check(
            "sentence",
            ident + "-adjunct-ownership",
            "matrix sensory event retains patient and qualified adjunct",
            p,
            p.get("features", {}).get("verb") == verb
            and event(p, verb, ["nora", patient])
            and bool(p.get("features", {}).get("themes")),
        )
    for ident, sign, outer in [("not-very", -1, "TYPE_ASSERT"), ("very-not", 1, "NOT")]:
        p = predicates[ident]
        degree = [d for n in nodes(p) for d in n.get("features", {}).get("degree", [])]
        check(
            "sentence",
            ident + "-scope",
            "degree scope differs from clause negation",
            p,
            p.get("op") == outer and any(d.get("level") == sign and d.get("target") == "tall" for d in degree),
        )
    p = predicates["want"]
    check(
        "sentence",
        "control-shared-subject",
        "want controls Mira's rest, not occurrence of rest",
        p,
        p.get("op") == "CONTROL" and p.get("args", [])[:2] == ["mira", "mira"] and event(p, "rest", ["mira"]),
    )
    p = predicates["want-negative"]
    check(
        "sentence",
        "negated-control-scope",
        "negation scopes over WANT, not REST",
        p,
        p.get("op") == "NOT" and p.get("args", [{}])[0].get("op") == "CONTROL",
    )

    p = predicates["teacher-relative"]
    check(
        "sentence",
        "teacher-matrix-relative",
        "person is matrix complement; teaching belongs to person's occupation",
        p,
        p.get("op") == "TYPE_ASSERT"
        and p.get("args", [None])[0] == "teacher"
        and any(n.get("op") == "REL_RESTRICT" and n.get("args", [None])[0] == "person" for n in nodes(p))
        and any(
            n.get("op") == "TYPE_ASSERT" and n.get("args") == ["person's occupation", "teaching"] for n in nodes(p)
        ),
    )
    p = predicates["femur-modifier"]
    coordinations = [n.get("args") for n in nodes(p) if n.get("op") == "COORD"]
    check(
        "sentence",
        "femur-modifiers-attachment",
        "long/thick modify bone; of human skeleton retained, not coordinate peers",
        p,
        p.get("op") == "TYPE_ASSERT"
        and p.get("args", [None])[0] == "femur"
        and coordinations == [["long", "thick"]]
        and event(p, "of", ["bone", "human skeleton"]),
    )
    p = predicates["he-chemical-copula"]
    check(
        "sentence",
        "chemical-copula-nominal",
        "He asserted inert gas, not gas event",
        p,
        p.get("op") == "TYPE_ASSERT" and p.get("args") == ["he", "inert gas"] and not event(p, "gas"),
    )

    expected = [
        [("Event", "committed", 1), ("TypeAssertion", "non_committed", 1)],
        [("Event", "committed", 1), ("TypeAssertion", "committed", 1)],
        [("Event", "committed", -1), ("TypeAssertion", "abstained", 1)],
        [("Event", "non_committed", 1)],
        [("Event", "committed", -1)],
        [("Event", "committed", 1)],
    ]
    for index, (case, wanted) in enumerate(zip(operations["queries"]["claims"], expected, strict=True)):
        actual = [(p["kind"], p["commitment"], p["polarity"]["sign"]) for p in case["propositions"]]
        check("queries", "commitment-polarity-" + str(index), wanted, actual, actual == wanted)

    doc = operations["document"]
    predicates = [c["predicate"] for c in doc["contracts"]]
    first, second, quote = predicates
    agent0, agent1, speaker = (p["args"][0] for p in predicates)
    check(
        "document",
        "same-referent-across-paragraph",
        "she and supporting woman have same exact document entity ID",
        [agent0, agent1, doc["supporting_mentions"]],
        agent0["entity_id"] == agent1["entity_id"]
        and agent1["lemma"] == "woman"
        and any(
            m["eid"] == agent0["entity_id"] and m["source_sentence_id"] == "s0" for m in doc["supporting_mentions"]
        ),
    )
    check(
        "document",
        "quoted-speaker-binding",
        "quoted I waits here as Nora, not earlier woman",
        quote,
        quote.get("features", {}).get("verb") == "wait"
        and speaker["lemma"] == "nora"
        and speaker["entity_id"] != agent0["entity_id"]
        and "here" in quote.get("features", {}).get("themes", []),
    )
    inference = operations["inference"]
    check(
        "inference",
        "exact-type-source-set",
        "all three type premises cited, no invented source",
        inference["type"]["positive"]["source_ids"],
        set(inference["type"]["positive"]["source_ids"]) == {"type-1", "type-2", "type-3"},
    )
    check(
        "inference",
        "exact-conditional-source-set",
        "both rules and only relevant member/fact premises cited",
        inference["conditional"]["lina"]["source_ids"],
        set(inference["conditional"]["lina"]["source_ids"]) == {"premise-0", "premise-2", "premise-3", "premise-4"},
    )
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outcomes", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.outcomes.read_bytes()
    report = json.loads(raw)
    checks = semantic_checks(report)
    result = dict(
        format="GSE.retained-semantic-development-checks/1",
        scope="POST_INSPECTION_DEVELOPMENT_NOT_FINAL_HOLDOUT",
        outcomes=str(args.outcomes),
        outcomes_sha256=hashlib.sha256(raw).hexdigest(),
        candidate=report["candidate"],
        sha256=report["sha256"],
        checks=checks,
        passed=sum(c["passed"] for c in checks),
        failed_ids=[c["id"] for c in checks if not c["passed"]],
        original_failed_checks=[c for c in report["checks"] if not c["passed"]],
        checkpoint_complete=False,
        production_or_lexical_writes=0,
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in ["outcomes_sha256", "sha256", "passed", "failed_ids"]}, indent=2))


if __name__ == "__main__":
    main()
