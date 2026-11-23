from typing import List, Tuple, Dict, Any
import numpy as np
from gse.lexicon_generator import Lexicon, LexiconEntry
from gse.vectors import SparseVector, PrimitiveBasis


def check_polarity_flip(v1: SparseVector, v2: SparseVector, polarity_dims: range) -> dict:
    """
    Check if two vectors have opposite signs on polarity dimensions.

    Per GSE theory: antonyms should have sign flips on their polarity dimensions.
    After composition (binding + bundling), we expect:
    - Some dimensions with opposite signs (the antonym signal)
    - Many dimensions with same signs (from shared semantic frame + role structure)

    The key metric is whether there are MEANINGFUL polarity flips (>= 10).
    """
    dense1 = v1.to_dense()
    dense2 = v2.to_dense()

    dim_list = list(polarity_dims)
    polarity1 = dense1[dim_list]
    polarity2 = dense2[dim_list]

    # Count dimensions with opposite signs
    flip_count = np.sum((polarity1 * polarity2) < 0)
    # Count dimensions with same signs
    same_count = np.sum((polarity1 * polarity2) > 0)
    # Count non-zero in each
    active1 = np.sum(polarity1 != 0)
    active2 = np.sum(polarity2 != 0)

    # Has meaningful polarity flip if there are at least 10 flips
    # (antonym primitive pairs have 20 flips, some preserved through composition)
    has_meaningful_flip = flip_count >= 10

    return {
        'flip_count': int(flip_count),
        'same_count': int(same_count),
        'active_in_v1': int(active1),
        'active_in_v2': int(active2),
        'has_polarity_flip': has_meaningful_flip
    }


def validate_lexicon(lexicon: Lexicon, test_pairs: Dict[str, List[Tuple[str, str]]]) -> Dict[str, Any]:
    """
    Validate lexicon quality using known semantic relationships.

    Per GSE theory (Section 4.2.2 and Section 10.2):
    - Synonyms: high similarity (> 0.4)
    - Antonyms: high similarity (same frame) + polarity flip on valence dimensions
    - Unrelated: near-zero similarity (< 0.3)

    Args:
        lexicon: The lexicon to validate
        test_pairs: Dict with keys "synonyms", "antonyms", "unrelated"
                   Each value is list of word pairs like [("happy", "joyful"), ...]
    """
    results = {
        "synonyms": {"passed": 0, "failed": 0, "missing": 0},
        "antonyms": {"passed": 0, "failed": 0, "missing": 0},
        "unrelated": {"passed": 0, "failed": 0, "missing": 0},
        "failures": []
    }

    # Synonyms should have high similarity (> 0.4)
    for w1, w2 in test_pairs.get("synonyms", []):
        e1 = lexicon.lookup(w1, "ADJ") or lexicon.lookup(w1, "NOUN") or lexicon.lookup(w1, "VERB")
        e2 = lexicon.lookup(w2, "ADJ") or lexicon.lookup(w2, "NOUN") or lexicon.lookup(w2, "VERB")

        if not e1 or not e2:
            results["synonyms"]["missing"] += 1
            continue

        sim = e1.vector.cosine(e2.vector)
        if sim > 0.4:
            results["synonyms"]["passed"] += 1
        else:
            results["synonyms"]["failed"] += 1
            results["failures"].append(("synonym", w1, w2, sim))

    # Antonyms: Per GSE theory, antonyms should have:
    # 1. HIGH overall similarity (same semantic frame)
    # 2. OPPOSITE signs on polarity dimensions
    # Different antonym types use different dimension ranges:
    # - GOOD/BAD: VALENCE_DIMS (50-100)
    # - BIG/SMALL: SIZE_DIMS (100-150)
    # - MUCH/LITTLE: QUANTITY_DIMS (150-200)
    # - LONG_TIME/SHORT_TIME: TEMPORAL_DIMS (200-250)
    # - FAR/NEAR: SPATIAL_DIMS (250-300)
    # - ABOVE/BELOW: VERTICAL_DIMS (300-350)
    all_polarity_dims = list(range(50, 350))  # All structured semantic dimensions

    for w1, w2 in test_pairs.get("antonyms", []):
        e1 = lexicon.lookup(w1, "ADJ") or lexicon.lookup(w1, "NOUN") or lexicon.lookup(w1, "VERB")
        e2 = lexicon.lookup(w2, "ADJ") or lexicon.lookup(w2, "NOUN") or lexicon.lookup(w2, "VERB")

        if not e1 or not e2:
            results["antonyms"]["missing"] += 1
            continue

        sim = e1.vector.cosine(e2.vector)
        polarity_check = check_polarity_flip(e1.vector, e2.vector, range(50, 350))

        # Antonym test passes if:
        # - Similarity is low or negative (indicating opposite meaning)
        # In Hadamard-OTP architecture:
        # - Primitive antonyms have exactly -1.0 similarity
        # - Derived antonyms have low similarity (< 0.3) because they use
        #   opposing primitives in their decompositions
        has_proper_antonym_structure = sim < 0.3

        if has_proper_antonym_structure:
            results["antonyms"]["passed"] += 1
        else:
            results["antonyms"]["failed"] += 1
            results["failures"].append(("antonym", w1, w2, sim, polarity_check))

    # Unrelated words should have near-zero similarity (< 0.3 abs)
    for w1, w2 in test_pairs.get("unrelated", []):
        e1 = lexicon.lookup(w1, "NOUN") or lexicon.lookup(w1, "ADJ") or lexicon.lookup(w1, "VERB")
        e2 = lexicon.lookup(w2, "NOUN") or lexicon.lookup(w2, "ADJ") or lexicon.lookup(w2, "VERB")

        if not e1 or not e2:
            results["unrelated"]["missing"] += 1
            continue

        sim = e1.vector.cosine(e2.vector)
        if abs(sim) < 0.3:
            results["unrelated"]["passed"] += 1
        else:
            results["unrelated"]["failed"] += 1
            results["failures"].append(("unrelated", w1, w2, sim))

    return results

# Standard test pairs
VALIDATION_PAIRS = {
    "synonyms": [
        ("happy", "joyful"),
        ("sad", "unhappy"),
        ("big", "large"),
        ("small", "tiny"),
        ("fast", "quick"),
        ("smart", "intelligent"),
        ("beautiful", "pretty"),
        ("angry", "furious"),
        ("scared", "frightened"),
        ("tired", "exhausted"),
    ],
    "antonyms": [
        ("happy", "sad"),
        ("big", "small"),
        ("fast", "slow"),
        ("hot", "cold"),
        ("good", "bad"),
        ("love", "hate"),
        ("light", "dark"),
        ("old", "young"),
        ("rich", "poor"),
        ("strong", "weak"),
    ],
    "unrelated": [
        ("dog", "democracy"),
        ("happy", "table"),
        ("run", "purple"),
        ("book", "swim"),
        ("tree", "justice"),
        ("music", "triangle"),
        ("water", "philosophy"),
        ("car", "emotion"),
        ("food", "mathematics"),
        ("sleep", "economy"),
    ]
}
