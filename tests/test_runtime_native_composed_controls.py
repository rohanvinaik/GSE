"""Development regressions through actual native encoder and composed consumers.

The three reported failures and subsequently inspected cases are development,
not a fresh final holdout or evidence of full workload acceptance.
"""

import pytest

from GSE.api import GSEEncoder
from GSE.symbolic import emit_contract, evaluate_tree, from_trace, resolve
from GSE.symbolic.expression import Negation
from GSE.symbolic.predicates import Event, RelativeRestriction, Temporal, TypeAssertion
from GSE.symbolic.queries import is_logically_equal_to
from GSE.symbolic.resolution import Coordination, Entity
from GSE.symbolic.serialization import from_dict, to_dict


@pytest.mark.parametrize("text", ["I think about the door.", "Nora thinks about the lamp."])
def test_topic_pp_is_a_constituent_not_an_asserted_about_event(encoder, text):
    trace = encoder.encode(text)
    tree = evaluate_tree(resolve(from_trace(trace)))
    assert isinstance(tree, Event) and tree.verb == "think"
    assert tree.patient is None
    assert len(tree.themes) == 1
    theme = tree.themes[0]
    assert [atom.lemma for atom in theme.atoms][0] == "about"
    assert theme.atoms[-1].lemma in {"door", "lamp"}
    assert from_dict(to_dict(tree)) == tree
    assert emit_contract(tree)["predicate"]["features"]["verb"] == "think"


@pytest.mark.parametrize("modifier", ["here", "quietly"])
def test_intransitive_adverbial_is_not_a_patient(encoder, modifier):
    tree = compose(encoder, f"The child waited {modifier}.")
    assert isinstance(tree, Event) and tree.verb == "wait"
    assert tree.patient is None
    assert [a.lemma for a in tree.themes[0].atoms] == [modifier]
    assert from_dict(to_dict(tree)) == tree


@pytest.mark.parametrize("text", ["Nora did the work.", "Nora does her work.", "Nora did it."])
def test_main_do_retains_the_event_and_nominal_complement(encoder, text):
    trace = encoder.encode(text)
    assert next(t for t in trace.tokens if t.lemma == "do").pos == "VERB"
    tree = evaluate_tree(resolve(from_trace(trace)))
    assert isinstance(tree, Event) and tree.verb == "do"
    assert tree.agent.head.lemma == "nora"
    assert isinstance(tree.patient, Entity)


@pytest.mark.parametrize("text", ["Nora did repair the bicycle.", "Nora did not repair the bicycle."])
def test_do_support_does_not_steal_the_content_predicate(encoder, text):
    trace = encoder.encode(text)
    assert next(t for t in trace.tokens if t.lemma == "do").pos == "AUX"
    tree = evaluate_tree(resolve(from_trace(trace)))
    if "not" in text:
        assert isinstance(tree, Negation)
        tree = tree.operand
    assert isinstance(tree, Event) and tree.verb == "repair"
    assert tree.agent.head.lemma == "nora" and tree.patient.head.lemma == "bicycle"


@pytest.mark.parametrize("text,patient", [("Do the work.", "work"), ("Do it.", "it")])
def test_imperative_do_retains_directive_not_a_committed_fact(encoder, text, patient):
    from GSE.symbolic.propositions import commitment, propositions

    trace = encoder.encode(text)
    assert trace.tokens[0].pos == "VERB"
    tree = evaluate_tree(resolve(from_trace(trace)))
    assert isinstance(tree, Event) and tree.verb == "do"
    assert tree.agent.head.lemma == "you" and tree.agent.head.word_primitives == {}
    assert tree.patient.head.lemma == patient
    readings = propositions(tree)
    assert readings[0].status == "directive"
    assert commitment(readings[0]) != "committed"


@pytest.mark.parametrize("text,verb", [("Does Nora repair the bicycle?", "repair"), ("Does it work?", "work")])
def test_inverted_do_support_retains_the_content_predicate(encoder, text, verb):
    trace = encoder.encode(text)
    assert trace.tokens[0].pos == "AUX"
    tree = evaluate_tree(resolve(from_trace(trace)))
    assert isinstance(tree, Event) and tree.verb == verb


def test_coordinating_conjunction_does_not_turn_main_do_into_an_auxiliary(encoder):
    trace = encoder.encode("Nora sings and does the work.")
    assert next(t for t in trace.tokens if t.lemma == "do").pos == "VERB"
    from GSE.symbolic.queries import predicates

    tree = evaluate_tree(resolve(from_trace(trace)))
    assert {p.verb for p in predicates(tree) if isinstance(p, Event)} == {"sing", "do"}


def test_fronted_absolute_retains_matrix_predicate_and_adjunct(encoder):
    trace = encoder.encode("With her eyes open, Nora sees the bright lamp.")
    tree = evaluate_tree(resolve(from_trace(trace)))
    assert isinstance(tree, Event) and tree.verb == "see"
    assert tree.agent.head.lemma == "nora"
    assert tree.patient.head.lemma == "lamp"
    assert len(tree.themes) == 1
    assert [atom.lemma for atom in tree.themes[0].atoms] == ["with", "her", "eyes", "open"]
    assert from_dict(to_dict(tree)) == tree
    assert "eyes open" in emit_contract(tree)["predicate"]["features"]["themes"][0]


def test_trailing_participle_does_not_steal_matrix_predicate(encoder):
    tree = evaluate_tree(resolve(from_trace(encoder.encode("Nora fled, fearing capture."))))
    assert isinstance(tree, Event) and tree.verb == "flee"
    assert tree.agent.head.lemma == "nora"


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as instance:
        instance.conn.execute("PRAGMA query_only=ON")
        yield instance


def compose(encoder, text):
    return evaluate_tree(resolve(from_trace(encoder.encode(text))))


def test_spatial_opposites_reach_query_and_emitted_contract(encoder):
    above = compose(encoder, "The bird is above the tree.")
    below = compose(encoder, "The bird is below the tree.")
    assert isinstance(above, Event) and isinstance(below, Event)
    assert (above.verb, below.verb) == ("above", "below")
    assert above.agent.head.lemma == below.agent.head.lemma == "bird"
    assert above.patient.head.lemma == below.patient.head.lemma == "tree"
    assert not is_logically_equal_to(above, below)
    assert emit_contract(above)["predicate"]["features"]["verb"] == "above"
    assert emit_contract(below)["predicate"]["features"]["verb"] == "below"
    negated = compose(encoder, "The bird is not above the tree.")
    assert isinstance(negated, Negation) and negated.operand.verb == "above"


@pytest.mark.parametrize("linker,anchor", [("before", "dawn"), ("after", "noon"), ("after", "winter")])
def test_native_time_typed_nominal_is_setting_not_patient(encoder, linker, anchor):
    tree = compose(encoder, f"Alice arrived {linker} {anchor}.")
    assert isinstance(tree, Temporal) and tree.conjunction == linker
    assert tree.setting.head.lemma == anchor
    assert isinstance(tree.event, Event) and tree.event.verb == "arrive"
    assert tree.event.agent.head.lemma == "alice" and tree.event.patient is None
    assert emit_contract(tree)["predicate"]["features"]["conjunction"] == linker


@pytest.mark.parametrize("linker", ["before", "after"])
def test_existing_clausal_temporal_arguments_remain_events(encoder, linker):
    tree = compose(encoder, f"Alice arrived {linker} Bob left.")
    assert isinstance(tree, Temporal) and tree.conjunction == linker
    assert isinstance(tree.setting, Event) and tree.setting.verb == "leave"
    assert isinstance(tree.event, Event) and tree.event.verb == "arrive"


def test_non_time_anchor_cannot_become_temporal_from_preposition_alone(encoder):
    assert not isinstance(compose(encoder, "Alice stood before the king."), Temporal)


@pytest.mark.parametrize("anchor", ["spring", "period"])
def test_possible_time_sense_does_not_erase_other_anchor_readings(encoder, anchor):
    trace = encoder.encode(f"Alice stood before the {anchor}.")
    tree = evaluate_tree(resolve(from_trace(trace)))
    assert isinstance(tree, Event) and tree.verb == "before"
    assert isinstance(tree.agent, Event) and tree.agent.verb == "stand"
    assert tree.agent.patient is None and tree.patient.head.lemma == anchor
    linker = next(t for t in trace.tokens if t.lemma == "before")
    witness = linker.lexical_evidence["nominal_preposition_reading"]
    assert witness["code"] == "UNRESOLVED_PREPOSITION_ANCHOR_ROLE"
    assert witness["alternatives"] == ["TEMPORAL", "SPATIAL"]
    assert len(witness["native_noun_readings"]) > len(witness["temporal_readings"])


@pytest.mark.parametrize("text,head", [("He is a very strict judge.", "judge"), ("He is a very inert gas.", "gas")])
def test_degree_modified_copular_nominal_keeps_its_head(encoder, text, head):
    trace = encoder.encode(text)
    token = next(t for t in trace.tokens if t.lemma == head)
    assert token.pos == "NOUN" and "SYN_COMPL" in token.sent_primitives
    assert isinstance(evaluate_tree(resolve(from_trace(trace))), TypeAssertion)


def test_native_chemical_identity_survives_nominal_copula_and_emission(encoder):
    trace = encoder.encode("He is an inert gas.")
    assert trace.tokens[0].lexical_evidence["selected_record"]["entry_id"] == "wordnet:he:helium.n.01"
    gas = next(t for t in trace.tokens if t.lemma == "gas")
    assert gas.pos == "NOUN" and "SYN_COMPL" in gas.sent_primitives
    tree = evaluate_tree(resolve(from_trace(trace)))
    assert isinstance(tree, TypeAssertion)
    assert tree.entity.head.lemma == "he"
    assert emit_contract(tree)["predicate"]["op"] == "TYPE_ASSERT"


@pytest.mark.parametrize(
    "text,verb", [("He gases the room.", "gas"), ("He is moving.", "move"), ("He was killed.", "kill")]
)
def test_nominal_copula_repair_does_not_override_main_progressive_or_passive_verb(encoder, text, verb):
    tree = compose(encoder, text)
    assert isinstance(tree, Event) and tree.verb == verb


@pytest.mark.parametrize("copula", ["is", "was"])
def test_matrix_copula_and_genitive_relative_keep_separate_predicates(encoder, copula):
    trace = encoder.encode(f"The teacher {copula} a person whose occupation is teaching.")
    teacher = next(t for t in trace.tokens if t.lemma == "teacher")
    assert teacher.word_primitives.get("SOMEONE") == 1
    relative = next(c for c in trace.clauses if c.kind == "relative")
    assert relative.gap_role == "possessor"
    tree = evaluate_tree(resolve(from_trace(trace)))
    assert isinstance(tree, TypeAssertion) and tree.entity.head.lemma == "teacher"
    assert isinstance(tree.kind, RelativeRestriction) and tree.kind.head.head.lemma == "person"
    inner = tree.kind.restriction
    assert isinstance(inner, TypeAssertion) and inner.entity.head.lemma == "occupation"
    assert inner.entity.possessor.head.lemma == "person" and inner.kind.head.lemma == "teaching"
    assert from_dict(to_dict(tree)) == tree
    payload = emit_contract(tree)["predicate"]
    assert payload["op"] == "TYPE_ASSERT"
    assert payload["args"][1]["args"][1]["args"] == ["person's occupation", "teaching"]


def test_relative_auxiliary_and_participle_do_not_steal_matrix_predicate(encoder):
    tree = compose(encoder, "The child who is teaching works.")
    assert isinstance(tree, Event) and tree.verb == "work"
    assert isinstance(tree.agent, RelativeRestriction) and tree.agent.head.head.lemma == "child"
    inner = tree.agent.restriction
    assert isinstance(inner, Event) and inner.verb == "teach" and inner.agent.head.lemma == "child"
    assert inner.patient is None


def test_genitive_relative_does_not_turn_its_owner_into_a_patient(encoder):
    tree = compose(encoder, "The person whose child is teaching works.")
    assert isinstance(tree, Event) and tree.verb == "work"
    inner = tree.agent.restriction
    assert isinstance(inner, Event) and inner.verb == "teach"
    assert inner.agent.head.lemma == "child" and inner.agent.possessor.head.lemma == "person"
    assert inner.patient is None


def test_copular_relative_binds_its_subject_gap(encoder):
    tree = compose(encoder, "The person who is king works.")
    assert isinstance(tree, Event) and tree.verb == "work"
    inner = tree.agent.restriction
    assert isinstance(inner, TypeAssertion)
    assert inner.entity.head.lemma == "person" and inner.kind.head.lemma == "king"


def test_genitive_relative_keeps_its_own_negation(encoder):
    tree = compose(encoder, "The teacher is a person whose occupation is not teaching.")
    assert isinstance(tree, TypeAssertion) and not isinstance(tree, Negation)
    inner = tree.kind.restriction
    assert isinstance(inner, Negation) and isinstance(inner.operand, TypeAssertion)
    assert inner.operand.entity.possessor.head.lemma == "person"


@pytest.mark.parametrize("text", ["The child is teaching.", "The occupation is teaching the child."])
def test_gerund_activity_noun_requires_the_complete_nominal_construction(encoder, text):
    tree = compose(encoder, text)
    assert isinstance(tree, Event) and tree.verb == "teach"


def test_coordinated_adjectives_and_of_attachment_modify_one_nominal_head(encoder):
    trace = encoder.encode("The femur is the longest and thickest bone of the human skeleton.")
    assert next(t for t in trace.tokens if t.lemma == "femur").word_primitives.get("BODY") == 1
    tree = evaluate_tree(resolve(from_trace(trace)))
    assert isinstance(tree, TypeAssertion) and tree.entity.head.lemma == "femur"
    assert isinstance(tree.kind, RelativeRestriction)
    modified = tree.kind.head
    assert isinstance(modified, RelativeRestriction) and modified.head.head.lemma == "bone"
    assert isinstance(modified.restriction, TypeAssertion)
    modifiers = modified.restriction.kind
    assert isinstance(modifiers, Coordination) and modifiers.conjunction == "and"
    assert [a.lemma for a in modifiers.members] == ["long", "thick"]
    assert all(a.graded for a in modifiers.members)
    of = tree.kind.restriction
    assert isinstance(of, Event) and of.verb == "of"
    assert of.agent.head.lemma == "bone" and of.patient.head.lemma == "skeleton"
    assert of.patient.modifier.lemma == "human" and of.patient.possessor is None
    assert from_dict(to_dict(tree)) == tree
    payload = emit_contract(tree)["predicate"]["args"][1]
    assert payload["args"][1]["features"]["verb"] == "of"
    assert payload["args"][0]["args"][1]["args"][1]["args"] == ["long", "thick"]


@pytest.mark.parametrize("conjunction", ["and", "or"])
def test_genuine_nominal_coordination_is_not_reclassified_as_adjectival(encoder, conjunction):
    tree = compose(encoder, f"The bone {conjunction} the skeleton is hard.")
    assert isinstance(tree, TypeAssertion) and isinstance(tree.entity, Coordination)
    assert tree.entity.conjunction == conjunction
    assert [m.head.lemma for m in tree.entity.members] == ["bone", "skeleton"]


def test_of_anchor_coordination_stays_inside_the_nominal_attachment(encoder):
    tree = compose(encoder, "The bone of the child and the adult is hard.")
    assert isinstance(tree, TypeAssertion) and isinstance(tree.entity, RelativeRestriction)
    of = tree.entity.restriction
    assert isinstance(of, Event) and of.verb == "of" and of.agent.head.lemma == "bone"
    assert isinstance(of.patient, Coordination)
    assert all(isinstance(m, Entity) for m in of.patient.members)
    assert [m.head.lemma for m in of.patient.members] == ["child", "adult"]


@pytest.mark.parametrize(
    "text,verb,preposition,anchor",
    [
        ("Something happens to me.", "happen", "to", "me"),
        ("Alice stood by the window.", "stand", "by", "window"),
        ("Alice moved toward the door.", "move", "toward", "door"),
    ],
)
def test_intransitive_preposition_keeps_relation_and_anchor_without_inventing_patient(
    encoder, text, verb, preposition, anchor
):
    tree = compose(encoder, text)
    assert isinstance(tree, Event) and tree.verb == preposition
    assert isinstance(tree.agent, Event) and tree.agent.verb == verb
    assert tree.agent.patient is None
    assert tree.patient.head.lemma == anchor
    assert from_dict(to_dict(tree)) == tree
    emitted = emit_contract(tree)["predicate"]
    assert emitted["features"]["verb"] == preposition
    assert emitted["args"][0]["features"]["verb"] == verb
    assert anchor in emitted["args"][1]
