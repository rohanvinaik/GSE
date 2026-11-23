"""Local corpus membership cannot invent lexical meanings or accept bad input."""

import json
from types import SimpleNamespace

import pytest

from GSE.curation import build_wordlist
from GSE.nlp import spellcheck


def configure(tmp_path, monkeypatch, records):
    source = tmp_path / "source.jsonl"
    source.write_text("".join(json.dumps(record) + "\n" for record in records))
    monkeypatch.setattr(build_wordlist, "OUT", tmp_path / "words.txt")
    monkeypatch.setattr(build_wordlist, "TRIE", tmp_path / "words.marisa")
    monkeypatch.setattr(spellcheck, "_DEFAULT_LEXICON", SimpleNamespace(confusions={"teh": ["the"]}))
    return source


def test_local_records_build_exact_membership_without_semantic_values(tmp_path, monkeypatch):
    source = configure(
        tmp_path,
        monkeypatch,
        [
            {"word": "encoder", "lang_code": "en"},
            {"word": "Encoder", "lang_code": "en"},
            {"word": "teh", "lang_code": "en"},
            {"word": "bonjour", "lang_code": "fr"},
            {"word": "two words", "lang_code": "en"},
        ],
    )
    report = build_wordlist.build_from_kaikki(source)
    assert build_wordlist.OUT.read_text() == "encoder\n"
    assert report["semantic_assignments"] == 0
    assert report["known_misspellings_excluded"] == 1
    assert report["words"] == 1
    assert report["records"] == 5
    assert report["storage"] == "TEXT"


@pytest.mark.parametrize("record", [None, [], {}, {"word": 12}])
def test_bad_record_never_replaces_existing_membership(tmp_path, monkeypatch, record):
    source = configure(tmp_path, monkeypatch, [{"word": "encoder", "lang_code": "en"}, record])
    build_wordlist.OUT.write_text("preserved\n")
    with pytest.raises(ValueError, match="INVALID_KAIKKI_WORD_RECORD"):
        build_wordlist.build_from_kaikki(source)
    assert build_wordlist.OUT.read_text() == "preserved\n"


def test_empty_corpus_is_not_a_successful_resource_replacement(tmp_path, monkeypatch):
    source = configure(tmp_path, monkeypatch, [])
    with pytest.raises(ValueError, match="EMPTY_VALIDITY_CORPUS"):
        build_wordlist.build_from_kaikki(source)
    assert not build_wordlist.OUT.exists()
