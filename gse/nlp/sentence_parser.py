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
