"""The staging boundary must preserve missing values and expose competing rules."""

from GSE.curation.lexicon_builder.engine import TERNARY, Assertion
from GSE.curation.lexicon_builder.resolution import resolve_dictionary
from scripts.stage_lexicon_coherence import _forward, _relation


def proposal(name, premise, head):
    spec = {"id": name, "antecedent": premise, "consequent": head, "source_refs": ["synthetic"], "guards": []}
    return spec, _relation(spec)


def test_known_target_does_not_activate_rule_with_unknown_premise():
    def solve(rules):
        return resolve_dictionary(("SAY", "DO"), (Assertion("DO", 0, "fixture", "known", "fixture"),), rules)

    prior = solve(())
    rule = proposal("action", ("SAY", 1), ("DO", 1))
    result, fired, issues = _forward(prior, (rule,), solve)
    assert fired == issues == []
    assert result.domains == {"SAY": TERNARY, "DO": frozenset({0})}


def test_forward_set_can_activate_a_second_rule_after_closure():
    def solve(rules):
        return resolve_dictionary(("SAY", "DO", "HAPPEN"),
                                  (Assertion("SAY", 1, "fixture", "known", "fixture"),), rules)

    action = proposal("action", ("SAY", 1), ("DO", 1))
    occurrence = proposal("occurrence", ("DO", 1), ("HAPPEN", 1))
    result, fired, issues = _forward(solve(()), (occurrence, action), solve)
    assert fired == ["action", "occurrence"] and not issues
    assert result.assignments == {"SAY": 1, "DO": 1, "HAPPEN": 1}


def test_joint_disagreement_has_named_proof_and_preserves_unknown():
    def solve(rules):
        return resolve_dictionary(("SAY", "DO"), (Assertion("SAY", 1, "fixture", "known", "fixture"),), rules)

    action = proposal("action", ("SAY", 1), ("DO", 1))
    neutral = proposal("neutral", ("SAY", 1), ("DO", 0))
    prior = solve(())
    assert _forward(prior, (neutral,), solve)[0].domains["DO"] == {0}
    result, fired, issues = _forward(prior, (action, neutral), solve)
    assert fired == ["action", "neutral"]
    assert result.domains["DO"] == TERNARY
    assert any(issue["reason"] == "CONDITIONAL_COMPONENT_CONFLICT" and
               issue["rule_ids"] == ("action", "neutral") for issue in issues)
