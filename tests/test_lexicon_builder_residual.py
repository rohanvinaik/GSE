"""Adversarial tests for the one-cell completion boundary; no live model calls."""

import copy
import json
from dataclasses import replace
from functools import partial
from unittest.mock import MagicMock, patch

import pytest

from gse.curation.lexicon_builder.engine import Assertion, Relation, propagate
from gse.curation.lexicon_builder.evidence import Definition
from gse.curation.lexicon_builder.residual import OllamaTransport, build_request, complete_bank
from gse.curation.lexicon_builder.resolution import resolve_dictionary


class Transport:
    model = "test-model"

    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, payload, schema):
        self.calls.append((payload, schema))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def known_assertion():
    return Assertion("FEEL", 1, "source", "record:1", "dictionary")


def observation():
    return {"source": "dictionary", "record_id": "record:1", "features": {"kind": "mental"}}


def relation(rule_id, banks, rows):
    return Relation(rule_id, banks, rows, ("test:contract",), approved=True)


def test_request_is_one_cell_typed_and_reproducible():
    state = propagate(("FEEL", "WANT"), (known_assertion(),), ())
    request = build_request(
        "definition:1",
        "WANT",
        state,
        (observation(),),
        definition=Definition("definition:1", "want", "verb", "desire something"),
    )
    same = build_request(
        "definition:1",
        "WANT",
        state,
        (observation(),),
        definition=Definition("definition:1", "want", "verb", "desire something"),
    )
    assert request.request_id == same.request_id
    assert request.allowed_values == (-1, 0, 1)
    assert request.known == {"FEEL": 1}
    assert request.payload()["fill"] == {"WANT": None}
    assert request.payload()["definition"] == {
        "entry_id": "definition:1",
        "lemma": "want",
        "pos": "verb",
        "definition": "desire something",
    }
    assert request.output_schema() == {
        "type": "object",
        "properties": {"WANT": {"type": ["integer", "null"], "enum": [-1, 0, 1, None]}},
        "required": ["WANT"],
        "additionalProperties": False,
    }


def test_request_hash_is_independent_of_dictionary_key_order():
    state = propagate(("FEEL", "WANT"), (), ())
    left = build_request(
        "d", "WANT", state, ({"a": 1, "b": 2},), definition=Definition("d", "want", "verb", "desire something")
    )
    right = build_request(
        "d", "WANT", state, ({"b": 2, "a": 1},), definition=Definition("d", "want", "verb", "desire something")
    )
    assert left.request_id == right.request_id


def test_definition_context_is_required_even_without_observations():
    state = propagate(("WANT",), (), ())
    with pytest.raises(TypeError):
        build_request("opaque-id", "WANT", state, ())
    definition = Definition("opaque-id", "want", "verb", "desire something")
    request = build_request("opaque-id", "WANT", state, (), definition=definition)
    transport = Transport('{"WANT":null}')
    assert complete_bank(request, ("WANT",), (), (), transport).code == "ABSTAINED"
    payload, schema = transport.calls[0]
    assert payload["definition"] == {
        "entry_id": "opaque-id",
        "lemma": "want",
        "pos": "verb",
        "definition": "desire something",
    }
    assert payload["observations"] == []
    assert schema["required"] == ["WANT"]


@pytest.mark.parametrize("field", ["entry_id", "lemma", "pos", "definition"])
@pytest.mark.parametrize("value", [None, "", "  ", True, 3, []])
def test_definition_context_rejects_malformed_fields(field, value):
    definition = Definition("d", "want", "verb", "desire something")
    object.__setattr__(definition, field, value)
    with pytest.raises(ValueError, match="invalid_definition_context"):
        build_request("d", "WANT", propagate(("WANT",), (), ()), (), definition=definition)


@pytest.mark.parametrize("definition", [None, {}, "desire something"])
def test_definition_context_requires_typed_definition(definition):
    with pytest.raises(ValueError, match="invalid_definition_context"):
        build_request("d", "WANT", propagate(("WANT",), (), ()), (), definition=definition)


def test_definition_identity_must_match_request():
    with pytest.raises(ValueError, match="definition_identity_mismatch"):
        build_request(
            "other",
            "WANT",
            propagate(("WANT",), (), ()),
            (),
            definition=Definition("d", "want", "verb", "desire something"),
        )


@pytest.mark.parametrize("field,value", [("lemma", "need"), ("pos", "noun"), ("definition", "require something")])
def test_definition_context_is_part_of_digest_and_freshness(field, value):
    definition = Definition("d", "want", "verb", "desire something")
    state = propagate(("WANT",), (), ())
    request = build_request("d", "WANT", state, (), definition=definition)
    changed = replace(definition, **{field: value})
    other = build_request("d", "WANT", state, (), definition=changed)
    assert request.request_id != other.request_id
    forged = replace(request, definition=changed)
    transport = Transport('{"WANT":1}')
    assert complete_bank(forged, ("WANT",), (), (), transport).code == "STALE_REQUEST"
    assert transport.calls == []


def test_definition_payload_is_an_independent_copy():
    request = build_request(
        "d",
        "WANT",
        propagate(("WANT",), (), ()),
        (),
        definition=Definition("d", "want", "verb", "desire something"),
    )
    payload = request.payload()
    payload["definition"]["definition"] = "changed"
    assert request.payload()["definition"]["definition"] == "desire something"


def test_request_and_payload_do_not_share_mutable_source_data():
    state = propagate(("FEEL", "WANT"), (known_assertion(),), ())
    original = observation()
    request = build_request(
        "d", "WANT", state, (original,), definition=Definition("d", "want", "verb", "desire something")
    )
    original["features"]["kind"] = "changed"
    payload = request.payload()
    payload["known"]["FEEL"] = -1
    payload["observations"][0]["features"]["kind"] = "changed_again"
    assert request.known == {"FEEL": 1}
    assert request.observations[0]["features"]["kind"] == "mental"


@pytest.mark.parametrize("entry_id", [None, "", 1, True])
def test_request_requires_an_entry_identity(entry_id):
    state = propagate(("WANT",), (), ())
    with pytest.raises(ValueError, match="invalid_entry_id"):
        build_request(entry_id, "WANT", state, (), definition=Definition("d", "want", "verb", "desire something"))


def test_request_rejects_unknown_assigned_and_conflicted_banks():
    state = propagate(("FEEL", "WANT"), (known_assertion(),), ())
    with pytest.raises(ValueError, match="unknown_bank"):
        build_request("d", "NUMBER", state, (), definition=Definition("d", "want", "verb", "desire something"))
    with pytest.raises(ValueError, match="already_assigned"):
        build_request("d", "FEEL", state, (), definition=Definition("d", "want", "verb", "desire something"))
    conflicting = propagate(
        ("FEEL", "WANT"),
        (known_assertion(), Assertion("FEEL", -1, "other", "r2", "dictionary")),
        (),
    )
    with pytest.raises(ValueError, match="conflicted_resolution"):
        build_request("d", "WANT", conflicting, (), definition=Definition("d", "want", "verb", "desire something"))


@pytest.mark.parametrize(
    "observations", [[{}], ("prose",), ({"bad": float("nan")},), ({1: "key"},), ({"bad": object()},)]
)
def test_request_rejects_untyped_or_non_json_observations(observations):
    state = propagate(("WANT",), (), ())
    with pytest.raises(ValueError):
        build_request("d", "WANT", state, observations, definition=Definition("d", "want", "verb", "desire something"))


def test_request_domain_is_narrowed_by_symbolic_rules():
    rules = (relation("allowed", ("WANT",), ((0,), (1,))),)
    request = build_request(
        "d",
        "WANT",
        propagate(("WANT",), (), rules),
        (),
        definition=Definition("d", "want", "verb", "desire something"),
        relations=rules,
    )
    assert request.allowed_values == (0, 1)
    assert request.output_schema()["properties"]["WANT"]["enum"] == [0, 1, None]


@pytest.mark.parametrize("value", [-1, 0, 1])
def test_valid_ruling_adds_only_requested_assertion_with_model_provenance(value):
    banks = ("FEEL", "WANT")
    assertions = (known_assertion(),)
    request = build_request(
        "d",
        "WANT",
        propagate(banks, assertions, ()),
        (observation(),),
        definition=Definition("d", "want", "verb", "desire something"),
    )
    transport = Transport(json.dumps({"WANT": value}))
    result = complete_bank(request, banks, assertions, (), transport)
    assert result.code == "ASSIGNED"
    assert result.assertion.bank == "WANT"
    assert result.assertion.value == value
    assert result.assertion.source == "model:test-model"
    assert result.assertion.family == "model"
    assert result.assertion.record_id == request.request_id
    assert result.resolution.assignments == {"FEEL": 1, "WANT": value}
    assert assertions == (known_assertion(),)
    assert len(transport.calls) == 1


def test_abstention_never_assigns_zero():
    banks = ("WANT",)
    initial = propagate(banks, (), ())
    request = build_request("d", "WANT", initial, (), definition=Definition("d", "want", "verb", "desire something"))
    result = complete_bank(request, banks, (), (), Transport('{"WANT":null}'))
    assert result.code == "ABSTAINED"
    assert result.assertion is None
    assert result.resolution.assignments == {}
    assert result.resolution.domains == initial.domains


@pytest.mark.parametrize(
    "output",
    [
        "",
        "not json",
        '```json\n{"WANT":1}\n```',
        "{}",
        "null",
        "[]",
        "1",
        '{"WANT":true}',
        '{"WANT":1.0}',
        '{"WANT":"1"}',
        '{"WANT":2}',
        '{"WANT":NaN}',
        '{"WANT":[]}',
        '{"FEEL":-1}',
        '{"WANT":1,"FEEL":-1}',
        '{"WANT":1,"explanation":"ok"}',
        '{"WANT":0,"WANT":1}',
        None,
        {"WANT": 1},
    ],
)
def test_invalid_output_never_overwrites_or_fills(output):
    banks = ("FEEL", "WANT")
    assertions = (known_assertion(),)
    initial = propagate(banks, assertions, ())
    request = build_request("d", "WANT", initial, (), definition=Definition("d", "want", "verb", "desire something"))
    result = complete_bank(request, banks, assertions, (), Transport(output))
    assert result.code == "INVALID_OUTPUT"
    assert result.assertion is None
    assert result.resolution.domains == initial.domains
    assert result.resolution.assignments == {"FEEL": 1}


def test_valid_ternary_outside_remaining_domain_is_rejected():
    banks = ("WANT",)
    rules = (relation("nonnegative", banks, ((0,), (1,))),)
    request = build_request(
        "d",
        "WANT",
        propagate(banks, (), rules),
        (),
        definition=Definition("d", "want", "verb", "desire something"),
        relations=rules,
    )
    result = complete_bank(request, banks, (), rules, Transport('{"WANT":-1}'))
    assert result.code == "INVALID_OUTPUT"
    assert result.resolution.domains["WANT"] == frozenset({0, 1})


def test_transport_exception_is_named_and_never_zero():
    banks = ("WANT",)
    request = build_request(
        "d", "WANT", propagate(banks, (), ()), (), definition=Definition("d", "want", "verb", "desire something")
    )
    result = complete_bank(request, banks, (), (), Transport(TimeoutError("timed out")))
    assert result.code == "TRANSPORT_ERROR"
    assert result.assertion is None
    assert result.details["error_type"] == "TimeoutError"
    assert result.resolution.assignments == {}


@pytest.mark.parametrize("mutation", ["assigned", "narrowed", "known_changed", "conflict"])
def test_stale_state_is_rejected_before_transport(mutation):
    banks = ("FEEL", "WANT")
    assertions = (known_assertion(),)
    request = build_request(
        "d",
        "WANT",
        propagate(banks, assertions, ()),
        (),
        definition=Definition("d", "want", "verb", "desire something"),
    )
    rules = ()
    if mutation == "assigned":
        assertions += (Assertion("WANT", 0, "s", "r", "dictionary"),)
    elif mutation == "narrowed":
        rules = (relation("narrow", ("WANT",), ((0,), (1,))),)
    elif mutation == "known_changed":
        assertions = (Assertion("FEEL", -1, "s", "r", "dictionary"),)
    else:
        assertions += (Assertion("FEEL", -1, "s", "r", "dictionary"),)
    transport = Transport('{"WANT":1}')
    result = complete_bank(request, banks, assertions, rules, transport)
    assert result.code == "STALE_REQUEST"
    assert result.assertion is None
    assert transport.calls == []


def test_mutated_request_observations_fail_digest_before_transport():
    banks = ("WANT",)
    request = build_request(
        "d",
        "WANT",
        propagate(banks, (), ()),
        (observation(),),
        definition=Definition("d", "want", "verb", "desire something"),
    )
    request.observations[0]["features"]["kind"] = "changed"
    transport = Transport('{"WANT":1}')
    assert complete_bank(request, banks, (), (), transport).code == "STALE_REQUEST"
    assert transport.calls == []


def test_assigned_ruling_propagates_before_another_request():
    banks = ("A", "B")
    rules = (relation("equal", banks, ((0, 0), (1, 1))),)
    initial = propagate(banks, (), rules)
    request = build_request(
        "d", "A", initial, (), definition=Definition("d", "want", "verb", "desire something"), relations=rules
    )
    result = complete_bank(request, banks, (), rules, Transport('{"A":1}'))
    assert result.code == "ASSIGNED"
    assert result.resolution.assignments == {"A": 1, "B": 1}
    with pytest.raises(ValueError, match="already_assigned"):
        build_request(
            "d",
            "B",
            result.resolution,
            (),
            definition=Definition("d", "want", "verb", "desire something"),
            relations=rules,
        )


def test_ruling_that_exposes_joint_contradiction_is_not_admitted(monkeypatch):
    # Deliberately cap joint search below the eight combinations. The problem
    # has the witness A=B=C=0, but GAC alone also leaves unsupported value 1.
    monkeypatch.setattr(
        "gse.curation.lexicon_builder.resolution.propagate", partial(propagate, max_joint_assignments=7)
    )
    banks = ("A", "B", "C")
    rules = (
        relation("ab", ("A", "B"), ((0, 0), (1, 1))),
        relation("bc", ("B", "C"), ((0, 0), (1, 1))),
        relation("ac", ("A", "C"), ((0, 0), (0, 1), (1, 0))),
    )
    initial = resolve_dictionary(banks, (), rules)
    assert initial.code == "PARTIAL"
    assert any(record["kind"] == "SOLVER_LIMIT" for record in initial.trace)
    assert propagate(banks, (), rules).assignments == {"A": 0, "B": 0, "C": 0}
    request = build_request(
        "d", "A", initial, (), definition=Definition("d", "want", "verb", "desire something"), relations=rules
    )
    result = complete_bank(request, banks, (), rules, Transport('{"A":1}'))
    assert result.code == "CONTRADICTION"
    assert result.assertion is None
    assert result.resolution.domains == initial.domains
    assert result.resolution.assignments == {}
    assert result.details["conflicts"]
    assert result.details["conditional_exceptions"]


def test_model_can_resolve_previously_excepted_conditional_component():
    banks = ("WANT",)
    rules = (relation("positive", banks, ((1,),)), relation("negative", banks, ((-1,),)))
    initial = resolve_dictionary(banks, (), rules)
    request = build_request(
        "d", "WANT", initial, (), definition=Definition("d", "want", "verb", "desire something"), relations=rules
    )
    result = complete_bank(request, banks, (), rules, Transport('{"WANT":1}'))
    assert result.code == "ASSIGNED"
    assert result.resolution.assignments == {"WANT": 1}
    exceptions = [record for record in result.resolution.trace if record["kind"] == "CONDITIONAL_EXCEPTION"]
    assert exceptions[0]["rule_ids"] == ("negative",)


def test_model_may_not_erase_a_known_conditional_assignment(monkeypatch):
    monkeypatch.setattr(
        "gse.curation.lexicon_builder.resolution.propagate", partial(propagate, max_joint_assignments=7)
    )
    banks = ("A", "B", "C", "D")
    rules = (
        relation("ab", ("A", "B"), ((0, 0), (1, 1))),
        relation("bc", ("B", "C"), ((0, 0), (1, 1))),
        relation("ac", ("A", "C"), ((0, 0), (0, 1), (1, 0))),
        relation("known", ("D",), ((1,),)),
        relation("bridge", ("A", "D"), ((0, 1), (1, 1))),
    )
    initial = resolve_dictionary(banks, (), rules)
    assert initial.assignments == {"D": 1}
    assert any(record["kind"] == "SOLVER_LIMIT" for record in initial.trace)
    assert propagate(banks, (), rules).assignments == {"A": 0, "B": 0, "C": 0, "D": 1}
    request = build_request(
        "d", "A", initial, (), definition=Definition("d", "want", "verb", "desire something"), relations=rules
    )
    result = complete_bank(request, banks, (), rules, Transport('{"A":1}'))
    assert result.code == "CONTRADICTION"
    assert result.resolution.assignments == {"D": 1}
    assert result.details["changed_known"] == {"D": {"before": 1, "after": None}}


def test_guard_context_is_used_for_freshness_and_repropagation():
    banks = ("A", "B")
    rules = (Relation("equal", banks, ((0, 0), (1, 1)), ("source",), approved=True, guards=(("pos", "v"),)),)
    context = {"pos": "v"}
    request = build_request(
        "d",
        "A",
        propagate(banks, (), rules, context),
        (),
        definition=Definition("d", "want", "verb", "desire something"),
        relations=rules,
        context=context,
    )
    result = complete_bank(request, banks, (), rules, Transport('{"A":1}'), context)
    assert result.code == "ASSIGNED"
    assert result.resolution.assignments["B"] == 1


@pytest.mark.parametrize("model", [None, "", "  ", 3])
def test_transport_never_chooses_a_model(model):
    with pytest.raises(ValueError, match="model_required"):
        OllamaTransport(model)


@pytest.mark.parametrize("timeout", [None, True, 0, -1, float("nan"), float("inf"), "60"])
def test_transport_requires_finite_positive_timeout(timeout):
    with pytest.raises(ValueError, match="invalid_timeout"):
        OllamaTransport("test", timeout=timeout)


@pytest.mark.parametrize(
    "base_url", [None, "", "file:///tmp/model", "localhost", "http://localhost?a=1", "http://localhost#x"]
)
def test_transport_validates_endpoint(base_url):
    with pytest.raises(ValueError, match="invalid_base_url"):
        OllamaTransport("test", base_url=base_url)


def test_ollama_transport_sends_only_json_data_and_generation_schema():
    payload = build_request(
        "d",
        "WANT",
        propagate(("WANT", "FEEL"), (known_assertion(),), ()),
        (),
        definition=Definition("d", "want", "verb", "desire something"),
    ).payload()
    schema = {"type": "object", "additionalProperties": False}
    before = copy.deepcopy((payload, schema))
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"response":"{\\"WANT\\":0}"}'
    with patch("gse.curation.lexicon_builder.residual.urlopen", return_value=response) as opening:
        with (
            patch("gse.curation.llm.ollama_client.register_model") as register,
            patch.object(OllamaTransport, "_installed_digest", return_value="a" * 64),
        ):
            transport = OllamaTransport("explicit-model", "http://localhost:11434/", 7)
            transport.pin()
            result = transport(payload, schema)
    assert result == '{"WANT":0}'
    request = opening.call_args.args[0]
    assert opening.call_args.kwargs == {"timeout": 7.0}
    assert request.full_url == "http://localhost:11434/api/generate"
    body = json.loads(request.data)
    assert body["model"] == "explicit-model"
    protocol = json.loads(body["prompt"])
    assert {key: value for key, value in protocol["input"].items() if key != "scaffold"} == {
        key: value for key, value in payload.items() if key not in {"fill", "scaffold"}
    }
    assert protocol["input"]["scaffold"]["format"] == "gse.symbolic-scaffold-view/1"
    assert protocol["input"]["scaffold"]["domains"] == payload["scaffold"]["domains"]
    assert protocol["operation"] == "LEXICAL_COMPONENT_ENTAILMENT"
    assert protocol["coordinate"]["negative_pole"] == "NOT_WANT"
    assert "negative_poles" not in protocol
    assert body["format"] == schema
    assert "raw" not in body
    assert body["think"] is True
    assert body["stream"] is False
    assert "system" not in body
    assert (payload, schema) == before
    register.assert_called_once_with("explicit-model", "http://localhost:11434")


@pytest.mark.parametrize("envelope", [b"null", b"{}", b'{"response":0}', b"not json"])
def test_ollama_transport_rejects_missing_or_malformed_envelope(envelope):
    payload = build_request(
        "d",
        "WANT",
        propagate(("WANT",), (), ()),
        (),
        definition=Definition("d", "want", "verb", "desire something"),
    ).payload()
    response = MagicMock()
    response.__enter__.return_value.read.return_value = envelope
    with patch("gse.curation.lexicon_builder.residual.urlopen", return_value=response):
        with patch.object(OllamaTransport, "_installed_digest", return_value="a" * 64):
            transport = OllamaTransport("explicit-model")
            transport.pin()
            with pytest.raises(ValueError):
                transport(payload, {})


def test_transport_rejects_context_overflow_without_truncation_or_call():
    request = build_request(
        "d",
        "WANT",
        propagate(("WANT",), (), ()),
        (
            {
                "source": "nrc_emotion",
                "record_id": "a",
                "family": "ratings",
                "scope": "association",
                "features": {"lemma": "x" * 40000},
            },
        ),
        definition=Definition("d", "want", "verb", "desire something"),
    )
    with patch("gse.curation.lexicon_builder.residual.urlopen") as opening:
        with pytest.raises(ValueError, match="MODEL_CONTEXT_EXCEEDED"):
            OllamaTransport("explicit-model")(request.payload(), request.output_schema())
    opening.assert_not_called()


def test_model_receipt_identity_includes_protocol():
    transport = Transport('{"WANT":0}')
    transport.identity = "model@protocol-hash"
    request = build_request(
        "d",
        "WANT",
        propagate(("WANT",), (), ()),
        (),
        definition=Definition("d", "stone", "noun", "a lump of mineral matter"),
    )
    result = complete_bank(request, ("WANT",), (), (), transport)
    assert result.assertion.source == "model:model@protocol-hash"


@pytest.mark.parametrize("context", [None, True, 0, -1, 2047, 8192.0])
def test_transport_requires_valid_context_budget(context):
    with pytest.raises(ValueError, match="invalid_context_tokens"):
        OllamaTransport("explicit-model", context_tokens=context)


def test_model_protocol_keeps_all_source_observations():
    from gse.curation.lexicon_builder.model_protocol import model_input

    records = tuple(
        {
            "source": "nrc_emotion",
            "record_id": key,
            "family": "ratings",
            "scope": "association",
            "entry_id": None,
            "candidate_entry_ids": ["d"],
            "features": {"emotions": {"joy": value}},
        }
        for key, value in (("a", 1), ("b", 0))
    )
    request = build_request(
        "d",
        "WANT",
        propagate(("WANT",), (), ()),
        records,
        definition=Definition("d", "stone", "noun", "a lump of mineral matter"),
    )
    wire = model_input(request.payload())
    assert [record["features"] for record in wire["input"]["evidence"]["records"]] == [
        record["features"] for record in records
    ]
    assert wire["input"]["evidence"]["omission_semantics"] == "OMITTED_IS_NOT_ZERO"
    assert "fill" not in wire["input"]
    wire["input"]["evidence"]["records"][0]["record_id"] = "changed"
    assert request.observations == records


def test_transport_identity_changes_with_generation_contract():
    default = OllamaTransport("model")
    assert default.identity != OllamaTransport("model", thinking=False).identity
    assert default.identity != OllamaTransport("model", context_tokens=8192).identity
    assert default.identity == OllamaTransport("model").identity


def test_incomplete_model_output_is_never_admitted():
    payload = build_request(
        "d",
        "WANT",
        propagate(("WANT",), (), ()),
        (),
        definition=Definition("d", "want", "verb", "desire something"),
    ).payload()
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"response":"{\\"WANT\\":1}","done_reason":"length"}'
    with patch("gse.curation.lexicon_builder.residual.urlopen", return_value=response):
        with patch.object(OllamaTransport, "_installed_digest", return_value="a" * 64):
            transport = OllamaTransport("model")
            transport.pin()
            with pytest.raises(ValueError, match="INCOMPLETE_MODEL_OUTPUT"):
                transport(payload, {})
