"""Voice consumes stored grammatical readings without resolving content homographs."""

import sys
from pathlib import Path

import pytest

from gse.api import GSEEncoder
from gse.curation.external_sources.gse_closed_class import GSEClosedClassParser
from gse.curation.lexicon_builder.engine import Assertion, propagate
from gse.curation.lexicon_builder.evidence import Definition, collect_evidence
from gse.curation.lexicon_builder.foundation import BANKS
from gse.curation.lexicon_builder.pipeline import build_dictionary
from gse.curation.lexicon_builder.storage import open_build, store_entry

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import rohan_voice  # noqa: E402


@pytest.fixture
def dictionary(tmp_path, monkeypatch):
    path = tmp_path / "definitions.db"
    parser = GSEClosedClassParser()
    parser.load()
    build_dictionary(collect_evidence({"gse_closed_class": parser}, ()), path)
    connection = open_build(path)
    try:
        for entry_id, lemma, pos, values in (
            ("fixture:can:container", "can", "noun", {"SOMETHING": 1}),
            ("fixture:help", "help", "verb", {"DO": 1, "GOOD": 0}),
            ("fixture:carry", "carry", "verb", {"DO": 1}),
            ("fixture:happy:one", "happy", "adj", {"GOOD": 1}),
            ("fixture:happy:two", "happy", "adj", {"FEEL": 1}),
            ("fixture:unresolved", "unresolved", "adj", {}),
        ):
            assertions = tuple(
                Assertion(bank, value, "fixture", entry_id, "dictionary") for bank, value in values.items()
            )
            store_entry(
                connection,
                Definition(entry_id, lemma, pos, entry_id),
                propagate(BANKS, assertions, ()),
                assertions,
            )
        connection.commit()
    finally:
        connection.close()
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
    connection = open_build(dictionary)
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
    assert rohan_voice.SCHEMA == "gse.rohan-voice/2"
    assert identity["features"] == "gse.rohan-voice-features/3"
    assert "public encoder token lexical evidence" in identity["tokens"]
    paths = {Path(record["path"]).name for record in identity["code"]}
    assert {"encoder.py", "gse_closed_class.py", "storage.py", "lexicon_resource.py"} <= paths
    assert all(record["state"] == "read" for record in identity["code"])
