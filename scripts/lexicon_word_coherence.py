"""Word-level coherence over the cohort's datasets: a measurement, nothing is admitted or written (rebuild task 8).

F108: "relations between banks in single WORDS, stable across the tens of thousands of WORDS that exist in multiple
datasets". A word is a lemma and a part of speech of the pinned cohort. A dataset states a (bank, state) of a word
when it states it of the word or of one of the word's readings; facts about one word are existential (some reading
has it). Within one root (one record) a word's restrictions intersect; across a dataset's roots they unite, so a
dataset that states two different states of one word, on two of its readings, states the union.

Families:
- lexical: the source lenses (`projection.project`: VerbNet lifted to the lemma of the bound reading; USAS with
  FrameNet through their source rules, restrictions and lemma-level obligations; VerbNet with USAS), the NSM content
  per bound lemma (`nsm.compile_records`, restrictions and obligations), closed-class rows, the prime profiles'
  generalizing statements (the authored silence boundary is confined to its reading and is not lifted to a word)
  and the approved anchors;
- discovery-only, categorical: NRC Emotion's binary flags and ConceptNet's relation types, each mapped by its
  parser's own table (`EMOTION_TO_PRIMITIVE`; `RELATION_TO_PRIMITIVE`, `PROPERTY_PRIMITIVES` and the IsA hypernym
  cases), applied to every flag or edge, with no ranking, no edge limit and no conflict resolution;
- discovery-only, cutoff-mapped: NRC VAD, Lancaster, concreteness and SentiWordNet, through their parsers'
  `to_primitives` defaults, which turn continuous scores into bank values by numeric cutoffs.

`bank_laws.json` and `projection.competence()` give every rating source `writes: {}` and an association policy
("investigate exceptions and validate the conditional mechanism"): they are recorded, never written. The bank maps
used here are the parsers' own, for discovery only.

A candidate "A in a => B in b" (a and b as datasets state them):
- witnesses: words where one dataset states A in a and another states B in b (dataset sets disjoint: a
  `verbnet+usas` fact and a `verbnet` fact share VerbNet);
- counterexamples: one dataset states A in a and another states B outside b;
- unknowns: some dataset states A in a and no other dataset states B;
- near-misses: one dataset states A outside a and another states B outside b.
"Every time" is an empty counterexample set. Lexical candidates use lexical datasets only; discovery candidates have a
discovery-only dataset on at least one side of a witness, and their counterexamples come from every dataset.

NSM validation (F101: "validated by ... symbolic reasoning"): a candidate is NSM-entailed when some NSM explication,
molecule or template states A in a and B in b, and no NSM record states A in a with B outside b.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lexicon_rebuild_discovery as discovery  # noqa: E402

from GSE.curation.lexicon_builder import inventory, nsm, projection  # noqa: E402
from GSE.curation.lexicon_builder.cells import BANK_INDEX, BANKS, NEG, POS, SILENT, START, ZERO  # noqa: E402
from GSE.curation.lexicon_builder.coherence import render  # noqa: E402

CATEGORICAL, CUTOFF = "discovery_categorical", "discovery_cutoff"
_LABEL = {"+1": POS, "-1": NEG, "0": ZERO, "SILENT": SILENT}
_WN_POS = {"noun": "n", "verb": "v", "adj": "a", "adv": "r"}


def _mask(label: str) -> int:
    out = 0
    for part in label.split("|"):
        out |= _LABEL[part]
    return out


def datasets(family: str) -> frozenset[str]:
    return frozenset(family.split("+"))


class Words:
    """The cohort's words (lemma, part of speech), and every dataset's facts about them, per root."""

    def __init__(self, readings):
        self.keys: list[tuple[str, str]] = []
        self.index: dict[tuple[str, str], int] = {}
        self.of_reading = np.zeros(len(readings), dtype=np.int64)
        self.by_lemma: dict[str, list[int]] = defaultdict(list)
        for i, r in enumerate(readings):
            key = (r.lemma.lower(), r.pos)
            if key not in self.index:
                self.index[key] = len(self.keys)
                self.keys.append(key)
                self.by_lemma[key[0]].append(self.index[key])
            self.of_reading[i] = self.index[key]
        self.facts: dict[tuple[str, str, int, int], int] = {}  # (family, root, word, col) -> intersected mask
        self.kind: dict[str, str] = {}
        self.refused: Counter = Counter()
        self.root_conflicts: Counter = Counter()

    def add(self, family: str, kind: str, root: str, word: int, bank: str, value: int) -> None:
        from GSE.curation.lexicon_builder.cells import NEGATIVE_POLES

        if bank in NEGATIVE_POLES:
            bank, value = NEGATIVE_POLES[bank], {POS: NEG, NEG: POS}.get(value, value)
        if bank not in BANK_INDEX:
            self.refused[f"{family}:bank_outside_registry:{bank}"] += 1
            return
        col = BANK_INDEX[bank]
        if not value or value & ~int(START[col]):
            self.refused[f"{family}:illegal_state:{bank}{render(value)}"] += 1
            return
        self.kind[family] = kind
        key = (family, root, word, col)
        self.facts[key] = self.facts.get(key, 15) & value

    def columns(self) -> dict[str, dict[int, tuple[np.ndarray, np.ndarray]]]:
        """family -> col -> (words, masks): within a root intersected, across roots united."""
        united: dict[tuple[str, int, int], int] = {}
        for (family, root, word, col), m in self.facts.items():
            if not m:
                self.root_conflicts[family] += 1
                continue
            united[(family, word, col)] = united.get((family, word, col), 0) | m
        out: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))
        for (family, word, col), m in united.items():
            out[family][col].append((word, m))
        cols = {}
        for family, by_col in out.items():
            cols[family] = {}
            for col, pairs in by_col.items():
                pairs.sort()
                cols[family][col] = (
                    np.array([w for w, _ in pairs], dtype=np.int64),
                    np.array([m for _, m in pairs], dtype=np.uint8),
                )
        return cols


# ------------------------------------------------------------------------------------------------------ loaders


def lexical(words: Words, readings, ids):
    sources, load_seconds = projection.load_sources()
    lens = projection.project(readings, sources)
    r = lens.restrictions
    source_of = dict(zip(r.rule_ids, r.rule_sources))
    for row, col, allowed, rule, premise in zip(
        r.rows.tolist(), r.cols.tolist(), r.allowed.tolist(), r.rules.tolist(), r.premises.tolist()
    ):
        words.add(
            r.rule_sources[rule], "lexical", r.premise_ids[premise], int(words.of_reading[row]), BANKS[col], allowed
        )
    lens_split = Counter()
    for o in lens.obligations:
        targets = set(words.of_reading[o.rows].tolist())
        if len(targets) != 1:
            lens_split[o.rule_id] += 1
            continue
        words.add(source_of[o.rule_id], "lexical", ";".join(o.premises) or o.rule_id, targets.pop(), o.bank, o.allowed)
    compiled = nsm.compile_records(nsm.load_records(discovery.ROOT / nsm.RECORDS), readings)
    record_of, same_as = {}, {}
    for e in compiled.receipt:
        record = f"nsm:{e['source']}:{e['start_line']}-{e['end_line']}"
        for b in [e, *[m for m in e.get("members", []) if isinstance(m, dict)]]:
            if "rule_id" in b:
                record_of[b["rule_id"]] = record
                if "same_as" in b:
                    same_as[b["rule_id"]] = b["same_as"]

    def root(rule_id):
        return record_of[same_as.get(rule_id, rule_id)]

    for row, col, allowed, rule in zip(
        compiled.rows.tolist(), compiled.cols.tolist(), compiled.allowed.tolist(), compiled.rules.tolist()
    ):
        words.add("nsm", "lexical", root(compiled.rule_ids[rule]), int(words.of_reading[row]), BANKS[col], allowed)
    nsm_split = Counter()
    for o in compiled.obligations:
        if o.joint:
            continue
        targets = set(words.of_reading[o.rows].tolist())
        if len(targets) != 1:
            nsm_split[o.rule_id] += 1
            continue
        words.add("nsm", "lexical", root(o.rule_id), targets.pop(), o.bank, o.allowed)
    index = {rid: i for i, rid in enumerate(ids)}
    skipped, bindings = Counter(), {}
    authored = discovery.closed_class(index, skipped)
    stated, _derived = discovery.prime_profiles(index, skipped, bindings)
    authored += [o for o in stated if o.generalizes]
    authored += discovery.approved_anchors(index, bindings, skipped)
    for o in authored:
        words.add(o.family, "lexical", o.root, int(words.of_reading[index[o.reading]]), o.bank, o.states)
    return compiled, {
        "load_seconds": load_seconds,
        "lens_obligations_over_several_words": sum(lens_split.values()),
        "nsm_obligations_over_several_words": sum(nsm_split.values()),
        "confined_profile_statements_not_lifted": sum(1 for o in stated if not o.generalizes),
        "skipped": dict(skipped),
    }


def nrc_emotion(words: Words):
    from GSE.curation.external_sources.nrc_emotion import EMOTION_TO_PRIMITIVE, NRCEmotionParser

    p = NRCEmotionParser()
    p.load()
    for lemma, entry in p.entries.items():
        targets = words.by_lemma.get(lemma.lower().replace("_", " "), [])
        for emotion, flag in sorted(entry.emotions.items()):
            if flag != 1:
                continue
            for bank, value in sorted(EMOTION_TO_PRIMITIVE.get(emotion, {}).items()):
                for w in targets:
                    words.add("nrc_emotion", CATEGORICAL, f"nrc_emotion:{lemma}", w, bank, _value(value))


def conceptnet(words: Words):
    from GSE.curation.external_sources.conceptnet import CONCEPTNET_DB, PROPERTY_PRIMITIVES, RELATION_TO_PRIMITIVE

    isa = {
        "person": "SOMEONE",
        "human": "SOMEONE",
        "people": "SOMEONE",
        "animal": "ALIVE",
        "creature": "ALIVE",
        "place": "WHERE",
        "location": "WHERE",
        "time": "WHEN",
        "period": "WHEN",
        "feeling": "FEEL",
        "emotion": "FEEL",
        "action": "DO",
        "activity": "DO",
    }
    mapped = sorted(r for r, m in RELATION_TO_PRIMITIVE.items() if m) + ["HasProperty"]
    db = sqlite3.connect(f"file:{CONCEPTNET_DB}?mode=ro", uri=True)
    marks = ",".join("?" * len(mapped))
    for rid, relation, start, end in db.execute(
        f"SELECT id, relation, start_word, end_word FROM edges WHERE relation IN ({marks})", mapped
    ):
        root = f"conceptnet:{rid}"
        for word, other, own_end in ((start, end, False), (end, start, True)):
            targets = words.by_lemma.get(word, [])
            if not targets:
                continue
            claims = dict(RELATION_TO_PRIMITIVE.get(relation, {}))
            if relation == "HasProperty":
                claims = dict(PROPERTY_PRIMITIVES.get(other, {}))
            if relation == "IsA" and not own_end and other in isa:
                claims[isa[other]] = 1
            for bank, value in sorted(claims.items()):
                for w in targets:
                    words.add("conceptnet", CATEGORICAL, root, w, bank, _value(value))
    db.close()


def cutoff_ratings(words: Words):
    from GSE.curation.external_sources.concreteness import ConcretenessParser
    from GSE.curation.external_sources.lancaster_sensorimotor import LancasterSensorimotorParser
    from GSE.curation.external_sources.nrc_vad import NRCVADParser
    from GSE.curation.external_sources.sentiwordnet import SentiWordNetParser

    for name, parser in (
        ("nrc_vad", NRCVADParser()),
        ("lancaster", LancasterSensorimotorParser()),
        ("concreteness", ConcretenessParser()),
    ):
        parser.load()
        for lemma in list(parser.entries):
            targets = words.by_lemma.get(lemma.lower().replace("_", " "), [])
            if not targets:
                continue
            for bank, value in sorted(parser.to_primitives(lemma).items()):
                for w in targets:
                    words.add(name, CUTOFF, f"{name}:{lemma}", w, bank, _value(value))
    swn = SentiWordNetParser()
    swn.load()
    for (lemma, pos), w in sorted(words.index.items()):
        if pos in _WN_POS and lemma.replace(" ", "_") in swn.entries:
            for bank, value in sorted(swn.to_primitives(lemma.replace(" ", "_"), _WN_POS[pos]).items()):
                words.add("sentiwordnet", CUTOFF, f"sentiwordnet:{lemma}:{pos}", w, bank, _value(value))


def _value(v: int) -> int:
    return {1: POS, -1: NEG, 0: ZERO}[v]


# ------------------------------------------------------------------------------------------------------ measurement


def _within(masks, states):
    return np.logical_not(masks & (15 & ~states))


def _outside(masks, states):
    return np.logical_not(masks & states)


def measure(cols):
    """Every (A, a, B, b) any two disjoint datasets state of a common word: witnesses and counterexamples by pair."""
    families = sorted(cols)
    patterns: dict[tuple, dict] = defaultdict(lambda: {"witness": defaultdict(list), "counter": defaultdict(list)})
    for f in families:
        for a_col, (fw, fm) in sorted(cols[f].items()):
            for a in sorted(set(fm.tolist())):
                wa = fw[_within(fm, a)]
                for g in families:
                    if datasets(f) & datasets(g):
                        continue
                    for b_col, (gw, gm) in sorted(cols[g].items()):
                        if b_col == a_col:
                            continue
                        common, _, ib = np.intersect1d(wa, gw, assume_unique=True, return_indices=True)
                        if not common.size:
                            continue
                        masks = gm[ib]
                        for b in sorted(set(masks.tolist())):
                            key = (a_col, a, b_col, b)
                            wit = common[_within(masks, b)]
                            cnt = common[_outside(masks, b)]
                            if wit.size:
                                patterns[key]["witness"][(f, g)].append(wit)
                            if cnt.size:
                                patterns[key]["counter"][(f, g)].append(cnt)
    return patterns


def _union(arrays):
    return np.unique(np.concatenate(arrays)) if arrays else np.zeros(0, dtype=np.int64)


def _lexical_pair(fg, kinds):
    return kinds[fg[0]] == "lexical" and kinds[fg[1]] == "lexical"


def cheap(pattern, kinds, universe):
    """Witnesses and counterexamples of a pattern in a universe: 'lexical' (both datasets lexical) or 'discovery'
    (a witness pair has a discovery-only dataset; counterexamples from every dataset)."""
    if universe == "lexical":
        w_pairs = {fg: v for fg, v in pattern["witness"].items() if _lexical_pair(fg, kinds)}
        c_pairs = {fg: v for fg, v in pattern["counter"].items() if _lexical_pair(fg, kinds)}
    else:
        w_pairs = {fg: v for fg, v in pattern["witness"].items() if not _lexical_pair(fg, kinds)}
        c_pairs = dict(pattern["counter"])
    return {
        "witnesses": _union([x for v in w_pairs.values() for x in v]),
        "witness_pairs": {f"{f}->{g}": int(_union(v).size) for (f, g), v in sorted(w_pairs.items())},
        "counterexamples": _union([x for v in c_pairs.values() for x in v]),
        "counter_pairs": {f"{f}->{g}": int(_union(v).size) for (f, g), v in sorted(c_pairs.items())},
    }


def full(key, cols, kinds, universe) -> dict:
    """Unknowns and near-misses of a pattern in a universe."""
    a_col, a, b_col, b = key
    fams = [f for f in cols if universe == "discovery" or kinds[f] == "lexical"]
    holders, stated_b, outside_a, outside_b = {}, {}, {}, {}
    for f in fams:
        if a_col in cols[f]:
            w, m = cols[f][a_col]
            holders[f] = w[_within(m, a)]
            outside_a[f] = w[_outside(m, a)]
        if b_col in cols[f]:
            w, m = cols[f][b_col]
            stated_b[f] = w
            outside_b[f] = w[_outside(m, b)]
    covered, near = [], []
    for f in holders:
        for g in stated_b:
            if not (datasets(f) & datasets(g)):
                covered.append(np.intersect1d(holders[f], stated_b[g], assume_unique=True))
    for f in outside_a:
        for g in outside_b:
            if not (datasets(f) & datasets(g)):
                near.append(np.intersect1d(outside_a[f], outside_b[g], assume_unique=True))
    antecedent = _union(list(holders.values()))
    return {
        "unknown": np.setdiff1d(antecedent, _union(covered), assume_unique=True),
        "near_misses": _union(near),
    }


def nsm_records(compiled):
    """Each NSM explication, molecule and template's content once (a republication is the record it repeats)."""
    out = []
    for e in compiled.receipt:
        if e.get("kind") not in {"explication", "molecule", "template"} or not e.get("banks"):
            continue
        if "same_as" in e:
            continue
        masks = {BANK_INDEX[b]: _mask(label) for b, label in e["banks"].items() if b in BANK_INDEX}
        out.append((f"nsm:{e['source']}:{e['start_line']}-{e['end_line']}", e.get("lemma"), masks))
    return out


def entailment(key, records, witness_lemmas=frozenset()):
    """Some NSM record states A in a and B in b and none states A in a with B outside b. `independent` counts only
    records whose explicated lemma is not a witness word, so the record is not the witness's own NSM side."""
    a_col, a, b_col, b = key
    states = [r for r in records if a_col in r[2] and b_col in r[2] and not (r[2][a_col] & ~a & 15)]
    entailing = [r for r in states if not (r[2][b_col] & ~b & 15)]
    contradicting = [r[0] for r in states if not (r[2][b_col] & b)]
    independent = [r[0] for r in entailing if r[1] not in witness_lemmas]
    return {
        "entailed": bool(entailing) and not contradicting,
        "independently_entailed": bool(independent) and not contradicting,
        "entailing_records": [r[0] for r in entailing][:10],
        "entailing_count": len(entailing),
        "independent_entailing_count": len(independent),
        "contradicting_records": contradicting[:10],
        "contradicting_count": len(contradicting),
    }


def _name(key):
    a_col, a, b_col, b = key
    return f"{BANKS[a_col]}{render(a)}=>{BANKS[b_col]}{render(b)}"


def _ex(words, rows, k=10):
    return {"count": int(rows.size), "examples": ["|".join(words.keys[i]) for i in rows[:k].tolist()]}


def run() -> dict:
    t0 = time.perf_counter()
    readings = inventory.load(discovery.COHORT)
    ids = tuple(r.reading_id for r in readings)
    words = Words(readings)
    compiled, lexical_notes = lexical(words, readings, ids)
    nrc_emotion(words)
    conceptnet(words)
    cutoff_ratings(words)
    t_load = time.perf_counter() - t0
    cols = words.columns()
    kinds = dict(words.kind)
    by_family = {
        f: {
            "kind": kinds[f],
            "words": int(np.unique(np.concatenate([w for w, _ in cols[f].values()])).size),
            "word_bank_facts": int(sum(w.size for w, _ in cols[f].values())),
            "banks": sorted(BANKS[c] for c in cols[f]),
            "root_conflicts_excluded": words.root_conflicts.get(f, 0),
        }
        for f in sorted(cols)
    }
    lexical_words = defaultdict(set)
    for f in cols:
        if kinds[f] == "lexical":
            for w, _ in cols[f].values():
                for i in w.tolist():
                    lexical_words[i].add(f)
    overlap = Counter(
        "&".join(sorted(fs))
        for fs in lexical_words.values()
        if any(not (datasets(x) & datasets(y)) for x in fs for y in fs)
    )
    patterns = measure(cols)
    t_measure = time.perf_counter() - t0 - t_load
    records = nsm_records(compiled)
    summary, top = {}, {}
    for universe in ("lexical", "discovery"):
        items = []
        for key, pattern in patterns.items():
            ev = cheap(pattern, kinds, universe)
            if ev["witnesses"].size:
                items.append({"candidate": _name(key), "exact": not ev["counterexamples"].size, "_key": key, "_ev": ev})
        exact = [x for x in items if x["exact"]]
        for x in exact:
            x["_ev"] |= full(x["_key"], cols, kinds, universe)
            lemmas = frozenset(words.keys[i][0] for i in x["_ev"]["witnesses"].tolist())
            x["nsm"] = entailment(x["_key"], records, lemmas)
        entailed = [x for x in exact if x["nsm"]["entailed"]]
        inexact = sorted(
            [x for x in items if not x["exact"]], key=lambda x: (-x["_ev"]["witnesses"].size, x["candidate"])
        )
        for x in inexact[:10]:
            x["_ev"] |= full(x["_key"], cols, kinds, universe)
        summary[universe] = {
            "candidates_with_witnesses": len(items),
            "exact": len(exact),
            "exact_and_nsm_entailed": len(entailed),
            "exact_not_entailed": len(exact) - len(entailed),
            "exact_and_independently_entailed": sum(1 for x in exact if x["nsm"]["independently_entailed"]),
            "exact_with_near_misses": sum(1 for x in exact if x["_ev"]["near_misses"].size),
            "exact_and_entailed_with_near_misses": sum(1 for x in entailed if x["_ev"]["near_misses"].size),
            "exact_by_witness_pair": dict(sorted(Counter(p for x in exact for p in x["_ev"]["witness_pairs"]).items())),
        }
        ranked = sorted(exact, key=lambda x: (-x["_ev"]["witnesses"].size, x["candidate"]))
        top[universe] = [_public(x, words) for x in ranked[:30]]
        top[f"{universe}_entailed"] = [_public(x, words) for x in ranked if x["nsm"]["entailed"]][:30]
        top[f"{universe}_most_witnessed_inexact"] = [_public(x, words) for x in inexact[:10]]
        top[f"{universe}_all"] = [
            {
                "candidate": x["candidate"],
                "exact": x["exact"],
                "witness_words": int(x["_ev"]["witnesses"].size),
                "counterexample_words": int(x["_ev"]["counterexamples"].size),
                "unknown_words": int(x["_ev"]["unknown"].size) if "unknown" in x["_ev"] else None,
                "near_miss_words": int(x["_ev"]["near_misses"].size) if "near_misses" in x["_ev"] else None,
                "witness_pairs": x["_ev"]["witness_pairs"],
                "counter_pairs": x["_ev"]["counter_pairs"],
                "nsm_entailed": x["nsm"]["entailed"] if "nsm" in x else None,
                "nsm_independently_entailed": x["nsm"]["independently_entailed"] if "nsm" in x else None,
            }
            for x in sorted(items, key=lambda x: (-x["_ev"]["witnesses"].size, x["candidate"]))
        ]
        if universe == "lexical":
            contested = [x for x in exact if cheap(patterns[x["_key"]], kinds, "discovery")["counterexamples"].size]
            summary[universe]["exact_contested_by_discovery_datasets"] = len(contested)
    return {
        "format": "GSE.rebuild-word-coherence/1",
        "measurement_only": "nothing is admitted or written",
        "inputs": discovery._digests(),
        "words": len(words.keys),
        "families": by_family,
        "refused_facts": dict(sorted(words.refused.items())),
        "lexical_notes": lexical_notes,
        "nsm_records_with_content": len(records),
        "patterns_stated_by_two_datasets": len(patterns),
        "words_with_two_disjoint_lexical_datasets": {"total": sum(overlap.values()), "by_families": dict(overlap)},
        "summary": summary,
        "top": top,
        "seconds": {
            "load": round(t_load, 1),
            "measure": round(t_measure, 1),
            "total": round(time.perf_counter() - t0, 1),
        },
    }


def _public(x, words):
    ev = x["_ev"]
    out = {"candidate": x["candidate"], "exact": x["exact"]}
    if "nsm" in x:
        out["nsm"] = x["nsm"]
    out["witness_pairs"] = ev["witness_pairs"]
    out["counter_pairs"] = ev["counter_pairs"]
    for name in ("witnesses", "counterexamples", "unknown", "near_misses"):
        if name in ev:
            out[name] = _ex(words, ev[name])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    receipt = run()
    if args.out:
        args.out.write_text(json.dumps(receipt, indent=1, default=str) + "\n")
    print(json.dumps({k: receipt[k] for k in ("words", "families", "summary", "seconds")}, indent=1, default=str))


if __name__ == "__main__":
    main()
