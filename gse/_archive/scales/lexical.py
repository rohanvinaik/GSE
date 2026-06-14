"""
Lexical Scale Encoder

Handles individual words and multi-word expressions.
Wraps the core Lexicon and LexiconGenerator.

Includes ContentWeightedComposer for semantic similarity that
downweights function words to improve topic discrimination.
"""

from typing import Optional, List, Tuple, Dict
from collections import Counter
import math

from gse.vectors import SparseVector
from gse.lexicon_generator import Lexicon

class LexicalScale:
    """
    Encoder for the Lexical Scale (Scale 1).
    """
    
    def __init__(self, lexicon: Lexicon):
        self.lexicon = lexicon
        
    def encode(self, word: str, pos: str = "noun") -> Optional[SparseVector]:
        """
        Encode a single word.
        
        Args:
            word: The word lemma.
            pos: Part of speech (noun, verb, adj, etc.)
            
        Returns:
            SparseVector if found/generated, else None.
        """
        entry = self.lexicon.lookup(word, pos)
        if entry:
            return entry.vector
        return None
        
    def decompose(self, word: str, pos: str = "noun") -> List[Tuple[str, str]]:
        """Get the decomposition for a word."""
        entry = self.lexicon.lookup(word, pos)
        if entry:
            return entry.decomposition
        return []


class ContentWeightedComposer:
    """
    Compose word vectors with content-word weighting.

    Downweights function words (the, a, is, etc.) to improve
    semantic similarity discrimination between unrelated topics.

    Uses TF-IDF-like weighting where:
    - Function words get low weight (0.1)
    - Content words get weight based on inverse document frequency
    - Rare content words get boosted weight
    """

    # Core function words that should be heavily downweighted
    FUNCTION_WORDS = frozenset({
        # Articles
        'the', 'a', 'an',
        # Pronouns
        'i', 'you', 'he', 'she', 'it', 'we', 'they',
        'me', 'him', 'her', 'us', 'them',
        'my', 'your', 'his', 'its', 'our', 'their',
        'mine', 'yours', 'hers', 'ours', 'theirs',
        'this', 'that', 'these', 'those',
        'who', 'whom', 'whose', 'which', 'what',
        'myself', 'yourself', 'himself', 'herself', 'itself',
        'ourselves', 'yourselves', 'themselves',
        # Prepositions
        'in', 'on', 'at', 'to', 'for', 'with', 'by', 'from',
        'of', 'about', 'into', 'through', 'during', 'before',
        'after', 'above', 'below', 'between', 'under', 'over',
        # Conjunctions
        'and', 'or', 'but', 'nor', 'so', 'yet', 'both', 'either',
        'neither', 'not', 'only', 'than', 'as', 'if', 'when',
        'while', 'although', 'because', 'since', 'unless',
        # Auxiliary verbs
        'is', 'am', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'having',
        'do', 'does', 'did', 'doing',
        'will', 'would', 'shall', 'should',
        'can', 'could', 'may', 'might', 'must',
        # Other common function words
        'there', 'here', 'where', 'then', 'now',
        'very', 'just', 'also', 'too', 'even',
        'some', 'any', 'no', 'all', 'each', 'every',
        'more', 'most', 'less', 'least', 'much', 'many',
        'such', 'other', 'another', 'same',
    })

    # Minimum weight for function words
    FUNCTION_WORD_WEIGHT = 0.1

    # Default weight for unknown content words
    DEFAULT_CONTENT_WEIGHT = 1.0

    # Boost factor for rare content words
    RARE_WORD_BOOST = 1.5

    def __init__(self, corpus_word_counts: Optional[Dict[str, int]] = None,
                 total_documents: int = 1000):
        """
        Initialize the composer.

        Args:
            corpus_word_counts: Word frequency counts from corpus (optional)
            total_documents: Total number of documents in corpus for IDF
        """
        self.corpus_word_counts = corpus_word_counts or {}
        self.total_documents = total_documents
        self._idf_cache: Dict[str, float] = {}

        if corpus_word_counts:
            self._compute_idf_weights()

    def _compute_idf_weights(self) -> None:
        """Compute IDF weights from corpus statistics."""
        if not self.corpus_word_counts:
            return

        max_count = max(self.corpus_word_counts.values()) if self.corpus_word_counts else 1

        for word, count in self.corpus_word_counts.items():
            # IDF = log(N / df) where df = document frequency
            # We approximate df from word count
            df_estimate = min(count, self.total_documents)
            idf = math.log(self.total_documents / (1 + df_estimate))

            # Normalize to 0-2 range
            normalized_idf = 0.5 + (idf / math.log(self.total_documents + 1))

            self._idf_cache[word.lower()] = max(0.3, min(2.0, normalized_idf))

    def get_word_weight(self, word: str) -> float:
        """
        Get the weight for a word.

        Args:
            word: The word to weight

        Returns:
            Weight in range [0.1, 2.0]
        """
        word_lower = word.lower()

        # Function words get minimal weight
        if word_lower in self.FUNCTION_WORDS:
            return self.FUNCTION_WORD_WEIGHT

        # Check IDF cache
        if word_lower in self._idf_cache:
            return self._idf_cache[word_lower]

        # Unknown content word - use default
        return self.DEFAULT_CONTENT_WEIGHT

    def get_content_weights(self, words: List[str]) -> List[float]:
        """
        Get weights for a list of words.

        Args:
            words: List of words

        Returns:
            List of weights, one per word
        """
        return [self.get_word_weight(w) for w in words]

    def compose_weighted(self, word_vectors: List[SparseVector],
                         words: List[str]) -> SparseVector:
        """
        Compose word vectors with content-based weighting.

        Args:
            word_vectors: List of word vectors
            words: Corresponding words

        Returns:
            Weighted composite vector
        """
        if not word_vectors:
            return SparseVector.zeros(8192)

        if len(word_vectors) != len(words):
            raise ValueError(f"Mismatch: {len(word_vectors)} vectors, {len(words)} words")

        weights = self.get_content_weights(words)

        # Build weighted composite
        result_pos: Dict[int, float] = {}
        result_neg: Dict[int, float] = {}

        for vec, weight in zip(word_vectors, weights):
            for idx, val in vec.positive.items():
                result_pos[idx] = result_pos.get(idx, 0) + val * weight
            for idx, val in vec.negative.items():
                result_neg[idx] = result_neg.get(idx, 0) + val * weight

        # Normalize by total weight
        total_weight = sum(weights)
        if total_weight > 0:
            result_pos = {k: v / total_weight for k, v in result_pos.items()}
            result_neg = {k: v / total_weight for k, v in result_neg.items()}

        return SparseVector(
            dim=8192,
            positive=result_pos,
            negative=result_neg
        )

    def compute_weighted_similarity(self, vec1: SparseVector, words1: List[str],
                                    vec2: SparseVector, words2: List[str]) -> float:
        """
        Compute similarity with content weighting applied at comparison time.

        This is an alternative to compose_weighted that applies weighting
        during similarity computation rather than composition.

        Args:
            vec1, vec2: Pre-composed sentence vectors
            words1, words2: Original words used to compose vectors

        Returns:
            Weighted cosine similarity
        """
        # Get content density for each sentence
        density1 = self._content_density(words1)
        density2 = self._content_density(words2)

        # Raw similarity
        raw_sim = vec1.cosine(vec2)

        # Adjust based on content density
        # Higher density = more meaningful comparison
        avg_density = (density1 + density2) / 2

        # Scale similarity: low density sentences get penalized
        adjusted = raw_sim * (0.5 + 0.5 * avg_density)

        return adjusted

    def _content_density(self, words: List[str]) -> float:
        """
        Compute what fraction of words are content words.

        Args:
            words: List of words

        Returns:
            Ratio of content words (0 to 1)
        """
        if not words:
            return 0.0

        content_count = sum(
            1 for w in words
            if w.lower() not in self.FUNCTION_WORDS
        )

        return content_count / len(words)
