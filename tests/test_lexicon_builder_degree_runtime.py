"""Degree is sentence grammar; definition ambiguity never chooses a sense."""

import pytest

from gse.api import GSEEncoder
from gse.api.trace import OperationTrace
from gse.curation.lexicon_builder.engine import Assertion, propagate
from gse.curation.lexicon_builder.evidence import Definition
from gse.curation.lexicon_builder.storage import open_build, store_entry
from gse.discourse.speech import encode_document_utterance_events
from gse.symbolic import emit_contract, evaluate_tree, from_trace, negation_signs, resolve
from gse.symbolic.queries import is_logically_equal_to
from gse.symbolic.serialization import from_json, to_json


@pytest.fixture
def encoder(tmp_path):
    path = tmp_path / "definitions.db"
    connection = open_build(path)
    for entry_id, lemma, bank, value, level in (
        ("very:degree", "very", "INTENSITY", 1, 1),
        ("very:identity", "very", None, None, None),
        ("extremely:degree", "extremely", "INTENSITY", 1, 2),
        ("extremely:other", "extremely", None, None, None),
        ("good:positive", "good", "GOOD", 1, None),
        ("good:other", "good", "GOOD", 0, None),
        ("bad:negative", "bad", "GOOD", -1, None),
        ("fine:zero", "fine", "GOOD", 0, None),
        ("really:degree", "really", "INTENSITY", 1, 1),
        ("really:other", "really", None, None, None),
        ("kind:adjective", "kind", "GOOD", 1, None),
        ("kind:noun", "kind", None, None, None),
    ):
        assertions = (Assertion(bank, value, "fixture", entry_id, "dictionary"),) if bank and value is not None else ()
        store_entry(
            connection,
            Definition(
                entry_id,
                lemma,
                ("noun" if entry_id == "kind:noun" else "adjective") if lemma == "kind" else "adverb",
                entry_id,
            ),
            propagate(("GOOD", "INTENSITY"), assertions, ()),
            assertions,
            {"INTENSITY": level} if level else None,
        )
    connection.commit()
    connection.close()
    with GSEEncoder(str(path)) as instance:
        yield instance


def document_event(encoder, text):
    return next(
        event
        for event in encode_document_utterance_events(encoder, [{"id": "scope", "text": text}])
        if event["type"] == "utterance"
    )


@pytest.mark.parametrize(
    "phrase,operation,level,mechanism",
    [
        ("very good", "TYPE_ASSERT", 1, None),
        ("very very good", "TYPE_ASSERT", 2, None),
        ("extremely good", "TYPE_ASSERT", 2, None),
        ("not very good", "TYPE_ASSERT", -1, "hierarchy_direction"),
        ("very not good", "NOT", 1, "syntactic_negation"),
        ("not not very good", "TYPE_ASSERT", 1, "hierarchy_direction"),
    ],
)
def test_public_intake_distinguishes_degree_and_scope_without_selecting_senses(
    encoder, phrase, operation, level, mechanism
):
    event = document_event(encoder, f"The dog is {phrase}.")
    assert event["state"] == "read", event["error"]
    trace = event["trace"]
    target = next(token for token in trace.tokens if token.lemma == "good")
    assert target.degree["level"] == level
    assert target.word_primitives == {}
    assert target.word_vec_nnz == 0
    for token in trace.tokens:
        if token.lemma in {"very", "extremely", "good"}:
            assert token.lexical_evidence["selection_status"] == "AMBIGUOUS"
            assert token.lexical_evidence["selected_record"] is None
    predicate = emit_contract(event["tree"])["predicate"]
    assert predicate["op"] == operation
    assertion = predicate["args"][0] if operation == "NOT" else predicate
    assert assertion["args"] == ["dog", "good"]
    assert assertion["features"]["degree"] == [{"argument": 1, "target": "good", "scale": "INTENSITY", "level": level}]
    if mechanism:
        assert negation_signs(trace)["owners"][0]["mechanism"] == mechanism
    assert OperationTrace.from_json(trace.to_json()).to_dict() == trace.to_dict()
    assert emit_contract(from_json(to_json(event["tree"]))) == emit_contract(event["tree"])


@pytest.mark.parametrize("count", range(1, 7))
def test_repeated_degree_retains_each_source_and_adds_ordinal_steps(encoder, count):
    trace = encoder.encode(f"The dog is {'very ' * count}good.")
    target = next(token for token in trace.tokens if token.lemma == "good")
    assert target.degree["level"] == count
    assert target.degree["sources"] == list(range(3, 3 + count))
    assert len([token for token in trace.tokens if token.degree_modifier]) == count


def test_logical_comparison_uses_degree_and_retains_sign_scope(encoder):
    trees = [
        evaluate_tree(resolve(from_trace(encoder.encode(f"The dog is {phrase}."))))
        for phrase in (
            "very good",
            "very very good",
            "extremely good",
            "not very good",
            "very not good",
        )
    ]
    assert is_logically_equal_to(trees[1], trees[2])
    assert not is_logically_equal_to(trees[0], trees[1])
    assert not is_logically_equal_to(trees[0], trees[3])
    assert not is_logically_equal_to(trees[3], trees[4])


@pytest.mark.parametrize(
    "text", ["The very same dog runs.", "The very idea matters.", "Very dog.", "Very, good.", "Very.", ""]
)
def test_nominal_homographs_and_boundaries_do_not_gain_degree(encoder, text):
    trace = encoder.encode(text)
    assert all(not token.degree and not token.degree_modifier for token in trace.tokens)


@pytest.mark.parametrize("word,expected", [("bad", -1), ("fine", 0)])
def test_degree_preserves_known_signed_or_zero_base(encoder, word, expected):
    before = encoder.lookup_definition(f"{word}:{'negative' if expected else 'zero'}")
    trace = encoder.encode(f"The dog is not very {word}.")
    target = next(token for token in trace.tokens if token.lemma == word)
    assert target.degree["level"] == -1
    assert target.lexical_evidence["selected_record"]["assignments"]["GOOD"] == expected
    assert target.word_primitives.get("GOOD", 0) == expected
    assert encoder.lookup_definition(f"{word}:{'negative' if expected else 'zero'}") == before
    if expected == 0:
        assert target.word_vec_nnz == 0


def test_unregistered_candidate_dependent_degree_abstains_at_real_intake(encoder):
    event = document_event(encoder, "The dog is not really good.")
    assert event["state"] == "unread"
    assert event["tree"] is None
    assert event["error"]["code"] == "UNRESOLVED_DEGREE_SCOPE"
    assert "UNRESOLVED_DEGREE_SCOPE" in event["error"]["message"]


def test_null_input_is_rejected_not_misread(encoder):
    with pytest.raises((ValueError, TypeError, AttributeError)):
        encoder.encode(None)


@pytest.mark.parametrize(
    "bad_degree",
    [
        None,
        [],
        {"scale": "INTENSITY", "level": True, "sources": [3]},
        {"scale": "INTENSITY", "level": 99, "sources": [3]},
    ],
)
def test_malformed_or_forged_serialized_degree_is_not_accepted(encoder, bad_degree):
    trace = encoder.encode("The dog is very good.")
    next(token for token in trace.tokens if token.lemma == "good").degree = bad_degree
    with pytest.raises(ValueError, match="^INVALID_DEGREE_METADATA$"):
        from_trace(trace)


def test_older_trace_can_reconstruct_degree_through_public_constructor(encoder):
    payload = encoder.encode("The dog is not very good.").to_dict()
    for token in payload["tokens"]:
        token.pop("degree")
        token.pop("degree_modifier")
    trace = OperationTrace.from_dict(payload)
    tree = evaluate_tree(resolve(from_trace(trace)))
    predicate = emit_contract(tree)["predicate"]
    assert predicate["op"] == "TYPE_ASSERT"
    assert predicate["features"]["degree"][0]["level"] == -1


@pytest.mark.parametrize(
    "text,negative,level,count",
    [
        ("not very good", False, -1, 0),
        ("very not good", True, 1, 1),
        ("very very not good", True, 2, 1),
        ("very not not good", False, 1, 2),
        ("not extremely good", False, -2, 0),
    ],
)
def test_bare_degree_operand_preserves_sign_and_ordinal_at_document_entry(encoder, text, negative, level, count):
    event = document_event(encoder, text)
    assert event["state"] == "read", event["error"]
    contract = emit_contract(event["tree"])
    expected = {"op": "NOT", "args": ["good"], "features": {}} if negative else "good"
    assert contract["predicate"] == expected
    assert contract["degree"] == [{"target": "good", "scale": "INTENSITY", "level": level}]
    signs = negation_signs(event["trace"])
    assert signs["state"] == "read"
    assert signs["count"] == count
    assert not signs["unresolved"]
    assert emit_contract(from_json(to_json(event["tree"]))) == contract


@pytest.mark.parametrize(
    "text,level",
    [("very kind", 1), ("extremely kind.", 2), ("very very kind!", 2), ("not very kind", -1), ("very not kind", 1)],
)
def test_bare_degree_uses_adjective_category_without_selecting_homograph(encoder, text, level):
    event = document_event(encoder, text)
    assert event["state"] == "read", event["error"]
    operand = next(token for token in event["trace"].tokens if token.lemma == "kind")
    assert operand.pos == "ADJ"
    assert operand.degree["level"] == level
    assert operand.lexical_evidence["selection_status"] == "AMBIGUOUS"
    assert operand.lexical_evidence["selected_record"] is None
    assert operand.word_primitives == {}
    assert emit_contract(event["tree"])["degree"] == [{"target": "kind", "scale": "INTENSITY", "level": level}]


@pytest.mark.parametrize(
    "text",
    [
        "the very kind",
        "very kind of dog",
        "very same dog",
        "very dog",
        "very sort",
        "very, kind",
        "very and kind",
        "very because kind",
    ],
)
def test_bare_degree_repair_does_not_cross_nominal_or_operator_context(encoder, text):
    trace = encoder.encode(text)
    assert all(not token.degree and not token.degree_modifier for token in trace.tokens)
