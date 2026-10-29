"""Sentence operators remain available while lexical definitions abstain."""

import sqlite3

import pytest

from gse.api import GSEEncoder
from gse.api.errors import OOVError
from gse.curation.lexicon_builder.engine import Assertion, propagate
from gse.curation.lexicon_builder.evidence import Definition
from gse.curation.lexicon_builder.storage import open_build, store_entry
from gse.discourse.speech import encode_document_utterance_events
from gse.symbolic import emit_contract, evaluate_tree, from_trace, resolve


@pytest.fixture
def dictionary_path(tmp_path):
    path = tmp_path / "definitions.db"
    connection = open_build(path)
    try:
        # Conflicting senses are distinct entries, never evidence to choose one.
        for entry_id, lemma, value in (("only:one", "only", 1), ("only:two", "only", -1)):
            assertions = (Assertion("GOOD", value, "fixture", entry_id, "dictionary"),)
            store_entry(
                connection,
                Definition(entry_id, lemma, "adverb", entry_id),
                propagate(("GOOD",), assertions, ()),
                assertions,
            )
        connection.commit()
    finally:
        connection.close()
    return path


@pytest.fixture
def encoder(dictionary_path):
    with GSEEncoder(str(dictionary_path)) as instance:
        yield instance


@pytest.mark.parametrize(
    "text,word,operation,selection,top",
    [
        ("Alice helps Bob because Bob helps Carol.", "because", "CAUSAL_SOURCE", "NOT_FOUND", "CAUSATION"),
        ("Only the dog runs.", "only", "SET_RESTRICT", "AMBIGUOUS", "SET_RESTRICT"),
        ("The dog is bigger than the cat.", "than", "SET_DIFF", "NOT_FOUND", "COMPARISON"),
        ("Alice helps Bob and Carol helps Dave.", "and", "CLAUSE_COORD", "NOT_FOUND", "CLAUSE_COORD"),
    ],
)
def test_public_encode_keeps_grammar_without_selecting_lexical_meaning(encoder, text, word, operation, selection, top):
    trace = encoder.encode(text)
    token = next(token for token in trace.tokens if token.lemma == word)
    assert token.comp_operation == operation
    assert token.is_operator
    assert token.word_primitives == {}
    assert token.word_vec_nnz == 0
    assert token.lexical_evidence["selection_status"] == selection
    assert token.lexical_evidence["selected_record"] is None
    assert token.lexical_evidence["sense_resolved"] is False
    if selection == "AMBIGUOUS":
        assert token.lexical_evidence["candidate_entry_ids"] == ["only:one", "only:two"]
    assert emit_contract(evaluate_tree(resolve(from_trace(trace))))["predicate"]["op"] == top


def test_document_intake_preserves_causal_arguments_and_coordination(encoder):
    events = list(
        encode_document_utterance_events(
            encoder,
            [
                {"id": "cause", "text": "Alice helps Bob because Bob helps Carol."},
                {"id": "coordinate", "text": "Alice helps Bob and Carol helps Dave."},
            ],
        )
    )
    outcomes = {event["source_sentence_id"]: event for event in events if event["type"] == "utterance"}
    assert all(outcome["state"] == "read" for outcome in outcomes.values())
    cause = emit_contract(outcomes["cause"]["tree"])["predicate"]
    assert cause["op"] == "CAUSATION"
    assert cause["args"] == [
        {"op": "EVENT", "args": ["bob", "carol"], "features": {"verb": "help"}},
        {"op": "EVENT", "args": ["alice", "bob"], "features": {"verb": "help"}},
    ]
    coordinate = emit_contract(outcomes["coordinate"]["tree"])["predicate"]
    assert coordinate["op"] == "CLAUSE_COORD"
    assert [argument["args"] for argument in coordinate["args"]] == [["alice", "bob"], ["carol", "dave"]]
    assert events[-1]["failed"] == 0


def test_document_intake_preserves_restriction_member_and_comparison_arguments(encoder):
    outcomes = [
        event
        for event in encode_document_utterance_events(
            encoder,
            [
                {"id": "restrict", "text": "Only the dog runs."},
                {"id": "compare", "text": "The dog is bigger than the cat."},
            ],
        )
        if event["type"] == "utterance"
    ]
    restriction, comparison = [emit_contract(event["tree"])["predicate"] for event in outcomes]
    assert restriction["op"] == "SET_RESTRICT"
    assert restriction["args"] == ["dog", {"op": "EVENT", "args": ["dog"], "features": {"verb": "run"}}]
    assert comparison["op"] == "COMPARISON"
    assert comparison["args"] == ["big dog", "cat"]


def test_strict_mode_accepts_registered_grammar_but_rejects_unknown_content(dictionary_path):
    with GSEEncoder(str(dictionary_path), strict=True) as strict:
        token = strict.encode("because").tokens[0]
        assert token.comp_operation == "CAUSAL_SOURCE"
        assert token.lexical_evidence["selection_status"] == "NOT_FOUND"
        assert token.word_primitives == {}
        with pytest.raises(OOVError):
            strict.encode("unlistedword")


@pytest.mark.parametrize("operation,arity", [("CONSEQUENCE", 2), ("CAUSAL_SOURCE", 1)])
def test_selected_definition_cannot_override_registered_grammar(encoder, operation, arity):
    store_entry(
        encoder.conn,
        Definition("because:one", "because", "conjunction", "fixture"),
        propagate(("GOOD",), (), ()),
    )
    encoder.conn.execute(
        "UPDATE lexemes SET comp_primitive='COMP_BECAUSE',comp_operation=?,comp_arity=? WHERE lemma='because'",
        (operation, arity),
    )
    encoder.conn.commit()
    with pytest.raises(ValueError, match="^GRAMMATICAL_OPERATOR_METADATA_MISMATCH$"):
        encoder.encode("because")


def test_matching_metadata_and_known_content_are_preserved(encoder):
    assertions = (Assertion("GOOD", 0, "fixture", "because", "dictionary"),)
    store_entry(
        encoder.conn,
        Definition("because:one", "because", "conjunction", "fixture"),
        propagate(("GOOD",), assertions, ()),
        assertions,
    )
    encoder.conn.execute(
        "UPDATE lexemes SET comp_primitive='COMP_BECAUSE',comp_operation='CAUSAL_SOURCE',comp_arity=2 "
        "WHERE lemma='because'"
    )
    encoder.conn.commit()
    token = encoder.encode("because").tokens[0]
    assert token.comp_operation == "CAUSAL_SOURCE"
    assert token.lexical_evidence["selection_status"] == "IDENTIFIED"
    assert token.lexical_evidence["selected_record"]["assignments"] == {"GOOD": 0}
    assert token.word_primitives == {}


def test_conflicted_lexical_definition_does_not_disable_registered_grammar(encoder):
    assertions = (
        Assertion("GOOD", 1, "fixture", "positive", "dictionary"),
        Assertion("GOOD", -1, "fixture", "negative", "dictionary"),
    )
    store_entry(
        encoder.conn,
        Definition("because:conflict", "because", "conjunction", "conflicting lexical evidence"),
        propagate(("GOOD",), assertions, ()),
        assertions,
    )
    encoder.conn.commit()
    token = encoder.encode("because").tokens[0]
    assert token.comp_operation == "CAUSAL_SOURCE"
    assert token.lexical_evidence["selection_status"] == "CONFLICT"
    assert token.lexical_evidence["selected_record"] is None
    assert token.word_primitives == {}
    assert token.word_vec_nnz == 0


def test_legacy_lookup_does_not_gain_new_registry_behavior(tmp_path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    try:
        connection.executescript("""
            CREATE TABLE lexemes (id INTEGER PRIMARY KEY, lemma TEXT, pos TEXT,
                comp_primitive TEXT, comp_arity INTEGER, comp_operation TEXT);
            CREATE TABLE primitive_values (lexeme_id INTEGER, primitive TEXT, value INTEGER);
            CREATE TABLE sentence_primitive_values (lexeme_id INTEGER, primitive TEXT, value INTEGER);
            INSERT INTO lexemes(id,lemma,pos) VALUES (1,'seed','NOUN');
        """)
    finally:
        connection.close()
    with GSEEncoder(str(path)) as legacy:
        token = legacy.encode("because").tokens[0]
        assert token.comp_operation is None
        assert token.lexical_evidence["state"] == "no_row"
    with GSEEncoder(str(path), strict=True) as strict:
        with pytest.raises(OOVError):
            strict.encode("because")
