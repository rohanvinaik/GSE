#!/usr/bin/env python3
"""
Multi-Source NLP Database Audit Script

Compares primitive assignments from Wiktionary against other NLP databases
(VerbNet, FrameNet, WordNet, USAS, PPDB) to:
1. Flag potential conflicts without changing anything
2. Validate decomposition consistency
3. Organize lexicon by word frequency

Usage:
    python scripts/audit_lexicon_sources.py --audit      # Run conflict audit
    python scripts/audit_lexicon_sources.py --frequency  # Add frequency data
    python scripts/audit_lexicon_sources.py --report     # Generate full report
"""

import argparse
import csv
import json
import logging
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# Setup paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
EXTERNAL_DIR = DATA_DIR / "external"
WIKT_DB = EXTERNAL_DIR / "wiktionary" / "wiktionary_primitives.db"
LEXICON_DB = DATA_DIR / "lexicon.db"
AUDIT_OUTPUT = DATA_DIR / "audit_results"

# External data paths
CONCEPTNET_DB = EXTERNAL_DIR / "conceptnet-en.sqlite"
LANCASTER_CSV = EXTERNAL_DIR / "lancaster_sensorimotor.csv"
NRC_EMOTION_TXT = EXTERNAL_DIR / "nrc_emotion.txt"
NRC_VAD_TXT = EXTERNAL_DIR / "nrc_vad.txt"
CONCRETENESS_CSV = EXTERNAL_DIR / "concreteness.csv"
USAS_TSV = EXTERNAL_DIR / "usas" / "semantic_lexicon_en.tsv"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# SOURCE-SPECIFIC PRIMITIVE MAPPINGS
# =============================================================================

# VerbNet class → primitive mappings
VERBNET_CLASS_PRIMITIVES = {
    # Motion verbs
    "run-51.3.2": {"MOVE": 1, "BODY": 1},
    "walk-51.3.1": {"MOVE": 1, "BODY": 1},
    "roll-51.3.1": {"MOVE": 1},
    "slide-11.2": {"MOVE": 1},
    "fly-51.4.2": {"MOVE": 1, "ABOVE": 1},
    "swim-51.3.2": {"MOVE": 1, "BODY": 1},

    # Communication verbs
    "say-37.7": {"SAY": 1, "WORDS": 1},
    "talk-37.5": {"SAY": 1, "WORDS": 1},
    "tell-37.2": {"SAY": 1, "WORDS": 1, "KNOW": 1},
    "ask-37.1.2": {"SAY": 1, "WANT": 1},

    # Cognition verbs
    "think-29.4": {"THINK": 1},
    "know-29.5": {"KNOW": 1},
    "believe-29.2": {"THINK": 1, "MAYBE": 1},
    "understand-29.5": {"KNOW": 1, "THINK": 1},

    # Perception verbs
    "see-30.1": {"SEE": 1},
    "hear-30.1": {"HEAR": 1},
    "feel-30.1": {"FEEL": 1},

    # Psych verbs (experiencer subject)
    "admire-31.2": {"FEEL": 1, "GOOD": 1},
    "fear-31.2": {"FEEL": 1, "GOOD": -1},
    "love-31.2": {"FEEL": 1, "WANT": 1, "GOOD": 1},
    "hate-31.2": {"FEEL": 1, "GOOD": -1},

    # Change of state
    "break-45.1": {"CAUSE": 1, "END": 1},
    "cut-21.1": {"DO": 1, "CAUSE": 1},
    "open-45.4": {"CAUSE": 1, "START": 1},
    "close-45.4": {"CAUSE": 1, "END": 1},

    # Creation/destruction
    "create-26.4": {"DO": 1, "CAUSE": 1, "START": 1},
    "build-26.1": {"DO": 1, "CAUSE": 1},
    "destroy-44": {"DO": 1, "CAUSE": 1, "END": 1},

    # Possession
    "give-13.1": {"HAVE": -1, "CAUSE": 1},
    "get-13.5.1": {"HAVE": 1, "START": 1},
    "have-100": {"HAVE": 1},
    "own-100.1": {"HAVE": 1},
}

# FrameNet frame → primitive mappings
FRAMENET_FRAME_PRIMITIVES = {
    # Motion frames
    "Motion": {"MOVE": 1},
    "Self_motion": {"MOVE": 1, "BODY": 1},
    "Cause_motion": {"MOVE": 1, "CAUSE": 1},
    "Arriving": {"MOVE": 1, "END": 1},
    "Departing": {"MOVE": 1, "START": 1},

    # Communication frames
    "Statement": {"SAY": 1, "WORDS": 1},
    "Communication": {"SAY": 1},
    "Request": {"SAY": 1, "WANT": 1},
    "Questioning": {"SAY": 1, "WANT": 1, "KNOW": 1},

    # Cognition frames
    "Awareness": {"KNOW": 1},
    "Perception_active": {"SEE": 1, "DO": 1},
    "Perception_experience": {"FEEL": 1},
    "Reasoning": {"THINK": 1},
    "Categorization": {"THINK": 1, "KIND": 1},

    # Emotion frames
    "Emotions": {"FEEL": 1},
    "Experiencer_obj": {"FEEL": 1, "CAUSE": 1},
    "Desiring": {"WANT": 1},

    # Causation frames
    "Causation": {"CAUSE": 1},
    "Cause_change": {"CAUSE": 1, "HAPPEN": 1},
    "Creating": {"DO": 1, "CAUSE": 1, "START": 1},
    "Destroying": {"DO": 1, "CAUSE": 1, "END": 1},

    # Possession frames
    "Possession": {"HAVE": 1},
    "Getting": {"HAVE": 1, "START": 1},
    "Giving": {"HAVE": -1, "CAUSE": 1},
    "Commerce_buy": {"HAVE": 1, "START": 1},

    # Life frames
    "Being_born": {"ALIVE": 1, "START": 1},
    "Death": {"ALIVE": -1, "END": 1},
    "Killing": {"ALIVE": -1, "CAUSE": 1},
}

# USAS semantic tag → primitive mappings (Lancaster tagset)
USAS_TAG_PRIMITIVES = {
    # A: General & Abstract Terms
    "A1.1.1": {"GOOD": 1},  # General: Good/bad
    "A1.1.2": {"GOOD": -1},
    "A2.1": {"CAUSE": 1},  # Affect: Cause/Effect
    "A3+": {"BIG": 1},  # Comparing: Similar/Different
    "A3-": {"BIG": -1},
    "A4.1": {"KIND": 1},  # Class/Category
    "A5.1+": {"MAYBE": 1},  # Evaluation: True/False
    "A5.2+": {"TRUE": 1},
    "A5.2-": {"FALSE": 1},
    "A6.1+": {"SOMETHING": 1},  # Substance
    "A7+": {"MAYBE": 1, "CAN": 1},  # Likelihood
    "A8": {"CAN": 1},  # Ability
    "A9+": {"MUST": 1},  # Need

    # B: The Body & The Individual
    "B1": {"BODY": 1},  # Body
    "B2": {"BODY": 1, "GOOD": -1},  # Health/Disease
    "B3": {"BODY": 1, "FEEL": 1},  # Medicines
    "B4": {"BODY": 1, "DO": 1},  # Cleaning
    "B5": {"BODY": 1},  # Clothes

    # C: Arts & Crafts
    "C1": {"DO": 1},  # Arts & Crafts

    # E: Emotional Actions/States
    "E1": {"FEEL": 1, "GOOD": 1},  # Emotional: General
    "E2+": {"FEEL": 1, "GOOD": 1},  # Liking
    "E2-": {"FEEL": 1, "GOOD": -1},  # Disliking
    "E3-": {"FEEL": 1, "GOOD": -1},  # Calm/Violent
    "E4.1+": {"FEEL": 1, "GOOD": 1},  # Happy
    "E4.1-": {"FEEL": 1, "GOOD": -1},  # Sad
    "E4.2+": {"FEEL": 1},  # Surprised
    "E5+": {"FEEL": 1, "GOOD": -1},  # Fear
    "E6+": {"FEEL": 1, "GOOD": -1},  # Angry

    # I: Money & Commerce
    "I1": {"HAVE": 1, "QUANTITY": 1},  # Money
    "I2.1": {"DO": 1, "HAVE": 1},  # Business

    # K: Entertainment/Sports
    "K1": {"DO": 1, "FEEL": 1},  # Entertainment
    "K2": {"HEAR": 1, "FEEL": 1},  # Music
    "K4": {"DO": 1},  # Drama
    "K5.1": {"DO": 1, "BODY": 1, "MOVE": 1},  # Sports

    # L: Life & Living Things
    "L1": {"ALIVE": 1},  # Life
    "L2": {"ALIVE": 1, "BODY": 1},  # Living creatures
    "L3": {"ALIVE": 1},  # Plants

    # M: Movement/Location
    "M1": {"MOVE": 1},  # Moving
    "M2": {"MOVE": 1, "WITH": 1},  # Putting
    "M3": {"MOVE": 1, "TOWARD": 1},  # Transport
    "M4": {"MOVE": 1},  # Swimming
    "M5": {"WHERE": 1},  # Location
    "M6": {"WHERE": 1, "INSIDE": 1},  # Open/Close
    "M7": {"WHERE": 1},  # Places
    "M8": {"WHERE": 1, "OUTSIDE": 1},  # Outside

    # N: Numbers & Measurement
    "N1": {"QUANTITY": 1, "ONE": 1},  # Numbers
    "N2": {"QUANTITY": 1, "MUCH": 1},  # Amount
    "N3.1": {"QUANTITY": 1, "MUCH": 1},  # Measurement: Size
    "N3.2": {"WHEN": 1, "QUANTITY": 1},  # Measurement: Time
    "N4": {"BIG": 1},  # Linear order
    "N5": {"QUANTITY": 1},  # Quantities

    # O: Substances, Materials, Objects
    "O1": {"SOMETHING": 1},  # Substances
    "O2": {"SOMETHING": 1},  # Objects
    "O3": {"SOMETHING": 1, "DO": 1},  # Electricity
    "O4.1": {"SOMETHING": 1},  # Physical attributes
    "O4.2+": {"SEE": 1, "GOOD": 1},  # Color: Bright
    "O4.2-": {"SEE": 1},  # Color: Dark
    "O4.3": {"SEE": 1, "SOMETHING": 1},  # Shape
    "O4.4": {"TOUCH": 1},  # Texture
    "O4.5": {"FEEL": 1, "BODY": 1},  # Temperature
    "O4.6": {"HEAR": 1},  # Sound

    # P: Education
    "P1": {"KNOW": 1, "THINK": 1},  # Education

    # Q: Language & Communication
    "Q1.1": {"SAY": 1, "WORDS": 1},  # Communication: Linguistic
    "Q1.2": {"SEE": 1, "WORDS": 1},  # Writing
    "Q1.3": {"SAY": 1},  # Speech
    "Q2.1": {"SAY": 1, "WORDS": 1},  # Speech acts
    "Q2.2": {"WORDS": 1},  # Naming
    "Q3": {"HEAR": 1, "SAY": 1},  # Telecommunications
    "Q4.1": {"WORDS": 1},  # Media
    "Q4.2": {"SEE": 1, "WORDS": 1},  # Visual media

    # S: Social Actions/States
    "S1.1.1": {"PEOPLE": 1},  # Social: General
    "S1.1.2+": {"PEOPLE": 1, "WITH": 1},  # Participating
    "S1.2.1+": {"PEOPLE": 1, "GOOD": 1},  # Friendly
    "S1.2.1-": {"PEOPLE": 1, "GOOD": -1},  # Hostile
    "S2": {"SOMEONE": 1, "PEOPLE": 1},  # People
    "S3.1": {"PEOPLE": 1, "WITH": 1},  # Relationship: General
    "S3.2": {"PEOPLE": 1, "ALIVE": 1},  # Family
    "S4": {"PEOPLE": 1, "ALIVE": 1},  # Sex
    "S5+": {"PEOPLE": 1, "GOOD": 1},  # Groups: Member
    "S6+": {"MUST": 1},  # Obligation
    "S7.1+": {"CAN": 1, "PEOPLE": 1},  # Power
    "S8+": {"MUST": 1, "WORDS": 1},  # Religion
    "S9": {"MUST": 1, "GOOD": 1},  # Ethics

    # T: Time
    "T1": {"WHEN": 1},  # Time
    "T1.1": {"WHEN": 1, "NOW": 1},  # Time: Present
    "T1.1.1": {"WHEN": 1, "BEFORE": 1},  # Time: Past
    "T1.1.2": {"WHEN": 1, "NOW": 1},  # Time: Present
    "T1.1.3": {"WHEN": 1, "AFTER": 1},  # Time: Future
    "T1.2": {"WHEN": 1, "MOMENT": 1},  # Time: Momentary
    "T1.3": {"WHEN": 1, "LONG_TIME": 1},  # Time: Period
    "T2+": {"START": 1, "WHEN": 1},  # Beginning
    "T2-": {"END": 1, "WHEN": 1},  # Ending
    "T3-": {"BEFORE": 1, "WHEN": 1},  # Old
    "T4": {"WHEN": 1, "QUANTITY": 1},  # Frequency

    # W: World & Environment
    "W1": {"WHERE": 1},  # World
    "W2": {"WHERE": 1, "SEE": 1},  # Light
    "W3": {"WHERE": 1},  # Geographical
    "W4": {"WHERE": 1, "HAPPEN": 1},  # Weather
    "W5": {"SOMETHING": 1},  # Green issues

    # X: Psychological Actions/States
    "X1": {"THINK": 1},  # Mental: General
    "X2.1": {"THINK": 1, "KNOW": 1},  # Thought processes
    "X2.2+": {"KNOW": 1},  # Knowledge
    "X2.2-": {"KNOW": -1},  # Ignorance
    "X2.4": {"THINK": 1, "KNOW": 1},  # Investigating
    "X2.5+": {"KNOW": 1, "TRUE": 1},  # Understand
    "X2.5-": {"KNOW": -1},  # Misunderstand
    "X2.6+": {"KNOW": 1, "BEFORE": 1},  # Remember
    "X2.6-": {"KNOW": -1, "BEFORE": 1},  # Forget
    "X3.2": {"SEE": 1},  # Sensory perception
    "X3.4": {"FEEL": 1},  # Touch
    "X4.1": {"THINK": 1},  # Mental object
    "X4.2": {"THINK": 1, "KNOW": 1},  # Certainty
    "X5.1+": {"THINK": 1, "GOOD": 1},  # Interested
    "X5.1-": {"THINK": 1},  # Uninterested
    "X5.2+": {"THINK": 1, "WANT": 1},  # Attention
    "X5.2-": {"THINK": -1},  # Inattentive
    "X6+": {"MUST": 1, "THINK": 1},  # Decided
    "X6-": {"MAYBE": 1},  # Undecided
    "X7+": {"WANT": 1},  # Wanting
    "X7-": {"WANT": -1},  # Not wanting
    "X8+": {"WANT": 1, "DO": 1},  # Try
    "X9.1+": {"CAN": 1},  # Able
    "X9.1-": {"CAN": -1},  # Unable
    "X9.2+": {"DO": 1, "GOOD": 1},  # Success
    "X9.2-": {"DO": 1, "GOOD": -1},  # Failure

    # Z: Names & Grammar
    "Z1": {"SOMEONE": 1},  # Personal names
    "Z2": {"WHERE": 1},  # Geographical names
    "Z3": {"SOMETHING": 1},  # Other proper names
}

# ConceptNet relation → primitive mappings
CONCEPTNET_RELATION_PRIMITIVES = {
    # Taxonomic relations
    "IsA": {"KIND": 1},
    "InstanceOf": {"KIND": 1, "ONE": 1},
    "DefinedAs": {"SAME": 1},

    # Part-whole relations
    "HasA": {"HAVE": 1, "PART": 1},
    "PartOf": {"PART": 1},
    "MadeOf": {"SOMETHING": 1},

    # Spatial relations
    "AtLocation": {"WHERE": 1},
    "LocatedNear": {"WHERE": 1, "NEAR": 1},

    # Action/causation relations
    "CapableOf": {"CAN": 1, "DO": 1},
    "Causes": {"CAUSE": 1},
    "CausesDesire": {"CAUSE": 1, "WANT": 1},
    "HasPrerequisite": {"BEFORE": 1, "MUST": 1},
    "HasSubevent": {"PART": 1, "DO": 1},
    "HasFirstSubevent": {"START": 1, "DO": 1},
    "HasLastSubevent": {"END": 1, "DO": 1},
    "Entails": {"CAUSE": 1, "MUST": 1},
    "MannerOf": {"DO": 1, "LIKE": 1},

    # Property relations
    "HasProperty": {},  # Property depends on the object
    "NotHasProperty": {},

    # Mental/desire relations
    "Desires": {"WANT": 1},
    "NotDesires": {"WANT": -1},
    "MotivatedByGoal": {"WANT": 1, "CAUSE": 1},

    # Creation relations
    "CreatedBy": {"CAUSE": 1, "DO": 1},

    # Opposition
    "Antonym": {},  # Handled specially - flip polarity
    "DistinctFrom": {"OTHER": 1},

    # Etymology (less semantic)
    "DerivedFrom": {"BEFORE": 1},
    "EtymologicallyRelatedTo": {},
    "EtymologicallyDerivedFrom": {"BEFORE": 1},
    "FormOf": {"SAME": 1},

    # Context
    "HasContext": {},  # Domain marker
}

# Lancaster sensorimotor modality → primitive mappings
# Threshold: mean > 2.5 indicates strong modality association
SENSORIMOTOR_PRIMITIVES = {
    "Auditory": {"HEAR": 1},
    "Gustatory": {"BODY": 1},  # Taste → body
    "Haptic": {"TOUCH": 1, "BODY": 1},
    "Interoceptive": {"FEEL": 1, "BODY": 1},  # Internal sensations
    "Olfactory": {"BODY": 1},  # Smell → body
    "Visual": {"SEE": 1},
    "Foot_leg": {"BODY": 1, "MOVE": 1},
    "Hand_arm": {"BODY": 1, "DO": 1},
    "Head": {"BODY": 1, "THINK": 1},
    "Mouth": {"BODY": 1, "SAY": 1},
    "Torso": {"BODY": 1},
}
SENSORIMOTOR_THRESHOLD = 2.5  # Mean score threshold for activation

# NRC emotion → primitive mappings
NRC_EMOTION_PRIMITIVES = {
    "anger": {"FEEL": 1, "GOOD": -1},
    "anticipation": {"FEEL": 1, "WANT": 1, "AFTER": 1},
    "disgust": {"FEEL": 1, "GOOD": -1},
    "fear": {"FEEL": 1, "GOOD": -1},
    "joy": {"FEEL": 1, "GOOD": 1},
    "sadness": {"FEEL": 1, "GOOD": -1},
    "surprise": {"FEEL": 1},
    "trust": {"FEEL": 1, "GOOD": 1},
    "positive": {"GOOD": 1},
    "negative": {"GOOD": -1},
}

# NRC VAD thresholds for primitive mapping
# Values are in range [-1, 1] approximately
VAD_THRESHOLDS = {
    "valence": {"high": 0.3, "low": -0.3},  # GOOD+/-
    "arousal": {"high": 0.3, "low": -0.3},  # FEEL intensity
    "dominance": {"high": 0.3, "low": -0.3},  # CAN/MUST
}

# Concreteness thresholds (scale 1-5)
CONCRETENESS_THRESHOLDS = {
    "concrete": 4.0,  # High → SOMETHING, BODY, physical
    "abstract": 2.5,  # Low → THINK, mental
}


@dataclass
class AuditResult:
    """Container for audit findings."""
    word: str
    pos: Optional[str]
    wiktionary_primitives: Dict[str, int]
    source_primitives: Dict[str, Dict[str, int]]  # source -> primitive -> value
    conflicts: List[Dict]
    agreement_score: float
    frequency_rank: Optional[int] = None


@dataclass
class ConflictReport:
    """Details of a primitive conflict."""
    word: str
    primitive: str
    wiktionary_value: int
    source_name: str
    source_value: int
    conflict_type: str  # 'value_mismatch', 'missing_in_wikt', 'missing_in_source'


# =============================================================================
# AUDIT FUNCTIONS
# =============================================================================

def load_wiktionary_primitives(db_path: Path) -> Dict[str, Dict[str, int]]:
    """Load all word-primitive mappings from Wiktionary database."""
    logger.info(f"Loading Wiktionary primitives from {db_path}")

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return {}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    cursor = conn.execute("""
        SELECT word, primitive, value, confidence
        FROM word_primitives
        ORDER BY word, confidence DESC
    """)

    word_prims = defaultdict(dict)
    for row in cursor:
        word = row['word']
        prim = row['primitive']
        if prim not in word_prims[word]:  # Keep highest confidence
            word_prims[word][prim] = row['value']

    conn.close()
    logger.info(f"Loaded primitives for {len(word_prims):,} words")
    return dict(word_prims)


def load_aggregation_sources(data_dir: Path) -> Dict[str, Dict[str, Dict[str, int]]]:
    """
    Load primitives from other NLP databases.
    Returns: source_name -> word -> primitive -> value
    """
    sources = {}

    # ConceptNet (3.1M edges)
    if CONCEPTNET_DB.exists():
        sources['conceptnet'] = load_conceptnet_primitives(CONCEPTNET_DB)

    # Lancaster Sensorimotor Norms
    if LANCASTER_CSV.exists():
        sources['sensorimotor'] = load_sensorimotor_primitives(LANCASTER_CSV)

    # NRC Emotion Lexicon
    if NRC_EMOTION_TXT.exists():
        sources['nrc_emotion'] = load_nrc_emotion_primitives(NRC_EMOTION_TXT)

    # NRC VAD Lexicon
    if NRC_VAD_TXT.exists():
        sources['nrc_vad'] = load_nrc_vad_primitives(NRC_VAD_TXT)

    # Concreteness Ratings
    if CONCRETENESS_CSV.exists():
        sources['concreteness'] = load_concreteness_primitives(CONCRETENESS_CSV)

    # USAS Semantic Tags
    if USAS_TSV.exists():
        sources['usas'] = load_usas_primitives_from_tsv(USAS_TSV)

    return sources


def load_verbnet_primitives(path: Path) -> Dict[str, Dict[str, int]]:
    """Load VerbNet class-based primitives."""
    word_prims = {}

    # Check for verb-class mapping file
    mapping_file = path / "verb_classes.json"
    if mapping_file.exists():
        with open(mapping_file) as f:
            verb_classes = json.load(f)

        for verb, class_id in verb_classes.items():
            if class_id in VERBNET_CLASS_PRIMITIVES:
                word_prims[verb.lower()] = VERBNET_CLASS_PRIMITIVES[class_id].copy()

    logger.info(f"Loaded VerbNet primitives for {len(word_prims)} verbs")
    return word_prims


def load_framenet_primitives(path: Path) -> Dict[str, Dict[str, int]]:
    """Load FrameNet frame-based primitives."""
    word_prims = {}

    # Check for lexical unit mapping file
    lu_file = path / "lexical_units.json"
    if lu_file.exists():
        with open(lu_file) as f:
            lex_units = json.load(f)

        for word, frame in lex_units.items():
            if frame in FRAMENET_FRAME_PRIMITIVES:
                word_prims[word.lower()] = FRAMENET_FRAME_PRIMITIVES[frame].copy()

    logger.info(f"Loaded FrameNet primitives for {len(word_prims)} words")
    return word_prims


def load_wordnet_primitives(db_path: Path) -> Dict[str, Dict[str, int]]:
    """Load primitives from existing lexicon (WordNet-derived)."""
    word_prims = {}

    if not db_path.exists():
        return word_prims

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.execute("""
            SELECT l.lemma as word, pv.primitive, pv.value
            FROM primitive_values pv
            JOIN lexemes l ON pv.lexeme_id = l.id
            WHERE pv.source LIKE '%wordnet%'
        """)

        for row in cursor:
            word = row['word'].lower()
            if word not in word_prims:
                word_prims[word] = {}
            word_prims[word][row['primitive']] = row['value']
    except sqlite3.OperationalError as e:
        logger.warning(f"Could not load WordNet primitives (table may not exist): {e}")

    conn.close()
    logger.info(f"Loaded WordNet primitives for {len(word_prims)} words")
    return word_prims


def load_usas_primitives(path: Path) -> Dict[str, Dict[str, int]]:
    """Load USAS semantic tag-based primitives."""
    word_prims = {}

    # Check for word-tag mapping
    tag_file = path / "word_tags.json"
    if tag_file.exists():
        with open(tag_file) as f:
            word_tags = json.load(f)

        for word, tags in word_tags.items():
            prims = {}
            for tag in tags if isinstance(tags, list) else [tags]:
                # Match tag prefix
                for usas_tag, tag_prims in USAS_TAG_PRIMITIVES.items():
                    if tag.startswith(usas_tag):
                        prims.update(tag_prims)
                        break
            if prims:
                word_prims[word.lower()] = prims

    logger.info(f"Loaded USAS primitives for {len(word_prims)} words")
    return word_prims


def load_conceptnet_primitives(db_path: Path) -> Dict[str, Dict[str, int]]:
    """Load primitives from ConceptNet relations."""
    word_prims = defaultdict(dict)

    if not db_path.exists():
        return dict(word_prims)

    conn = sqlite3.connect(str(db_path))

    # Get edges with semantic relations
    cursor = conn.execute("""
        SELECT relation, start_word, end_word, weight
        FROM edges
        WHERE weight > 1.0
        ORDER BY start_word
    """)

    count = 0
    for relation, start_word, end_word, weight in cursor:
        # Clean words (remove /c/en/ prefix if present)
        word = start_word.lower().replace('/c/en/', '').replace('_', ' ')

        if relation in CONCEPTNET_RELATION_PRIMITIVES:
            prims = CONCEPTNET_RELATION_PRIMITIVES[relation]
            for prim, val in prims.items():
                if prim not in word_prims[word]:
                    word_prims[word][prim] = val
                    count += 1

    conn.close()
    logger.info(f"Loaded ConceptNet primitives for {len(word_prims):,} words ({count:,} assignments)")
    return dict(word_prims)


def load_sensorimotor_primitives(csv_path: Path) -> Dict[str, Dict[str, int]]:
    """Load primitives from Lancaster Sensorimotor Norms."""
    word_prims = {}

    if not csv_path.exists():
        return word_prims

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = row['Word'].lower()
            prims = {}

            # Check each modality
            for modality, prim_map in SENSORIMOTOR_PRIMITIVES.items():
                col_name = f"{modality}.mean"
                if col_name in row:
                    try:
                        score = float(row[col_name])
                        if score >= SENSORIMOTOR_THRESHOLD:
                            for prim, val in prim_map.items():
                                if prim not in prims:
                                    prims[prim] = val
                    except (ValueError, TypeError):
                        pass

            if prims:
                word_prims[word] = prims

    logger.info(f"Loaded sensorimotor primitives for {len(word_prims):,} words")
    return word_prims


def load_nrc_emotion_primitives(txt_path: Path) -> Dict[str, Dict[str, int]]:
    """Load primitives from NRC Emotion Lexicon."""
    word_prims = defaultdict(dict)

    if not txt_path.exists():
        return dict(word_prims)

    with open(txt_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) != 3:
                continue

            word, emotion, value = parts
            word = word.lower()

            if value == '1' and emotion in NRC_EMOTION_PRIMITIVES:
                for prim, val in NRC_EMOTION_PRIMITIVES[emotion].items():
                    if prim not in word_prims[word]:
                        word_prims[word][prim] = val

    logger.info(f"Loaded NRC emotion primitives for {len(word_prims):,} words")
    return dict(word_prims)


def load_nrc_vad_primitives(txt_path: Path) -> Dict[str, Dict[str, int]]:
    """Load primitives from NRC VAD Lexicon."""
    word_prims = {}

    if not txt_path.exists():
        return word_prims

    with open(txt_path, 'r', encoding='utf-8') as f:
        next(f)  # Skip header
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) != 4:
                continue

            word, valence, arousal, dominance = parts
            word = word.lower()
            prims = {}

            try:
                v, a, d = float(valence), float(arousal), float(dominance)

                # Valence → GOOD
                if v >= VAD_THRESHOLDS["valence"]["high"]:
                    prims["GOOD"] = 1
                elif v <= VAD_THRESHOLDS["valence"]["low"]:
                    prims["GOOD"] = -1

                # Arousal → FEEL (high arousal)
                if a >= VAD_THRESHOLDS["arousal"]["high"]:
                    prims["FEEL"] = 1

                # Dominance → CAN (high) or MUST (low)
                if d >= VAD_THRESHOLDS["dominance"]["high"]:
                    prims["CAN"] = 1
                elif d <= VAD_THRESHOLDS["dominance"]["low"]:
                    prims["MUST"] = 1

            except (ValueError, TypeError):
                pass

            if prims:
                word_prims[word] = prims

    logger.info(f"Loaded NRC VAD primitives for {len(word_prims):,} words")
    return word_prims


def load_concreteness_primitives(csv_path: Path) -> Dict[str, Dict[str, int]]:
    """Load primitives from Concreteness Ratings."""
    word_prims = {}

    if not csv_path.exists():
        return word_prims

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = row['Word'].lower()
            prims = {}

            try:
                conc = float(row['Conc.M'])

                if conc >= CONCRETENESS_THRESHOLDS["concrete"]:
                    prims["SOMETHING"] = 1
                elif conc <= CONCRETENESS_THRESHOLDS["abstract"]:
                    prims["THINK"] = 1

            except (ValueError, TypeError, KeyError):
                pass

            if prims:
                word_prims[word] = prims

    logger.info(f"Loaded concreteness primitives for {len(word_prims):,} words")
    return word_prims


def load_usas_primitives_from_tsv(tsv_path: Path) -> Dict[str, Dict[str, int]]:
    """Load USAS semantic tags from TSV file."""
    word_prims = {}

    if not tsv_path.exists():
        return word_prims

    with open(tsv_path, 'r', encoding='utf-8') as f:
        next(f)  # Skip header
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) < 3:
                continue

            lemma, pos, tags = parts[0], parts[1], parts[2]
            word = lemma.lower()
            prims = {}

            # Tags can be multiple separated by /
            for tag in tags.split('/'):
                tag = tag.strip()
                # Match tag prefix (e.g., "E1" matches "E1.1+")
                for usas_tag, tag_prims in USAS_TAG_PRIMITIVES.items():
                    if tag.startswith(usas_tag):
                        for prim, val in tag_prims.items():
                            if prim not in prims:
                                prims[prim] = val
                        break

            if prims:
                word_prims[word] = prims

    logger.info(f"Loaded USAS primitives for {len(word_prims):,} words")
    return word_prims


def find_conflicts(
    wikt_prims: Dict[str, Dict[str, int]],
    source_prims: Dict[str, Dict[str, Dict[str, int]]]
) -> List[ConflictReport]:
    """Find conflicts between Wiktionary and other sources."""
    conflicts = []

    for source_name, source_words in source_prims.items():
        for word, prims in source_words.items():
            if word not in wikt_prims:
                continue

            wikt = wikt_prims[word]

            for prim, source_val in prims.items():
                if prim in wikt:
                    wikt_val = wikt[prim]
                    if wikt_val != source_val:
                        conflicts.append(ConflictReport(
                            word=word,
                            primitive=prim,
                            wiktionary_value=wikt_val,
                            source_name=source_name,
                            source_value=source_val,
                            conflict_type='value_mismatch'
                        ))
                else:
                    conflicts.append(ConflictReport(
                        word=word,
                        primitive=prim,
                        wiktionary_value=0,
                        source_name=source_name,
                        source_value=source_val,
                        conflict_type='missing_in_wikt'
                    ))

    return conflicts


def load_word_frequencies(path: Optional[Path] = None) -> Dict[str, int]:
    """Load word frequency data."""
    frequencies = {}

    # Default: use Wiktionary entry counts as proxy
    if path is None or not path.exists():
        logger.info("Using Wiktionary entry count as frequency proxy")
        if WIKT_DB.exists():
            conn = sqlite3.connect(str(WIKT_DB))
            cursor = conn.execute("""
                SELECT word, COUNT(*) as freq
                FROM word_primitives
                GROUP BY word
                ORDER BY freq DESC
            """)
            for i, (word, count) in enumerate(cursor):
                frequencies[word] = i + 1  # Rank
            conn.close()
    else:
        # Load from frequency file
        with open(path) as f:
            for i, line in enumerate(f):
                word = line.strip().split()[0].lower()
                frequencies[word] = i + 1

    return frequencies


def generate_audit_report(
    wikt_prims: Dict[str, Dict[str, int]],
    source_prims: Dict[str, Dict[str, Dict[str, int]]],
    conflicts: List[ConflictReport],
    frequencies: Dict[str, int]
) -> Dict:
    """Generate comprehensive audit report."""

    # Conflict statistics
    conflict_by_source = defaultdict(list)
    conflict_by_primitive = defaultdict(list)
    conflict_by_type = defaultdict(list)

    for c in conflicts:
        conflict_by_source[c.source_name].append(c)
        conflict_by_primitive[c.primitive].append(c)
        conflict_by_type[c.conflict_type].append(c)

    # Coverage statistics
    source_coverage = {}
    for source_name, words in source_prims.items():
        overlap = len(set(words.keys()) & set(wikt_prims.keys()))
        source_coverage[source_name] = {
            'total_words': len(words),
            'overlap_with_wikt': overlap,
            'overlap_pct': overlap / len(words) * 100 if words else 0
        }

    # High-frequency word conflicts (more important)
    high_freq_conflicts = [
        c for c in conflicts
        if c.word in frequencies and frequencies[c.word] <= 10000
    ]

    report = {
        'summary': {
            'wiktionary_words': len(wikt_prims),
            'total_conflicts': len(conflicts),
            'high_frequency_conflicts': len(high_freq_conflicts),
            'conflict_rate': len(conflicts) / len(wikt_prims) * 100 if wikt_prims else 0
        },
        'by_source': {
            name: {
                'conflicts': len(cs),
                'coverage': source_coverage.get(name, {})
            }
            for name, cs in conflict_by_source.items()
        },
        'by_primitive': {
            prim: len(cs)
            for prim, cs in sorted(conflict_by_primitive.items(), key=lambda x: -len(x[1]))[:20]
        },
        'by_type': {
            ctype: len(cs)
            for ctype, cs in conflict_by_type.items()
        },
        'sample_conflicts': [
            {
                'word': c.word,
                'primitive': c.primitive,
                'wikt_value': c.wiktionary_value,
                'source': c.source_name,
                'source_value': c.source_value,
                'type': c.conflict_type,
                'frequency_rank': frequencies.get(c.word, -1)
            }
            for c in sorted(high_freq_conflicts, key=lambda x: frequencies.get(x.word, float('inf')))[:50]
        ]
    }

    return report


# =============================================================================
# MAIN
# =============================================================================

def run_audit():
    """Run the multi-source audit."""
    logger.info("=" * 60)
    logger.info("Multi-Source NLP Database Audit")
    logger.info("=" * 60)

    # Load Wiktionary primitives
    wikt_prims = load_wiktionary_primitives(WIKT_DB)
    if not wikt_prims:
        logger.error("Failed to load Wiktionary primitives")
        return False

    # Load other sources
    source_prims = load_aggregation_sources(DATA_DIR)
    logger.info(f"Loaded {len(source_prims)} additional sources")

    # Find conflicts
    conflicts = find_conflicts(wikt_prims, source_prims)
    logger.info(f"Found {len(conflicts)} potential conflicts")

    # Load frequencies
    frequencies = load_word_frequencies()

    # Generate report
    report = generate_audit_report(wikt_prims, source_prims, conflicts, frequencies)

    # Save report
    AUDIT_OUTPUT.mkdir(parents=True, exist_ok=True)
    report_path = AUDIT_OUTPUT / "audit_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    print(f"Wiktionary words: {report['summary']['wiktionary_words']:,}")
    print(f"Total conflicts: {report['summary']['total_conflicts']:,}")
    print(f"High-frequency conflicts: {report['summary']['high_frequency_conflicts']:,}")
    print(f"Conflict rate: {report['summary']['conflict_rate']:.2f}%")
    print("\nConflicts by source:")
    for source, data in report['by_source'].items():
        print(f"  {source}: {data['conflicts']} conflicts")
    print("\nTop conflicting primitives:")
    for prim, count in list(report['by_primitive'].items())[:10]:
        print(f"  {prim}: {count}")
    print(f"\nFull report saved to: {report_path}")

    return True


def add_frequency_data():
    """Add word frequency ranking to the database."""
    logger.info("Adding word frequency data...")

    frequencies = load_word_frequencies()

    if not WIKT_DB.exists():
        logger.error(f"Database not found: {WIKT_DB}")
        return False

    conn = sqlite3.connect(str(WIKT_DB))

    # Create frequency table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS word_frequency (
            word TEXT PRIMARY KEY,
            rank INTEGER,
            tier TEXT
        )
    """)

    # Assign tiers based on rank
    def get_tier(rank: int) -> str:
        if rank <= 1000:
            return 'core'      # Core vocabulary
        elif rank <= 5000:
            return 'common'    # Common words
        elif rank <= 20000:
            return 'standard'  # Standard vocabulary
        elif rank <= 100000:
            return 'extended'  # Extended vocabulary
        else:
            return 'rare'      # Rare words

    batch = []
    for word, rank in frequencies.items():
        tier = get_tier(rank)
        batch.append((word, rank, tier))

        if len(batch) >= 10000:
            conn.executemany(
                "INSERT OR REPLACE INTO word_frequency (word, rank, tier) VALUES (?, ?, ?)",
                batch
            )
            conn.commit()
            batch = []

    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO word_frequency (word, rank, tier) VALUES (?, ?, ?)",
            batch
        )
        conn.commit()

    # Create index
    conn.execute("CREATE INDEX IF NOT EXISTS idx_freq_tier ON word_frequency(tier)")
    conn.commit()

    # Stats
    cursor = conn.execute("SELECT tier, COUNT(*) FROM word_frequency GROUP BY tier ORDER BY MIN(rank)")
    print("\nFrequency tier distribution:")
    for tier, count in cursor:
        print(f"  {tier}: {count:,} words")

    conn.close()
    logger.info("Frequency data added successfully")
    return True


def main():
    parser = argparse.ArgumentParser(description="Multi-Source NLP Audit")
    parser.add_argument('--audit', action='store_true', help='Run conflict audit')
    parser.add_argument('--frequency', action='store_true', help='Add frequency data')
    parser.add_argument('--report', action='store_true', help='Generate full report')

    args = parser.parse_args()

    if args.audit or args.report:
        if not run_audit():
            sys.exit(1)

    if args.frequency:
        if not add_frequency_data():
            sys.exit(1)

    if not any([args.audit, args.frequency, args.report]):
        parser.print_help()


if __name__ == "__main__":
    main()
