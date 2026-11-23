"""Unit tests for lexical SQLite connection reuse and thread-local caching (Task 3.1).

Verifies the cache contract defined in design D2:
1. Repeated lookups against the same database path reuse one connection.
2. Rewriting the lexicon file atomically invalidates the cache, yielding a new connection
   and a new provenance hash.
3. Lookups from multiple concurrent threads succeed independently without cross-thread
   connection sharing.
4. Missing database files return state="unread" gracefully without crashing.
5. close_lexical_connections() closes open connections and empties the cache.
6. A controlled replacement occurring mid-lookup (between initial stat and query completion)
   is detected, triggering a clean retry that prevents pairing one file's hash with another file's rows.

Policy Scope & Boundary:
These tests demonstrate invalidation when writers adhere to atomic replacement
(write-to-temp + fsync + os.replace). They do not establish that arbitrary external
writers adhere to this policy; non-atomic or in-place byte edits that leave inode/mtime
intact are unsupported.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gse.lexical_evidence import (  # noqa: E402
    _tls,
    close_lexical_connections,
    lookup_lexeme,
)


def create_sample_lexicon(path: Path, lemma: str = "happy", prime: str = "GOOD", value: int = 1) -> None:
    """Create a minimal SQLite lexicon database."""
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE lexemes (id INTEGER PRIMARY KEY, lemma TEXT, pos TEXT);")
        conn.execute(
            "CREATE TABLE primitive_values (id INTEGER PRIMARY KEY, lexeme_id INTEGER, primitive TEXT, value INTEGER);"
        )
        conn.execute("INSERT INTO lexemes (id, lemma, pos) VALUES (1, ?, 'a');", (lemma,))
        conn.execute("INSERT INTO primitive_values (lexeme_id, primitive, value) VALUES (1, ?, ?);", (prime, value))


def test_repeated_lookups_reuse_connection(tmp_path):
    close_lexical_connections()
    db = tmp_path / "test_reuse.db"
    create_sample_lexicon(db)

    res1 = lookup_lexeme("happy", db)
    assert res1["state"] == "primes"
    assert res1["primitives"] == {"GOOD": 1}

    cache = getattr(_tls, "connections", {})
    resolved_path = str(db.resolve())
    assert resolved_path in cache
    conn1 = cache[resolved_path][1]

    res2 = lookup_lexeme("happy", db)
    assert res2["state"] == "primes"
    conn2 = cache[resolved_path][1]

    # Exactly the same connection object
    assert conn1 is conn2


def test_rewriting_lexicon_yields_new_connection_and_hash(tmp_path):
    close_lexical_connections()
    db = tmp_path / "test_rewrite.db"
    create_sample_lexicon(db, lemma="happy", prime="GOOD", value=1)

    res1 = lookup_lexeme("happy", db)
    assert res1["state"] == "primes"
    assert res1["primitives"] == {"GOOD": 1}
    sha1 = res1["provenance"]["sha256"]
    conn1 = _tls.connections[str(db.resolve())][1]

    # Atomically replace db with new content
    temp_db = tmp_path / "temp_rewrite.db"
    create_sample_lexicon(temp_db, lemma="happy", prime="FEEL", value=1)
    os.replace(temp_db, db)

    res2 = lookup_lexeme("happy", db)
    assert res2["state"] == "primes"
    assert res2["primitives"] == {"FEEL": 1}
    sha2 = res2["provenance"]["sha256"]
    conn2 = _tls.connections[str(db.resolve())][1]

    # New connection, old closed, new provenance hash
    assert conn2 is not conn1
    assert sha2 != sha1

    # Verify old connection was closed
    with pytest.raises(sqlite3.ProgrammingError):
        conn1.execute("SELECT 1")


def test_concurrent_threads_both_succeed(tmp_path):
    close_lexical_connections()
    db = tmp_path / "test_threads.db"
    create_sample_lexicon(db)

    results = {}
    thread_connections = {}
    errors = []

    def worker(thread_id: int):
        try:
            res = lookup_lexeme("happy", db)
            results[thread_id] = res
            cache = getattr(_tls, "connections", {})
            thread_connections[thread_id] = cache[str(db.resolve())][1]
            close_lexical_connections()
        except Exception as e:
            errors.append((thread_id, e))

    t1 = threading.Thread(target=worker, args=(1,))
    t2 = threading.Thread(target=worker, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors, f"Thread errors: {errors}"
    assert results[1]["state"] == "primes"
    assert results[2]["state"] == "primes"
    # Thread-local connections must be distinct objects
    assert thread_connections[1] is not thread_connections[2]


def test_missing_file_returns_unread(tmp_path):
    close_lexical_connections()
    missing_path = tmp_path / "nonexistent_lexicon.db"
    res = lookup_lexeme("happy", missing_path)
    assert res["state"] == "unread"
    assert res["selected_record"] is None
    assert res["primitives"] == {}
    assert "reason" in res


def test_close_lexical_connections(tmp_path):
    close_lexical_connections()
    db = tmp_path / "test_close.db"
    create_sample_lexicon(db)

    lookup_lexeme("happy", db)
    cache = getattr(_tls, "connections", {})
    resolved_path = str(db.resolve())
    assert resolved_path in cache
    conn = cache[resolved_path][1]

    close_lexical_connections()
    assert len(cache) == 0
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_atomic_replacement_between_steps_prevents_provenance_race(tmp_path, monkeypatch):
    """Verify that atomic replacement occurring between stat and query completion does not
    pair one file's provenance hash with another file's rows.

    The cache contract assumes writers follow atomic replacement (write-temp + fsync + os.replace).
    This test verifies that if replacement occurs mid-lookup, the lookup detects the stat change,
    retries once, and returns provenance and rows originating from the exact same file version.
    """
    close_lexical_connections()
    db = tmp_path / "test_race.db"
    create_sample_lexicon(db, lemma="happy", prime="GOOD", value=1)

    db_new = tmp_path / "temp_race_new.db"
    create_sample_lexicon(db_new, lemma="happy", prime="FEEL", value=1)

    replaced = [False]
    orig_stat = Path.stat

    def racing_stat(self, *args, **kwargs):
        res = orig_stat(self, *args, **kwargs)
        # Squeeze atomic replacement right after the initial stat reading of db
        if str(self) == str(db) and not replaced[0]:
            os.replace(db_new, db)
            replaced[0] = True
        return res

    monkeypatch.setattr(Path, "stat", racing_stat)

    res = lookup_lexeme("happy", db)
    assert res["state"] == "primes"
    # Must return rows and provenance from the newly swapped file consistently
    assert res["primitives"] == {"FEEL": 1}
    # Verify provenance matches the current db file bytes exactly
    from gse.lexical_evidence import resource_identity

    current_provenance = resource_identity(db)
    assert res["provenance"]["sha256"] == current_provenance["sha256"]
