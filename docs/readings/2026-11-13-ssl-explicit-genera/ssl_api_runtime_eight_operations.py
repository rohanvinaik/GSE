"""Finite, read-only production consumer audit; NOT a lexicon constructor.

The manifest is written before executing cases. Development families and exposed
counterexamples stay development. This runner never supplies lexical answers to
the encoder or writes a lexical store. Failed checks are retained, not filtered.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from GSE.api import GSEEncoder
from GSE.cassettes.multiscale import MultiScaleDoc
from GSE.cassettes.entity_identity import EntityIdentity
from GSE.cassettes.deck import CassetteDeck
from GSE.discourse.profile import text_profile
from GSE.nlp.spellcheck import _Lexicon, correct
from GSE.pipeline_v2 import GSEPipeline
from GSE.symbolic import KnowledgeBase, emit_contract, evaluate_tree, from_trace, resolve
from GSE.symbolic import queries
from GSE.symbolic.claims import claim_key, commitment, polarity
from GSE.symbolic.grounding import NullGenealogy
from GSE.symbolic.propositions import propositions


D = Path(__file__).resolve().parent
ROLE = "B — CP-07 REAL RUNTIME IDENTITY / CHECKPOINT ACCEPTANCE"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def plain(value):
    if is_dataclass(value):
        return plain(asdict(value))
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return {"shape": list(value.shape), "dtype": str(value.dtype),
                "sha256": hashlib.sha256(value.tobytes()).hexdigest()}
    if isinstance(value, (set, frozenset)):
        return sorted(plain(v) for v in value)
    return value


def objects(value):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from objects(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from objects(v)


def write(path, data):
    Path(path).write_text(json.dumps(plain(data), indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("lexicon", type=Path)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    start = time.monotonic()
    before = sha(args.lexicon)
    freeze = D / "ssl-api-runtime-fourth-source-freeze.json"
    pins = json.loads(freeze.read_text())["source_pins"]
    # A manifest of finite expectations is persisted before any consumer call.
    sentence_cases = json.loads((D / "ssl-api-runtime-complete-operation-cases-v1.json").read_text())["cases"]
    sentence_cases += [
        {"id": "topic-about", "text": "I think about the door.", "expected": "think event with door topic, not about event"},
        {"id": "he-generic", "text": "He is an organism.", "expected": "pronoun person preserved, not chemical identity"},
        {"id": "he-symbol", "text": "The chemical symbol He denotes helium.", "expected": "exact native helium identity, not pronoun"},
        {"id": "he-chemical-copula", "text": "He is an inert gas.", "expected": "nominal type assertion and exact helium identity"},
        {"id": "teacher-relative", "text": "The teacher is a person whose occupation is teaching.", "expected": "matrix person assertion plus relative occupation/teaching; exact teacher source"},
        {"id": "femur-modifier", "text": "The femur is the longest and thickest bone of the human skeleton.", "expected": "bone head; long and thick modifiers; skeleton attachment not coordinate peer"},
        {"id": "imperative-main-do", "text": "Do the work.", "expected": "imperative do(you,work), not auxiliary"},
        {"id": "imperative-pronoun-do", "text": "Do it.", "expected": "imperative do(you,it), not auxiliary"},
        {"id": "inverted-do", "text": "Does Nora repair the bicycle?", "expected": "interrogative repair(nora,bicycle), not main do"},
        {"id": "inverted-pronoun-do", "text": "Does it work?", "expected": "interrogative work(it), not main do"},
        {"id": "aux-have-possession-leak", "text": "I have eaten.", "expected": "eat event, no lexical HAVE on auxiliary"},
        {"id": "aux-be-state-leak", "text": "She is running.", "expected": "run event, no lexical BE on progressive auxiliary"},
        {"id": "copula-be-state-leak", "text": "She is a person.", "expected": "type assertion, no lexical BE on grammatical copula"},
        {"id": "temporal-ambiguous-spring", "text": "Alice stood before the spring.", "expected": "retain unresolved temporal/spatial alternatives"},
        {"id": "temporal-ambiguous-period", "text": "Alice stood before the period.", "expected": "retain unresolved temporal/spatial alternatives"},
    ]
    manifest = {
        "format": "GSE.eight-operation-manifest/1", "role_scope": ROLE,
        "created_utc": datetime.now(timezone.utc).isoformat(), "candidate": str(args.lexicon),
        "sha256": before, "source_freeze": str(freeze), "source_freeze_sha256": sha(freeze),
        "scope": "DEVELOPMENT_INTEGRATED_ACCEPTANCE; no untouched final claim for these inspected families",
        "sentence_cases": sentence_cases,
        "operation_expectations": {
            "lexical": "Exact source identity, signed/zero/unknown distinction, ambiguity retained, no merged sense signature",
            "sentence": "All retained development cases, full production composition, source identity and scope at correct scale",
            "queries": "Axis, swap versus equality, entities, proposition commitment/polarity and safe exact key refusal",
            "document": "One intake, cross-paragraph pronoun support, source lineage, actual cassette results, no invented world answers",
            "inference": "Source-cited type and conditional chains; reverse, other agent, negated/modal/reported exclusions",
            "profile": "Actual structural counts; positive and negative evaluation measured, unsupported quantity not evaluation; unknown explicit",
            "decoder_pipeline": "Same encoder trace/vector; immutable exact IDs, numeric neighbor search not identity selection",
            "integration": "Actual spellcheck on same store; existing inference/emission for Regenesis; SparseWiki resource availability honest",
        },
        "independent_source_warrants": [
            "docs/program/LEXICON_CONSTRUCTION_DESIGN.md word/sentence and checkpoint contracts",
            "WordNet exact leap.n.01 movement / whisper.n.01 speaking / femur.n.01 anatomical part / teacher.n.01 person glosses",
            "Primary NSM chart own-coordinate GOOD/BAD polarity, not full signatures or finer WordNet alignment",
            "English construction and grammatical scope witnesses predeclared in complete-operation-cases-v1.json; no construction requests generated here",
        ],
    }
    manifest_path = D / f"ssl-api-runtime-eight-operation-manifest-{args.tag}.json"
    if manifest_path.exists() and not args.resume:
        raise FileExistsError(manifest_path)
    if not args.resume:
        write(manifest_path, manifest)
    else:
        manifest = json.loads(manifest_path.read_text())
        assert manifest["sha256"] == before
    report = {"format": "GSE.eight-operation-outcomes/1", "role_scope": ROLE,
              "candidate": str(args.lexicon), "sha256": before, "manifest": str(manifest_path),
              "manifest_sha256": sha(manifest_path), "scope": manifest["scope"], "operations": {}, "checks": []}
    output = D / f"ssl-api-runtime-eight-operation-outcomes-{args.tag}.json"
    if args.resume:
        report = json.loads(output.read_text())
        report.setdefault("harness_attempts", []).append({"at_utc": datetime.now(timezone.utc).isoformat(),
            "failed_checks": [c for c in report["checks"] if c["id"].endswith("-execution")],
            "reason": "Correct TokenTrace sent_primitives field and ndarray serialization; completed consumer operations reused, not rerun"})
        report["checks"] = [c for c in report["checks"] if not c["id"].endswith("-execution")]

    def check(op, ident, expected, actual, passed, cause=None):
        row = {"operation": op, "id": ident, "required": expected, "actual": plain(actual), "passed": bool(passed)}
        if cause:
            row["cause_if_failed"] = cause
        report["checks"].append(row)

    def run(op, fn):
        if args.resume and op in report["operations"] and not (isinstance(report["operations"][op], dict) and "error" in report["operations"][op]):
            return
        try:
            report["operations"][op] = fn()
        except Exception as exc:
            report["operations"][op] = {"error": type(exc).__name__, "detail": str(exc)}
            check(op, op + "-execution", "operation executes through real production seam", str(exc), False, "consumer or audit harness; classify before repair")
        finally:
            write(output, report)

    with GSEEncoder(args.lexicon) as enc:
        enc.conn.execute("PRAGMA query_only=ON")
        cache = {}

        def composed(text):
            if text not in cache:
                trace = enc.encode(text)
                tree = evaluate_tree(resolve(from_trace(trace)))
                cache[text] = (trace, tree, emit_contract(tree, include_semantics=True, source_text=text))
            return cache[text]

        def lexical():
            cases = [("wordnet:leap:leap.n.01", "HAPPEN", 1), ("wordnet:whisper:whisper.n.01", "SAY", 1),
                     ("wordnet:femur:femur.n.01", "BODY", 1), ("wordnet:teacher:teacher.n.01", "SOMEONE", 1),
                     ("wordnet:water:water.n.01", "I", 0), ("nsm_chart:v20:good", "GOOD", 1),
                     ("nsm_chart:v20:bad", "GOOD", -1)]
            out = []
            for eid, bank, value in cases:
                result = enc.lookup_definition(eid)
                selected = result.get("selected") or {}
                row = {"entry_id": eid, "code": result["code"], "gloss": selected.get("gloss"),
                       "assignments": selected.get("assignments"), "hierarchy": selected.get("hierarchy"),
                       "domains": selected.get("domains"), "trace_sha256": hashlib.sha256(json.dumps(selected.get("trace"), sort_keys=True).encode()).hexdigest()}
                out.append(row)
                check("lexical", eid + ":" + bank, {"bank": bank, "value": value, "exact_identity": eid},
                      {"code": result["code"], "domain": selected.get("domains", {}).get(bank)},
                      result["code"] == "IDENTIFIED" and selected.get("domains", {}).get(bank) == [value], "source bank or exact identity")
            for lemma in ["good", "he", "have", "bank"]:
                result = enc.lexical_lookup(lemma)
                row = {k: result.get(k) for k in ["selection_status", "candidate_entry_ids", "primitives", "selected_record"]}
                row.pop("selected_record")
                out.append({"lemma": lemma, **row})
                check("lexical", "ambiguity-" + lemma, "competing exact definitions retained; no first-sense selection", row,
                      result.get("selection_status") == "AMBIGUOUS" and not result.get("primitives"), "identity eligibility")
            water = enc.lookup_definition("wordnet:water:water.n.01")["selected"]
            check("lexical", "unknown-not-zero", "water KNOW remains unknown, not zero or negative", water["domains"]["KNOW"], water["domains"]["KNOW"] == [-1, 0, 1])
            return out

        run("lexical", lexical)

        def sentences():
            out = []
            for case in sentence_cases:
                text = case["text"]
                trace, tree, contract = composed(text)
                tokens = [{"token": t.token, "lemma": t.lemma, "pos": t.pos,
                           "word": t.word_primitives, "sentence": t.sent_primitives} for t in trace.tokens]
                out.append({**case, "contract": contract, "tree": repr(tree), "tokens": tokens})
                check("sentence", case["id"] + "-read", "nonempty composed predicate", contract.get("predicate"), bool(contract.get("predicate")), "composed construction")
                if case["id"] in ["aux-have-possession-leak", "aux-be-state-leak", "copula-be-state-leak", "inverted-do", "do-aux", "have-aux"]:
                    leaks = [{"token": t["token"], "word": t["word"]} for t in tokens if t["pos"] == "AUX" and any(t["word"].get(k) for k in ["HAVE", "BE", "DO", "HAPPEN"])]
                    check("sentence", case["id"] + "-own-content", "no unsupported own lexical HAVE/BE/DO/HAPPEN on grammatical auxiliary", leaks, not leaks, "source projection; controller migration/replay required")
                if case["id"] in ["he-symbol", "he-chemical-copula"]:
                    he = next(t for t in trace.tokens if t.token == "He")
                    selected = enc.contextual_grounding(he, trace.tokens) if hasattr(enc, "contextual_grounding") else None
                    check("sentence", case["id"] + "-role", "chemical He is nominal, not pronoun", {"pos": he.pos, "word": he.word_primitives, "context": selected}, he.pos == "NOUN" and not he.word_primitives.get("SOMEONE"), "native contextual identity")
                if case["id"] == "he-generic":
                    he = next(t for t in tokens if t["token"] == "He")
                    check("sentence", "he-generic-pronoun", "broad ancestor includes person; preserve pronoun", he, he["pos"] == "PRON" and he["word"].get("SOMEONE") == 1)
                if case["id"] in ["do-main", "imperative-main-do", "imperative-pronoun-do", "inverted-do", "inverted-pronoun-do", "topic-about", "see-qualified", "hear-qualified"]:
                    verb = {"do-main": "do", "imperative-main-do": "do", "imperative-pronoun-do": "do", "inverted-do": "repair", "inverted-pronoun-do": "work", "topic-about": "think", "see-qualified": "see", "hear-qualified": "hear"}[case["id"]]
                    events = [x for x in objects(contract) if x.get("op") == "EVENT"]
                    check("sentence", case["id"] + "-matrix", "matrix event " + verb, events,
                          bool(events) and events[0].get("features", {}).get("verb") == verb, "composed matrix/role construction")
            return out

        run("sentence", sentences)

        def query_op():
            text = "The tower is bigger than the cottage."
            _, first, _ = composed(text)
            _, swapped, _ = composed("The cottage is bigger than the tower.")
            result = {"entities": queries.entity_lemmas(first), "axis": queries.axis_of_comparison(first),
                      "swap": queries.is_argument_swap_of(first, swapped),
                      "self_equal": queries.is_logically_equal_to(first, first),
                      "swapped_equal": queries.is_logically_equal_to(first, swapped),
                      "clauses": [type(p).__name__ for p in queries.clauses(first)]}
            check("queries", "comparison", "axis big, swap true, self equal true, swapped equal false", result,
                  result["axis"] == "big" and result["swap"] and result["self_equal"] and not result["swapped_equal"])
            claims = []
            for text in ["Nora believes that the gate is open.", "Nora knows that the gate is open.",
                         "Nora does not know that the gate is open.", "Nora can open the gate.",
                         "Nora did not open the gate.", "Nora opened the gate."]:
                _, tree, _ = composed(text)
                rows = [{"kind": p.kind, "commitment": commitment(p), "polarity": plain(polarity(p)),
                         "claim_key": plain(claim_key(p))} for p in propositions(tree, source_text=text)]
                claims.append({"text": text, "propositions": rows})
            check("queries", "exact-key-does-not-invent-relation-identity", "ambiguous event key refuses unsupported relation identity",
                  claims[-1], all(r["claim_key"]["state"] != "keyed" for r in claims[-1]["propositions"]), "identity or relation scope")
            return {"comparison": result, "claims": claims}

        run("queries", query_op)

        def document():
            text = 'A woman entered the room.\n\nShe opened the window. Nora said, "I waited here."'
            doc = MultiScaleDoc(text, encoder=enc, store=NullGenealogy())
            second = doc.unit_view(paragraph_id=doc.source_sentences[1].paragraph_id)
            identity = list(EntityIdentity().run(doc))
            deck = CassetteDeck([EntityIdentity()]).resolve(doc)
            out = {"text": text, "phases": doc.phases, "source_sentences": plain(doc.source_sentences),
                   "tree_sources": doc.tree_sources, "mentions": plain(doc.mentions),
                   "supporting_mentions": plain(second["supporting_mentions"]),
                   "contracts": [emit_contract(t) for t in doc.resolved], "failures": plain(doc.failures),
                   "cassette_proposals": plain(identity), "deck_merges": plain(deck.merges),
                   "deck_abstained": plain(deck.abstained)}
            check("document", "one-document-read", "all source sentences retained with read intake/fold/graph", out["phases"],
                  not doc.failures and len(doc.tree_sources) >= len(doc.source_sentences), "intake or document composition")
            check("document", "cross-paragraph-support", "second paragraph retains earlier woman support for she", out["supporting_mentions"],
                  bool(out["supporting_mentions"]), "reference resolution")
            check("document", "no-ungrounded-cassette-merge", "no identity merge without sufficient independent strands", out["deck_merges"], not deck.merges, "cassette eligibility")
            return out

        run("document", document)

        def inference():
            texts = ["All sparrows are birds.", "All birds are animals.", "Lina is a sparrow."]
            trees = [composed(t)[1] for t in texts]
            kb = KnowledgeBase.from_trees(trees, source_texts=texts, source_ids=["type-1", "type-2", "type-3"])
            yes, no = kb.is_a("lina", "animal"), kb.is_a("animal", "lina")
            check("inference", "type-source-chain", "Lina animal entailed with source chain; reverse not entailed", {"positive": yes, "negative": no}, yes.holds and not no.holds and bool(yes.source_ids))
            texts = ["Lina is a member.", "Omar is a member.",
                     "If a member misses the payment then the member loses the vote.",
                     "If a member loses the vote then the member leaves the board.",
                     "Lina missed the payment.", "Ruth did not miss the payment.",
                     "Omar can miss the payment.", "Nora says that Ruth missed the payment."]
            kb = KnowledgeBase.from_trees([composed(t)[1] for t in texts], source_texts=texts,
                                         source_ids=["premise-" + str(i) for i in range(len(texts))])
            derivations = {name: plain(kb.event("leave", name, "board")) for name in ["lina", "omar", "ruth"]}
            check("inference", "conditional-source-chain", "Lina leaves board via two cited rules", derivations["lina"], derivations["lina"]["holds"] and len(derivations["lina"]["source_ids"]) >= 3)
            check("inference", "conditional-must-not", "other agent, modal and reported/negative premises do not entail departure", derivations,
                  not derivations["omar"]["holds"] and not derivations["ruth"]["holds"])
            return {"type": {"positive": plain(yes), "reverse": plain(no)}, "conditional": derivations,
                    "admissions": plain(kb.admissions)}

        run("inference", inference)

        def profile():
            out = []
            for ident, text, expected in [
                ("dev-good", "Kindness is morally good.", "positive"),
                ("dev-bad", "Cruelty is morally bad.", "negative"),
                ("quantity-good-negative", "It was a good forty miles.", "not-positive"),
                ("structural-profile", "Lina wants to rest. She does not want to run.", "structural"),
            ]:
                result = text_profile(enc, text).to_dict()
                out.append({"id": ident, "text": text, "profile": result})
                val = result["affect"].get("valence_mean")
                if expected in ["positive", "negative"]:
                    passed = val is not None and (val > 0 if expected == "positive" else val < 0)
                    check("profile", ident, "source-warranted " + expected + " evaluative measurement, not unavailable", result["affect"], passed, "contextual evaluative identity/source access")
                elif expected == "not-positive":
                    check("profile", ident, "quantity/intensity good must not assert positive evaluation", result["affect"], val is None or val <= 0)
                else:
                    check("profile", ident, "both utterances read with actual operation counts", {k: result.get(k) for k in ["state", "n_read", "operations", "failures"]}, result["n_read"] == 2 and bool(result["operations"]) and not result["failures"])
            return out

        run("profile", profile)

        def pipeline():
            pipeline = GSEPipeline(str(args.lexicon))
            try:
                text = "I think about the door."
                trace = enc.encode(text)
                result = pipeline.encode_sentence(text, with_trace=True)
                same_trace = result.trace.to_dict() == trace.to_dict()
                same_vector = np.array_equal(result.vector, trace.vector.to_dense())
                check("decoder_pipeline", "same-production-encoder", "public pipeline uses same trace and vector", {"same_trace": same_trace, "same_vector": same_vector}, same_trace and same_vector)
                exact = pipeline.decompose_word("good", "ADJ", entry_id="nsm_chart:v20:good")
                unknown = pipeline.decompose_word("unattested-checkpoint-spelling", "NOUN")
                matches = pipeline.find_similar(exact.vector, top_k=3)
                check("decoder_pipeline", "unknown-not-fabricated", "unknown word has None vector, not filled geometry", {"source": unknown.source, "vector_is_none": unknown.vector is None}, unknown.vector is None)
                check("decoder_pipeline", "numeric-neighbors-not-identities", "numeric lexeme IDs; similarity not sense selection", {"matches": matches.matches, "route_info": matches.route_info}, bool(matches.matches) and not matches.route_info["identity_selection"] and all(i.isdigit() for i, _ in matches.matches))
                return {"same_trace": same_trace, "same_vector": same_vector, "matches": plain(matches),
                        "statistics": pipeline.get_statistics(), "integrity": pipeline.verify_integrity()}
            finally:
                pipeline.close()

        run("decoder_pipeline", pipeline)

        def integration():
            lexicon = _Lexicon(args.lexicon)
            try:
                results = {word: plain(correct(word, lexicon=lexicon)) for word in ["bicycle", "bycicle", "ZXQ9"]}
                check("integration", "spellcheck-grounded", "valid ordinary word unchanged", results["bicycle"], results["bicycle"]["committed"] == "bicycle" and not results["bicycle"]["fired"])
                check("integration", "spellcheck-noisy-channel", "simple spelling error offers grounded bicycle", results["bycicle"], any(c["word"] == "bicycle" for c in results["bycicle"]["ranked"]))
                check("integration", "spellcheck-code-must-not", "unknown code not auto-corrected", results["ZXQ9"], results["ZXQ9"]["committed"] is None)
                resources = {"SparseWiki_genealogy": {"path": "data/genealogy.db", "available": Path("data/genealogy.db").exists(),
                              "scope": "Orthogonal world resource; no world-grounding certificate when absent"},
                             "Regenesis": {"consumer_seam": "emit_contract + KnowledgeBase source-chain operations measured above", "separate_runtime_created": False}}
                return {"spellcheck": results, "resources": resources}
            finally:
                if lexicon._conn is not None:
                    lexicon._conn.close()

        run("integration", integration)

    report["sha256_after"] = sha(args.lexicon)
    report["source_pins_unchanged"] = all(sha(ROOT / path) == digest for path, digest in pins.items())
    report["lexicon_unchanged"] = report["sha256_after"] == before
    report["seconds"] = time.monotonic() - start
    for op in manifest["operation_expectations"]:
        checks = [c for c in report["checks"] if c["operation"] == op]
        report.setdefault("summary", {})[op] = {"checks": len(checks), "passed": sum(c["passed"] for c in checks),
                                               "failed_ids": [c["id"] for c in checks if not c["passed"]]}
    report["all_checks_passed"] = bool(report["checks"]) and all(c["passed"] for c in report["checks"])
    report["checkpoint_complete"] = False
    report["not_completion_reason"] = "Development integrated audit; final lineage-separated slice, final candidate replay/CI/publication remain separate obligations."
    write(output, report)
    print(json.dumps({"output": str(output), "sha256": before, "summary": report["summary"], "lexicon_unchanged": report["lexicon_unchanged"], "source_pins_unchanged": report["source_pins_unchanged"], "seconds": report["seconds"]}, indent=2))


if __name__ == "__main__":
    main()
