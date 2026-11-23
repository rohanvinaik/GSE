"""Typed symbolic context reaches the real one-cell boundary unchanged."""

import copy
import hashlib
import json
from dataclasses import replace
from itertools import product

import pytest

from GSE.curation.lexicon_builder.engine import DomainRestriction, Relation
from GSE.curation.lexicon_builder.evidence import Definition
from GSE.curation.lexicon_builder.model_protocol import coordinate_contract, model_input, protocol_contract
from GSE.curation.lexicon_builder.residual import LEGACY_REQUEST_FORMAT, OllamaTransport, build_request, complete_bank
from GSE.curation.lexicon_builder.resolution import resolve_dictionary

DEFINITION = Definition("entry:desire", "desire", "verb", "feel a desire for something")
BANKS = ("FEEL", "WANT", "GOOD")


def rule(name="equal", **kwargs):
    fields = {"approved": True, "authority": "conditional"}
    fields.update(kwargs)
    return Relation(name, ("FEEL", "WANT"), tuple((v, v) for v in (-1, 0, 1)), ("source:rule",), **fields)


def request(rules=(), assertions=(), context=None, restrictions=(), observations=()):
    state = resolve_dictionary(BANKS, assertions, rules, context, domain_restrictions=restrictions)
    return build_request(
        DEFINITION.entry_id, "WANT", state, observations, definition=DEFINITION, relations=rules, context=context
    )


def test_full_scaffold_and_native_candidate_scope_reach_transport_without_output_expansion():
    rules = (rule(),)
    restrictions = (DomainRestriction("FEEL", (0, 1), "native", "record:native", "dictionary"),)
    observations = (
        {
            "source": "nrc_emotion",
            "record_id": "rating",
            "family": "affect",
            "scope": "association",
            "entry_id": None,
            "candidate_entry_ids": [DEFINITION.entry_id, "other:sense"],
            "features": {"emotions": {"joy": 0}},
        },
    )
    original = request(rules, context={"pos": "verb"}, restrictions=restrictions, observations=observations)
    wire = model_input(original.payload())
    scaffold = wire["input"]["scaffold"]
    assert scaffold["domains"] == {"FEEL": [0, 1], "WANT": [0, 1], "GOOD": [-1, 0, 1]}
    assert scaffold["context"] == {"pos": "verb"}
    assert scaffold["approved_relations"][0]["allowed_rows"] == [[-1, -1], [0, 0], [1, 1]]
    assert scaffold["approved_relations"][0]["disposition"] == "ACTIVE"
    assert scaffold["approved_relations"][0]["provenance"] == ["source:rule"]
    assert any(receipt["kind"] == "DOMAIN_RESTRICTION" for receipt in scaffold["proof_trace"])
    evidence = wire["input"]["evidence"]["records"][0]
    assert evidence["entry_id"] is None
    assert evidence["candidate_entry_ids"] == [DEFINITION.entry_id, "other:sense"]
    assert evidence["scope"] == "association"
    calls = []

    def transport(payload, schema):
        calls.append((model_input(payload), schema))
        return '{"WANT":0}'

    result = complete_bank(original, BANKS, (), rules, transport, {"pos": "verb"}, domain_restrictions=restrictions)
    assert result.code == "ASSIGNED"
    assert result.resolution.assignments == {"FEEL": 0, "WANT": 0}
    assert calls[0][1]["required"] == ["WANT"]
    assert set(calls[0][1]["properties"]) == {"WANT"}
    assert calls[0][0] == wire


def test_guarded_blocked_and_excepted_rules_are_never_presented_as_active():
    rules = (
        rule("guarded", guards=(("pos", "noun"),)),
        Relation("positive", ("WANT",), ((1,),), ("source:a",), approved=True),
        Relation("negative", ("WANT",), ((-1,),), ("source:b",), approved=True),
        Relation("candidate", ("GOOD",), ((0,),), ("source:c",), approved=False),
    )
    payload = request(rules, context={"pos": "verb"}).payload()
    records = {record["rule_id"]: record for record in payload["scaffold"]["approved_relations"]}
    assert "candidate" not in records
    assert records["guarded"]["disposition"] == "BLOCKED"
    assert records["guarded"]["reason"] == "GUARD_MISMATCH"
    assert records["positive"]["disposition"] == "EXCEPTED_FOR_THIS_DEFINITION"
    assert records["negative"]["disposition"] == "EXCEPTED_FOR_THIS_DEFINITION"
    assert any(r["kind"] == "CONDITIONAL_EXCEPTION" for r in payload["scaffold"]["proof_trace"])


def test_evidence_guard_receipt_retains_relevance_without_assigning_its_bank():
    rules = (
        Relation(
            "absence",
            ("GOOD", "WANT"),
            tuple((a, b) for a, b in product((-1, 0, 1), repeat=2) if a == 0 or b == 0),
            ("source:absence",),
            approved=True,
            absent_evidence=("WANT",),
        ),
    )
    state = resolve_dictionary(BANKS, (), rules, evidence_banks=("WANT",))
    value = build_request(DEFINITION.entry_id, "WANT", state, (), definition=DEFINITION, relations=rules)
    record = value.payload()["scaffold"]["approved_relations"][0]
    assert record["disposition"] == "BLOCKED"
    assert record["reason"] == "RELEVANT_EVIDENCE"
    assert record["absent_evidence"] == ["WANT"]
    guard = next(r for r in value.scaffold["proof_trace"] if r["kind"] == "EVIDENCE_GUARD")
    assert guard["witnesses"][0]["supplied_evidence"] is True
    assert value.known == {}


def test_omitted_relation_or_guard_context_refuses_instead_of_dropping_symbolic_evidence():
    rules = (rule(guards=(("pos", "verb"),)),)
    state = resolve_dictionary(BANKS, (), rules, {"pos": "verb"})
    with pytest.raises(ValueError, match="missing_request_relation_context"):
        build_request(DEFINITION.entry_id, "WANT", state, (), definition=DEFINITION)
    with pytest.raises(ValueError, match="inconsistent_request_guard_context"):
        build_request(DEFINITION.entry_id, "WANT", state, (), definition=DEFINITION, relations=rules)


@pytest.mark.parametrize("change", ["table", "provenance", "context", "unrequested_domain", "proof"])
def test_same_requested_domain_and_known_values_do_not_hide_stale_context(change):
    rules = (rule(),)
    context = {"pos": "verb"}
    original = request(rules, context=context)
    restrictions = ()
    if change == "table":
        rules = (replace(rules[0], allowed_rows=tuple(product((-1, 0, 1), repeat=2))),)
    elif change == "provenance":
        rules = (replace(rules[0], provenance=("changed",)),)
    elif change == "context":
        context = {"pos": "adjective"}
    elif change == "unrequested_domain":
        restrictions = (DomainRestriction("GOOD", (0, 1), "native", "record", "dictionary"),)
    else:
        original.scaffold["proof_trace"].append({"kind": "FORGED"})
    seen = []
    result = complete_bank(
        original,
        BANKS,
        (),
        rules,
        lambda *args: seen.append(args) or '{"WANT":1}',
        context,
        domain_restrictions=restrictions,
    )
    assert result.code == "STALE_REQUEST"
    assert seen == []


def test_legacy_request_regenerates_original_bytes_but_cannot_be_submitted_to_new_protocol():
    state = resolve_dictionary(BANKS, (), (rule(),))
    old = build_request(
        DEFINITION.entry_id, "WANT", state, (), definition=DEFINITION, request_format=LEGACY_REQUEST_FORMAT
    )
    payload = {
        "format": "gse.bank-request/1",
        "entry_id": DEFINITION.entry_id,
        "definition": {
            "entry_id": DEFINITION.entry_id,
            "lemma": "desire",
            "pos": "verb",
            "definition": DEFINITION.definition,
        },
        "bank": "WANT",
        "allowed_values": [-1, 0, 1],
        "known": {},
        "observations": [],
        "fill": {"WANT": None},
    }
    assert old.payload() == payload
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    assert old.request_id == hashlib.sha256(raw.encode()).hexdigest()
    with pytest.raises(ValueError, match="INVALID_MODEL_REQUEST"):
        model_input(payload)


def test_context_copies_are_independent_and_null_stays_unknown():
    rules = (rule(),)
    original = request(rules)
    payload = original.payload()
    payload["scaffold"]["domains"]["WANT"] = [0]
    payload["scaffold"]["approved_relations"][0]["provenance"].append("changed")
    assert original.allowed_values == (-1, 0, 1)
    assert original.scaffold["approved_relations"][0]["provenance"] == ["source:rule"]
    result = complete_bank(original, BANKS, (), rules, lambda *_: '{"WANT":null}')
    assert result.code == "ABSTAINED"
    assert result.assertion is None
    assert result.resolution.assignments == {}


@pytest.mark.parametrize(
    "bank,gloss",
    [
        ("KIND", "Category/type"),
        ("LIKE", "Similarity"),
        ("INFER", "Epistemic inference - draw conclusion from evidence"),
    ],
)
def test_canonical_metadata_disambiguates_bank_and_does_not_invent_negative(bank, gloss):
    coordinate = coordinate_contract(bank)
    assert coordinate["registry_gloss"] == gloss
    assert coordinate["negative_pole"] == {"code": "NOT_DECLARED"}
    assert coordinate["scale"] == "WORD"
    assert coordinate["families"]


def test_polarity_registry_metadata_and_scope_are_pinned_in_protocol_identity(monkeypatch):
    contract = protocol_contract()
    assert contract["coordinates"]["WANT"]["negative_pole"] == "NOT_WANT"
    assert contract["coordinates"]["THEN"]["negative_pole"] == "NOW"
    assert contract["coordinates"]["THEN"]["bipolar_dimension"] == "TEMPORAL_REF"
    assert contract["excluded_scope"] == ["WORLD_ASSOCIATION", "ARGUMENT_IDENTITY", "EXAMPLE_CONTENT"]
    before = OllamaTransport("model").identity
    altered = copy.deepcopy(contract)
    altered["coordinates"]["KIND"]["registry_gloss"] = "changed meaning"
    monkeypatch.setattr("GSE.curation.lexicon_builder.model_protocol.protocol_contract", lambda: altered)
    assert OllamaTransport("model").identity != before


@pytest.mark.parametrize("bad", [None, {}, [], "scaffold"])
def test_missing_or_malformed_scaffold_never_reaches_model(bad):
    payload = request().payload()
    payload["scaffold"] = bad
    with pytest.raises(ValueError, match="INVALID_MODEL_SCAFFOLD"):
        model_input(payload)


def test_wire_component_omits_disconnected_tables_only_with_hashes_and_preserves_full_receipt():
    from GSE.curation.lexicon_builder.foundation import BANKS as ALL_BANKS
    from GSE.curation.lexicon_builder.foundation import projection_relations

    rules = projection_relations()
    state = resolve_dictionary(ALL_BANKS, (), rules, {"pos": "noun"})
    value = build_request(
        DEFINITION.entry_id, "WANT", state, (), definition=DEFINITION, relations=rules, context={"pos": "noun"}
    )
    before = copy.deepcopy(value.payload())
    wire = model_input(value.payload())["input"]
    scaffold = wire["scaffold"]
    assert scaffold["approved_relations"] == []
    assert scaffold["component_banks"] == ["WANT"]
    assert scaffold["domains"] == before["scaffold"]["domains"]
    assert wire["known"] == {"GOOD": 0}
    assert scaffold["context"] == {"pos": "noun"}
    assert scaffold["omissions"]["approved_relation_count"] == len(rules)
    assert scaffold["omissions"]["proof_receipt_count"] > 0
    assert len(scaffold["omissions"]["proof_receipts_sha256"]) == 64
    assert all(p["kind"] == "INFERENCE_SCOPE" for p in scaffold["proof_trace"])
    assert value.payload() == before
    assert len(before["scaffold"]["approved_relations"]) == 23


def test_connected_wire_view_keeps_transitive_blocked_and_excepted_rules_with_proofs():
    banks = (*BANKS, "CAN", "MUST")
    rules = (
        rule(),
        Relation(
            "bridge",
            ("FEEL", "GOOD"),
            tuple((v, v) for v in (-1, 0, 1)),
            ("source:bridge",),
            approved=True,
            guards=(("pos", "noun"),),
        ),
        Relation("positive", ("GOOD",), ((1,),), ("source:a",), approved=True),
        Relation("negative", ("GOOD",), ((-1,),), ("source:b",), approved=True),
        Relation(
            "disconnected",
            ("CAN", "MUST"),
            tuple(product((-1, 0, 1), repeat=2)),
            ("source:independent",),
            approved=True,
        ),
    )
    state = resolve_dictionary(banks, (), rules, {"pos": "verb"})
    value = build_request(
        DEFINITION.entry_id, "WANT", state, (), definition=DEFINITION, relations=rules, context={"pos": "verb"}
    )
    view = model_input(value.payload())["input"]["scaffold"]
    assert view["component_banks"] == ["FEEL", "GOOD", "WANT"]
    statuses = {r["rule_id"]: r["disposition"] for r in view["approved_relations"]}
    assert statuses == {
        "equal": "ACTIVE",
        "bridge": "BLOCKED",
        "negative": "EXCEPTED_FOR_THIS_DEFINITION",
        "positive": "EXCEPTED_FOR_THIS_DEFINITION",
    }
    assert any(p["kind"] == "CONDITIONAL_EXCEPTION" for p in view["proof_trace"])
    assert any(p["kind"] == "RELATION_SKIPPED" and p["rule_id"] == "bridge" for p in view["proof_trace"])
    assert view["omissions"]["approved_relation_count"] == 1
    assert all("disconnected" not in p.get("rule_ids", ()) for p in view["proof_trace"])


def test_evidence_guard_dependency_connects_a_bank_outside_table_columns():
    rules = (
        rule(),
        Relation("guard-edge", ("FEEL",), ((-1,), (0,), (1,)), ("source:g",), approved=True, absent_evidence=("GOOD",)),
        Relation("good-domain", ("GOOD",), ((0,), (1,)), ("source:r",), approved=True),
    )
    value = request(rules)
    view = model_input(value.payload())["input"]["scaffold"]
    assert view["component_banks"] == ["FEEL", "GOOD", "WANT"]
    assert {r["rule_id"] for r in view["approved_relations"]} == {"equal", "guard-edge", "good-domain"}
    assert any(p["kind"] == "EVIDENCE_GUARD" for p in view["proof_trace"])
    assert view["omissions"]["approved_relation_count"] == 0


def test_forged_component_flag_cannot_hide_a_connected_rule():
    value = request((rule(),)).payload()
    value["scaffold"]["approved_relations"][0]["requested_component"] = False
    with pytest.raises(ValueError, match="INVALID_MODEL_SCAFFOLD_COMPONENT"):
        model_input(value)
