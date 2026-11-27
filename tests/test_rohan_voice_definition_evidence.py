"""Voice consumes stored grammatical readings without resolving content homographs."""

import sqlite3
import sys
from pathlib import Path

import pytest

from GSE.api import GSEEncoder
from GSE.curation.external_sources.gse_closed_class import GSEClosedClassParser
from GSE.curation.lexicon_builder import store

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
rohan_voice = pytest.importorskip(
    "rohan_voice",
    reason="scripts/rohan_voice.py, the recognizer these tests exercise, was deleted with the old construction path "
    "(task 0.2, 6c61ecc); the fixture is rebuilt on store.py (task 10.1)",
)


@pytest.fixture
def dictionary(tmp_path, monkeypatch):
    path = tmp_path / "definitions.db"
    parser = GSEClosedClassParser()
    parser.load()
    # The closed-class catalog as the build states it, plus controlled content definitions.
    entries, records = store.closed_class_fixtures(parser)
    entries += [
        store.FixtureEntry(entry_id, lemma, pos, entry_id, values)
        for entry_id, lemma, pos, values in (
            ("fixture:can:container", "can", "noun", {"SOMETHING": 1}),
            ("fixture:help", "help", "verb", {"DO": 1, "GOOD": 0}),
            ("fixture:carry", "carry", "verb", {"DO": 1}),
            ("fixture:happy:one", "happy", "adj", {"GOOD": 1}),
            ("fixture:happy:two", "happy", "adj", {"FEEL": 1}),
            ("fixture:unresolved", "unresolved", "adj", {}),
        )
    ]
    store.fixture(path, entries, records)
    monkeypatch.setenv("GSE_LEXICON", str(path))
    return path


def test_versioned_voice_reads_exact_modal_from_public_trace(dictionary, monkeypatch):
    with GSEEncoder(dictionary) as encoder:
        assert encoder.lexical_lookup("can")["selection_status"] == "AMBIGUOUS"
        token = next(token for token in encoder.encode("You can help.").tokens if token.token == "can")
        assert token.lexical_evidence["selected_record"]["entry_id"] == "gse_closed_class:modal:can"
        assert token.lexical_evidence["primitives"] == {"CAN": 1}

    # The consumer must use that trace, not perform another lemma lookup.
    monkeypatch.setattr(rohan_voice, "lookup_lexeme", lambda *args, **kwargs: pytest.fail("consumer reselected lemma"))
    result = rohan_voice.featurize("You can help.")
    assert result["state"] == "read"
    assert result["populations"] == {"primes": 3, "no_primes": 0, "no_row": 0, "unread": 0}
    assert result["dist"][rohan_voice.CURATED.index("CAN")] == pytest.approx(1 / 3)
    assert result["dist"][rohan_voice.CURATED.index("GOOD")] == 0


def test_same_lemma_in_two_roles_does_not_reuse_modal_reading(dictionary):
    text = "You can carry a can."
    with GSEEncoder(dictionary) as encoder:
        tokens = [token for token in encoder.encode(text).tokens if token.lemma == "can"]
    assert [token.pos for token in tokens] == ["AUX", "NOUN"]
    assert [token.lexical_evidence["selection_status"] for token in tokens] == ["IDENTIFIED", "AMBIGUOUS"]
    result = rohan_voice.featurize(text)
    assert result["state"] == "unread"
    assert result["populations"]["primes"] == 3
    assert result["populations"]["unread"] == 1
    assert "bank" not in result


@pytest.mark.parametrize("word", ["happy", "unresolved", "xqzzzt"])
def test_ambiguous_unresolved_or_absent_content_stays_unread(dictionary, word):
    result = rohan_voice.featurize(f"You can help {word}.")
    assert result["state"] == "unread"
    assert result["reason"] == "incomplete_lexical_features"
    assert result["populations"]["unread"] + result["populations"]["no_row"] == 1
    assert "bank" not in result


def test_missing_required_modal_returns_named_unread(dictionary):
    connection = sqlite3.connect(dictionary)
    try:
        connection.execute("DELETE FROM definition_states WHERE entry_id=?", ("gse_closed_class:modal:can",))
        connection.commit()
    finally:
        connection.close()
    result = rohan_voice.featurize("You can help.")
    assert result["state"] == "unread"
    assert result["reason"] == "MISSING_GRAMMATICAL_DEFINITION"
    assert "bank" not in result


def test_feature_identity_versions_the_selection_change(dictionary):
    identity = rohan_voice.feature_identity()
    assert rohan_voice.SCHEMA == "GSE.rohan-voice/2"
    assert identity["features"] == "GSE.rohan-voice-features/3"
    assert "public encoder token lexical evidence" in identity["tokens"]
    paths = {Path(record["path"]).name for record in identity["code"]}
    assert {"encoder.py", "gse_closed_class.py", "store.py", "lexicon_resource.py"} <= paths  # the artifact writer
    assert all(record["state"] == "read" for record in identity["code"])
