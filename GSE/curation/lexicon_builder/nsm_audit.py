"""The audit of inherited values against the NSM explications (design E8, F148; the lead's ruling of 2026-11-27).

The verb hierarchy's cells stay interpolated and are audited against NSM (F148: the tail is the disagreement with NSM
by word, bank and rule). An explication is the complete meaning of its sense, so a carried +1 or -1 on a bank the
explication neither mentions nor reaches through its molecules disagrees with it. Each disagreement names the link
through which the value entered the chain of kinds leading to the explicated sense, as a candidate defeater with the
NSM record (source key and line range) as its warrant (TrialLedger: "Defaults have declared applicability and
defeaters"). Nothing is defeated automatically; candidates are decided by review.

Banks not judged. An explication cannot be complete over a bank its metalanguage cannot express (the lead's ruling of
2026-11-27), so a bank no NSM record ever writes is not judged, and its carried cells are counted apart. Measured on
the verified records (2026-11-27), twelve banks are never written by any record's compiled content: CAUSE, HAVE,
START, I, YOU, SOMEONE, INFER, TOWARD, WITH, MUST, TRUE and CERTAINTY. NSM states causation through BECAUSE, so CAUSE
is not a bank its explications can mention. The judged banks are computed from the records each time
(`audit_against_nsm(..., expressible=)`), so the list follows the compiler.

The lineage it walks is `lineage.py`; the readings and their bindings come from `nsm.compile_records`, read only by
`explications_from_nsm`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np

from .cells import _POPCOUNT, BANKS, BIT_NAMES, NEG, POS, SILENT, ZERO
from .inheritance import SYNONYMY, Settlement, state_names
from .lineage import SYNONYM_HOP

CONTENT = POS | NEG
_WIDTH = len(BANKS)

DISAGREE_UNMENTIONED = "carried content on a bank the explication does not mention"
DISAGREE_OPPOSITE = "carried state the explication's own states exclude"


@dataclass(frozen=True)
class Explication:
    """One NSM explication as the audit reads it: its record key (source and line range), the lemma and part of
    speech it explicates, the readings it binds to (one, or the typed candidates of which one is its sense), and the
    states it gives each bank it mentions or reaches through its molecules."""

    key: str
    lemma: str
    pos: str
    rows: np.ndarray
    states: dict[str, int]


_LABEL_BITS = {"+1": POS, "-1": NEG, "0": ZERO, "SILENT": SILENT}


def explications_from_nsm(compiled, kinds=("explication", "molecule"), pos=("verb", "noun")) -> list[Explication]:
    """The audited explications from `nsm.compile_records` output: records of `kinds` for `pos`, bound to a reading
    (a restriction) or to typed candidates (an obligation); templates and unbound records are not explications of
    one sense. The banks are the record's content with its molecules'."""
    by_rule = {}
    for o in compiled.obligations:
        by_rule.setdefault(o.rule_id, np.asarray(o.rows, dtype=np.int64))
    out = []
    for entry in compiled.receipt:
        if entry.get("kind") not in kinds or entry.get("pos") not in pos or "rule_id" not in entry:
            continue
        disposition = entry.get("disposition")
        if disposition == "RESTRICTION":
            rows = np.array([entry["reading"]], dtype=np.int64)
        elif disposition in {"OBLIGATION", "UNTYPED"} and entry["rule_id"] in by_rule:
            rows = by_rule[entry["rule_id"]]
        else:
            continue
        states = {bank: sum(_LABEL_BITS[x] for x in label.split("|")) for bank, label in entry.get("banks", {}).items()}
        key = f"{entry['source']}:{entry['start_line']}-{entry['end_line']}"
        out.append(Explication(key, entry["lemma"], entry["pos"], rows, states))
    return out


def audit_against_nsm(settlement: Settlement, explications, expressible=None) -> dict:
    """Every carried value on an explicated sense, judged against the explication as its complete meaning.

    For each explication and bank, each candidate reading's carried state (a single +1, -1 or 0 that inheritance
    landed on it) agrees with the explication, disagrees with it, or says nothing. A carried +1 or -1 on a bank the
    explication neither mentions nor reaches through its molecules disagrees; so does a carried state the
    explication's own states on that bank exclude; a carried 0 on a bank it does not mention says nothing. When the
    explication binds to several candidate readings, one of which is its sense, it disagrees (or agrees) only if
    every candidate does; a mixed bank is undetermined.

    Each disagreeing reading names its origins, their paths, and the candidate defeater: the link through which the
    value entered the chain of kinds leading to the explicated sense, from its origin to the first node after it
    (`synonymy` when the value is stated on the reading's own synset, which no link carries). Candidates are
    aggregated with what else rests on them: the explications that agree through the same link, and every inherited
    cell whose path starts with it. Nothing is defeated here.

    An explication is complete only over what NSM content can say: a bank no NSM record ever writes (`expressible`,
    by default every bank some given explication writes) is not judged, and its carried cells are counted apart.

    While a binding still has several candidates, a candidate that disagrees does so only if it is the sense: such
    readings are reported apart, as conditional disagreements with their own aggregated candidate links, never
    mixed with the definite ones.
    """
    explications = tuple(explications)
    if expressible is None:
        expressible = {bank for ex in explications for bank in ex.states}
    expressible = frozenset(expressible)
    not_judged: Counter = Counter()
    g, st, lin = settlement.graph, settlement.state, settlement.lineage
    masks = st.masks
    known_nodes = g.node_masks(settlement.known.masks)
    inherited = settlement.inherited & settlement.interpolated
    org = settlement.origins()
    cell_key = org["rows"] * _WIDTH + org["cols"]
    order = np.argsort(cell_key, kind="stable")
    sorted_keys = cell_key[order]
    names = [f.name for f in g.families]

    def family_name(code: int) -> str:
        return SYNONYMY.name if code == SYNONYM_HOP else names[code]

    def link_of(i: int) -> tuple[str, str, str]:
        origin = g.keys[int(org["origin"][i])]
        if org["entry"][i] < 0:
            return (SYNONYMY.name, origin, origin)
        return (family_name(int(org["first_family"][i])), origin, g.keys[int(org["first"][i])])

    def origins_of(row: int, col: int) -> list[tuple[int, dict]]:
        key = row * _WIDTH + col
        out = []
        for i in order[np.searchsorted(sorted_keys, key) : np.searchsorted(sorted_keys, key, "right")].tolist():
            e = int(org["entry"][i])
            hops = [] if e < 0 else [(family_name(int(lin.family[j])), g.keys[int(lin.node[j])]) for j in lin.path(e)]
            origin = int(org["origin"][i])
            fam, frm, to = link_of(i)
            out.append(
                (
                    i,
                    {
                        "origin": g.keys[origin],
                        "origin_stated": bool(_POPCOUNT[known_nodes[origin, col]] == 1),
                        "path": hops,
                        "candidate": {"family": fam, "from": frm, "to": to},
                        "last_hop": {
                            "family": family_name(int(org["family"][i])),
                            "from": g.keys[int(org["parent"][i])],
                        },
                    },
                )
            )
        return out

    def verdict(row: int, col: int, told) -> str | None:
        v = int(masks[row, col])
        if not inherited[row, col] or _POPCOUNT[v] != 1:
            return None
        if told is None:
            return DISAGREE_UNMENTIONED if v & CONTENT else None
        return "agrees" if v & told else DISAGREE_OPPOSITE

    disagreements, undetermined, conditional = [], [], []
    confirmations = 0
    link_disagree: dict = defaultdict(set)
    link_conditional: dict = defaultdict(set)
    link_agree: Counter = Counter()
    for ex in explications:
        rows = np.unique(np.asarray(ex.rows, dtype=np.int64))
        if not rows.size:
            continue
        for col in np.flatnonzero(inherited[rows].any(axis=0)).tolist():
            bank = BANKS[col]
            if bank not in expressible:
                not_judged[bank] += int(inherited[rows, col].sum())
                continue
            told = ex.states.get(bank)
            verdicts = [verdict(r, col, told) for r in rows.tolist()]
            if all(x == "agrees" for x in verdicts):
                confirmations += 1
                for r in rows.tolist():
                    for i, _ in origins_of(r, col):
                        link_agree[(*link_of(i), bank)] += 1
            elif all(x in (DISAGREE_UNMENTIONED, DISAGREE_OPPOSITE) for x in verdicts):
                readings = []
                for r, x in zip(rows.tolist(), verdicts):
                    carried = BIT_NAMES[int(masks[r, col])]
                    found = origins_of(r, col)
                    readings.append(
                        {"reading": st.readings[r], "carried": carried, "kind": x, "origins": [o for _, o in found]}
                    )
                    for i, _ in found:
                        link_disagree[(*link_of(i), bank, carried)].add(ex.key)
                disagreements.append(
                    {
                        "explication": ex.key,
                        "lemma": ex.lemma,
                        "pos": ex.pos,
                        "bank": bank,
                        "explication_states": state_names(told) if told is not None else [],
                        "readings": readings,
                    }
                )
            elif any(x in (DISAGREE_UNMENTIONED, DISAGREE_OPPOSITE) for x in verdicts):
                undetermined.append({"explication": ex.key, "lemma": ex.lemma, "pos": ex.pos, "bank": bank})
                for r, x in zip(rows.tolist(), verdicts):
                    if x not in (DISAGREE_UNMENTIONED, DISAGREE_OPPOSITE):
                        continue
                    carried = BIT_NAMES[int(masks[r, col])]
                    found = origins_of(r, col)
                    conditional.append(
                        {
                            "explication": ex.key,
                            "lemma": ex.lemma,
                            "pos": ex.pos,
                            "bank": bank,
                            "candidates": int(rows.size),
                            "reading": st.readings[r],
                            "carried": carried,
                            "kind": x,
                            "origins": [o for _, o in found],
                        }
                    )
                    for i, _ in found:
                        link_conditional[(*link_of(i), bank, carried)].add((ex.key, st.readings[r]))
    reach = Counter((*link_of(i), BANKS[int(org["cols"][i])]) for i in range(org["rows"].size))
    candidates = [
        {
            "link": {"family": fam, "from": frm, "to": to},
            "bank": bank,
            "carried": carried,
            "disagreeing_explications": sorted(keys),
            "agreeing_through_it": link_agree[(fam, frm, to, bank)],
            "inherited_cells_resting_on_it": reach[(fam, frm, to, bank)],
            "warrant": "NSM " + ", ".join(sorted(keys)),
        }
        for (fam, frm, to, bank, carried), keys in sorted(link_disagree.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    ]
    conditional_candidates = [
        {
            "link": {"family": fam, "from": frm, "to": to},
            "bank": bank,
            "carried": carried,
            "explications": sorted({k for k, _ in pairs}),
            "readings": len(pairs),
            "inherited_cells_resting_on_it": reach[(fam, frm, to, bank)],
        }
        for (fam, frm, to, bank, carried), pairs in sorted(
            link_conditional.items(), key=lambda kv: (-len(kv[1]), kv[0])
        )
    ]
    by_word_bank = Counter((d["lemma"], d["pos"], d["bank"]) for d in disagreements)
    conditional_by_word_bank = Counter((d["lemma"], d["pos"], d["bank"]) for d in conditional)
    return {
        "explications": len(explications),
        "disagreements": len(disagreements),
        "confirmations": confirmations,
        "undetermined": len(undetermined),
        "by_word_and_bank": {f"{w} ({p}) {b}": n for (w, p, b), n in sorted(by_word_bank.items())},
        "by_bank": dict(Counter(d["bank"] for d in disagreements).most_common()),
        "candidates": candidates,
        "details": disagreements,
        "undetermined_cells": undetermined,
        "not_judged": {"banks": sorted(set(BANKS) - expressible), "carried_cells": dict(not_judged.most_common())},
        "conditional": {
            "readings": len(conditional),
            "by_word_and_bank": {f"{w} ({p}) {b}": n for (w, p, b), n in sorted(conditional_by_word_bank.items())},
            "candidates": conditional_candidates,
            "details": conditional,
        },
    }
