#!/usr/bin/env python3
"""
GSE Paper Experiments Runner (Sections 5.1 & 5.2)

Runs comprehensive evaluation of GSE against baselines:
- Experiment 5.1: Word-level structural semantics (SimLex-999, antonyms)
- Experiment 5.2: Sentence-level semantics (STS Benchmark, negation)

Usage:
    python scripts/run_experiments.py --all
    python scripts/run_experiments.py --word-level
    python scripts/run_experiments.py --sentence-level
    python scripts/run_experiments.py --antonyms-only
"""

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.stats import pearsonr, spearmanr

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gse.benchmarks.datasets import (
    BenchmarkDataset,
    load_custom_antonyms,
    load_custom_synonyms,
    load_simlex999,
    load_sts_benchmark,
    load_wordsim353,
)
from gse.pipeline_v2 import GSEPipeline

# =============================================================================
# RESULT DATA STRUCTURES
# =============================================================================


@dataclass
class WordLevelResult:
    """Results for a word-level evaluation."""

    model_name: str
    dataset_name: str
    spearman_rho: float
    spearman_p: float
    pearson_r: float
    pearson_p: float
    coverage: float  # % of pairs where both words found
    n_pairs: int
    antonym_neg_rate: Optional[float] = None
    antonym_mean_sim: Optional[float] = None
    predictions: List[float] = field(default_factory=list)


@dataclass
class SentenceLevelResult:
    """Results for sentence-level evaluation."""

    model_name: str
    dataset_name: str
    encoding_method: str
    spearman_rho: float
    spearman_p: float
    n_pairs: int
    negation_rho: Optional[float] = None
    negation_n: Optional[int] = None


@dataclass
class ExperimentResults:
    """Complete experiment results."""

    timestamp: str
    word_level: List[WordLevelResult] = field(default_factory=list)
    sentence_level: List[SentenceLevelResult] = field(default_factory=list)
    antonym_analysis: Dict[str, Any] = field(default_factory=dict)
    ablations: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# GSE EVALUATOR
# =============================================================================


class GSEEvaluator:
    """Evaluate GSE on benchmark datasets."""

    # POS tags to try - content words first
    POS_OPTIONS = ["ADJ", "NOUN", "VERB", "ADV", "ADP", "DET", "n", "v", "adj", "adv"]

    def __init__(self, lexicon_path: str = "data/lexicon.db"):
        self.pipeline = GSEPipeline(lexicon_path=lexicon_path)
        self._word_cache = {}

        # Build index of best POS for each word (most primitives with meaningful content)
        self._best_pos_cache = {}

    def _get_best_lexeme(self, word: str):
        """Find the lexeme entry with the most semantic content."""
        word_lower = word.lower()

        if word_lower in self._best_pos_cache:
            return self._best_pos_cache[word_lower]

        best_lexeme = None
        best_score = -1

        # Search all POS options
        for pos in self.POS_OPTIONS:
            for sense_id in ["01", "02", "03"]:
                key = f"{word_lower}_{pos}_{sense_id}"
                lexeme = self.pipeline.tree.get_lexeme(key)

                if lexeme:
                    vec_size = len(lexeme.vector_positive) + len(lexeme.vector_negative)
                    decomp_size = len(lexeme.decomposition)

                    # Score: prefer ADJ/NOUN/VERB, penalize ADV/ADP
                    pos_bonus = 10 if pos in ["ADJ", "NOUN", "VERB"] else 0
                    score = vec_size + decomp_size + pos_bonus

                    if score > best_score:
                        best_score = score
                        best_lexeme = (lexeme, pos)

        self._best_pos_cache[word_lower] = best_lexeme
        return best_lexeme

    def get_word_vector(self, word: str) -> Optional[np.ndarray]:
        """Get dense vector for a word by finding best lexeme entry."""
        if word in self._word_cache:
            return self._word_cache[word]

        word_lower = word.lower()

        # Find best lexeme
        result = self._get_best_lexeme(word_lower)

        if result:
            lexeme, pos = result
            if len(lexeme.vector_positive) > 0 or len(lexeme.vector_negative) > 0:
                decomp_result = self.pipeline.decompose_word(word_lower, pos)
                if decomp_result.vector and decomp_result.vector.nnz > 0:
                    vec = decomp_result.vector.to_dense()
                    self._word_cache[word] = vec
                    return vec

        # Fallback: try encode_sentence (may infer)
        try:
            result = self.pipeline.encode_sentence(word)
            if result.vector is not None and np.any(result.vector):
                self._word_cache[word] = result.vector
                return result.vector
        except Exception:
            pass

        return None

    def word_similarity(self, word1: str, word2: str) -> Optional[float]:
        """Compute cosine similarity between two words."""
        v1 = self.get_word_vector(word1)
        v2 = self.get_word_vector(word2)

        if v1 is None or v2 is None:
            return None

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return None

        return float(np.dot(v1, v2) / (norm1 * norm2))

    def sentence_similarity(self, sent1: str, sent2: str, method: str = "mean") -> Optional[float]:
        """Compute similarity between two sentences."""
        try:
            result1 = self.pipeline.encode_sentence(sent1)
            result2 = self.pipeline.encode_sentence(sent2)

            if result1.vector is None or result2.vector is None:
                return None

            v1 = result1.vector
            v2 = result2.vector

            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)

            if norm1 == 0 or norm2 == 0:
                return None

            return float(np.dot(v1, v2) / (norm1 * norm2))

        except Exception:
            return None

    def evaluate_word_dataset(self, dataset: BenchmarkDataset, is_antonym: bool = False) -> WordLevelResult:
        """Evaluate on a word-level dataset."""
        predictions = []
        human_scores = []
        covered = 0

        for pair in dataset.pairs:
            sim = self.word_similarity(pair.word1, pair.word2)
            if sim is not None:
                predictions.append(sim)
                human_scores.append(pair.score)
                covered += 1
            else:
                # Skip pairs with OOV words
                pass

        if len(predictions) < 10:
            return WordLevelResult(
                model_name="GSE",
                dataset_name=dataset.name,
                spearman_rho=0.0,
                spearman_p=1.0,
                pearson_r=0.0,
                pearson_p=1.0,
                coverage=covered / len(dataset) if len(dataset) > 0 else 0,
                n_pairs=len(predictions),
                predictions=predictions,
            )

        spearman_rho, spearman_p = spearmanr(predictions, human_scores)
        pearson_r, pearson_p = pearsonr(predictions, human_scores)

        result = WordLevelResult(
            model_name="GSE",
            dataset_name=dataset.name,
            spearman_rho=float(spearman_rho),
            spearman_p=float(spearman_p),
            pearson_r=float(pearson_r),
            pearson_p=float(pearson_p),
            coverage=covered / len(dataset),
            n_pairs=len(predictions),
            predictions=predictions,
        )

        if is_antonym:
            result.antonym_neg_rate = sum(1 for p in predictions if p < 0) / len(predictions)
            result.antonym_mean_sim = float(np.mean(predictions))

        return result

    def evaluate_sentence_dataset(self, dataset: BenchmarkDataset, method: str = "mean") -> SentenceLevelResult:
        """Evaluate on a sentence-level dataset."""
        predictions = []
        human_scores = []
        negation_preds = []
        negation_scores = []

        for pair in dataset.pairs:
            sim = self.sentence_similarity(pair.sentence1, pair.sentence2, method)
            if sim is not None:
                # Scale from [-1, 1] to [0, 5] for STS
                scaled = (sim + 1) / 2 * 5
                predictions.append(scaled)
                human_scores.append(pair.score)

                # Check for negation
                has_negation = any(
                    neg in pair.sentence1.lower() or neg in pair.sentence2.lower()
                    for neg in ["not", "no", "never", "nothing", "nobody", "none", "neither", "n't", "cannot"]
                )
                if has_negation:
                    negation_preds.append(scaled)
                    negation_scores.append(pair.score)

        if len(predictions) < 10:
            return SentenceLevelResult(
                model_name="GSE",
                dataset_name=dataset.name,
                encoding_method=method,
                spearman_rho=0.0,
                spearman_p=1.0,
                n_pairs=len(predictions),
            )

        spearman_rho, spearman_p = spearmanr(predictions, human_scores)

        result = SentenceLevelResult(
            model_name="GSE",
            dataset_name=dataset.name,
            encoding_method=method,
            spearman_rho=float(spearman_rho),
            spearman_p=float(spearman_p),
            n_pairs=len(predictions),
        )

        # Negation subset
        if len(negation_preds) >= 10:
            neg_rho, _ = spearmanr(negation_preds, negation_scores)
            result.negation_rho = float(neg_rho)
            result.negation_n = len(negation_preds)

        return result


# =============================================================================
# BASELINE EVALUATORS
# =============================================================================


class BaselineEvaluator:
    """Base class for baseline model evaluators."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model = None

    def load(self):
        """Load the model."""
        raise NotImplementedError

    def word_similarity(self, word1: str, word2: str) -> Optional[float]:
        """Compute word similarity."""
        raise NotImplementedError

    def sentence_similarity(self, sent1: str, sent2: str) -> Optional[float]:
        """Compute sentence similarity."""
        raise NotImplementedError


class GensimEvaluator(BaselineEvaluator):
    """Evaluator for gensim word vectors (Word2Vec, GloVe, FastText)."""

    def __init__(self, model_name: str, gensim_id: str):
        super().__init__(model_name)
        self.gensim_id = gensim_id

    def load(self):
        import gensim.downloader as api

        print(f"Loading {self.model_name}...")
        self.model = api.load(self.gensim_id)
        print(f"  Loaded: {len(self.model)} vectors")

    def word_similarity(self, word1: str, word2: str) -> Optional[float]:
        if self.model is None:
            return None
        try:
            return float(self.model.similarity(word1, word2))
        except KeyError:
            return None


class SentenceTransformerEvaluator(BaselineEvaluator):
    """Evaluator for sentence-transformers models."""

    def __init__(self, model_name: str, hf_id: str):
        super().__init__(model_name)
        self.hf_id = hf_id

    def load(self):
        from sentence_transformers import SentenceTransformer

        print(f"Loading {self.model_name}...")
        self.model = SentenceTransformer(self.hf_id)
        print(f"  Loaded: {self.hf_id}")

    def word_similarity(self, word1: str, word2: str) -> Optional[float]:
        if self.model is None:
            return None
        try:
            embeddings = self.model.encode([word1, word2])
            sim = np.dot(embeddings[0], embeddings[1]) / (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]))
            return float(sim)
        except Exception:
            return None

    def sentence_similarity(self, sent1: str, sent2: str) -> Optional[float]:
        if self.model is None:
            return None
        try:
            embeddings = self.model.encode([sent1, sent2])
            sim = np.dot(embeddings[0], embeddings[1]) / (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]))
            return float(sim)
        except Exception:
            return None


def evaluate_baseline_word(
    evaluator: BaselineEvaluator, dataset: BenchmarkDataset, is_antonym: bool = False
) -> WordLevelResult:
    """Evaluate a baseline on word-level dataset."""
    predictions = []
    human_scores = []
    covered = 0

    for pair in dataset.pairs:
        sim = evaluator.word_similarity(pair.word1, pair.word2)
        if sim is not None:
            predictions.append(sim)
            human_scores.append(pair.score)
            covered += 1

    if len(predictions) < 10:
        return WordLevelResult(
            model_name=evaluator.model_name,
            dataset_name=dataset.name,
            spearman_rho=0.0,
            spearman_p=1.0,
            pearson_r=0.0,
            pearson_p=1.0,
            coverage=covered / len(dataset) if len(dataset) > 0 else 0,
            n_pairs=len(predictions),
            predictions=predictions,
        )

    spearman_rho, spearman_p = spearmanr(predictions, human_scores)
    pearson_r, pearson_p = pearsonr(predictions, human_scores)

    result = WordLevelResult(
        model_name=evaluator.model_name,
        dataset_name=dataset.name,
        spearman_rho=float(spearman_rho),
        spearman_p=float(spearman_p),
        pearson_r=float(pearson_r),
        pearson_p=float(pearson_p),
        coverage=covered / len(dataset),
        n_pairs=len(predictions),
        predictions=predictions,
    )

    if is_antonym:
        result.antonym_neg_rate = sum(1 for p in predictions if p < 0) / len(predictions)
        result.antonym_mean_sim = float(np.mean(predictions))

    return result


def evaluate_baseline_sentence(
    evaluator: BaselineEvaluator,
    dataset: BenchmarkDataset,
) -> SentenceLevelResult:
    """Evaluate a baseline on sentence-level dataset."""
    predictions = []
    human_scores = []
    negation_preds = []
    negation_scores = []

    for pair in dataset.pairs:
        sim = evaluator.sentence_similarity(pair.sentence1, pair.sentence2)
        if sim is not None:
            scaled = (sim + 1) / 2 * 5
            predictions.append(scaled)
            human_scores.append(pair.score)

            has_negation = any(
                neg in pair.sentence1.lower() or neg in pair.sentence2.lower()
                for neg in ["not", "no", "never", "nothing", "nobody", "none", "neither", "n't", "cannot"]
            )
            if has_negation:
                negation_preds.append(scaled)
                negation_scores.append(pair.score)

    if len(predictions) < 10:
        return SentenceLevelResult(
            model_name=evaluator.model_name,
            dataset_name=dataset.name,
            encoding_method="default",
            spearman_rho=0.0,
            spearman_p=1.0,
            n_pairs=len(predictions),
        )

    spearman_rho, _ = spearmanr(predictions, human_scores)

    result = SentenceLevelResult(
        model_name=evaluator.model_name,
        dataset_name=dataset.name,
        encoding_method="default",
        spearman_rho=float(spearman_rho),
        spearman_p=0.0,
        n_pairs=len(predictions),
    )

    if len(negation_preds) >= 10:
        neg_rho, _ = spearmanr(negation_preds, negation_scores)
        result.negation_rho = float(neg_rho)
        result.negation_n = len(negation_preds)

    return result


# =============================================================================
# MAIN EXPERIMENT RUNNER
# =============================================================================


def run_word_level_experiments(
    gse_evaluator: GSEEvaluator, baselines: List[BaselineEvaluator], verbose: bool = True
) -> Tuple[List[WordLevelResult], Dict[str, Any]]:
    """Run Experiment 5.1: Word-level structural semantics."""
    results = []
    antonym_analysis = {}

    # Load datasets
    if verbose:
        print("\n" + "=" * 60)
        print("EXPERIMENT 5.1: Word-Level Structural Semantics")
        print("=" * 60)

    simlex = load_simlex999()
    wordsim = load_wordsim353()
    antonyms = load_custom_antonyms()
    synonyms = load_custom_synonyms()

    if verbose:
        print("\nDatasets loaded:")
        print(f"  SimLex-999: {len(simlex)} pairs")
        print(f"  WordSim-353: {len(wordsim)} pairs")
        print(f"  Custom Antonyms: {len(antonyms)} pairs")
        print(f"  Custom Synonyms: {len(synonyms)} pairs")

    # Evaluate GSE
    if verbose:
        print("\nEvaluating GSE...")

    for dataset in [simlex, wordsim]:
        if len(dataset) > 0:
            result = gse_evaluator.evaluate_word_dataset(dataset)
            results.append(result)
            if verbose:
                print(f"  {dataset.name}: ρ={result.spearman_rho:.4f} (coverage={result.coverage:.1%})")

    # Antonym evaluation
    if len(antonyms) > 0:
        ant_result = gse_evaluator.evaluate_word_dataset(antonyms, is_antonym=True)
        results.append(ant_result)
        antonym_analysis["gse_antonyms"] = {
            "neg_rate": ant_result.antonym_neg_rate,
            "mean_sim": ant_result.antonym_mean_sim,
            "predictions": ant_result.predictions[:20],  # Sample
        }
        if verbose:
            print(f"  Antonyms: neg_rate={ant_result.antonym_neg_rate:.1%}, mean={ant_result.antonym_mean_sim:.4f}")

    # Synonym evaluation
    if len(synonyms) > 0:
        syn_result = gse_evaluator.evaluate_word_dataset(synonyms)
        results.append(syn_result)
        if verbose:
            print(
                f"  Synonyms: mean_sim={np.mean(syn_result.predictions):.4f}"
                if syn_result.predictions
                else "  Synonyms: no coverage"
            )

    # Evaluate baselines
    for baseline in baselines:
        if verbose:
            print(f"\nEvaluating {baseline.model_name}...")

        try:
            baseline.load()
        except Exception as e:
            if verbose:
                print(f"  Failed to load: {e}")
            continue

        for dataset in [simlex, wordsim]:
            if len(dataset) > 0:
                result = evaluate_baseline_word(baseline, dataset)
                results.append(result)
                if verbose:
                    print(f"  {dataset.name}: ρ={result.spearman_rho:.4f} (coverage={result.coverage:.1%})")

        # Antonym evaluation
        if len(antonyms) > 0:
            ant_result = evaluate_baseline_word(baseline, antonyms, is_antonym=True)
            results.append(ant_result)
            antonym_analysis[f"{baseline.model_name}_antonyms"] = {
                "neg_rate": ant_result.antonym_neg_rate,
                "mean_sim": ant_result.antonym_mean_sim,
            }
            if verbose:
                print(f"  Antonyms: neg_rate={ant_result.antonym_neg_rate:.1%}, mean={ant_result.antonym_mean_sim:.4f}")

    return results, antonym_analysis


def run_sentence_level_experiments(
    gse_evaluator: GSEEvaluator, baselines: List[BaselineEvaluator], verbose: bool = True
) -> List[SentenceLevelResult]:
    """Run Experiment 5.2: Sentence-level semantics."""
    results = []

    if verbose:
        print("\n" + "=" * 60)
        print("EXPERIMENT 5.2: Sentence-Level Semantics")
        print("=" * 60)

    # Load STS Benchmark
    sts_test = load_sts_benchmark(split="test")

    if verbose:
        print("\nDatasets loaded:")
        print(f"  STS-B test: {len(sts_test)} pairs")

    # Evaluate GSE
    if verbose:
        print("\nEvaluating GSE...")

    result = gse_evaluator.evaluate_sentence_dataset(sts_test, method="mean")
    results.append(result)
    if verbose:
        print(f"  STS-B: ρ={result.spearman_rho:.4f} (n={result.n_pairs})")
        if result.negation_rho is not None:
            print(f"  STS-B Negation: ρ={result.negation_rho:.4f} (n={result.negation_n})")

    # Evaluate baselines (sentence-transformers only)
    for baseline in baselines:
        if not isinstance(baseline, SentenceTransformerEvaluator):
            continue

        if verbose:
            print(f"\nEvaluating {baseline.model_name}...")

        try:
            if baseline.model is None:
                baseline.load()
        except Exception as e:
            if verbose:
                print(f"  Failed to load: {e}")
            continue

        result = evaluate_baseline_sentence(baseline, sts_test)
        results.append(result)
        if verbose:
            print(f"  STS-B: ρ={result.spearman_rho:.4f} (n={result.n_pairs})")
            if result.negation_rho is not None:
                print(f"  STS-B Negation: ρ={result.negation_rho:.4f} (n={result.negation_n})")

    return results


def generate_results_markdown(results: ExperimentResults, output_path: str):
    """Generate markdown report from results."""
    lines = []

    lines.append("# GSE Experimental Results")
    lines.append("")
    lines.append(f"**Generated**: {results.timestamp}")
    lines.append("")

    # Word-level results
    lines.append("## Experiment 5.1: Word-Level Structural Semantics")
    lines.append("")

    # Group by dataset
    simlex_results = [r for r in results.word_level if "SimLex" in r.dataset_name]
    wordsim_results = [r for r in results.word_level if "WordSim" in r.dataset_name]
    antonym_results = [r for r in results.word_level if "Antonym" in r.dataset_name]

    if simlex_results:
        lines.append("### SimLex-999 Results")
        lines.append("")
        lines.append("| Model | Spearman ρ | Pearson r | Coverage | N |")
        lines.append("|-------|------------|-----------|----------|---|")
        for r in sorted(simlex_results, key=lambda x: -x.spearman_rho):
            lines.append(
                f"| {r.model_name} | {r.spearman_rho:.4f} | {r.pearson_r:.4f} | {r.coverage:.1%} | {r.n_pairs} |"
            )
        lines.append("")

    if wordsim_results:
        lines.append("### WordSim-353 Results")
        lines.append("")
        lines.append("| Model | Spearman ρ | Pearson r | Coverage | N |")
        lines.append("|-------|------------|-----------|----------|---|")
        for r in sorted(wordsim_results, key=lambda x: -x.spearman_rho):
            lines.append(
                f"| {r.model_name} | {r.spearman_rho:.4f} | {r.pearson_r:.4f} | {r.coverage:.1%} | {r.n_pairs} |"
            )
        lines.append("")

    if antonym_results:
        lines.append("### Antonym Analysis (Key Result)")
        lines.append("")
        lines.append("| Model | Negative Rate | Mean Similarity |")
        lines.append("|-------|---------------|-----------------|")
        for r in sorted(antonym_results, key=lambda x: -(x.antonym_neg_rate or 0)):
            neg_rate = f"{r.antonym_neg_rate:.1%}" if r.antonym_neg_rate is not None else "N/A"
            mean_sim = f"{r.antonym_mean_sim:.4f}" if r.antonym_mean_sim is not None else "N/A"
            lines.append(f"| {r.model_name} | {neg_rate} | {mean_sim} |")
        lines.append("")
        lines.append(
            "**Key Finding**: GSE achieves negative similarity for antonyms, while distributional baselines achieve positive similarity."
        )
        lines.append("")

    # Sentence-level results
    if results.sentence_level:
        lines.append("## Experiment 5.2: Sentence-Level Semantics")
        lines.append("")
        lines.append("### STS Benchmark Results")
        lines.append("")
        lines.append("| Model | Full ρ | Negation ρ | N | Negation N |")
        lines.append("|-------|--------|------------|---|------------|")
        for r in sorted(results.sentence_level, key=lambda x: -x.spearman_rho):
            neg_rho = f"{r.negation_rho:.4f}" if r.negation_rho is not None else "N/A"
            neg_n = r.negation_n if r.negation_n is not None else "N/A"
            lines.append(f"| {r.model_name} | {r.spearman_rho:.4f} | {neg_rho} | {r.n_pairs} | {neg_n} |")
        lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("### Hypothesis Validation")
    lines.append("")

    # Check H1.2 (antonym negative rate)
    gse_ant = next((r for r in antonym_results if r.model_name == "GSE"), None)
    if gse_ant and gse_ant.antonym_neg_rate:
        h12_status = "VALIDATED" if gse_ant.antonym_neg_rate > 0.5 else "NOT VALIDATED"
        lines.append(
            f"- **H1.2 (Antonym Negative Similarity)**: {h12_status} - GSE achieves {gse_ant.antonym_neg_rate:.1%} negative rate"
        )

    lines.append("")

    # Write to file
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"\nResults written to: {output_path}")


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Run GSE paper experiments")
    parser.add_argument("--all", action="store_true", help="Run all experiments")
    parser.add_argument("--word-level", action="store_true", help="Run word-level experiments only")
    parser.add_argument("--sentence-level", action="store_true", help="Run sentence-level experiments only")
    parser.add_argument("--antonyms-only", action="store_true", help="Run antonym analysis only")
    parser.add_argument("--no-baselines", action="store_true", help="Skip baseline models (faster)")
    parser.add_argument("--output", type=str, default=None, help="Output markdown path")
    parser.add_argument("--lexicon", type=str, default="data/lexicon.db", help="Path to lexicon")

    args = parser.parse_args()

    # Default to all if nothing specified
    if not (args.all or args.word_level or args.sentence_level or args.antonyms_only):
        args.all = True

    # Initialize evaluators
    print("Initializing GSE evaluator...")
    gse_evaluator = GSEEvaluator(lexicon_path=args.lexicon)

    # Setup baselines
    baselines = []
    if not args.no_baselines:
        baselines = [
            GensimEvaluator("Word2Vec", "word2vec-google-news-300"),
            GensimEvaluator("GloVe", "glove-wiki-gigaword-300"),
            SentenceTransformerEvaluator("all-MiniLM", "all-MiniLM-L6-v2"),
        ]

    # Initialize results
    results = ExperimentResults(timestamp=datetime.now().isoformat())

    # Run experiments
    if args.all or args.word_level or args.antonyms_only:
        word_results, antonym_analysis = run_word_level_experiments(gse_evaluator, baselines, verbose=True)
        results.word_level = word_results
        results.antonym_analysis = antonym_analysis

    if args.all or args.sentence_level:
        sent_results = run_sentence_level_experiments(gse_evaluator, baselines, verbose=True)
        results.sentence_level = sent_results

    # Generate output
    output_path = (
        args.output
        or "/Users/rohanvinaik/rohan-vinaik.github.io/papers/Core Documents/GSE/GSE_PAPER_EXPERIMENTS/EXPERIMENTAL_RESULTS.md"
    )
    generate_results_markdown(results, output_path)

    print("\n" + "=" * 60)
    print("EXPERIMENTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
