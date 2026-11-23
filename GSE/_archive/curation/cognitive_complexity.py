"""
Cognitive Complexity Scoring

Measures the cognitive complexity of text based on GSE semantic bank activations.

Key insight: Text that requires integration across multiple semantic banks
(e.g., temporal + causal + mental) is more "cognitively complex" and
potentially more valuable for model training.

This is the core metric for Experiment 3, providing an alternative to
perplexity-based data selection (as in Rho-1).

Advantages over perplexity:
1. Interpretable: We know WHY text scored high (which banks activated)
2. Verifiable: Merkle proofs provide cryptographic verification
3. Deterministic: Same input always produces same score
4. Efficient: CPU-only, ~2,272 parameters, <1ms per sentence
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Bank configuration
BANK_SIZE = 1024
NUM_BANKS = 8
TOTAL_DIM = BANK_SIZE * NUM_BANKS  # 8192

# Bank names from GSE primitives
BANK_NAMES = [
    "SUBSTANTIVES",
    "DETERMINERS",
    "EVALUATORS",
    "MENTAL",
    "ACTION",
    "TEMPORAL",
    "SPATIAL",
    "LOGICAL",
]

# Thresholds (tunable hyperparameters)
DEFAULT_ACTIVATION_THRESHOLD = 0.1
DEFAULT_COMPLEXITY_WEIGHTS = {
    'n_active': 0.4,
    'entropy': 0.3,
    'cross_bank': 0.3,
}


@dataclass
class CognitiveComplexityScore:
    """
    Comprehensive cognitive complexity metrics for a piece of text.

    Attributes:
        n_active_banks: Number of banks with significant activation (0-8)
        activation_entropy: Uniformity of bank activation (0-1, 1=uniform)
        cross_bank_score: Interaction/co-activation between banks (0-1)
        composite: Weighted combination of all metrics (0-1)
        bank_profile: Per-bank activation strengths (list of 8 floats)
        dominant_banks: Names of most active banks
    """
    n_active_banks: int
    activation_entropy: float
    cross_bank_score: float
    composite: float
    bank_profile: List[float]
    dominant_banks: List[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'n_active_banks': self.n_active_banks,
            'activation_entropy': self.activation_entropy,
            'cross_bank_score': self.cross_bank_score,
            'composite': self.composite,
            'bank_profile': self.bank_profile,
            'dominant_banks': self.dominant_banks,
        }


def compute_bank_activations(vector: np.ndarray) -> List[float]:
    """
    Compute activation strength for each semantic bank.

    Args:
        vector: GSE vector (8192-D dense or sparse representation)

    Returns:
        List of 8 activation values (one per bank)
    """
    if len(vector) != TOTAL_DIM:
        logger.warning(f"Expected {TOTAL_DIM}-D vector, got {len(vector)}-D")
        # Pad or truncate
        if len(vector) < TOTAL_DIM:
            vector = np.pad(vector, (0, TOTAL_DIM - len(vector)))
        else:
            vector = vector[:TOTAL_DIM]

    activations = []
    for bank_idx in range(NUM_BANKS):
        start = bank_idx * BANK_SIZE
        end = (bank_idx + 1) * BANK_SIZE
        bank_slice = vector[start:end]

        # Activation = L2 norm of bank region
        activation = float(np.linalg.norm(bank_slice))
        activations.append(activation)

    return activations


def compute_activation_entropy(activations: List[float]) -> float:
    """
    Compute normalized entropy of bank activations.

    Higher entropy = more uniform activation across banks
    Lower entropy = concentrated in few banks

    Args:
        activations: List of bank activation values

    Returns:
        Normalized entropy in [0, 1] (1 = perfectly uniform)
    """
    total = sum(activations)
    if total == 0:
        return 0.0

    # Normalize to probability distribution
    probs = [a / total for a in activations]

    # Compute entropy
    entropy = 0.0
    for p in probs:
        if p > 0:
            entropy -= p * np.log(p)

    # Normalize by max entropy (log(N) for uniform distribution)
    max_entropy = np.log(NUM_BANKS)
    if max_entropy == 0:
        return 0.0

    return float(entropy / max_entropy)


def compute_cross_bank_interaction(vector: np.ndarray) -> float:
    """
    Measure interaction/co-activation patterns between banks.

    High score indicates unusual combinations of bank activations,
    suggesting text that requires integrating multiple semantic dimensions.

    This is inspired by ARC's PrimitivePatternNetwork.get_cross_bank_info().

    Args:
        vector: GSE vector (8192-D)

    Returns:
        Cross-bank interaction score in [0, 1]
    """
    activations = compute_bank_activations(vector)

    # Compute pairwise co-activation
    co_activation = 0.0
    n_pairs = 0

    for i in range(NUM_BANKS):
        for j in range(i + 1, NUM_BANKS):
            # Co-activation = geometric mean of normalized activations
            a_i = activations[i]
            a_j = activations[j]

            if a_i > 0 and a_j > 0:
                # Normalize by max possible activation
                max_activation = max(activations) if max(activations) > 0 else 1.0
                norm_i = a_i / max_activation
                norm_j = a_j / max_activation

                # Geometric mean captures co-occurrence
                co_activation += np.sqrt(norm_i * norm_j)

            n_pairs += 1

    if n_pairs == 0:
        return 0.0

    # Normalize by number of pairs
    return float(co_activation / n_pairs)


def compute_cognitive_complexity(
    text: str,
    gse_pipeline,
    activation_threshold: float = DEFAULT_ACTIVATION_THRESHOLD,
    weights: Optional[Dict[str, float]] = None,
) -> CognitiveComplexityScore:
    """
    Compute cognitive complexity score for a piece of text.

    This is the core metric for GSE-based data curation.
    High complexity text activates multiple semantic banks
    and requires integrating different types of meaning.

    Args:
        text: Input text to score
        gse_pipeline: GSE pipeline instance
        activation_threshold: Minimum activation to count bank as "active"
        weights: Weights for composite score components

    Returns:
        CognitiveComplexityScore with detailed metrics
    """
    if weights is None:
        weights = DEFAULT_COMPLEXITY_WEIGHTS

    # Process through GSE
    try:
        result = gse_pipeline.process(text)
        if result is None:
            logger.warning(f"GSE returned None for text: {text[:50]}...")
            return _empty_score()

        # Get dense vector
        if hasattr(result.vector, 'to_dense'):
            vector = result.vector.to_dense()
        else:
            vector = np.array(result.vector)

    except Exception as e:
        logger.warning(f"GSE processing failed: {e}")
        return _empty_score()

    # Compute bank activations
    activations = compute_bank_activations(vector)

    # Count active banks
    n_active = sum(1 for a in activations if a > activation_threshold)

    # Compute entropy
    entropy = compute_activation_entropy(activations)

    # Compute cross-bank interaction
    cross_bank = compute_cross_bank_interaction(vector)

    # Compute composite score
    composite = (
        weights['n_active'] * (n_active / NUM_BANKS) +
        weights['entropy'] * entropy +
        weights['cross_bank'] * cross_bank
    )

    # Find dominant banks
    sorted_banks = sorted(
        zip(BANK_NAMES, activations),
        key=lambda x: x[1],
        reverse=True
    )
    dominant = [name for name, act in sorted_banks[:3] if act > activation_threshold]

    return CognitiveComplexityScore(
        n_active_banks=n_active,
        activation_entropy=entropy,
        cross_bank_score=cross_bank,
        composite=composite,
        bank_profile=activations,
        dominant_banks=dominant,
    )


def _empty_score() -> CognitiveComplexityScore:
    """Return an empty/zero complexity score."""
    return CognitiveComplexityScore(
        n_active_banks=0,
        activation_entropy=0.0,
        cross_bank_score=0.0,
        composite=0.0,
        bank_profile=[0.0] * NUM_BANKS,
        dominant_banks=[],
    )


def score_document(
    document: Dict,
    gse_pipeline,
    text_field: str = 'text',
    aggregate: str = 'mean',
) -> Dict:
    """
    Score a document by aggregating sentence-level complexity.

    Args:
        document: Dictionary containing document data
        gse_pipeline: GSE pipeline instance
        text_field: Key for text content in document dict
        aggregate: Aggregation method ('mean', 'max', 'sum')

    Returns:
        Document dict with added 'complexity' field
    """
    text = document.get(text_field, '')
    if not text:
        document['complexity'] = _empty_score().to_dict()
        return document

    # Split into sentences (simple heuristic)
    sentences = _split_sentences(text)

    if not sentences:
        document['complexity'] = _empty_score().to_dict()
        return document

    # Score each sentence
    scores = []
    for sentence in sentences:
        if len(sentence.strip()) > 10:  # Skip very short sentences
            score = compute_cognitive_complexity(sentence, gse_pipeline)
            scores.append(score)

    if not scores:
        document['complexity'] = _empty_score().to_dict()
        return document

    # Aggregate scores
    if aggregate == 'mean':
        agg_composite = np.mean([s.composite for s in scores])
        agg_n_active = np.mean([s.n_active_banks for s in scores])
        agg_entropy = np.mean([s.activation_entropy for s in scores])
        agg_cross = np.mean([s.cross_bank_score for s in scores])
        agg_profile = np.mean([s.bank_profile for s in scores], axis=0).tolist()
    elif aggregate == 'max':
        max_idx = np.argmax([s.composite for s in scores])
        max_score = scores[max_idx]
        agg_composite = max_score.composite
        agg_n_active = max_score.n_active_banks
        agg_entropy = max_score.activation_entropy
        agg_cross = max_score.cross_bank_score
        agg_profile = max_score.bank_profile
    else:  # sum
        agg_composite = sum(s.composite for s in scores)
        agg_n_active = max(s.n_active_banks for s in scores)
        agg_entropy = np.mean([s.activation_entropy for s in scores])
        agg_cross = np.mean([s.cross_bank_score for s in scores])
        agg_profile = np.sum([s.bank_profile for s in scores], axis=0).tolist()

    # Get dominant banks across document
    bank_totals = np.sum([s.bank_profile for s in scores], axis=0)
    sorted_banks = sorted(
        zip(BANK_NAMES, bank_totals),
        key=lambda x: x[1],
        reverse=True
    )
    dominant = [name for name, _ in sorted_banks[:3]]

    document['complexity'] = {
        'composite': float(agg_composite),
        'n_active_banks': float(agg_n_active),
        'activation_entropy': float(agg_entropy),
        'cross_bank_score': float(agg_cross),
        'bank_profile': agg_profile,
        'dominant_banks': dominant,
        'n_sentences': len(scores),
        'n_high_complexity': sum(1 for s in scores if s.composite > 0.6),
    }

    return document


def _split_sentences(text: str) -> List[str]:
    """
    Simple sentence splitting heuristic.

    For production, consider using spaCy or NLTK.
    """
    import re

    # Split on sentence-ending punctuation
    sentences = re.split(r'(?<=[.!?])\s+', text)

    # Filter empty/whitespace
    return [s.strip() for s in sentences if s.strip()]


def analyze_complexity_characteristics(
    high_complexity_texts: List[str],
    low_complexity_texts: List[str],
) -> Dict:
    """
    Analyze linguistic features that correlate with GSE complexity.

    This provides interpretable explanation for why certain texts
    are selected by GSE-based curation.

    Args:
        high_complexity_texts: Texts with high GSE complexity scores
        low_complexity_texts: Texts with low GSE complexity scores

    Returns:
        Dictionary of feature comparisons
    """
    import re

    features = {
        # Syntactic markers
        'avg_sentence_length': lambda text: np.mean([
            len(s.split()) for s in _split_sentences(text)
        ]) if _split_sentences(text) else 0,

        # Causal reasoning (LOGICAL bank)
        'causal_connectives': lambda text: len(re.findall(
            r'\b(because|therefore|thus|hence|so|since|consequently)\b',
            text.lower()
        )) / max(1, len(_split_sentences(text))),

        # Conditional reasoning (LOGICAL bank)
        'conditional_rate': lambda text: len(re.findall(
            r'\b(if|unless|whether|when|provided|assuming)\b',
            text.lower()
        )) / max(1, len(_split_sentences(text))),

        # Mental state verbs (MENTAL bank)
        'mental_verbs': lambda text: len(re.findall(
            r'\b(think|believe|know|feel|want|hope|expect|understand|remember)\b',
            text.lower()
        )) / max(1, len(_split_sentences(text))),

        # Temporal markers (TEMPORAL bank)
        'temporal_markers': lambda text: len(re.findall(
            r'\b(before|after|when|while|during|until|since|then|now|later)\b',
            text.lower()
        )) / max(1, len(_split_sentences(text))),

        # Negation (requires polarity processing)
        'negation_rate': lambda text: len(re.findall(
            r"\b(not|no|never|n't|neither|nobody|nothing|none)\b",
            text.lower()
        )) / max(1, len(_split_sentences(text))),

        # Questions (often require reasoning)
        'question_rate': lambda text: text.count('?') / max(1, len(_split_sentences(text))),
    }

    results = {}
    for feature_name, feature_fn in features.items():
        high_values = [feature_fn(t) for t in high_complexity_texts]
        low_values = [feature_fn(t) for t in low_complexity_texts]

        # Statistical comparison
        from scipy import stats
        t_stat, p_value = stats.ttest_ind(high_values, low_values)

        # Effect size (Cohen's d)
        pooled_std = np.sqrt((np.var(high_values) + np.var(low_values)) / 2)
        cohens_d = (np.mean(high_values) - np.mean(low_values)) / max(pooled_std, 1e-10)

        results[feature_name] = {
            'high_mean': float(np.mean(high_values)),
            'low_mean': float(np.mean(low_values)),
            't_statistic': float(t_stat),
            'p_value': float(p_value),
            'cohens_d': float(cohens_d),
            'significant': p_value < 0.05,
        }

    return results
