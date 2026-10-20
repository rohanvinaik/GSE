"""Actual spelling-resource identities and honest process-cache receipts."""

from __future__ import annotations

import stat
from pathlib import Path

from gse.lexical_evidence import resource_identity

_BASELINE: dict | None = None
_UNVERIFIED: set[str] = set()


def _file(path: str | Path | None) -> dict:
    if path is None:
        return {"state": "missing", "path": None, "sha256": None, "reason": "no_selected_resource"}
    source = Path(path).resolve()
    try:
        mode = source.stat().st_mode
    except FileNotFoundError:
        return {"state": "missing", "path": str(source), "sha256": None, "reason": "resource_missing"}
    except OSError as exc:
        return {"state": "unread", "path": str(source), "sha256": None, "reason": type(exc).__name__}
    if stat.S_ISDIR(mode):
        return {"state": "unread", "path": str(source), "sha256": None, "reason": "unhashed_directory"}
    return resource_identity(source)


def _resources() -> tuple[dict, dict, dict]:
    import nltk
    from nltk.corpus import wordnet as wn

    from gse.nlp import hdc_speller, spellcheck, spellcheck_entity

    lexicon = spellcheck._DEFAULT_LEXICON
    entities = spellcheck_entity._DEFAULT_ENTITIES
    repo = Path(spellcheck._REPO_ROOT)
    local = Path(spellcheck.__file__).resolve().parent / "data"
    trie, text = repo / "data" / "wordlist_wiktionary.marisa", repo / "data" / "wordlist_wiktionary.txt"
    selected = trie if trie.is_file() else text if text.is_file() else None
    paths = {
        "lexicon": lexicon.db_path,
        "usage_frequency": repo / "data" / "frequency.db",
        "validity_wordlist": selected,
        "project_allowlist": local / "project_allowlist.txt",
        "misspellings": local / "misspellings_wikipedia.tsv",
        "entities": entities.db_path,
        "entity_anchors": spellcheck_entity._GENEALOGY_DB,
        "keyboard_hdc": hdc_speller._CACHE_PATH,
    }
    loaded = {
        "lexicon": any(value is not None for value in (lexicon._lex_vocab, lexicon._freq, lexicon._conn)),
        "usage_frequency": lexicon._usage is not None,
        "validity_wordlist": lexicon._validity_vocab is not None,
        "project_allowlist": lexicon._allowlist is not None,
        "misspellings": lexicon._confusions is not None,
        "entities": entities._conn is not None or entities._missing,
        "entity_anchors": spellcheck_entity._ANCHOR_CONN is not None,
        "keyboard_hdc": hdc_speller.default_speller.cache_info().currsize > 0,
        "wordnet": type(wn).__name__ != "LazyCorpusLoader",
    }
    files = {name: _file(path) for name, path in paths.items()}
    wordnet = {"nltk_version": nltk.__version__, "version": None}
    try:
        source = getattr(getattr(wn.root, "zipfile", None), "filename", None)
        files["wordnet"] = _file(source if source else str(wn.root))
        wordnet["version"] = wn.get_version()
    except (LookupError, OSError) as exc:
        files["wordnet"] = {"state": "unread", "path": None, "sha256": None, "reason": type(exc).__name__}
    return files, loaded, wordnet


def provenance() -> dict:
    """Snapshot before loading; report stale bytes or unattested prior caches.

    Call before any reading in a fresh process, then again for the final receipt.
    Existing cached tries/sets cannot be retroactively attributed to current files.
    Unloaded resources can adopt a new snapshot before their first consumption.
    """
    global _BASELINE
    files, loaded, wordnet = _resources()
    if _BASELINE is None:
        _BASELINE = dict(files)
        _UNVERIFIED.update(name for name, present in loaded.items() if present)
    records = {}
    for name, current in files.items():
        before = _BASELINE[name]
        changed = current != before
        if changed and not loaded[name] and name not in _UNVERIFIED:
            _BASELINE[name] = before = current
            changed = False
        state = "stale" if changed else "unverified_cache" if name in _UNVERIFIED else current["state"]
        records[name] = {
            "state": state,
            "cache": "loaded" if loaded[name] else "not_loaded",
            "snapshot": before,
            "current": current,
            "identity_scope": "current_source_only" if name in _UNVERIFIED else "process_snapshot_before_load",
        }
    states = {item["state"] for item in records.values()}
    return {
        "schema": "gse.healing-resources/1",
        "state": "stale" if "stale" in states else "unverified_cache" if "unverified_cache" in states else "read",
        "files": records,
        "wordnet": {**wordnet, "resource": records["wordnet"]},
        "cache_policy": {
            "spelling": "process_lifetime_lazy_sets_tries_sqlite_and_hdc; restart_after_resource_changes",
            "snapshot": "call_before_reading_then_after; loaded_before_first_receipt_is_unverified",
            "dictionary": "separate_dynamic_validated_store_with_stat_identity_invalidation",
            "missing_optional_resources": "named_missing; no_download_or_substitution",
        },
    }
