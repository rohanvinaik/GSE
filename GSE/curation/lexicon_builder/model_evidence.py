"""Pure typed views of native evidence for bounded model questions.

The full request remains the replay authority. This view neither deduces signs
nor classifies omitted information as irrelevant. Selection is by source schema,
never by score, requested bank, first sense, or a model context-size cutoff.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from typing import Any

from .foundation import BANKS

FORMAT = "gse.model-evidence/5"
CANDIDATE_LINKS_FORMAT = "gse.model-candidate-links/1"
_COMMON = frozenset({"lemma", "word", "bank_relevance", "projection_candidates"})
_FIELDS = {
    "nsm_chart": _COMMON
    | {
        "entry_id",
        "unit_id",
        "pos",
        "definition",
        "definition_kind",
        "chart_heading",
        "forms",
        "frame_text",
        "source_reference",
        "chart_notes",
        "frames_are",
    },
    "websters1913": _COMMON
    | {
        "entry_id",
        "pos",
        "definition",
        "native_id",
        "native_pos",
        "native_entry_text",
        "source_url",
        "source_sha256",
        "retrieved_utc",
        "definition_index",
        "identity_scheme",
    },
    "wiktionary": _COMMON
    | {
        "entry_id",
        "pos",
        "definition",
        "native_id",
        "senseid_path",
        "identity_scheme",
        "record_sha256",
        "source_sha256",
        "source_line",
        "sense_index",
        "sense_count",
        "reference_semantics",
    },
    "gse_closed_class": _COMMON
    | {
        "entry_id",
        "pos",
        "definition",
        "catalog",
        "grammar_roles",
        "primitives",
        "grammatical_features",
        "native_encodings",
        "provenance",
        "cohort",
    },
    "wordnet_hierarchy": _COMMON
    | {
        "definition",
        "pos",
        "synset_name",
        "lemma_names",
        "lexname",
        "hypernym_paths",
        "taxonomy_proposals",
        "native_relations",
        "entry_id",
        "definition_identity",
        "context_only",
    },
    "sentiwordnet": _COMMON | {"pos", "pos_score", "neg_score", "obj_score", "synset_id"},
    "nrc_emotion": _COMMON | {"emotions"},
    "nrc_vad": _COMMON | {"valence", "arousal", "dominance", "native_version", "native_scale", "native_header"},
    "usas": _COMMON | {"pos", "semantic_tags"},
    "framenet": _COMMON | {"frame_id", "frame_name", "pos", "core_fes", "is_core_lu"},
    "verbnet": _COMMON
    | {
        "verb_class",
        "wordnet_sense_keys",
        "member_attributes",
        "thematic_roles",
        "native_record_id",
        "definition_links",
        "projection",
    },
    "propbank": _COMMON | {"roleset_id", "name", "roles", "role_mappings", "verbnet_classes", "native_attributes"},
    "concreteness": _COMMON | {"concreteness", "known_percent", "n_ratings"},
    "lancaster_sensorimotor": _COMMON
    | {
        "auditory",
        "gustatory",
        "haptic",
        "interoceptive",
        "olfactory",
        "visual",
        "foot_leg",
        "hand_arm",
        "head",
        "mouth",
        "torso",
        "max_perceptual",
        "max_action",
        "dominant_perceptual",
        "dominant_action",
        "raw_fields",
        "raw_extra_fields",
    },
}
_ENVELOPE = frozenset({"source", "record_id", "family", "scope", "entry_id", "candidate_entry_ids"})
_OMISSIONS = {
    ("websters1913", "source_html"): "SOURCE_MARKUP_NOT_INCLUDED_IN_DEFINITION_VIEW",
    ("wordnet_hierarchy", "native_records"): "DUPLICATED_NATIVE_RECORDS_NOT_INCLUDED",
    ("wordnet_hierarchy", "examples"): "USAGE_EXAMPLES_NOT_INCLUDED_IN_DEFINITION_VIEW",
    ("framenet", "frame_metadata"): "FRAME_METADATA_NOT_INCLUDED_IN_LEXICAL_UNIT_VIEW",
    ("propbank", "native_xml"): "XML_NOT_INCLUDED_IN_TYPED_ROLESET_VIEW",
}
_WIKTIONARY_FIELDS = {
    "native_sense": {
        "id",
        "senseid",
        "glosses",
        "raw_glosses",
        "tags",
        "raw_tags",
        "topics",
        "qualifier",
        "head_nr",
        "alt_of",
        "form_of",
        "links",
        "synonyms",
        "antonyms",
        "hypernyms",
        "hyponyms",
        "holonyms",
        "meronyms",
        "coordinate_terms",
        "related",
    },
    "record_context": {
        "word",
        "pos",
        "lang",
        "lang_code",
        "etymology_number",
        "etymology_text",
        "forms",
        "antonyms",
        "synonyms",
        "hypernyms",
        "hyponyms",
        "coordinate_terms",
        "related",
    },
}
_WIKTIONARY_OMISSIONS = {
    "examples": "USAGE_EXAMPLES_NOT_INCLUDED_IN_DEFINITION_VIEW",
    "attestations": "USAGE_EXAMPLES_NOT_INCLUDED_IN_DEFINITION_VIEW",
    "translations": "TRANSLATIONS_NOT_INCLUDED_IN_DEFINITION_VIEW",
    "categories": "EDITORIAL_CATEGORIES_NOT_INCLUDED_IN_DEFINITION_VIEW",
    "derived": "DICTIONARY_NAVIGATION_NOT_INCLUDED_IN_DEFINITION_VIEW",
    "descendants": "DICTIONARY_NAVIGATION_NOT_INCLUDED_IN_DEFINITION_VIEW",
    "wikipedia": "DICTIONARY_NAVIGATION_NOT_INCLUDED_IN_DEFINITION_VIEW",
    "wikidata": "DICTIONARY_NAVIGATION_NOT_INCLUDED_IN_DEFINITION_VIEW",
    "sounds": "PHONOLOGY_NOT_INCLUDED_IN_DEFINITION_VIEW",
    "hyphenations": "PHONOLOGY_NOT_INCLUDED_IN_DEFINITION_VIEW",
    "head_templates": "RENDERED_MARKUP_NOT_INCLUDED_IN_DEFINITION_VIEW",
    "etymology_templates": "RENDERED_MARKUP_NOT_INCLUDED_IN_DEFINITION_VIEW",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _json_copy(value: Any) -> Any:
    """Validate JSON without coercing numbers, absent cells, or empty strings."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) in (list, tuple):
        return [_json_copy(item) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: _json_copy(item) for key, item in value.items()}
    raise ValueError("INVALID_MODEL_EVIDENCE_JSON")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _path(parent: str, key: str) -> str:
    return parent + "/" + key.replace("~", "~0").replace("/", "~1")


def _omit(omitted: list[dict], path: str, reason: str) -> None:
    omitted.append({"field": path, "code": reason})


def _verbnet_context(value: Any, path: str, selected: list[str], omitted: list[dict]) -> list[dict]:
    """Keep all frame semantics and their class/frame position, without XML."""
    if not isinstance(value, list):
        raise ValueError("INVALID_MODEL_EVIDENCE_VERBNET_CONTEXT")
    result = []
    for index, level in enumerate(value):
        if not isinstance(level, dict):
            raise ValueError("INVALID_MODEL_EVIDENCE_VERBNET_CONTEXT")
        level_path = _path(path, str(index))
        compact = {}
        for key, item in sorted(level.items()):
            field = _path(level_path, key)
            if key == "class_id":
                if not isinstance(item, str):
                    raise ValueError("INVALID_MODEL_EVIDENCE_VERBNET_CLASS")
                compact[key] = item
                selected.append(field)
            elif key == "frames":
                if not isinstance(item, list) or any(not isinstance(frame, dict) for frame in item):
                    raise ValueError("INVALID_MODEL_EVIDENCE_VERBNET_FRAMES")
                compact[key] = []
                if not item:
                    selected.append(field)
                for frame_index, frame in enumerate(item):
                    frame_path = _path(field, str(frame_index))
                    compact_frame = {}
                    for frame_key, frame_value in sorted(frame.items()):
                        frame_field = _path(frame_path, frame_key)
                        if frame_key == "semantics":
                            if not isinstance(frame_value, list) or any(
                                not isinstance(predicate, dict) for predicate in frame_value
                            ):
                                raise ValueError("INVALID_MODEL_EVIDENCE_VERBNET_SEMANTICS")
                            compact_frame[frame_key] = frame_value
                            selected.append(frame_field)
                        else:
                            reason = (
                                "VERBNET_XML_NOT_INCLUDED_IN_TYPED_EVENT_VIEW"
                                if frame_key == "native"
                                else "UNKNOWN_FIELD_NOT_IN_MODEL_VIEW_SCHEMA"
                            )
                            _omit(omitted, frame_field, reason)
                    # Empty frames must survive: omission cannot fabricate all-frame agreement.
                    compact[key].append(compact_frame)
            else:
                reason = (
                    "NESTED_ROLE_TREE_NOT_INCLUDED_IN_TYPED_EVENT_VIEW"
                    if key == "thematic_roles"
                    else "UNKNOWN_FIELD_NOT_IN_MODEL_VIEW_SCHEMA"
                )
                _omit(omitted, field, reason)
        result.append(compact)
    if not value:
        selected.append(path)
    return result


def _native_reference_view(packet: dict, path: str, selected: list[str], omitted: list[dict]) -> dict:
    """Retain every explicit target and diagnostic, applying native field schema."""
    result = {}
    for key, value in sorted(packet.items()):
        field = _path(path, key)
        if key == "source_entry":
            result[key] = _features("wiktionary", value, field, selected, omitted)
        elif key in {"target_entries", "other_pos_entries"}:
            result[key] = [
                _features("wiktionary", item, _path(field, str(index)), selected, omitted)
                for index, item in enumerate(value)
            ]
            if not value:
                selected.append(field)
        else:
            result[key] = value
            selected.append(field)
    return result


def _features(source: str, features: dict, path: str, selected: list[str], omitted: list[dict]) -> dict:
    result = {}
    for key, value in sorted(features.items()):
        field = _path(path, key)
        if key in _FIELDS[source]:
            result[key] = value
            selected.append(field)
        elif source == "wiktionary" and key == "native_reference":
            result[key] = _native_reference_view(value, field, selected, omitted)
        elif source == "wiktionary" and key in _WIKTIONARY_FIELDS:
            if not isinstance(value, dict):
                raise ValueError("INVALID_MODEL_EVIDENCE_WIKTIONARY_NATIVE")
            result[key] = {}
            for native_key, native_value in sorted(value.items()):
                native_field = _path(field, native_key)
                if native_key in _WIKTIONARY_FIELDS[key]:
                    result[key][native_key] = native_value
                    selected.append(native_field)
                else:
                    reason = _WIKTIONARY_OMISSIONS.get(native_key, "UNKNOWN_FIELD_NOT_IN_MODEL_VIEW_SCHEMA")
                    _omit(omitted, native_field, reason)
            if not value:
                selected.append(field)
        elif source == "verbnet" and key == "native":
            if not isinstance(value, dict):
                raise ValueError("INVALID_MODEL_EVIDENCE_VERBNET_NATIVE")
            result[key] = _features(source, value, field, selected, omitted)
            if not value:
                selected.append(field)
        elif source == "verbnet" and key == "class_context":
            result[key] = _verbnet_context(value, field, selected, omitted)
        elif source == "framenet" and key == "native_lu":
            if not isinstance(value, dict):
                raise ValueError("INVALID_MODEL_EVIDENCE_FRAMENET_LU")
            result[key] = {}
            if not value:
                selected.append(field)
            for lu_key, lu_value in sorted(value.items()):
                lu_field = _path(field, lu_key)
                if lu_key in {"ID", "name", "POS", "definition"}:
                    result[key][lu_key] = lu_value
                    selected.append(lu_field)
                else:
                    _omit(omitted, lu_field, "NATIVE_LU_FIELD_NOT_INCLUDED_IN_COMPACT_DEFINITION_VIEW")
        else:
            _omit(omitted, field, _OMISSIONS.get((source, key), "UNKNOWN_FIELD_NOT_IN_MODEL_VIEW_SCHEMA"))
    return result


def _record(raw: Any) -> dict:
    if type(raw) is not dict:
        raise ValueError("INVALID_MODEL_EVIDENCE_RECORD")
    record = _json_copy(raw)
    for key in ("source", "record_id", "family", "scope"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ValueError("INVALID_MODEL_EVIDENCE_IDENTITY")
    if record.get("entry_id") is not None and (
        not isinstance(record["entry_id"], str) or not record["entry_id"].strip()
    ):
        raise ValueError("INVALID_MODEL_EVIDENCE_ENTRY_ID")
    if "candidate_entry_ids" in record and (
        not isinstance(record["candidate_entry_ids"], list)
        or any(not isinstance(item, str) or not item.strip() for item in record["candidate_entry_ids"])
    ):
        raise ValueError("INVALID_MODEL_EVIDENCE_CANDIDATE_IDS")
    if not isinstance(record.get("features"), dict):
        raise ValueError("INVALID_MODEL_EVIDENCE_FEATURES")
    if "native_reference" in record["features"]:
        from .evidence import native_reference_observation

        expected = native_reference_observation(record["features"]["native_reference"])
        if record != _json_copy(asdict(expected)):
            raise ValueError("NATIVE_REFERENCE_OBSERVATION_MISMATCH")
    if "definition_identity" in record["features"]:
        from .wordnet_identity import wordnet_identity_observation

        features = record["features"]
        root = {key: features.get(key) for key in ("entry_id", "lemma", "pos", "definition")}
        expected = wordnet_identity_observation(features["definition_identity"], root)
        if record != _json_copy(asdict(expected)):
            raise ValueError("WORDNET_IDENTITY_OBSERVATION_MISMATCH")
    return record


def evidence_view(observations: list[dict] | tuple[dict, ...], bank: str) -> dict:
    """Return an explicitly partial view, preserving source values and linkage.

    Unknown sources refuse with a named error. Unknown fields on known schemas
    are reported by escaped JSON-pointer path. Every retained record has a hash
    of its complete original JSON record; world associations have a count and a
    deterministic multiset digest. No omitted value means zero or irrelevance.
    The requested bank labels the question, and never filters cross-bank data.
    """
    if type(bank) is not str or bank not in BANKS:
        raise ValueError("INVALID_MODEL_EVIDENCE_BANK")
    if type(observations) not in (list, tuple):
        raise ValueError("INVALID_MODEL_EVIDENCE_OBSERVATIONS")
    records = []
    world_digests = []
    world_fields = set()
    for raw in observations:
        record = _record(raw)
        source = record["source"]
        if source == "conceptnet":
            world_digests.append(_sha256(record))
            world_fields.update(_path("", key) for key in record if key != "features")
            world_fields.update(_path("/features", key) for key in record["features"])
            continue
        if source not in _FIELDS:
            raise ValueError(f"UNKNOWN_MODEL_EVIDENCE_SOURCE:{source}")
        selected, omitted = [], []
        summary = {key: record[key] for key in sorted(_ENVELOPE & record.keys())}
        selected.extend(_path("", key) for key in summary)
        summary["features"] = _features(source, record["features"], "/features", selected, omitted)
        for key in sorted(record.keys() - _ENVELOPE - {"features"}):
            _omit(omitted, _path("", key), "UNKNOWN_FIELD_NOT_IN_MODEL_VIEW_SCHEMA")
        summary["selected_fields"] = sorted(selected)
        summary["omitted_fields"] = sorted(omitted, key=lambda item: item["field"])
        summary["full_record_sha256"] = _sha256(record)
        records.append(summary)
    excluded = []
    if world_digests:
        excluded.append(
            {
                "source": "conceptnet",
                "code": "WORLD_ASSOCIATION_NOT_LEXICAL_EVIDENCE",
                "record_count": len(world_digests),
                "full_records_sha256": _sha256(sorted(world_digests)),
                "digest_scheme": "SHA256_CANONICAL_JSON_SORTED_FULL_RECORD_SHA256",
                "selected_fields": [],
                "omitted_fields": sorted(world_fields),
            }
        )
    return {
        "format": FORMAT,
        "bank": bank,
        "code": "PARTIAL_TYPED_VIEW",
        "omission_semantics": "OMITTED_IS_NOT_ZERO",
        "selection": "SOURCE_SCHEMA_ALL_BANK_CONTEXT",
        "role_semantics": "ARGUMENT_ROLES_ARE_NOT_OWN_WORD_BANK_ASSIGNMENTS",
        "candidate_semantics": "PROJECTION_CANDIDATES_ARE_ASSOCIATION_NOT_ASSIGNMENTS",
        "reference_semantics": "ONE_HOP_NATIVE_REFERENCE_CONTEXT_NOT_IDENTITY_OR_BANK_TRANSFER",
        "record_count": len(observations),
        "records": records,
        "excluded_sources": excluded,
    }


def candidate_links_contract() -> dict:
    """Describe reversible wire sharing, without narrowing candidate identity."""
    return {
        "format": CANDIDATE_LINKS_FORMAT,
        "reference_field": "candidate_entry_ids_ref",
        "reference_target": "candidate_sets[reference].entry_ids",
        "expanded_field": "candidate_entry_ids",
        "interpretation": "DEREFERENCE_BEFORE_IDENTITY_OR_SCOPE_REASONING",
        "semantics": "EXACT_ORDER_AND_DUPLICATES_PRESERVED_NO_CANDIDATES_REMOVED",
        "unknown": "UNRESOLVED_CANDIDATE_LINK_IS_NOT_ZERO_OR_EXACT_IDENTITY",
        "integrity": "SHA256_CANONICAL_JSON_FULL_EXPANDED_VIEW_AND_EACH_SHARED_LIST",
    }


def _expanded_candidate_view(value: Any) -> dict:
    data = _json_copy(value)
    if type(data) is not dict or data.get("format") != FORMAT or type(data.get("records")) is not list:
        raise ValueError("INVALID_CANDIDATE_LINK_VIEW")
    for record in data["records"]:
        if type(record) is not dict or "candidate_entry_ids_ref" in record:
            raise ValueError("INVALID_CANDIDATE_LINK_RECORD")
        if "candidate_entry_ids" in record:
            ids = record["candidate_entry_ids"]
            if type(ids) is not list or any(type(item) is not str or not item.strip() for item in ids):
                raise ValueError("INVALID_CANDIDATE_LINK_IDS")
    return data


def compact_candidate_links(view: dict) -> dict:
    """Intern repeated candidate lists only when serialized wire bytes decrease.

    This boundary retains every candidate in original order, including repeated
    candidates. The expanded evidence view and the original bank request remain
    unchanged. Small or unrepeated lists keep their ordinary representation.
    """
    from collections import Counter

    data = _expanded_candidate_view(view)
    counts = Counter(
        _canonical(record["candidate_entry_ids"]) for record in data["records"] if "candidate_entry_ids" in record
    )
    pools, references = {}, {}
    for serialized, count in sorted(counts.items()):
        if count < 2:
            continue
        ids = json.loads(serialized)
        slot = f"c{len(pools)}"
        pool = {"entry_ids": ids, "sha256": _sha256(ids)}
        old_bytes = len(_canonical({"candidate_entry_ids": ids}).encode("utf-8"))
        ref_bytes = len(_canonical({"candidate_entry_ids_ref": slot}).encode("utf-8"))
        pool_bytes = len(_canonical({slot: pool}).encode("utf-8"))
        if count * (old_bytes - ref_bytes) > pool_bytes:
            pools[slot] = pool
            references[serialized] = slot
    if not pools:
        return data
    expanded_sha = _sha256(data)
    original_bytes = len(_canonical(data).encode("utf-8"))
    for record in data["records"]:
        if "candidate_entry_ids" in record:
            slot = references.get(_canonical(record["candidate_entry_ids"]))
            if slot is not None:
                del record["candidate_entry_ids"]
                record["candidate_entry_ids_ref"] = slot
    result = {
        "format": CANDIDATE_LINKS_FORMAT,
        "codebook": candidate_links_contract(),
        "expanded_view_sha256": expanded_sha,
        "candidate_sets": pools,
        "view": data,
    }
    if len(_canonical(result).encode("utf-8")) >= original_bytes:
        return _expanded_candidate_view(view)
    if restore_candidate_links(result) != _expanded_candidate_view(view):
        raise ValueError("CANDIDATE_LINK_ROUNDTRIP_MISMATCH")
    return result


def restore_candidate_links(value: dict) -> dict:
    """Restore full candidate lists and verify all content before returning it."""
    data = _json_copy(value)
    if type(data) is not dict:
        raise ValueError("INVALID_CANDIDATE_LINK_VIEW")
    if data.get("format") == FORMAT:
        return _expanded_candidate_view(data)
    required = {"format", "codebook", "expanded_view_sha256", "candidate_sets", "view"}
    if set(data) != required or data.get("format") != CANDIDATE_LINKS_FORMAT:
        raise ValueError("INVALID_CANDIDATE_LINK_ENCODING")
    if data["codebook"] != candidate_links_contract():
        raise ValueError("INVALID_CANDIDATE_LINK_CODEBOOK")
    pools, view = data["candidate_sets"], data["view"]
    if type(pools) is not dict or not pools or set(pools) != {f"c{index}" for index in range(len(pools))}:
        raise ValueError("INVALID_CANDIDATE_LINK_POOL")
    for pool in pools.values():
        if type(pool) is not dict or set(pool) != {"entry_ids", "sha256"}:
            raise ValueError("INVALID_CANDIDATE_LINK_POOL")
        ids = pool["entry_ids"]
        if type(ids) is not list or any(type(item) is not str or not item.strip() for item in ids):
            raise ValueError("INVALID_CANDIDATE_LINK_IDS")
        if pool["sha256"] != _sha256(ids):
            raise ValueError("CANDIDATE_LINK_POOL_HASH_MISMATCH")
    if type(view) is not dict or type(view.get("records")) is not list:
        raise ValueError("INVALID_CANDIDATE_LINK_VIEW")
    used = set()
    for record in view["records"]:
        if type(record) is not dict:
            raise ValueError("INVALID_CANDIDATE_LINK_RECORD")
        if "candidate_entry_ids_ref" not in record:
            continue
        slot = record.pop("candidate_entry_ids_ref")
        if type(slot) is not str or slot not in pools or "candidate_entry_ids" in record:
            raise ValueError("INVALID_CANDIDATE_LINK_REFERENCE")
        record["candidate_entry_ids"] = list(pools[slot]["entry_ids"])
        used.add(slot)
    if used != set(pools):
        raise ValueError("UNUSED_CANDIDATE_LINK_POOL")
    restored = _expanded_candidate_view(view)
    if data["expanded_view_sha256"] != _sha256(restored):
        raise ValueError("CANDIDATE_LINK_VIEW_HASH_MISMATCH")
    return restored
