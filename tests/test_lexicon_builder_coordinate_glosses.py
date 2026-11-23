"""Existing registry glosses disambiguate typed questions, not lexical values."""

import copy

import pytest

from GSE.curation.lexicon_builder import model_protocol
from GSE.curation.lexicon_builder.engine import Assertion, propagate
from GSE.curation.lexicon_builder.evidence import Definition
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.residual import OllamaTransport, build_request


@pytest.mark.parametrize("bank,gloss", [("BE", "Stative existence"), ("EXIST", "Ontological status")])
def test_coordinate_gloss_quotes_registry_without_inventing_negative_pole(bank, gloss):
    coordinate = model_protocol.coordinate_contract(bank)
    assert coordinate["registry_gloss"] == gloss
    assert coordinate["registry_source"] == "GSE/primitives_v2.py"
    assert coordinate["negative_pole"] == {"code": "NOT_DECLARED"}
    assert coordinate["zero"] == "JUSTIFIED_ORTHOGONALITY"
    assert coordinate["null"] == "CANNOT_DETERMINE"


def test_metadata_repair_changes_transport_pin_but_not_original_request(monkeypatch):
    resolution = propagate(BANKS, (Assertion("SOMEONE", 1, "fixture", "r", "dictionary"),), ())
    request = build_request(
        "fixture:pronoun",
        "BE",
        resolution,
        (),
        definition=Definition("fixture:pronoun", "you", "pronoun", "Second person reference."),
    )
    original = copy.deepcopy(request.payload())
    original_id = request.request_id
    current_contract = model_protocol.coordinate_contract

    def previous_contract(bank):
        result = current_contract(bank)
        if bank == "BE":
            result.pop("scope_convention")
        return result

    with monkeypatch.context() as old:
        old.setattr(model_protocol, "PROTOCOL_VERSION", "GSE.lexical-component-entailment/7")
        old.setattr(model_protocol, "coordinate_contract", previous_contract)
        previous_wire = model_protocol.model_input(original)
        previous_identity = OllamaTransport("fixture", thinking=False, output_tokens=1024).identity
    current_wire = model_protocol.model_input(original)
    current_identity = OllamaTransport("fixture", thinking=False, output_tokens=1024).identity
    assert current_identity != previous_identity
    assert current_wire["format"] == "GSE.lexical-component-entailment/14"
    assert current_wire["coordinate"]["registry_gloss"] == "Stative existence"
    previous_wire["format"] = current_wire["format"]
    previous_wire["coordinate"]["scope_convention"] = current_wire["coordinate"]["scope_convention"]
    assert previous_wire == current_wire
    assert request.payload() == original
    assert request.request_id == original_id
    assert "BE" not in original["known"]
    assert original["fill"] == {"BE": None}
    assert original["allowed_values"] == [-1, 0, 1]


def test_stative_scope_convention_is_be_specific_and_never_supplies_zero():
    coordinate = model_protocol.coordinate_contract("BE")
    convention = coordinate["scope_convention"]
    assert convention == {
        "code": "DEFINITION_OWN_STATIVE_CONTENT_REQUIRED",
        "positive_requires": "DEFINITION_OWN_STATIVE_CONTENT",
        "positive_sufficient": "NOUN_DEFINITION_OWN_STATE_DENOTATION",
        "grammatical_copula_alone": "INSUFFICIENT",
        "insufficient_for_positive": ["ENTITY_REFERENCE_ALONE"],
        "zero_requires": "INDEPENDENT_DEFINITION_SCOPED_JUSTIFICATION",
        "unsupported_remains": "UNRESOLVED",
        "authority": "FOUNDER_APPROVED",
        "source": "docs/program/LEXICON_CONSTRUCTION_DESIGN.md#be-stative-content-scope",
    }
    assert "scope_convention" not in model_protocol.coordinate_contract("EXIST")
    assert "scope_convention" not in model_protocol.coordinate_contract("SOMEONE")
    assert coordinate["negative_pole"] == {"code": "NOT_DECLARED"}
    resolution = propagate(BANKS, (Assertion("SOMEONE", 1, "fixture", "r", "dictionary"),), ())
    assert resolution.domains["BE"] == frozenset((-1, 0, 1))
    assert "BE" not in resolution.assignments


def test_word_genus_contract_preserves_the_unresolved_audit_question():
    definition = Definition("fixture:negative", "negative", "noun", "A word that indicates negation.")
    resolution = propagate(BANKS, (), ())
    request = build_request(definition.entry_id, "WORDS", resolution, (), definition=definition)
    original = request.payload()
    wire = model_protocol.model_input(original)

    convention = wire["coordinate"]["scope_convention"]
    assert convention["positive_content"] == ["EXPLICIT_SINGULAR_WORD_AS_DEFINING_GENUS"]
    assert "WORD_AS_ARGUMENT_OF_ANOTHER_GENUS" in convention["insufficient_for_positive"]
    assert convention["zero_requires"] == "INDEPENDENT_DEFINITION_SCOPED_JUSTIFICATION"
    assert wire["input"]["definition"]["definition"] == definition.definition
    assert request.payload() == original
    assert request.output_schema()["required"] == ["WORDS"]
    assert original["allowed_values"] == [-1, 0, 1]
    assert "WORDS" not in original["known"]
