"""Write the GSE-02 population-scale learning plan for scripts/run_lexicon_epochs.py (tasks.md GSE-02.3).

All 56 banks; scopes that select every native WordNet noun (under entity.n.01) and every native verb under an approved
verb identity root (selections only: a scope carries no sign); no authored rule families, so rules come from the
controller's own discovery over what it is taught (grounded chains, observed conjunctions); audits on held-out
everyday senses. The plan pins the baseline lexicon and the active pointer by digest, as the runner requires.

    .venv/bin/python scripts/plan_population_epochs.py --baseline <the live lexicon .db> --out <plan.json>
"""

import argparse
import json
from pathlib import Path

from GSE.curation.external_sources.wordnet_hierarchy import _WARRANTED_ROOT_PRIMITIVES
from GSE.curation.lexicon_builder.epoch import fingerprint, parse_plan
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.curation.lexicon_builder.learning_curriculum import FORMAT
from GSE.lexicon_resource import ACTIVE_POINTER

AUDITS = (
    "wordnet:dog:dog.n.01",
    "wordnet:door:door.n.01",
    "wordnet:tree:tree.n.01",
    "wordnet:water:water.n.01",
    "wordnet:house:house.n.01",
    "wordnet:glass:glass.n.01",
    "wordnet:run:run.v.01",
    "wordnet:eat:eat.v.01",
    "wordnet:give:give.v.03",
    "wordnet:know:know.v.01",
    "wordnet:see:see.v.01",
    "wordnet:hold:hold.v.02",
)


def scopes() -> list[dict]:
    native = ["wordnet_native_lemma", "true"]
    out = [{"id": "curriculum:nouns", "guards": [["pos", "noun"], native, ["wordnet_ancestor:entity.n.01", "true"]]}]
    for root in sorted(r for r in _WARRANTED_ROOT_PRIMITIVES if ".v." in r):
        out.append(
            {
                "id": f"curriculum:verbs-{root}",
                "guards": [["pos", "verb"], native, [f"wordnet_ancestor:{root}", "true"]],
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=50)
    args = parser.parse_args()
    plan = {
        "format": FORMAT,
        "baseline_sha256": fingerprint(args.baseline.resolve(strict=True)),
        "active_pointer_sha256": fingerprint(ACTIVE_POINTER),
        "epochs": args.epochs,
        "audits_per_epoch": 3,
        "families": [],
        "curriculum": {
            "banks": sorted(BANKS),
            "scopes": scopes(),
            "frontier_limit": 512,
            "banks_per_entry": 4,
            "candidate_limit": 64,
            "audit_entry_ids": list(AUDITS),
        },
    }
    parse_plan(plan)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(plan, indent=1) + "\n")
    print(
        json.dumps(
            {"scopes": len(plan["curriculum"]["scopes"]), "banks": len(BANKS), "baseline": plan["baseline_sha256"][:12]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
