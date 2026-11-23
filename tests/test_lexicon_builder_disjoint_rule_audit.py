"""An existing equal sign table must not conflate disjoint lexical scopes."""

from dataclasses import replace

import pytest
from test_lexicon_builder_reviewed_patterns import FakeTransport, execute
from test_lexicon_builder_reviewed_source_guards import source_input

from gse.curation.lexicon_builder.engine import Relation
from gse.curation.lexicon_builder.foundation import lexical_context
from gse.curation.lexicon_builder.rule_history import relation_records


def scoped_input(rule):
    raw = source_input()
    raw["rulings"] = []  # This fixture tests audit independence, not discovery authority.
    raw["relations"] = relation_records((rule,))
    raw["entries"] = raw["entries"][:2]
    raw["audit_entry_ids"] = raw["audit_entry_ids"][:1]
    for item in raw["entries"]:
        item["context"] = lexical_context(item["definition"], item["observations"], (rule,))
    return raw


def prior_rule(**changes):
    rule = Relation(
        "synthetic:other-population",
        ("WANT",),
        ((0,),),
        ("synthetic:test-only",),
        approved=True,
        guards=(("wordnet_ancestor:monetary_unit.n.01", "true"),),
    )
    return replace(rule, **changes)


def test_disjoint_native_scope_allows_withheld_answer_audit(tmp_path):
    raw = scoped_input(prior_rule())
    transport = FakeTransport(['{"WANT":0}'])
    report = execute(tmp_path, raw, transport, 1)
    assert report["model_calls"] == 1
    assert report["candidates"][0]["audit_outcomes"] == {"MODEL_AGREEMENT": 1}
    question = transport.calls[0][0]
    assert "WANT" not in question["known"]
    assert question["allowed_values"] == [-1, 0, 1]
    assert report["lexicon_writes"] is False


@pytest.mark.parametrize("guards", [(), (("pos", "noun"),), (("wordnet_ancestor:linear_unit.n.01", "true"),)])
def test_applicable_equal_table_is_still_refused_before_model(tmp_path, guards):
    raw = scoped_input(prior_rule(guards=guards))
    transport = FakeTransport([])
    with pytest.raises(ValueError, match="TESTED_RULE_PRESENT_IN_BASELINE"):
        execute(tmp_path, raw, transport, 1)
    assert transport.calls == []


def test_absence_condition_blocked_by_native_evidence_does_not_leak_answer(tmp_path):
    raw = scoped_input(prior_rule(guards=(), absent_evidence=("BODY",)))
    transport = FakeTransport(['{"WANT":0}'])
    report = execute(tmp_path, raw, transport, 1)
    assert report["model_calls"] == 1
    assert "WANT" not in transport.calls[0][0]["known"]
    assert report["candidates"][0]["audit_outcomes"] == {"MODEL_AGREEMENT": 1}
