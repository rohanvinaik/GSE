"""Versioned dictionary selection through the real encoder and evidence API."""

import json
import sqlite3

import numpy as np
import pytest

from GSE.api.encoder import GSEEncoder
from GSE.api.errors import EncodingError, OOVError
from GSE.curation.lexicon_builder.engine import Assertion, Relation, propagate
from GSE.curation.lexicon_builder.evidence import Definition, Observation
from GSE.curation.lexicon_builder.storage import open_build, store_entry, store_observations
from GSE.lexical_evidence import close_lexical_connections, lookup_lexeme
from GSE.vectors_v2 import bundle, encode_hierarchy


@pytest.fixture
def built_dictionary(tmp_path):
    path = tmp_path / "definitions.db"
    conn = open_build(path)
    banks = ("SOMETHING", "ALIVE", "GOOD", "FEEL", "HAVE", "WHERE", "WANT")
    for entry_id, lemma, values, hierarchy in (
        ("dog:animal", "dog", {"SOMETHING": 1, "ALIVE": 1, "GOOD": 0}, {}),
        ("cat:animal", "cat", {"SOMETHING": 1, "ALIVE": 1, "GOOD": 0}, {}),
        ("bank:finance", "bank", {"SOMETHING": 1, "HAVE": 1}, {}),
        ("bank:river", "bank", {"SOMETHING": 1, "WHERE": 1}, {}),
        ("tired:state", "tired", {"GOOD": -1, "FEEL": 1}, {"GOOD": 2, "FEEL": -1}),
        ("bad:evaluation", "bad", {"GOOD": -1}, {"GOOD": 2}),
        ("silent:state", "silent", {}, {}),
    ):
        assertions = tuple(Assertion(bank, value, "fixture", entry_id, "dictionary") for bank, value in values.items())
        resolution = propagate(banks, assertions, ())
        definition = Definition(entry_id, lemma, "n" if lemma in {"dog", "cat", "bank"} else "a", entry_id)
        store_entry(conn, definition, resolution, assertions, hierarchy)
    conflict = (
        Assertion("GOOD", 1, "s1", "r1", "dictionary"),
        Assertion("GOOD", -1, "s2", "r2", "dictionary"),
    )
    store_entry(
        conn, Definition("clash:state", "clash", "n", "conflicting evidence"), propagate(banks, conflict, ()), conflict
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def encoder(built_dictionary):
    with GSEEncoder(str(built_dictionary)) as result:
        yield result


def test_distinct_entries_can_have_equal_vectors(encoder):
    dog = encoder.lookup_definition("dog:animal")
    cat = encoder.lookup_definition("cat:animal")
    assert dog["code"] == cat["code"] == "IDENTIFIED"
    assert dog["selected"]["entry_id"] != cat["selected"]["entry_id"]
    np.testing.assert_array_equal(
        encoder.encode_definition("dog:animal").to_dense(),
        encoder.encode_definition("cat:animal").to_dense(),
    )


def test_ambiguous_spelling_does_not_choose_first_definition(encoder):
    word, sentence, operation = encoder._lookup_lexeme("bank")
    assert word == sentence == operation == {}
    evidence = encoder.lexical_lookup("bank")
    assert evidence["selection_status"] == "AMBIGUOUS"
    assert evidence["state"] == "unread"
    assert evidence["selected_record"] is None
    assert evidence["primitives"] == {}
    assert evidence["sense_resolved"] is False
    assert evidence["candidate_entry_ids"] == ["bank:finance", "bank:river"]


def test_contextual_grounding_binds_exact_native_senses_and_preserves_open_domains(tmp_path):
    path = tmp_path / "wordnet.db"
    rows = (
        ("bank", "bank.n.01", "Sloping land beside a body of water.", ["The bank of the river."]),
        ("bank", "depository_financial_institution.n.01", "A financial institution.", ["A mortgage from the bank."]),
        ("river", "river.n.01", "A natural stream of water.", []),
        ("mortgage", "mortgage.n.01", "A loan secured by property.", []),
        ("electrician", "electrician.n.01", "A skilled electrical worker.", []),
        ("light", "light.n.08", "A person regarded fondly.", []),
        ("light", "light.n.02", "A source of illumination.", []),
    )
    conn = open_build(path)
    try:
        for lemma, synset, gloss, examples in rows:
            entry_id = f"wordnet:{lemma}:{synset}"
            definition = Definition(entry_id, lemma, "noun", gloss)
            assignments = (
                Assertion("SOMETHING", 1, "fixture", entry_id, "test"),
                Assertion("GOOD", 0, "fixture", entry_id, "test"),
            )
            store_entry(conn, definition, propagate(("GOOD", "SOMETHING", "WANT"), assignments, ()), assignments)
            store_observations(
                conn,
                (
                    Observation(
                        entry_id,
                        "wordnet_hierarchy",
                        entry_id,
                        "wordnet",
                        {
                            "lemma": lemma,
                            "pos": "noun",
                            "definition": gloss,
                            "synset_name": synset,
                            "lemma_names": [lemma],
                            "hypernym_paths": [
                                [
                                    "entity.n.01",
                                    *(["person.n.01"] if synset in {"electrician.n.01", "light.n.08"} else []),
                                    synset,
                                ]
                            ],
                            "examples": examples,
                        },
                        "lexical",
                    ),
                ),
            )
        conn.commit()
    finally:
        conn.close()

    with GSEEncoder(path) as enc:
        for sentence, expected in (
            ("The river rose above the bank.", "wordnet:bank:bank.n.01"),
            ("The bank approved the mortgage.", "wordnet:bank:depository_financial_institution.n.01"),
            ("The river flooded. I saw a bank.", None),
            ("The river and mortgage are near the bank.", None),
        ):
            token = next(token for token in enc.encode(sentence).tokens if token.lemma == "bank")
            evidence = token.lexical_evidence
            if expected is None:
                assert evidence["selection_status"] == "AMBIGUOUS"
                assert token.word_primitives == {}
            else:
                assert evidence["selected_record"]["entry_id"] == expected
                assert evidence["domains"]["GOOD"] == [0]
                assert evidence["domains"]["WANT"] == [-1, 0, 1]
                assert token.word_primitives == {"SOMETHING": 1}
        light = next(
            token for token in enc.encode("An electrician repaired the light.").tokens if token.lemma == "light"
        )
        assert light.lexical_evidence["selection_status"] == "AMBIGUOUS"
        assert light.lexical_evidence["contextual_grounding"]["code"] == "TYPE_COHERENCE_WITHOUT_LEXICAL_WITNESS"
        assert light.word_primitives == {}


def test_normal_sentence_trace_reports_ambiguity_without_lexical_activation(encoder):
    trace = encoder.encode("bank")
    token = trace.tokens[0]
    assert token.word_primitives == {}
    assert token.word_vec_nnz == 0
    assert token.lexicon_status == "unread"
    assert token.lexical_evidence["selection_status"] == "AMBIGUOUS"
    assert token.lexical_evidence["selected_record"] is None
    assert token.lexical_evidence["candidate_entry_ids"] == ["bank:finance", "bank:river"]


def test_explicit_selection_identifies_each_definition(encoder, built_dictionary):
    finance = encoder.lookup_definition("bank:finance")
    river = encoder.lookup_definition("bank:river")
    assert finance["selected"]["assignments"] == {"HAVE": 1, "SOMETHING": 1}
    assert river["selected"]["assignments"] == {"SOMETHING": 1, "WHERE": 1}
    assert not np.array_equal(
        encoder.encode_definition("bank:finance").to_dense(),
        encoder.encode_definition("bank:river").to_dense(),
    )
    evidence = lookup_lexeme("bank", built_dictionary, entry_id="bank:river")
    assert evidence["selection_status"] == "IDENTIFIED"
    assert evidence["selected_record"]["entry_id"] == "bank:river"
    assert evidence["sense_resolved"] is True
    assert evidence["ambiguous"] is False


def test_wrong_entry_identity_never_falls_back_to_another_word(built_dictionary):
    evidence = lookup_lexeme("bank", built_dictionary, entry_id="dog:animal")
    assert evidence["selection_status"] == "NOT_FOUND"
    assert evidence["selected_record"] is None
    assert evidence["primitives"] == {}


def test_partial_definition_preserves_zero_and_silence_in_evidence(encoder):
    evidence = encoder.lexical_lookup("dog")
    assert evidence["selection_status"] == "IDENTIFIED"
    assert evidence["definition_status"] == "PARTIAL"
    assert evidence["selected_record"]["assignments"]["GOOD"] == 0
    assert any(row["primitive"] == "GOOD" and row["value"] == 0 for row in evidence["primitive_evidence"])
    assert not any(row["primitive"] == "WANT" for row in evidence["primitive_evidence"])
    assert evidence["domains"]["GOOD"] == [0]
    assert evidence["domains"]["WANT"] == [-1, 0, 1]
    assert evidence["primitives"] == {"ALIVE": 1, "SOMETHING": 1}
    assert encoder.encode_definition("dog:animal").nnz > 0


def test_entirely_silent_identified_definition_stays_empty(encoder):
    evidence = encoder.lexical_lookup("silent")
    assert evidence["selection_status"] == "IDENTIFIED"
    assert evidence["definition_status"] == "PARTIAL"
    assert evidence["primitive_evidence"] == []
    assert evidence["state"] == "unread"
    assert evidence["reason"] == "UNRESOLVED_DEFINITION_VALUES"
    assert evidence["sense_resolved"] is True
    assert evidence["selected_record"]["entry_id"] == "silent:state"
    assert encoder.encode_definition("silent:state").nnz == 0
    token = encoder.encode("silent").tokens[0]
    assert token.lexicon_status == "unread"
    assert token.word_vec_nnz == 0


@pytest.mark.parametrize("values,partial", [({}, True), ({"GOOD": 0}, True), ({"GOOD": 0, "FEEL": 0}, False)])
def test_empty_partial_and_justified_zero_have_distinct_negation_evidence(tmp_path, values, partial):
    from GSE.nlp.morphology import NEGATION, negation_admission

    path = tmp_path / "zero-evidence.db"
    conn = open_build(path)
    assertions = tuple(Assertion(bank, value, "fixture", "unhappy:1", "dictionary") for bank, value in values.items())
    store_entry(
        conn,
        Definition("unhappy:1", "unhappy", "a", "fixture definition"),
        propagate(("GOOD", "FEEL"), assertions, ()),
        assertions,
    )
    conn.commit()
    conn.close()
    evidence = lookup_lexeme("unhappy", path)
    assert evidence["state"] == ("unread" if partial else "no_primes")
    assert evidence["selected_record"]["assignments"] == values
    assert evidence["primitives"] == {}
    assert evidence["domains"]["FEEL"] == ([-1, 0, 1] if partial else [0])
    admission = negation_admission(
        {"state": "resolved", "feature": NEGATION},
        evidence,
        {"state": "primes", "selected_record": {"pos": "a"}, "primitives": {"GOOD": 1}},
        "ADJ",
    )
    assert admission["decision"] == "preserve"
    assert admission["code"] == ("lexical_unread" if partial else "surface_lexical_zero")


def test_conflicted_definition_never_publishes_a_vector(encoder):
    assert encoder._lookup_lexeme("clash") == ({}, {}, {})
    assert encoder.lookup_definition("clash:state")["code"] == "CONFLICT"
    evidence = encoder.lexical_lookup("clash")
    assert evidence["selection_status"] == "CONFLICT"
    assert evidence["selected_record"] is None
    assert evidence["primitives"] == {}
    with pytest.raises(ValueError, match="DEFINITION_CONFLICT"):
        encoder.encode_definition("clash:state")
    token = encoder.encode("clash").tokens[0]
    assert token.word_vec_nnz == 0
    assert token.lexicon_status == "unread"


def test_not_found_and_strict_unknown_are_distinct_from_ambiguity(encoder, built_dictionary):
    assert encoder.lookup_definition("missing:definition")["code"] == "NOT_FOUND"
    with pytest.raises(ValueError, match="DEFINITION_NOT_FOUND"):
        encoder.encode_definition("missing:definition")
    assert encoder.lexical_lookup("unlistedword")["selection_status"] == "NOT_FOUND"
    with GSEEncoder(str(built_dictionary), strict=True) as strict:
        assert strict._lookup_lexeme("bank") == ({}, {}, {})
        with pytest.raises(OOVError):
            strict._lookup_lexeme("unlistedword")


def test_each_hierarchy_target_uses_its_own_signed_base(encoder):
    before = encoder.lookup_definition("tired:state")["selected"]
    expected = bundle(
        [
            encode_hierarchy(
                encoder.word_basis.get_primitive("GOOD").negate(), encoder.word_basis.get_primitive("HIER_PLUS"), 2
            ),
            encode_hierarchy(
                encoder.word_basis.get_primitive("FEEL"), encoder.word_basis.get_primitive("HIER_MINUS"), 1
            ),
        ]
    )
    actual = encoder.encode_definition("tired:state")
    np.testing.assert_array_equal(actual.to_dense(), expected.to_dense())
    after = encoder.lookup_definition("tired:state")["selected"]
    assert before["assignments"] == after["assignments"] == {"FEEL": 1, "GOOD": -1}
    assert after["hierarchy"] == {"FEEL": -1, "GOOD": 2}
    assert "NUMBER" not in after["assignments"]


@pytest.mark.parametrize("level", [-2, 0, 2])
def test_number_hierarchy_does_not_flip_the_base_sign(encoder, level):
    encoder.conn.execute(
        "UPDATE definition_states SET hierarchy=? WHERE entry_id='bad:evaluation'",
        (json.dumps({"GOOD": level}),),
    )
    encoder.conn.commit()
    base = encoder.word_basis.get_primitive("GOOD")
    vector = encoder.encode_definition("bad:evaluation")
    assert base.bank is not None
    np.testing.assert_array_equal(vector.with_bank_only(base.bank).to_dense(), base.negate().to_dense())


def test_normal_encode_uses_stored_per_target_hierarchy(encoder):
    token = encoder.encode("bad").tokens[0]
    assert token.word_primitives == {"GOOD": -1}
    assert token.lexical_evidence["hierarchy"] == {"GOOD": 2}
    assert token.word_vec_nnz == encoder.encode_definition("bad:evaluation").nnz


def test_missing_parser_lemma_can_use_exact_surface_definition(encoder):
    token = encoder.encode("tired").tokens[0]
    assert token.lemma == "tire"
    assert token.word_primitives == {"FEEL": 1, "GOOD": -1}
    assert token.lexical_evidence["lookup_form"] == "tired"
    assert token.lexical_evidence["parser_lemma"] == "tire"
    assert token.lexical_evidence["selected_record"]["entry_id"] == "tired:state"
    assert token.lexical_evidence["hierarchy"] == {"FEEL": -1, "GOOD": 2}
    assert token.word_vec_nnz == encoder.encode_definition("tired:state").nnz


def test_surface_fallback_does_not_choose_among_ambiguous_definitions(encoder):
    assertions = (Assertion("GOOD", 1, "fixture", "second", "dictionary"),)
    store_entry(
        encoder.conn,
        Definition("tired:other", "tired", "a", "different definition"),
        propagate(("GOOD",), assertions, ()),
        assertions,
    )
    encoder.conn.commit()
    token = encoder.encode("tired").tokens[0]
    assert token.word_primitives == {}
    assert token.lexical_evidence["lookup_form"] == "tired"
    assert token.lexical_evidence["selection_status"] == "AMBIGUOUS"
    assert token.lexical_evidence["candidate_entry_ids"] == ["tired:other", "tired:state"]


def test_ambiguous_parser_lemma_does_not_fall_back_to_unique_surface(encoder):
    for entry_id, value in (("tire:one", 1), ("tire:two", -1)):
        assertions = (Assertion("GOOD", value, "fixture", entry_id, "dictionary"),)
        store_entry(
            encoder.conn,
            Definition(entry_id, "tire", "v", entry_id),
            propagate(("GOOD",), assertions, ()),
            assertions,
        )
    encoder.conn.commit()
    token = encoder.encode("tired").tokens[0]
    assert token.word_primitives == {}
    assert token.lexical_evidence["lookup_form"] == "tire"
    assert token.lexical_evidence["selection_status"] == "AMBIGUOUS"
    assert token.lexical_evidence["candidate_entry_ids"] == ["tire:one", "tire:two"]


@pytest.mark.parametrize(
    "entry_id,hierarchy,code",
    [
        ("dog:animal", {"GOOD": 1}, "HIERARCHY_REQUIRES_NONZERO_BASE"),
        ("dog:animal", {"WANT": 1}, "HIERARCHY_REQUIRES_NONZERO_BASE"),
        ("bad:evaluation", {"GOOD": True}, "INVALID_HIERARCHY_LEVEL"),
        ("bad:evaluation", {"GOOD": 1.5}, "INVALID_HIERARCHY_LEVEL"),
    ],
)
def test_malformed_hierarchy_cannot_create_or_alter_base(encoder, entry_id, hierarchy, code):
    encoder.conn.execute("UPDATE definition_states SET hierarchy=? WHERE entry_id=?", (json.dumps(hierarchy), entry_id))
    encoder.conn.commit()
    with pytest.raises(ValueError, match=code):
        encoder.encode_definition(entry_id)


def test_unsupported_builder_version_is_not_treated_as_legacy(built_dictionary):
    with sqlite3.connect(built_dictionary) as conn:
        conn.execute("UPDATE builder_metadata SET value=? WHERE key='format'", (json.dumps("future/99"),))
    with pytest.raises(ValueError, match="UNSUPPORTED_BUILD_FORMAT"):
        GSEEncoder(str(built_dictionary))
    evidence = lookup_lexeme("dog", built_dictionary)
    assert evidence["state"] == "unread"
    assert evidence["selected_record"] is None


def test_legacy_dictionary_keeps_existing_selection_contract(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE lexemes (id INTEGER PRIMARY KEY, lemma TEXT, pos TEXT,
              comp_primitive TEXT, comp_arity INTEGER, comp_operation TEXT);
            CREATE TABLE primitive_values (lexeme_id INTEGER, primitive TEXT, value INTEGER);
            CREATE TABLE sentence_primitive_values (lexeme_id INTEGER, primitive TEXT, value INTEGER);
            INSERT INTO lexemes(id,lemma,pos) VALUES (1,'bank','NOUN'), (2,'bank','NOUN');
            INSERT INTO primitive_values VALUES (1,'HAVE',1),(2,'WHERE',1);
        """)
    with GSEEncoder(str(path)) as legacy:
        assert legacy._lookup_lexeme("bank")[0] == {"HAVE": 1}
        evidence = legacy.lexical_lookup("bank")
        assert evidence["selection_policy"] == "lemma-pos-consumable-id/2"
        assert evidence["selected_record"]["id"] == 1
        assert evidence["ambiguous"] is True
        with pytest.raises(ValueError, match="DEFINITION_SELECTION_REQUIRES_VERSIONED_DATABASE"):
            legacy.lookup_definition("bank:any")


def test_retired_release_rows_never_supply_an_encoding(tmp_path):
    """MUST-NOT: a row released by the retired upstream constructor is read as an ordinary flat row."""
    path = tmp_path / "retired-release.db"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE lexemes (id INTEGER PRIMARY KEY, lemma TEXT, pos TEXT, source TEXT,
              validation_status TEXT, comp_primitive TEXT, comp_arity INTEGER, comp_operation TEXT);
            CREATE TABLE primitive_values (lexeme_id INTEGER, primitive TEXT, value INTEGER);
            CREATE TABLE sentence_primitive_values (lexeme_id INTEGER, primitive TEXT, value INTEGER);
            INSERT INTO lexemes(id,lemma,pos,source,validation_status)
              VALUES (1,'vague','ADJ','gse_symbolic_release','symbolic_partial'), (2,'good','ADJ','wordnet','reviewed');
            INSERT INTO primitive_values VALUES (1,'GOOD',1),(2,'GOOD',1);
        """)
    try:
        refused = lookup_lexeme("vague", path)
        assert refused["state"] == "unread"
        assert refused["reason"] == "RETIRED_RELEASE_FORMAT"
        assert refused["primitives"] == {}
        assert lookup_lexeme("good", path)["primitives"] == {"GOOD": 1}  # ordinary flat rows are unaffected
        with GSEEncoder(str(path)) as lenient:
            assert lenient._lookup_lexeme("vague") == ({}, {}, {})
        with GSEEncoder(str(path), strict=True) as strict:
            with pytest.raises(EncodingError, match="RETIRED_RELEASE_FORMAT"):
                strict.encode("vague")
    finally:
        close_lexical_connections()


@pytest.mark.parametrize("empty_table", [False, True])
def test_encoder_closes_connection_when_database_is_not_usable(tmp_path, monkeypatch, empty_table):
    path = tmp_path / "unusable.db"
    conn = sqlite3.connect(path)
    if empty_table:
        conn.execute("CREATE TABLE lexemes (id INTEGER)")
    conn.close()
    original = sqlite3.connect
    opened = []

    def tracked(*args, **kwargs):
        result = original(*args, **kwargs)
        opened.append(result)
        return result

    monkeypatch.setattr(sqlite3, "connect", tracked)
    with pytest.raises(ValueError, match="0 lexemes|no 'lexemes' table"):
        GSEEncoder(str(path))
    assert opened
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


@pytest.mark.parametrize("word", ["dog", "bank", "missing"])
def test_lexical_evidence_closes_connection_on_all_selection_paths(built_dictionary, monkeypatch, word):
    original = sqlite3.connect
    opened = []

    def tracked(*args, **kwargs):
        result = original(*args, **kwargs)
        opened.append(result)
        return result

    monkeypatch.setattr(sqlite3, "connect", tracked)
    close_lexical_connections()
    lookup_lexeme(word, built_dictionary)
    assert opened
    # Lookups share a per-thread cached connection (tests/test_lexical_connection_cache.py);
    # releasing the cache must close every connection any selection path opened.
    close_lexical_connections()
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


@pytest.mark.parametrize("base,negative", [("happy", "unhappy"), ("fair", "unfair")])
def test_negative_prefix_cannot_overwrite_an_explicit_zero(tmp_path, base, negative):
    path = tmp_path / "negative.db"
    conn = open_build(path)
    try:
        for word, values in ((base, {"GOOD": 1, "FEEL": 1}), (negative, {"GOOD": -1, "FEEL": 0})):
            assertions = tuple(Assertion(bank, value, "fixture", word, "dictionary") for bank, value in values.items())
            store_entry(
                conn,
                Definition(word + ":1", word, "a", word),
                propagate(("GOOD", "FEEL"), assertions, ()),
                assertions,
            )
        conn.commit()
    finally:
        conn.close()
    with GSEEncoder(str(path)) as encoder:
        token = encoder.encode(negative).tokens[0]
        assert token.lexical_evidence["selected_record"]["assignments"] == {"GOOD": -1, "FEEL": 0}
        assert token.word_primitives == {"GOOD": -1}
        assert token.negation_evidence["admission"]["decision"] == "preserve"
        assert token.negation_evidence["admission"]["code"] == "selected_definition_assignment_conflict"
        assert token.word_vec_nnz == encoder.encode_definition(negative + ":1").nnz


def test_negative_prefix_cannot_escape_a_remaining_domain(tmp_path):
    path = tmp_path / "negative-domain.db"
    conn = open_build(path)
    try:
        for word, values in (("happy", {"GOOD": 1, "FEEL": 1}), ("unhappy", {"GOOD": -1})):
            assertions = tuple(Assertion(bank, value, "fixture", word, "dictionary") for bank, value in values.items())
            rules = (
                (Relation("nonpositive", ("FEEL",), ((-1,), (0,)), ("fixture",), approved=True),)
                if word == "unhappy"
                else ()
            )
            store_entry(
                conn,
                Definition(word + ":1", word, "a", word),
                propagate(("GOOD", "FEEL"), assertions, rules),
                assertions,
            )
        conn.commit()
    finally:
        conn.close()
    with GSEEncoder(str(path)) as encoder:
        token = encoder.encode("unhappy").tokens[0]
        assert token.lexical_evidence["domains"]["FEEL"] == [-1, 0]
        assert token.word_primitives == {"GOOD": -1}
        assert token.negation_evidence["admission"]["decision"] == "preserve"
        assert token.negation_evidence["admission"]["code"] == "selected_definition_domain_conflict"
