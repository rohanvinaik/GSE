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


@dataclass(frozen=True)
class Definition:
    entry_id: str
    lexeme_id: int
    pos: str
    resolved: Mapping[str, int]  # the definition's stored values (primitive_values)
    load_bearing: Mapping[str, tuple[int, float, str, str]]  # bank -> (value, weight, cause, kind)

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
        by_pos.setdefault(pos, []).append(
            Definition(entry_id, lexeme_id, pos, resolved, load_bearing_values(json.loads(trace or "[]"), reach))
        )
    return by_pos


def collapse(
    definitions: Sequence[Definition],
    anchor: Mapping[str, int] | None = None,
    corroboration: Mapping[str, frozenset[int]] | None = None,
) -> list[Sense]:
    """Group one part of speech's definitions into senses.

    The main sense is seeded by ``anchor``, the word's agreed source signs for this part of
    speech: where independent sources converge is the word's obvious meaning. A definition joins
    a sense when it conflicts with none of the sense's values and either refines it fully (it
    resolves every bank the sense has) or every source-asserted value it adds is corroborated by
    an independent word-level source (``corroboration``: bank -> signs any source votes). That
    is the same agreement across independent evidence, between the definition and the word.
    Values a rule derived follow from the definition's own evidence and need no corroboration.
    A definition that adds an uncorroborated value is a different meaning and starts its own
    sense. A definition with no load-bearing value is absorbed into the main sense.
    """
    corroboration = corroboration or {}
    senses: list[Sense] = [Sense(core=dict(anchor))] if anchor else []
    evidenced = sorted((d for d in definitions if d.load_bearing), key=lambda d: (-d.weight, d.entry_id))
    for definition in evidenced:
        values = {bank: entry[0] for bank, entry in definition.load_bearing.items()}
        asserted = {bank for bank, entry in definition.load_bearing.items() if entry[3] == "ASSERTION"}
        for sense in senses:
            if any(sense.core.get(bank, value) != value for bank, value in values.items()):
                continue
            added = {bank: value for bank, value in values.items() if bank not in sense.core and bank in asserted}
            corroborated = all(value in corroboration.get(bank, ()) for bank, value in added.items())
            if corroborated or sense.core.keys() <= values.keys():
                sense.core.update(values)
                sense.members.append(definition)
                break
        else:
            senses.append(Sense(core=dict(values), members=[definition]))
    if not senses:
        senses.append(Sense())
    head, rest = (senses[:1], senses[1:]) if anchor else ([], senses)
    rest.sort(key=lambda sense: (-sense.weight, sense.members[0].entry_id if sense.members else ""))
    senses = head + rest
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


def close_sense(lemma: str, pos: str, index: int, sense: Sense, agreed: Mapping[str, int], relations: Sequence) -> dict:
    """A sense's core: members' values, agreed source signs, closed under the rules."""
    values: dict[str, set[int]] = {}
    for definition in sense.members + sense.absorbed:
        for bank, value in definition.resolved.items():
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
    return _row(lemma, pos, index, sense, fixed, contested, resolution, kept, blocked, resolution.code)


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


def _row(lemma, pos, index, sense, fixed, contested, resolution, kept, blocked, code) -> dict:
    assignments = dict(resolution.assignments) if code != "MEMBERS_CONFLICT_UNDER_RULES" else dict(fixed)
    agreed_banks = {assertion.bank for assertion in kept}
    provenance = {}
    for bank, value in sorted(assignments.items()):
        if bank in fixed:
            sources = sorted(d.entry_id for d in sense.members + sense.absorbed if d.resolved.get(bank) == value)
            provenance[bank] = {"from": "members", "entries": sources}
        elif bank in agreed_banks:
            provenance[bank] = {"from": "source-agreement"}
        else:
            provenance[bank] = {"from": "rules"}
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


def dominant_pos(by_pos: Mapping[str, Sequence[Definition]]) -> str | None:
    """The part of speech with the most definitions; ties go to noun, verb, adjective, adverb."""
    order = {"noun": 0, "verb": 1, "adj": 2, "adv": 3}
    ranked = sorted(by_pos, key=lambda pos: (-len(by_pos[pos]), order.get(pos, 9), pos))
    return ranked[0] if ranked else None


def build_word(
    conn: sqlite3.Connection, lemma: str, votes: Mapping[str, Mapping[str, int]], relations: Sequence, reach
) -> list[dict]:
    """Every sense of every part of speech of one lemma."""
    from .source_agreement import agree, committed_signs, votes_for_pos

    by_pos = read_definitions(conn, lemma, reach)
    dominant = dominant_pos(by_pos)
    corroboration: dict[str, frozenset[int]] = {}
    for signs in votes.values():
        for bank, sign in signs.items():
            corroboration[bank] = corroboration.get(bank, frozenset()) | {sign}
    rows = []
    for pos, definitions in sorted(by_pos.items()):
        agreed = committed_signs(agree(votes_for_pos(votes, pos, pos == dominant)))
        anchor = settle_anchor(agreed, relations, pos)
        for index, sense in enumerate(collapse(definitions, anchor, corroboration)):
            rows.append(close_sense(lemma, pos, index, sense, agreed, relations))
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
