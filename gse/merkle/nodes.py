#!/usr/bin/env python3
"""
Merkle Tree Node Definitions for GSE Lexicon

Defines the 5-level tree structure:
- Level 0: RootNode (single node verifying entire lexicon)
- Level 1: BankNode (8 nodes - one per semantic bank)
- Level 2: FamilyNode (~15 nodes - primitive clusters)
- Level 3: HubNode (24 nodes - bank representatives)
- Level 4: LexemeNode (18k+ entries - individual words)

Each node contains:
- Content hash: Hash of node's own data
- Children hash: Hash of all child hashes
- Combined hash: hash(content_hash || children_hash)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

from gse.primitives_v2 import SEMANTIC_BANK_NAMES, SemanticBank

# =============================================================================
# BASE NODE
# =============================================================================

@dataclass
class MerkleNode:
    """
    Base class for all Merkle tree nodes.

    The combined_hash is used for verification and routing.
    Hash format: SHA-256 truncated to 32 hex chars (128 bits).
    """
    node_id: str
    node_type: str  # 'root', 'bank', 'family', 'hub', 'lexeme'

    # Hash chain
    content_hash: str = ""
    children_hash: str = ""
    combined_hash: str = ""

    def update_combined_hash(self):
        """Recompute combined hash from content and children."""
        from gse.merkle.hash_chain import MerkleHashChain
        self.combined_hash = MerkleHashChain.combine_hashes(
            self.content_hash,
            self.children_hash
        )


# =============================================================================
# LEVEL 0: ROOT NODE
# =============================================================================

@dataclass
class RootNode(MerkleNode):
    """
    Level 0: Single root node verifying entire lexicon.

    The root hash changes if ANY lexeme changes.
    Used for rapid lexicon identity comparison.
    """
    node_type: str = "root"

    # Children: 8 bank nodes
    bank_hashes: Dict[int, str] = field(default_factory=dict)

    # Metadata
    total_lexemes: int = 0
    total_primitives: int = 0
    version: str = "2.0.0"

    def compute_content_hash(self) -> str:
        """Hash of root's own metadata."""
        from gse.merkle.hash_chain import MerkleHashChain
        content = f"root|v{self.version}|lexemes:{self.total_lexemes}|prims:{self.total_primitives}"
        self.content_hash = MerkleHashChain.compute_hash(content.encode())
        return self.content_hash

    def compute_children_hash(self) -> str:
        """Hash of all bank hashes in order."""
        from gse.merkle.hash_chain import MerkleHashChain
        bank_chain = "|".join(
            f"{k}:{v}" for k, v in sorted(self.bank_hashes.items())
        )
        self.children_hash = MerkleHashChain.compute_hash(bank_chain.encode())
        return self.children_hash


# =============================================================================
# LEVEL 1: BANK NODE
# =============================================================================

@dataclass
class BankNode(MerkleNode):
    """
    Level 1: Semantic bank node.

    Each of the 8 banks (SUBSTANTIVES, QUANTITY, EVALUATORS, etc.)
    has one BankNode containing all families in that bank.
    """
    node_type: str = "bank"

    # Bank identity
    bank_id: int = 0
    bank_name: str = ""

    # Children: family nodes
    family_hashes: Dict[str, str] = field(default_factory=dict)

    # Dimension range in 8192-D space
    dim_start: int = 0
    dim_end: int = 1024

    # Statistics
    primitive_count: int = 0
    lexeme_count: int = 0

    def compute_content_hash(self) -> str:
        """Hash of bank's own data."""
        from gse.merkle.hash_chain import MerkleHashChain
        content = (
            f"bank|{self.bank_id}|{self.bank_name}|"
            f"dims:{self.dim_start}-{self.dim_end}|"
            f"prims:{self.primitive_count}|lexemes:{self.lexeme_count}"
        )
        self.content_hash = MerkleHashChain.compute_hash(content.encode())
        return self.content_hash

    def compute_children_hash(self) -> str:
        """Hash of all family hashes."""
        from gse.merkle.hash_chain import MerkleHashChain
        family_chain = "|".join(
            f"{k}:{v}" for k, v in sorted(self.family_hashes.items())
        )
        self.children_hash = MerkleHashChain.compute_hash(family_chain.encode())
        return self.children_hash


# =============================================================================
# LEVEL 2: FAMILY NODE
# =============================================================================

@dataclass
class FamilyNode(MerkleNode):
    """
    Level 2: Primitive family cluster.

    Groups related primitives within a bank (e.g., "entity_animate",
    "mental_cognitive"). Used for routing during semantic search.
    """
    node_type: str = "family"

    # Family identity
    family_id: str = ""
    bank_id: int = 0
    description: str = ""

    # Member primitives
    member_primitives: List[str] = field(default_factory=list)

    # Hub primitive (representative for this family)
    hub_primitive: str = ""

    # Children: hub nodes (typically 1-3 per family)
    hub_hashes: Dict[str, str] = field(default_factory=dict)

    # Semantic centroid (for routing)
    centroid_positive: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.uint16))
    centroid_negative: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.uint16))

    # Statistics
    lexeme_count: int = 0
    intra_family_coherence: float = 0.0

    def compute_content_hash(self) -> str:
        """Hash of family's own data."""
        from gse.merkle.hash_chain import MerkleHashChain
        prims = ",".join(sorted(self.member_primitives))
        content = (
            f"family|{self.family_id}|bank:{self.bank_id}|"
            f"prims:[{prims}]|hub:{self.hub_primitive}|"
            f"lexemes:{self.lexeme_count}"
        )
        self.content_hash = MerkleHashChain.compute_hash(content.encode())
        return self.content_hash

    def compute_children_hash(self) -> str:
        """Hash of all hub hashes."""
        from gse.merkle.hash_chain import MerkleHashChain
        hub_chain = "|".join(
            f"{k}:{v}" for k, v in sorted(self.hub_hashes.items())
        )
        self.children_hash = MerkleHashChain.compute_hash(hub_chain.encode())
        return self.children_hash


# =============================================================================
# LEVEL 3: HUB NODE
# =============================================================================

@dataclass
class HubNode(MerkleNode):
    """
    Level 3: Hub primitive node.

    Each hub represents a bank in the learning network.
    Contains lexemes that primarily use this primitive.
    """
    node_type: str = "hub"

    # Hub identity
    primitive_name: str = ""
    bank_id: int = 0
    family_id: str = ""

    # Children: lexeme nodes
    lexeme_hashes: Dict[str, str] = field(default_factory=dict)

    # HDC encoding (hard-coded ternary values)
    vector_positive: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.uint16))
    vector_negative: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.uint16))

    # Polarity map: for each primitive, its typical polarity in this hub's lexemes
    polarity_tendencies: Dict[str, float] = field(default_factory=dict)

    # Statistics
    lexeme_count: int = 0

    def compute_content_hash(self) -> str:
        """Hash of hub's own data."""
        from gse.merkle.hash_chain import MerkleHashChain
        # Include vector signature in hash
        vec_sig = f"pos:{len(self.vector_positive)},neg:{len(self.vector_negative)}"
        content = (
            f"hub|{self.primitive_name}|bank:{self.bank_id}|"
            f"family:{self.family_id}|{vec_sig}|lexemes:{self.lexeme_count}"
        )
        self.content_hash = MerkleHashChain.compute_hash(content.encode())
        return self.content_hash

    def compute_children_hash(self) -> str:
        """Hash of all lexeme hashes."""
        from gse.merkle.hash_chain import MerkleHashChain
        lexeme_chain = "|".join(
            f"{k}:{v}" for k, v in sorted(self.lexeme_hashes.items())
        )
        self.children_hash = MerkleHashChain.compute_hash(lexeme_chain.encode())
        return self.children_hash


# =============================================================================
# LEVEL 4: LEXEME NODE
# =============================================================================

@dataclass
class LexemeNode(MerkleNode):
    """
    Level 4: Individual lexicon entry.

    Contains a word's decomposition into primitives with roles and polarities,
    plus the pre-computed HDC vector.
    """
    node_type: str = "lexeme"

    # Lexeme identity
    lemma: str = ""
    pos: str = ""
    sense_id: str = ""
    gloss: str = ""

    # Decomposition: List of (primitive, role, polarity) tuples
    # Polarity is +1, -1, or 0
    decomposition: List[Tuple[str, str, int]] = field(default_factory=list)

    # Pre-computed HDC vector (sparse ternary)
    vector_positive: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.uint16))
    vector_negative: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.uint16))

    # Parent hub
    parent_hub: str = ""

    # Metadata
    frequency: float = 1.0
    source: str = "manual"  # manual, llm, inferred
    confidence: float = 1.0

    # For membership proofs
    sibling_hashes: List[str] = field(default_factory=list)

    def compute_content_hash(self) -> str:
        """Hash of lexeme's complete data."""
        from gse.merkle.hash_chain import MerkleHashChain

        # Include full decomposition in hash
        decomp_str = "|".join(
            f"{p}:{r}:{pol}" for p, r, pol in self.decomposition
        )

        # Include vector fingerprint
        vec_sig = f"pos:{len(self.vector_positive)},neg:{len(self.vector_negative)}"

        content = (
            f"lexeme|{self.lemma}|{self.pos}|{self.sense_id}|"
            f"gloss:{self.gloss[:50]}|"
            f"decomp:[{decomp_str}]|{vec_sig}|"
            f"source:{self.source}|conf:{self.confidence:.2f}"
        )
        self.content_hash = MerkleHashChain.compute_hash(content.encode())
        return self.content_hash

    def compute_children_hash(self) -> str:
        """Lexemes have no children, so children_hash is empty."""
        from gse.merkle.hash_chain import MerkleHashChain
        self.children_hash = MerkleHashChain.compute_hash(b"")
        return self.children_hash

    @property
    def key(self) -> str:
        """Unique key for this lexeme."""
        return f"{self.lemma}_{self.pos}_{self.sense_id}"

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "lemma": self.lemma,
            "pos": self.pos,
            "sense_id": self.sense_id,
            "gloss": self.gloss,
            "decomposition": self.decomposition,
            "vector_positive": self.vector_positive.tolist(),
            "vector_negative": self.vector_negative.tolist(),
            "parent_hub": self.parent_hub,
            "frequency": self.frequency,
            "source": self.source,
            "confidence": self.confidence,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "LexemeNode":
        """Create from dictionary."""
        node = cls(
            node_id=f"{data['lemma']}_{data['pos']}_{data.get('sense_id', '01')}",
            lemma=data["lemma"],
            pos=data["pos"],
            sense_id=data.get("sense_id", "01"),
            gloss=data.get("gloss", ""),
            decomposition=[tuple(d) for d in data.get("decomposition", [])],
            vector_positive=np.array(data.get("vector_positive", []), dtype=np.uint16),
            vector_negative=np.array(data.get("vector_negative", []), dtype=np.uint16),
            parent_hub=data.get("parent_hub", ""),
            frequency=data.get("frequency", 1.0),
            source=data.get("source", "manual"),
            confidence=data.get("confidence", 1.0),
        )
        node.content_hash = data.get("content_hash", "")
        return node


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_bank_node(bank: SemanticBank) -> BankNode:
    """Create a BankNode for the given semantic bank."""
    from gse.primitives_v2 import get_dimension_range

    start, end = get_dimension_range(bank)

    return BankNode(
        node_id=f"bank_{bank.value}",
        bank_id=bank.value,
        bank_name=SEMANTIC_BANK_NAMES[bank.value],
        dim_start=start,
        dim_end=end,
    )


def create_family_node(
    family_id: str,
    bank: SemanticBank,
    primitives: List[str],
    hub: str,
    description: str = "",
) -> FamilyNode:
    """Create a FamilyNode for a primitive family."""
    return FamilyNode(
        node_id=f"family_{family_id}",
        family_id=family_id,
        bank_id=bank.value,
        member_primitives=primitives,
        hub_primitive=hub,
        description=description,
    )


def create_hub_node(
    primitive_name: str,
    bank_id: int,
    family_id: str,
) -> HubNode:
    """Create a HubNode for a hub primitive."""
    return HubNode(
        node_id=f"hub_{primitive_name}",
        primitive_name=primitive_name,
        bank_id=bank_id,
        family_id=family_id,
    )
