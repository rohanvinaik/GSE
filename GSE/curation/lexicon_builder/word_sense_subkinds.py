"""Sub-kind inheritance: a meaning takes the decided values of every meaning it is a kind of (Rohan, 2026-11-26).

"Sub-categories of word meaning are the *easiest* tier": a kind of X is an X, so what is decided about X holds for it.
The values inherited are a meaning's own decided content, read from the word senses it belongs to, with a warrant of
member values, the release's rules or NSM molecule inheritance (never lemma-level source agreement, which is word
evidence, not the meaning's). Only nonzero values are inherited: a zero is recomputed by its own rule on each
definition. The kind-of relations come from the sources that state them:

* WordNet's hypernyms and instance hypernyms (a jump-start, not a gold standard), followed transitively;
* the other structural relations the design names (openspec design, "Founder correction 2"): synonymy (another
  lemma's definition of the same synset), an adjective satellite refining its head (similar_to), and verb entailment
  (V1 entails V2, so V2's content is part of V1), each followed with the same parent law;
* Wiktionary's own ``form_of`` and ``alt_of`` links: an inflection or alternative spelling means what its target
  means, when the target word has exactly one sense in that part of speech.

A kind's own decided value always stands; an inherited value that contradicts it is an exception, recorded and never
written. Two kind-of parents that disagree on a bank leave it open.

Admission is constraint propagation, TrialLedger's (Rohan, 2026-11-26: "TrialLedger's constraint propagation ideas
are how we allow sub-kind inheritance without introducing spurious and incorrect additions"). The kind's stored state
is its known level, already closed under the release's rules. Each inherited value is a default whose applicability
is the source-stated kind-of fact. The interpolated level is the known level closed under the release's rules and the
defaults together, with the definition's own rule context (``resolve_dictionary``, as every revision resolves). A
default that empties a domain on its own is suspended and reported with its cause; if the remaining defaults still
conflict together, all of them are suspended, never chosen by order. What the interpolated closure decides beyond the
known level (the defaults and their strict consequences) goes to the derived table the word senses read as member
evidence below every stated value, never load-bearing (``word_senses.DERIVED_TABLE``), with the edge that warrants it.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from functools import lru_cache

from .word_senses import DERIVED_TABLE

FORMAT = "GSE.subkind-inheritance/1"
INHERITABLE = frozenset({"members", "rules", "nsm-molecule"})


def sense_values(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """entry -> the decided nonzero values of the sense(s) it belongs to (inheritable warrants; senses that disagree
    on a bank leave it out)."""
    out: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for assignments, provenance, members in conn.execute("SELECT assignments, provenance, members FROM word_senses"):
        values, origins = json.loads(assignments), json.loads(provenance)
        kept = {b: v for b, v in values.items() if v and (origins.get(b) or {}).get("from") in INHERITABLE}
        for entry in json.loads(members):
            for b, v in kept.items():
                out[entry][b].add(v)
    return {e: {b: next(iter(s)) for b, s in banks.items() if len(s) == 1} for e, banks in out.items()}


def stored(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """entry -> its stored decided values (singleton domains)."""
    return {
        entry: {b: v[0] for b, v in json.loads(raw).items() if len(v) == 1}
        for entry, raw in conn.execute("SELECT entry_id, domains FROM definition_states")
    }


class Hierarchy:
    """WordNet's kind-of graph over synsets, with each synset's own decided values from its definitions."""

    def __init__(self, own_by_entry: dict[str, dict[str, int]]):
        by_synset: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
        for entry, values in own_by_entry.items():
            if entry.startswith("wordnet:"):
                for b, v in values.items():
                    by_synset[entry.rsplit(":", 1)[1]][b].add(v)
        self.own = {s: {b: next(iter(v)) for b, v in banks.items() if len(v) == 1} for s, banks in by_synset.items()}
        self.inherited = lru_cache(maxsize=None)(self._inherited)
        self._path: set[str] = set()  # entailment and cluster links can cycle; a meaning on the path adds nothing

    @staticmethod
    def parents(synset_name: str) -> tuple[str, ...]:
        """What the synset is a kind of, refines or entails, as WordNet states it."""
        from nltk.corpus import wordnet as wn

        try:
            synset = wn.synset(synset_name)
        except Exception:
            return ()
        linked = synset.hypernyms() + synset.instance_hypernyms() + synset.entailments()
        if synset.pos() == "s":
            linked += synset.similar_tos()  # a satellite refines its cluster's head
        return tuple(sorted({h.name() for h in linked}))

    def _inherited(self, synset_name: str) -> dict[str, tuple[int, str]]:
        """bank -> (value, the synset it was decided on) for everything this synset is a kind of."""
        merged: dict[str, set[tuple[int, str]]] = defaultdict(set)
        if synset_name in self._path:
            return {}
        self._path.add(synset_name)
        for parent in self.parents(synset_name):
            from_parent = dict(self.inherited(parent))
            for b, v in self.own.get(parent, {}).items():  # the parent's own decision stands over what it inherits
                from_parent[b] = (v, parent)
            for b, (v, origin) in from_parent.items():
                merged[b].add((v, origin))
        self._path.discard(synset_name)
        out = {}
        for b, found in merged.items():
            values = {v for v, _o in found}
            if len(values) == 1:
                out[b] = (next(iter(values)), sorted(o for _v, o in found)[0])
        return out


def form_of_targets(conn: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    """Wiktionary entry -> (target lemma, its part of speech) where the source states form_of or alt_of."""
    import ast

    pos_of = dict(
        conn.execute("SELECT d.entry_id, l.pos FROM definition_states d JOIN lexemes l ON d.lexeme_id = l.id")
    )
    out = {}
    for entry, payload in conn.execute("SELECT entry_id, payload FROM source_observations WHERE source='wiktionary'"):
        native = json.loads(payload)["features"].get("native_sense")
        try:
            native = ast.literal_eval(native) if isinstance(native, str) else (native or {})
        except ValueError, SyntaxError:
            continue
        links = (native.get("form_of") or []) + (native.get("alt_of") or [])
        words = {link.get("word") for link in links if isinstance(link, dict) and link.get("word")}
        if entry and len(words) == 1 and entry in pos_of:
            out[entry] = (next(iter(words)), pos_of[entry])
    return out


def inherit(conn: sqlite3.Connection) -> tuple[dict[str, tuple[dict, dict]], dict]:
    """entry -> (settled cells, edge), and a census with the exceptions."""
    own = sense_values(conn)
    held = stored(conn)
    hierarchy = Hierarchy(own)
    rows: dict[str, tuple[dict, dict]] = {}
    exceptions, cells = [], 0
    for entry, decided in held.items():
        if not entry.startswith("wordnet:"):
            continue
        synset = entry.rsplit(":", 1)[1]
        inherited = dict(hierarchy.inherited(synset))
        for b, v in hierarchy.own.get(synset, {}).items():  # synonymy: the synset's decision under any lemma
            inherited[b] = (v, synset)
        settled, origins = {}, {}
        for b, (v, origin) in sorted(inherited.items()):
            if b in decided or b in own.get(entry, {}):
                if (own.get(entry, {}).get(b, decided.get(b))) != v:
                    exceptions.append(
                        {
                            "entry": entry,
                            "bank": b,
                            "inherited": v,
                            "from": origin,
                            "holds": own.get(entry, {}).get(b, decided.get(b)),
                        }
                    )
                continue
            settled[b], origins[b] = v, origin
        if settled:
            rows[entry] = (
                settled,
                {
                    "genus": list(hierarchy.parents(synset)),
                    "differentia": [],
                    "template": "subkind-inheritance",
                    "origins": origins,
                    "format": FORMAT,
                },
            )
            cells += len(settled)
    # Wiktionary inflections and alternative spellings mean what their single-sense target means.
    senses_by_word: dict[tuple[str, str], list[dict[str, int]]] = defaultdict(list)
    for lemma, pos, assignments, provenance in conn.execute(
        "SELECT lemma, pos, assignments, provenance FROM word_senses"
    ):
        values, origins = json.loads(assignments), json.loads(provenance)
        senses_by_word[(lemma, pos)].append(
            {b: v for b, v in values.items() if v and (origins.get(b) or {}).get("from") in INHERITABLE}
        )
    for entry, (word, pos) in form_of_targets(conn).items():
        target = senses_by_word.get((word, pos)) or []
        if len(target) != 1:
            continue
        decided = held.get(entry, {})
        settled = {b: v for b, v in target[0].items() if b not in decided and b not in own.get(entry, {})}
        clash = {b: v for b, v in target[0].items() if b in decided and decided[b] != v}
        for b, v in clash.items():
            exceptions.append(
                {"entry": entry, "bank": b, "inherited": v, "from": f"form_of:{word}", "holds": decided[b]}
            )
        if settled:
            rows[entry] = (
                settled,
                {
                    "genus": [f"{word}/{pos}"],
                    "differentia": [],
                    "template": "form-of",
                    "origins": {b: f"form_of:{word}" for b in settled},
                    "format": FORMAT,
                },
            )
            cells += len(settled)
    return rows, {"definitions": len(rows), "cells": cells, "exceptions": len(exceptions), "exception_rows": exceptions}


def admit(conn: sqlite3.Connection, rows: dict[str, tuple[dict, dict]], progress=None) -> tuple[dict, dict]:
    """Close each kind's known level under the release's rules and its inherited defaults; keep what survives."""
    from .completion import _contexts, _entry, _prepare_context_index
    from .engine import Assertion
    from .foundation import BANKS, lexical_context
    from .resolution import resolve_dictionary
    from .validation import _metadata, _relations

    rules = _relations(_metadata(conn, "relations"))
    _prepare_context_index(conn)
    entries = tuple(sorted(rows))
    admitted, suspended, counts = {}, [], defaultdict(int)
    for start in range(0, len(entries), 500):  # SQLite bounds the variables in one statement
        batch = entries[start : start + 500]
        contexts, relevance = _contexts(conn, batch, indexed=True)
        for entry_id in batch:
            settled, edge = rows[entry_id]
            definition, assertions, restrictions, _hierarchy = _entry(conn, entry_id)
            context = lexical_context(definition, contexts[entry_id], rules)
            evidence = tuple(sorted(relevance[entry_id]))

            def close(
                defaults,
                definition=definition,
                assertions=assertions,
                restrictions=restrictions,
                context=context,
                evidence=evidence,
            ):
                added = tuple(
                    Assertion(b, v, "subkind-inheritance", entry_id, "derived") for b, v in sorted(defaults.items())
                )
                return resolve_dictionary(
                    BANKS,
                    tuple(assertions) + added,
                    rules,
                    context,
                    evidence_banks=evidence,
                    domain_restrictions=restrictions,
                )

            known = close({})
            if known.code == "CONFLICT":
                counts["known_conflict"] += 1
                continue
            alone_bad = {b: v for b, v in settled.items() if close({b: v}).code == "CONFLICT"}
            remaining = {b: v for b, v in settled.items() if b not in alone_bad}
            joint = close(remaining) if remaining else known
            if remaining and joint.code == "CONFLICT":
                alone_bad.update(remaining)
                remaining, joint = {}, known
            for b, v in alone_bad.items():
                suspended.append({"entry": entry_id, "bank": b, "default": v, "from": edge["origins"].get(b)})
            beyond = {b: v for b, v in joint.assignments.items() if b not in known.assignments and v is not None}
            if beyond:
                origins = {b: edge["origins"].get(b, "strict consequence of the inherited defaults") for b in beyond}
                admitted[entry_id] = (beyond, {**edge, "origins": origins})
                counts["cells"] += len(beyond)
                counts["consequence_cells"] += sum(1 for b in beyond if b not in settled)
        if progress:
            progress(start + len(batch), len(entries))
    census = {
        "definitions": len(admitted),
        "cells": counts["cells"],
        "consequence_cells": counts["consequence_cells"],
        "suspended": len(suspended),
        "known_conflicts": counts["known_conflict"],
        "suspended_rows": suspended,
    }
    return admitted, census


def write(conn: sqlite3.Connection, rows: dict[str, tuple[dict, dict]]) -> None:
    conn.execute(f"DROP TABLE IF EXISTS {DERIVED_TABLE}")
    conn.execute(f"CREATE TABLE {DERIVED_TABLE} (entry_id TEXT PRIMARY KEY, settled TEXT NOT NULL, edge TEXT NOT NULL)")
    conn.executemany(
        f"INSERT INTO {DERIVED_TABLE} VALUES (?, ?, ?)",
        [(e, json.dumps(s, sort_keys=True), json.dumps(edge, sort_keys=True)) for e, (s, edge) in sorted(rows.items())],
    )
