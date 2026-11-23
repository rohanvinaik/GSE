"""Wire sharing preserves every unresolved definition alternative losslessly."""

import copy
import hashlib
import json

import pytest

from GSE.curation.lexicon_builder.engine import propagate
from GSE.curation.lexicon_builder.evidence import Definition
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.model_evidence import (
    CANDIDATE_LINKS_FORMAT,
    FORMAT,
    compact_candidate_links,
    evidence_view,
    restore_candidate_links,
)
from GSE.curation.lexicon_builder.model_protocol import PROTOCOL_VERSION, model_input, protocol_contract
from GSE.curation.lexicon_builder.residual import build_request


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def observations():
    first = ["fixture:" + str(i) + ":" + "a" * 64 for i in range(20)]
    second = ["fixture:" + str(i) + ":" + "b" * 64 for i in range(20)]
    first.extend([first[0], first[0]])
    return [
        {
            "source": "nrc_emotion",
            "record_id": f"r{index}",
            "family": "affect",
            "scope": "association",
            "entry_id": None,
            "candidate_entry_ids": ids,
            "features": {"emotions": {"positive": 0} if index % 2 else {}, "lemma": "fixture"},
        }
        for index, ids in enumerate((first, second, first, second))
    ]


def test_shared_lists_roundtrip_order_duplicates_zero_absence_and_record_hashes():
    view = evidence_view(observations(), "WANT")
    original = copy.deepcopy(view)
    compact = compact_candidate_links(view)
    assert compact["format"] == CANDIDATE_LINKS_FORMAT
    assert len(canonical(compact).encode()) < len(canonical(view).encode())
    assert restore_candidate_links(compact) == view == original
    assert compact["expanded_view_sha256"] == digest(view)
    assert [r["full_record_sha256"] for r in compact["view"]["records"]] == [
        r["full_record_sha256"] for r in view["records"]
    ]
    assert compact["view"]["records"][0]["features"]["emotions"] == {}
    assert compact["view"]["records"][1]["features"]["emotions"] == {"positive": 0}
    assert all(r["entry_id"] is None for r in compact["view"]["records"])
    assert "NOT_ZERO" in compact["codebook"]["unknown"]
    restored = restore_candidate_links(compact)
    restored["records"][0]["candidate_entry_ids"].clear()
    assert restore_candidate_links(compact) == original


@pytest.mark.parametrize("mode", ["empty", "single", "tiny", "unique"])
def test_nonbeneficial_views_remain_expanded_independent_copies(mode):
    native = observations()
    if mode == "empty":
        native = []
    elif mode == "single":
        native = native[:1]
    elif mode == "tiny":
        for record in native:
            record["candidate_entry_ids"] = ["d"]
    else:
        native = native[:2]
    view = evidence_view(native, "WANT")
    compact = compact_candidate_links(view)
    assert compact["format"] == FORMAT
    assert compact == view and compact is not view
    assert restore_candidate_links(compact) == view


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("missing_pool", "INVALID_CANDIDATE_LINK_POOL"),
        ("missing_reference", "CANDIDATE_LINK_VIEW_HASH_MISMATCH"),
        ("foreign_reference", "INVALID_CANDIDATE_LINK_REFERENCE"),
        ("typed_reference", "INVALID_CANDIDATE_LINK_REFERENCE"),
        ("both_forms", "INVALID_CANDIDATE_LINK_REFERENCE"),
        ("pool_tamper", "CANDIDATE_LINK_POOL_HASH_MISMATCH"),
        ("pool_reorder_rehash", "CANDIDATE_LINK_VIEW_HASH_MISMATCH"),
        ("swap_references", "CANDIDATE_LINK_VIEW_HASH_MISMATCH"),
        ("record_reorder", "CANDIDATE_LINK_VIEW_HASH_MISMATCH"),
        ("unused_pool", "UNUSED_CANDIDATE_LINK_POOL"),
        ("extra_envelope", "INVALID_CANDIDATE_LINK_ENCODING"),
        ("changed_codebook", "INVALID_CANDIDATE_LINK_CODEBOOK"),
        ("hidden_nan", "INVALID_MODEL_EVIDENCE_JSON"),
    ],
)
def test_corruption_refuses_before_releasing_reconstructed_evidence(mutation, code):
    compact = compact_candidate_links(evidence_view(observations(), "WANT"))
    records, pools = compact["view"]["records"], compact["candidate_sets"]
    if mutation == "missing_pool":
        pools.pop("c0")
    elif mutation == "missing_reference":
        records[0].pop("candidate_entry_ids_ref")
    elif mutation == "foreign_reference":
        records[0]["candidate_entry_ids_ref"] = "c99"
    elif mutation == "typed_reference":
        records[0]["candidate_entry_ids_ref"] = None
    elif mutation == "both_forms":
        records[0]["candidate_entry_ids"] = []
    elif mutation == "pool_tamper":
        pools["c0"]["entry_ids"].pop()
    elif mutation == "pool_reorder_rehash":
        pools["c0"]["entry_ids"].reverse()
        pools["c0"]["sha256"] = digest(pools["c0"]["entry_ids"])
    elif mutation == "swap_references":
        records[0]["candidate_entry_ids_ref"], records[1]["candidate_entry_ids_ref"] = (
            records[1]["candidate_entry_ids_ref"],
            records[0]["candidate_entry_ids_ref"],
        )
    elif mutation == "record_reorder":
        records.reverse()
    elif mutation == "unused_pool":
        pools["c2"] = copy.deepcopy(pools["c0"])
    elif mutation == "extra_envelope":
        compact["unrecognized"] = {}
    elif mutation == "changed_codebook":
        compact["codebook"]["unknown"] = "ZERO"
    elif mutation == "hidden_nan":
        pools["c2"] = {"entry_ids": [float("nan")], "sha256": "unused"}
    with pytest.raises(ValueError, match=f"^{code}$"):
        restore_candidate_links(compact)


def test_compaction_rejects_malformed_reference_or_candidate_ids_in_expanded_view():
    view = evidence_view(observations(), "WANT")
    view["records"][0]["candidate_entry_ids_ref"] = "c0"
    with pytest.raises(ValueError, match="INVALID_CANDIDATE_LINK_RECORD"):
        compact_candidate_links(view)
    del view["records"][0]["candidate_entry_ids_ref"]
    view["records"][0]["candidate_entry_ids"] = [0]
    with pytest.raises(ValueError, match="INVALID_CANDIDATE_LINK_IDS"):
        compact_candidate_links(view)


def test_production_model_input_pins_wire_contract_and_preserves_full_request():
    native = observations()
    resolution = propagate(BANKS, (), ())
    request = build_request(
        "fixture:d",
        "WANT",
        resolution,
        tuple(native),
        definition=Definition("fixture:d", "fixture", "noun", "A fixture."),
    )
    payload = request.payload()
    original = copy.deepcopy(payload)
    wire = model_input(payload)
    assert PROTOCOL_VERSION == "gse.lexical-component-entailment/14"
    assert protocol_contract()["candidate_links"]["format"] == CANDIDATE_LINKS_FORMAT
    assert restore_candidate_links(wire["input"]["evidence"]) == evidence_view(native, "WANT")
    assert request.payload() == payload == original
    assert request.request_id == digest(original)
