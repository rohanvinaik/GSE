#!/usr/bin/env python3
"""
GSE Decoder API.

Decodes HDC vectors to semantic information:
- Entities (via SOMETHING/SOMEONE probing)
- Attributes (via GOOD/BAD/BIG/SMALL probing)
- Relations (via COMP_* activations)
- Nearest lexemes (similarity search)
"""

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

from gse.api.trace import (
    AttributeExtraction,
    DecodedSemantics,
    EntityExtraction,
    RelationExtraction,
    SimilarityResult,
)
from gse.vectors_v2 import (
    SparseVector,
    bundle,
    create_basis,
    create_sentence_basis,
)

# Absolute path resolved from this module (repo root), as the encoder resolves its default, so the
# decoder reads the same lexicon whatever the process working directory (#20).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_LEXICON = os.path.join(_REPO_ROOT, "data", "lexicon_clean.db")


class GSEDecoder:
    """
    Decode HDC vectors to semantic information.

    Usage:
        decoder = GSEDecoder()
        semantics = decoder.decode(vector)
        print(semantics.to_json())
    """

    # Entity primitives (things that can be subjects/objects)
    ENTITY_PRIMITIVES = ["SOMETHING", "SOMEONE", "BODY", "ALIVE"]

    # Attribute primitives (qualities that can be extracted)
    ATTRIBUTE_PRIMITIVES = {
        "GOOD": ("positive_quality", 1),
        "BAD": ("negative_quality", -1),
        "BIG": ("large_size", 1),
        "SMALL": ("small_size", -1),
        "MORE": ("intensity_high", 1),
        "VERY": ("intensity_very", 1),
    }

    # Relation primitives (compositional operators)
    RELATION_PRIMITIVES = {
        "COMP_THAN": "SET_DIFF",
        "COMP_HOW": "DEGREE_QUERY",
        "COMP_JUST": "SCALAR_EXTREME",
        "COMP_BUT": "CONTRAST",
        "COMP_BECAUSE": "CAUSAL_SOURCE",
        "COMP_SO": "CONSEQUENCE",
        "COMP_LIKE": "BIND_EQ",
    }

    def __init__(self, db_path: str = _DEFAULT_LEXICON):
        """Initialize decoder with bases and database."""
        self.db_path = Path(db_path)
        # sqlite3.connect() creates a missing file, so check first: a wrong path fails here
        # instead of leaving an empty database behind (#20).
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"GSE lexicon not found: {self.db_path} (cwd={Path.cwd()}). Pass an absolute "
                "db_path or omit it for the repo's data/lexicon_clean.db."
            )

        # Load HDC bases
        self.word_basis = create_basis()
        self.sent_basis = create_sentence_basis()

        # Database connection
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        # Build lexeme index for similarity search
        self._build_lexeme_index()

    def _build_lexeme_index(self):
        """Build index of lexeme vectors for similarity search."""
        self.lexeme_vectors: Dict[str, Tuple[SparseVector, str]] = {}

        # Get all lexemes with primitives
        self.cursor.execute("""
            SELECT l.id, l.lemma, l.pos
            FROM lexemes l
            WHERE EXISTS (
                SELECT 1 FROM primitive_values pv
                WHERE pv.lexeme_id = l.id AND pv.value != 0
            )
        """)
        lexemes = self.cursor.fetchall()

        for lexeme_id, lemma, pos in lexemes:
            # Get word primitives
            self.cursor.execute(
                """
                SELECT primitive, value FROM primitive_values
                WHERE lexeme_id = ? AND value != 0
            """,
                (lexeme_id,),
            )
            prims = {row[0]: row[1] for row in self.cursor.fetchall()}

            if prims:
                vec = self._encode_primitives(prims)
                if vec.nnz > 0:
                    self.lexeme_vectors[lemma] = (vec, pos or "UNK")

    def _encode_primitives(self, primitives: Dict[str, int]) -> SparseVector:
        """Encode primitives into a vector."""
        if not primitives:
            return SparseVector.zeros(self.word_basis.dimension)

        components = []
        for prim, value in primitives.items():
            prim_vec = self.word_basis.get_primitive(prim)
            if prim_vec:
                if value == -1:
                    prim_vec = prim_vec.negate()
                components.append(prim_vec)

        if not components:
            return SparseVector.zeros(self.word_basis.dimension)

        return bundle(components)

    def decode(self, vector: SparseVector) -> DecodedSemantics:
        """
        Extract semantic information from vector.

        Args:
            vector: HDC vector to decode

        Returns:
            DecodedSemantics with entities, attributes, relations
        """
        # 1. Compute primitive activations
        word_activations = self._probe_primitives(vector, self.word_basis)
        sent_activations = self._probe_primitives(vector, self.sent_basis)

        # 2. Extract entities
        entities = self._extract_entities(vector, word_activations)

        # 3. Extract attributes
        attributes = self._extract_attributes(word_activations)

        # 4. Extract relations
        relations = self._extract_relations(sent_activations)

        # 5. Find nearest lexemes
        nearest = self._find_nearest_lexemes(vector, top_k=10)

        # 6. Bank activity profile
        bank_profile = self._compute_bank_activity(vector)

        return DecodedSemantics(
            entities=entities,
            attributes=attributes,
            relations=relations,
            nearest_lexemes=nearest,
            bank_activations=bank_profile,
            primitive_activations={**word_activations, **sent_activations},
        )

    def _probe_primitives(
        self,
        vector: SparseVector,
        basis: Any,
    ) -> Dict[str, float]:
        """Compute cosine similarity to each primitive in basis."""
        activations = {}

        for prim_name, prim_vec in basis.primitives.items():
            cos = vector.cosine(prim_vec)
            if abs(cos) > 0.01:  # Only include non-trivial activations
                activations[prim_name] = round(cos, 4)

        return activations

    def _extract_entities(
        self,
        vector: SparseVector,
        word_activations: Dict[str, float],
    ) -> List[EntityExtraction]:
        """Extract entities by finding lexemes with entity primitives."""
        entities = []

        # Check if vector has entity-like activations
        has_entity_signal = any(word_activations.get(p, 0) > 0.02 for p in self.ENTITY_PRIMITIVES)

        if not has_entity_signal:
            return entities

        # Find lexemes with high similarity that have entity primitives
        for lemma, (lex_vec, pos) in self.lexeme_vectors.items():
            cos = vector.cosine(lex_vec)
            if cos > 0.005:
                # Check if this lexeme has entity primitives
                self.cursor.execute(
                    """
                    SELECT pv.primitive FROM primitive_values pv
                    JOIN lexemes l ON l.id = pv.lexeme_id
                    WHERE l.lemma = ? AND pv.primitive IN (?, ?, ?, ?)
                    AND pv.value = 1
                """,
                    (lemma, *self.ENTITY_PRIMITIVES),
                )

                prims = [row[0] for row in self.cursor.fetchall()]
                if prims:
                    entities.append(
                        EntityExtraction(
                            lemma=lemma,
                            pos=pos,
                            confidence=round(cos, 4),
                            primitives=prims,
                        )
                    )

        # Sort by confidence and return top entities
        entities.sort(key=lambda x: -x.confidence)
        return entities[:10]

    def _extract_attributes(
        self,
        word_activations: Dict[str, float],
    ) -> List[AttributeExtraction]:
        """Extract attributes from evaluator primitive activations."""
        attributes = []

        for prim, (attr_name, polarity) in self.ATTRIBUTE_PRIMITIVES.items():
            activation = word_activations.get(prim, 0)
            if abs(activation) > 0.01:
                # Determine actual polarity based on activation sign
                actual_polarity = polarity if activation > 0 else -polarity
                attributes.append(
                    AttributeExtraction(
                        attribute=attr_name,
                        polarity=actual_polarity,
                        intensity=round(abs(activation), 4),
                        source_primitive=prim,
                    )
                )

        # Sort by intensity
        attributes.sort(key=lambda x: -x.intensity)
        return attributes

    def _extract_relations(
        self,
        sent_activations: Dict[str, float],
    ) -> List[RelationExtraction]:
        """Extract relations from compositional operator activations."""
        relations = []

        for prim, operation in self.RELATION_PRIMITIVES.items():
            activation = sent_activations.get(prim, 0)
            if abs(activation) > 0.02:
                # Find potential argument candidates
                # This is approximate - full reconstruction would need
                # to unbind positional encodings
                relations.append(
                    RelationExtraction(
                        relation=prim,
                        confidence=round(abs(activation), 4),
                        operation=operation,
                        arg1_candidates=[],  # Would need trace for full recovery
                        arg2_candidates=[],
                    )
                )

        # Sort by confidence
        relations.sort(key=lambda x: -x.confidence)
        return relations

    def _find_nearest_lexemes(
        self,
        vector: SparseVector,
        top_k: int = 10,
    ) -> List[Tuple[str, float]]:
        """Find lexemes most similar to vector."""
        similarities = []

        for lemma, (lex_vec, _) in self.lexeme_vectors.items():
            cos = vector.cosine(lex_vec)
            if cos > 0.02:
                similarities.append((lemma, round(cos, 4)))

        # Sort by similarity
        similarities.sort(key=lambda x: -x[1])
        return similarities[:top_k]

    def _compute_bank_activity(
        self,
        vector: SparseVector,
    ) -> Dict[str, float]:
        """Compute activity level in each semantic bank."""
        # Banks are defined in PRIMITIVE_REGISTRY
        # Approximate by checking a representative primitive from each bank
        bank_reps = {
            "Substantives": "SOMETHING",
            "Determiners": "THIS",
            "Quantifiers": "ONE",
            "Evaluators": "GOOD",
            "Descriptors": "BIG",
            "Mental": "THINK",
            "Speech": "SAY",
            "Actions": "DO",
        }

        bank_activity = {}
        for bank_name, rep_prim in bank_reps.items():
            prim_vec = self.word_basis.get_primitive(rep_prim)
            if prim_vec:
                cos = abs(vector.cosine(prim_vec))
                if cos > 0.01:
                    bank_activity[bank_name] = round(cos, 4)

        return bank_activity

    def similarity(
        self,
        v1: SparseVector,
        v2: SparseVector,
        sentence1: str = "",
        sentence2: str = "",
    ) -> SimilarityResult:
        """
        Compute detailed similarity between two vectors.

        Returns breakdown of:
        - cosine: overall similarity
        - alignment: same-sign overlap
        - opposition: opposite-sign overlap
        - orthogonality: non-overlap
        """
        cosine = v1.cosine(v2)

        # Compute alignment/opposition/orthogonality
        # alignment: positions where both have same sign
        # opposition: positions where signs differ
        # orthogonality: positions where one or both are zero

        pos1 = set(v1.positive_indices.tolist())
        neg1 = set(v1.negative_indices.tolist())
        pos2 = set(v2.positive_indices.tolist())
        neg2 = set(v2.negative_indices.tolist())

        # Same-sign overlap
        aligned_pos = len(pos1 & pos2)
        aligned_neg = len(neg1 & neg2)
        alignment = aligned_pos + aligned_neg

        # Opposite-sign overlap
        opposed = len(pos1 & neg2) + len(neg1 & pos2)

        # Total active dimensions
        total_active = len(pos1 | neg1 | pos2 | neg2)

        # Normalize
        if total_active > 0:
            alignment_score = alignment / total_active
            opposition_score = opposed / total_active
            orthogonality_score = 1.0 - alignment_score - opposition_score
        else:
            alignment_score = 0.0
            opposition_score = 0.0
            orthogonality_score = 1.0

        # Find shared/different primitives
        shared_prims = []
        different_prims = []

        act1 = self._probe_primitives(v1, self.word_basis)
        act2 = self._probe_primitives(v2, self.word_basis)

        all_prims = set(act1.keys()) | set(act2.keys())
        for prim in all_prims:
            a1 = act1.get(prim, 0)
            a2 = act2.get(prim, 0)
            if a1 > 0.1 and a2 > 0.1:
                shared_prims.append(prim)
            elif abs(a1 - a2) > 0.2:
                different_prims.append(prim)

        return SimilarityResult(
            sentence1=sentence1,
            sentence2=sentence2,
            cosine=round(cosine, 4),
            alignment=round(alignment_score, 4),
            opposition=round(opposition_score, 4),
            orthogonality=round(orthogonality_score, 4),
            shared_primitives=shared_prims,
            different_primitives=different_prims,
        )

    def close(self):
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
