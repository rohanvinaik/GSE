"""Grammatical context selects stored catalog definitions, never noun homographs."""

import json
import shutil
import sqlite3

import pytest

from GSE.api import GSEEncoder
from GSE.api.encoder import GrammaticalDefinitionError
from GSE.curation.external_sources.gse_closed_class import GSEClosedClassParser
from GSE.curation.lexicon_builder.engine import Assertion, propagate
from GSE.curation.lexicon_builder.evidence import Definition, collect_evidence
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.storage import open_build, store_entry
from GSE.discourse.speech import encode_document_utterance_events
from GSE.symbolic import emit_contract, evaluate_tree, from_trace, resolve
from GSE.symbolic.inference import KnowledgeBase
from GSE.symbolic.propositions import propositions


def _store(conn, entry_id, lemma, pos, values):
    assertions = tuple(Assertion(bank, value, "fixture", entry_id, "dictionary") for bank, value in values)
    store_entry(conn, Definition(entry_id, lemma, pos, entry_id), propagate(BANKS, assertions, ()), assertions)


@pytest.fixture(scope="module")
def catalog_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("grammar") / "definitions.db"
    parser = GSEClosedClassParser()
    parser.load()
    build_dictionary(collect_evidence({"gse_closed_class": parser}, ()), path)
    conn = open_build(path)
    try:
        for lemma in ("he", "might", "can"):
            _store(conn, f"fixture:noun:{lemma}", lemma, "noun", [("SOMETHING", 1)])
        conn.commit()
    finally:
        conn.close()
    return path


@pytest.fixture
def encoder(catalog_path, monkeypatch):
    from GSE import lexicon_resource

    pointer = catalog_path.parent / "active.json"
    pointer.write_text(json.dumps({"format": lexicon_resource.POINTER_FORMAT, "path": str(catalog_path)}))
    monkeypatch.setattr(lexicon_resource, "ACTIVE_POINTER", pointer)
    with GSEEncoder() as instance:
        yield instance


@pytest.mark.parametrize(
    "word,bank,status",
    [
        ("might", "MAYBE", "possible"),
        ("may", "MAYBE", "possible"),
        ("would", "MAYBE", "possible"),
        ("can", "CAN", "possible"),
        ("could", "CAN", "possible"),
        ("must", "MUST", "necessary"),
        ("should", "MUST", "necessary"),
    ],
)
def test_default_path_catalog_modals_reach_claim_semantics(encoder, word, bank, status):
    trace = encoder.encode(f"He {word} leave.")
    token = next(token for token in trace.tokens if token.token == word)
    assert token.pos == "AUX"
    assert token.word_primitives == {bank: 1}
    assert token.lexical_evidence["selected_record"]["entry_id"] == f"gse_closed_class:modal:{word}"
    tree = evaluate_tree(resolve(from_trace(trace)))
    assert emit_contract(tree)["predicate"]["features"]["modal"] == [bank]
    assert propositions(tree)[0].status == status
    assert KnowledgeBase.from_trees([tree]).event("leave", "he").state == "not_entailed"


@pytest.mark.parametrize("word", ["will", "shall"])
def test_tense_only_auxiliary_does_not_require_undeclared_modal_bank(encoder, word):
    tree = evaluate_tree(resolve(from_trace(encoder.encode(f"He {word} leave."))))
    assert propositions(tree)[0].status == "asserted"


def test_pronoun_selection_does_not_replace_explicit_noun_identity(encoder):
    assert encoder.lexical_lookup("he")["selection_status"] == "AMBIGUOUS"
    token = encoder.encode("He runs.").tokens[0]
    assert token.word_primitives == {"SOMEONE": 1}
    assert token.lexical_evidence["selected_record"]["entry_id"] == "gse_closed_class:pronoun:he"
    selected = encoder.lookup_definition("fixture:noun:he")
    assert selected["selected"]["assignments"] == {"SOMETHING": 1}
    assert encoder.lexical_lookup("he", entry_id="fixture:noun:he")["primitives"] == {"SOMETHING": 1}


def test_noun_role_does_not_select_modal_definition(encoder):
    token = next(token for token in encoder.encode("The can fell.").tokens if token.lemma == "can")
    assert token.pos == "NOUN"
    assert token.word_primitives == {}
    assert token.lexical_evidence["selection_status"] == "AMBIGUOUS"
    assert "grammatical_selection" not in token.lexical_evidence


def test_surface_and_resolved_contraction_lemma_select_actual_catalog_id(encoder):
    are = next(token for token in encoder.encode("They are dogs.").tokens if token.token == "are")
    assert are.lexical_evidence["selected_record"]["entry_id"] == "gse_closed_class:auxiliary:are"
    would = next(token for token in encoder.encode("He'd leave.").tokens if token.token == "'d")
    assert would.lemma == "would"
    assert would.lexical_evidence["selected_record"]["entry_id"] == "gse_closed_class:modal:would"
    had = next(token for token in encoder.encode("He'd gone.").tokens if token.token == "'d")
    assert had.lemma == "have"
    assert had.lexical_evidence["selected_record"]["entry_id"] == "gse_closed_class:auxiliary:have"


def test_missing_pronoun_catalog_abstains_without_injecting_values(tmp_path):
    path = tmp_path / "sparse.db"
    conn = open_build(path)
    try:
        _store(conn, "fixture:noun:he", "he", "noun", [("SOMETHING", 1)])
        conn.commit()
    finally:
        conn.close()
    with GSEEncoder(str(path)) as encoder:
        token = encoder.encode("He runs.").tokens[0]
        assert token.word_primitives == {}
        assert token.lexical_evidence["selection_status"] == "NOT_FOUND"
        assert token.lexical_evidence["reason"] == "MISSING_GRAMMATICAL_DEFINITION"
        assert encoder.lookup_definition("fixture:noun:he")["code"] == "IDENTIFIED"
        assert encoder.lookup_definition("gse_closed_class:pronoun:he")["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    "case,code",
    [
        ("missing", "MISSING_GRAMMATICAL_DEFINITION"),
        ("unknown", "UNRESOLVED_MODAL_DEFINITION"),
        ("conflict", "UNRESOLVED_GRAMMATICAL_DEFINITION"),
    ],
)
def test_unread_modal_cannot_become_an_asserted_event(catalog_path, tmp_path, case, code):
    path = tmp_path / "altered.db"
    shutil.copyfile(catalog_path, path)
    conn = sqlite3.connect(path)
    try:
        if case == "missing":
            conn.execute("DELETE FROM definition_states WHERE entry_id=?", ("gse_closed_class:modal:might",))
        else:
            values = [] if case == "unknown" else [("MAYBE", -1), ("MAYBE", 1)]
            _store(conn, "gse_closed_class:modal:might", "might", "auxiliary", values)
        conn.commit()
    finally:
        conn.close()
    with GSEEncoder(str(path)) as encoder:
        with pytest.raises(GrammaticalDefinitionError) as caught:
            encoder.encode("He might leave.")
        assert caught.value.code == code
        event = next(
            event
            for event in encode_document_utterance_events(encoder, [{"id": "modal", "text": "He might leave."}])
            if event["type"] == "utterance"
        )
        assert event["state"] == "unread"
        assert event["tree"] is None
        assert event["error"]["code"] == code


def test_multiple_eligible_ids_never_select_a_first_definition(encoder, monkeypatch):
    from GSE.curation.external_sources import gse_closed_class

    original = gse_closed_class.grammatical_entry_ids

    def ambiguous(word, pos):
        if word == "might" and pos == "AUX":
            return ("gse_closed_class:modal:might", "gse_closed_class:modal:unresolved")
        return original(word, pos)

    monkeypatch.setattr(gse_closed_class, "grammatical_entry_ids", ambiguous)
    with pytest.raises(GrammaticalDefinitionError) as caught:
        encoder.encode("He might leave.")
    assert caught.value.code == "AMBIGUOUS_GRAMMATICAL_DEFINITION"
