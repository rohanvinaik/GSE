"""
Staged Lexicon Builder

Orchestrates the multi-phase lexicon building process:
- Phase 1: Core vocabulary (top 1000 words) - LLM + full validation
- Phase 2: Extended vocabulary (1001-3000) - LLM + lighter validation
- Phase 3: Expansion (3001+) - Rule-based + LLM spot-checks
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from gse.curation.frequency_integration import FrequencyDatabase, FrequencyIntegration
from gse.curation.lexicon_db import LexiconDatabase
from gse.curation.llm.batch_processor import BatchProcessor
from gse.curation.llm.ollama_client import OllamaClient
from gse.curation.llm.qwen_client import MockQwenClient

logger = logging.getLogger(__name__)


@dataclass
class BuildStats:
    """Statistics for a build phase."""

    phase: int
    words_total: int
    words_processed: int
    words_validated: int
    words_failed: int
    words_review: int
    duration_seconds: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class StagedBuilder:
    """
    Orchestrates the multi-phase lexicon building process.

    The builder manages:
    1. Frequency database integration (word prioritization)
    2. LLM decomposition (Qwen3-8B)
    3. Validation and quality control
    4. Checkpointing and resumption
    5. Progress tracking
    """

    def __init__(
        self,
        lexicon_db_path: str = "lexicon.db",
        frequency_db_path: Optional[str] = None,
        model_path: Optional[str] = None,
        use_mock_llm: bool = False,
    ):
        """
        Initialize the staged builder.

        Args:
            lexicon_db_path: Path to lexicon database
            frequency_db_path: Path to frequency database
            model_path: Path to Qwen model (optional, uses default)
            use_mock_llm: Use mock LLM for testing
        """
        self.lexicon_db = LexiconDatabase(lexicon_db_path)
        self.lexicon_db_path = lexicon_db_path

        # Set up frequency database
        if frequency_db_path:
            self.freq_db_path = frequency_db_path
        else:
            from gse.curation.frequency_integration import get_default_frequency_db_path

            self.freq_db_path = get_default_frequency_db_path()

        self.freq_db = FrequencyDatabase(self.freq_db_path)

        # Set up LLM - use Ollama for fast local inference
        if use_mock_llm:
            self.llm = MockQwenClient()
        else:
            self.llm = OllamaClient(model=model_path or "qwen2.5:7b")

        # Set up batch processor
        self.processor = BatchProcessor(self.lexicon_db, self.llm)

        # Track build stats
        self.stats: Dict[int, BuildStats] = {}

    def close(self):
        """Clean up resources."""
        self.lexicon_db.close()
        self.freq_db.close()
        self.llm.unload()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    def initialize_from_frequency(self, phases: Optional[List[int]] = None):
        """
        Populate lexicon database with words from frequency database.

        Args:
            phases: List of phases to initialize (default: all)
        """
        phases = phases or [1, 2, 3]
        integration = FrequencyIntegration(self.freq_db_path, self.lexicon_db_path)

        for phase in phases:
            if phase == 1:
                start_rank, end_rank = 1, 1000
            elif phase == 2:
                start_rank, end_rank = 1001, 3000
            else:
                start_rank, end_rank = 3001, None

            added = integration.populate_lexicon_from_frequency(
                start_rank=start_rank,
                end_rank=end_rank,
                phase=phase,
            )
            logger.info(f"Phase {phase}: Added {added} words from frequency database")

        integration.close()

    # =========================================================================
    # PHASE 1: CORE VOCABULARY
    # =========================================================================

    def build_phase_one(self, resume: bool = True) -> BuildStats:
        """
        Build Phase 1: Core vocabulary (top 1000 words).

        - Full LLM decomposition with Qwen3-8B
        - All validators run (bipolar, hierarchy, coverage)
        - Flag low-confidence (<0.7) for manual review
        - Target: 100% validated coverage
        """
        logger.info("=" * 60)
        logger.info("PHASE 1: Core Vocabulary (ranks 1-1000)")
        logger.info("=" * 60)

        started_at = datetime.now()

        # Ensure words are loaded
        count = self.lexicon_db.count_by_phase(1)
        if count["total"] == 0:
            logger.info("Initializing Phase 1 words from frequency database")
            self.initialize_from_frequency([1])
            count = self.lexicon_db.count_by_phase(1)

        logger.info(f"Words in Phase 1: {count['total']}")
        logger.info(f"Already validated: {count['validated']}")
        logger.info(f"Pending: {count['pending']}")

        # Load LLM
        logger.info("Loading LLM model...")
        self.llm.load()

        # Process
        result = self.processor.process_phase(1, resume=resume)

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        stats = BuildStats(
            phase=1,
            words_total=count["total"],
            words_processed=result["processed"],
            words_validated=result["validated"],
            words_failed=result["failed"],
            words_review=result.get("review_flagged", 0),
            duration_seconds=duration,
            started_at=started_at,
            completed_at=completed_at,
        )

        self.stats[1] = stats
        self._log_stats(stats)

        return stats

    # =========================================================================
    # PHASE 2: EXTENDED VOCABULARY
    # =========================================================================

    def build_phase_two(self, resume: bool = True) -> BuildStats:
        """
        Build Phase 2: Extended vocabulary (ranks 1001-3000).

        - LLM + morphological hints from Phase 1 patterns
        - 3 validators (skip antonym cosine for speed)
        - Lower review threshold (0.6)
        """
        logger.info("=" * 60)
        logger.info("PHASE 2: Extended Vocabulary (ranks 1001-3000)")
        logger.info("=" * 60)

        started_at = datetime.now()

        # Ensure Phase 1 is complete
        phase1_count = self.lexicon_db.count_by_phase(1)
        if phase1_count["validated"] < phase1_count["total"] * 0.8:
            logger.warning(
                f"Phase 1 only {phase1_count['validated']}/{phase1_count['total']} validated. "
                "Consider completing Phase 1 first."
            )

        # Ensure words are loaded
        count = self.lexicon_db.count_by_phase(2)
        if count["total"] == 0:
            logger.info("Initializing Phase 2 words from frequency database")
            self.initialize_from_frequency([2])
            count = self.lexicon_db.count_by_phase(2)

        logger.info(f"Words in Phase 2: {count['total']}")
        logger.info(f"Already validated: {count['validated']}")

        # Load LLM if needed
        self.llm.load()

        # Process
        result = self.processor.process_phase(2, resume=resume)

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        stats = BuildStats(
            phase=2,
            words_total=count["total"],
            words_processed=result["processed"],
            words_validated=result["validated"],
            words_failed=result["failed"],
            words_review=result.get("review_flagged", 0),
            duration_seconds=duration,
            started_at=started_at,
            completed_at=completed_at,
        )

        self.stats[2] = stats
        self._log_stats(stats)

        return stats

    # =========================================================================
    # PHASE 3: EXPANSION
    # =========================================================================

    def build_phase_three(self, resume: bool = True) -> BuildStats:
        """
        Build Phase 3: Expansion (ranks 3001+).

        - Rule-based morphology primary
        - LLM fallback for low-confidence
        - 10% random LLM spot-checks
        - Antonym inference from Phase 1/2
        """
        logger.info("=" * 60)
        logger.info("PHASE 3: Expansion (ranks 3001+)")
        logger.info("=" * 60)

        started_at = datetime.now()

        # Ensure words are loaded
        count = self.lexicon_db.count_by_phase(3)
        if count["total"] == 0:
            logger.info("Initializing Phase 3 words from frequency database")
            self.initialize_from_frequency([3])
            count = self.lexicon_db.count_by_phase(3)

        logger.info(f"Words in Phase 3: {count['total']}")
        logger.info(f"Already validated: {count['validated']}")

        # Load LLM for fallback
        self.llm.load()

        # Process
        result = self.processor.process_phase(3, resume=resume)

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        stats = BuildStats(
            phase=3,
            words_total=count["total"],
            words_processed=result["processed"],
            words_validated=result["validated"],
            words_failed=result["failed"],
            words_review=result.get("review_flagged", 0),
            duration_seconds=duration,
            started_at=started_at,
            completed_at=completed_at,
        )

        self.stats[3] = stats
        self._log_stats(stats)

        return stats

    # =========================================================================
    # BUILD ALL
    # =========================================================================

    def build_all(self, resume: bool = True) -> Dict[int, BuildStats]:
        """
        Build all phases sequentially.

        Returns:
            Dict mapping phase number to BuildStats
        """
        logger.info("Starting full lexicon build...")

        self.build_phase_one(resume=resume)
        self.build_phase_two(resume=resume)
        self.build_phase_three(resume=resume)

        return self.stats

    # =========================================================================
    # STATUS AND REPORTING
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get current build status across all phases."""
        status = {
            "phases": {},
            "total": {
                "words": 0,
                "validated": 0,
                "pending": 0,
                "rejected": 0,
            },
        }

        for phase in [1, 2, 3]:
            counts = self.lexicon_db.count_by_phase(phase)
            status["phases"][phase] = counts
            status["total"]["words"] += counts["total"]
            status["total"]["validated"] += counts["validated"]
            status["total"]["pending"] += counts["pending"]
            status["total"]["rejected"] += counts["rejected"]

        if status["total"]["words"] > 0:
            status["total"]["validation_rate"] = 100 * status["total"]["validated"] / status["total"]["words"]
        else:
            status["total"]["validation_rate"] = 0

        return status

    def _log_stats(self, stats: BuildStats):
        """Log build statistics."""
        logger.info("-" * 40)
        logger.info(f"Phase {stats.phase} Complete")
        logger.info(f"  Processed: {stats.words_processed}/{stats.words_total}")
        logger.info(f"  Validated: {stats.words_validated}")
        logger.info(f"  Failed: {stats.words_failed}")
        logger.info(f"  Flagged for review: {stats.words_review}")
        logger.info(f"  Duration: {stats.duration_seconds:.1f}s")

        if stats.words_processed > 0:
            rate = 100 * stats.words_validated / stats.words_processed
            logger.info(f"  Validation rate: {rate:.1f}%")
        logger.info("-" * 40)


# Convenience function
def build_lexicon(
    lexicon_db_path: str = "lexicon.db",
    frequency_db_path: Optional[str] = None,
    phases: Optional[List[int]] = None,
    resume: bool = True,
    use_mock: bool = False,
) -> Dict[str, Any]:
    """
    Build the GSE lexicon.

    Args:
        lexicon_db_path: Path to output lexicon database
        frequency_db_path: Path to frequency database
        phases: List of phases to build (default: all)
        resume: Resume from last checkpoint
        use_mock: Use mock LLM for testing

    Returns:
        Build status and statistics
    """
    phases = phases or [1, 2, 3]

    with StagedBuilder(
        lexicon_db_path=lexicon_db_path,
        frequency_db_path=frequency_db_path,
        use_mock_llm=use_mock,
    ) as builder:
        for phase in phases:
            if phase == 1:
                builder.build_phase_one(resume=resume)
            elif phase == 2:
                builder.build_phase_two(resume=resume)
            elif phase == 3:
                builder.build_phase_three(resume=resume)

        return builder.get_status()
