#!/usr/bin/env python3
"""
GSE Lexicon Audit Pipeline (v4)

Complete pipeline for auditing and fixing the lexicon database.
Implements the 6-stage audit process with the Three-Layer Architecture.

Run with: python scripts/run_full_audit_pipeline.py --db data/lexicon.db
         python scripts/run_full_audit_pipeline.py --stage 0  # Run only component classification
         python scripts/run_full_audit_pipeline.py --verify   # Run verification only

See: prompts/AUDIT_PIPELINE.md for full documentation
"""

import argparse
import json
import logging
import sqlite3
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# STAGE 0: COMPONENT CLASSIFICATION
# =============================================================================

SIGN_OPERATORS = {"not", "never", "no", "n't", "neither", "nor"}

HIERARCHY_OPERATORS = {
    "very",
    "extremely",
    "quite",
    "rather",
    "somewhat",
    "barely",
    "hardly",
    "slightly",
    "highly",
    "totally",
    "really",
    "truly",
    "fairly",
    "pretty",
    "incredibly",
    "exceedingly",
    "remarkably",
    "awfully",
    "terribly",
}

AUXILIARY_VERBS = {
    "be",
    "am",
    "is",
    "are",
    "was",
    "were",
    "been",
    "being",
    "have",
    "has",
    "had",
    "having",
    "do",
    "does",
    "did",
    "doing",
    "can",
    "could",
    "will",
    "would",
    "shall",
    "should",
    "may",
    "might",
    "must",
}

DETERMINERS = {
    "the",
    "a",
    "an",
    "this",
    "that",
    "these",
    "those",
    "my",
    "your",
    "his",
    "her",
    "its",
    "our",
    "their",
    "some",
    "any",
    "no",
    "every",
    "each",
    "all",
    "both",
    "few",
    "many",
    "much",
    "several",
    "most",
    "either",
    "neither",
    "another",
    "such",
    "what",
    "which",
    "whose",
}

PREPOSITIONS = {
    "in",
    "on",
    "at",
    "by",
    "for",
    "with",
    "to",
    "from",
    "of",
    "about",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "over",
    "across",
    "against",
    "along",
    "among",
    "around",
    "behind",
    "beneath",
    "beside",
    "beyond",
    "down",
    "inside",
    "near",
    "off",
    "onto",
    "outside",
    "past",
    "toward",
    "towards",
    "up",
    "upon",
    "within",
    "without",
}

CONJUNCTIONS = {"and", "or", "but", "nor", "yet", "so", "for"}

COMPLEMENTIZERS = {
    "that",
    "if",
    "whether",
    "because",
    "although",
    "while",
    "when",
    "where",
    "whereas",
    "unless",
    "until",
    "since",
    "though",
    "as",
}


def classify_word(lemma: str, pos: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Classify a word into component_type, operator_type, binding_behavior.

    Returns: (component_type, operator_type, binding_behavior)
    """
    lemma_lower = lemma.lower()

    # Check SIGN operators first
    if lemma_lower in SIGN_OPERATORS:
        return ("OPERATOR", "SIGN", "GREEDY")

    # Check HIERARCHY operators
    if lemma_lower in HIERARCHY_OPERATORS:
        return ("OPERATOR", "HIERARCHY", "GREEDY")

    # Check auxiliaries - these are HYBRID
    if lemma_lower in AUXILIARY_VERBS:
        return ("HYBRID", "AUXILIARY", "LAZY")

    # Check determiners
    if lemma_lower in DETERMINERS:
        return ("OPERATOR", "DETERMINER", "GREEDY")

    # Check prepositions
    if lemma_lower in PREPOSITIONS:
        return ("OPERATOR", "PREPOSITION", "GREEDY")

    # Check conjunctions
    if lemma_lower in CONJUNCTIONS:
        return ("OPERATOR", "CONJUNCTION", None)

    # Check complementizers
    if lemma_lower in COMPLEMENTIZERS:
        return ("OPERATOR", "COMPLEMENTIZER", None)

    # Default: ATOMIC
    return ("ATOMIC", None, None)


def run_stage_0(cursor: sqlite3.Cursor) -> Dict[str, int]:
    """Stage 0: Component Classification"""
    logger.info("=" * 60)
    logger.info("STAGE 0: COMPONENT CLASSIFICATION")
    logger.info("=" * 60)

    stats = {"classified": 0, "atomic": 0, "operator": 0, "hybrid": 0}

    # Add columns if they don't exist
    for col, default in [
        ("component_type", "'ATOMIC'"),
        ("operator_type", "NULL"),
        ("binding_behavior", "NULL"),
        ("gram_features", "NULL"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE lexemes ADD COLUMN {col} TEXT DEFAULT {default}")
            logger.info(f"  Added column: {col}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Get all lexemes
    cursor.execute("SELECT id, lemma, pos FROM lexemes")
    rows = cursor.fetchall()

    for id_, lemma, pos in rows:
        comp_type, op_type, binding = classify_word(lemma, pos or "")

        cursor.execute(
            """
            UPDATE lexemes
            SET component_type = ?,
                operator_type = ?,
                binding_behavior = ?
            WHERE id = ?
        """,
            (comp_type, op_type, binding, id_),
        )

        stats["classified"] += 1
        if comp_type == "ATOMIC":
            stats["atomic"] += 1
        elif comp_type == "OPERATOR":
            stats["operator"] += 1
        elif comp_type == "HYBRID":
            stats["hybrid"] += 1

    logger.info(f"  Classified {stats['classified']} lexemes")
    logger.info(f"    ATOMIC: {stats['atomic']}")
    logger.info(f"    OPERATOR: {stats['operator']}")
    logger.info(f"    HYBRID: {stats['hybrid']}")

    return stats


# =============================================================================
# STAGE 1: FUNCTION WORD PRIMITIVES
# =============================================================================

FUNCTION_WORDS = [
    "the",
    "of",
    "and",
    "to",
    "a",
    "in",
    "is",
    "that",
    "for",
    "it",
    "with",
    "as",
    "on",
    "at",
    "by",
    "from",
    "or",
    "an",
    "be",
    "this",
    "are",
    "was",
    "were",
    "been",
    "being",
    "have",
    "has",
    "had",
    "not",
    "but",
    "if",
    "which",
    "their",
    "so",
    "what",
    "when",
    "into",
    "than",
    "its",
    "any",
    "no",
    "do",
    "how",
    "up",
    "out",
    "just",
    "about",
]


def run_stage_1(cursor: sqlite3.Cursor) -> Dict[str, int]:
    """Stage 1: Reset function word primitives to minimal set"""
    logger.info("=" * 60)
    logger.info("STAGE 1: FUNCTION WORD PRIMITIVES")
    logger.info("=" * 60)

    stats = {"reset": 0}

    placeholders = ",".join(["?"] * len(FUNCTION_WORDS))
    cursor.execute(
        f"""
        UPDATE primitive_values
        SET value = 0, confidence = 0.9, source = 'fix:function_word'
        WHERE lexeme_id IN (
            SELECT id FROM lexemes WHERE lemma IN ({placeholders})
        )
    """,
        FUNCTION_WORDS,
    )

    stats["reset"] = cursor.rowcount
    logger.info(f"  Reset {cursor.rowcount} primitive values for function words")

    return stats


# =============================================================================
# STAGES 2-5: SEMANTIC PRIMITIVES FIXES
# =============================================================================

SAY_FALSE_POSITIVES = [
    "you",
    "me",
    "people",
    "life",
    "time",
    "system",
    "being",
    "example",
    "human",
    "social",
    "world",
    "control",
    "something",
    "person",
    "order",
    "love",
    "everything",
    "protein",
    "health",
    "living",
    "water",
    "relationship",
    "sense",
    "feeling",
    "activity",
    "bit",
    "food",
    "air",
    "medicine",
    "hot",
    "reaction",
    "motion",
    "fish",
    "eat",
    "mushroom",
    "caffeine",
    "liquid",
    "consumption",
    "fluid",
    "salt",
    "feed",
    "pleasure",
    "treat",
]

SPEECH_WORDS = [
    "said",
    "told",
    "word",
    "language",
    "response",
    "communication",
    "expression",
    "teaching",
    "explain",
    "saying",
    "speaking",
    "speech",
    "conversation",
    "ask",
    "answer",
    "describe",
    "introduction",
    "discussion",
    "offer",
    "argument",
    "statement",
    "feedback",
    "storytelling",
    "talking",
    "chat",
    "promise",
    "emphasis",
    "introduce",
    "spoke",
    "stated",
    "ordered",
    "conversational",
    "participation",
    "sentence",
]

FEEL_FALSE_POSITIVES = [
    "time",
    "system",
    "structure",
    "theory",
    "energy",
    "network",
    "result",
    "production",
    "resources",
    "quality",
    "war",
    "organization",
    "management",
    "policy",
    "law",
    "school",
    "body",
    "death",
    "past",
    "full",
    "weight",
    "loss",
    "operation",
    "trade",
    "machine",
    "error",
    "music",
    "ground",
    "base",
    "established",
    "period",
    "constant",
    "lines",
    "effort",
    "strength",
    "architecture",
    "exchange",
    "concentration",
    "assembly",
    "statistical",
    "sample",
    "variable",
    "spike",
    "assessment",
    "university",
    "government",
    "economy",
    "budget",
    "differential",
    "mathematical",
    "hypothesis",
    "score",
    "execution",
    "perturbation",
    "mail",
    "sun",
    "fire",
    "electric",
    "phone",
    "birth",
    "title",
    "proof",
    "challenge",
]

HIGH_VALENCE_WORDS = ["life", "birth", "cash", "confidence", "robustness"]

FIRST_PERSON = ["i", "me", "my", "myself", "mine"]
SECOND_PERSON = ["you", "your", "yourself", "yours"]
THIRD_PERSON = [
    "he",
    "she",
    "him",
    "her",
    "his",
    "hers",
    "himself",
    "herself",
    "they",
    "them",
    "their",
    "themselves",
    "someone",
    "somebody",
    "anyone",
    "anybody",
    "everyone",
    "everybody",
    "nobody",
    "person",
    "people",
]


def run_stage_2_5(cursor: sqlite3.Cursor) -> Dict[str, int]:
    """Stages 2-5: Semantic primitive fixes"""
    logger.info("=" * 60)
    logger.info("STAGES 2-5: SEMANTIC PRIMITIVES FIXES")
    logger.info("=" * 60)

    stats = {"say_false": 0, "words_added": 0, "feel_false": 0, "good_fixes": 0, "pronoun_fixes": 0}

    # SAY=0 for false positives
    logger.info("  Fix 2a: SAY=0 for false positives...")
    placeholders = ",".join(["?"] * len(SAY_FALSE_POSITIVES))
    cursor.execute(
        f"""
        UPDATE primitive_values
        SET value = 0, confidence = 0.8, source = 'fix:say_false_positive'
        WHERE primitive = 'SAY'
        AND lexeme_id IN (
            SELECT id FROM lexemes WHERE lemma IN ({placeholders})
        )
    """,
        SAY_FALSE_POSITIVES,
    )
    stats["say_false"] = cursor.rowcount

    # WORDS=1 for speech words
    logger.info("  Fix 2b: WORDS=1 for speech words...")
    placeholders = ",".join(["?"] * len(SPEECH_WORDS))
    cursor.execute(
        f"""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'WORDS', 1, 0.85, 'fix:say_requires_words'
        FROM lexemes WHERE lemma IN ({placeholders})
    """,
        SPEECH_WORDS,
    )
    stats["words_added"] = cursor.rowcount

    # FEEL=0 for abstract/inanimate
    logger.info("  Fix 3: FEEL=0 for abstract/inanimate...")
    placeholders = ",".join(["?"] * len(FEEL_FALSE_POSITIVES))
    cursor.execute(
        f"""
        UPDATE primitive_values
        SET value = 0, confidence = 0.8, source = 'fix:feel_false_positive'
        WHERE primitive = 'FEEL'
        AND lexeme_id IN (
            SELECT id FROM lexemes WHERE lemma IN ({placeholders})
        )
    """,
        FEEL_FALSE_POSITIVES,
    )
    stats["feel_false"] = cursor.rowcount

    # GOOD=1 for high-valence words
    logger.info("  Fix 4: GOOD=1 for high-valence words...")
    placeholders = ",".join(["?"] * len(HIGH_VALENCE_WORDS))
    cursor.execute(
        f"""
        UPDATE primitive_values
        SET value = 1, confidence = 0.9, source = 'fix:nrc_vad_positive'
        WHERE primitive = 'GOOD'
        AND lexeme_id IN (
            SELECT id FROM lexemes WHERE lemma IN ({placeholders})
        )
    """,
        HIGH_VALENCE_WORDS,
    )
    stats["good_fixes"] = cursor.rowcount

    # Pronoun fixes
    logger.info("  Fix 5: Pronoun corrections...")

    # First person
    placeholders = ",".join(["?"] * len(FIRST_PERSON))
    cursor.execute(
        f"""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'I', 1, 0.95, 'fix:pronoun_first_person'
        FROM lexemes WHERE lemma IN ({placeholders})
    """,
        FIRST_PERSON,
    )
    cursor.execute(
        f"""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'SOMEONE', 1, 0.95, 'fix:pronoun_first_person'
        FROM lexemes WHERE lemma IN ({placeholders})
    """,
        FIRST_PERSON,
    )

    # Second person
    placeholders = ",".join(["?"] * len(SECOND_PERSON))
    cursor.execute(
        f"""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'YOU', 1, 0.95, 'fix:pronoun_second_person'
        FROM lexemes WHERE lemma IN ({placeholders})
    """,
        SECOND_PERSON,
    )
    cursor.execute(
        f"""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'SOMEONE', 1, 0.95, 'fix:pronoun_second_person'
        FROM lexemes WHERE lemma IN ({placeholders})
    """,
        SECOND_PERSON,
    )

    # Third person
    placeholders = ",".join(["?"] * len(THIRD_PERSON))
    cursor.execute(
        f"""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'SOMEONE', 1, 0.9, 'fix:pronoun_third_person'
        FROM lexemes WHERE lemma IN ({placeholders})
    """,
        THIRD_PERSON,
    )

    stats["pronoun_fixes"] = len(FIRST_PERSON) * 2 + len(SECOND_PERSON) * 2 + len(THIRD_PERSON)

    logger.info(f"    SAY false positives: {stats['say_false']}")
    logger.info(f"    WORDS added: {stats['words_added']}")
    logger.info(f"    FEEL false positives: {stats['feel_false']}")
    logger.info(f"    GOOD fixes: {stats['good_fixes']}")
    logger.info(f"    Pronoun fixes: {stats['pronoun_fixes']}")

    return stats


# =============================================================================
# STAGE 6: MODIFIER HIERARCHY
# =============================================================================


def run_stage_6(cursor: sqlite3.Cursor) -> Dict[str, int]:
    """Stage 6: Modifier hierarchy encoding"""
    logger.info("=" * 60)
    logger.info("STAGE 6: MODIFIER HIERARCHY")
    logger.info("=" * 60)

    stats = {"updated": 0}

    # Try to load ground truth
    try:
        import sys

        sys.path.insert(0, ".")
        from scripts.load_intensity_ground_truth import get_modifier_ground_truth

        gt = get_modifier_ground_truth()

        for word, entry in gt.modifiers.items():
            cursor.execute("SELECT id FROM lexemes WHERE lemma = ?", (word,))
            row = cursor.fetchone()
            if not row:
                continue
            lex_id = row[0]

            # Set base primitive to +1
            cursor.execute(
                """
                INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                VALUES (?, ?, 1, 0.9, 'fix:modifier_hierarchy')
            """,
                (lex_id, entry.hierarchy_type),
            )

            # Set HIER_PLUS or HIER_MINUS
            if entry.level > 0:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, 'HIER_PLUS', ?, 0.9, 'fix:modifier_hierarchy')
                """,
                    (lex_id, entry.level),
                )
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, 'HIER_MINUS', 0, 0.9, 'fix:modifier_hierarchy')
                """,
                    (lex_id,),
                )
            elif entry.level < 0:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, 'HIER_MINUS', ?, 0.9, 'fix:modifier_hierarchy')
                """,
                    (lex_id, abs(entry.level)),
                )
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, 'HIER_PLUS', 0, 0.9, 'fix:modifier_hierarchy')
                """,
                    (lex_id,),
                )
            else:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, 'HIER_PLUS', 0, 0.9, 'fix:modifier_hierarchy')
                """,
                    (lex_id,),
                )
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, 'HIER_MINUS', 0, 0.9, 'fix:modifier_hierarchy')
                """,
                    (lex_id,),
                )

            stats["updated"] += 1

        logger.info(f"  Applied hierarchy encoding to {stats['updated']} modifiers")
    except ImportError:
        logger.warning("  Skipped - ground truth loader not available")

    return stats


# =============================================================================
# STAGE 7: INFORMATIONAL ZERO INSTANTIATION
# =============================================================================

# POS tag mappings for different tag sets
NOUN_POS = ("NOUN", "NN", "NNS", "NNP", "NNPS")
PRON_POS = ("PRON", "PRP", "PRP$", "WP", "WP$")
VERB_POS = ("VERB", "VB", "VBD", "VBG", "VBN", "VBP", "VBZ")
ADJ_POS = ("ADJ", "JJ", "JJR", "JJS")
ADV_POS = ("ADV", "RB", "RBR", "RBS")
DET_POS = ("DET", "DT", "PDT", "WDT")


def run_stage_7(cursor: sqlite3.Cursor) -> Dict[str, int]:
    """Stage 7: Informational Zero Instantiation"""
    logger.info("=" * 60)
    logger.info("STAGE 7: INFORMATIONAL ZERO INSTANTIATION")
    logger.info("=" * 60)

    stats = {
        "syn_subj": 0,
        "syn_obj": 0,
        "syn_pred": 0,
        "syn_adj_mod": 0,
        "syn_adv_mod": 0,
        "syn_det": 0,
        "syn_compl": 0,
    }

    # SYN_SUBJ for nouns and pronouns
    for pos_list in [NOUN_POS, PRON_POS]:
        placeholders = ",".join(["?"] * len(pos_list))
        cursor.execute(
            f"""
            INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
            SELECT id, 'SYN_SUBJ', 0, 0.95, 'fix:informational_zero'
            FROM lexemes WHERE pos IN ({placeholders})
        """,
            pos_list,
        )
        stats["syn_subj"] += cursor.rowcount

    # SYN_OBJ for nouns and pronouns
    for pos_list in [NOUN_POS, PRON_POS]:
        placeholders = ",".join(["?"] * len(pos_list))
        cursor.execute(
            f"""
            INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
            SELECT id, 'SYN_OBJ', 0, 0.95, 'fix:informational_zero'
            FROM lexemes WHERE pos IN ({placeholders})
        """,
            pos_list,
        )
        stats["syn_obj"] += cursor.rowcount

    # SYN_COMPL for nouns, pronouns, adjectives
    for pos_list in [NOUN_POS, PRON_POS, ADJ_POS]:
        placeholders = ",".join(["?"] * len(pos_list))
        cursor.execute(
            f"""
            INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
            SELECT id, 'SYN_COMPL', 0, 0.95, 'fix:informational_zero'
            FROM lexemes WHERE pos IN ({placeholders})
        """,
            pos_list,
        )
        stats["syn_compl"] += cursor.rowcount

    # SYN_PRED for verbs
    placeholders = ",".join(["?"] * len(VERB_POS))
    cursor.execute(
        f"""
        INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'SYN_PRED', 0, 0.95, 'fix:informational_zero'
        FROM lexemes WHERE pos IN ({placeholders})
    """,
        VERB_POS,
    )
    stats["syn_pred"] = cursor.rowcount

    # SYN_ADJ_MOD for adjectives
    placeholders = ",".join(["?"] * len(ADJ_POS))
    cursor.execute(
        f"""
        INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'SYN_ADJ_MOD', 0, 0.95, 'fix:informational_zero'
        FROM lexemes WHERE pos IN ({placeholders})
    """,
        ADJ_POS,
    )
    stats["syn_adj_mod"] = cursor.rowcount

    # SYN_ADV_MOD for adverbs
    placeholders = ",".join(["?"] * len(ADV_POS))
    cursor.execute(
        f"""
        INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'SYN_ADV_MOD', 0, 0.95, 'fix:informational_zero'
        FROM lexemes WHERE pos IN ({placeholders})
    """,
        ADV_POS,
    )
    stats["syn_adv_mod"] = cursor.rowcount

    # SYN_DET for determiners
    placeholders = ",".join(["?"] * len(DET_POS))
    cursor.execute(
        f"""
        INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'SYN_DET', 0, 0.95, 'fix:informational_zero'
        FROM lexemes WHERE pos IN ({placeholders})
    """,
        DET_POS,
    )
    stats["syn_det"] = cursor.rowcount

    logger.info(f"  SYN_SUBJ: {stats['syn_subj']}")
    logger.info(f"  SYN_OBJ: {stats['syn_obj']}")
    logger.info(f"  SYN_COMPL: {stats['syn_compl']}")
    logger.info(f"  SYN_PRED: {stats['syn_pred']}")
    logger.info(f"  SYN_ADJ_MOD: {stats['syn_adj_mod']}")
    logger.info(f"  SYN_ADV_MOD: {stats['syn_adv_mod']}")
    logger.info(f"  SYN_DET: {stats['syn_det']}")

    return stats


# =============================================================================
# STAGE 8: GRAMMATICAL METADATA
# =============================================================================


def run_stage_8(cursor: sqlite3.Cursor) -> Dict[str, int]:
    """Stage 8: Grammatical Metadata (gram_features JSON)"""
    logger.info("=" * 60)
    logger.info("STAGE 8: GRAMMATICAL METADATA")
    logger.info("=" * 60)

    stats = {"past_tense": 0, "progressive": 0, "perfect": 0, "3sg_pres": 0, "plural": 0}

    # Past tense verbs (VBD)
    cursor.execute("""
        UPDATE lexemes SET gram_features = '{"tense": "PAST"}'
        WHERE pos = 'VBD' AND gram_features IS NULL
    """)
    stats["past_tense"] = cursor.rowcount

    # Present participles (VBG)
    cursor.execute("""
        UPDATE lexemes SET gram_features = '{"aspect": "PROGRESSIVE"}'
        WHERE pos = 'VBG' AND gram_features IS NULL
    """)
    stats["progressive"] = cursor.rowcount

    # Past participles (VBN)
    cursor.execute("""
        UPDATE lexemes SET gram_features = '{"aspect": "PERFECT"}'
        WHERE pos = 'VBN' AND gram_features IS NULL
    """)
    stats["perfect"] = cursor.rowcount

    # Third person singular present (VBZ)
    cursor.execute("""
        UPDATE lexemes SET gram_features = '{"tense": "PRESENT", "person": 3, "number": "SINGULAR"}'
        WHERE pos = 'VBZ' AND gram_features IS NULL
    """)
    stats["3sg_pres"] = cursor.rowcount

    # Plural nouns (NNS, NNPS)
    cursor.execute("""
        UPDATE lexemes SET gram_features = '{"number": "PLURAL"}'
        WHERE pos IN ('NNS', 'NNPS') AND gram_features IS NULL
    """)
    stats["plural"] = cursor.rowcount

    logger.info(f"  Past tense (VBD): {stats['past_tense']}")
    logger.info(f"  Progressive (VBG): {stats['progressive']}")
    logger.info(f"  Perfect (VBN): {stats['perfect']}")
    logger.info(f"  3sg present (VBZ): {stats['3sg_pres']}")
    logger.info(f"  Plural nouns: {stats['plural']}")

    return stats


# =============================================================================
# LLM AUDIT INTEGRATION
# Multi-Model Local Audit System with Database Cross-Validation
#
# Architecture:
#   SQL Audit (find issues) → External Data Validation → LLM Validation → Fixes
#
# Models: smollm:1.7b, granite3-moe:1b, gemma2:2b (small), qwen3:32b (large)
# External Data: NRC-VAD, intensity_ground_truth.json, Lancaster, concreteness
# Mode: AUDIT ONLY - flags issues, generates fix scripts
# =============================================================================

import csv
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Default models for multi-model consensus
DEFAULT_SMALL_MODELS = ["smollm:1.7b", "granite3-moe:1b", "gemma2:2b"]
DEFAULT_LARGE_MODEL = "qwen3:32b"

# Bipolar pairs that cannot both be +1
BIPOLAR_PAIRS = [
    ("GOOD", "BAD"),
    ("TRUE", "FALSE"),
    ("BIG", "SMALL"),
    ("LONG_TIME", "SHORT_TIME"),
    ("NEAR", "FAR"),
    ("ABOVE", "BELOW"),
    ("BEFORE", "AFTER"),
    ("INSIDE", "OUTSIDE"),
    ("MORE", "LESS"),
]

# =============================================================================
# DATABASE-DRIVEN GROUP IDENTIFICATION (from semantic_review_prompt.md)
# These SQL queries identify specific issue groups for LLM validation
# =============================================================================


def get_group1_feel_without_experiencer(cursor: sqlite3.Cursor) -> List[Dict]:
    """
    Group 1: FEEL=1 without Experiencer (SOMEONE/I/YOU)

    These words have FEEL=1 but lack an experiencer primitive.
    LLM determines if:
      A) FEEL=1 is WRONG (inanimate/abstract) → SET FEEL=0
      B) FEEL=1 is CORRECT → ADD SOMEONE=1
    """
    cursor.execute("""
        SELECT l.id, l.lemma, l.pos,
               GROUP_CONCAT(pv.primitive || '=' || pv.value) as primitives
        FROM lexemes l
        JOIN primitive_values feel ON l.id = feel.lexeme_id
            AND feel.primitive = 'FEEL' AND feel.value = 1
        LEFT JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.value != 0
        WHERE l.id NOT IN (
            SELECT lexeme_id FROM primitive_values
            WHERE primitive IN ('SOMEONE', 'I', 'YOU') AND value = 1
        )
        GROUP BY l.id
        ORDER BY l.frequency_rank
    """)
    return [
        {"id": r[0], "lemma": r[1], "pos": r[2] or "UNKNOWN", "primitives": r[3] or "", "issue": "FEEL_NO_EXPERIENCER"}
        for r in cursor.fetchall()
    ]


def get_group2_verbs_missing_do_happen(cursor: sqlite3.Cursor) -> List[Dict]:
    """
    Group 2: Verbs Potentially Missing DO/HAPPEN

    Verbs should have DO=1 (agentive) or HAPPEN=1 (non-agentive) or both.
    """
    cursor.execute("""
        SELECT l.id, l.lemma, l.pos,
               GROUP_CONCAT(pv.primitive || '=' || pv.value) as primitives
        FROM lexemes l
        LEFT JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.value != 0
        WHERE l.pos IN ('VERB', 'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ')
        AND l.component_type = 'ATOMIC'
        AND l.id NOT IN (
            SELECT lexeme_id FROM primitive_values
            WHERE primitive IN ('DO', 'HAPPEN') AND value = 1
        )
        GROUP BY l.id
        ORDER BY l.frequency_rank
        LIMIT 100
    """)
    return [
        {"id": r[0], "lemma": r[1], "pos": r[2] or "VERB", "primitives": r[3] or "", "issue": "VERB_NO_DO_HAPPEN"}
        for r in cursor.fetchall()
    ]


def get_group3_intensity_issues(cursor: sqlite3.Cursor) -> List[Dict]:
    """
    Group 3: INTENSITY Value Review

    Finds:
    - INTENSITY=-1 (should be INTENSITY=1 with HIER_MINUS)
    - Missing HIER markers on modifiers
    """
    issues = []

    # INTENSITY=-1 is WRONG
    cursor.execute("""
        SELECT l.id, l.lemma, l.pos, pv.value,
               GROUP_CONCAT(pv2.primitive || '=' || pv2.value) as primitives
        FROM lexemes l
        JOIN primitive_values pv ON l.id = pv.lexeme_id
            AND pv.primitive = 'INTENSITY' AND pv.value = -1
        LEFT JOIN primitive_values pv2 ON l.id = pv2.lexeme_id AND pv2.value != 0
        GROUP BY l.id
    """)
    for r in cursor.fetchall():
        issues.append(
            {
                "id": r[0],
                "lemma": r[1],
                "pos": r[2] or "UNKNOWN",
                "primitives": r[4] or "",
                "issue": "INTENSITY_NEGATIVE",
                "current_value": r[3],
            }
        )

    # Hierarchy modifiers missing HIER markers
    cursor.execute("""
        SELECT l.id, l.lemma, l.pos,
               GROUP_CONCAT(pv.primitive || '=' || pv.value) as primitives
        FROM lexemes l
        JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.value != 0
        WHERE l.operator_type = 'HIERARCHY'
        AND l.id NOT IN (
            SELECT lexeme_id FROM primitive_values
            WHERE primitive IN ('HIER_PLUS', 'HIER_MINUS') AND value != 0
        )
        GROUP BY l.id
    """)
    for r in cursor.fetchall():
        issues.append(
            {
                "id": r[0],
                "lemma": r[1],
                "pos": r[2] or "UNKNOWN",
                "primitives": r[3] or "",
                "issue": "MISSING_HIER_MARKERS",
            }
        )

    return issues


def get_group4_modifier_hierarchy_validation(cursor: sqlite3.Cursor) -> List[Dict]:
    """
    Group 4: Modifier Hierarchy Validation against ground truth

    Cross-validates modifiers against data/external/intensity_ground_truth.json
    """
    try:
        from scripts.load_intensity_ground_truth import get_modifier_ground_truth

        gt = get_modifier_ground_truth()
    except ImportError:
        logger.warning("  Could not load intensity ground truth")
        return []

    issues = []

    for word in gt.get_all_modifiers():
        cursor.execute(
            """
            SELECT l.id, l.lemma, l.pos,
                   MAX(CASE WHEN pv.primitive = 'INTENSITY' THEN pv.value END) as intensity,
                   MAX(CASE WHEN pv.primitive = 'QUANTITY' THEN pv.value END) as quantity,
                   MAX(CASE WHEN pv.primitive = 'CERTAINTY' THEN pv.value END) as certainty,
                   MAX(CASE WHEN pv.primitive = 'HIER_PLUS' THEN pv.value END) as hier_plus,
                   MAX(CASE WHEN pv.primitive = 'HIER_MINUS' THEN pv.value END) as hier_minus
            FROM lexemes l
            LEFT JOIN primitive_values pv ON l.id = pv.lexeme_id
            WHERE l.lemma = ?
            GROUP BY l.id
        """,
            (word,),
        )
        row = cursor.fetchone()

        if not row:
            continue

        entry = gt.get_entry(word)
        expected = gt.get_expected_encoding(word)

        if not expected:
            continue

        # Check if current encoding matches expected
        current = {
            "INTENSITY": row[3] or 0,
            "QUANTITY": row[4] or 0,
            "CERTAINTY": row[5] or 0,
            "HIER_PLUS": row[6] or 0,
            "HIER_MINUS": row[7] or 0,
        }

        # Compare base primitive
        base_prim = entry.hierarchy_type
        if current.get(base_prim, 0) != 1:
            issues.append(
                {
                    "id": row[0],
                    "lemma": word,
                    "pos": row[2] or "UNKNOWN",
                    "issue": f"WRONG_{base_prim}",
                    "current": current,
                    "expected": expected,
                    "ground_truth_level": entry.level,
                }
            )
        # Compare HIER markers
        elif entry.level > 0 and current.get("HIER_PLUS", 0) != entry.level:
            issues.append(
                {
                    "id": row[0],
                    "lemma": word,
                    "pos": row[2] or "UNKNOWN",
                    "issue": "WRONG_HIER_PLUS",
                    "current": current,
                    "expected": expected,
                    "ground_truth_level": entry.level,
                }
            )
        elif entry.level < 0 and current.get("HIER_MINUS", 0) != abs(entry.level):
            issues.append(
                {
                    "id": row[0],
                    "lemma": word,
                    "pos": row[2] or "UNKNOWN",
                    "issue": "WRONG_HIER_MINUS",
                    "current": current,
                    "expected": expected,
                    "ground_truth_level": entry.level,
                }
            )

    return issues


def get_group5_say_without_words(cursor: sqlite3.Cursor) -> List[Dict]:
    """
    Group 5: SAY=1 without WORDS

    SAY=1 requires WORDS=1 (communicative speech act)
    """
    cursor.execute("""
        SELECT l.id, l.lemma, l.pos,
               GROUP_CONCAT(pv.primitive || '=' || pv.value) as primitives
        FROM lexemes l
        JOIN primitive_values say ON l.id = say.lexeme_id
            AND say.primitive = 'SAY' AND say.value = 1
        LEFT JOIN primitive_values words ON l.id = words.lexeme_id
            AND words.primitive = 'WORDS'
        LEFT JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.value != 0
        WHERE (words.value IS NULL OR words.value != 1)
        GROUP BY l.id
        ORDER BY l.frequency_rank
    """)
    return [
        {"id": r[0], "lemma": r[1], "pos": r[2] or "UNKNOWN", "primitives": r[3] or "", "issue": "SAY_NO_WORDS"}
        for r in cursor.fetchall()
    ]


def get_group6_bipolar_violations(cursor: sqlite3.Cursor) -> List[Dict]:
    """
    Group 6: Bipolar Violations

    Bipolar pairs (GOOD/BAD, TRUE/FALSE, etc.) cannot both be +1
    """
    issues = []

    for prim1, prim2 in BIPOLAR_PAIRS:
        cursor.execute(
            """
            SELECT l.id, l.lemma, l.pos, p1.value, p2.value
            FROM lexemes l
            JOIN primitive_values p1 ON l.id = p1.lexeme_id
                AND p1.primitive = ? AND p1.value = 1
            JOIN primitive_values p2 ON l.id = p2.lexeme_id
                AND p2.primitive = ? AND p2.value = 1
        """,
            (prim1, prim2),
        )

        for r in cursor.fetchall():
            issues.append(
                {
                    "id": r[0],
                    "lemma": r[1],
                    "pos": r[2] or "UNKNOWN",
                    "issue": f"BIPOLAR_{prim1}_{prim2}",
                    "primitives": f"{prim1}=1,{prim2}=1",
                }
            )

    return issues


def get_group7_function_words_excessive_primitives(cursor: sqlite3.Cursor) -> List[Dict]:
    """
    Group 7: Function words with too many primitives

    OPERATORs should have 0-2 active primitives (informational zeros only)
    """
    cursor.execute("""
        SELECT l.id, l.lemma, l.pos, l.component_type, l.operator_type,
               COUNT(*) as prim_count,
               GROUP_CONCAT(pv.primitive || '=' || pv.value) as primitives
        FROM lexemes l
        JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.value != 0
        WHERE l.component_type = 'OPERATOR'
        GROUP BY l.id
        HAVING prim_count > 2
        ORDER BY prim_count DESC
    """)
    return [
        {
            "id": r[0],
            "lemma": r[1],
            "pos": r[2] or "UNKNOWN",
            "component_type": r[3],
            "operator_type": r[4],
            "prim_count": r[5],
            "primitives": r[6] or "",
            "issue": "OPERATOR_EXCESSIVE_PRIMITIVES",
        }
        for r in cursor.fetchall()
    ]


# =============================================================================
# EXTERNAL DATA CROSS-VALIDATION
# Load and validate against external linguistic resources
# =============================================================================


class ExternalDataValidator:
    """
    Cross-validates lexicon against external data sources:
    - NRC-VAD: valence/arousal/dominance → GOOD/BAD, INTENSITY
    - Lancaster: sensorimotor norms → BODY, SEE, HEAR, MOVE
    - Concreteness: abstract vs concrete → BODY validation
    - Intensity ground truth: modifier hierarchy → INTENSITY/QUANTITY/CERTAINTY
    """

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data" / "external"
        self.data_dir = Path(data_dir)

        self.nrc_vad = {}
        self.lancaster = {}
        self.concreteness = {}

        self._load_nrc_vad()
        self._load_concreteness()
        # Lancaster is large, load on demand

    def _load_nrc_vad(self):
        """Load NRC-VAD lexicon (valence, arousal, dominance)."""
        vad_path = self.data_dir / "nrc_vad.txt"
        if not vad_path.exists():
            logger.warning(f"  NRC-VAD not found: {vad_path}")
            return

        try:
            with open(vad_path) as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    word = row.get("term", row.get("word", "")).lower()
                    if word:
                        self.nrc_vad[word] = {
                            "valence": float(row.get("valence", 0)),
                            "arousal": float(row.get("arousal", 0)),
                            "dominance": float(row.get("dominance", 0)),
                        }
            logger.info(f"  Loaded NRC-VAD: {len(self.nrc_vad)} words")
        except Exception as e:
            logger.warning(f"  Error loading NRC-VAD: {e}")

    def _load_concreteness(self):
        """Load concreteness ratings."""
        conc_path = self.data_dir / "concreteness.csv"
        if not conc_path.exists():
            return

        try:
            with open(conc_path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    word = row.get("Word", row.get("word", "")).lower()
                    rating = row.get("Conc.M", row.get("concreteness", row.get("rating", "")))
                    if word and rating:
                        self.concreteness[word] = float(rating)
            logger.info(f"  Loaded concreteness: {len(self.concreteness)} words")
        except Exception as e:
            logger.warning(f"  Error loading concreteness: {e}")

    def validate_intensity_with_arousal(self, word: str, current_intensity: int) -> Optional[Dict]:
        """
        Cross-validate INTENSITY with NRC-VAD arousal scores.

        High arousal (>0.3) should correlate with INTENSITY=1
        Low arousal (<-0.3) should correlate with INTENSITY=-1 or HIER_MINUS
        """
        word = word.lower()
        if word not in self.nrc_vad:
            return None

        arousal = self.nrc_vad[word]["arousal"]

        # Check for mismatches
        if arousal > 0.3 and current_intensity != 1:
            return {
                "word": word,
                "issue": "AROUSAL_INTENSITY_MISMATCH",
                "arousal": arousal,
                "current_intensity": current_intensity,
                "expected": "INTENSITY=1 (high arousal)",
            }
        elif arousal < -0.3 and current_intensity == 1:
            return {
                "word": word,
                "issue": "AROUSAL_INTENSITY_MISMATCH",
                "arousal": arousal,
                "current_intensity": current_intensity,
                "expected": "Consider HIER_MINUS (low arousal)",
            }

        return None

    def validate_valence_with_good_bad(self, word: str, good_val: int, bad_val: int) -> Optional[Dict]:
        """
        Cross-validate GOOD/BAD with NRC-VAD valence scores.

        High valence (>0.3) should have GOOD=1
        Low valence (<-0.3) should have BAD=1
        """
        word = word.lower()
        if word not in self.nrc_vad:
            return None

        valence = self.nrc_vad[word]["valence"]

        if valence > 0.3 and good_val != 1:
            return {
                "word": word,
                "issue": "VALENCE_GOOD_MISMATCH",
                "valence": valence,
                "current": f"GOOD={good_val}",
                "expected": "GOOD=1 (high valence)",
            }
        elif valence < -0.3 and bad_val != 1:
            return {
                "word": word,
                "issue": "VALENCE_BAD_MISMATCH",
                "valence": valence,
                "current": f"BAD={bad_val}",
                "expected": "BAD=1 (low valence)",
            }

        return None

    def validate_body_with_concreteness(self, word: str, body_val: int) -> Optional[Dict]:
        """
        Cross-validate BODY with concreteness ratings.

        Abstract words (concreteness < 2.5) should NOT have BODY=1
        """
        word = word.lower()
        if word not in self.concreteness:
            return None

        conc = self.concreteness[word]

        if conc < 2.5 and body_val == 1:
            return {
                "word": word,
                "issue": "BODY_ABSTRACT_MISMATCH",
                "concreteness": conc,
                "current": "BODY=1",
                "expected": "BODY=0 (abstract concept)",
            }

        return None

    def get_arousal(self, word: str) -> Optional[float]:
        """Get NRC-VAD arousal score for a word."""
        return self.nrc_vad.get(word.lower(), {}).get("arousal")

    def get_valence(self, word: str) -> Optional[float]:
        """Get NRC-VAD valence score for a word."""
        return self.nrc_vad.get(word.lower(), {}).get("valence")

    def get_concreteness(self, word: str) -> Optional[float]:
        """Get concreteness rating for a word."""
        return self.concreteness.get(word.lower())


def run_external_data_validation(cursor: sqlite3.Cursor) -> Dict[str, List[Dict]]:
    """
    Run cross-validation against all external data sources.

    Returns dict of issue groups with external data disagreements.
    """
    logger.info("=" * 60)
    logger.info("EXTERNAL DATA CROSS-VALIDATION")
    logger.info("=" * 60)

    validator = ExternalDataValidator()
    issues = {"arousal_intensity": [], "valence_good_bad": [], "body_concreteness": [], "modifier_hierarchy": []}

    # Get words with INTENSITY for arousal validation
    cursor.execute("""
        SELECT l.lemma, pv.value
        FROM lexemes l
        JOIN primitive_values pv ON l.id = pv.lexeme_id
        WHERE pv.primitive = 'INTENSITY'
    """)
    for lemma, intensity_val in cursor.fetchall():
        issue = validator.validate_intensity_with_arousal(lemma, intensity_val)
        if issue:
            issues["arousal_intensity"].append(issue)

    # Get words for valence/GOOD-BAD validation
    cursor.execute("""
        SELECT l.lemma,
               MAX(CASE WHEN pv.primitive = 'GOOD' THEN pv.value ELSE 0 END) as good_val,
               MAX(CASE WHEN pv.primitive = 'BAD' THEN pv.value ELSE 0 END) as bad_val
        FROM lexemes l
        LEFT JOIN primitive_values pv ON l.id = pv.lexeme_id
        GROUP BY l.id
        HAVING good_val != 0 OR bad_val != 0
    """)
    for lemma, good_val, bad_val in cursor.fetchall():
        issue = validator.validate_valence_with_good_bad(lemma, good_val, bad_val)
        if issue:
            issues["valence_good_bad"].append(issue)

    # Get words with BODY for concreteness validation
    cursor.execute("""
        SELECT l.lemma, pv.value
        FROM lexemes l
        JOIN primitive_values pv ON l.id = pv.lexeme_id
        WHERE pv.primitive = 'BODY' AND pv.value = 1
    """)
    for lemma, body_val in cursor.fetchall():
        issue = validator.validate_body_with_concreteness(lemma, body_val)
        if issue:
            issues["body_concreteness"].append(issue)

    # Modifier hierarchy validation (Group 4)
    issues["modifier_hierarchy"] = get_group4_modifier_hierarchy_validation(cursor)

    # Summary
    logger.info(f"  Arousal/INTENSITY mismatches: {len(issues['arousal_intensity'])}")
    logger.info(f"  Valence/GOOD-BAD mismatches: {len(issues['valence_good_bad'])}")
    logger.info(f"  BODY/concreteness mismatches: {len(issues['body_concreteness'])}")
    logger.info(f"  Modifier hierarchy issues: {len(issues['modifier_hierarchy'])}")

    return issues


# =============================================================================
# COMPREHENSIVE DATABASE AUDIT
# Runs all group identification queries and external validation
# =============================================================================


def run_database_audit(cursor: sqlite3.Cursor) -> Dict[str, List[Dict]]:
    """
    Run comprehensive database audit to identify all issue groups.

    This is the SQL AUDIT phase that finds potential issues before LLM validation.

    Returns dict with all issue groups:
      - group1_feel: FEEL=1 without experiencer
      - group2_verbs: Verbs missing DO/HAPPEN
      - group3_intensity: INTENSITY encoding issues
      - group4_modifiers: Modifier hierarchy mismatches
      - group5_say: SAY=1 without WORDS
      - group6_bipolar: Bipolar violations
      - group7_operators: Function words with excessive primitives
      - external_*: External data cross-validation issues
    """
    logger.info("=" * 60)
    logger.info("DATABASE AUDIT - SQL GROUP IDENTIFICATION")
    logger.info("=" * 60)

    all_issues = {}

    # Group 1: FEEL without experiencer
    logger.info("  Group 1: FEEL without experiencer...")
    all_issues["group1_feel"] = get_group1_feel_without_experiencer(cursor)
    logger.info(f"    Found: {len(all_issues['group1_feel'])} words")

    # Group 2: Verbs missing DO/HAPPEN
    logger.info("  Group 2: Verbs missing DO/HAPPEN...")
    all_issues["group2_verbs"] = get_group2_verbs_missing_do_happen(cursor)
    logger.info(f"    Found: {len(all_issues['group2_verbs'])} verbs")

    # Group 3: INTENSITY issues
    logger.info("  Group 3: INTENSITY encoding issues...")
    all_issues["group3_intensity"] = get_group3_intensity_issues(cursor)
    logger.info(f"    Found: {len(all_issues['group3_intensity'])} issues")

    # Group 4: Modifier hierarchy validation
    logger.info("  Group 4: Modifier hierarchy validation...")
    all_issues["group4_modifiers"] = get_group4_modifier_hierarchy_validation(cursor)
    logger.info(f"    Found: {len(all_issues['group4_modifiers'])} mismatches")

    # Group 5: SAY without WORDS
    logger.info("  Group 5: SAY without WORDS...")
    all_issues["group5_say"] = get_group5_say_without_words(cursor)
    logger.info(f"    Found: {len(all_issues['group5_say'])} words")

    # Group 6: Bipolar violations
    logger.info("  Group 6: Bipolar violations...")
    all_issues["group6_bipolar"] = get_group6_bipolar_violations(cursor)
    logger.info(f"    Found: {len(all_issues['group6_bipolar'])} violations")

    # Group 7: Function words with excessive primitives
    logger.info("  Group 7: OPERATOR excessive primitives...")
    all_issues["group7_operators"] = get_group7_function_words_excessive_primitives(cursor)
    logger.info(f"    Found: {len(all_issues['group7_operators'])} words")

    # External data cross-validation
    logger.info("  Running external data cross-validation...")
    external_issues = run_external_data_validation(cursor)
    for key, issues in external_issues.items():
        all_issues[f"external_{key}"] = issues

    # Summary
    total_issues = sum(len(v) for v in all_issues.values())
    logger.info("=" * 60)
    logger.info(f"DATABASE AUDIT COMPLETE: {total_issues} total issues identified")
    logger.info("=" * 60)

    return all_issues


# =============================================================================
# PROMPT TEMPLATES (from multi_model_audit.md)
# =============================================================================

# Template A: Quick Check (5 words per batch) - Phase 1
TEMPLATE_A_QUICK_CHECK = """Review these word-primitive assignments. For each word, identify any rule violations.

Rules:
1. Function words (the, of, and, to, a, in, is, that, for, with, as, on, at, by, from, or, an, be, are, was, were, been, being, have, has, had, not, but, if, which, so, what, when, into, than, its, any, no, do, how, up, out, just, about) should have 0-2 active primitives.
2. FEEL=1 requires SOMEONE/I/YOU=1 (experiencer)
3. SAY=1 requires WORDS=1 (speech)
4. Bipolar pairs (GOOD/BAD, TRUE/FALSE, BIG/SMALL, NEAR/FAR, ABOVE/BELOW, BEFORE/AFTER, INSIDE/OUTSIDE, MORE/LESS) cannot both be 1
5. BODY=1 requires physical object (not abstract concepts)
6. Verbs should have DO=1 (agentive) or HAPPEN=1 (non-agentive) or both
7. Pronouns (I, me, you, he, she, they, etc.) need SOMEONE=1
8. Emotion words (happy, sad, angry, afraid, etc.) need FEEL=1
9. Intensity modifiers use INTENSITY=1 with HIER_PLUS/HIER_MINUS (never INTENSITY=-1)

Words:
{words_formatted}

For each violation found, output:
WORD:RULE_NUMBER:ISSUE

If no violations, output: OK"""

# Template B: Semantic Validation (1 word deep check) - Phase 2
TEMPLATE_B_DEEP_CHECK = """Is this primitive assignment correct?

Word: {lemma}
POS: {pos}
Active primitives: {primitives}

Check:
1. Does FEEL=1 make sense? (requires subjective experience by a sentient being)
2. Does SAY=1 make sense? (requires speech/language/communication)
3. Does BODY=1 make sense? (requires physical/tangible object)
4. Are there contradictory primitives? (bipolar pairs both =1)
5. If verb, does it have DO=1 or HAPPEN=1?
6. If pronoun, does it have SOMEONE=1?
7. If emotion word, does it have FEEL=1?

Output ONE of:
CORRECT - assignment is accurate
WRONG:primitive:reason - specify which primitive is wrong
MISSING:primitive - specify which primitive should be added"""

# Template C: Comparative Check (2 words) - Phase 3
TEMPLATE_C_COMPARATIVE = """Compare these two word assignments for consistency:

Word A: {word_a} - {primitives_a}
Word B: {word_b} - {primitives_b}

These words are semantically similar. Do their primitives match appropriately?

Output:
CONSISTENT - both assignments make sense
INCONSISTENT:reason - explain the inconsistency"""

# Template for larger model review (qwen3:32b)
TEMPLATE_LARGE_MODEL_REVIEW = """You are reviewing semantic primitive assignments in a lexicon database.

## Semantic Primitives Reference
The 72 Wierzbickian semantic primitives:
- Substantives: I, YOU, SOMEONE, SOMETHING, PEOPLE, BODY
- Determiners: THIS, SAME, OTHER, ONE, TWO, QUANTITY
- Mental Predicates: THINK, KNOW, WANT, FEEL, SEE, HEAR, SAY, WORDS
- Evaluators: GOOD, BAD
- Descriptors: BIG, SMALL, INTENSITY
- Time: WHEN, NOW, BEFORE, AFTER, LONG_TIME, SHORT_TIME, MOMENT, THEN, START, END
- Space: WHERE, HERE, ABOVE, BELOW, FAR, NEAR, SIDE, INSIDE, OUTSIDE, TOWARD, AWAY, TOUCH
- Existence/Possession: EXIST, HAVE, ALIVE, DEAD
- Actions: DO, HAPPEN, MOVE, MAKE, CHANGE, CAUSE
- Logical: NOT, IF, BECAUSE, INFER, CERTAINTY, TRUE, FALSE
- Relations: KIND, LIKE, PART, WITH, WITHOUT
- Hierarchy: HIER_PLUS, HIER_MINUS

## Key Rules
1. FEEL=1 requires subjective experiencer (SOMEONE, I, or YOU)
2. SAY=1 requires communicative speech act (needs WORDS)
3. ALIVE=1 requires biological life
4. First person pronouns → I=1, SOMEONE=1
5. Second person pronouns → YOU=1, SOMEONE=1
6. Third person pronouns → SOMEONE=1

## Words to Review (small models disagreed on these)
{words_to_review}

For each word, output:
WORD: <word>
PRIMITIVE: <primitive in question>
CURRENT: <current value>
DECISION: KEEP | SET_0 | SET_1
REASON: <brief justification>
"""

# =============================================================================
# LLM EXECUTION FUNCTIONS
# =============================================================================


def run_ollama(model: str, prompt: str, timeout: int = 60) -> Optional[str]:
    """Execute a prompt with an Ollama model."""
    try:
        result = subprocess.run(["ollama", "run", model, prompt], capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning(f"  {model} timed out")
        return None
    except FileNotFoundError:
        logger.warning("  Ollama not found - skipping LLM audit")
        return None


def parse_quick_check_output(output: str, words: List[str]) -> Dict[str, List[str]]:
    """Parse Template A output into per-word issues."""
    issues = {w: [] for w in words}

    if not output or "OK" in output.upper():
        return issues

    for line in output.strip().split("\n"):
        line = line.strip()
        if ":" in line:
            parts = line.split(":")
            if len(parts) >= 2:
                word = parts[0].strip().lower()
                issue = ":".join(parts[1:]).strip()
                if word in issues:
                    issues[word].append(issue)
                else:
                    # Try fuzzy match
                    for w in words:
                        if w.lower() in word.lower() or word.lower() in w.lower():
                            issues[w].append(issue)
                            break

    return issues


def parse_deep_check_output(output: str) -> Dict[str, any]:
    """Parse Template B output into structured verdict."""
    output = output.strip().upper() if output else ""

    if output.startswith("CORRECT"):
        return {"verdict": "CORRECT", "issue": None, "primitive": None}
    elif output.startswith("WRONG"):
        parts = output.split(":")
        primitive = parts[1] if len(parts) > 1 else None
        reason = parts[2] if len(parts) > 2 else None
        return {"verdict": "WRONG", "primitive": primitive, "reason": reason}
    elif output.startswith("MISSING"):
        parts = output.split(":")
        primitive = parts[1] if len(parts) > 1 else None
        return {"verdict": "MISSING", "primitive": primitive}
    else:
        return {"verdict": "UNCLEAR", "raw": output[:100]}


def parse_comparative_output(output: str) -> Dict[str, any]:
    """Parse Template C output into consistency verdict."""
    output = output.strip().upper() if output else ""

    if output.startswith("CONSISTENT"):
        return {"verdict": "CONSISTENT", "reason": None}
    elif output.startswith("INCONSISTENT"):
        parts = output.split(":", 1)
        reason = parts[1].strip() if len(parts) > 1 else None
        return {"verdict": "INCONSISTENT", "reason": reason}
    else:
        return {"verdict": "UNCLEAR", "raw": output[:100]}


# =============================================================================
# PHASE 1: QUICK SCAN (All Words, Batches of 5)
# =============================================================================


def run_phase1_quick_scan(
    cursor: sqlite3.Cursor,
    models: List[str] = None,
    batch_size: int = 5,
    max_batches: int = None,
    sleep_sec: float = 1.0,
) -> Dict[str, Dict]:
    """
    Phase 1: Quick Scan - Process all words in batches using Template A.

    Returns: {word: {'flagged': bool, 'issues': [...], 'models': {...}}}
    """
    if models is None:
        models = DEFAULT_SMALL_MODELS

    logger.info("=" * 60)
    logger.info("PHASE 1: QUICK SCAN")
    logger.info("=" * 60)

    # Get all words ordered by frequency
    cursor.execute("""
        SELECT l.id, l.lemma, l.pos,
               GROUP_CONCAT(pv.primitive || '=' || pv.value)
        FROM lexemes l
        LEFT JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.value != 0
        GROUP BY l.id
        ORDER BY l.frequency_rank
    """)
    all_words = cursor.fetchall()

    results = {}
    batch_num = 0
    flagged_count = 0

    logger.info(f"  Processing {len(all_words)} words in batches of {batch_size}")

    for i in range(0, len(all_words), batch_size):
        if max_batches and batch_num >= max_batches:
            break

        batch = all_words[i : i + batch_size]
        batch_num += 1

        # Format batch for prompt
        words_formatted = "\n".join([f"{row[1]}: {row[3] or '(none)'}" for row in batch])
        word_list = [row[1] for row in batch]

        prompt = TEMPLATE_A_QUICK_CHECK.format(words_formatted=words_formatted)

        # Run through all models
        model_outputs = {}
        for model in models:
            output = run_ollama(model, prompt)
            if output is None:
                logger.warning("  Stopping - Ollama not available")
                return results
            model_outputs[model] = parse_quick_check_output(output, word_list)

        # Aggregate per-word
        for word in word_list:
            issues_by_model = {m: model_outputs[m].get(word, []) for m in models}

            # Count how many models flagged this word
            flagged_models = sum(1 for m in models if issues_by_model[m])

            results[word] = {
                "flagged": flagged_models >= 2,  # 2/3 agreement to flag
                "issues": issues_by_model,
                "agreement": flagged_models,
                "priority": "HIGH"
                if flagged_models == 3
                else "MEDIUM"
                if flagged_models == 2
                else "LOW"
                if flagged_models == 1
                else "NONE",
            }

            if flagged_models >= 2:
                flagged_count += 1

        # Progress logging
        if batch_num % 20 == 0:
            logger.info(f"  Batch {batch_num}: {flagged_count} words flagged so far")

        # Write batch to audit log
        _write_audit_log(batch_num, word_list, results)

        time.sleep(sleep_sec)

    logger.info(f"  Phase 1 complete: {batch_num} batches, {flagged_count} words flagged")

    return results


# =============================================================================
# PHASE 2: DEEP CHECK (Flagged Words Only)
# =============================================================================


def run_phase2_deep_check(
    cursor: sqlite3.Cursor, flagged_words: List[str], models: List[str] = None, sleep_sec: float = 0.5
) -> Dict[str, Dict]:
    """
    Phase 2: Deep Check - Process flagged words individually using Template B.

    Returns: {word: {'verdicts': {...}, 'priority': str, 'action': str}}
    """
    if models is None:
        models = DEFAULT_SMALL_MODELS

    logger.info("=" * 60)
    logger.info("PHASE 2: DEEP CHECK")
    logger.info("=" * 60)
    logger.info(f"  Processing {len(flagged_words)} flagged words")

    results = {}

    for i, word in enumerate(flagged_words):
        # Get word data
        cursor.execute(
            """
            SELECT l.id, l.lemma, l.pos,
                   GROUP_CONCAT(pv.primitive || '=' || pv.value)
            FROM lexemes l
            LEFT JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.value != 0
            WHERE l.lemma = ?
            GROUP BY l.id
        """,
            (word,),
        )
        row = cursor.fetchone()

        if not row:
            continue

        word_data = {"lemma": row[1], "pos": row[2] or "UNKNOWN", "primitives": row[3] or "(none)"}

        prompt = TEMPLATE_B_DEEP_CHECK.format(**word_data)

        # Run through all models
        verdicts = {}
        for model in models:
            output = run_ollama(model, prompt)
            if output:
                verdicts[model] = parse_deep_check_output(output)

        # Aggregate verdicts
        wrong_count = sum(1 for v in verdicts.values() if v["verdict"] == "WRONG")
        missing_count = sum(1 for v in verdicts.values() if v["verdict"] == "MISSING")
        issue_count = wrong_count + missing_count

        if issue_count == 3:
            priority = "HIGH"
            action = "FIX"
        elif issue_count >= 2:
            priority = "MEDIUM"
            action = "FIX"
        elif issue_count == 1:
            priority = "NEEDS_ANALYSIS"
            action = "REVIEW_LARGE_MODEL"
        else:
            priority = "NONE"
            action = "SKIP"

        results[word] = {"verdicts": verdicts, "priority": priority, "action": action, "word_data": word_data}

        if (i + 1) % 10 == 0:
            logger.info(f"  Processed {i + 1}/{len(flagged_words)}")

        time.sleep(sleep_sec)

    # Summary
    high = sum(1 for r in results.values() if r["priority"] == "HIGH")
    medium = sum(1 for r in results.values() if r["priority"] == "MEDIUM")
    needs_analysis = sum(1 for r in results.values() if r["priority"] == "NEEDS_ANALYSIS")

    logger.info(f"  Phase 2 complete: HIGH={high}, MEDIUM={medium}, NEEDS_ANALYSIS={needs_analysis}")

    return results


# =============================================================================
# PHASE 3: CROSS-VALIDATION (Similar Word Pairs)
# =============================================================================


def run_phase3_cross_validation(
    cursor: sqlite3.Cursor, sample_size: int = 50, models: List[str] = None, sleep_sec: float = 0.5
) -> Dict[str, Dict]:
    """
    Phase 3: Cross-Validation - Compare semantically similar word pairs using Template C.

    Returns: {pair_key: {'verdict': str, 'reason': str}}
    """
    if models is None:
        models = DEFAULT_SMALL_MODELS

    logger.info("=" * 60)
    logger.info("PHASE 3: CROSS-VALIDATION")
    logger.info("=" * 60)

    # Find similar word pairs (same POS, similar frequency)
    cursor.execute(
        """
        SELECT a.lemma, a.pos,
               GROUP_CONCAT(pva.primitive || '=' || pva.value) as prims_a,
               b.lemma, b.pos,
               GROUP_CONCAT(pvb.primitive || '=' || pvb.value) as prims_b
        FROM lexemes a
        JOIN lexemes b ON a.pos = b.pos
            AND a.id < b.id
            AND ABS(a.frequency_rank - b.frequency_rank) < 100
        LEFT JOIN primitive_values pva ON a.id = pva.lexeme_id AND pva.value != 0
        LEFT JOIN primitive_values pvb ON b.id = pvb.lexeme_id AND pvb.value != 0
        WHERE a.component_type = 'ATOMIC' AND b.component_type = 'ATOMIC'
        GROUP BY a.id, b.id
        ORDER BY RANDOM()
        LIMIT ?
    """,
        (sample_size,),
    )
    pairs = cursor.fetchall()

    logger.info(f"  Checking {len(pairs)} word pairs")

    results = {}
    inconsistent_count = 0

    for row in pairs:
        word_a, pos_a, prims_a, word_b, pos_b, prims_b = row

        prompt = TEMPLATE_C_COMPARATIVE.format(
            word_a=word_a, primitives_a=prims_a or "(none)", word_b=word_b, primitives_b=prims_b or "(none)"
        )

        # Run through all models
        verdicts = {}
        for model in models:
            output = run_ollama(model, prompt)
            if output:
                verdicts[model] = parse_comparative_output(output)

        # Check for inconsistency consensus
        inconsistent_votes = sum(1 for v in verdicts.values() if v["verdict"] == "INCONSISTENT")

        pair_key = f"{word_a}|{word_b}"
        results[pair_key] = {
            "word_a": word_a,
            "word_b": word_b,
            "verdicts": verdicts,
            "inconsistent": inconsistent_votes >= 2,
        }

        if inconsistent_votes >= 2:
            inconsistent_count += 1

        time.sleep(sleep_sec)

    logger.info(f"  Phase 3 complete: {inconsistent_count} inconsistent pairs found")

    return results


# =============================================================================
# LARGE MODEL REVIEW (for disputed cases)
# =============================================================================


def run_large_model_review(disputed_words: List[Dict], model: str = None) -> Dict[str, Dict]:
    """
    Run larger model (qwen3:32b) review on cases where small models disagreed.

    Returns: {word: {'decision': str, 'primitive': str, 'reason': str}}
    """
    if model is None:
        model = DEFAULT_LARGE_MODEL

    logger.info("=" * 60)
    logger.info("LARGE MODEL REVIEW")
    logger.info("=" * 60)
    logger.info(f"  Using {model} for {len(disputed_words)} disputed words")

    if not disputed_words:
        logger.info("  No disputed words to review")
        return {}

    # Format words for review
    words_formatted = "\n".join(
        [
            f"- {w['lemma']} ({w['pos']}): {w['primitives']} -- Issue: {w.get('issue', 'unclear')}"
            for w in disputed_words
        ]
    )

    prompt = TEMPLATE_LARGE_MODEL_REVIEW.format(words_to_review=words_formatted)

    output = run_ollama(model, prompt, timeout=120)

    if not output:
        logger.warning("  Large model review failed")
        return {}

    # Parse output
    results = {}
    current_word = None
    current_result = {}

    for line in output.strip().split("\n"):
        line = line.strip()
        if line.startswith("WORD:"):
            if current_word:
                results[current_word] = current_result
            current_word = line.split(":", 1)[1].strip().lower()
            current_result = {}
        elif line.startswith("PRIMITIVE:"):
            current_result["primitive"] = line.split(":", 1)[1].strip()
        elif line.startswith("CURRENT:"):
            current_result["current"] = line.split(":", 1)[1].strip()
        elif line.startswith("DECISION:"):
            current_result["decision"] = line.split(":", 1)[1].strip()
        elif line.startswith("REASON:"):
            current_result["reason"] = line.split(":", 1)[1].strip()

    if current_word:
        results[current_word] = current_result

    logger.info(f"  Large model reviewed {len(results)} words")

    return results


# =============================================================================
# CONTINUOUS AUDIT LOOP
# =============================================================================


def run_continuous_audit(
    db_path: str, batch_size: int = 5, sleep_sec: float = 1.0, max_batches: int = None, summary_interval: int = 100
):
    """
    Continuous background audit loop.

    Implements the continuous improvement loop from multi_model_audit.md:
    1. Select next batch of words (by frequency rank)
    2. Run through all 3 models
    3. Aggregate results
    4. Write findings to audit log
    5. Sleep 1 second between batches
    6. After every 100 batches, write summary report
    7. Restart from beginning when all words processed
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    logger.info("=" * 60)
    logger.info("CONTINUOUS AUDIT LOOP")
    logger.info("=" * 60)

    # Get total word count
    cursor.execute("SELECT COUNT(*) FROM lexemes")
    total_words = cursor.fetchone()[0]
    logger.info(f"  Total words: {total_words}")

    cycle = 0
    while True:
        cycle += 1
        logger.info(f"  Starting cycle {cycle}")

        # Run Phase 1
        phase1_results = run_phase1_quick_scan(
            cursor, batch_size=batch_size, max_batches=max_batches, sleep_sec=sleep_sec
        )

        if not phase1_results:
            logger.warning("  Audit stopped - Ollama not available")
            break

        # Get flagged words for Phase 2
        flagged = [w for w, r in phase1_results.items() if r["flagged"]]

        if flagged:
            # Run Phase 2 on flagged words
            phase2_results = run_phase2_deep_check(cursor, flagged, sleep_sec=sleep_sec)

            # Get disputed words for large model
            disputed = [
                {"lemma": w, **r["word_data"], "issue": str(r["verdicts"])}
                for w, r in phase2_results.items()
                if r["priority"] == "NEEDS_ANALYSIS"
            ]

            if disputed:
                large_model_results = run_large_model_review(disputed)

        # Write cycle summary
        _write_cycle_summary(cycle, phase1_results, phase2_results if flagged else {})

        if max_batches:
            logger.info(f"  Cycle {cycle} complete (limited run)")
            break

        logger.info(f"  Cycle {cycle} complete, restarting...")

    conn.close()


# =============================================================================
# OUTPUT AND LOGGING
# =============================================================================


def _write_audit_log(batch_num: int, words: List[str], results: Dict):
    """Write batch results to audit log."""
    try:
        with open("data/audit_log.jsonl", "a") as f:
            f.write(
                json.dumps(
                    {
                        "batch": batch_num,
                        "timestamp": datetime.now().isoformat(),
                        "words": words,
                        "flagged": [w for w in words if results.get(w, {}).get("flagged", False)],
                    }
                )
                + "\n"
            )
    except Exception as e:
        logger.warning(f"  Could not write to audit log: {e}")


def _write_cycle_summary(cycle: int, phase1: Dict, phase2: Dict):
    """Write cycle summary report."""
    summary = {
        "cycle": cycle,
        "timestamp": datetime.now().isoformat(),
        "words_processed": len(phase1),
        "phase1_flagged": sum(1 for r in phase1.values() if r.get("flagged")),
        "phase2_high": sum(1 for r in phase2.values() if r.get("priority") == "HIGH"),
        "phase2_medium": sum(1 for r in phase2.values() if r.get("priority") == "MEDIUM"),
        "phase2_needs_analysis": sum(1 for r in phase2.values() if r.get("priority") == "NEEDS_ANALYSIS"),
    }

    try:
        with open("data/audit_summary.jsonl", "a") as f:
            f.write(json.dumps(summary) + "\n")
        logger.info(f"  Summary: {summary}")
    except Exception as e:
        logger.warning(f"  Could not write summary: {e}")


def generate_per_word_result(word: str, pos: str, verdicts: Dict) -> Dict:
    """
    Generate per-word result in the specified JSON format.

    Format:
    {
      "word": "example",
      "pos": "NOUN",
      "models": {
        "smollm": {"verdict": "WRONG", "issue": "FEEL:abstract_noun", "confidence": 0.8},
        ...
      },
      "agreement": 2,
      "priority": "MEDIUM",
      "action": "review_feel_primitive"
    }
    """
    models_result = {}
    for model, verdict in verdicts.items():
        if isinstance(verdict, dict):
            models_result[model] = {
                "verdict": verdict.get("verdict", "UNCLEAR"),
                "issue": f"{verdict.get('primitive', '')}:{verdict.get('reason', '')}".strip(":"),
                "confidence": 0.8 if verdict.get("verdict") in ("CORRECT", "WRONG") else 0.5,
            }

    # Count agreement
    wrong_count = sum(1 for v in verdicts.values() if isinstance(v, dict) and v.get("verdict") in ("WRONG", "MISSING"))

    if wrong_count == 3:
        priority = "HIGH"
        action = "immediate_fix"
    elif wrong_count >= 2:
        priority = "MEDIUM"
        action = "review_and_fix"
    elif wrong_count == 1:
        priority = "NEEDS_ANALYSIS"
        action = "large_model_review"
    else:
        priority = "NONE"
        action = "no_action"

    return {
        "word": word,
        "pos": pos,
        "models": models_result,
        "agreement": wrong_count,
        "priority": priority,
        "action": action,
    }


# =============================================================================
# SQL FIX GENERATION
# =============================================================================


def generate_fixes_from_llm_audit(
    phase2_results: Dict, large_model_results: Dict = None, database_audit: Dict = None
) -> str:
    """
    Generate SQL fix script from LLM audit and database audit results.

    Combines:
    - Phase 2 HIGH/MEDIUM priority LLM findings
    - Large model decisions for disputed cases
    - Database audit group findings (bipolar, INTENSITY, modifiers, etc.)
    """
    fixes = []

    # Group by issue type
    feel_false_positives = []
    say_false_positives = []
    body_false_positives = []
    missing_someone = []
    missing_do_happen = []
    missing_feel = []
    intensity_fixes = []
    modifier_fixes = []
    bipolar_fixes = []

    # Process phase 2 LLM results
    for word, result in phase2_results.items():
        if result.get("priority") not in ("HIGH", "MEDIUM"):
            continue

        for model, verdict in result.get("verdicts", {}).items():
            if not isinstance(verdict, dict):
                continue

            v = verdict.get("verdict", "")
            prim = verdict.get("primitive", "").upper()

            if v == "WRONG":
                if prim == "FEEL":
                    feel_false_positives.append(word)
                elif prim == "SAY":
                    say_false_positives.append(word)
                elif prim == "BODY":
                    body_false_positives.append(word)
            elif v == "MISSING":
                if prim == "SOMEONE":
                    missing_someone.append(word)
                elif prim in ("DO", "HAPPEN"):
                    missing_do_happen.append(word)
                elif prim == "FEEL":
                    missing_feel.append(word)

    # Process large model results (overrides small model consensus)
    if large_model_results:
        for word, result in large_model_results.items():
            decision = result.get("decision", "").upper()
            prim = result.get("primitive", "").upper()

            if decision == "SET_0":
                if prim == "FEEL" and word not in feel_false_positives:
                    feel_false_positives.append(word)
                elif prim == "SAY" and word not in say_false_positives:
                    say_false_positives.append(word)
            elif decision == "SET_1":
                if prim == "SOMEONE" and word not in missing_someone:
                    missing_someone.append(word)

    # Process database audit results
    if database_audit:
        # Group 3: INTENSITY issues (INTENSITY=-1 should be +1 with HIER_MINUS)
        for issue in database_audit.get("group3_intensity", []):
            if issue.get("issue") == "INTENSITY_NEGATIVE":
                intensity_fixes.append(issue["lemma"])

        # Group 4: Modifier hierarchy validation
        for issue in database_audit.get("group4_modifiers", []):
            modifier_fixes.append(
                {
                    "word": issue["lemma"],
                    "expected": issue.get("expected", {}),
                    "ground_truth_level": issue.get("ground_truth_level", 0),
                }
            )

        # Group 6: Bipolar violations
        for issue in database_audit.get("group6_bipolar", []):
            bipolar_fixes.append({"word": issue["lemma"], "issue": issue["issue"]})

        # External: BODY/concreteness mismatches
        for issue in database_audit.get("external_body_concreteness", []):
            if issue["word"] not in body_false_positives:
                body_false_positives.append(issue["word"])

    # Generate SQL
    fixes.append("-- LLM Audit Generated Fixes")
    fixes.append(f"-- Generated: {datetime.now().isoformat()}")
    fixes.append("")

    if feel_false_positives:
        words = "', '".join(set(feel_false_positives))
        fixes.append(f"""-- FEEL false positives ({len(set(feel_false_positives))} words)
UPDATE primitive_values SET value = 0, confidence = 0.85, source = 'fix:llm_audit'
WHERE primitive = 'FEEL'
AND lexeme_id IN (SELECT id FROM lexemes WHERE lemma IN ('{words}'));
""")

    if say_false_positives:
        words = "', '".join(set(say_false_positives))
        fixes.append(f"""-- SAY false positives ({len(set(say_false_positives))} words)
UPDATE primitive_values SET value = 0, confidence = 0.85, source = 'fix:llm_audit'
WHERE primitive = 'SAY'
AND lexeme_id IN (SELECT id FROM lexemes WHERE lemma IN ('{words}'));
""")

    if body_false_positives:
        words = "', '".join(set(body_false_positives))
        fixes.append(f"""-- BODY false positives ({len(set(body_false_positives))} words)
UPDATE primitive_values SET value = 0, confidence = 0.85, source = 'fix:llm_audit'
WHERE primitive = 'BODY'
AND lexeme_id IN (SELECT id FROM lexemes WHERE lemma IN ('{words}'));
""")

    if missing_someone:
        words = "', '".join(set(missing_someone))
        fixes.append(f"""-- Missing SOMEONE ({len(set(missing_someone))} words)
INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SOMEONE', 1, 0.85, 'fix:llm_audit'
FROM lexemes WHERE lemma IN ('{words}');
""")

    if missing_feel:
        words = "', '".join(set(missing_feel))
        fixes.append(f"""-- Missing FEEL ({len(set(missing_feel))} words)
INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'FEEL', 1, 0.85, 'fix:llm_audit'
FROM lexemes WHERE lemma IN ('{words}');
""")

    # Database audit fixes: INTENSITY=-1 (should be INTENSITY=1 with HIER_MINUS)
    if intensity_fixes:
        words = "', '".join(set(intensity_fixes))
        fixes.append(f"""-- INTENSITY=-1 fixes (should be +1 with HIER_MINUS) ({len(set(intensity_fixes))} words)
-- Step 1: Set INTENSITY to +1
UPDATE primitive_values SET value = 1, confidence = 0.85, source = 'fix:db_audit_intensity'
WHERE primitive = 'INTENSITY' AND value = -1
AND lexeme_id IN (SELECT id FROM lexemes WHERE lemma IN ('{words}'));

-- Step 2: Add HIER_MINUS=1 if not present
INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'HIER_MINUS', 1, 0.85, 'fix:db_audit_intensity'
FROM lexemes WHERE lemma IN ('{words}');
""")

    # Database audit fixes: Modifier hierarchy (from ground truth)
    if modifier_fixes:
        fixes.append(f"-- Modifier hierarchy fixes from ground truth ({len(modifier_fixes)} words)")
        for fix in modifier_fixes:
            word = fix["word"]
            expected = fix.get("expected", {})
            level = fix.get("ground_truth_level", 0)

            for prim, val in expected.items():
                fixes.append(f"""
INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, '{prim}', {val}, 0.90, 'fix:ground_truth'
FROM lexemes WHERE lemma = '{word}';""")

    # Database audit fixes: Bipolar violations
    if bipolar_fixes:
        fixes.append(f"\n-- Bipolar violations ({len(bipolar_fixes)} words)")
        fixes.append("-- NOTE: Manual review required - cannot auto-fix without context")
        for fix in bipolar_fixes:
            fixes.append(f"-- {fix['word']}: {fix['issue']}")

    return "\n".join(fixes)


# =============================================================================
# SIMPLIFIED ENTRY POINTS
# =============================================================================


def run_full_llm_audit(
    cursor: sqlite3.Cursor,
    models: List[str] = None,
    large_model: str = None,
    max_phase1_batches: int = None,
    skip_database_audit: bool = False,
) -> Dict:
    """
    Run complete LLM audit pipeline WITH database cross-validation.

    Complete Pipeline:
      1. DATABASE AUDIT - SQL queries identify issue groups
      2. EXTERNAL VALIDATION - Cross-validate with NRC-VAD, ground truth, etc.
      3. LLM PHASE 1 - Quick scan (batches of 5, Template A)
      4. LLM PHASE 2 - Deep check (flagged words, Template B)
      5. LLM PHASE 3 - Cross-validation (similar pairs, Template C)
      6. LARGE MODEL REVIEW - Disputed cases (qwen3:32b)
      7. FIX GENERATION - SQL script from confirmed issues

    Returns complete audit results with all phases.
    """
    logger.info("=" * 60)
    logger.info("FULL LLM AUDIT PIPELINE WITH DATABASE CROSS-VALIDATION")
    logger.info("=" * 60)

    results = {
        "database_audit": {},
        "phase1": {},
        "phase2": {},
        "phase3": {},
        "large_model": {},
        "fixes_sql": "",
        "summary": {},
    }

    # Step 1: Database Audit (SQL group identification + external validation)
    if not skip_database_audit:
        logger.info("\n>>> STEP 1: DATABASE AUDIT")
        results["database_audit"] = run_database_audit(cursor)

    # Step 2: LLM Phase 1 - Quick Scan
    logger.info("\n>>> STEP 2: LLM PHASE 1 - QUICK SCAN")
    phase1 = run_phase1_quick_scan(cursor, models, max_batches=max_phase1_batches)
    if not phase1:
        results["error"] = "Ollama not available"
        return results

    results["phase1"] = phase1

    # Combine flagged words from BOTH database audit AND phase 1 LLM
    phase1_flagged = set(w for w, r in phase1.items() if r["flagged"])

    # Extract words from database-identified issues for LLM validation
    db_flagged = set()
    for group_name, issues in results["database_audit"].items():
        for issue in issues:
            word = issue.get("word") or issue.get("lemma")
            if word:
                db_flagged.add(word)

    # Combined flagged list
    all_flagged = list(db_flagged | phase1_flagged)
    logger.info(f"\n  Combined flagged words: {len(all_flagged)}")
    logger.info(f"    - From database audit: {len(db_flagged)}")
    logger.info(f"    - From LLM phase 1: {len(phase1_flagged)}")
    logger.info(f"    - Overlap: {len(db_flagged & phase1_flagged)}")

    # Step 3: LLM Phase 2 - Deep Check on flagged words
    logger.info("\n>>> STEP 3: LLM PHASE 2 - DEEP CHECK")
    if all_flagged:
        # Limit to 200 for practical processing time
        results["phase2"] = run_phase2_deep_check(cursor, all_flagged[:200], models)

    # Step 4: LLM Phase 3 - Cross-validation (sample)
    logger.info("\n>>> STEP 4: LLM PHASE 3 - CROSS-VALIDATION")
    results["phase3"] = run_phase3_cross_validation(cursor, sample_size=50, models=models)

    # Step 5: Large Model Review for disputed cases
    logger.info("\n>>> STEP 5: LARGE MODEL REVIEW")
    disputed = []
    for w, r in results["phase2"].items():
        if r.get("priority") == "NEEDS_ANALYSIS":
            disputed.append({"lemma": w, **r.get("word_data", {}), "issue": str(r.get("verdicts", {}))})

    if disputed:
        results["large_model"] = run_large_model_review(disputed, large_model)
    else:
        logger.info("  No disputed cases for large model review")

    # Step 6: Generate fixes from confirmed issues
    logger.info("\n>>> STEP 6: GENERATING FIXES")
    results["fixes_sql"] = generate_fixes_from_llm_audit(
        results["phase2"], results["large_model"], results["database_audit"]
    )

    # Build summary
    results["summary"] = {
        "database_issues_total": sum(len(v) for v in results["database_audit"].values()),
        "phase1_scanned": len(results["phase1"]),
        "phase1_flagged": len(phase1_flagged),
        "database_flagged": len(db_flagged),
        "combined_flagged": len(all_flagged),
        "phase2_processed": len(results["phase2"]),
        "phase2_high": sum(1 for r in results["phase2"].values() if r.get("priority") == "HIGH"),
        "phase2_medium": sum(1 for r in results["phase2"].values() if r.get("priority") == "MEDIUM"),
        "phase3_inconsistent": sum(1 for r in results["phase3"].values() if r.get("inconsistent")),
        "large_model_reviewed": len(results["large_model"]),
    }

    logger.info("\n" + "=" * 60)
    logger.info("FULL LLM AUDIT COMPLETE")
    logger.info(f"  Summary: {results['summary']}")
    logger.info("=" * 60)

    return results


# =============================================================================
# VERIFICATION
# =============================================================================


def run_verification(cursor: sqlite3.Cursor) -> None:
    """Run verification queries."""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    # 1. Component type distribution
    cursor.execute("""
        SELECT component_type, COUNT(*)
        FROM lexemes
        GROUP BY component_type
    """)
    print("\n1. Component Type Distribution:")
    for comp_type, count in cursor.fetchall():
        print(f"   {comp_type or 'NULL'}: {count}")

    # 2. Operator type distribution
    cursor.execute("""
        SELECT operator_type, COUNT(*)
        FROM lexemes
        WHERE operator_type IS NOT NULL
        GROUP BY operator_type
    """)
    print("\n2. Operator Type Distribution:")
    for op_type, count in cursor.fetchall():
        print(f"   {op_type}: {count}")

    # 3. Check for OPERATORs without operator_type
    cursor.execute("""
        SELECT COUNT(*) FROM lexemes
        WHERE component_type = 'OPERATOR' AND operator_type IS NULL
    """)
    count = cursor.fetchone()[0]
    print(f"\n3. OPERATORs missing operator_type: {count}")

    # 4. Function words with active primitives
    cursor.execute("""
        SELECT l.lemma, COUNT(*) as active
        FROM lexemes l
        JOIN primitive_values pv ON l.id = pv.lexeme_id
        WHERE l.lemma IN ('the', 'of', 'and', 'to', 'a', 'is')
        AND pv.value != 0
        GROUP BY l.lemma
    """)
    results = cursor.fetchall()
    print(f"\n4. Function words with active primitives: {len(results)}")
    if results:
        for lemma, count in results:
            print(f"   WARNING: {lemma} has {count} active primitives")
    else:
        print("   OK - All checked function words have 0 active primitives")

    # 5. SYN_* dimension counts
    cursor.execute("""
        SELECT primitive, COUNT(*)
        FROM primitive_values
        WHERE primitive LIKE 'SYN_%'
        GROUP BY primitive
    """)
    print("\n5. SYN_* Dimension Distribution:")
    for prim, count in cursor.fetchall():
        print(f"   {prim}: {count}")

    # 6. gram_features distribution
    cursor.execute("""
        SELECT gram_features, COUNT(*)
        FROM lexemes
        WHERE gram_features IS NOT NULL
        GROUP BY gram_features
        LIMIT 10
    """)
    print("\n6. gram_features Distribution (top 10):")
    for gf, count in cursor.fetchall():
        print(f"   {gf}: {count}")

    # 7. Fix source counts
    cursor.execute("""
        SELECT source, COUNT(*)
        FROM primitive_values
        WHERE source LIKE 'fix:%'
        GROUP BY source
        ORDER BY COUNT(*) DESC
    """)
    print("\n7. Fixes by Source:")
    for source, count in cursor.fetchall():
        print(f"   {source}: {count}")

    # 8. Modifier hierarchy check
    cursor.execute("""
        SELECT l.lemma,
               i.value as INTENSITY, hp.value as HIER_PLUS, hm.value as HIER_MINUS
        FROM lexemes l
        LEFT JOIN primitive_values i ON l.id = i.lexeme_id AND i.primitive = 'INTENSITY'
        LEFT JOIN primitive_values hp ON l.id = hp.lexeme_id AND hp.primitive = 'HIER_PLUS'
        LEFT JOIN primitive_values hm ON l.id = hm.lexeme_id AND hm.primitive = 'HIER_MINUS'
        WHERE l.lemma IN ('very', 'extremely', 'barely', 'slightly')
    """)
    print("\n8. Modifier Hierarchy Encoding:")
    for row in cursor.fetchall():
        print(f"   {row[0]}: INTENSITY={row[1]}, HIER_PLUS={row[2]}, HIER_MINUS={row[3]}")


# =============================================================================
# MAIN
# =============================================================================


def run_full_pipeline(
    db_path: str, stages: Optional[List[int]] = None, dry_run: bool = False, verify_only: bool = False
) -> None:
    """Run the full audit pipeline."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if verify_only:
        run_verification(cursor)
        conn.close()
        return

    all_stages = [0, 1, 2, 6, 7, 8]  # 2 includes 2-5
    stages_to_run = stages if stages else all_stages

    print("\n" + "=" * 60)
    print("GSE LEXICON AUDIT PIPELINE (v4)")
    print("=" * 60)
    print(f"Database: {db_path}")
    print(f"Stages to run: {stages_to_run}")
    print(f"Dry run: {dry_run}")
    print("=" * 60)

    all_stats = {}

    if 0 in stages_to_run:
        all_stats["stage_0"] = run_stage_0(cursor)

    if 1 in stages_to_run:
        all_stats["stage_1"] = run_stage_1(cursor)

    if 2 in stages_to_run:
        all_stats["stage_2_5"] = run_stage_2_5(cursor)

    if 6 in stages_to_run:
        all_stats["stage_6"] = run_stage_6(cursor)

    if 7 in stages_to_run:
        all_stats["stage_7"] = run_stage_7(cursor)

    if 8 in stages_to_run:
        all_stats["stage_8"] = run_stage_8(cursor)

    if dry_run:
        print("\nDRY RUN - Rolling back all changes...")
        conn.rollback()
    else:
        conn.commit()
        print("\nChanges committed to database")

    run_verification(cursor)

    # Final summary
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)

    cursor.execute("SELECT COUNT(DISTINCT lexeme_id) FROM primitive_values WHERE source LIKE 'fix:%'")
    fixed_words = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM primitive_values WHERE source LIKE 'fix:%'")
    fixed_values = cursor.fetchone()[0]

    print(f"Total words affected: {fixed_words}")
    print(f"Total primitive values modified: {fixed_values}")
    print("=" * 60)

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="GSE Lexicon Audit Pipeline (v4)", epilog="See prompts/AUDIT_PIPELINE.md for documentation"
    )
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument(
        "--stage", type=int, action="append", help="Run specific stage(s). Can be repeated. Default: run all"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without committing")
    parser.add_argument("--verify", action="store_true", help="Only run verification queries")
    parser.add_argument("--use-llm", action="store_true", help="Run LLM validation after SQL audit stages")
    parser.add_argument("--continuous", action="store_true", help="Run continuous background LLM audit")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size for continuous audit (default: 5)")
    parser.add_argument(
        "--max-batches", type=int, default=None, help="Maximum batches for continuous audit (default: unlimited)"
    )
    parser.add_argument("--generate-fixes", action="store_true", help="Generate SQL fix script from LLM audit results")
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help="Small LLM models to use (default: smollm:1.7b granite3-moe:1b gemma2:2b)",
    )
    parser.add_argument("--large-model", default=None, help="Large model for disputed cases (default: qwen3:32b)")

    args = parser.parse_args()

    # Continuous audit mode
    if args.continuous:
        run_continuous_audit(db_path=args.db, batch_size=args.batch_size, max_batches=args.max_batches)
        return

    # Standard pipeline
    run_full_pipeline(db_path=args.db, stages=args.stage, dry_run=args.dry_run, verify_only=args.verify)

    # Optional LLM validation after standard pipeline
    if args.use_llm and not args.verify:
        conn = sqlite3.connect(args.db)
        cursor = conn.cursor()

        # Run the full three-phase LLM audit
        audit_results = run_full_llm_audit(
            cursor, models=args.models, large_model=args.large_model, max_phase1_batches=args.max_batches
        )

        if "error" in audit_results:
            print(f"\nLLM audit error: {audit_results['error']}")
        else:
            # Print summary
            summary = audit_results.get("summary", {})
            print("\n" + "=" * 60)
            print("LLM AUDIT SUMMARY")
            print("=" * 60)
            print(f"  Total words scanned: {summary.get('total_scanned', 0)}")
            print(f"  Phase 1 flagged: {summary.get('phase1_flagged', 0)}")
            print(f"  Phase 2 HIGH priority: {summary.get('phase2_high', 0)}")
            print(f"  Phase 2 MEDIUM priority: {summary.get('phase2_medium', 0)}")
            print(f"  Phase 3 inconsistent pairs: {summary.get('phase3_inconsistent', 0)}")
            print(f"  Large model reviewed: {summary.get('large_model_reviewed', 0)}")

            if args.generate_fixes:
                fixes_sql = audit_results.get("fixes_sql", "")
                if fixes_sql:
                    print("\n" + "=" * 60)
                    print("GENERATED SQL FIXES FROM LLM AUDIT")
                    print("=" * 60)
                    print(fixes_sql)

                    # Write to file
                    with open("data/llm_audit_fixes.sql", "w") as f:
                        f.write(fixes_sql)
                    print("\nFixes written to: data/llm_audit_fixes.sql")

        conn.close()


if __name__ == "__main__":
    main()
