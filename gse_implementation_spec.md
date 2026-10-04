# Geometric Semantic Encoding (GSE) Implementation Specification

## For Autonomous Implementation by LLM Coding Agents

**Version 1.0 | December 2025**

---

## Executive Summary

You are implementing a **Geometric Semantic Encoding (GSE)** system—a symbolic NLP pipeline that encodes natural language as high-dimensional sparse ternary vectors. The system decomposes words into universal semantic primitives, composes sentence meaning through algebraic operations, and provides interpretable, verifiable semantic representations.

This is a standalone system designed for efficiency, interpretability, and eventual integration with LLM-based AI systems.

**Key Properties:**
- Deterministic: same input → same output
- Interpretable: can trace exactly how meaning was constructed
- Efficient: O(n) processing for most sentences, ~2GB total storage
- Verifiable: Merkle-like structure enables integrity checking

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Technical Stack](#2-technical-stack)
3. [Phase 1: Vector Foundation](#3-phase-1-vector-foundation)
4. [Phase 2: Lexicon Generation](#4-phase-2-lexicon-generation)
5. [Phase 3: Parser Integration](#5-phase-3-parser-integration)
6. [Phase 4: Composition Engine](#6-phase-4-composition-engine)
7. [Phase 5: Coherence & Verification](#7-phase-5-coherence-verification)
8. [Phase 6: API & Integration](#8-phase-6-api-integration)
9. [Testing Strategy](#9-testing-strategy)
10. [File Structure](#10-file-structure)
11. [Data Specifications](#11-data-specifications)
12. [Reference Implementation Code](#12-reference-implementation-code)

---

## 1. System Overview

### 1.1 What GSE Does

```
Input: "The bank approved the loan."
       ↓
Output: {
  vector: SparseVector[10000],      # Semantic representation
  confidence: 0.94,                  # How certain the parse is
  merkle_root: "a3f2...",           # Integrity hash
  parse_trace: {...},               # How we got here
  sense_selections: {               # Which word senses were chosen
    "bank": "financial_institution",
    "approved": "officially_accept",
    "loan": "borrowed_money"
  }
}
```

### 1.2 Core Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      GSE PIPELINE                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 0: Tokenization           O(n)    Always runs       │
│     ↓                                                       │
│  Layer 1: Morphological Analysis O(n)    Always runs       │
│     ↓                                                       │
│  Layer 2: Syntactic Parsing      O(n)    Always runs       │
│     ↓                                                       │
│  Layer 3: Lexical Lookup         O(n)    Always runs       │
│     ↓                                                       │
│  Layer 4: Semantic Composition   O(n·d)  Always runs       │
│     ↓                                                       │
│  Layer 5: Coherence Check        O(d)    Always runs       │
│     ↓                                                       │
│  Layer 6: Deep Analysis          O(k·d)  Only if L5 fails  │
│     ↓                                                       │
│  Layer 7: Fallback               O(ext)  Only if L6 fails  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Key Insight: Constraint Hierarchy

The system applies cheap constraints first. Syntax eliminates 75%+ of word sense ambiguity before any vector computation:

| Constraint Type | Cost | Ambiguity Reduction |
|-----------------|------|---------------------|
| POS tagging | O(n) | 50-90% of senses eliminated |
| Dependency parsing | O(n) | Determines who-does-what-to-whom |
| Semantic role labeling | O(n) | Agent, patient, theme, etc. |
| Vector composition | O(n·d) | Final meaning representation |

---

## 2. Technical Stack

### 2.1 Required Dependencies

```python
# Core
numpy>=1.24.0
scipy>=1.10.0

# NLP
spacy>=3.5.0
# Download: python -m spacy download en_core_web_sm

# Storage
sqlite3  # stdlib
msgpack>=1.0.0  # efficient serialization

# Optional: LLM for lexicon generation
anthropic>=0.18.0  # or openai>=1.0.0

# Testing
pytest>=7.0.0
```

### 2.2 Hardware Requirements

- Minimum: 8GB RAM, any modern CPU
- Recommended: 16GB+ RAM for full lexicon in memory
- Storage: ~2GB for complete system

### 2.3 Target Performance

| Operation | Target Latency |
|-----------|----------------|
| Single sentence processing | <10ms |
| Lexicon lookup | <1μs per word |
| Vector similarity | <10μs per comparison |
| Batch processing (100 sentences) | <500ms |

---

## 3. Phase 1: Vector Foundation

### 3.1 Objective

Implement the sparse ternary vector infrastructure with binding, bundling, and permutation operations.

### 3.2 Specifications

**Vector Parameters:**
- Dimensionality: d = 10,000
- Sparsity: ~10% non-zero elements (1,000 per vector)
- Values: {-1, 0, +1} only
- Balance: equal +1 and -1 counts

**Primitive Basis:**
- 65 semantic primitives (see Section 11.1)
- Quasi-orthogonal: |dot(p_i, p_j)| < 0.05 for i ≠ j

**Role Vectors:**
- 15 thematic roles (see Section 11.2)
- Same orthogonality requirements

### 3.3 Implementation

```python
# File: gse/vectors.py

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
import msgpack

@dataclass
class SparseVector:
    """
    Sparse ternary vector representation.
    Only stores indices of non-zero elements for efficiency.
    """
    dimension: int
    positive_indices: np.ndarray  # dtype=uint16
    negative_indices: np.ndarray  # dtype=uint16
    
    @property
    def nnz(self) -> int:
        """Number of non-zero elements."""
        return len(self.positive_indices) + len(self.negative_indices)
    
    @property
    def sparsity(self) -> float:
        """Fraction of non-zero elements."""
        return self.nnz / self.dimension
    
    def to_dense(self) -> np.ndarray:
        """Convert to dense numpy array."""
        v = np.zeros(self.dimension, dtype=np.int8)
        v[self.positive_indices] = 1
        v[self.negative_indices] = -1
        return v
    
    @classmethod
    def from_dense(cls, v: np.ndarray) -> 'SparseVector':
        """Create from dense numpy array."""
        return cls(
            dimension=len(v),
            positive_indices=np.where(v > 0)[0].astype(np.uint16),
            negative_indices=np.where(v < 0)[0].astype(np.uint16)
        )
    
    @classmethod
    def random(cls, dimension: int, nnz: int, seed: Optional[int] = None) -> 'SparseVector':
        """Generate random sparse ternary vector."""
        rng = np.random.default_rng(seed)
        indices = rng.choice(dimension, nnz, replace=False)
        half = nnz // 2
        return cls(
            dimension=dimension,
            positive_indices=indices[:half].astype(np.uint16),
            negative_indices=indices[half:].astype(np.uint16)
        )
    
    def dot(self, other: 'SparseVector') -> int:
        """Efficient sparse dot product."""
        # +1 * +1 = +1
        pp = len(np.intersect1d(self.positive_indices, other.positive_indices))
        # -1 * -1 = +1
        nn = len(np.intersect1d(self.negative_indices, other.negative_indices))
        # +1 * -1 = -1
        pn = len(np.intersect1d(self.positive_indices, other.negative_indices))
        # -1 * +1 = -1
        np_ = len(np.intersect1d(self.negative_indices, other.positive_indices))
        
        return pp + nn - pn - np_
    
    def cosine(self, other: 'SparseVector') -> float:
        """Cosine similarity."""
        dot_product = self.dot(other)
        norm_self = np.sqrt(self.nnz)
        norm_other = np.sqrt(other.nnz)
        if norm_self * norm_other == 0:
            return 0.0
        return dot_product / (norm_self * norm_other)
    
    def serialize(self) -> bytes:
        """Serialize to bytes."""
        return msgpack.packb({
            'd': self.dimension,
            'p': self.positive_indices.tobytes(),
            'n': self.negative_indices.tobytes()
        })
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'SparseVector':
        """Deserialize from bytes."""
        obj = msgpack.unpackb(data)
        return cls(
            dimension=obj['d'],
            positive_indices=np.frombuffer(obj['p'], dtype=np.uint16),
            negative_indices=np.frombuffer(obj['n'], dtype=np.uint16)
        )


def bind(a: SparseVector, b: SparseVector) -> SparseVector:
    """
    Binding operation: element-wise multiplication.
    Creates a vector dissimilar to both inputs.
    Used for: predication, role-filler binding
    """
    assert a.dimension == b.dimension
    
    # For ternary vectors: 
    # (+1) * (+1) = +1, (-1) * (-1) = +1
    # (+1) * (-1) = -1, (-1) * (+1) = -1
    # anything * 0 = 0
    
    # Positive result: (++ or --)
    new_pos = np.union1d(
        np.intersect1d(a.positive_indices, b.positive_indices),
        np.intersect1d(a.negative_indices, b.negative_indices)
    ).astype(np.uint16)
    
    # Negative result: (+- or -+)
    new_neg = np.union1d(
        np.intersect1d(a.positive_indices, b.negative_indices),
        np.intersect1d(a.negative_indices, b.positive_indices)
    ).astype(np.uint16)
    
    return SparseVector(
        dimension=a.dimension,
        positive_indices=new_pos,
        negative_indices=new_neg
    )


def bundle(vectors: List[SparseVector], normalize: bool = True) -> SparseVector:
    """
    Bundling operation: element-wise addition with majority vote.
    Creates a vector similar to all inputs.
    Used for: collecting role-fillers, representing sets
    """
    if not vectors:
        raise ValueError("Cannot bundle empty list")
    
    dimension = vectors[0].dimension
    
    # Sum all vectors
    accumulator = np.zeros(dimension, dtype=np.int32)
    for v in vectors:
        accumulator[v.positive_indices] += 1
        accumulator[v.negative_indices] -= 1
    
    # Threshold to ternary
    if normalize:
        # Take sign, breaking ties randomly
        result = np.sign(accumulator)
        # Handle ties (zeros in sum) - leave as zero
    else:
        result = accumulator
    
    return SparseVector.from_dense(result.astype(np.int8))


def permute(v: SparseVector, n: int = 1) -> SparseVector:
    """
    Permutation operation: circular shift of indices.
    Creates a vector dissimilar to input.
    Used for: encoding sequence position
    """
    d = v.dimension
    new_pos = ((v.positive_indices.astype(np.int32) + n) % d).astype(np.uint16)
    new_neg = ((v.negative_indices.astype(np.int32) + n) % d).astype(np.uint16)
    
    return SparseVector(
        dimension=d,
        positive_indices=new_pos,
        negative_indices=new_neg
    )


class PrimitiveBasis:
    """
    The fundamental basis vectors for semantic primitives.
    These are generated once and remain fixed.
    """
    
    def __init__(self, dimension: int = 10000, sparsity: float = 0.1, seed: int = 42):
        self.dimension = dimension
        self.nnz = int(dimension * sparsity)
        self.seed = seed
        self.primitives: dict[str, SparseVector] = {}
        self.roles: dict[str, SparseVector] = {}
        
    def generate(self, primitive_names: List[str], role_names: List[str]):
        """Generate quasi-orthogonal basis vectors."""
        rng = np.random.default_rng(self.seed)
        
        all_names = primitive_names + role_names
        
        for i, name in enumerate(all_names):
            # Use deterministic seed for each name
            vec = SparseVector.random(
                self.dimension, 
                self.nnz, 
                seed=self.seed + i
            )
            
            if name in primitive_names:
                self.primitives[name] = vec
            else:
                self.roles[name] = vec
        
        # Verify orthogonality
        self._verify_orthogonality()
    
    def _verify_orthogonality(self, threshold: float = 0.1):
        """Verify all basis vectors are quasi-orthogonal."""
        all_vecs = list(self.primitives.values()) + list(self.roles.values())
        all_names = list(self.primitives.keys()) + list(self.roles.keys())
        
        max_sim = 0.0
        for i, v1 in enumerate(all_vecs):
            for j, v2 in enumerate(all_vecs):
                if i < j:
                    sim = abs(v1.cosine(v2))
                    if sim > max_sim:
                        max_sim = sim
                    if sim > threshold:
                        print(f"Warning: {all_names[i]} and {all_names[j]} have similarity {sim:.3f}")
        
        print(f"Max pairwise similarity: {max_sim:.4f}")
    
    def save(self, path: str):
        """Save basis to file."""
        data = {
            'dimension': self.dimension,
            'nnz': self.nnz,
            'seed': self.seed,
            'primitives': {k: v.serialize() for k, v in self.primitives.items()},
            'roles': {k: v.serialize() for k, v in self.roles.items()}
        }
        with open(path, 'wb') as f:
            msgpack.pack(data, f)
    
    @classmethod
    def load(cls, path: str) -> 'PrimitiveBasis':
        """Load basis from file."""
        with open(path, 'rb') as f:
            data = msgpack.unpack(f)
        
        basis = cls(data['dimension'], data['nnz'] / data['dimension'], data['seed'])
        basis.primitives = {k: SparseVector.deserialize(v) for k, v in data['primitives'].items()}
        basis.roles = {k: SparseVector.deserialize(v) for k, v in data['roles'].items()}
        return basis
```

### 3.4 Phase 1 Tests

```python
# File: tests/test_vectors.py

import pytest
import numpy as np
from gse.vectors import SparseVector, bind, bundle, permute, PrimitiveBasis

def test_sparse_vector_creation():
    v = SparseVector.random(10000, 1000, seed=42)
    assert v.dimension == 10000
    assert v.nnz == 1000
    assert len(v.positive_indices) == 500
    assert len(v.negative_indices) == 500

def test_sparse_vector_roundtrip():
    v = SparseVector.random(10000, 1000, seed=42)
    dense = v.to_dense()
    v2 = SparseVector.from_dense(dense)
    assert np.array_equal(v.positive_indices, v2.positive_indices)
    assert np.array_equal(v.negative_indices, v2.negative_indices)

def test_dot_product():
    v1 = SparseVector.random(10000, 1000, seed=42)
    v2 = SparseVector.random(10000, 1000, seed=43)
    
    # Sparse dot should match dense dot
    sparse_dot = v1.dot(v2)
    dense_dot = np.dot(v1.to_dense(), v2.to_dense())
    assert sparse_dot == dense_dot

def test_self_similarity():
    v = SparseVector.random(10000, 1000, seed=42)
    assert v.cosine(v) == pytest.approx(1.0)

def test_random_vectors_nearly_orthogonal():
    v1 = SparseVector.random(10000, 1000, seed=42)
    v2 = SparseVector.random(10000, 1000, seed=43)
    # Random vectors should have low similarity
    assert abs(v1.cosine(v2)) < 0.15

def test_bind_dissimilarity():
    v1 = SparseVector.random(10000, 1000, seed=42)
    v2 = SparseVector.random(10000, 1000, seed=43)
    bound = bind(v1, v2)
    
    # Bound vector should be dissimilar to both inputs
    assert abs(bound.cosine(v1)) < 0.2
    assert abs(bound.cosine(v2)) < 0.2

def test_bind_self_inverse():
    v1 = SparseVector.random(10000, 1000, seed=42)
    v2 = SparseVector.random(10000, 1000, seed=43)
    bound = bind(v1, v2)
    
    # v1 ⊗ (v1 ⊗ v2) ≈ v2
    recovered = bind(v1, bound)
    assert recovered.cosine(v2) > 0.8

def test_bundle_similarity():
    v1 = SparseVector.random(10000, 1000, seed=42)
    v2 = SparseVector.random(10000, 1000, seed=43)
    bundled = bundle([v1, v2])
    
    # Bundled vector should be similar to both inputs
    assert bundled.cosine(v1) > 0.3
    assert bundled.cosine(v2) > 0.3

def test_permute_dissimilarity():
    v = SparseVector.random(10000, 1000, seed=42)
    permuted = permute(v, 1)
    
    # Permuted vector should be dissimilar to original
    assert abs(permuted.cosine(v)) < 0.15

def test_permute_inverse():
    v = SparseVector.random(10000, 1000, seed=42)
    permuted = permute(v, 5)
    recovered = permute(permuted, -5)
    
    # Should recover original
    assert recovered.cosine(v) == pytest.approx(1.0)

def test_primitive_basis_orthogonality():
    from gse.primitives import PRIMITIVES, ROLES
    
    basis = PrimitiveBasis(dimension=10000, sparsity=0.1, seed=42)
    basis.generate(PRIMITIVES, ROLES)
    
    # Check all pairs are quasi-orthogonal
    all_vecs = list(basis.primitives.values()) + list(basis.roles.values())
    for i, v1 in enumerate(all_vecs):
        for j, v2 in enumerate(all_vecs):
            if i < j:
                assert abs(v1.cosine(v2)) < 0.1, f"Pair {i},{j} too similar"

def test_serialization_roundtrip():
    v = SparseVector.random(10000, 1000, seed=42)
    serialized = v.serialize()
    recovered = SparseVector.deserialize(serialized)
    
    assert v.dimension == recovered.dimension
    assert np.array_equal(v.positive_indices, recovered.positive_indices)
    assert np.array_equal(v.negative_indices, recovered.negative_indices)
```

### 3.5 Phase 1 Deliverables

- [ ] `gse/vectors.py` - SparseVector class with all operations
- [ ] `gse/primitives.py` - Primitive and role name constants
- [ ] `tests/test_vectors.py` - Comprehensive vector tests
- [ ] `data/basis.msgpack` - Pre-generated primitive basis

---

## 4. Phase 2: Lexicon Generation

### 4.1 Objective

Generate GSE encodings for 20,000 word families using LLM-assisted decomposition into semantic primitives.

### 4.2 The NSM Decomposition Format

Each word is decomposed into primitive-role pairs:

```python
# Example decompositions
DECOMPOSITIONS = {
    "murder": [
        ("SOMEONE", "agent"),
        ("DO", "action"),
        ("SOMEONE", "patient"),
        ("DIE", "result"),
        ("WANT", "intention"),
        ("BAD", "evaluation")
    ],
    "gift": [
        ("SOMEONE", "agent"),
        ("SOMETHING", "theme"),
        ("SOMEONE", "recipient"),
        ("WANT", "intention"),
        ("GOOD", "evaluation")
    ],
    "run": [
        ("SOMEONE", "agent"),
        ("MOVE", "action"),
        ("BODY", "instrument"),
        ("FAST", "manner")  # Note: FAST maps to "VERY" + "MOVE"
    ]
}
```

### 4.3 LLM Decomposition Pipeline

```python
# File: gse/lexicon_generator.py

import json
import sqlite3
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import anthropic  # or openai

from gse.primitives import PRIMITIVES, ROLES
from gse.vectors import SparseVector, PrimitiveBasis, bind, bundle

@dataclass
class LexiconEntry:
    lemma: str
    pos: str
    sense_id: str
    gloss: str
    decomposition: List[Tuple[str, str]]  # [(primitive, role), ...]
    vector: SparseVector
    frequency: float
    source: str  # "manual", "llm", "fallback"
    confidence: float

class LexiconGenerator:
    """Generate GSE lexicon entries using LLM decomposition."""
    
    DECOMPOSITION_PROMPT = '''You are a semantic analyst decomposing words into universal semantic primitives.

PRIMITIVES (use ONLY these):
{primitives}

ROLES (use ONLY these):
{roles}

Decompose the following word into primitive-role pairs. Output ONLY valid JSON.

Word: {word}
Part of speech: {pos}
Definition hint: {definition}

Output format:
{{"decomposition": [{{"primitive": "...", "role": "..."}}, ...]}}

Rules:
1. Use ONLY primitives and roles from the lists above
2. Capture the core meaning, not every nuance
3. 3-8 primitive-role pairs is typical
4. Every decomposition needs at least an action/state and usually an agent or theme

Example for "murder":
{{"decomposition": [
  {{"primitive": "SOMEONE", "role": "agent"}},
  {{"primitive": "DO", "role": "action"}},
  {{"primitive": "SOMEONE", "role": "patient"}},
  {{"primitive": "DIE", "role": "result"}},
  {{"primitive": "WANT", "role": "intention"}},
  {{"primitive": "BAD", "role": "evaluation"}}
]}}

Now decompose "{word}" ({pos}):'''

    def __init__(self, basis: PrimitiveBasis, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.basis = basis
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
    def decompose_word(self, word: str, pos: str, definition: str = "") -> Optional[List[Tuple[str, str]]]:
        """Get LLM decomposition for a word."""
        prompt = self.DECOMPOSITION_PROMPT.format(
            primitives=", ".join(PRIMITIVES),
            roles=", ".join(ROLES),
            word=word,
            pos=pos,
            definition=definition
        )
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse JSON response
            text = response.content[0].text.strip()
            # Handle markdown code blocks
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            
            data = json.loads(text)
            decomposition = [
                (item["primitive"], item["role"])
                for item in data["decomposition"]
            ]
            
            # Validate
            for prim, role in decomposition:
                if prim not in PRIMITIVES:
                    print(f"Warning: Unknown primitive '{prim}' for {word}")
                    return None
                if role not in ROLES:
                    print(f"Warning: Unknown role '{role}' for {word}")
                    return None
            
            return decomposition
            
        except Exception as e:
            print(f"Error decomposing {word}: {e}")
            return None
    
    def encode_decomposition(self, decomposition: List[Tuple[str, str]]) -> SparseVector:
        """Convert decomposition to GSE vector."""
        components = []
        for primitive, role in decomposition:
            prim_vec = self.basis.primitives[primitive]
            role_vec = self.basis.roles[role]
            bound = bind(prim_vec, role_vec)
            components.append(bound)
        
        return bundle(components)
    
    def generate_batch(self, words: List[Dict], output_db: str):
        """
        Generate lexicon entries for a batch of words.
        
        Args:
            words: List of {"word": str, "pos": str, "definition": str, "frequency": float}
            output_db: Path to SQLite database
        """
        conn = sqlite3.connect(output_db)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS lexicon (
                id INTEGER PRIMARY KEY,
                lemma TEXT,
                pos TEXT,
                sense_id TEXT,
                gloss TEXT,
                decomposition TEXT,
                vector BLOB,
                frequency REAL,
                source TEXT,
                confidence REAL,
                UNIQUE(lemma, pos, sense_id)
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_lemma ON lexicon(lemma)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_lemma_pos ON lexicon(lemma, pos)')
        
        for i, entry in enumerate(words):
            word = entry["word"]
            pos = entry["pos"]
            definition = entry.get("definition", "")
            frequency = entry.get("frequency", 0.0)
            
            # Check if already exists
            existing = conn.execute(
                'SELECT 1 FROM lexicon WHERE lemma = ? AND pos = ?',
                (word, pos)
            ).fetchone()
            
            if existing:
                continue
            
            # Get decomposition
            decomposition = self.decompose_word(word, pos, definition)
            
            if decomposition:
                vector = self.encode_decomposition(decomposition)
                conn.execute('''
                    INSERT OR REPLACE INTO lexicon 
                    (lemma, pos, sense_id, gloss, decomposition, vector, frequency, source, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    word,
                    pos,
                    f"{word}.{pos}.01",
                    definition,
                    json.dumps(decomposition),
                    vector.serialize(),
                    frequency,
                    "llm",
                    0.8
                ))
            
            if (i + 1) % 100 == 0:
                print(f"Processed {i + 1}/{len(words)} words")
                conn.commit()
        
        conn.commit()
        conn.close()


class Lexicon:
    """Runtime lexicon for word lookup."""
    
    def __init__(self, db_path: str, basis: PrimitiveBasis):
        self.db_path = db_path
        self.basis = basis
        self.cache: Dict[Tuple[str, str], LexiconEntry] = {}
        self._load_frequent_words()
    
    def _load_frequent_words(self, top_n: int = 5000):
        """Pre-load frequent words into cache."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute('''
            SELECT lemma, pos, sense_id, gloss, decomposition, vector, frequency, source, confidence
            FROM lexicon
            ORDER BY frequency DESC
            LIMIT ?
        ''', (top_n,)).fetchall()
        
        for row in rows:
            entry = LexiconEntry(
                lemma=row[0],
                pos=row[1],
                sense_id=row[2],
                gloss=row[3],
                decomposition=json.loads(row[4]),
                vector=SparseVector.deserialize(row[5]),
                frequency=row[6],
                source=row[7],
                confidence=row[8]
            )
            self.cache[(entry.lemma, entry.pos)] = entry
        
        conn.close()
        print(f"Loaded {len(self.cache)} frequent words into cache")
    
    def lookup(self, lemma: str, pos: str) -> Optional[LexiconEntry]:
        """Look up a word in the lexicon."""
        key = (lemma.lower(), pos)
        
        if key in self.cache:
            return self.cache[key]
        
        # Check database
        conn = sqlite3.connect(self.db_path)
        row = conn.execute('''
            SELECT lemma, pos, sense_id, gloss, decomposition, vector, frequency, source, confidence
            FROM lexicon
            WHERE lemma = ? AND pos = ?
        ''', key).fetchone()
        conn.close()
        
        if row:
            entry = LexiconEntry(
                lemma=row[0],
                pos=row[1],
                sense_id=row[2],
                gloss=row[3],
                decomposition=json.loads(row[4]),
                vector=SparseVector.deserialize(row[5]),
                frequency=row[6],
                source=row[7],
                confidence=row[8]
            )
            self.cache[key] = entry
            return entry
        
        return None
    
    def get_all_senses(self, lemma: str) -> List[LexiconEntry]:
        """Get all senses for a lemma."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute('''
            SELECT lemma, pos, sense_id, gloss, decomposition, vector, frequency, source, confidence
            FROM lexicon
            WHERE lemma = ?
        ''', (lemma.lower(),)).fetchall()
        conn.close()
        
        return [
            LexiconEntry(
                lemma=row[0],
                pos=row[1],
                sense_id=row[2],
                gloss=row[3],
                decomposition=json.loads(row[4]),
                vector=SparseVector.deserialize(row[5]),
                frequency=row[6],
                source=row[7],
                confidence=row[8]
            )
            for row in rows
        ]
```

### 4.4 Lexicon Validation

```python
# File: gse/lexicon_validator.py

from typing import List, Tuple, Dict
from gse.lexicon_generator import Lexicon, LexiconEntry
from gse.vectors import SparseVector

def validate_lexicon(lexicon: Lexicon, test_pairs: Dict[str, List[str]]) -> Dict:
    """
    Validate lexicon quality using known semantic relationships.
    
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
    
    # Synonyms should have high similarity (> 0.5)
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
    
    # Antonyms should have low/negative similarity (< 0.2)
    for w1, w2 in test_pairs.get("antonyms", []):
        e1 = lexicon.lookup(w1, "ADJ") or lexicon.lookup(w1, "NOUN") or lexicon.lookup(w1, "VERB")
        e2 = lexicon.lookup(w2, "ADJ") or lexicon.lookup(w2, "NOUN") or lexicon.lookup(w2, "VERB")
        
        if not e1 or not e2:
            results["antonyms"]["missing"] += 1
            continue
        
        sim = e1.vector.cosine(e2.vector)
        if sim < 0.3:
            results["antonyms"]["passed"] += 1
        else:
            results["antonyms"]["failed"] += 1
            results["failures"].append(("antonym", w1, w2, sim))
    
    # Unrelated words should have near-zero similarity
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
```

### 4.5 Word Frequency List Source

Use one of these freely available frequency lists:

1. **COCA (Corpus of Contemporary American English)**: Top 60,000 words
   - Download from: https://www.wordfrequency.info/
   
2. **Google Ngram Unigrams**: Massive coverage
   - Download from: https://storage.googleapis.com/books/ngrams/books/datasetsv3.html

3. **Wikipedia Word Frequency**: Good coverage, free
   - Various GitHub repos have pre-processed versions

### 4.6 Phase 2 Deliverables

- [ ] `gse/lexicon_generator.py` - LLM decomposition pipeline
- [ ] `gse/lexicon_validator.py` - Validation utilities
- [ ] `scripts/generate_lexicon.py` - Batch generation script
- [ ] `scripts/validate_lexicon.py` - Validation runner
- [ ] `data/lexicon.db` - SQLite database with 20K entries
- [ ] `data/validation_report.json` - Validation results

---

## 5. Phase 3: Parser Integration

### 5.1 Objective

Integrate SpaCy for tokenization, POS tagging, and dependency parsing. Map syntactic structure to semantic roles.

### 5.2 Implementation

```python
# File: gse/parser.py

import spacy
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum

class POS(Enum):
    """Part of speech tags (simplified from SpaCy's tag set)."""
    NOUN = "NOUN"
    VERB = "VERB"
    ADJ = "ADJ"
    ADV = "ADV"
    PRON = "PRON"
    DET = "DET"
    ADP = "ADP"      # Preposition
    CONJ = "CONJ"
    PUNCT = "PUNCT"
    NUM = "NUM"
    AUX = "AUX"
    PART = "PART"    # Particle (e.g., "to", "'s")
    OTHER = "OTHER"

@dataclass
class Token:
    """Parsed token with linguistic annotations."""
    surface: str          # Original text
    lemma: str            # Base form
    pos: POS              # Part of speech
    dep: str              # Dependency relation
    head_idx: int         # Index of syntactic head
    idx: int              # Token index in sentence
    is_root: bool         # Is this the root of the parse?

@dataclass
class SemanticRole:
    """Semantic role assignment."""
    role: str             # agent, patient, theme, etc.
    token_idx: int        # Which token fills this role
    confidence: float     # How confident are we?

@dataclass
class ParsedSentence:
    """Complete parse of a sentence."""
    text: str
    tokens: List[Token]
    roles: List[SemanticRole]
    root_idx: int
    
    def get_dependents(self, idx: int) -> List[Token]:
        """Get all tokens that depend on the given token."""
        return [t for t in self.tokens if t.head_idx == idx and t.idx != idx]
    
    def bottom_up_order(self) -> List[int]:
        """Return token indices in bottom-up order for composition."""
        # Topological sort based on dependency structure
        visited = set()
        order = []
        
        def visit(idx: int):
            if idx in visited:
                return
            for t in self.tokens:
                if t.head_idx == idx and t.idx != idx:
                    visit(t.idx)
            visited.add(idx)
            order.append(idx)
        
        for t in self.tokens:
            visit(t.idx)
        
        return order


# Mapping from SpaCy dependency relations to semantic roles
DEP_TO_ROLE = {
    # Core arguments
    "nsubj": "agent",           # Nominal subject
    "nsubjpass": "patient",     # Passive nominal subject
    "dobj": "patient",          # Direct object
    "obj": "patient",           # Object (newer SpaCy)
    "iobj": "recipient",        # Indirect object
    
    # Oblique arguments
    "obl": "oblique",           # Oblique nominal
    "nmod": "modifier",         # Nominal modifier
    
    # Modifiers
    "amod": "attribute",        # Adjectival modifier
    "advmod": "manner",         # Adverbial modifier
    "nummod": "quantity",       # Numeric modifier
    
    # Function words
    "det": "determiner",        # Determiner
    "case": "case",             # Case marking
    "aux": "auxiliary",         # Auxiliary verb
    "cop": "copula",            # Copula
    
    # Coordination and subordination
    "conj": "conjunction",      # Conjunct
    "cc": "coordinator",        # Coordinating conjunction
    "mark": "marker",           # Marker (subordinating conjunction)
    
    # Other
    "compound": "compound",     # Compound
    "poss": "possessor",        # Possessive
    "prep": "preposition",      # Prepositional modifier
    "pobj": "prep_object",      # Object of preposition
}


class Parser:
    """SpaCy-based parser with semantic role extraction."""
    
    def __init__(self, model: str = "en_core_web_sm"):
        self.nlp = spacy.load(model)
    
    def parse(self, text: str) -> List[ParsedSentence]:
        """Parse text into sentences with full annotations."""
        doc = self.nlp(text)
        sentences = []
        
        for sent in doc.sents:
            tokens = []
            root_idx = 0
            
            for i, token in enumerate(sent):
                # Map POS
                try:
                    pos = POS[token.pos_]
                except KeyError:
                    pos = POS.OTHER
                
                # Calculate head index relative to sentence
                sent_start = sent.start
                head_idx = token.head.i - sent_start
                is_root = token.head == token
                
                if is_root:
                    root_idx = i
                
                tokens.append(Token(
                    surface=token.text,
                    lemma=token.lemma_.lower(),
                    pos=pos,
                    dep=token.dep_,
                    head_idx=head_idx,
                    idx=i,
                    is_root=is_root
                ))
            
            # Extract semantic roles
            roles = self._extract_roles(tokens, root_idx)
            
            sentences.append(ParsedSentence(
                text=sent.text,
                tokens=tokens,
                roles=roles,
                root_idx=root_idx
            ))
        
        return sentences
    
    def _extract_roles(self, tokens: List[Token], root_idx: int) -> List[SemanticRole]:
        """Extract semantic roles from dependency structure."""
        roles = []
        
        for token in tokens:
            dep = token.dep_.lower()
            
            if dep in DEP_TO_ROLE:
                role = DEP_TO_ROLE[dep]
                
                # Special handling for preposition objects
                if dep == "pobj":
                    # Find the preposition
                    prep_token = tokens[token.head_idx]
                    if prep_token.lemma in ["for", "to"]:
                        role = "beneficiary"
                    elif prep_token.lemma in ["with"]:
                        role = "instrument"
                    elif prep_token.lemma in ["in", "at", "on"]:
                        role = "location"
                    elif prep_token.lemma in ["from"]:
                        role = "source"
                
                roles.append(SemanticRole(
                    role=role,
                    token_idx=token.idx,
                    confidence=0.9
                ))
        
        return roles
    
    def parse_single(self, text: str) -> ParsedSentence:
        """Parse a single sentence."""
        sentences = self.parse(text)
        if not sentences:
            raise ValueError(f"Could not parse: {text}")
        return sentences[0]
```

### 5.3 Phase 3 Tests

```python
# File: tests/test_parser.py

import pytest
from gse.parser import Parser, POS

@pytest.fixture
def parser():
    return Parser()

def test_basic_parse(parser):
    result = parser.parse_single("The dog runs.")
    assert len(result.tokens) == 4  # The, dog, runs, .
    assert result.tokens[1].lemma == "dog"
    assert result.tokens[2].lemma == "run"

def test_pos_tagging(parser):
    result = parser.parse_single("The big dog runs quickly.")
    assert result.tokens[1].pos == POS.ADJ  # big
    assert result.tokens[2].pos == POS.NOUN  # dog
    assert result.tokens[3].pos == POS.VERB  # runs
    assert result.tokens[4].pos == POS.ADV   # quickly

def test_dependency_structure(parser):
    result = parser.parse_single("The dog chased the cat.")
    # Find tokens by lemma
    dog = [t for t in result.tokens if t.lemma == "dog"][0]
    chased = [t for t in result.tokens if t.lemma == "chase"][0]
    cat = [t for t in result.tokens if t.lemma == "cat"][0]
    
    # Dog should depend on chased (subject)
    assert dog.head_idx == chased.idx
    # Cat should depend on chased (object)
    assert cat.head_idx == chased.idx

def test_semantic_roles(parser):
    result = parser.parse_single("John gave Mary a book.")
    
    role_map = {r.role: result.tokens[r.token_idx].lemma for r in result.roles}
    
    assert "agent" in role_map
    assert role_map["agent"] == "john"

def test_bottom_up_order(parser):
    result = parser.parse_single("The big dog runs.")
    order = result.bottom_up_order()
    
    # Leaves should come before their heads
    the_idx = [t.idx for t in result.tokens if t.surface == "The"][0]
    dog_idx = [t.idx for t in result.tokens if t.lemma == "dog"][0]
    
    assert order.index(the_idx) < order.index(dog_idx)

def test_multiple_sentences(parser):
    results = parser.parse("The dog runs. The cat sleeps.")
    assert len(results) == 2
```

### 5.4 Phase 3 Deliverables

- [ ] `gse/parser.py` - SpaCy integration
- [ ] `tests/test_parser.py` - Parser tests
- [ ] Verified POS → sense filtering works

---

## 6. Phase 4: Composition Engine

### 6.1 Objective

Implement bottom-up semantic composition following the dependency tree.

### 6.2 Implementation

```python
# File: gse/composer.py

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import hashlib

from gse.vectors import SparseVector, bind, bundle, permute, PrimitiveBasis
from gse.parser import ParsedSentence, Token, SemanticRole
from gse.lexicon_generator import Lexicon, LexiconEntry

@dataclass
class CompositionTrace:
    """Record of how a vector was composed."""
    token_idx: int
    operation: str  # "lexical", "bind", "bundle"
    inputs: List[int]  # Indices of input traces
    result_vector: SparseVector

@dataclass
class CompositionResult:
    """Result of composing a sentence."""
    sentence: str
    sentence_vector: SparseVector
    token_vectors: Dict[int, SparseVector]
    sense_selections: Dict[int, str]  # token_idx -> sense_id
    traces: Dict[int, CompositionTrace]
    merkle_root: str
    confidence: float

class Composer:
    """
    Semantic composition engine.
    Builds sentence meaning bottom-up from dependency structure.
    """
    
    def __init__(self, lexicon: Lexicon, basis: PrimitiveBasis):
        self.lexicon = lexicon
        self.basis = basis
    
    def compose(self, parsed: ParsedSentence) -> CompositionResult:
        """
        Compose semantic vector for a parsed sentence.
        
        Process:
        1. Look up each content word in lexicon
        2. Compose bottom-up following dependency tree
        3. Bind modifiers with their heads
        4. Bundle coordinated elements
        5. Build Merkle tree for verification
        """
        token_vectors: Dict[int, SparseVector] = {}
        sense_selections: Dict[int, str] = {}
        traces: Dict[int, CompositionTrace] = {}
        confidence_scores: List[float] = []
        
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
                sense_selections[idx] = lex_entry.sense_id
                confidence_scores.append(lex_entry.confidence)
            else:
                # Unknown word - use fallback
                base_vector = self._fallback_encoding(token)
                sense_selections[idx] = f"{token.lemma}.{token.pos.value}.unknown"
                confidence_scores.append(0.3)
            
            # Step 2: Get dependents that have been processed
            dependents = parsed.get_dependents(idx)
            dependent_vectors = []
            dependent_traces = []
            
            for dep_token in dependents:
                if dep_token.idx in token_vectors:
                    # Get role for this dependent
                    role = self._get_role_for_token(parsed, dep_token)
                    if role and role in self.basis.roles:
                        role_vec = self.basis.roles[role]
                        dep_vec = token_vectors[dep_token.idx]
                        # Bind role with filler
                        bound = bind(role_vec, dep_vec)
                        dependent_vectors.append(bound)
                        dependent_traces.append(dep_token.idx)
            
            # Step 3: Compose
            if dependent_vectors:
                # Bundle base vector with role-bound dependents
                all_components = [base_vector] + dependent_vectors
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
        
        # Sentence vector is the root's vector
        sentence_vector = token_vectors.get(parsed.root_idx)
        if sentence_vector is None:
            # Fallback: bundle all content word vectors
            content_vectors = [v for idx, v in token_vectors.items() 
                             if parsed.tokens[idx].pos.value in ["NOUN", "VERB", "ADJ", "ADV"]]
            if content_vectors:
                sentence_vector = bundle(content_vectors)
            else:
                # Ultimate fallback
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
            confidence=confidence
        )
    
    def _get_role_for_token(self, parsed: ParsedSentence, token: Token) -> Optional[str]:
        """Get semantic role for a token."""
        for role in parsed.roles:
            if role.token_idx == token.idx:
                return role.role
        
        # Fallback: map dependency relation to role
        from gse.parser import DEP_TO_ROLE
        return DEP_TO_ROLE.get(token.dep.lower())
    
    def _fallback_encoding(self, token: Token) -> SparseVector:
        """Generate encoding for unknown word."""
        # Use deterministic random based on lemma
        seed = int(hashlib.md5(token.lemma.encode()).hexdigest()[:8], 16)
        return SparseVector.random(self.basis.dimension, 200, seed=seed)
    
    def _compute_merkle_root(self, parsed: ParsedSentence, 
                             token_vectors: Dict[int, SparseVector]) -> str:
        """Compute Merkle root for semantic verification."""
        def hash_vector(v: SparseVector) -> str:
            # Hash the sparse representation
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
            
            # Hash this node's vector
            vec_hash = hash_vector(token_vectors[idx])
            
            # Combine with children's hashes
            dependents = parsed.get_dependents(idx)
            child_hashes = [node_hashes[d.idx] for d in dependents if d.idx in node_hashes]
            
            if child_hashes:
                for ch in child_hashes:
                    vec_hash = combine_hashes(vec_hash, ch)
            
            node_hashes[idx] = vec_hash
        
        # Root hash
        return node_hashes.get(parsed.root_idx, "")
```

### 6.3 Phase 4 Tests

```python
# File: tests/test_composer.py

import pytest
from gse.vectors import PrimitiveBasis
from gse.parser import Parser
from gse.lexicon_generator import Lexicon
from gse.composer import Composer

@pytest.fixture
def composer(tmp_path):
    # Create minimal test lexicon
    basis = PrimitiveBasis(dimension=1000, sparsity=0.1)
    basis.generate(PRIMITIVES[:10], ROLES[:5])  # Minimal set
    
    # Would need actual lexicon here
    # For testing, use mock
    lexicon = MockLexicon(basis)
    
    return Composer(lexicon, basis)

def test_simple_sentence_composition(composer):
    parser = Parser()
    parsed = parser.parse_single("The dog runs.")
    result = composer.compose(parsed)
    
    assert result.sentence_vector is not None
    assert result.confidence > 0
    assert result.merkle_root != ""

def test_transitive_sentence(composer):
    parser = Parser()
    parsed = parser.parse_single("John loves Mary.")
    result = composer.compose(parsed)
    
    # Should have sense selections for content words
    assert len(result.sense_selections) >= 3

def test_composition_determinism(composer):
    parser = Parser()
    parsed = parser.parse_single("The quick brown fox jumps.")
    
    result1 = composer.compose(parsed)
    result2 = composer.compose(parsed)
    
    # Same input should produce same output
    assert result1.merkle_root == result2.merkle_root
    assert result1.sentence_vector.cosine(result2.sentence_vector) == pytest.approx(1.0)

def test_different_sentences_different_vectors(composer):
    parser = Parser()
    
    result1 = composer.compose(parser.parse_single("The dog runs."))
    result2 = composer.compose(parser.parse_single("The cat sleeps."))
    
    # Different sentences should have different vectors
    similarity = result1.sentence_vector.cosine(result2.sentence_vector)
    assert similarity < 0.9  # Not identical

def test_similar_sentences_similar_vectors(composer):
    parser = Parser()
    
    result1 = composer.compose(parser.parse_single("The dog runs quickly."))
    result2 = composer.compose(parser.parse_single("The dog runs fast."))
    
    # Similar sentences should have similar vectors
    similarity = result1.sentence_vector.cosine(result2.sentence_vector)
    assert similarity > 0.5  # Reasonably similar
```

### 6.4 Phase 4 Deliverables

- [ ] `gse/composer.py` - Composition engine
- [ ] `tests/test_composer.py` - Composition tests
- [ ] Verified Merkle tree computation

---

## 7. Phase 5: Coherence & Verification

### 7.1 Objective

Implement coherence checking and anomaly detection.

### 7.2 Implementation

```python
# File: gse/coherence.py

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import numpy as np

from gse.vectors import SparseVector, bind, bundle
from gse.composer import CompositionResult
from gse.parser import ParsedSentence

@dataclass
class CoherenceResult:
    """Result of coherence checking."""
    passed: bool
    score: float              # 0-1, higher is more coherent
    confidence: float         # Overall confidence
    anomalies: List[str]      # Detected issues
    suggestions: List[str]    # Possible fixes

class CoherenceChecker:
    """
    Check semantic coherence of composed vectors.
    
    Coherence checking detects:
    - Selectional restriction violations (e.g., "the rock thinks")
    - Semantic incompatibilities (e.g., "colorless green")
    - Missing required arguments
    - Unusual role fillers
    """
    
    def __init__(self, 
                 dimension: int = 10000,
                 base_threshold: float = 0.3,
                 strict_threshold: float = 0.5):
        self.dimension = dimension
        self.base_threshold = base_threshold
        self.strict_threshold = strict_threshold
        
        # Semantic dimension indices for checking
        # These would be learned or specified based on the primitive encoding
        self.animacy_dims = list(range(0, 100))      # First 100 dims for animacy
        self.valence_dims = list(range(100, 200))    # Next 100 for valence
        self.agency_dims = list(range(200, 300))     # Next 100 for agency
    
    def check(self, 
              composition: CompositionResult, 
              parsed: ParsedSentence,
              strict: bool = False) -> CoherenceResult:
        """Check coherence of a composed sentence."""
        
        anomalies = []
        scores = []
        
        # Check 1: Agent animacy for mental/volitional verbs
        agent_score = self._check_agent_animacy(composition, parsed)
        scores.append(agent_score)
        if agent_score < 0.3:
            anomalies.append("Possible animacy violation: agent may be inanimate")
        
        # Check 2: Overall vector coherence (not too sparse or too dense)
        sparsity_score = self._check_sparsity(composition)
        scores.append(sparsity_score)
        if sparsity_score < 0.3:
            anomalies.append("Unusual vector sparsity")
        
        # Check 3: Role filling completeness
        completeness_score = self._check_completeness(composition, parsed)
        scores.append(completeness_score)
        if completeness_score < 0.5:
            anomalies.append("Missing expected semantic roles")
        
        # Check 4: Internal consistency
        consistency_score = self._check_consistency(composition, parsed)
        scores.append(consistency_score)
        if consistency_score < 0.3:
            anomalies.append("Semantic inconsistency detected")
        
        # Overall score
        overall_score = np.mean(scores)
        threshold = self.strict_threshold if strict else self.base_threshold
        passed = overall_score >= threshold
        
        # Generate suggestions
        suggestions = self._generate_suggestions(anomalies, composition, parsed)
        
        return CoherenceResult(
            passed=passed,
            score=overall_score,
            confidence=composition.confidence,
            anomalies=anomalies,
            suggestions=suggestions
        )
    
    def _check_agent_animacy(self, composition: CompositionResult, 
                              parsed: ParsedSentence) -> float:
        """Check if agents are appropriately animate for the verb."""
        # Find agent role
        agent_idx = None
        for role in parsed.roles:
            if role.role == "agent":
                agent_idx = role.token_idx
                break
        
        if agent_idx is None or agent_idx not in composition.token_vectors:
            return 1.0  # No agent to check
        
        # Check animacy dimensions
        agent_vec = composition.token_vectors[agent_idx].to_dense()
        animacy_signal = np.sum(agent_vec[self.animacy_dims])
        
        # Positive animacy signal is good for agents
        return min(1.0, max(0.0, (animacy_signal + 10) / 20))
    
    def _check_sparsity(self, composition: CompositionResult) -> float:
        """Check if vector sparsity is in expected range."""
        sparsity = composition.sentence_vector.sparsity
        
        # Expected range: 5% to 30%
        if 0.05 <= sparsity <= 0.30:
            return 1.0
        elif sparsity < 0.05:
            return sparsity / 0.05
        else:
            return max(0, 1 - (sparsity - 0.30) / 0.30)
    
    def _check_completeness(self, composition: CompositionResult,
                            parsed: ParsedSentence) -> float:
        """Check if expected roles are filled."""
        # Find main verb
        main_verb = parsed.tokens[parsed.root_idx]
        
        if main_verb.pos.value != "VERB":
            return 1.0  # Not a verbal predicate
        
        # Check for subject
        has_subject = any(t.dep in ["nsubj", "nsubjpass"] for t in parsed.tokens)
        
        # Simple scoring
        if has_subject:
            return 1.0
        return 0.5
    
    def _check_consistency(self, composition: CompositionResult,
                           parsed: ParsedSentence) -> float:
        """Check internal semantic consistency."""
        # Check if composed vector is reasonably similar to at least some components
        component_sims = []
        for idx, vec in composition.token_vectors.items():
            sim = composition.sentence_vector.cosine(vec)
            component_sims.append(sim)
        
        if not component_sims:
            return 1.0
        
        # At least some components should be reflected in the whole
        max_sim = max(component_sims)
        return min(1.0, max_sim + 0.5)
    
    def _generate_suggestions(self, anomalies: List[str],
                              composition: CompositionResult,
                              parsed: ParsedSentence) -> List[str]:
        """Generate suggestions for fixing anomalies."""
        suggestions = []
        
        for anomaly in anomalies:
            if "animacy" in anomaly.lower():
                suggestions.append("Check if the subject is appropriate for this verb")
            if "sparsity" in anomaly.lower():
                suggestions.append("Sentence may have unusual semantic structure")
            if "missing" in anomaly.lower():
                suggestions.append("Consider adding more context or arguments")
            if "inconsistency" in anomaly.lower():
                suggestions.append("Check for semantic conflicts between words")
        
        return suggestions


def detect_anomaly(text: str, pipeline) -> Tuple[bool, str]:
    """
    High-level anomaly detection for a sentence.
    
    Returns (is_anomalous, explanation)
    """
    result = pipeline.process(text)
    coherence = pipeline.check_coherence(result)
    
    if coherence.passed:
        return False, "Sentence appears semantically coherent"
    else:
        explanation = f"Score: {coherence.score:.2f}. Issues: {', '.join(coherence.anomalies)}"
        return True, explanation
```

### 7.3 Famous Anomaly Test Cases

```python
# File: tests/test_coherence.py

ANOMALY_TEST_CASES = [
    # Should be flagged as anomalous
    ("Colorless green ideas sleep furiously.", True),
    ("The rock thought about politics.", True),
    ("Silence tastes purple.", True),
    
    # Should pass coherence
    ("The dog runs in the park.", False),
    ("John loves Mary.", False),
    ("The committee approved the proposal.", False),
]
```

### 7.4 Phase 5 Deliverables

- [ ] `gse/coherence.py` - Coherence checking
- [ ] `tests/test_coherence.py` - Coherence tests
- [ ] Verified anomaly detection on test cases

---

## 8. Phase 6: API & Integration

### 8.1 Objective

Create a clean API for the complete GSE pipeline.

### 8.2 Implementation

```python
# File: gse/pipeline.py

from dataclasses import dataclass
from typing import Optional, List, Dict
import time

from gse.vectors import PrimitiveBasis, SparseVector
from gse.parser import Parser, ParsedSentence
from gse.lexicon_generator import Lexicon
from gse.composer import Composer, CompositionResult
from gse.coherence import CoherenceChecker, CoherenceResult

@dataclass
class GSEConfig:
    """Configuration for GSE pipeline."""
    lexicon_path: str
    basis_path: str
    dimension: int = 10000
    sparsity: float = 0.1
    coherence_threshold: float = 0.3
    strict_coherence_threshold: float = 0.5
    cache_size: int = 10000

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

class GSEPipeline:
    """
    Main GSE processing pipeline.
    
    Usage:
        config = GSEConfig(lexicon_path="data/lexicon.db", basis_path="data/basis.msgpack")
        pipeline = GSEPipeline(config)
        
        result = pipeline.process("The dog runs in the park.")
        print(f"Confidence: {result.confidence}")
        print(f"Coherent: {result.coherence_passed}")
    """
    
    def __init__(self, config: GSEConfig):
        self.config = config
        
        # Load components
        print("Loading GSE pipeline...")
        
        print("  Loading basis vectors...")
        self.basis = PrimitiveBasis.load(config.basis_path)
        
        print("  Loading lexicon...")
        self.lexicon = Lexicon(config.lexicon_path, self.basis)
        
        print("  Initializing parser...")
        self.parser = Parser()
        
        print("  Initializing composer...")
        self.composer = Composer(self.lexicon, self.basis)
        
        print("  Initializing coherence checker...")
        self.coherence = CoherenceChecker(
            dimension=config.dimension,
            base_threshold=config.coherence_threshold,
            strict_threshold=config.strict_coherence_threshold
        )
        
        # Result cache
        self._cache: Dict[str, GSEResult] = {}
        
        print("GSE pipeline ready.")
    
    def process(self, text: str, strict_coherence: bool = False) -> GSEResult:
        """
        Process text through the full GSE pipeline.
        
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
    
    def process_batch(self, texts: List[str]) -> List[GSEResult]:
        """Process multiple texts."""
        return [self.process(text) for text in texts]
    
    def similarity(self, text1: str, text2: str) -> float:
        """Compute semantic similarity between two texts."""
        result1 = self.process(text1)
        result2 = self.process(text2)
        return result1.similarity(result2)
    
    def find_similar(self, query: str, candidates: List[str], top_k: int = 5) -> List[tuple]:
        """Find most similar texts from candidates."""
        query_result = self.process(query)
        
        scored = []
        for candidate in candidates:
            cand_result = self.process(candidate)
            sim = query_result.similarity(cand_result)
            scored.append((candidate, sim))
        
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]
    
    def is_anomalous(self, text: str) -> tuple:
        """Check if text is semantically anomalous."""
        result = self.process(text, strict_coherence=True)
        return not result.coherence_passed, result.anomalies


# Convenience functions
def load_pipeline(lexicon_path: str = "data/lexicon.db",
                  basis_path: str = "data/basis.msgpack") -> GSEPipeline:
    """Load GSE pipeline with default configuration."""
    config = GSEConfig(lexicon_path=lexicon_path, basis_path=basis_path)
    return GSEPipeline(config)
```

### 8.3 CLI Interface

```python
# File: gse/cli.py

import argparse
import json
from gse.pipeline import load_pipeline

def main():
    parser = argparse.ArgumentParser(description="GSE Semantic Encoding")
    parser.add_argument("command", choices=["encode", "similarity", "check", "batch"])
    parser.add_argument("--text", "-t", help="Input text")
    parser.add_argument("--text2", help="Second text for similarity")
    parser.add_argument("--file", "-f", help="Input file")
    parser.add_argument("--output", "-o", help="Output file")
    parser.add_argument("--lexicon", default="data/lexicon.db")
    parser.add_argument("--basis", default="data/basis.msgpack")
    
    args = parser.parse_args()
    
    pipeline = load_pipeline(args.lexicon, args.basis)
    
    if args.command == "encode":
        result = pipeline.process(args.text)
        print(json.dumps({
            "text": result.text,
            "confidence": result.confidence,
            "coherence_score": result.coherence_score,
            "coherence_passed": result.coherence_passed,
            "merkle_root": result.merkle_root,
            "processing_time_ms": result.processing_time_ms,
            "anomalies": result.anomalies
        }, indent=2))
    
    elif args.command == "similarity":
        sim = pipeline.similarity(args.text, args.text2)
        print(f"Similarity: {sim:.4f}")
    
    elif args.command == "check":
        is_anomalous, anomalies = pipeline.is_anomalous(args.text)
        print(f"Anomalous: {is_anomalous}")
        if anomalies:
            print(f"Issues: {', '.join(anomalies)}")
    
    elif args.command == "batch":
        with open(args.file) as f:
            texts = [line.strip() for line in f if line.strip()]
        
        results = []
        for text in texts:
            result = pipeline.process(text)
            results.append({
                "text": result.text,
                "confidence": result.confidence,
                "coherence_score": result.coherence_score
            })
        
        output = json.dumps(results, indent=2)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
        else:
            print(output)

if __name__ == "__main__":
    main()
```

### 8.4 Phase 6 Deliverables

- [ ] `gse/pipeline.py` - Main pipeline API
- [ ] `gse/cli.py` - Command line interface
- [ ] `tests/test_pipeline.py` - Integration tests
- [ ] README.md with usage examples

---

## 9. Testing Strategy

### 9.1 Unit Tests

Each module has dedicated unit tests (see test files above).

Run with: `pytest tests/ -v`

### 9.2 Integration Tests

```python
# File: tests/test_integration.py

import pytest
from gse.pipeline import load_pipeline

@pytest.fixture(scope="module")
def pipeline():
    return load_pipeline()

def test_end_to_end_simple(pipeline):
    result = pipeline.process("The dog runs.")
    assert result.confidence > 0.5
    assert result.coherence_passed

def test_end_to_end_complex(pipeline):
    result = pipeline.process("The committee approved the controversial proposal despite objections.")
    assert result.vector is not None
    assert result.merkle_root != ""

def test_similarity_synonyms(pipeline):
    sim = pipeline.similarity(
        "The dog runs quickly.",
        "The dog runs fast."
    )
    assert sim > 0.6

def test_similarity_unrelated(pipeline):
    sim = pipeline.similarity(
        "The dog runs.",
        "Philosophy is complex."
    )
    assert sim < 0.4

def test_anomaly_detection(pipeline):
    is_anomalous, _ = pipeline.is_anomalous("Colorless green ideas sleep furiously.")
    assert is_anomalous

def test_normal_sentence_not_anomalous(pipeline):
    is_anomalous, _ = pipeline.is_anomalous("The cat sleeps on the couch.")
    assert not is_anomalous

def test_determinism(pipeline):
    result1 = pipeline.process("The quick brown fox.")
    result2 = pipeline.process("The quick brown fox.")
    assert result1.merkle_root == result2.merkle_root

def test_batch_processing(pipeline):
    texts = [
        "The dog runs.",
        "The cat sleeps.",
        "John loves Mary."
    ]
    results = pipeline.process_batch(texts)
    assert len(results) == 3
    assert all(r.confidence > 0 for r in results)
```

### 9.3 Benchmarks

```python
# File: tests/benchmark.py

import time
from gse.pipeline import load_pipeline

def benchmark_throughput():
    pipeline = load_pipeline()
    
    sentences = [
        "The dog runs in the park.",
        "John loves Mary.",
        "The committee approved the proposal.",
        "She quickly finished her homework.",
        "The big red ball rolled down the hill."
    ] * 20  # 100 sentences
    
    start = time.perf_counter()
    for sentence in sentences:
        pipeline.process(sentence)
    elapsed = time.perf_counter() - start
    
    print(f"Processed {len(sentences)} sentences in {elapsed:.2f}s")
    print(f"Throughput: {len(sentences)/elapsed:.1f} sentences/second")
    print(f"Latency: {elapsed/len(sentences)*1000:.2f}ms/sentence")

def benchmark_similarity():
    pipeline = load_pipeline()
    
    queries = ["The dog runs."] * 100
    corpus = [f"Sentence number {i}." for i in range(1000)]
    
    start = time.perf_counter()
    for query in queries:
        pipeline.find_similar(query, corpus[:100], top_k=5)
    elapsed = time.perf_counter() - start
    
    print(f"100 similarity searches in {elapsed:.2f}s")
    print(f"Throughput: {100/elapsed:.1f} searches/second")

if __name__ == "__main__":
    benchmark_throughput()
    benchmark_similarity()
```

---

## 10. File Structure

```
gse/
├── __init__.py
├── vectors.py          # SparseVector, bind, bundle, permute
├── primitives.py       # PRIMITIVES, ROLES constants
├── parser.py           # SpaCy integration
├── lexicon_generator.py # LLM decomposition pipeline
├── lexicon_validator.py # Validation utilities
├── composer.py         # Semantic composition
├── coherence.py        # Coherence checking
├── pipeline.py         # Main API
└── cli.py              # Command line interface

scripts/
├── generate_basis.py   # Generate primitive basis
├── generate_lexicon.py # Batch lexicon generation
├── validate_lexicon.py # Run validation
└── benchmark.py        # Performance benchmarks

tests/
├── test_vectors.py
├── test_parser.py
├── test_composer.py
├── test_coherence.py
├── test_pipeline.py
└── test_integration.py

data/
├── basis.msgpack       # Pre-generated primitive basis
├── lexicon.db          # SQLite lexicon database
├── word_frequencies.txt # Frequency list for generation
└── validation_pairs.json # Test pairs for validation

README.md
requirements.txt
setup.py
```

---

## 11. Data Specifications

### 11.1 Semantic Primitives (NSM-based)

```python
# File: gse/primitives.py

PRIMITIVES = [
    # Substantives
    "I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY",
    
    # Relational substantives
    "KIND", "PART",
    
    # Determiners
    "THIS", "SAME", "OTHER",
    
    # Quantifiers
    "ONE", "TWO", "SOME", "ALL", "MUCH", "LITTLE",
    
    # Evaluators
    "GOOD", "BAD",
    
    # Descriptors
    "BIG", "SMALL",
    
    # Mental predicates
    "THINK", "KNOW", "WANT", "FEEL", "SEE", "HEAR",
    
    # Speech
    "SAY", "WORDS", "TRUE",
    
    # Actions, events, movement
    "DO", "HAPPEN", "MOVE",
    
    # Existence, possession
    "BE", "HAVE", "EXIST",
    
    # Life and death
    "LIVE", "DIE",
    
    # Time
    "WHEN", "NOW", "BEFORE", "AFTER", "LONG_TIME", "SHORT_TIME", "MOMENT",
    
    # Space
    "WHERE", "HERE", "ABOVE", "BELOW", "FAR", "NEAR", "INSIDE", "SIDE", "TOUCH",
    
    # Logical concepts
    "NOT", "MAYBE", "CAN", "BECAUSE", "IF",
    
    # Intensifier
    "VERY", "MORE",
    
    # Similarity
    "LIKE",
]

ROLES = [
    # Core roles
    "agent",        # Doer of action
    "patient",      # Affected by action
    "experiencer",  # Experiences mental state
    "theme",        # Thing moved or affected
    
    # Oblique roles
    "recipient",    # Receiver
    "beneficiary",  # Benefits from action
    "instrument",   # Tool used
    "source",       # Origin
    "goal",         # Destination
    "location",     # Place
    
    # Modifier roles
    "attribute",    # Property
    "manner",       # How
    "time",         # When
    "cause",        # Why
    "result",       # Effect
    
    # Special roles
    "action",       # The action itself
    "state",        # The state itself
    "evaluation",   # Good/bad judgment
    "intention",    # Purpose
    "content",      # What is known/said
]
```

### 11.2 POS Tag Mapping

```python
# SpaCy POS to GSE POS
POS_MAP = {
    "NOUN": "NOUN",
    "PROPN": "NOUN",  # Proper noun → NOUN
    "VERB": "VERB",
    "AUX": "AUX",
    "ADJ": "ADJ",
    "ADV": "ADV",
    "PRON": "PRON",
    "DET": "DET",
    "ADP": "ADP",
    "CONJ": "CONJ",
    "CCONJ": "CONJ",
    "SCONJ": "CONJ",
    "PUNCT": "PUNCT",
    "NUM": "NUM",
    "PART": "PART",
    "INTJ": "OTHER",
    "SYM": "OTHER",
    "X": "OTHER",
}
```

---

## 12. Reference Implementation Code

### 12.1 Quick Start Script

```python
# File: scripts/quickstart.py

"""
Quick start script for GSE.
Run this to set up and test the system.
"""

import os
import sys

def main():
    print("GSE Quick Start")
    print("=" * 50)
    
    # Step 1: Check dependencies
    print("\n1. Checking dependencies...")
    try:
        import numpy
        import scipy
        import spacy
        import msgpack
        print("   All dependencies installed ✓")
    except ImportError as e:
        print(f"   Missing dependency: {e}")
        print("   Run: pip install numpy scipy spacy msgpack")
        sys.exit(1)
    
    # Step 2: Check SpaCy model
    print("\n2. Checking SpaCy model...")
    try:
        spacy.load("en_core_web_sm")
        print("   SpaCy model loaded ✓")
    except OSError:
        print("   Downloading SpaCy model...")
        os.system("python -m spacy download en_core_web_sm")
    
    # Step 3: Generate basis if not exists
    print("\n3. Checking basis vectors...")
    if not os.path.exists("data/basis.msgpack"):
        print("   Generating basis vectors...")
        from gse.vectors import PrimitiveBasis
        from gse.primitives import PRIMITIVES, ROLES
        
        os.makedirs("data", exist_ok=True)
        basis = PrimitiveBasis(dimension=10000, sparsity=0.1, seed=42)
        basis.generate(PRIMITIVES, ROLES)
        basis.save("data/basis.msgpack")
        print("   Basis vectors generated ✓")
    else:
        print("   Basis vectors exist ✓")
    
    # Step 4: Check lexicon
    print("\n4. Checking lexicon...")
    if not os.path.exists("data/lexicon.db"):
        print("   ⚠ Lexicon not found!")
        print("   Run: python scripts/generate_lexicon.py")
        print("   (Requires API key for LLM decomposition)")
    else:
        print("   Lexicon exists ✓")
    
    # Step 5: Test basic functionality
    print("\n5. Testing basic functionality...")
    from gse.vectors import SparseVector, bind, bundle
    
    v1 = SparseVector.random(10000, 1000, seed=1)
    v2 = SparseVector.random(10000, 1000, seed=2)
    
    bound = bind(v1, v2)
    bundled = bundle([v1, v2])
    
    assert abs(bound.cosine(v1)) < 0.2, "Binding should produce dissimilar vectors"
    assert bundled.cosine(v1) > 0.3, "Bundling should produce similar vectors"
    print("   Vector operations working ✓")
    
    # Step 6: Test parser
    print("\n6. Testing parser...")
    from gse.parser import Parser
    
    parser = Parser()
    result = parser.parse_single("The dog runs.")
    assert len(result.tokens) == 4
    print("   Parser working ✓")
    
    print("\n" + "=" * 50)
    print("GSE setup complete!")
    print("\nNext steps:")
    print("1. Generate lexicon: python scripts/generate_lexicon.py")
    print("2. Run tests: pytest tests/ -v")
    print("3. Try it: python -m gse.cli encode -t 'The dog runs.'")

if __name__ == "__main__":
    main()
```

### 12.2 Lexicon Generation Script

```python
# File: scripts/generate_lexicon.py

"""
Generate GSE lexicon using LLM decomposition.
"""

import os
import argparse
import json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True, help="Anthropic API key")
    parser.add_argument("--words", type=int, default=1000, help="Number of words to generate")
    parser.add_argument("--frequency-list", default="data/word_frequencies.txt")
    parser.add_argument("--output", default="data/lexicon.db")
    parser.add_argument("--basis", default="data/basis.msgpack")
    args = parser.parse_args()
    
    from gse.vectors import PrimitiveBasis
    from gse.lexicon_generator import LexiconGenerator
    
    # Load basis
    print("Loading basis...")
    basis = PrimitiveBasis.load(args.basis)
    
    # Load word list
    print("Loading word list...")
    if os.path.exists(args.frequency_list):
        with open(args.frequency_list) as f:
            words = []
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    word, pos = parts[0], parts[1]
                    freq = float(parts[2]) if len(parts) > 2 else 1.0
                    words.append({"word": word, "pos": pos, "frequency": freq})
    else:
        # Fallback: basic word list
        print("Using built-in word list...")
        words = [
            {"word": "dog", "pos": "NOUN", "frequency": 100},
            {"word": "cat", "pos": "NOUN", "frequency": 90},
            {"word": "run", "pos": "VERB", "frequency": 80},
            # ... add more
        ]
    
    words = words[:args.words]
    print(f"Generating decompositions for {len(words)} words...")
    
    # Generate
    generator = LexiconGenerator(basis, args.api_key)
    generator.generate_batch(words, args.output)
    
    print(f"Lexicon saved to {args.output}")

if __name__ == "__main__":
    main()
```

---

## 13. Success Criteria

### Phase 1: Vector Foundation
- [ ] All vector tests pass
- [ ] Basis vectors are quasi-orthogonal (max similarity < 0.1)
- [ ] Bind produces dissimilar vectors
- [ ] Bundle produces similar vectors
- [ ] Operations complete in < 1ms

### Phase 2: Lexicon Generation
- [ ] 1,000+ words encoded
- [ ] Synonym pairs have similarity > 0.4
- [ ] Antonym pairs have similarity < 0.3
- [ ] < 5% validation failures

### Phase 3: Parser Integration
- [ ] All parser tests pass
- [ ] Correct POS tagging on test sentences
- [ ] Correct dependency structure

### Phase 4: Composition Engine
- [ ] Deterministic composition (same input → same output)
- [ ] Similar sentences have similar vectors
- [ ] Different sentences have different vectors
- [ ] Merkle roots are computed correctly

### Phase 5: Coherence Checking
- [ ] Anomalous sentences flagged (e.g., "Colorless green ideas...")
- [ ] Normal sentences pass coherence
- [ ] Confidence scores are calibrated

### Phase 6: API & Integration
- [ ] Pipeline processes sentences in < 20ms
- [ ] CLI works for all commands
- [ ] Batch processing works
- [ ] Similarity search works

---

## 14. Notes for Implementation Agent

1. **Start with Phase 1** and ensure all vector tests pass before proceeding
2. **Use the provided test cases** as specifications
3. **The lexicon generation requires an API key** - skip to Phase 3 first if testing without LLM
4. **SpaCy model must be downloaded** before parser tests will work
5. **Keep vectors sparse** - this is critical for performance
6. **Determinism is essential** - same input must always produce same output
7. **Follow the file structure** exactly as specified
8. **Run tests after each phase** before moving to the next

---

*End of Implementation Specification*
