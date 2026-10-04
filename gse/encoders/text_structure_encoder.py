#!/usr/bin/env python3
"""
GSE Text Structure Encoder

Captures document-level features: genre, register, and domain.
Uses the TextBank primitives from primitives_v2.py.

Key features:
1. Genre detection (narrative, expository, argumentative, descriptive)
2. Register detection (formal, informal, technical, conversational)
3. Domain detection (academic, commercial, personal, institutional)
4. Entity tracking across paragraphs
5. Overall document structure analysis

The text encoder operates on ParagraphEncodings and produces a unified
TextEncoding that captures document-level semantics.
"""

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from gse.encoders.marker_detection import KeywordDetector
from gse.primitives_v2 import (
    TEXT_BANK_NAMES,
    D,
)

# =============================================================================
# TEXT CATEGORIES
# =============================================================================

class Genre(Enum):
    """Document genre types."""
    NARRATIVE = "narrative"
    EXPOSITORY = "expository"
    ARGUMENTATIVE = "argumentative"
    DESCRIPTIVE = "descriptive"
    MIXED = "mixed"


class Register(Enum):
    """Language register types."""
    FORMAL = "formal"
    INFORMAL = "informal"
    TECHNICAL = "technical"
    CONVERSATIONAL = "conversational"
    MIXED = "mixed"


class Domain(Enum):
    """Content domain types."""
    ACADEMIC = "academic"
    COMMERCIAL = "commercial"
    PERSONAL = "personal"
    INSTITUTIONAL = "institutional"
    MIXED = "mixed"


# =============================================================================
# DETECTION MARKERS
# =============================================================================

# Genre, register, and domain are NO LONGER detected by surface keywords. The legacy
# keyword bags classified by *vocabulary*, not *structure* (antithetical to GSE), and
# mis-fired constantly. Genre now comes from the trained Society-of-Mind register router
# over GSE's deterministic structural profile (gse/encoders/som_genre.py → gse/discourse).
# Register and domain are not load-bearing (Genesis discards them) and have no clean SoM
# mapping into these legacy enums, so they abstain to MIXED rather than keyword-guess.
# (Follow-up: surface the SoM register_class as a real register signal in its own
# taxonomy, instead of the FORMAL/INFORMAL enum.)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class EntityMention:
    """A mention of an entity in the document."""
    text: str
    paragraph_idx: int
    sentence_idx: int
    entity_type: str  # PERSON, ORG, LOCATION, etc.


@dataclass
class DocumentEntity:
    """An entity tracked across the document."""
    id: str
    canonical_form: str
    mentions: List[EntityMention]
    salience: float
    vector: np.ndarray


@dataclass
class TextStructure:
    """Parsed document structure."""
    raw_text: str
    paragraphs: List[str]
    genre: Genre
    genre_confidence: float
    register: Register
    register_confidence: float
    domain: Domain
    domain_confidence: float
    entities: List[DocumentEntity]
    topic_words: List[str]


@dataclass
class TextEncoding:
    """Result of text/document encoding."""
    vector: np.ndarray
    structure: TextStructure
    paragraph_vectors: List[np.ndarray]
    bank_activations: Dict[str, float]
    coherence_score: float


# =============================================================================
# CODEBOOKS
# =============================================================================

class TextCodebook:
    """Codebook for text-level primitive vectors."""

    def __init__(self, dim: int = D, seed: int = 42):
        self.dim = dim
        self.seed = seed
        self.genre_vectors: Dict[Genre, np.ndarray] = {}
        self.register_vectors: Dict[Register, np.ndarray] = {}
        self.domain_vectors: Dict[Domain, np.ndarray] = {}
        self._generate_vectors()

    def _generate_vectors(self):
        for genre in Genre:
            seed = int(hashlib.md5(
                f"{self.seed}_GENRE_{genre.value}".encode()
            ).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            vec = np.zeros(self.dim, dtype=np.float32)
            rand = rng.random(self.dim)
            vec[rand < 0.33] = 1.0
            vec[rand > 0.67] = -1.0
            self.genre_vectors[genre] = vec

        for register in Register:
            seed = int(hashlib.md5(
                f"{self.seed}_REGISTER_{register.value}".encode()
            ).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            vec = np.zeros(self.dim, dtype=np.float32)
            rand = rng.random(self.dim)
            vec[rand < 0.33] = 1.0
            vec[rand > 0.67] = -1.0
            self.register_vectors[register] = vec

        for domain in Domain:
            seed = int(hashlib.md5(
                f"{self.seed}_DOMAIN_{domain.value}".encode()
            ).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            vec = np.zeros(self.dim, dtype=np.float32)
            rand = rng.random(self.dim)
            vec[rand < 0.33] = 1.0
            vec[rand > 0.67] = -1.0
            self.domain_vectors[domain] = vec

    def get_genre(self, genre: Genre) -> np.ndarray:
        return self.genre_vectors[genre]

    def get_register(self, register: Register) -> np.ndarray:
        return self.register_vectors[register]

    def get_domain(self, domain: Domain) -> np.ndarray:
        return self.domain_vectors[domain]


# =============================================================================
# TEXT ENCODER
# =============================================================================

class TextStructureEncoder:
    """
    Encode documents preserving genre, register, and domain.

    Features:
    - Genre detection (narrative, expository, argumentative, descriptive)
    - Register detection (formal, informal, technical, conversational)
    - Domain detection (academic, commercial, personal, institutional)
    - Entity tracking across paragraphs
    - Topic continuity analysis
    """

    def __init__(
        self,
        dim: int = D,
        codebook: Optional[TextCodebook] = None,
        genre_detector=None,
        register_detector: Optional[KeywordDetector] = None,
        domain_detector: Optional[KeywordDetector] = None,
    ):
        self.dim = dim
        self.codebook = codebook or TextCodebook(dim=dim)

        # No keyword defaults. Genre is the SoM router (injected by
        # ``get_text_encoder``). Register/domain are no longer keyword-detected — a bare
        # encoder (or one with no injected detector) reports MIXED rather than guessing
        # from vocabulary. Detectors remain injectable for explicit/legacy use.
        self.genre_detector = genre_detector
        self.register_detector = register_detector
        self.domain_detector = domain_detector

    def encode(
        self,
        text: str,
        paragraph_vectors: Optional[List[np.ndarray]] = None,
    ) -> TextEncoding:
        """
        Encode a document into HDC space.

        Args:
            text: Raw document text
            paragraph_vectors: Pre-computed paragraph vectors (optional)

        Returns:
            TextEncoding with structure and vector
        """
        paragraphs = self._segment_paragraphs(text)

        if not paragraphs:
            return TextEncoding(
                vector=np.zeros(self.dim, dtype=np.float32),
                structure=TextStructure(
                    raw_text=text,
                    paragraphs=[],
                    genre=Genre.MIXED,
                    genre_confidence=0.0,
                    register=Register.MIXED,
                    register_confidence=0.0,
                    domain=Domain.MIXED,
                    domain_confidence=0.0,
                    entities=[],
                    topic_words=[],
                ),
                paragraph_vectors=[],
                bank_activations={name: 0.0 for name in TEXT_BANK_NAMES.values()},
                coherence_score=0.0,
            )

        # Create paragraph vectors if not provided
        para_vecs = []
        for i, para in enumerate(paragraphs):
            if paragraph_vectors and i < len(paragraph_vectors):
                vec = paragraph_vectors[i]
            else:
                vec = self._hash_vector(para)
            para_vecs.append(vec)

        # Detect text features
        genre, genre_conf = self._detect_genre(text)
        register, register_conf = self._detect_register(text)
        domain, domain_conf = self._detect_domain(text)

        # Extract entities
        entities = self._extract_entities(paragraphs)

        # Extract topic words
        topic_words = self._extract_topics(paragraphs)

        # Build document vector
        doc_vec = self._build_document_vector(
            para_vecs, genre, register, domain
        )

        # Compute bank activations
        bank_activations = self._compute_bank_activations(
            genre, register, domain
        )

        # Compute coherence
        coherence_score = self._compute_coherence(para_vecs)

        structure = TextStructure(
            raw_text=text,
            paragraphs=paragraphs,
            genre=genre,
            genre_confidence=genre_conf,
            register=register,
            register_confidence=register_conf,
            domain=domain,
            domain_confidence=domain_conf,
            entities=entities,
            topic_words=topic_words,
        )

        return TextEncoding(
            vector=doc_vec,
            structure=structure,
            paragraph_vectors=para_vecs,
            bank_activations=bank_activations,
            coherence_score=coherence_score,
        )

    def _segment_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        paragraphs = re.split(r'\n\n+', text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _hash_vector(self, text: str) -> np.ndarray:
        """Create hash-based vector for text."""
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        vec = np.zeros(self.dim, dtype=np.float32)
        nnz = min(len(text.split()) * 30, 1000)
        indices = rng.choice(self.dim, nnz, replace=False)
        for i, idx in enumerate(indices):
            vec[idx] = 1.0 if i % 2 == 0 else -1.0
        return vec

    @staticmethod
    def _pick_top_category(scores: dict, mixed_default, threshold: float = 0.3):
        """Normalize raw detector scores and choose the top category, or MIXED."""
        total = sum(scores.values()) + 1e-6
        normalized = {cat: score / total for cat, score in scores.items()}
        best = max(normalized.keys(), key=lambda c: normalized[c])
        confidence = normalized[best]
        if confidence < threshold:
            return mixed_default, confidence
        return best, confidence

    def _detect_genre(self, text: str) -> Tuple[Genre, float]:
        """Detect document genre via the SoM router (no keywords). Returns MIXED when
        no genre detector is wired (a bare encoder) or the router abstains."""
        if self.genre_detector is None:
            return Genre.MIXED, 0.0
        if hasattr(self.genre_detector, "classify"):     # SomGenreDetector
            return self.genre_detector.classify(text)
        # Back-compat: a keyword-style detector, if one is explicitly injected.
        return self._pick_top_category(self.genre_detector.detect(text), Genre.MIXED)

    def _detect_register(self, text: str) -> Tuple[Register, float]:
        """Register is no longer keyword-detected → MIXED unless a detector is injected."""
        if self.register_detector is None:
            return Register.MIXED, 0.0
        return self._pick_top_category(self.register_detector.detect(text), Register.MIXED)

    def _detect_domain(self, text: str) -> Tuple[Domain, float]:
        """Domain is no longer keyword-detected → MIXED unless a detector is injected."""
        if self.domain_detector is None:
            return Domain.MIXED, 0.0
        return self._pick_top_category(self.domain_detector.detect(text), Domain.MIXED)

    def _extract_entities(self, paragraphs: List[str]) -> List[DocumentEntity]:
        """Extract and track entities across paragraphs."""
        entity_mentions: Dict[str, List[EntityMention]] = {}

        # Simple capitalized word extraction (placeholder for NER)
        for para_idx, para in enumerate(paragraphs):
            sentences = re.split(r'[.!?]', para)
            for sent_idx, sent in enumerate(sentences):
                # Find capitalized words (simple entity extraction)
                words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', sent)
                for word in words:
                    if word not in entity_mentions:
                        entity_mentions[word] = []
                    entity_mentions[word].append(EntityMention(
                        text=word,
                        paragraph_idx=para_idx,
                        sentence_idx=sent_idx,
                        entity_type="UNKNOWN",
                    ))

        # Create DocumentEntity objects for entities with multiple mentions
        entities = []
        for i, (name, mentions) in enumerate(entity_mentions.items()):
            if len(mentions) >= 2:  # Only track recurring entities
                entities.append(DocumentEntity(
                    id=f"entity_{i}",
                    canonical_form=name,
                    mentions=mentions,
                    salience=len(mentions) / len(paragraphs),
                    vector=self._hash_vector(name),
                ))

        # Sort by salience
        entities.sort(key=lambda e: -e.salience)

        return entities[:10]  # Top 10 entities

    def _extract_topics(self, paragraphs: List[str]) -> List[str]:
        """Extract topic words that persist across paragraphs."""
        word_counts: Dict[str, int] = {}
        para_presence: Dict[str, Set[int]] = {}

        for para_idx, para in enumerate(paragraphs):
            words = set(re.findall(r'\b[a-z]{4,}\b', para.lower()))
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1
                if word not in para_presence:
                    para_presence[word] = set()
                para_presence[word].add(para_idx)

        # Words appearing in multiple paragraphs
        topic_words = [
            word for word, paras in para_presence.items()
            if len(paras) >= 2 and word_counts[word] >= 3
        ]

        # Sort by frequency
        topic_words.sort(key=lambda w: -word_counts[w])

        return topic_words[:20]  # Top 20 topic words

    def _build_document_vector(
        self,
        para_vecs: List[np.ndarray],
        genre: Genre,
        register: Register,
        domain: Domain,
    ) -> np.ndarray:
        """Build document vector encoding structure."""
        if not para_vecs:
            return np.zeros(self.dim, dtype=np.float32)

        components = []

        # Add genre vector
        genre_vec = self.codebook.get_genre(genre)
        components.append(genre_vec * 1.5)

        # Add register vector
        register_vec = self.codebook.get_register(register)
        components.append(register_vec * 1.2)

        # Add domain vector
        domain_vec = self.codebook.get_domain(domain)
        components.append(domain_vec * 1.2)

        # Bind each paragraph with its position
        for i, vec in enumerate(para_vecs):
            pos_weight = 1.0
            if i == 0:
                pos_weight = 1.5  # First paragraph weighted higher
            elif i == len(para_vecs) - 1:
                pos_weight = 1.3  # Last paragraph weighted higher
            components.append(vec * pos_weight)

        return self._bundle(components)

    def _bundle(self, vecs: List[np.ndarray]) -> np.ndarray:
        """Bundle vectors with thresholding."""
        if not vecs:
            return np.zeros(self.dim, dtype=np.float32)

        summed = np.stack(vecs).sum(axis=0)
        result = np.zeros(self.dim, dtype=np.float32)
        threshold = len(vecs) * 0.3
        result[summed > threshold] = 1.0
        result[summed < -threshold] = -1.0

        return result

    def _compute_bank_activations(
        self,
        genre: Genre,
        register: Register,
        domain: Domain,
    ) -> Dict[str, float]:
        """Compute activation per text bank."""
        activations = {name: 0.0 for name in TEXT_BANK_NAMES.values()}

        # Genre activates GENRE bank
        if genre != Genre.MIXED:
            activations["GENRE"] = 0.8

        # Register activates REGISTER bank
        if register != Register.MIXED:
            activations["REGISTER"] = 0.8

        # Domain activates DOMAIN bank
        if domain != Domain.MIXED:
            activations["DOMAIN"] = 0.8

        # Normalize
        total = sum(activations.values()) + 1e-6
        for bank in activations:
            activations[bank] /= total

        return activations

    def _compute_coherence(self, para_vecs: List[np.ndarray]) -> float:
        """Compute overall document coherence."""
        if len(para_vecs) < 2:
            return 1.0

        coherences = []
        for i in range(len(para_vecs) - 1):
            v1, v2 = para_vecs[i], para_vecs[i + 1]
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 > 0 and norm2 > 0:
                cos = np.dot(v1, v2) / (norm1 * norm2)
                coherences.append(float(cos))

        return float(np.mean(coherences)) if coherences else 1.0

    def similarity(self, enc1: TextEncoding, enc2: TextEncoding) -> float:
        """Compute cosine similarity between text encodings."""
        norm1 = np.linalg.norm(enc1.vector)
        norm2 = np.linalg.norm(enc2.vector)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(enc1.vector, enc2.vector) / (norm1 * norm2))


# Document-encoder cache, keyed by the GSEEncoder identity that backs the SoM genre
# detector (id 0 = the lazily-built default encoder for standalone callers).
_text_encoders: Dict[int, "TextStructureEncoder"] = {}
_default_gse_encoder = None


def _gse_encoder_for(encoder):
    """The sentence-level GSEEncoder the SoM genre profile runs on. Reuses the caller's
    (the bridge's warm one) when injected; else lazily builds and caches a default."""
    global _default_gse_encoder
    if encoder is not None:
        return encoder
    if _default_gse_encoder is None:
        from gse.api import GSEEncoder
        _default_gse_encoder = GSEEncoder()
    return _default_gse_encoder


def get_text_encoder(encoder=None) -> TextStructureEncoder:
    """Get or create the document encoder, wired with the SoM genre detector. ``encoder``
    is the sentence-level GSEEncoder the genre profile is computed on — inject the warm
    one to avoid a second load (the bridge does)."""
    key = id(encoder) if encoder is not None else 0
    enc = _text_encoders.get(key)
    if enc is None:
        from gse.encoders.som_genre import SomGenreDetector
        det = SomGenreDetector(_gse_encoder_for(encoder))
        enc = TextStructureEncoder(genre_detector=det)
        _text_encoders[key] = enc
    return enc


def encode_text(text: str, encoder=None) -> TextEncoding:
    """Convenience function to encode a document. Pass the warm GSEEncoder so the SoM
    genre profile reuses it instead of loading a second encoder."""
    return get_text_encoder(encoder).encode(text)
