#!/usr/bin/env python3
"""
Scale-Specific Learning Networks for GSE

Implements Hebbian learning networks at each scale of the constraint cascade:
- TextScaleNetwork: Genre, register, domain patterns (12×12)
- ParagraphScaleNetwork: RST discourse relations (15×15)
- SentenceScaleNetwork: Syntactic structure patterns (10×10)
- WordScaleNetwork: Semantic primitive co-occurrence (24×24)

Each network learns co-activation patterns through Hebbian updates:
    Δw_ij = η * x_i * x_j

where η is the learning rate, and x_i, x_j are activation levels.
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

# =============================================================================
# BASE NETWORK
# =============================================================================


@dataclass
class LearningNetwork:
    """
    Base class for Hebbian learning networks.

    Implements a fully-connected network where weights encode
    co-activation patterns between nodes.
    """

    name: str
    node_names: List[str]
    weights: np.ndarray = field(default=None)

    # Learning parameters
    learning_rate: float = 0.01
    decay_rate: float = 0.001
    activation_threshold: float = 0.1

    # Statistics
    update_count: int = 0
    total_activations: int = 0

    def __post_init__(self):
        n = len(self.node_names)
        if self.weights is None:
            # Initialize with small random weights
            self.weights = np.random.randn(n, n) * 0.01
            # Zero diagonal (no self-connections)
            np.fill_diagonal(self.weights, 0)

        # Build name→index lookup
        self._name_to_idx = {name: i for i, name in enumerate(self.node_names)}

    @property
    def n_nodes(self) -> int:
        """Number of nodes in network."""
        return len(self.node_names)

    def get_index(self, name: str) -> int:
        """Get index for node name."""
        return self._name_to_idx.get(name, -1)

    def activate(self, activations: Dict[str, float]) -> Dict[str, float]:
        """
        Propagate activations through network.

        Args:
            activations: Dict of node_name → activation level

        Returns:
            Dict of node_name → output activation
        """
        # Build input vector
        x = np.zeros(self.n_nodes)
        for name, level in activations.items():
            idx = self.get_index(name)
            if idx >= 0:
                x[idx] = level

        # Propagate: y = Wx + x (residual connection)
        y = np.dot(self.weights, x) + x

        # Apply activation function (tanh for bounded output)
        y = np.tanh(y)

        # Build output dict
        output = {}
        for i, name in enumerate(self.node_names):
            if abs(y[i]) > self.activation_threshold:
                output[name] = float(y[i])

        self.total_activations += len(activations)
        return output

    def learn(self, activations: Dict[str, float]):
        """
        Update weights based on co-activations (Hebbian learning).

        Args:
            activations: Dict of node_name → activation level
        """
        # Build activation vector
        x = np.zeros(self.n_nodes)
        for name, level in activations.items():
            idx = self.get_index(name)
            if idx >= 0:
                x[idx] = level

        # Hebbian update: Δw_ij = η * x_i * x_j
        outer = np.outer(x, x)
        self.weights += self.learning_rate * outer

        # Weight decay to prevent unbounded growth
        self.weights *= 1 - self.decay_rate

        # Keep diagonal zero
        np.fill_diagonal(self.weights, 0)

        self.update_count += 1

    def get_associations(self, name: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Get strongest associations for a node.

        Args:
            name: Node name
            top_k: Number of top associations

        Returns:
            List of (node_name, weight) tuples
        """
        idx = self.get_index(name)
        if idx < 0:
            return []

        weights = self.weights[idx]
        indices = np.argsort(np.abs(weights))[::-1][:top_k]

        return [(self.node_names[i], float(weights[i])) for i in indices if i != idx]

    def get_weight(self, name1: str, name2: str) -> float:
        """Get weight between two nodes."""
        i = self.get_index(name1)
        j = self.get_index(name2)
        if i >= 0 and j >= 0:
            return float(self.weights[i, j])
        return 0.0

    def save(self, path: str):
        """Save network to file."""
        data = {
            "name": self.name,
            "node_names": self.node_names,
            "weights": self.weights.tolist(),
            "learning_rate": self.learning_rate,
            "decay_rate": self.decay_rate,
            "update_count": self.update_count,
        }
        with open(path, "w") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, path: str) -> "LearningNetwork":
        """Load network from file."""
        with open(path) as f:
            data = json.load(f)

        # Create instance (subclasses may have fixed name/node_names)
        if cls == LearningNetwork:
            network = cls(
                name=data["name"],
                node_names=data["node_names"],
            )
        else:
            # Subclass - use its defaults
            network = cls()

        # Load weights and parameters
        network.weights = np.array(data["weights"])
        network.learning_rate = data.get("learning_rate", 0.01)
        network.decay_rate = data.get("decay_rate", 0.001)
        network.update_count = data.get("update_count", 0)

        return network


# =============================================================================
# TEXT-SCALE NETWORK
# =============================================================================

# Text-level primitives (genre, register, domain)
TEXT_PRIMITIVES = [
    # Genre
    "NARRATIVE",
    "EXPOSITORY",
    "ARGUMENTATIVE",
    "DESCRIPTIVE",
    # Register
    "FORMAL",
    "INFORMAL",
    "TECHNICAL",
    "COLLOQUIAL",
    # Domain
    "ACADEMIC",
    "LITERARY",
    "JOURNALISTIC",
    "CONVERSATIONAL",
]


class TextScaleNetwork(LearningNetwork):
    """
    Network for text-level patterns.

    Learns associations like:
    - FORMAL + TECHNICAL → ACADEMIC
    - NARRATIVE + INFORMAL → CONVERSATIONAL
    """

    def __init__(self, **kwargs):
        super().__init__(name="text_scale", node_names=TEXT_PRIMITIVES, **kwargs)

    def classify_text(self, features: Dict[str, float]) -> Dict[str, float]:
        """
        Classify text based on observed features.

        Args:
            features: Dict of feature → activation (e.g., {"FORMAL": 0.8})

        Returns:
            Dict of inferred features with activations
        """
        return self.activate(features)


# =============================================================================
# PARAGRAPH-SCALE NETWORK
# =============================================================================

# RST-inspired discourse primitives
PARAGRAPH_PRIMITIVES = [
    # Nucleus-Satellite relations
    "ELABORATION",
    "BACKGROUND",
    "CIRCUMSTANCE",
    "CAUSE",
    "RESULT",
    "PURPOSE",
    "CONDITION",
    "CONCESSION",
    "CONTRAST",
    "COMPARISON",
    # Multi-nuclear relations
    "SEQUENCE",
    "CONJUNCTION",
    "DISJUNCTION",
    "RESTATEMENT",
    "SUMMARY",
]


class ParagraphScaleNetwork(LearningNetwork):
    """
    Network for paragraph-level discourse patterns.

    Learns RST-like relations:
    - CLAIM + EXAMPLE → ELABORATION
    - CAUSE + RESULT → follows
    """

    def __init__(self, **kwargs):
        super().__init__(name="paragraph_scale", node_names=PARAGRAPH_PRIMITIVES, **kwargs)

    def predict_next_relation(
        self,
        current: str,
        context: List[str] = None,
    ) -> List[Tuple[str, float]]:
        """
        Predict likely next discourse relation.

        Args:
            current: Current relation type
            context: Previous relations for context

        Returns:
            List of (relation, probability) tuples
        """
        activations = {current: 1.0}
        if context:
            for i, rel in enumerate(context[-3:]):  # Last 3
                weight = 0.5 ** (len(context) - i)  # Decay
                activations[rel] = weight

        output = self.activate(activations)

        # Exclude current from predictions
        predictions = [(name, level) for name, level in output.items() if name != current]

        return sorted(predictions, key=lambda x: -x[1])


# =============================================================================
# SENTENCE-SCALE NETWORK
# =============================================================================

# Syntactic primitives (from sentence_structure_encoder)
SENTENCE_PRIMITIVES = [
    # Core structure
    "SYN_SUBJ",
    "SYN_PRED",
    "SYN_OBJ",
    "SYN_COMPL",
    # Modification
    "SYN_ADJ_MOD",
    "SYN_ADV_MOD",
    "SYN_DET",
    # TAM features
    "SYN_TENSE_PAST",
    "SYN_ASPECT_PERF",
    "SYN_MOOD_INTER",
]


class SentenceScaleNetwork(LearningNetwork):
    """
    Network for sentence-level syntactic patterns.

    Learns structural co-occurrences:
    - SYN_SUBJ(animate) + SYN_PRED(mental) → SYN_OBJ(propositional)
    - SYN_TENSE_PAST + SYN_ASPECT_PERF → completed action
    """

    def __init__(self, **kwargs):
        super().__init__(name="sentence_scale", node_names=SENTENCE_PRIMITIVES, **kwargs)

    def predict_structure(
        self,
        partial: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Complete sentence structure from partial specification.

        Args:
            partial: Known structural elements

        Returns:
            Predicted complete structure
        """
        return self.activate(partial)


# =============================================================================
# WORD-SCALE NETWORK
# =============================================================================

# Hub primitives (representatives from each family)
# These should cover key primitives from each bank including new bipolar pairs
WORD_PRIMITIVES = [
    # Substantives (Bank 0)
    "SOMEONE",
    "SOMETHING",
    "PART",
    # Quantity (Bank 1)
    "ONE",
    "QUANTITY",
    # Evaluators (Bank 2)
    "GOOD",
    "BIG",
    # Mental (Bank 3) - including INFER
    "THINK",
    "FEEL",
    "KNOW",
    "WANT",
    "INFER",
    # Action (Bank 4) - including ALIVE/DEAD bipolar
    "DO",
    "BE",
    "MOVE",
    "SAY",
    "ALIVE",
    # Temporal (Bank 5) - including START/END bipolar
    "BEFORE",
    "MOMENT",
    "START",
    # Spatial (Bank 6) - including TOWARD/AWAY, WITH/WITHOUT bipolars
    "WHERE",
    "ABOVE",
    "TOWARD",
    "WITH",
    # Logical (Bank 7) - including MUST, CERTAINTY, and CAUSE
    "NOT",
    "BECAUSE",
    "CAUSE",
    "MUST",
    "CERTAINTY",
    # Hierarchy markers
    "HIER_PLUS",
    "HIER_MINUS",
    "INTENSITY",
]


class WordScaleNetwork(LearningNetwork):
    """
    Network for word-level semantic patterns.

    Learns primitive co-occurrences from lexicon:
    - FEEL + GOOD + INTENSITY(+) → "ecstatic"
    - THINK + NOT → "doubt"
    """

    def __init__(self, **kwargs):
        super().__init__(name="word_scale", node_names=WORD_PRIMITIVES, **kwargs)

    def learn_from_decomposition(
        self,
        decomposition: List[Tuple[str, str, int]],
    ):
        """
        Learn from a word's decomposition.

        Args:
            decomposition: List of (primitive, role, polarity) tuples
        """
        # Build activations with polarity
        activations = {}
        for prim, role, polarity in decomposition:
            if prim in self._name_to_idx:
                activations[prim] = float(polarity)

        if len(activations) >= 2:
            self.learn(activations)

    def predict_primitives(
        self,
        seed_primitives: List[str],
        top_k: int = 5,
    ) -> List[Tuple[str, float]]:
        """
        Predict likely co-occurring primitives.

        Args:
            seed_primitives: Starting primitives
            top_k: Number of predictions

        Returns:
            List of (primitive, activation) tuples
        """
        activations = {p: 1.0 for p in seed_primitives if p in self._name_to_idx}
        output = self.activate(activations)

        # Exclude seeds
        predictions = [(name, level) for name, level in output.items() if name not in seed_primitives]

        return sorted(predictions, key=lambda x: -abs(x[1]))[:top_k]


# =============================================================================
# NETWORK COLLECTION
# =============================================================================


@dataclass
class ScaleNetworkCollection:
    """
    Collection of all scale-specific networks.

    Provides unified interface for learning and inference
    across all scales.
    """

    text: TextScaleNetwork = field(default_factory=TextScaleNetwork)
    paragraph: ParagraphScaleNetwork = field(default_factory=ParagraphScaleNetwork)
    sentence: SentenceScaleNetwork = field(default_factory=SentenceScaleNetwork)
    word: WordScaleNetwork = field(default_factory=WordScaleNetwork)

    def get_network(self, scale: str) -> LearningNetwork:
        """Get network by scale name."""
        return {
            "text": self.text,
            "paragraph": self.paragraph,
            "sentence": self.sentence,
            "word": self.word,
        }.get(scale)

    def learn_from_document(
        self,
        text_features: Dict[str, float] = None,
        paragraph_relations: List[str] = None,
        sentence_structures: List[Dict[str, float]] = None,
        word_decompositions: List[List[Tuple[str, str, int]]] = None,
    ):
        """
        Learn patterns from a complete document.

        Args:
            text_features: Document-level features
            paragraph_relations: Sequence of RST relations
            sentence_structures: Syntactic patterns per sentence
            word_decompositions: Primitive decompositions per word
        """
        if text_features:
            self.text.learn(text_features)

        if paragraph_relations:
            for i in range(len(paragraph_relations) - 1):
                self.paragraph.learn(
                    {
                        paragraph_relations[i]: 1.0,
                        paragraph_relations[i + 1]: 0.5,  # Transition
                    }
                )

        if sentence_structures:
            for struct in sentence_structures:
                self.sentence.learn(struct)

        if word_decompositions:
            for decomp in word_decompositions:
                self.word.learn_from_decomposition(decomp)

    def get_statistics(self) -> Dict[str, Dict]:
        """Get statistics for all networks."""
        return {
            "text": {
                "nodes": self.text.n_nodes,
                "updates": self.text.update_count,
                "weight_norm": float(np.linalg.norm(self.text.weights)),
            },
            "paragraph": {
                "nodes": self.paragraph.n_nodes,
                "updates": self.paragraph.update_count,
                "weight_norm": float(np.linalg.norm(self.paragraph.weights)),
            },
            "sentence": {
                "nodes": self.sentence.n_nodes,
                "updates": self.sentence.update_count,
                "weight_norm": float(np.linalg.norm(self.sentence.weights)),
            },
            "word": {
                "nodes": self.word.n_nodes,
                "updates": self.word.update_count,
                "weight_norm": float(np.linalg.norm(self.word.weights)),
            },
        }

    def save(self, directory: str):
        """Save all networks to directory."""
        import os

        os.makedirs(directory, exist_ok=True)

        self.text.save(os.path.join(directory, "text_network.json"))
        self.paragraph.save(os.path.join(directory, "paragraph_network.json"))
        self.sentence.save(os.path.join(directory, "sentence_network.json"))
        self.word.save(os.path.join(directory, "word_network.json"))

    @classmethod
    def load(cls, directory: str) -> "ScaleNetworkCollection":
        """Load all networks from directory."""
        import os

        collection = cls()
        collection.text = TextScaleNetwork.load(os.path.join(directory, "text_network.json"))
        collection.paragraph = ParagraphScaleNetwork.load(os.path.join(directory, "paragraph_network.json"))
        collection.sentence = SentenceScaleNetwork.load(os.path.join(directory, "sentence_network.json"))
        collection.word = WordScaleNetwork.load(os.path.join(directory, "word_network.json"))

        return collection


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    print("Scale-Specific Networks Tests")
    print("=" * 50)

    # Test 1: Text scale network
    text_net = TextScaleNetwork()
    print(f"✓ TextScaleNetwork: {text_net.n_nodes} nodes ({text_net.n_nodes**2} weights)")

    # Learn a pattern
    text_net.learn({"FORMAL": 1.0, "TECHNICAL": 0.8, "ACADEMIC": 0.9})
    text_net.learn({"FORMAL": 1.0, "TECHNICAL": 0.8, "ACADEMIC": 0.9})  # Reinforce

    # Test activation
    output = text_net.activate({"FORMAL": 1.0, "TECHNICAL": 0.8})
    print(f"  FORMAL+TECHNICAL → {list(output.keys())[:3]}")

    # Test 2: Paragraph scale network
    para_net = ParagraphScaleNetwork()
    print(f"✓ ParagraphScaleNetwork: {para_net.n_nodes} nodes")

    # Learn discourse patterns
    para_net.learn({"CAUSE": 1.0, "RESULT": 0.9})
    para_net.learn({"CLAIM": 1.0, "ELABORATION": 0.8})

    predictions = para_net.predict_next_relation("CAUSE")
    print(f"  After CAUSE → {predictions[:2]}")

    # Test 3: Sentence scale network
    sent_net = SentenceScaleNetwork()
    print(f"✓ SentenceScaleNetwork: {sent_net.n_nodes} nodes")

    # Learn syntactic pattern
    sent_net.learn({"SYN_SUBJ": 1.0, "SYN_PRED": 1.0, "SYN_OBJ": 0.8})

    struct = sent_net.predict_structure({"SYN_SUBJ": 1.0, "SYN_PRED": 1.0})
    print(f"  SUBJ+PRED → {list(struct.keys())[:3]}")

    # Test 4: Word scale network
    word_net = WordScaleNetwork()
    print(f"✓ WordScaleNetwork: {word_net.n_nodes} nodes")

    # Learn from decompositions
    word_net.learn_from_decomposition(
        [
            ("FEEL", "experiencer", 1),
            ("GOOD", "attribute", 1),
        ]
    )
    word_net.learn_from_decomposition(
        [
            ("FEEL", "experiencer", 1),
            ("GOOD", "attribute", 1),
            ("INTENSITY", "degree", 1),
        ]
    )

    predictions = word_net.predict_primitives(["FEEL", "GOOD"])
    print(f"  FEEL+GOOD → {predictions[:3]}")

    # Test 5: Collection
    collection = ScaleNetworkCollection()
    print("\n✓ ScaleNetworkCollection created")

    stats = collection.get_statistics()
    for scale, s in stats.items():
        print(f"  {scale}: {s['nodes']} nodes, {s['updates']} updates")

    # Test 6: Save/Load
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        collection.save(tmpdir)
        loaded = ScaleNetworkCollection.load(tmpdir)
        assert loaded.word.n_nodes == word_net.n_nodes
        print("\n✓ Save/Load verified")

    print("\n" + "=" * 50)
    print("All Scale-Specific Networks tests passed!")
