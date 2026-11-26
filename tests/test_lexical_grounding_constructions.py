"""Grounding must keep candidate identity, competing evidence and open banks."""

import pytest  # noqa: E402

pytest.importorskip(
    "GSE.curation.lexicon_builder.storage",
    reason="fixture lexicons await the rebuilt artifact writer (rebuild-lexicon-symbolic-closure task 10.1)",
)

from dataclasses import replace

import pytest
from nltk.corpus import wordnet as wn

from GSE.api.encoder import GSEEncoder
from GSE.curation.lexicon_builder.engine import Assertion, propagate
from GSE.curation.lexicon_builder.evidence import Definition, Observation
from GSE.curation.lexicon_builder.storage import open_build, store_entry, store_observations
from GSE.symbolic.lexical_grounding import LexicalGrounding, _unique_native_witness


@pytest.fixture(scope="module")
def encoder(tmp_path_factory):
    path = tmp_path_factory.mktemp("grounding-constructions") / "native.db"
    lexemes = (
        "cut",
        "buying",
        "sunrise",
        "horizon",
        "sun",
        "shot",
        "arrest",
        "incident",
        "accident",
        "sleeping",
        "anger",
        "nonbeing",
        "nonexistence",
    )
    conn = open_build(path)
    try:
        for word in lexemes:
            for sense in wn.synsets(word, pos=wn.NOUN):
                if word not in sense.lemma_names():
                    continue
                entry_id = f"wordnet:{word}:{sense.name()}"
                gloss = sense.definition()
                definition = Definition(entry_id, word, "noun", gloss)
                assertions = (Assertion("GOOD", 0, "fixture", entry_id, "dictionary"),)
                store_entry(conn, definition, propagate(("BE", "DO", "GOOD"), assertions, ()), assertions)
                observation = Observation(
                    entry_id,
                    "wordnet_hierarchy",
                    entry_id,
                    "wordnet",
                    {
                        "lemma": word,
                        "pos": "noun",
                        "definition": gloss,
                        "synset_name": sense.name(),
                        "lemma_names": sense.lemma_names(),
                        "hypernym_paths": [[node.name() for node in thread] for thread in sense.hypernym_paths()],
                        "examples": sense.examples(),
                    },
                    "lexical",
                )
                store_observations(conn, (observation,))
        # Buying has a single exact WordNet noun and still needs contextual evidence
        # to distinguish it from records elsewhere in the lexical snapshot.
        for word in ("buying", "sleeping", "anger", "nonbeing", "nonexistence"):
            alternative = Definition(f"fixture:{word}:other", word, "noun", "an alternative record")
            store_entry(conn, alternative, propagate(("BE", "DO", "GOOD"), (), ()))
        conn.commit()
    finally:
        conn.close()
    with GSEEncoder(path) as instance:
        instance.conn.execute("PRAGMA query_only=ON")
        yield instance


@pytest.mark.parametrize(
    "sentence, token, entry",
    [
        (
            "With one cut, she divided the rope into two parts.",
            "cut",
            "wordnet:cut:cut.n.17",
        ),
        (
            "The buying took all morning as she purchased supplies for the shop.",
            "buying",
            "wordnet:buying:buying.n.01",
        ),
        (
            "The sunrise came before six, when the sun rose above the horizon.",
            "sunrise",
            "wordnet:sunrise:sunrise.n.03",
        ),
        ("He was surprised by the shot.", "shot", None),
        ("The man remained in arrest after the police detained him.", "arrest", None),
        ("An incident delayed the train by twenty minutes.", "incident", None),
        (
            "The incident was a single distinct event that delayed the train.",
            "incident",
            "wordnet:incident:incident.n.01",
        ),
        ("The incident was a public disturbance.", "incident", "wordnet:incident:incident.n.02"),
        ("The incident caused a public disturbance.", "incident", None),
        ("The incident was a public disturbance or a single distinct event.", "incident", None),
        ("The incident seems to be a public disturbance.", "incident", None),
        ("The incident was a public disturbance?", "incident", None),
        ("The incident was not a public disturbance.", "incident", None),
        ("It was an accident that the two trains arrived at the same minute.", "accident", None),
        ("The accident was a chance event.", "accident", "wordnet:accident:accident.n.02"),
        ("The accident was a mishap that caused damage and injury.", "accident", "wordnet:accident:accident.n.01"),
        ("The accident caused a chance event.", "accident", None),
        ("The accident was a stroke.", "accident", None),
        ("The arrest was a state of inactivity.", "arrest", "wordnet:arrest:arrest.n.02"),
        ("The anger was the state of being angry.", "anger", "wordnet:anger:anger.n.02"),
        ("Sleeping is the state of being asleep.", "Sleeping", "wordnet:sleeping:sleeping.n.01"),
        ("Nonbeing is the state of not being.", "Nonbeing", "wordnet:nonbeing:nonbeing.n.01"),
        ("Nonexistence is the state of not existing.", "Nonexistence", "wordnet:nonexistence:nonexistence.n.01"),
        ("The arrest was not a state of inactivity.", "arrest", None),
        ("The anger was not the state of being angry.", "anger", None),
        ("The arrest was a state of inactivity?", "arrest", None),
        ("The arrest was a state of inactivity or an action.", "arrest", None),
        ("Sleeping seems to be the state of being asleep.", "Sleeping", None),
        ("Sleeping thanked Alice.", "Sleeping", None),
        ("Anger was a friend of Alice.", "Anger", None),
        ("Nonbeing is not the state of not being.", "Nonbeing", None),
        ("The anger caused the state of being angry.", "anger", None),
    ],
)
def test_contextual_grounding_through_encoder(encoder, sentence, token, entry):
    actual = next(t for t in encoder.encode(sentence).tokens if t.token == token)
    selected = actual.lexical_evidence.get("selected_record") or {}
    assert selected.get("entry_id") == entry
    if token == "buying":
        assert selected["domains"]["DO"] == [-1, 0, 1]
        assert "DO" not in actual.word_primitives
    if entry is not None:
        assert selected["domains"]["BE"] == [-1, 0, 1]
        assert "BE" not in actual.word_primitives


def test_construction_competition_abstains():
    assert _unique_native_witness({"a": {}, "b": {}}) == {
        "code": "COMPETING_DEFINITION_CONSTRUCTIONS",
        "construction_candidates": ["a", "b"],
    }


def test_bare_one_remains_available_as_subject(encoder):
    cut = next(t for t in encoder.encode("One cut the rope into two parts.").tokens if t.token == "cut")
    assert cut.pos == "VERB"


def test_capitalized_subject_cannot_use_nominal_support_without_definition(encoder, monkeypatch):
    doc = encoder.nlp("Sleeping thanked Alice.")
    grounding = LexicalGrounding(encoder.conn, doc, set())
    candidates = encoder.lexical_lookup("sleeping")["candidate_entry_ids"]
    monkeypatch.setattr(
        LexicalGrounding,
        "_nominal_support",
        lambda *args: {"code": "EXACT_WORDNET_SENSE", "entry_id": "wordnet:sleeping:sleeping.n.01"},
    )
    actual = grounding.select(0, "sleeping", candidates)
    assert actual["code"] == "NO_DEFINITION_CONSTRUCTION_WITNESS"


def test_modal_definition_is_not_asserted(encoder):
    grounding = LexicalGrounding(encoder.conn, encoder.nlp("Sleeping may be the state of being asleep."), set())
    assert grounding._definition_predication(0) is None


def test_state_genus_requires_verified_state_type_and_same_condition(encoder):
    grounding = LexicalGrounding(encoder.conn, encoder.nlp("The arrest was a state of inactivity."), set())
    predicate = grounding._definition_predication(1)
    sense = grounding._senses("arrest")["wordnet:arrest:arrest.n.02"]
    assert LexicalGrounding._matches_definition_predication(sense, predicate)
    assert not LexicalGrounding._matches_definition_predication(
        replace(sense, nodes=sense.nodes - {"state.n.02"}), predicate
    )
    assert not LexicalGrounding._matches_definition_predication(
        replace(sense, gloss="the state of not experiencing inactivity"), predicate
    )


def test_unfinished_state_condition_does_not_identify_a_definition(encoder):
    token = next(t for t in encoder.encode("Sleeping is the state of being.").tokens if t.token == "Sleeping")
    assert token.lexical_evidence["selection_status"] == "AMBIGUOUS"
    assert "BE" not in token.word_primitives
