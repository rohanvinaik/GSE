"""Conditional meaning consequences preserve, rather than guess, identities."""

import pytest  # noqa: E402

pytest.importorskip(
    "GSE.curation.lexicon_builder.storage",
    reason="fixture lexicons await the rebuilt artifact writer (rebuild-lexicon-symbolic-closure task 10.1)",
)

import json

import pytest
from nltk.corpus import wordnet as wn

from GSE.api import GSEEncoder
from GSE.api.trace import OperationTrace
from GSE.curation.lexicon_builder import catalog
from GSE.curation.lexicon_builder.engine import Assertion, propagate
from GSE.curation.lexicon_builder.evidence import Definition, Observation
from GSE.curation.lexicon_builder.storage import open_build, store_entry, store_observations
from GSE.discourse.profile import text_profile


@pytest.fixture(scope="module")
def encoder(tmp_path_factory):
    path = tmp_path_factory.mktemp("qualified-profile") / "native.db"
    conn = open_build(path)
    signed = {"good.a.03": 1, "good.s.05": 1, "bad.s.10": -1}
    for word, pos, native_pos in (("good", wn.ADJ, "adj"), ("bad", wn.ADJ, "adj"), ("morally", wn.ADV, "adv")):
        for sense in wn.synsets(word, pos=pos):
            if word not in sense.lemma_names():
                continue
            entry_id = f"wordnet:{word}:{sense.name()}"
            assertions = (
                (Assertion("GOOD", signed[sense.name()], "fixture", entry_id, "dictionary"),)
                if sense.name() in signed
                else ()
            )
            definition = Definition(entry_id, word, native_pos, sense.definition())
            store_entry(conn, definition, propagate(("GOOD", "BE", "DO"), assertions, ()), assertions)
            store_observations(
                conn,
                (
                    Observation(
                        entry_id,
                        "wordnet_hierarchy",
                        entry_id,
                        "wordnet",
                        {
                            "lemma": word,
                            "pos": native_pos,
                            "definition": sense.definition(),
                            "synset_name": sense.name(),
                            "lemma_names": sense.lemma_names(),
                            "hypernym_paths": [[n.name() for n in thread] for thread in sense.hypernym_paths()],
                            "examples": sense.examples(),
                        },
                        "lexical",
                    ),
                ),
            )
    for record in catalog.chart_definition_records():
        if record["entry_id"] not in {"nsm_chart:v20:good", "nsm_chart:v20:bad"}:
            continue
        sign = 1 if record["entry_id"].endswith(":good") else -1
        assertion = Assertion("GOOD", sign, "fixture", record["entry_id"], "dictionary")
        definition = Definition(record["entry_id"], record["lemma"], record["pos"], record["definition"])
        store_entry(conn, definition, propagate(("GOOD", "BE", "DO"), (assertion,), ()), (assertion,))
        store_observations(
            conn,
            (
                Observation(
                    record["entry_id"],
                    "nsm_chart",
                    record["entry_id"],
                    "nsm_primary_chart",
                    json.loads(json.dumps(record)),
                    "source_structure",
                ),
            ),
        )
    # Explicitly preserve a qualifier rival which is NOT the licensed domain.
    definition = Definition("fixture:morally:practically", "morally", "adv", "practically")
    store_entry(conn, definition, propagate(("GOOD", "BE", "DO"), (), ()))
    conn.commit()
    conn.close()
    with GSEEncoder(path) as enc:
        enc.conn.execute("PRAGMA query_only=ON")
        yield enc


@pytest.fixture
def frames(monkeypatch):
    # Test registration follows the reviewed producer interface. The actual
    # candidate audit separately pins A's production catalogue and signed DB.
    result = tuple(
        {
            "warrant_id": "test:reviewed-moral-quality",
            "dimension": "EVALUATION",
            "bank": "GOOD",
            "qualifier": {
                "entry_id": "wordnet:morally:morally.r.01",
                "definition": "with respect to moral principles",
            },
            "quality_meanings": [
                {"entry_id": f"wordnet:{word}:{synset}", "definition": wn.synset(synset).definition()}
                for synset in senses
            ],
            "canonical_pole": f"nsm_chart:v20:{word}",
            "review_sha256": "a" * 64,
        }
        for word, senses in (("good", ("good.a.03", "good.s.05")), ("bad", ("bad.s.10",)))
    )
    monkeypatch.setattr(catalog, "qualified_dimension_frames", lambda: result, raising=False)
    return result


@pytest.mark.parametrize("text,sign", [("Kindness is morally good.", 1), ("Cruelty is morally bad.", -1)])
def test_actual_encoder_profile_conditioned_consequence(encoder, frames, text, sign):
    trace = encoder.encode(text)
    quality = next(t for t in trace.tokens if t.pos == "ADJ")
    assert quality.lexical_evidence["selection_status"] == "AMBIGUOUS"
    assert quality.word_primitives == {}
    constraint = quality.lexical_evidence["qualified_dimensions"][0]
    assert constraint["domain"] == [sign]
    assert constraint["unconditional"] is False
    assert "fixture:morally:practically" in constraint["surviving_qualifier_entry_ids"]
    assert (
        OperationTrace.from_dict(trace.to_dict()).tokens[quality.position].lexical_evidence == quality.lexical_evidence
    )
    profile = text_profile(encoder, text)
    assert profile.affect["valence_mean"] is None
    assert profile.conditioned_affect[0]["valence_mean"] == sign
    assert profile.to_dict()["conditioned_affect"] == profile.conditioned_affect


@pytest.mark.parametrize(
    "text",
    [
        "It was a good forty miles.",
        "Kindness is good.",
        "The morally good teacher repaired the bicycle.",
        "The morally strict teacher is good.",
        "Kindness is morally good news.",
        "I see my doctor.",
        "The court heard the case.",
    ],
)
def test_no_conditional_projection_without_bound_reviewed_quality(encoder, frames, text):
    trace = encoder.encode(text)
    assert not any((t.lexical_evidence or {}).get("qualified_dimensions") for t in trace.tokens)
    assert text_profile(encoder, text).conditioned_affect == []


def test_stale_source_meaning_blocks_consequence(encoder, frames, monkeypatch):
    altered = [{**frames[0], "qualifier": {**frames[0]["qualifier"], "definition": "a different meaning"}}]
    monkeypatch.setattr(catalog, "qualified_dimension_frames", lambda: altered)
    assert text_profile(encoder, "Kindness is morally good.").conditioned_affect == []


def test_unknown_reviewed_quality_bank_is_not_a_signed_premise(encoder, frames, monkeypatch):
    unknown = {
        "entry_id": "wordnet:good:good.a.01",
        "definition": wn.synset("good.a.01").definition(),
    }
    monkeypatch.setattr(catalog, "qualified_dimension_frames", lambda: [{**frames[0], "quality_meanings": [unknown]}])
    assert text_profile(encoder, "Kindness is morally good.").conditioned_affect == []


def test_missing_canonical_pole_blocks_consequence(encoder, frames, monkeypatch):
    monkeypatch.setattr(catalog, "qualified_dimension_frames", lambda: [{**frames[0], "canonical_pole": "absent"}])
    assert text_profile(encoder, "Kindness is morally good.").conditioned_affect == []


@pytest.mark.parametrize("text", ["Kindness is not morally good.", "Kindness is morally very good."])
def test_scope_is_retained_and_not_written_into_word_bank(encoder, frames, text):
    profile = text_profile(encoder, text)
    assert profile.conditioned_affect[0]["domain"] == [1]
    assert profile.affect["valence_mean"] is None
    if "not" in text:
        assert profile.conditioned_affect[0]["scope"] == ["NEGATION"]
