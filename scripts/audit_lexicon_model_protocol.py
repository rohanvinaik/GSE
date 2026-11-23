"""Run explicit, labeled single-bank probes through the real local adapter.

Labels are supplied by the caller. This does not manufacture independent gold
or write the lexical database; results retain identified/abstained/wrong by class.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from gse.curation.lexicon_builder.engine import Assertion, DomainRestriction, propagate
from gse.curation.lexicon_builder.evidence import Definition, Observation, validate_assertion_competence
from gse.curation.lexicon_builder.foundation import BANKS, definition_context, projection_relations
from gse.curation.lexicon_builder.interchange import read_json
from gse.curation.lexicon_builder.relevance import observation_relevance
from gse.curation.lexicon_builder.residual import OllamaTransport, _read_value, build_request
from gse.curation.lexicon_builder.resolution import resolve_dictionary


def prepare_case(payload: dict, *, production_scaffold: bool = False):
    """Derive domains from explicit inputs, never trust fixture domain snapshots.

    Production mode exercises the real projection resolver and source relevance
    boundary. Known fixture assertions retain their supplied-fixture authority;
    this does not claim a complete production-database evidence reconstruction.
    """
    definition = Definition(**payload["definition"])
    if payload["entry_id"] != definition.entry_id:
        raise ValueError("CALIBRATION_DEFINITION_IDENTITY_MISMATCH")
    bank = payload["bank"]
    if bank not in BANKS:
        raise ValueError("INVALID_CALIBRATION_BANK")
    known = payload.get("known", {})
    assertions = tuple(Assertion(k, v, "fixture", f"known:{k}", "fixture") for k, v in known.items())
    observations = tuple(payload.get("observations", ()))
    context = definition_context(definition.pos) if production_scaffold else None
    relations = projection_relations() if production_scaffold else ()
    if production_scaffold:
        links, relevant = {}, set()
        for raw in observations:
            native = dict(raw)
            native["candidate_entry_ids"] = tuple(native.get("candidate_entry_ids", ()))
            observation = Observation(**native)
            targets = (observation.entry_id,) if observation.entry_id is not None else observation.candidate_entry_ids
            if definition.entry_id not in targets:
                raise ValueError("CALIBRATION_SOURCE_DEFINITION_MISMATCH")
            key = (observation.source, observation.record_id)
            if key in links and links[key] != observation:
                raise ValueError("CALIBRATION_SOURCE_RECORD_COLLISION")
            links[key] = observation
            relevant.update(observation_relevance(observation))
        restrictions = []
        for raw in payload.get("domain_restrictions", ()):
            record = dict(raw)
            record["allowed_values"] = tuple(record["allowed_values"])
            restriction = DomainRestriction(**record)
            validate_assertion_competence(restriction)
            observation = links.get((restriction.source, restriction.record_id))
            if (
                observation is None
                or observation.entry_id != definition.entry_id
                or observation.scope != "lexical"
                or observation.family != restriction.family
                or restriction.source.startswith(("model:", "rule:", "derived:"))
                or restriction.family in {"model", "derived"}
            ):
                raise ValueError("CALIBRATION_RESTRICTION_PROVENANCE_MISMATCH")
            restrictions.append(restriction)
        state = resolve_dictionary(
            BANKS,
            assertions,
            relations,
            context,
            evidence_banks=tuple(sorted(relevant)),
            domain_restrictions=tuple(restrictions),
        )
    else:
        state = propagate(tuple(sorted({bank, *known})), assertions, ())
    if state.code == "CONFLICT":
        return None, {"code": "SYMBOLIC_CONFLICT", "conflicts": state.conflicts}
    if bank in state.assignments:
        return None, {"code": "SYMBOLICALLY_RESOLVED", "value": state.assignments[bank], "proof_trace": state.trace}
    return build_request(
        definition.entry_id, bank, state, observations, definition=definition, relations=relations, context=context
    ), None


def calibration_results(cases, transport, *, budget, batch_size=1, production_scaffold=False, prepare=prepare_case):
    """Keep fixed labels outside requests and budget individual cell questions.

    Batches contain distinct definitions. A preparation refusal shrinks only the
    group; each original request and its evidence remain intact. Timing belongs
    to the whole invocation, never an invented individual-cell latency.
    """
    prepared = []
    for case in cases:
        expected = case["expected"]
        if expected is not None and (type(expected) is not int or expected not in (-1, 0, 1)):
            raise ValueError("INVALID_CALIBRATION_LABEL")
        prepared.append(prepare(case["input"], production_scaffold=production_scaffold))
    questions = invocations = index = 0
    while index < len(cases):
        request, symbolic = prepared[index]
        start = time.monotonic()
        selected = [index]
        results: list[dict] = []
        if symbolic is not None:
            results = [dict(symbolic)]
        elif questions >= budget:
            results = [{"code": "MODEL_BUDGET_EXHAUSTED"}]
        else:
            assert request is not None
            entries = {request.entry_id}
            for following in range(index + 1, min(len(cases), index + batch_size, index + budget - questions)):
                candidate, resolved = prepared[following]
                if resolved is not None or candidate is None or candidate.entry_id in entries:
                    break
                entries.add(candidate.entry_id)
                selected.append(following)
            error = None
            while True:
                requests = [prepared[position][0] for position in selected]
                items = tuple((item.payload(), item.output_schema()) for item in requests)
                try:
                    if batch_size > 1:
                        transport.prepare(items)
                    break
                except Exception as exc:
                    if (
                        getattr(exc, "code", None) in {"BATCH_INPUT_TOO_LARGE", "BATCH_OUTPUT_BUDGET_EXCEEDED"}
                        and len(selected) > 1
                    ):
                        selected.pop()
                        continue
                    error = exc
                    break
            if error is None:
                questions += len(selected)
                invocations += 1
                try:
                    raw_items = transport.callable_batch(items) if batch_size > 1 else (transport(*items[0]),)
                    if not isinstance(raw_items, tuple) or len(raw_items) != len(selected):
                        raise ValueError("INVALID_BATCH_RESULT_CARDINALITY")
                except Exception as exc:
                    error = exc
            for position, item in zip(selected, requests, strict=True):
                try:
                    if error is not None:
                        raise error
                    raw = raw_items[len(results)]
                    value = _read_value(raw, item)
                    expected = cases[position]["expected"]
                    outcome = "IDENTIFIED" if value == expected else "ABSTAINED" if value is None else "WRONG"
                    results.append(
                        {
                            "value": value,
                            "code": outcome,
                            "raw": raw,
                            "transport_metrics": getattr(transport, "last_metrics", None),
                        }
                    )
                except Exception as exc:
                    results.append({"code": "ERROR", "error_type": type(exc).__name__, "reason": str(exc)})
        elapsed = round(time.monotonic() - start, 3)
        for position, result in zip(selected, results, strict=True):
            request, _ = prepared[position]
            expected = cases[position]["expected"]
            result.update(
                input=request.payload() if request is not None else cases[position]["input"],
                expected=expected,
                expected_class="UNRESOLVED" if expected is None else str(expected),
                elapsed_seconds=elapsed,
                elapsed_scope="SHARED_BATCH_INVOCATION" if len(selected) > 1 else "CASE",
                invocation_case_indices=selected,
            )
            result["expected_agreement"] = (
                ("MATCH" if result.get("value") == expected else "MISMATCH") if "value" in result else "NO_VALUE"
            )
            yield position, result, questions, invocations
        index += len(selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-base-url", help="Explicit Ollama-compatible endpoint; otherwise localhost")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-tokens", type=int)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--no-thinking", action="store_true")
    parser.add_argument("--production-scaffold", action="store_true")
    parser.add_argument("--max-model-calls", type=int)
    parser.add_argument("--batch-size", type=int, default=1)
    args = parser.parse_args()
    fixture = read_json(args.cases)
    budget = len(fixture["cases"]) if args.max_model_calls is None else args.max_model_calls
    if type(budget) is not int or budget < 0:
        raise ValueError("INVALID_CALIBRATION_BUDGET")
    if args.batch_size < 1:
        raise ValueError("INVALID_CALIBRATION_BATCH_SIZE")
    endpoint = {"base_url": args.model_base_url} if args.model_base_url is not None else {}
    transport = OllamaTransport(
        args.model,
        output_tokens=args.output_tokens,
        timeout=args.timeout,
        thinking=not args.no_thinking,
        **endpoint,
    )
    model_pin = transport.pin()
    base_transport = transport
    if args.batch_size > 1:
        from gse.curation.lexicon_builder.model_batch import OllamaBatchTransport

        transport = OllamaBatchTransport(base_transport, max_items=args.batch_size)
    records = []
    counts = defaultdict(Counter)
    agreements = defaultdict(Counter)
    for index, result, model_calls, invocations in calibration_results(
        fixture["cases"],
        transport,
        budget=budget,
        batch_size=args.batch_size,
        production_scaffold=args.production_scaffold,
    ):
        label = result["expected_class"]
        records.append(result)
        counts[label][result["code"]] += 1
        agreements[label][result["expected_agreement"]] += 1
        report = {
            "format": "gse.model-protocol-calibration/1",
            "model": args.model,
            "transport_identity": transport.identity,
            "model_pin": model_pin,
            "generation": {
                "output_tokens": base_transport.output_tokens,
                "context_tokens": base_transport.context_tokens,
                "thinking": base_transport.thinking,
                "timeout_seconds": base_transport.timeout,
            },
            "label_authority": fixture.get("label_authority", "CALLER_SUPPLIED_UNVERIFIED"),
            "per_class": {key: dict(value) for key, value in counts.items()},
            "per_class_expected_agreement": {key: dict(value) for key, value in agreements.items()},
            "scaffold_mode": "FULL_BASIS_PROJECTION_WITH_SUPPLIED_EVIDENCE"
            if args.production_scaffold
            else "SMALL_AUTHORED_FIXTURE",
            "fixture_known_authority": "SUPPLIED_FIXTURE_NOT_NATIVE_DERIVED_OR_INDEPENDENT_GOLD",
            "model_calls": model_calls,
            "cell_questions": model_calls,
            "transport_invocations": invocations,
            "budget_unit": "CELL_QUESTIONS",
            "batch_size": args.batch_size,
            "max_model_calls": budget,
            "expected_cases": len(fixture["cases"]),
            "completed_cases": len(records),
            "cases": records,
        }
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(f"{index + 1}/{len(fixture['cases'])} {result['input']['bank']} {result['code']}", flush=True)


if __name__ == "__main__":
    main()
