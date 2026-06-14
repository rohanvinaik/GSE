"""
Daemon Configuration

Configuration settings for the passive lexicon audit daemon.
Optimized for 2013 MacBook Pro with 16GB RAM running Ollama.
"""

from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "lexicon.db"
LOGS_DIR = BASE_DIR / "logs"

# Throttling configuration
# Optimized for 2013 Mac Pro - still conservative but not excessive
THROTTLE_CONFIG = {
    # Base delays (seconds) - reduced but still gentle on the system
    "between_words": 1.0,           # 1 second between words (was 2.0)
    "between_primitives": 0.05,     # 50ms between primitives (was 0.1)
    "after_ollama_call": 1.0,       # 1 second after LLM call (was 5.0)

    # Adaptive throttling based on system load
    "cpu_threshold_percent": 80,    # Pause if CPU > 80% (was 70%)
    "memory_threshold_gb": 100,     # Effectively disabled - swap is fine for background
    "pause_duration": 15,           # Pause for 15s if threshold exceeded (was 30)

    # Time-based throttling
    "active_hours": (0, 24),        # Run 24/7
    "weekend_active": True,         # Run on weekends

    # Batch limits - significantly increased
    "words_per_hour": 500,          # Max 500 words/hour (was 100)
    "ollama_calls_per_hour": 1000,  # Max 1000 LLM calls/hour (was 50 - was blocking mid-word!)
}

# Ollama configuration
OLLAMA_CONFIG = {
    "base_url": "http://192.168.50.73:11434",
    "model": "gemma2:9b",           # Best single model for instruction following
    "models": ["gemma2:9b"],        # Single model (no voting needed)
    "timeout": 120,                 # 2 minute timeout
    "temperature": 0.1,             # Low temperature for consistency
    "num_predict": 50,              # Allow slightly longer responses for reasoning
    "use_voting": False,            # Single model, no voting
    "min_agreement": 1,             # N/A with single model
}

# Audit configuration
AUDIT_CONFIG = {
    "min_auto_apply_confidence": 0.8,   # Minimum confidence for auto-apply
    "min_sufficient_confidence": 0.3,   # Minimum to consider "sufficient"
    "top_n_words": 5000,                # Focus on top N words by frequency
    "primitives_count": 107,            # Total number of primitives
    "batch_size": 10,                   # Words per batch
}

# Review queue configuration
REVIEW_CONFIG = {
    "max_queue_size": 10000,        # Maximum items in review queue
    "priority_levels": 10,          # Priority levels (1=highest)
}

# Logging configuration
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    "file": LOGS_DIR / "audit_daemon.log",
    "max_bytes": 10 * 1024 * 1024,  # 10MB per log file
    "backup_count": 5,              # Keep 5 backup files
}


# Primitive definitions (for reference)
# Full list of 107 primitives organized by bank
PRIMITIVES_BY_BANK = {
    "SUBSTANTIVES": [
        "I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY",
        "KIND", "PART", "SAME", "OTHER"
    ],
    "QUANTITY": [
        "ONE", "TWO", "SOME", "ALL", "MUCH", "LITTLE",
        "SING", "PLUR", "ZERO", "QUANTITY"
    ],
    "EVALUATORS": [
        "GOOD", "BAD", "BIG", "SMALL", "BEAUTIFUL"
    ],
    "MENTAL": [
        "THINK", "KNOW", "WANT", "FEEL", "SEE", "HEAR",
        "BELIEVE", "INFER", "TOUCH"
    ],
    "ACTION": [
        "DO", "HAPPEN", "MOVE", "LIVE", "DIE", "START", "END",
        "MAKE", "TRANSFER", "SAY", "WORDS", "BE", "HAVE", "EXIST",
        "ALIVE", "DEAD"
    ],
    "TEMPORAL": [
        "WHEN", "NOW", "BEFORE", "AFTER", "LONG_TIME", "SHORT_TIME",
        "MOMENT", "THEN"
    ],
    "SPATIAL": [
        "WHERE", "HERE", "ABOVE", "BELOW", "FAR", "NEAR",
        "INSIDE", "OUTSIDE", "SIDE", "TOWARD", "AWAY",
        "WITH", "WITHOUT"
    ],
    "LOGICAL": [
        "NOT", "MAYBE", "CAN", "MUST", "BECAUSE", "CAUSE", "IF",
        "LIKE", "TRUE", "FALSE", "HIER_PLUS", "HIER_MINUS",
        "INTENSITY", "CERTAINTY", "AGREE"
    ],
}

# Flatten to get all primitives
ALL_PRIMITIVES = []
for prims in PRIMITIVES_BY_BANK.values():
    ALL_PRIMITIVES.extend(prims)


def get_frequency_priority(rank: int) -> int:
    """Convert frequency rank to review priority (1=highest, 10=lowest)."""
    if rank <= 100:
        return 1      # Top 100 words: highest priority
    elif rank <= 500:
        return 2
    elif rank <= 1000:
        return 3
    elif rank <= 2000:
        return 4
    elif rank <= 3000:
        return 5
    elif rank <= 4000:
        return 6
    elif rank <= 5000:
        return 7
    else:
        return 10     # Beyond top 5000: lowest priority
