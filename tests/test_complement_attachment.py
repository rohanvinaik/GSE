"""A clausal complement attaches to the event of the verb that takes it, wherever that event sits (#114).

complex_sentence_architecture.md §3.3 nests a TO-clause as "the *object-set* of the outer verb", and §3.4: "A
clause-predicate may be an **operand** to a clause-operator"; a 'that'-complement nests the same way. So "He laughed and
said that she left" gives say its complement inside the coordination, instead of dropping it because the whole sentence
is not one event. The host is found by its verb; when two events share that verb the attachment is ambiguous and
abstains (CSA §5: "never a silent wrong commit").
"""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import emit_contract, evaluate_tree, from_trace, resolve
from gse.symbolic.expression import Atom, Negation, Op, Phrase, _attach_complement


def _event(verb, *subjects):
    return Op(primitive=verb, operation="EVENT", arity=1, args=[Phrase(atoms=[Atom(lemma=s) for s in subjects])])


INNER = _event("leave", "she")


def test_a_single_event_takes_the_complement_as_its_last_argument():
    attached, code = _attach_complement(_event("say", "he"), "say", INNER)
    assert code == "attached"
    assert attached.primitive == "say" and attached.args[-1] is INNER and attached.arity == 2


def test_a_coordinated_event_takes_the_complement_in_place():
    coord = Op(
        primitive="COMP_AND", operation="CLAUSE_COORD", arity=2, args=[_event("laugh", "he"), _event("say", "he")]
    )
    attached, code = _attach_complement(coord, "say", INNER)
    assert code == "attached"
    laugh, say = attached.args
    assert laugh.args[-1] is not INNER and say.args[-1] is INNER


def test_a_negated_event_keeps_its_negation_around_the_complement():
    attached, code = _attach_complement(Negation(operand=_event("know", "she")), "know", INNER)
    assert code == "attached"
    assert isinstance(attached, Negation) and attached.operand.args[-1] is INNER


def test_a_punctuation_argument_is_dropped_before_the_complement():
    say = Op(
        primitive="say",
        operation="EVENT",
        arity=2,
        args=[Phrase(atoms=[Atom(lemma="he")]), Phrase(atoms=[Atom(lemma=".")])],
    )
    attached, code = _attach_complement(say, "say", INNER)
    assert code == "attached"
    assert attached.args == [say.args[0], INNER] and attached.arity == 2


def test_no_event_of_that_verb_leaves_the_tree_unchanged():
    tree = _event("laugh", "he")
    assert _attach_complement(tree, "say", INNER) == (tree, "absent")


def test_only_an_event_hosts_the_complement():
    # The host is the verb's EVENT; an operator that merely carries the same name is not a second host.
    named_alike = Op(
        primitive="say", operation="CLAUSE_COORD", arity=2, args=[_event("say", "he"), _event("laugh", "he")]
    )
    attached, code = _attach_complement(named_alike, "say", INNER)
    assert code == "attached"
    assert attached.args[0].args[-1] is INNER


def test_only_the_path_to_the_host_is_rebuilt():
    laugh = _event("laugh", "he")
    denied = Negation(operand=_event("weep", "he"))
    coord = Op(primitive="COMP_AND", operation="CLAUSE_COORD", arity=3, args=[laugh, denied, _event("say", "he")])
    attached, code = _attach_complement(coord, "say", INNER)
    assert code == "attached"
    assert attached.args[0] is laugh and attached.args[1] is denied
    assert attached.args[2].args[-1] is INNER


def test_two_events_of_that_verb_abstain():
    coord = Op(
        primitive="COMP_AND", operation="CLAUSE_COORD", arity=2, args=[_event("say", "he"), _event("say", "she")]
    )
    assert _attach_complement(coord, "say", INNER) == (coord, "ambiguous")


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def _ops(node):
    if isinstance(node, list):
        return [op for item in node for op in _ops(item)]
    if not isinstance(node, dict):
        return []
    return [node, *_ops(node.get("args", []))]


def _host(encoder, sentence, verb):
    contract = emit_contract(evaluate_tree(resolve(from_trace(encoder.encode(sentence)))))["predicate"]
    (host,) = [op for op in _ops(contract) if op.get("op") == "EVENT" and op.get("features", {}).get("verb") == verb]
    return host


@pytest.mark.parametrize(
    "sentence",
    ["He laughed and said that she left.", "Macbeth fled and claimed that Banquo was dead."],
)
def test_through_the_encoder_a_coordinated_verb_keeps_its_complement(encoder, sentence):
    verb = "say" if "said" in sentence else "claim"
    assert any(isinstance(arg, dict) for arg in _host(encoder, sentence, verb)["args"])


def _events(node):
    """Every EVENT Op of a from_trace tree, through Op args and Negation operands."""
    if isinstance(node, Negation):
        return _events(node.operand)
    if isinstance(node, Op):
        return ([node] if node.operation == "EVENT" else []) + [e for arg in node.args for e in _events(arg)]
    return []


def test_through_the_encoder_the_complement_goes_under_its_own_verb_only(encoder):
    hosts = {e.primitive: e for e in _events(from_trace(encoder.encode("He laughed and said that she left.")))}
    assert hosts["say"].args[-1] is hosts["leave"]
    assert not any(isinstance(arg, Op) for arg in hosts["laugh"].args)


def test_through_the_encoder_complements_nest_under_their_own_hosts(encoder):
    hosts = {e.primitive: e for e in _events(from_trace(encoder.encode("She believed that he said that they left.")))}
    assert hosts["believe"].args[-1] is hosts["say"]
    assert hosts["say"].args[-1] is hosts["leave"]


def test_through_the_encoder_a_lone_verb_is_unchanged(encoder):
    say = _host(encoder, "She said that he left.", "say")
    assert say["args"][0] == "she" and say["args"][1]["features"]["verb"] == "leave"
