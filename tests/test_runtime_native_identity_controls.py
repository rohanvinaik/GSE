"""Actual activated resource, native parser and public encoder identity witnesses."""

import pytest

from GSE.api import GSEEncoder


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as instance:
        instance.conn.execute("PRAGMA query_only=ON")
        yield instance


@pytest.mark.parametrize(
    "text",
    [
        "He is an entity.",
        "He is a thing.",
        "He is an organism.",
        "He is an animal.",
        "He is a person.",
        "He is happy.",
        "He studies helium.",
        "He discusses gas.",
        "He is not a gas.",
        "He is an inert gas?",
    ],
)
def test_broad_ancestor_or_unasserted_type_cannot_veto_person_reference(encoder, text):
    token = encoder.encode(text).tokens[0]
    assert token.lexical_evidence["selected_record"]["entry_id"] == "gse_closed_class:pronoun:he"
    assert token.word_primitives == {"SOMEONE": 1}


def test_exact_native_context_is_consumed_not_dropped_after_pos_challenge(encoder):
    token = encoder.encode("He is an inert gas.").tokens[0]
    evidence = token.lexical_evidence
    assert evidence["selected_record"]["entry_id"] == "wordnet:he:helium.n.01"
    assert evidence["reading_eligibility"]["code"] == "CONTEXTUAL_DEFINITION_SELECTED"
    assert evidence["contextual_grounding"]["code"] == "EXACT_WORDNET_SENSE"
    assert token.pos == "NOUN"  # prevents subsequent pronoun recency binding
    assert token.word_primitives == {k: v for k, v in evidence["selected_record"]["assignments"].items() if v}
    assert evidence["domains"] == encoder.lookup_definition("wordnet:he:helium.n.01")["selected"]["domains"]
    assert evidence["domains"]["WANT"] == [-1, 0, 1]


def test_native_expansion_name_and_type_thread_identify_symbol_not_person(encoder):
    token = next(t for t in encoder.encode("The chemical symbol He denotes helium.").tokens if t.token == "He")
    evidence = token.lexical_evidence
    assert evidence["selected_record"]["entry_id"] == "wordnet:he:helium.n.01"
    witness = evidence["contextual_grounding"]["native_synonym_support"]["wordnet:he:helium.n.01"]
    assert witness["synset"] == "helium.n.01"
    assert witness["context_entry_ids"] == {"helium": "wordnet:helium:helium.n.01"}
    assert token.word_primitives.get("SOMEONE") != 1
    assert evidence["domains"]["WANT"] == [-1, 0, 1]


@pytest.mark.parametrize("text", ["The chemical symbol He was discussed."])
def test_specific_unsupported_reading_remains_named_abstention_not_person(encoder, text):
    token = next(t for t in encoder.encode(text).tokens if t.token == "He")
    assert token.lexical_evidence["selection_status"] == "CONFLICT"
    assert token.lexical_evidence["selected_record"] is None
    assert token.lexical_evidence["reading_eligibility"]["code"] == "GRAMMATICAL_CONTEXT_CONFLICT"
    assert token.word_primitives == {} and token.word_vec_nnz == 0


def test_complete_asserted_native_type_is_independent_of_accidental_verbal_parse(encoder):
    token = encoder.encode("He is a noble gas.").tokens[0]
    assert token.lexical_evidence["selected_record"]["entry_id"] == "wordnet:he:helium.n.01"
    assert token.lexical_evidence["contextual_grounding"]["witness_kind"] == "ASSERTED_NATIVE_READING_TYPE"


@pytest.mark.parametrize(
    "text,lemma,entry,bank",
    [
        (
            "The femur is the longest and thickest bone of the human skeleton.",
            "femur",
            "wordnet:femur:femur.n.01",
            "BODY",
        ),
        ("The teacher is a person whose occupation is teaching.", "teacher", "wordnet:teacher:teacher.n.01", "SOMEONE"),
    ],
)
def test_complete_native_definition_clause_identifies_occurrence_not_spelling(encoder, text, lemma, entry, bank):
    token = next(t for t in encoder.encode(text).tokens if t.lemma == lemma)
    assert token.lexical_evidence["selected_record"]["entry_id"] == entry
    assert token.lexical_evidence["contextual_grounding"]["witness_kind"] == "WORDNET_DEFINITION_CONSTRUCTION"
    assert token.word_primitives[bank] == 1
    assert token.lexical_evidence["domains"]["TOUCH"] == [-1, 0, 1]


@pytest.mark.parametrize(
    "text,lemma",
    [
        ("The femur is the longest bone.", "femur"),
        ("The femur is not the longest and thickest bone of the human skeleton.", "femur"),
        ("The femur is the longest and thickest bone of the human skeleton?", "femur"),
        ("The teacher is a person whose occupation is teaching or nursing.", "teacher"),
        ("The teacher is not a person whose occupation is teaching.", "teacher"),
    ],
)
def test_partial_negated_queried_or_disjunctive_definition_does_not_license_exact_identity(encoder, text, lemma):
    token = next(t for t in encoder.encode(text).tokens if t.lemma == lemma)
    assert token.lexical_evidence["selected_record"] is None


@pytest.mark.parametrize(
    "text, lemma, entry, bank",
    [
        ("I want to go home now.", "want", "desire.v.01", "WANT"),
        ("I think he is very smart.", "think", "think.v.01", "THINK"),
        ("I know that the President lied to the people.", "know", "know.v.01", "KNOW"),
        ("You have to be a good observer to see all the details.", "see", "see.v.01", "SEE"),
        ("She feels resentful.", "feel", "feel.v.01", "FEEL"),
        ("He said that he wanted to marry her.", "say", "state.v.01", "SAY"),
        ("What is happening?", "happen", "happen.v.01", "HAPPEN"),
        ("He moved his hand slightly to the right.", "move", "move.v.03", "MOVE"),
    ],
)
def test_native_predicate_constructions_are_reachable_without_first_sense_selection(encoder, text, lemma, entry, bank):
    token = next(t for t in encoder.encode(text).tokens if t.lemma == lemma)
    proof = token.lexical_evidence["contextual_grounding"]
    assert proof["code"] == "EXACT_WORDNET_SENSE"
    assert proof["witness_kind"] == "WORDNET_NATIVE_EXAMPLE_CONSTRUCTION"
    assert proof["native_examples"] and proof["eligible_pos"] == "VERB"
    assert token.lexical_evidence["selected_record"]["entry_id"] == f"wordnet:{lemma}:{entry}"
    assert token.word_primitives[bank] == 1
    assert token.lexical_evidence["domains"]["TOUCH"] == [-1, 0, 1]


@pytest.mark.parametrize(
    "text,lemma,entry,bank",
    [
        ("She wants to go home now.", "want", "desire.v.01", "WANT"),
        ("You think he is very smart.", "think", "think.v.01", "THINK"),
        ("She knows that the President lied to the people.", "know", "know.v.01", "KNOW"),
        ("He feels resentful.", "feel", "feel.v.01", "FEEL"),
        ("She moved his hand slightly to the right.", "move", "move.v.03", "MOVE"),
    ],
)
def test_person_reference_can_vary_in_complete_source_example_not_arbitrary_frames(encoder, text, lemma, entry, bank):
    token = next(t for t in encoder.encode(text).tokens if t.lemma == lemma)
    proof = token.lexical_evidence["contextual_grounding"]
    assert proof["code"] == "EXACT_WORDNET_SENSE"
    assert proof["witness_kind"] == "WORDNET_NATIVE_EXAMPLE_PERSON_SUBSTITUTION"
    assert proof["subject_role_witnesses"]
    assert token.lexical_evidence["selected_record"]["entry_id"] == f"wordnet:{lemma}:{entry}"
    assert token.word_primitives[bank] == 1
    assert token.lexical_evidence["domains"]["TOUCH"] == [-1, 0, 1]


@pytest.mark.parametrize(
    "text, lemma",
    [
        ("I hear a sound.", "hear"),
        ("I feel pain.", "feel"),
        ("I want to go home now or stay here.", "want"),
        ("I do not want to go home now.", "want"),
    ],
)
def test_pos_or_partial_native_example_cannot_force_a_predicate_reading(encoder, text, lemma):
    trace = encoder.encode(text)
    token = next(t for t in trace.tokens if t.lemma == lemma)
    assert token.lexical_evidence["selection_status"] == "AMBIGUOUS"
    assert token.lexical_evidence["selected_record"] is None
    assert token.word_primitives == {}


@pytest.mark.parametrize(
    "text,lemma,entry",
    [
        ("You want something.", "want", "wordnet:want:desire.v.01"),
        ("She thinks about something.", "think", "nsm_chart:v20:think"),
        ("You know.", "know", "wordnet:know:know.v.01"),
        ("I see someone.", "see", "wordnet:see:see.v.01"),
        ("She hears something.", "hear", "wordnet:hear:hear.v.01"),
        ("You feel something.", "feel", "nsm_chart:v20:feel"),
        ("He says something.", "say", "nsm_chart:v20:say"),
        ("Something happens to me.", "happen", "wordnet:happen:happen.v.01"),
        ("You move.", "move", "nsm_chart:v20:move"),
        ("This is good.", "good", "nsm_chart:v20:good"),
        ("That is bad.", "bad", "nsm_chart:v20:bad"),
        ("Something big.", "big", "nsm_chart:v20:big"),
        ("Something small.", "small", "nsm_chart:v20:small"),
    ],
)
def test_complete_primary_frame_is_compatibility_not_unique_meaning(encoder, text, lemma, entry):
    token = next(t for t in encoder.encode(text).tokens if t.lemma == lemma)
    evidence = token.lexical_evidence
    proof = evidence["contextual_grounding"]
    assert proof["code"] == "PRIMARY_FRAME_COMPATIBLE_NOT_IDENTIFYING"
    assert proof["identity_scope"] == "UNRESOLVED"
    assert proof["compatible_entry_id"] == entry
    assert proof["missing_witness"] == "INDEPENDENT_MEANING_DISCRIMINATION"
    assert evidence["selected_record"] is None
    assert proof["unresolved_ordinary_entry_ids"]  # finer identities were NOT merged
    assert proof["source_reference"]["sha256"] == "5847b39219381181f98a2afbfc57b149ad16cd77157ca0d205b341d1466cf732"
    assert all(frame["source_record_ids"] and frame["role_witnesses"] for frame in proof["frames"])
    assert token.word_primitives == {} and token.word_vec_nnz == 0


@pytest.mark.parametrize(
    "text,lemma",
    [
        ("She feels the cloth.", "feel"),
        ("They hear a case.", "hear"),
        ("She feels good about this.", "feel"),
        ("He moved the proposal.", "move"),
        ("A good ten miles.", "good"),
        ("Something wants someone.", "want"),
        ("He wants something or someone.", "want"),
        ("The rock knows.", "know"),
        ("I see my doctor.", "see"),
        ("The court heard the case.", "hear"),
        ("It was a good forty miles.", "good"),
    ],
)
def test_primary_frame_requires_whole_valency_and_independently_attested_roles(encoder, text, lemma):
    token = next(t for t in encoder.encode(text).tokens if t.lemma == lemma)
    assert token.lexical_evidence["selected_record"] is None
    assert token.word_primitives == {}
    assert token.lexical_evidence["contextual_grounding"]["code"] != "PRIMARY_UNIT_FRAME"


def test_primary_unit_source_observation_must_match_complete_original_features(encoder, monkeypatch):
    from GSE.symbolic import lexical_grounding

    records = {k: dict(v) for k, v in lexical_grounding._primary_records().items()}
    records["nsm_chart:v20:think"]["frame_text"] = "changed frame"
    monkeypatch.setattr(lexical_grounding, "_primary_records", lambda: records)
    token = next(t for t in encoder.encode("You think about something.").tokens if t.lemma == "think")
    assert token.lexical_evidence["selected_record"] is None
    assert token.word_primitives == {}
