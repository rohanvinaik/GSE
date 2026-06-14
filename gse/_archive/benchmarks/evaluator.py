"""
Unified Benchmark Evaluator

Runs GSE and baseline models against standard benchmarks,
computes metrics, and generates reports.

Key evaluation:
- GSE should achieve NEGATIVE similarity for antonyms
- Distributional approaches (Word2Vec, BERT) give POSITIVE similarity
- This is the core differentiation for the paper
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import json
import logging
import numpy as np
from datetime import datetime

from .datasets import (
    BenchmarkDataset,
    WordPair,
    load_simlex999,
    load_wordsim353,
    load_sts_benchmark,
    load_custom_antonyms,
    load_custom_synonyms,
    get_all_datasets,
)
from .metrics import (
    spearman_correlation,
    correlation_with_ci,
    antonym_metrics,
    discrimination_metrics,
    AntonymMetrics,
    DiscriminationMetrics,
    CorrelationResult,
    per_pos_correlation,
)
from .baselines import BaselineModel, get_all_baselines, get_baseline

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result from a single benchmark evaluation."""
    model_name: str
    dataset_name: str
    correlation: CorrelationResult
    coverage: float  # Fraction of pairs the model could evaluate
    predictions: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AntonymResult:
    """Result from antonym detection evaluation."""
    model_name: str
    metrics: AntonymMetrics
    similarities: List[float] = field(default_factory=list)


@dataclass
class DiscriminationResult:
    """Result from antonym/synonym discrimination."""
    model_name: str
    metrics: DiscriminationMetrics
    antonym_sims: List[float] = field(default_factory=list)
    synonym_sims: List[float] = field(default_factory=list)


@dataclass
class ExperimentReport:
    """Complete experiment report."""
    timestamp: str
    word_similarity_results: Dict[str, Dict[str, BenchmarkResult]]
    antonym_results: Dict[str, AntonymResult]
    discrimination_results: Dict[str, DiscriminationResult]
    bank_analysis: Optional[Dict] = None
    ablations: Optional[Dict] = None


class SemanticBenchmarkRunner:
    """
    Unified benchmark runner for GSE experiments.

    Evaluates GSE against baselines on:
    - Word similarity (SimLex-999, WordSim-353)
    - Antonym detection (negative similarity rate)
    - Antonym/synonym discrimination (AUC)
    - Per-bank analysis
    """

    def __init__(
        self,
        gse_pipeline=None,
        baselines: Optional[Dict[str, BaselineModel]] = None,
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize benchmark runner.

        Args:
            gse_pipeline: GSE pipeline instance. If None, creates new one.
            baselines: Dict of baseline models. If None, loads all available.
            cache_dir: Directory for caching datasets.
        """
        self.gse_pipeline = gse_pipeline
        self.baselines = baselines or {}
        self.cache_dir = cache_dir
        self._datasets_cache: Dict[str, BenchmarkDataset] = {}

        # Initialize GSE if needed
        if self.gse_pipeline is None:
            self._init_gse()

        # Add GSE to baselines for unified evaluation
        if 'gse' not in self.baselines and self.gse_pipeline is not None:
            from .baselines import GSEBaseline
            self.baselines['gse'] = GSEBaseline(self.gse_pipeline)

    def _init_gse(self):
        """Initialize GSE pipeline."""
        try:
            from gse.pipeline import GSEPipeline, GSEConfig
            from pathlib import Path

            # Find data directory
            gse_root = Path(__file__).parent.parent.parent
            data_dir = gse_root / 'data'

            if not data_dir.exists():
                # Try alternate location
                data_dir = Path.home() / '.gse' / 'data'

            lexicon_path = data_dir / 'lexicon.db'
            basis_path = data_dir / 'basis.msgpack'

            if not lexicon_path.exists() or not basis_path.exists():
                logger.warning(f"GSE data not found at {data_dir}")
                self.gse_pipeline = None
                return

            logger.info("Initializing GSE pipeline")
            config = GSEConfig(
                lexicon_path=str(lexicon_path),
                basis_path=str(basis_path),
            )
            self.gse_pipeline = GSEPipeline(config)

        except Exception as e:
            logger.warning(f"Could not initialize GSE: {e}")
            self.gse_pipeline = None

    def load_baselines(self, model_names: Optional[List[str]] = None):
        """
        Load baseline models for comparison.

        Args:
            model_names: List of model names to load.
                         If None, loads all available.
        """
        if model_names is None:
            self.baselines = get_all_baselines()
        else:
            for name in model_names:
                model = get_baseline(name)
                if model is not None:
                    self.baselines[name] = model

        logger.info(f"Loaded baselines: {list(self.baselines.keys())}")

    def _get_dataset(self, dataset_name: str) -> BenchmarkDataset:
        """Get or load a dataset with caching."""
        if dataset_name not in self._datasets_cache:
            if dataset_name == 'simlex999':
                self._datasets_cache[dataset_name] = load_simlex999(self.cache_dir)
            elif dataset_name == 'wordsim353':
                self._datasets_cache[dataset_name] = load_wordsim353(self.cache_dir)
            elif dataset_name.startswith('sts'):
                split = dataset_name.replace('sts_', '') if '_' in dataset_name else 'test'
                self._datasets_cache[dataset_name] = load_sts_benchmark(split, self.cache_dir)
            elif dataset_name == 'antonyms':
                self._datasets_cache[dataset_name] = load_custom_antonyms()
            elif dataset_name == 'synonyms':
                self._datasets_cache[dataset_name] = load_custom_synonyms()
            else:
                raise ValueError(f"Unknown dataset: {dataset_name}")

        return self._datasets_cache[dataset_name]

    def run_word_similarity(
        self,
        dataset_name: str,
        model_names: Optional[List[str]] = None,
    ) -> Dict[str, BenchmarkResult]:
        """
        Run word similarity evaluation on specified dataset.

        Args:
            dataset_name: Name of dataset (simlex999, wordsim353)
            model_names: Models to evaluate. If None, evaluates all loaded.

        Returns:
            Dict of model_name -> BenchmarkResult
        """
        dataset = self._get_dataset(dataset_name)
        models = self._select_models(model_names)

        logger.info(f"Running word similarity on {dataset_name} ({len(dataset)} pairs)")

        results = {}
        human_scores = dataset.get_scores()

        for name, model in models.items():
            logger.info(f"Evaluating {name}...")

            predictions = []
            valid_indices = []

            for i, pair in enumerate(dataset.pairs):
                try:
                    sim = model.similarity(pair.word1, pair.word2)
                    if not np.isnan(sim):
                        predictions.append(sim)
                        valid_indices.append(i)
                except Exception as e:
                    logger.debug(f"{name} failed on ({pair.word1}, {pair.word2}): {e}")

            if not predictions:
                logger.warning(f"{name} could not evaluate any pairs")
                continue

            # Get corresponding human scores
            valid_human = [human_scores[i] for i in valid_indices]

            # Compute correlation with CI
            corr = correlation_with_ci(predictions, valid_human)
            coverage = len(predictions) / len(dataset)

            results[name] = BenchmarkResult(
                model_name=name,
                dataset_name=dataset_name,
                correlation=corr,
                coverage=coverage,
                predictions=predictions,
                metadata={
                    'n_evaluated': len(predictions),
                    'n_total': len(dataset),
                }
            )

            logger.info(
                f"  {name}: rho={corr.rho:.4f} "
                f"[{corr.ci_low:.4f}, {corr.ci_high:.4f}] "
                f"coverage={coverage:.2%}"
            )

        return results

    def run_antonym_detection(
        self,
        model_names: Optional[List[str]] = None,
    ) -> Dict[str, AntonymResult]:
        """
        Run antonym detection evaluation.

        This is the KEY metric for the GSE paper:
        - GSE should achieve >80% NEGATIVE similarity for antonyms
        - Distributional approaches achieve ~0% negative

        Args:
            model_names: Models to evaluate. If None, evaluates all.

        Returns:
            Dict of model_name -> AntonymResult
        """
        antonym_dataset = self._get_dataset('antonyms')
        models = self._select_models(model_names)

        logger.info(f"Running antonym detection ({len(antonym_dataset)} pairs)")
        logger.info("Target: GSE should achieve >80% negative similarity rate")

        results = {}

        for name, model in models.items():
            logger.info(f"Evaluating {name}...")

            similarities = []
            for pair in antonym_dataset.pairs:
                try:
                    sim = model.similarity(pair.word1, pair.word2)
                    if not np.isnan(sim):
                        similarities.append(sim)
                except Exception as e:
                    logger.debug(f"{name} failed on ({pair.word1}, {pair.word2}): {e}")

            if not similarities:
                logger.warning(f"{name} could not evaluate any antonym pairs")
                continue

            metrics = antonym_metrics(similarities)

            results[name] = AntonymResult(
                model_name=name,
                metrics=metrics,
                similarities=similarities,
            )

            logger.info(
                f"  {name}: negative_rate={metrics.negative_rate:.2%} "
                f"mean_sim={metrics.mean_similarity:.4f}"
            )

        return results

    def run_discrimination(
        self,
        model_names: Optional[List[str]] = None,
    ) -> Dict[str, DiscriminationResult]:
        """
        Run antonym/synonym discrimination evaluation.

        Tests how well each model separates antonyms from synonyms
        using similarity alone.

        Args:
            model_names: Models to evaluate.

        Returns:
            Dict of model_name -> DiscriminationResult
        """
        antonym_dataset = self._get_dataset('antonyms')
        synonym_dataset = self._get_dataset('synonyms')
        models = self._select_models(model_names)

        logger.info(
            f"Running discrimination "
            f"({len(antonym_dataset)} antonyms, {len(synonym_dataset)} synonyms)"
        )

        results = {}

        for name, model in models.items():
            logger.info(f"Evaluating {name}...")

            antonym_sims = []
            for pair in antonym_dataset.pairs:
                try:
                    sim = model.similarity(pair.word1, pair.word2)
                    if not np.isnan(sim):
                        antonym_sims.append(sim)
                except Exception:
                    pass

            synonym_sims = []
            for pair in synonym_dataset.pairs:
                try:
                    sim = model.similarity(pair.word1, pair.word2)
                    if not np.isnan(sim):
                        synonym_sims.append(sim)
                except Exception:
                    pass

            if not antonym_sims or not synonym_sims:
                logger.warning(f"{name} could not evaluate pairs")
                continue

            metrics = discrimination_metrics(antonym_sims, synonym_sims)

            results[name] = DiscriminationResult(
                model_name=name,
                metrics=metrics,
                antonym_sims=antonym_sims,
                synonym_sims=synonym_sims,
            )

            logger.info(
                f"  {name}: AUC={metrics.auc:.4f} "
                f"accuracy={metrics.accuracy:.2%} "
                f"separation={metrics.separation:.2f}"
            )

        return results

    def run_bank_analysis(
        self,
        dataset_name: str,
    ) -> Dict[str, Dict[str, float]]:
        """
        Analyze per-bank correlation for GSE.

        This shows which semantic banks contribute most to
        performance on different benchmarks.

        Args:
            dataset_name: Dataset to analyze.

        Returns:
            Dict of bank_name -> {rho, p_value, n}
        """
        if self.gse_pipeline is None:
            logger.warning("GSE not available for bank analysis")
            return {}

        dataset = self._get_dataset(dataset_name)
        human_scores = dataset.get_scores()

        logger.info(f"Running bank analysis on {dataset_name}")

        # Get bank names from GSE
        from gse.primitives import SemanticBank
        bank_names = [b.name for b in SemanticBank]

        # Compute per-bank similarities
        bank_similarities: Dict[str, List[float]] = {b: [] for b in bank_names}
        valid_human = []

        BANK_SIZE = 1024

        for pair in dataset.pairs:
            try:
                # Get full vectors
                result1 = self.gse_pipeline.process(pair.word1)
                result2 = self.gse_pipeline.process(pair.word2)

                if result1 is None or result2 is None:
                    continue

                v1 = result1.vector.to_dense() if hasattr(result1.vector, 'to_dense') else np.array(result1.vector)
                v2 = result2.vector.to_dense() if hasattr(result2.vector, 'to_dense') else np.array(result2.vector)

                # Compute per-bank cosine similarity
                for i, bank_name in enumerate(bank_names):
                    start = i * BANK_SIZE
                    end = (i + 1) * BANK_SIZE
                    b1 = v1[start:end]
                    b2 = v2[start:end]

                    norm1 = np.linalg.norm(b1)
                    norm2 = np.linalg.norm(b2)

                    if norm1 > 0 and norm2 > 0:
                        sim = np.dot(b1, b2) / (norm1 * norm2)
                        bank_similarities[bank_name].append(sim)
                    else:
                        bank_similarities[bank_name].append(0.0)

                valid_human.append(pair.score)

            except Exception as e:
                logger.debug(f"Bank analysis failed for ({pair.word1}, {pair.word2}): {e}")

        # Compute correlations for each bank
        results = {}
        for bank_name, sims in bank_similarities.items():
            if len(sims) >= 10:
                rho, p = spearman_correlation(sims, valid_human)
                results[bank_name] = {
                    'rho': rho,
                    'p_value': p,
                    'n': len(sims),
                }
                logger.info(f"  {bank_name}: rho={rho:.4f} (p={p:.4f})")

        return results

    def run_ablation_study(
        self,
        dataset_name: str = 'simlex999',
    ) -> Dict[str, BenchmarkResult]:
        """
        Run ablation study on GSE components.

        Tests:
        - Full GSE (baseline)
        - No polarity propagation
        - Random bank assignment
        - Reduced primitives

        Args:
            dataset_name: Dataset for ablation.

        Returns:
            Dict of ablation_name -> BenchmarkResult
        """
        logger.info(f"Running ablation study on {dataset_name}")
        # This requires modifying GSE internals - stub for now
        # Full implementation would involve:
        # 1. Creating modified GSE pipelines
        # 2. Running each variant
        # 3. Comparing results

        results = {}
        logger.warning("Ablation study not yet fully implemented")
        return results

    def run_full_evaluation(
        self,
        datasets: List[str] = ['simlex999', 'wordsim353'],
        model_names: Optional[List[str]] = None,
    ) -> ExperimentReport:
        """
        Run complete evaluation suite.

        Args:
            datasets: Word similarity datasets to evaluate.
            model_names: Models to include.

        Returns:
            ExperimentReport with all results.
        """
        logger.info("=" * 60)
        logger.info("Running full GSE benchmark evaluation")
        logger.info("=" * 60)

        # Word similarity
        word_sim_results = {}
        for dataset in datasets:
            word_sim_results[dataset] = self.run_word_similarity(dataset, model_names)

        # Antonym detection
        antonym_results = self.run_antonym_detection(model_names)

        # Discrimination
        discrimination_results = self.run_discrimination(model_names)

        # Bank analysis (GSE only)
        bank_analysis = {}
        if self.gse_pipeline is not None:
            for dataset in datasets:
                bank_analysis[dataset] = self.run_bank_analysis(dataset)

        return ExperimentReport(
            timestamp=datetime.now().isoformat(),
            word_similarity_results=word_sim_results,
            antonym_results=antonym_results,
            discrimination_results=discrimination_results,
            bank_analysis=bank_analysis,
        )

    def _select_models(
        self,
        model_names: Optional[List[str]]
    ) -> Dict[str, BaselineModel]:
        """Select models for evaluation."""
        if model_names is None:
            return self.baselines
        return {n: self.baselines[n] for n in model_names if n in self.baselines}

    def generate_report(
        self,
        report: ExperimentReport,
        output_path: Optional[Path] = None,
    ) -> str:
        """
        Generate markdown report from experiment results.

        Args:
            report: ExperimentReport from run_full_evaluation.
            output_path: If provided, saves report to file.

        Returns:
            Markdown formatted report string.
        """
        lines = [
            "# GSE Benchmark Evaluation Report",
            f"\nGenerated: {report.timestamp}",
            "\n---\n",
        ]

        # Word Similarity Results
        lines.append("## Word Similarity Benchmarks\n")
        for dataset_name, results in report.word_similarity_results.items():
            lines.append(f"### {dataset_name}\n")
            lines.append("| Model | Spearman ρ | 95% CI | Coverage |")
            lines.append("|-------|-----------|--------|----------|")

            # Sort by correlation
            sorted_results = sorted(
                results.values(),
                key=lambda r: r.correlation.rho,
                reverse=True
            )

            for result in sorted_results:
                corr = result.correlation
                lines.append(
                    f"| {result.model_name} | {corr.rho:.4f} | "
                    f"[{corr.ci_low:.4f}, {corr.ci_high:.4f}] | "
                    f"{result.coverage:.1%} |"
                )
            lines.append("")

        # Antonym Detection Results
        lines.append("## Antonym Detection (Key GSE Differentiator)\n")
        lines.append(
            "**Target:** GSE should achieve >80% negative similarity rate "
            "for antonyms.\n"
        )
        lines.append(
            "**Baseline expectation:** Distributional models (Word2Vec, BERT) "
            "achieve ~0% because antonyms appear in similar contexts.\n"
        )
        lines.append("| Model | Negative Rate | Mean Sim | Median Sim |")
        lines.append("|-------|--------------|----------|------------|")

        for name, result in sorted(
            report.antonym_results.items(),
            key=lambda x: x[1].metrics.negative_rate,
            reverse=True
        ):
            m = result.metrics
            lines.append(
                f"| {name} | {m.negative_rate:.1%} | "
                f"{m.mean_similarity:.4f} | {m.median_similarity:.4f} |"
            )
        lines.append("")

        # Discrimination Results
        lines.append("## Antonym/Synonym Discrimination\n")
        lines.append("| Model | AUC | Accuracy | Cohen's d |")
        lines.append("|-------|-----|----------|-----------|")

        for name, result in sorted(
            report.discrimination_results.items(),
            key=lambda x: x[1].metrics.auc,
            reverse=True
        ):
            m = result.metrics
            lines.append(
                f"| {name} | {m.auc:.4f} | {m.accuracy:.1%} | {m.separation:.2f} |"
            )
        lines.append("")

        # Bank Analysis
        if report.bank_analysis:
            lines.append("## Per-Bank Analysis (GSE Only)\n")
            for dataset_name, banks in report.bank_analysis.items():
                lines.append(f"### {dataset_name}\n")
                lines.append("| Bank | Spearman ρ | p-value |")
                lines.append("|------|-----------|---------|")

                for bank_name, stats in sorted(
                    banks.items(),
                    key=lambda x: x[1]['rho'],
                    reverse=True
                ):
                    lines.append(
                        f"| {bank_name} | {stats['rho']:.4f} | {stats['p_value']:.4f} |"
                    )
                lines.append("")

        # Summary
        lines.append("## Summary\n")
        lines.append("### Key Findings\n")

        # Check if GSE outperforms on antonym detection
        if 'gse' in report.antonym_results:
            gse_neg_rate = report.antonym_results['gse'].metrics.negative_rate
            lines.append(
                f"- **GSE Antonym Negative Rate:** {gse_neg_rate:.1%}\n"
            )
            if gse_neg_rate > 0.8:
                lines.append(
                    "  - Confirms emergent antonymy through polarity propagation\n"
                )

        # Check discrimination
        if 'gse' in report.discrimination_results:
            gse_auc = report.discrimination_results['gse'].metrics.auc
            lines.append(f"- **GSE Discrimination AUC:** {gse_auc:.4f}\n")

        report_text = "\n".join(lines)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(report_text)
            logger.info(f"Report saved to {output_path}")

        return report_text

    def save_results_json(
        self,
        report: ExperimentReport,
        output_path: Path,
    ):
        """Save results as JSON for further analysis."""

        def serialize_result(obj):
            if hasattr(obj, '__dict__'):
                return {k: serialize_result(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, list):
                return [serialize_result(v) for v in obj]
            elif isinstance(obj, dict):
                return {k: serialize_result(v) for k, v in obj.items()}
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, (np.float32, np.float64)):
                return float(obj)
            else:
                return obj

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(serialize_result(report), f, indent=2)
        logger.info(f"Results saved to {output_path}")


def run_experiment_1(
    output_dir: Path = Path('results/exp1'),
    models: Optional[List[str]] = None,
) -> ExperimentReport:
    """
    Run Experiment 1: Structural Semantic Evaluation.

    This is the main experiment from the GSE paper comparing
    GSE against distributional baselines on:
    - SimLex-999 (word similarity)
    - WordSim-353 (word relatedness)
    - Custom antonym detection

    Args:
        output_dir: Directory for results.
        models: Specific models to evaluate.

    Returns:
        ExperimentReport with full results.
    """
    logger.info("=" * 60)
    logger.info("EXPERIMENT 1: Structural Semantic Evaluation")
    logger.info("=" * 60)

    # Initialize runner
    runner = SemanticBenchmarkRunner()

    # Load baselines
    if models:
        runner.load_baselines(models)
    else:
        runner.load_baselines()

    # Run evaluation
    report = runner.run_full_evaluation(
        datasets=['simlex999', 'wordsim353'],
        model_names=models,
    )

    # Generate outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    markdown_report = runner.generate_report(
        report,
        output_dir / 'exp1_report.md'
    )

    runner.save_results_json(report, output_dir / 'exp1_results.json')

    # Print summary
    print("\n" + "=" * 60)
    print("EXPERIMENT 1 RESULTS SUMMARY")
    print("=" * 60)
    print(markdown_report)

    return report


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='GSE Benchmark Evaluation')
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path('results/exp1'),
        help='Output directory'
    )
    parser.add_argument(
        '--models', '-m',
        nargs='+',
        help='Models to evaluate (default: all)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose logging'
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    run_experiment_1(args.output, args.models)
