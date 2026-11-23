"""
GSE Curation Database Schema

Defines the SQLite schema for the lexicon database and constants
for the 72-primitive system.
"""

from typing import List, Tuple

# =============================================================================
# ALL 72 PRIMITIVES (from primitives_v2.py)
# =============================================================================

# Bank 0: SUBSTANTIVES (10 primitives)
BANK_0_PRIMITIVES = [
    "I",
    "YOU",
    "SOMEONE",
    "SOMETHING",
    "PEOPLE",
    "BODY",
    "KIND",
    "PART",
    "SAME",
    "OTHER",  # Bipolar: IDENTITY
]

# Bank 1: QUANTITY (3 primitives)
BANK_1_PRIMITIVES = [
    "ONE",
    "TWO",
    "QUANTITY",
]

# Bank 2: EVALUATORS (4 primitives - all bipolar)
BANK_2_PRIMITIVES = [
    "GOOD",
    "BAD",  # Bipolar: EVALUATION
    "BIG",
    "SMALL",  # Bipolar: SIZE
]

# Bank 3: MENTAL (7 primitives)
BANK_3_PRIMITIVES = [
    "THINK",
    "KNOW",
    "WANT",
    "FEEL",
    "SEE",
    "HEAR",
    "INFER",
]

# Bank 4: ACTION (10 primitives)
BANK_4_PRIMITIVES = [
    "SAY",
    "WORDS",
    "DO",
    "HAPPEN",
    "MOVE",
    "BE",
    "HAVE",
    "EXIST",
    "ALIVE",
    "DEAD",  # Bipolar: VITALITY
]

# Bank 5: TEMPORAL (10 primitives)
BANK_5_PRIMITIVES = [
    "MOMENT",
    "WHEN",
    "LONG_TIME",
    "SHORT_TIME",  # Bipolar: DURATION
    "BEFORE",
    "AFTER",  # Bipolar: TEMPORAL_ORDER
    "THEN",
    "NOW",  # Bipolar: TEMPORAL_REF
    "START",
    "END",  # Bipolar: TEMPORAL_BOUND
]

# Bank 6: SPATIAL (14 primitives)
BANK_6_PRIMITIVES = [
    "WHERE",
    "HERE",
    "SIDE",
    "TOUCH",
    "ABOVE",
    "BELOW",  # Bipolar: VERTICAL
    "FAR",
    "NEAR",  # Bipolar: DISTANCE
    "OUTSIDE",
    "INSIDE",  # Bipolar: CONTAINMENT
    "TOWARD",
    "AWAY",  # Bipolar: DIRECTION
    "WITH",
    "WITHOUT",  # Bipolar: ACCOMPANIMENT
]

# Bank 7: LOGICAL (14 primitives)
BANK_7_PRIMITIVES = [
    "NOT",
    "MAYBE",
    "CAN",
    "MUST",
    "BECAUSE",
    "CAUSE",
    "IF",
    "LIKE",
    "TRUE",
    "FALSE",  # Bipolar: TRUTH
    "HIER_PLUS",
    "HIER_MINUS",
    "INTENSITY",
    "CERTAINTY",
]

# Complete list of all 72 primitives
ALL_PRIMITIVES: List[str] = (
    BANK_0_PRIMITIVES
    + BANK_1_PRIMITIVES
    + BANK_2_PRIMITIVES
    + BANK_3_PRIMITIVES
    + BANK_4_PRIMITIVES
    + BANK_5_PRIMITIVES
    + BANK_6_PRIMITIVES
    + BANK_7_PRIMITIVES
)

# Verify count
assert len(ALL_PRIMITIVES) == 72, f"Expected 72 primitives, got {len(ALL_PRIMITIVES)}"

# Bank assignment for each primitive
PRIMITIVE_TO_BANK = {}
for prim in BANK_0_PRIMITIVES:
    PRIMITIVE_TO_BANK[prim] = 0
for prim in BANK_1_PRIMITIVES:
    PRIMITIVE_TO_BANK[prim] = 1
for prim in BANK_2_PRIMITIVES:
    PRIMITIVE_TO_BANK[prim] = 2
for prim in BANK_3_PRIMITIVES:
    PRIMITIVE_TO_BANK[prim] = 3
for prim in BANK_4_PRIMITIVES:
    PRIMITIVE_TO_BANK[prim] = 4
for prim in BANK_5_PRIMITIVES:
    PRIMITIVE_TO_BANK[prim] = 5
for prim in BANK_6_PRIMITIVES:
    PRIMITIVE_TO_BANK[prim] = 6
for prim in BANK_7_PRIMITIVES:
    PRIMITIVE_TO_BANK[prim] = 7


# =============================================================================
# BIPOLAR PAIRS (14 pairs - cannot both be non-zero)
# =============================================================================

BIPOLAR_PAIRS: List[Tuple[str, str]] = [
    # Bank 0: SUBSTANTIVES
    ("SAME", "OTHER"),  # IDENTITY
    # Bank 2: EVALUATORS
    ("GOOD", "BAD"),  # EVALUATION
    ("BIG", "SMALL"),  # SIZE
    # Bank 4: ACTION
    ("ALIVE", "DEAD"),  # VITALITY
    # Bank 5: TEMPORAL
    ("LONG_TIME", "SHORT_TIME"),  # DURATION
    ("BEFORE", "AFTER"),  # TEMPORAL_ORDER
    ("THEN", "NOW"),  # TEMPORAL_REF
    ("START", "END"),  # TEMPORAL_BOUND
    # Bank 6: SPATIAL
    ("ABOVE", "BELOW"),  # VERTICAL
    ("FAR", "NEAR"),  # DISTANCE
    ("OUTSIDE", "INSIDE"),  # CONTAINMENT
    ("TOWARD", "AWAY"),  # DIRECTION
    ("WITH", "WITHOUT"),  # ACCOMPANIMENT
    # Bank 7: LOGICAL
    ("TRUE", "FALSE"),  # TRUTH
]

# Quick lookup: primitive -> its bipolar partner
BIPOLAR_PARTNER = {}
for pos, neg in BIPOLAR_PAIRS:
    BIPOLAR_PARTNER[pos] = neg
    BIPOLAR_PARTNER[neg] = pos

# Set of all bipolar primitives
BIPOLAR_PRIMITIVES = set()
for pos, neg in BIPOLAR_PAIRS:
    BIPOLAR_PRIMITIVES.add(pos)
    BIPOLAR_PRIMITIVES.add(neg)


# =============================================================================
# HIERARCHY DEFINITIONS
# =============================================================================

# Quantity hierarchy (7 levels)
QUANTITY_HIERARCHY = {
    "NONE": -3,
    "FEW": -2,
    "SOME": -1,
    "MIDDLE": 0,
    "MORE": 1,
    "MANY": 2,
    "ALL": 3,
}

# Intensity hierarchy (5 levels)
INTENSITY_HIERARCHY = {
    "BARELY": -2,
    "SLIGHTLY": -1,
    "MODERATE": 0,
    "VERY": 1,
    "EXTREMELY": 2,
}

# Certainty hierarchy (7 levels)
CERTAINTY_HIERARCHY = {
    "IMPOSSIBLE": -3,
    "UNLIKELY": -2,
    "DOUBTFUL": -1,
    "POSSIBLE": 0,
    "PROBABLE": 1,
    "LIKELY": 2,
    "CERTAIN": 3,
}


# =============================================================================
# DATABASE SCHEMA
# =============================================================================

SCHEMA = """
-- =============================================================================
-- GSE Lexicon Builder Database Schema
-- Full 72-primitive decomposition with validation tracking
-- =============================================================================

-- Main lexeme table
CREATE TABLE IF NOT EXISTS lexemes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma TEXT NOT NULL,
    pos TEXT NOT NULL,
    sense_id TEXT DEFAULT '01',
    gloss TEXT,
    source TEXT DEFAULT 'llm',
    confidence REAL DEFAULT 1.0,
    frequency_rank INTEGER,
    frequency_weight REAL,
    phase INTEGER DEFAULT 0,
    validation_status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(lemma, pos, sense_id)
);

-- Full 72-primitive decomposition (72 rows per lexeme for complete coverage)
CREATE TABLE IF NOT EXISTS primitive_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lexeme_id INTEGER NOT NULL,
    primitive TEXT NOT NULL,
    value INTEGER NOT NULL DEFAULT 0,
    confidence REAL DEFAULT 1.0,
    source TEXT DEFAULT 'inferred',
    FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE,
    UNIQUE(lexeme_id, primitive)
);

-- Provenance tracking for decomposition changes
CREATE TABLE IF NOT EXISTS decomposition_provenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lexeme_id INTEGER NOT NULL,
    primitive TEXT,
    source_type TEXT NOT NULL,
    source_detail TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence_before REAL,
    confidence_after REAL,
    FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE
);

-- Validation results for each lexeme
CREATE TABLE IF NOT EXISTS validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lexeme_id INTEGER NOT NULL,
    validation_type TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE
);

-- LLM batch tracking for processing state
CREATE TABLE IF NOT EXISTS llm_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT UNIQUE NOT NULL,
    phase INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    words_count INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    model_name TEXT,
    prompt_version TEXT,
    error_message TEXT
);

-- Processing checkpoints for resumption
CREATE TABLE IF NOT EXISTS processing_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase INTEGER NOT NULL,
    last_processed_rank INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    words_processed INTEGER DEFAULT 0,
    words_validated INTEGER DEFAULT 0,
    UNIQUE(phase)
);

-- External source disagreements (LLM vs external sources)
CREATE TABLE IF NOT EXISTS external_disagreements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lexeme_id INTEGER NOT NULL,
    primitive TEXT NOT NULL,
    llm_value INTEGER NOT NULL,
    external_value INTEGER NOT NULL,
    external_source TEXT NOT NULL,
    severity TEXT NOT NULL,  -- 'minor', 'major', 'sign_flip'
    resolved BOOLEAN DEFAULT FALSE,
    resolution TEXT,  -- 'llm_correct', 'external_correct', 'both_valid', 'manual'
    resolved_value INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE
);

-- External source coverage tracking
CREATE TABLE IF NOT EXISTS external_source_coverage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lexeme_id INTEGER NOT NULL,
    source_name TEXT NOT NULL,
    primitives_matched INTEGER DEFAULT 0,
    primitives_agreed INTEGER DEFAULT 0,
    agreement_rate REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE,
    UNIQUE(lexeme_id, source_name)
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_lexemes_lemma ON lexemes(lemma);
CREATE INDEX IF NOT EXISTS idx_lexemes_phase ON lexemes(phase);
CREATE INDEX IF NOT EXISTS idx_lexemes_rank ON lexemes(frequency_rank);
CREATE INDEX IF NOT EXISTS idx_lexemes_status ON lexemes(validation_status);
CREATE INDEX IF NOT EXISTS idx_pv_lexeme ON primitive_values(lexeme_id);
CREATE INDEX IF NOT EXISTS idx_pv_primitive ON primitive_values(primitive);
CREATE INDEX IF NOT EXISTS idx_pv_value ON primitive_values(value);
CREATE INDEX IF NOT EXISTS idx_validation_lexeme ON validation_results(lexeme_id);
CREATE INDEX IF NOT EXISTS idx_validation_type ON validation_results(validation_type);
CREATE INDEX IF NOT EXISTS idx_provenance_lexeme ON decomposition_provenance(lexeme_id);
CREATE INDEX IF NOT EXISTS idx_disagreements_lexeme ON external_disagreements(lexeme_id);
CREATE INDEX IF NOT EXISTS idx_disagreements_severity ON external_disagreements(severity);
CREATE INDEX IF NOT EXISTS idx_disagreements_resolved ON external_disagreements(resolved);
CREATE INDEX IF NOT EXISTS idx_coverage_lexeme ON external_source_coverage(lexeme_id);
"""


# =============================================================================
# SCHEMA HELPER FUNCTIONS
# =============================================================================


def get_primitive_bank(primitive: str) -> int:
    """Get the bank number for a primitive."""
    return PRIMITIVE_TO_BANK.get(primitive, -1)


def is_bipolar_primitive(primitive: str) -> bool:
    """Check if a primitive is part of a bipolar pair."""
    return primitive in BIPOLAR_PRIMITIVES


def get_bipolar_partner(primitive: str) -> str | None:
    """Get the bipolar partner of a primitive, if any."""
    return BIPOLAR_PARTNER.get(primitive)


def validate_primitive_name(primitive: str) -> bool:
    """Check if a primitive name is valid."""
    return primitive in ALL_PRIMITIVES
