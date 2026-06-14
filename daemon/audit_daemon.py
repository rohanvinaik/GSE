#!/usr/bin/env python3
"""
GSE Lexicon Audit Daemon

Passively audits the lexicon database in the background.
Designed for continuous operation on resource-constrained hardware.

Usage:
    python audit_daemon.py           # Run in foreground
    python audit_daemon.py --test    # Test mode (10 words only)
    python audit_daemon.py --stats   # Show statistics only
"""

import sys
import time
import signal
import argparse
import logging
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from daemon.config import (
    DB_PATH, LOGS_DIR, THROTTLE_CONFIG, OLLAMA_CONFIG, AUDIT_CONFIG,
    ALL_PRIMITIVES, get_frequency_priority
)
from daemon.state_manager import StateManager
from daemon.throttle import ThrottleManager
from daemon.ollama_client import OllamaClient
from daemon.review_queue import ReviewQueue
from daemon.audit_logger import AuditLogger
from daemon.primitive_rules import (
    infer_primitive_value,
    is_grammatical_primitive,
    get_bipolar_opposite,
    BIPOLAR_PAIRS,
)

# Setup logging
LOGS_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "audit_daemon.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("audit_daemon")

# Graceful shutdown flag
shutdown_requested = False


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    global shutdown_requested
    logger.info("Shutdown signal received, finishing current word...")
    shutdown_requested = True


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def load_constraint_engine():
    """Load the constraint aggregation engine."""
    from gse.curation.constraint_aggregation import ConstraintAggregationEngine

    logger.info("Loading constraint aggregation engine...")
    engine = ConstraintAggregationEngine(
        min_auto_apply_confidence=AUDIT_CONFIG["min_auto_apply_confidence"],
        include_large_sources=False,  # Start without large sources for faster startup
    )
    stats = engine.load_sources()
    logger.info(f"Loaded {len(stats)} sources: {list(stats.keys())}")
    return engine


def format_source_context(profile, primitive: str) -> str:
    """
    Format external source data as context for LLM.

    The LLM uses this to understand what each source says about the word,
    then translates that into a GSE primitive assignment.
    """
    lines = []

    # Get all source data relevant to this word
    if profile.raw_source_data:
        for source_name, source_data in profile.raw_source_data.items():
            if source_data:
                lines.append(f"  {source_name}: {source_data}")

    # Get any existing constraint info
    constraint = profile.constraints.get(primitive)
    if constraint and constraint.supporting_sources:
        lines.append(f"  [Existing constraint for {primitive}]: value={constraint.value}, "
                    f"sources={constraint.supporting_sources}, confidence={constraint.confidence:.2f}")

    return "\n".join(lines) if lines else "  (no external data available)"


def process_word(
    word: dict,
    engine,
    state: StateManager,
    throttle: ThrottleManager,
    ollama: OllamaClient,
    review: ReviewQueue,
    audit_log: AuditLogger,
) -> dict:
    """
    Process a single word against all primitives.

    Processing order (source-gated for efficiency):
    1. Auto-apply: Sources unanimously agree → apply directly
    2. Flag review: Sources conflict → manual review queue
    3. Bipolar inference: Infer BAD from GOOD, SMALL from BIG, etc.
    4. Grammatical rules: Closed-class words (I, YOU, ONE, TWO, SING, PLUR)
    5. LLM translation: Only when sources provide context to translate
    6. Default: No context → 0 (neutral) rather than unreliable LLM guess

    The LLM is the TRANSLATION LAYER:
    - External sources provide data in their own formats
    - LLM interprets this data and assigns GSE primitives
    - LLM is NOT called when there's no source data to translate

    Args:
        word: Word dict with id, lemma, pos, frequency_rank
        engine: ConstraintAggregationEngine
        state: StateManager
        throttle: ThrottleManager
        ollama: OllamaClient - the translation layer
        review: ReviewQueue
        audit_log: AuditLogger

    Returns:
        Dict with processing statistics
    """
    word_id = word['id']
    lemma = word['lemma']
    pos = word['pos']
    freq_rank = word.get('frequency_rank', 99999)
    priority = get_frequency_priority(freq_rank)
    definition = word.get('gloss', '')

    logger.info(f"Processing: {lemma} ({pos}) rank={freq_rank}, priority={priority}")

    stats = {
        'auto_applied': 0,
        'flagged_review': 0,
        'rule_inferred': 0,      # New: bipolar + grammatical
        'llm_assigned': 0,
        'defaulted': 0,          # New: no context → 0
        'conflicts': 0,
    }

    # Get constraint profile from aggregation engine (all external source data)
    profile = engine.aggregate_constraints(lemma)

    logger.debug(f"  Sources with data: {profile.sources_with_data}")
    logger.debug(f"  Constraints found: {len(profile.constraints)}")

    # Collect known values for bipolar inference
    # First pass: gather auto-apply values
    known_values = {}
    for prim, constraint in profile.constraints.items():
        if constraint and constraint.status == "auto_apply":
            known_values[prim] = constraint.value

    # Process each primitive with source-gating
    for primitive in ALL_PRIMITIVES:
        throttle.throttle_between_primitives()

        # Get current value
        old_value = state.get_primitive_value(word_id, primitive)

        # Check if we have a constraint from external sources
        constraint = profile.constraints.get(primitive)
        source_has_data = constraint is not None and len(constraint.supporting_sources) > 0

        # === PRIORITY 1: Auto-apply from unanimous sources ===
        if constraint and constraint.status == "auto_apply":
            state.set_primitive_value(
                word_id, primitive, constraint.value,
                source=f"audit:sources:{','.join(constraint.supporting_sources[:3])}",
                confidence=constraint.confidence
            )
            audit_log.log_decision(
                word_id, lemma, primitive, "auto_applied",
                old_value, constraint.value,
                {"supporting": constraint.supporting_sources},
                constraint.confidence
            )
            known_values[primitive] = constraint.value  # For bipolar inference
            stats['auto_applied'] += 1
            continue

        # === PRIORITY 2: Flag for review if sources conflict ===
        if constraint and constraint.status == "flag_review" and constraint.conflicting_sources:
            review.add(
                word_id, lemma, pos, primitive,
                old_value, constraint.value,
                nlp_constraints={"supporting": constraint.supporting_sources,
                                 "conflicting": constraint.conflicting_sources},
                conflict_type="source_disagreement",
                conflict_detail=f"Supporting: {constraint.supporting_sources}, Conflicting: {constraint.conflicting_sources}",
                confidence=constraint.confidence,
                priority=priority
            )
            audit_log.log_decision(
                word_id, lemma, primitive, "manual_required",
                old_value, constraint.value,
                {"supporting": constraint.supporting_sources,
                 "conflicting": constraint.conflicting_sources},
                constraint.confidence
            )
            stats['flagged_review'] += 1
            stats['conflicts'] += 1
            continue

        # === PRIORITY 3: Try rule-based inference (no LLM needed) ===
        inferred_value, method = infer_primitive_value(
            primitive, lemma, pos, known_values, source_has_data
        )

        if method in ("bipolar", "grammatical"):
            # Rule-based inference succeeded
            state.set_primitive_value(
                word_id, primitive, inferred_value,
                source=f"audit:rule:{method}",
                confidence=0.85 if method == "bipolar" else 0.9
            )
            audit_log.log_decision(
                word_id, lemma, primitive, f"rule_{method}",
                old_value, inferred_value,
                {"method": method},
                0.85 if method == "bipolar" else 0.9
            )
            known_values[primitive] = inferred_value
            stats['rule_inferred'] += 1
            continue

        # === PRIORITY 4: LLM translation (only if source has context) ===
        if method == "llm_needed" and ollama.is_available():
            throttle.throttle_before_ollama()

            # Format source context for LLM
            source_context = format_source_context(profile, primitive)

            # Query LLM with source context
            llm_value = ollama.query_primitive_with_context(
                lemma, pos, primitive, definition, source_context
            )

            throttle.throttle_after_ollama()

            if llm_value is not None:
                state.set_primitive_value(
                    word_id, primitive, llm_value,
                    source=f"audit:llm:{ollama.model}",
                    confidence=0.7
                )
                audit_log.log_decision(
                    word_id, lemma, primitive, "llm_assigned",
                    old_value, llm_value,
                    {"model": ollama.model, "source_context": source_context[:200]},
                    0.7
                )
                known_values[primitive] = llm_value
                stats['llm_assigned'] += 1
                continue

        # === PRIORITY 5: Default to neutral (no context to translate) ===
        # This is key: we don't call LLM with no context - that's guessing, not translating
        if inferred_value is not None:
            state.set_primitive_value(
                word_id, primitive, inferred_value,
                source=f"audit:default:{method}",
                confidence=0.3  # Low confidence for defaults
            )
            audit_log.log_decision(
                word_id, lemma, primitive, f"default_{method}",
                old_value, inferred_value,
                {"reason": "no source context to translate"},
                0.3
            )
            stats['defaulted'] += 1
        else:
            # Truly unknown - mark as 0 with very low confidence
            state.set_primitive_value(
                word_id, primitive, 0,
                source="audit:default:unknown",
                confidence=0.1
            )
            audit_log.log_decision(
                word_id, lemma, primitive, "default_unknown",
                old_value, 0,
                {"reason": "no source data, no rule, no LLM context"},
                0.1
            )
            stats['defaulted'] += 1

    logger.info(f"  Completed: auto={stats['auto_applied']}, rules={stats['rule_inferred']}, "
                f"llm={stats['llm_assigned']}, defaults={stats['defaulted']}, "
                f"review={stats['flagged_review']}, conflicts={stats['conflicts']}")

    return stats


def run_audit(test_mode: bool = False):
    """
    Main audit loop.

    Args:
        test_mode: If True, only process 10 words
    """
    global shutdown_requested

    logger.info("=" * 60)
    logger.info("GSE Lexicon Audit Daemon Starting")
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"Test mode: {test_mode}")
    logger.info("=" * 60)

    # Initialize components
    state = StateManager(DB_PATH)
    throttle = ThrottleManager(THROTTLE_CONFIG)
    ollama = OllamaClient(OLLAMA_CONFIG)  # LLM = translation layer
    review = ReviewQueue(DB_PATH)
    audit_log = AuditLogger(DB_PATH)

    # Verify LLM is available
    if not ollama.is_available():
        logger.error(f"LLM not available at {OLLAMA_CONFIG.get('base_url')}!")
        logger.error("The LLM is the translation layer - cannot proceed without it.")
        return

    # Load constraint aggregation engine
    engine = load_constraint_engine()

    # Get checkpoint
    checkpoint = state.get_checkpoint()
    last_word_id = checkpoint.get("last_word_id", 0)
    logger.info(f"Resuming from word_id={last_word_id}")

    words_processed = 0
    total_stats = {
        'auto_applied': 0,
        'flagged_review': 0,
        'rule_inferred': 0,
        'llm_assigned': 0,
        'defaulted': 0,
        'conflicts': 0,
    }

    max_words = 10 if test_mode else AUDIT_CONFIG["top_n_words"]
    batch_size = AUDIT_CONFIG["batch_size"]

    while not shutdown_requested:
        # Get next batch of words
        words = state.get_words_to_audit(
            resume_from=last_word_id,
            batch_size=batch_size,
            max_frequency_rank=max_words
        )

        if not words:
            if test_mode:
                logger.info("Test mode complete!")
                break
            else:
                logger.info("All words processed! Daemon sleeping...")
                time.sleep(3600)  # Sleep 1 hour, then check for new words
                continue

        for word in words:
            if shutdown_requested:
                break

            # Process word - LLM translates source data to primitives
            stats = process_word(
                word, engine, state, throttle, ollama, review, audit_log
            )

            # Update totals
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)

            # Update checkpoint
            last_word_id = word['id']
            words_processed += 1
            state.save_checkpoint(
                last_word_id,
                words_processed=1,
                primitives_audited=len(ALL_PRIMITIVES),
                auto_applied=stats['auto_applied'],
                flagged_review=stats['flagged_review'],
                conflicts_found=stats['conflicts'],
            )

            # Throttle between words
            throttle.throttle_between_words()

            # Check if we've hit test limit
            if test_mode and words_processed >= 10:
                break

        if test_mode and words_processed >= 10:
            break

    # Final summary
    logger.info("=" * 60)
    logger.info(f"Daemon stopped. Processed {words_processed} words this session.")
    logger.info(f"Total stats: {total_stats}")
    logger.info("=" * 60)

    # Clean up
    engine.close()
    state.set_checkpoint_status("paused" if shutdown_requested else "completed")
    state.close()
    review.close()
    audit_log.close()


def show_stats():
    """Show current audit statistics."""
    state = StateManager(DB_PATH)
    review = ReviewQueue(DB_PATH)
    audit_log = AuditLogger(DB_PATH)

    print("\n" + "=" * 60)
    print("GSE Lexicon Audit Statistics")
    print("=" * 60)

    # Checkpoint info
    checkpoint = state.get_checkpoint()
    print(f"\nCheckpoint:")
    print(f"  Status: {checkpoint.get('status', 'unknown')}")
    print(f"  Last word ID: {checkpoint.get('last_word_id', 0)}")
    print(f"  Total words processed: {checkpoint.get('total_words_processed', 0)}")
    print(f"  Total primitives audited: {checkpoint.get('total_primitives_audited', 0)}")
    print(f"  Auto-applied: {checkpoint.get('auto_applied', 0)}")
    print(f"  Flagged for review: {checkpoint.get('flagged_review', 0)}")
    print(f"  Conflicts found: {checkpoint.get('conflicts_found', 0)}")

    # Review queue stats
    review_stats = review.get_stats()
    print(f"\nReview Queue:")
    print(f"  Pending: {review_stats.get('total_pending', 0)}")
    print(f"  Resolved: {review_stats.get('total_resolved', 0)}")
    print(f"  By priority: {review_stats.get('by_priority', {})}")

    # Audit log stats
    log_stats = audit_log.get_summary()
    print(f"\nAudit Log:")
    print(f"  Total decisions: {log_stats.get('total_decisions', 0)}")
    print(f"  Unique words: {log_stats.get('unique_words', 0)}")
    print(f"  Last hour: {log_stats.get('recent_hour', 0)}")
    print(f"  By decision type: {log_stats.get('by_decision', {})}")

    print("\n" + "=" * 60)

    state.close()
    review.close()
    audit_log.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="GSE Lexicon Audit Daemon")
    parser.add_argument("--test", action="store_true", help="Test mode (10 words only)")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        run_audit(test_mode=args.test)


if __name__ == "__main__":
    main()
