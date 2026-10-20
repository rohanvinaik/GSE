"""Two signs of the shared claim contract, including the real public KB door."""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import evaluate_tree, from_trace, resolve
from gse.symbolic.claims import claim_key, commitment, commitment_modes, identity, polarity, scope_signature
from gse.symbolic.emit import emit_contract
from gse.symbolic.expression import Atom, Negation
from gse.symbolic.inference import KnowledgeBase
from gse.symbolic.narrative import NarrativeGraph, _collect_predicates, _trace_key
from gse.symbolic.predicates import ClauseCoordination, Conditional, Event, Temporal, TypeAssertion
from gse.symbolic.propositions import Proposition, propositions
from gse.symbolic.resolution import Entity


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def _entity(lemma, eid=None):
    return Entity(Atom(lemma), entity_id=eid)


@pytest.mark.parametrize(
    "modes,expected",
    [
        ((), "committed"),
        (("negated",), "committed"),
        (("negated", "possible"), "non_committed"),
        (("epistemic", "negated"), "committed"),
        (("belief",), "non_committed"),
        (("asserted", "belief"), "non_committed"),
        (("conditional",), "non_committed"),
        (("irrealis",), "non_committed"),
        (("necessary",), "non_committed"),
        (("negated", "epistemic"), "abstained"),
        (("negated", "belief"), "abstained"),
        (("abstained",), "abstained"),
        (("question",), "in_question"),
        (("in_question",), "in_question"),
        (("unrecognized",), "non_committed"),
    ],
)
def test_flat_scope_decision_has_both_signs(modes, expected):
    assert commitment_modes(modes) == expected


def test_structural_invalidity_and_interrogative_evidence_have_named_decisions():
    assert commitment_modes(("negated",), valid=False) == "unresolved"
    assert commitment_modes(("negated", "epistemic"), interrogative=True) == "in_question"
    assert commitment(None) == "unresolved"
    assert polarity(Proposition(Event("", None))).state == "unresolved"


def test_possible_negative_is_not_a_committed_negative(encoder):
    possible = evaluate_tree(resolve(from_trace(encoder.encode("He might not leave."))))
    definite = evaluate_tree(resolve(from_trace(encoder.encode("He did not leave."))))
    (p,) = propositions(possible)
    (q,) = propositions(definite)
    assert p.status == q.status == "negated"  # legacy status cannot decide commitment
    assert commitment(p) == "non_committed"
    assert commitment(q) == "committed"
    assert polarity(p).sign == polarity(q).sign == -1


def test_belief_and_denied_knowing_do_not_admit_their_content(encoder):
    belief = evaluate_tree(resolve(from_trace(encoder.encode("She believes that he left."))))
    denied = evaluate_tree(resolve(from_trace(encoder.encode("She does not know that he left."))))
    assert commitment(propositions(belief)[-1]) == "non_committed"
    assert commitment(propositions(denied)[-1]) == "abstained"
    assert polarity(propositions(denied)[-1]).clause_sign == 1


def test_source_question_cannot_become_a_fact():
    event = Event("bark", _entity("rex"))
    (question,) = propositions(event, source_text="Rex barks?")
    assert commitment(question) == "in_question"
    assert commitment(Proposition(event), interrogative=True) == "in_question"
    kb = KnowledgeBase.from_trees([event], source_texts=["Rex barks?"])
    assert kb.event("bark", "rex").state == "not_entailed"
    assert kb.admissions[0].commitment == "in_question"


def test_negation_must_not_distribute_over_conjunction():
    first = Event("bark", _entity("rex"))
    second = Event("leave", _entity("mike"))
    readings = propositions(Negation(ClauseCoordination(first, second)))
    assert all(commitment(item) == "non_committed" for item in readings)
    kb = KnowledgeBase.from_trees([Negation(ClauseCoordination(first, second))])
    assert kb._neg_facts == set()
    assert not kb.event("bark", "rex").holds


def test_verified_prefix_and_clause_signs_compose_without_erasure(encoder):
    tree = evaluate_tree(resolve(from_trace(encoder.encode("The knight is not disloyal."))))
    (reading,) = propositions(tree)
    result = polarity(reading)
    assert commitment(reading) == "committed"
    assert (result.state, result.clause_sign, result.lexical_sign, result.sign, result.base) == (
        "read",
        -1,
        -1,
        1,
        "loyal",
    )


def test_negative_primitive_content_is_not_a_denied_clause():
    event = Event("hurt", _entity("guard", "g"), _entity("prisoner", "p"))
    assert polarity(Proposition(event)).sign == 1
    key = claim_key(Proposition(event), {"DO": 1, "GOOD": -1})
    assert key.state == "supported"
    assert ("GOOD", -1) in key.key[1][1][1]


def test_identity_never_certifies_a_lemma_fallback():
    result = identity(_entity("cell"))
    assert result.state == "unresolved"
    assert result.reason == "missing_resolved_referent"
    assert identity(_entity("cell", "c1")).key != identity(_entity("cell", "c2")).key
    assert identity(_entity("it", "c1")).key == identity(_entity("cell", "c1")).key


def test_same_primitive_form_meets_only_with_the_same_resolved_roles():
    hurt = Proposition(Event("hurt", _entity("guard", "g"), _entity("prisoner", "p")))
    wound = Proposition(Event("wound", _entity("he", "g"), _entity("him", "p")))
    swapped = Proposition(Event("hurt", _entity("prisoner", "p"), _entity("guard", "g")))
    signature = {"DO": 1, "GOOD": -1}
    assert claim_key(hurt, signature).key == claim_key(wound, signature).key
    assert claim_key(hurt, signature).key != claim_key(swapped, signature).key
    assert claim_key(hurt, signature, namespace="doc1").key != claim_key(hurt, signature, namespace="doc2").key


def test_same_lemma_different_referents_and_themes_do_not_collapse():
    a = Proposition(Event("hurt", _entity("cell", "c1"), _entity("cell", "c2")))
    b = Proposition(Event("hurt", _entity("cell", "c1"), _entity("cell", "c3")))
    c = Proposition(Event("hurt", _entity("cell", "c1"), _entity("cell", "c2"), themes=(_entity("tool", "t"),)))
    signature = {"DO": 1, "GOOD": -1}
    assert claim_key(a, signature).key != claim_key(b, signature).key
    assert claim_key(a, signature).key != claim_key(c, signature).key


def test_generic_unresolved_and_malformed_keys_abstain():
    exact = Proposition(Event("do", _entity("cell", "c")))
    unresolved = Proposition(Event("hurt", _entity("cell")))
    assert claim_key(exact, {"DO": 1}).reason == "generic_relation"
    assert claim_key(exact, {"DO": 1, "HIER_PLUS": 1}).reason == "generic_relation"
    assert claim_key(exact).reason == "missing_relation_primitive_evidence"
    assert claim_key(unresolved, {"GOOD": -1}).state == "unresolved"
    assert claim_key(exact, {"GOOD": float("nan")}).reason == "malformed_relation_primitives"
    assert claim_key(exact, {"GOOD": True}).reason == "malformed_relation_primitives"
    assert claim_key(exact, {"not_a_prime": 1}).reason == "unknown_relation_primitives"
    assert claim_key(Proposition(TypeAssertion(_entity("it", "c"), Atom("thing")))).reason == "generic_kind"


def test_temporal_context_is_preserved_and_is_not_a_missing_qualifier_match():
    event = Event("hurt", _entity("guard", "g"), _entity("prisoner", "p"))
    context = Temporal(Event("arrive", _entity("warden", "w")), event, "after")
    contextual = propositions(context)[-1]
    assert commitment(contextual) == "committed"
    assert scope_signature(contextual)
    assert claim_key(contextual, {"GOOD": -1}).key != claim_key(Proposition(event), {"GOOD": -1}).key
    kb = KnowledgeBase.from_trees([context], relation_primitives={"GOOD": -1})
    assert kb.event("hurt", "guard", "prisoner").holds  # explicitly documented lexical projection
    assert kb.claim(contextual).state == "entailed"


@pytest.mark.parametrize(
    "sentence,verb,agent",
    [
        ("He might leave.", "leave", "he"),
        ("He should leave.", "leave", "he"),
        ("He might not leave.", "leave", "he"),
    ],
)
def test_modal_events_never_become_categorical_facts(encoder, sentence, verb, agent):
    tree = evaluate_tree(resolve(from_trace(encoder.encode(sentence))))
    kb = KnowledgeBase.from_trees([tree])
    assert kb.event(verb, agent).state == "not_entailed"
    assert kb._facts == kb._neg_facts == set()
    assert any(record.commitment == "non_committed" for record in kb.admissions)


def test_modal_type_is_withheld_but_a_plain_type_still_lands(encoder):
    modal = evaluate_tree(resolve(from_trace(encoder.encode("This should be clear."))))
    plain = evaluate_tree(resolve(from_trace(encoder.encode("The door is open."))))
    kb = KnowledgeBase.from_trees([modal, plain])
    assert not kb.is_a("this", "clear").holds
    assert kb.is_a("door", "open").holds


def test_negative_type_and_negative_event_stay_separate(encoder):
    trees = [
        evaluate_tree(resolve(from_trace(encoder.encode(sentence))))
        for sentence in ("Rex did not bark.", "The knight is disloyal.")
    ]
    kb = KnowledgeBase.from_trees(trees)
    assert not kb.event("bark", "rex").holds
    assert ("bark", "rex", None) in kb._neg_facts
    assert not kb.is_a("knight", "loyal").holds
    assert ("knight", "loyal") in kb._neg_types


def test_compound_rule_arms_are_withheld_whole():
    bark = Event("bark", _entity("rex"))
    leave = Event("leave", _entity("mike"))
    smile = Event("smile", _entity("spot"))
    kb = KnowledgeBase.from_trees([Conditional(ClauseCoordination(bark, smile), leave), bark])
    assert not kb.event("leave", "mike").holds
    assert any(item.state == "unsupported_rule_structure" for item in kb.admissions)
    kb = KnowledgeBase.from_trees([Conditional(bark, ClauseCoordination(leave, smile)), bark])
    assert not kb.event("leave", "mike").holds


def test_modal_and_secondary_argument_rules_are_withheld():
    bark = Event("bark", _entity("rex"))
    modal = Event("leave", _entity("mike"), modal=("MAYBE",))
    themes = Event("leave", _entity("mike"), themes=(_entity("tool"),))
    kb = KnowledgeBase.from_trees([Conditional(bark, modal), Conditional(bark, themes), bark])
    assert not kb.event("leave", "mike").holds
    assert {item.state for item in kb.admissions} >= {"unsupported_rule_scope", "unsupported_rule_arguments"}


def test_supported_rule_still_derives_with_actual_source_ids(encoder):
    sentences = ["If Rex barks, Mike leaves.", "Rex barks."]
    trees = [evaluate_tree(resolve(from_trace(encoder.encode(sentence)))) for sentence in sentences]
    kb = KnowledgeBase.from_trees(trees, source_ids=["rule-source", "fact-source"])
    result = kb.event("leave", "mike")
    assert result.state == "entailed"
    assert result.source_ids == ("fact-source", "rule-source")
    assert any(step.startswith("rule:") for step in result.chain)
    assert not kb.event("bark", "mike").holds


def test_exact_claim_query_never_uses_lemma_fallback_or_opposite_sign():
    event = Event("hurt", _entity("cell", "c1"), _entity("cell", "c2"))
    kb = KnowledgeBase.from_trees([event], source_ids=["s1"], relation_primitives={"GOOD": -1})
    assert kb.claim(Proposition(event)).state == "entailed"
    other = Event("hurt", _entity("cell", "c1"), _entity("cell", "c3"))
    assert kb.claim(Proposition(other)).state == "not_entailed"
    assert kb.claim(Proposition(Event("hurt", _entity("cell"), _entity("cell")))).state == "unresolved"
    (negative,) = propositions(Negation(event))
    assert kb.claim(negative).state == "not_entailed"


def test_certified_claim_derivation_keeps_supported_rule_sources():
    rex, mike = _entity("rex", "r"), _entity("mike", "m")
    rule = Conditional(Event("bark", rex), Event("leave", mike))
    fact = Event("bark", rex)
    kb = KnowledgeBase.from_trees([rule, fact], source_ids=["rule", "fact"], relation_primitives={"MOVE": 1})
    result = kb.claim(Proposition(Event("leave", mike)))
    assert result.state == "entailed"
    assert result.source_ids == ("fact", "rule")
    assert any(step.startswith("rule:") for step in result.rule_chain)
    other_mike = _entity("mike", "other-mike")
    assert kb.claim(Proposition(Event("leave", other_mike))).state == "not_entailed"


def test_certified_type_chain_refuses_a_same_lemma_alias_collision():
    alice, member = _entity("alice", "a"), _entity("member", "member")
    facts = [TypeAssertion(alice, Atom("member")), TypeAssertion(member, Atom("person"))]
    kb = KnowledgeBase.from_trees(facts, source_ids=["type1", "type2"])
    result = kb.claim(Proposition(TypeAssertion(alice, Atom("person"))))
    assert result.state == "entailed"
    assert result.source_ids == ("type1", "type2")
    collision = TypeAssertion(_entity("alice", "other-alice"), Atom("visitor"))
    kb = KnowledgeBase.from_trees([*facts, collision])
    assert kb.claim(Proposition(TypeAssertion(alice, Atom("person")))).state == "not_entailed"


def test_matrix_negation_stays_in_context_and_never_becomes_content_sign():
    subject, object_ = _entity("she", "she"), _entity("he", "he")
    content = Event("leave", object_)
    affirmative = propositions(Event("know", subject, content))[-1]
    denied = propositions(Negation(Event("know", subject, content)))[-1]
    assert polarity(affirmative).sign == polarity(denied).sign == 1
    assert scope_signature(affirmative) != scope_signature(denied)
    assert commitment(affirmative) == "committed"
    assert commitment(denied) == "abstained"


def test_source_sequences_must_not_shift_or_silently_truncate():
    with pytest.raises(ValueError, match="one-to-one"):
        KnowledgeBase.from_trees([Event("bark", _entity("rex"))], source_texts=[])
    with pytest.raises(ValueError, match="one-to-one"):
        KnowledgeBase.from_trees([Event("bark", _entity("rex"))], source_ids=[])


def test_atomic_premise_ids_are_not_replaced_by_their_conjunction_container():
    rex, mike = _entity("rex", "r"), _entity("mike", "m")
    facts = ClauseCoordination(Event("sleep", rex), Event("bark", rex))
    rule = Conditional(Event("bark", rex), Event("leave", mike))
    kb = KnowledgeBase.from_trees(
        [facts, rule],
        source_ids=["fact-container", "rule-container"],
        source_claim_ids=[
            ["coordination-claim", "sleep-claim", "bark-claim"],
            ["rule-claim", "antecedent-claim", "consequent-claim"],
        ],
        relation_primitives=lambda verb: {"THINK": 1} if verb == "sleep" else {"MOVE": 1},
    )
    result = kb.claim(Proposition(Event("leave", mike)))
    assert result.state == "entailed"
    assert result.source_ids == ("bark-claim", "rule-claim")
    assert kb.claim(Proposition(Event("sleep", rex))).source_ids == ("sleep-claim",)


@pytest.mark.parametrize(
    "mapping",
    [[], [["only-one"]], [["container", "first", ""]], [["container", "first", 2]], ["abc"], [None], [2], "a", 2],
)
def test_atomic_premise_mapping_must_align_with_shared_extraction(mapping):
    rex = _entity("rex", "r")
    facts = ClauseCoordination(Event("sleep", rex), Event("bark", rex))
    with pytest.raises(ValueError, match="source_claim_ids"):
        KnowledgeBase.from_trees([facts], source_claim_ids=mapping)


def test_narrative_spine_never_turns_modal_content_into_an_actual_event():
    modal = Event("leave", _entity("mike", "m"), modal=("MAYBE",))
    plain = Event("leave", _entity("mike", "m"))
    assert _collect_predicates(modal) == []
    assert _collect_predicates(plain) == [plain]
    assert NarrativeGraph.from_document([modal]).edges == []
    assert [edge.rel for edge in NarrativeGraph.from_document([plain]).edges] == ["leave"]
    assert _collect_predicates(Negation(plain)) == [Negation(plain)]


def test_narrative_compaction_never_merges_argument_swaps_or_modal_features():
    first = {
        "predicate": {"op": "EVENT", "args": [{"entity_id": "a"}, {"entity_id": "b"}], "features": {"verb": "hurt"}}
    }
    swapped = {
        "predicate": {"op": "EVENT", "args": [{"entity_id": "b"}, {"entity_id": "a"}], "features": {"verb": "hurt"}}
    }
    modal = {
        "predicate": {
            "op": "EVENT",
            "args": [{"entity_id": "a"}, {"entity_id": "b"}],
            "features": {"verb": "hurt", "modal": ["MAYBE"]},
        }
    }
    assert _trace_key(first) != _trace_key(swapped)
    assert _trace_key(first) != _trace_key(modal)
    assert _trace_key(first) == _trace_key(dict(first))


def test_emit_semantics_uses_shared_commitment_without_changing_default_gold():
    node = Negation(Event("leave", _entity("he", "h"), modal=("MAYBE",)))
    legacy = emit_contract(node)
    enriched = emit_contract(node, include_semantics=True, relation_primitives={"MOVE": 1})
    assert set(legacy) == {"contract_version", "predicate"}
    assert enriched["predicate"] == legacy["predicate"]
    (reading,) = enriched["claim_semantics"]["claims"]
    assert reading["commitment"] == "non_committed"
    assert reading["polarity"]["sign"] == -1
    questioned = emit_contract(node, include_semantics=True, source_text="He might not leave?")
    assert questioned["claim_semantics"]["claims"][0]["commitment"] == "in_question"
