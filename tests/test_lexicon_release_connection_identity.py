"""An unstable published resource must abstain instead of asserting stale identity."""

import sqlite3

from gse import lexical_evidence


def database(path, value):
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE lexemes(id INTEGER PRIMARY KEY,lemma TEXT,pos TEXT,source TEXT);
            CREATE TABLE primitive_values(lexeme_id INTEGER,primitive TEXT,value INTEGER);
        """)
        conn.execute("INSERT INTO lexemes VALUES(1,'word','x','test')")
        conn.execute("INSERT INTO primitive_values VALUES(1,'GOOD',?)", (value,))


def test_repeated_replacement_during_lookup_refuses_the_unstable_source(tmp_path, monkeypatch):
    path = tmp_path / "lexicon.db"
    database(path, 1)
    original = lexical_evidence._valid_primitive_value
    replacements = []

    def replace_during_read(primitive, value, source):
        replacement = tmp_path / f"replacement-{len(replacements)}.db"
        database(replacement, -value)
        replacement.replace(path)
        replacements.append(replacement)
        return original(primitive, value, source)

    monkeypatch.setattr(lexical_evidence, "_valid_primitive_value", replace_during_read)
    result = lexical_evidence.lookup_lexeme("word", path)
    assert len(replacements) == 2
    assert result["state"] == "unread"
    assert result["reason"] == "LEXICON_CHANGED_DURING_READ"
    assert result["primitives"] == {}
    assert result["selected_record"] is None
    lexical_evidence.close_lexical_connections()
