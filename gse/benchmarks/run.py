"""
Benchmark runner CLI.

Encodes the pairs in a benchmark dataset with the GSE encoder, computes
cosine similarity between each pair, and reports the dataset-appropriate
metric (Spearman correlation with bootstrap CI for graded datasets;
antonym/synonym discrimination AUC for the custom relation sets).

Examples
--------

    python -m gse.benchmarks.run --task simlex999
    python -m gse.benchmarks.run --task sts --limit 50
    python -m gse.benchmarks.run --task antonyms
    python -m gse.benchmarks.run --task all
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from typing import List, Optional

from gse.api import GSEEncoder
from gse.benchmarks.datasets import (
    BenchmarkDataset,
    load_custom_antonyms,
    load_custom_synonyms,
    load_simlex999,
    load_sts_benchmark,
)
from gse.benchmarks.metrics import (
    antonym_metrics,
    antonym_synonym_auc,
    bank_cosine_signature,
    correlation_with_ci,
)
from gse.primitives_v2 import BIPOLAR_DIMENSIONS, DIMS_PER_BANK

logger = logging.getLogger(__name__)

# Map task name -> (loader, mode). Mode is "correlation" for graded datasets,
# "antonym" or "synonym" for the custom relation sets.
TASKS: dict = {
    "simlex999": (load_simlex999, "correlation"),
    "sts": (lambda: load_sts_benchmark(split="dev"), "correlation"),
    "antonyms": (load_custom_antonyms, "antonym"),
    "synonyms": (load_custom_synonyms, "synonym"),
}


@dataclass
class PairResult:
    text1: str
    text2: str
    gold: float
    predicted: float
    # For antonym/synonym tasks, also record per-bank cosine structure so the
    # benchmark can distinguish "globally similar but oppose in one bank"
    # (the expected antonym geometry) from "indiscriminate similarity."
    min_bank_cosine: Optional[float] = None
    min_bank_name: Optional[str] = None


def _encode_pairs(
    dataset: BenchmarkDataset,
    encoder: GSEEncoder,
    limit: Optional[int] = None,
    compute_bank_signature: bool = False,
) -> List[PairResult]:
    """Encode each pair in the dataset and record gold + predicted similarity.

    When ``compute_bank_signature`` is True, also records the per-pair
    minimum bank-projected cosine and the bank that produced it. This is
    architecture-aligned for antonym/synonym tasks where the bipolar
    structure lives in a specific bank rather than the global bundle.
    """
    results: List[PairResult] = []
    pairs = list(dataset.pairs)
    if limit is not None:
        pairs = pairs[:limit]

    for i, pair in enumerate(pairs):
        if hasattr(pair, "word1"):
            t1, t2 = pair.word1, pair.word2
        else:
            t1, t2 = pair.sentence1, pair.sentence2
        v1 = encoder.encode(t1).vector
        v2 = encoder.encode(t2).vector
        predicted = v1.cosine(v2)

        min_bank_cos = None
        min_bank_name = None
        if compute_bank_signature:
            sig = bank_cosine_signature(v1, v2)
            min_bank_cos = sig.min_bank_cosine
            min_bank_name = sig.min_bank_name

        results.append(PairResult(
            text1=t1, text2=t2, gold=pair.score, predicted=predicted,
            min_bank_cosine=min_bank_cos, min_bank_name=min_bank_name,
        ))

        if (i + 1) % 50 == 0:
            logger.info("Encoded %d/%d pairs", i + 1, len(pairs))

    return results


def _print_header(name: str, n: int) -> None:
    print()
    print(f"=== {name} ({n} pairs) ===")


def _report_correlation(name: str, results: List[PairResult], n_bootstrap: int) -> None:
    gold = [r.gold for r in results]
    predicted = [r.predicted for r in results]
    corr = correlation_with_ci(predicted, gold, n_bootstrap=n_bootstrap)
    _print_header(name, len(results))
    print(f"  Spearman rho:   {corr.rho:+.4f}")
    print(f"  95% CI:         [{corr.ci_low:+.4f}, {corr.ci_high:+.4f}]")
    print(f"  p-value:        {corr.p_value:.2e}")


def _report_antonym(name: str, results: List[PairResult]) -> None:
    sims = [r.predicted for r in results]
    metrics = antonym_metrics(sims)
    _print_header(name, len(results))
    print("  -- Global cosine (whole bundle) --")
    print(f"  Negative rate:  {metrics.negative_rate:.3f}  (fraction with global cos < 0)")
    print(f"  Mean cos:       {metrics.mean_similarity:+.4f}")
    print(f"  Median cos:     {metrics.median_similarity:+.4f}")
    print(f"  Range:          [{metrics.min_similarity:+.4f}, {metrics.max_similarity:+.4f}]")

    # Bank-projected view: antonyms are expected to oppose in the bipolar
    # dimension's bank even when the global bundle stays positive. Report
    # the most-negative bank per pair.
    bank_sims: List[float] = [
        r.min_bank_cosine for r in results if r.min_bank_cosine is not None
    ]
    if bank_sims:
        bank_neg_rate = sum(1 for s in bank_sims if s < 0) / len(bank_sims)
        bank_scored = [r for r in results if r.min_bank_cosine is not None]
        print()
        print("  -- Bank-projected (most-negative bank per pair) --")
        print(f"  Negative rate:  {bank_neg_rate:.3f}  (fraction with min-bank cos < 0)")
        print(f"  Mean min-bank:  {sum(bank_sims) / len(bank_sims):+.4f}")
        # Bank-of-opposition breakdown
        from collections import Counter
        bank_counts = Counter(r.min_bank_name for r in bank_scored if r.min_bank_name)
        print(f"  Opposition bank: {dict(bank_counts.most_common())}")


def _report_synonym(name: str, results: List[PairResult]) -> None:
    sims = [r.predicted for r in results]
    _print_header(name, len(results))
    if sims:
        positive_rate = sum(1 for s in sims if s > 0) / len(sims)
        mean = sum(sims) / len(sims)
        print(f"  Positive rate:  {positive_rate:.3f}  (fraction with global cos > 0)")
        print(f"  Mean cos:       {mean:+.4f}")


def _report_auc(antonym_results: List[PairResult], synonym_results: List[PairResult]) -> None:
    if antonym_results and synonym_results:
        auc = antonym_synonym_auc(
            [r.predicted for r in antonym_results],
            [r.predicted for r in synonym_results],
        )
        print()
        print("=== Antonym vs Synonym Discrimination ===")
        print(f"  AUC:            {auc:.4f}  (0.5 = chance, 1.0 = perfect)")


def run_bipolar_pairs(
    encoder: Optional[GSEEncoder] = None,
) -> List[PairResult]:
    """Run the 14 GSE BIPOLAR_DIMENSIONS as a benchmark.

    For each bipolar pair (GOOD/BAD, BIG/SMALL, NEAR/FAR, …), encode the
    two English labels and assert that the bank-projected cosine in the
    dimension's home bank is strongly negative (≤ -0.9). This is the
    architecture-aligned theory contract for word-scale antonym geometry.

    Reports per-pair: target bank, target-bank cos, global cos, source
    of decomposition (Tier 0 if dispatched, aggregation otherwise).
    """
    encoder = encoder or GSEEncoder()
    results: List[PairResult] = []
    n_passing = 0

    _print_header("Bipolar antagonism (14 GSE BIPOLAR_DIMENSIONS)", len(BIPOLAR_DIMENSIONS))
    print(
        f"  {'dimension':18} {'pair':22} {'bank':14} {'target_cos':>11} "
        f"{'global':>8}"
    )
    print("  " + "-" * 76)

    for dim in BIPOLAR_DIMENSIONS:
        pos_word = dim.positive.lower()
        neg_word = dim.negative.lower()
        t1 = encoder.encode(pos_word)
        t2 = encoder.encode(neg_word)
        v1 = t1.vector
        v2 = t2.vector

        global_cos = v1.cosine(v2)
        bank_idx = dim.bank.value
        b1 = v1.with_bank_only(bank_idx, DIMS_PER_BANK)
        b2 = v2.with_bank_only(bank_idx, DIMS_PER_BANK)
        if b1.nnz > 0 and b2.nnz > 0:
            target_cos = b1.cosine(b2)
        else:
            target_cos = float("nan")

        results.append(PairResult(
            text1=pos_word,
            text2=neg_word,
            gold=-1.0,
            predicted=global_cos,
            min_bank_cosine=target_cos,
            min_bank_name=dim.bank.name,
        ))

        passing = target_cos <= -0.9
        if passing:
            n_passing += 1
        marker = "✓" if passing else "✗"
        pair_str = f"{pos_word}/{neg_word}"
        print(
            f"  {marker} {dim.name:16} {pair_str:22} {dim.bank.name:14} "
            f"{target_cos:+11.4f} {global_cos:+8.4f}"
        )

    print()
    print(f"  {n_passing}/{len(BIPOLAR_DIMENSIONS)} pairs pass target_cos ≤ -0.9")
    return results


def run_task(
    task: str,
    encoder: Optional[GSEEncoder] = None,
    limit: Optional[int] = None,
    n_bootstrap: int = 1000,
) -> List[PairResult]:
    """Run a single named benchmark task. Returns the per-pair results."""
    if task == "bipolar_pairs":
        return run_bipolar_pairs(encoder=encoder)

    if task not in TASKS:
        raise ValueError(f"Unknown task {task!r}; options: {sorted(TASKS)}")

    loader, mode = TASKS[task]
    dataset = loader()
    encoder = encoder or GSEEncoder()
    # Antonym/synonym tasks need per-bank cosine to expose bipolar structure;
    # correlation tasks treat global cosine as the model's prediction.
    want_bank = mode in ("antonym", "synonym")
    results = _encode_pairs(dataset, encoder, limit=limit, compute_bank_signature=want_bank)

    if mode == "correlation":
        _report_correlation(dataset.name, results, n_bootstrap=n_bootstrap)
    elif mode == "antonym":
        _report_antonym(dataset.name, results)
    elif mode == "synonym":
        _report_synonym(dataset.name, results)

    return results


def run_all(
    encoder: Optional[GSEEncoder] = None,
    limit: Optional[int] = None,
    n_bootstrap: int = 1000,
) -> None:
    """Run every benchmark in TASKS, plus the antonym/synonym AUC summary."""
    encoder = encoder or GSEEncoder()
    antonym_results: List[PairResult] = []
    synonym_results: List[PairResult] = []

    for task in TASKS:
        results = run_task(task, encoder=encoder, limit=limit, n_bootstrap=n_bootstrap)
        if task == "antonyms":
            antonym_results = results
        elif task == "synonyms":
            synonym_results = results

    _report_auc(antonym_results, synonym_results)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run GSE benchmark tasks")
    parser.add_argument(
        "--task",
        choices=sorted(list(TASKS) + ["all", "bipolar_pairs"]),
        default="all",
        help="Which benchmark to run (default: all).",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Cap on pairs (useful for smoke tests)."
    )
    parser.add_argument(
        "--bootstrap",
        type=int,
        default=1000,
        help="Bootstrap samples for correlation CIs.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable INFO logging.")
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.task == "all":
        run_all(limit=args.limit, n_bootstrap=args.bootstrap)
    else:
        run_task(args.task, limit=args.limit, n_bootstrap=args.bootstrap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
