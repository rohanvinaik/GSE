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
read back as evidence for anything but this closure.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
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
    return {
        "template": "genus_differentia",
        "genus": None if structure.note.startswith("circular") else structure.genus,
        "differentia": [item.head_lemma for item in structure.differentia],
        "negated": bool(structure.negations),
    }


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
) -> tuple[Edge | None, str]:
    """The definition's edge, or None and the reason it has none."""
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
        genus = tuple((name, () if name in withdrawn else index.by_synset.get(name, ())) for name in hypernyms)
        template = "wordnet_hypernym"
    elif form_of:
        genus = tuple((word, index.by_lemma_pos.get((word, pos), ())) for word in form_of)
        return _edge(entry_id, pos, "wiktionary_form_of", genus, ()), ""
    else:
        if parsed is None:
            return None, "UNPARSED"
        if parsed["template"] == "sentence_scale":
            return None, "SENTENCE_SCALE"
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


def compile_constraint(edge: Edge, state: Mapping[str, int]) -> int:
    """The packed domain the genus plus the differentia allow, all banks at once."""
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
    return genus & _spread(untouched & ZERO_BITS) | contribution


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


def determine_axiom(entry_id: str, pos: str, current: int, rules, stored_exceptions):
    """A fully determined axiom: its current values and 0 on every open bank, under the rules.

    A prime counts only where its own nonzero bank is settled. A zero a rule forbids is a typed
    contradiction; the other zeros still hold.
    """
    is_prime = not entry_id.startswith("gse_closed_class:")
    if is_prime and not any(bank_values(current, i) in ((-1,), (1,)) for i in range(N)):
        return None, [
            GenusDifferentiaContradiction(
                "AXIOM_OWN_BANK_OPEN", entry_id, None, {"values": "no settled nonzero bank"}, {"axiom": "prime"}
            ).as_record()
        ]
    cause = {"axiom": "prime" if is_prime else "gse_closed_class"}
    zeros = [i for i in open_banks(current) if 0 in bank_values(current, i)]
    contradictions, kept = [], []
    allowed = FULL
    for i in zeros:
        allowed &= ~(7 << 3 * i) | SIGN_BIT[0] << 3 * i
    try:
        result = resolve_entry(entry_id, pos, current, allowed, rules, stored_exceptions, cause)
        return result, contradictions
    except GenusDifferentiaContradiction:
        pass
    for i in zeros:  # each zero alone, then the survivors together
        single = FULL & ~(7 << 3 * i) | SIGN_BIT[0] << 3 * i
        try:
            resolve_entry(entry_id, pos, current, single, rules, stored_exceptions, cause)
            kept.append(i)
        except GenusDifferentiaContradiction as error:
            error.kind = "AXIOM_" + error.kind
            error.bank = BANKS[i]
            contradictions.append(error.as_record())
    allowed = FULL
    for i in kept:
        allowed &= ~(7 << 3 * i) | SIGN_BIT[0] << 3 * i
    try:
        return resolve_entry(entry_id, pos, current, allowed, rules, stored_exceptions, cause), contradictions
    except GenusDifferentiaContradiction as error:
        error.kind = "AXIOM_JOINT_" + error.kind
        return None, contradictions + [error.as_record()]


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


def close(
    stored: Mapping[str, int],
    pos_of: Mapping[str, str],
    edges: Mapping[str, Edge],
    axioms: Iterable[str],
    rules: tuple[Relation, ...],
    stored_exceptions,
    progress=None,
) -> Closure:
    """Run the genus/differentia constraint over the whole graph until no pass changes anything.

    Pass 0 determines the axioms. Each later pass recomputes, from the previous pass's state, every
    definition one of whose genus or differentia words changed (pass 1: every definition with an
    edge), in sorted order. Domains only narrow, so the passes end.
    """
    closure = Closure(dict(stored))
    contradicted: set[str] = set()
    changed = []
    axioms = sorted(axioms)
    for entry_id in axioms:
        result, errors = determine_axiom(entry_id, pos_of[entry_id], stored[entry_id], rules, stored_exceptions)
        closure.contradictions.extend(errors)
        if result is not None:
            closure.state[entry_id], resolution = result
            closure.changed_in[entry_id] = 0
            closure.traces[entry_id] = receipts(resolution)
            changed.append(entry_id)
    closure.passes.append({"pass": 0, "evaluated": len(axioms), "changed": len(changed)})
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
                allowed = compile_constraint(edge, snapshot)
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


def open_census(closure: Closure, edges: Mapping[str, Edge], limit: int = 25) -> dict:
    """What keeps each open bank of an edged definition open: its genus, its differentia, or a contradiction."""
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
            touched = [word for word, values in words if values >> 3 * i & 7 != SIGN_BIT[0]]
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
