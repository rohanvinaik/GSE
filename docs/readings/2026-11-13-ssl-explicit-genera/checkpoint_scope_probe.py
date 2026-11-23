"""Exercise composed document context and the actual claim-key consumer."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from GSE.api import GSEEncoder
from GSE.cassettes.multiscale import MultiScaleDoc
from GSE.symbolic import claim_key, commitment, propositions, to_dict


def main():
    cases = []
    with GSEEncoder() as encoder:
        for text in ("The dog is bigger than the cat.", "The dog is an animal.",
                     "Alice says that Bob left.", "The dog chases the cat."):
            doc = MultiScaleDoc(text, encoder=encoder)
            claims = []
            for tree in doc.resolved:
                for proposition in propositions(tree, source_text=text):
                    # A missing producer-selected verb signature stays unavailable.
                    evidence = None
                    verb = getattr(proposition.node, "verb", None)
                    selected = [t.word_primitives for outcome in doc.utterance_outcomes
                                if outcome["state"] == "read" for t in outcome["trace"].tokens
                                if t.lemma == verb and t.word_primitives]
                    if len(selected) == 1:
                        evidence = selected[0]
                    claims.append({"kind": type(proposition.node).__name__, "verb": verb,
                                   "commitment": commitment(proposition),
                                   "key": dataclasses.asdict(claim_key(proposition, evidence, namespace="checkpoint-probe"))})
            cases.append({"text": text, "phases": doc.phases, "claims": claims,
                          "trees": [to_dict(tree) for tree in doc.resolved],
                          "utterances": [{k: outcome[k] for k in ("content", "speaker", "quoted", "state")}
                                         for outcome in doc.utterance_outcomes]})
    destination = Path(__file__).with_name("checkpoint-composed-consumer-probe.json")
    destination.write_text(json.dumps({"format": "GSE.checkpoint-composed-consumer-probe/1", "cases": cases}, indent=2) + "\n")
    print(json.dumps([{"text": case["text"], "claims": case["claims"]} for case in cases], indent=2))


if __name__ == "__main__":
    main()
