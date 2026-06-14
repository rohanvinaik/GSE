"""
Hybrid Lexicon Builder

Uses a two-model approach for efficient and accurate primitive decomposition:
1. qwen2.5:7b - Fast model for quick YES/NO/OPPOSITE primitive matching
2. qwen3:32b - Thinking model for validation and correction of uncertain cases

Strategy:
1. Pre-populate from external sources (already done)
2. Fast pass: qwen2.5:7b fills missing primitives with simple prompts
3. Validation pass: qwen3:32b reviews low-confidence or conflicting values
"""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple

from gse.curation.llm.ollama_client import GenerationConfig, OllamaClient
from gse.curation.llm.primitive_matcher import (
    BIPOLAR_PAIRS as MATCHER_BIPOLAR_PAIRS,
)
from gse.curation.llm.primitive_matcher import (
    MATCHER_SYSTEM,
    SINGLE_PRIMITIVES,
    get_bipolar_prompt,
    get_single_prompt,
)
from gse.curation.schema import ALL_PRIMITIVES

logger = logging.getLogger(__name__)


@dataclass
class BuilderStats:
    """Statistics for the hybrid builder."""
    words_processed: int = 0
    primitives_fast_filled: int = 0
    primitives_validated: int = 0
    primitives_corrected: int = 0
    validation_skipped: int = 0
    errors: int = 0

    def __str__(self):
        return (
            f"Processed: {self.words_processed} words | "
            f"Fast-filled: {self.primitives_fast_filled} | "
            f"Validated: {self.primitives_validated} | "
            f"Corrected: {self.primitives_corrected}"
        )


class HybridLexiconBuilder:
    """
    Two-stage lexicon builder for efficient primitive decomposition.

    Stage 1 (Fast): qwen2.5:7b answers simple YES/NO questions
    Stage 2 (Validate): qwen3:32b reviews uncertain cases with reasoning
    """

    def __init__(
        self,
        db_path: str,
        fast_model: str = "qwen2.5:7b",
        validator_model: str = "qwen3:32b",
        validation_threshold: float = 0.6,  # Below this, send to validator
    ):
        self.db_path = db_path
        self.fast_model = fast_model
        self.validator_model = validator_model
        self.validation_threshold = validation_threshold

        # Initialize clients
        logger.info(f"Initializing fast model: {fast_model}")
        self.fast_client = OllamaClient(model=fast_model)
        self.fast_config = GenerationConfig(
            temperature=0.1,
            max_tokens=20,
        )

        logger.info(f"Initializing validator model: {validator_model}")
        self.validator_client = OllamaClient(model=validator_model)
        self.validator_config = GenerationConfig(
            temperature=0.3,
            max_tokens=200,
        )

        self.conn = sqlite3.connect(db_path)
        self.stats = BuilderStats()

    # =========================================================================
    # STAGE 1: FAST MATCHING WITH qwen2.5:7b
    # =========================================================================

    def fast_match_bipolar(
        self,
        word: str,
        pole_a: str,
        pole_b: str,
    ) -> Tuple[int, int, float]:
        """
        Fast bipolar matching with confidence estimation.

        Returns: (value_a, value_b, confidence)
        """
        prompt = get_bipolar_prompt(word, pole_a, pole_b)

        try:
            response = self.fast_client.generate(
                prompt=prompt,
                system_prompt=MATCHER_SYSTEM,
                config=self.fast_config,
            ).strip().upper()

            # Parse with confidence based on response clarity
            if response.startswith('A') or f"({pole_a}" in response:
                return (1, 0, 0.8)
            elif response.startswith('B') or f"({pole_b}" in response:
                return (0, 1, 0.8)
            elif 'NEITHER' in response or response.startswith('C'):
                return (0, 0, 0.9)  # High confidence for "neither"
            else:
                # Ambiguous response - lower confidence
                if pole_a.upper() in response:
                    return (1, 0, 0.5)
                elif pole_b.upper() in response:
                    return (0, 1, 0.5)
                return (0, 0, 0.4)  # Very uncertain

        except Exception as e:
            logger.warning(f"Fast bipolar match failed for {word}/{pole_a}: {e}")
            self.stats.errors += 1
            return (0, 0, 0.0)

    def fast_match_single(
        self,
        word: str,
        primitive: str,
    ) -> Tuple[int, float]:
        """
        Fast single primitive matching with confidence.

        Returns: (value, confidence)
        """
        prompt = get_single_prompt(word, primitive)

        try:
            response = self.fast_client.generate(
                prompt=prompt,
                system_prompt=MATCHER_SYSTEM,
                config=self.fast_config,
            ).strip().upper()

            if response.startswith('YES') or response == 'Y':
                return (1, 0.8)
            elif 'OPPOSITE' in response or 'OPP' in response:
                return (-1, 0.75)
            elif response.startswith('NO') or response == 'N':
                return (0, 0.85)
            else:
                # Ambiguous
                if 'YES' in response:
                    return (1, 0.5)
                elif 'NO' in response:
                    return (0, 0.5)
                return (0, 0.3)

        except Exception as e:
            logger.warning(f"Fast single match failed for {word}/{primitive}: {e}")
            self.stats.errors += 1
            return (0, 0.0)

    def fast_decompose(
        self,
        word: str,
        missing_primitives: Set[str],
    ) -> Dict[str, Tuple[int, float]]:
        """
        Fast decomposition of missing primitives.

        Returns: Dict of primitive -> (value, confidence)
        """
        results = {}

        # Process bipolar pairs
        for pole_a, pole_b in MATCHER_BIPOLAR_PAIRS:
            if pole_a in missing_primitives or pole_b in missing_primitives:
                val_a, val_b, conf = self.fast_match_bipolar(word, pole_a, pole_b)

                if pole_a in missing_primitives:
                    results[pole_a] = (val_a, conf)
                if pole_b in missing_primitives:
                    results[pole_b] = (val_b, conf)

                if val_a or val_b:
                    self.stats.primitives_fast_filled += 1

        # Process single primitives
        for prim in SINGLE_PRIMITIVES:
            if prim in missing_primitives:
                val, conf = self.fast_match_single(word, prim)
                results[prim] = (val, conf)

                if val:
                    self.stats.primitives_fast_filled += 1

        return results

    # =========================================================================
    # STAGE 2: VALIDATION WITH qwen3:32b
    # =========================================================================

    VALIDATION_PROMPT = """Review these primitive assignments for the word "{word}":

{assignments}

For each assignment, indicate if it's:
- CORRECT: The assignment is accurate
- WRONG: Should be different (specify correct value: +1, 0, or -1)
- UNCERTAIN: Cannot determine

Focus on semantic accuracy. Consider the word's core meaning.

Return JSON: {{"PRIMITIVE": "CORRECT|WRONG:new_value|UNCERTAIN", ...}}"""

    def validate_decomposition(
        self,
        word: str,
        primitives: Dict[str, Tuple[int, float]],
    ) -> Dict[str, int]:
        """
        Validate low-confidence primitives with the thinking model.

        Returns: Dict of corrected primitive values
        """
        # Filter to low-confidence assignments
        to_validate = {
            p: v for p, (v, conf) in primitives.items()
            if conf < self.validation_threshold and v != 0
        }

        if not to_validate:
            self.stats.validation_skipped += len(primitives)
            return {p: v for p, (v, _) in primitives.items()}

        # Format assignments for review
        assignments = "\n".join(
            f"- {prim}: {'+1' if val > 0 else '-1' if val < 0 else '0'}"
            for prim, val in to_validate.items()
        )

        prompt = self.VALIDATION_PROMPT.format(word=word, assignments=assignments)

        try:
            response = self.validator_client.generate(
                prompt=prompt,
                system_prompt="You are a semantic primitive expert. Be precise and concise.",
                config=self.validator_config,
            )

            # Parse JSON from response
            import re
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                corrections = json.loads(json_match.group())

                # Apply corrections
                result = {p: v for p, (v, _) in primitives.items()}

                for prim, judgment in corrections.items():
                    if prim in result:
                        self.stats.primitives_validated += 1

                        if judgment == "CORRECT":
                            pass  # Keep as-is
                        elif judgment.startswith("WRONG:"):
                            try:
                                new_val = int(judgment.split(":")[1])
                                if result[prim] != new_val:
                                    result[prim] = new_val
                                    self.stats.primitives_corrected += 1
                            except ValueError:
                                pass

                return result

        except Exception as e:
            logger.warning(f"Validation failed for {word}: {e}")
            self.stats.errors += 1

        # Fallback: return original values
        return {p: v for p, (v, _) in primitives.items()}

    # =========================================================================
    # MAIN PIPELINE
    # =========================================================================

    def get_missing_primitives(self, lexeme_id: int) -> Set[str]:
        """Get primitives not yet filled for a lexeme."""
        cursor = self.conn.execute(
            "SELECT primitive FROM primitive_values WHERE lexeme_id = ?",
            (lexeme_id,)
        )
        filled = {row[0] for row in cursor.fetchall()}
        return set(ALL_PRIMITIVES) - filled

    def process_word(
        self,
        lexeme_id: int,
        lemma: str,
        validate: bool = True,
    ) -> Dict[str, int]:
        """
        Full hybrid processing of a single word.

        1. Get missing primitives
        2. Fast-fill with qwen2.5:7b
        3. Validate uncertain ones with qwen3:32b
        4. Store results
        """
        missing = self.get_missing_primitives(lexeme_id)

        if not missing:
            logger.debug(f"{lemma}: all primitives already filled")
            return {}

        # Stage 1: Fast decomposition
        fast_results = self.fast_decompose(lemma, missing)

        # Stage 2: Validation (if enabled)
        if validate:
            final_results = self.validate_decomposition(lemma, fast_results)
        else:
            final_results = {p: v for p, (v, _) in fast_results.items()}

        # Store results
        for prim, value in final_results.items():
            conf = fast_results.get(prim, (0, 0.5))[1]
            self.conn.execute("""
                INSERT OR REPLACE INTO primitive_values
                (lexeme_id, primitive, value, confidence, source)
                VALUES (?, ?, ?, ?, ?)
            """, (lexeme_id, prim, value, conf, f"hybrid:{self.fast_model}+{self.validator_model}"))

        self.conn.commit()
        self.stats.words_processed += 1

        return final_results

    def process_batch(
        self,
        limit: Optional[int] = None,
        validate: bool = True,
        min_missing: int = 10,  # Only process words with this many missing primitives
    ) -> BuilderStats:
        """
        Process a batch of words with the hybrid approach.

        Args:
            limit: Maximum words to process
            validate: Whether to run validation pass
            min_missing: Minimum missing primitives to bother processing
        """
        # Get words with missing primitives
        cursor = self.conn.execute("""
            SELECT l.id, l.lemma, 72 - COUNT(p.id) as missing_count
            FROM lexemes l
            LEFT JOIN primitive_values p ON l.id = p.lexeme_id
            GROUP BY l.id
            HAVING missing_count >= ?
            ORDER BY l.frequency_rank NULLS LAST
        """, (min_missing,))

        words = cursor.fetchall()
        if limit:
            words = words[:limit]

        logger.info(f"Processing {len(words)} words with hybrid approach...")
        logger.info(f"Fast model: {self.fast_model}, Validator: {self.validator_model}")

        start_time = time.time()

        for i, (lex_id, lemma, missing_count) in enumerate(words):
            try:
                self.process_word(lex_id, lemma, validate=validate)

                if (i + 1) % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed
                    logger.info(
                        f"Progress: {i + 1}/{len(words)} ({rate:.1f} words/sec) - "
                        f"{lemma} | {self.stats}"
                    )

            except Exception as e:
                logger.error(f"Failed to process {lemma}: {e}")
                self.stats.errors += 1

        return self.stats

    def close(self):
        self.conn.close()


def main():
    """Run the hybrid lexicon builder."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(description="Hybrid Lexicon Builder")
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument("--fast-model", default="qwen2.5:7b", help="Fast model for matching")
    parser.add_argument("--validator-model", default="qwen3:32b", help="Validator model")
    parser.add_argument("--limit", type=int, help="Max words to process")
    parser.add_argument("--no-validate", action="store_true", help="Skip validation pass")
    parser.add_argument("--word", help="Process single word")
    parser.add_argument("--min-missing", type=int, default=10, help="Min missing primitives")

    args = parser.parse_args()

    builder = HybridLexiconBuilder(
        db_path=args.db,
        fast_model=args.fast_model,
        validator_model=args.validator_model,
    )

    try:
        if args.word:
            # Process single word
            cursor = builder.conn.execute(
                "SELECT id FROM lexemes WHERE lemma = ?", (args.word,)
            )
            row = cursor.fetchone()
            if row:
                result = builder.process_word(row[0], args.word, validate=not args.no_validate)
                print(f"\n=== {args.word} ===")
                active = {k: v for k, v in result.items() if v != 0}
                print(f"Active primitives: {active}")
                print(f"\nStats: {builder.stats}")
            else:
                print(f"Word not found: {args.word}")
        else:
            # Process batch
            stats = builder.process_batch(
                limit=args.limit,
                validate=not args.no_validate,
                min_missing=args.min_missing,
            )

            print("\n" + "="*50)
            print("HYBRID BUILD COMPLETE")
            print("="*50)
            print(f"Words processed: {stats.words_processed}")
            print(f"Primitives fast-filled: {stats.primitives_fast_filled}")
            print(f"Primitives validated: {stats.primitives_validated}")
            print(f"Primitives corrected: {stats.primitives_corrected}")
            print(f"Errors: {stats.errors}")

    finally:
        builder.close()


if __name__ == "__main__":
    main()
