"""
Sentence-level semantic encoding.

Preserves predicate-argument structure through role binding.
Enhanced with emotional register and rhetorical function markers
derived from analysis of user's communication patterns.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import torch
import spacy
from pathlib import Path
import json
import hashlib
import re

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    pass # Will be handled by the user ensuring the model is downloaded


class Modality(Enum):
    DECLARATIVE = "declarative"
    INTERROGATIVE = "interrogative"
    RHETORICAL_QUESTION = "rhetorical_question"  # NEW: Common in user's style
    IMPERATIVE = "imperative"
    CONDITIONAL = "conditional"
    EXCLAMATORY = "exclamatory"


class TenseAspect(Enum):
    PAST_SIMPLE = "past_simple"
    PAST_PROGRESSIVE = "past_progressive"
    PAST_PERFECT = "past_perfect"
    PRESENT_SIMPLE = "present_simple"
    PRESENT_PROGRESSIVE = "present_progressive"
    PRESENT_PERFECT = "present_perfect"
    FUTURE_SIMPLE = "future_simple"
    FUTURE_PROGRESSIVE = "future_progressive"
    FUTURE_PERFECT = "future_perfect"
    INFINITIVE = "infinitive"
    UNKNOWN = "unknown"


class EmotionalRegister(Enum):
    """Emotional register markers derived from user's communication patterns."""
    NEUTRAL = "neutral"
    EMPHATIC = "emphatic"           # Intensity markers: CAPS, !!, profanity
    IRONIC = "ironic"               # Sarcasm markers: "congratulations", "of course"
    ANALYTICAL = "analytical"        # Hedged language, qualifications
    PASSIONATE = "passionate"        # Value-laden vocabulary
    RESIGNED = "resigned"            # Futility markers
    CONTEMPLATIVE = "contemplative"  # Meta-cognitive, reflective


class RhetoricalFunction(Enum):
    """Rhetorical function in argumentation."""
    CLAIM = "claim"                  # Main assertion
    EVIDENCE = "evidence"            # Supporting fact
    EXAMPLE = "example"              # Illustrative case
    ANALOGY = "analogy"              # Semantic shortcut
    QUALIFICATION = "qualification"  # Nested qualifier
    COUNTER = "counter"              # Opposing view
    META = "meta"                    # About the communication itself
    QUESTION = "question"            # Query/interrogative


@dataclass
class SentenceStructure:
    """Parsed sentence structure."""
    raw_text: str
    predicate: str
    predicate_lemma: str
    arguments: Dict[str, str]  # role -> filler
    modality: Modality
    tense_aspect: TenseAspect
    polarity: bool  # True = affirmative
    certainty: float  # 0.0-1.0
    
    # Enhanced features from user's cognitive patterns
    emotional_register: EmotionalRegister = EmotionalRegister.NEUTRAL
    rhetorical_function: RhetoricalFunction = RhetoricalFunction.CLAIM
    intensity_score: float = 0.5  # 0.0-1.0
    has_analogy: bool = False
    has_meta_commentary: bool = False
    nested_depth: int = 0  # Parenthetical/clause nesting
    
    # Optional rich features
    named_entities: List[Tuple[str, str]] = field(default_factory=list)
    dependency_root: Optional[str] = None


@dataclass
class SentenceEncoding:
    """Result of sentence encoding."""
    vector: torch.Tensor
    structure: SentenceStructure
    component_vectors: Dict[str, torch.Tensor]


class RoleCodebook:
    """
    Codebook of role vectors for argument binding.
    
    Roles are semantic relations like AGENT, PATIENT, INSTRUMENT, etc.
    Each role gets a fixed random vector for consistent binding.
    """
    
    STANDARD_ROLES = [
        # Dependency roles
        "nsubj", "nsubjpass", "dobj", "iobj", "pobj",
        "attr", "acomp", "xcomp", "ccomp", "advcl",
        "advmod", "neg", "aux", "auxpass", "agent",
        "prep", "prt", "amod", "compound", "det", "ROOT",
        # Semantic markers
        "PREDICATE", "MODALITY", "TENSE", "POLARITY", "CERTAINTY",
        # Enhanced markers (from user's cognitive patterns)
        "EMOTIONAL_REGISTER", "RHETORICAL_FUNCTION",
        "ANALOGY_SOURCE", "ANALOGY_TARGET",
        "META_LEVEL", "INTENSITY",
        "SARCASM", "EMPHASIS",
    ]
    
    def __init__(self, dim: int = 8192, seed: int = 42):
        self.dim = dim
        self.seed = seed
        self.vectors: Dict[str, torch.Tensor] = {}
        self._generate_role_vectors()
    
    def _generate_role_vectors(self):
        """Generate deterministic role vectors."""
        for role in self.STANDARD_ROLES:
            self.vectors[role] = self._generate_vector(role)
    
    def _generate_vector(self, role: str) -> torch.Tensor:
        """Generate a deterministic ternary vector for a role."""
        role_seed = int(hashlib.md5(f"{self.seed}_{role}".encode()).hexdigest()[:8], 16)
        torch.manual_seed(role_seed)
        
        vec = torch.zeros(self.dim)
        rand = torch.rand(self.dim)
        vec[rand < 0.33] = 1.0
        vec[rand > 0.67] = -1.0
        
        return vec
    
    def get(self, role: str) -> torch.Tensor:
        """Get role vector, generating if necessary."""
        if role not in self.vectors:
            self.vectors[role] = self._generate_vector(role)
        return self.vectors[role]
    
    def save(self, path: Path):
        """Save codebook to file."""
        data = {role: vec.tolist() for role, vec in self.vectors.items()}
        with open(path, 'w') as f:
            json.dump(data, f)
    
    def load(self, path: Path):
        """Load codebook from file."""
        with open(path) as f:
            data = json.load(f)
        self.vectors = {role: torch.tensor(vec) for role, vec in data.items()}


class SentenceEncoder:
    """
    Encode sentences preserving predicate-argument structure.
    Enhanced with emotional and rhetorical markers.
    """
    
    # Certainty markers
    CERTAINTY_BOOSTERS = {"certainly", "definitely", "absolutely", "clearly", "obviously", "undoubtedly"}
    CERTAINTY_REDUCERS = {"maybe", "perhaps", "possibly", "might", "could", "probably", "arguably"}
    
    # Sarcasm/irony markers (from user's patterns)
    SARCASM_MARKERS = {
        "congratulations", "of course", "obviously", "naturally", "sure",
        "well,", "oh,", "great", "wonderful", "brilliant", "genius",
    }
    
    # Intensity markers
    INTENSITY_MARKERS = {
        "fucking", "goddamn", "absolute", "utter", "complete", "total",
        "incredible", "unbelievable", "insane", "ridiculous", "important", "critical",
    }
    
    # Analogy markers
    ANALOGY_MARKERS = {
        "like", "similar to", "just as", "the same as", "reminds me of",
        "think of it as", "imagine", "picture", "it's as if",
    }
    
    # Meta-commentary markers
    META_MARKERS = {
        "i'm saying", "what i mean", "let me explain", "in other words",
        "to put it another way", "the point is", "what's interesting",
        "notice how", "observe that", "here's the thing",
    }
    
    # Resignation/futility markers (from psa_letters)
    RESIGNATION_MARKERS = {
        "hopeless", "futile", "pointless", "useless", "inevitable",
        "nothing matters", "why bother", "what's the point",
    }
    
    def __init__(
        self, 
        base_encoder,  # GSE word encoder
        role_codebook: Optional[RoleCodebook] = None,
        dim: int = 8192
    ):
        self.base = base_encoder
        self.roles = role_codebook or RoleCodebook(dim=dim)
        self.dim = dim
    
    def encode(self, sentence: str) -> SentenceEncoding:
        """Encode a sentence into HDC space."""
        # Ensure model is efficient
        if not hasattr(self, '_nlp_checked'):
             try:
                 global nlp
                 if 'nlp' not in globals():
                     nlp = spacy.load("en_core_web_sm")
             except Exception:
                 pass
             self._nlp_checked = True

        structure = self._parse(sentence)
        component_vectors = {}
        
        # Encode predicate
        pred_vec = self._encode_text(structure.predicate_lemma)
        component_vectors["predicate"] = pred_vec
        
        # Encode and bind arguments
        arg_vecs = []
        for role, filler in structure.arguments.items():
            filler_vec = self._encode_text(filler)
            role_vec = self.roles.get(role)
            bound = self._bind(role_vec, filler_vec)
            component_vectors[f"arg_{role}"] = bound
            arg_vecs.append(bound)
        
        # Encode modality
        modality_vec = self._encode_modality(structure.modality)
        component_vectors["modality"] = modality_vec
        
        # Encode tense
        tense_vec = self._encode_tense(structure.tense_aspect)
        component_vectors["tense"] = tense_vec
        
        # Encode emotional register (NEW)
        emotional_vec = self._encode_emotional_register(structure.emotional_register)
        component_vectors["emotional"] = emotional_vec
        
        # Encode rhetorical function (NEW)
        rhetorical_vec = self._encode_rhetorical_function(structure.rhetorical_function)
        component_vectors["rhetorical"] = rhetorical_vec
        
        # Bundle predicate with markers
        pred_marked = self._bind(self.roles.get("PREDICATE"), pred_vec)
        modality_marked = self._bind(self.roles.get("MODALITY"), modality_vec)
        tense_marked = self._bind(self.roles.get("TENSE"), tense_vec)
        emotional_marked = self._bind(self.roles.get("EMOTIONAL_REGISTER"), emotional_vec)
        rhetorical_marked = self._bind(self.roles.get("RHETORICAL_FUNCTION"), rhetorical_vec)
        
        # Add analogy marker if detected
        if structure.has_analogy:
            analogy_vec = self.roles.get("ANALOGY_SOURCE")
            arg_vecs.append(analogy_vec * 1.5)  # Weight analogies heavily
        
        # Add meta-commentary marker if detected
        if structure.has_meta_commentary:
            meta_vec = self.roles.get("META_LEVEL")
            arg_vecs.append(meta_vec)
        
        # Bundle all components
        all_vecs = [pred_marked, modality_marked, tense_marked, 
                    emotional_marked, rhetorical_marked] + arg_vecs
        
        # Weight by intensity score
        all_vecs = [v * (0.5 + structure.intensity_score) for v in all_vecs]
        
        sentence_vec = self._bundle(all_vecs)
        
        # Apply polarity
        if not structure.polarity:
            sentence_vec = self._negate(sentence_vec)
            component_vectors["polarity_applied"] = torch.tensor([-1.0])
        else:
            component_vectors["polarity_applied"] = torch.tensor([1.0])
        
        # Weight by certainty
        sentence_vec = sentence_vec * structure.certainty
        
        # Handle sarcasm (invert polarity partially)
        if structure.emotional_register == EmotionalRegister.IRONIC:
            # Blend original and inverted
            sentence_vec = sentence_vec * 0.3 + self._negate(sentence_vec) * 0.7
        
        # Normalize
        sentence_vec = self._normalize(sentence_vec)
        
        return SentenceEncoding(
            vector=sentence_vec,
            structure=structure,
            component_vectors=component_vectors
        )
    
    def _parse(self, sentence: str) -> SentenceStructure:
        """Parse sentence into structured representation."""
        doc = nlp(sentence)
        
        # Find root
        root = None
        for token in doc:
            if token.dep_ == "ROOT":
                root = token
                break
        
        if root is None:
            for token in doc:
                if token.pos_ == "VERB":
                    root = token
                    break
            if root is None:
                root = doc[0]
        
        predicate = root.text
        predicate_lemma = root.lemma_
        
        # Extract arguments
        arguments = {}
        for child in root.children:
            if child.dep_ in ["nsubj", "nsubjpass", "dobj", "iobj", "pobj", 
                             "attr", "acomp", "xcomp", "ccomp", "agent"]:
                span = self._get_span(child)
                arguments[child.dep_] = span
        
        # Check for prepositional phrases
        for child in root.children:
            if child.dep_ == "prep":
                prep_text = child.text
                for pchild in child.children:
                    if pchild.dep_ == "pobj":
                        span = self._get_span(pchild)
                        arguments[f"prep_{prep_text}"] = span
        
        # Detect properties
        modality = self._detect_modality(doc, sentence)
        tense_aspect = self._detect_tense(root)
        polarity = self._detect_polarity(doc)
        certainty = self._detect_certainty(doc)
        
        # Enhanced detection (NEW)
        emotional_register = self._detect_emotional_register(sentence, doc)
        rhetorical_function = self._detect_rhetorical_function(sentence, doc)
        intensity_score = self._detect_intensity(sentence)
        has_analogy = self._detect_analogy(sentence)
        has_meta = self._detect_meta_commentary(sentence)
        nested_depth = self._count_nesting(sentence)
        
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        
        return SentenceStructure(
            raw_text=sentence,
            predicate=predicate,
            predicate_lemma=predicate_lemma,
            arguments=arguments,
            modality=modality,
            tense_aspect=tense_aspect,
            polarity=polarity,
            certainty=certainty,
            emotional_register=emotional_register,
            rhetorical_function=rhetorical_function,
            intensity_score=intensity_score,
            has_analogy=has_analogy,
            has_meta_commentary=has_meta,
            nested_depth=nested_depth,
            named_entities=entities,
            dependency_root=root.text
        )
    
    def _get_span(self, token) -> str:
        """Get the full span of a token including its dependents."""
        subtree_tokens = sorted(token.subtree, key=lambda t: t.i)
        return " ".join(t.text for t in subtree_tokens)
    
    def _detect_modality(self, doc, sentence: str) -> Modality:
        """Detect sentence modality."""
        text = sentence.strip()
        
        if text.endswith("?"):
            # Check if rhetorical (contains markers or has no real answer expected)
            rhetorical_patterns = [
                r"what.*think", r"do you really", r"are you telling me",
                r"who.*cares", r"why.*bother", r"how.*supposed to",
                r"\?\?+",  # Multiple question marks
            ]
            text_lower = text.lower()
            if any(re.search(p, text_lower) for p in rhetorical_patterns):
                return Modality.RHETORICAL_QUESTION
            return Modality.INTERROGATIVE
        
        if text.endswith("!"):
            return Modality.EXCLAMATORY
        
        first_token = doc[0]
        if first_token.pos_ == "VERB" and first_token.dep_ == "ROOT":
            has_subject = any(child.dep_ in ["nsubj", "nsubjpass"] for child in first_token.children)
            if not has_subject:
                return Modality.IMPERATIVE
        
        conditional_markers = {"if", "unless", "provided", "assuming", "suppose", "given"}
        if any(token.text.lower() in conditional_markers for token in doc):
            return Modality.CONDITIONAL
        
        return Modality.DECLARATIVE
    
    def _detect_tense(self, root) -> TenseAspect:
        """Detect tense and aspect from the root verb."""
        if root.pos_ != "VERB":
            return TenseAspect.UNKNOWN
        
        tag = root.tag_
        
        has_progressive = any(child.text.lower() in ["is", "am", "are", "was", "were", "been", "being"] 
                             for child in root.children if child.dep_ in ["aux", "auxpass"])
        has_perfect = any(child.text.lower() in ["has", "have", "had"] 
                         for child in root.children if child.dep_ == "aux")
        has_future = any(child.text.lower() in ["will", "shall", "going"] 
                        for child in root.children if child.dep_ == "aux")
        
        if has_future:
            if has_perfect:
                return TenseAspect.FUTURE_PERFECT
            elif has_progressive:
                return TenseAspect.FUTURE_PROGRESSIVE
            else:
                return TenseAspect.FUTURE_SIMPLE
        elif tag in ["VBD", "VBN"]:
            if has_perfect:
                return TenseAspect.PAST_PERFECT
            elif has_progressive:
                return TenseAspect.PAST_PROGRESSIVE
            else:
                return TenseAspect.PAST_SIMPLE
        elif tag in ["VBP", "VBZ", "VB"]:
            if has_perfect:
                return TenseAspect.PRESENT_PERFECT
            elif has_progressive:
                return TenseAspect.PRESENT_PROGRESSIVE
            else:
                return TenseAspect.PRESENT_SIMPLE
        elif tag == "VB":
            return TenseAspect.INFINITIVE
        
        return TenseAspect.UNKNOWN
    
    def _detect_polarity(self, doc) -> bool:
        """Detect if sentence is affirmative (True) or negative (False)."""
        negation_words = {"not", "n't", "never", "no", "none", "nobody", "nothing", "neither", "nowhere"}
        neg_count = sum(1 for token in doc if token.text.lower() in negation_words or token.dep_ == "neg")
        return neg_count % 2 == 0
    
    def _detect_certainty(self, doc) -> float:
        """Detect certainty level (0.0 to 1.0)."""
        certainty = 0.8
        for token in doc:
            word = token.text.lower()
            if word in self.CERTAINTY_BOOSTERS:
                certainty = min(1.0, certainty + 0.15)
            elif word in self.CERTAINTY_REDUCERS:
                certainty = max(0.3, certainty - 0.2)
        return certainty
    
    def _detect_emotional_register(self, sentence: str, doc) -> EmotionalRegister:
        """Detect emotional register based on user's communication patterns."""
        text_lower = sentence.lower()
        
        # Check for intensity markers (emphatic)
        if any(m in text_lower for m in self.INTENSITY_MARKERS):
            return EmotionalRegister.EMPHATIC
        
        # Check for all caps (emphatic)
        caps_ratio = sum(1 for c in sentence if c.isupper()) / max(len(sentence), 1)
        if caps_ratio > 0.3:
            return EmotionalRegister.EMPHATIC
        
        # Check for sarcasm/irony markers
        if any(m in text_lower for m in self.SARCASM_MARKERS):
            return EmotionalRegister.IRONIC
        
        # Check for resignation markers
        if any(m in text_lower for m in self.RESIGNATION_MARKERS):
            return EmotionalRegister.RESIGNED
        
        # Check for meta-commentary (contemplative)
        if any(m in text_lower for m in self.META_MARKERS):
            return EmotionalRegister.CONTEMPLATIVE
        
        # Check for analytical hedging
        analytical_markers = {"however", "although", "nevertheless", "therefore", "thus"}
        if any(m in text_lower for m in analytical_markers):
            return EmotionalRegister.ANALYTICAL
        
        return EmotionalRegister.NEUTRAL
    
    def _detect_rhetorical_function(self, sentence: str, doc) -> RhetoricalFunction:
        """Detect rhetorical function of the sentence."""
        text_lower = sentence.lower()
        
        # Check for example markers
        example_markers = {"for example", "for instance", "e.g.", "such as", "like when"}
        if any(m in text_lower for m in example_markers):
            return RhetoricalFunction.EXAMPLE
        
        # Check for analogy markers
        if any(m in text_lower for m in self.ANALOGY_MARKERS):
            return RhetoricalFunction.ANALOGY
        
        # Check for meta-commentary
        if any(m in text_lower for m in self.META_MARKERS):
            return RhetoricalFunction.META
        
        # Check for qualification
        qual_markers = {"but", "however", "although", "though", "except"}
        if any(m in text_lower for m in qual_markers):
            return RhetoricalFunction.QUALIFICATION
        
        # Check for counter-argument
        counter_markers = {"on the other hand", "conversely", "in contrast", "opponents say"}
        if any(m in text_lower for m in counter_markers):
            return RhetoricalFunction.COUNTER
        
        # Check for evidence
        evidence_markers = {"studies show", "research indicates", "according to", "data shows"}
        if any(m in text_lower for m in evidence_markers):
            return RhetoricalFunction.EVIDENCE
        
        # Check if question
        if sentence.strip().endswith("?"):
            return RhetoricalFunction.QUESTION
        
        return RhetoricalFunction.CLAIM
    
    def _detect_intensity(self, sentence: str) -> float:
        """Detect intensity score 0.0-1.0."""
        intensity = 0.5
        text_lower = sentence.lower()
        
        # Intensity boosters
        for marker in self.INTENSITY_MARKERS:
            if marker in text_lower:
                intensity = min(1.0, intensity + 0.15)
        
        # All caps words
        words = sentence.split()
        caps_words = sum(1 for w in words if w.strip(".,!?\"'").isupper() and len(w.strip(".,!?\"'")) > 2)
        intensity = min(1.0, intensity + caps_words * 0.1)
        
        # Multiple exclamation/question marks
        if "!!" in sentence or "??" in sentence:
            intensity = min(1.0, intensity + 0.2)
        
        return intensity
    
    def _detect_analogy(self, sentence: str) -> bool:
        """Detect if sentence contains an analogy."""
        text_lower = sentence.lower()
        return any(m in text_lower for m in self.ANALOGY_MARKERS)
    
    def _detect_meta_commentary(self, sentence: str) -> bool:
        """Detect if sentence is meta-commentary about communication."""
        text_lower = sentence.lower()
        return any(m in text_lower for m in self.META_MARKERS)
    
    def _count_nesting(self, sentence: str) -> int:
        """Count parenthetical/em-dash nesting depth."""
        max_depth = 0
        current_depth = 0
        for char in sentence:
            if char in "([":
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char in ")]":
                current_depth = max(0, current_depth - 1)
        # Also count em-dashes
        max_depth += sentence.count("--") // 2
        return max_depth
    
    def _encode_text(self, text: str) -> torch.Tensor:
        """Encode text using base encoder."""
        if hasattr(self.base, 'encode'):
            result = self.base.encode(text)
            if isinstance(result, dict):
                return result.get("hdc_vector", torch.zeros(self.dim))
            # Handle other return types if necessary (e.g., SentenceEncoding object, or plain vector)
            if hasattr(result, 'vector'):
                return result.vector
            if isinstance(result, torch.Tensor):
                return result
            # Fallback
            return torch.zeros(self.dim)
        else:
            return self._hash_encode(text)
            
    def _hash_encode(self, text: str) -> torch.Tensor:
        """Fallback hash encoding."""
        # Simple random projection seeded by text
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        torch.manual_seed(seed)
        vec = torch.zeros(self.dim)
        rand = torch.rand(self.dim)
        vec[rand < 0.33] = 1.0
        vec[rand > 0.67] = -1.0
        return vec

    def _bind(self, v1: torch.Tensor, v2: torch.Tensor) -> torch.Tensor:
        """Bind two vectors (element-wise multiplication)."""
        return v1 * v2

    def _bundle(self, vectors: List[torch.Tensor]) -> torch.Tensor:
        """Bundle vectors (element-wise sum)."""
        if not vectors:
            return torch.zeros(self.dim)
        return sum(vectors)

    def _negate(self, vec: torch.Tensor) -> torch.Tensor:
        """Negate vector."""
        return -vec

    def _normalize(self, vec: torch.Tensor) -> torch.Tensor:
        """Normalize vector roughly to {-1, 0, 1} ternary structure if desired, 
        or just keep it as float for composition.
        
        The spec suggests ternary vectors, but bundles usually become non-ternary 
        integers until threshold, or we keep them as floats for weighted superposition.
        Here we'll do simple L2 normalization for now to keep values in reasonable range.
        """
        norm = torch.norm(vec)
        if norm > 0:
            return vec / norm
        return vec
    
    def _encode_modality(self, modality: Modality) -> torch.Tensor:
        return self.roles.get(f"MODALITY_{modality.value.upper()}")

    def _encode_tense(self, tense: TenseAspect) -> torch.Tensor:
        return self.roles.get(f"TENSE_{tense.value.upper()}")

    def _encode_emotional_register(self, register: EmotionalRegister) -> torch.Tensor:
        return self.roles.get(f"REGISTER_{register.value.upper()}")

    def _encode_rhetorical_function(self, func: RhetoricalFunction) -> torch.Tensor:
        return self.roles.get(f"RHETORICAL_{func.value.upper()}")

    def similarity(self, enc1: SentenceEncoding, enc2: SentenceEncoding) -> float:
        """Compute cosine similarity between sentence encodings."""
        return torch.nn.functional.cosine_similarity(
            enc1.vector.unsqueeze(0),
            enc2.vector.unsqueeze(0)
        ).item()
