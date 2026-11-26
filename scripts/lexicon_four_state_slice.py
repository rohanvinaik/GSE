"""Element 2's first slice: the four-state contract on a cohort, read-only against a release.

Each definition starts at the F040 domains (silence possible), keeps its stored singletons (the release's own warranted
closure, cited by entry), and is closed under:
- the release's relations, read under F088 (silence.read_with_silence);
- the archived founder laws' data whose guards a stated source decides: the head record by part of speech (F057,
  F088, F118, F144) and F067's evaluator/size exclusions where WordNet's attribute relation types the adjective by
  the attribute stated for the prime's own exponent (good.a.01/bad.a.01 -> quality.n.01; big/large/small.a.01 ->
  size.n.01). OPERATOR_HEADS_NO_SUBSTANTIVE and FEAR_AVERSION (flagged at F156) are not used.

    .venv/bin/python scripts/lexicon_four_state_slice.py [--words FILE] [--show w1,w2,...] [--receipt FILE]
"""

from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from GSE.curation.lexicon_builder.engine import EMPTY, STATES, DomainRestriction, Relation, propagate  # noqa: E402
from GSE.curation.lexicon_builder.foundation import BANKS, definition_context  # noqa: E402
from GSE.curation.lexicon_builder.silence import read_with_silence, starting_domains  # noqa: E402

RELEASE = ROOT / "data/lexicon_builder/2026-11-12/sparse-release-022-verbnet-do.db"
WORDS = ROOT / "docs/verification/lexicon-rebuild/closeout-2026-10-25/gate/gate_words.txt"
LAWS = ROOT / "GSE/curation/lexicon_builder/bank_laws.json"
USED_LAWS = (
    "MODIFIER_LACKS_INDEPENDENT_OBJECTNESS",
    "MODIFIER_HEADS_NO_SUBSTANTIVE",
    "VERB_HEADS_NO_SUBSTANTIVE",
    "EVALUATOR_EXCLUDES_SIZE",
    "SIZE_DESCRIPTOR_EXCLUDES_EVALUATION",
)
# The head record's own word classes (F144): a located verb is a lexical predicate; an adjective or adverb is an
# exclusively modifying property. Nouns are substantive heads and get no role guard here.
ROLE_BY_POS = {"verb": "lexical_predicate", "adjective": "modifier_property_only", "adverb": "modifier_property_only"}
# The attribute WordNet states for the prime's own exponent synset.
KIND_BY_ATTRIBUTE = {"quality.n.01": "evaluator", "size.n.01": "size_descriptor"}
STATE = {"empty": EMPTY, "0": 0, "+1": 1, "-1": -1}


def _laws() -> tuple[Relation, ...]:
    out = []
    for law in json.loads(LAWS.read_text())["laws"]:
        if law["rule_id"] not in USED_LAWS:
            continue
        rows = tuple(tuple(STATE[value] for value in row) for row in law["allowed"])
        refs = tuple(law.get("source_refs") or ()) or (str(law.get("warrant", ""))[:120],)
        guards = tuple((key, value) for key, value in law["guard"])
        out.append(Relation(law["rule_id"], tuple(law["coordinates"]), rows, refs, "foundational", True, guards))
    return tuple(out)


def _release_relations(conn) -> tuple[Relation, ...]:
    (raw,) = conn.execute("SELECT value FROM builder_metadata WHERE key='relations'").fetchone()
    out = []
    for r in json.loads(raw):
        relation = Relation(
            r["rule_id"],
            tuple(r["banks"]),
            tuple(tuple(row) for row in r["allowed_rows"]),
            tuple(r["provenance"]),
            r["authority"],
            r["approved"],
            tuple(tuple(g) for g in r["guards"]),
            tuple(r.get("absent_evidence") or ()),
        )
        if not relation.absent_evidence:
            out.append(read_with_silence(relation))
    return tuple(out)


def _semantic_kind(entry_id: str) -> str | None:
    if not entry_id.startswith("wordnet:"):
        return None
    from nltk.corpus import wordnet as wn

    try:
        synset = wn.synset(entry_id.rsplit(":", 1)[1])
    except Exception:
        return None
    if synset.pos() not in ("a", "s"):
        return None
    heads = synset.similar_tos() if synset.pos() == "s" else [synset]
    kinds = {KIND_BY_ATTRIBUTE[a.name()] for h in heads for a in h.attributes() if a.name() in KIND_BY_ATTRIBUTE}
    return kinds.pop() if len(kinds) == 1 else None


def _type_silences(entry: str, stored: dict) -> tuple[tuple, list]:
    """A WordNet noun's type-orthogonal banks as silence restrictions (applicability.py); a bank whose stored
    content collides is not silenced but recorded as an exception to the type row (significance weighting)."""
    if not entry.startswith("wordnet:") or not (".n." in entry or ".v." in entry):
        return (), []
    from nltk.corpus import wordnet as wn

    from GSE.curation.lexicon_builder.applicability import silent_banks, verb_silent_banks

    try:
        noun_type = wn.synset(entry.rsplit(":", 1)[1]).lexname()
    except Exception:
        return (), []
    out, excepted = [], []
    banks = verb_silent_banks(noun_type) if noun_type.startswith("verb.") else silent_banks(noun_type)
    for bank in banks:
        value = stored.get(bank)
        if value and len(value) == 1:  # a stored decision stands: content is an exception, an explicit 0 is kept
            if value[0]:
                excepted.append({"entry": entry, "type": noun_type, "bank": bank, "stored": value[0]})
            continue
        out.append(DomainRestriction(bank, (EMPTY,), "noun-type-applicability", f"{noun_type}#{bank}", "applicability"))
    return tuple(out), excepted


def _cells(domains: dict) -> dict:
    out = collections.Counter()
    for values in domains.values():
        if not values:
            out["conflict"] += 1
        elif len(values) > 1:
            out["open"] += 1
        else:
            (value,) = tuple(values)
            out["silent" if value is EMPTY else "zero" if value == 0 else "content"] += 1
    return out


def run(words: list[str] | None, show: set[str], out: Path | None = None) -> dict:
    conn = sqlite3.connect(f"file:{RELEASE}?mode=ro", uri=True)
    relations = _release_relations(conn) + _laws()
    start = starting_domains(BANKS)
    by_pos: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    shown, codes, kinds, exceptions = [], collections.Counter(), collections.Counter(), []
    sink = None
    if out is not None:
        sink = sqlite3.connect(out)
        sink.execute("DROP TABLE IF EXISTS four_state_cells")
        sink.execute(
            "CREATE TABLE four_state_cells (entry_id TEXT PRIMARY KEY, code TEXT, content TEXT, zero TEXT, silent TEXT,"
            " open TEXT, conflicts TEXT)"
        )
    batches = (
        [
            (
                w,
                conn.execute(
                    "SELECT d.entry_id, l.pos, d.domains FROM definition_states d JOIN lexemes l ON d.lexeme_id = l.id"
                    " WHERE l.lemma = ?",
                    (w,),
                ).fetchall(),
            )
            for w in words
        ]
        if words is not None
        else [
            (
                None,
                conn.execute(
                    "SELECT d.entry_id, l.pos, d.domains FROM definition_states d JOIN lexemes l ON d.lexeme_id = l.id"
                ),
            )
        ]
    )
    for word, rows in batches:
        for entry, pos, raw in rows:
            stored = json.loads(raw)
            before = _cells({bank: frozenset(v) if len(v) == 1 else frozenset(STATES) for bank, v in stored.items()})
            restrictions = tuple(
                DomainRestriction(bank, (v[0],), "release-closure", f"{entry}#{bank}", "stored-state")
                for bank, v in sorted(stored.items())
                if len(v) == 1 and bank in start
            )
            context = definition_context(pos or "")
            role = ROLE_BY_POS.get(context.get("pos", ""))
            if role:
                context["own_role"] = role
            silences, excepted = _type_silences(entry, stored)
            restrictions = restrictions + silences
            exceptions.extend(excepted)
            kind = _semantic_kind(entry)
            if kind:
                context["own_semantic_kind"] = kind
                kinds[kind] += 1
            result = propagate(BANKS, (), relations, context, domain_restrictions=restrictions, initial_domains=start)
            after = _cells(result.domains)
            if sink is not None:
                sink.execute(
                    "INSERT INTO four_state_cells VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        entry,
                        result.code,
                        json.dumps(result.assignments and {b: v for b, v in result.assignments.items() if v}),
                        json.dumps(sorted(b for b, d in result.domains.items() if d == {0})),
                        json.dumps(list(result.silent)),
                        json.dumps(
                            {
                                b: sorted(d, key=lambda x: -2 if x is None else x)
                                for b, d in result.domains.items()
                                if len(d) > 1
                            }
                        ),
                        json.dumps(result.conflicts[:1], default=str),
                    ),
                )
            codes[result.code] += 1
            key = context.get("pos", pos or "?")
            for state in ("content", "zero", "silent", "open", "conflict"):
                by_pos[key][f"before_{state}"] += before.get(state, 0)
                by_pos[key][f"after_{state}"] += after.get(state, 0)
            by_pos[key]["definitions"] += 1
            if word in show:
                changed = {
                    r["bank"]: f"{r['remaining']} <- {r.get('rule_id') or r.get('source')}"
                    for r in result.trace
                    if r["kind"] in ("RELATION", "DOMAIN_RESTRICTION") and r.get("source") != "release-closure"
                }
                shown.append(
                    {
                        "word": word,
                        "entry": entry,
                        "pos": key,
                        "context": context,
                        "code": result.code,
                        "content": {
                            b: next(iter(v))
                            for b, v in result.domains.items()
                            if len(v) == 1 and next(iter(v)) not in (0, EMPTY)
                        },
                        "zero": sorted(b for b, v in result.domains.items() if v == {0}),
                        "silent": list(result.silent),
                        "open": sorted(b for b, v in result.domains.items() if len(v) > 1),
                        "newly_decided_by": changed,
                    }
                )
    if sink is not None:
        sink.commit()
    return {
        "words": len(words) if words is not None else "ALL",
        "codes": dict(codes),
        "typed_adjectives": dict(kinds),
        "type_exceptions": exceptions,
        "by_pos": {k: dict(v) for k, v in by_pos.items()},
        "shown": shown,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--words", type=Path, default=WORDS)
    parser.add_argument("--show", default="")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--all", action="store_true", help="every definition in the release, not a word list")
    parser.add_argument("--out", type=Path, help="write each definition's four-state cells to this SQLite file")
    args = parser.parse_args()
    words = None if args.all else [w.strip() for w in args.words.read_text().split("\n") if w.strip()]
    result = run(words, {w for w in args.show.split(",") if w}, args.out)
    text = json.dumps(result, indent=1, default=str)
    if args.receipt:
        args.receipt.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
