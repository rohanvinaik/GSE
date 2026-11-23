"""Propose, stage and directly audit reviewed patterns without changing a lexicon.

Input: gse.reviewed-pattern-input/2 (legacy /1 remains replayable), with native
premise proofs and explicit receipt-pinned ACCEPTED
reviews, disjoint discovery/audit definition IDs, exact definition inputs and
baseline relations. Reviewed model prefixes replay from the native/anchor
baseline with every dependency supplied and no audit-target leakage. Optional
guarded_candidates carry explicit warrants, typed guards and absent-evidence
conditions; reports retain those warrants but never approve a rule.
"""

import argparse
import json
from pathlib import Path

from gse.curation.lexicon_builder.residual import OllamaTransport
from gse.curation.lexicon_builder.reviewed_patterns import run_workflow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--model")
    parser.add_argument("--max-model-calls", type=int, default=0)
    parser.add_argument("--output-tokens", type=int, default=128)
    parser.add_argument("--context-tokens", type=int)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--no-thinking", action="store_true")
    args = parser.parse_args()
    if args.input.resolve() == args.report.resolve() or (args.report.exists() and args.report.samefile(args.input)):
        raise ValueError("PATTERN_REPORT_CANNOT_OVERWRITE_INPUT")
    if args.max_model_calls < 0 or bool(args.model) != (args.max_model_calls > 0):
        raise ValueError("MODEL_REQUIRES_EXPLICIT_POSITIVE_AUDIT_BUDGET")
    transport = None
    if args.model:
        context_options = {} if args.context_tokens is None else {"context_tokens": args.context_tokens}
        transport = OllamaTransport(
            args.model,
            output_tokens=args.output_tokens,
            timeout=args.timeout,
            thinking=not args.no_thinking,
            **context_options,
        )
        transport.pin()
    report = run_workflow(args.input, transport, max_calls=args.max_model_calls)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "candidates": len(report["candidates"]),
                "model_calls": report["model_calls"],
                "admission": "UNAPPROVED_CANDIDATES_ONLY",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
