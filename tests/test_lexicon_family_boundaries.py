"""Ordinary closure must preserve omissions, scope and authored-boundary provenance."""

from copy import deepcopy
from pathlib import Path

import pytest

from gse.lexicon_builder.artifact import export_sparse, export_vector
from gse.lexicon_builder.build import adjective_seed, build, source_matches
from gse.lexicon_builder.core import legal_domain
from gse.lexicon_builder.families import family_contract_status
from gse.lexicon_builder.reading import construct_reading
from gse.lexicon_builder.registry import load_rulebook
from gse.lexicon_builder.sources import NativeSources
from tests.lexicon_sources import requires_lexicon_sources


class EmptyOptionalSelector:
    """A schema witness, not an oracle or a lexical-accuracy measurement."""

    def select(self, payload, options):
        assert payload.get("projection_scope", payload.get("scope")) is not None
        return {"request_sha256": "schema-witness", "answer": {c: "empty" for c in options}}


@pytest.fixture
def source_case():
    sources = NativeSources(["afraid", "sad", "fear"], Path("data/external"), Path.home() / "nltk_data/corpora")
    book = load_rulebook()
    return sources, book


@requires_lexicon_sources
def test_native_family_boundary_reaches_the_real_builder_and_export(source_case):
    sources, book = source_case
    record = next(build(["afraid"], sources, book, EmptyOptionalSelector()))["readings"][0]
    assert record["code"] == "PARTIAL"
    assert record["definition_accounting"]["code"] == "FAMILY_UNRESOLVED"
    assert record["candidate_vector"] is None
    assert record["model_calls"] == []
    assert {d["code"] for d in record["decisions"]} == {"WITHHELD_MODEL_TASK_TYPE"}
    with pytest.raises(ValueError, match="only a complete candidate"):
        export_vector(record)
    assert export_sparse(record)["cells"]["FEEL"]["state"] == "+1"
    assert export_sparse(record)["definition_accounting"] == record["definition_accounting"]
    assert record["production_eligible"] is False


@requires_lexicon_sources
def test_boundary_cannot_supply_a_deleted_content_warrant(source_case):
    sources, book = source_case
    book["laws"] = [r for r in book["laws"] if r["rule_id"] != "OWN_AFFECTIVE_FEELING"]
    record = next(build(["afraid"], sources, book, EmptyOptionalSelector()))["readings"][0]
    assert record["candidate_vector"] is None
    assert record["definition_accounting"]["code"] == "FAMILY_UNRESOLVED"
    assert {"FEEL", "WANT", "NOT"} <= set(record["definition_accounting"]["unresolved"])
    assert len(record["after_selection"]["domains"]["FEEL"]) > 1


@requires_lexicon_sources
def test_wrong_source_scope_and_withheld_contract_cannot_close_cells(source_case):
    sources, book = source_case
    for word in ("sad", "fear"):
        readings = next(build([word], sources, book, None))["readings"]
        assert all(r.get("definition_accounting", {}).get("family_id") != "GSE_FEAR_ADJ_BOUNDARY_V1" for r in readings)
    stale = deepcopy(book)
    rule = next(r for r in stale["source_rules"] if r["rule_id"] == "EMOTION_FEAR_ADJ")
    rule["definition_boundary"]["cells"]["FAR"]["reason"] += " changed"
    record = next(build(["afraid"], sources, stale, None))
    assert all(r.get("rule_id") != "EMOTION_FEAR_ADJ" for r in record["readings"])
    assert record["withheld_unadmitted_writes"]


@requires_lexicon_sources
def test_removing_one_silence_support_reopens_only_its_coordinate(source_case):
    sources, book = source_case
    native = sources.for_word("afraid")
    match = source_matches(native, book)[0]
    seed = adjective_seed("afraid", match, native)
    seed.laws = [law for law in seed.laws if law.rule_id != "FAMILY:GSE_FEAR_ADJ_BOUNDARY_V1:FAR"]
    result = construct_reading(seed, book, EmptyOptionalSelector())
    assert result["candidate_vector"] is None
    assert set(result["definition_accounting"]["unresolved"]) == {"FAR", "DO", "IF", "KNOW", "THEN", "MAYBE", "MUST"}
    assert result["after_selection"]["forced"]["SEE"] == "empty"


@requires_lexicon_sources
def test_optional_zero_survives_and_abstention_does_not_complete(source_case):
    sources, book = source_case
    native = sources.for_word("afraid")
    match = source_matches(native, book)[0]
    contract = match["rule"]["definition_boundary"]
    assert contract["cells"]["DO"]["domain"] == sorted(v.value for v in legal_domain("DO"))
    seed = adjective_seed("afraid", match, native)
    result = construct_reading(seed, book, None)
    assert result["candidate_vector"] is None
    assert set(result["definition_accounting"]["unresolved"]) == {
        "DO",
        "IF",
        "KNOW",
        "THEN",
        "MAYBE",
        "MUST",
    }


def test_family_validator_refuses_malformed_and_unaccounted_decisions():
    book = load_rulebook()
    boundary = next(r for r in book["source_rules"] if r["rule_id"] == "EMOTION_FEAR_ADJ")["definition_boundary"]
    assert family_contract_status(boundary) == "VALID_FAMILY_CONTRACT"
    assert family_contract_status(None) == "MALFORMED_FAMILY_CONTRACT"
    changed = deepcopy(boundary)
    changed["cells"].pop("FAR")
    assert family_contract_status(changed) == "INCOMPLETE_FAMILY_ACCOUNT"
    changed = deepcopy(boundary)
    changed["cells"]["FAR"]["kind"] = []
    assert family_contract_status(changed) == "UNKNOWN_FAMILY_DECISION"
    changed = deepcopy(boundary)
    changed["cells"]["DO"]["domain"] = ["+1"]
    assert family_contract_status(changed) == "FAMILY_DECISION_SHAPE"
    changed = deepcopy(boundary)
    changed["cells"]["FAR"]["domain"] = ["0"]
    assert family_contract_status(changed) == "FAMILY_SILENCE_MISMATCH"
