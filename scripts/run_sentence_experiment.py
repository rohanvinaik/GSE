#!/usr/bin/env python3
"""
Experiment 5.2: Sentence-Level Semantics with GSE API

Uses the proper GSEEncoder/GSEDecoder API for:
- Encoding sentences to HDC vectors
- Computing cosine similarity
- Benchmarking against STS-B test set

Features:
- Parallelized encoding using multiprocessing
- Progress tracking
- Negation subset analysis
"""

import multiprocessing as mp
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from scipy.stats import pearsonr, spearmanr

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from gse.benchmarks.datasets import SentencePair, load_sts_benchmark

# Global for worker processes
_worker_encoder = None
_worker_decoder = None


def init_worker(db_path: str = "data/lexicon.db"):
    """Initialize worker process with GSE encoder/decoder."""
    global _worker_encoder, _worker_decoder

    from gse.api import GSEDecoder, GSEEncoder

    _worker_encoder = GSEEncoder(db_path=db_path)
    _worker_decoder = GSEDecoder(db_path=db_path)


def encode_pair_worker(args: Tuple[int, str, str]) -> Tuple[int, Optional[float]]:
    """Encode a sentence pair and compute similarity."""
    global _worker_encoder, _worker_decoder

    idx, sent1, sent2 = args

    try:
        trace1 = _worker_encoder.encode(sent1)
        trace2 = _worker_encoder.encode(sent2)

        if trace1.final_nnz == 0 or trace2.final_nnz == 0:
            return idx, None

        # Use the decoder's similarity method
        sim_result = _worker_decoder.similarity(trace1.vector, trace2.vector, sent1, sent2)
        return idx, float(sim_result.cosine)
    except Exception:
        return idx, None


@dataclass
class SentenceResult:
    model: str
    spearman_rho: float
    pearson_r: float
    coverage: float
    n_pairs: int
    negation_rho: Optional[float] = None


def evaluate_gse_parallel(
    pairs: List[SentencePair],
    db_path: str = "data/lexicon.db",
    n_workers: int = 10,
) -> SentenceResult:
    """Evaluate GSE on sentence pairs using parallel processing."""

    print(f"  Using {n_workers} workers with GSE API")

    # Prepare work items
    work_items = [(i, pair.sentence1, pair.sentence2) for i, pair in enumerate(pairs)]

    predictions = [None] * len(pairs)
    human_scores = [pair.score for pair in pairs]

    start_time = time.time()
    completed = 0

    with ProcessPoolExecutor(max_workers=n_workers, initializer=init_worker, initargs=(db_path,)) as executor:
        futures = {executor.submit(encode_pair_worker, item): item[0] for item in work_items}

        for future in as_completed(futures):
            idx, sim = future.result()
            predictions[idx] = sim
            completed += 1

            if completed % 100 == 0 or completed == len(pairs):
                elapsed = time.time() - start_time
                rate = completed / elapsed
                eta = (len(pairs) - completed) / rate if rate > 0 else 0
                print(
                    f"\r  Progress: {completed}/{len(pairs)} ({100 * completed / len(pairs):.1f}%) - {rate:.1f} pairs/s - ETA: {eta:.0f}s",
                    end="",
                    flush=True,
                )

    print()  # Newline after progress

    # Filter valid predictions
    valid_mask = [p is not None for p in predictions]
    valid_predictions = [p for p, v in zip(predictions, valid_mask) if v]
    valid_human = [h for h, v in zip(human_scores, valid_mask) if v]

    coverage = len(valid_predictions) / len(pairs)

    if len(valid_predictions) < 2:
        return SentenceResult("GSE", 0.0, 0.0, coverage, len(pairs))

    spearman_rho, _ = spearmanr(valid_predictions, valid_human)
    pearson_r, _ = pearsonr(valid_predictions, valid_human)

    # Negation subset analysis
    negation_markers = ["not", "n't", "no", "never", "neither", "nobody", "nothing", "none", "nor", "cannot", "without"]
    negation_preds = []
    negation_human = []

    for i, pair in enumerate(pairs):
        if predictions[i] is None:
            continue
        s1_lower = pair.sentence1.lower()
        s2_lower = pair.sentence2.lower()
        has_negation = any(m in s1_lower or m in s2_lower for m in negation_markers)
        if has_negation:
            negation_preds.append(predictions[i])
            negation_human.append(pair.score)

    negation_rho = None
    if len(negation_preds) >= 2:
        negation_rho, _ = spearmanr(negation_preds, negation_human)
        print(f"  Negation subset: {len(negation_preds)} pairs, ρ={negation_rho:.4f}")

    return SentenceResult(
        model="GSE (Hadamard-OTP)",
        spearman_rho=spearman_rho,
        pearson_r=pearson_r,
        coverage=coverage,
        n_pairs=len(pairs),
        negation_rho=negation_rho,
    )


def evaluate_baseline(pairs: List[SentencePair], model_name: str) -> SentenceResult:
    """Evaluate a sentence-transformers baseline."""
    from sentence_transformers import SentenceTransformer

    print(f"  Loading {model_name}...")
    model = SentenceTransformer(model_name)

    sentences1 = [pair.sentence1 for pair in pairs]
    sentences2 = [pair.sentence2 for pair in pairs]
    human_scores = [pair.score for pair in pairs]

    print("  Encoding sentences...")
    embeddings1 = model.encode(sentences1, show_progress_bar=True)
    embeddings2 = model.encode(sentences2, show_progress_bar=True)

    # Cosine similarities
    predictions = []
    for e1, e2 in zip(embeddings1, embeddings2):
        sim = np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2))
        predictions.append(float(sim))

    spearman_rho, _ = spearmanr(predictions, human_scores)
    pearson_r, _ = pearsonr(predictions, human_scores)

    # Negation subset
    negation_markers = ["not", "n't", "no", "never", "neither", "nobody", "nothing", "none", "nor", "cannot", "without"]
    negation_preds = []
    negation_human = []

    for i, pair in enumerate(pairs):
        s1_lower = pair.sentence1.lower()
        s2_lower = pair.sentence2.lower()
        has_negation = any(m in s1_lower or m in s2_lower for m in negation_markers)
        if has_negation:
            negation_preds.append(predictions[i])
            negation_human.append(pair.score)

    negation_rho = None
    if len(negation_preds) >= 2:
        negation_rho, _ = spearmanr(negation_preds, negation_human)
        print(f"  Negation subset: {len(negation_preds)} pairs, ρ={negation_rho:.4f}")

    return SentenceResult(
        model=model_name,
        spearman_rho=spearman_rho,
        pearson_r=pearson_r,
        coverage=1.0,
        n_pairs=len(pairs),
        negation_rho=negation_rho,
    )


def main():
    print("=" * 60)
    print("EXPERIMENT 5.2: Sentence-Level Semantics")
    print("=" * 60)
    print()

    # Load dataset
    print("Loading STS Benchmark...")
    sts_test = load_sts_benchmark("test")
    print(f"  Loaded {len(sts_test)} pairs")
    print()

    results = []

    # GSE evaluation (parallel)
    print("Evaluating GSE...")
    n_cores = min(10, mp.cpu_count())
    gse_result = evaluate_gse_parallel(
        list(sts_test),
        n_workers=n_cores,
    )
    results.append(gse_result)
    print(
        f"  STS-B: ρ={gse_result.spearman_rho:.4f}, r={gse_result.pearson_r:.4f} (coverage={gse_result.coverage * 100:.1f}%)"
    )
    print()

    # Baselines
    baselines = ["all-MiniLM-L6-v2"]

    for baseline in baselines:
        print(f"Evaluating {baseline}...")
        result = evaluate_baseline(list(sts_test), baseline)
        results.append(result)
        print(f"  STS-B: ρ={result.spearman_rho:.4f}, r={result.pearson_r:.4f}")
        print()

    # Summary
    print("=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print()
    print("| Model | Spearman ρ | Pearson r | Negation ρ |")
    print("|-------|------------|-----------|------------|")
    for r in results:
        neg = f"{r.negation_rho:.4f}" if r.negation_rho else "N/A"
        print(f"| {r.model[:30]:30} | {r.spearman_rho:.4f} | {r.pearson_r:.4f} | {neg} |")

    print()
    print("Done!")


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()
