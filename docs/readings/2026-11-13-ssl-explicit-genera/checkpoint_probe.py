"""Read-only public-entry-point comparison; semantic expectations precede execution."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from GSE.api import GSEEncoder
from GSE.cassettes.multiscale import MultiScaleDoc
from GSE.discourse.speech import encode_document_utterance_events
from GSE.structure import structural_loss_evidence
from GSE.symbolic import commitment, evaluate_tree, from_trace, polarity, propositions, resolve, to_dict

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

# These are declared structural expectations, not a general NLP gold set.
CASES = (
    ("action", "The dog chases the cat.", "Event", (("chase", "dog", "cat"),)),
    ("argument_swap", "The cat chases the dog.", "Event", (("chase", "cat", "dog"),)),
    ("negation", "The dog does not chase the cat.", "Negation", (("chase", "dog", "cat"),)),
    ("possibility", "The dog might chase the cat.", "Event", (("chase", "dog", "cat"),)),
    ("conditional", "If the dog runs, the cat sleeps.", "Conditional", (("run", "dog", None), ("sleep", "cat", None))),
    ("causation", "The dog runs because the cat barks.", "Causation", (("run", "dog", None), ("bark", "cat", None))),
    ("temporal", "Before the dog runs, the cat sleeps.", "Temporal", (("run", "dog", None), ("sleep", "cat", None))),
    ("comparison", "The dog is bigger than the cat.", "Comparison", ()),
    ("reported_claim", "Alice says that Bob left.", "Event", (("leave", "bob", None),)),
    ("type", "The dog is an animal.", "TypeAssertion", ()),
    ("possession", "The dog has a tail.", "Event", (("have", "dog", "tail"),)),
    ("conation", "The person wants food.", "Event", (("want", "person", "food"),)),
    ("medical_action", "The doctor examined the patient.", "Event", (("examine", "doctor", "patient"),)),
    ("acquisition", "She bought a book.", "Event", (("buy", "she", "book"),)),
    ("physical_event", "The river flows.", "Event", (("flow", "river", None),)),
    ("ambiguous_bank", "The bank is open.", "TypeAssertion", ()),
)

CLAIM_EXPECTATIONS = {
    "negation": (("chase", "committed", -1),),
    "possibility": (("chase", "non_committed", 1),),
    "conditional": (("run", "non_committed", 1), ("sleep", "non_committed", 1)),
    "reported_claim": (("leave", "non_committed", 1),),
}


def lexical_record(evidence):
    """Retain decisions and source IDs; replay reads definitions from the pinned DB."""
    contextual = evidence.get("contextual_grounding")
    return {
        **{
            key: evidence.get(key)
            for key in ("state", "reason", "selection_status", "sense_resolved", "candidate_entry_ids")
        },
        "selected_record": evidence.get("selected_record"),
        "domains": evidence.get("domains"),
        "contextual_grounding": (
            {k: v for k, v in contextual.items() if k != "considered_entry_ids"}
            if isinstance(contextual, dict)
            else contextual
        ),
    }


def module_hashes():
    result = {}
    for name, module in tuple(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        if name.startswith("gse.") and isinstance(filename, str):
            path = Path(filename)
            if path.suffix == ".py":
                result[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def head(value):
    if not isinstance(value, dict):
        return None
    if value.get("_kind") == "Atom":
        return value["lemma"]
    if value.get("_kind") == "Entity":
        return head(value["head"])
    return None


def sentence(enc, case):
    name, text, root, required = case
    record = {"id": name, "text": text, "expected_root": root, "required_events": required}
    try:
        trace = enc.encode(text)
        tree = evaluate_tree(resolve(from_trace(trace)))
        serialized = to_dict(tree)
        events = [
            (v["verb"], head(v.get("agent")), head(v.get("patient")))
            for v in walk(serialized)
            if v.get("_kind") == "Event"
        ]
        record.update(
            tree=serialized,
            events=events,
            structural_expectation=(
                "IDENTIFIED" if serialized["_kind"] == root and all(v in events for v in required) else "WRONG"
            ),
            structural_loss=structural_loss_evidence(trace, tree),
            claims=[
                {
                    "kind": type(p.node).__name__,
                    "verb": getattr(p.node, "verb", None),
                    "commitment": commitment(p),
                    "polarity": dataclasses.asdict(polarity(p)),
                    "scopes": [s.mode for s in p.scopes],
                }
                for p in propositions(tree, source_text=text)
            ],
            tokens=[
                {
                    "token": t.token,
                    "lemma": t.lemma,
                    "pos": t.pos,
                    "word_primitives": t.word_primitives,
                    "lexicon_status": t.lexicon_status,
                    "lexical_evidence": lexical_record(t.lexical_evidence),
                }
                for t in trace.tokens
            ],
        )
        observed_claims = {
            (getattr(p.node, "verb", None), commitment(p), polarity(p).sign)
            for p in propositions(tree, source_text=text)
        }
        record["claim_expectations"] = [
            {"expected": expected, "outcome": "IDENTIFIED" if expected in observed_claims else "WRONG"}
            for expected in CLAIM_EXPECTATIONS.get(name, ())
        ]
    except Exception as exc:
        record.update(structural_expectation="ABSTAINED", error_type=type(exc).__name__, error=str(exc))
    return record


def document(enc, text):
    try:
        doc = MultiScaleDoc(text, encoder=enc)
        return {
            "text": text,
            "phases": doc.phases,
            "sentence_states": doc.sentence_states,
            "trees": [to_dict(t) for t in doc.resolved],
            "losses": [e["structural_loss"] for e in doc.utterance_outcomes],
            "failures": [{k: e[k] for k in ("source_sentence_id", "error")} for e in doc.failures],
        }
    except Exception as exc:
        return {"text": text, "error_type": type(exc).__name__, "error": str(exc)}


def boundaries(enc):
    out = []
    for name, records in (
        ("empty", []),
        ("null", None),
        ("duplicate_id", [{"id": "x", "text": "The dog runs."}, {"id": "x", "text": "The cat sleeps."}]),
        ("empty_text", [{"id": "empty", "text": ""}]),
    ):
        try:
            events = list(encode_document_utterance_events(enc, records))
            out.append({"id": name, "outcome": "RETURNED", "events": events})
        except Exception as exc:
            out.append({"id": name, "outcome": "REFUSED", "error_type": type(exc).__name__, "error": str(exc)})
    return out


def main():
    results = []
    for label, path in (("active_sparse", None), ("legacy_proposal_resource", ROOT / "data/lexicon_clean.db")):
        enc = GSEEncoder(db_path=path)
        try:
            rows = [sentence(enc, c) for c in CASES]
            results.append(
                {
                    "resource": label,
                    "path": str(enc.db_path),
                    "sentences": rows,
                    "structural_counts": dict(Counter(r["structural_expectation"] for r in rows)),
                    "documents": [
                        document(enc, t)
                        for t in (
                            "The woman owns a dog. She feeds it.",
                            "Alice owns a dog. She feeds it.",
                            "The doctor treated the patient. The patient thanked the doctor.",
                        )
                    ],
                    "boundaries": boundaries(enc),
                }
            )
        finally:
            enc.close()
    report = {
        "format": "GSE.checkpoint-public-api-probe/1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "active_pointer": json.loads((ROOT / "data/lexicon_active.json").read_text()),
        "legacy_sha256": hashlib.file_digest((ROOT / "data/lexicon_clean.db").open("rb"), "sha256").hexdigest(),
        "expectation_scope": "DECLARED_STRUCTURAL_SUBSET_NOT_GENERAL_SEMANTIC_ACCURACY",
        "code_sha256": module_hashes(),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "results": results,
    }
    destination = HERE / "checkpoint-public-api-probe.json"
    destination.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(
        json.dumps(
            {
                "report": str(destination),
                "results": [{"resource": r["resource"], "structural_counts": r["structural_counts"]} for r in results],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
