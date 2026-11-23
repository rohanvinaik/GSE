from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import hashlib
import numpy as np

from gse.vectors import SparseVector, bundle, weighted_bundle, permute, PrimitiveBasis, SYNTACTIC_SHIFTS
from gse.parser import ParsedSentence, Token, SemanticRole
from gse.lexicon_generator import Lexicon, LexiconEntry
from gse.parser import DEP_TO_ROLE

# Lazy import for frequency database (optional dependency)
_frequency_db = None

def get_frequency_db():
    """Get or create the global frequency database."""
    global _frequency_db
    if _frequency_db is None:
        try:
            from gse.frequency import FrequencyDatabase
            _frequency_db = FrequencyDatabase()
        except Exception:
            _frequency_db = None
    return _frequency_db

# Map SpaCy dependency relations to syntactic shift keys
DEP_TO_SYNTACTIC_ROLE = {
    # Core arguments
    "nsubj": "agent",
    "nsubjpass": "patient",  # Passive subject is semantically patient
    "dobj": "patient",
    "obj": "patient",
    "iobj": "recipient",
    "dative": "recipient",

    # Predicate
    "ROOT": "predicate",
    "root": "predicate",

    # Modifiers
    "amod": "attribute",
    "advmod": "manner",
    "nummod": "attribute",
    "nmod": "modifier",

    # Oblique/prepositional
    "obl": "oblique",
    "prep": "preposition",
    "pobj": "oblique",

    # Function words
    "det": "determiner",
    "aux": "auxiliary",
    "case": "preposition",

    # Coordination
    "conj": "conjunction",
    "cc": "conjunction",

    # Compounds and possession
    "compound": "modifier",
    "poss": "modifier",

    # Clausal
    "ccomp": "subordinate",
    "xcomp": "subordinate",
    "advcl": "subordinate",
    "relcl": "subordinate",
    "acl": "subordinate",
}

@dataclass
class CompositionTrace:
    """Record of how a vector was composed."""
    token_idx: int
    operation: str  # "lexical", "bind", "bundle"
    inputs: List[int]  # Indices of input traces
    result_vector: SparseVector

@dataclass
class SenseInfo:
    """Information about a selected word sense."""
    sense_id: str
    lemma: str
    pos: str
    decomposition: List[Tuple[str, str]]  # [(primitive, role), ...]

@dataclass
class CompositionResult:
    """Result of composing a sentence."""
    sentence: str
    sentence_vector: SparseVector
    token_vectors: Dict[int, SparseVector]
    sense_selections: Dict[int, SenseInfo]  # token_idx -> sense info
    traces: Dict[int, CompositionTrace]
    merkle_root: str
    confidence: float
    frequency_weights: Optional[Dict[int, float]] = None  # token_idx -> frequency weight

class Composer:
    """
    Semantic composition engine.
    Builds sentence meaning bottom-up from dependency structure.

    Supports frequency-weighted composition where:
    - High-frequency words provide structural scaffolding
    - Low-frequency words carry specific semantic content
    """

    def __init__(self, lexicon: Lexicon, basis: PrimitiveBasis, use_frequency_weights: bool = True, weight_profile: str = "content_focused"):
        self.lexicon = lexicon
        self.basis = basis
        self.use_frequency_weights = use_frequency_weights
        self._freq_db = get_frequency_db() if use_frequency_weights else None
        # Default to CONTENT_FOCUSED for semantic search (Rare=High)
        # But user can override for structure matching (Common=High)
        self.weight_profile = weight_profile
    
    def compose(self, parsed: ParsedSentence) -> CompositionResult:
        """
        Compose semantic vector for a parsed sentence.

        Process:
        1. Look up each content word in lexicon
        2. Get frequency weights for each token
        3. Compose bottom-up following dependency tree
        4. Bind modifiers with their heads
        5. Bundle (optionally weighted) coordinated elements
        6. Build Merkle tree for verification

        Frequency weighting ensures:
        - High-frequency words (the, a, is) provide structure with low weight
        - Low-frequency words (algorithm, photosynthesis) dominate with high weight
        """
        token_vectors: Dict[int, SparseVector] = {}
        sense_selections: Dict[int, SenseInfo] = {}
        traces: Dict[int, CompositionTrace] = {}
        confidence_scores: List[float] = []
        frequency_weights: Dict[int, float] = {}

        # Pre-fetch frequency weights for all tokens
        if self._freq_db and self.use_frequency_weights:
            from gse.frequency import WeightProfile  # Import here to avoid circular
            words = [t.lemma for t in parsed.tokens]
            freq_info = self._freq_db.batch_lookup(words)
            for idx, token in enumerate(parsed.tokens):
                info = freq_info.get(token.lemma.lower(), None)
                if info is None:
                    base_weight = 2.0  # Unknown = max weight
                else:
                    base_weight = info.weight
                
                # Apply profile
                frequency_weights[idx] = WeightProfile.apply(self.weight_profile, base_weight)

        # Process in bottom-up order
        for idx in parsed.bottom_up_order():
            token = parsed.tokens[idx]

            # Skip punctuation
            if token.pos.value == "PUNCT":
                continue

            # Step 1: Get lexical vector
            lex_entry = self.lexicon.lookup(token.lemma, token.pos.value)

            if lex_entry:
                base_vector = lex_entry.vector
                sense_selections[idx] = SenseInfo(
                    sense_id=lex_entry.sense_id,
                    lemma=lex_entry.lemma,
                    pos=lex_entry.pos,
                    decomposition=lex_entry.decomposition or []
                )
                confidence_scores.append(lex_entry.confidence)
            else:
                # Unknown word - use fallback
                base_vector = self._fallback_encoding(token)
                sense_selections[idx] = SenseInfo(
                    sense_id=f"{token.lemma}.{token.pos.value}.unknown",
                    lemma=token.lemma,
                    pos=token.pos.value,
                    decomposition=[]
                )
                confidence_scores.append(0.3)

            # Step 2: Get syntactic role for this token and apply permutation
            syntactic_role = self._get_syntactic_role(token)
            shift = SYNTACTIC_SHIFTS.get(syntactic_role, SYNTACTIC_SHIFTS["default"])

            # Apply syntactic permutation to encode position in sentence structure
            if shift > 0:
                base_vector = permute(base_vector, shift)

            # Step 3: Get dependents that have been processed
            dependents = parsed.get_dependents(idx)
            dependent_vectors = []
            dependent_weights = []
            dependent_traces = []

            for dep_token in dependents:
                if dep_token.idx in token_vectors:
                    # Dependent vectors are already permuted by their own syntactic role
                    # (this happened when they were processed in bottom-up order)
                    dep_vec = token_vectors[dep_token.idx]
                    if dep_vec.nnz > 0:  # Only include non-empty vectors
                        dependent_vectors.append(dep_vec)
                        dependent_weights.append(frequency_weights.get(dep_token.idx, 1.0))
                        dependent_traces.append(dep_token.idx)

            # Step 4: Compose by bundling (optionally weighted)
            # The permutation-based encoding ensures that:
            # - "dog bites man" ≠ "man bites dog" (different agent/patient permutations)
            # - Semantic content is preserved (same primitives)
            # - Syntactic structure is recoverable via inverse permutation
            if dependent_vectors:
                # Bundle base vector with dependent vectors
                all_components = [base_vector] + dependent_vectors
                all_weights = [frequency_weights.get(idx, 1.0)] + dependent_weights

                if self.use_frequency_weights and self._freq_db:
                    composed = weighted_bundle(all_components, all_weights)
                else:
                    composed = bundle(all_components)
                operation = "bundle"
            else:
                composed = base_vector
                operation = "lexical"

            token_vectors[idx] = composed
            traces[idx] = CompositionTrace(
                token_idx=idx,
                operation=operation,
                inputs=dependent_traces,
                result_vector=composed
            )

        # Sentence vector: weighted bundle of all content word vectors
        # This is the final sentence representation
        # NOTE: Include ADP for spatial/temporal prepositions (above/below/before/after)
        # These encode core semantic primitives in SPATIAL and TEMPORAL banks
        content_vectors = []
        content_weights = []
        for idx, v in token_vectors.items():
            if parsed.tokens[idx].pos.value in ["NOUN", "VERB", "ADJ", "ADV", "PROPN", "ADP"]:
                content_vectors.append(v)
                content_weights.append(frequency_weights.get(idx, 1.0))

        if content_vectors:
            if self.use_frequency_weights and self._freq_db:
                sentence_vector = weighted_bundle(content_vectors, content_weights)
            else:
                sentence_vector = bundle(content_vectors)
        else:
            # Fallback: use root's vector or random
            sentence_vector = token_vectors.get(parsed.root_idx)
            if sentence_vector is None:
                sentence_vector = SparseVector.random(self.basis.dimension, 100)

        # Compute Merkle root
        merkle_root = self._compute_merkle_root(parsed, token_vectors)

        # Overall confidence
        confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0

        return CompositionResult(
            sentence=parsed.text,
            sentence_vector=sentence_vector,
            token_vectors=token_vectors,
            sense_selections=sense_selections,
            traces=traces,
            merkle_root=merkle_root,
            confidence=confidence,
            frequency_weights=frequency_weights if self.use_frequency_weights else None
        )
    
    def _get_role_for_token(self, parsed: ParsedSentence, token: Token) -> Optional[str]:
        """Get semantic role for a token."""
        for role in parsed.roles:
            if role.token_idx == token.idx:
                return role.role

        # Fallback: map dependency relation to role
        return DEP_TO_ROLE.get(token.dep.lower())

    def _get_syntactic_role(self, token: Token) -> str:
        """
        Get syntactic role for permutation shift.

        Maps the token's dependency relation to a syntactic role key
        used for looking up the permutation shift in SYNTACTIC_SHIFTS.
        """
        dep = token.dep.lower()

        # Check if it's the root
        if token.is_root:
            return "predicate"

        # Map dependency to syntactic role
        if dep in DEP_TO_SYNTACTIC_ROLE:
            return DEP_TO_SYNTACTIC_ROLE[dep]

        # Fallback based on POS
        pos = token.pos.value
        if pos == "VERB":
            return "predicate"
        elif pos == "ADJ":
            return "attribute"
        elif pos == "ADV":
            return "manner"
        elif pos == "DET":
            return "determiner"
        elif pos == "AUX":
            return "auxiliary"
        elif pos in ["NOUN", "PRON"]:
            # Default nouns to theme if we can't determine agent/patient
            return "theme"

        return "default"
    
    def _fallback_encoding(self, token: Token) -> SparseVector:
        """Generate encoding for unknown word with special handling for letters/numbers."""
        lemma = token.lemma.lower()

        # Special handling for single letters
        if len(lemma) == 1 and lemma.isalpha():
            # Single letters get WORDS-based encoding (they're symbols/characters)
            decomp = [("WORDS", "theme"), ("PART", "attribute"), ("ONE", "quantity")]
            return self.lexicon.generator.encode_decomposition(decomp)

        # Special handling for numbers
        if lemma.isdigit() or self._is_number(lemma):
            # Numbers get quantity-based encoding
            decomp = [("ONE", "quantity"), ("SOMETHING", "theme"), ("PART", "attribute")]
            # Adjust based on magnitude
            try:
                num = float(lemma.replace(',', ''))
                if num == 0:
                    decomp = [("NOT", "quantity"), ("ONE", "theme"), ("BE", "state")]
                elif num == 1:
                    decomp = [("ONE", "quantity"), ("SAME", "attribute"), ("BE", "state")]
                elif num < 10:
                    decomp = [("SOME", "quantity"), ("ONE", "relation"), ("BE", "state")]
                elif num < 100:
                    decomp = [("MUCH", "quantity"), ("SOME", "attribute"), ("BE", "state")]
                else:
                    decomp = [("MUCH", "quantity"), ("BIG", "attribute"), ("BE", "state")]
            except ValueError:
                pass
            return self.lexicon.generator.encode_decomposition(decomp)

        # Special handling for ordinals (1st, 2nd, 3rd, etc.)
        if len(lemma) > 2 and lemma[:-2].isdigit() and lemma[-2:] in ('st', 'nd', 'rd', 'th'):
            decomp = [("ONE", "quantity"), ("AFTER", "relation"), ("BE", "state")]
            return self.lexicon.generator.encode_decomposition(decomp)

        # Default: use deterministic random based on lemma
        seed = int(hashlib.md5(token.lemma.encode()).hexdigest()[:8], 16)
        return SparseVector.random(self.basis.dimension, 200, seed=seed)

    def _is_number(self, s: str) -> bool:
        """Check if string represents a number (including decimals, negatives)."""
        try:
            float(s.replace(',', ''))
            return True
        except ValueError:
            return False
    
    def _compute_merkle_root(self, parsed: ParsedSentence, 
                             token_vectors: Dict[int, SparseVector]) -> str:
        """Compute Merkle root for semantic verification."""
        def hash_vector(v: SparseVector) -> str:
            # Hash the sparse representation
            # serialize() returns bytes, consistent.
            data = v.serialize()
            return hashlib.sha256(data).hexdigest()[:16]
        
        def combine_hashes(h1: str, h2: str) -> str:
            combined = h1 + h2
            return hashlib.sha256(combined.encode()).hexdigest()[:16]
        
        # Build Merkle tree bottom-up
        node_hashes: Dict[int, str] = {}
        
        for idx in parsed.bottom_up_order():
            if idx not in token_vectors:
                continue
            
            # Hash this node's composed vector
            vec_hash = hash_vector(token_vectors[idx])
            
            # Combine with children's hashes (dependents)
            dependents = parsed.get_dependents(idx)
            # Sort dependents by index to be deterministic
            dependents.sort(key=lambda t: t.idx)
            
            child_hashes = [node_hashes[d.idx] for d in dependents if d.idx in node_hashes]
            
            if child_hashes:
                # Combine sequentially
                for ch in child_hashes:
                    vec_hash = combine_hashes(vec_hash, ch)
            
            node_hashes[idx] = vec_hash
        
        # Root hash
        return node_hashes.get(parsed.root_idx, "")
