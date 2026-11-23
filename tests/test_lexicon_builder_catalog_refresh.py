"""Explicit catalog link replacement is replayed once and writes metadata only."""

import json
import sqlite3
import subprocess
import sys

import pytest

from gse.curation.lexicon_builder import validation
from gse.curation.lexicon_builder.catalog import catalog_report
from gse.curation.lexicon_builder.engine import Assertion, DomainRestriction
from gse.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from gse.curation.lexicon_builder.foundation import projection_relations
from gse.curation.lexicon_builder.pipeline import build_dictionary


def _links(tmp_path, entries=None):
    path = tmp_path / "links.json"
    path.write_text(
        json.dumps(
            {
                "format": "gse.prime-definition-links/1",
                "prime_entries": {"nsm:v20:good": ["entry"]} if entries is None else entries,
            }
        )
    )
    return path


def _build(tmp_path):
    path = tmp_path / "lexicon.db"
    definition = Definition("entry", "good", "adj", "A fixture evaluative sense.")
    bundle = EvidenceBundle(
        (definition,),
        (Observation("entry", "fixture", "record", "native", {}, "lexical"),),
        (Assertion("GOOD", 1, "fixture", "record", "native"),),
        (),
        (DomainRestriction("THINK", (0, 1), "fixture", "record", "native"),),
    )
    build_dictionary(bundle, path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE builder_metadata SET value=? WHERE key='catalog'",
            (json.dumps(catalog_report({}, bundle.definitions, projection_relations(), legacy_duration=True)),),
        )
    assert validation.validate_build(path)["code"] == "REPLAY_VALIDATED"
    return path


def _metadata(path):
    with sqlite3.connect(path) as conn:
        return {key: json.loads(value) for key, value in conn.execute("SELECT key,value FROM builder_metadata")}


def _non_metadata(path):
    with sqlite3.connect(path) as conn:
        names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {
            name: conn.execute(f'SELECT * FROM "{name}"').fetchall() for name in names if name != "builder_metadata"
        }


def test_read_only_preview_uses_one_observation_pass_and_keeps_saved_catalog(tmp_path, monkeypatch):
    path = _build(tmp_path)
    before = path.read_bytes()
    original = validation._observations
    calls = []

    def tracked(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(validation, "_observations", tracked)
    result = validation.refresh_catalog(path, _links(tmp_path))
    assert result["code"] == "CATALOG_LINKS_PREVIEW"
    assert result["catalog"]["coverage_counts"] == {"PARTIAL_FOUNDATION_CLOSURE": 1, "UNLINKED": 64}
    assert result["replay"]["code"] == "REPLAY_VALIDATED"
    assert result["dictionary_states"] == "UNCHANGED"
    assert calls == [1]
    assert path.read_bytes() == before
    assert _metadata(path)["catalog"]["format"] == "gse.nsm-catalog-coverage/1"
    assert _metadata(path)["catalog"]["readiness"]["mapping_complete"] is False


def test_apply_changes_only_three_metadata_records_and_replays(tmp_path):
    path = _build(tmp_path)
    before = _metadata(path)
    dictionary = _non_metadata(path)
    result = validation.refresh_catalog(path, _links(tmp_path), apply_links=True)
    assert result["code"] == "CATALOG_LINKS_APPLIED"
    after = _metadata(path)
    assert {key for key in before if before[key] != after[key]} == {"catalog", "prime_entries", "last_report"}
    assert set(after) == set(before)
    assert _non_metadata(path) == dictionary
    assert after["prime_entries"] == {"nsm:v20:good": ["entry"]}
    assert after["catalog"]["format"] == "gse.nsm-catalog-coverage/2"
    assert after["catalog"]["readiness"]["mapping_complete"] is True
    assert after["last_report"]["model_calls"] == before["last_report"]["model_calls"]
    assert after["last_report"]["prime_coverage"] == after["catalog"]["coverage_counts"]
    assert validation.validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_explicit_empty_mapping_replaces_links_without_deleting_values(tmp_path):
    path = _build(tmp_path)
    validation.refresh_catalog(path, _links(tmp_path), apply_links=True)
    values = _non_metadata(path)
    result = validation.refresh_catalog(path, _links(tmp_path, {}), apply_links=True)
    assert result["catalog"]["coverage_counts"] == {"UNLINKED": 65}
    assert _metadata(path)["prime_entries"] == {}
    assert _non_metadata(path) == values


def test_apply_rolls_back_all_metadata_when_final_write_fails(tmp_path):
    path = _build(tmp_path)
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TRIGGER refuse_report BEFORE INSERT ON builder_metadata
                        WHEN NEW.key='last_report' BEGIN SELECT RAISE(ABORT,'fixture interruption'); END""")
    before = _metadata(path)
    with pytest.raises(ValueError, match="INVALID_BUILD_DATABASE"):
        validation.refresh_catalog(path, _links(tmp_path), apply_links=True)
    assert _metadata(path) == before
    assert validation.validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_concurrent_completion_metadata_is_not_overwritten(tmp_path, monkeypatch):
    path = _build(tmp_path)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
    original = validation._replay
    before = _metadata(path)

    def concurrent(conn, relations, **kwargs):
        result = original(conn, relations, **kwargs)
        with sqlite3.connect(path) as writer:
            report = json.loads(
                writer.execute("SELECT value FROM builder_metadata WHERE key='last_report'").fetchone()[0]
            )
            report["model_calls"] = 99
            writer.execute("UPDATE builder_metadata SET value=? WHERE key='last_report'", (json.dumps(report),))
        return result

    monkeypatch.setattr(validation, "_replay", concurrent)
    with pytest.raises(ValueError, match="CATALOG_CONCURRENT_MODIFICATION"):
        validation.refresh_catalog(path, _links(tmp_path), apply_links=True)
    after = _metadata(path)
    assert after["catalog"] == before["catalog"]
    assert after["prime_entries"] == before["prime_entries"]
    assert after["last_report"]["model_calls"] == 99


def test_existing_writer_is_refused_without_retry_or_catalog_changes(tmp_path, monkeypatch):
    path = _build(tmp_path)
    before = _metadata(path)
    original = validation._replay
    writers = []

    def concurrent(conn, relations, **kwargs):
        result = original(conn, relations, **kwargs)
        writer = sqlite3.connect(path)
        writer.execute("BEGIN IMMEDIATE")
        writers.append(writer)
        return result

    monkeypatch.setattr(validation, "_replay", concurrent)
    try:
        with pytest.raises(ValueError, match="CATALOG_WRITER_BUSY"):
            validation.refresh_catalog(path, _links(tmp_path), apply_links=True)
    finally:
        for writer in writers:
            writer.close()
    assert _metadata(path) == before


def test_corrupt_dictionary_cannot_be_relabelled_by_catalog_upgrade(tmp_path):
    path = _build(tmp_path)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE primitive_values SET value=-1 WHERE primitive='GOOD'")
    before = _metadata(path)
    with pytest.raises(ValueError, match="CATALOG_REQUIRES_VALID_REPLAY"):
        validation.refresh_catalog(path, _links(tmp_path), apply_links=True)
    assert _metadata(path) == before


@pytest.mark.parametrize(
    "entries,error",
    [
        ({"nsm:v20:good": ["missing"]}, "UNKNOWN_CATALOG_DEFINITION"),
        ({"unknown": ["entry"]}, "UNKNOWN_CATALOG_UNIT"),
        ({"nsm:v20:good": ["entry", "entry"]}, "AMBIGUOUS_CATALOG_DEFINITION"),
        ({"nsm:v20:good": ["entry"], "nsm:v20:bad": ["entry"]}, "AMBIGUOUS_CATALOG_DEFINITION"),
    ],
)
def test_invalid_identity_replacements_leave_metadata_unchanged(tmp_path, entries, error):
    path = _build(tmp_path)
    before = _metadata(path)
    with pytest.raises(ValueError, match=error):
        validation.refresh_catalog(path, _links(tmp_path, entries), apply_links=True)
    assert _metadata(path) == before


@pytest.mark.parametrize(
    "raw",
    [
        {"format": "gse.lexicon-rules/1", "prime_entries": {}},
        {"format": "gse.prime-definition-links/1", "prime_entries": {}, "anchors": {}},
        {"format": "gse.prime-definition-links/1", "prime_entries": {}, "relations": []},
        {"format": "gse.prime-definition-links/1", "prime_entries": {"nsm:v20:good": "entry"}},
        {"format": "gse.prime-definition-links/1", "prime_entries": {"nsm:v20:good": [None]}},
        {"format": "gse.prime-definition-links/1"},
    ],
)
def test_link_only_format_rejects_semantic_manifest_and_malformed_records(tmp_path, raw):
    links = tmp_path / "invalid.json"
    links.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="INVALID_PRIME_DEFINITION_LINKS"):
        validation.refresh_catalog(tmp_path / "not-created.db", links, apply_links=True)
    assert not (tmp_path / "not-created.db").exists()


def test_real_cli_previews_applies_and_still_reads_saved_catalog(tmp_path):
    path = _build(tmp_path)
    links = _links(tmp_path)
    report = tmp_path / "preview.json"
    command = [sys.executable, "-m", "gse.curation.cli.commands", "--lexicon-db", str(path), "catalog"]
    preview = subprocess.run(
        command + ["--links", str(links), "--report", str(report)], capture_output=True, text=True, check=True
    )
    assert json.loads(preview.stdout) == json.loads(report.read_text())
    assert json.loads(preview.stdout)["code"] == "CATALOG_LINKS_PREVIEW"
    applied = subprocess.run(
        command + ["--links", str(links), "--apply-links"], capture_output=True, text=True, check=True
    )
    assert json.loads(applied.stdout)["code"] == "CATALOG_LINKS_APPLIED"
    saved = subprocess.run(command, capture_output=True, text=True, check=True)
    assert json.loads(saved.stdout) == _metadata(path)["catalog"]


@pytest.mark.parametrize(
    "arguments,error",
    [
        (["--apply-links"], "CATALOG_APPLY_REQUIRES_LINKS"),
        (["--inventory", "--links", "unused.json"], "CATALOG_INVENTORY_CANNOT_USE_LINKS"),
    ],
)
def test_cli_rejects_incompatible_catalog_flags(tmp_path, arguments, error):
    path = _build(tmp_path)
    before = _metadata(path)
    result = subprocess.run(
        [sys.executable, "-m", "gse.curation.cli.commands", "--lexicon-db", str(path), "catalog", *arguments],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert error in result.stderr
    assert _metadata(path) == before
