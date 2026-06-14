#!/usr/bin/env python3
"""
End-to-end architecture validation for GSE Multi-Scale HDC.

Tests the full pipeline:
  Input → Tokenize → Lexicon Lookup → Compose → Operator Resolution → Bundle

Example: "The dog is cuter than the cat"
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import spacy

# GSE imports
from gse.vectors_v2 import (
    SparseVector,
    bind,
    bundle,
    create_basis,
    create_sentence_basis,
    encode_word_full,
    permute,
)

DB_PATH = Path("data/lexicon.db")


@dataclass
class TokenEncoding:
    """Complete encoding for a single token."""
    token: str
    lemma: str
    pos: str

    # Word-scale (semantic primitives)
    word_primitives: Dict[str, int]
    word_vec: Optional[SparseVector] = None

    # Sentence-scale (syntactic/compositional)
    sent_primitives: Dict[str, int] = None
    sent_vec: Optional[SparseVector] = None

    # Composed
    full_vec: Optional[SparseVector] = None

    # Compositional operator info
    is_operator: bool = False
    comp_primitive: Optional[str] = None
    comp_arity: int = 0
    comp_operation: Optional[str] = None


class ArchitectureValidator:
    """Validates the full GSE multi-scale HDC architecture."""

    def __init__(self):
        print("=" * 70)
        print("GSE Multi-Scale HDC Architecture Validation")
        print("=" * 70)

        # Load models
        print("\n[1] Loading models...")
        self.nlp = spacy.load("en_core_web_sm")
        print("    ✓ spaCy loaded")

        self.word_basis = create_basis()
        print(f"    ✓ Word-scale basis: {len(self.word_basis.primitives)} primitives")

        self.sent_basis = create_sentence_basis()
        print(f"    ✓ Sentence-scale basis: {len(self.sent_basis.primitives)} primitives")

        # Database connection
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        print(f"    ✓ Database connected: {DB_PATH}")

    def lookup_lexeme(self, lemma: str) -> Tuple[Dict[str, int], Dict[str, int], Dict]:
        """Look up word-scale and sentence-scale primitives for a lemma."""
        # Get lexeme ID and compositional metadata
        self.cursor.execute("""
            SELECT id, comp_primitive, comp_arity, comp_operation
            FROM lexemes WHERE lemma = ? LIMIT 1
        """, (lemma,))
        row = self.cursor.fetchone()

        if not row:
            return {}, {}, {}

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

    def encode_word_scale(self, primitives: Dict[str, int]) -> SparseVector:
        """Encode word-scale primitives into a vector."""
        if not primitives:
            return SparseVector.zeros(self.word_basis.dimension)

        components = []
        for prim, value in primitives.items():
            prim_vec = self.word_basis.get_primitive(prim)
            if prim_vec:
                if value == -1:
                    prim_vec = prim_vec.negate()
                components.append(prim_vec)

        return bundle(components) if components else SparseVector.zeros(self.word_basis.dimension)

    def encode_sent_scale(self, primitives: Dict[str, int]) -> SparseVector:
        """Encode sentence-scale primitives into a vector."""
        if not primitives:
            return SparseVector.zeros(self.sent_basis.dimension)

        components = []
        for prim, value in primitives.items():
            prim_vec = self.sent_basis.get_primitive(prim)
            if prim_vec:
                if value == -1:
                    prim_vec = prim_vec.negate()
                components.append(prim_vec)

        return bundle(components) if components else SparseVector.zeros(self.sent_basis.dimension)

    def process_sentence(self, text: str) -> List[TokenEncoding]:
        """Process a sentence through the full pipeline."""
        print("\n[2] TOKENIZE + POS TAG")
        print(f"    Input: \"{text}\"")

        doc = self.nlp(text)
        encodings = []

        print(f"\n    {'Token':<12} {'Lemma':<12} {'POS':<8} {'Dep':<10}")
        print("    " + "-" * 50)

        for tok in doc:
            print(f"    {tok.text:<12} {tok.lemma_:<12} {tok.pos_:<8} {tok.dep_:<10}")

            # Lexicon lookup
            word_prims, sent_prims, comp_meta = self.lookup_lexeme(tok.lemma_.lower())

            enc = TokenEncoding(
                token=tok.text,
                lemma=tok.lemma_.lower(),
                pos=tok.pos_,
                word_primitives=word_prims,
                sent_primitives=sent_prims,
                is_operator=bool(comp_meta.get("comp_primitive")),
                comp_primitive=comp_meta.get("comp_primitive"),
                comp_arity=comp_meta.get("comp_arity", 0),
                comp_operation=comp_meta.get("comp_operation"),
            )
            encodings.append(enc)

        return encodings

    def display_lexicon_lookup(self, encodings: List[TokenEncoding]):
        """Display lexicon lookup results."""
        print("\n[3] LEXICON LOOKUP")

        for enc in encodings:
            print(f"\n    {enc.lemma} ({enc.pos}):")

            # Word-scale
            if enc.word_primitives:
                prims = ", ".join(enc.word_primitives.keys())
                print(f"      word_vec: [{prims}]")
            else:
                print("      word_vec: [∅] (informational zero)")

            # Sentence-scale
            if enc.sent_primitives:
                prims = ", ".join(enc.sent_primitives.keys())
                print(f"      sent_vec: [{prims}]")
            else:
                print("      sent_vec: [∅]")

            # Compositional operator
            if enc.is_operator:
                print(f"      OPERATOR: {enc.comp_primitive} → {enc.comp_operation} (arity={enc.comp_arity})")

    def compose_vectors(self, encodings: List[TokenEncoding]):
        """Compose word_full = bind(word_vec, sent_vec) for each token."""
        print("\n[4] COMPOSE: word_full = bind(word_vec, sent_vec)")

        for enc in encodings:
            # Encode vectors
            enc.word_vec = self.encode_word_scale(enc.word_primitives)
            enc.sent_vec = self.encode_sent_scale(enc.sent_primitives)

            # Compose
            enc.full_vec = encode_word_full(enc.word_vec, enc.sent_vec)

            print(f"\n    {enc.lemma}:")
            print(f"      word_vec:  nnz={enc.word_vec.nnz:3d}  (semantic content)")
            print(f"      sent_vec:  nnz={enc.sent_vec.nnz:3d}  (syntactic role)")
            print(f"      full_vec:  nnz={enc.full_vec.nnz:3d}  (composed)")

            # Verify orthogonality of composition
            if enc.word_vec.nnz > 0 and enc.sent_vec.nnz > 0:
                cos_word = enc.full_vec.cosine(enc.word_vec)
                cos_sent = enc.full_vec.cosine(enc.sent_vec)
                print(f"      cos(full, word)={cos_word:.3f}  cos(full, sent)={cos_sent:.3f}")

    def resolve_operators(self, encodings: List[TokenEncoding]) -> Dict:
        """Identify and resolve compositional operators."""
        print("\n[5] OPERATOR RESOLUTION")

        operators = [e for e in encodings if e.is_operator]

        if not operators:
            print("    No compositional operators found")
            return {}

        results = {}
        for op in operators:
            print(f"\n    Found: {op.comp_primitive}")
            print(f"      Operation: {op.comp_operation}")
            print(f"      Arity: {op.comp_arity}")

            # Identify arguments based on position
            op_idx = encodings.index(op)

            if op.comp_operation == "SET_DIFF":
                # COMP_THAN: arg1 is before, arg2 is after
                arg1_tokens = [e for e in encodings[:op_idx] if e.word_vec and e.word_vec.nnz > 0]
                arg2_tokens = [e for e in encodings[op_idx+1:] if e.word_vec and e.word_vec.nnz > 0]

                arg1_names = [e.lemma for e in arg1_tokens]
                arg2_names = [e.lemma for e in arg2_tokens]

                print(f"      Arg1 (comparee): {arg1_names}")
                print(f"      Arg2 (standard): {arg2_names}")

                # Compute set difference representation
                if arg1_tokens and arg2_tokens:
                    arg1_bundled = bundle([e.full_vec for e in arg1_tokens if e.full_vec.nnz > 0])
                    arg2_bundled = bundle([e.full_vec for e in arg2_tokens if e.full_vec.nnz > 0])

                    # SET_DIFF: emphasize what's in arg1 but not arg2
                    # In HDC, this is approximated by bind(arg1, neg(arg2))
                    diff_vec = bind(arg1_bundled, arg2_bundled.negate())

                    print(f"      SET_DIFF result: nnz={diff_vec.nnz}")
                    results[op.comp_primitive] = {
                        "arg1": arg1_names,
                        "arg2": arg2_names,
                        "result_vec": diff_vec,
                    }

        return results

    def bundle_sentence(self, encodings: List[TokenEncoding], operator_results: Dict) -> SparseVector:
        """Bundle all token vectors into final sentence representation."""
        print("\n[6] BUNDLE → Sentence vector")

        components = []

        for i, enc in enumerate(encodings):
            if enc.full_vec and enc.full_vec.nnz > 0:
                # Apply positional permutation
                positioned = permute(enc.full_vec, shift=i * 100)
                components.append(positioned)
                print(f"    + {enc.lemma:<12} (pos={i}, nnz={positioned.nnz})")

        # Add operator resolution results
        for op_name, result in operator_results.items():
            if result.get("result_vec"):
                components.append(result["result_vec"])
                print(f"    + {op_name} result (nnz={result['result_vec'].nnz})")

        if not components:
            print("    WARNING: No components to bundle!")
            return SparseVector.zeros(8192)

        sentence_vec = bundle(components)
        print(f"\n    Final sentence vector: nnz={sentence_vec.nnz} / 8192 dims")
        print(f"    Sparsity: {sentence_vec.sparsity:.2%}")

        return sentence_vec

    def analyze_sentence_vector(self, sentence_vec: SparseVector, encodings: List[TokenEncoding]):
        """Analyze what's encoded in the sentence vector."""
        print("\n[7] ANALYSIS")

        # Check similarity to individual token vectors
        print("\n    Token contributions (cosine similarity):")
        for enc in encodings:
            if enc.full_vec and enc.full_vec.nnz > 0:
                cos = sentence_vec.cosine(enc.full_vec)
                bar = "█" * int(abs(cos) * 20)
                sign = "+" if cos > 0 else "-"
                print(f"      {enc.lemma:<12}: {sign}{abs(cos):.3f} {bar}")

        # Check for primitive activations
        print("\n    Semantic primitive activations:")
        for prim_name in ["GOOD", "BAD", "SOMETHING", "BODY", "ALIVE", "MORE"]:
            prim_vec = self.word_basis.get_primitive(prim_name)
            if prim_vec:
                cos = sentence_vec.cosine(prim_vec)
                if abs(cos) > 0.05:
                    bar = "█" * int(abs(cos) * 20)
                    sign = "+" if cos > 0 else "-"
                    print(f"      {prim_name:<12}: {sign}{abs(cos):.3f} {bar}")

        print("\n    Compositional operator activations:")
        for prim_name in ["COMP_THAN", "COMP_HOW", "COMP_JUST", "COMP_BUT"]:
            prim_vec = self.sent_basis.get_primitive(prim_name)
            if prim_vec:
                cos = sentence_vec.cosine(prim_vec)
                if abs(cos) > 0.01:
                    bar = "█" * int(abs(cos) * 20)
                    sign = "+" if cos > 0 else "-"
                    print(f"      {prim_name:<12}: {sign}{abs(cos):.3f} {bar}")

    def validate(self, text: str):
        """Run full validation on a sentence."""
        # Step 1-2: Tokenize
        encodings = self.process_sentence(text)

        # Step 3: Lexicon lookup display
        self.display_lexicon_lookup(encodings)

        # Step 4: Compose vectors
        self.compose_vectors(encodings)

        # Step 5: Operator resolution
        operator_results = self.resolve_operators(encodings)

        # Step 6: Bundle
        sentence_vec = self.bundle_sentence(encodings, operator_results)

        # Step 7: Analysis
        self.analyze_sentence_vector(sentence_vec, encodings)

        print("\n" + "=" * 70)
        print("✓ Architecture validation complete")
        print("=" * 70)

        return sentence_vec, encodings

    def close(self):
        self.conn.close()


def main():
    validator = ArchitectureValidator()

    # Test sentence
    test_sentence = "The dog is cuter than the cat"

    sentence_vec, encodings = validator.validate(test_sentence)

    # Additional test sentences
    print("\n\n" + "=" * 70)
    print("Additional Test Sentences")
    print("=" * 70)

    for test in [
        "How fast can you run?",
        "She just finished the work.",
    ]:
        print(f"\n>>> {test}")
        encodings = validator.process_sentence(test)
        validator.display_lexicon_lookup(encodings)

    validator.close()


if __name__ == "__main__":
    main()
