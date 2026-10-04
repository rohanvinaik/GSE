"""
Primitive-by-Primitive Matcher

Ultra-granular approach: one primitive (or bipolar pair) per prompt.
Much simpler for LLM - just a single similarity judgment.

Strategy:
1. Bipolar pairs: "For WORD: GOOD, BAD, or neither?"
2. Single primitives: "Does WORD involve PRIMITIVE?" → yes/no/opposite
3. Batch post-processing for common-sense fixes
"""

import logging
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Tuple

from gse.curation.llm.ollama_client import GenerationConfig, OllamaClient

logger = logging.getLogger(__name__)


# 14 bipolar pairs - ask as single question
BIPOLAR_PAIRS = [
    ("GOOD", "BAD"),
    ("BIG", "SMALL"),
    ("SAME", "OTHER"),
    ("ALIVE", "DEAD"),
    ("LONG_TIME", "SHORT_TIME"),
    ("BEFORE", "AFTER"),
    ("THEN", "NOW"),
    ("START", "END"),
    ("ABOVE", "BELOW"),
    ("FAR", "NEAR"),
    ("OUTSIDE", "INSIDE"),
    ("TOWARD", "AWAY"),
    ("WITH", "WITHOUT"),
    ("TRUE", "FALSE"),
]

# All primitives not in bipolar pairs
SINGLE_PRIMITIVES = [
    "I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY", "KIND", "PART",
    "ONE", "TWO", "QUANTITY",
    "THINK", "KNOW", "WANT", "FEEL", "SEE", "HEAR", "INFER",
    "SAY", "WORDS", "DO", "HAPPEN", "MOVE", "BE", "HAVE", "EXIST",
    "MOMENT", "WHEN", "WHERE", "HERE", "SIDE", "TOUCH",
    "NOT", "MAYBE", "CAN", "MUST", "BECAUSE", "CAUSE", "IF", "LIKE",
    "HIER_PLUS", "HIER_MINUS", "INTENSITY", "CERTAINTY",
]


def get_bipolar_prompt(word: str, pole_a: str, pole_b: str) -> str:
    """Simple bipolar question."""
    return f"""Word: "{word}"

Which applies? Answer with just the letter:
A) {pole_a} - the word leans toward {pole_a}
B) {pole_b} - the word leans toward {pole_b}
C) Neither - not relevant to this word

Answer:"""


def get_single_prompt(word: str, primitive: str) -> str:
    """Simple single primitive question."""
    return f"""Word: "{word}"
Primitive: {primitive}

Does this word's meaning involve {primitive}?
Answer with just: YES, NO, or OPPOSITE

Answer:"""


MATCHER_SYSTEM = """You are matching words to semantic primitives.
Give brief, direct answers. No explanation needed."""


@dataclass
class MatchResult:
    """Result from primitive matching."""
    word: str
    primitive: str
    value: int  # +1, 0, or -1
    raw_response: str


class PrimitiveMatcher:
    """
    Match words to primitives one at a time.

    Much simpler than batch decomposition - just similarity judgments.
    Uses qwen2.5:7b for fast direct answers.
    """

    def __init__(
        self,
        model: str = "qwen2.5:7b",  # Fast model for simple YES/NO
        temperature: float = 0.1,  # Low temp for consistent answers
        timeout: int = 30,  # Short timeout for simple questions
        db_path: str = None,  # Optional database for batch operations
    ):
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.db_path = db_path
        self.client = OllamaClient(model=model)
        self.config = GenerationConfig(
            temperature=temperature,
            max_tokens=20,  # Very short responses
        )
        self.conn = None
        if db_path:
            self.conn = sqlite3.connect(db_path)

    def match_bipolar(
        self,
        word: str,
        pole_a: str,
        pole_b: str,
    ) -> Tuple[int, int]:
        """
        Match word against bipolar pair.

        Returns:
            (value_a, value_b) where exactly one is non-zero or both are 0
        """
        prompt = get_bipolar_prompt(word, pole_a, pole_b)

        try:
            response = self.client.generate(
                prompt=prompt,
                system_prompt=MATCHER_SYSTEM,
                config=self.config,
            ).strip().upper()

            # Parse response
            if 'A' in response[:5] or pole_a.upper() in response:
                return (1, 0)
            elif 'B' in response[:5] or pole_b.upper() in response:
                return (0, 1)
            else:
                return (0, 0)

        except Exception as e:
            logger.warning(f"Bipolar match failed for {word}/{pole_a}: {e}")
            return (0, 0)

    def match_single(self, word: str, primitive: str) -> int:
        """
        Match word against single primitive.

        Returns:
            +1 (yes), -1 (opposite), or 0 (no/not relevant)
        """
        prompt = get_single_prompt(word, primitive)

        try:
            response = self.client.generate(
                prompt=prompt,
                system_prompt=MATCHER_SYSTEM,
                config=self.config,
            ).strip().upper()

            if 'YES' in response:
                return 1
            elif 'OPPOSITE' in response or 'OPP' in response:
                return -1
            else:
                return 0

        except Exception as e:
            logger.warning(f"Single match failed for {word}/{primitive}: {e}")
            return 0

    def decompose_word(self, word: str) -> Dict[str, int]:
        """
        Full decomposition via primitive-by-primitive matching.

        Makes 14 bipolar + ~44 single = ~58 LLM calls per word.
        Each call is very fast (short prompt, short response).
        """
        result = {}

        # Bipolar pairs first (14 calls)
        for pole_a, pole_b in BIPOLAR_PAIRS:
            val_a, val_b = self.match_bipolar(word, pole_a, pole_b)
            result[pole_a] = val_a
            result[pole_b] = val_b

            if val_a or val_b:
                logger.debug(f"{word}: {pole_a}={val_a}, {pole_b}={val_b}")

        # Single primitives (~44 calls)
        for prim in SINGLE_PRIMITIVES:
            val = self.match_single(word, prim)
            result[prim] = val

            if val:
                logger.debug(f"{word}: {prim}={val}")

        return result

    def decompose_word_fast(
        self,
        word: str,
        skip_zeros: bool = True,
    ) -> Dict[str, int]:
        """
        Fast decomposition - only return non-zero values.

        Uses early termination and skips unlikely primitives.
        """
        result = {}

        # Priority primitives for quick semantic fingerprint
        priority_bipolars = [
            ("GOOD", "BAD"),
            ("BIG", "SMALL"),
            ("ALIVE", "DEAD"),
        ]

        priority_singles = [
            "FEEL", "THINK", "WANT", "DO", "MOVE", "SAY",
            "BODY", "PEOPLE", "SOMEONE", "SOMETHING",
        ]

        # Check priority bipolars
        for pole_a, pole_b in priority_bipolars:
            val_a, val_b = self.match_bipolar(word, pole_a, pole_b)
            if val_a: result[pole_a] = val_a
            if val_b: result[pole_b] = val_b

        # Check priority singles
        for prim in priority_singles:
            val = self.match_single(word, prim)
            if val: result[prim] = val

        # Fill remaining if needed
        if not skip_zeros:
            for pole_a, pole_b in BIPOLAR_PAIRS:
                if pole_a not in result:
                    val_a, val_b = self.match_bipolar(word, pole_a, pole_b)
                    result[pole_a] = val_a
                    result[pole_b] = val_b

            for prim in SINGLE_PRIMITIVES:
                if prim not in result:
                    result[prim] = self.match_single(word, prim)

        return result


    def get_missing_primitives(self, lexeme_id: int) -> List[str]:
        """Get primitives not yet filled for a lexeme."""
        if not self.conn:
            return list(set(p for pair in BIPOLAR_PAIRS for p in pair) | set(SINGLE_PRIMITIVES))

        cursor = self.conn.execute(
            "SELECT primitive FROM primitive_values WHERE lexeme_id = ?",
            (lexeme_id,)
        )
        filled = {row[0] for row in cursor.fetchall()}
        all_prims = set(p for pair in BIPOLAR_PAIRS for p in pair) | set(SINGLE_PRIMITIVES)
        return [p for p in all_prims if p not in filled]

    def process_word_to_db(
        self,
        lexeme_id: int,
        lemma: str,
        skip_filled: bool = True,
    ) -> Dict[str, int]:
        """
        Process a single word and store results in database.
        """
        if not self.conn:
            raise ValueError("Database connection required for process_word_to_db")

        if skip_filled:
            missing = set(self.get_missing_primitives(lexeme_id))
        else:
            missing = set(p for pair in BIPOLAR_PAIRS for p in pair) | set(SINGLE_PRIMITIVES)

        result = {}

        # Bipolar pairs
        for pole_a, pole_b in BIPOLAR_PAIRS:
            if pole_a in missing or pole_b in missing:
                val_a, val_b = self.match_bipolar(lemma, pole_a, pole_b)
                if pole_a in missing:
                    result[pole_a] = val_a
                if pole_b in missing:
                    result[pole_b] = val_b

        # Single primitives
        for prim in SINGLE_PRIMITIVES:
            if prim in missing:
                result[prim] = self.match_single(lemma, prim)

        # Store in database
        for prim, value in result.items():
            self.conn.execute("""
                INSERT OR REPLACE INTO primitive_values
                (lexeme_id, primitive, value, confidence, source)
                VALUES (?, ?, ?, ?, ?)
            """, (lexeme_id, prim, value, 0.7, f"llm:{self.model}"))

        self.conn.commit()
        return result

    def process_batch(
        self,
        limit: int = None,
        min_missing: int = 10,
    ) -> Dict[str, int]:
        """
        Process words with missing primitives.

        Args:
            limit: Max words to process
            min_missing: Minimum missing primitives to bother processing

        Returns:
            Stats dict
        """
        if not self.conn:
            raise ValueError("Database connection required for batch processing")

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

        logger.info(f"Processing {len(words)} words with primitive matcher ({self.model})...")

        stats = {"processed": 0, "primitives_filled": 0, "errors": 0}
        import time
        start_time = time.time()

        for i, (lex_id, lemma, missing_count) in enumerate(words):
            try:
                result = self.process_word_to_db(lex_id, lemma)
                stats["processed"] += 1
                stats["primitives_filled"] += sum(1 for v in result.values() if v != 0)

                if (i + 1) % 5 == 0:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed
                    logger.info(
                        f"Progress: {i + 1}/{len(words)} ({rate:.2f}/sec) - {lemma}"
                    )

            except Exception as e:
                logger.error(f"Failed to process {lemma}: {e}")
                stats["errors"] += 1

        return stats

    def close(self):
        if self.conn:
            self.conn.close()


# =============================================================================
# COMMON-SENSE POST-PROCESSOR
# =============================================================================

class CommonSensePostProcessor:
    """
    Apply common-sense fixes to the database after LLM processing.

    Fixes:
    1. Bipolar violations (both poles non-zero)
    2. Obvious semantic rules (e.g., verbs should have DO/HAPPEN)
    3. Consistency across word forms
    """

    BIPOLAR_PAIRS_LIST = [
        ("GOOD", "BAD"),
        ("BIG", "SMALL"),
        ("SAME", "OTHER"),
        ("ALIVE", "DEAD"),
        ("LONG_TIME", "SHORT_TIME"),
        ("BEFORE", "AFTER"),
        ("THEN", "NOW"),
        ("START", "END"),
        ("ABOVE", "BELOW"),
        ("FAR", "NEAR"),
        ("OUTSIDE", "INSIDE"),
        ("TOWARD", "AWAY"),
        ("WITH", "WITHOUT"),
        ("TRUE", "FALSE"),
    ]

    # POS-based rules: verbs typically have these primitives
    POS_RULES = {
        "v": {"likely": ["DO", "HAPPEN"], "unlikely": []},
        "n": {"likely": ["SOMETHING"], "unlikely": []},
        "adj": {"likely": [], "unlikely": ["DO", "HAPPEN"]},
    }

    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)

    def fix_bipolar_violations(self) -> int:
        """
        Fix cases where both poles of a bipolar pair are non-zero.
        Keep the one with higher confidence, or the positive one if tied.
        """
        fixed = 0

        for pole_a, pole_b in self.BIPOLAR_PAIRS_LIST:
            # Find violations
            cursor = self.conn.execute("""
                SELECT pa.lexeme_id, pa.value as val_a, pa.confidence as conf_a,
                       pb.value as val_b, pb.confidence as conf_b
                FROM primitive_values pa
                JOIN primitive_values pb ON pa.lexeme_id = pb.lexeme_id
                WHERE pa.primitive = ? AND pb.primitive = ?
                AND pa.value != 0 AND pb.value != 0
            """, (pole_a, pole_b))

            violations = cursor.fetchall()

            for lex_id, val_a, conf_a, val_b, conf_b in violations:
                # Decide which to keep (higher confidence wins)
                if conf_a > conf_b:
                    # Zero out pole_b
                    self.conn.execute("""
                        UPDATE primitive_values SET value = 0
                        WHERE lexeme_id = ? AND primitive = ?
                    """, (lex_id, pole_b))
                else:
                    # Zero out pole_a
                    self.conn.execute("""
                        UPDATE primitive_values SET value = 0
                        WHERE lexeme_id = ? AND primitive = ?
                    """, (lex_id, pole_a))
                fixed += 1

        self.conn.commit()
        return fixed

    def apply_pos_rules(self) -> int:
        """Apply POS-based common-sense rules."""
        updated = 0

        for pos, rules in self.POS_RULES.items():
            # Get lexemes with this POS
            cursor = self.conn.execute(
                "SELECT id FROM lexemes WHERE pos = ?", (pos,)
            )
            lex_ids = [row[0] for row in cursor.fetchall()]

            for lex_id in lex_ids:
                # Check unlikely primitives - if they're set but shouldn't be
                for prim in rules.get("unlikely", []):
                    cursor = self.conn.execute("""
                        SELECT value, confidence FROM primitive_values
                        WHERE lexeme_id = ? AND primitive = ?
                    """, (lex_id, prim))
                    row = cursor.fetchone()

                    if row and row[0] != 0 and row[1] < 0.8:
                        # Low confidence + unlikely = zero it out
                        self.conn.execute("""
                            UPDATE primitive_values SET value = 0
                            WHERE lexeme_id = ? AND primitive = ?
                        """, (lex_id, prim))
                        updated += 1

        self.conn.commit()
        return updated

    def run_all(self) -> Dict[str, int]:
        """Run all post-processing fixes."""
        stats = {
            "bipolar_fixed": self.fix_bipolar_violations(),
            "pos_rules_applied": self.apply_pos_rules(),
        }
        logger.info(f"Post-processing complete: {stats}")
        return stats

    def close(self):
        self.conn.close()


def test_matcher():
    """Quick test of the primitive matcher."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Use qwen2.5:7b for fast testing
    matcher = PrimitiveMatcher(model="qwen2.5:7b")

    test_words = ["love", "hate", "run", "think", "big", "small"]

    for word in test_words:
        print(f"\n=== {word} ===")

        # Just test a few key primitives
        for pole_a, pole_b in [("GOOD", "BAD"), ("BIG", "SMALL")]:
            val_a, val_b = matcher.match_bipolar(word, pole_a, pole_b)
            if val_a or val_b:
                print(f"  {pole_a}/{pole_b}: {val_a}/{val_b}")

        for prim in ["FEEL", "THINK", "MOVE", "BODY"]:
            val = matcher.match_single(word, prim)
            if val:
                print(f"  {prim}: {val}")


def run_batch():
    """Run batch processing on the lexicon."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(description="Primitive Matcher Batch Processing")
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument("--model", default="qwen2.5:7b", help="Model to use")
    parser.add_argument("--limit", type=int, help="Max words to process")
    parser.add_argument("--min-missing", type=int, default=10, help="Min missing primitives")
    parser.add_argument("--post-process", action="store_true", help="Run post-processing")

    args = parser.parse_args()

    matcher = PrimitiveMatcher(model=args.model, db_path=args.db)

    try:
        stats = matcher.process_batch(limit=args.limit, min_missing=args.min_missing)
        print("\n=== Batch Complete ===")
        print(f"Processed: {stats['processed']}")
        print(f"Primitives filled: {stats['primitives_filled']}")
        print(f"Errors: {stats['errors']}")

        if args.post_process:
            print("\n=== Running Post-Processing ===")
            processor = CommonSensePostProcessor(args.db)
            post_stats = processor.run_all()
            print(f"Bipolar fixes: {post_stats['bipolar_fixed']}")
            print(f"POS rules: {post_stats['pos_rules_applied']}")
            processor.close()

    finally:
        matcher.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        sys.argv.pop(1)  # Remove --batch flag
        run_batch()
    else:
        test_matcher()
