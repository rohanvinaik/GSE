"""The Wiktionary binding: Wiktionary senses joined to the readings they name (design E8, rebuild task 6.2).

F080: "I don't think we EVER need the raw gloss text". A Wiktionary sense is bound only through its structured
fields, read from the native sense record (`STRUCTURED_FIELDS`). Its glosses are never read.

- `form_of` and `alt_of`: an inflection or a variant has the meaning of its target. The sense is bound to the
  target lemma's readings in its own part of speech. With one reading, that is an identity edge. With several, it
  is an identity obligation, F073's form: the sense means one of these.
- `synonyms` (on the sense): the same, as synonymy candidates.
- The anchor alignment. `links` are the words the sense's editors linked. Each linked word gives its WordNet
  synsets. The candidates are the WordNet readings of the sense's own lemma and part of speech. The sense aligns to
  a candidate only when exactly one candidate has a linked word's synset among its kind-of ancestors, or as itself
  (`inheritance`'s kind-of families). With no such candidate, or two or more, it abstains, with its reason. This is
  set logic over editor links and the kind-of graph, with no score and no margin.
- `topics`, and categories of a natively typed domain kind (`DOMAIN_KINDS`), are domain facts named
  `wiktionary_topic=<t>`. They are guard facts, not edges.

Every identity is proposed, never known (E8: "An alignment is a proposed identity: content crosses it as an
interpolated default, suspended on any conflict"). The output is in the inheritance graph's shape:
- `groups`: a node per bound reading outside WordNet, keyed by its reading id. WordNet nodes are synsets
  (`inheritance.wordnet_groups`).
- `links`: `(family, giver, receiver)`, each identity in both directions.
- `classes`: readings joined by an alignment, a `form_of` or an `alt_of` identity share a class. A synonym is left
  out of the classes, because near-synonymy is not transitive.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

import numpy as np

from . import inventory
from .projection import UPOS, LensOutput, candidates, lemma_pos_groups

STRUCTURED_FIELDS = ("form_of", "alt_of", "synonyms", "links", "topics", "categories")
IDENTITY_FIELDS = {"form_of": "form_of", "alt_of": "alt_of", "synonyms": "sense_synonym"}
ALIGNED = "aligned"
CLASS_FAMILIES = frozenset({ALIGNED, "form_of", "alt_of"})
TOPIC = "wiktionary_topic"
# kaikki's category kinds other than "other" (maintenance, translation and topical names, which no native field tells
# apart in this export).
DOMAIN_KINDS = frozenset({"topical", "place", "lifeform"})


def _lookup(word: str) -> str:
    """The cohort's lemma spelling (WiktionaryParser: lowercase, spaces for underscores)."""
    return word.strip().lower().replace("_", " ")


@dataclass(frozen=True)
class Sense:
    """The structured fields of one Wiktionary reading."""

    row: int
    lemma: str
    pos: str
    form_of: tuple[str, ...] = ()
    alt_of: tuple[str, ...] = ()
    synonyms: tuple[str, ...] = ()
    links: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()


def sense_fields(row: int, lemma: str, pos: str, native_sense: dict) -> Sense:
    """Read only the structured fields of a native sense record."""
    words = {
        name: tuple(
            _lookup(item["word"])
            for item in native_sense.get(name, ())
            if isinstance(item, dict) and isinstance(item.get("word"), str)
        )
        for name in IDENTITY_FIELDS
    }
    links = []
    for pair in native_sense.get("links", ()):
        if not (isinstance(pair, list) and len(pair) == 2 and isinstance(pair[1], str)):
            continue
        target = pair[1].split("#", 1)[0]
        if target and ":" not in target:  # a namespaced page (Thesaurus:, w:, Appendix:) is not a word
            links.append(_lookup(target))
    topics = [t for t in native_sense.get("topics", ()) if isinstance(t, str)]
    topics += [
        c["name"]
        for c in native_sense.get("categories", ())
        if isinstance(c, dict) and c.get("kind") in DOMAIN_KINDS and isinstance(c.get("name"), str)
    ]
    return Sense(row, lemma, pos, **words, links=tuple(dict.fromkeys(links)), topics=tuple(dict.fromkeys(topics)))


@dataclass
class Taxonomy:
    """WordNet as the alignment reads it: a word's synsets, and a synset's kind-of ancestors."""

    synsets_of: Callable[[str], frozenset[str]]
    parents: dict[str, tuple[str, ...]]
    _ancestors: dict[str, frozenset[str]] = field(default_factory=dict)

    def ancestors(self, synset: str) -> frozenset[str]:
        """The synset itself and every kind-of ancestor."""
        if synset not in self._ancestors:
            seen, stack = {synset}, [synset]
            while stack:
                for parent in self.parents.get(stack.pop(), ()):
                    if parent not in seen:
                        seen.add(parent)
                        stack.append(parent)
            self._ancestors[synset] = frozenset(seen)
        return self._ancestors[synset]


@dataclass(frozen=True)
class IdentityObligation:
    """F073 over meanings: reading `row` means one of `targets`."""

    kind: str
    row: int
    targets: np.ndarray
    premises: tuple[str, ...]


@dataclass
class Binding:
    groups: dict[str, list[int]]
    links: list[tuple[str, str, str]]
    classes: np.ndarray
    obligations: list[IdentityObligation]
    facts: dict[str, np.ndarray]
    dispositions: dict[str, dict[str, int]]
    aligned: dict[int, int]

    def census(self, readings) -> dict:
        wiktionary = np.array([r.source == "wiktionary" for r in readings])
        wordnet = np.array([r.source == "wordnet" for r in readings])
        edges = Counter(family for family, _, _ in self.links)
        return {
            "edges_by_family": {f: n // 2 for f, n in sorted(edges.items())},
            "identity_obligations_by_kind": dict(sorted(Counter(o.kind for o in self.obligations).items())),
            "aligned_wiktionary_readings": len(self.aligned),
            "wiktionary_readings_connected_to_wordnet": int(self.connected(readings)[wiktionary].sum()),
            "classes_with_several_readings": int((np.bincount(self.classes) > 1).sum()),
            "wordnet_readings_in_a_shared_class": int((wordnet & (np.bincount(self.classes)[self.classes] > 1)).sum()),
            "topic_facts": len(self.facts),
            "readings_with_a_topic": int(np.unique(np.concatenate(list(self.facts.values()))).size)
            if self.facts
            else 0,
            "dispositions": self.dispositions,
        }

    def connected(self, readings) -> np.ndarray:
        """Readings that reach a WordNet reading through identity edges of any family."""
        node_rows = defaultdict(list)
        for row, r in enumerate(readings):
            node_rows[_key(r)].append(row)
        parent = {}

        def find(x):
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent[x], parent[x])
                x = parent[x]
            return x

        for _, a, b in self.links:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
        reach = {find(_key(r)) for r in readings if r.source == "wordnet"}
        return np.array([find(_key(r)) in reach for r in readings])


def _key(reading) -> str:
    """The inheritance node of a reading: its synset for WordNet, else its own id."""
    if reading.source == "wordnet":
        return unquote(reading.reading_id.rsplit(":", 1)[1])
    return reading.reading_id


class _Classes:
    def __init__(self, n: int):
        self.parent = np.arange(n, dtype=np.int64)

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return int(root)

    def join(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def array(self) -> np.ndarray:
        return np.array([self.find(i) for i in range(self.parent.size)], dtype=np.int64)


def _identity(readings, sense, field_name, word, groups, lemmas, out) -> None:
    """One form_of, alt_of or synonym target: an identity edge, an identity obligation, or unbound."""
    family = IDENTITY_FIELDS[field_name]
    tags = _upos(readings[sense.row].pos)
    rows = sorted({int(r) for tag in tags for r in groups.get((word, tag), ())} - {sense.row})
    premise = f"{readings[sense.row].reading_id}:{field_name}:{word}"
    if len(rows) == 1:
        out["identities"].append((family, sense.row, rows[0]))
        out["notes"][family]["IDENTITY_EDGE"] += 1
    elif rows:
        out["obligations"].append(IdentityObligation(family, sense.row, np.array(rows, dtype=np.int64), (premise,)))
        out["notes"][family]["IDENTITY_OBLIGATION"] += 1
    elif word == sense.lemma:
        out["notes"][family]["SELF_REFERENCE"] += 1
    else:
        out["notes"][family]["TARGET_HAS_ONLY_OTHER_POS" if word in lemmas else "TARGET_NOT_IN_COHORT"] += 1


def _align(readings, sense, groups, taxonomy: Taxonomy) -> tuple[str, int | None]:
    """The anchor alignment of one sense: ("ALIGNED", row) or an abstention reason."""
    tags = _upos(readings[sense.row].pos)
    candidates = [int(r) for tag in tags for r in groups.get((sense.lemma, tag), ()) if readings[r].source == "wordnet"]
    if not sense.links:
        return "NO_LINKS", None
    if not candidates:
        return "NO_WORDNET_CANDIDATE", None
    linked = frozenset().union(*(taxonomy.synsets_of(w) for w in sense.links))
    if not linked:
        return "NO_LINKED_SYNSET", None
    matches = [r for r in candidates if taxonomy.ancestors(_key(readings[r])) & linked]
    if len(matches) == 1:
        return "ALIGNED", matches[0]
    return ("NO_CANDIDATE_MATCHES" if not matches else "SEVERAL_CANDIDATES_MATCH"), None


def _upos(pos: str) -> frozenset[str]:
    return UPOS[pos]


def bind(readings, senses: Iterable[Sense], taxonomy: Taxonomy) -> Binding:
    """Every structured binding of the given Wiktionary senses over the cohort."""
    groups = lemma_pos_groups(readings)
    lemmas = {r.lemma.lower() for r in readings}
    out = {"identities": [], "obligations": [], "notes": defaultdict(Counter)}
    aligned: dict[int, int] = {}
    topics: dict[str, list[int]] = defaultdict(list)
    for sense in senses:
        for field_name in IDENTITY_FIELDS:
            for word in getattr(sense, field_name):
                _identity(readings, sense, field_name, word, groups, lemmas, out)
        reason, row = _align(readings, sense, groups, taxonomy)
        out["notes"][ALIGNED][reason] += 1
        if reason == "SEVERAL_CANDIDATES_MATCH" and sense.lemma in sense.links:
            out["notes"]["aligned_detail"]["SEVERAL_WITH_OWN_LEMMA_LINKED"] += 1
        if row is not None:
            aligned[sense.row] = row
            out["identities"].append((ALIGNED, sense.row, row))
        for topic in sense.topics:
            topics[f"{TOPIC}={topic}"].append(sense.row)
    classes = _Classes(len(readings))
    node_groups: dict[str, list[int]] = {}
    links = []
    for family, a, b in out["identities"]:
        if family in CLASS_FAMILIES:
            classes.join(a, b)
        ka, kb = _key(readings[a]), _key(readings[b])
        for r, k in ((a, ka), (b, kb)):
            if readings[r].source != "wordnet":
                node_groups[k] = [r]
        links += [(family, ka, kb), (family, kb, ka)]
    return Binding(
        groups=node_groups,
        links=links,
        classes=_without_contradictions(readings, classes.array(), out["notes"]),
        obligations=out["obligations"],
        facts={name: np.array(sorted(set(rows)), dtype=np.int64) for name, rows in sorted(topics.items())},
        dispositions={k: dict(sorted(v.items())) for k, v in sorted(out["notes"].items())},
        aligned=aligned,
    )


def _without_contradictions(readings, classes: np.ndarray, notes) -> np.ndarray:
    """A class holding two WordNet readings of one lemma and part of speech would identify two senses WordNet keeps
    apart. Such a class is dissolved into single readings and reported; its edges stay, for inheritance to suspend.
    The test reads the finished classes, so it does not depend on the order of the edges."""
    seen: dict[tuple[int, str, str], int] = {}
    broken = set()
    for row in np.flatnonzero(np.bincount(classes)[classes] > 1):
        r = readings[row]
        if r.source == "wordnet":
            for tag in UPOS[r.pos]:
                key = (int(classes[row]), r.lemma.lower(), tag)
                if key in seen:
                    broken.add(key[0])
                seen[key] = int(row)
    out = classes.copy()
    for root in broken:
        rows = np.flatnonzero(classes == root)
        out[rows] = rows
    if broken:
        notes["classes"]["DISSOLVED_TWO_WORDNET_SENSES_OF_ONE_LEMMA"] += len(broken)
    return out


def located_groups(readings, lens: LensOutput, binding: Binding, masks: np.ndarray) -> list[dict]:
    """The lens obligation groups that one alignment class now locates, with the facts they would carry."""
    by_witness = defaultdict(list)
    for o in lens.obligations:
        by_witness[o.witness].append(o)
    out = []
    for witness, found in sorted(candidates(masks, lens.obligations, binding.classes).items()):
        members = by_witness[witness]
        if found.size == 1 and members[0].rows.size > 1:
            rows = members[0].rows[binding.classes[members[0].rows] == found[0]]
            out.append(
                {
                    "rule_id": members[0].rule_id,
                    "lemma": readings[int(rows[0])].lemma,
                    "readings": [readings[int(r)].reading_id for r in rows],
                    "claims": {o.bank: o.allowed for o in members},
                    "facts": list(members[0].facts),
                }
            )
    return out


# --- The real cohort ------------------------------------------------------------------------------------------


def load_senses(readings) -> list[Sense]:
    """The structured fields of every cohort Wiktionary reading, from the pinned dump (WiktionaryParser)."""
    from GSE.curation.external_sources.wiktionary import WIKTIONARY_DUMP, WiktionaryParser

    index = {r.reading_id: i for i, r in enumerate(readings) if r.source == "wiktionary"}
    parser = WiktionaryParser(data_path=WIKTIONARY_DUMP)
    if not parser.load():
        raise RuntimeError("SOURCE_UNAVAILABLE wiktionary")
    lemmas = tuple(sorted({readings[i].lemma for i in index.values()}))
    senses = []
    for entry in parser.get_definition_entries(lemmas):
        row = index.get(entry.entry_id)
        if row is not None:
            senses.append(sense_fields(row, readings[row].lemma, readings[row].pos, entry.native_sense))
    if len(senses) != len(index):
        raise RuntimeError(f"WIKTIONARY_READINGS_UNBOUND {len(index) - len(senses)}")
    return senses


def wordnet_taxonomy() -> Taxonomy:
    """WordNet 3.0 (nltk): a word's synsets, and the inheritance graph's own kind-of families."""
    from nltk.corpus import wordnet as wn

    from .inheritance import FAMILIES, KIND_OF, wordnet_links

    kind_of = {f.name for f in FAMILIES if f.carries == KIND_OF}
    parents: dict[str, list[str]] = defaultdict(list)
    for family, giver, receiver in wordnet_links(wn):
        if family in kind_of:
            parents[receiver].append(giver)
    cache: dict[str, frozenset[str]] = {}

    def synsets_of(word: str) -> frozenset[str]:
        if word not in cache:
            cache[word] = frozenset(s.name() for s in wn.synsets(word.replace(" ", "_")))
        return cache[word]

    return Taxonomy(synsets_of, {k: tuple(v) for k, v in parents.items()})


def main(argv=None) -> dict:
    parser = argparse.ArgumentParser(description="Bind the cohort's Wiktionary readings through structured fields.")
    parser.add_argument("--cohort", type=Path, default=Path("data/lexicon_builder/rebuild/cohort.jsonl"))
    parser.add_argument("--receipt", type=Path, default=None)
    parser.add_argument("--settle", action="store_true", help="also run inheritance.settle with the binding")
    args = parser.parse_args(argv)
    readings = inventory.load(args.cohort)
    started = time.perf_counter()
    senses = load_senses(readings)
    loaded = time.perf_counter() - started
    started = time.perf_counter()
    binding = bind(readings, senses, wordnet_taxonomy())
    from . import projection
    from .cells import State

    sources, _ = projection.load_sources()
    sources.ratings = {}
    lens = projection.project(readings, sources)
    from . import guards, laws
    from .closure import close

    known = State.opening([r.reading_id for r in readings])
    law_relations = laws.compile_laws()
    lens_relations, lens_scopes = projection.restriction_relations(lens.restrictions, len(readings))
    wanted = {r.scope for r in law_relations}
    close(known, lens_relations + law_relations, guards.scopes(readings, wanted, lens.facts) | lens_scopes)
    by_classes = candidates(known.masks, lens.obligations, binding.classes)
    receipt = {
        "format": "GSE.rebuild-wiktionary-binding/1",
        "cohort": {"readings": len(readings), "sha256": inventory.digest(readings)},
        "senses": len(senses),
        "seconds": {"load": round(loaded, 1), "bind": round(time.perf_counter() - started, 1)},
        "binding": binding.census(readings),
        "lens_obligation_groups": {
            "groups": len(by_classes),
            "by_candidate_classes": dict(sorted(Counter(str(v.size) for v in by_classes.values()).items())),
            "located_by_one_class": located_groups(readings, lens, binding, known.masks),
        },
    }
    if args.settle:
        from .inheritance import wordnet_links

        receipt["settled"] = projection.settled_round(
            readings,
            lens,
            links=list(wordnet_links()) + binding.links,
            groups=binding.groups,
            classes=binding.classes,
        )
    if args.receipt:
        args.receipt.write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps(receipt, indent=1))
    return receipt


if __name__ == "__main__":
    main()
