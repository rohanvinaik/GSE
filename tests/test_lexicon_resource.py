"""Activation selects one versioned resource without fallback or sense collapse."""

import json
import sqlite3

import pytest

from GSE import lexicon_resource
from GSE.api import GSEDecoder, GSEEncoder
from GSE.curation.lexicon_builder.engine import Assertion, propagate
from GSE.curation.lexicon_builder.evidence import Definition
from GSE.curation.lexicon_builder.storage import open_build, store_entry
from GSE.lexical_evidence import lookup_lexeme
from GSE.nlp import heal, spellcheck


def database(path, rows):
    conn = open_build(path)
    for index, (identity, lemma, bank) in enumerate(rows, 1):
        assertion = Assertion(bank, 1, "fixture", identity, "dictionary")
        store_entry(
            conn,
            Definition(identity, lemma, "noun", identity),
            propagate(("SOMETHING", "SOMEONE"), (assertion,), ()),
            (assertion,),
        )
        conn.execute("UPDATE lexemes SET frequency_rank=? WHERE sense_id=?", (index, identity))
    conn.commit()
    conn.close()
    return path


def activate(pointer, target):
    pointer.write_text(json.dumps({"format": lexicon_resource.POINTER_FORMAT, "path": target.name}))


def test_absent_pointer_is_the_only_archive_fallback(tmp_path, monkeypatch):
    pointer = tmp_path / "active.json"
    monkeypatch.setattr(lexicon_resource, "ACTIVE_POINTER", pointer)
    assert lexicon_resource.resolve_lexicon_path() == lexicon_resource.ARCHIVED_LEXICON.resolve()
    pointer.write_text("broken JSON")
    with pytest.raises(ValueError, match="INVALID_ACTIVE_LEXICON"):
        lexicon_resource.resolve_lexicon_path()
    explicit = tmp_path / "explicit.db"
    assert lexicon_resource.resolve_lexicon_path(explicit) == explicit
    assert not explicit.exists()


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"format": "wrong", "path": "x"},
        {"format": lexicon_resource.POINTER_FORMAT, "path": ""},
        {"format": lexicon_resource.POINTER_FORMAT, "path": 42},
        {"format": lexicon_resource.POINTER_FORMAT, "path": "x", "extra": True},
    ],
)
def test_invalid_activation_is_named(tmp_path, payload):
    pointer = tmp_path / "active.json"
    pointer.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="INVALID_ACTIVE_LEXICON"):
        lexicon_resource.resolve_lexicon_path(pointer_path=pointer)


def test_missing_or_unversioned_target_never_creates_or_falls_back(tmp_path):
    pointer = tmp_path / "active.json"
    target = tmp_path / "missing.db"
    activate(pointer, target)
    with pytest.raises(FileNotFoundError, match="ACTIVE_LEXICON_UNAVAILABLE"):
        lexicon_resource.resolve_lexicon_path(pointer_path=pointer)
    assert not target.exists()
    target.write_text("not a database")
    with pytest.raises(ValueError, match="ACTIVE_LEXICON_NOT_VERSIONED"):
        lexicon_resource.resolve_lexicon_path(pointer_path=pointer)


def test_runtime_defaults_and_healer_switch_to_same_activated_build(tmp_path, monkeypatch):
    first = database(tmp_path / "first.db", [("alpha:thing", "alpha", "SOMETHING")])
    second = database(tmp_path / "second.db", [("beta:person", "beta", "SOMEONE")])
    pointer = tmp_path / "active.json"
    monkeypatch.setattr(lexicon_resource, "ACTIVE_POINTER", pointer)
    monkeypatch.setattr(heal, "_enc", None)
    activate(pointer, first)
    lexical = spellcheck._Lexicon()
    explicit = spellcheck._Lexicon(first)
    assert "alpha" in lexical.lex_vocab
    assert lexical.freq == {"alpha": 1}
    assert lexical.primitives("alpha") == {"SOMETHING"}
    old_encoder = heal._encoder()
    assert old_encoder.db_path == first
    activate(pointer, second)
    with GSEEncoder() as encoder, GSEDecoder() as decoder:
        assert encoder.db_path == decoder.db_path == second
        assert lookup_lexeme("beta")["provenance"]["path"] == str(second)
    assert "beta" in lexical.lex_vocab and "alpha" not in lexical.lex_vocab
    assert lexical.freq == {"beta": 1}
    assert not lexical.primitives("alpha")
    assert lexical.primitives("beta") == {"SOMEONE"}
    assert explicit.db_path == str(first) and "alpha" in explicit.lex_vocab
    assert heal._encoder().db_path == second
    with pytest.raises(sqlite3.ProgrammingError):
        old_encoder.conn.execute("SELECT 1")
    heal._encoder().close()
    lexical.conn.close()
    explicit.conn.close()


def test_decoder_preserves_definition_identity_and_queries_own_entity_banks(tmp_path):
    path = database(
        tmp_path / "senses.db",
        [
            ("bank:thing", "bank", "SOMETHING"),
            ("bank:person", "bank", "SOMEONE"),
            ("bank:other", "bank", "SOMETHING"),
        ],
    )
    with GSEDecoder(path) as decoder:
        assert len(decoder.lexeme_vectors) == 3
        assert set(decoder.lexeme_labels.values()) == {"bank"}
        vector = next(iter(decoder.lexeme_vectors.values()))[0]
        entities = decoder._extract_entities(vector, {"SOMETHING": 1})
        assert all(len(entity.primitives) == 1 for entity in entities)


def test_public_cli_uses_active_resource(tmp_path, monkeypatch, capsys):
    import argparse

    from GSE.cli.main import cmd_encode

    target = database(tmp_path / "active.db", [("alpha:thing", "alpha", "SOMETHING")])
    pointer = tmp_path / "active.json"
    activate(pointer, target)
    monkeypatch.setattr(lexicon_resource, "ACTIVE_POINTER", pointer)
    cmd_encode(argparse.Namespace(text="Alpha.", format="json", output=None))
    trace = json.loads(capsys.readouterr().out)
    assert trace["tokens"][0]["word_primitives"] == {"SOMETHING": 1}


def test_spelling_uses_only_unique_definition_nonzero_assignments(tmp_path):
    path = database(
        tmp_path / "spelling.db",
        [("bank:thing", "bank", "SOMETHING"), ("bank:person", "bank", "SOMEONE")],
    )
    conn = open_build(path)
    for identity, lemma, values in (
        ("absent:state", "absent", (("GOOD", 0),)),
        ("mixed:state", "mixed", (("GOOD", 0), ("SOMETHING", 1))),
        ("bad:state", "bad", (("GOOD", -1),)),
        ("conflict:state", "conflict", (("GOOD", 1), ("GOOD", -1))),
    ):
        assertions = tuple(Assertion(bank, value, "fixture", identity, "dictionary") for bank, value in values)
        store_entry(
            conn,
            Definition(identity, lemma, "noun", identity),
            propagate(("GOOD", "SOMETHING", "FEEL"), assertions, ()),
            assertions,
        )
    conn.commit()
    conn.close()
    lexicon = spellcheck._Lexicon(path)
    assert lexicon.grounds("bank")  # Membership does not require a selected sense.
    assert lexicon.primitives("bank") == frozenset()
    assert lexicon.primitives("absent") == frozenset()
    assert lexicon.primitives("missing") == frozenset()
    assert lexicon.primitives("conflict") == frozenset()
    assert lexicon.primitives("mixed") == {"SOMETHING"}
    assert lexicon.primitives("bad") == {"GOOD"}
    lexicon.conn.close()


def test_spelling_legacy_explicit_zeros_are_not_active_banks(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            "CREATE TABLE lexemes(id INTEGER, lemma TEXT);"
            "CREATE TABLE primitive_values(lexeme_id INTEGER, primitive TEXT, value INTEGER);"
            "INSERT INTO lexemes VALUES(1,'thing');"
            "INSERT INTO primitive_values VALUES(1,'GOOD',0),(1,'SOMETHING',1);"
        )
    lexicon = spellcheck._Lexicon(path)
    assert lexicon.primitives("thing") == {"SOMETHING"}
    lexicon.conn.close()


@pytest.mark.parametrize("journal_mode", ["DELETE", "WAL"])
def test_spelling_refreshes_committed_values_without_pointer_change(tmp_path, journal_mode):
    path = database(tmp_path / "live.db", [("alpha:thing", "alpha", "SOMETHING")])
    lexicon = spellcheck._Lexicon(path)
    assert lexicon.primitives("alpha") == {"SOMETHING"}
    assert "beta" not in lexicon.lex_vocab
    assert lexicon.freq == {"alpha": 1}
    with sqlite3.connect(path) as writer:
        writer.execute(f"PRAGMA journal_mode={journal_mode}")
        assertion = Assertion("SOMEONE", 1, "fixture", "beta:person", "dictionary")
        store_entry(
            writer,
            Definition("beta:person", "beta", "noun", "fixture person"),
            propagate(("SOMETHING", "SOMEONE"), (assertion,), ()),
            (assertion,),
        )
        writer.execute("UPDATE lexemes SET frequency_rank=2 WHERE lemma='beta'")
        writer.commit()
        assert lexicon.primitives("beta") == {"SOMEONE"}
        assert "beta" in lexicon.lex_vocab
        assert lexicon.freq == {"alpha": 1, "beta": 2}
    lexicon.conn.close()


def test_document_encoder_refreshes_both_default_cache_layers(tmp_path, monkeypatch):
    from GSE.encoders import text_structure_encoder as text_module

    first = database(tmp_path / "first.db", [("alpha:thing", "alpha", "SOMETHING")])
    second = database(tmp_path / "second.db", [("beta:thing", "beta", "SOMETHING")])
    pointer = tmp_path / "active.json"
    monkeypatch.setattr(lexicon_resource, "ACTIVE_POINTER", pointer)
    monkeypatch.setattr(text_module, "_default_gse_encoder", None)
    monkeypatch.setattr(text_module, "_text_encoders", {})
    activate(pointer, first)
    document_first = text_module.get_text_encoder()
    old_sentence = document_first.genre_detector.encoder
    assert old_sentence.db_path == first
    assert text_module.get_text_encoder() is document_first
    with GSEEncoder(first) as explicit:
        injected = text_module.get_text_encoder(explicit)
        activate(pointer, second)
        document_second = text_module.get_text_encoder()
        assert document_second is not document_first
        assert document_second.genre_detector.encoder.db_path == second
        assert text_module.get_text_encoder(explicit) is injected
        assert injected.genre_detector.encoder is explicit
        assert explicit.conn.execute("SELECT count(*) FROM lexemes").fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError):
        old_sentence.conn.execute("SELECT 1")
    document_second.genre_detector.encoder.close()


@pytest.mark.parametrize("explicit", [False, True])
def test_sense_vector_entrypoint_resolves_selected_source(tmp_path, monkeypatch, explicit):
    from scripts import build_sense_vectors

    target = database(tmp_path / "selected.db", [("alpha:thing", "alpha", "SOMETHING")])
    archive = database(tmp_path / "archive.db", [("beta:thing", "beta", "SOMETHING")])
    pointer = tmp_path / "active.json"
    activate(pointer, target)
    monkeypatch.setattr(lexicon_resource, "ACTIVE_POINTER", pointer)
    argv = ["build_sense_vectors", "--corpus", str(tmp_path / "missing-*.txt")]
    if explicit:
        argv.extend(["--lexicon", str(archive)])
    monkeypatch.setattr("sys.argv", argv)

    class SourceReached(Exception):
        pass

    def consume_source(*, lexicon_path):
        assert lexicon_path == str(archive if explicit else target)
        raise SourceReached

    monkeypatch.setattr(build_sense_vectors, "GSEPipeline", consume_source)
    with pytest.raises(SourceReached):
        build_sense_vectors.main()
