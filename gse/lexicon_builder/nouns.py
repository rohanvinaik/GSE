"""Located noun heads, projected through the shared reading constructor.

These are sourced GSE projection conventions, not inheritance from every
participant in a frame. A noun's own target is distinguished from its
arguments. Unknown heads and other senses remain explicit unresolved readings.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import partial

from gse.lexicon_builder.core import Cell, Law, Observation
from gse.lexicon_builder.model import OllamaSelector
from gse.lexicon_builder.reading import Construction, ReadingSeed, construct_reading
from gse.lexicon_builder.sources import word_key
from gse.lexicon_builder.tail import attach_tail


@dataclass(frozen=True)
class NounHeadContract:
    frame_id: str
    target: str
    target_id: str
    head: str
    reason: str
    whole: str | None = None
    required_type: str | None = None


# Reviewed complete FrameNet 1.7 frame and FE definitions. These contracts
# identify nominal denotation; an FE with the same name in another frame has
# no authority. Generic Physical_entity/Artifact typing alone writes no head.
NOUN_HEAD_CONTRACTS = {
    "Containers": NounHeadContract(
        "78",
        "Container",
        "367",
        "SOMETHING",
        "The Container FE explicitly tags the target object conventionally used as a container.",
    ),
    "Animals": NounHeadContract(
        "2840",
        "Animal",
        "16148",
        "SOMETHING",
        "The frame's LUs refer to nonhuman, nonplant biological entities; Animal is the target organism.",
    ),
    "Clothing": NounHeadContract(
        "134",
        "Garment",
        "869",
        "SOMETHING",
        "The target denotes the clothing worn; Wearer and Body_location are arguments.",
    ),
    "Artifact": NounHeadContract(
        "421",
        "Artifact",
        "3874",
        "SOMETHING",
        "The nominal target denotes the designed entity or substance, including digital artifacts, not its Type.",
    ),
    "Buildings": NounHeadContract(
        "173",
        "Building",
        "6037",
        "SOMETHING",
        "The frame's words name fixed structures; Building denotes the entity built.",
    ),
    "People": NounHeadContract(
        "304",
        "Person",
        "2618",
        "SOMEONE",
        "The nominal Person target is explicitly a human being.",
        required_type="Human",
    ),
    "People_by_age": NounHeadContract(
        "973",
        "Person",
        "5937",
        "SOMEONE",
        "The Person target is the human being of an age; incorporated Age does not become the head.",
        required_type="Human",
    ),
    "People_by_vocation": NounHeadContract(
        "1071",
        "Person",
        "6263",
        "SOMEONE",
        "The Person target is the human being, with vocation as its characterization.",
        required_type="Human",
    ),
    "Organization": NounHeadContract(
        "1371",
        "Organization",
        "7698",
        "PEOPLE",
        "The nominal frame denotes intentionally formed human social groups; Members is a person.",
        required_type="Group",
    ),
    "Body_parts": NounHeadContract(
        "119",
        "Body_part",
        "692",
        "PART",
        "The target denotes a body part belonging to a Possessor; neither Possessor nor BODY is its own head.",
        whole="Possessor",
        required_type="Body_part",
    ),
    "Part_whole": NounHeadContract(
        "140",
        "Part",
        "1088",
        "PART",
        "The nominal target denotes a part of a Whole.",
        whole="Whole",
    ),
    "Shaped_part": NounHeadContract(
        "970",
        "Part",
        "5920",
        "PART",
        "The nominal target denotes a shaped part of a larger Whole.",
        whole="Whole",
    ),
    "Artifact_subpart": NounHeadContract(
        "2470",
        "Component",
        "14301",
        "PART",
        "The Component target is a part of a complex Artifact with a distinct Function.",
        whole="Artifact",
    ),
    "Vehicle_subpart": NounHeadContract(
        "2426",
        "Part",
        "14220",
        "PART",
        "The nominal target denotes an integrated part of a vehicle.",
        whole="Whole",
    ),
    "Connecting_architecture": NounHeadContract(
        "1025",
        "Part",
        "6107",
        "PART",
        "The nominal target denotes an integrated architectural part.",
        whole="Whole",
    ),
    "Type": NounHeadContract(
        "128",
        "Subtype",
        "848",
        "KIND",
        "The nominal target denotes a subtype, not an item belonging to it.",
    ),
    "Biological_classification": NounHeadContract(
        "2701",
        "Rank",
        "15444",
        "KIND",
        "Rank is explicitly always the target-denoting taxonomic category.",
    ),
}


# Explicit judgments of COMPLETE native LU definitions where a frame groups
# unlike heads. Keys are located LU identities, never lemma-wide exceptions.
# Exact definition checks prevent these authored judgments silently surviving a
# source revision. They do not parse definition text at build time.
NOUN_LU_CLAIMS = {
    "1588": ("Leadership", "SOMEONE", "Leader", "COD: a person in charge; a director or leader. "),
    "2387": (
        "Body_parts",
        "BODY",
        "Body_part",
        "COD: the physical structure, including the bones, flesh, and organs, of a person or an animal. ",
    ),
    "5511": ("People", "PEOPLE", "Person", "COD: human beings in general or considered collectively. "),
    "13115": ("Aggregate", "PEOPLE", "Aggregate", "COD: an organized group of people with a common function"),
    "2135": ("Aggregate", "PEOPLE", "Aggregate", "COD: a large number of people gathered together"),
    "2247": ("Education_teaching", "SOMEONE", "Teacher", "FN: A person who teaches in an educational establishment"),
}


def noun_record_status(record: object) -> str:
    """Validate the native boundary before interpreting a located noun claim."""
    if not isinstance(record, dict) or not isinstance(record.get("record_id"), str):
        return "INVALID_NATIVE_NOUN_RECORD"
    value = record.get("values")
    if not isinstance(value, dict) or not isinstance(value.get("pos"), str):
        return "INVALID_NATIVE_NOUN_RECORD"
    for field in ("lu_id", "frame", "frame_id", "definition", "frame_definition", "detail_status"):
        if field in value and not isinstance(value[field], str):
            return "INVALID_NATIVE_NOUN_FIELD"
    sources = value.get("source_record_ids", [])
    if not isinstance(sources, list) or any(not isinstance(s, str) for s in sources):
        return "INVALID_NATIVE_NOUN_PROVENANCE"
    elements = value.get("frame_elements", [])
    if not isinstance(elements, list):
        return "INVALID_NATIVE_NOUN_ELEMENTS"
    for fe in elements:
        if not isinstance(fe, dict):
            return "INVALID_NATIVE_NOUN_ELEMENTS"
        for field in ("name", "ID", "record_id", "definition"):
            if not isinstance(fe.get(field), str):
                return "INVALID_NATIVE_NOUN_ELEMENTS"
        types = fe.get("semantic_types", [])
        if not isinstance(types, list) or any(
            not isinstance(t, dict) or not isinstance(t.get("name"), str) for t in types
        ):
            return "INVALID_NATIVE_NOUN_TYPES"
    bindings = value.get("target_role_evidence", [])
    if not isinstance(bindings, list) or any(
        not isinstance(b, dict) or any(not isinstance(b.get(f), str) for f in ("kind", "frame_element", "record_id"))
        for b in bindings
    ):
        return "INVALID_NATIVE_NOUN_BINDINGS"
    return "VALID_NATIVE_NOUN_RECORD"


def noun_head_claim(record: dict) -> dict:
    """Decide or name why the located noun target has no supported head.

    Incorporation is retained as evidence but never treated as target identity.
    The reviewed nominal frame contract may identify a target when an LU has no
    DEN annotation. Corpus DEN bindings can vary with constructions (e.g.
    kind.n is annotated as Subtype and as Category); they do not replace the
    LU's construction-independent definition or veto it by a majority vote.
    """
    status = noun_record_status(record)
    if status != "VALID_NATIVE_NOUN_RECORD":
        return {"code": status}
    value = record["values"]
    contract = NOUN_HEAD_CONTRACTS.get(value.get("frame"))
    lu_claim = NOUN_LU_CLAIMS.get(value.get("lu_id"))
    if value.get("detail_status") != "AVAILABLE":
        return {"code": "NOUN_SOURCE_DETAIL_UNAVAILABLE"}
    if lu_claim:
        frame, head, target, definition = lu_claim
        if value.get("frame") != frame or value.get("definition", "").strip() != definition.strip():
            return {"code": "NOUN_AUTHORED_CLAIM_SOURCE_CHANGED"}
        reason = "Reviewed complete LU definition: " + definition.strip()
        whole = None
        basis = "LOCATED_LU_DEFINITION"
    elif contract is not None:
        if value.get("frame_id") != contract.frame_id:
            return {"code": "NOUN_FRAME_ID_MISMATCH"}
        if not value.get("frame_definition"):
            return {"code": "NOUN_FRAME_DEFINITION_UNAVAILABLE"}
        head, target, reason, whole = contract.head, contract.target, contract.reason, contract.whole
        basis = "REVIEWED_NOMINAL_FRAME_TARGET"
    else:
        return {"code": "NO_NOUN_HEAD_RULE"}
    targets = [fe for fe in value.get("frame_elements", []) if fe.get("name") == target]
    if len(targets) != 1 or not targets[0].get("definition"):
        return {"code": "NOUN_TARGET_DEFINITION_UNAVAILABLE"}
    target_fe = targets[0]
    if not lu_claim and contract is not None:
        if target_fe.get("ID") != contract.target_id:
            return {"code": "NOUN_TARGET_ID_MISMATCH"}
        if contract.required_type and not any(
            t.get("name") == contract.required_type for t in target_fe.get("semantic_types", [])
        ):
            return {"code": "NOUN_TARGET_TYPE_UNCONFIRMED"}
    denotations = {e["frame_element"] for e in value.get("target_role_evidence", []) if e.get("kind") == "DEN_VALENCE"}
    binding_scope = {
        "code": "CORPUS_TARGET_BINDINGS_RETAINED" if denotations else "NO_CORPUS_DEN_BINDING",
        "denoted_roles": sorted(denotations),
        "lexical_target_role": target,
        "writes_cells": False,
    }
    relations = []
    if whole:
        wholes = [fe for fe in value.get("frame_elements", []) if fe.get("name") == whole]
        if len(wholes) != 1:
            return {"code": "NOUN_WHOLE_ARGUMENT_UNAVAILABLE"}
        relations.append(
            {
                "relation": "PART_OF",
                "target_role": target,
                "whole_role": whole,
                "whole_semantic_types": wholes[0].get("semantic_types", []),
                "whole_record_id": wholes[0]["record_id"],
                "binding": "UNBOUND_ARGUMENT",
                "writes_whole_head": False,
            }
        )
    return {
        "code": "LOCATED_NOUN_HEAD",
        "head": head,
        "target_role": target,
        "target_record_id": target_fe["record_id"],
        "reason": reason,
        "claim_basis": basis,
        "relations": relations,
        "binding_scope": binding_scope,
        "definition_sha256": hashlib.sha256(value.get("definition", "").encode()).hexdigest(),
    }


def _noun_record(word: str, reading_id: str, record: dict, claim: dict, premises: list[str], c: Construction) -> dict:
    return {
        "word": word,
        "reading_id": reading_id,
        "code": c.state.code if claim["code"] == "LOCATED_NOUN_HEAD" else "UNRESOLVED_NOUN_HEAD",
        "source_scope": "FRAMENET_NOUN_TARGET",
        "production_eligible": False,
        "premise_record_ids": premises,
        "annotation_origin": {"lu_id": record["values"].get("lu_id"), "frame": record["values"].get("frame")},
        "head_claim": claim,
        "relations": claim.get("relations", []),
        "projection_convention": "SOURCED_GSE_PROJECTION_CONVENTION",
        "symbolic_before": c.initial.to_json(),
        "after_selection": c.state.to_json(),
        "model_calls": c.calls,
        "decisions": c.decisions,
        "candidate_vector": c.candidate,
        "unmapped": [] if claim["code"] == "LOCATED_NOUN_HEAD" else [{"code": claim["code"]}],
        "coverage_gap": "Only the located head is projected; no automatic family inheritance, head zeros or mask closure.",
    }


def noun_readings(
    word: str,
    native: dict,
    rulebook: dict,
    selector: OllamaSelector | None = None,
    tail_tasks: list[dict] | None = None,
    exceptions: tuple = (),
) -> list[dict]:
    """One noun LU, one reading; unknown head alternatives are never discarded."""
    if not isinstance(word, str) or not word_key(word):
        raise ValueError("INVALID_NOUN_WORD")
    if not isinstance(native, dict) or not isinstance(native.get("framenet", {}), dict):
        raise ValueError("INVALID_NATIVE_NOUN_SOURCE")
    records = native.get("framenet", {}).get("records", [])
    if not isinstance(records, list):
        raise ValueError("INVALID_NATIVE_NOUN_RECORDS")
    result = []
    for record in records:
        status = noun_record_status(record)
        if status != "VALID_NATIVE_NOUN_RECORD":
            raise ValueError(status)
        if record["values"]["pos"].casefold() not in {"n", "noun"}:
            continue
        reading_id = f"{word}:NOUN:framenet-lu-{record['values'].get('lu_id', record['record_id'])}"
        claim = noun_head_claim(record)
        premises = sorted(set([record["record_id"], *record["values"].get("source_record_ids", [])]))
        laws, facts = [], []
        if claim["code"] == "LOCATED_NOUN_HEAD":
            premises.append(claim["target_record_id"])
            facts = [("own_role", "source_bound_noun_head"), ("noun_head", claim["head"])]
            rule_id = f"FN_NOUN_HEAD:{record['values']['frame']}:{claim['head']}"
            laws.append(
                Law(
                    rule_id,
                    (claim["head"],),
                    ((Cell.PLUS,),),
                    (("noun_head", claim["head"]),),
                    claim["reason"],
                    "CONDITIONAL",
                )
            )
            if claim["head"] != "KIND":
                laws.append(
                    Law(
                        rule_id + ":NOT_CATEGORY",
                        ("KIND",),
                        ((Cell.ZERO,),),
                        (("noun_head", claim["head"]),),
                        "F007/F144: this located reading denotes the entity, person, collective, body or part, not a category.",
                        "CONDITIONAL",
                    )
                )
        seed = ReadingSeed(
            word=word,
            reading_id=reading_id,
            observations=tuple(Observation(reading_id, "framenet", "+".join(premises), f, v, True) for f, v in facts),
            laws=laws,
            layout=partial(_noun_record, word, reading_id, record, claim, premises),
            exportable=False,
            exceptions=exceptions,
            context={"selected_types": {"pos": "NOUN", "frame": record["values"].get("frame"), "head_claim": claim}},
        )
        if tail_tasks is not None:
            seed = attach_tail(seed, tail_tasks)
        result.append(construct_reading(seed, rulebook, selector))
    return result
