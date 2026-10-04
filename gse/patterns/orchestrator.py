#!/usr/bin/env python3
"""
Orchestrator Network for GSE Cross-Scale Coordination

The Orchestrator Network coordinates processing across all scales:
- Routes inputs to appropriate scale networks
- Combines outputs from multiple scales
- Manages confidence and error handling
- Maintains context across processing steps

Network structure (36 nodes):
- Scale routing (4): ROUTE_TEXT, ROUTE_PARA, ROUTE_SENT, ROUTE_WORD
- Task types (8): CLASSIFY, EXTRACT, COMPARE, GENERATE, etc.
- Confidence (4): HIGH, MEDIUM, LOW, AMBIGUOUS
- Combination (8): BUNDLE, BIND, PERMUTE, WEIGHT, etc.
- Error handling (4): RETRY, FALLBACK, ESCALATE, ACCEPT
- Context (8): PRIOR, POSTERIOR, RESET, CACHE_*, FREQUENCY, etc.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from gse.patterns.networks_v2 import (
    LearningNetwork,
    ScaleNetworkCollection,
)

# =============================================================================
# ORCHESTRATOR PRIMITIVES
# =============================================================================


class OrchestratorNode(Enum):
    """All 36 orchestrator network nodes."""

    # Scale routing (4)
    ROUTE_TEXT = auto()
    ROUTE_PARA = auto()
    ROUTE_SENT = auto()
    ROUTE_WORD = auto()

    # Task types (8)
    TASK_CLASSIFY = auto()
    TASK_EXTRACT = auto()
    TASK_COMPARE = auto()
    TASK_GENERATE = auto()
    TASK_SUMMARIZE = auto()
    TASK_TRANSLATE = auto()
    TASK_ANSWER = auto()
    TASK_DECOMPOSE = auto()

    # Confidence levels (4)
    CONF_HIGH = auto()
    CONF_MEDIUM = auto()
    CONF_LOW = auto()
    CONF_AMBIGUOUS = auto()

    # Combination operations (8)
    COMB_BUNDLE = auto()
    COMB_BIND = auto()
    COMB_PERMUTE = auto()
    COMB_WEIGHT = auto()
    COMB_NEGATE = auto()
    COMB_PROJECT = auto()
    COMB_AVERAGE = auto()
    COMB_SELECT = auto()

    # Error handling (4)
    ERR_RETRY = auto()
    ERR_FALLBACK = auto()
    ERR_ESCALATE = auto()
    ERR_ACCEPT = auto()

    # Context management (8)
    CTX_PRIOR = auto()
    CTX_POSTERIOR = auto()
    CTX_RESET = auto()
    CTX_CACHE_HIT = auto()
    CTX_CACHE_MISS = auto()
    CTX_FREQUENCY = auto()
    CTX_RECENCY = auto()
    CTX_SIMILARITY = auto()


# Node lists by category
SCALE_NODES = [
    OrchestratorNode.ROUTE_TEXT,
    OrchestratorNode.ROUTE_PARA,
    OrchestratorNode.ROUTE_SENT,
    OrchestratorNode.ROUTE_WORD,
]

TASK_NODES = [
    OrchestratorNode.TASK_CLASSIFY,
    OrchestratorNode.TASK_EXTRACT,
    OrchestratorNode.TASK_COMPARE,
    OrchestratorNode.TASK_GENERATE,
    OrchestratorNode.TASK_SUMMARIZE,
    OrchestratorNode.TASK_TRANSLATE,
    OrchestratorNode.TASK_ANSWER,
    OrchestratorNode.TASK_DECOMPOSE,
]

CONF_NODES = [
    OrchestratorNode.CONF_HIGH,
    OrchestratorNode.CONF_MEDIUM,
    OrchestratorNode.CONF_LOW,
    OrchestratorNode.CONF_AMBIGUOUS,
]

COMB_NODES = [
    OrchestratorNode.COMB_BUNDLE,
    OrchestratorNode.COMB_BIND,
    OrchestratorNode.COMB_PERMUTE,
    OrchestratorNode.COMB_WEIGHT,
    OrchestratorNode.COMB_NEGATE,
    OrchestratorNode.COMB_PROJECT,
    OrchestratorNode.COMB_AVERAGE,
    OrchestratorNode.COMB_SELECT,
]

ERR_NODES = [
    OrchestratorNode.ERR_RETRY,
    OrchestratorNode.ERR_FALLBACK,
    OrchestratorNode.ERR_ESCALATE,
    OrchestratorNode.ERR_ACCEPT,
]

CTX_NODES = [
    OrchestratorNode.CTX_PRIOR,
    OrchestratorNode.CTX_POSTERIOR,
    OrchestratorNode.CTX_RESET,
    OrchestratorNode.CTX_CACHE_HIT,
    OrchestratorNode.CTX_CACHE_MISS,
    OrchestratorNode.CTX_FREQUENCY,
    OrchestratorNode.CTX_RECENCY,
    OrchestratorNode.CTX_SIMILARITY,
]

ALL_ORCHESTRATOR_NODES = SCALE_NODES + TASK_NODES + CONF_NODES + COMB_NODES + ERR_NODES + CTX_NODES


# =============================================================================
# PROCESSING CONTEXT
# =============================================================================


@dataclass
class ProcessingContext:
    """
    Context maintained across processing steps.

    Tracks:
    - Processing history
    - Cached results
    - Confidence scores
    - Error counts
    """

    # History
    scale_history: List[str] = field(default_factory=list)
    task_history: List[str] = field(default_factory=list)
    result_history: List[Any] = field(default_factory=list)

    # Cache
    cache: Dict[str, Any] = field(default_factory=dict)
    cache_hits: int = 0
    cache_misses: int = 0

    # Confidence tracking
    confidence_scores: List[float] = field(default_factory=list)

    # Error tracking
    error_count: int = 0
    retry_count: int = 0

    # Statistics
    steps_processed: int = 0

    def add_step(
        self,
        scale: str,
        task: str,
        result: Any,
        confidence: float,
    ):
        """Record a processing step."""
        self.scale_history.append(scale)
        self.task_history.append(task)
        self.result_history.append(result)
        self.confidence_scores.append(confidence)
        self.steps_processed += 1

    @property
    def average_confidence(self) -> float:
        """Average confidence across all steps."""
        if not self.confidence_scores:
            return 0.0
        return sum(self.confidence_scores) / len(self.confidence_scores)

    def get_cache_key(self, input_data: Any) -> str:
        """Generate cache key for input."""
        return str(hash(str(input_data)))

    def check_cache(self, input_data: Any) -> Optional[Any]:
        """Check cache for result."""
        key = self.get_cache_key(input_data)
        if key in self.cache:
            self.cache_hits += 1
            return self.cache[key]
        self.cache_misses += 1
        return None

    def update_cache(self, input_data: Any, result: Any):
        """Update cache with result."""
        key = self.get_cache_key(input_data)
        self.cache[key] = result


# =============================================================================
# ORCHESTRATOR NETWORK
# =============================================================================


class OrchestratorNetwork(LearningNetwork):
    """
    Cross-scale coordination network.

    Routes processing through scale networks and combines results.
    Uses Hebbian learning to optimize routing decisions.
    """

    def __init__(self, scale_networks: ScaleNetworkCollection = None, **kwargs):
        """
        Initialize orchestrator.

        Args:
            scale_networks: Collection of scale-specific networks
        """
        super().__init__(name="orchestrator", node_names=[n.name for n in ALL_ORCHESTRATOR_NODES], **kwargs)

        self.scale_networks = scale_networks or ScaleNetworkCollection()

        # Build enum → index lookup
        self._enum_to_idx = {n: i for i, n in enumerate(ALL_ORCHESTRATOR_NODES)}

        # Processing context
        self.context = ProcessingContext()

    def get_enum_index(self, node: OrchestratorNode) -> int:
        """Get index for orchestrator node enum."""
        return self._enum_to_idx.get(node, -1)

    def activate_nodes(self, nodes: List[OrchestratorNode]) -> Dict[str, float]:
        """
        Activate specific orchestrator nodes.

        Args:
            nodes: List of nodes to activate

        Returns:
            Activation output from network
        """
        activations = {n.name: 1.0 for n in nodes}
        return self.activate(activations)

    def route_to_scale(
        self,
        input_features: Dict[str, float],
    ) -> Tuple[str, float]:
        """
        Determine which scale to route input to.

        Args:
            input_features: Input feature activations

        Returns:
            (scale_name, confidence) tuple
        """
        # Activate routing nodes based on input characteristics
        routing_activations = {}

        # Heuristic: more features → larger scale
        n_features = len(input_features)

        if n_features > 10:
            routing_activations[OrchestratorNode.ROUTE_TEXT.name] = 0.8
        elif n_features > 5:
            routing_activations[OrchestratorNode.ROUTE_PARA.name] = 0.8
        elif n_features > 2:
            routing_activations[OrchestratorNode.ROUTE_SENT.name] = 0.8
        else:
            routing_activations[OrchestratorNode.ROUTE_WORD.name] = 0.8

        # Propagate through network
        output = self.activate(routing_activations)

        # Find strongest scale activation
        scale_scores = {
            "text": output.get(OrchestratorNode.ROUTE_TEXT.name, 0),
            "paragraph": output.get(OrchestratorNode.ROUTE_PARA.name, 0),
            "sentence": output.get(OrchestratorNode.ROUTE_SENT.name, 0),
            "word": output.get(OrchestratorNode.ROUTE_WORD.name, 0),
        }

        best_scale = max(scale_scores, key=scale_scores.get)
        confidence = abs(scale_scores[best_scale])

        return best_scale, confidence

    # Top-down processing order for the constraint cascade.
    # Each scale's output is injected into the next as a `prior_*` prefixed
    # feature dict — coarser scales constrain finer ones.
    CASCADE_ORDER = ("text", "paragraph", "sentence", "word")

    def process(
        self,
        input_data: Dict[str, Any],
        task: OrchestratorNode = None,
        force_scale: str = None,
        cascade: bool = False,
    ) -> Dict[str, Any]:
        """
        Process input through appropriate scale network(s).

        Args:
            input_data: Input features by scale (keys: "text", "paragraph",
                "sentence", "word", and optionally "features" for routing).
            task: Task type node (default TASK_CLASSIFY).
            force_scale: Force a specific scale instead of routing.
            cascade: If True, run all four scales top-down with each scale's
                output feeding the next as constraint priors (the full
                constraint-cascade pipeline). Mutually exclusive with
                `force_scale`.

        Returns:
            Processing result with outputs and metadata. When cascade=True,
            result["outputs"] contains entries for each scale in order, and
            result["scales_used"] lists all scales reached.
        """
        result = {
            "outputs": {},
            "scales_used": [],
            "confidence": 0.0,
            "context": {},
        }

        # Check cache
        cached = self.context.check_cache(input_data)
        if cached is not None:
            return cached

        # Determine task
        if task is None:
            task = OrchestratorNode.TASK_CLASSIFY

        confidences: List[float] = []

        if cascade:
            # Top-down cascade: every scale runs, prior outputs propagated forward
            prior_output: Dict[str, float] = {}
            for scale in self.CASCADE_ORDER:
                network = self.scale_networks.get_network(scale)
                if network is None:
                    continue

                scale_input = dict(input_data.get(scale, {}))
                # Inject prior-scale activations as constraint features
                for prior_key, prior_val in prior_output.items():
                    scale_input[f"prior_{prior_key}"] = prior_val

                scale_output = network.activate(scale_input)
                result["outputs"][scale] = scale_output
                result["scales_used"].append(scale)
                if scale_output:
                    max_activation = max(abs(v) for v in scale_output.values())
                    confidences.append(max_activation)
                # Prior output for next scale = current scale's activations
                prior_output = dict(scale_output)
            scales = list(result["scales_used"])
        else:
            # Determine scale(s) to use
            if force_scale:
                scales = [force_scale]
            else:
                scale, _conf = self.route_to_scale(input_data.get("features", {}))
                scales = [scale]

            for scale in scales:
                network = self.scale_networks.get_network(scale)
                if network is None:
                    continue

                scale_input = input_data.get(scale, input_data.get("features", {}))
                scale_output = network.activate(scale_input)

                result["outputs"][scale] = scale_output
                result["scales_used"].append(scale)

                if scale_output:
                    max_activation = max(abs(v) for v in scale_output.values())
                    confidences.append(max_activation)

        # Aggregate confidence
        if confidences:
            result["confidence"] = sum(confidences) / len(confidences)

        # Update context
        self.context.add_step(
            scale=",".join(scales),
            task=task.name,
            result=result,
            confidence=result["confidence"],
        )

        # Cache result
        self.context.update_cache(input_data, result)

        # Learn from this processing step
        self._learn_from_step(scales, task, result["confidence"])

        return result

    def _learn_from_step(
        self,
        scales: List[str],
        task: OrchestratorNode,
        confidence: float,
    ):
        """Learn from a processing step."""
        # Build activations
        activations = {task.name: 1.0}

        # Scale routing
        scale_to_node = {
            "text": OrchestratorNode.ROUTE_TEXT,
            "paragraph": OrchestratorNode.ROUTE_PARA,
            "sentence": OrchestratorNode.ROUTE_SENT,
            "word": OrchestratorNode.ROUTE_WORD,
        }
        for scale in scales:
            node = scale_to_node.get(scale)
            if node:
                activations[node.name] = 1.0

        # Confidence
        if confidence > 0.8:
            activations[OrchestratorNode.CONF_HIGH.name] = confidence
        elif confidence > 0.5:
            activations[OrchestratorNode.CONF_MEDIUM.name] = confidence
        elif confidence > 0.2:
            activations[OrchestratorNode.CONF_LOW.name] = confidence
        else:
            activations[OrchestratorNode.CONF_AMBIGUOUS.name] = 1.0 - confidence

        self.learn(activations)

    def combine_results(
        self,
        results: List[Dict[str, Any]],
        method: OrchestratorNode = None,
    ) -> Dict[str, Any]:
        """
        Combine results from multiple processing steps.

        Args:
            results: List of processing results
            method: Combination method node

        Returns:
            Combined result
        """
        if not results:
            return {"outputs": {}, "confidence": 0.0}

        if method is None:
            method = OrchestratorNode.COMB_AVERAGE

        combined = {"outputs": {}, "confidence": 0.0}

        if method == OrchestratorNode.COMB_AVERAGE:
            # Average all outputs
            all_keys = set()
            for r in results:
                for scale_output in r.get("outputs", {}).values():
                    all_keys.update(scale_output.keys())

            for key in all_keys:
                values = []
                for r in results:
                    for scale_output in r.get("outputs", {}).values():
                        if key in scale_output:
                            values.append(scale_output[key])
                if values:
                    combined["outputs"][key] = sum(values) / len(values)

            # Average confidence
            confidences = [r.get("confidence", 0) for r in results]
            combined["confidence"] = sum(confidences) / len(confidences)

        elif method == OrchestratorNode.COMB_SELECT:
            # Select highest confidence result
            best = max(results, key=lambda r: r.get("confidence", 0))
            combined = best

        elif method == OrchestratorNode.COMB_BUNDLE:
            # Bundle all outputs (union)
            for r in results:
                for scale, scale_output in r.get("outputs", {}).items():
                    if scale not in combined["outputs"]:
                        combined["outputs"][scale] = {}
                    combined["outputs"][scale].update(scale_output)

            combined["confidence"] = max(r.get("confidence", 0) for r in results)

        return combined

    def handle_error(
        self,
        error: Exception,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle processing error.

        Args:
            error: The exception that occurred
            input_data: Original input data

        Returns:
            Recovery result or error response
        """
        self.context.error_count += 1

        # Activate error handling nodes
        error_activations = {OrchestratorNode.ERR_RETRY.name: 0.5}

        if self.context.retry_count < 3:
            # Retry with different scale
            self.context.retry_count += 1
            error_activations[OrchestratorNode.ERR_RETRY.name] = 1.0

            # Try fallback to smaller scale
            current_scale = self.context.scale_history[-1] if self.context.scale_history else "word"
            scale_order = ["text", "paragraph", "sentence", "word"]
            current_idx = scale_order.index(current_scale) if current_scale in scale_order else 0
            next_scale = scale_order[min(current_idx + 1, len(scale_order) - 1)]

            return self.process(input_data, force_scale=next_scale)
        else:
            # Escalate or accept
            error_activations[OrchestratorNode.ERR_ESCALATE.name] = 1.0

            return {
                "outputs": {},
                "confidence": 0.0,
                "error": str(error),
                "action": "escalate",
            }

    def get_statistics(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            "network": {
                "nodes": self.n_nodes,
                "updates": self.update_count,
                "weight_norm": float(np.linalg.norm(self.weights)),
            },
            "context": {
                "steps_processed": self.context.steps_processed,
                "average_confidence": self.context.average_confidence,
                "cache_hits": self.context.cache_hits,
                "cache_misses": self.context.cache_misses,
                "error_count": self.context.error_count,
            },
            "scale_networks": self.scale_networks.get_statistics(),
        }


# =============================================================================
# PIPELINE INTEGRATION
# =============================================================================


class OrchestratedPipeline:
    """
    Complete processing pipeline with orchestrator.

    Provides high-level interface for processing text through
    all scales with automatic routing and error handling.
    """

    def __init__(self):
        """Initialize pipeline with orchestrator."""
        self.scale_networks = ScaleNetworkCollection()
        self.orchestrator = OrchestratorNetwork(self.scale_networks)

    @staticmethod
    def _segment_paragraphs(text: str) -> List[str]:
        """Split text into paragraphs on blank lines."""
        import re

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        return paragraphs or ([text.strip()] if text.strip() else [])

    @staticmethod
    def _segment_sentences(paragraph: str) -> List[str]:
        """Split a paragraph into sentences on sentence-final punctuation."""
        import re

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", paragraph) if s.strip()]
        return sentences or ([paragraph.strip()] if paragraph.strip() else [])

    def process_hierarchical(
        self,
        text: str,
        task: str = "classify",
    ) -> Dict[str, Any]:
        """
        Process text through every scale (text → paragraph → sentence → word),
        running the constraint cascade top-down and composing vectors bottom-up.

        Args:
            text: Input text (one or more paragraphs).
            task: Task type for the orchestrator's learning signal.

        Returns:
            A dictionary with:
                - paragraphs:           List[str] (segmented)
                - sentences:            List[List[str]] (per paragraph)
                - text_features:        Dict[str, Any] from text-scale encoder
                  (genre, register, domain, coherence_score)
                - paragraph_features:   List[Dict[str, Any]] per paragraph
                - cascade_context:      Dict propagated top-down through scales
                - orchestrator_result:  Multi-scale activations from the cascade
                - scales_used:          List of scales actually engaged
                - confidence:           Aggregate confidence across scales
        """
        # 1. Top-down segmentation
        paragraphs = self._segment_paragraphs(text)
        sentences = [self._segment_sentences(p) for p in paragraphs]

        # 2. Text-level encoding — establishes the cascade context
        from gse.encoders import encode_paragraph, encode_text

        text_encoding = encode_text(text)
        cascade_context: Dict[str, Any] = {
            "genre": text_encoding.structure.genre.name,
            "register": text_encoding.structure.register.name,
            "domain": text_encoding.structure.domain.name,
            "coherence_score": text_encoding.coherence_score,
        }
        text_features = {
            **cascade_context,
            "paragraph_count": len(paragraphs),
            "bank_activations": text_encoding.bank_activations,
        }

        # 3. Paragraph-level encoding — refines cascade context per paragraph
        paragraph_features: List[Dict[str, Any]] = []
        for para in paragraphs:
            if not para:
                paragraph_features.append({})
                continue
            para_enc = encode_paragraph(para)
            paragraph_features.append(
                {
                    "coherence_score": float(para_enc.coherence_score),
                    "sentence_count": len(para_enc.structure.sentences),
                }
            )

        # 4. Multi-scale orchestrator cascade — runs all four networks
        scale_inputs = self._build_scale_inputs(
            text_features=text_features,
            paragraph_features=paragraph_features,
            sentences=sentences,
        )
        task_map = {
            "classify": OrchestratorNode.TASK_CLASSIFY,
            "extract": OrchestratorNode.TASK_EXTRACT,
            "compare": OrchestratorNode.TASK_COMPARE,
            "generate": OrchestratorNode.TASK_GENERATE,
            "summarize": OrchestratorNode.TASK_SUMMARIZE,
            "decompose": OrchestratorNode.TASK_DECOMPOSE,
        }
        task_node = task_map.get(task, OrchestratorNode.TASK_CLASSIFY)
        orch_result = self.orchestrator.process(
            scale_inputs,
            task=task_node,
            cascade=True,
        )

        return {
            "paragraphs": paragraphs,
            "sentences": sentences,
            "text_features": text_features,
            "paragraph_features": paragraph_features,
            "cascade_context": cascade_context,
            "orchestrator_result": orch_result,
            "scales_used": orch_result.get("scales_used", []),
            "confidence": orch_result.get("confidence", 0.0),
        }

    @staticmethod
    def _build_scale_inputs(
        text_features: Dict[str, Any],
        paragraph_features: List[Dict[str, Any]],
        sentences: List[List[str]],
    ) -> Dict[str, Any]:
        """Aggregate per-scale features into the orchestrator input format."""
        # Flatten sentences
        flat_sentences = [s for paragraph in sentences for s in paragraph]
        total_words = sum(len(s.split()) for s in flat_sentences)

        # Coerce non-numeric features to floats where possible
        def _to_features(d: Dict[str, Any]) -> Dict[str, Any]:
            return {k: v for k, v in d.items() if isinstance(v, (int, float))}

        para_summary = {
            "paragraph_count": float(len(paragraph_features)),
            "avg_sentences_per_para": (
                sum(p.get("sentence_count", 0) for p in paragraph_features) / max(1, len(paragraph_features))
            ),
        }

        return {
            "features": {
                "text_word_count": float(total_words),
                "paragraph_count": float(len(paragraph_features)),
            },
            "text": _to_features(text_features),
            "paragraph": para_summary,
            "sentence": {"sentence_count": float(len(flat_sentences))},
            "word": {"word_count": float(total_words)},
        }

    def process_text(
        self,
        text: str,
        task: str = "classify",
    ) -> Dict[str, Any]:
        """
        Process text through the pipeline.

        Args:
            text: Input text
            task: Task type (classify, extract, etc.)

        Returns:
            Processing result
        """
        # Map task string to node
        task_map = {
            "classify": OrchestratorNode.TASK_CLASSIFY,
            "extract": OrchestratorNode.TASK_EXTRACT,
            "compare": OrchestratorNode.TASK_COMPARE,
            "generate": OrchestratorNode.TASK_GENERATE,
            "summarize": OrchestratorNode.TASK_SUMMARIZE,
            "decompose": OrchestratorNode.TASK_DECOMPOSE,
        }
        task_node = task_map.get(task, OrchestratorNode.TASK_CLASSIFY)

        # Extract features (placeholder - would integrate with actual encoders)
        features = self._extract_features(text)

        # Process through orchestrator
        try:
            result = self.orchestrator.process(features, task=task_node)
        except Exception as e:
            result = self.orchestrator.handle_error(e, features)

        return result

    def _extract_features(self, text: str) -> Dict[str, Any]:
        """Extract features from text for processing."""
        # Placeholder - would integrate with actual feature extraction
        words = text.split()

        return {
            "features": {
                "length": len(words),
                "has_punctuation": any(c in text for c in ".,!?;:"),
            },
            "text": {},  # Would have text-level features
            "paragraph": {},  # Would have paragraph features
            "sentence": {},  # Would have sentence features
            "word": {},  # Would have word-level features
        }

    def learn_from_feedback(
        self,
        result: Dict[str, Any],
        correct: bool,
        feedback: Dict[str, Any] = None,
    ):
        """
        Learn from feedback on a result.

        Args:
            result: Previous processing result
            correct: Whether result was correct
            feedback: Additional feedback data
        """
        if correct:
            # Reinforce current patterns
            for scale in result.get("scales_used", []):
                network = self.scale_networks.get_network(scale)
                if network:
                    for output in result.get("outputs", {}).values():
                        network.learn(output)
        # If incorrect, patterns would need adjustment (negative learning)

    def get_statistics(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return self.orchestrator.get_statistics()


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    print("Orchestrator Network Tests")
    print("=" * 50)

    # Test 1: Create orchestrator
    orchestrator = OrchestratorNetwork()
    print(f"✓ OrchestratorNetwork: {orchestrator.n_nodes} nodes ({orchestrator.n_nodes**2} weights)")

    # Test 2: Route to scale
    scale, conf = orchestrator.route_to_scale({"feature1": 0.5, "feature2": 0.8})
    print(f"✓ Route 2 features → {scale} (conf={conf:.3f})")

    scale, conf = orchestrator.route_to_scale({f"f{i}": 0.5 for i in range(15)})
    print(f"✓ Route 15 features → {scale} (conf={conf:.3f})")

    # Test 3: Process input
    input_data = {
        "features": {"test1": 0.5, "test2": 0.8},
        "word": {"FEEL": 0.9, "GOOD": 0.7},
    }
    result = orchestrator.process(input_data, task=OrchestratorNode.TASK_CLASSIFY)
    print(f"✓ Process result: scales={result['scales_used']}, conf={result['confidence']:.3f}")

    # Test 4: Combine results
    results = [
        {"outputs": {"word": {"A": 0.5}}, "confidence": 0.8},
        {"outputs": {"word": {"B": 0.6}}, "confidence": 0.7},
    ]
    combined = orchestrator.combine_results(results, OrchestratorNode.COMB_AVERAGE)
    print(f"✓ Combined results: conf={combined['confidence']:.3f}")

    # Test 5: Context tracking
    stats = orchestrator.get_statistics()
    print(
        f"✓ Statistics: steps={stats['context']['steps_processed']}, "
        f"avg_conf={stats['context']['average_confidence']:.3f}"
    )

    # Test 6: Pipeline
    pipeline = OrchestratedPipeline()
    result = pipeline.process_text("The quick brown fox jumps.", task="classify")
    print(f"✓ Pipeline: processed text, scales={result.get('scales_used', [])}")

    # Test 7: Learning
    orchestrator.learn(
        {
            OrchestratorNode.TASK_CLASSIFY.name: 1.0,
            OrchestratorNode.ROUTE_WORD.name: 1.0,
            OrchestratorNode.CONF_HIGH.name: 0.9,
        }
    )
    print(f"✓ Learning: updates={orchestrator.update_count}")

    # Test 8: Associations
    assoc = orchestrator.get_associations(OrchestratorNode.TASK_CLASSIFY.name)
    print(f"✓ Associations for TASK_CLASSIFY: {assoc[:3]}")

    print("\n" + "=" * 50)
    print("All Orchestrator Network tests passed!")
