"""Intent guards: qualifying operators preserve the clause and its participants."""

import pytest

from gse.api import GSEEncoder
from gse.api.encoder import head_linker_operation
from gse.symbolic import evaluate_tree, from_trace, resolve
from gse.symbolic.expression import Phrase, operator_composition_plan
from gse.symbolic.predicates import BoundaryCase, Contrast, Event, SetRestriction, TypeQuery


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def test_attachment_codes_preserve_the_tier():
    assert operator_composition_plan("CONTRAST", 2, True, True, False) == "clause_pair"
    assert operator_composition_plan("CONTRAST", 2, False, True, True) == "open_discourse"
    assert operator_composition_plan("CONTRAST", 2, False, False, False) == "operand"
    assert operator_composition_plan("SET_RESTRICT", 1, False, True, True) == "qualified_core"
    assert operator_composition_plan("SET_DIFF", 2, True, False, False) == "operand"
    assert operator_composition_plan("BIND_EQ", 2, True, True, False) == "matrix_core"
    assert operator_composition_plan("", 0, False, False, False) == "operand"


def test_head_linker_codes_are_scoped():
    assert head_linker_operation("however", True) == "CONTRAST"
    assert head_linker_operation("therefore", True) == "CONSEQUENCE"
    assert head_linker_operation("and", True) == "CLAUSE_COORD"
    assert head_linker_operation("then", True) == "TEMPORAL"
    assert head_linker_operation("however", False) == "none"
    assert head_linker_operation("when", True) == "none"
    assert head_linker_operation("", True) == "none"


@pytest.mark.parametrize(
    "linker", ["However", "Yet", "Still", "Instead", "Thus", "Therefore", "Hence", "Consequently", "And", "Then"]
)
def test_supported_head_linkers_retain_their_open_relation_and_event(encoder, linker):
    from gse.symbolic.propositions import propositions

    trace = encoder.encode(f"{linker} the cell moved.")
    assert trace.tokens[0].operator_tier == "discourse"
    tree = evaluate_tree(resolve(from_trace(trace)))
    events = [p.node for p in propositions(tree) if isinstance(p.node, Event)]
    assert len(events) == 1 and events[0].verb == "move"
    assert events[0].agent.head.lemma == "cell"


def test_head_contrast_keeps_event_without_inventing_a_previous_clause(encoder):
    tree = evaluate_tree(resolve(from_trace(encoder.encode("But the cell moved."))))
    assert isinstance(tree, Contrast)
    assert isinstance(tree.left, Phrase) and tree.left.atoms == []
    assert isinstance(tree.right, Event) and tree.right.verb == "move"
    assert tree.right.agent.head.lemma == "cell"


def test_clause_contrast_keeps_both_events_and_roles(encoder):
    tree = evaluate_tree(resolve(from_trace(encoder.encode("The cell moved, but the lens stopped."))))
    assert isinstance(tree, Contrast)
    assert isinstance(tree.left, Event) and tree.left.verb == "move"
    assert isinstance(tree.right, Event) and tree.right.verb == "stop"
    assert tree.left.agent.head.lemma == "cell"
    assert tree.right.agent.head.lemma == "lens"


def test_restriction_keeps_its_member_and_event(encoder):
    tree = evaluate_tree(resolve(from_trace(encoder.encode("Only the king slept."))))
    assert isinstance(tree, SetRestriction)
    assert tree.member.head.lemma == "king"
    assert isinstance(tree.predicate, Event) and tree.predicate.verb == "sleep"


def test_even_keeps_its_modal_event(encoder):
    tree = evaluate_tree(resolve(from_trace(encoder.encode("You can even validate it by hand."))))
    assert isinstance(tree, BoundaryCase)
    assert isinstance(tree.predicate, Event) and tree.predicate.verb == "validate"
    assert tree.predicate.agent.head.lemma == "you"
    assert "CAN" in tree.predicate.modal


def test_unary_query_reads_the_following_operand(encoder):
    tree = evaluate_tree(resolve(from_trace(encoder.encode("What is a dog?"))))
    assert isinstance(tree, TypeQuery)
    assert tree.entity.head.lemma == "dog"


def test_phrase_contrast_does_not_invent_events(encoder):
    tree = evaluate_tree(resolve(from_trace(encoder.encode("small but strong"))))
    assert isinstance(tree, Contrast)
    assert not isinstance(tree.left, Event) and not isinstance(tree.right, Event)
