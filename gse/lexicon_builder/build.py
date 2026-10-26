"""Source records → symbolic closure → bounded local selection → closure.

Lexical projections are explicit rulebook entries. Candidate template closure
is recorded separately from source/rule-certified cells and cannot be exported
as an audited production lexicon.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterator
from functools import partial
from pathlib import Path

from gse.lexicon_builder.artifact import export_sparse, export_vector
from gse.lexicon_builder.basis import BASIS_ID
from gse.lexicon_builder.conditionals import ConditionalCatalog, catalog_report, evaluate_catalog, load_catalog
from gse.lexicon_builder.core import (
    CANONICAL_COORDINATES,
    Observation,
    Resolution,
    RuleException,
    coordinate_vocabulary,
    legal_domain,
)
from gse.lexicon_builder.families import account_family, family_laws
from gse.lexicon_builder.fill import USAS_TAGSET, fill_payload, usas_labels, usas_type
from gse.lexicon_builder.foundation import FOUNDATION, foundation_readings, load_foundation, structural_entries
from gse.lexicon_builder.model import DEFAULT_MODEL, OllamaSelector
from gse.lexicon_builder.native_constraints import native_readings, withheld_frame_writes
from gse.lexicon_builder.nouns import noun_readings
from gse.lexicon_builder.reading import (
    Construction,
    CoordinateDecision,
    ReadingSeed,
    ReviewContract,
    construct_reading,
    restriction,
)
from gse.lexicon_builder.registry import (
    RULE_FAMILIES,
    RULEBOOK,
    admission_report,
    export_candidates,
    load_rulebook,
    split_by_admission,
)
from gse.lexicon_builder.sources import NativeSources, sha256, word_key
from gse.lexicon_builder.tail import BudgetedSelector, attach_tail, nominated_components, tail_ledger, tail_task_status


def source_matches(native: dict, rulebook: dict) -> list[dict]:
    """Typed POS/category/frame conjunction; preserve every native alternative."""
    matches: list[dict] = []
    for record in native["usas"]["records"]:
        row = record["values"]
        for alternative in row["alternatives"]:
            # A slash is joint membership: an unhandled second component cannot
            # be discarded to manufacture a complete simple template.
            for rule in rulebook["source_rules"]:
                if row["pos"] not in rule["pos"] or "/" in alternative:
                    continue
                tag = next(
                    (
                        found
                        for category in rule.get("categories") or [rule["category"]]
                        if (found := re.fullmatch(re.escape(category) + r"([+]+|[-]+)", alternative))
                    ),
                    None,
                )
                if tag is None or tag[1][0] not in rule.get("signs", "+-"):
                    continue
                frames = [
                    r
                    for r in native["framenet"]["records"]
                    if r["values"]["pos"] == {"ADJ": "a", "NOUN": "n", "VERB": "v"}.get(row["pos"])
                    and r["values"]["frame"] in rule["frames"]
                ]
                if not frames:
                    continue
                matches.append(
                    {
                        "rule": rule,
                        "pos": row["pos"],
                        "tag": alternative,
                        "pole": "+1" if tag[1][0] == "+" else "-1",
                        "native_degree_rank": len(tag[1]),
                        "premises": [record["record_id"]] + [r["record_id"] for r in frames],
                        "frames": [r["values"] for r in frames],
                    }
                )
    unique = {}
    for match in matches:
        identity = (match["rule"]["rule_id"], match["pos"], match["tag"], tuple(sorted(match["premises"])))
        unique.setdefault(identity, match)
    multiplicity = Counter((m["pos"], m["tag"], m["rule"]["family"]) for m in unique.values())
    for identity, match in unique.items():
        if multiplicity[match["pos"], match["tag"], match["rule"]["family"]] > 1:
            match["reading_suffix"] = ":source-" + hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:16]
    return list(unique.values())


def _payload(word: str, reading_id: str, match: dict, native: dict, state: Resolution) -> dict:
    # Word-level associations stay explicitly scoped; FN alternatives not
    # selected by the typed join are preserved in the artifact, not asserted
    # as properties of this reading in a model request.
    return {
        "schema": "GSE_RESIDUAL_V1",
        "projection_scope": match["rule"].get("fill_scope", "TARGET_READING_OWN_DEFINITION"),
        "word": word,
        "reading_id": reading_id,
        "selected_native_types": {"pos": match["pos"], "usas_tag": match["tag"], "frames": match["frames"]},
        "native_word_observations": {s: native[s] for s in ("concreteness", "lancaster", "vad", "emotion")},
        "fixed_coordinates": {c: v.value for c, v in state.forced().items()},
        "residual_domains": {
            c: [s.value for s in state.domains[c]]
            for c in nominated_components(match["rule"])
            if len(state.domains[c]) > 1
        },
        "residual_warrants": match["rule"].get("residual_warrants", {}),
        "coordinate_vocabulary": {c: coordinate_vocabulary(c) for c in nominated_components(match["rule"])},
        "degree_contract": {
            "coordinate": "INTENSITY",
            "present": "DEFINITION_CONTAINS_DEGREE_BEARING_CONTENT",
            "relative_strength": "SEPARATE_NUMBER_OPERATOR_PRESERVING_SIGNS_AND_MASKS",
            "native_degree_rank": match["native_degree_rank"],
            "rating_limit": "ASSOCIATION_VALENCE_AND_AROUSAL_DO_NOT_ESTABLISH_LEXICAL_SCALE",
        },
        "operation": "FILL_ONLY_REMAINING_TYPED_FIELDS",
    }


def _adjective_record(word: str, reading_id: str, match: dict, c: Construction) -> dict:
    rule = match["rule"]
    return {
        "word": word,
        "reading_id": reading_id,
        "code": "SOURCE_CONFLICT"
        if c.definition_accounting.get("code") == "FAMILY_CONTRADICTED"
        else "CONFLICT"
        if c.state.code == "CONFLICT"
        else "CANDIDATE_COMPLETE"
        if c.candidate
        else "PARTIAL",
        "production_eligible": False,
        "rule_id": rule["rule_id"],
        "rule_review_state": rule["review_state"],
        "premise_record_ids": match["premises"],
        "symbolic_before": c.initial.to_json(),
        "after_selection": c.state.to_json(),
        "after_closure": c.closed.to_json() if c.closed is not None else None,
        "decisions": c.decisions,
        "model_calls": c.calls,
        "omission_challenge": c.coverage,
        "coverage_review": {k: c.review[k] for k in ("code", "rounds", "missing")},
        "coverage_gap": rule.get("coverage_gap"),
        "candidate_vector": c.candidate,
        "provisional_vector": c.proposal,
        "provisional_closure": c.proposed_closure.to_json() if c.proposed_closure is not None else None,
        "completion_status": "CONSTRAINT_RESOLVED" if c.candidate else "UNPROVEN_COVERAGE",
        "definition_accounting": c.definition_accounting,
        "relations": rule.get("relations", []),
        "residual_coordinates": nominated_components(rule),
        "number_scale": {
            "family": rule["family"] + ":" + match["pole"],
            "native_ordinal_rank": match["native_degree_rank"],
            "coordinates": [rule["coordinate"]],
            "numeric_gain": None,
            "status": "NATIVE_TAG_ORDER_ONLY; NOT_CROSS_WORD_CALIBRATED",
        },
    }


def adjective_seed(word: str, match: dict, native: dict, fill_labels: dict[str, str] | None = None) -> ReadingSeed:
    """An adjectival source-rule match as a reading seed for the shared constructor.

    With fill_labels (the USAS tag list, possibly empty), every cell the rules leave open is filled by bank.
    """
    rule = match["rule"]
    reading_id = f"{word}:{match['pos']}:{match['tag']}:{rule['family']}" + match.get("reading_suffix", "")
    observations = tuple(
        Observation(reading_id, "native_source_join", "+".join(match["premises"]), field, value, True)
        for field, value in [
            ("own_role", rule.get("own_role", "modifier_property_only")),
            *rule.get("reading_facts", []),
        ]
    )
    laws = [
        restriction(
            rule["rule_id"], rule["coordinate"], [match["pole"]], rule["warrant"], rule.get("tier", "CONDITIONAL")
        )
    ]
    for coordinate, value in rule["companions"].items():
        laws.append(
            restriction(
                rule["rule_id"] + ":" + coordinate,
                coordinate,
                [value],
                rule["warrant"],
                rule.get("tier", "CONDITIONAL"),
            )
        )
    for coordinate in nominated_components(rule):
        laws.append(
            restriction(
                rule["rule_id"] + ":DOMAIN:" + coordinate,
                coordinate,
                rule.get("residual_domains", {}).get(coordinate, sorted(v.value for v in legal_domain(coordinate))),
                "Scoped template: optional own component; no written middle without a contract",
            )
        )
    laws.extend(family_laws(rule))
    payload = partial(_payload, word, reading_id, match, native)
    return ReadingSeed(
        word=word,
        reading_id=reading_id,
        observations=observations,
        laws=laws,
        layout=partial(_adjective_record, word, reading_id, match),
        decisions=[]
        if fill_labels is not None
        else [CoordinateDecision(coordinate, payload, allow_abstain=True) for coordinate in nominated_components(rule)],
        review=None
        if rule["coverage"] is None
        else ReviewContract(payload, rule.get("completion_domains", {}), rule["coverage"]),
        fill=None
        if fill_labels is None
        else partial(
            fill_payload,
            word,
            match["pos"],
            rule.get("fill_scope", "OWN_DEFINITION"),
            {
                "usas": usas_type(match["tag"], fill_labels),
                "framenet_frames": sorted({f["frame"] for f in match["frames"]}),
            },
        ),
        context={
            "selected_types": {"pos": match["pos"], "usas_tag": match["tag"], "frames": match["frames"]},
            "word_observations": {s: native[s] for s in ("concreteness", "lancaster", "vad", "emotion") if s in native},
            "projection_scope": rule.get("fill_scope", "TARGET_READING_OWN_DEFINITION"),
        },
        completion_check=partial(account_family, rule),
    )


def construct(
    word: str,
    match: dict,
    native: dict,
    rulebook: dict,
    selector: OllamaSelector | None,
    bank_review: bool = False,
    fill_labels: dict[str, str] | None = None,
    tail_tasks: list[dict] | None = None,
    exceptions: tuple[RuleException, ...] = (),
) -> dict:
    seed = adjective_seed(word, match, native, fill_labels)
    seed.exceptions = exceptions
    if tail_tasks is not None:
        seed = attach_tail(seed, tail_tasks)
    return construct_reading(seed, rulebook, selector, bank_review)


def _head_record(word: str, reading_id: str, premises: list[str], c: Construction) -> dict:
    return {
        "word": word,
        "reading_id": reading_id,
        "code": c.state.code,
        "source_scope": "LEMMA_POS_HEAD_CONTRACT",
        "production_eligible": False,
        "premise_record_ids": premises,
        "symbolic_before": c.initial.to_json(),
        "after_selection": c.state.to_json(),
        "model_calls": c.calls,
        "decisions": c.decisions,
        "candidate_vector": None,
    }


def head_readings(
    word: str,
    native: dict,
    rulebook: dict,
    covered_pos: set[str],
    selector=None,
    tail_tasks: list[dict] | None = None,
    exceptions: tuple = (),
) -> list[dict]:
    """POS can establish the head contract without inventing semantic components."""
    results = []
    for pos, role in (
        ("ADJ", "modifier_property_only"),
        ("VERB", "lexical_predicate"),
        ("NOUN", "unresolved_substantive_head"),
        ("ADV", "unresolved_adverbial_head"),
    ):
        bindings = [("usas", r["record_id"]) for r in native["usas"]["records"] if r["values"]["pos"] == pos]
        bindings.extend(
            ("framenet", r["record_id"])
            for r in native.get("framenet", {}).get("records", [])
            if r["values"]["pos"] == {"ADJ": "a", "VERB": "v", "NOUN": "n", "ADV": "adv"}[pos]
        )
        premises = [record_id for _, record_id in bindings]
        if not premises or pos in covered_pos:
            continue
        reading_id = f"{word}:{pos}:unresolved-native-reading"
        seed = ReadingSeed(
            word,
            reading_id,
            tuple(Observation(reading_id, source, record_id, "own_role", role, True) for source, record_id in bindings),
            [],
            partial(_head_record, word, reading_id, premises),
            exportable=False,
            exceptions=exceptions,
            context={
                s: native[s] for s in ("usas", "framenet", "concreteness", "lancaster", "vad", "emotion") if s in native
            },
        )
        if tail_tasks is not None:
            seed = attach_tail(seed, tail_tasks)
        results.append(construct_reading(seed, rulebook, selector))
    return results


def withheld_source_writes(word: str, matches: list[dict]) -> list[dict]:
    """What unadmitted adjective source rules would write and assert; recorded, never applied."""
    return [
        {
            "family": "source_rules",
            "reading_id": f"{word}:{m['pos']}:{m['tag']}:{m['rule']['family']}" + m.get("reading_suffix", ""),
            "rule_ids": [m["rule"]["rule_id"]],
            "review_states": [m["rule"]["review_state"]],
            "premise_record_ids": m["premises"],
            "would_write": {m["rule"]["coordinate"]: m["pole"], **m["rule"]["companions"]},
            "would_assert": [["own_role", "modifier_property_only"], *m["rule"].get("reading_facts", [])],
        }
        for m in matches
    ]


def build(
    words: list[str],
    sources: NativeSources,
    rulebook: dict,
    selector: OllamaSelector | None,
    bank_review: bool = False,
    fill: bool = False,
    tail_tasks: list[dict] | None = None,
    exceptions: tuple[RuleException, ...] = (),
    include_foundation: bool = True,
    conditional_catalog: ConditionalCatalog | None = None,
) -> Iterator[dict]:
    # F129: only admitted rules construct. An unadmitted rule writes no cell, asserts no
    # fact that an admitted law could consume, and asks no model question.
    admitted, withheld = split_by_admission(rulebook)
    labels = usas_labels() if fill else None
    foundation = load_foundation() if include_foundation else None
    for raw_word in words:
        word = word_key(raw_word)
        native = sources.for_word(word)
        matches = source_matches(native, admitted)
        withheld_matches = source_matches(native, withheld)
        readings = [
            construct(word, m, native, admitted, selector, bank_review, labels, tail_tasks, exceptions) for m in matches
        ]
        readings.extend(native_readings(word, native, admitted, selector, tail_tasks, exceptions))
        readings.extend(noun_readings(word, native, admitted, selector, tail_tasks, exceptions))
        readings.extend(
            head_readings(
                word,
                native,
                admitted,
                {m["pos"] for m in matches}
                | ({"VERB"} if any(r.get("source_scope") == "NATIVE_CLASS_FRAME" for r in readings) else set())
                | ({"NOUN"} if any(r.get("source_scope") == "FRAMENET_NOUN_TARGET" for r in readings) else set()),
                selector,
                tail_tasks,
                exceptions,
            )
        )
        homes = structural_entries(word, foundation) if foundation is not None else []
        if foundation is not None:
            readings.extend(foundation_readings(word, admitted, foundation))
        withheld_writes = withheld_source_writes(word, withheld_matches) + withheld_frame_writes(word, native, withheld)
        diagnostic = evaluate_catalog(native, conditional_catalog) if conditional_catalog is not None else None
        if diagnostic is not None:
            # All dispositions are counted. Only met premises need repeated
            # word-level evidence; catalog and native records reproduce the rest.
            diagnostic["results"] = [
                r
                for r in diagnostic["results"]
                if r["code"] in {"CORROBORATED_NATIVE_ASSOCIATION", "CONTRADICTED_NATIVE_ASSOCIATION"}
                or r.get("blocked_role") == "CONSEQUENT"
            ]
            diagnostic["result_policy"] = "MET_PREMISES; ALL_OUTCOMES_COUNTED; RECOMPUTABLE_FROM_PINNED_INPUTS"
        yield {
            "word": word,
            "native": native,
            "readings": readings,
            "structural_entries": homes,
            "code": "CONSTRUCTED_READINGS"
            if readings
            else "STRUCTURAL_ENTRIES"
            if homes
            else "PARTIAL_UNADMITTED_RULES_ONLY"
            if withheld_writes
            else "PARTIAL_NO_APPLICABLE_RULE",
            "unhandled_native_alternatives": [
                {"record_id": r["record_id"], "pos": r["values"]["pos"], "tag": tag}
                for r in native["usas"]["records"]
                for tag in r["values"]["alternatives"]
                if not any(m["pos"] == r["values"]["pos"] and m["tag"] == tag for m in matches + withheld_matches)
            ],
            "withheld_unadmitted_writes": withheld_writes,
            "conditional_diagnostics": diagnostic,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "rules"))
    parser.add_argument("--words", nargs="+")
    parser.add_argument("--word-file", type=Path)
    parser.add_argument(
        "--all-source-words", action="store_true", help="union of available native word lists plus foundation surfaces"
    )
    parser.add_argument("--sources", type=Path, default=Path("data/external"))
    parser.add_argument("--nltk", type=Path, default=Path.home() / "nltk_data/corpora")
    parser.add_argument("--rulebook", type=Path, default=RULEBOOK)
    parser.add_argument(
        "--coherence", type=Path, default=Path("docs/verification/lexicon-rebuild/coherence-2026-10-24/results.json")
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--symbolic-only", action="store_true")
    parser.add_argument("--tail-queue", type=Path, help="explicit diagnosed typed tasks; the only CLI route to a model")
    parser.add_argument("--model-budget", type=int, default=64, help="maximum attempted tail calls in this run")
    parser.add_argument("--exceptions", type=Path, help="independent local exception records for conditional rules")
    parser.add_argument(
        "--conditional-catalog",
        type=Path,
        help="optional native-association diagnostic catalog; writes no lexical cells",
    )
    parser.add_argument("--bank-review", action="store_true", help="run the diagnostic per-bank omission review")
    parser.add_argument(
        "--no-fill", action="store_true", help="compatibility flag; ordinary builds are always symbolic"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "rules":
        print(json.dumps(export_candidates(args.coherence, args.output), indent=2))
        return 0
    if sum(bool(v) for v in (args.words, args.word_file, args.all_source_words)) != 1:
        parser.error("build requires exactly one of --words, --word-file or --all-source-words")
    words = args.words or (args.word_file.read_text().splitlines() if args.word_file else None)
    if words is not None and (not words or any(not isinstance(w, str) or not word_key(w) for w in words)):
        parser.error("EMPTY_WORKLIST: words must be nonempty strings")
    tasks = json.loads(args.tail_queue.read_text()) if args.tail_queue else []
    if not isinstance(tasks, list) or any(tail_task_status(t) != "VALID_TAIL_TASK" for t in tasks):
        parser.error("INVALID_TAIL_QUEUE")
    if len({(t["reading_id"], t["coordinate"]) for t in tasks}) != len(tasks):
        parser.error("DUPLICATE_TAIL_TASK")
    if args.model_budget < 0:
        parser.error("INVALID_MODEL_BUDGET")
    if args.symbolic_only and tasks:
        parser.error("SYMBOLIC_ONLY_REFUSES_MODEL_TASKS")
    exceptions = tuple(RuleException(**e) for e in json.loads(args.exceptions.read_text())) if args.exceptions else ()
    args.output.mkdir(parents=True, exist_ok=True)
    rulebook = load_rulebook(args.rulebook)
    catalog = load_catalog(args.conditional_catalog) if args.conditional_catalog else None
    sources = NativeSources(words, args.sources, args.nltk)
    if words is None:
        foundation = load_foundation()
        words = sorted(
            sources.words
            | {w for p in foundation["profiles"] + foundation["structural_entries"] for w in p["surfaces"]}
        )
    selector = BudgetedSelector(OllamaSelector(args.model), args.model_budget) if tasks else None
    manifest = {
        "schema_version": 1,
        "basis_id": BASIS_ID,
        "coordinate_order": CANONICAL_COORDINATES,
        "rulebook": str(args.rulebook),
        "rulebook_sha256": sha256(args.rulebook),
        "sources": sources.manifest,
        "words": words,
        "worklist_policy": "AVAILABLE_NATIVE_UNION_AND_FOUNDATION" if args.all_source_words else "EXPLICIT_SURFACES",
        "foundation_sha256": sha256(FOUNDATION),
        "tail_queue_sha256": sha256(args.tail_queue) if args.tail_queue else None,
        "model_budget": args.model_budget if tasks else 0,
        "exceptions_sha256": sha256(args.exceptions) if args.exceptions else None,
        "conditional_catalog": catalog_report(catalog, rulebook) if catalog is not None else None,
        "rule_admission": admission_report(rulebook),
        "model": {"requested": args.model, "identity": "RECORDED_PER_ACTUAL_CALL"} if selector else None,
        "bank_review": args.bank_review,
        "fill": False,
        "usas_tagset_sha256": sha256(USAS_TAGSET) if USAS_TAGSET.exists() else None,
        "admission": {
            "policy": "Source-justified executable rules and recorded legacy approvals; no automatic lexical promotion from association scores",
            "admitted": {f: [r["rule_id"] for r in split_by_admission(rulebook)[0][f]] for f in RULE_FAMILIES},
            "withheld": {f: [r["rule_id"] for r in split_by_admission(rulebook)[1][f]] for f in RULE_FAMILIES},
        },
        "implementation": {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")},
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    counts: Counter = Counter()
    task_decisions = []
    with (
        (args.output / "words.jsonl").open("w") as f,
        (args.output / "vectors.jsonl").open("w") as vectors,
        (args.output / "sparse.jsonl").open("w") as sparse,
        (args.output / "structures.jsonl").open("w") as structures,
    ):
        for record in build(
            words, sources, rulebook, selector, args.bank_review, False, tasks, exceptions, conditional_catalog=catalog
        ):
            f.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            f.flush()
            for reading in record["readings"]:
                task_decisions.extend(reading.get("decisions", []))
                counts[reading["code"]] += 1
                sparse.write(json.dumps(export_sparse(reading), ensure_ascii=False, allow_nan=False) + "\n")
                if reading["candidate_vector"] is not None:
                    vectors.write(json.dumps(export_vector(reading), ensure_ascii=False, allow_nan=False) + "\n")
                    vectors.flush()
            for entry in record["structural_entries"]:
                structures.write(
                    json.dumps({"word": record["word"], "basis_id": BASIS_ID, **entry}, ensure_ascii=False) + "\n"
                )
            if not record["readings"]:
                counts[record["code"]] += 1
            print(record["word"], [r["code"] for r in record["readings"]] or record["code"], flush=True)
    (args.output / "summary.json").write_text(json.dumps(dict(counts), indent=2) + "\n")
    (args.output / "tail-ledger.json").write_text(json.dumps(tail_ledger(tasks, task_decisions), indent=2) + "\n")
    return 0
