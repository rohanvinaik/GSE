from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple, Any, Union
import time
import os
import torch
import numpy as np

from gse.vectors import PrimitiveBasis, SparseVector, D
from gse.parser import Parser, ParsedSentence
from gse.lexicon_generator import Lexicon
from gse.composer import Composer, CompositionResult
from gse.coherence import CoherenceChecker, CoherenceResult
from gse.cascade import ConstraintCascade, CascadeResult, create_cascade
from gse.primitives import Scale

# Multi-scale encoders
from gse.encoders.sentence_encoder import SentenceEncoder, SentenceEncoding
from gse.encoders.paragraph_encoder import ParagraphEncoder, ParagraphEncoding
from gse.encoders.conversation_encoder import ConversationEncoder, ConversationEncoding

@dataclass
class GSEConfig:
    """Configuration for GSE pipeline."""
    lexicon_path: str
    basis_path: str
    dimension: int = D  # Hadamard-OTP: 8192
    sparsity: float = 0.1  # Not used in new architecture
    coherence_threshold: float = 0.3
    strict_coherence_threshold: float = 0.5
    cache_size: int = 10000
    weight_profile: str = "content_focused"  # Default to semantic specificity

@dataclass
class GSEResult:
    """Complete result from GSE processing."""
    text: str
    vector: SparseVector
    confidence: float
    coherence_score: float
    coherence_passed: bool
    merkle_root: str
    sense_selections: Dict[int, str]
    anomalies: List[str]
    processing_time_ms: float
    
    def similarity(self, other: 'GSEResult') -> float:
        """Compute semantic similarity with another result."""
        return self.vector.cosine(other.vector)

class GSEWordAdapter:
    """Adapts GSEPipeline to act as a word/base encoder for SentenceEncoder."""
    def __init__(self, pipeline):
        self.pipeline = pipeline
    
    def encode(self, text: str) -> Any:
        # Use existing pipeline to process word/short phrase
        # We handle strict_coherence=False for base encoding
        result = self.pipeline.process(text, strict_coherence=False)
        
        # Convert SparseVector to torch.Tensor
        # SparseVector.to_dense() returns int8 numpy array
        dense = result.vector.to_dense()
        tensor_vec = torch.from_numpy(dense.astype(np.float32))
        
        # Return object with .vector attribute as expected by SentenceEncoder
        return type('WordEncoding', (), {'vector': tensor_vec})()

class GSEPipeline:
    """
    Main GSE processing pipeline.
    Enhanced with multi-scale encoding (sentence, paragraph, conversation).
    """
    
    def __init__(self, config: GSEConfig):
        self.config = config
        
        # Load components
        print("Loading GSE pipeline...")
        
        if not os.path.exists(config.basis_path):
             print(f"Warning: Basis not found at {config.basis_path}. Creating new temporary basis.")
             # Actually we should probably fail or generate one
             # Let's generate a temporary one for now or fail
             pass

        print("  Loading basis vectors...")
        try:
            self.basis = PrimitiveBasis.load(config.basis_path)
        except Exception as e:
            print(f"  Failed to load basis: {e}. Generating new.")
            from gse.primitives import PRIMITIVES, ROLES
            self.basis = PrimitiveBasis.generate(PRIMITIVES, ROLES)
        
        print("  Loading lexicon...")
        self.lexicon = Lexicon(config.lexicon_path, self.basis)
        
        print("  Initializing parser...")
        self.parser = Parser()
        
        print("  Initializing composer...")
        self.composer = Composer(
            self.lexicon, 
            self.basis, 
            weight_profile=config.weight_profile
        )
        
        print("  Initializing coherence checker...")
        self.coherence = CoherenceChecker(
            dimension=config.dimension,
            base_threshold=config.coherence_threshold,
            strict_threshold=config.strict_coherence_threshold
        )
        
        # Result cache (for base processing)
        self._cache: Dict[str, GSEResult] = {}
        
        # Initialize multi-scale encoders
        print("  Initializing multi-scale encoders...")
        self.word_adapter = GSEWordAdapter(self)
        self.sentence_encoder = SentenceEncoder(self.word_adapter, dim=config.dimension)
        self.paragraph_encoder = ParagraphEncoder(self.sentence_encoder, dim=config.dimension)
        self.conversation_encoder = ConversationEncoder(self.paragraph_encoder, dim=config.dimension)
        
        print("GSE pipeline ready.")
    
    def process(self, text: str, strict_coherence: bool = False) -> GSEResult:
        """
        Process text through the full GSE pipeline (Base Level).
        
        Args:
            text: Input text (single sentence recommended)
            strict_coherence: Use stricter coherence threshold
        
        Returns:
            GSEResult with semantic vector and metadata
        """
        # Check cache
        cache_key = f"{text}|{strict_coherence}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        start_time = time.perf_counter()
        
        # Step 1: Parse
        parsed = self.parser.parse_single(text)
        
        # Step 2: Compose
        composition = self.composer.compose(parsed)
        
        # Step 3: Check coherence
        coherence_result = self.coherence.check(
            composition, parsed, strict=strict_coherence
        )
        
        # Build result
        processing_time = (time.perf_counter() - start_time) * 1000
        
        result = GSEResult(
            text=text,
            vector=composition.sentence_vector,
            confidence=composition.confidence,
            coherence_score=coherence_result.score,
            coherence_passed=coherence_result.passed,
            merkle_root=composition.merkle_root,
            sense_selections=composition.sense_selections,
            anomalies=coherence_result.anomalies,
            processing_time_ms=processing_time
        )
        
        # Cache
        if len(self._cache) < self.config.cache_size:
            self._cache[cache_key] = result
        
        return result
    
    def process_content(
        self, 
        content: Union[str, List[Dict[str, str]]],
        level: str = "auto"
    ) -> Dict[str, Any]:
        """
        Process content at the appropriate level (Multi-Scale).
        
        Args:
            content: String or list of turn dicts
            level: "word", "sentence", "paragraph", "conversation", or "auto"
        
        Returns:
            Dict with vector, level, and metadata
        """
        if level == "auto":
            level = self._detect_level(content)
        
        if level == "word":
            # Use base process for word/phrase
            if not isinstance(content, str):
                raise ValueError("Content must be string for word level")
            res = self.process(content)
            # Return as tensor
            vec = torch.from_numpy(res.vector.to_dense().astype(np.float32))
            return {
                "vector": vec,
                "level": "word",
                "metadata": {
                    "text": content,
                    "confidence": res.confidence,
                    "coherence": res.coherence_score
                }
            }
        
        elif level == "sentence":
            if not isinstance(content, str):
                raise ValueError("Content must be string for sentence level")
            enc = self.sentence_encoder.encode(content)
            return {
                "vector": enc.vector,
                "level": "sentence",
                "metadata": {
                    "predicate": enc.structure.predicate,
                    "modality": enc.structure.modality.value,
                    "polarity": enc.structure.polarity,
                    "emotional_register": enc.structure.emotional_register.value,
                    "rhetorical_function": enc.structure.rhetorical_function.value,
                    "intensity": enc.structure.intensity_score,
                    "has_analogy": enc.structure.has_analogy,
                }
            }
        
        elif level == "paragraph":
            if not isinstance(content, str):
                raise ValueError("Content must be string for paragraph level")
            enc = self.paragraph_encoder.encode(content)
            return {
                "vector": enc.vector,
                "level": "paragraph",
                "metadata": {
                    "sentence_count": len(enc.structure.sentences),
                    "main_claim_idx": enc.structure.main_claim_idx,
                    "gestalt_points": len(enc.structure.gestalt_points),
                    "intensity_trajectory": enc.structure.intensity_trajectory.trajectory_type if enc.structure.intensity_trajectory else None,
                    "analogy_count": len(enc.structure.analogy_indices),
                }
            }
        
        elif level == "conversation":
            # content should be list of dicts
            if isinstance(content, str):
                # Try to wrap single string as a user turn? Or fail?
                # Let's assume list of dicts required
                raise ValueError("Content must be list of dicts for conversation level")
                
            enc = self.conversation_encoder.encode(content)
            return {
                "vector": enc.vector,
                "level": "conversation",
                "metadata": {
                    "turn_count": len(enc.structure.turns),
                    "goal": enc.structure.goal.value,
                    "resolution": enc.structure.resolution_status,
                    "gestalt_emergence_points": len(enc.structure.gestalt_emergence_points),
                    "has_meta_reflection": len(enc.structure.meta_reflection_points) > 0,
                }
            }
        
        else:
            raise ValueError(f"Unknown level: {level}")

    def _detect_level(self, content) -> str:
        """Auto-detect the appropriate encoding level."""
        if isinstance(content, list):
            # List of dicts -> conversation
            return "conversation"
        
        if not isinstance(content, str):
            # Fallback
            return "word"
        
        # Count sentences (simple heuristic)
        # Using spacy would be better but self.sentence_encoder._segment is not exposed easily
        # Just use simple split
        sentences = len([s for s in content.split('.') if s.strip()])
        
        if sentences <= 1:
            # Single sentence
            words = len(content.split())
            if words <= 3:
                return "word"
            return "sentence"
        elif sentences <= 5:
            return "paragraph"  # Small paragraph
        else:
            return "paragraph"  # Long text -> paragraph

    def process_batch(self, texts: List[str]) -> List[GSEResult]:
        """Process multiple texts (base level)."""
        return [self.process(text) for text in texts]
    
    def similarity(self, text1: str, text2: str) -> float:
        """Compute semantic similarity between two texts."""
        result1 = self.process(text1)
        result2 = self.process(text2)
        return result1.similarity(result2)
    
    def find_similar(self, query: str, candidates: List[str], top_k: int = 5) -> List[Tuple[str, float]]:
        """Find most similar texts from candidates."""
        query_result = self.process(query)
        
        scored = []
        for candidate in candidates:
            cand_result = self.process(candidate)
            sim = query_result.similarity(cand_result)
            scored.append((candidate, sim))
        
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]
    
    def is_anomalous(self, text: str) -> Tuple[bool, List[str]]:
        """Check if text is semantically anomalous."""
        result = self.process(text, strict_coherence=True)
        return not result.coherence_passed, result.anomalies


@dataclass
class CascadeConfig:
    """Configuration for Cascade-based pipeline."""
    lexicon_path: str
    basis_path: str
    networks_path: Optional[str] = None
    use_cache: bool = True
    cache_size: int = 1000


class CascadePipeline:
    """
    Production-ready GSE pipeline using Constraint Cascade architecture.

    This is the unified interface combining:
    - Multi-scale constraint propagation (Text → Paragraph → Sentence → Word)
    - Compound pattern learning networks (24-node word, 36-node orchestrator)
    - Merkle tree verification and caching
    - HDC vector composition
    """

    def __init__(self, config: CascadeConfig):
        self.config = config

        print("Loading GSE Cascade Pipeline...")

        # Create cascade
        self.cascade = create_cascade(
            lexicon_path=config.lexicon_path,
            basis_path=config.basis_path
        )
        # Configure caching
        self.cascade.use_cache = config.use_cache

        # Load trained networks if available
        if config.networks_path and os.path.exists(config.networks_path):
            print(f"  Loading trained networks from {config.networks_path}...")
            self.cascade.load_networks(config.networks_path)

        print("GSE Cascade Pipeline ready.")

    def process(self, text: str) -> GSEResult:
        """
        Process text through the constraint cascade.

        Args:
            text: Input text of any length

        Returns:
            GSEResult compatible with legacy interface
        """
        result = self.cascade.process(text)

        # Convert to GSEResult for compatibility
        return GSEResult(
            text=result.text,
            vector=result.vector,
            confidence=result.confidence,
            coherence_score=result.confidence,  # Use cascade confidence
            coherence_passed=result.confidence > 0.3,
            merkle_root=result.merkle_root,
            sense_selections={},  # Cascade handles this internally
            anomalies=result.ambiguities,
            processing_time_ms=result.processing_time * 1000
        )

    def process_with_frames(self, text: str) -> CascadeResult:
        """
        Process text and return full cascade result with scale frames.

        This provides access to activations at each scale level.
        """
        return self.cascade.process(text)

    def process_batch(self, texts: List[str]) -> List[GSEResult]:
        """Process multiple texts."""
        return [self.process(text) for text in texts]

    def similarity(self, text1: str, text2: str) -> float:
        """Compute semantic similarity between two texts."""
        result1 = self.process(text1)
        result2 = self.process(text2)
        return result1.vector.cosine(result2.vector)

    def find_similar(self, query: str, candidates: List[str], top_k: int = 5) -> List[Tuple[str, float]]:
        """Find most similar texts from candidates."""
        query_result = self.process(query)

        scored = []
        for candidate in candidates:
            cand_result = self.process(candidate)
            sim = query_result.vector.cosine(cand_result.vector)
            scored.append((candidate, sim))

        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    def train(self, lexicon_path: Optional[str] = None,
              corpus_dir: Optional[str] = None) -> Dict[str, int]:
        """
        Train the learning networks.

        Args:
            lexicon_path: Path to lexicon for word network training
            corpus_dir: Path to text corpus for orchestrator training

        Returns:
            Training statistics
        """
        return self.cascade.train(
            lexicon_path=lexicon_path or self.config.lexicon_path,
            corpus_dir=corpus_dir
        )

    def save_networks(self, path: str):
        """Save trained networks."""
        self.cascade.save_networks(path)

    def load_networks(self, path: str):
        """Load trained networks."""
        self.cascade.load_networks(path)

    def get_scale_activations(self, text: str) -> Dict[str, Dict[str, float]]:
        """Get primitive activations at each scale for debugging."""
        result = self.cascade.process(text)
        return {
            scale.value: dict(frame.active)
            for scale, frame in result.frames.items()
        }


# Convenience functions
def load_pipeline(lexicon_path: str = "data/lexicon.db",
                  basis_path: str = "data/basis.msgpack",
                  weight_profile: str = "content_focused",
                  use_cascade: bool = False,
                  networks_path: Optional[str] = None) -> Union[GSEPipeline, CascadePipeline]:
    """
    Load GSE pipeline.

    Args:
        lexicon_path: Path to lexicon database
        basis_path: Path to basis vectors
        weight_profile: Weight profile for legacy pipeline
        use_cascade: If True, use the new Constraint Cascade architecture
        networks_path: Path to trained networks (for cascade mode)

    Returns:
        GSEPipeline or CascadePipeline depending on use_cascade flag
    """
    if use_cascade:
        config = CascadeConfig(
            lexicon_path=lexicon_path,
            basis_path=basis_path,
            networks_path=networks_path
        )
        return CascadePipeline(config)
    else:
        config = GSEConfig(
            lexicon_path=lexicon_path,
            basis_path=basis_path,
            weight_profile=weight_profile
        )
        return GSEPipeline(config)


def load_cascade_pipeline(
    lexicon_path: str = "data/lexicon.db",
    basis_path: str = "data/basis.msgpack",
    networks_path: str = "data/networks"
) -> CascadePipeline:
    """Load the Constraint Cascade pipeline with trained networks."""
    config = CascadeConfig(
        lexicon_path=lexicon_path,
        basis_path=basis_path,
        networks_path=networks_path
    )
    return CascadePipeline(config)
