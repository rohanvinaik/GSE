"""Reviewed dependency replay and explicit guarded proposal behavior."""

import pytest
from test_lexicon_builder_reviewed_patterns import FakeTransport, execute, fixture, ruling

from gse.curation.lexicon_builder.engine import Assertion


def warranted(*, antecedent=None, guards=None, absent=()):
    return {
        "antecedent": antecedent,
        "consequent": ["GOOD", 0],
        "guards": guards if guards is not None else [["pos", "noun"]],
        "absent_evidence": list(absent),
        "warrant": {
            "warrant_id": "synthetic:test-warrant",
            "kind": "DEFINITIONAL_DERIVATION",
            "source_refs": ["synthetic:test-source"],
            "statement": "Synthetic typed law for contract tests only.",
            "review_id": "synthetic:review",
            "reviewer": "synthetic:reviewer",
        },
    }


def test_complete_reviewed_model_prefix_replays_without_context_stripping(tmp_path):
    data = fixture()
    held = data["entries"][1]
    first = ruling(held, "SEE", 0)
    first_assertion = Assertion(**first["receipt"]["assertion"])
    second = ruling(held, "HEAR", 1, previous=(first_assertion,))
    second_assertion = Assertion(**second["receipt"]["assertion"])
    last = ruling(held, "WANT", 1, previous=(first_assertion, second_assertion))
    data["rulings"][-1:] = [last, first, second]  # input order is not dependency order
    transport = FakeTransport(['{"GOOD":0}'])
    result = execute(tmp_path, data, transport, 1)
    audit = result["candidates"][0]["audits"][0]
    assert audit["code"] == "MODEL_AGREEMENT"
    assert transport.calls[0][0]["known"] == {"SEE": 0, "HEAR": 1, "WANT": 1}
    assert audit["accepted_assertion"]["bank"] == "GOOD"
    assert audit["accepted_assertion"]["source"] == "model:synthetic-pinned-audit"
    assert result["lexicon_writes"] is False


def test_dependency_target_leakage_is_refused_even_when_ancestor_is_reviewed(tmp_path):
    data = fixture()
    first = ruling(data["entries"][1], "GOOD", 0)
    dependency = Assertion(**first["receipt"]["assertion"])
    data["rulings"][-1:] = [first, ruling(data["entries"][1], "WANT", 1, previous=(dependency,))]
    transport = FakeTransport([])
    report = execute(tmp_path, data, transport, 1)
    assert report["candidates"][0]["audit_outcomes"] == {"TARGET_LEAKAGE_IN_ANTECEDENT_REQUEST": 1}
    assert transport.calls == []


def test_unreviewed_dependency_stays_refusal_not_zero(tmp_path):
    data = fixture()
    first = ruling(data["entries"][1], "SEE", 0)
    data["rulings"][-1] = ruling(data["entries"][1], "WANT", 1, previous=(Assertion(**first["receipt"]["assertion"]),))
    report = execute(tmp_path, data)
    assert report["candidates"][0]["audit_outcomes"] == {"UNSUPPORTED_PRIOR_MODEL_DEPENDENCY": 1}


def test_unary_guarded_proposal_stages_but_does_not_enter_direct_model_context(tmp_path):
    data = fixture()
    data.pop("candidates")
    data["guarded_candidates"] = [warranted()]
    transport = FakeTransport(['{"GOOD":0}'])
    report = execute(tmp_path, data, transport, 1)
    candidate = report["candidates"][0]
    assert candidate["antecedent"] is None
    assert candidate["proposal_kind"] == "GUARDED_WARRANTED_PROPOSAL"
    assert candidate["warrant"] == data["guarded_candidates"][0]["warrant"]
    assert candidate["warrant_sha256"]
    assert candidate["relation"]["approved"] is False
    assert candidate["staging"][0]["changed_domains"]["GOOD"]["after"] == [0]
    assert transport.calls[0][0]["known"] == {}
    assert transport.calls[0][0]["scaffold"]["approved_relations"] == []


@pytest.mark.parametrize(
    "mutate,code",
    [
        (lambda c: c.update(guards=[["pos", "verb"]]), "GUARD_NOT_MET"),
        (lambda c: c.update(absent_evidence=["GOOD"]), "RELEVANT_EVIDENCE_PRESENT"),
    ],
)
def test_guard_or_relevant_evidence_prevents_staging_and_model_call(tmp_path, mutate, code):
    data = fixture()
    candidate = warranted()
    mutate(candidate)
    data["guarded_candidates"] = [candidate]
    data["candidates"] = []
    if code == "RELEVANT_EVIDENCE_PRESENT":
        data["entries"][1]["observations"] = [
            {
                "entry_id": "heldout",
                "source": "websters1913",
                "record_id": "native:r",
                "family": "dictionary",
                "scope": "lexical",
                "features": {"definition": "native content"},
            }
        ]
    report = execute(tmp_path, data, FakeTransport([]), 1)
    assert report["candidates"][0]["staging"][0]["code"] == code
    assert report["candidates"][0]["audit_outcomes"] == {code: 1}
    assert report["model_calls"] == 0


@pytest.mark.parametrize(
    "mutate,code",
    [
        (lambda c: c.update(guards=[]), "UNARY_PATTERN_REQUIRES_TYPED_GUARD"),
        (lambda c: c["warrant"].update(kind="MODEL_AGREEMENT"), "EXPLICIT_CAUSAL_WARRANT_REQUIRED"),
        (lambda c: c["warrant"].update(source_refs=[]), "EXPLICIT_CAUSAL_WARRANT_REQUIRED"),
        (lambda c: c.update(guards=[["label", "invented"]]), "UNSUPPORTED_PATTERN_CONTEXT"),
        (lambda c: c.update(consequent=["GOOD", True]), "INVALID_GUARDED_PATTERN_COORDINATE"),
    ],
)
def test_guarded_candidates_require_typed_scope_and_explicit_nonstatistical_warrant(tmp_path, mutate, code):
    data = fixture()
    candidate = warranted()
    mutate(candidate)
    data["guarded_candidates"] = [candidate]
    with pytest.raises(ValueError, match=code):
        execute(tmp_path, data)
