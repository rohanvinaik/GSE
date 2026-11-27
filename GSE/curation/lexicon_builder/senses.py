"""Senses: the homonym and coherence collapse of a word's definitions (design E10; rebuild task 10.0).

Rohan, 2026-11-25 01:53: the 44 definitions of "lock" are "splintered from a much smaller set of *actual*
definitions"; "parse out the definitions of a word to each of the genuinely unique homynyms", each with "a central,
coherent, 'platonic ideal' version that encapsulates the *meaning* of the idea over the noise of specific
instantiations". 03:28: "They're the same sense of the word if they resolve to the same bank encodings across the
ones that are of high salience, that are definitional across the load-bearing banks". 05:30: "If a single input
completely destroys the coherence model, then that's an out-of-variance exception". 20:20: no frequency-defined
"main sense".

For each lemma and part of speech, over the round's closed state:

1. Evidenced definitions are one sense only when their load-bearing encodings are EQUAL (03:28: "the same bank
   encodings"; the lead's revision of E10, 2026-11-27): every load-bearing bank decided in either one has the same
   value in both. A bank decided in one and open in the other is not shown equal. Compatibility is not enough:
   differently evidenced senses of "go" would otherwise accumulate the union of their content.
2. A prime reading's sense (a reading bound to a prime profile, and the readings of its synset) is its own: its
   silence is confined to that reading, so nothing joins it but readings equal to it.
3. A definition with no evidence of its own (every cell at its starting mask, or narrowed only by a law that its
   part of speech alone selects) joins its word's core when the word has exactly one evidenced sense other than a
   prime reading's and its exceptions. With several, it stays a residual listing them. With none (only a prime
   reading's sense, or no evidence at all), the evidence-free definitions form one sense of their own.
4. One evidenced definition alone against the core (the one ordinary sense of two or more equal definitions) is an
   out-of-variance exception when it destructively interferes with the core, a load-bearing bank where their states
   have nothing in common: kept apart as its own record, with its interfering banks named, never averaged in.
5. A sense's encoding, in each layer, is on each bank the states every evidenced member allows. A bank where they
   allow nothing in common is a recorded conflict, written as the empty mask.
6. Load-bearing banks: the banks decided in the known layer, on a definition, by a stated, law or admitted-rule
   warrant (stated premises, profile derivations, lenses, NSM, located obligations and stated identities are all
   stated warrants; laws include the part-of-speech laws). Inherited values never separate senses, because they are
   interpolated: the grouping reads the known layer only, and the interpolated layer gives each sense its
   interpolated encoding.
7. Every part of speech present keeps at least one sense. Senses are numbered by their least member reading id:
   there is no main sense and no frequency.

The sense encodings are then closed under the authored laws, over the facts every evidenced member holds.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import guards, laws
from .cells import BANKS, BIT_NAMES, NEG, POS, SILENT, START, ZERO, State
from .closure import close
from .inventory import Reading

# The scopes `guards` derives from the part of speech alone: a law over one of them is a part-of-speech consequence.
POS_SCOPES = frozenset({"own_role=lexical_predicate", "own_role=modifier_property_only"})
# Known-layer warrants, as the round runner names them (`scripts/rebuild_lexicon.py`, CLASSES).
STATED_WARRANTS = frozenset(
    {"stated", "profile_derivation", "lens", "nsm", "forced_obligation", "stated_identity", "admitted"}
)
LOAD_BEARING_WARRANTS = STATED_WARRANTS | {"law"}
PRIME_ROOT = "stated:prime_profile:"  # the rule of a cell a prime profile states (`lexicon_rebuild_discovery`)
_STATES = (POS, NEG, ZERO, SILENT)
_POPCOUNT = np.array([bin(i).count("1") for i in range(16)], dtype=np.uint8)


def label(mask: int) -> str:
    return "|".join(BIT_NAMES[s] for s in _STATES if int(mask) & s) or "conflict"


@dataclass
class Round:
    """What the collapse reads from a round: the readings, both layers' masks, each known cell's warrant class and
    rule, and the known layer's guard facts."""

    readings: tuple
    known: np.ndarray
    interpolated: np.ndarray
    known_class: np.ndarray
    known_rule: np.ndarray
    rule_ids: tuple[str, ...]
    class_names: tuple[str, ...]
    facts: dict[str, np.ndarray] = field(default_factory=dict)


def load_round(path: Path, readings) -> Round:
    """The runner's persisted final state (`data/lexicon_builder/rebuild/round-final.npz`)."""
    data = np.load(path, allow_pickle=True)
    ids = tuple(data["readings"].tolist())
    if ids != tuple(r.reading_id for r in readings):
        raise ValueError("ROUND_READINGS_DIFFER_FROM_COHORT")
    facts = {}
    if "fact_names" in data:
        bits = np.unpackbits(data["known_facts"], axis=1, count=len(ids)).astype(bool)
        facts = {str(name): bits[i] for i, name in enumerate(data["fact_names"].tolist())}
    return Round(
        readings=tuple(readings),
        known=data["known_masks"],
        interpolated=data["interpolated_masks"],
        known_class=data["known_class"],
        known_rule=data["known_rule"],
        rule_ids=tuple(data["rule_ids"].tolist()),
        class_names=tuple(data["classes"].tolist()),
        facts=facts,
    )


@dataclass
class Sense:
    """One sense of a word: its member readings, those with evidence of their own, the word's load-bearing banks,
    both layers' encodings (closed under the laws), and its conflicts and splits."""

    sense_id: str
    lemma: str
    pos: str
    kind: str  # "sense" or "exception"
    members: tuple[int, ...]
    evidenced: tuple[int, ...]
    load_bearing: tuple[str, ...]
    known: np.ndarray
    interpolated: np.ndarray
    prime: bool = False  # a prime reading's sense
    conflicts: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    splits: dict[str, dict[str, list[str]]] = field(default_factory=dict)  # other sense -> unequal, interfering
    against_core: list[str] = field(default_factory=list)  # an exception's banks incompatible with the core

    def record(self, readings) -> dict:
        def encoding(masks):
            return {BANKS[b]: label(m) for b, m in enumerate(masks.tolist()) if m != int(START[b])}

        return {
            "sense": self.sense_id,
            "lemma": self.lemma,
            "pos": self.pos,
            "kind": self.kind,
            "prime": self.prime,
            "members": [readings[r].reading_id for r in self.members],
            "evidenced": [readings[r].reading_id for r in self.evidenced],
            "load_bearing": list(self.load_bearing),
            "known": encoding(self.known),
            "interpolated": encoding(self.interpolated),
            "conflicts": self.conflicts,
            "splits": self.splits,
            "against_core": self.against_core,
        }


@dataclass
class Word:
    """A lemma and part of speech: its senses, exceptions, residual definitions with the senses each could join."""

    lemma: str
    pos: str
    senses: list[str]
    exceptions: list[str]
    residuals: list[dict]


@dataclass
class Senses:
    senses: list[Sense]
    words: list[Word]
    sense_of: np.ndarray  # reading row -> index into `senses`, or -1 for a residual
    known: State
    interpolated: State
    receipt: dict

    def columns(self, readings) -> dict[str, np.ndarray]:
        """Per sense, as `measure.census` takes a population: both layers' masks, lemma, part of speech, kind, and
        source (the member readings' source families, sorted and joined by "+")."""
        return {
            "known": self.known.masks,
            "interpolated": self.interpolated.masks,
            "lemma": np.array([s.lemma for s in self.senses], dtype=object),
            "pos": np.array([s.pos for s in self.senses], dtype=object),
            "kind": np.array([s.kind for s in self.senses], dtype=object),
            "source": np.array(
                ["+".join(sorted({readings[r].source for r in s.members})) for s in self.senses], dtype=object
            ),
        }


# --- The collapse of one word -------------------------------------------------------------------------------------


def _pos_law_rules(rule_ids) -> np.ndarray:
    pos_laws = {r.rule_id for r in laws.compile_laws() if r.scope in POS_SCOPES}
    return np.array([r in pos_laws for r in rule_ids], dtype=bool)


def _fits(acc: np.ndarray, mask: np.ndarray) -> bool:
    return bool(((acc & mask) != 0).all())


def _combine(masks: np.ndarray) -> np.ndarray:
    return np.bitwise_and.reduce(masks, axis=0) if masks.shape[0] else START.copy()


def _conflicts(masks: np.ndarray, rows, readings) -> dict[str, list[str]]:
    combined = _combine(masks)
    out = {}
    for b in np.flatnonzero(combined == 0).tolist():
        out[BANKS[b]] = sorted({f"{readings[r].reading_id}:{label(m)}" for r, m in zip(rows, masks[:, b].tolist())})
    return out


@dataclass
class _Group:
    members: list[int]
    evidenced: list[int]


def collapse_word(rows: np.ndarray, rnd: Round, evidence: np.ndarray, bearing: np.ndarray, prime: np.ndarray):
    """The groups of one lemma and part of speech: (groups, exception indices, residuals, load-bearing banks, the
    indices of prime readings' groups). Residual candidates are group indices."""
    has = evidence[rows]
    load = np.flatnonzero(bearing[rows].any(axis=0))
    evidenced, free = rows[has], rows[~has]
    if not evidenced.size:
        return [_Group(rows.tolist(), [])], [], [], load, set()
    # The load-bearing signature: each load bank's decided value where a load-bearing warrant decided it, else 0.
    signature = np.where(bearing[evidenced][:, load], rnd.known[evidenced][:, load], 0)
    _, inverse = np.unique(signature, axis=0, return_inverse=True)
    inverse = inverse.ravel()
    groups = [
        _Group(evidenced[inverse == k].tolist(), evidenced[inverse == k].tolist()) for k in range(inverse.max() + 1)
    ]
    primes = {g for g, group in enumerate(groups) if prime[group.evidenced].any()}
    ordinary = [g for g in range(len(groups)) if g not in primes]
    cores = [g for g in ordinary if len(groups[g].evidenced) >= 2]
    exceptions = []
    if len(cores) == 1:
        core = _combine(rnd.known[groups[cores[0]].evidenced][:, load])
        for g in ordinary:
            alone = groups[g].evidenced
            if g != cores[0] and len(alone) == 1 and not _fits(core, rnd.known[alone[0]][load]):
                exceptions.append(g)
    joinable = [g for g in ordinary if g not in exceptions]
    residuals = []
    if free.size:
        if len(joinable) == 1:
            groups[joinable[0]].members.extend(free.tolist())
        elif not joinable:
            groups.append(_Group(free.tolist(), []))
        else:
            residuals = [
                {"row": int(r), "candidates": joinable, "reason": "NO_EVIDENCE_SEVERAL_SENSES"} for r in free.tolist()
            ]
    return groups, exceptions, residuals, load, primes


# --- The whole cohort ---------------------------------------------------------------------------------------------


def prime_readings(rnd: Round) -> np.ndarray:
    """Per reading, whether it is a prime reading: bound to a prime profile (a cell the profile states), or a WordNet
    reading of the same synset as one (one definition)."""
    from . import inheritance

    codes = [i for i, rule in enumerate(rnd.rule_ids) if rule.startswith(PRIME_ROOT)]
    out = np.isin(rnd.known_rule, codes).any(axis=1) if codes else np.zeros(len(rnd.readings), dtype=bool)
    for rows in inheritance.wordnet_groups(rnd.readings).values():
        if out[rows].any():
            out[rows] = True
    return out


def evidence_masks(rnd: Round) -> tuple[np.ndarray, np.ndarray]:
    """Per reading, whether it has evidence of its own (known); per cell, whether it is load-bearing."""
    code = {name: i for i, name in enumerate(rnd.class_names)}
    cls = rnd.known_class
    pos_law = _pos_law_rules(rnd.rule_ids)
    rule = rnd.known_rule
    by_pos_law = np.zeros(rule.shape, dtype=bool)
    on = rule >= 0
    by_pos_law[on] = pos_law[rule[on]]
    narrowed = rnd.known != START[None, :]
    stated = np.isin(cls, [code[n] for n in STATED_WARRANTS if n in code])
    lawful = cls == code.get("law", -1)
    evidence = (narrowed & (stated | (lawful & ~by_pos_law))).any(axis=1)
    decided = _POPCOUNT[rnd.known] == 1
    bearing = decided & np.isin(cls, [code[n] for n in LOAD_BEARING_WARRANTS if n in code])
    return evidence, bearing


def _sense_facts(senses: list[Sense], facts: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """A guard fact holds of a sense when it holds of every evidenced member (of every member, if none is)."""
    out = {}
    for name, mask in facts.items():
        held = np.zeros(len(senses), dtype=bool)
        for i, s in enumerate(senses):
            rows = list(s.evidenced) or list(s.members)
            held[i] = bool(rows) and bool(mask[rows].all())
        if held.any():
            out[name] = held
    return out


def _close(senses: list[Sense], masks: np.ndarray, facts: dict[str, np.ndarray]) -> State:
    readings = tuple(Reading(s.sense_id, s.lemma, s.pos, "") for s in senses)
    state = State(tuple(s.sense_id for s in senses), masks.copy())
    relations = laws.compile_laws()
    scopes = guards.scopes(readings, {r.scope for r in relations}, facts)
    close(state, relations, scopes)
    return state


def collapse(rnd: Round) -> Senses:
    """Every lemma and part of speech of the round collapsed into its senses, closed under the laws."""
    started = time.perf_counter()
    readings = rnd.readings
    evidence, bearing = evidence_masks(rnd)
    prime = prime_readings(rnd)
    by_word: dict[tuple[str, str], list[int]] = defaultdict(list)
    for row, r in enumerate(readings):
        by_word[(r.lemma, r.pos)].append(row)
    senses: list[Sense] = []
    words: list[Word] = []
    sense_of = np.full(len(readings), -1, dtype=np.int64)
    known_rows, interpolated_rows = [], []
    for (lemma, pos), word_rows in sorted(by_word.items()):
        rows = np.array(sorted(word_rows, key=lambda r: readings[r].reading_id), dtype=np.int64)
        groups, exceptions, residuals, load, primes = collapse_word(rows, rnd, evidence, bearing, prime)
        order = sorted(range(len(groups)), key=lambda g: min(readings[r].reading_id for r in groups[g].members))
        first = len(senses)
        number = {g: first + n for n, g in enumerate(order)}
        load_names = tuple(BANKS[b] for b in load.tolist())
        for n, g in enumerate(order):
            group = groups[g]
            members = tuple(sorted(group.members, key=lambda r: readings[r].reading_id))
            evid = tuple(sorted(group.evidenced, key=lambda r: readings[r].reading_id))
            basis = list(evid) or list(members)
            interp_basis = [r for r in members if r in set(evid) or (rnd.interpolated[r] != START).any()] or basis
            k_masks, i_masks = rnd.known[basis], rnd.interpolated[interp_basis]
            sense = Sense(
                sense_id=f"sense:{lemma}:{pos}:{n + 1}",
                lemma=lemma,
                pos=pos,
                kind="exception" if g in exceptions else "sense",
                prime=g in primes,
                members=members,
                evidenced=evid,
                load_bearing=load_names,
                known=_combine(k_masks),
                interpolated=_combine(i_masks),
                conflicts={
                    k: v
                    for k, v in (
                        ("known", _conflicts(k_masks, basis, readings)),
                        ("interpolated", _conflicts(i_masks, interp_basis, readings)),
                    )
                    if v
                },
            )
            senses.append(sense)
            sense_of[list(members)] = first + n
            known_rows.append(sense.known)
            interpolated_rows.append(sense.interpolated)
        word_senses = senses[first:]
        for a in word_senses:
            for b in word_senses:
                if a is not b and a.evidenced and b.evidenced:
                    unequal = [
                        BANKS[x]
                        for x in load.tolist()
                        if a.known[x] != b.known[x] and (_POPCOUNT[a.known[x]] == 1 or _POPCOUNT[b.known[x]] == 1)
                    ]
                    if unequal:
                        interfering = [BANKS[x] for x in load.tolist() if not (a.known[x] & b.known[x])]
                        a.splits[b.sense_id] = {"unequal": unequal, "interfering": interfering}
        cores = [s for s in word_senses if s.kind == "sense" and not s.prime and len(s.evidenced) >= 2]
        for s in word_senses:
            if s.kind == "exception" and len(cores) == 1:
                s.against_core = [BANKS[x] for x in load.tolist() if not (s.known[x] & cores[0].known[x])]
        words.append(
            Word(
                lemma,
                pos,
                [s.sense_id for s in word_senses if s.kind == "sense"],
                [s.sense_id for s in word_senses if s.kind == "exception"],
                [
                    {
                        "reading": readings[x["row"]].reading_id,
                        "candidates": [senses[i].sense_id for i in sorted(number[c] for c in x["candidates"])],
                        "reason": x["reason"],
                    }
                    for x in residuals
                ],
            )
        )
    known = np.array(known_rows, dtype=np.uint8).reshape(-1, len(BANKS))
    interpolated = np.array(interpolated_rows, dtype=np.uint8).reshape(-1, len(BANKS))
    facts = _sense_facts(senses, rnd.facts)
    known_state, interpolated_state = _close(senses, known, facts), _close(senses, interpolated, facts)
    for i, s in enumerate(senses):
        s.known, s.interpolated = known_state.masks[i], interpolated_state.masks[i]
    out = Senses(senses, words, sense_of, known_state, interpolated_state, {})
    out.receipt = census(out, readings) | {"seconds": round(time.perf_counter() - started, 2)}
    return out


def census(result: Senses, readings) -> dict:
    """Senses by part of speech and kind, homonym splits, exceptions, residuals, and both layers' census."""
    by_pos = Counter(s.pos for s in result.senses if s.kind == "sense")
    words_by_pos = Counter(w.pos for w in result.words)
    split_words = [w for w in result.words if len(w.senses) > 1]
    return {
        "words": len(result.words),
        "words_by_pos": dict(sorted(words_by_pos.items())),
        "senses": sum(by_pos.values()),
        "senses_by_pos": dict(sorted(by_pos.items())),
        "exceptions": sum(len(w.exceptions) for w in result.words),
        "words_with_several_senses": len(split_words),
        "prime_senses": sum(1 for s in result.senses if s.prime),
        "evidence_free_senses": sum(1 for s in result.senses if not s.evidenced),
        "splits_by_unequal_bank": dict(
            sorted(Counter(b for s in result.senses for split in s.splits.values() for b in split["unequal"]).items())
        ),
        "splits_by_interfering_bank": dict(
            sorted(
                Counter(b for s in result.senses for split in s.splits.values() for b in split["interfering"]).items()
            )
        ),
        "residual_definitions": sum(len(w.residuals) for w in result.words),
        "residuals_by_reason": dict(sorted(Counter(x["reason"] for w in result.words for x in w.residuals).items())),
        "readings_in_a_sense": int((result.sense_of >= 0).sum()),
        "readings": len(readings),
        "senses_with_conflicts": {
            layer: sum(1 for s in result.senses if layer in s.conflicts) for layer in ("known", "interpolated")
        },
        "known": result.known.census(),
        "interpolated": result.interpolated.census(),
    }


# --- The artifact writer's input ----------------------------------------------------------------------------------

ROUND = Path("data/lexicon_builder/rebuild/round-final.npz")
COHORT = Path("data/lexicon_builder/rebuild/cohort.jsonl")
OUT = Path("data/lexicon_builder/rebuild/senses.npz")
RECORDS = Path("data/lexicon_builder/rebuild/senses.jsonl")
RECEIPT = Path("docs/verification/2026-11-27-rebuild-senses.json")


def persist(result: Senses, readings, path: Path = OUT, records: Path = RECORDS) -> dict:
    """The senses as the artifact writer reads them: `path` holds the arrays (sense ids, lemma, part of speech, kind,
    both layers' closed masks over the 56 banks, and each reading's sense, -1 for a residual); `records` holds one
    JSON line per sense (members, evidenced members, load-bearing banks, encodings, conflicts, splits) and one per
    word with residuals."""
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        sense_ids=np.array([s.sense_id for s in result.senses], dtype=object),
        lemmas=np.array([s.lemma for s in result.senses], dtype=object),
        pos=np.array([s.pos for s in result.senses], dtype=object),
        kinds=np.array([s.kind for s in result.senses], dtype=object),
        known=result.known.masks,
        interpolated=result.interpolated.masks,
        sense_of=result.sense_of,
        readings=np.array([r.reading_id for r in readings], dtype=object),
        banks=np.array(BANKS, dtype=object),
    )
    with records.open("w", encoding="utf-8") as out:
        for sense in result.senses:
            out.write(json.dumps({"type": "sense"} | sense.record(readings), ensure_ascii=False) + "\n")
        for word in result.words:
            if word.residuals or word.exceptions or len(word.senses) > 1:
                line = {"type": "word", "lemma": word.lemma, "pos": word.pos, "senses": word.senses}
                line |= {"exceptions": word.exceptions, "residuals": word.residuals}
                out.write(json.dumps(line, ensure_ascii=False) + "\n")
    return {"path": str(path), "records": str(records), "senses": len(result.senses)}


def main(argv=None) -> dict:
    import argparse
    import json

    from . import inventory

    parser = argparse.ArgumentParser(description="Collapse the round's definitions into senses (design E10).")
    parser.add_argument("--round", type=Path, default=ROUND)
    parser.add_argument("--cohort", type=Path, default=COHORT)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--records", type=Path, default=RECORDS)
    args = parser.parse_args(argv)
    readings = inventory.load(args.cohort)
    result = collapse(load_round(args.round, readings))
    persisted = persist(result, readings, args.out, args.records)
    receipt = {"format": "GSE.rebuild-senses/1", "census": result.receipt, "persisted": persisted}
    args.receipt.write_text(json.dumps(receipt, indent=1, default=int) + "\n")
    return receipt


if __name__ == "__main__":
    print(main()["census"])
