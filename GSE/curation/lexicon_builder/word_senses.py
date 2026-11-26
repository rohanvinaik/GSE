"""Word senses: a word's definitions collapse, by coherence, into its few real senses.

Rohan's design (``openspec/changes/lexicon-symbolic-foundation/design.md``, *Founder correction*):
definitions are the same sense when they resolve to the same values on the load-bearing banks.
A bank is load-bearing in a definition when a source assertion or a rule resolved it against
real alternatives. Its weight is the alternatives removed times (1 + the bank's downstream
reach: how many rules name it). Part-of-speech conventions (GOOD = 0 on nouns,
SOMETHING = 0 on adjectives and adverbs) and the I/YOU zeros are not load-bearing.

- Splitting needs a witness, a conflict on a load-bearing bank. A definition with no load-bearing
  value is absorbed into the main sense and never becomes a sense of its own.
- A sense's core holds every value its members resolved. A bank its members disagree on is
  contested and carries both values. The core then takes the word's agreed source signs
  (``source_agreement``) that contradict nothing, and is closed under the release's own rules
  with the existing resolver.
- An agreed sign that a member value or a rule contradicts is not committed. It is recorded as
  blocked, with its cause.
- Where the candidate carries the genus/differentia closure (``derived:genus-differentia``, Rohan's
  decision 1 of 2026-11-26), the cells it settled on a sense's definitions are member evidence of the
  lowest standing: they fill a bank no stated member value and no agreed sign speaks to, only where
  every definition of the sense holds the same derived value, under the rules, with the warrant ``genus-differentia`` naming the definitions whose closure record holds
  them. They are never load-bearing, never a source vote, and never contest a stated value.
- Proper names are not word senses (they are handled elsewhere).

Everything here is computed from the release and the sources, so ``verify`` can rebuild and
compare it. No release table or definition state is changed.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .engine import Assertion
from .foundation import BANKS, definition_context
from .resolution import resolve_dictionary

FORMAT = "GSE.word-senses/1"
CONVENTION_RULES = frozenset(
    {"founder:noun-own-evaluation", "founder:adjective-not-object", "founder:adverb-not-object"}
)
CONVENTION_ZERO_BANKS = frozenset({"I", "YOU"})
EXCLUDED_POS = frozenset({"name"})
# Rohan's ruling (2026-11-24, option (c), "be very judicious"): a noun carries an agreed GOOD sign
# only when the word names a feeling ("'Hatred' is a negative emotion ... an idea that is inherently
# of negative valence"). Decided by WordNet's category for the sense's most common WordNet
# definition: hatred, love, joy, anger, fear, grief, pride are noun.feeling; pain and happiness
# (states), success (event), beauty (attribute), mom (person) and murder (act) are not.
FEELING_NOUN_CATEGORIES = frozenset({"noun.feeling"})
NOUN_EVALUATION_RULE = "founder:noun-own-evaluation"
# Definitions resolving the same load-bearing values that count as coherence across definitions
# (a judgment, recorded in the design): one or two can be an incidental minority sense.


@dataclass(frozen=True)
class Definition:
    entry_id: str
    lexeme_id: int
    pos: str
    resolved: Mapping[str, int]  # the definition's stored values (primitive_values)
    load_bearing: Mapping[str, tuple[int, float, str, str]]  # bank -> (value, weight, cause, kind)
    conventions: Mapping[str, str] = field(default_factory=dict)  # bank -> convention rule that set it
    # Cells the genus/differentia closure settled (``word_sense_genus_differentia.CHANNEL``): member
    # evidence below every stated value, never load-bearing, never a source vote.
    derived: Mapping[str, int] = field(default_factory=dict)

    @property
    def weight(self) -> float:
        return sum(entry[1] for entry in self.load_bearing.values())


@dataclass
class Sense:
    core: dict[str, int] = field(default_factory=dict)  # load-bearing values that define it
    members: list[Definition] = field(default_factory=list)
    absorbed: list[Definition] = field(default_factory=list)

    @property
    def weight(self) -> float:
        return sum(member.weight for member in self.members)


def downstream_reach(relations: Sequence) -> dict[str, int]:
    """How many rules name each bank: a value there settles or constrains that many others."""
    reach: dict[str, int] = {}
    for relation in relations:
        for bank in relation.banks:
            reach[bank] = reach.get(bank, 0) + 1
    return reach


def load_bearing_values(trace: Sequence[Mapping], reach: Mapping[str, int]) -> dict[str, tuple[int, float, str, str]]:
    """The values a definition's derivation resolved against real alternatives."""
    values: dict[str, tuple[int, float, str, str]] = {}
    for entry in trace:
        if entry.get("kind") not in ("ASSERTION", "RELATION"):
            continue
        remaining, removed, bank = entry.get("remaining"), entry.get("removed"), entry.get("bank")
        if not bank or not removed or not isinstance(remaining, list) or len(remaining) != 1:
            continue
        cause = entry.get("rule_id") or entry.get("source") or entry["kind"]
        value = remaining[0]
        if cause in CONVENTION_RULES or (value == 0 and bank in CONVENTION_ZERO_BANKS):
            continue
        weight = len(removed) * (1 + reach.get(bank, 0))
        previous = values.get(bank)
        values[bank] = (value, max(weight, previous[1]) if previous else weight, cause, entry["kind"])
    return values


def convention_values(trace: Sequence[Mapping]) -> dict[str, str]:
    """The banks a part-of-speech convention rule set, and which rule."""
    return {
        entry["bank"]: entry["rule_id"]
        for entry in trace
        if entry.get("kind") == "RELATION" and entry.get("rule_id") in CONVENTION_RULES and entry.get("bank")
    }


DERIVED_TABLE = "genus_differentia_closure"
DERIVED_WARRANT = "genus-differentia"


def derived_cells(conn: sqlite3.Connection, entry_id: str) -> dict[str, int]:
    """The cells the genus/differentia closure settled on one definition, when the candidate has them."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (DERIVED_TABLE,)).fetchone() is None:
        return {}
    row = conn.execute(f"SELECT settled FROM {DERIVED_TABLE} WHERE entry_id = ?", (entry_id,)).fetchone()
    return json.loads(row[0]) if row else {}


def read_definitions(conn: sqlite3.Connection, lemma: str, reach: Mapping[str, int]) -> dict[str, list[Definition]]:
    """A lemma's definitions by part of speech, proper names excluded."""
    by_pos: dict[str, list[Definition]] = {}
    rows = conn.execute(
        "SELECT l.id, l.pos, d.entry_id, d.trace FROM lexemes l JOIN definition_states d ON d.lexeme_id = l.id "
        "WHERE l.lemma = ? ORDER BY d.entry_id",
        (lemma,),
    ).fetchall()
    for lexeme_id, pos, entry_id, trace in rows:
        if pos in EXCLUDED_POS:
            continue
        resolved = {
            bank: value
            for bank, value in conn.execute(
                "SELECT primitive, value FROM primitive_values WHERE lexeme_id = ?", (lexeme_id,)
            )
        }
        steps = json.loads(trace or "[]")
        derived = {bank: value for bank, value in derived_cells(conn, entry_id).items() if bank not in resolved}
        by_pos.setdefault(pos, []).append(
            Definition(
                entry_id,
                lexeme_id,
                pos,
                resolved,
                load_bearing_values(steps, reach),
                convention_values(steps),
                derived,
            )
        )
    return by_pos


# Which word-level families can say which sense is a word's main one. WordNet's word-level
# projection is its first (most frequent) sense, and the rating lexicons rate a word's dominant
# use. VerbNet's word-level vote is the union of every class the verb belongs to, so it says
# nothing about which sense is meant.
_SELF_IDENTIFYING = frozenset({"wordnet_hierarchy"})
_NOT_SENSE_IDENTIFYING = frozenset({"verb_structure"})


def _corroborated(bank: str, value: int, group: Sequence[Definition], corroboration) -> bool:
    """An added value is corroborated by a measuring, sense-identifying word-level family that
    is independent of the family that gave the definition the value."""
    from .source_agreement import family_of

    families = {
        family for family in corroboration.get(bank, {}).get(value, frozenset()) if family not in _NOT_SENSE_IDENTIFYING
    }
    if not families:
        return False
    for definition in group:
        entry = definition.load_bearing.get(bank)
        if entry is None or entry[3] != "ASSERTION":
            continue
        own = family_of(entry[2])
        if not any(family != own or family in _SELF_IDENTIFYING for family in families):
            return False
    return True


def collapse(
    definitions: Sequence[Definition],
    anchor: Mapping[str, int] | None = None,
    corroboration: Mapping[str, Mapping[int, frozenset[str]]] | None = None,
) -> list[Sense]:
    """Group one part of speech's definitions into senses.

    Definitions with the same load-bearing encoding are one sense (Rohan, 2026-11-25 03:28: "They're the same sense
    of the word if they resolve to the same bank encodings across ... the load-bearing banks"). A definition that adds
    or lacks a load-bearing value is another sense; nothing merges on mere absence of conflict, and corroboration does
    not merge encodings (the nail witness). No sense is ranked or made a default; grammar and context choose among
    them at read time. A definition with no load-bearing value forms no sense: it is listed on the first stored sense
    for identity only. ``corroboration`` is accepted for compatibility and no longer merges senses.
    """
    anchor = anchor or {}
    corroboration = corroboration or {}
    groups: dict[frozenset, list[Definition]] = {}
    for definition in (d for d in definitions if d.load_bearing):
        key = frozenset((bank, entry[0]) for bank, entry in definition.load_bearing.items())
        groups.setdefault(key, []).append(definition)

    def rank(item):
        key, group = item
        return (
            len(key),  # the most general encoding first: a more specific group joins only on corroboration
            -len(group),
            -sum(d.weight for d in group),
            min(d.entry_id for d in group),
        )

    ordered = [sorted(group, key=lambda d: d.entry_id) for _key, group in sorted(groups.items(), key=rank)]
    senses: list[Sense] = []
    for group in ordered:
        values = {bank: entry[0] for bank, entry in group[0].load_bearing.items()}
        for sense in senses:
            # Rohan (2026-11-25 03:28): "They're the same sense of the word if they resolve to the same bank encodings
            # across the ones that are of high salience ... the load-bearing banks." Equality, not mere absence of
            # conflict: a group that adds or lacks a load-bearing value is another meaning (the nail witness: the unit
            # of length's QUANTITY+ must not join the fastener).
            if values != sense.core:
                continue
            sense.members.extend(group)
            break
        else:
            senses.append(Sense(core=dict(values), members=list(group)))
    if not senses:
        senses.append(Sense(core=dict(anchor)))
    senses[1:] = sorted(
        senses[1:],
        key=lambda sense: (-len(sense.members), -sense.weight, sense.members[0].entry_id if sense.members else ""),
    )
    senses[0].absorbed.extend(d for d in definitions if not d.load_bearing)
    return senses


def _resolve(assertions: Sequence[Assertion], relations: Sequence, pos: str):
    return resolve_dictionary(BANKS, tuple(assertions), tuple(relations), definition_context(pos))


def settle_anchor(agreed: Mapping[str, int], relations: Sequence, pos: str) -> dict[str, int]:
    """The agreed signs as this part of speech's rules allow them, with their consequences.

    A sign a rule forbids for this part of speech (GOOD on a noun, under the founder rule) is
    dropped; the rules' consequences (HAPPEN from DO) are added. Zeros are left out: the anchor
    marks what the sources positively establish.
    """
    kept: list[Assertion] = []
    for bank, sign in sorted(agreed.items()):
        trial = Assertion(bank, sign, "source-agreement", "agreement", "source-agreement")
        if _resolve(kept + [trial], relations, pos).code != "CONFLICT":
            kept.append(trial)
    if not kept:
        return {}
    closed = _resolve(kept, relations, pos)
    return {bank: value for bank, value in closed.assignments.items() if value}


def close_sense(
    lemma: str,
    pos: str,
    index: int,
    sense: Sense,
    agreed: Mapping[str, int],
    relations: Sequence,
    feeling_noun: bool = False,
) -> dict:
    """A sense's core: members' values, agreed source signs, closed under the rules."""
    if feeling_noun:  # the noun-evaluation zero does not apply to a word that names a feeling
        relations = [relation for relation in relations if relation.rule_id != NOUN_EVALUATION_RULE]
    values: dict[str, set[int]] = {}
    for definition in sense.members + sense.absorbed:
        for bank, value in definition.resolved.items():
            if feeling_noun and definition.conventions.get(bank) == NOUN_EVALUATION_RULE:
                continue
            values.setdefault(bank, set()).add(value)
    fixed = {bank: next(iter(v)) for bank, v in values.items() if len(v) == 1}
    contested = {bank: sorted(v) for bank, v in values.items() if len(v) > 1}
    record = f"sense:{lemma}:{pos}:{index}"
    base = [Assertion(bank, value, "word-sense", record, "word-sense") for bank, value in sorted(fixed.items())]
    blocked: dict[str, dict] = {}
    candidates = []
    for bank, sign in sorted(agreed.items()):
        if bank in contested:
            blocked[bank] = {"sign": sign, "cause": "CONTESTED_BY_MEMBERS", "values": contested[bank]}
        elif bank in fixed and fixed[bank] != sign:
            blocked[bank] = {"sign": sign, "cause": "CONTRADICTS_MEMBER_VALUE", "value": fixed[bank]}
        elif bank not in fixed:
            candidates.append(Assertion(bank, sign, "source-agreement", f"agreement:{lemma}", "source-agreement"))
    resolution = _resolve(base, relations, pos)
    if resolution.code == "CONFLICT":
        return _row(lemma, pos, index, sense, fixed, contested, resolution, [], blocked, "MEMBERS_CONFLICT_UNDER_RULES")
    kept = []
    for candidate in candidates:  # each agreed sign alone, then together
        trial = _resolve(base + [candidate], relations, pos)
        if trial.code == "CONFLICT":
            blocked[candidate.bank] = {
                "sign": candidate.value,
                "cause": "RULE_CONFLICT",
                "rules": _conflict_rules(trial),
            }
        else:
            kept.append(candidate)
    while kept:
        resolution = _resolve(base + kept, relations, pos)
        if resolution.code != "CONFLICT":
            break
        dropped = kept.pop()  # a joint conflict: drop the last (bank order), deterministically
        blocked[dropped.bank] = {
            "sign": dropped.value,
            "cause": "JOINT_RULE_CONFLICT",
            "rules": _conflict_rules(resolution),
        }
    else:
        resolution = _resolve(base, relations, pos)
    derived, derived_contested = derived_values(sense, set(fixed) | set(contested) | set(agreed), feeling_noun)
    added, sources = [], {}
    for bank, (value, entries) in sorted(derived.items()):  # each derived value alone, then together
        if bank in resolution.assignments:
            continue  # the stated values and the rules already settle it
        candidate = Assertion(bank, value, DERIVED_WARRANT, f"{DERIVED_WARRANT}:{lemma}:{pos}:{index}", DERIVED_WARRANT)
        trial = _resolve(base + kept + [candidate], relations, pos)
        if trial.code == "CONFLICT":
            blocked[bank] = {"sign": value, "cause": "DERIVED_RULE_CONFLICT", "rules": _conflict_rules(trial)}
        else:
            added.append(candidate)
            sources[bank] = entries
    while added:
        joint = _resolve(base + kept + added, relations, pos)
        if joint.code != "CONFLICT":
            resolution = joint
            break
        dropped = added.pop()
        sources.pop(dropped.bank)
        blocked[dropped.bank] = {
            "sign": dropped.value,
            "cause": "DERIVED_JOINT_RULE_CONFLICT",
            "rules": _conflict_rules(joint),
        }
    row = _row(lemma, pos, index, sense, fixed, contested, resolution, kept, blocked, resolution.code, sources)
    for bank, values in derived_contested.items():
        if bank not in row["assignments"]:
            row["open"].setdefault(bank, values)
    if feeling_noun and "GOOD" in row["provenance"]:
        # Recorded where it is stored, so a rebuild compares equal (Rohan's ruling D-1).
        row["provenance"]["GOOD"]["exemption"] = "feeling-noun"
    return row


def derived_values(
    sense: Sense, settled: set[str], feeling_noun: bool = False
) -> tuple[dict[str, tuple[int, list[str]]], dict[str, list[int]]]:
    """The closure's derived cells over a sense's member definitions, on banks no stated member value and no agreed
    source sign speaks to: bank -> (value, the definitions) where every member holds the same derived value, and
    bank -> values where they hold different ones. A value only some members hold is not the sense's: members share a
    thin stated encoding but can differ below it (run.v.26 is causative by its ancestry, run.v.01 is not), and the
    others are unknown there, not in agreement. Absorbed definitions carry no load-bearing value and are not the
    meaning, so they neither hold nor block a value. Derived values fill; they never contest or override a stated
    value. A feeling noun takes no derived GOOD (the noun-evaluation zero does not apply to it)."""
    definitions = sense.members
    found: dict[str, dict[int, list[str]]] = {}
    for definition in definitions:
        for bank, value in definition.derived.items():
            if bank in settled or (feeling_noun and bank == "GOOD"):
                continue
            found.setdefault(bank, {}).setdefault(value, []).append(definition.entry_id)
    agreed = {
        bank: (value, sorted(entries))
        for bank, by_value in found.items()
        if len(by_value) == 1
        for value, entries in by_value.items()
        if definitions and len(entries) == len(definitions)
    }
    return agreed, {bank: sorted(v) for bank, v in found.items() if len(v) > 1}


def _conflict_rules(resolution) -> list[str]:
    rules = set()
    for conflict in resolution.conflicts:
        for key in ("rule_id", "rule_ids", "relation", "relations"):
            value = conflict.get(key) if isinstance(conflict, Mapping) else None
            if isinstance(value, str):
                rules.add(value)
            elif isinstance(value, (list, tuple)):
                rules.update(str(v) for v in value)
    return sorted(rules)


def rule_warrants(resolution, bank: str) -> list[str]:
    """The rules the solver's trace names for fixing one bank: the warrant of a value from closure."""
    named = {e["rule_id"] for e in resolution.trace if e.get("kind") == "RELATION" and e.get("bank") == bank}
    if not named:
        named = {
            rule
            for e in resolution.trace
            if e.get("kind") == "JOINT_CHECK" and bank in e.get("banks", ())
            for rule in e.get("rule_ids", ())
        }
    if not named:
        named = {
            e["rule_id"]
            for e in resolution.trace
            if e.get("kind") == "EVIDENCE_GUARD" and e.get("status") != "BLOCKED" and bank in e["relation"]["banks"]
        }
    return sorted(named)


def _row(lemma, pos, index, sense, fixed, contested, resolution, kept, blocked, code, derived=None) -> dict:
    assignments = dict(resolution.assignments) if code != "MEMBERS_CONFLICT_UNDER_RULES" else dict(fixed)
    agreed_banks = {assertion.bank for assertion in kept}
    derived = derived or {}
    provenance = {}
    for bank, value in sorted(assignments.items()):
        if bank in fixed:
            sources = sorted(d.entry_id for d in sense.members + sense.absorbed if d.resolved.get(bank) == value)
            provenance[bank] = {"from": "members", "entries": sources}
        elif bank in agreed_banks:
            provenance[bank] = {"from": "source-agreement"}
        elif bank in derived:
            provenance[bank] = {"from": DERIVED_WARRANT, "entries": derived[bank]}
        else:
            provenance[bank] = {"from": "rules", "rules": rule_warrants(resolution, bank)}
    open_domains = {
        bank: sorted(domain)
        for bank, domain in sorted(resolution.domains.items())
        if 1 < len(domain) < 3 and bank not in assignments
    }
    open_domains.update({bank: values for bank, values in contested.items()})
    return {
        "lemma": lemma,
        "pos": pos,
        "sense": index,
        "code": code,
        "core": {bank: sense.core[bank] for bank in sorted(sense.core)},
        "members": [d.entry_id for d in sense.members],
        "absorbed": [d.entry_id for d in sense.absorbed],
        "assignments": assignments,
        "open": open_domains,
        "provenance": provenance,
        "blocked": blocked,
    }


_WORDNET_POS = {"noun": "n", "verb": "v", "adj": "a", "adv": "r"}


def names_a_feeling(lemma: str, sense: Sense) -> bool:
    """Whether the sense's most common WordNet definition is in WordNet's feeling category."""
    from nltk.corpus import wordnet

    order = {synset.name(): rank for rank, synset in enumerate(wordnet.synsets(lemma, "n"))}
    held = [
        d.entry_id.rsplit(":", 1)[-1]
        for d in sense.members + sense.absorbed
        if d.entry_id.startswith("wordnet:") and d.entry_id.rsplit(":", 1)[-1] in order
    ]
    if not held:
        return False
    primary = min(held, key=order.__getitem__)
    return wordnet.synset(primary).lexname() in FEELING_NOUN_CATEGORIES


def dominant_pos(by_pos: Mapping[str, Sequence[Definition]]) -> str | None:
    """The part of speech with the most definitions; ties go to noun, verb, adjective, adverb."""
    order = {"noun": 0, "verb": 1, "adj": 2, "adv": 3}
    ranked = sorted(by_pos, key=lambda pos: (-len(by_pos[pos]), order.get(pos, 9), pos))
    return ranked[0] if ranked else None


def build_word(
    conn: sqlite3.Connection, lemma: str, votes: Mapping[str, Mapping[str, int]], relations: Sequence, reach
) -> list[dict]:
    """Every sense of every part of speech of one lemma."""
    from .source_agreement import agree, committed_signs, family_of, measures, votes_for_pos

    by_pos = read_definitions(conn, lemma, reach)
    dominant = dominant_pos(by_pos)
    corroboration: dict[str, dict[int, frozenset[str]]] = {}
    for source, signs in votes.items():
        family = family_of(source)
        for bank, sign in signs.items():
            if measures(family, bank):  # only a family that measures the bank corroborates
                by_sign = corroboration.setdefault(bank, {})
                by_sign[sign] = by_sign.get(sign, frozenset()) | {family}
    rows = []
    for pos, definitions in sorted(by_pos.items()):
        agreement = agree(votes_for_pos(votes, pos, pos == dominant))
        agreed = committed_signs(agreement)
        anchor = settle_anchor(agreed, relations, pos)
        for index, sense in enumerate(collapse(definitions, anchor, corroboration)):
            feeling = pos == "noun" and names_a_feeling(lemma, sense)
            # NSM molecule inheritance (word_sense_nsm_molecules): what every member inherits from a bound NSM
            # category explication, on banks no member value or agreed source sign speaks to.
            inherited = {}
            if pos == "noun":
                from .word_sense_nsm_molecules import sense_inheritance

                stated = {bank for d in sense.members for bank in d.resolved} | set(agreed)
                inherited = {
                    b: v for b, v in sense_inheritance([d.entry_id for d in sense.members]).items() if b not in stated
                }
            sense_agreed = {**agreed, **{bank: value for bank, (value, _w) in inherited.items()}}
            row = close_sense(lemma, pos, index, sense, sense_agreed, relations, feeling)
            for bank, origin in row["provenance"].items():
                if bank in inherited and origin["from"] == "source-agreement":
                    origin["from"] = "nsm-molecule"
                    origin["warrant"] = inherited[bank][1]
                elif origin["from"] == "source-agreement":  # name the agreeing measuring families
                    origin["families"] = list(agreement[bank].measuring[row["assignments"][bank]])
            rows.append(row)
    return rows


SCHEMA = """
CREATE TABLE IF NOT EXISTS word_senses (
    lemma TEXT NOT NULL,
    pos TEXT NOT NULL,
    sense INTEGER NOT NULL,
    code TEXT NOT NULL,
    core TEXT NOT NULL,
    members TEXT NOT NULL,
    absorbed TEXT NOT NULL,
    assignments TEXT NOT NULL,
    open TEXT NOT NULL,
    provenance TEXT NOT NULL,
    blocked TEXT NOT NULL,
    PRIMARY KEY (lemma, pos, sense)
);
CREATE TABLE IF NOT EXISTS word_source_agreement (
    lemma TEXT PRIMARY KEY,
    agreement TEXT NOT NULL
);
"""

_COLUMNS = (
    "lemma",
    "pos",
    "sense",
    "code",
    "core",
    "members",
    "absorbed",
    "assignments",
    "open",
    "provenance",
    "blocked",
)


def write_word(conn: sqlite3.Connection, lemma: str, agreement_record: Mapping, rows: Sequence[dict]) -> None:
    conn.execute("DELETE FROM word_senses WHERE lemma = ?", (lemma,))
    conn.execute(
        "INSERT OR REPLACE INTO word_source_agreement(lemma, agreement) VALUES (?, ?)",
        (lemma, json.dumps(agreement_record, sort_keys=True)),
    )
    conn.executemany(
        f"INSERT INTO word_senses({', '.join(_COLUMNS)}) VALUES ({', '.join('?' * len(_COLUMNS))})",
        [
            tuple(json.dumps(row[c], sort_keys=True) if isinstance(row[c], (dict, list)) else row[c] for c in _COLUMNS)
            for row in rows
        ],
    )


def stored_rows(conn: sqlite3.Connection, lemma: str) -> list[dict]:
    out = []
    for values in conn.execute(
        f"SELECT {', '.join(_COLUMNS)} FROM word_senses WHERE lemma = ? ORDER BY pos, sense", (lemma,)
    ):
        row = dict(zip(_COLUMNS, values))
        for key in ("core", "members", "absorbed", "assignments", "open", "provenance", "blocked"):
            row[key] = json.loads(row[key])
        out.append(row)
    return out
