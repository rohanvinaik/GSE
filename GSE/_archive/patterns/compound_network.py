"""
Compound Pattern Learning Network

Minsky/Winston-inspired minimal learning network that learns COMPOUND
primitive activation patterns, NOT word co-occurrences.

Key insight: We learn that if primitives {3, 7, 42} activate together,
there's increased proclivity for pattern {4, 19, 62}. This is mechanistic
learning - extracting structural rules about primitive interactions.

Two networks:
1. WordScaleNetwork (24 hub nodes) - learns primitive connection rules
2. OrchestratorNetwork (36 nodes) - learns routing and combination rules
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, FrozenSet, Optional
import numpy as np
import json
import time
from pathlib import Path
from collections import defaultdict

from gse.primitives import (
    Scale, HUB_PRIMITIVES, ORCHESTRATOR_NODES,
    WORD_PRIMITIVES, PRIMITIVE_TO_BANK, SEMANTIC_BANKS
)


@dataclass
class CompoundPattern:
    """
    A learned compound activation pattern.

    This is NOT about specific words - it's about primitive combinations.
    When primitives in `trigger` activate, `result` primitives have
    increased activation proclivity.
    """
    id: str
    trigger: FrozenSet[int]     # Indices of triggering hub primitives
    result: FrozenSet[int]      # Indices of resulting activations
    confidence: float = 0.5     # How reliable this pattern is
    frequency: int = 1          # How often observed
    created_at: float = field(default_factory=time.time)

    def match_score(self, active: Set[int]) -> float:
        """How well does this pattern match current activations?"""
        if not self.trigger:
            return 0.0
        overlap = len(self.trigger & active)
        return overlap / len(self.trigger)

    def get_predictions(self, active: Set[int]) -> Set[int]:
        """What additional primitives does this pattern predict?"""
        return self.result - active


class CompoundPatternNetwork:
    """
    Minimal learning network for compound primitive patterns.

    This is NOT gradient descent on massive data. It's Hebbian-like
    learning: primitives that fire together wire together.

    The network learns RULES about primitive interactions:
    - "FEEL + GOOD often co-activates with VERY" (intensity pattern)
    - "SOMEONE + DO + SOMETHING forms complete agent-action-patient"
    - "THINK + TRUE rarely co-activates with FEEL" (cognitive vs affective)
    """

    def __init__(self, nodes: List[str], scale: Scale):
        """
        Initialize network with given node set.

        Args:
            nodes: List of primitive names to use as network nodes
            scale: Which scale this network operates at
        """
        self.nodes = nodes
        self.n = len(nodes)
        self.scale = scale
        self.node_to_idx = {n: i for i, n in enumerate(nodes)}
        self.idx_to_node = {i: n for i, n in enumerate(nodes)}

        # Connection weights (primitive-to-primitive proclivity)
        # NOT trained via backprop - updated via Hebbian co-activation
        self.weights = np.zeros((self.n, self.n), dtype=np.float32)

        # Compound pattern storage (K-line inspired)
        self.patterns: Dict[str, CompoundPattern] = {}
        self._pattern_index: Dict[FrozenSet[int], str] = {}

        # Bank-level priors (some banks rarely co-activate)
        self.bank_affinity = np.ones((8, 8), dtype=np.float32)

        # Learning statistics
        self.total_observations = 0
        self.last_update = time.time()

    def observe(self, active_primitives: Set[str]) -> None:
        """
        Observe which primitives activated together.
        Update weights via Hebbian learning.

        This is LEARNING (extracting rules), not TRAINING (grading examples).
        """
        # Convert to indices
        active_indices = set()
        for p in active_primitives:
            if p in self.node_to_idx:
                active_indices.add(self.node_to_idx[p])

        if len(active_indices) < 2:
            return

        # Hebbian update: strengthen connections between co-active nodes
        for i in active_indices:
            for j in active_indices:
                if i != j:
                    # Small increment - we're learning rules, not memorizing
                    self.weights[i, j] += 0.01

        # Decay unused connections (prevents runaway weights)
        self.weights *= 0.999

        # Store as compound pattern if 3+ primitives
        if len(active_indices) >= 3:
            self._store_pattern(active_indices)

        # Update bank-level affinity
        self._update_bank_affinity(active_primitives)

        self.total_observations += 1
        self.last_update = time.time()

    def _update_bank_affinity(self, active_primitives: Set[str]) -> None:
        """Track which semantic banks tend to co-activate."""
        active_banks = set()
        for p in active_primitives:
            if p in PRIMITIVE_TO_BANK:
                active_banks.add(PRIMITIVE_TO_BANK[p])

        # Strengthen affinity between co-active banks
        for b1 in active_banks:
            for b2 in active_banks:
                self.bank_affinity[b1, b2] += 0.001

        # Normalize
        self.bank_affinity /= self.bank_affinity.max()

    def _store_pattern(self, active_indices: Set[int]) -> None:
        """Store or reinforce a compound activation pattern."""
        frozen = frozenset(active_indices)

        if frozen in self._pattern_index:
            # Reinforce existing pattern
            pattern_id = self._pattern_index[frozen]
            pattern = self.patterns[pattern_id]
            pattern.frequency += 1
            pattern.confidence = min(1.0, pattern.confidence + 0.01)
        else:
            # Create new pattern
            pattern_id = f"cp_{len(self.patterns)}_{int(time.time() * 1000) % 100000}"
            pattern = CompoundPattern(
                id=pattern_id,
                trigger=frozen,
                result=frozen,  # Initially, trigger == result
                confidence=0.3,
                frequency=1
            )
            self.patterns[pattern_id] = pattern
            self._pattern_index[frozen] = pattern_id

        # Prune if too many patterns
        if len(self.patterns) > 5000:
            self._prune_weak_patterns()

    def _prune_weak_patterns(self, keep_ratio: float = 0.8) -> None:
        """Remove weakest patterns to prevent memory bloat."""
        if not self.patterns:
            return

        # Score by frequency * confidence
        scored = [
            (pid, p.frequency * p.confidence)
            for pid, p in self.patterns.items()
        ]
        scored.sort(key=lambda x: -x[1])

        # Keep top patterns
        keep_count = int(len(scored) * keep_ratio)
        keep_ids = {pid for pid, _ in scored[:keep_count]}

        # Remove weak patterns
        for pid in list(self.patterns.keys()):
            if pid not in keep_ids:
                pattern = self.patterns[pid]
                del self._pattern_index[pattern.trigger]
                del self.patterns[pid]

    def predict(self, active: Set[str], top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Given active primitives, predict what else should activate.
        Uses COMPOUND patterns, not just pairwise weights.

        Returns list of (primitive_name, confidence) tuples.
        """
        active_indices = {
            self.node_to_idx[p] for p in active
            if p in self.node_to_idx
        }

        if not active_indices:
            return []

        predictions: Dict[int, float] = defaultdict(float)

        # Signal 1: Pairwise weights
        for i in active_indices:
            for j in range(self.n):
                if j not in active_indices:
                    predictions[j] += self.weights[i, j]

        # Signal 2: Compound pattern matching
        for pattern in self.patterns.values():
            match_score = pattern.match_score(active_indices)
            if match_score > 0.5:  # Significant match
                for pred_idx in pattern.get_predictions(active_indices):
                    predictions[pred_idx] += match_score * pattern.confidence

        # Convert to sorted list
        results = [
            (self.idx_to_node[idx], score)
            for idx, score in predictions.items()
            if score > 0.01
        ]
        results.sort(key=lambda x: -x[1])

        return results[:top_k]

    def coherence_score(self, primitives: Set[str]) -> float:
        """
        How coherent/typical is this set of primitives?
        High score = commonly observed together
        Low score = unusual/anomalous combination
        """
        indices = {
            self.node_to_idx[p] for p in primitives
            if p in self.node_to_idx
        }

        if len(indices) < 2:
            return 1.0  # Single primitive is trivially coherent

        # Check pairwise connection strength
        total_weight = 0.0
        n_pairs = 0
        for i in indices:
            for j in indices:
                if i < j:
                    total_weight += self.weights[i, j]
                    n_pairs += 1

        if n_pairs == 0:
            return 0.5

        avg_weight = total_weight / n_pairs

        # Check compound pattern match
        frozen = frozenset(indices)
        if frozen in self._pattern_index:
            pattern = self.patterns[self._pattern_index[frozen]]
            return min(1.0, 0.5 + pattern.confidence * 0.5)

        # Normalize weight to [0, 1]
        return min(1.0, avg_weight * 10)  # Scale factor based on typical weight range

    def save(self, path: str) -> None:
        """Save network state."""
        data = {
            'nodes': self.nodes,
            'scale': self.scale.value,
            'weights': self.weights.tolist(),
            'bank_affinity': self.bank_affinity.tolist(),
            'patterns': [
                {
                    'id': p.id,
                    'trigger': list(p.trigger),
                    'result': list(p.result),
                    'confidence': p.confidence,
                    'frequency': p.frequency,
                }
                for p in self.patterns.values()
            ],
            'total_observations': self.total_observations,
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str) -> 'CompoundPatternNetwork':
        """Load network state."""
        with open(path) as f:
            data = json.load(f)

        # Handle subclass instantiation
        if cls == WordScaleNetwork:
            network = WordScaleNetwork()
        elif cls == OrchestratorNetwork:
            network = OrchestratorNetwork()
        else:
            network = cls(data['nodes'], Scale(data['scale']))
        network.weights = np.array(data['weights'], dtype=np.float32)
        network.bank_affinity = np.array(data['bank_affinity'], dtype=np.float32)
        network.total_observations = data['total_observations']

        for p_data in data['patterns']:
            pattern = CompoundPattern(
                id=p_data['id'],
                trigger=frozenset(p_data['trigger']),
                result=frozenset(p_data['result']),
                confidence=p_data['confidence'],
                frequency=p_data['frequency'],
            )
            network.patterns[pattern.id] = pattern
            network._pattern_index[pattern.trigger] = pattern.id

        return network


class WordScaleNetwork(CompoundPatternNetwork):
    """
    24-node learning network for word-scale primitive patterns.

    Uses HUB_PRIMITIVES as nodes - key primitives that drive
    activation patterns within their semantic banks.
    """

    def __init__(self):
        super().__init__(HUB_PRIMITIVES, Scale.WORD)
        self._init_bank_structure()

    def _init_bank_structure(self) -> None:
        """Initialize with prior knowledge about bank relationships."""
        # Same-bank primitives have slight positive prior
        for i, p1 in enumerate(self.nodes):
            for j, p2 in enumerate(self.nodes):
                if i != j:
                    b1 = PRIMITIVE_TO_BANK.get(p1, -1)
                    b2 = PRIMITIVE_TO_BANK.get(p2, -1)
                    if b1 == b2 and b1 >= 0:
                        # Same bank: slight positive prior
                        self.weights[i, j] = 0.05

    def learn_from_lexicon(self, lexicon_path: str) -> int:
        """
        Learn compound patterns from lexicon decompositions.

        Returns number of observations processed.
        """
        import sqlite3

        conn = sqlite3.connect(lexicon_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT decomposition FROM lexicon
                WHERE decomposition IS NOT NULL
                AND source IN ('claude-code', 'manual-fix', 'curated-enhanced',
                               'enhanced-v2', 'audit_fix', 'ollama-enhanced')
            """)
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            print("Warning: lexicon table not found")
            return 0

        conn.close()

        count = 0
        for (decomp_json,) in rows:
            if not decomp_json:
                continue

            try:
                decomp = json.loads(decomp_json)
            except json.JSONDecodeError:
                continue

            # Extract primitives from decomposition
            primitives = set()
            for item in decomp:
                if len(item) >= 1:
                    prim = item[0] if isinstance(item, (list, tuple)) else item
                    if prim in WORD_PRIMITIVES:
                        primitives.add(prim)

            if len(primitives) >= 2:
                # Map to hub primitives (bank representatives)
                hub_actives = self._map_to_hubs(primitives)
                if hub_actives:
                    self.observe(hub_actives)
                    count += 1

        print(f"WordScaleNetwork learned from {count} decompositions")
        print(f"  Total patterns: {len(self.patterns)}")
        print(f"  Total observations: {self.total_observations}")

        return count

    def _map_to_hubs(self, primitives: Set[str]) -> Set[str]:
        """Map full primitive set to hub primitives."""
        hubs = set()
        for p in primitives:
            if p in HUB_PRIMITIVES:
                hubs.add(p)
            else:
                # Find hub for this primitive's bank
                bank = PRIMITIVE_TO_BANK.get(p)
                if bank is not None:
                    for hub in HUB_PRIMITIVES:
                        if PRIMITIVE_TO_BANK.get(hub) == bank:
                            hubs.add(hub)
                            break
        return hubs


class OrchestratorNetwork(CompoundPatternNetwork):
    """
    36-node learning network for routing and combination decisions.

    This is the "mini homunculus" that learns:
    - Which scales to activate for different inputs
    - How to combine signals from different scales
    - When to use different combination strategies
    - How to handle errors and ambiguity
    """

    def __init__(self):
        super().__init__(ORCHESTRATOR_NODES, Scale.TEXT)  # Operates at meta-level
        self._init_routing_priors()

    def _init_routing_priors(self) -> None:
        """Initialize with sensible routing priors."""
        # Route signals are mutually reinforcing in chains
        route_indices = [
            self.node_to_idx[n] for n in
            ["ROUTE_TEXT", "ROUTE_PARAGRAPH", "ROUTE_SENTENCE", "ROUTE_WORD"]
        ]
        for i, r in enumerate(route_indices[:-1]):
            # Each scale activates the next
            self.weights[r, route_indices[i + 1]] = 0.1

        # High confidence should prefer simpler combination
        conf_high = self.node_to_idx["CONF_HIGH"]
        combine_bundle = self.node_to_idx["COMBINE_BUNDLE"]
        self.weights[conf_high, combine_bundle] = 0.1

        # Low confidence should trigger error handling
        conf_low = self.node_to_idx["CONF_LOW"]
        error_retry = self.node_to_idx["ERROR_RETRY"]
        self.weights[conf_low, error_retry] = 0.1

    def route_decision(self, input_features: Dict[str, float]) -> Dict[str, float]:
        """
        Given input features, decide routing weights.

        Args:
            input_features: Dict mapping orchestrator node names to activation levels

        Returns:
            Dict mapping node names to output activation levels
        """
        # Convert to indices and activations
        activations = np.zeros(self.n, dtype=np.float32)
        for node, level in input_features.items():
            if node in self.node_to_idx:
                activations[self.node_to_idx[node]] = level

        # Propagate through weights
        output = np.dot(activations, self.weights)

        # Add pattern-based activations
        active_indices = {i for i in range(self.n) if activations[i] > 0.1}
        for pattern in self.patterns.values():
            match = pattern.match_score(active_indices)
            if match > 0.5:
                for idx in pattern.result:
                    output[idx] += match * pattern.confidence

        # Convert back to dict
        return {
            self.idx_to_node[i]: float(output[i])
            for i in range(self.n)
            if output[i] > 0.01
        }

    def learn_from_text_corpus(self, corpus_dir: str) -> int:
        """
        Learn routing patterns from text corpus.

        This learns things like:
        - Formal academic text → activate FORMAL + ACADEMIC + EXPOSITORY
        - Personal narrative → activate INFORMAL + PERSONAL + NARRATIVE
        """
        corpus_path = Path(corpus_dir)
        if not corpus_path.exists():
            print(f"Warning: corpus directory not found: {corpus_dir}")
            return 0

        count = 0
        for txt_file in corpus_path.glob("*.txt"):
            try:
                text = txt_file.read_text(encoding='utf-8')
                features = self._extract_text_features(text, txt_file.name)
                self.observe(features)
                count += 1
            except Exception as e:
                print(f"Error processing {txt_file.name}: {e}")

        print(f"OrchestratorNetwork learned from {count} documents")
        return count

    def _extract_text_features(self, text: str, filename: str) -> Set[str]:
        """Extract orchestrator-relevant features from text."""
        features = set()

        # Always process all scales for full documents
        features.add("ROUTE_TEXT")
        features.add("ROUTE_PARAGRAPH")
        features.add("ROUTE_SENTENCE")
        features.add("ROUTE_WORD")

        # Detect formality
        formal_markers = ["therefore", "consequently", "furthermore", "moreover",
                         "nevertheless", "notwithstanding"]
        informal_markers = ["kinda", "gonna", "wanna", "dunno", "yeah", "nope"]

        text_lower = text.lower()
        formal_count = sum(1 for m in formal_markers if m in text_lower)
        informal_count = sum(1 for m in informal_markers if m in text_lower)

        if formal_count > informal_count:
            features.add("ROUTE_TEXT")  # Signals formal processing

        # Detect question density (interrogative)
        question_ratio = text.count("?") / max(1, len(text.split(".")))
        if question_ratio > 0.3:
            features.add("TASK_ANALYZE")  # Questions suggest analysis needed

        # Filename heuristics for domain
        filename_lower = filename.lower()
        if "thesis" in filename_lower or "academic" in filename_lower:
            features.add("CTX_PRIOR")  # Use prior academic context
        if "chat" in filename_lower or "conversation" in filename_lower:
            features.add("CTX_RECENCY")  # Recency matters for dialogue

        # Length-based confidence
        word_count = len(text.split())
        if word_count < 50:
            features.add("CONF_LOW")
        elif word_count > 500:
            features.add("CONF_HIGH")
        else:
            features.add("CONF_MEDIUM")

        return features


# =============================================================================
# SENTENCE SCALE NETWORK
# =============================================================================
# Sentence-level primitives (different from word-level NSM primes)
# These capture sentence-level semantic patterns that discriminate meaning.

SENTENCE_SEMANTIC_PRIMITIVES = [
    # Semantic role patterns
    "AGENT_ACTION",      # Someone does something
    "EXPERIENCER_STATE", # Someone feels/experiences something
    "THEME_CHANGE",      # Something changes state

    # Polarity patterns - CRITICAL for antonym discrimination
    "POSITIVE_PREDICATE", # Main verb has positive valence
    "NEGATIVE_PREDICATE", # Main verb has negative valence
    "NEUTRAL_PREDICATE",  # Main verb is neutral

    # Information structure
    "TOPIC_FOCUS",       # Sentence introduces new topic
    "TOPIC_CONTINUE",    # Sentence continues existing topic
    "CONTRAST",          # Sentence contrasts with prior

    # Complexity patterns
    "SIMPLE_CLAUSE",     # Single clause
    "COMPOUND",          # Multiple coordinated clauses
    "COMPLEX",           # Subordination

    # Content density
    "HIGH_CONTENT",      # Many content words
    "LOW_CONTENT",       # Many function words
    "TECHNICAL",         # Domain-specific vocabulary

    # Quantification
    "UNIVERSAL",         # All, every, always
    "EXISTENTIAL",       # Some, a, sometimes
    "NEGATED",           # Contains negation

    # Reference patterns
    "DEFINITE_REF",      # The X (presupposes existence)
    "INDEFINITE_REF",    # A X (introduces new)
]


@dataclass
class SentenceFrame:
    """Frame capturing sentence-level semantic patterns."""
    predicate_polarity: float  # -1 (negative) to +1 (positive)
    content_density: float     # 0 (all function) to 1 (all content)
    sentence_type: str         # 'agent_action', 'experiencer_state', etc.
    active_patterns: Set[str]  # Active sentence primitives


class SentenceScaleNetwork(CompoundPatternNetwork):
    """
    20-node network learning sentence-level semantic patterns.

    Key insight: This network operates AFTER word-level encoding,
    looking at the PATTERN of primitive activations across the sentence.

    Learns:
    - Which combinations of word-level patterns indicate topic shift
    - How predicate polarity should weight overall sentence polarity
    - When shared structure is "noise" vs "signal"
    """

    def __init__(self):
        super().__init__(SENTENCE_SEMANTIC_PRIMITIVES, Scale.SENTENCE)
        self.n_nodes = len(SENTENCE_SEMANTIC_PRIMITIVES)

        # Predicate polarity dominance: how much does the main verb
        # determine overall sentence polarity?
        self.predicate_weight = 0.6  # Can be learned from corpus

        # Content word boost (vs function words)
        self.content_boost = 1.5

        # Function words to downweight
        self.function_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall',
            'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
            'it', 'this', 'that', 'these', 'those', 'what', 'which',
            'and', 'or', 'but', 'if', 'then', 'so', 'as', 'than',
            'i', 'you', 'he', 'she', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
        }

    def analyze_sentence(self, word_vectors: list, words: List[str],
                         syntax_info: Optional[Dict] = None) -> SentenceFrame:
        """
        Analyze sentence-level patterns from word encodings.

        Args:
            word_vectors: List of SparseVector for each word
            words: List of word strings
            syntax_info: Optional dict with 'predicate_indices', 'subject', etc.

        Returns:
            SentenceFrame with analyzed patterns
        """
        active_patterns = set()

        # Compute content density
        content_count = sum(1 for w in words if w.lower() not in self.function_words)
        content_density = content_count / max(1, len(words))

        if content_density > 0.6:
            active_patterns.add("HIGH_CONTENT")
        elif content_density < 0.4:
            active_patterns.add("LOW_CONTENT")

        # Detect predicate polarity
        predicate_polarity = 0.0
        if syntax_info and 'predicate_indices' in syntax_info:
            pred_indices = syntax_info['predicate_indices']
            if pred_indices and word_vectors:
                pred_polarity = self._compute_predicate_polarity(
                    word_vectors, pred_indices
                )
                predicate_polarity = pred_polarity
                if pred_polarity > 0.2:
                    active_patterns.add("POSITIVE_PREDICATE")
                elif pred_polarity < -0.2:
                    active_patterns.add("NEGATIVE_PREDICATE")
                else:
                    active_patterns.add("NEUTRAL_PREDICATE")
        else:
            active_patterns.add("NEUTRAL_PREDICATE")

        # Detect sentence type from patterns
        sentence_type = self._classify_sentence_type(words, word_vectors)
        active_patterns.add(sentence_type.upper().replace("_", "_"))

        # Check for negation
        negation_words = {'not', "n't", 'never', 'no', 'neither', 'nor', 'nothing', 'nobody'}
        if any(w.lower() in negation_words or w.lower().endswith("n't") for w in words):
            active_patterns.add("NEGATED")

        # Check quantification
        universal_words = {'all', 'every', 'always', 'each', 'everyone', 'everything'}
        existential_words = {'some', 'a', 'an', 'sometimes', 'someone', 'something'}
        if any(w.lower() in universal_words for w in words):
            active_patterns.add("UNIVERSAL")
        if any(w.lower() in existential_words for w in words):
            active_patterns.add("EXISTENTIAL")

        return SentenceFrame(
            predicate_polarity=predicate_polarity,
            content_density=content_density,
            sentence_type=sentence_type,
            active_patterns=active_patterns
        )

    def _compute_predicate_polarity(self, word_vectors: list,
                                     predicate_indices: List[int]) -> float:
        """
        Compute polarity of the predicate (main verb).

        Looks at EVALUATORS bank activation - positive or negative?
        """
        if not predicate_indices or not word_vectors:
            return 0.0

        # Get predicate vector(s)
        pred_vectors = [word_vectors[i] for i in predicate_indices
                        if i < len(word_vectors)]
        if not pred_vectors:
            return 0.0

        # Check EVALUATORS bank (bank 2, dims 2048-3072)
        total_polarity = 0.0
        for vec in pred_vectors:
            dense = vec.to_dense()
            eval_start, eval_end = 2 * 1024, 3 * 1024
            eval_signal = dense[eval_start:eval_end]
            pos_sum = np.sum(eval_signal[eval_signal > 0])
            neg_sum = np.sum(np.abs(eval_signal[eval_signal < 0]))
            if pos_sum + neg_sum > 0:
                polarity = (pos_sum - neg_sum) / (pos_sum + neg_sum)
                total_polarity += polarity

        return total_polarity / max(1, len(pred_vectors))

    def _classify_sentence_type(self, words: List[str], word_vectors: list) -> str:
        """Classify sentence into semantic type."""
        # Simple heuristics - can be learned from corpus
        word_set = set(w.lower() for w in words)

        # Experiencer state pattern
        experience_verbs = {'feel', 'feels', 'felt', 'think', 'thinks', 'thought',
                            'love', 'loves', 'loved', 'hate', 'hates', 'hated',
                            'like', 'likes', 'liked', 'want', 'wants', 'wanted'}
        if experience_verbs & word_set:
            return "experiencer_state"

        # Theme change pattern
        change_verbs = {'become', 'becomes', 'became', 'turn', 'turns', 'turned',
                        'grow', 'grows', 'grew', 'change', 'changes', 'changed'}
        if change_verbs & word_set:
            return "theme_change"

        # Default to agent action
        return "agent_action"

    def compute_adjusted_similarity(self,
                                     sent1_frame: SentenceFrame,
                                     sent2_frame: SentenceFrame,
                                     raw_similarity: float) -> float:
        """
        Adjust raw vector similarity based on sentence-level patterns.

        Key adjustments:
        1. If predicates have opposite polarity → reduce similarity
        2. If content densities differ greatly → reduce similarity
        3. If sentence types differ → reduce similarity

        This is CRITICAL for antonym discrimination at sentence level.
        """
        adjustment = 0.0

        # Predicate polarity mismatch (STRONGEST signal for antonyms)
        polarity_product = sent1_frame.predicate_polarity * sent2_frame.predicate_polarity
        if polarity_product < 0:
            # Opposite polarity - significant reduction
            adjustment -= 0.4 * self.predicate_weight
        elif polarity_product > 0.1:
            # Same polarity - slight boost
            adjustment += 0.1

        # Content density mismatch
        density_diff = abs(sent1_frame.content_density - sent2_frame.content_density)
        if density_diff > 0.3:
            adjustment -= 0.2

        # Sentence type mismatch
        if sent1_frame.sentence_type != sent2_frame.sentence_type:
            adjustment -= 0.1

        # Negation mismatch
        sent1_negated = "NEGATED" in sent1_frame.active_patterns
        sent2_negated = "NEGATED" in sent2_frame.active_patterns
        if sent1_negated != sent2_negated:
            adjustment -= 0.15

        return max(-1.0, min(1.0, raw_similarity + adjustment))

    def get_content_weights(self, words: List[str]) -> List[float]:
        """
        Get weighting for each word based on content vs function status.

        Content words get boosted, function words get reduced.
        """
        weights = []
        for word in words:
            if word.lower() in self.function_words:
                weights.append(0.3)  # Heavy discount for function words
            else:
                weights.append(self.content_boost)  # Boost for content words
        return weights
