"""Partial native evidence excludes values without inventing assignments."""

import json
import sqlite3
from dataclasses import asdict

import pytest

from GSE.curation.lexicon_builder.engine import Assertion, DomainRestriction, Relation, propagate
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.pipeline import build_dictionary, load_evidence
from GSE.curation.lexicon_builder.residual import build_request, complete_bank
from GSE.curation.lexicon_builder.resolution import resolve_dictionary
from GSE.curation.lexicon_builder.validation import validate_build


def restriction(bank="GOOD", values=(-1, 1), source="native", record="r", family="lexical"):
    return DomainRestriction(bank, values, source, record, family)


@pytest.mark.parametrize("values", [(), (-1, 0, 1), (True,), (1.0,), (2,), (0, 0), [-1, 1]])
def test_invalid_restriction_domains_are_refused(values):
    with pytest.raises(ValueError):
        restriction(values=values)


def test_restrictions_intersect_and_propagate_inverse_relations():
    rule = Relation("equal", ("A", "B"), ((-1, -1), (0, 0), (1, 1)), ("law",), "foundational", True)
    restrictions = (restriction("A"), restriction("B", (0, 1)))
    result = propagate(("A", "B"), (), (rule,), domain_restrictions=restrictions)
    assert result.assignments == {"A": 1, "B": 1}
    assert result == propagate(("A", "B"), (), (rule,), domain_restrictions=tuple(reversed(restrictions)))
    assert any(row["kind"] == "DOMAIN_RESTRICTION" for row in result.trace)


def test_nonzero_evidence_keeps_sign_unresolved_and_zero_evidence_is_explicit():
    result = resolve_dictionary(("A", "B"), (), (), domain_restrictions=(restriction("A"), restriction("B", (0,))))
    assert result.domains["A"] == frozenset((-1, 1))
    assert result.assignments == {"B": 0}


def test_restrictions_cannot_be_voted_away_or_excepted():
    claims = (restriction("A", (-1,)), restriction("A", (1,)))
    result = resolve_dictionary(("A",), (), (), domain_restrictions=claims)
    assert result.code == "CONFLICT"
    assert result.conflicts[0]["code"] == "DOMAIN_RESTRICTION_CONFLICT"
    rule = Relation("conditional-zero", ("A",), ((0,),), ("law",), approved=True)
    result = resolve_dictionary(("A",), (), (rule,), domain_restrictions=(restriction("A"),))
    assert result.domains["A"] == frozenset((-1, 1))
    assert any(row["kind"] == "CONDITIONAL_EXCEPTION" for row in result.trace)


def test_explicit_assertion_conflicting_with_restriction_stays_conflict():
    claim = Assertion("A", 0, "other", "other-record", "lexical")
    result = propagate(("A",), (claim,), (), domain_restrictions=(restriction("A"),))
    assert result.code == "CONFLICT"
    assert result.domains["A"] == frozenset()
    assert result.conflicts[0]["assertions"][0]["value"] == 0


def test_restriction_blocks_absence_default_before_application():
    rule = Relation("default", ("A",), ((0,),), ("law",), approved=True, absent_evidence=("A",))
    result = resolve_dictionary(("A",), (), (rule,), domain_restrictions=(restriction("A"),))
    assert result.domains["A"] == frozenset((-1, 1))
    assert result.trace[-1]["reason"] == "RELEVANT_EVIDENCE"
    assert not any(row["kind"] == "CONDITIONAL_EXCEPTION" for row in result.trace)


def test_model_request_domain_and_poststate_keep_restrictions():
    definition = Definition("d", "d", "verb", "fixture")
    restrictions = (restriction("A"),)
    result = resolve_dictionary(("A",), (), (), domain_restrictions=restrictions)
    request = build_request("d", "A", result, (), definition=definition)
    assert request.allowed_values == (-1, 1)
    invalid = complete_bank(request, ("A",), (), (), lambda *_: '{"A":0}', domain_restrictions=restrictions)
    assert invalid.code == "INVALID_OUTPUT"
    assigned = complete_bank(request, ("A",), (), (), lambda *_: '{"A":1}', domain_restrictions=restrictions)
    assert assigned.code == "ASSIGNED"
    assert assigned.resolution.assignments == {"A": 1}
    stale = complete_bank(request, ("A",), (), (), lambda *_: pytest.fail("stale request reached transport"))
    assert stale.code == "STALE_REQUEST"


def bundle():
    return EvidenceBundle(
        (Definition("d", "d", "verb", "fixture"),),
        (Observation("d", "native", "r", "lexical", {}, "lexical"),),
        (),
        (),
        (restriction(),),
    )


def test_typed_interchange_and_stored_partial_domain_replay(tmp_path):
    raw = {"format": "GSE.lexicon-evidence/1", **asdict(bundle())}
    source = tmp_path / "evidence.json"
    source.write_text(json.dumps(raw))
    loaded = load_evidence(source)
    assert loaded == bundle()
    path = tmp_path / "partial.db"
    report = build_dictionary(loaded, path)
    assert report["domain_restrictions"] == 1
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    with sqlite3.connect(path) as conn:
        domains = json.loads(conn.execute("SELECT domains FROM definition_states").fetchone()[0])
        assert domains["GOOD"] == [-1, 1]
        assert not conn.execute("SELECT value FROM primitive_values WHERE primitive='GOOD'").fetchall()


def test_build_model_request_and_replay_use_native_restrictions(tmp_path):
    # All other banks have native singleton restrictions, leaving exactly one model decision.
    initial = bundle()
    restrictions = tuple(restriction(bank, (-1, 1) if bank == "GOOD" else (0,)) for bank in BANKS)
    evidence = EvidenceBundle(initial.definitions, initial.observations, (), (), restrictions)
    path = tmp_path / "modeled.db"

    def transport(payload, schema):
        assert payload["bank"] == "GOOD"
        assert payload["allowed_values"] == [-1, 1]
        assert schema["properties"]["GOOD"]["enum"] == [-1, 1, None]
        return '{"GOOD":1}'

    report = build_dictionary(evidence, path, transport=transport, max_model_calls=1)
    assert report["model_outcomes"] == {"ASSIGNED": 1}
    assert report["outcomes"] == {"RESOLVED": 1}
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("change", ["value", "source", "family", "missing", "orphan", "ordinal"])
def test_restriction_storage_tampering_is_detected(tmp_path, change):
    path = tmp_path / "tampered.db"
    build_dictionary(bundle(), path)
    with sqlite3.connect(path) as conn:
        raw = json.loads(conn.execute("SELECT payload FROM builder_domain_restrictions").fetchone()[0])
        if change == "missing":
            conn.execute("DELETE FROM builder_domain_restrictions")
        elif change == "orphan":
            conn.execute("UPDATE builder_domain_restrictions SET entry_id='missing'")
        elif change == "ordinal":
            conn.execute("UPDATE builder_domain_restrictions SET ordinal=1")
        else:
            raw[{"value": "allowed_values", "source": "source", "family": "family"}[change]] = (
                [0, True] if change == "value" else "forged"
            )
            conn.execute("UPDATE builder_domain_restrictions SET payload=?", (json.dumps(raw),))
    assert validate_build(path)["code"] == "REPLAY_MISMATCH"


def test_restrictions_require_exact_link_and_competent_source(tmp_path):
    definition = Definition("d", "d", "verb", "fixture")
    ambiguous = Observation(None, "native", "r", "lexical", {}, "lexical", ("d",))
    with pytest.raises(ValueError, match="EXACT_DEFINITION_LINK"):
        build_dictionary(EvidenceBundle((definition,), (ambiguous,), (), (), (restriction(),)), tmp_path / "a.db")
    sentiment = Observation("d", "sentiwordnet", "r", "lexical", {}, "lexical")
    with pytest.raises(ValueError, match="OUTSIDE_SOURCE_SCOPE"):
        build_dictionary(
            EvidenceBundle((definition,), (sentiment,), (), (), (restriction("DO", source="sentiwordnet"),)),
            tmp_path / "b.db",
        )


def test_legacy_snapshot_without_restriction_extension_still_replays(tmp_path):
    initial = bundle()
    path = tmp_path / "legacy.db"
    build_dictionary(EvidenceBundle(initial.definitions, initial.observations, (), ()), path)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE builder_domain_restrictions")
        conn.execute("DELETE FROM builder_metadata WHERE key='domain_restrictions_format'")
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
