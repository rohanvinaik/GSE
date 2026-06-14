"""
Semantic Data Curator

Selects high-value training data based on GSE cognitive complexity scores.
Implements various curation strategies for comparison:

1. Random: Baseline random selection
2. Perplexity: Inverse perplexity (Rho-1 style)
3. GSE Complexity: Our method - select multi-bank activation
4. Combined: GSE + perplexity hybrid

The key hypothesis is that GSE complexity is a better proxy for
"useful" training data than perplexity alone.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Callable
from pathlib import Path
from enum import Enum
import json
import random
import logging
import numpy as np

from .corpus_scorer import DocumentScore, load_scored_corpus

logger = logging.getLogger(__name__)


class CurationMethod(Enum):
    """Available curation methods."""
    RANDOM = "random"
    PERPLEXITY = "perplexity"
    GSE_COMPLEXITY = "gse_complexity"
    GSE_PERPLEXITY = "gse_perplexity"
    GSE_DIVERSITY = "gse_diversity"


@dataclass
class CurationResult:
    """Result of data curation."""
    method: str
    target_fraction: float
    n_selected: int
    n_total: int
    avg_complexity: float
    avg_perplexity: Optional[float]
    documents: List[DocumentScore]

    def to_summary(self) -> Dict:
        return {
            'method': self.method,
            'target_fraction': self.target_fraction,
            'n_selected': self.n_selected,
            'n_total': self.n_total,
            'actual_fraction': self.n_selected / self.n_total if self.n_total > 0 else 0,
            'avg_complexity': self.avg_complexity,
            'avg_perplexity': self.avg_perplexity,
        }


class SemanticCurator:
    """
    Curates training data based on semantic complexity.

    The core insight is that cognitively complex text (activating
    multiple GSE banks) leads to more efficient model learning.
    """

    def __init__(
        self,
        target_fraction: float = 0.01,
        diversity_weight: float = 0.3,
        seed: int = 42,
    ):
        """
        Initialize curator.

        Args:
            target_fraction: Fraction of corpus to select (e.g., 0.01 = 1%)
            diversity_weight: Weight for bank diversity in combined scoring
            seed: Random seed for reproducibility
        """
        self.target_fraction = target_fraction
        self.diversity_weight = diversity_weight
        self.seed = seed
        self._rng = random.Random(seed)

    def curate(
        self,
        scored_corpus: List[DocumentScore],
        method: CurationMethod = CurationMethod.GSE_COMPLEXITY,
        custom_scorer: Optional[Callable[[DocumentScore], float]] = None,
    ) -> CurationResult:
        """
        Select documents from scored corpus.

        Args:
            scored_corpus: List of DocumentScore objects
            method: Curation method to use
            custom_scorer: Optional custom scoring function

        Returns:
            CurationResult with selected documents
        """
        n_total = len(scored_corpus)
        n_select = max(1, int(n_total * self.target_fraction))

        logger.info(
            f"Curating {n_select}/{n_total} documents "
            f"({self.target_fraction:.1%}) using {method.value}"
        )

        if method == CurationMethod.RANDOM:
            selected = self._select_random(scored_corpus, n_select)
        elif method == CurationMethod.PERPLEXITY:
            selected = self._select_by_perplexity(scored_corpus, n_select)
        elif method == CurationMethod.GSE_COMPLEXITY:
            selected = self._select_by_complexity(scored_corpus, n_select)
        elif method == CurationMethod.GSE_PERPLEXITY:
            selected = self._select_combined(scored_corpus, n_select)
        elif method == CurationMethod.GSE_DIVERSITY:
            selected = self._select_diverse(scored_corpus, n_select)
        elif custom_scorer is not None:
            selected = self._select_by_custom(scored_corpus, n_select, custom_scorer)
        else:
            raise ValueError(f"Unknown method: {method}")

        # Compute statistics
        complexities = [
            d.complexity.get('composite', 0) for d in selected
        ]
        perplexities = [
            d.perplexity for d in selected if d.perplexity is not None
        ]

        result = CurationResult(
            method=method.value,
            target_fraction=self.target_fraction,
            n_selected=len(selected),
            n_total=n_total,
            avg_complexity=float(np.mean(complexities)) if complexities else 0,
            avg_perplexity=float(np.mean(perplexities)) if perplexities else None,
            documents=selected,
        )

        logger.info(
            f"Selected {result.n_selected} documents, "
            f"avg complexity: {result.avg_complexity:.4f}"
        )

        return result

    def _select_random(
        self,
        corpus: List[DocumentScore],
        n: int,
    ) -> List[DocumentScore]:
        """Random baseline selection."""
        return self._rng.sample(corpus, min(n, len(corpus)))

    def _select_by_perplexity(
        self,
        corpus: List[DocumentScore],
        n: int,
    ) -> List[DocumentScore]:
        """
        Select by inverse perplexity (Rho-1 style).

        Lower perplexity = more predictable = potentially less useful?
        Or: Lower perplexity = cleaner data = better for learning?

        We use INVERSE perplexity (1/ppl) so higher is better.
        """
        # Filter documents with perplexity scores
        with_ppl = [d for d in corpus if d.perplexity is not None]

        if not with_ppl:
            logger.warning("No perplexity scores available, using random")
            return self._select_random(corpus, n)

        # Sort by inverse perplexity (lowest perplexity first)
        # This matches Rho-1's approach of selecting "easy" examples
        sorted_corpus = sorted(with_ppl, key=lambda d: d.perplexity)

        return sorted_corpus[:n]

    def _select_by_complexity(
        self,
        corpus: List[DocumentScore],
        n: int,
    ) -> List[DocumentScore]:
        """
        Select by GSE cognitive complexity.

        Our core hypothesis: Higher complexity = more valuable for training
        """
        # Sort by composite complexity (already sorted in corpus_scorer, but ensure)
        sorted_corpus = sorted(
            corpus,
            key=lambda d: d.complexity.get('composite', 0),
            reverse=True
        )

        return sorted_corpus[:n]

    def _select_combined(
        self,
        corpus: List[DocumentScore],
        n: int,
        complexity_weight: float = 0.5,
    ) -> List[DocumentScore]:
        """
        Select by combined GSE complexity + inverse perplexity.

        Combines semantic complexity with language model confidence.
        """
        # Compute combined scores
        scored = []
        for doc in corpus:
            gse_score = doc.complexity.get('composite', 0)

            # Normalize perplexity to [0, 1] using sigmoid
            if doc.perplexity is not None:
                # Lower perplexity = higher score
                ppl_score = 1.0 / (1.0 + doc.perplexity / 100)
            else:
                ppl_score = 0.5  # Neutral if missing

            combined = complexity_weight * gse_score + (1 - complexity_weight) * ppl_score
            scored.append((doc, combined))

        # Sort by combined score
        scored.sort(key=lambda x: x[1], reverse=True)

        return [doc for doc, _ in scored[:n]]

    def _select_diverse(
        self,
        corpus: List[DocumentScore],
        n: int,
    ) -> List[DocumentScore]:
        """
        Select with bank diversity constraint.

        Ensures selected documents cover all semantic banks,
        not just a few high-complexity outliers.
        """
        # First, select top candidates by complexity
        candidates = sorted(
            corpus,
            key=lambda d: d.complexity.get('composite', 0),
            reverse=True
        )[:n * 3]  # Consider 3x candidates

        # Track bank coverage
        bank_coverage = {bank: 0 for bank in [
            "SUBSTANTIVES", "DETERMINERS", "EVALUATORS", "MENTAL",
            "ACTION", "TEMPORAL", "SPATIAL", "LOGICAL"
        ]}

        selected = []
        for doc in candidates:
            if len(selected) >= n:
                break

            # Score based on complexity + filling coverage gaps
            profile = doc.complexity.get('bank_profile', [0] * 8)
            dominant = doc.complexity.get('dominant_banks', [])

            # Bonus for underrepresented banks
            coverage_bonus = 0
            for bank in dominant:
                if bank in bank_coverage:
                    # More bonus if bank is underrepresented
                    coverage_bonus += 1.0 / (1 + bank_coverage[bank])

            # Combined score
            score = (
                (1 - self.diversity_weight) * doc.complexity.get('composite', 0) +
                self.diversity_weight * coverage_bonus / 3  # Normalize by max 3 dominant banks
            )

            # Select if good score
            selected.append((doc, score))

            # Update coverage
            for bank in dominant:
                if bank in bank_coverage:
                    bank_coverage[bank] += 1

        # Final sort by score
        selected.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in selected[:n]]

    def _select_by_custom(
        self,
        corpus: List[DocumentScore],
        n: int,
        scorer: Callable[[DocumentScore], float],
    ) -> List[DocumentScore]:
        """Select by custom scoring function."""
        scored = [(doc, scorer(doc)) for doc in corpus]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in scored[:n]]

    def curate_from_file(
        self,
        scored_path: Path,
        output_path: Path,
        method: CurationMethod = CurationMethod.GSE_COMPLEXITY,
    ) -> CurationResult:
        """
        Curate from a pre-scored corpus file.

        Args:
            scored_path: Path to scored corpus JSONL
            output_path: Path to save curated documents
            method: Curation method

        Returns:
            CurationResult
        """
        # Load scored corpus
        corpus = load_scored_corpus(scored_path)
        logger.info(f"Loaded {len(corpus)} scored documents")

        # Curate
        result = self.curate(corpus, method)

        # Save curated documents
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            for doc in result.documents:
                f.write(json.dumps(doc.to_dict()) + '\n')

        # Save summary
        summary_path = output_path.with_suffix('.summary.json')
        with open(summary_path, 'w') as f:
            json.dump(result.to_summary(), f, indent=2)

        logger.info(f"Saved curated corpus to {output_path}")

        return result


def run_curation_comparison(
    scored_corpus_path: Path,
    output_dir: Path,
    fractions: List[float] = [0.01, 0.05, 0.10],
) -> Dict[str, Dict[str, CurationResult]]:
    """
    Run all curation methods for comparison.

    This generates datasets for Experiment 3, comparing:
    - Random baseline
    - Perplexity-based (Rho-1 style)
    - GSE complexity
    - Combined GSE + perplexity

    Args:
        scored_corpus_path: Path to pre-scored corpus
        output_dir: Directory for curated datasets
        fractions: Target fractions to test

    Returns:
        Nested dict of fraction -> method -> CurationResult
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load corpus once
    corpus = load_scored_corpus(scored_corpus_path)
    logger.info(f"Loaded {len(corpus)} documents for curation comparison")

    results = {}

    for fraction in fractions:
        fraction_key = f"{int(fraction * 100)}pct"
        results[fraction_key] = {}

        curator = SemanticCurator(target_fraction=fraction)

        for method in CurationMethod:
            logger.info(f"Running {method.value} @ {fraction:.0%}")

            result = curator.curate(corpus, method)

            # Save curated dataset
            output_path = output_dir / f"{method.value}_{fraction_key}.jsonl"
            with open(output_path, 'w', encoding='utf-8') as f:
                for doc in result.documents:
                    f.write(json.dumps(doc.to_dict()) + '\n')

            results[fraction_key][method.value] = result

    # Save comparison summary
    summary = {
        frac: {
            method: result.to_summary()
            for method, result in methods.items()
        }
        for frac, methods in results.items()
    }

    with open(output_dir / 'curation_comparison.json', 'w') as f:
        json.dump(summary, f, indent=2)

    return results
