"""Whole-population genus/differentia closure (Rohan, 2026-11-26).

The dictionary is a closed system of definitions, and every definition is a genus plus a differentia.
That structure is the warrant: no threshold, sample or vote admits anything here.

- **Axioms.** A tier-0 prime's definition (``prime_entries``) whose stored state settles its own
  nonzero bank is fully determined: its rule consequences, and 0 on every other bank. The curated
  closed-class grammar (``gse_closed_class``) is authoritative in its scope: its declared components,
  and 0 on every other bank.
- **Genus edge.** A WordNet sense's genus is its direct hypernyms, read from ``hypernym_paths()``
  sorted by synset names. A Wiktionary sense's genus is the source's own ``form_of``/``alt_of``
  target when it states one; otherwise the head ``definitional_decomposer`` parses from the gloss
  (its identity templates name an operand; its genus/differentia template a genus head). A genus
  word with several definitions carries all of them as possibilities (their union), never one
  chosen by frequency. A sense with several hypernyms is a kind of each (their intersection).
- **Differentia.** The clause heads ``definition_structure`` parses from the same gloss, each a
  defined entry with all its definitions as possibilities.
- **The constraint**, for every bank at once: where no differentia word can be nonzero the kind
  takes the genus's state, zeros included; where a differentia word can be nonzero the kind takes
  the differentia's nonzero values; where both are possible, the union. Unknown stays unknown.
- **Propagation** runs in passes to a fixpoint. Each narrowing is compiled into the release's own
  constraint state (``resolve_dictionary`` with the release's rules) over the entry's current
  domains, so a value never widens and no stored value changes.
- **Contradictions** are typed (``GenusDifferentiaContradiction``) with both causes. A contradicted
  entry keeps its state.

The derived values are their own channel (``CHANNEL``): never written as a source assertion, never
read back as evidence for anything but this closure and the word senses, which read them as member
evidence below every stated value (``word_senses.close_sense``).

Round 2 (Rohan, 2026-11-26, "Agreed on your reads. Please proceed"):

- **A differentia contributes its content, never its noun's identity.** On the identity banks
  (``identity_banks``: the NSM chart's substantives, relational substantives and life-and-death
  primes, with TIME, PLACE and WORDS, read from Goddard 2012 Table 1 and the catalog's bank map) the
  kind takes its genus's state whatever its differentia words are. A differentia head the gloss
  writes only with a capital is a name (a citation, a place), not differentia.
- **Root axioms.** Each synset of the reviewed anchor table (``_WARRANTED_ROOT_PRIMITIVES``) is
  its identity: that bank is +1. Nothing else is stipulated: its other banks follow the same law as
  every definition. An anchor synset with no definition in the release stands in the graph as a
  root of that identity only (``ROOT_PREFIX``), so its kinds still have a genus.
- **Catalog axioms.** A prime-linked definition whose own bank the release leaves open takes the
  bank and sign the NSM catalog maps its unit to (EXACT or ADAPTED), then is fully determined like
  every prime axiom. A unit the catalog gives no sign stays open.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from .engine import Assertion, DomainRestriction, Relation
from .foundation import BANKS, definition_context
from .resolution import resolve_dictionary

FORMAT = "GSE.genus-differentia-closure/1"
CHANNEL = "derived:genus-differentia"
FAMILY = "derived"
EXCLUDED_POS = frozenset({"name"})  # proper names are handled elsewhere (design, Scope)
CONTENT_POS = frozenset({"noun", "verb", "adj", "adv"})
WORDNET_GENUS_POS = frozenset({"noun", "verb"})  # WordNet states hypernyms for nouns and verbs only

# A domain is three bits per bank (-1, 0, +1), all 56 banks packed into one integer.
SIGN_BIT = {-1: 1, 0: 2, 1: 4}
N = len(BANKS)
FULL = int("111" * N, 2)
ZERO_BITS = sum(SIGN_BIT[0] << 3 * i for i in range(N))
LOW_BITS = sum(SIGN_BIT[-1] << 3 * i for i in range(N))
HIGH_BITS = sum(SIGN_BIT[1] << 3 * i for i in range(N))
NONZERO_BITS = LOW_BITS | HIGH_BITS
ROOT_PREFIX = "wordnet_root:"  # an anchor synset the release has no definition of

# The identity banks (decision 2): the NSM chart categories whose primes say what a thing IS, read
# from the published category table; TIME and PLACE are the nominal primes of the time and space
# categories ("life/place/time"), and WORDS is named in Rohan's decision (Goddard 2012 files it
# under speech).
CATEGORY_TABLE = "data/external/references/goddard-2012-primes-molecules-templates.txt"
IDENTITY_CATEGORIES = ("substantives", "relational substantives", "life and death")
IDENTITY_UNITS = ("TIME", "PLACE", "WORDS")


def pack(domains: Mapping[str, Iterable[int]]) -> int:
    """Bank domains to the packed form; a bank not named is unknown."""
    packed = 0
    for i, bank in enumerate(BANKS):
        values = domains.get(bank, (-1, 0, 1))
        packed |= sum(SIGN_BIT[value] for value in values) << 3 * i
    return packed


def bank_values(packed: int, i: int) -> tuple[int, ...]:
    bits = packed >> 3 * i & 7
    return tuple(value for value in (-1, 0, 1) if bits & SIGN_BIT[value])


def unpack(packed: int) -> dict[str, list[int]]:
    return {bank: list(bank_values(packed, i)) for i, bank in enumerate(BANKS)}


def _spread(flags: int) -> int:
    """A per-bank flag held in any of a bank's three bits, set on all three."""
    low = (flags | flags >> 1 | flags >> 2) & LOW_BITS
    return low | low << 1 | low << 2


def empty_banks(packed: int) -> list[int]:
    present = _spread(packed) & LOW_BITS
    return [i for i in range(N) if not present >> 3 * i & 1]


def open_banks(packed: int) -> list[int]:
    return [i for i in range(N) if len(bank_values(packed, i)) > 1]


def only(i: int, value: int) -> int:
    """Every bank unknown except bank ``i``, which holds one value."""
    return FULL & ~(7 << 3 * i) | SIGN_BIT[value] << 3 * i


def mask(banks: Iterable[str]) -> int:
    """All three bits of each named bank."""
    return sum(7 << 3 * BANKS.index(bank) for bank in set(banks))


# ---------------------------------------------------------------------------------------------
# The identity banks and the catalog's own banks (round 2)
# ---------------------------------------------------------------------------------------------


def _normal(exponent: str) -> str:
    """A chart exponent for matching: parentheticals dropped, lower case, no plural s."""
    return re.sub(r"\([^)]*\)", "", exponent).strip().lower().removesuffix("s")


def category_table(text: str) -> dict[str, tuple[str, ...]]:
    """Table 1 of Goddard (2012), "Semantic primes (English exponents), grouped into related
    categories": each category and its exponents, as printed in two columns. A row with no
    category continues the exponents above it; a category ending in a comma continues below."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("Table 1:"))
    groups: list[tuple[list[str], list[str]]] = []
    for line in lines[start + 1 :]:
        if not line.strip():
            break
        left, right = (re.split(r"\s{2,}", line.strip(), maxsplit=1) + [""])[:2]
        if groups and (not right or groups[-1][1][-1].endswith(",")):
            groups[-1][0].append(left)
            if right:
                groups[-1][1].append(right)
        else:
            groups.append(([left], [right]))
    return {
        " ".join(rights): tuple(e.strip() for e in " ".join(lefts).split(",") if e.strip()) for lefts, rights in groups
    }


def catalog_signs(units: Iterable[Mapping]) -> dict[str, tuple[str, int, str, str]]:
    """unit id -> (bank, sign, code, note) for every chart unit the catalog maps EXACT or ADAPTED."""
    return {
        unit["unit_id"]: (
            unit["mapping"]["bank"],
            unit["mapping"]["value"],
            unit["mapping"]["code"],
            unit["mapping"]["note"],
        )
        for unit in units
        if unit["mapping"]["code"] in ("EXACT", "ADAPTED") and unit["mapping"]["bank"] in BANKS
    }


def identity_banks(table_text: str, units: Sequence[Mapping]) -> dict[str, tuple[str, ...]]:
    """bank -> the chart units that make it an identity bank.

    The exponents of ``IDENTITY_CATEGORIES`` and the table exponents with an ``IDENTITY_UNITS``
    allolex, each matched to the catalog unit with that form (``catalog.catalog_inventory``), whose
    EXACT or ADAPTED mapping names the bank. An exponent with no mapped unit is an error, not a skip.
    """
    table = category_table(table_text)
    named = {_normal(unit) for unit in IDENTITY_UNITS}
    exponents = [e for category in IDENTITY_CATEGORIES for e in table[category]]
    exponents += [e for row in table.values() for e in row if {_normal(a) for a in e.split("~")} & named]
    signs = catalog_signs(units)
    found: dict[str, set[str]] = defaultdict(set)
    for exponent in exponents:
        wanted = {_normal(a) for a in exponent.split("~")}
        matched = [u["unit_id"] for u in units if {_normal(f) for f in u["forms"]} & wanted and u["unit_id"] in signs]
        if not matched:
            raise ValueError("IDENTITY_EXPONENT_WITHOUT_CATALOG_BANK:" + exponent)
        for unit_id in matched:
            found[signs[unit_id][0]].add(unit_id)
    return {bank: tuple(sorted(found[bank])) for bank in sorted(found, key=BANKS.index)}


@dataclass(frozen=True)
class Edge:
    """One definition's genus and differentia, each a word with all its definitions."""

    entry_id: str
    pos: str
    template: str
    genus: tuple[tuple[str, tuple[str, ...]], ...]  # (label, entries): each label is a genus it is a kind of
    differentia: tuple[tuple[str, tuple[str, ...]], ...] = ()  # (word, entries)

    def targets(self) -> set[str]:
        return {entry for _, entries in self.genus + self.differentia for entry in entries}

    def as_json(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "pos": self.pos,
            "template": self.template,
            "genus": [[label, list(entries)] for label, entries in self.genus],
            "differentia": [[word, list(entries)] for word, entries in self.differentia],
        }

    @classmethod
    def from_json(cls, raw: Mapping) -> Edge:
        return cls(
            raw["entry_id"],
            raw["pos"],
            raw["template"],
            tuple((label, tuple(entries)) for label, entries in raw["genus"]),
            tuple((word, tuple(entries)) for word, entries in raw["differentia"]),
        )


class GenusDifferentiaContradiction(ValueError):
    """The closure meets a value it cannot hold: both causes, never an overwrite."""

    def __init__(self, kind: str, entry_id: str, bank: str | None, stated: dict, derived: dict):
        super().__init__(f"{kind}:{entry_id}:{bank}")
        self.kind, self.entry_id, self.bank, self.stated, self.derived = kind, entry_id, bank, stated, derived

    def as_record(self) -> dict:
        return {
            "kind": self.kind,
            "entry_id": self.entry_id,
            "bank": self.bank,
            "stated": self.stated,
            "derived": self.derived,
        }


# ---------------------------------------------------------------------------------------------
# Parsing: the genus and differentia of one definition
# ---------------------------------------------------------------------------------------------


def wordnet_genus(synset_name: str) -> tuple[str, ...]:
    """The direct hypernyms (instance hypernyms included), from paths sorted by synset names."""
    from nltk.corpus import wordnet

    paths = sorted(wordnet.synset(synset_name).hypernym_paths(), key=lambda path: [node.name() for node in path])
    return tuple(sorted({path[-2].name() for path in paths if len(path) > 1}))


def parse_gloss(lemma: str, pos: str, gloss: str) -> dict:
    """The definition linker's parse of one gloss: its template, genus head and differentia heads.

    Identity templates (inflection, plural, comparative, alternative form, adverb of manner) name
    the operand the definition is identical to. Negation, relational and attributive templates
    ("not X", "relating to X", "having X") do not state a kind of anything, so they carry no
    genus here. A gloss with a definitional negative anywhere is marked, because the parser does
    not say which differentia the negative scopes over.
    """
    from GSE.curation.decomposition.definition_linker import _IDENTITY_OPS
    from GSE.curation.decomposition.definition_structure import extract_structure
    from GSE.curation.decomposition.definitional_decomposer import _SENTENCE_SCALE_WORDS, _clean_operand, classify
    from GSE.curation.external_sources.tier_0_dispatch import is_tier_0

    if lemma.lower() in _SENTENCE_SCALE_WORDS and not is_tier_0(lemma):
        return {"template": "sentence_scale", "genus": None, "differentia": [], "negated": False}
    template, operation, operand, _ = classify(gloss or "")
    if template and operation in _IDENTITY_OPS:
        return {
            "template": template,
            "genus": _clean_operand(operand or "") or None,
            "differentia": [],
            "negated": False,
        }
    if template:
        return {"template": template, "genus": None, "differentia": [], "negated": False}
    structure = extract_structure(lemma, pos, "x", gloss or "")
    # "Any of various similar works issued in England ...": a name is not a genus. (A WordNet
    # sense's genus is its hypernyms, so this matters only where the parse names the genus.)
    words = " ".join(re.findall(r"[^\W\d_][\w'’-]*|[.;:!?]", gloss or ""))
    name_genus = bool(structure.genus) and is_name(structure.genus, words)
    return {
        "template": "genus_differentia",
        **({"name_genus": structure.genus} if name_genus else {}),
        "genus": None if structure.note.startswith("circular") or name_genus else structure.genus,
        "differentia": [item.head_lemma for item in structure.differentia if not is_name(item.head_lemma, item.text)],
        "negated": bool(structure.negations),
    }


def is_name(head: str, text: str) -> bool:
    """A differentia head the gloss writes only with a capital is a name (a citation, a place),
    not differentia: "(Robert ...)", "in Scotland"."""
    words = text.split()
    written = [(k, word) for k, word in enumerate(words) if word.lower() == head]
    # A capital that opens a sentence says nothing about a name.
    inside = [word for k, word in written if k and words[k - 1] not in (".", ";", ":", "!", "?")]
    return (
        bool(inside) and all(word[:1].isupper() for word in inside) and all(word[:1].isupper() for _, word in written)
    )


def synset_of(entry_id: str) -> str:
    """The WordNet synset name of a ``wordnet:`` definition (identifiers are percent-encoded)."""
    from urllib.parse import unquote

    return unquote(entry_id.rsplit(":", 1)[1])


def operand_pos(template: str, pos: str) -> str:
    """The part of speech the operand is read in: an adverb of manner reduces to its adjective."""
    return "adj" if template == "adv_manner" else pos


@dataclass
class Index:
    """The release's definitions by lemma, by (lemma, POS) and by WordNet synset."""

    by_lemma: dict[str, tuple[str, ...]]
    by_lemma_pos: dict[tuple[str, str], tuple[str, ...]]
    by_synset: dict[str, tuple[str, ...]]

    @classmethod
    def build(cls, rows: Iterable[tuple[str, str, str]]) -> Index:
        by_lemma, by_lemma_pos, by_synset = defaultdict(list), defaultdict(list), defaultdict(list)
        for entry_id, lemma, pos in rows:
            if pos in EXCLUDED_POS:
                continue
            by_lemma[lemma].append(entry_id)
            by_lemma_pos[(lemma, pos)].append(entry_id)
            if entry_id.startswith("wordnet:"):
                by_synset[synset_of(entry_id)].append(entry_id)

        def freeze(mapping):
            return {key: tuple(sorted(values)) for key, values in mapping.items()}

        return cls(freeze(by_lemma), freeze(by_lemma_pos), freeze(by_synset))


def build_edge(
    entry_id: str,
    lemma: str,
    pos: str,
    parsed: Mapping | None,
    index: Index,
    *,
    hypernyms: tuple[str, ...] = (),
    form_of: tuple[str, ...] = (),
    withdrawn: frozenset[str] = frozenset(),
    roots: frozenset[str] = frozenset(),
) -> tuple[Edge | None, str]:
    """The definition's edge, or None and the reason it has none.

    ``roots``: anchor synsets the release has no definition of; such a hypernym is the root
    ``ROOT_PREFIX + name``, which holds the anchor's identity only.
    """
    if pos not in CONTENT_POS:
        return None, "NOT_CONTENT_POS"
    if entry_id.startswith("wordnet:"):
        if pos not in WORDNET_GENUS_POS:
            return None, "WORDNET_NO_HYPERNYM_POS"
        if not hypernyms:
            return None, "WORDNET_ROOT"
        if parsed is None or parsed["template"] != "genus_differentia" or parsed["negated"]:
            return None, "WORDNET_DIFFERENTIA_UNPARSED"
        # A prime-linked synset that review withdrew as an identity root does not carry its axiom
        # to the kinds WordNet files under it (design, SP-1: "words and titles are not parts").
        genus = tuple((name, _synset_entries(name, index, withdrawn, roots)) for name in hypernyms)
        template = "wordnet_hypernym"
    elif form_of:
        genus = tuple((word, index.by_lemma_pos.get((word, pos), ())) for word in form_of)
        return _edge(entry_id, pos, "wiktionary_form_of", genus, ()), ""
    else:
        if parsed is None:
            return None, "UNPARSED"
        if parsed["template"] == "sentence_scale":
            return None, "SENTENCE_SCALE"
        if parsed.get("name_genus"):
            return None, "NO_GENUS:name_genus"
        if parsed["genus"] is None:
            return None, "NO_GENUS:" + parsed["template"]
        if parsed["negated"]:
            return None, "NEGATED_DIFFERENTIA"
        word = parsed["genus"]
        entries = index.by_lemma_pos.get((word, operand_pos(parsed["template"], pos)), ())
        if not entries:
            return None, "GENUS_NOT_DEFINED"
        genus = ((word, entries),)
        template = "wiktionary_" + parsed["template"]
    differentia = tuple((word, index.by_lemma.get(word, ())) for word in parsed["differentia"])
    return _edge(entry_id, pos, template, genus, differentia), ""


def _synset_entries(name: str, index: Index, withdrawn: frozenset[str], roots: frozenset[str]) -> tuple[str, ...]:
    if name in withdrawn:
        return ()
    if name not in index.by_synset and name in roots:
        return (ROOT_PREFIX + name,)
    return index.by_synset.get(name, ())


def _edge(entry_id, pos, template, genus, differentia):
    # A definition is not its own genus or differentia; a self-reference adds nothing.
    genus = tuple((label, tuple(e for e in entries if e != entry_id)) for label, entries in genus)
    differentia = tuple((word, tuple(e for e in entries if e != entry_id)) for word, entries in differentia)
    return Edge(entry_id, pos, template, genus, differentia)


# ---------------------------------------------------------------------------------------------
# The constraint
# ---------------------------------------------------------------------------------------------


def _union(entries: tuple[str, ...], state: Mapping[str, int]) -> int:
    if not entries:
        return FULL  # an undefined word: unknown on every bank
    packed = 0
    for entry in entries:
        packed |= state[entry]
    return packed


def compile_constraint(edge: Edge, state: Mapping[str, int], identity: int = 0) -> int:
    """The packed domain the genus plus the differentia allow, all banks at once.

    ``identity`` masks the identity banks: there a differentia word's own values never carry, and
    the kind takes its genus's state.
    """
    genus = FULL
    for _label, entries in edge.genus:
        genus &= _union(entries, state)
    gaps = empty_banks(genus)
    if gaps:
        raise GenusDifferentiaContradiction(
            "GENUS_CONFLICT",
            edge.entry_id,
            BANKS[gaps[0]],
            {"genus": _explain(edge.genus[:1], state, gaps[0])},
            {"genus": _explain(edge.genus[1:], state, gaps[0])},
        )
    if not edge.differentia:
        return genus
    untouched, contribution = ZERO_BITS, 0
    for _word, entries in edge.differentia:
        values = _union(entries, state)
        untouched &= values
        contribution |= values & NONZERO_BITS
    content = genus & _spread(untouched & ZERO_BITS) | contribution
    return content & ~identity | genus & identity


def _explain(groups, state, i) -> list[dict]:
    return [
        {"word": label, "entries": len(entries), "values": list(bank_values(_union(entries, state), i))}
        for label, entries in groups
    ]


def explain(edge: Edge, state: Mapping[str, int], i: int) -> dict:
    """Why the constraint allows what it allows on one bank: each genus and differentia word's values."""
    return {
        "template": edge.template,
        "genus": _explain(edge.genus, state, i),
        "differentia": _explain(edge.differentia, state, i),
    }


def _floor(entry_id: str, packed: int) -> tuple[tuple[Assertion, ...], tuple[DomainRestriction, ...]]:
    """The entry's current domains as in-memory evidence: singletons asserted, pairs restricted."""
    assertions, restrictions = [], []
    record = "floor:" + entry_id
    for i, bank in enumerate(BANKS):
        values = bank_values(packed, i)
        if len(values) == 1:
            assertions.append(Assertion(bank, values[0], CHANNEL, record, FAMILY))
        elif len(values) == 2:
            restrictions.append(DomainRestriction(bank, values, CHANNEL, record, FAMILY))
    return tuple(assertions), tuple(restrictions)


def derived_relations(allowed: int) -> tuple[Relation, ...]:
    """The constraint as approved unary relations, one per narrowed bank."""
    return tuple(
        Relation(
            f"{CHANNEL}:{bank}",
            (bank,),
            tuple((value,) for value in bank_values(allowed, i)),
            (CHANNEL,),
            authority="foundational",
            approved=True,
        )
        for i, bank in enumerate(BANKS)
        if allowed >> 3 * i & 7 != 7
    )


def receipts(resolution) -> list[dict]:
    """The solver receipts a measurement of the joint space needs."""
    kept = ("INFERENCE_SCOPE", "JOINT_CHECK", "SOLVER_LIMIT", "CONDITIONAL_EXCEPTION")
    return [dict(row) for row in resolution.trace if row.get("kind") in kept]


def resolve_entry(
    entry_id: str,
    pos: str,
    current: int,
    allowed: int,
    rules: tuple[Relation, ...],
    stored_exceptions,
    cause: dict,
):
    """Compile the constraint into the release's constraint state over the entry's current domains.

    Returns (packed domains, resolution), or None when nothing narrows. Raises a typed
    contradiction for an empty bank, a rule conflict, a new conditional exception or a solver limit.
    """
    narrowed = current & allowed
    gaps = empty_banks(narrowed)
    if gaps:
        i = gaps[0]
        raise GenusDifferentiaContradiction(
            "STORED_CONFLICT",
            entry_id,
            BANKS[i],
            {"values": list(bank_values(current, i))},
            {"allowed": list(bank_values(allowed, i)), **cause},
        )
    if narrowed == current:
        return None
    assertions, restrictions = _floor(entry_id, current)
    resolution = resolve_dictionary(
        BANKS, assertions, rules + derived_relations(allowed), definition_context(pos), domain_restrictions=restrictions
    )
    if resolution.code == "CONFLICT":
        rows = [dict(conflict) for conflict in resolution.conflicts]
        bank = next((row.get("bank") for row in rows if row.get("bank")), None)
        raise GenusDifferentiaContradiction(
            "RULE_CONFLICT", entry_id, bank, {"conflicts": _jsonable(rows)}, {"allowed": unpack(allowed), **cause}
        )
    if any(row.get("kind") == "SOLVER_LIMIT" for row in resolution.trace):
        raise GenusDifferentiaContradiction("SOLVER_LIMIT", entry_id, None, {}, cause)
    excepted = {
        rule for row in resolution.trace if row.get("kind") == "CONDITIONAL_EXCEPTION" for rule in row["rule_ids"]
    }
    if excepted and excepted - set(stored_exceptions(entry_id)):
        raise GenusDifferentiaContradiction(
            "CONDITIONAL_EXCEPTION",
            entry_id,
            None,
            {"rules": sorted(excepted - set(stored_exceptions(entry_id)))},
            {"allowed": unpack(allowed), **cause},
        )
    packed = pack(resolution.domains)
    if packed & ~current:
        raise RuntimeError("GENUS_DIFFERENTIA_WIDENED:" + entry_id)  # a defect, never a lexical outcome
    return packed, resolution


def _jsonable(value):
    return json.loads(json.dumps(value, default=list))


# ---------------------------------------------------------------------------------------------
# Axioms
# ---------------------------------------------------------------------------------------------


def axiom_entries(conn: sqlite3.Connection) -> list[str]:
    """Prime-linked definitions and the curated closed-class grammar."""
    (raw,) = conn.execute("SELECT value FROM builder_metadata WHERE key='prime_entries'").fetchone()
    linked = {entry for entries in json.loads(raw).values() for entry in entries}
    closed = {
        row[0]
        for row in conn.execute("SELECT entry_id FROM definition_states WHERE entry_id LIKE 'gse_closed_class:%'")
    }
    return sorted(linked | closed)


def _settles_nonzero(packed: int) -> bool:
    return any(bank_values(packed, i) in ((-1,), (1,)) for i in range(N))


def determine_axiom(entry_id: str, pos: str, current: int, rules, stored_exceptions, own=None):
    """A fully determined axiom: its current values and 0 on every open bank, under the rules.

    A prime counts only where its own nonzero bank is settled, by the release or, where the release
    leaves it open, by ``own`` = (bank, sign, warrant), the NSM catalog's mapping of its unit. A
    zero a rule forbids is a typed contradiction; the other zeros still hold.
    """
    is_prime = not entry_id.startswith("gse_closed_class:")
    base, cause = FULL, {"axiom": "prime" if is_prime else "gse_closed_class"}
    if is_prime and not _settles_nonzero(current):
        if own is None:
            return None, [
                GenusDifferentiaContradiction(
                    "AXIOM_OWN_BANK_OPEN", entry_id, None, {"values": "no settled nonzero bank"}, {"axiom": "prime"}
                ).as_record()
            ]
        bank, sign, warrant = own
        base, cause = only(BANKS.index(bank), sign), {"axiom": "nsm_catalog", "bank": bank, "sign": sign, **warrant}
        try:
            resolve_entry(entry_id, pos, current, base, rules, stored_exceptions, cause)
        except GenusDifferentiaContradiction as error:
            error.kind = "AXIOM_CATALOG_" + error.kind
            return None, [error.as_record()]
    target = current & base
    zeros = [i for i in open_banks(target) if 0 in bank_values(target, i)]
    contradictions, kept = [], []
    allowed = base
    for i in zeros:
        allowed &= only(i, 0)
    try:
        result = resolve_entry(entry_id, pos, current, allowed, rules, stored_exceptions, cause)
        return result, contradictions
    except GenusDifferentiaContradiction:
        pass
    for i in zeros:  # each zero alone, then the survivors together
        try:
            resolve_entry(entry_id, pos, current, base & only(i, 0), rules, stored_exceptions, cause)
            kept.append(i)
        except GenusDifferentiaContradiction as error:
            error.kind = "AXIOM_" + error.kind
            error.bank = BANKS[i]
            contradictions.append(error.as_record())
    allowed = base
    for i in kept:
        allowed &= only(i, 0)
    try:
        return resolve_entry(entry_id, pos, current, allowed, rules, stored_exceptions, cause), contradictions
    except GenusDifferentiaContradiction as error:
        error.kind = "AXIOM_JOINT_" + error.kind
        return None, contradictions + [error.as_record()]


def root_axiom(entry_id: str, pos: str, current: int, banks: Iterable[str], rules, stored_exceptions, warrant: dict):
    """A root axiom states what the root IS: each anchor bank +1, under the rules. Nothing else is
    stipulated; the root's other banks follow the same law as every definition.

    Returns (result or None, contradiction records)."""
    allowed = FULL
    for bank in banks:
        allowed &= only(BANKS.index(bank), 1)
    try:
        return resolve_entry(entry_id, pos, current, allowed, rules, stored_exceptions, warrant), []
    except GenusDifferentiaContradiction as error:
        error.kind = "ROOT_AXIOM_" + error.kind
        return None, [error.as_record()]


# ---------------------------------------------------------------------------------------------
# The fixpoint
# ---------------------------------------------------------------------------------------------


@dataclass
class Closure:
    state: dict[str, int]
    changed_in: dict[str, int] = field(default_factory=dict)  # entry -> the pass that last narrowed it
    traces: dict[str, list[dict]] = field(default_factory=dict)  # entry -> its last resolution's receipts
    contradictions: list[dict] = field(default_factory=list)
    passes: list[dict] = field(default_factory=list)
    axioms: dict[str, dict] = field(default_factory=dict)  # entry -> what made it an axiom and the cells it settled


def _settled(before: int, after: int) -> dict[str, int]:
    return {
        BANKS[i]: bank_values(after, i)[0]
        for i in range(N)
        if len(bank_values(after, i)) == 1 and len(bank_values(before, i)) > 1
    }


def close(
    stored: Mapping[str, int],
    pos_of: Mapping[str, str],
    edges: Mapping[str, Edge],
    axioms: Iterable[str],
    rules: tuple[Relation, ...],
    stored_exceptions,
    progress=None,
    *,
    identity: int = 0,
    own_signs: Mapping[str, tuple[str, int, dict]] | None = None,
    roots: Mapping[str, tuple[tuple[str, ...], dict]] | None = None,
) -> Closure:
    """Run the genus/differentia constraint over the whole graph until no pass changes anything.

    Pass 0 determines the axioms: the primes and closed class (``own_signs`` supplies a prime's
    catalog bank where the release leaves it open), then the root axioms (``roots``: entry ->
    (anchor banks, warrant)). Each later pass recomputes, from the previous pass's state, every
    definition one of whose genus or differentia words changed (pass 1: every definition with an
    edge), in sorted order. Domains only narrow, so the passes end.
    """
    closure = Closure(dict(stored))
    contradicted: set[str] = set()
    changed = []
    axioms = sorted(axioms)
    own_signs, roots = own_signs or {}, roots or {}

    def settle(entry_id, result, record):
        before = closure.state[entry_id]
        closure.state[entry_id], resolution = result
        closure.changed_in[entry_id] = 0
        closure.traces[entry_id] = receipts(resolution)
        settled = closure.axioms.get(entry_id, {}).get("settled", {})
        record = {**record, "settled": {**settled, **_settled(before, closure.state[entry_id])}}
        closure.axioms[entry_id] = {**closure.axioms.get(entry_id, {}), **record}
        changed.append(entry_id)

    for entry_id in axioms:
        own = own_signs.get(entry_id)
        result, errors = determine_axiom(entry_id, pos_of[entry_id], stored[entry_id], rules, stored_exceptions, own)
        closure.contradictions.extend(errors)
        if result is not None:
            kind = "prime" if not entry_id.startswith("gse_closed_class:") else "gse_closed_class"
            if kind == "prime" and own is not None and not _settles_nonzero(stored[entry_id]):
                kind = "nsm_catalog"
            settle(
                entry_id,
                result,
                {"kind": kind, **({"bank": own[0], "sign": own[1], **own[2]} if kind == "nsm_catalog" else {})},
            )
    for entry_id in sorted(roots):
        banks, warrant = roots[entry_id]
        result, errors = root_axiom(
            entry_id, pos_of[entry_id], closure.state[entry_id], banks, rules, stored_exceptions, warrant
        )
        closure.contradictions.extend(errors)
        if result is not None:
            settle(entry_id, result, {"kind": "wordnet_root", "banks": list(banks), **warrant})
    closure.passes.append({"pass": 0, "evaluated": len(axioms) + len(roots), "changed": len(set(changed))})
    dependents: dict[str, set[str]] = defaultdict(set)
    for entry_id, edge in edges.items():
        for target in edge.targets():
            dependents[target].add(entry_id)
    work = sorted(edges)
    number = 0
    while work:
        number += 1
        snapshot = dict(closure.state)
        changed, counts = [], Counter()
        for entry_id in work:
            if entry_id in contradicted:
                continue
            edge = edges[entry_id]
            counts["evaluated"] += 1
            try:
                allowed = compile_constraint(edge, snapshot, identity)
                if allowed == FULL:
                    continue
                counts["constrained"] += 1
                cause = {"edge": edge.template}
                result = resolve_entry(entry_id, edge.pos, snapshot[entry_id], allowed, rules, stored_exceptions, cause)
            except GenusDifferentiaContradiction as error:
                record = error.as_record()
                if error.bank in BANKS:
                    record["derived"]["explanation"] = explain(edge, snapshot, BANKS.index(error.bank))
                record["pass"] = number
                closure.contradictions.append(record)
                contradicted.add(entry_id)
                counts["contradicted"] += 1
                continue
            if result is None:
                continue
            closure.state[entry_id], resolution = result
            closure.changed_in[entry_id] = number
            closure.traces[entry_id] = receipts(resolution)
            changed.append(entry_id)
        closure.passes.append({"pass": number, **counts, "changed": len(changed)})
        if progress:
            progress(closure.passes[-1])
        work = sorted({dependent for entry_id in changed for dependent in dependents.get(entry_id, ())})
    return closure


def open_census(closure: Closure, edges: Mapping[str, Edge], limit: int = 25, identity: int = 0) -> dict:
    """What keeps each open bank of an edged definition open: its genus, its differentia, or a contradiction.

    On an identity bank no differentia word touches the kind, so only its genus can keep it open."""
    reasons, genus_words, differentia_words = Counter(), Counter(), Counter()
    contradicted = {row["entry_id"] for row in closure.contradictions}
    state = closure.state
    for entry_id, edge in edges.items():
        packed = state[entry_id]
        banks = open_banks(packed)
        if not banks:
            continue
        if entry_id in contradicted:
            reasons["CONTRADICTED"] += len(banks)
            continue
        unions = [(label, _union(entries, state)) for label, entries in edge.genus]
        words = [(word, _union(entries, state)) for word, entries in edge.differentia]
        for i in banks:
            touched = [
                word for word, values in words if values >> 3 * i & 7 != SIGN_BIT[0] and not identity >> 3 * i & 7
            ]
            open_genus = [label for label, values in unions if len(bank_values(values, i)) > 1]
            if touched:
                reasons["DIFFERENTIA_WORD_OPEN_OR_NONZERO"] += 1
                differentia_words.update(touched)
            elif open_genus:
                reasons["GENUS_OPEN"] += 1
                genus_words.update(open_genus)
            else:
                reasons["OTHER"] += 1
    return {
        "open_banks_by_reason": dict(reasons),
        "genus_keeping_most_banks_open": genus_words.most_common(limit),
        "differentia_keeping_most_banks_open": differentia_words.most_common(limit),
    }
