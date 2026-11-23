"""Source-native GSE grammatical definitions, separate from lexical homographs.

Only existing catalogs supply declared lexical values. Undeclared banks remain
unknown: an empty operator encoding never becomes a vector of zeros.
"""

from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote

from gse.curation.build_clean_closed_class import EXPONENTS, PERIPHRASTIC_MODALS, TIER0_FORMS, ZERO
from gse.curation.external_sources.tier_0_dispatch import canonical_decomposition
from gse.lexicon.function_words import CONJUNCTION_ENCODINGS, DETERMINER_ENCODINGS, PREPOSITION_ENCODINGS
from gse.lexicon.pronouns import PRONOUN_ENCODINGS
from gse.nlp.native import _ADP, _ADV_CLOSED, _AUX_BE, _AUX_DO, _AUX_MODAL, _CCONJ, _IRREGULAR_LEMMA, _NEG
from gse.symbolic.modality import MODAL_PRIMES

SOURCE = "gse_closed_class"
FOUNDATION_COHORT = "MANDATORY_FOUNDATION_COHORT"


def _require_native_json(value) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) in (list, tuple):
        for item in value:
            _require_native_json(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _require_native_json(item)
        return
    raise ValueError("INVALID_CLOSED_CLASS_NATIVE_ENCODING")


@dataclass(frozen=True)
class GSEClosedClassEntry:
    entry_id: str
    lemma: str
    pos: str
    definition: str
    catalog: str
    grammar_roles: tuple[str, ...]
    primitives: dict[str, int]
    grammatical_features: dict
    native_encodings: tuple[dict, ...]
    provenance: tuple[str, ...]
    cohort: str = FOUNDATION_COHORT

    def __post_init__(self):
        from gse.curation.external_sources.source_scope import SOURCE_PRIMITIVE_SCOPE

        if any(
            type(value) is not str or not value.strip()
            for value in (self.entry_id, self.lemma, self.pos, self.definition, self.catalog)
        ):
            raise ValueError("INVALID_CLOSED_CLASS_IDENTITY")
        if self.entry_id != f"{SOURCE}:{self.catalog}:{quote(self.lemma, safe='')}" or self.cohort != FOUNDATION_COHORT:
            raise ValueError("INVALID_CLOSED_CLASS_IDENTITY")
        if (
            type(self.grammar_roles) is not tuple
            or not self.grammar_roles
            or any(
                type(role) is not str or role not in {"PRON", "DET", "ADP", "CCONJ", "SCONJ", "AUX", "ADV", "PART"}
                for role in self.grammar_roles
            )
        ):
            raise ValueError("INVALID_CLOSED_CLASS_GRAMMAR_ROLE")
        if type(self.primitives) is not dict or any(
            bank not in SOURCE_PRIMITIVE_SCOPE[SOURCE] or type(value) is not int or value not in (-1, 1)
            for bank, value in self.primitives.items()
        ):
            raise ValueError("INVALID_CLOSED_CLASS_LEXICAL_COMPONENT")
        if type(self.grammatical_features) is not dict:
            raise ValueError("INVALID_CLOSED_CLASS_GRAMMAR_FEATURES")
        if (
            type(self.provenance) is not tuple
            or not self.provenance
            or any(type(value) is not str or not value.strip() for value in self.provenance)
        ):
            raise ValueError("INVALID_CLOSED_CLASS_PROVENANCE")
        if type(self.native_encodings) is not tuple or not self.native_encodings:
            raise ValueError("INVALID_CLOSED_CLASS_NATIVE_ENCODING")
        for native in self.native_encodings:
            if (
                type(native) is not dict
                or set(native) != {"module", "symbol", "key", "value"}
                or any(type(native[key]) is not str or not native[key].strip() for key in ("module", "symbol", "key"))
            ):
                raise ValueError("INVALID_CLOSED_CLASS_NATIVE_ENCODING")
        _require_native_json([self.grammatical_features, self.native_encodings])


def _origin(module: str, symbol: str, key: str, value) -> dict:
    return {"module": module, "symbol": symbol, "key": key, "value": copy.deepcopy(value)}


def _entry(word, catalog, pos, roles, primitives, grammar, origins) -> GSEClosedClassEntry:
    if any(type(value) is not int or value not in (-1, 1) for value in primitives.values()):
        raise ValueError("INVALID_CLOSED_CLASS_LEXICAL_COMPONENT")
    provenance = tuple(f"{item['module']}:{item['symbol']}:{item['key']}" for item in origins)
    content = ", ".join(f"{bank}={value:+d}" for bank, value in sorted(primitives.items()))
    description = f"Curated GSE {catalog} use of {word!r}. "
    description += (
        f"Declared lexical components: {content}. " if content else "No lexical bank assignment is declared. "
    )
    description += "Grammatical features: " + json.dumps(grammar, sort_keys=True, ensure_ascii=False) + "."
    return GSEClosedClassEntry(
        f"{SOURCE}:{catalog}:{quote(word, safe='')}",
        word,
        pos,
        description,
        catalog,
        roles,
        dict(primitives),
        copy.deepcopy(grammar),
        tuple(origins),
        provenance,
    )


def _function_entries() -> list[GSEClosedClassEntry]:
    entries = []
    for word, encoding in sorted(PRONOUN_ENCODINGS.items()):
        grammar = {key: value for key, value in encoding.items() if key != "primitives"}
        entries.append(
            _entry(
                word,
                "pronoun",
                "pronoun",
                ("PRON",),
                encoding["primitives"],
                grammar,
                [_origin("gse.lexicon.pronouns", "PRONOUN_ENCODINGS", word, encoding)],
            )
        )
    for catalog, table, symbol in (
        ("determiner", DETERMINER_ENCODINGS, "DETERMINER_ENCODINGS"),
        ("conjunction", CONJUNCTION_ENCODINGS, "CONJUNCTION_ENCODINGS"),
        ("preposition", PREPOSITION_ENCODINGS, "PREPOSITION_ENCODINGS"),
    ):
        for word, encoding in sorted(table.items()):
            role = (
                "DET"
                if catalog == "determiner"
                else "ADP"
                if catalog == "preposition"
                else "CCONJ"
                if word in _CCONJ
                else "SCONJ"
            )
            origins = [_origin("gse.lexicon.function_words", symbol, word, encoding)]
            primitives = {}
            if catalog == "preposition" and word in EXPONENTS:
                primitives = EXPONENTS[word]
                origins.append(_origin("gse.curation.build_clean_closed_class", "EXPONENTS", word, primitives))
            entries.append(_entry(word, catalog, catalog, (role,), primitives, encoding, origins))
    return entries


def _auxiliary_entries() -> list[GSEClosedClassEntry]:
    # Context-dependent 'd is resolved by grammar before choosing would/had.
    # It must not receive an unconditional modal identity from its spelling.
    forms = (set(_AUX_BE) | set(_AUX_DO) | set(_AUX_MODAL) | set(TIER0_FORMS)) - {"'d"}
    forms.update(word for word, lemma in _IRREGULAR_LEMMA.items() if lemma in {"be", "do", "have"})
    forms.add("have")
    entries = []
    for word in sorted(forms):
        lemma = _IRREGULAR_LEMMA.get(word, word)
        origins = []
        for table, symbol in (
            (TIER0_FORMS, "TIER0_FORMS"),
            (PERIPHRASTIC_MODALS, "PERIPHRASTIC_MODALS"),
            (EXPONENTS, "EXPONENTS"),
        ):
            key = word if word in table else lemma
            if key in table:
                primitives = table[key]
                origins.append(_origin("gse.curation.build_clean_closed_class", symbol, key, primitives))
                break
        else:
            primitives = canonical_decomposition(lemma) or {}
            origins.append(
                _origin("gse.curation.external_sources.tier_0_dispatch", "canonical_decomposition", lemma, primitives)
            )
        if word in _IRREGULAR_LEMMA:
            origins.append(_origin("gse.nlp.native", "_IRREGULAR_LEMMA", word, lemma))
        for table, symbol in ((_AUX_MODAL, "_AUX_MODAL"), (_AUX_BE, "_AUX_BE"), (_AUX_DO, "_AUX_DO")):
            if word in table:
                origins.append(_origin("gse.nlp.native", symbol, word, word))
        modal = word in _AUX_MODAL or bool(set(primitives) & MODAL_PRIMES)
        entries.append(
            _entry(
                word, "modal" if modal else "auxiliary", "auxiliary", ("AUX",), primitives, {"lemma": lemma}, origins
            )
        )
    return entries


def _catalog_entries() -> tuple[GSEClosedClassEntry, ...]:
    entries = _function_entries() + _auxiliary_entries()
    covered = {entry.lemma for entry in entries}
    for word, primitives in sorted(EXPONENTS.items()):
        if word in covered:
            continue
        role = "ADV" if word in _ADV_CLOSED else "ADP"
        entries.append(
            _entry(
                word,
                "modal" if set(primitives) & MODAL_PRIMES else "exponent",
                "adverb" if role == "ADV" else "preposition",
                (role,),
                primitives,
                {},
                [_origin("gse.curation.build_clean_closed_class", "EXPONENTS", word, primitives)],
            )
        )
    for word in sorted(_NEG | {prime.lower() for prime in MODAL_PRIMES if prime.lower() in _ADV_CLOSED}):
        lemma = _IRREGULAR_LEMMA.get(word, word)
        primitives = canonical_decomposition(lemma) or {}
        role = "PART" if word in _NEG else "ADV"
        entries.append(
            _entry(
                word,
                "negation" if role == "PART" else "modal",
                "particle" if role == "PART" else "adverb",
                (role,),
                primitives,
                {"lemma": lemma},
                [
                    _origin("gse.nlp.native", "_NEG" if role == "PART" else "_ADV_CLOSED", word, word),
                    _origin(
                        "gse.curation.external_sources.tier_0_dispatch", "canonical_decomposition", lemma, primitives
                    ),
                ],
            )
        )
    covered = {entry.lemma for entry in entries}
    for word in sorted(ZERO - covered):
        role = "ADP" if word in _ADP else "ADV"
        entries.append(
            _entry(
                word,
                "operator",
                "preposition" if role == "ADP" else "adverb",
                (role,),
                {},
                {},
                [_origin("gse.curation.build_clean_closed_class", "ZERO", word, {"declared_lexical_components": {}})],
            )
        )
    identities = [entry.entry_id for entry in entries]
    if len(set(identities)) != len(identities):
        raise ValueError("DUPLICATE_CLOSED_CLASS_DEFINITION")
    return tuple(sorted(entries, key=lambda entry: entry.entry_id))


@lru_cache(maxsize=1)
def _grammatical_identity_index() -> dict[tuple[str, str], tuple[str, ...]]:
    index: dict[tuple[str, str], list[str]] = {}
    for entry in _catalog_entries():
        for role in entry.grammar_roles:
            index.setdefault((entry.lemma, role), []).append(entry.entry_id)
    return {key: tuple(sorted(ids)) for key, ids in index.items()}


def grammatical_entry_ids(lemma: str, pos: str) -> tuple[str, ...]:
    """Exact grammar-role eligibility; callers must verify IDs exist in storage.

    No banks or spelling-only fallback are supplied. A NOUN cannot select its
    homographic modal/pronoun. Try the token's surface then its resolved lemma.
    """
    if not isinstance(lemma, str) or not isinstance(pos, str):
        raise ValueError("INVALID_GRAMMATICAL_IDENTITY_QUERY")
    return _grammatical_identity_index().get((lemma.strip().lower(), pos.upper()), ())


@lru_cache(maxsize=1)
def _grammatical_requirements() -> dict[str, str]:
    return {
        entry.entry_id: "MODAL_PROJECTION_REQUIRED"
        if any(entry.primitives.get(bank, 0) > 0 for bank in MODAL_PRIMES)
        else "LEXICAL_ABSTENTION_ALLOWED"
        for entry in _catalog_entries()
    }


def grammatical_requirement(entry_id: str) -> str:
    """Whether an identified native definition requires a modal projection.

    A syntactic modal can be tense-only (will/shall); its catalog category
    alone does not warrant a CAN/MUST/MAYBE bank. Requirements derive only
    from positive components explicitly present in the existing source row.
    """
    if not isinstance(entry_id, str):
        raise ValueError("INVALID_GRAMMATICAL_IDENTITY_QUERY")
    return _grammatical_requirements().get(entry_id, "UNKNOWN_GRAMMATICAL_DEFINITION")


class GSEClosedClassParser:
    def __init__(self):
        self.entries: dict[str, list[GSEClosedClassEntry]] = {}
        self._loaded = False

    def load(self) -> bool:
        entries: dict[str, list[GSEClosedClassEntry]] = {}
        for entry in _catalog_entries():
            entries.setdefault(entry.lemma, []).append(entry)
        self.entries = entries
        self._loaded = True
        return True

    def get_all_words(self) -> list[str]:
        if not self._loaded:
            self.load()
        return sorted(self.entries)

    def get_entries(self, word: str) -> tuple[GSEClosedClassEntry, ...]:
        if not self._loaded:
            self.load()
        return tuple(self.entries.get(word.lower(), ()))

    def to_primitives_for_entry(self, entry: GSEClosedClassEntry) -> dict[str, int]:
        if not isinstance(entry, GSEClosedClassEntry):
            raise ValueError("INVALID_CLOSED_CLASS_ENTRY")
        entry.__post_init__()
        return dict(entry.primitives)

    def to_primitives(self, word: str) -> dict[str, int]:
        """Legacy spelling-only consumers abstain on multiple definitions."""
        entries = self.get_entries(word)
        return self.to_primitives_for_entry(entries[0]) if len(entries) == 1 else {}
