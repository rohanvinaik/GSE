"""Positive gloss composition over the whole lexicon, to a fixpoint (round 3).

Design: ``openspec/changes/lexicon-symbolic-foundation/gloss-composition.md``. Rohan (2026-11-26): a positive
definition is never assembled through exclusion or through negatives; the lexicon fills with positive reads from
the sources provided for them. So this module composes only nonzero values, each traced to what produced it, and
never writes a zero.

- **A word's banks are its own denotatum, so a definition takes its genus only.** The genus is the exact WordNet
  hypernym synsets for a WordNet noun or verb; otherwise the head ``parse_gloss`` reads, at the exact synset the
  Princeton gloss tags name when there is one (``wordnet_glosstag``). Differentia (relative clauses, objects,
  complements, purposes) describe what the referent does or what a predicate takes, not what the word denotes: "a
  hen that lays eggs" is not DO, "diligent in investigation" is not DO. A verb, adjective or adverb never takes the
  identity banks (identity enters only through a noun's genus). An identity template ("present participle of ban")
  is its operand, every bank.
- **A contributing word is read from its definitions, not from merged word senses.** Its reading is what every one
  of its definitions holds (a definition silent on a bank allows every sign), so a homonym's values never spill
  onto another's: "nail" the fastener does not lend QUANTITY from "nail" the unit. This is monotone: a value added
  to a definition can complete an agreement, never break one.
- **Closed-class words are grammar** (``gse_closed_class`` lemmas); a gloss the parser marks negated contributes no
  differentia, because "not X" states no positive content and flipping a sign would assert the opposite pole.
- **Admission.** A composed value enters only an open bank whose domain holds it; two contributors with opposite
  signs leave the bank contested; a value a domain excludes is a typed contradiction. Nothing stored changes.
"""

from __future__ import annotations

import json
import pickle
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from . import word_sense_genus_differentia as gd
from .foundation import BANKS

FORMAT = "GSE.gloss-composition/1"
CHANNEL = "derived:gloss-composition"
COMPOSED_POS = frozenset({"noun", "verb", "adj", "adv"})
BANK_INDEX = {bank: i for i, bank in enumerate(BANKS)}


def identity_bank_set(root: Path) -> frozenset[str]:
    """The identity banks, derived from the NSM chart's categories through the catalog (round 2's derivation)."""
    from .catalog import catalog_inventory

    table = (root / gd.CATEGORY_TABLE).read_text(encoding="utf-8")
    return frozenset(gd.identity_banks(table, catalog_inventory()["units"]))


def parse_definition(entry_id: str, lemma: str, pos: str, gloss: str) -> dict:
    """What one definition composes from: WordNet nouns/verbs name their hypernym synsets; every gloss is parsed."""
    parsed = gd.parse_gloss(lemma, pos, gloss or "")
    if entry_id.startswith("wordnet:") and pos in ("noun", "verb"):
        try:
            parsed["synset_genus"] = list(gd.wordnet_genus(gd.synset_of(entry_id)))
        except Exception as exc:  # a synset nltk cannot resolve is recorded, never guessed
            parsed["synset_error"] = type(exc).__name__
    return parsed


def _parse_chunk(rows: list[tuple]) -> list[tuple[str, dict]]:
    return [(entry, parse_definition(entry, lemma, pos, gloss)) for entry, lemma, pos, gloss in rows]


@dataclass
class Composition:
    """The overlay: stored values plus composed values, with traces, contests and contradictions."""

    derived: dict[str, dict[str, int]] = field(default_factory=dict)
    trace: dict[str, dict[str, str]] = field(default_factory=dict)
    contested: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    contradictions: list[dict] = field(default_factory=list)
    passes: list[int] = field(default_factory=list)


class Lexicon:
    """One release's definitions in memory: domains, words, synsets, parses."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        root: Path,
        parses: Mapping[str, dict] | None = None,
        tags: Mapping[str, list[dict]] | None = None,
    ):
        self.identity = identity_bank_set(root)
        self.domain: dict[str, int] = {}
        self.word: dict[str, tuple[str, str]] = {}
        self.by_word: dict[tuple[str, str], list[str]] = defaultdict(list)
        self.by_synset: dict[str, list[str]] = defaultdict(list)
        self.gloss: dict[str, str] = {}
        rows = conn.execute(
            "SELECT d.entry_id, l.lemma, l.pos, l.gloss, d.domains FROM definition_states d "
            "JOIN lexemes l ON d.lexeme_id = l.id"
        )
        for entry, lemma, pos, gloss, domains in rows:
            self.domain[entry] = gd.pack(json.loads(domains))
            key = ((lemma or "").lower(), pos or "")
            self.word[entry] = key
            self.by_word[key].append(entry)
            self.gloss[entry] = gloss or ""
            if entry.startswith("wordnet:"):
                self.by_synset[gd.synset_of(entry)].append(entry)
        self.closed = frozenset(self.word[e][0] for e in self.domain if e.startswith("gse_closed_class:"))
        self.parses = dict(parses or {})
        self.tags = dict(tags or {})  # synset -> its definition's sense-tagged words (wordnet_glosstag)
        self._held: dict[str, dict[str, int]] = {}

    # -- values -----------------------------------------------------------------------------------------------------
    def stored(self, entry: str) -> dict[str, int]:
        packed = self.domain[entry]
        out = {}
        for i, bank in enumerate(BANKS):
            values = gd.bank_values(packed, i)
            if len(values) == 1:
                out[bank] = values[0]
        return out

    def held(self, entry: str, comp: Composition) -> dict[str, int]:
        if entry not in self._held:
            self._held[entry] = self.stored(entry)
        return {**self._held[entry], **comp.derived.get(entry, {})}

    def agreement(self, entries: Iterable[str], comp: Composition) -> dict[str, int]:
        """What every definition holds, nonzero only: a definition silent on a bank blocks agreement there."""
        entries = list(entries)
        if not entries:
            return {}
        common = dict(self.held(entries[0], comp))
        for entry in entries[1:]:
            values = self.held(entry, comp)
            common = {b: v for b, v in common.items() if values.get(b) == v}
            if not common:
                break
        return {b: v for b, v in common.items() if v}

    def reading(self, lemma: str, pos: str | None, comp: Composition) -> dict[str, int]:
        """A word's reading: what all its definitions in ``pos`` (every content pos when None) hold."""
        lemma = lemma.lower()
        if lemma in self.closed:
            return {}
        poses = [pos] if pos else sorted(COMPOSED_POS)
        entries = [e for p in poses for e in self.by_word.get((lemma, p), ())]
        return self.agreement(entries, comp)

    # -- one definition ---------------------------------------------------------------------------------------------
    def compose(self, entry: str, comp: Composition) -> dict[str, dict[int, str]]:
        """bank -> {sign: trace} from what this definition's genus and differentia positively hold."""
        lemma, pos = self.word[entry]
        parsed = self.parses.get(entry)
        if pos not in COMPOSED_POS or parsed is None:
            return {}
        out: dict[str, dict[int, str]] = defaultdict(dict)

        def add(values: Mapping[str, int], source: str, identity_allowed: bool) -> None:
            for bank, value in values.items():
                if value and (identity_allowed or bank not in self.identity):
                    out[bank].setdefault(value, source)

        template = parsed.get("template")
        if parsed.get("synset_genus"):  # WordNet noun/verb: the exact hypernym synsets
            for synset in parsed["synset_genus"]:
                add(self.agreement(self.by_synset.get(synset, ()), comp), f"genus {synset}", pos == "noun")
            if pos == "noun":
                return dict(out)
        elif template not in (None, "genus_differentia", "sentence_scale") and parsed.get("genus"):
            operand_pos = gd.operand_pos(template, pos)  # an identity template is its operand, every bank
            add(self.reading(parsed["genus"], operand_pos, comp), f"{template} {parsed['genus']}", True)
            return dict(out)
        if template != "genus_differentia" or parsed.get("negated"):
            return dict(out)  # a negated gloss states no positive content beyond its structural hypernym
        genus = parsed.get("genus")
        if genus and not parsed.get("synset_genus"):
            link = self._tagged_head(entry, genus)
            if link is not None:  # the genus head at the exact synset its gloss tag names
                values = self.agreement(self.by_synset.get(link["synset"], ()), comp)
                add(values, f"genus {genus}={link['synset']}", pos == "noun")
            else:
                add(self.reading(genus, pos, comp), f"genus word {genus}", pos == "noun")
        # Differentia (objects, complements, purposes) describe a predicate's arguments, not what it denotes.
        return dict(out)

    def _tagged_head(self, entry: str, genus: str) -> dict | None:
        if not entry.startswith("wordnet:"):
            return None
        wanted = genus.lower().replace(" ", "_")
        for link in self.tags.get(gd.synset_of(entry), ()):
            if link["key"].split("%", 1)[0].lower() == wanted:
                return link
        return None

    # -- the fixpoint -----------------------------------------------------------------------------------------------
    def close(self, entries: Iterable[str] | None = None, max_passes: int = 50) -> Composition:
        comp = Composition()
        targets = sorted(entries if entries is not None else self.domain)
        for number in range(1, max_passes + 1):
            admitted: dict[str, dict[str, tuple[int, str]]] = defaultdict(dict)
            for entry in targets:
                current = self.held(entry, comp)
                for bank, signs in self.compose(entry, comp).items():
                    if len(signs) > 1:
                        comp.contested.setdefault(entry, {})[bank] = sorted(f"{v:+d} {s}" for v, s in signs.items())
                        continue
                    ((value, source),) = signs.items()
                    if current.get(bank) == value:
                        continue
                    allowed = gd.bank_values(self.domain[entry], BANK_INDEX[bank])
                    if bank in current or value not in allowed:
                        kind = "OPPOSES_HELD_VALUE" if bank in current else "OUTSIDE_DOMAIN"
                        record = {"kind": kind, "entry_id": entry, "bank": bank, "value": value, "source": source}
                        if record not in comp.contradictions:
                            comp.contradictions.append(record)
                        continue
                    admitted[entry][bank] = (value, f"pass {number}: {source}")
            if not admitted:
                break
            for entry, cells in admitted.items():
                for bank, (value, source) in cells.items():
                    comp.derived.setdefault(entry, {})[bank] = value
                    comp.trace.setdefault(entry, {})[bank] = source
            comp.passes.append(sum(len(c) for c in admitted.values()))
        return comp


def measure(lexicon: Lexicon, comp: Composition, entries: Iterable[str]) -> dict:
    """Nonzero values per definition before and after, gains by source and part of speech."""
    entries = list(entries)
    before = sum(1 for e in entries for v in lexicon.stored(e).values() if v)
    gained = sum(len(comp.derived.get(e, {})) for e in entries)
    by_kind: Counter = Counter()
    for e in entries:
        source = e.split(":", 1)[0]
        by_kind[f"{source}/{lexicon.word[e][1]}"] += len(comp.derived.get(e, {}))
    return {
        "definitions": len(entries),
        "nonzero_per_definition_before": before / max(len(entries), 1),
        "nonzero_per_definition_after": (before + gained) / max(len(entries), 1),
        "cells_gained": gained,
        "passes": comp.passes,
        "contested_cells": sum(len(c) for e, c in comp.contested.items() if e in set(entries)),
        "contradictions": Counter(r["kind"] for r in comp.contradictions),
        "gained_by_source_pos": dict(by_kind.most_common()),
    }


def load_parses(path: Path) -> dict[str, dict]:
    with path.open("rb") as handle:
        return pickle.load(handle)
