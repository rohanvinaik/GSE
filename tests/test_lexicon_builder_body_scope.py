"""Reference-only native pronouns do not justify positive bodily lexical content."""

import copy
import json
import sqlite3
from dataclasses import asdict

import pytest

from GSE.curation.external_sources.gse_closed_class import GSEClosedClassParser
from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.engine import propagate
from GSE.curation.lexicon_builder.evidence import collect_evidence
from GSE.curation.lexicon_builder.model_batch import OllamaBatchTransport
from GSE.curation.lexicon_builder.model_protocol import coordinate_contract, model_input
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.residual import OllamaTransport, build_request, complete_bank
from GSE.curation.lexicon_builder.scope_admission import BODY_SCOPE_SOURCE, model_scope_admission
from GSE.curation.lexicon_builder.validation import validate_build

BANKS = ("BODY", "BE", "SOMEONE", "SOMETHING", "EXIST")


def native(word="you"):
    parser = GSEClosedClassParser()
    parser.load()
    bundle = collect_evidence({"gse_closed_class": parser}, (word,))
    entry_id = f"gse_closed_class:pronoun:{word}"
    definition = next(item for item in bundle.definitions if item.entry_id == entry_id)
    observations = tuple(
        json.loads(json.dumps(asdict(item))) for item in bundle.observations if item.entry_id == entry_id
    )
    ids = {record["record_id"] for record in observations}
    assertions = tuple(item for item in bundle.assertions if item.record_id in ids)
    current = propagate(BANKS, assertions, ())
    return build_request(entry_id, "BODY", current, observations, definition=definition), assertions, current


@pytest.mark.parametrize("word", ["you", "he", "it", "this", "someone"])
def test_native_reference_only_positive_body_refusal_preserves_unknown_and_known(word):
    request, assertions, current = native(word)
    before = request.payload()
    result = complete_bank(request, BANKS, assertions, (), lambda *_: '{"BODY":1}')
    assert result.code == "SCOPE_UNJUSTIFIED"
    assert result.assertion is None
    assert result.resolution == current
    assert current.domains["BODY"] == frozenset((-1, 0, 1))
    assert "BODY" not in current.assignments
    assert result.details["reason"] == "ENTITY_REFERENCE_ALONE_DOES_NOT_JUSTIFY_POSITIVE_BODY"
    assert result.details["source"] == BODY_SCOPE_SOURCE
    assert result.details["disposition"] == "NO_ASSERTION_CURRENT_DOMAINS_UNCHANGED"
    assert request.payload() == before


@pytest.mark.parametrize("value,code", [(None, "ABSTAINED"), (0, "ASSIGNED"), (-1, "ASSIGNED")])
def test_other_body_answers_follow_ordinary_admission(value, code):
    request, assertions, current = native()
    assert model_scope_admission(request.entry_id, "BODY", value, request.observations) == {
        "code": "NOT_APPLICABLE",
        "reason": "OUTSIDE_POSITIVE_BODY_SCOPE_CHECK",
    }
    result = complete_bank(request, BANKS, assertions, (), lambda *_: json.dumps({"BODY": value}))
    assert result.code == code
    if value is None:
        assert result.assertion is None and result.resolution == current
    else:
        assert result.assertion is not None and result.assertion.value == value


@pytest.mark.parametrize("raw", ['{"BODY":true}', '{"BODY":2}', '{"BODY":1,"BE":0}', "{}", "null", ""])
def test_malformed_ruling_never_reaches_assignment(raw):
    request, assertions, current = native()
    result = complete_bank(request, BANKS, assertions, (), lambda *_: raw)
    assert result.code == "INVALID_OUTPUT"
    assert result.assertion is None and result.resolution == current


@pytest.mark.parametrize(
    "foreign_entry,scope",
    [
        (None, "lexical"),
        ("foreign", "lexical"),
        ("self", "association"),
        ("self", "world"),
        ("self", "source_structure"),
    ],
)
def test_foreign_candidate_and_nonlexical_records_do_not_supply_own_body_content(foreign_entry, scope):
    request, _, _ = native()
    record = {
        "entry_id": request.entry_id if foreign_entry == "self" else foreign_entry,
        "candidate_entry_ids": [request.entry_id],
        "source": "fixture",
        "scope": scope,
        "features": {"primitives": {"BODY": 1}},
    }
    assert (
        model_scope_admission(request.entry_id, "BODY", 1, request.observations + (record,))["code"]
        == "SCOPE_UNJUSTIFIED"
    )


def test_additional_exact_lexical_source_prevents_reference_only_classification():
    request, _, _ = native()
    other = {
        "entry_id": request.entry_id,
        "source": "fixture",
        "scope": "lexical",
        "features": {"definition": "Separate bodily content."},
    }
    assert model_scope_admission(request.entry_id, "BODY", 1, request.observations + (other,)) == {
        "code": "NOT_APPLICABLE",
        "reason": "ADDITIONAL_EXACT_LEXICAL_SOURCE",
    }


@pytest.mark.parametrize(
    "change", ["boolean", "own_body", "definition", "role", "extra", "empty", "not_mapping", "record_id"]
)
def test_native_labels_require_exact_complete_record_equality(change):
    request, _, _ = native()
    observations = copy.deepcopy(request.observations)
    features = observations[0]["features"]
    if change == "boolean":
        features["primitives"]["SOMEONE"] = True
    elif change == "own_body":
        features["primitives"]["BODY"] = 1
    elif change == "definition":
        features["definition"] = "Different lexical definition."
    elif change == "role":
        features["grammar_roles"] = ["NOUN"]
    elif change == "extra":
        features["extra"] = True
    elif change == "empty":
        features["primitives"] = {}
    elif change == "not_mapping":
        observations[0]["features"] = None
    else:
        observations[0]["record_id"] = None
    assert model_scope_admission(request.entry_id, "BODY", 1, observations)["code"] == "NOT_APPLICABLE"


@pytest.mark.parametrize("records", [None, {}, [None], []])
def test_unclassified_or_absent_source_never_triggers_spelling_mask(records):
    assert model_scope_admission("gse_closed_class:pronoun:you", "BODY", 1, records)["code"] == "NOT_APPLICABLE"


def test_body_contract_has_scoped_interpretation_authority_and_protocol_pin():
    request, _, _ = native()
    original = request.payload()
    coordinate = coordinate_contract("BODY")
    assert coordinate["scope_convention"] == {
        "code": "DEFINITION_OWN_BODILY_CONTENT_REQUIRED",
        "positive_requires": "DEFINITION_OWN_BODILY_CONTENT",
        "positive_content": ["ANATOMICAL_STRUCTURE", "ANATOMICAL_SITE_REQUIRED_BY_DEFINITION"],
        "positive_sufficient": {
            "scope": "LITERAL_ORGANISM_KIND",
            "content": "CONSTITUTIVE_ANATOMY",
            "routes": ["EXPLICIT_OWN_DEFINITION", "VERIFIED_DEFINING_GENUS_CONTENT"],
            "genus_requires": ["EXACT_NATIVE_IDENTITY", "SOURCE_VERIFIED_DEFINING_ANCESTRY", "GENUS_DEFINITION"],
            "authority": "FOUNDER_APPROVED",
            "source": "docs/program/LEXICON_CONSTRUCTION_DESIGN.md#constitutive-anatomy-and-defining-genus",
        },
        "insufficient_for_positive": ["ENTITY_REFERENCE_ALONE", "GRAMMATICAL_ANIMACY_ALONE"],
        "zero_requires": "INDEPENDENT_DEFINITION_SCOPED_JUSTIFICATION",
        "unsupported_remains": "UNRESOLVED",
        "authority": "SOURCE_BACKED_DESIGN_INTERPRETATION",
        "source": BODY_SCOPE_SOURCE,
    }
    wire = model_input(original)
    assert wire["format"] == "GSE.lexical-component-entailment/14"
    assert [example["output"] for example in coordinate["examples"]] == [
        {"BODY": 1},
        {"BODY": 0},
        {"BODY": None},
        {"BODY": 1},
        {"BODY": 1},
    ]
    assert wire["coordinate"] == coordinate
    assert coordinate["negative_pole"] == {"code": "NOT_DECLARED"}
    assert request.payload() == original
    assert original["allowed_values"] == [-1, 0, 1]
    assert "BODY" not in original["known"]
    assert coordinate_contract("BE")["scope_convention"]["authority"] == "FOUNDER_APPROVED"
    assert "scope_convention" not in coordinate_contract("EXIST")


def test_actual_batched_completion_refuses_body_and_journals_without_assignment(tmp_path, monkeypatch):
    parser = GSEClosedClassParser()
    parser.load()
    bundle = collect_evidence({"gse_closed_class": parser}, ("you", "he"))
    path = tmp_path / "body-reference.db"
    build_dictionary(bundle, path)
    entries = ("gse_closed_class:pronoun:he", "gse_closed_class:pronoun:you")
    with sqlite3.connect(path) as conn:
        before = conn.execute("SELECT * FROM definition_states ORDER BY entry_id").fetchall()
    base = OllamaTransport("fixture", thinking=False, output_tokens=1024)
    posts = []

    def network(message, _malformed_code):
        if message.method == "GET":
            return {"models": [{"name": "fixture", "digest": "a" * 64}]}
        posts.append(json.loads(message.data))
        return {"done": True, "done_reason": "stop", "response": '{"q0":{"BODY":1},"q1":{"BODY":1}}'}

    monkeypatch.setattr(base, "_request_json", network)
    monkeypatch.setattr("GSE.curation.llm.ollama_client.register_model", lambda *_: None)
    transport = OllamaBatchTransport(base, max_items=2)
    transport.pin()
    report = complete_dictionary(path, transport, 2, banks=("BODY",), entry_ids=entries, batch_size=2)
    assert report["outcomes"] == {"SCOPE_UNJUSTIFIED": 2}
    assert report["model_calls"] == 2 and report["transport_invocations"] == len(posts) == 1
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT * FROM definition_states ORDER BY entry_id").fetchall() == before
        assert conn.execute("SELECT COUNT(*) FROM accepted_model_receipts").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM primitive_values WHERE primitive='BODY'").fetchone()[0] == 0
        for code, details in conn.execute("SELECT code,details FROM completion_attempts"):
            assert code == "SCOPE_UNJUSTIFIED"
            assert json.loads(details)["reason"] == "ENTITY_REFERENCE_ALONE_DOES_NOT_JUSTIFY_POSITIVE_BODY"
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"


def test_publication_audit_flags_historical_reference_body_ruling_without_rewriting(tmp_path, monkeypatch):
    from GSE.curation.lexicon_builder import scope_admission
    from GSE.curation.lexicon_builder.publication import _model_scope_audit

    parser = GSEClosedClassParser()
    parser.load()
    path = tmp_path / "historical-body.db"
    build_dictionary(collect_evidence({"gse_closed_class": parser}, ("you",)), path)
    # Construct a receipt admitted before this narrow guard existed. The
    # current publication consumer must flag it without rewriting its history.
    with monkeypatch.context() as historical:
        historical.setattr(scope_admission, "model_scope_admission", lambda *_: {"code": "NOT_APPLICABLE"})
        result = complete_dictionary(
            path, lambda *_: '{"BODY":1}', 1, entry_ids=("gse_closed_class:pronoun:you",), banks=("BODY",)
        )
        assert result["outcomes"] == {"ASSIGNED": 1}
    before = path.read_bytes()
    with sqlite3.connect(path) as conn:
        audit = _model_scope_audit(conn)
    assert audit["code"] == "SCOPE_UNJUSTIFIED"
    assert audit["outcomes"] == {"SCOPE_UNJUSTIFIED": 1}
    assert audit["records"][0]["admission"]["reason"] == "ENTITY_REFERENCE_ALONE_DOES_NOT_JUSTIFY_POSITIVE_BODY"
    assert path.read_bytes() == before
