"""Unread usage is never evidence that a valid tail word is a typo."""

import sqlite3
from types import SimpleNamespace

import pytest

from gse.curation import personal_dictionary
from gse.nlp import heal, spellcheck


def _lexicon(tmp_path, monkeypatch, ranks=None):
    monkeypatch.setattr(spellcheck, "_REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(personal_dictionary, "membership", lambda word: {"state": "not_member"})
    lexicon = spellcheck._Lexicon()
    lexicon._lex_vocab = lexicon._wn_vocab = lexicon._allowlist = frozenset()
    lexicon._validity_vocab = frozenset({"cen"})
    path = tmp_path / "data" / "frequency.db"
    path.parent.mkdir()
    if ranks is not None:
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE frequency (word TEXT, combined_rank)")
            conn.executemany("INSERT INTO frequency VALUES (?, ?)", ranks)
    return lexicon, path


def test_missing_usage_is_unread_and_never_creates_database(tmp_path, monkeypatch):
    lexicon, path = _lexicon(tmp_path, monkeypatch)
    evidence = lexicon.rarity_evidence("cen")
    assert evidence["state"] == "unread" and evidence["reason"] == "usage_frequency_unread"
    assert not lexicon.is_rare_tail("cen") and not path.exists()


@pytest.mark.parametrize("rank", [0, -1, 1.5, "not-a-rank", None])
def test_malformed_usage_cannot_license_tail_recovery(tmp_path, monkeypatch, rank):
    lexicon, path = _lexicon(tmp_path, monkeypatch, [("can", 1), ("broken", rank)])
    before = path.read_bytes()
    assert lexicon.rarity_evidence("cen")["state"] == "unread"
    assert lexicon.usage == {} and path.read_bytes() == before


def test_valid_observed_absence_only_licenses_a_local_slot_check(tmp_path, monkeypatch):
    lexicon, _ = _lexicon(tmp_path, monkeypatch, [("can", 1)])
    evidence = lexicon.rarity_evidence("cen")
    assert evidence["state"] == "rare_tail"
    assert evidence["reason"] == "broad_tail_without_observed_rank"
    assert lexicon.is_common_target("can") and lexicon.is_rare_tail("cen")


def test_observed_tail_word_and_core_words_are_preserved(tmp_path, monkeypatch):
    lexicon, _ = _lexicon(tmp_path, monkeypatch, [("cen", 1_000_000)])
    assert lexicon.rarity_evidence("cen")["state"] == "not_rare_tail"
    assert lexicon.rarity_evidence("cen")["reason"] == "observed_usage"
    lexicon._wn_vocab = frozenset({"quiddity"})
    assert lexicon.rarity_evidence("quiddity")["reason"] == "core_or_protected_word"


def test_healing_consumes_unread_code_and_preserves_word(tmp_path, monkeypatch):
    lexicon, _ = _lexicon(tmp_path, monkeypatch)
    monkeypatch.setattr(heal, "_DEFAULT_LEXICON", lexicon)
    monkeypatch.setattr(heal, "recover_rare_tail", lambda *args: pytest.fail("unread rarity admitted recovery"))
    result = heal._grounded_proposal("cen", 1, object(), False, 5, SimpleNamespace())
    assert result.keep_reason == "rarity_unread"
    assert result.payload["misspelled"] is False
    assert result.evidence[0]["state"] == "unread"
