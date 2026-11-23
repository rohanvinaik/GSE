"""Versioned representation conventions, separate from corpus-discovered rules.

These are the founder-approved projection laws, not a claim that NSM's full
prime explications have already been compiled. Additional justified relations
and hand-reviewed definition anchors enter through the build manifest.
"""

import hashlib
import json
import re
from itertools import product
from pathlib import Path
from urllib.parse import quote

from GSE.curation.schema import ALL_PRIMITIVES, BIPOLAR_PAIRS
from GSE.namespace import current_id

from .definition_frames import (
    NATIVE_FRAME_PREFIX,
    NATIVE_NOUN_FRAMES,
    WIKTIONARY_ANATOMY_FRAME_PREFIX,
    WIKTIONARY_ANATOMY_FRAMES,
    native_noun_frames,
    wiktionary_anatomy_frame,
)
from .engine import Assertion, Relation
from .interchange import read_json

FOUNDER_SOURCE = "docs/program/LEXICON_FOUNDER_WORDS_2026-10-24.md"
DESIGN_SOURCE = "docs/program/LEXICON_CONSTRUCTION_DESIGN.md"
CONVENTION_VERSION = "GSE.lexicon-conventions/2026-10-29"
WANT_POLARITY = {-1: "NOT_WANT", 0: "ORTHOGONAL_TO_WANTING", 1: "WANT"}
ORDINAL_INTENSITY = {"VERY": 1, "EXTREMELY": 2}
NEGATIVE_POLES = {negative: positive for positive, negative in BIPOLAR_PAIRS}
BANKS = tuple(p for p in ALL_PRIMITIVES if p not in NEGATIVE_POLES and p not in {"NUMBER", "HIER_PLUS", "HIER_MINUS"})
POS_NAMES = {
    "n": "noun",
    "v": "verb",
    "a": "adjective",
    "s": "adjective",
    "r": "adverb",
    "adj": "adjective",
    "adv": "adverb",
}


def representation_contract() -> dict:
    """Pin supported ordinal laws and fingerprint the lexical basis explicitly.

    Other historical ordinal tables are not silently promoted to authority.
    A conflicting runtime mapping requires an explicit representation migration.
    """
    from GSE.primitives_v2 import get_hierarchy_encoding

    for modifier, level in ORDINAL_INTENSITY.items():
        if get_hierarchy_encoding(modifier) != ("INTENSITY", level, abs(level)):
            raise ValueError("ORDINAL_REPRESENTATION_DRIFT")
    return {
        "version": CONVENTION_VERSION,
        "basis": list(BANKS),
        "basis_sha256": hashlib.sha256(json.dumps(BANKS, separators=(",", ":")).encode()).hexdigest(),
        "want_polarity": {str(k): v for k, v in WANT_POLARITY.items()},
        "ordinal_intensity": dict(ORDINAL_INTENSITY),
        "ordinal_source": DESIGN_SOURCE + "#ordinal-stability",
        "other_ordinal_levels": "EXPLICIT_JUSTIFIED_MANIFEST_ONLY",
    }


def definition_context(pos: str) -> dict[str, str]:
    """Keep unknown POS unknown; only explicit lexical types activate a law."""
    normalized = pos.lower()
    return {"pos": POS_NAMES.get(normalized, normalized)}


_WORDNET_SYNSET = re.compile(r"[^\s:]+\.[nvasr]\.(?:0[1-9]|[1-9][0-9]+)\Z")
_ANCESTOR_PREFIX = "wordnet_ancestor:"


EXCEPTION_GUARD_PREFIX = "except_entry:"
WORDNET_OUTSIDE_ANCESTOR_PREFIX = "wordnet_outside_ancestor:"
WORDNET_OTHER_SYNSET_PREFIX = "wordnet_other_than_synset:"
WORDNET_ANCESTRY_GUARD_PREFIXES = (
    _ANCESTOR_PREFIX,
    WORDNET_OUTSIDE_ANCESTOR_PREFIX,
    WORDNET_OTHER_SYNSET_PREFIX,
)


def valid_lexical_guard(key, value) -> bool:
    """Recognize lexical scope predicates, never bank values or inferred signs."""
    if not isinstance(key, str) or not isinstance(value, str):
        return False
    if key == "pos":
        return bool(value.strip())
    if key == "wordnet_native_lemma":
        return value == "true"
    if key.startswith(NATIVE_FRAME_PREFIX):
        return value == "true" and key.removeprefix(NATIVE_FRAME_PREFIX) in NATIVE_NOUN_FRAMES
    if key.startswith(WIKTIONARY_ANATOMY_FRAME_PREFIX):
        return value == "true" and key.removeprefix(WIKTIONARY_ANATOMY_FRAME_PREFIX) in WIKTIONARY_ANATOMY_FRAMES
    if key.startswith(EXCEPTION_GUARD_PREFIX):
        identity = key.removeprefix(EXCEPTION_GUARD_PREFIX)
        return bool(identity) and not any(char.isspace() for char in identity) and value == "true"
    return value == "true" and any(
        key.startswith(prefix) and _WORDNET_SYNSET.fullmatch(key.removeprefix(prefix)) is not None
        for prefix in WORDNET_ANCESTRY_GUARD_PREFIXES
    )


def validate_lexical_guards(relations) -> tuple[str, ...]:
    """Refuse unsupported scope schemas, including for empty build populations."""
    requested = set()
    for relation in relations:
        for key, value in relation.guards:
            if not valid_lexical_guard(key, value):
                raise ValueError("UNSUPPORTED_LEXICAL_GUARD")
            for prefix in WORDNET_ANCESTRY_GUARD_PREFIXES:
                if key.startswith(prefix):
                    requested.add(key.removeprefix(prefix))
    return tuple(sorted(requested))


def _field(record, name):
    return record.get(name) if isinstance(record, dict) else getattr(record, name, None)


def _exact_wordnet_ancestry(definition, observation) -> frozenset[str]:
    """Read a complete exact native witness; malformed/mismatched data abstains.

    Native paths include the synset itself. Aliases are not guessed: both the
    definition identity and each path must name the recorded canonical synset.
    Candidate links and association observations supply no membership authority.
    """
    entry_id = _field(definition, "entry_id")
    if (
        _field(observation, "source") != "wordnet_hierarchy"
        or _field(observation, "scope") != "lexical"
        or _field(observation, "entry_id") != entry_id
        or _field(observation, "record_id") != entry_id
    ):
        return frozenset()
    features = _field(observation, "features")
    if not isinstance(features, dict):
        return frozenset()
    lemma, pos, gloss = (_field(definition, name) for name in ("lemma", "pos", "definition"))
    synset = features.get("synset_name")
    native_pos = features.get("pos")
    if (
        not isinstance(synset, str)
        or _WORDNET_SYNSET.fullmatch(synset) is None
        or not isinstance(lemma, str)
        or not isinstance(pos, str)
        or not isinstance(native_pos, str)
        or not isinstance(gloss, str)
        or not gloss.strip()
        or features.get("lemma") != lemma
        or features.get("definition") != gloss
        or entry_id != f"wordnet:{quote(lemma, safe='')}:{quote(synset, safe='')}"
        or definition_context(native_pos) != definition_context(pos)
        or definition_context(synset.rsplit(".", 2)[1]) != definition_context(pos)
    ):
        return frozenset()
    paths = features.get("hypernym_paths")
    if not isinstance(paths, (list, tuple)) or not paths:
        return frozenset()
    ancestors = set()
    for path in paths:
        if (
            not isinstance(path, (list, tuple))
            or not path
            or any(not isinstance(node, str) or _WORDNET_SYNSET.fullmatch(node) is None for node in path)
            or path[-1] != synset
            or len(set(path)) != len(path)
            or any(node.rsplit(".", 2)[1] != synset.rsplit(".", 2)[1] for node in path)
        ):
            return frozenset()
        ancestors.update(path)
    return frozenset(ancestors)


def _attested_wordnet_lemma(definition, observation) -> bool:
    """Test the native spelling after an exact WordNet identity check."""
    names = _field(observation, "features").get("lemma_names")
    return (
        isinstance(names, (list, tuple))
        and bool(names)
        and all(isinstance(name, str) and name.strip() for name in names)
        and _field(definition, "lemma").casefold().replace("_", " ")
        in {name.casefold().replace("_", " ") for name in names}
    )


def native_frame_source(definition, observation) -> str | None:
    """Return the native sense group for an exact WordNet or Wiktionary witness."""
    source = _field(observation, "source")
    features = _field(observation, "features")
    if source == "wordnet_hierarchy":
        if _exact_wordnet_ancestry(definition, observation) and _attested_wordnet_lemma(definition, observation):
            return "wordnet:" + features["synset_name"]
        return None
    entry_id = _field(definition, "entry_id")
    if (
        source != "wiktionary"
        or _field(observation, "family") != "wiktionary"
        or _field(observation, "scope") != "lexical"
        or _field(observation, "entry_id") != entry_id
        or not isinstance(features, dict)
        or current_id(features.get("identity_scheme")) != "GSE.wiktionary-native-leaf/1"
        or any(features.get(field) != _field(definition, field) for field in ("entry_id", "lemma", "pos", "definition"))
    ):
        return None
    sense = features.get("native_sense")
    native_id, word = features.get("native_id"), features.get("word")
    if (
        not isinstance(sense, dict)
        or sense.get("glosses") != [features["definition"]]
        or any(key in sense for key in ("alt_of", "form_of"))
        or not isinstance(sense.get("tags", []), list)
        or any(tag in ("figuratively", "figurative", "metaphorical") for tag in sense.get("tags", []))
        or not isinstance(native_id, str)
        or not native_id
        or not isinstance(word, str)
        or not word
    ):
        return None
    from .evidence import _record_id

    if _field(observation, "record_id") != _record_id("wiktionary", word, features):
        return None
    return "wiktionary:" + native_id


def lexical_context(definition, observations, relations) -> dict[str, str]:
    """Add only requested predicates supported by exact native witnesses.

    Accept typed Definition/Observation objects or their serialized dictionaries.
    Missing witnesses remain absent, never false or a bank zero. With no source
    guards, the result is byte-for-byte equivalent to the old POS-only context;
    unrelated source context cannot perturb historical model request identities.
    """
    context = definition_context(_field(definition, "pos"))
    requested = validate_lexical_guards(relations)
    native_lemma_requested = any(key == "wordnet_native_lemma" for rule in relations for key, _ in rule.guards)
    frame_guards = {key for rule in relations for key, _ in rule.guards if key.startswith(NATIVE_FRAME_PREFIX)}
    gloss = _field(definition, "definition")
    if frame_guards and context.get("pos") == "noun" and isinstance(gloss, str):
        matched = frame_guards.intersection(NATIVE_FRAME_PREFIX + frame for frame in native_noun_frames(gloss))
        if matched and any(native_frame_source(definition, row) for row in observations):
            context.update(dict.fromkeys(sorted(matched), "true"))
    anatomy_guards = {
        key for rule in relations for key, _ in rule.guards if key.startswith(WIKTIONARY_ANATOMY_FRAME_PREFIX)
    }
    if anatomy_guards and context.get("pos") == "noun" and isinstance(gloss, str):
        for observation in observations:
            if _field(observation, "source") != "wiktionary" or not native_frame_source(definition, observation):
                continue
            frame = wiktionary_anatomy_frame(gloss, "noun", _field(observation, "features")["native_sense"])
            if frame is not None and WIKTIONARY_ANATOMY_FRAME_PREFIX + frame in anatomy_guards:
                context[WIKTIONARY_ANATOMY_FRAME_PREFIX + frame] = "true"
    if requested or native_lemma_requested:
        ancestors = set()
        synsets = set()
        for observation in observations:
            witnessed = _exact_wordnet_ancestry(definition, observation)
            ancestors.update(witnessed)
            if witnessed:
                synsets.add(_field(observation, "features")["synset_name"])
            if native_lemma_requested and witnessed and _attested_wordnet_lemma(definition, observation):
                context["wordnet_native_lemma"] = "true"
        if ancestors:
            for relation in relations:
                for key, _ in relation.guards:
                    if (
                        key.startswith(_ANCESTOR_PREFIX)
                        and key.removeprefix(_ANCESTOR_PREFIX) in ancestors
                        or key.startswith(WORDNET_OUTSIDE_ANCESTOR_PREFIX)
                        and key.removeprefix(WORDNET_OUTSIDE_ANCESTOR_PREFIX) not in ancestors
                        or key.startswith(WORDNET_OTHER_SYNSET_PREFIX)
                        and len(synsets) == 1
                        and key.removeprefix(WORDNET_OTHER_SYNSET_PREFIX) not in synsets
                    ):
                        context[key] = "true"
    for relation in relations:
        exclusions = [key for key, _ in relation.guards if key.startswith(EXCEPTION_GUARD_PREFIX)]
        if exclusions and all(context.get(key) == value for key, value in relation.guards if key not in exclusions):
            identity = _field(definition, "entry_id")
            if not isinstance(identity, str) or not identity:
                continue
            context.update(
                {key: "false" if identity == key.removeprefix(EXCEPTION_GUARD_PREFIX) else "true" for key in exclusions}
            )
    return context


def projection_relations() -> tuple[Relation, ...]:
    """Compile the approved own-word projection rules, with their scope guards."""
    foundational = (
        Relation(
            "founder:noun-own-evaluation",
            ("GOOD",),
            ((0,),),
            (FOUNDER_SOURCE + "#F057",),
            "foundational",
            True,
            (("pos", "noun"),),
        ),
        Relation(
            "founder:adjective-not-object",
            ("SOMETHING",),
            ((0,),),
            (FOUNDER_SOURCE + "#F057",),
            "foundational",
            True,
            (("pos", "adjective"),),
        ),
        Relation(
            "founder:adverb-not-object",
            ("SOMETHING",),
            ((0,),),
            (FOUNDER_SOURCE + "#F057",),
            "foundational",
            True,
            (("pos", "adverb"),),
        ),
    )
    categories = (
        ("I", "SOMEONE", (1,), ()),
        ("YOU", "SOMEONE", (1,), ()),
        ("BODY", "SOMETHING", (1,), (("pos", "noun"),)),
        ("ONE", "QUANTITY", (1,), ()),
        ("TWO", "QUANTITY", (1,), ()),
        ("MOVE", "HAPPEN", (1,), ()),
        ("DO", "HAPPEN", (1,), ()),
        ("CAUSE", "HAPPEN", (1,), ()),
        ("THEN", "WHEN", (-1, 1), ()),
        ("BEFORE", "WHEN", (-1, 1), ()),
        ("LONG_TIME", "WHEN", (-1, 1), ()),
        ("MOMENT", "WHEN", (1,), ()),
        ("ABOVE", "WHERE", (-1, 1), ()),
        ("FAR", "WHERE", (-1, 1), ()),
        ("OUTSIDE", "WHERE", (-1, 1), ()),
        ("TOWARD", "WHERE", (-1, 1), ()),
        ("HERE", "WHERE", (1,), ()),
        ("SIDE", "WHERE", (1,), ()),
    )
    category_relations = tuple(
        Relation(
            f"founder:category:{specific.lower()}-{general.lower()}",
            (specific, general),
            tuple((a, b) for a, b in product((-1, 0, 1), repeat=2) if a not in active or b == 1),
            (DESIGN_SOURCE + "#category-content",),
            "conditional",
            True,
            guards,
        )
        for specific, general, active, guards in categories
    )
    absence_relations = tuple(
        Relation(
            f"founder:absence:{source.lower()}-{target.lower()}",
            (source, target),
            tuple((a, b) for a, b in product((-1, 0, 1), repeat=2) if a == 0 or b == 0),
            (DESIGN_SOURCE + "#evidence-conditioned-absence",),
            "conditional",
            True,
            (("pos", "adjective"),),
            absent_evidence=(target,),
        )
        for source, target in (("GOOD", "BIG"), ("BIG", "GOOD"))
    )
    return foundational + category_relations + absence_relations


def load_manifest(path: str | Path | None) -> tuple[tuple[Relation, ...], dict[str, tuple[Assertion, ...]], dict]:
    """Load explicit approved rules/anchors and NUMBER metadata, never infer approval.

    Anchors are keyed by dictionary entry ID, not spelling. Each assertion must
    name its source and record. A manifest cannot mint additional coordinates.
    """
    if path is None:
        return (), {}, {}
    raw = read_json(path)
    if not isinstance(raw, dict) or current_id(raw.get("format")) != "GSE.lexicon-rules/1":
        raise ValueError("INVALID_RULE_MANIFEST")
    if set(raw) - {"format", "relations", "anchors", "hierarchy", "definitions", "prime_entries"}:
        raise ValueError("UNKNOWN_MANIFEST_FIELD")
    if not isinstance(raw.get("relations", []), list) or not isinstance(raw.get("anchors", {}), dict):
        raise ValueError("INVALID_RULE_MANIFEST")
    for entry_id, records in raw.get("anchors", {}).items():
        if not isinstance(entry_id, str) or not entry_id.strip() or not isinstance(records, list):
            raise ValueError("INVALID_ANCHORS")
    relations = []
    for record in raw.get("relations", []):
        required = {"rule_id", "banks", "allowed_rows", "provenance"}
        if (
            not isinstance(record, dict)
            or not required <= record.keys()
            or set(record) - required - {"authority", "approved", "guards", "absent_evidence"}
        ):
            raise ValueError("INVALID_RELATION_RECORD")
        for key in ("banks", "provenance", "allowed_rows", "guards", "absent_evidence"):
            if not isinstance(record.get(key, []), list):
                raise ValueError("INVALID_RELATION_SEQUENCE")
        if any(not isinstance(row, list) for row in record["allowed_rows"] + record.get("guards", [])):
            raise ValueError("INVALID_RELATION_ROWS")
        record = dict(record)
        for key in ("banks", "provenance"):
            record[key] = tuple(record[key])
        record["allowed_rows"] = tuple(tuple(row) for row in record["allowed_rows"])
        record["guards"] = tuple(tuple(pair) for pair in record.get("guards", []))
        record["absent_evidence"] = tuple(record.get("absent_evidence", []))
        relations.append(Relation(**record))
    try:
        anchors = {
            entry_id: tuple(Assertion(**record) for record in records)
            for entry_id, records in raw.get("anchors", {}).items()
        }
    except TypeError as exc:
        raise ValueError("INVALID_ANCHOR_RECORD") from exc
    hierarchy = raw.get("hierarchy", {})
    if not isinstance(hierarchy, dict):
        raise ValueError("INVALID_HIERARCHY")
    for entry_id, targets in hierarchy.items():
        if not isinstance(entry_id, str) or not isinstance(targets, dict):
            raise ValueError("INVALID_HIERARCHY")
        for bank, level in targets.items():
            if bank not in BANKS or type(level) is not int:
                raise ValueError("INVALID_HIERARCHY_TARGET")
    validate_lexical_guards(relations)
    return tuple(relations), anchors, hierarchy


def load_manifest_extensions(path: str | Path | None):
    """Explicit hand-authored definitions and prime-unit identity bindings.

    Existing source identities must be reused when they denote the same definition;
    neither this boundary nor catalog coverage merges meanings by spelling.
    """
    from .evidence import Definition

    if path is None:
        return (), {}
    raw = read_json(path)
    records = raw.get("definitions", [])
    links = raw.get("prime_entries", {})
    if not isinstance(records, list) or not isinstance(links, dict):
        raise ValueError("INVALID_MANIFEST_DEFINITIONS")
    definitions = []
    for record in records:
        required = {"entry_id", "lemma", "pos", "definition"}
        if not isinstance(record, dict) or not required <= record.keys() or set(record) - required - {"source_ids"}:
            raise ValueError("INVALID_MANIFEST_DEFINITION")
        if not isinstance(record.get("source_ids", []), list):
            raise ValueError("INVALID_MANIFEST_SOURCE_IDS")
        definitions.append(
            Definition(
                record["entry_id"],
                record["lemma"],
                record["pos"],
                record["definition"],
                tuple(record.get("source_ids", [])),
            )
        )
    for unit, entries in links.items():
        if (
            not isinstance(unit, str)
            or not isinstance(entries, list)
            or any(not isinstance(entry, str) or not entry.strip() for entry in entries)
        ):
            raise ValueError("INVALID_PRIME_ENTRIES")
    return tuple(definitions), {unit: tuple(entries) for unit, entries in links.items()}
