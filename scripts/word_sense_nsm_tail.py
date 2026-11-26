"""Classify every disagreement between the lexicon and NSM's verified explications by cause (F148, the tail).

The explications are matched to words exactly as ``scripts/lexicon_measure_vs_nsm.py`` matches them; each prime their
own clauses use that the word's reading does not hold at +1 gets a cause from
``GSE.curation.lexicon_builder.word_sense_nsm_tail``. The agreements are classified by the same token kinds, so the
receipt also says how many of them rest on template structure rather than content. The receipt holds source keys, line
ranges, lemmas, banks, classes and counts; never the explications' text.

    .venv/bin/python scripts/word_sense_nsm_tail.py --receipt docs/verification/<date>-nsm-tail-classes.json [--db X.db]
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from GSE.curation.lexicon_builder import word_sense_nsm_tail as tail  # noqa: E402
from GSE.curation.lexicon_builder.applicability import bank_categories  # noqa: E402
from GSE.curation.lexicon_builder.template_types import banks_in, own_lines, verified_records  # noqa: E402
from GSE.lexicon.senses import read_senses  # noqa: E402
from GSE.lexicon_resource import resolve_lexicon_path  # noqa: E402

POS_GUESS = ("noun", "verb", "adj")


def _lemma(explicandum: str) -> str | None:
    words = re.sub(r"\(.*?\)|\[.*?\]", " ", explicandum.lower()).split()
    return words[0] if len(words) == 1 else None


def _match(conn, record):
    """The same lemma and part of speech ``lexicon_measure_vs_nsm`` reads."""
    lemma = _lemma(record["explicates"])
    if not lemma:
        return None, None
    for form in dict.fromkeys([lemma, lemma[:-1] if lemma.endswith("s") else lemma]):
        for pos in POS_GUESS:
            found = read_senses(conn, form, pos)
            if found and found["pos"] == pos:
                return found, (form, pos)
    return None, None


def _senses(conn, lemma: str, pos: str) -> list[dict]:
    return [
        {"sense": s, "assignments": json.loads(a), "provenance": json.loads(p), "blocked": json.loads(b)}
        for s, a, p, b in conn.execute(
            "SELECT sense, assignments, provenance, blocked FROM word_senses WHERE lemma = ? AND pos = ? ORDER BY sense",
            (lemma, pos),
        )
    ]


def _votes(conn, lemma: str) -> dict:
    row = conn.execute("SELECT agreement FROM word_source_agreement WHERE lemma = ?", (lemma,)).fetchone()
    return json.loads(row[0])["votes"] if row else {}


def _dominant(conn, lemma: str) -> str | None:
    """The part of speech with the most definitions, as ``word_senses.dominant_pos`` chooses it at build time."""
    counts = {}
    for pos, members, absorbed in conn.execute(
        "SELECT pos, members, absorbed FROM word_senses WHERE lemma = ?", (lemma,)
    ):
        counts[pos] = counts.get(pos, 0) + len(json.loads(members)) + len(json.loads(absorbed))
    order = {"noun": 0, "verb": 1, "adj": 2, "adv": 3}
    ranked = sorted(counts, key=lambda pos: (-counts[pos], order.get(pos, 9), pos))
    return ranked[0] if ranked else None


def _traces(conn, senses) -> dict[str, list]:
    entries = {e for s in senses for origin in s["provenance"].values() for e in origin.get("entries") or ()}
    out = {}
    for entry in sorted(entries):
        row = conn.execute("SELECT trace FROM definition_states WHERE entry_id = ?", (entry,)).fetchone()
        out[entry] = json.loads(row[0] or "[]") if row else []
    return out


def measure_synset_carry(conn, matched: list[tuple[dict, tuple[str, str], dict]]) -> dict:
    """The synset carry (``word_sense_nsm_tail.synset_carry``) over the whole lexicon, and against every matched NSM
    explication: a carried value on a bank the explication's own clauses use counts as a counterexample when it
    differs from +1 (any token) or from the sign of the explication's content tokens; it agrees when it is +1."""
    values: dict[int, dict[str, int]] = {}
    for lexeme, bank, value in conn.execute("SELECT lexeme_id, primitive, value FROM primitive_values"):
        values.setdefault(lexeme, {})[bank] = value
    entries = conn.execute(
        "SELECT d.entry_id, d.lexeme_id, l.lemma FROM definition_states d JOIN lexemes l ON l.id = d.lexeme_id "
        "WHERE d.entry_id LIKE 'wordnet:%'"
    ).fetchall()
    carry = tail.synset_carry(entries, values)
    gained = Counter((bank, value) for row in carry.values() for bank, value in row["gained"].items())
    nsm = {"agree": 0, "counterexample_any_token": 0, "counterexample_content_sign": 0, "cells_reaching": 0}
    examples = []
    for record, (lemma, pos), tokens in matched:
        members = {
            e
            for (m,) in conn.execute("SELECT members FROM word_senses WHERE lemma = ? AND pos = ?", (lemma, pos))
            for e in json.loads(m)
        }
        for entry in sorted(members & set(carry)):
            for bank, value in carry[entry]["gained"].items():
                found = tokens.get(bank)
                if not found:
                    continue
                nsm["cells_reaching"] += 1
                content = {t.sign for t in found if t.kind == "content"}
                if value == 1:
                    nsm["agree"] += 1
                else:
                    nsm["counterexample_any_token"] += 1
                if content and value not in content:
                    nsm["counterexample_content_sign"] += 1
                if value != 1 or (content and value not in content):
                    examples.append(
                        {
                            "source": record["source"],
                            "lines": [record["start_line"], record["end_line"]],
                            "entry": entry,
                            "bank": bank,
                            "carried": value,
                        }
                    )
    return {
        "derived_spelling_entries_with_native_sibling": len(carry),
        "entries_gaining": sum(1 for row in carry.values() if row["gained"]),
        "lemmas_gaining": len({e.split(":")[1] for e, row in carry.items() if row["gained"]}),
        "cells_gained": sum(gained.values()),
        "cells_gained_by_bank_value": {f"{b}={v}": n for (b, v), n in gained.most_common()},
        "stored_value_clashes": sum(len(row["clash"]) for row in carry.values()),
        "nsm": nsm,
        "nsm_counterexamples": examples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--db", type=Path, help="a candidate lexicon (default: the active pointer)")
    parser.add_argument(
        "--synset-carry", type=Path, help="also measure the (unbuilt) synset carry and write its receipt here"
    )
    args = parser.parse_args()
    db = args.db or resolve_lexicon_path()
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    categories = bank_categories()
    rows = []
    classes: Counter = Counter()
    agree_kinds: Counter = Counter()
    by_class_bank: Counter = Counter()
    content_sources: Counter = Counter()
    matched = []
    for record in verified_records():
        if record["kind"] != "explication":
            continue
        reading, used = _match(conn, record)
        if not reading:
            continue
        nsm = sorted(set().union(set(), *(banks_in(c) for c in own_lines(record["text"]))))
        held = reading["assignments"]
        senses = _senses(conn, *used)
        traces = _traces(conn, senses)
        votes = _votes(conn, used[0])
        dominant = _dominant(conn, used[0])
        tokens = tail.bank_tokens(record["text"], categories)
        matched.append((record, used, tokens))
        out = {}
        for bank in nsm:
            found = tokens.get(bank, [])
            entry = {
                "held": held.get(bank),
                "token_kinds": dict(sorted(Counter(t.kind for t in found).items())),
                "nsm_signs": sorted({t.sign for t in found}),
            }
            if held.get(bank) == 1:
                entry["class"] = "AGREE"
                agree_kinds[tail.token_class(bank, found, categories)] += 1
            else:
                entry["class"] = tail.classify(bank, held, senses, found, categories, traces)
                classes[entry["class"]] += 1
                by_class_bank[(entry["class"], bank)] += 1
                if entry["class"] in ("CONTENT", "LOGICAL_OPERATOR"):
                    entry["sources"] = tail.source_state(bank, votes, used[1], used[1] == dominant)
                    entry["senses_holding"] = sorted(
                        {s["assignments"][bank] for s in senses if bank in s["assignments"]}
                    )
                    entry["blocked_in_senses"] = sorted(
                        {s["blocked"][bank]["cause"] for s in senses if bank in s["blocked"]}
                    )
                    content_sources[(entry["class"], bank, entry["sources"])] += 1
            out[bank] = entry
        rows.append(
            {
                "source": record["source"],
                "lines": [record["start_line"], record["end_line"]],
                "lemma": used[0],
                "pos": used[1],
                "banks": out,
            }
        )
    receipt = {
        "lexicon": str(db),
        "explications_matched": len(rows),
        "component_introducers": list(tail.component_introducers()),
        "disagreements_by_class": dict(classes.most_common()),
        "disagreements_by_class_and_bank": {
            cls: dict(sorted(((b, n) for (c, b), n in by_class_bank.items() if c == cls), key=lambda x: (-x[1], x[0])))
            for cls in classes
        },
        "agreements_by_token_class": dict(agree_kinds.most_common()),
        "content_by_source_state": dict(
            sorted(Counter(state for (_c, _b, state), n in content_sources.items() for _ in range(n)).items())
        ),
        "content_by_bank_and_source_state": {
            f"{cls}/{bank}/{state}": n for (cls, bank, state), n in sorted(content_sources.items())
        },
        "rows": rows,
    }
    args.receipt.write_text(json.dumps(receipt, indent=1) + "\n")
    if args.synset_carry:
        carry = {"lexicon": str(db), **measure_synset_carry(conn, matched)}
        args.synset_carry.write_text(json.dumps(carry, indent=1) + "\n")
        print(json.dumps({k: v for k, v in carry.items() if k not in ("nsm_counterexamples",)}))
    print(
        json.dumps(
            {
                "explications_matched": len(rows),
                "disagreements": sum(classes.values()),
                "by_class": receipt["disagreements_by_class"],
                "agreements_by_token_class": receipt["agreements_by_token_class"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
