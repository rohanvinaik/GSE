"""Native morphology evidence within an already selected WordNet definition.

This records identity witnesses, never chooses a sense or supplies a bank sign.
Regular substitution rules remain proposals even when their bases occur in the
selected synset: the same machinery proposes ``as -> A`` and ``feet -> foot``.
The latter has an explicit exception witness; the former does not.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from urllib.parse import quote

from nltk.corpus.reader.wordnet import WordNetError

from GSE.namespace import current_id, identity_form

FORMAT = "GSE.wordnet-definition-identity/1"
DEFINING_CONTEXT_FORMAT = "GSE.wordnet-definition-identity/2"
ANCESTRY_FORMAT = "GSE.wordnet-defining-ancestry/1"
_POS = {
    "n": "noun",
    "noun": "noun",
    "v": "verb",
    "verb": "verb",
    "a": "adj",
    "s": "adj",
    "adj": "adj",
    "adjective": "adj",
    "r": "adv",
    "adv": "adv",
    "adverb": "adv",
}


def _canonical(value):
    return value.casefold().replace("_", " ")


def _strings(value, code):
    if (
        not isinstance(value, (list, tuple))
        or not value
        or any(type(item) is not str or not item.strip() for item in value)
    ):
        raise ValueError(code)
    return list(value)


def _witness(synset):
    if synset is None:
        raise ValueError("SYNSET_REQUIRED")
    values = {
        key: getattr(synset, method)()
        for key, method in (
            ("name", "name"),
            ("pos", "pos"),
            ("definition", "definition"),
            ("lemma_names", "lemma_names"),
            ("lexname", "lexname"),
        )
    }
    if any(type(values[key]) is not str or not values[key].strip() for key in ("name", "pos", "definition", "lexname")):
        raise ValueError("INVALID_NATIVE_SYNSET")
    if values["pos"] not in {"n", "v", "a", "s", "r"}:
        raise ValueError("INVALID_NATIVE_POS")
    values["lemma_names"] = _strings(values["lemma_names"], "INVALID_NATIVE_LEMMAS")
    return values


def _records(parser, base, witness):
    """Read exact base-index records, not a first record or another sense."""
    entries = getattr(parser, "entries", None)
    if not isinstance(entries, Mapping):
        raise ValueError("INVALID_NATIVE_RECORD_INDEX")
    records = entries.get(_canonical(base), ())
    if not isinstance(records, (list, tuple)):
        raise ValueError("INVALID_NATIVE_RECORD_LIST")
    selected = []
    for record in records:
        raw = asdict(record) if is_dataclass(record) and not isinstance(record, type) else record
        if not isinstance(raw, Mapping):
            raise ValueError("INVALID_NATIVE_RECORD")
        if raw.get("synset_name") != witness["name"]:
            continue
        if (
            type(raw.get("word")) is not str
            or _canonical(raw["word"]) != _canonical(base)
            or type(raw.get("pos")) is not str
            or _POS.get(raw["pos"]) != _POS[witness["pos"]]
            or raw.get("lexname") != witness["lexname"]
        ):
            raise ValueError("NATIVE_RECORD_IDENTITY_MISMATCH")
        if "definition" in raw and raw["definition"] != witness["definition"]:
            raise ValueError("NATIVE_RECORD_DEFINITION_MISMATCH")
        if any(type(key) is not str for key in raw):
            raise ValueError("INVALID_NATIVE_RECORD_KEYS")
        selected.append(json.loads(json.dumps(dict(raw), allow_nan=False)))
    return selected


def _finish(packet, code, reason):
    packet.update(code=code, reason=reason)
    packet["authority"] = (
        "IDENTITY_EVIDENCE_WITHIN_SELECTED_SENSE"
        if code in {"NATIVE_LEMMA", "EXCEPTION_DERIVED"}
        else "CANDIDATE_ONLY"
        if code == "REGULAR_RULE_CANDIDATES"
        else "NONE"
    )
    return packet


def wordnet_identity_evidence(parser, surface, synset, *, pos=None):
    """Return JSON evidence using the collector's loaded parser and selected synset.

    ``pos`` optionally checks the caller's expected source POS. No adapter is
    loaded, no download is attempted, and no lexical/sense search is performed.
    An exact named-synset relookup validates that the supplied witness belongs to
    this parser. ``_morphy`` is the existing enumerator used by WordNet ``synsets``;
    all alternatives are retained instead of accepting ``morphy``'s first form.
    """
    packet = {
        "format": FORMAT,
        "code": "UNRESOLVED",
        "reason": "NOT_EVALUATED",
        "authority": "NONE",
        "surface": surface if type(surface) is str else None,
        "normalized_surface": None,
        "source": {"name": "wordnet_hierarchy", "version": None},
        "native_synset": None,
        "analyses": [],
        "unmatched_candidates": [],
        "selects_sense": False,
        "assigns_banks": False,
    }
    if type(surface) is not str or not surface.strip() or surface != surface.strip():
        return _finish(packet, "MALFORMED", "INVALID_SURFACE")
    packet["normalized_surface"] = _canonical(surface)
    if pos is not None and (type(pos) is not str or pos not in _POS):
        return _finish(packet, "MALFORMED", "INVALID_EXPECTED_POS")
    if getattr(parser, "_loaded", False) is not True or getattr(parser, "_wn", None) is None:
        return _finish(packet, "UNRESOLVED", "SOURCE_NOT_LOADED")
    wordnet = parser._wn
    try:
        version = wordnet.get_version()
        if type(version) is not str or not version.strip():
            return _finish(packet, "UNRESOLVED", "SOURCE_VERSION_UNAVAILABLE")
        packet["source"]["version"] = version
        witness = _witness(synset)
        if pos is not None and _POS[pos] != _POS[witness["pos"]]:
            return _finish(packet, "MALFORMED", "EXPECTED_POS_MISMATCH")
        if _witness(wordnet.synset(witness["name"])) != witness:
            return _finish(packet, "MALFORMED", "SELECTED_SYNSET_MISMATCH")
        packet["native_synset"] = witness
        normalized = packet["normalized_surface"]
        native_names = witness["lemma_names"]
        native_matching = [name for name in native_names if _canonical(name) == normalized]
        if native_matching:
            packet["analyses"] = [
                {
                    "base": normalized,
                    "native_lemmas": native_matching,
                    "derivation": {"kind": "NATIVE_LEMMA", "exception_bases": [], "substitutions": []},
                    "native_records": _records(parser, normalized, witness),
                }
            ]
            return _finish(packet, "NATIVE_LEMMA", "EXPLICIT_NATIVE_LEMMA_MEMBERSHIP")
        wn_pos = witness["pos"]
        form = normalized.replace(" ", "_")
        exception_maps = wordnet._exception_map
        if not isinstance(exception_maps, Mapping):
            raise ValueError("INVALID_EXCEPTION_MAP")
        exception_map = exception_maps.get(wn_pos)
        if not isinstance(exception_map, Mapping):
            raise ValueError("INVALID_EXCEPTION_MAP")
        exceptional = form in exception_map
        exceptions = _strings(exception_map[form], "INVALID_EXCEPTION_BASES") if exceptional else []
        rule_maps = wordnet.MORPHOLOGICAL_SUBSTITUTIONS
        if not isinstance(rule_maps, Mapping):
            raise ValueError("INVALID_MORPHOLOGY_RULES")
        rules = rule_maps.get(wn_pos)
        if not isinstance(rules, (list, tuple)) or any(
            not isinstance(rule, (list, tuple))
            or len(rule) != 2
            or any(type(part) is not str for part in rule)
            or not rule[0]
            for rule in rules
        ):
            raise ValueError("INVALID_MORPHOLOGY_RULES")
        candidates = wordnet._morphy(form, wn_pos)
        if not isinstance(candidates, (list, tuple)) or any(type(item) is not str or not item for item in candidates):
            raise ValueError("INVALID_MORPHOLOGY_CANDIDATES")
        for base in dict.fromkeys(candidates):
            names = [name for name in native_names if _canonical(name) == _canonical(base)]
            if not names:
                packet["unmatched_candidates"].append(base)
                continue
            substitutions = (
                [
                    {"suffix": old, "replacement": new}
                    for old, new in rules
                    if form.endswith(old) and form[: -len(old)] + new == base
                ]
                if not exceptional
                else []
            )
            if exceptional and base not in exceptions or not exceptional and not substitutions:
                raise ValueError("MORPHOLOGY_DERIVATION_MISMATCH")
            packet["analyses"].append(
                {
                    "base": base,
                    "native_lemmas": names,
                    "derivation": {
                        "kind": "EXCEPTION" if exceptional else "REGULAR_SUBSTITUTION",
                        "exception_bases": exceptions,
                        "substitutions": substitutions,
                    },
                    "native_records": _records(parser, base, witness),
                }
            )
        if not packet["analyses"]:
            return _finish(packet, "UNRESOLVED", "NO_MATCHING_NATIVE_BASE")
        return _finish(
            packet,
            "EXCEPTION_DERIVED" if exceptional else "REGULAR_RULE_CANDIDATES",
            "EXPLICIT_NATIVE_EXCEPTION" if exceptional else "SUFFIX_RULE_IS_CANDIDATE_ONLY",
        )
    except LookupError, WordNetError:
        return _finish(packet, "UNRESOLVED", "NATIVE_SOURCE_UNAVAILABLE")
    except (AttributeError, TypeError, ValueError) as error:
        packet["analyses"] = []
        return _finish(packet, "MALFORMED", str(error) if isinstance(error, ValueError) else "INVALID_SOURCE_INTERFACE")


def wordnet_defining_context(parser, surface, synset, *, pos=None):
    """Extend exact selected noun identity with complete native genus witnesses.

    The existing parser supplies every hypernym path. No new source, sense
    selection, lexical search or bank projection is introduced. Legacy identity
    packets remain byte-for-byte reproducible through the original constructor.
    """
    packet = wordnet_identity_evidence(parser, surface, synset, pos=pos)
    if packet["code"] not in {"NATIVE_LEMMA", "EXCEPTION_DERIVED", "REGULAR_RULE_CANDIDATES"}:
        raise ValueError("DEFINING_CONTEXT_REQUIRES_SELECTED_IDENTITY")
    if packet["native_synset"]["pos"] != "n":
        raise ValueError("DEFINING_GENUS_REQUIRES_NOUN")
    paths, witnesses = [], {}
    for path in synset.hypernym_paths():
        names = []
        for node in path:
            witness = _witness(node)
            if _witness(parser._wn.synset(witness["name"])) != witness:
                raise ValueError("DEFINING_ANCESTOR_SOURCE_MISMATCH")
            previous = witnesses.setdefault(witness["name"], witness)
            if previous != witness:
                raise ValueError("DEFINING_ANCESTOR_AMBIGUOUS_WITNESS")
            names.append(witness["name"])
        paths.append(names)
    packet["format"] = DEFINING_CONTEXT_FORMAT
    packet["defining_ancestry"] = {
        "format": ANCESTRY_FORMAT,
        "code": "EXACT_NATIVE_HYPERNYM_PATHS",
        "paths": sorted(paths),
        "synsets": {name: witnesses[name] for name in sorted(witnesses)},
        "semantics": "DEFINING_GENUS_CONTEXT_NOT_AUTOMATIC_BANK_TRANSFER",
    }
    _validate_defining_ancestry(packet["defining_ancestry"], packet["native_synset"])
    return packet


def _validate_defining_ancestry(ancestry, native_synset):
    """Check the stored graph's shape; enrichment independently re-fetches it."""
    if (
        type(ancestry) is not dict
        or set(ancestry) != {"format", "code", "paths", "synsets", "semantics"}
        or current_id(ancestry["format"]) != ANCESTRY_FORMAT
        or ancestry["code"] != "EXACT_NATIVE_HYPERNYM_PATHS"
        or ancestry["semantics"] != "DEFINING_GENUS_CONTEXT_NOT_AUTOMATIC_BANK_TRANSFER"
    ):
        raise ValueError("INVALID_DEFINING_ANCESTRY")
    if native_synset["pos"] != "n":
        raise ValueError("DEFINING_GENUS_REQUIRES_NOUN")
    paths, witnesses = ancestry["paths"], ancestry["synsets"]
    if type(paths) is not list or not paths or type(witnesses) is not dict:
        raise ValueError("INVALID_DEFINING_ANCESTRY_GRAPH")
    used, seen = set(), set()
    for path in paths:
        _strings(path, "INVALID_DEFINING_ANCESTRY_PATH")
        if path[-1] != native_synset["name"] or len(set(path)) != len(path) or tuple(path) in seen:
            raise ValueError("DEFINING_ANCESTRY_PATH_IDENTITY_MISMATCH")
        seen.add(tuple(path))
        used.update(path)
    if set(witnesses) != used or witnesses.get(native_synset["name"]) != native_synset:
        raise ValueError("DEFINING_ANCESTRY_WITNESS_COVERAGE_MISMATCH")
    for name, witness in witnesses.items():
        if (
            type(witness) is not dict
            or set(witness) != {"name", "pos", "definition", "lemma_names", "lexname"}
            or witness["name"] != name
            or witness["pos"] != "n"
            or any(type(witness[key]) is not str or not witness[key].strip() for key in ("name", "definition", "lexname"))
        ):
            raise ValueError("INVALID_DEFINING_ANCESTOR_WITNESS")
        _strings(witness["lemma_names"], "INVALID_DEFINING_ANCESTOR_LEMMAS")


def _definition_record(definition):
    from .evidence import Definition

    raw = asdict(definition) if isinstance(definition, Definition) else definition
    required = {"entry_id", "lemma", "pos", "definition"}
    if (
        not isinstance(raw, Mapping)
        or not required <= set(raw)
        or set(raw) - required - {"source_ids"}
        or any(type(raw[key]) is not str or not raw[key].strip() for key in required)
    ):
        raise ValueError("INVALID_IDENTITY_ROOT_DEFINITION")
    return {key: raw[key] for key in sorted(required)}


def _json_packet(value):
    """A serialized packet is JSON, not a coercible Python object graph."""
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("INVALID_IDENTITY_JSON_KEYS")
        for item in value.values():
            _json_packet(item)
    elif type(value) is list:
        for item in value:
            _json_packet(item)
    elif value is not None and type(value) not in (str, int, bool, float):
        raise ValueError("INVALID_IDENTITY_JSON_VALUE")
    json.dumps(value, allow_nan=False)


def validate_wordnet_identity(packet, definition):
    """Validate a stored context packet against its exact original definition.

    This checks the recorded witness and derivation structure. It does not fetch
    WordNet, certify externally supplied assertions as native truth, or promote a
    regular candidate to identity authority. Source construction supplies that
    provenance; consumers keep the packet context-only.
    """
    root = _definition_record(definition)
    keys = {
        "format",
        "code",
        "reason",
        "authority",
        "surface",
        "normalized_surface",
        "source",
        "native_synset",
        "analyses",
        "unmatched_candidates",
        "selects_sense",
        "assigns_banks",
    }
    if type(packet) is dict and current_id(packet.get("format")) == DEFINING_CONTEXT_FORMAT:
        keys.add("defining_ancestry")
    if type(packet) is not dict or set(packet) != keys:
        raise ValueError("INVALID_WORDNET_IDENTITY_PACKET")
    _json_packet(packet)
    if type(packet["format"]) is not str or current_id(packet["format"]) not in {FORMAT, DEFINING_CONTEXT_FORMAT}:
        raise ValueError("INVALID_WORDNET_IDENTITY_FORMAT")
    states = {
        "NATIVE_LEMMA": ("IDENTITY_EVIDENCE_WITHIN_SELECTED_SENSE", "EXPLICIT_NATIVE_LEMMA_MEMBERSHIP"),
        "EXCEPTION_DERIVED": ("IDENTITY_EVIDENCE_WITHIN_SELECTED_SENSE", "EXPLICIT_NATIVE_EXCEPTION"),
        "REGULAR_RULE_CANDIDATES": ("CANDIDATE_ONLY", "SUFFIX_RULE_IS_CANDIDATE_ONLY"),
        "UNRESOLVED": ("NONE", "NO_MATCHING_NATIVE_BASE"),
    }
    if type(packet["code"]) is not str or packet["code"] not in states:
        raise ValueError("IDENTITY_PACKET_NOT_USABLE_CONTEXT")
    if (packet["authority"], packet["reason"]) != states[packet["code"]]:
        raise ValueError("IDENTITY_AUTHORITY_MISMATCH")
    if packet["selects_sense"] is not False or packet["assigns_banks"] is not False:
        raise ValueError("IDENTITY_CONTEXT_ONLY_REQUIRED")
    if (
        packet["surface"] != root["lemma"]
        or not root["lemma"].strip()
        or packet["normalized_surface"] != _canonical(root["lemma"])
    ):
        raise ValueError("IDENTITY_ROOT_SURFACE_MISMATCH")
    source = packet["source"]
    if (
        type(source) is not dict
        or set(source) != {"name", "version"}
        or source["name"] != "wordnet_hierarchy"
        or type(source["version"]) is not str
        or not source["version"].strip()
    ):
        raise ValueError("IDENTITY_SOURCE_VERSION_REQUIRED")
    witness = packet["native_synset"]
    if (
        type(witness) is not dict
        or set(witness) != {"name", "pos", "definition", "lemma_names", "lexname"}
        or any(
            type(witness[key]) is not str or not witness[key].strip()
            for key in ("name", "pos", "definition", "lexname")
        )
        or witness["pos"] not in {"n", "v", "a", "s", "r"}
    ):
        raise ValueError("INVALID_IDENTITY_SYNSET_WITNESS")
    names = _strings(witness["lemma_names"], "INVALID_IDENTITY_NATIVE_LEMMAS")
    expected = f"wordnet:{quote(root['lemma'], safe='')}:{quote(witness['name'], safe='')}"
    if (
        root["entry_id"] != expected
        or root["definition"] != witness["definition"]
        or _POS.get(root["pos"]) != _POS[witness["pos"]]
    ):
        raise ValueError("IDENTITY_ROOT_DEFINITION_MISMATCH")
    if current_id(packet["format"]) == DEFINING_CONTEXT_FORMAT:
        _validate_defining_ancestry(packet["defining_ancestry"], witness)
    analyses, unmatched = packet["analyses"], packet["unmatched_candidates"]
    if type(analyses) is not list or type(unmatched) is not list:
        raise ValueError("INVALID_IDENTITY_ANALYSES")
    if any(type(item) is not str or not item for item in unmatched) or len(set(unmatched)) != len(unmatched):
        raise ValueError("INVALID_IDENTITY_UNMATCHED_CANDIDATES")
    native_set = {_canonical(name) for name in names}
    if any(_canonical(base) in native_set for base in unmatched):
        raise ValueError("IDENTITY_MATCHED_BASE_MISLABELLED")
    surface_native = packet["normalized_surface"] in native_set
    if surface_native != (packet["code"] == "NATIVE_LEMMA"):
        raise ValueError("IDENTITY_NATIVE_MEMBERSHIP_MISMATCH")
    if bool(analyses) == (packet["code"] == "UNRESOLVED"):
        raise ValueError("IDENTITY_ANALYSIS_STATUS_MISMATCH")
    seen = set()
    form = packet["normalized_surface"].replace(" ", "_")
    for analysis in analyses:
        if type(analysis) is not dict or set(analysis) != {"base", "native_lemmas", "derivation", "native_records"}:
            raise ValueError("INVALID_IDENTITY_ANALYSIS")
        base = analysis["base"]
        if type(base) is not str or not base or base in seen:
            raise ValueError("INVALID_IDENTITY_BASE")
        seen.add(base)
        matching = [name for name in names if _canonical(name) == _canonical(base)]
        if not matching or analysis["native_lemmas"] != matching:
            raise ValueError("IDENTITY_BASE_NOT_NATIVE")
        derivation = analysis["derivation"]
        if type(derivation) is not dict or set(derivation) != {"kind", "exception_bases", "substitutions"}:
            raise ValueError("INVALID_IDENTITY_DERIVATION")
        exceptions, rules = derivation["exception_bases"], derivation["substitutions"]
        if type(exceptions) is not list or type(rules) is not list:
            raise ValueError("INVALID_IDENTITY_DERIVATION_LISTS")
        if packet["code"] == "NATIVE_LEMMA":
            if (
                len(analyses) != 1
                or _canonical(base) != packet["normalized_surface"]
                or derivation != {"kind": "NATIVE_LEMMA", "exception_bases": [], "substitutions": []}
            ):
                raise ValueError("INVALID_NATIVE_MEMBERSHIP_DERIVATION")
        elif packet["code"] == "EXCEPTION_DERIVED":
            if (
                derivation["kind"] != "EXCEPTION"
                or base not in _strings(exceptions, "INVALID_EXCEPTION_BASES")
                or rules
            ):
                raise ValueError("INVALID_EXCEPTION_DERIVATION")
        else:
            if derivation["kind"] != "REGULAR_SUBSTITUTION" or exceptions or not rules:
                raise ValueError("INVALID_REGULAR_DERIVATION")
            for rule in rules:
                if (
                    type(rule) is not dict
                    or set(rule) != {"suffix", "replacement"}
                    or type(rule["suffix"]) is not str
                    or not rule["suffix"]
                    or type(rule["replacement"]) is not str
                    or not form.endswith(rule["suffix"])
                    or form[: -len(rule["suffix"])] + rule["replacement"] != base
                ):
                    raise ValueError("INVALID_REGULAR_TRANSFORMATION")
        if type(analysis["native_records"]) is not list:
            raise ValueError("INVALID_IDENTITY_NATIVE_RECORDS")

        # Reuse the exact record checker without consulting a live source.
        class RecordIndex:
            entries = {_canonical(base): analysis["native_records"]}

        records = _records(RecordIndex(), base, witness)
        if records != analysis["native_records"]:
            raise ValueError("IDENTITY_CONTAINS_OTHER_SENSE_RECORD")
    return json.loads(json.dumps(packet, allow_nan=False))


def wordnet_identity_observation_fields(packet, definition):
    """Return validated envelope fields without recursively constructing an observation."""
    root = _definition_record(definition)
    checked = validate_wordnet_identity(packet, root)
    bound = {"definition": root, "definition_identity": checked}
    serialized = json.dumps(identity_form(bound), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    record_id = "wordnet_identity:" + hashlib.sha256(serialized.encode()).hexdigest()
    return {
        "entry_id": root["entry_id"],
        "source": "wordnet_hierarchy",
        "record_id": record_id,
        "family": "wordnet",
        "features": {**root, "definition_identity": checked, "context_only": True},
        "scope": "lexical",
        "candidate_entry_ids": (root["entry_id"],),
    }


def wordnet_identity_observation(packet, definition):
    """Construct an additive, exact-root, context-only existing Observation."""
    from .evidence import Observation

    return Observation(**wordnet_identity_observation_fields(packet, definition))
