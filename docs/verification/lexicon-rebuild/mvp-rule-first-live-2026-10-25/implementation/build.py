"""Source records → symbolic closure → bounded local selection → closure.

Lexical projections are explicit rulebook entries. Candidate template closure
is recorded separately from source/rule-certified cells and cannot be exported
as an audited production lexicon.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

from gse.lexicon_builder.artifact import export_vector
from gse.lexicon_builder.basis import BASIS_ID, PRIME_TO_BANK
from gse.lexicon_builder.core import CANONICAL_COORDINATES, Cell, Law, Observation, Resolution, resolve
from gse.lexicon_builder.model import DEFAULT_MODEL, OllamaSelector
from gse.lexicon_builder.native_constraints import native_readings
from gse.lexicon_builder.registry import RULEBOOK, compile_law, export_candidates, load_rulebook
from gse.lexicon_builder.sources import NativeSources, sha256, word_key


def restriction(rule_id: str, coordinate: str, states: list[str], warrant: str) -> Law:
    return Law(rule_id, (coordinate,), tuple((Cell(v),) for v in states), (), warrant)


def source_matches(native: dict, rulebook: dict) -> list[dict]:
    """Typed POS/category/frame conjunction; preserve every native alternative."""
    matches = []
    for record in native["usas"]["records"]:
        row = record["values"]
        for alternative in row["alternatives"]:
            # A slash is joint membership: an unhandled second component cannot
            # be discarded to manufacture a complete simple template.
            for rule in rulebook["source_rules"]:
                if row["pos"] not in rule["pos"] or "/" in alternative:
                    continue
                tag = re.fullmatch(re.escape(rule["category"]) + r"([+]+|[-]+)", alternative)
                if tag is None:
                    continue
                frames = [
                    r
                    for r in native["framenet"]["records"]
                    if r["values"]["pos"] == "a" and r["values"]["frame"] in rule["frames"]
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
    return matches


def _payload(word: str, reading_id: str, match: dict, native: dict, state: Resolution) -> dict:
    # Word-level associations stay explicitly scoped; FN alternatives not
    # selected by the typed join are preserved in the artifact, not asserted
    # as properties of this reading in a model request.
    return {
        "schema": "GSE_RESIDUAL_V1",
        "word": word,
        "reading_id": reading_id,
        "selected_native_types": {"pos": match["pos"], "usas_tag": match["tag"], "frames": match["frames"]},
        "native_word_observations": {s: native[s] for s in ("concreteness", "lancaster", "vad", "emotion")},
        "fixed_coordinates": {c: v.value for c, v in state.forced().items()},
        "residual_domains": {
            c: [s.value for s in state.domains[c]] for c in match["rule"]["residual"] if len(state.domains[c]) > 1
        },
        "residual_warrants": match["rule"].get("residual_warrants", {}),
        "degree_contract": {
            "coordinate": "INTENSITY",
            "present": "DEFINITION_CONTAINS_DEGREE_BEARING_CONTENT",
            "relative_strength": "SEPARATE_NUMBER_OPERATOR_PRESERVING_SIGNS_AND_MASKS",
            "native_degree_rank": match["native_degree_rank"],
            "rating_limit": "ASSOCIATION_VALENCE_AND_AROUSAL_DO_NOT_ESTABLISH_LEXICAL_SCALE",
        },
        "operation": "FILL_ONLY_REMAINING_TYPED_FIELDS",
    }


def construct(word: str, match: dict, native: dict, rulebook: dict, selector: OllamaSelector | None) -> dict:
    rule = match["rule"]
    reading_id = f"{word}:{match['pos']}:{match['tag']}:{rule['family']}"
    observations = tuple(
        Observation(reading_id, "rulebook", rule["rule_id"], field, value, True)
        for field, value in [("own_role", "modifier_property_only"), *rule.get("reading_facts", [])]
    )
    laws = [compile_law(r) for r in rulebook["laws"]]
    laws.append(restriction(rule["rule_id"], rule["coordinate"], [match["pole"]], rule["warrant"]))
    for coordinate, value in rule["companions"].items():
        laws.append(restriction(rule["rule_id"] + ":" + coordinate, coordinate, [value], rule["warrant"]))
    for coordinate in rule["residual"]:
        states = ["empty", "+1"]
        laws.append(
            restriction(
                rule["rule_id"] + ":DOMAIN:" + coordinate,
                coordinate,
                states,
                "Scoped template: optional own component; no written middle without a contract",
            )
        )
    initial = resolve(reading_id, observations, laws=tuple(laws))
    state = initial
    calls = []
    decisions = []
    # Choose one residual coordinate, close immediately, and recompute. New
    # multi-coordinate bank laws can settle other fields without another call.
    if selector is not None:
        while state.code != "CONFLICT":
            unresolved = [c for c in rule["residual"] if len(state.domains[c]) > 1]
            if not unresolved:
                break
            coordinate = unresolved[0]
            options = {coordinate: [v.value for v in state.domains[coordinate]]}
            call = selector.select(_payload(word, reading_id, match, native, state), options)
            calls.append(call)
            laws.append(
                restriction(
                    "MODEL:" + call["request_sha256"],
                    coordinate,
                    [call["answer"][coordinate]],
                    "Typed local selection; candidate, not a new source fact",
                )
            )
            previous = state
            state = resolve(reading_id, observations, laws=tuple(laws))
            decisions.append(
                {
                    "selected": call["answer"],
                    "before": {c: [v.value for v in previous.domains[c]] for c in unresolved},
                    "after": {c: [v.value for v in state.domains[c]] for c in unresolved},
                    "forced_after": len(state.forced()),
                }
            )
    complete_residual = all(len(state.domains[c]) == 1 for c in rule["residual"])
    coverage = "NOT_CHECKED"
    if selector is not None and complete_residual and rule["coverage"] is not None and state.code != "CONFLICT":
        payload = _payload(word, reading_id, match, native, state)
        payload.update(
            {
                "operation": "OMISSION_CHALLENGE",
                "candidate_active_coordinates": [
                    c for c, value in state.forced().items() if value not in (Cell.SILENT, Cell.ZERO)
                ],
                "challenge": "MISSING_DEFINITIONAL_COMPONENT_OUTSIDE_TEMPLATE",
                "coordinate_bank_ids": PRIME_TO_BANK,
            }
        )
        options = {
            "MISSING_COORDINATE": ["NONE"]
            + [c for c in CANONICAL_COORDINATES if c not in state.forced() or state.forced()[c] == Cell.SILENT]
        }
        call = selector.select(payload, options)
        calls.append(call)
        coverage = call["answer"]["MISSING_COORDINATE"]
    candidate = None
    closed = None
    if complete_residual and coverage == "NONE" and state.code != "CONFLICT":
        # This is the founder-approved provisional closure after an omission
        # challenge. Preserve the pre-closure state and label every added mask.
        provisional = []
        for coordinate in CANONICAL_COORDINATES:
            if len(state.domains[coordinate]) > 1:
                provisional.append(coordinate)
                laws.append(
                    restriction(
                        "PROVISIONAL_COVERAGE:" + rule["coverage"],
                        coordinate,
                        ["empty"],
                        "Template coverage proposal + local omission challenge; requires Zipf audit",
                    )
                )
        closed = resolve(reading_id, observations, laws=tuple(laws))
        if closed.code == "RESOLVED":
            forced = closed.forced()
            candidate = {
                "states": {c: forced[c].value for c in CANONICAL_COORDINATES},
                "mask": [forced[c] != Cell.SILENT for c in CANONICAL_COORDINATES],
                "signs": [None if forced[c] == Cell.SILENT else int(forced[c]) for c in CANONICAL_COORDINATES],
                "provisional_silence": provisional,
                "trace": list(closed.trace),
            }
    code = "CONFLICT" if state.code == "CONFLICT" else "CANDIDATE_COMPLETE" if candidate else "PARTIAL"
    return {
        "word": word,
        "reading_id": reading_id,
        "code": code,
        "production_eligible": False,
        "rule_id": rule["rule_id"],
        "rule_review_state": rule["review_state"],
        "premise_record_ids": match["premises"],
        "symbolic_before": initial.to_json(),
        "after_selection": state.to_json(),
        "after_closure": closed.to_json() if closed is not None else None,
        "decisions": decisions,
        "model_calls": calls,
        "omission_challenge": coverage,
        "coverage_gap": rule.get("coverage_gap"),
        "candidate_vector": candidate,
        "number_scale": {
            "family": rule["family"] + ":" + match["pole"],
            "native_ordinal_rank": match["native_degree_rank"],
            "coordinates": [rule["coordinate"]],
            "numeric_gain": None,
            "status": "NATIVE_TAG_ORDER_ONLY; NOT_CROSS_WORD_CALIBRATED",
        },
    }


def build(words: list[str], sources: NativeSources, rulebook: dict, selector: OllamaSelector | None) -> Iterator[dict]:
    for raw_word in words:
        word = word_key(raw_word)
        native = sources.for_word(word)
        matches = source_matches(native, rulebook)
        readings = [construct(word, m, native, rulebook, selector) for m in matches]
        readings.extend(native_readings(word, native, rulebook, selector))
        yield {
            "word": word,
            "native": native,
            "readings": readings,
            "code": "CONSTRUCTED_READINGS" if readings else "PARTIAL_NO_APPLICABLE_RULE",
            "unhandled_native_alternatives": [
                {"record_id": r["record_id"], "pos": r["values"]["pos"], "tag": tag}
                for r in native["usas"]["records"]
                for tag in r["values"]["alternatives"]
                if not any(m["pos"] == r["values"]["pos"] and m["tag"] == tag for m in matches)
            ],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "rules"))
    parser.add_argument("--words", nargs="+")
    parser.add_argument("--word-file", type=Path)
    parser.add_argument("--sources", type=Path, default=Path("data/external"))
    parser.add_argument("--nltk", type=Path, default=Path.home() / "nltk_data/corpora")
    parser.add_argument("--rulebook", type=Path, default=RULEBOOK)
    parser.add_argument(
        "--coherence", type=Path, default=Path("docs/verification/lexicon-rebuild/coherence-2026-10-24/results.json")
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--symbolic-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "rules":
        print(json.dumps(export_candidates(args.coherence, args.output), indent=2))
        return 0
    words = args.words or (args.word_file.read_text().splitlines() if args.word_file else [])
    if not words:
        parser.error("build requires --words or --word-file")
    args.output.mkdir(parents=True, exist_ok=True)
    rulebook = load_rulebook(args.rulebook)
    sources = NativeSources(words, args.sources, args.nltk)
    selector = None if args.symbolic_only else OllamaSelector(args.model)
    manifest = {
        "schema_version": 1,
        "basis_id": BASIS_ID,
        "coordinate_order": CANONICAL_COORDINATES,
        "rulebook": str(args.rulebook),
        "rulebook_sha256": sha256(args.rulebook),
        "sources": sources.manifest,
        "words": words,
        "model": selector.identity() if selector else None,
        "implementation": {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")},
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    counts: Counter = Counter()
    with (args.output / "words.jsonl").open("w") as f, (args.output / "vectors.jsonl").open("w") as vectors:
        for record in build(words, sources, rulebook, selector):
            f.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            f.flush()
            for reading in record["readings"]:
                counts[reading["code"]] += 1
                if reading["candidate_vector"] is not None:
                    vectors.write(json.dumps(export_vector(reading), ensure_ascii=False, allow_nan=False) + "\n")
                    vectors.flush()
            if not record["readings"]:
                counts[record["code"]] += 1
            print(record["word"], [r["code"] for r in record["readings"]] or record["code"], flush=True)
    (args.output / "summary.json").write_text(json.dumps(dict(counts), indent=2) + "\n")
    return 0
