"""
Batch Processing Pipeline

Efficiently processes words in batches with checkpointing and progress tracking.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterator, List

from gse.curation.lexicon_db import LexiconDatabase
from gse.curation.llm.ollama_client import GenerationConfig
from gse.curation.llm.prompts import BATCH_CONFIG
from gse.curation.validation.bipolar_validator import BipolarValidator
from gse.curation.validation.coverage_checker import CoverageChecker
from gse.curation.validation.hierarchy_validator import HierarchyValidator

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a single word."""
    word: str
    success: bool
    decomposition: Dict[str, int]
    confidence: float
    validation_passed: bool
    validation_errors: List[str]
    warnings: List[str]


class BatchProcessor:
    """
    Efficient batch processing with checkpointing.

    Handles:
    - Batch decomposition with LLM
    - Validation after each batch
    - Checkpointing for resumption
    - Progress tracking
    """

    def __init__(
        self,
        db: LexiconDatabase,
        llm,  # OllamaClient or QwenClient
        checkpoint_interval: int = 50,
    ):
        """
        Initialize batch processor.

        Args:
            db: Lexicon database
            llm: LLM client
            checkpoint_interval: Save checkpoint every N words
        """
        self.db = db
        self.llm = llm
        self.checkpoint_interval = checkpoint_interval

        # Validators
        self.bipolar_validator = BipolarValidator()
        self.coverage_checker = CoverageChecker()
        self.hierarchy_validator = HierarchyValidator()

    def process_phase(
        self,
        phase: int,
        resume: bool = True,
    ) -> Dict[str, Any]:
        """
        Process all words for a phase.

        Args:
            phase: Build phase (1, 2, or 3)
            resume: Whether to resume from last checkpoint

        Returns:
            Dict with processing statistics
        """
        config = BATCH_CONFIG.get(f"phase_{phase}", BATCH_CONFIG["phase_1"])
        gen_config = GenerationConfig(
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
        )

        # Get resume point
        start_rank = 1
        if resume:
            checkpoint = self.db.get_last_checkpoint(phase)
            if checkpoint:
                start_rank = checkpoint["last_processed_rank"] + 1
                logger.info(f"Resuming phase {phase} from rank {start_rank}")

        # Get words to process
        rank_ranges = {1: (1, 1000), 2: (1001, 3000), 3: (3001, None)}
        min_rank, max_rank = rank_ranges.get(phase, (1, None))

        if start_rank < min_rank:
            start_rank = min_rank

        words = self.db.get_unprocessed_words(phase, start_rank=start_rank)
        logger.debug(f"Got {len(words)} unprocessed words from rank {start_rank}")

        if not words:
            logger.info(f"No unprocessed words for phase {phase}")
            return {"processed": 0, "validated": 0, "failed": 0}

        logger.info(f"Processing {len(words)} words for phase {phase}")
        logger.info(f"First 5 words: {[w.get('lemma', w) for w in words[:5]]}")

        stats = {
            "processed": 0,
            "validated": 0,
            "failed": 0,
            "review_flagged": 0,
            "start_time": datetime.now(),
        }

        # Process in batches
        batch_size = config["batch_size"]
        batch_num = 0
        for batch in self._chunk(words, batch_size):
            batch_num += 1
            logger.info(f"Processing batch {batch_num} ({len(batch)} words): {[w.get('lemma') for w in batch[:3]]}...")
            try:
                results = self._process_batch(batch, gen_config, config)

                for word_data, result in zip(batch, results):
                    self._store_result(word_data, result, phase, config)
                    stats["processed"] += 1

                    if result.validation_passed:
                        stats["validated"] += 1
                    else:
                        stats["failed"] += 1

                    if result.confidence < config["human_review_threshold"]:
                        stats["review_flagged"] += 1

                # Checkpoint
                if stats["processed"] % self.checkpoint_interval == 0:
                    last_rank = batch[-1].get("frequency_rank", 0)
                    self.db.checkpoint(
                        phase,
                        last_rank,
                        stats["processed"],
                        stats["validated"],
                    )
                    self._log_progress(stats, len(words), phase)

            except Exception as e:
                logger.error(f"Batch processing error: {e}")
                for word_data in batch:
                    stats["failed"] += 1

        stats["end_time"] = datetime.now()
        stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

        return stats

    def _process_batch(
        self,
        batch: List[Dict[str, Any]],
        gen_config: GenerationConfig,
        phase_config: Dict[str, Any],
    ) -> List[ProcessingResult]:
        """Process a single batch of words."""
        results = []

        # Prepare word data for LLM
        word_inputs = [
            {
                "word": w.get("lemma", w.get("word", "")),
                "pos": w.get("pos", "unknown"),
                "gloss": w.get("gloss"),
            }
            for w in batch
        ]

        # Get decompositions from LLM
        llm_results = self.llm.decompose_batch(word_inputs, config=gen_config)

        # Validate each result
        for word_data, (decomp, confidence, warnings) in zip(batch, llm_results):
            word = word_data.get("lemma", word_data.get("word", ""))

            # Run validators
            validation_errors = []

            bipolar_result = self.bipolar_validator.validate(decomp)
            if not bipolar_result.passed:
                validation_errors.extend(
                    [v["message"] for v in bipolar_result.violations]
                )
                # Auto-fix bipolar violations
                decomp, _ = self.bipolar_validator.fix_violations(decomp)

            coverage_result = self.coverage_checker.validate(decomp)
            if not coverage_result.passed:
                validation_errors.extend(
                    [v["message"] for v in coverage_result.violations]
                )
                # Auto-fill missing primitives
                decomp = self.coverage_checker.fill_missing(decomp)

            hierarchy_result = self.hierarchy_validator.validate(decomp)
            if not hierarchy_result.passed:
                validation_errors.extend(
                    [v.get("message", v.get("detail", "")) for v in hierarchy_result.violations]
                )

            validation_passed = (
                bipolar_result.passed and
                coverage_result.passed and
                hierarchy_result.passed
            )

            results.append(ProcessingResult(
                word=word,
                success=True,
                decomposition=decomp,
                confidence=confidence,
                validation_passed=validation_passed,
                validation_errors=validation_errors,
                warnings=warnings,
            ))

        return results

    def _store_result(
        self,
        word_data: Dict[str, Any],
        result: ProcessingResult,
        phase: int,
        config: Dict[str, Any],
    ):
        """Store processing result in database."""
        lexeme_id = word_data.get("id")

        if lexeme_id is None:
            # Word not in database yet, add it
            lexeme_id = self.db.add_lexeme(
                lemma=result.word,
                pos=word_data.get("pos", "unknown"),
                gloss=word_data.get("gloss"),
                source="llm",
                confidence=result.confidence,
                frequency_rank=word_data.get("frequency_rank"),
                frequency_weight=word_data.get("frequency_weight"),
                phase=phase,
            )

        # Store decomposition
        self.db.set_decomposition(
            lexeme_id,
            result.decomposition,
            source="llm",
        )

        # Determine validation status
        if result.validation_passed:
            if result.confidence >= config["human_review_threshold"]:
                status = "validated"
            else:
                status = "review"
        else:
            status = "pending"

        # Update lexeme
        self.db.update_lexeme(
            lexeme_id,
            validation_status=status,
            confidence=result.confidence,
        )

        # Store validation results
        for error in result.validation_errors:
            self.db.store_validation_result(
                lexeme_id,
                validation_type="decomposition",
                passed=False,
                details=error,
            )

        # Add provenance
        self.db.add_provenance(
            lexeme_id,
            source_type="llm",
            source_detail="qwen3-8b",
            confidence_after=result.confidence,
        )

    def _chunk(
        self,
        items: List[Any],
        size: int,
    ) -> Iterator[List[Any]]:
        """Yield successive chunks of items."""
        for i in range(0, len(items), size):
            yield items[i:i + size]

    def _log_progress(
        self,
        stats: Dict[str, Any],
        total: int,
        phase: int,
    ):
        """Log progress update."""
        processed = stats["processed"]
        validated = stats["validated"]
        pct = 100 * processed / total if total > 0 else 0

        logger.info(
            f"Phase {phase}: {processed}/{total} ({pct:.1f}%) - "
            f"Validated: {validated} ({100*validated/processed:.1f}%)"
        )
