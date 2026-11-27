"""Source lenses: what each source is competent to say about a reading (design E2, rebuild task 3).

F056: "What semantic degrees of freedom are pinned by every typed, categorical assertion in them". A lens reads one
parser's native records, loaded once, and writes only what that source's authored contract in `bank_laws.json`
declares. Nothing else in a record removes a state.

- VerbNet (`native_predicate_rules`). A reading bound by one of its exact WordNet sense keys gets the rule's prime
  when the predicate is asserted of its own event in every frame of its class: scope
  ONE_NATIVE_CLASS_FRAME_AND_ARGUMENT_BINDING, or for `cause` the event and its causer. A missing predicate
  removes nothing (missing_policy NO_RESTRICTION).
- USAS with FrameNet (`source_rules`). A signed USAS tag of the rule's category and part of speech, with a FrameNet
  unit of the same lemma and part of speech in one of the rule's frames, puts the rule's coordinate at the tag's
  pole, with the rule's companions.
- VerbNet with USAS (`native_residual_rules`). A perception predicate fixes the function. USAS X3.2 or X3.4 fixes
  HEAR or SEE, but only when both bind to the same reading.
- Ratings and associations write nothing. This covers `association_policy`, SentiWordNet and ConceptNet: they are
  counted and recorded (F115).

No gloss is read (F080). No threshold, rate, support count or score decides anything.

USAS and FrameNet speak of a lemma and a part of speech, never of one sense. What they state is an obligation, F073's
semantic sudoku: at least one of that lemma's readings holds it. It is never copied onto every reading. Only when the
lemma and part of speech have a single reading does the obligation become a restriction on that reading. Only then
do the rule's reading facts hold of a reading (`own_semantic_kind=evaluator`, `own_semantic_kind=size_descriptor`,
the Fear frame and so on, the guards its laws select on). A guard is a fact about one reading, and a word-level
binding does not say which reading it is.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import numpy as np

from GSE.curation.external_sources.verbnet import (
    _cause_status,
    _component_status,
    _existence_change,
    _predicate_binding,
)

from . import guards, inventory, laws
from .cells import ALL, BANK_INDEX, BANKS, BIPOLAR, BIT_NAMES, NEG, NEGATIVE_POLES, POS, SILENT, ZERO, State
from .closure import Derivations, close
from .obligations import Obligation
from .relations import Relation

_VALUE = {"+1": POS, "-1": NEG, "0": ZERO, "empty": SILENT}
_STATES = (POS, NEG, ZERO, SILENT)

# Every part-of-speech spelling in the cohort, mapped to the UPOS tags USAS uses. A spelling that names no single
# part of speech (NSM chart units and constructions, phrases, affixes, contractions, characters) binds to none.
UPOS: dict[str, frozenset[str]] = {
    pos: frozenset(tags)
    for pos, tags in {
        "adj": ("ADJ",),
        "adv": ("ADV",),
        "article": ("DET",),
        "auxiliary": ("AUX",),
        "character": (),
        "conj": ("CCONJ", "SCONJ"),
        "conjunction": ("CCONJ", "SCONJ"),
        "contraction": (),
        "demonstrative": ("DET", "PRON"),
        "det": ("DET",),
        "determiner": ("DET",),
        "infix": (),
        "intj": ("INTJ",),
        "name": ("PROPN",),
        "noun": ("NOUN",),
        "nsm_construction": (),
        "nsm_lexical_unit": (),
        "num": ("NUM",),
        "particle": ("PART",),
        "phrase": (),
        "postp": ("ADP",),
        "prep": ("ADP",),
        "prep_phrase": (),
        "preposition": ("ADP",),
        "pron": ("PRON",),
        "pronoun": ("PRON",),
        "punct": ("PUNCT",),
        "suffix": (),
        "symbol": ("SYM",),
        "verb": ("VERB",),
    }.items()
}
FRAMENET_POS = {"ADJ": "a", "NOUN": "n", "VERB": "v", "ADV": "adv"}

# VN_EXISTENCE authority: "VerbNet exist class or existence transition, not participant mention".
EXIST_CLASS = "exist-47.1"
PERCEIVE = "perceive"
# Ratings and associations are recorded and never write (association_policy; design E2, "LLM slop", F115).
POLICY_KEYS = {
    "nrc_emotion": "NRC_emotion",
    "nrc_vad": "NRC_VAD",
    "lancaster": "Lancaster",
    "concreteness": "concreteness",
}
UNLISTED_RATING = "RATING_OR_ASSOCIATION_SCORE; recorded, never written (design E2)"
RATINGS = ("nrc_emotion", "nrc_vad", "lancaster", "concreteness", "sentiwordnet", "conceptnet")
VERBNET, USAS_FRAMENET, VERBNET_USAS = "verbnet", "usas+framenet", "verbnet+usas"

_TAG = re.compile(r"(?P<category>[A-Z]\d+(?:\.\d+)*)(?P<marks>.*)")
_SIGNED = re.compile(r"\++|-+")


@dataclass
class Restrictions:
    """Reading-level restrictions. Cell (rows[i], cols[i]) keeps only the states in allowed[i]."""

    rows: np.ndarray
    cols: np.ndarray
    allowed: np.ndarray
    rules: np.ndarray
    premises: np.ndarray
    rule_ids: tuple[str, ...]
    warrants: tuple[str, ...]
    premise_ids: tuple[str, ...]
    rule_sources: tuple[str, ...] = ()

    def __len__(self) -> int:
        return int(self.rows.size)

    def by_rule(self) -> dict[str, int]:
        counts = np.bincount(self.rules, minlength=len(self.rule_ids))
        return {rule: int(c) for rule, c in zip(self.rule_ids, counts) if c}


@dataclass
class LensOutput:
    restrictions: Restrictions
    facts: dict[str, np.ndarray]
    obligations: list[Obligation]
    dispositions: dict[str, dict[str, dict[str, int]]]

    def census(self) -> dict:
        r = self.restrictions
        cells = int(np.unique(r.rows * len(BANKS) + r.cols).size)
        by_bank = Counter(
            f"{r.rule_ids[rule]}:{BANKS[col]}:{label(mask)}" for rule, col, mask in zip(r.rules, r.cols, r.allowed)
        )
        return {
            "restrictions": len(r),
            "restricted_cells": cells,
            "restricted_readings": int(np.unique(r.rows).size),
            "restrictions_by_rule": r.by_rule(),
            "restrictions_by_rule_bank": dict(sorted(by_bank.items())),
            "restricted_cells_by_source_bank": self._cells_by_source_bank(),
            "facts": {name: int(mask.sum()) for name, mask in sorted(self.facts.items())},
            "obligations": len(self.obligations),
            "obligation_witnesses": len({o.witness for o in self.obligations}),
            "obligations_by_rule_bank": dict(
                sorted(Counter(f"{o.rule_id}:{o.bank}:{label(o.allowed)}" for o in self.obligations).items())
            ),
            "dispositions": self.dispositions,
        }

    def _cells_by_source_bank(self) -> dict[str, int]:
        """Distinct cells each source restricts, by bank (a value, or an excluded pole)."""
        r = self.restrictions
        sources = np.array(r.rule_sources, dtype=object)[r.rules] if len(r) else np.zeros(0, dtype=object)
        cells = {(src, int(row), int(col)) for src, row, col in zip(sources, r.rows, r.cols)}
        return dict(sorted(Counter(f"{src}:{BANKS[col]}" for src, _, col in cells).items()))


@dataclass
class Sources:
    """Native records, loaded once (`load_sources`); tests build them by hand.

    `links` resolves a VerbNet membership's attached sense keys (`VerbNetParser.definition_links`).
    `ratings` maps a rating or association source to its observations per lemma.
    """

    verbnet: dict = field(default_factory=dict)
    links: Callable[[object], list[dict]] = lambda entry: [{"code": "WORDNET_UNAVAILABLE"}]
    usas: dict = field(default_factory=dict)
    framenet: dict = field(default_factory=dict)
    ratings: dict[str, dict[str, int]] = field(default_factory=dict)


def label(mask: int) -> str:
    return "|".join(BIT_NAMES[s] for s in _STATES if int(mask) & s)


def reading_id(lemma: str, synset: str) -> str:
    """The cohort id of a WordNet sense (inventory: `wordnet:<lemma>:<synset>`, each part quoted)."""
    return f"wordnet:{quote(lemma, safe='')}:{quote(synset, safe='')}"


def lemma_pos_groups(readings) -> dict[tuple[str, str], np.ndarray]:
    """The rows of every (lemma, UPOS) pair: what a word-level source binds to."""
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, r in enumerate(readings):
        if r.pos not in UPOS:
            raise ValueError(f"UNMAPPED_POS {r.pos!r}")
        for tag in UPOS[r.pos]:
            groups[r.lemma.lower(), tag].append(i)
    return {key: np.array(rows, dtype=np.int64) for key, rows in groups.items()}


def _warrant(rule: dict) -> str:
    return f"{rule.get('review_state')}: {rule.get('warrant') or rule.get('meaning')}"


def _pole(prime: str) -> tuple[str, int]:
    """A prime's bank and pole: END is START at -1 (cells.NEGATIVE_POLES, from BIPOLAR_PAIRS)."""
    if prime in BANK_INDEX:
        return prime, POS
    if prime in NEGATIVE_POLES:
        return NEGATIVE_POLES[prime], NEG
    raise ValueError(f"UNKNOWN_PRIME {prime}")


class _Writer:
    """Collects restrictions, facts, obligations and dispositions, then freezes them into a LensOutput."""

    def __init__(self, n: int):
        self.n = n
        self.cells: list[tuple[int, int, int, int, int]] = []
        self.rule_index: dict[str, int] = {}
        self.warrants: list[str] = []
        self.rule_sources: list[str] = []
        self.premise_index: dict[str, int] = {}
        self.facts: dict[str, np.ndarray] = {}
        self.witnesses: dict[tuple, tuple[int, list[str]]] = {}
        self.dispositions: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))

    def declare(self, rule_id: str, warrant: str, source: str) -> None:
        if rule_id not in self.rule_index:
            self.rule_index[rule_id] = len(self.warrants)
            self.warrants.append(warrant)
            self.rule_sources.append(source)

    def restrict(self, row: int, bank: str, allowed: int, rule_id: str, premise: str) -> None:
        premise_id = self.premise_index.setdefault(premise, len(self.premise_index))
        self.cells.append((int(row), BANK_INDEX[bank], int(allowed), self.rule_index[rule_id], premise_id))

    def fact(self, name: str, row: int) -> None:
        self.facts.setdefault(name, np.zeros(self.n, dtype=bool))[row] = True

    def oblige(self, rule_id: str, claims: dict[str, int], rows: np.ndarray, premises: tuple[str, ...]) -> None:
        key = (rule_id, rows.tobytes(), tuple(sorted(claims.items())))
        if key not in self.witnesses:
            self.witnesses[key] = (len(self.witnesses), [])
        self.witnesses[key][1].extend(p for p in premises if p not in self.witnesses[key][1])

    def note(self, source: str, category: str, reason: str, count: int = 1) -> None:
        self.dispositions[source][category][reason] += count

    def output(self) -> LensOutput:
        a = np.array(self.cells, dtype=np.int64).reshape(-1, 5)
        restrictions = Restrictions(
            rows=a[:, 0].copy(),
            cols=a[:, 1].copy(),
            allowed=a[:, 2].astype(np.uint8),
            rules=a[:, 3].astype(np.int32),
            premises=a[:, 4].astype(np.int32),
            rule_ids=tuple(self.rule_index),
            warrants=tuple(self.warrants),
            premise_ids=tuple(self.premise_index),
            rule_sources=tuple(self.rule_sources),
        )
        obligations = [
            Obligation(
                rule_id, bank, allowed, np.frombuffer(rows, dtype=np.int64), witness=witness, premises=tuple(premises)
            )
            for (rule_id, rows, claims), (witness, premises) in self.witnesses.items()
            for bank, allowed in claims
        ]
        dispositions = {
            source: {category: dict(sorted(reasons.items())) for category, reasons in sorted(categories.items())}
            for source, categories in sorted(self.dispositions.items())
        }
        return LensOutput(restrictions, self.facts, obligations, dispositions)


# --- VerbNet: native predicates over every frame of a class ---------------------------------------------------


@dataclass
class _Reading:
    """What one frame, or every frame of a class, asserts. `values`: coordinate -> (state bit, rule id), or None
    where two rules disagree in one frame."""

    values: dict[str, tuple[int, str] | None]
    refused: dict[str, str]
    perceive: bool
    partial: frozenset[str] = frozenset()


def _refusal(rule: dict, class_id: str, affective: bool) -> str | None:
    """A join the rule's own conditions refuse, before any polarity is read."""
    if rule.get("requires_verb_emotion_tag") and not affective:
        return "UNALIGNED_AFFECTIVE_READING"
    prefix = rule.get("class_number_prefix")
    if prefix and not class_id.partition("-")[2].startswith(prefix):
        return "OUTSIDE_RULE_CLASS_SCOPE"
    return None


def _in_class(class_id: str, root: str) -> bool:
    return class_id == root or class_id.startswith(root + "-")


def _transition(frame: dict, name: str, pole: int) -> int | None:
    """TRANSITION_POLE: the result direction within one event and participant binding.

    native_predicate_policy.transition_warrants: "A positive start state and negative terminal state for the same
    event and participant establishes death", the opposite pole. A positive terminal state, or an unphased positive
    state, is the rule's own pole. A start state alone projects nothing. Bindings that disagree leave it open.
    """
    phases: dict[tuple, dict[str, set[bool]]] = defaultdict(lambda: defaultdict(set))
    for predicate in frame["semantics"]:
        if predicate["predicate_value"] == name:
            binding = _predicate_binding(predicate)
            phases[binding["event"], binding["roles"]][binding["phase"]].add(binding["negative"])
    found = set()
    for seen in phases.values():
        terminal = seen["end"] | seen["result"]
        if terminal == {True} and False in seen["start"]:
            found.add(POS + NEG - pole)
        elif terminal == {False} or (not terminal and False in seen["whole"] | seen["during"]):
            found.add(pole)
    return found.pop() if len(found) == 1 else None


def _put(values: dict, coordinate: str, value: tuple[int, str]) -> None:
    if coordinate in values and values[coordinate] is not None and values[coordinate][0] != value[0]:
        values[coordinate] = None
    elif coordinate not in values:
        values[coordinate] = value


def negated_pole(rule: dict) -> str:
    """The rule id under which a negated bipolar predicate excludes its pole."""
    return f"{rule['rule_id']}:NEGATED_POLE"


def _read_frame(class_id: str, frame: dict, roles: dict, rules: dict, affective: bool) -> _Reading:
    names = {p["predicate_value"] for p in frame["semantics"]}
    refused = {n: code for n in sorted(names & rules.keys()) if (code := _refusal(rules[n], class_id, affective))}
    values: dict[str, tuple[int, str] | None] = {}
    for name in sorted((names & rules.keys()) - {"cause"} - refused.keys()):
        rule = rules[name]
        status = _component_status(frame, name)
        coordinate, pole = _pole(rule["prime"])
        if status["code"] == "NO_POSITIVE_LEXICAL_COMPONENT":
            # Every binding of the predicate is negated. source_polarity: "A negated bipolar pole only excludes that
            # pole"; an unpaired component writes nothing (lexical_component, missing_policy NO_RESTRICTION).
            if coordinate in BIPOLAR:
                _put(values, coordinate, (ALL & ~pole, negated_pole(rule)))
            continue
        if status["code"] != "WARRANTED_LEXICAL_COMPONENT":
            continue
        if rule.get("requires_existence_change") and not (
            _in_class(class_id, EXIST_CLASS) or any(_existence_change(frame, b) for b in status["bindings"])
        ):
            refused[name] = "PARTICIPANT_EXISTENCE_PRESUPPOSITION"
            continue
        if rule["projection_kind"] == "TRANSITION_POLE":
            pole = _transition(frame, name, pole)
            if pole is None:
                continue
        _put(values, coordinate, (pole, rule["rule_id"]))
    if "cause" in rules and "cause" in names:
        # "A predicate refused as a wrong-sense or out-of-scope join never counts" (VN_CAUSATION).
        for proof in _cause_status(frame, roles).get("proofs", []):
            if frame["semantics"][proof["outcome_predicate"]]["predicate_value"] not in refused:
                for bank in proof["primitives"]:
                    _put(values, bank, (POS, rules["cause"]["rule_id"]))
    perceive = _component_status(frame, PERCEIVE)["code"] == "WARRANTED_LEXICAL_COMPONENT"
    return _Reading(values, refused, perceive)


def _read_class(context: list[dict], rules: dict, affective: bool) -> _Reading:
    """Only what every frame of the class, inherited frames included, asserts with the same value."""
    roles = {
        role["attributes"]["type"]: role
        for level in context
        for role in level.get("thematic_roles", [])
        if role.get("attributes", {}).get("type")
    }
    frames = [(level["class_id"], frame) for level in context for frame in level["frames"]]
    if not frames:
        return _Reading({}, {}, False)
    read = [_read_frame(class_id, frame, roles, rules, affective) for class_id, frame in frames]
    universal = {
        c: v for c, v in read[0].values.items() if v is not None and all(r.values.get(c) == v for r in read[1:])
    }
    partial = frozenset(v[1] for r in read for c, v in r.values.items() if v is not None and c not in universal)
    refused = {name: code for r in read for name, code in r.refused.items()}
    return _Reading(universal, refused, all(r.perceive for r in read), partial)


def _emotion_verbs(usas: dict) -> frozenset[str]:
    """VN_AFFECTIVE_STATE `requires_verb_emotion_tag`: the lemma's USAS verb entry has an E tag in an alternative."""
    return frozenset(
        lemma
        for lemma, entries in usas.items()
        for entry in entries
        if entry.pos == "VERB" and any(re.match(r"E\d", part) for tag in entry.semantic_tags for part in tag.split("/"))
    )


def _verbnet_lens(index: dict, sources: Sources, book: dict, w: _Writer) -> dict[int, list[str]]:
    """Restrictions from exact sense-key bindings. Returns the perception-bound rows with their premises."""
    rules = {r["predicate"]: r for r in book["native_predicate_rules"]}
    polarity = book["native_predicate_policy"]["source_polarity"]
    for rule in rules.values():
        w.declare(rule["rule_id"], _warrant(rule), VERBNET)
        if _pole(rule["prime"])[0] in BIPOLAR:
            w.declare(negated_pole(rule), f"{rule['review_state']}: source_polarity: {polarity}", VERBNET)
    motion = rules["motion"]["rule_id"]
    motion_fact = laws.scope_name([("own_predicate", "physical_change_of_place")])
    affective = _emotion_verbs(sources.usas)
    classes: dict[tuple[str, bool], _Reading] = {}
    perceivers: dict[int, list[str]] = defaultdict(list)
    for word in sorted(sources.verbnet):
        for entry in sources.verbnet[word]:
            key = (entry.verb_class, entry.word in affective)
            if key not in classes:
                classes[key] = _read_class(entry.class_context, rules, key[1])
            reading = classes[key]
            for link in sources.links(entry):
                if link["code"] != "LINKED":
                    w.note("verbnet", "unbound", link["code"])
                    continue
                row = index.get(reading_id(entry.word, link["synset_name"]))
                if row is None:
                    w.note("verbnet", "unbound", "READING_NOT_IN_COHORT")
                    continue
                premise = f"verbnet:{entry.verb_class}:{link['sense_key']}"
                for coordinate, (allowed, rule_id) in sorted(reading.values.items()):
                    w.restrict(row, coordinate, allowed, rule_id, premise)
                    if rule_id == motion:
                        w.fact(motion_fact, row)
                if reading.perceive:
                    perceivers[row].append(premise)
                for rule_id in sorted(reading.partial):
                    w.note("verbnet", "withheld", f"NOT_IN_EVERY_FRAME:{rule_id}")
                for code in sorted(set(reading.refused.values())):
                    w.note("verbnet", "withheld", f"REFUSED_JOIN:{code}")
                if reading.values:
                    w.note("verbnet", "used", "PROJECTED")
                elif reading.refused:
                    w.note("verbnet", "refused", "+".join(sorted(set(reading.refused.values()))))
                else:
                    w.note("verbnet", "recorded_only", "NO_RULE_PREDICATE_IN_EVERY_FRAME")
    return perceivers


# --- USAS with FrameNet: source contracts at lemma and part of speech ------------------------------------------


def _match(rule: dict, pos: str, tag: str) -> tuple[str, str | int]:
    """("skip", ""), ("refused", reason) or ("pole", state bit) for one USAS alternative under one rule."""
    categories = rule.get("categories") or [rule["category"]]
    parts = tag.split("/")
    named = [m for part in parts if (m := _TAG.fullmatch(part)) and m["category"] in categories]
    if not named:
        return "skip", ""
    if pos not in rule["pos"]:
        return "refused", "POS_OUTSIDE_RULE"
    if len(parts) > 1:
        return "refused", "SLASH_TAG_JOINT_MEMBERSHIP"
    marks = named[0]["marks"]
    if not marks:
        return "refused", "UNSIGNED_TAG_NO_POLE"
    if not _SIGNED.fullmatch(marks):
        return "refused", "UNHANDLED_TAG_MARKER"
    if marks[0] not in rule.get("signs", "+-"):
        return "refused", "SIGN_OUTSIDE_RULE"
    pole = POS if marks[0] == "+" else NEG
    if pole == NEG and rule["coordinate"] not in BIPOLAR:
        return "refused", "NO_NEGATIVE_POLE"
    return "pole", pole


def _reading_facts(rule: dict) -> list[str]:
    return [laws.scope_name([fact]) for fact in laws.reading_facts(rule)]


_RANK = {"used": 3, "unbound": 2, "refused": 1, "recorded_only": 0}


def _apply_source_rule(rule, lemma, pos, tag, pole, sources, groups, w) -> tuple[str, str]:
    """A located tag binds its lemma and part of speech. With one reading it restricts that reading and sets the
    rule's reading facts on it; with several it is an obligation over them, and no per-reading guard is set."""
    units = [
        u for u in sources.framenet.get(lemma, ()) if u.pos == FRAMENET_POS.get(pos) and u.frame_name in rule["frames"]
    ]
    if not units:
        return "refused", "NO_ALIGNED_FRAME"
    rows = groups.get((lemma, pos))
    if rows is None:
        return "unbound", "NO_READING_FOR_LEMMA_POS"
    claims = {rule["coordinate"]: pole} | {bank: _VALUE[v] for bank, v in rule.get("companions", {}).items()}
    premises = (f"usas:{lemma}:{pos}:{tag}", *sorted({f"framenet:{u.word}.{u.pos}:{u.frame_name}" for u in units}))
    if rows.size == 1:
        for bank, allowed in claims.items():
            w.restrict(rows[0], bank, allowed, rule["rule_id"], ";".join(premises))
        for fact in _reading_facts(rule):
            w.fact(fact, rows[0])
        return "used", "RESTRICTION_ONE_READING"
    w.oblige(rule["rule_id"], claims, rows, premises)
    for fact in _reading_facts(rule):
        w.note("usas", "withheld", f"GUARD_NEEDS_ONE_READING:{fact}")
    return "used", "OBLIGATION_LEMMA_POS"


def _usas_lens(groups: dict, sources: Sources, book: dict, w: _Writer) -> None:
    rules = book["source_rules"]
    for rule in rules:
        w.declare(rule["rule_id"], _warrant(rule), USAS_FRAMENET)
    for lemma in sorted(sources.usas):
        key = lemma.replace("_", " ")
        for entry in sources.usas[lemma]:
            for tag in entry.semantic_tags:
                best = ("recorded_only", "NO_SOURCE_CONTRACT")
                for rule in rules:
                    kind, value = _match(rule, entry.pos, tag)
                    if kind == "skip":
                        continue
                    outcome = (
                        ("refused", value)
                        if kind == "refused"
                        else _apply_source_rule(rule, key, entry.pos, tag, value, sources, groups, w)
                    )
                    if _RANK[outcome[0]] > _RANK[best[0]]:
                        best = outcome
                w.note("usas", best[0], best[1])


# --- VerbNet with USAS: perception mode ------------------------------------------------------------------------


def _modes(rule: dict, entries) -> tuple[set[str], list[str]]:
    modes, tags = set(), []
    for entry in entries:
        if entry.pos != rule["source_pos"]:
            continue
        for tag in entry.semantic_tags:
            m = _TAG.fullmatch(tag)
            if "/" in tag or not m or m["category"] not in rule["category_modes"]:
                continue
            if m["marks"] and not _SIGNED.fullmatch(m["marks"]):
                continue
            modes.add(rule["category_modes"][m["category"]])
            tags.append(tag)
    return modes, tags


def _perception_lens(readings, groups: dict, perceivers: dict, sources: Sources, book: dict, w: _Writer) -> None:
    """VN_USAS_PERCEPTION_MODE: the function from VerbNet's own reading, the mode from USAS, on one reading."""
    for rule in book["native_residual_rules"]:
        if rule["native_predicate"] != PERCEIVE or rule["native_predicate_polarity"] != "positive":
            raise ValueError(f"UNSUPPORTED_RESIDUAL_RULE {rule['rule_id']}")
        rule_id = rule["rule_id"]
        w.declare(rule_id, _warrant(rule), VERBNET_USAS)
        for row, premises in sorted(perceivers.items()):
            lemma = readings[row].lemma.lower()
            rows = groups.get((lemma, rule["source_pos"]), np.zeros(0, dtype=np.int64))
            if rows.size != 1 or rows[0] != row:
                w.note(rule_id, "unbound", "USAS_BINDS_A_LEMMA_POS_OF_SEVERAL_READINGS")
                continue
            modes, tags = _modes(rule, sources.usas.get(lemma, ()))
            if not modes:
                w.note(rule_id, "recorded_only", "UNRESOLVED_NO_USAS_SENSORY_TAG")
            elif len(modes) > 1:
                w.note(rule_id, "refused", "MODE_NOT_UNIQUELY_LOCATED")
            elif (bank := rule["mode_coordinates"].get(next(iter(modes)))) is None:
                w.note(rule_id, "recorded_only", "OTHER_OR_UNSPECIFIED")
            else:
                w.restrict(row, bank, POS, rule_id, ";".join(premises + [f"usas:{lemma}:VERB:{t}" for t in tags]))
                w.note(rule_id, "used", "MODE_LOCATED")


# --- Ratings and associations: recorded, never written ---------------------------------------------------------


def _ratings_lens(lemmas: set[str], sources: Sources, book: dict, w: _Writer) -> None:
    policy = book["association_policy"]
    for source, observations in sorted(sources.ratings.items()):
        reason = policy.get(POLICY_KEYS.get(source, ""), UNLISTED_RATING)
        for lemma, count in observations.items():
            bound = lemma.lower().replace("_", " ") in lemmas
            w.note(source, "recorded_only" if bound else "unbound", reason if bound else "NO_READING_FOR_LEMMA", count)


def competence(book_path: Path = laws.LAWS) -> dict[str, dict]:
    """The published field-to-bank map: for each rule, its source, its binding, the native field it reads and the
    states it may write. A rating or association source may write nothing."""
    book = json.loads(Path(book_path).read_text())
    out: dict[str, dict] = {}
    for rule in book["native_predicate_rules"]:
        coordinate, pole = _pole(rule["prime"])
        writes = {coordinate: label(POS | NEG if rule["projection_kind"] == "TRANSITION_POLE" else pole)}
        if rule["predicate"] == "cause":
            writes |= {"DO": "+1", "HAPPEN": "+1"}
        conditions = {k: rule[k] for k in rule if k.startswith("requires_") or k == "class_number_prefix"}
        out[rule["rule_id"]] = {
            "source": VERBNET,
            "binding": "EXACT_WORDNET_SENSE_KEY",
            "field": f"semantics predicate {rule['predicate']} in every frame of the class",
            "scope": rule["scope"],
            "conditions": conditions,
            "writes": writes,
        }
        if coordinate in BIPOLAR:
            out[negated_pole(rule)] = {
                "source": VERBNET,
                "binding": "EXACT_WORDNET_SENSE_KEY",
                "field": f"semantics predicate {rule['predicate']} negated in every frame of the class",
                "scope": rule["scope"],
                "conditions": conditions,
                "writes": {coordinate: label(ALL & ~(POS if rule["projection_kind"] == "TRANSITION_POLE" else pole))},
            }
    for rule in book["source_rules"]:
        signs = rule.get("signs", "+-")
        writes = {rule["coordinate"]: label((POS if "+" in signs else 0) | (NEG if "-" in signs else 0))}
        writes |= dict(rule.get("companions", {}))
        categories = rule.get("categories") or [rule["category"]]
        out[rule["rule_id"]] = {
            "source": USAS_FRAMENET,
            "binding": "LEMMA_POS: an obligation; a restriction and the reading facts only on a single reading",
            "field": f"USAS {'/'.join(categories)} signed {signs} {'/'.join(rule['pos'])} with FrameNet {rule['frames']}",
            "writes": writes,
            "reading_facts": _reading_facts(rule),
        }
    for rule in book["native_residual_rules"]:
        out[rule["rule_id"]] = {
            "source": VERBNET_USAS,
            "binding": "EXACT_WORDNET_SENSE_KEY and a LEMMA_POS of that one reading",
            "field": f"{rule['native_predicate']} in every frame with USAS {rule['source_pos']} {rule['category_modes']}",
            "writes": {bank: "+1" for bank in rule["mode_coordinates"].values()},
        }
    policy = book["association_policy"]
    for source in RATINGS:
        out[source] = {
            "source": source,
            "writes": {},
            "policy": policy.get(POLICY_KEYS.get(source, ""), UNLISTED_RATING),
        }
    return out


def project(readings, sources: Sources, book_path: Path = laws.LAWS) -> LensOutput:
    """Every lens over the cohort: restrictions, facts, obligations and dispositions."""
    book = json.loads(Path(book_path).read_text())
    index = {r.reading_id: i for i, r in enumerate(readings)}
    groups = lemma_pos_groups(readings)
    w = _Writer(len(readings))
    perceivers = _verbnet_lens(index, sources, book, w)
    _usas_lens(groups, sources, book, w)
    _perception_lens(readings, groups, perceivers, sources, book, w)
    _ratings_lens({r.lemma.lower() for r in readings}, sources, book, w)
    return w.output()


# --- Closure with the laws ------------------------------------------------------------------------------------


def restriction_relations(restrictions: Restrictions, n: int) -> tuple[tuple[Relation, ...], dict[str, np.ndarray]]:
    """Each (rule, bank, mask) as a one-bank relation over the readings it restricts, so closure records the lens
    rule as the cause and wakes the laws that read the bank."""
    relations, scopes = [], {}
    keys = np.stack([restrictions.rules.astype(np.int64), restrictions.cols, restrictions.allowed.astype(np.int64)])
    for rule, col, mask in np.unique(keys, axis=1).T:
        rule_id, bank = restrictions.rule_ids[rule], BANKS[col]
        scope = f"lens:{rule_id}:{bank}:{label(mask)}"
        chosen = (keys[0] == rule) & (keys[1] == col) & (keys[2] == mask)
        scopes[scope] = np.zeros(n, dtype=bool)
        scopes[scope][restrictions.rows[chosen]] = True
        allowed = tuple((s,) for s in _STATES if int(mask) & s)
        relations.append(Relation(f"lens:{rule_id}", (bank,), allowed, restrictions.warrants[rule], scope))
    return tuple(relations), scopes


def closure_round(readings, lens: LensOutput, book_path: Path = laws.LAWS) -> dict:
    """One round of the authored laws with the lens: guards merged with the lens facts, plus its restrictions."""
    ids = [r.reading_id for r in readings]
    law_relations = laws.compile_laws(book_path)
    checks = laws.required_checks(book_path)
    wanted = {r.scope for r in law_relations} | {c.scope for c in checks}
    laws_only = State.opening(ids)
    opening = laws_only.census()
    laws_receipt = close(laws_only, law_relations, guards.scopes(readings, wanted))
    lens_relations, lens_scopes = restriction_relations(lens.restrictions, len(ids))
    state = State.opening(ids)
    derivations = Derivations()
    scopes = guards.scopes(readings, wanted, lens.facts) | lens_scopes
    # Lens relations first, so a removal the direct premise makes is credited to it (the fixed point is the same).
    receipt = close(state, lens_relations + law_relations, scopes, derivations)
    d = derivations.arrays()
    removals = Counter(d["rule_ids"][d["rules"]].tolist()) if d["rules"].size else Counter()
    decided = state.counts() == 1
    newly = decided & ~(laws_only.counts() == 1)
    conflict_rows, conflict_cols = np.nonzero(state.counts() == 0)
    return {
        "opening": opening,
        "laws_only": laws_only.census() | {"seconds": laws_receipt["seconds"]},
        "laws_and_lens": state.census() | {k: receipt[k] for k in ("relations", "applications", "removals", "seconds")},
        "bits_removed_by_lens": laws_only.bits() - state.bits(),
        "newly_decided_by_bank": {BANKS[c]: int(k) for c, k in enumerate(newly.sum(axis=0)) if k},
        "removals_by_rule": dict(sorted(removals.items())),
        "conflicts": [[ids[r], BANKS[c]] for r, c in zip(conflict_rows, conflict_cols)],
        "relations_by_kind": dict(Counter(r.rule_id.split(":")[0] for r in law_relations + lens_relations)),
        "readings_in_scope": {name: int(scopes[name].sum()) for name in sorted(wanted)},
        "required_checks": laws.check(state.masks, scopes, checks),
        "uncompiled_cells": list(laws.uncompiled_cells(book_path)),
    }


# --- The real cohort ------------------------------------------------------------------------------------------


def _require(name: str, check: Callable[[], object]) -> None:
    """Fail on a missing corpus instead of letting a parser download it."""
    try:
        check()
    except LookupError as error:
        raise RuntimeError(f"SOURCE_UNAVAILABLE {name}") from error


def _rating_sources() -> dict[str, dict[str, int]]:
    from GSE.curation.external_sources.concreteness import ConcretenessParser
    from GSE.curation.external_sources.lancaster_sensorimotor import LancasterSensorimotorParser
    from GSE.curation.external_sources.nrc_emotion import NRCEmotionParser
    from GSE.curation.external_sources.nrc_vad import NRCVADParser
    from GSE.curation.external_sources.sentiwordnet import SentiWordNetParser

    ratings: dict[str, dict[str, int]] = {}
    for name, parser in (
        ("nrc_emotion", NRCEmotionParser()),
        ("nrc_vad", NRCVADParser()),
        ("lancaster", LancasterSensorimotorParser()),
        ("concreteness", ConcretenessParser()),
    ):
        if not parser.data_path.exists():
            raise RuntimeError(f"SOURCE_UNAVAILABLE {name}")
        parser.load()
        ratings[name] = {word: 1 for word in parser.entries}
    from nltk.corpus import sentiwordnet

    _require("sentiwordnet", lambda: sentiwordnet.senti_synset("good.a.01"))
    swn = SentiWordNetParser()
    swn.load()
    ratings["sentiwordnet"] = {word: len(entries) for word, entries in swn.entries.items()}
    from GSE.curation.external_sources.conceptnet import CONCEPTNET_DB

    db = sqlite3.connect(f"file:{CONCEPTNET_DB}?mode=ro", uri=True)
    try:
        ratings["conceptnet"] = dict(db.execute("SELECT start_word, COUNT(*) FROM edges GROUP BY start_word"))
    finally:
        db.close()
    return ratings


def load_sources() -> tuple[Sources, dict[str, float]]:
    """Every parser, loaded once, offline. Returns the sources and the seconds each took."""
    from nltk.corpus import framenet, verbnet, wordnet

    from GSE.curation.external_sources.framenet import FrameNetParser
    from GSE.curation.external_sources.usas import USASParser
    from GSE.curation.external_sources.verbnet import VerbNetParser

    seconds = {}
    started = time.perf_counter()
    _require("wordnet", wordnet.get_version)
    _require("verbnet", verbnet.classids)
    vn = VerbNetParser()
    if not vn.load():
        raise RuntimeError("SOURCE_UNAVAILABLE verbnet")
    seconds["verbnet"] = time.perf_counter() - started
    started = time.perf_counter()
    usas = USASParser()
    if not usas.lexicon_path.exists() or not usas.load():
        raise RuntimeError("SOURCE_UNAVAILABLE usas")
    seconds["usas"] = time.perf_counter() - started
    started = time.perf_counter()
    _require("framenet", lambda: framenet.frame_by_name("Fear"))
    fn = FrameNetParser()
    if not fn.load():
        raise RuntimeError("SOURCE_UNAVAILABLE framenet")
    seconds["framenet"] = time.perf_counter() - started
    started = time.perf_counter()
    ratings = _rating_sources()
    seconds["ratings"] = time.perf_counter() - started
    sources = Sources(
        verbnet=vn.entries,
        links=lambda entry: vn.definition_links(entry, wordnet),
        usas=usas.entries,
        framenet=fn.entries,
        ratings=ratings,
    )
    return sources, {k: round(v, 2) for k, v in seconds.items()}


def main(argv=None) -> dict:
    parser = argparse.ArgumentParser(
        description="Run the source lenses over the pinned cohort, then one closure round."
    )
    parser.add_argument("--cohort", type=Path, default=Path("data/lexicon_builder/rebuild/cohort.jsonl"))
    parser.add_argument("--receipt", type=Path, default=None)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    readings = inventory.load(args.cohort)
    cohort_seconds = time.perf_counter() - started
    sources, load_seconds = load_sources()
    started = time.perf_counter()
    lens = project(readings, sources)
    project_seconds = time.perf_counter() - started
    round_ = closure_round(readings, lens)
    receipt = {
        "format": "GSE.rebuild-source-lenses/1",
        "cohort": {"readings": len(readings), "sha256": inventory.digest(readings)},
        "seconds": {"cohort": round(cohort_seconds, 2), "load": load_seconds, "project": round(project_seconds, 2)},
        "competence": competence(),
        "lens": lens.census(),
        "closure": round_,
    }
    if args.receipt:
        args.receipt.write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps(receipt, indent=1))
    return receipt


if __name__ == "__main__":
    main()
