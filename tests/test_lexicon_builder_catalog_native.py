"""Native catalog coverage preserves authority, unknowns and replay semantics."""

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

import pytest

from GSE.curation.lexicon_builder.catalog import catalog_report
from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.engine import Assertion, DomainRestriction
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.foundation import BANKS, load_manifest, load_manifest_extensions, projection_relations
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.validation import validate_build


def _metadata(path, key="catalog"):
    with sqlite3.connect(path) as conn:
        return json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key=?", (key,)).fetchone()[0])


def _save_metadata(path, value, key="catalog"):
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE builder_metadata SET value=? WHERE key=?", (json.dumps(value), key))


def _linked(report):
    return next(unit for unit in report["units"] if unit["unit_id"] == "nsm:v20:good")["definitions"][0]


def _build(tmp_path, *, conflict=False, relevance=None, restriction=False, transport=None):
    definition = Definition("entry", "good", "adj", "An explicitly identified fixture evaluation sense.")
    features = (
        {}
        if relevance is None
        else {"bank_relevance": {"code": "CLASSIFIED", "banks": relevance, "provenance": ["fixture:relevance"]}}
    )
    observations = [Observation("entry", "fixture-native", "native:1", "fixture", features, "lexical")]
    assertions = [Assertion("GOOD", 1, "fixture-native", "native:1", "fixture")]
    if conflict:
        observations.append(Observation("entry", "fixture-native", "native:2", "fixture", features, "lexical"))
        assertions.append(Assertion("GOOD", -1, "fixture-native", "native:2", "fixture"))
    restrictions = (DomainRestriction("THINK", (0, 1), "fixture-native", "native:1", "fixture"),) if restriction else ()
    bundle = EvidenceBundle((definition,), tuple(observations), tuple(assertions), (), restrictions)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"format": "GSE.lexicon-rules/1", "prime_entries": {"nsm:v20:good": ["entry"]}}))
    db = tmp_path / "lexicon.db"
    build_dictionary(bundle, db, manifest=manifest, transport=transport, max_model_calls=int(transport is not None))
    return db, bundle


def test_native_report_records_restrictions_authority_and_unknowns(tmp_path):
    db, bundle = _build(tmp_path, restriction=True)
    report = _metadata(db)
    linked = _linked(report)
    assert report["format"] == "GSE.nsm-catalog-coverage/2"
    assert report["evidence_scope"] == "SOURCE_AND_AUTHORED_ANCHOR_FOUNDATION"
    assert report["model_completions"] == "EXCLUDED_FROM_FOUNDATION_REPLAY"
    assert linked["code"] == "PARTIAL_FOUNDATION_CLOSURE"
    assert linked["anchors"] == []
    assert linked["native_assertions"] == [asdict(bundle.assertions[0])]
    assert linked["native_domain_restrictions"][0]["allowed_values"] == [0, 1]
    assert linked["domains"]["THINK"] == [0, 1]
    assert linked["domains"]["BIG"] == [-1, 0, 1]
    assert linked["assignments"] == {"GOOD": 1, "SOMETHING": 0}
    assert linked["authority"]["identity"] == "EXPLICIT_MANIFEST_LINK"
    assert linked["authority"]["model_completions"] == "EXCLUDED"
    assert report["readiness"]["all_foundation_domains_resolved"] is False
    assert report["readiness"]["founder_signature_completeness"] == "NOT_ESTABLISHED"
    assert validate_build(db)["code"] == "REPLAY_VALIDATED"


def test_conflicting_native_claims_publish_no_catalog_assignments(tmp_path):
    db, _ = _build(tmp_path, conflict=True)
    linked = _linked(_metadata(db))
    assert linked["code"] == "CONFLICT"
    assert linked["assignments"] == {}
    assert linked["domains"]["GOOD"] == []
    assert len(linked["native_assertions"]) == 2
    assert linked["conflicts"]
    assert validate_build(db)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("relevance,expected", [(None, None), (["GOOD", "BIG"], None), (["GOOD"], 0)])
def test_catalog_relevance_matches_build_default_guard(tmp_path, relevance, expected):
    db, _ = _build(tmp_path, relevance=relevance)
    linked = _linked(_metadata(db))
    assert linked["assignments"].get("BIG") == expected
    assert linked["evidence_banks"] == sorted(BANKS if relevance is None else relevance)
    assert linked["evidence_guards"]
    assert validate_build(db)["code"] == "REPLAY_VALIDATED"


def test_candidate_relevance_blocks_catalog_default_without_becoming_native_authority(tmp_path):
    db, bundle = _build(tmp_path, relevance=["GOOD"])
    candidate = Observation(None, "candidate-source", "candidate:1", "candidate", {}, "association", ("entry",))
    build_dictionary(
        EvidenceBundle(bundle.definitions, bundle.observations + (candidate,), bundle.assertions, ()),
        db,
        manifest=tmp_path / "manifest.json",
    )
    linked = _linked(_metadata(db))
    assert "BIG" not in linked["assignments"]
    assert len(linked["native_assertions"]) == 1
    assert validate_build(db)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("mutation", ["value", "authority", "version", "model_scope", "relevance"])
def test_tampered_native_catalog_is_rejected(tmp_path, mutation):
    db, _ = _build(tmp_path)
    report = _metadata(db)
    linked = _linked(report)
    if mutation == "value":
        linked["native_assertions"][0]["value"] = -1
    elif mutation == "authority":
        linked["authority"]["native_evidence"] = "FOUNDER_APPROVED"
    elif mutation == "version":
        report["format"] = "GSE.nsm-catalog-coverage/99"
    elif mutation == "model_scope":
        report.pop("model_completions")
    else:
        linked["evidence_banks"] = []
    _save_metadata(db, report)
    replay = validate_build(db)
    assert replay["code"] == "REPLAY_MISMATCH"
    assert replay["mismatch_counts"]["CATALOG_METADATA_MISMATCH"] == 1


def test_legacy_anchor_only_catalog_replay_remains_supported(tmp_path):
    db, bundle = _build(tmp_path, restriction=True)
    legacy = catalog_report({}, bundle.definitions, projection_relations(), prime_entries={"nsm:v20:good": ("entry",)})
    assert legacy["format"] == "GSE.nsm-catalog-coverage/1"
    assert _linked(legacy)["code"] == "NO_DECLARED_ANCHORS"
    assert "native_assertions" not in _linked(legacy)
    _save_metadata(db, legacy)
    assert validate_build(db)["code"] == "REPLAY_VALIDATED"


class _Transport:
    model = "catalog-fixture"

    def __call__(self, payload, schema):
        return json.dumps({payload["bank"]: 1})


@pytest.mark.parametrize("during_build", [False, True])
def test_accepted_model_ruling_does_not_change_foundation_catalog(tmp_path, during_build):
    db, _ = _build(tmp_path, restriction=True, transport=_Transport() if during_build else None)
    before = _metadata(db)
    if not during_build:
        result = complete_dictionary(db, _Transport(), max_model_calls=1, entry_ids=("entry",), banks=("THINK",))
        assert result["model_calls"] == 1
    assert _metadata(db) == before
    linked = _linked(before)
    assert linked["domains"]["THINK"] == [0, 1]
    assert "THINK" not in linked["assignments"]
    assert len(linked["native_assertions"]) == 1
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT value FROM primitive_values WHERE primitive='THINK'").fetchone() == (1,)
    assert validate_build(db)["code"] == "REPLAY_VALIDATED"


def test_source_and_authored_anchor_authorities_remain_distinct():
    definition = Definition("entry", "good", "adj", "An identified fixture meaning.")
    anchor = Assertion("KNOW", 1, "authored", "anchor:1", "founder_anchor")
    native = Assertion("GOOD", 1, "fixture-native", "native:1", "fixture")
    report = catalog_report(
        {"entry": (anchor,)},
        (definition,),
        projection_relations(),
        prime_entries={"nsm:v20:good": ("entry",)},
        native_assertions={"entry": (native,)},
    )
    linked = _linked(report)
    assert linked["anchors"] == [asdict(anchor)]
    assert linked["native_assertions"] == [asdict(native)]
    assert linked["assignments"]["KNOW"] == linked["assignments"]["GOOD"] == 1


def test_native_report_without_evidence_does_not_claim_foundation_coverage():
    report = catalog_report(
        {},
        (Definition("entry", "good", "adj", "An identified fixture meaning."),),
        projection_relations(),
        prime_entries={"nsm:v20:good": ("entry",)},
        native_assertions={},
    )
    assert _linked(report)["code"] == "NO_FOUNDATION_EVIDENCE"
    assert report["coverage_counts"]["MISSING_FOUNDATION_EVIDENCE"] == 1


def test_native_explicit_zero_and_partial_restriction_are_evidence_not_completion():
    definition = Definition("entry", "good", "adj", "An identified fixture meaning.")
    report = catalog_report(
        {},
        (definition,),
        (),
        prime_entries={"nsm:v20:good": ("entry",)},
        native_assertions={"entry": (Assertion("BIG", 0, "fixture", "r", "native"),)},
        native_domain_restrictions={"entry": (DomainRestriction("GOOD", (0, 1), "fixture", "r", "native"),)},
    )
    linked = _linked(report)
    assert linked["code"] == "PARTIAL_FOUNDATION_CLOSURE"
    assert linked["assignments"] == {"BIG": 0}
    assert linked["domains"]["GOOD"] == [0, 1]
    assert linked["domains"]["THINK"] == [-1, 0, 1]
    restrictions_only = catalog_report(
        {},
        (definition,),
        (),
        prime_entries={"nsm:v20:good": ("entry",)},
        native_domain_restrictions={"entry": (DomainRestriction("GOOD", (0, 1), "fixture", "r", "native"),)},
    )
    assert _linked(restrictions_only)["code"] == "PARTIAL_FOUNDATION_CLOSURE"
    assert _linked(restrictions_only)["assignments"] == {}


def test_six_verified_manifest_links_do_not_mint_anchors():
    manifest = Path(__file__).resolve().parents[1] / "docs/program/LEXICON_APPROVED_ANCHORS_2026-10-29.json"
    _, anchors, _ = load_manifest(manifest)
    _, links = load_manifest_extensions(manifest)
    expected = {
        "someone": "pronoun:someone",
        "something": "pronoun:something",
        "not": "negation:not",
        "can": "modal:can",
        "maybe": "modal:maybe",
        "like": "preposition:like",
    }
    for unit, suffix in expected.items():
        entry_id = "gse_closed_class:" + suffix
        assert links["nsm:v20:" + unit] == (entry_id,)
        assert entry_id not in anchors


def test_unknown_manifest_link_is_not_silently_dropped(tmp_path):
    manifest = tmp_path / "unknown.json"
    manifest.write_text(json.dumps({"format": "GSE.lexicon-rules/1", "prime_entries": {"nsm:v20:good": ["missing"]}}))
    db = tmp_path / "invalid.db"
    with pytest.raises(ValueError, match="UNKNOWN_CATALOG_DEFINITION"):
        build_dictionary(EvidenceBundle((), (), (), ()), db, manifest=manifest)
    assert not db.exists()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"native_assertions": {"entry": (Assertion("GOOD", 1, "model:fixture", "r", "model"),)}},
        {"native_assertions": {"entry": (Assertion("DO", 1, "sentiwordnet", "r", "wordnet"),)}},
        {"native_assertions": {"entry": ({"bank": "GOOD"},)}},
        {"native_domain_restrictions": {"missing": ()}},
        {"evidence_banks": {"entry": ("BAD",)}},
        {"evidence_banks": {"entry": ("BIG", "BIG")}},
    ],
)
def test_invalid_native_catalog_inputs_are_rejected(kwargs):
    with pytest.raises(ValueError):
        catalog_report({}, (Definition("entry", "good", "adj", "fixture"),), (), **kwargs)
