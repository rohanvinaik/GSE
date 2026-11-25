"""One read-only cycle of the lexicon promotion ledger over the type-guarded identity rules.

Each rule in ``wordnet_hierarchy._WARRANTED_ROOT_PRIMITIVES`` says every WordNet definition under type T
has bank b = v. This script measures, for each, its stated confirmations and contradictions (every exact
channel of ``stated_channels``, plus native restrictions; never ``wordnet_hierarchy``, whose values rules
derive), its
reach on the lexicon before identity, and any reviewed release rule for the same bank that the identity
rule extends beyond its reviewed scope; then applies ``ledger.verdict``. It writes nothing to a lexicon.

    .venv/bin/python scripts/lexicon_ledger_cycle.py --before PRE.db --after PUBLISHED.db --report OUT.json
"""

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

from nltk.corpus import wordnet as wn
from nltk.corpus.reader.wordnet import WordNetError

from GSE.curation.external_sources import wordnet_hierarchy as wh
from GSE.curation.external_sources.framenet import FRAME_TO_PRIMITIVE, FrameNetParser
from GSE.curation.external_sources.source_scope import in_scope
from GSE.curation.external_sources.usas import USASParser
from GSE.curation.lexicon_builder.ledger import impute_guard_candidates, verdict
from GSE.curation.lexicon_builder.stated_channels import collect

DERIVED_SOURCE = "wordnet_hierarchy"


def _conn(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _synset(entry_id):
    try:
        return wn.synset(unquote(entry_id.rsplit(":", 1)[-1]))
    except WordNetError, ValueError:
        return None


def _ancestors(synset):
    return frozenset(a.name() for path in synset.hypernym_paths() for a in path)


def _stated(conn):
    """entry -> [(bank, value, source)] from non-derived sources; entry -> [(bank, allowed, source)]."""
    facts = defaultdict(list)
    for entry, payload in conn.execute(
        "SELECT entry_id, payload FROM builder_assertions WHERE entry_id LIKE 'wordnet:%'"
    ):
        record = json.loads(payload)
        if record["source"] != DERIVED_SOURCE:
            facts[entry].append((record["bank"], record["value"], record["source"]))
    restrictions = defaultdict(list)
    columns = [row[1] for row in conn.execute("PRAGMA table_info(builder_domain_restrictions)")]
    if "payload" in columns:
        for entry, payload in conn.execute(
            "SELECT entry_id, payload FROM builder_domain_restrictions WHERE entry_id LIKE 'wordnet:%'"
        ):
            record = json.loads(payload)
            if record.get("source") != DERIVED_SOURCE:
                restrictions[entry].append((record["bank"], tuple(record["allowed_values"]), record["source"]))
    return facts, restrictions


def run(before, after):
    rules = []
    for name, banks in sorted(wh._WARRANTED_ROOT_PRIMITIVES.items()):
        for bank in sorted(banks):
            excluded = wh.REVIEWED_BRANCH_EXCLUSIONS.get((name, bank))
            rules.append((name, bank, wh.ROOT_CONCEPT_PRIMITIVES[name][bank], excluded))
    pre, post = _conn(before), _conn(after)
    _facts, restrictions = _stated(post)
    entries, linked = {}, {}
    for (entry,) in post.execute("SELECT entry_id FROM definition_states WHERE entry_id LIKE 'wordnet:%'"):
        synset = _synset(entry)
        if synset is not None:
            entries[entry] = _ancestors(synset) | {synset.name()}
            linked[entry] = (synset.name(), entries[entry], unquote(entry.split(":")[1]))
    usas = USASParser()
    usas.load()
    framenet = FrameNetParser()
    framenet.load()
    facts = collect(post, linked, usas, framenet.entries, FRAME_TO_PRIMITIVE, in_scope, wn)
    domains = {
        e: json.loads(d)
        for e, d in pre.execute("SELECT entry_id, domains FROM definition_states WHERE entry_id LIKE 'wordnet:%'")
    }
    reviewed = json.loads(post.execute("SELECT value FROM builder_metadata WHERE key='relations'").fetchone()[0])
    rows = []
    for name, bank, value, excluded in rules:
        members = [e for e, types in entries.items() if name in types and (excluded is None or excluded not in types)]
        confirming, contradicting, kappa = [], [], 0
        for entry in members:
            stated = {v for b, v, _s in facts.get(entry, ()) if b == bank}
            allowed = [set(a) for b, a, _s in restrictions.get(entry, ()) if b == bank]
            if value in stated or any(a == {value} for a in allowed):
                confirming.append(entry)
            if stated - {value} or any(value not in a for a in allowed):
                contradicting.append(entry)
            if domains.get(entry, {}).get(bank, [value]) != [value]:
                kappa += 1
        rivals = [
            r["rule_id"]
            for r in reviewed
            if bank in r["banks"] and any(k == f"wordnet_ancestor:{name}" for k, _ in r["guards"])
        ]
        guards = impute_guard_candidates([entries[e] for e in confirming], [entries[e] for e in contradicting])
        code = verdict(len(confirming), len(contradicting), kappa, guards, bool(rivals) and kappa > 0)
        sources = dict(
            sorted(
                __import__("collections")
                .Counter(
                    s.split(":")[0] for e in confirming for b, v, s in facts.get(e, ()) if b == bank and v == value
                )
                .items()
            )
        )
        rows.append(
            {
                "rule": f"{name} => {bank}={value:+d}",
                "excluded_branch": excluded,
                "definitions": len(members),
                "kappa_open_before_identity": kappa,
                "confirming": len(confirming),
                "confirming_sources": sources,
                "confirming_examples": [e.split(":", 1)[1] for e in confirming[:6]],
                "contradicting": len(contradicting),
                "contradicting_examples": [e.split(":", 1)[1] for e in contradicting[:6]],
                "separating_guards": list(guards[:8]),
                "reviewed_rules_for_bank": rivals,
                "verdict": code,
            }
        )
    return {"format": "GSE.lexicon-ledger-cycle/2", "before": str(before), "after": str(after), "rules": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise ValueError("LEDGER_CYCLE_REPORT_MUST_BE_NEW")
    report = run(args.before, args.after)
    args.report.write_text(json.dumps(report, indent=1) + "\n")
    for row in report["rules"]:
        print(
            f"{row['verdict']:32} {row['rule']:34} defs {row['definitions']:6} kappa {row['kappa_open_before_identity']:6}"
            f" +{row['confirming']:<4} -{row['contradicting']:<4} {row['confirming_sources']}"
        )


if __name__ == "__main__":
    main()
