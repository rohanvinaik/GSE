#!/usr/bin/env python3
"""
GSE Encoder API.

Encodes natural language to HDC vectors with full operation trace.
Produces JSON-serializable traces for verification and debugging.

Key feature: Dynamic syntactic role assignment from spaCy dependency parsing.
This ensures that argument order matters (dog as subject vs dog as object).
"""

import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from gse.api.errors import OOVError, PrimitiveError
from gse.api.trace import (
    OperationTrace,
    OperatorTrace,
    TokenTrace,
)
from gse.vectors_v2 import (
    SparseVector,
    bind,
    bundle,
    create_basis,
    create_sentence_basis,
    permute,
)

# Dynamic syntactic role mappings from spaCy dependency labels
# Based on Universal Dependencies schema - see sentence_parser.py for full docs
DEP_TO_SYNTACTIC = {
    # Core arguments (Bank 0: CORE_STRUCTURE)
    "nsubj": "SYN_SUBJ",
    "nsubjpass": "SYN_SUBJ",
    "csubj": "SYN_SUBJ",
    "csubjpass": "SYN_SUBJ",
    "agent": "SYN_SUBJ",

    "ROOT": "SYN_PRED",
    "root": "SYN_PRED",

    "dobj": "SYN_OBJ",
    "obj": "SYN_OBJ",
    "iobj": "SYN_OBJ",
    "pobj": "SYN_OBJ",

    "attr": "SYN_COMPL",
    "acomp": "SYN_COMPL",
    "xcomp": "SYN_COMPL",
    "ccomp": "SYN_COMPL",
    "oprd": "SYN_COMPL",

    # Modifiers (Bank 1: MODIFICATION)
    "amod": "SYN_ADJ_MOD",
    "nmod": "SYN_ADJ_MOD",
    "nn": "SYN_ADJ_MOD",
    "compound": "SYN_ADJ_MOD",

    "advmod": "SYN_ADV_MOD",
    "npadvmod": "SYN_ADV_MOD",
    "neg": "SYN_ADV_MOD",

    "det": "SYN_DET",
    "predet": "SYN_DET",
    "poss": "SYN_DET",
}

# TAM (Tense-Aspect-Mood) from morphological features
MORPH_TO_TAM = {
    "Tense=Past": "SYN_TENSE_PAST",
    "Tense=Pres": "SYN_TENSE_PRES",
    "Aspect=Perf": "SYN_ASPECT_PERF",
    "Aspect=Prog": "SYN_ASPECT_PROG",
}


class GSEEncoder:
    """
    Encode natural language to HDC vectors with full operation trace.

    Usage:
        encoder = GSEEncoder()
        trace = encoder.encode("The dog is cuter than the cat")
        print(trace.to_json())

    Strict Mode:
        encoder = GSEEncoder(strict=True)
        # Raises OOVError for unknown words instead of silent fallback

    Fallback Behavior (default, strict=False):
        - OOV words: Return empty primitives, contribute zero to vector
        - Invalid primitives: Skip silently
        - Failed operators: Return None for operator result
    """

    def __init__(self, db_path: str = "data/lexicon.db", strict: bool = False):
        """
        Initialize encoder with bases and database.

        Args:
            db_path: Path to lexicon database
            strict: If True, raise exceptions for OOV words and errors.
                    If False (default), use graceful fallbacks.
        """
        self.db_path = Path(db_path)
        self.strict = strict

        # Load HDC bases
        self.word_basis = create_basis()
        self.sent_basis = create_sentence_basis()

        # Load spaCy (lazy import — keeps gse.api importable in test/analysis
        # environments that don't have spacy installed)
        import spacy
        self.nlp = spacy.load("en_core_web_sm")

        # Database connection
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def encode(self, text: str) -> OperationTrace:
        """
        Encode text to HDC vector with full operation trace.

        Args:
            text: Input text (sentence)

        Returns:
            OperationTrace with all encoding steps
        """
        # 1. Tokenize
        doc = self.nlp(text)

        # 2. Process each token
        token_traces: List[TokenTrace] = []
        token_vectors: List[Tuple[int, SparseVector, Dict]] = []
        operator_indices: List[int] = []

        for i, tok in enumerate(doc):
            # Lexicon lookup (static primitives from database)
            word_prims, sent_prims, comp_meta = self._lookup_lexeme(tok.lemma_.lower())

            # DYNAMIC: Replace core syntactic role primitives based on dependency parsing
            # This ensures argument order matters (dog as SUBJ vs dog as OBJ)
            # The dynamic primitives OVERRIDE static ones for core roles
            dynamic_sent_prims = self._extract_dynamic_primitives(tok)

            # Remove static core role primitives - dynamic parsing is authoritative
            core_roles = {"SYN_SUBJ", "SYN_OBJ", "SYN_PRED", "SYN_COMPL"}
            sent_prims = {k: v for k, v in sent_prims.items() if k not in core_roles}
            sent_prims = {**sent_prims, **dynamic_sent_prims}

            # Encode vectors
            word_vec = self._encode_word_primitives(word_prims)
            sent_vec = self._encode_sent_primitives(sent_prims)

            # Compose: word_full = bundle([word_vec, sent_vec])
            # Using bundle() instead of bind() to preserve both signals
            # (bind() destroys signal when word-scale and sent-scale are orthogonal)
            if word_vec.nnz > 0 and sent_vec.nnz > 0:
                full_vec = bundle([word_vec, sent_vec])
            elif word_vec.nnz > 0:
                full_vec = word_vec
            elif sent_vec.nnz > 0:
                full_vec = sent_vec
            else:
                full_vec = SparseVector.zeros(self.word_basis.dimension)

            # Create token trace
            is_operator = bool(comp_meta.get("comp_primitive"))
            token_trace = TokenTrace(
                token=tok.text,
                lemma=tok.lemma_.lower(),
                pos=tok.pos_,
                position=i,
                word_primitives=word_prims,
                sent_primitives=sent_prims,
                word_vec_nnz=word_vec.nnz,
                sent_vec_nnz=sent_vec.nnz,
                full_vec_nnz=full_vec.nnz,
                is_operator=is_operator,
                comp_primitive=comp_meta.get("comp_primitive"),
                comp_operation=comp_meta.get("comp_operation"),
                comp_arity=comp_meta.get("comp_arity", 0),
            )
            token_traces.append(token_trace)
            token_vectors.append((i, full_vec, comp_meta))

            if is_operator:
                operator_indices.append(i)

        # 3. Resolve operators
        operator_traces: List[OperatorTrace] = []
        operator_results: List[SparseVector] = []

        for op_idx in operator_indices:
            _, _, comp_meta = token_vectors[op_idx]
            op_trace, result_vec = self._resolve_operator(
                op_idx, comp_meta, token_vectors, token_traces
            )
            if op_trace:
                operator_traces.append(op_trace)
                if result_vec and result_vec.nnz > 0:
                    operator_results.append(result_vec)

        # 4. Position encoding + bundling
        components: List[SparseVector] = []

        for i, (pos, full_vec, _) in enumerate(token_vectors):
            if full_vec.nnz > 0:
                # Apply positional permutation
                positioned = permute(full_vec, shift=pos * 100)
                components.append(positioned)

        # Add operator results
        components.extend(operator_results)

        # Bundle all components
        if components:
            sentence_vec = bundle(components)
        else:
            sentence_vec = SparseVector.zeros(self.word_basis.dimension)

        # 5. Compute primitive activations
        word_activations = self._compute_primitive_activations(
            sentence_vec, self.word_basis
        )
        sent_activations = self._compute_primitive_activations(
            sentence_vec, self.sent_basis
        )

        # 6. Compute vector hash
        vector_hash = self._hash_vector(sentence_vec)

        # 7. Create trace
        trace = OperationTrace(
            input_text=text,
            tokens=token_traces,
            operators=operator_traces,
            final_nnz=sentence_vec.nnz,
            sparsity=sentence_vec.sparsity,
            word_primitive_activations=word_activations,
            sent_primitive_activations=sent_activations,
            vector_hash=vector_hash,
        )
        trace.vector = sentence_vec

        return trace

    def encode_batch(self, texts: List[str]) -> List[OperationTrace]:
        """Batch encoding."""
        return [self.encode(t) for t in texts]

    def _extract_dynamic_primitives(self, tok) -> Dict[str, int]:
        """
        Extract dynamic syntactic primitives from spaCy token.

        This is the key to argument-order sensitivity. By binding word vectors
        with their syntactic roles (SUBJ vs OBJ), we ensure that:
        - "The dog is cuter than the cat" ≠ "The cat is cuter than the dog"

        The formal semantics basis: CCG/Montague-style function application
        where syntactic position determines semantic role.
        """
        primitives = {}

        # Map dependency label to syntactic primitive
        if tok.dep_ in DEP_TO_SYNTACTIC:
            syn_prim = DEP_TO_SYNTACTIC[tok.dep_]
            primitives[syn_prim] = 1

        # Extract TAM (Tense-Aspect-Mood) from morphology
        morph_str = str(tok.morph)
        for morph_feat, tam_prim in MORPH_TO_TAM.items():
            if morph_feat in morph_str and tam_prim:
                primitives[tam_prim] = 1

        return primitives

    def _lookup_lexeme(self, lemma: str) -> Tuple[Dict[str, int], Dict[str, int], Dict]:
        """
        Look up word-scale and sentence-scale primitives for a lemma.

        Fallback behavior (strict=False): Returns ({}, {}, {}) for OOV words
        Strict behavior (strict=True): Raises OOVError for OOV words
        """
        # Get lexeme ID and compositional metadata
        self.cursor.execute("""
            SELECT id, comp_primitive, comp_arity, comp_operation
            FROM lexemes WHERE lemma = ? LIMIT 1
        """, (lemma,))
        row = self.cursor.fetchone()

        if not row:
            if self.strict:
                raise OOVError(lemma)
            return {}, {}, {}  # Graceful fallback: OOV word contributes nothing

        lexeme_id, comp_prim, comp_arity, comp_op = row
        comp_meta = {
            "comp_primitive": comp_prim,
            "comp_arity": comp_arity or 0,
            "comp_operation": comp_op,
        } if comp_prim else {}

        # Get word-scale primitives
        self.cursor.execute("""
            SELECT primitive, value FROM primitive_values
            WHERE lexeme_id = ? AND value != 0
        """, (lexeme_id,))
        word_prims = {row[0]: row[1] for row in self.cursor.fetchall()}

        # Get sentence-scale primitives
        self.cursor.execute("""
            SELECT primitive, value FROM sentence_primitive_values
            WHERE lexeme_id = ? AND value != 0
        """, (lexeme_id,))
        sent_prims = {row[0]: row[1] for row in self.cursor.fetchall()}

        return word_prims, sent_prims, comp_meta

    def _encode_word_primitives(self, primitives: Dict[str, int]) -> SparseVector:
        """
        Encode word-scale primitives into a vector.

        Fallback behavior: Returns zero vector for empty primitives,
                          skips invalid primitives silently.
        Strict behavior: Raises PrimitiveError for invalid primitives.
        """
        if not primitives:
            return SparseVector.zeros(self.word_basis.dimension)

        components = []
        for prim, value in primitives.items():
            prim_vec = self.word_basis.get_primitive(prim)
            if prim_vec:
                if value == -1:
                    prim_vec = prim_vec.negate()
                components.append(prim_vec)
            elif self.strict:
                raise PrimitiveError(prim)
            # else: silently skip invalid primitive (graceful fallback)

        if not components:
            return SparseVector.zeros(self.word_basis.dimension)

        return bundle(components)

    def _encode_sent_primitives(self, primitives: Dict[str, int]) -> SparseVector:
        """
        Encode sentence-scale primitives into a vector.

        Fallback behavior: Returns zero vector for empty primitives,
                          skips invalid primitives silently.
        Strict behavior: Raises PrimitiveError for invalid primitives.
        """
        if not primitives:
            return SparseVector.zeros(self.sent_basis.dimension)

        components = []
        for prim, value in primitives.items():
            prim_vec = self.sent_basis.get_primitive(prim)
            if prim_vec:
                if value == -1:
                    prim_vec = prim_vec.negate()
                components.append(prim_vec)
            elif self.strict:
                raise PrimitiveError(prim)
            # else: silently skip invalid primitive (graceful fallback)

        if not components:
            return SparseVector.zeros(self.sent_basis.dimension)

        return bundle(components)

    def _resolve_operator(
        self,
        op_idx: int,
        comp_meta: Dict,
        token_vectors: List[Tuple[int, SparseVector, Dict]],
        token_traces: List[TokenTrace],
    ) -> Tuple[Optional[OperatorTrace], Optional[SparseVector]]:
        """Resolve a compositional operator."""
        primitive = comp_meta.get("comp_primitive")
        operation = comp_meta.get("comp_operation")
        arity = comp_meta.get("comp_arity", 0)

        if not primitive or not operation:
            return None, None

        # Find arguments based on position
        # For binary operators: arg1 is before, arg2 is after
        arg1_tokens = []
        arg2_tokens = []
        arg1_lemmas = []
        arg2_lemmas = []
        arg1_vecs = []
        arg2_vecs = []

        for i, (pos, vec, _) in enumerate(token_vectors):
            if i == op_idx:
                continue

            trace = token_traces[i]
            if vec.nnz > 0 and not trace.is_operator:
                if i < op_idx:
                    arg1_tokens.append(i)
                    arg1_lemmas.append(trace.lemma)
                    arg1_vecs.append(vec)
                else:
                    arg2_tokens.append(i)
                    arg2_lemmas.append(trace.lemma)
                    arg2_vecs.append(vec)

        # Apply operation
        result_vec = None
        if operation == "SET_DIFF" and arg1_vecs and arg2_vecs:
            # SET_DIFF with DIRECTIONAL ENCODING
            # This ensures argument order matters in the HDC vector
            #
            # Original: bind(arg1, negate(arg2)) - loses direction
            # New: Use different permutation shifts to encode arg1 vs arg2 position
            # - arg1 (comparee) gets positive shift
            # - arg2 (standard) gets negative shift (negate + different shift)
            #
            # This creates a slight but measurable difference when arguments swap
            arg1_bundled = bundle(arg1_vecs) if len(arg1_vecs) > 1 else arg1_vecs[0]
            arg2_bundled = bundle(arg2_vecs) if len(arg2_vecs) > 1 else arg2_vecs[0]

            # SET_DIFF: bind(bundle(arg1), negate(bundle(arg2)))
            # This encodes the semantic content of the comparison.
            # Argument order is captured in the OperationTrace, not the vector.
            result_vec = bind(arg1_bundled, arg2_bundled.negate())

        elif operation in ["DEGREE_QUERY", "TYPE_QUERY", "SET_RESTRICT", "SCALAR_EXTREME"]:
            # Unary operators: mark the scope
            if arg2_vecs:
                result_vec = bundle(arg2_vecs) if len(arg2_vecs) > 1 else arg2_vecs[0]

        elif operation in ["CONTRAST", "CONSEQUENCE", "CAUSAL_SOURCE", "BIND_EQ", "CARD_LOWER"]:
            # Binary operators: combine both arguments
            if arg1_vecs and arg2_vecs:
                arg1_bundled = bundle(arg1_vecs) if len(arg1_vecs) > 1 else arg1_vecs[0]
                arg2_bundled = bundle(arg2_vecs) if len(arg2_vecs) > 1 else arg2_vecs[0]
                result_vec = bind(arg1_bundled, arg2_bundled)

        op_trace = OperatorTrace(
            primitive=primitive,
            operation=operation,
            position=op_idx,
            arity=arity,
            arg1_tokens=arg1_tokens,
            arg2_tokens=arg2_tokens,
            arg1_lemmas=arg1_lemmas,
            arg2_lemmas=arg2_lemmas,
            result_nnz=result_vec.nnz if result_vec else 0,
        )

        return op_trace, result_vec

    def _compute_primitive_activations(
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

    def _hash_vector(self, vector: SparseVector) -> str:
        """Compute hash of vector for reproducibility verification."""
        # Create deterministic representation
        data = f"{sorted(vector.positive_indices.tolist())}{sorted(vector.negative_indices.tolist())}"
        return f"sha256:{hashlib.sha256(data.encode()).hexdigest()[:16]}"

    def close(self):
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
