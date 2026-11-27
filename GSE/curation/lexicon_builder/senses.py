"""Senses: the homonym and coherence collapse of a word's definitions (design E10; rebuild task 10.0).

Rohan, 2026-11-25 01:53: the 44 definitions of "lock" are "splintered from a much smaller set of *actual*
definitions"; "parse out the definitions of a word to each of the genuinely unique homynyms", each with "a central,
coherent, 'platonic ideal' version that encapsulates the *meaning* of the idea over the noise of specific
instantiations". 03:28: "They're the same sense of the word if they resolve to the same bank encodings across the
ones that are of high salience, that are definitional across the load-bearing banks". 05:30: "If a single input
completely destroys the coherence model, then that's an out-of-variance exception". 20:20: no frequency-defined
"main sense".

For each lemma and part of speech, over the round's closed state:

1. Coherence is the default. The definitions form one sense unless they destructively interfere: a load-bearing
   bank where their known states have nothing in common.
2. Homonyms are the fewest groups such that every group's members still share a state on every load-bearing bank
   (the constructive combination is non-empty). The partition is found exactly over the members that interfere.
   A member that could stand in more than one group is a residual, with the groups it could join: no member's
   placement is a choice.
3. A definition with no evidence of its own (every cell at its starting mask, or narrowed only by a law that its
   part of speech alone selects) interferes with nothing. It joins its word's core: the one group when there is
   one, or the one group of two or more evidenced definitions when the others are exceptions. When the word has
   several homonyms and no core, it is a residual over them.
4. One evidenced definition alone against the core is an out-of-variance exception: kept apart as its own record,
   with its interfering banks named, never averaged in.
5. A sense's encoding, in each layer, is on each bank the states every evidenced member allows. A bank where they
   allow nothing in common is a recorded conflict, written as the empty mask.
6. Load-bearing banks, the starting definition (the lead's of 2026-11-27, to be refined from the results): the
   banks decided in the known layer, on at least one definition of the word, by a stated, law or admitted-rule
   warrant (stated premises, profile derivations, lenses, NSM, located obligations and stated identities are all
   stated warrants; laws include the part-of-speech laws). Inherited values never separate homonyms, because they
   are interpolated: the partition reads the known layer only, and the interpolated layer gives each sense its
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
SEARCH_BUDGET = 200_000  # nodes of the exact partition search per word: a guard on time, reported when reached
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
    conflicts: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    splits: dict[str, list[str]] = field(default_factory=dict)  # other sense -> interfering banks
    against_core: list[str] = field(default_factory=list)  # an exception's banks incompatible with the core

    def record(self, readings) -> dict:
        def encoding(masks):
            return {BANKS[b]: label(m) for b, m in enumerate(masks.tolist()) if m != int(START[b])}

        return {
            "sense": self.sense_id,
            "lemma": self.lemma,
            "pos": self.pos,
            "kind": self.kind,
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
    search: str  # "trivial", "exact" or "budget"


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


def _minimum_partition(masks: np.ndarray, budget: int) -> tuple[list[list[int]], bool]:
    """The fewest groups of the rows of `masks` (classes x banks) whose intersection is non-empty on every bank.

    Exact branch and bound over a canonical order (most constrained first, then the masks themselves); returns the
    groups and whether the search finished within `budget` nodes."""
    k = masks.shape[0]
    conflicts = np.array([[not _fits(masks[i], masks[j]) for j in range(k)] for i in range(k)])
    order = sorted(range(k), key=lambda i: (-int(conflicts[i].sum()), masks[i].tolist()))
    best: list[list[int]] = []
    groups: list[list[int]] = []
    inters: list[np.ndarray] = []
    nodes = 0
    for i in order:  # a first solution, greedy in the same order, bounds the search
        for g, acc in enumerate(inters):
            if _fits(acc, masks[i]):
                groups[g].append(i)
                inters[g] = acc & masks[i]
                break
        else:
            groups.append([i])
            inters.append(masks[i].copy())
    best = [list(g) for g in groups]
    groups, inters = [], []

    def search(pos: int) -> None:
        nonlocal best, nodes
        nodes += 1
        if nodes > budget or len(groups) >= len(best):
            return
        if pos == k:
            best = [list(g) for g in groups]
            return
        i = order[pos]
        for g in range(len(groups)):
            if _fits(inters[g], masks[i]):
                saved = inters[g]
                groups[g].append(i)
                inters[g] = saved & masks[i]
                search(pos + 1)
                groups[g].pop()
                inters[g] = saved
        groups.append([i])
        inters.append(masks[i].copy())
        search(pos + 1)
        groups.pop()
        inters.pop()

    search(0)
    return best, nodes <= budget


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


def collapse_word(rows: np.ndarray, rnd: Round, evidence: np.ndarray, bearing: np.ndarray, budget: int):
    """The groups of one lemma and part of speech: (groups, exception indices, residuals, load-bearing banks,
    search). Residual candidates are group indices."""
    has = evidence[rows]
    load = np.flatnonzero(bearing[rows].any(axis=0))
    evidenced, free = rows[has], rows[~has]
    if evidenced.size <= 1:
        return [_Group(rows.tolist(), evidenced.tolist())], [], [], load, "trivial"
    sub = rnd.known[evidenced][:, load]
    clash = (sub[:, None, :] & sub[None, :, :]) == 0
    interfere = clash.any(axis=2)
    if not interfere.any():
        return [_Group(rows.tolist(), evidenced.tolist())], [], [], load, "trivial"
    involved = np.flatnonzero(interfere.any(axis=1))
    split_banks = np.flatnonzero(clash.any(axis=(0, 1)))
    keys, key_of = np.unique(sub[involved][:, split_banks], axis=0, return_inverse=True)
    parts, finished = _minimum_partition(keys, budget)
    key_of = key_of.ravel()
    groups = [[int(i) for k in part for i in involved[key_of == k]] for part in parts]
    # Placement must be forced: a member that also fits another group is a residual over the groups it fits.
    residual: dict[int, list[int]] = {}
    for g, members in enumerate(groups):
        for i in members:
            also = [h for h, other in enumerate(groups) if h != g and _fits(_combine(sub[other]), sub[i])]
            if also:
                residual[i] = sorted([g, *also])
    firm = [[i for i in g if i not in residual] for g in groups]
    for i in (i for i in range(sub.shape[0]) if i not in set(involved.tolist())):
        fits = [h for h, g in enumerate(firm) if g and _fits(_combine(sub[g]), sub[i])]
        if len(fits) == 1:
            firm[fits[0]].append(i)
        elif fits:
            residual[i] = fits
        else:
            firm.append([i])
    kept = [h for h, g in enumerate(firm) if g]
    new_index = {h: n for n, h in enumerate(kept)}
    firm = [firm[h] for h in kept]
    residuals = []
    for i, candidates in sorted(residual.items()):
        mapped = sorted({new_index[h] for h in candidates if h in new_index})
        if len(mapped) == 1:
            firm[mapped[0]].append(i)
        elif not mapped:
            firm.append([i])
        else:
            residuals.append({"row": int(evidenced[i]), "candidates": mapped, "reason": "FITS_SEVERAL_HOMONYMS"})
    out = [_Group([int(evidenced[i]) for i in g], [int(evidenced[i]) for i in g]) for g in firm]
    big = [n for n, g in enumerate(firm) if len(g) >= 2]
    exceptions = [n for n, g in enumerate(firm) if len(g) == 1] if len(big) == 1 else []
    core = big[0] if len(big) == 1 else (0 if len(firm) == 1 else None)
    if core is not None:
        out[core].members.extend(int(r) for r in free)
    else:
        every = list(range(len(out)))
        residuals += [{"row": int(r), "candidates": every, "reason": "NO_EVIDENCE_AND_NO_CORE"} for r in free]
    return out, exceptions, residuals, load, "exact" if finished else "budget"


# --- The whole cohort ---------------------------------------------------------------------------------------------


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


def collapse(rnd: Round, budget: int = SEARCH_BUDGET) -> Senses:
    """Every lemma and part of speech of the round collapsed into its senses, closed under the laws."""
    started = time.perf_counter()
    readings = rnd.readings
    evidence, bearing = evidence_masks(rnd)
    by_word: dict[tuple[str, str], list[int]] = defaultdict(list)
    for row, r in enumerate(readings):
        by_word[(r.lemma, r.pos)].append(row)
    senses: list[Sense] = []
    words: list[Word] = []
    sense_of = np.full(len(readings), -1, dtype=np.int64)
    known_rows, interpolated_rows = [], []
    for (lemma, pos), word_rows in sorted(by_word.items()):
        rows = np.array(sorted(word_rows, key=lambda r: readings[r].reading_id), dtype=np.int64)
        groups, exceptions, residuals, load, search = collapse_word(rows, rnd, evidence, bearing, budget)
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
                if a is not b:
                    banks = [BANKS[x] for x in load.tolist() if not (a.known[x] & b.known[x])]
                    if banks:
                        a.splits[b.sense_id] = banks
        cores = [s for s in word_senses if s.kind == "sense"]
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
                        "candidates": [senses[number[c]].sense_id for c in x["candidates"] if c in number],
                        "reason": x["reason"],
                    }
                    for x in residuals
                ],
                search,
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
        "words_with_homonyms": len(split_words),
        "homonym_splits_by_bank": dict(
            sorted(Counter(b for s in result.senses for banks in s.splits.values() for b in banks).items())
        ),
        "residual_definitions": sum(len(w.residuals) for w in result.words),
        "residuals_by_reason": dict(sorted(Counter(x["reason"] for w in result.words for x in w.residuals).items())),
        "readings_in_a_sense": int((result.sense_of >= 0).sum()),
        "readings": len(readings),
        "search": dict(sorted(Counter(w.search for w in result.words).items())),
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
                line |= {"exceptions": word.exceptions, "residuals": word.residuals, "search": word.search}
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
    args = parser.parse_args(argv)
    readings = inventory.load(args.cohort)
    result = collapse(load_round(args.round, readings))
    receipt = {"format": "GSE.rebuild-senses/1", "census": result.receipt, "persisted": persist(result, readings)}
    args.receipt.write_text(json.dumps(receipt, indent=1, default=int) + "\n")
    return receipt


if __name__ == "__main__":
    print(main()["census"])
