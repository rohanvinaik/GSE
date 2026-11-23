"""Native-association diagnostics, never implicit lexical-law admission.

Discovery unions a word's native alternatives. These diagnostics keep that
same scope; they cannot transfer a participant property into a lexical cell,
select a reading, create a correction, or confirm the builder's own answer.
An explicit reviewed conditional law may be linked for investigation, but its
authority continues to come solely from the rulebook's admission contract.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from gse.lexicon_builder.core import law_admission_status
from gse.lexicon_builder.registry import RULE_FAMILIES, candidate_id

SCOPE = "WORD_ALTERNATIVE_UNION"
SOURCES = {"usas", "framenet", "verbnet", "emotion", "vad", "lancaster"}
SENSE_FIELDS = ("Auditory", "Gustatory", "Haptic", "Interoceptive", "Olfactory", "Visual")
EFFECTOR_FIELDS = ("Foot_leg", "Hand_arm", "Head", "Mouth", "Torso")


class CatalogError(ValueError):
    """The catalog failed as a whole; individual invalid entries remain visible."""

    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class ConditionalCatalog:
    records: tuple[dict, ...]
    path: str | None = None
    sha256: str | None = None
    entries: tuple[CatalogEntry, ...] = ()


@dataclass(frozen=True)
class CatalogEntry:
    candidate_id: str | None
    disposition: str
    antecedents: tuple[str, ...] = ()
    consequent: str | None = None
    lineage: str = "NOT_SPECIFIED"
    lexical_rule_id: object = None


def _feature(feature: object) -> tuple[str, str, str] | None:
    if not isinstance(feature, str):
        return None
    return _parsed_feature(feature)


@lru_cache(maxsize=16_384)
def _parsed_feature(feature: str) -> tuple[str, str, str] | None:
    source, separator, label = feature.partition(":")
    selector, equal, value = label.partition("=")
    if not separator or not equal or source not in SOURCES or not value:
        return None
    allowed = {
        "usas": {"pos", "category", "field", "alternative", "single_alternative"},
        "framenet": {"frame"},
        "verbnet": {"class", "frame_predicate", "argument_role", "argument_restriction"},
        "emotion": {
            "anger",
            "anticipation",
            "disgust",
            "fear",
            "joy",
            "sadness",
            "surprise",
            "trust",
            "positive",
            "negative",
        },
        "vad": {"valence_sign", "arousal_sign", "dominance_sign"},
        "lancaster": {"dominant_sense", "dominant_effector"},
    }
    if selector not in allowed[source]:
        return None
    if source == "usas" and selector == "pos" and "&" in value:
        pos, separator, category = value.partition("&category=")
        if not separator or not pos or not category:
            return None
    if source == "emotion" and value not in {"0", "1"}:
        return None
    if source == "vad" and value not in {"negative", "zero", "positive"}:
        return None
    return source, selector, value


def catalog_entry_status(record: object) -> str:
    """Classify catalog data without granting any ability to write a cell."""
    if not isinstance(record, dict):
        return "MALFORMED_CATALOG_ENTRY"
    if record.get("kind") != "NATIVE_ASSOCIATION" or record.get("may_write_lexical_cells") is not False:
        return "NONDIAGNOSTIC_CATALOG_ENTRY"
    relation = record.get("relation")
    if not isinstance(relation, dict):
        return "MALFORMED_NATIVE_RELATION"
    antecedents, consequent = relation.get("antecedents"), relation.get("consequent")
    if (
        not isinstance(antecedents, list)
        or not antecedents
        or any(_feature(f) is None for f in antecedents)
        or _feature(consequent) is None
    ):
        return "UNSUPPORTED_NATIVE_FEATURE"
    if len(set(antecedents)) != len(antecedents) or consequent in antecedents:
        return "DEGENERATE_NATIVE_RELATION"
    if record.get("rule_id") != candidate_id(relation):
        return "CATALOG_IDENTITY_MISMATCH"
    if any(key in record for key in ("gold", "gold_explication", "builder_vector", "model_answer")):
        return "PROHIBITED_DIAGNOSTIC_INPUT"
    for key in ("discovery_sha256", "discovery_script_sha256"):
        if not isinstance(record.get(key), str) or re.fullmatch(r"[0-9a-f]{64}", record[key]) is None:
            return "UNPINNED_NATIVE_RELATION"
    if not isinstance(record.get("source_snapshots"), list) or not record["source_snapshots"]:
        return "UNPINNED_NATIVE_RELATION"
    lifecycle = record.get("lifecycle")
    if lifecycle is not None and not isinstance(lifecycle, str):
        return "UNKNOWN_CATALOG_LIFECYCLE"
    if lifecycle in {"RETIRED", "REJECTED"}:
        return "RETIRED_NATIVE_ASSOCIATION"
    if lifecycle not in {None, "ACTIVE"}:
        return "UNKNOWN_CATALOG_LIFECYCLE"
    return "DIAGNOSTIC_ONLY"


def compile_catalog(records: list, *, path: str | None = None, sha256: str | None = None) -> ConditionalCatalog:
    """Keep invalid entries as named dispositions; never silently drop one."""
    if not isinstance(records, list):
        raise CatalogError("MALFORMED_CATALOG", "expected a list of native relation records")
    seen = set()
    for record in records:
        rule_id = record.get("rule_id") if isinstance(record, dict) else None
        if isinstance(rule_id, str):
            if rule_id in seen:
                raise CatalogError("DUPLICATE_CATALOG_ID", rule_id)
            seen.add(rule_id)
    records = deepcopy(records)
    entries = []
    for record in records:
        disposition = catalog_entry_status(record)
        valid = disposition == "DIAGNOSTIC_ONLY"
        relation = record["relation"] if valid else {}
        entries.append(
            CatalogEntry(
                record.get("rule_id") if isinstance(record, dict) and isinstance(record.get("rule_id"), str) else None,
                disposition,
                tuple(relation.get("antecedents", [])),
                relation.get("consequent"),
                relation.get("lineage", "NOT_SPECIFIED"),
                record.get("lexical_rule_id") if isinstance(record, dict) else None,
            )
        )
    return ConditionalCatalog(tuple(records), path, sha256, tuple(entries))


def load_catalog(path: Path) -> ConditionalCatalog:
    """Load the existing content-addressed JSONL discovery catalog."""
    payload = path.read_bytes()
    try:
        records = [json.loads(line) for line in payload.decode().splitlines() if line.strip()]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CatalogError("MALFORMED_CATALOG_JSON", str(error)) from error
    return compile_catalog(records, path=str(path), sha256=hashlib.sha256(payload).hexdigest())


def catalog_report(catalog: ConditionalCatalog, rulebook: dict | None = None) -> dict:
    """A conditional link describes provenance, never a new admission path."""
    laws = {r["rule_id"]: r for family in RULE_FAMILIES for r in (rulebook or {}).get(family, [])}
    dispositions = []
    for entry in catalog.entries:
        code = entry.disposition
        linked = entry.lexical_rule_id
        if code == "DIAGNOSTIC_ONLY" and linked is not None:
            law = laws.get(linked) if isinstance(linked, str) else None
            code = (
                "LEXICAL_RULE_LINKED"
                if law is not None and law_admission_status(law) == "ADMITTED" and law.get("tier") == "CONDITIONAL"
                else "LEXICAL_RULE_LINK_UNADMITTED"
            )
        dispositions.append({"candidate_id": entry.candidate_id, "code": code, "lexical_rule_id": linked})
    return {
        "schema": "GSE_NATIVE_ASSOCIATION_DIAGNOSTICS_V1",
        "scope": SCOPE,
        "path": catalog.path,
        "sha256": catalog.sha256,
        "may_write_lexical_cells": False,
        "disposition_counts": dict(Counter(r["code"] for r in dispositions)),
        "records": dispositions,
    }


def _usas_features(values: dict, selector: str) -> set[str] | None:
    alternatives, pos = values.get("alternatives"), values.get("pos")
    if selector == "pos" and isinstance(pos, str) and "alternatives" not in values:
        return {pos}
    if (
        not isinstance(alternatives, list)
        or any(not isinstance(a, str) for a in alternatives)
        or not isinstance(pos, str)
    ):
        return None
    if selector in {"alternative", "single_alternative"}:
        return set(alternatives)
    categories = set()
    for alternative in alternatives:
        for component in alternative.split("/"):
            match = re.match(r"[A-Z]+\d+(?:\.\d+)*[+-]*", component)
            if match:
                categories.add(match.group())
    if selector == "category":
        return categories
    if selector == "field":
        return {c[0] for c in categories}
    return {pos, *(pos + "&category=" + c for c in categories)}


def _restriction_labels(nodes: object) -> set[str] | None:
    if not isinstance(nodes, list):
        return None
    labels = set()
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("attributes"), dict):
            return None
        if node.get("tag") == "SELRESTR":
            sign, kind = node["attributes"].get("Value"), node["attributes"].get("type")
            if not isinstance(sign, str) or not isinstance(kind, str):
                return None
            labels.add(sign + kind)
        nested = _restriction_labels(node.get("children", []))
        if nested is None:
            return None
        labels.update(nested)
    return labels


def _verbnet_features(values: dict, selector: str) -> set[str] | None:
    frames = values.get("frames")
    if not isinstance(frames, list) or any(not isinstance(frame, dict) for frame in frames):
        return None
    if selector == "class":
        labels = {values["class"]} if isinstance(values.get("class"), str) else set()
        labels.update(frame["class"] for frame in frames if isinstance(frame.get("class"), str))
        ancestry = values.get("class_ancestry")
        if isinstance(ancestry, list) and all(isinstance(c, str) for c in ancestry):
            labels.update(ancestry)
        # The adapter may not carry an ancestor defining no frames. A missing
        # ancestor class is therefore unobserved, never a counterexample.
        return labels
    if selector == "frame_predicate":
        labels = set()
        for frame in frames:
            predicates = frame.get("predicates")
            if not isinstance(predicates, list):
                return None
            for predicate in predicates:
                if not isinstance(predicate, dict) or not isinstance(predicate.get("predicate"), dict):
                    return None
                native = predicate["predicate"]
                if not isinstance(native.get("value"), str) or (
                    native.get("bool") is not None and native.get("bool") != "!"
                ):
                    return None
                labels.add((native.get("bool") or "") + native["value"])
        return labels
    roles = values.get("effective_role_restrictions")
    if not isinstance(roles, list):
        return None
    labels = set()
    for role in roles:
        if not isinstance(role, dict) or not isinstance(role.get("role"), str):
            return None
        if selector == "argument_role":
            labels.add(role["role"])
        else:
            restrictions = _restriction_labels(role.get("restrictions"))
            if restrictions is None:
                return None
            labels.update(role["role"] + ":" + r for r in restrictions)
    return labels


def _native_number(value: object, lower: int, upper: int) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        numeric = float(value)
    except OverflowError:
        return None
    return numeric if math.isfinite(numeric) and lower <= numeric <= upper else None


def _record_features(source: str, selector: str, values: dict) -> set[str] | None:
    if source == "usas":
        return _usas_features(values, selector)
    if source == "framenet":
        return {values["frame"]} if isinstance(values.get("frame"), str) else None
    if source == "verbnet":
        return _verbnet_features(values, selector)
    if source == "emotion":
        value = values.get(selector)
        return {str(value)} if type(value) is int and value in {0, 1} else None
    if source == "vad":
        value = _native_number(values.get(selector.removesuffix("_sign")), -1, 1)
        if value is None:
            return None
        return {"positive" if value > 0 else "negative" if value < 0 else "zero"}
    fields = SENSE_FIELDS if selector == "dominant_sense" else EFFECTOR_FIELDS
    scores: dict[str, float] = {}
    for name in fields:
        score = _native_number(values.get(name + ".mean"), 0, 5)
        if score is None:
            return None
        scores[name] = score
    maximum = max(scores.values())
    winners = [name for name, score in scores.items() if score == maximum]
    return {winners[0] if len(winners) == 1 else "TIE"}


def native_feature_evidence(native: object, feature: str) -> dict:
    """Presence requires a native witness; absence requires complete observations."""
    parsed = _feature(feature)
    result = {"feature": feature, "source": parsed[0] if parsed else None, "record_ids": []}
    if parsed is None:
        return {**result, "code": "UNSUPPORTED_NATIVE_FEATURE"}
    source, selector, wanted = parsed
    channel = native.get(source) if isinstance(native, dict) else None
    if not isinstance(channel, dict) or channel.get("status") == "UNAVAILABLE":
        return {**result, "code": "SOURCE_UNAVAILABLE"}
    records = channel.get("records")
    if not isinstance(records, list):
        return {**result, "code": "MALFORMED_NATIVE_RECORD"}
    status = channel.get("status")
    if status == "NO_RECORD":
        return {**result, "code": "SOURCE_STATUS_CONFLICT" if records else "SOURCE_NO_RECORD"}
    if status != "OBSERVED":
        return {**result, "code": "SOURCE_UNOBSERVED"}
    if not records:
        return {**result, "code": "SOURCE_STATUS_CONFLICT"}
    present, examined, unknown, alternatives = [], [], False, set()
    for record in records:
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("record_id"), str)
            or not record["record_id"]
            or not isinstance(record.get("values"), dict)
        ):
            return {**result, "code": "MALFORMED_NATIVE_RECORD"}
        labels = _record_features(source, selector, record["values"])
        if labels is None:
            unknown = True
            continue
        examined.append(record["record_id"])
        alternatives.update(labels)
        if wanted in labels:
            present.append(record["record_id"])
        if source == "verbnet" and selector == "class" and "class_ancestry" not in record["values"]:
            unknown = True
    if source == "usas" and selector == "single_alternative":
        present = examined if alternatives == {wanted} and not unknown else []
    if present:
        return {**result, "record_ids": sorted(set(present)), "code": "PRESENT"}
    return {**result, "record_ids": sorted(set(examined)), "code": "SOURCE_UNOBSERVED" if unknown else "ABSENT"}


def evaluate_catalog(native: dict, catalog: ConditionalCatalog) -> dict:
    """Compare native facts with native associations; return no lexical answers."""
    evidence = {}
    results = []
    for entry in catalog.entries:
        disposition = entry.disposition
        if disposition != "DIAGNOSTIC_ONLY":
            results.append({"candidate_id": entry.candidate_id, "code": disposition})
            continue
        assert entry.consequent is not None
        for feature in (*entry.antecedents, entry.consequent):
            if feature not in evidence:
                evidence[feature] = native_feature_evidence(native, feature)
        antecedents = [evidence[f] for f in entry.antecedents]
        consequent = evidence[entry.consequent]
        missing = next((a for a in antecedents if a["code"] not in {"PRESENT", "ABSENT"}), None)
        blocked_role = None
        if any(a["code"] == "ABSENT" for a in antecedents):
            code = "PREMISE_NOT_MET"
        elif missing is not None:
            code, blocked_role = missing["code"], "ANTECEDENT"
        elif consequent["code"] == "PRESENT":
            code = "CORROBORATED_NATIVE_ASSOCIATION"
        elif consequent["code"] == "ABSENT":
            code = "CONTRADICTED_NATIVE_ASSOCIATION"
        else:
            code, blocked_role = consequent["code"], "CONSEQUENT"
        results.append(
            {
                "candidate_id": entry.candidate_id,
                "code": code,
                "blocked_role": blocked_role,
                "antecedents": antecedents,
                "consequent": consequent,
                "lineage": entry.lineage,
            }
        )
    return {
        "schema": "GSE_NATIVE_ASSOCIATION_DIAGNOSTICS_V1",
        "scope": SCOPE,
        "may_write_lexical_cells": False,
        "catalog_sha256": catalog.sha256,
        "code_counts": dict(Counter(r["code"] for r in results)),
        "results": results,
    }
