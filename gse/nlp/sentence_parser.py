#!/usr/bin/env python3
"""
NLP Integration Layer: Map linguistic resources to sentence-scale primitives.

This module bridges established NLP resources (spaCy, AMR, CCG) to our
sentence-scale HDC primitive system. The mappings are based on decades
of formal semantics research (Montague 1973, Steedman 2000, etc.).

Key Resources:
- spaCy: Dependency parsing, POS tagging (always available)
- AMR: Abstract Meaning Representation (semantic graphs)
- CCG: Combinatory Categorial Grammar (syntax-semantics interface)

Mapping Architecture:
    Raw text → NLP Parse → Feature Extraction → Primitive Assignment

    spaCy dep labels → SYN_* primitives (syntactic roles)
    spaCy morph tags → TAM primitives (tense/aspect/mood)
    AMR relations → COMP_* operators (compositional semantics)
    CCG categories → Operator arity and scope
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Try imports with graceful fallback
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    import amrlib
    AMR_AVAILABLE = True
except ImportError:
    AMR_AVAILABLE = False


# =============================================================================
# MAPPING TABLES: Formal Semantics → GSE Primitives
# =============================================================================

# spaCy dependency labels → SYN_* primitives
# Based on Universal Dependencies (UD) schema
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

# spaCy morphological features → TAM primitives (Bank 2)
MORPH_TO_TAM = {
    # Tense
    "Tense=Past": "SYN_TENSE_PAST",
    "Tense=Pres": "SYN_TENSE_PRES",
    "Tense=Fut": "SYN_TENSE_FUT",

    # Aspect
    "Aspect=Perf": "SYN_ASPECT_PERF",
    "Aspect=Prog": "SYN_ASPECT_PROG",

    # Mood
    "Mood=Ind": None,  # Default, no special marker
    "Mood=Imp": "SYN_MOOD_IMPER",
    "Mood=Sub": None,
}

# Function words → COMP_* operators
# These are the "compositional operators as set-theoretic operations"
FUNCTION_WORD_OPERATORS = {
    # Bank 3: Comparison
    "than": {
        "primitive": "COMP_THAN",
        "arity": 2,
        "operation": "SET_DIFF",
        "description": "Degree comparison - set difference between compared entities",
        "formal_semantics": "λxλyλd.d(x) > d(y)",  # Kennedy & McNally 2005
    },
    "as": {
        "primitive": "COMP_AS",
        "arity": 2,
        "operation": "BIND_EQ",
        "description": "Equative comparison - bind equality",
        "formal_semantics": "λxλyλd.d(x) = d(y)",
    },

    # Bank 4: Quantification/Queries
    "how": {
        "primitive": "COMP_HOW",
        "arity": 1,
        "operation": "DEGREE_QUERY",
        "description": "Degree/manner wh-query",
        "formal_semantics": "λP.?d.P(d)",
    },
    "what": {
        "primitive": "COMP_WHAT",
        "arity": 1,
        "operation": "TYPE_QUERY",
        "description": "Type/entity wh-query",
        "formal_semantics": "λP.?x.P(x)",
    },

    # Bank 5: Constraint/Focus
    "just": {
        "primitive": "COMP_JUST",
        "arity": 2,
        "operation": "CARD_LOWER",
        "description": "Lower cardinality bound - minimal sufficiency",
        "formal_semantics": "ONLY(x) ∧ AT_LEAST(x)",  # Schwarzschild 2008
    },
    "only": {
        "primitive": "COMP_ONLY",
        "arity": 1,
        "operation": "SET_RESTRICT",
        "description": "Set restriction - exhaustive focus",
        "formal_semantics": "∀x[P(x) → x ∈ ALT]",
    },
    "even": {
        "primitive": "COMP_EVEN",
        "arity": 1,
        "operation": "SCALAR_EXTREME",
        "description": "Scalar endpoint - unlikely extreme",
        "formal_semantics": "UNLIKELY(P(x)) ∧ P(x)",
    },

    # Bank 6: Discourse/Connectives
    "but": {
        "primitive": "COMP_BUT",
        "arity": 2,
        "operation": "CONTRAST",
        "description": "Adversative contrast",
        "formal_semantics": "P ∧ Q ∧ CONTRAST(P, Q)",
    },
    "so": {
        "primitive": "COMP_SO",
        "arity": 2,
        "operation": "CONSEQUENCE",
        "description": "Consequence/result",
        "formal_semantics": "P → Q (pragmatic)",
    },
    "because": {
        "primitive": "COMP_BECAUSE",
        "arity": 2,
        "operation": "CAUSAL_SOURCE",
        "description": "Causal relation",
        "formal_semantics": "CAUSE(P, Q)",
    },
}

# AMR relations → GSE primitives
AMR_TO_PRIMITIVES = {
    # Argument structure
    ":ARG0": "SYN_SUBJ",
    ":ARG1": "SYN_OBJ",
    ":ARG2": "SYN_OBJ",  # Secondary object

    # Modification
    ":mod": "SYN_ADJ_MOD",
    ":manner": "SYN_ADV_MOD",
    ":degree": "SYN_ADV_MOD",

    # Comparison
    ":compared-to": "COMP_THAN",

    # Discourse
    ":cause": "COMP_BECAUSE",
    ":concession": "COMP_BUT",
    ":condition": None,  # Future: COMP_IF

    # Polarity/modality handled separately
    ":polarity": None,
    ":modal": None,
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class SentencePrimitiveAssignment:
    """Primitive assignments extracted from NLP parse."""
    lexeme: str
    pos: str
    primitives: Dict[str, int]  # primitive_name -> value (1 or -1)
    confidence: float = 1.0
    source: str = "nlp_parser"

    # Compositional operator metadata (if applicable)
    is_compositional: bool = False
    comp_primitive: Optional[str] = None
    comp_arity: int = 0
    comp_operation: Optional[str] = None


@dataclass
class ParsedSentence:
    """Complete NLP parse with primitive assignments."""
    text: str
    tokens: List[str]
    assignments: List[SentencePrimitiveAssignment]

    # Parse-level features
    is_interrogative: bool = False
    is_imperative: bool = False
    is_negative: bool = False
    has_comparison: bool = False

    # Raw parse data for debugging
    spacy_doc: Optional[object] = None
    amr_graph: Optional[str] = None


# =============================================================================
# PARSER CLASS
# =============================================================================

class SentencePrimitiveParser:
    """
    Extract sentence-scale primitives from text using NLP resources.

    Implements the formal semantics mappings from CCG/AMR/DRS to
    our HDC sentence-scale primitives.
    """

    def __init__(self, use_amr: bool = True):
        self.nlp = None
        self.amr_model = None
        self.use_amr = use_amr and AMR_AVAILABLE

        self._load_models()

    def _load_models(self):
        """Load NLP models."""
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                print("spaCy model not found. Run: python -m spacy download en_core_web_sm")
                self.nlp = None

        if self.use_amr:
            try:
                # AMR model requires separate download
                self.amr_model = amrlib.load_stog_model()
            except Exception as e:
                print(f"AMR model not available: {e}")
                self.amr_model = None
                self.use_amr = False

    def parse(self, text: str) -> ParsedSentence:
        """
        Parse text and extract sentence-scale primitives.

        Args:
            text: Input sentence

        Returns:
            ParsedSentence with primitive assignments
        """
        assignments = []
        tokens = []

        spacy_doc = None
        amr_graph = None

        is_interrogative = text.strip().endswith("?")
        is_imperative = False
        is_negative = False
        has_comparison = False

        # 1. spaCy dependency parse
        if self.nlp:
            spacy_doc = self.nlp(text)
            tokens = [tok.text for tok in spacy_doc]

            for tok in spacy_doc:
                prims = self._extract_spacy_primitives(tok, spacy_doc)
                if prims:
                    assignments.append(prims)

                    # Track sentence-level features
                    if tok.dep_ == "neg":
                        is_negative = True
                    if "COMP_THAN" in prims.primitives:
                        has_comparison = True

            # Check for imperative
            root = [tok for tok in spacy_doc if tok.dep_ == "ROOT"]
            if root and root[0].morph.get("VerbForm") == ["Inf"]:
                is_imperative = True

        # 2. AMR parse (if available)
        if self.amr_model:
            try:
                graphs = self.amr_model.parse_sents([text])
                if graphs:
                    amr_graph = graphs[0]
                    amr_prims = self._extract_amr_primitives(amr_graph)
                    # Merge AMR primitives with spaCy
                    self._merge_amr_assignments(assignments, amr_prims)
            except Exception as e:
                print(f"AMR parse error: {e}")

        # 3. Add interrogative/imperative mood markers
        if is_interrogative:
            for asn in assignments:
                if asn.pos in ("VB", "VBZ", "VBP", "VBD", "VERB"):
                    asn.primitives["SYN_MOOD_INTER"] = 1

        if is_imperative:
            for asn in assignments:
                if asn.pos in ("VB", "VERB"):
                    asn.primitives["SYN_MOOD_IMPER"] = 1

        return ParsedSentence(
            text=text,
            tokens=tokens,
            assignments=assignments,
            is_interrogative=is_interrogative,
            is_imperative=is_imperative,
            is_negative=is_negative,
            has_comparison=has_comparison,
            spacy_doc=spacy_doc,
            amr_graph=amr_graph,
        )

    def _extract_spacy_primitives(self, tok, doc) -> Optional[SentencePrimitiveAssignment]:
        """Extract primitives from a spaCy token."""
        primitives = {}
        is_compositional = False
        comp_primitive = None
        comp_arity = 0
        comp_operation = None

        lemma = tok.lemma_.lower()

        # Check for function word operators
        if lemma in FUNCTION_WORD_OPERATORS:
            op = FUNCTION_WORD_OPERATORS[lemma]
            primitives[op["primitive"]] = 1
            is_compositional = True
            comp_primitive = op["primitive"]
            comp_arity = op["arity"]
            comp_operation = op["operation"]

        # Map dependency label to syntactic primitive
        if tok.dep_ in DEP_TO_SYNTACTIC:
            syn_prim = DEP_TO_SYNTACTIC[tok.dep_]
            primitives[syn_prim] = 1

        # Extract TAM from morphology
        morph_str = str(tok.morph)
        for morph_feat, tam_prim in MORPH_TO_TAM.items():
            if morph_feat in morph_str and tam_prim:
                primitives[tam_prim] = 1

        # Handle negation scope
        for child in tok.children:
            if child.dep_ == "neg":
                # Add negation marker (could be used for sign flipping)
                primitives["_NEG_SCOPE"] = 1

        if not primitives:
            return None

        return SentencePrimitiveAssignment(
            lexeme=lemma,
            pos=tok.pos_,
            primitives=primitives,
            confidence=0.9 if is_compositional else 0.8,
            source="spacy",
            is_compositional=is_compositional,
            comp_primitive=comp_primitive,
            comp_arity=comp_arity,
            comp_operation=comp_operation,
        )

    def _extract_amr_primitives(self, amr_string: str) -> List[Tuple[str, str, int]]:
        """
        Extract primitive assignments from AMR graph.

        Returns list of (concept, primitive, value) tuples.
        """
        primitives = []

        # Parse AMR string for relations
        for relation, prim in AMR_TO_PRIMITIVES.items():
            if prim and relation in amr_string:
                # Extract the concept associated with this relation
                pattern = rf'{relation}\s+\((\w+)\s*/\s*(\S+)'
                matches = re.findall(pattern, amr_string)
                for var, concept in matches:
                    primitives.append((concept.split("-")[0], prim, 1))

        # Check for polarity
        if ":polarity -" in amr_string:
            primitives.append(("_sentence", "_NEG_SCOPE", 1))

        return primitives

    def _merge_amr_assignments(
        self,
        spacy_assignments: List[SentencePrimitiveAssignment],
        amr_primitives: List[Tuple[str, str, int]],
    ):
        """Merge AMR primitives into spaCy assignments."""
        for concept, prim, value in amr_primitives:
            # Find matching assignment by lemma
            for asn in spacy_assignments:
                if asn.lexeme.lower() == concept.lower():
                    if prim not in asn.primitives:
                        asn.primitives[prim] = value
                        asn.source = "spacy+amr"
                    break


# =============================================================================
# LEXICON POPULATOR
# =============================================================================

class LexiconSentencePrimitivePopulator:
    """
    Populate lexicon database with sentence-scale primitives.

    Uses NLP resources to assign:
    1. Default syntactic roles (SYN_*) based on POS
    2. Compositional operators (COMP_*) for function words
    3. TAM features for verbs
    """

    # Default syntactic capabilities by POS (Universal POS tags from spaCy)
    POS_DEFAULT_PRIMITIVES = {
        # Nouns can be subjects, objects
        "NOUN": {"SYN_SUBJ": 1, "SYN_OBJ": 1},
        "PROPN": {"SYN_SUBJ": 1, "SYN_OBJ": 1},
        "PRON": {"SYN_SUBJ": 1, "SYN_OBJ": 1},

        # Verbs are predicates
        "VERB": {"SYN_PRED": 1},
        "AUX": {"SYN_PRED": 1},

        # Adjectives modify nouns and can be complements
        "ADJ": {"SYN_ADJ_MOD": 1, "SYN_COMPL": 1},

        # Adverbs modify verbs/adjectives
        "ADV": {"SYN_ADV_MOD": 1},

        # Determiners
        "DET": {"SYN_DET": 1},

        # Adpositions (prepositions)
        "ADP": {"SYN_ADV_MOD": 1},

        # Conjunctions
        "CCONJ": {},  # Handled as COMP_* operators
        "SCONJ": {},  # Handled as COMP_* operators

        # Particles (like "to" in infinitives)
        "PART": {"SYN_ADV_MOD": 1},
    }

    def __init__(self, db_path: str):
        import sqlite3
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.parser = SentencePrimitiveParser(use_amr=False)  # Use spaCy only for speed

    def populate_function_words(self) -> Dict[str, int]:
        """
        Assign COMP_* primitives to function words in the lexicon.

        Returns:
            Dict mapping operator to count of words updated
        """
        counts = {}

        for word, op_data in FUNCTION_WORD_OPERATORS.items():
            # Find lexeme in database
            self.cursor.execute(
                "SELECT id FROM lexemes WHERE lemma = ?",
                (word,)
            )
            rows = self.cursor.fetchall()

            if not rows:
                # Try with different POS
                self.cursor.execute(
                    "SELECT id FROM lexemes WHERE lemma = ? LIMIT 1",
                    (word,)
                )
                rows = self.cursor.fetchall()

            for (lexeme_id,) in rows:
                # Update lexeme metadata
                self.cursor.execute("""
                    UPDATE lexemes SET
                        comp_primitive = ?,
                        comp_arity = ?,
                        comp_operation = ?
                    WHERE id = ?
                """, (op_data["primitive"], op_data["arity"],
                      op_data["operation"], lexeme_id))

                # Insert sentence primitive value
                self.cursor.execute("""
                    INSERT OR REPLACE INTO sentence_primitive_values
                    (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, ?, 1, 0.95, 'function_word_mapping')
                """, (lexeme_id, op_data["primitive"]))

                counts[op_data["primitive"]] = counts.get(op_data["primitive"], 0) + 1

        self.conn.commit()
        return counts

    def populate_pos_defaults(self, batch_size: int = 1000) -> int:
        """
        Assign default SYN_* primitives based on POS tags.

        Returns:
            Count of lexemes updated
        """
        count = 0

        for pos, primitives in self.POS_DEFAULT_PRIMITIVES.items():
            if not primitives:  # Skip empty mappings (conjunctions)
                continue

            # Exact POS match (spaCy uses uppercase)
            self.cursor.execute(
                "SELECT id FROM lexemes WHERE pos = ?",
                (pos,)
            )
            rows = self.cursor.fetchall()

            for (lexeme_id,) in rows:
                for prim, value in primitives.items():
                    self.cursor.execute("""
                        INSERT OR IGNORE INTO sentence_primitive_values
                        (lexeme_id, primitive, value, confidence, source)
                        VALUES (?, ?, ?, 0.7, 'pos_default')
                    """, (lexeme_id, prim, value))
                    if self.cursor.rowcount > 0:
                        count += 1

            if count % batch_size == 0:
                self.conn.commit()

        self.conn.commit()
        return count

    def close(self):
        self.conn.close()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=== Sentence Primitive Parser Test ===\n")

    parser = SentencePrimitiveParser(use_amr=False)

    test_sentences = [
        "The dog is cuter than the cat.",
        "How fast can you run?",
        "She just finished the work.",
        "I think but I'm not sure.",
        "The book on the table is red.",
    ]

    for sent in test_sentences:
        print(f"Input: {sent}")
        result = parser.parse(sent)

        print(f"  Interrogative: {result.is_interrogative}")
        print(f"  Comparison: {result.has_comparison}")
        print(f"  Negative: {result.is_negative}")
        print("  Assignments:")
        for asn in result.assignments:
            comp = f" [COMP: {asn.comp_operation}]" if asn.is_compositional else ""
            print(f"    {asn.lexeme} ({asn.pos}): {asn.primitives}{comp}")
        print()
