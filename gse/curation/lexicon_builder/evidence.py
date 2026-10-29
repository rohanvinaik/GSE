"""Preserve native source evidence before definition-specific lexical projection.

The supplied adapters must already be loaded. This module never loads a corpus,
downloads data, calls a model, or writes a database. WordNet definitions provide
the initial dictionary identity spine; class memberships and word ratings do not
create definitions and do not become assignments through voting.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import sqlite3
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass, replace
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import quote

from gse.curation.external_sources.source_scope import SOURCE_PRIMITIVE_SCOPE
from gse.curation.external_sources.wordnet_hierarchy import (
    LEXNAME_TO_PRIMITIVE,
    ROOT_CONCEPT_PRIMITIVES,
)
from gse.primitives_v2 import PRIMITIVE_REGISTRY, get_canonical_pole

from .engine import Assertion
from .foundation import BANKS


@dataclass(frozen=True)
class Definition:
    entry_id: str
    lemma: str
    pos: str
    definition: str
    source_ids: tuple[str, ...] = ()

    def __post_init__(self):
        for name in ("entry_id", "lemma", "pos"):
            _require_string(getattr(self, name), f"INVALID_DEFINITION_{name.upper()}")
        if not isinstance(self.definition, str):
            raise ValueError("INVALID_DEFINITION_TEXT")
        _require_ids(self.source_ids, "INVALID_DEFINITION_SOURCE_IDS")


@dataclass(frozen=True)
class Observation:
    entry_id: str | None
    source: str
    record_id: str
    family: str
    features: dict
    scope: str
    candidate_entry_ids: tuple[str, ...] = ()

    def __post_init__(self):
        if self.entry_id is not None:
            _require_string(self.entry_id, "INVALID_OBSERVATION_ENTRY_ID")
        for name in ("source", "record_id", "family", "scope"):
            _require_string(getattr(self, name), f"INVALID_OBSERVATION_{name.upper()}")
        _require_ids(self.candidate_entry_ids, "INVALID_OBSERVATION_CANDIDATE_IDS")
        if not isinstance(self.features, dict):
            raise ValueError("INVALID_OBSERVATION_FEATURES")
        _require_json(self.features)
        if "bank_relevance" in self.features:
            from .relevance import validate_bank_relevance

            validate_bank_relevance(self.features["bank_relevance"])


def _require_string(value, code: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(code)


def _require_ids(value, code: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(code)
    for item in value:
        _require_string(item, code)


def _require_json(value) -> None:
    """Validate actual JSON structure without replacing absent or invalid data."""
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("INVALID_OBSERVATION_FEATURES")
            _require_json(item)
        return
    if isinstance(value, list):
        for item in value:
            _require_json(item)
        return
    raise ValueError("INVALID_OBSERVATION_FEATURES")


@dataclass(frozen=True)
class EvidenceBundle:
    definitions: tuple[Definition, ...]
    observations: tuple[Observation, ...]
    assertions: tuple[Assertion, ...]
    unresolved: tuple[dict, ...]


_FAMILIES = {
    "wordnet_hierarchy": "wordnet",
    "sentiwordnet": "wordnet",
    "verbnet": "verb_structure",
    "framenet": "verb_structure",
    "propbank": "verb_structure",
    "conceptnet": "topical",
    "usas": "topical",
}
_ASSOCIATION_SOURCES = frozenset({"sentiwordnet", "nrc_emotion", "nrc_vad", "concreteness", "lancaster_sensorimotor"})
_POS = {"n": "noun", "v": "verb", "a": "adj", "s": "adj", "r": "adv", "adjective": "adj", "adverb": "adv"}


def _json_value(value):
    """Copy supported native values without truncation or silent coercion."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("NONFINITE_NATIVE_FEATURE")
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("NONSTRING_NATIVE_FEATURE_KEY")
        return {key: _json_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_json_value(item) for item in value), key=_canonical_json)
    raise ValueError("UNSUPPORTED_NATIVE_FEATURE_TYPE")


def _canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _native_features(record) -> dict:
    if is_dataclass(record) and not isinstance(record, type):
        raw = asdict(record)
    elif isinstance(record, Mapping):
        raw = record
    elif hasattr(record, "__dict__"):
        raw = vars(record)
    else:
        raise ValueError("UNSUPPORTED_NATIVE_RECORD")
    return _json_value(raw)


def _record_id(source: str, word: str, features: dict) -> str:
    """Content identity, stable across adapter/dictionary iteration order."""
    digest = hashlib.sha256(_canonical_json(features).encode()).hexdigest()
    return f"{source}:{quote(word, safe='')}:{digest}"


def _wordnet_id(word: str, synset_name: str) -> str:
    return f"wordnet:{quote(word, safe='')}:{quote(synset_name, safe='')}"


def _pos(value) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.lower()
    return _POS.get(normalized, normalized)


def _native_records(source: str, parser: object, word: str) -> list:
    """Read already-present records; never call adapters that can auto-load."""
    entries = getattr(parser, "entries", {})
    if isinstance(entries, Mapping) and word in entries:
        records = entries[word]
        return list(records) if isinstance(records, (list, tuple)) else [records]
    connection = getattr(parser, "conn", None)
    if connection is None:
        return []
    if source == "conceptnet":
        cursor = connection.execute("SELECT * FROM edges WHERE start_word=? OR end_word=?", (word, word))
    elif source == "wiktionary":
        cursor = connection.execute("SELECT * FROM entries WHERE word=?", (word,))
    else:
        return []
    columns = tuple(column[0] for column in cursor.description)
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _vocabulary(parsers: dict[str, object], words: tuple[str, ...] | None) -> tuple[str, ...]:
    if words is not None:
        if not isinstance(words, tuple) or any(not isinstance(word, str) or not word.strip() for word in words):
            raise ValueError("INVALID_WORDS")
        return tuple(sorted({word.strip().lower().replace("_", " ") for word in words}))
    vocabulary = set()
    for source, parser in parsers.items():
        entries = getattr(parser, "entries", {})
        if isinstance(entries, Mapping):
            vocabulary.update(word for word in entries if isinstance(word, str) and word)
        connection = getattr(parser, "conn", None)
        if source == "conceptnet" and connection is not None:
            vocabulary.update(
                row[0] for row in connection.execute("SELECT start_word FROM edges UNION SELECT end_word FROM edges")
            )
        elif source == "wiktionary" and connection is not None:
            vocabulary.update(row[0] for row in connection.execute("SELECT DISTINCT word FROM entries"))
    return tuple(
        sorted(
            {word.strip().lower().replace("_", " ") for word in vocabulary if isinstance(word, str) and word.strip()}
        )
    )


def _taxonomy_proposals(lexname: str, paths: list[list[str]]) -> list[dict]:
    """Keep every legacy mapping visible as a proposal with its exact origin."""
    origins = [("lexname", lexname, LEXNAME_TO_PRIMITIVE.get(lexname, {}))]
    origins.extend(
        ("is_a", name, ROOT_CONCEPT_PRIMITIVES.get(name, {}))
        for name in sorted({name for path in paths for name in path})
    )
    return [
        {"kind": kind, "origin": origin, "primitive": primitive, "value": value, "status": "CANDIDATE"}
        for kind, origin, mapping in origins
        for primitive, value in sorted(mapping.items())
    ]


def _taxonomy_assertions(
    record_id: str, projected: dict[str, int], source: str = "wordnet_hierarchy", family: str = "wordnet"
) -> tuple[Assertion, ...]:
    """Apply source competence and canonical coordinates to adapter projection."""
    permitted = SOURCE_PRIMITIVE_SCOPE.get(source)
    if permitted is None:
        return ()
    assignments = set()
    for primitive, value in projected.items():
        info = PRIMITIVE_REGISTRY.get(primitive)
        if primitive not in permitted or info is None or primitive == "NUMBER":
            continue
        if info.is_hierarchy_base or info.is_hierarchy_marker:
            continue
        if type(value) is not int or value not in (-1, 0, 1):
            raise ValueError("INVALID_TAXONOMY_VALUE")
        bank, orientation = get_canonical_pole(primitive)
        assignments.add((bank, value * orientation))
    assertions = tuple(
        Assertion(bank, value, source, record_id, family, "lexical") for bank, value in sorted(assignments)
    )
    for assertion in assertions:
        validate_assertion_competence(assertion)
    return assertions


def validate_assertion_competence(assertion: Assertion) -> None:
    """Enforce native source competence for collected and imported assertions.

    Source scopes name both primitive poles, while assertions use canonical
    banks: BAD therefore permits GOOD with a negative sign, never a separate
    BAD coordinate. Unknown authored dictionary sources have no native scope
    restriction here; their identity, lexical typing and closed-basis checks
    remain the caller's evidence/engine contract.
    """
    if not isinstance(assertion, Assertion):
        raise ValueError("INVALID_ASSERTION")
    permitted = SOURCE_PRIMITIVE_SCOPE.get(assertion.source)
    if permitted is None:
        return
    allowed = {
        bank
        for primitive in permitted
        if primitive in PRIMITIVE_REGISTRY
        for bank, _ in (get_canonical_pole(primitive),)
        if bank in BANKS
    }
    if assertion.bank not in allowed:
        raise ValueError("ASSERTION_OUTSIDE_SOURCE_SCOPE")


def _wordnet_definitions(parser: object | None, words: tuple[str, ...]):
    definitions: dict[str, Definition] = {}
    observations: dict[str, Observation] = {}
    assertions: list[Assertion] = []
    unresolved: list[dict] = []
    wordnet = getattr(parser, "_wn", None)
    if wordnet is None:
        return definitions, observations, assertions, unresolved
    for word in words:
        try:
            synsets = wordnet.synsets(word.replace(" ", "_"))
        except LookupError:
            unresolved.append({"code": "WORDNET_UNAVAILABLE", "lemma": word, "source": "wordnet_hierarchy"})
            continue
        for synset in synsets:
            synset_name = synset.name()
            record_id = _wordnet_id(word, synset_name)
            if record_id in definitions:
                continue
            definition = synset.definition()
            if not isinstance(definition, str) or not definition.strip():
                unresolved.append({"code": "MISSING_DEFINITION", "lemma": word, "record_id": record_id})
                continue
            pos = _pos(synset.pos())
            if pos is None:
                unresolved.append({"code": "MISSING_POS", "lemma": word, "record_id": record_id})
                continue
            paths = [[ancestor.name() for ancestor in path] for path in synset.hypernym_paths()]
            features = {
                "lemma": word,
                "synset_name": synset_name,
                "pos": pos,
                "definition": definition,
                "lexname": synset.lexname(),
                "hypernym_paths": paths,
            }
            features["taxonomy_proposals"] = _taxonomy_proposals(features["lexname"], paths)
            if callable(getattr(synset, "examples", None)):
                features["examples"] = synset.examples()
            if callable(getattr(synset, "lemma_names", None)):
                features["lemma_names"] = synset.lemma_names()
            native = _native_records("wordnet_hierarchy", parser, word)
            matching = [record for record in native if getattr(record, "synset_name", None) == synset_name]
            features["native_records"] = [_native_features(record) for record in matching]
            features = _json_value(features)
            definitions[record_id] = Definition(record_id, word, pos, definition, (record_id,))
            observations[record_id] = Observation(
                record_id, "wordnet_hierarchy", record_id, "wordnet", features, "lexical", (record_id,)
            )
            project = getattr(parser, "to_primitives_for_definition", None)
            if callable(project):
                assertions.extend(_taxonomy_assertions(record_id, project(synset_name)))
            else:
                unresolved.append({"code": "DEFINITION_PROJECTION_UNAVAILABLE", "record_id": record_id})
    return definitions, observations, assertions, unresolved


def _scope(source: str) -> str:
    if source not in SOURCE_PRIMITIVE_SCOPE:
        return "unscoped"
    if source in _ASSOCIATION_SOURCES:
        return "association"
    if source in {"verbnet", "framenet", "propbank"}:
        return "argument_structure"
    return "source_structure"


def _verbnet_links(parser, native, features, native_record_id, word, by_synset, wordnet):
    """Keep memberships intact and create separate exact-definition witnesses."""
    observations = []
    assertions = []
    diagnostics = []
    linked = {}
    for link in parser.definition_links(native, wordnet):
        entry_id = by_synset.get((word, link.get("synset_name"))) if link["code"] == "LINKED" else None
        if entry_id is None:
            diagnostics.append(
                {
                    "code": "UNRESOLVED_SOURCE_LINK",
                    "source": "verbnet",
                    "record_id": native_record_id,
                    "lemma": word,
                    "reason": "DEFINITION_NOT_IN_SPINE" if link["code"] == "LINKED" else link["code"],
                    "native_link": link,
                }
            )
        else:
            linked.setdefault(entry_id, []).append(link)
    projected = parser.to_primitives_for_entry(native) if linked else {}
    for entry_id, links in sorted(linked.items()):
        linked_features = {
            "native_record_id": native_record_id,
            "native": features,
            "definition_links": sorted(links, key=_canonical_json),
            "projection": projected,
        }
        record_id = _record_id("verbnet", word, linked_features)
        observations.append(
            Observation(entry_id, "verbnet", record_id, "verb_structure", linked_features, "lexical", (entry_id,))
        )
        assertions.extend(_taxonomy_assertions(record_id, projected, "verbnet", "verb_structure"))
    return observations, assertions, diagnostics


def collect_evidence(parsers: dict[str, object], words: tuple[str, ...] | None = None) -> EvidenceBundle:
    """Collect complete native observations and warranted per-definition facts.

    Only an explicit shared synset identifier links a non-spine observation.
    Even a lone candidate is not evidence that an unspecialized rating belongs
    to that definition. Unsupported source scopes and unavailable linkage are
    explicit diagnostics, not zero-valued assignments.
    """
    if not isinstance(parsers, dict) or any(not isinstance(name, str) or not name for name in parsers):
        raise ValueError("INVALID_PARSERS")
    unavailable = {name for name, parser in parsers.items() if getattr(parser, "_loaded", True) is False}
    loaded = {name: parser for name, parser in parsers.items() if name not in unavailable}
    vocabulary = _vocabulary(loaded, words)
    definitions, observations, assertions, unresolved = _wordnet_definitions(
        loaded.get("wordnet_hierarchy"), vocabulary
    )
    unresolved.extend({"code": "SOURCE_NOT_LOADED", "source": name} for name in sorted(unavailable))
    by_word: dict[str, list[Definition]] = {}
    by_synset: dict[tuple[str, str], str] = {}
    for definition in definitions.values():
        by_word.setdefault(definition.lemma, []).append(definition)
        features = observations[definition.entry_id].features
        by_synset[(definition.lemma, features["synset_name"])] = definition.entry_id
    for word in vocabulary:
        candidates = tuple(sorted(by_word.get(word, []), key=lambda definition: definition.entry_id))
        if not candidates:
            unresolved.append({"code": "NO_IDENTIFIED_DEFINITION", "lemma": word})
        for source, parser in sorted(loaded.items()):
            if source == "wordnet_hierarchy" and getattr(parser, "_wn", None) is not None:
                continue
            for native in _native_records(source, parser, word):
                try:
                    features = _native_features(native)
                except ValueError as error:
                    unresolved.append(
                        {"code": "MALFORMED_NATIVE_RECORD", "source": source, "lemma": word, "reason": str(error)}
                    )
                    continue
                features.setdefault("lemma", word)
                if source == "framenet":
                    metadata = getattr(parser, "_frame_cache", {}).get(features.get("frame_name"))
                    if metadata is not None:
                        features["frame_metadata"] = _json_value(metadata)
                record_id = _record_id(source, word, features)
                # Adapter-owned, typed record semantics may classify relevance.
                # Keep identity based on native data and preserve an explicit
                # existing annotation; a projection's output is not exhaustive
                # relevance. Missing/abstaining hooks leave every bank possible.
                relevance_hook = getattr(parser, "bank_relevance_for_entry", None)
                if "bank_relevance" not in features and callable(relevance_hook):
                    relevance = relevance_hook(native)
                    if relevance is not None:
                        features["bank_relevance"] = relevance
                native_pos = _pos(features.get("pos"))
                candidate_ids = tuple(d.entry_id for d in candidates if native_pos is None or native_pos == d.pos)
                synset_name = features.get("synset_name", features.get("synset_id"))
                entry_id = by_synset.get((word, synset_name)) if isinstance(synset_name, str) else None
                if entry_id is not None and entry_id not in candidate_ids:
                    entry_id = None
                scope = _scope(source)
                observations[record_id] = Observation(
                    entry_id, source, record_id, _FAMILIES.get(source, source), features, scope, candidate_ids
                )
                if entry_id is not None:
                    definition = definitions[entry_id]
                    definitions[entry_id] = replace(
                        definition, source_ids=tuple(sorted(set(definition.source_ids) | {record_id}))
                    )
                if scope == "unscoped":
                    unresolved.append({"code": "UNSCOPED_SOURCE", "source": source, "record_id": record_id})
                if source == "verbnet" and callable(getattr(parser, "definition_links", None)):
                    witnesses, projected, diagnostics = _verbnet_links(
                        parser,
                        native,
                        features,
                        record_id,
                        word,
                        by_synset,
                        getattr(loaded.get("wordnet_hierarchy"), "_wn", None),
                    )
                    assertions.extend(projected)
                    unresolved.extend(diagnostics)
                    for witness in witnesses:
                        observations[witness.record_id] = witness
                        definition = definitions[witness.entry_id]
                        definitions[witness.entry_id] = replace(
                            definition, source_ids=tuple(sorted(set(definition.source_ids) | {witness.record_id}))
                        )
                    continue
                if entry_id is None:
                    unresolved.append(
                        {
                            "code": "UNRESOLVED_SOURCE_LINK",
                            "source": source,
                            "record_id": record_id,
                            "lemma": word,
                        }
                    )
    return EvidenceBundle(
        tuple(definitions[key] for key in sorted(definitions)),
        tuple(observations[key] for key in sorted(observations)),
        tuple(sorted(set(assertions), key=lambda assertion: (assertion.record_id, assertion.bank, assertion.value))),
        tuple(sorted(unresolved, key=_canonical_json)),
    )


_SOURCE_CLASSES = {
    "wordnet_hierarchy": "WordNetHierarchyParser",
    "sentiwordnet": "SentiWordNetParser",
    "nrc_emotion": "NRCEmotionParser",
    "nrc_vad": "NRCVADParser",
    "verbnet": "VerbNetParser",
    "concreteness": "ConcretenessParser",
    "lancaster_sensorimotor": "LancasterSensorimotorParser",
    "framenet": "FrameNetParser",
    "propbank": "PropBankParser",
    "conceptnet": "ConceptNetParser",
    "usas": "USASParser",
}
_NLTK_SOURCES = frozenset({"wordnet_hierarchy", "sentiwordnet", "verbnet", "framenet", "propbank"})


class _LocalAdapter(Protocol):
    """Common loader boundary; legacy adapters do not share one base class."""

    entries: dict

    def load(self) -> bool: ...


class _IndexedAdapter(Protocol):
    """Additional fields on the existing ConceptNet cache adapter."""

    db_path: Path
    conn: sqlite3.Connection | None
    _loaded: bool


def _verify_nltk_cache(source: str) -> None:
    """Force the same local-reader prerequisites the legacy loader probes.

    NLTK corpus readers raise LookupError for missing resources; only the GSE
    adapter loaders catch that and download. Performing their checks here first
    prevents entering that fallback. SentiWordNet's generator is consumed so its
    underlying WordNet/SentiWordNet files are actually read.
    """
    from nltk import corpus

    if source == "wordnet_hierarchy":
        corpus.wordnet.synsets("test")
    elif source == "sentiwordnet":
        list(corpus.sentiwordnet.senti_synsets("good"))
    elif source == "verbnet":
        corpus.verbnet.classids()
    elif source == "framenet":
        corpus.framenet.frames()
    elif source == "propbank":
        corpus.propbank.rolesets()
    else:
        raise ValueError("UNKNOWN_NLTK_SOURCE")


def _load_local_source(source: str, parser: _LocalAdapter) -> dict:
    """Load only verified local caches; return a measured named diagnostic."""
    if source in _NLTK_SOURCES:
        try:
            _verify_nltk_cache(source)
        except (ImportError, LookupError, OSError) as error:
            return {"source": source, "code": "UNAVAILABLE", "reason": type(error).__name__}
    elif source == "conceptnet":
        indexed = cast(_IndexedAdapter, parser)
        path = Path(indexed.db_path)
        if not path.is_file():
            return {"source": source, "code": "UNAVAILABLE", "reason": "MISSING_SQLITE_CACHE", "path": str(path)}
        connection = None
        try:
            connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
            count = connection.execute("SELECT count(*) FROM edges").fetchone()[0]
            # Validate the columns needed by the native collector, not just any
            # file that happens to be a SQLite database.
            connection.execute("SELECT relation,start_word,end_word,weight,source FROM edges LIMIT 0")
        except (OSError, sqlite3.Error) as error:
            if connection is not None:
                connection.close()
            return {"source": source, "code": "UNAVAILABLE", "reason": type(error).__name__, "path": str(path)}
        indexed.conn = connection
        indexed._loaded = True
        return {"source": source, "code": "LOADED", "native_records": count, "path": str(path)}
    else:
        path = getattr(parser, "lexicon_path", None) if source == "usas" else getattr(parser, "data_path", None)
        if path is None or not Path(path).is_file():
            return {
                "source": source,
                "code": "UNAVAILABLE",
                "reason": "MISSING_LOCAL_FILE",
                "path": str(path) if path is not None else None,
            }
    if not parser.load():
        return {"source": source, "code": "UNAVAILABLE", "reason": "LOCAL_PARSE_FAILED"}
    entries = parser.entries
    count = sum(len(records) if isinstance(records, (list, tuple)) else 1 for records in entries.values())
    return {"source": source, "code": "LOADED", "words": len(entries), "native_records": count}


def load_local_sources(sources: tuple[str, ...] | None = None) -> tuple[dict[str, object], tuple[dict, ...]]:
    """Load registered adapters from existing caches without network or writes.

    Every requested source yields a diagnostic. ConceptNet opens read-only and
    never builds its index; other sources are preflighted before legacy loading.
    The caller owns and closes the returned adapters.
    """
    requested = tuple(_SOURCE_CLASSES) if sources is None else sources
    if not isinstance(requested, tuple) or any(source not in _SOURCE_CLASSES for source in requested):
        raise ValueError("UNKNOWN_LOCAL_SOURCE")
    parsers = {}
    diagnostics = []
    for source in dict.fromkeys(requested):
        try:
            module = importlib.import_module(f"gse.curation.external_sources.{source}")
            parser = getattr(module, _SOURCE_CLASSES[source])()
            diagnostic = _load_local_source(source, parser)
        except (ImportError, OSError, ValueError, sqlite3.Error) as error:
            diagnostic = {"source": source, "code": "UNAVAILABLE", "reason": type(error).__name__}
        diagnostics.append(diagnostic)
        if diagnostic["code"] == "LOADED":
            parsers[source] = parser
    return parsers, tuple(diagnostics)
