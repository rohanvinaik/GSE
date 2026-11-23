"""Versioned JSON-only task contract for a single lexical coordinate.

Examples teach the response algebra, not a replacement dictionary. Native
definitions and observations remain data; the output has exactly one field.
"""

from GSE.curation.schema import BIPOLAR_PAIRS
from GSE.namespace import current_id, identity_form
from GSE.primitives_v2 import PRIMITIVE_FAMILIES, get_primitive_info

from .foundation import BANKS
from .model_evidence import FORMAT as EVIDENCE_VIEW_FORMAT
from .model_evidence import candidate_links_contract, compact_candidate_links, evidence_view

PROTOCOL_VERSION = "GSE.lexical-component-entailment/14"
SCAFFOLD_VIEW_FORMAT = "GSE.symbolic-scaffold-view/1"


def coordinate_contract(bank: str) -> dict:
    """Expose registry semantics without inventing a missing negative pole.

    The glosses quote the registry's existing comments disambiguating
    English homographs; they are not new lexical assignments. Ordinal tables
    are deliberately not promoted into bank signs or full-vector defaults.
    """
    info = get_primitive_info(bank)
    if bank not in BANKS or info is None:
        raise ValueError("INVALID_MODEL_COORDINATE")
    negative = {**dict(BIPOLAR_PAIRS), "WANT": "NOT_WANT"}.get(bank)
    glosses = {
        "KIND": "Category/type",
        "LIKE": "Similarity",
        "INFER": "Epistemic inference - draw conclusion from evidence",
        "BE": "Stative existence",
        "EXIST": "Ontological status",
    }
    coordinate = {
        "positive_pole": bank,
        "negative_pole": negative if negative is not None else {"code": "NOT_DECLARED"},
        "negative_without_declared_pole": "REQUIRES_EXPLICIT_SOURCE_DEFINITION_ELSE_UNRESOLVED",
        "zero": "JUSTIFIED_ORTHOGONALITY",
        "null": "CANNOT_DETERMINE",
        "scale": "WORD",
        "category": info.bank.name,
        "bipolar_dimension": info.bipolar_dim,
        "families": sorted(
            name
            for name, family in PRIMITIVE_FAMILIES.items()
            if isinstance(family["primitives"], list) and bank in family["primitives"]
        ),
        "registry_gloss": glosses.get(bank),
        "registry_source": "GSE/primitives_v2.py",
        "hierarchy_base": info.is_hierarchy_base,
        "hierarchy_semantics": "ORDINAL_METADATA_SEPARATE_FROM_BASE_SIGN",
        "polarity_source": "GSE/curation/lexicon_builder/foundation.py#WANT_POLARITY"
        if bank == "WANT"
        else "GSE/curation/schema.py#BIPOLAR_PAIRS",
    }
    if bank == "BE":
        coordinate["scope_convention"] = {
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
    if bank == "BODY":
        coordinate["examples"] = [
            {"input": {"definition": "Delivered into a vein", "pos": "adj"}, "output": {"BODY": 1}},
            {"input": {"definition": "Delivered into the chamber of a pump", "pos": "adj"}, "output": {"BODY": 0}},
            {"input": {"definition": None, "pos": "adj"}, "output": {"BODY": None}},
            {
                "input": {"definition": "An organism with a segmented body and jointed appendages", "pos": "noun"},
                "output": {"BODY": 1},
            },
            {
                "input": {
                    "definition": "An organism of a specified genus",
                    "pos": "noun",
                    "verified_defining_genus": {
                        "relation": "EXACT_NATIVE_IS_A",
                        "definition": "Organisms having an internal supporting skeleton",
                    },
                },
                "output": {"BODY": 1},
            },
        ]
        coordinate["scope_convention"] = {
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
            "source": "docs/program/LEXICON_CONSTRUCTION_DESIGN.md#body-reference-content-scope",
        }
    if bank == "WORDS":
        coordinate["scope_convention"] = {
            "code": "DEFINITION_OWN_WORD_CONTENT",
            "positive_content": ["EXPLICIT_SINGULAR_WORD_AS_DEFINING_GENUS"],
            "insufficient_for_positive": ["WORD_MENTIONED_IN_AN_EXAMPLE", "WORD_AS_ARGUMENT_OF_ANOTHER_GENUS"],
            "zero_requires": "INDEPENDENT_DEFINITION_SCOPED_JUSTIFICATION",
            "unsupported_remains": "UNRESOLVED",
            "authority": "SOURCE_BACKED_DESIGN_INTERPRETATION",
            "source": "docs/program/LEXICON_CONSTRUCTION_DESIGN.md#words-defining-genus-scope",
        }
        coordinate["examples"] = [
            {"input": {"definition": "A word used to greet someone.", "pos": "noun"}, "output": {"WORDS": 1}},
        ]
    return coordinate


EXAMPLES = (
    {
        "input": {"lemma": "want", "definition": "feel a desire for something", "pos": "verb", "bank": "WANT"},
        "output": {"WANT": 1},
    },
    {
        "input": {"lemma": "not want", "definition": "not wanting something", "pos": "verb", "bank": "WANT"},
        "output": {"WANT": -1},
    },
    {
        "input": {"lemma": "stone", "definition": "a lump of hard mineral matter", "pos": "noun", "bank": "WANT"},
        "output": {"WANT": 0},
    },
    {
        "input": {"lemma": "unidentified", "definition": None, "pos": None, "bank": "SEE"},
        "output": {"SEE": None},
    },
)

def protocol_contract() -> dict:
    """Return independent protocol data, including the pinned polarity map."""
    import copy

    return {
        "format": PROTOCOL_VERSION,
        "operation": "LEXICAL_COMPONENT_ENTAILMENT",
        "scope": "OWN_DEFINITION",
        "definition_text": {
            "content": "/input/definition/definition",
            "identity": "/input/definition/entry_id",
            "expansion_witness": "/input/definition_content",
        },
        "excluded_scope": ["WORLD_ASSOCIATION", "ARGUMENT_IDENTITY", "EXAMPLE_CONTENT"],
        "codebook": {
            "-1": "DEFINITIONAL_NEGATIVE_POLE",
            "0": "JUSTIFIED_ORTHOGONALITY",
            "1": "DEFINITIONAL_POSITIVE_POLE",
            "null": "UNRESOLVED",
        },
        "negative_poles": {**dict(BIPOLAR_PAIRS), "WANT": "NOT_WANT"},
        "output_fields": "REQUESTED_BANK_ONLY",
        "known_values": "IMMUTABLE",
        "symbolic_context": "APPROVED_RULES_WITH_GUARDS_DISPOSITIONS_DOMAINS_AND_PROOF",
        "scaffold_view": SCAFFOLD_VIEW_FORMAT,
        "candidate_evidence": "IDENTITY_LINK_AND_SCOPE_REQUIRED_NOT_AUTOMATIC_ASSIGNMENT",
        "coordinates": {bank: coordinate_contract(bank) for bank in BANKS},
        "evidence_view": EVIDENCE_VIEW_FORMAT,
        "candidate_links": candidate_links_contract(),
        "examples": copy.deepcopy(EXAMPLES),
    }


def compact_scaffold(scaffold: dict, bank: str) -> dict:
    """Project only the wire view along exact approved constraint connectivity.

    Guard dependencies participate in the graph even when blocked or excepted.
    All surviving domains and actual context remain. Omitted proofs and tables
    are identified by deterministic hashes; the complete original request stays
    the replay authority and is never rewritten by this view.
    """
    import copy
    import hashlib
    import json

    def digest(value):
        encoded = json.dumps(identity_form(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    connected = {bank}
    rules = scaffold["approved_relations"]
    while True:
        expanded = connected | {
            name
            for rule in rules
            if connected.intersection(rule["banks"] + rule["absent_evidence"])
            for name in rule["banks"] + rule["absent_evidence"]
        }
        if expanded == connected:
            break
        connected = expanded
    selected, omitted = [], []
    for rule in rules:
        relevant = bool(connected.intersection(rule["banks"]))
        if rule.get("requested_component") is not relevant:
            raise ValueError("INVALID_MODEL_SCAFFOLD_COMPONENT")
        (selected if relevant else omitted).append(rule)
    rule_ids = {rule["rule_id"] for rule in selected}
    proofs, omitted_proofs = [], []
    for receipt in scaffold["proof_trace"]:
        ids = set(receipt.get("rule_ids", ()))
        if "rule_id" in receipt:
            ids.add(receipt["rule_id"])
        relevant = receipt["kind"] == "INFERENCE_SCOPE" or receipt.get("bank") in connected or bool(ids & rule_ids)
        (proofs if relevant else omitted_proofs).append(receipt)
    data = copy.deepcopy(scaffold)
    data.update(
        {
            "format": SCAFFOLD_VIEW_FORMAT,
            "approved_relations": copy.deepcopy(selected),
            "proof_trace": copy.deepcopy(proofs),
            "component_banks": sorted(connected),
            "selection": "REQUESTED_BANK_TRANSITIVE_APPROVED_RULE_AND_GUARD_DEPENDENCIES",
            "inference_scope": "RETAINED_INFERENCE_SCOPE_RECEIPT_DESCRIBES_FULL_CLOSURE",
            "full_scaffold_sha256": digest(scaffold),
            "omissions": {
                "code": "OUTSIDE_REQUESTED_APPROVED_CONSTRAINT_COMPONENT",
                "approved_relation_count": len(omitted),
                "approved_relations_sha256": digest(omitted),
                "proof_receipt_count": len(omitted_proofs),
                "proof_receipts_sha256": digest(omitted_proofs),
                "semantics": "OMITTED_IS_NOT_ZERO_OR_UNAPPROVED",
            },
        }
    )
    return data


def _abbreviation_content(evidence: dict, definition: dict | None) -> dict | None:
    """Select semantic text only for one verified, terminal abbreviation link."""
    if not isinstance(definition, dict) or not definition.get("entry_id"):
        return None
    references = [
        record["features"]["native_reference"]
        for record in evidence["records"]
        if record.get("entry_id") == definition["entry_id"] and "native_reference" in record["features"]
    ]
    if len(references) != 1:
        return None
    packet = references[0]
    root = packet["source_entry"]
    sense = root["native_sense"]
    tags = sense.get("tags")
    if (
        packet["relation"] != "alt_of"
        or packet["code"] != "TARGET_DEFINITIONS_AVAILABLE"
        or sense.get("alt_of") != [packet["link"]]
        or sense.get("form_of")
        or not isinstance(tags, list)
        or not any(tag in ("abbreviation", "initialism", "acronym") for tag in tags)
        or any(root[key] != definition.get(key) for key in ("entry_id", "lemma", "pos", "definition"))
        or len(packet["target_entries"]) != 1
    ):
        return None
    target = packet["target_entries"][0]
    if target["entry_id"] == root["entry_id"]:
        return None
    return {
        "code": "UNIQUE_TERMINAL_NATIVE_ABBREVIATION",
        "definition": target["definition"],
        "surface_definition": root["definition"],
        "target_entry_id": target["entry_id"],
        "source_sha256": packet["source_sha256"],
    }


def model_input(payload: dict) -> dict:
    """Remove the null placeholder, which completion models otherwise copy.

    The original request retains every native record for replay. The wire view
    reports schema-based omissions and full-record hashes, never truncates to a
    context window, and never turns an unrequested coordinate into output.
    """
    import copy

    if current_id(payload.get("format")) != "GSE.bank-request/2" or payload.get("bank") not in BANKS:
        raise ValueError("INVALID_MODEL_REQUEST")
    scaffold = payload.get("scaffold")
    if (
        type(scaffold) is not dict
        or current_id(scaffold.get("format")) != "GSE.symbolic-scaffold/1"
        or type(scaffold.get("domains")) is not dict
        or scaffold["domains"].get(payload["bank"]) != payload.get("allowed_values")
        or type(scaffold.get("approved_relations")) is not list
        or type(scaffold.get("proof_trace")) is not list
        or type(scaffold.get("context")) is not dict
    ):
        raise ValueError("INVALID_MODEL_SCAFFOLD")
    data = copy.deepcopy(payload)
    data.pop("fill", None)
    data.pop("definition_content", None)
    data["scaffold"] = compact_scaffold(data["scaffold"], data["bank"])
    if data.get("observations"):
        evidence = evidence_view(data.pop("observations"), data["bank"])
        content = _abbreviation_content(evidence, data.get("definition"))
        if content is not None:
            data["definition_content"] = content
            data["definition"]["definition"] = content["definition"]
        data["evidence"] = compact_candidate_links(evidence)
    contract = protocol_contract()
    bank = data["bank"]
    contract.pop("negative_poles")
    contract["coordinate"] = contract.pop("coordinates")[bank]
    return {**contract, "input": data}
