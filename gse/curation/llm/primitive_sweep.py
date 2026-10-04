"""
Primitive Sweep

Goes primitive-by-primitive across all words (instead of word-by-word).
Much faster: batch words per primitive prompt.

For 1000 words × 58 primitives:
- Word-first: 58,000 calls (58 per word)
- Primitive-first with batching: ~580 calls (10 words per prompt)
"""

import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

from gse.curation.llm.ollama_client import GenerationConfig, OllamaClient

logger = logging.getLogger(__name__)


# 14 bipolar pairs
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

# Single primitives (not in bipolar pairs)
SINGLE_PRIMITIVES = [
    "I",
    "YOU",
    "SOMEONE",
    "SOMETHING",
    "PEOPLE",
    "BODY",
    "KIND",
    "PART",
    "ONE",
    "TWO",
    "QUANTITY",
    "THINK",
    "KNOW",
    "WANT",
    "FEEL",
    "SEE",
    "HEAR",
    "INFER",
    "SAY",
    "WORDS",
    "DO",
    "HAPPEN",
    "MOVE",
    "BE",
    "HAVE",
    "EXIST",
    "MOMENT",
    "WHEN",
    "WHERE",
    "HERE",
    "SIDE",
    "TOUCH",
    "NOT",
    "MAYBE",
    "CAN",
    "MUST",
    "BECAUSE",
    "CAUSE",
    "IF",
    "LIKE",
    "HIER_PLUS",
    "HIER_MINUS",
    "INTENSITY",
    "CERTAINTY",
]


SYSTEM_PROMPT = """You are matching words to semantic primitives.
Give brief, direct answers. Format: WORD: ANSWER"""


def get_bipolar_batch_prompt(words: List[str], pole_a: str, pole_b: str) -> str:
    """Prompt for batch of words against a bipolar pair."""
    word_list = ", ".join(words)
    return f"""For each word, which applies?
A = {pole_a} (leans toward {pole_a})
B = {pole_b} (leans toward {pole_b})
N = Neither (not relevant)

Words: {word_list}

Answer each as "word: A/B/N" on separate lines:"""


def get_single_batch_prompt(words: List[str], primitive: str) -> str:
    """Prompt for batch of words against a single primitive."""
    word_list = ", ".join(words)
    return f"""Does each word's meaning involve {primitive}?
Y = Yes (involves {primitive})
N = No (not relevant)
O = Opposite (involves the opposite of {primitive})

Words: {word_list}

Answer each as "word: Y/N/O" on separate lines:"""


@dataclass
class SweepStats:
    """Statistics for the sweep."""

    primitives_processed: int = 0
    words_processed: int = 0
    values_set: int = 0
    errors: int = 0

    def __str__(self):
        return f"Prims: {self.primitives_processed} | Words: {self.words_processed} | Set: {self.values_set}"


class PrimitiveSweep:
    """
    Sweep through primitives, batching words per prompt.
    """

    def __init__(
        self,
        db_path: str,
        model: str = "qwen2.5:7b",
        batch_size: int = 20,  # Words per prompt
    ):
        self.db_path = db_path
        self.model = model
        self.batch_size = batch_size

        self.client = OllamaClient(model=model)
        self.config = GenerationConfig(
            temperature=0.1,
            max_tokens=500,  # Room for batch responses
        )
        self.conn = sqlite3.connect(db_path)
        self.stats = SweepStats()

    def get_top_words(self, limit: int = 1000) -> List[Tuple[int, str]]:
        """Get top N words by frequency rank."""
        cursor = self.conn.execute(
            """
            SELECT id, lemma FROM lexemes
            WHERE frequency_rank IS NOT NULL
            ORDER BY frequency_rank
            LIMIT ?
        """,
            (limit,),
        )
        return cursor.fetchall()

    def parse_bipolar_response(
        self,
        response: str,
        words: List[str],
        pole_a: str,
        pole_b: str,
    ) -> Dict[str, Tuple[int, int]]:
        """Parse batch response for bipolar pair."""
        import re

        results = {}

        for word in words:
            # Default to neither
            val_a, val_b = 0, 0

            # Look for exact pattern: "word: A/B/N" with word boundaries
            # Handle various formats: "word: A", "word:A", "word - A", etc.
            pattern = rf"\b{re.escape(word)}\b\s*[:=-]\s*([ABN])\b"

            for line in response.split("\n"):
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    answer = match.group(1).upper()
                    if answer == "A":
                        val_a, val_b = 1, 0
                    elif answer == "B":
                        val_a, val_b = 0, 1
                    # N = neither, keep (0, 0)
                    break

            results[word] = (val_a, val_b)

        return results

    def parse_single_response(
        self,
        response: str,
        words: List[str],
    ) -> Dict[str, int]:
        """Parse batch response for single primitive."""
        import re

        results = {}

        for word in words:
            val = 0  # Default

            # Look for exact pattern: "word: Y/N/O" with word boundaries
            pattern = rf"\b{re.escape(word)}\b\s*[:=-]\s*([YNO])\b"

            for line in response.split("\n"):
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    answer = match.group(1).upper()
                    if answer == "Y":
                        val = 1
                    elif answer == "O":
                        val = -1
                    # N = no, keep 0
                    break

            results[word] = val

        return results

    def sweep_bipolar(
        self,
        pole_a: str,
        pole_b: str,
        words: List[Tuple[int, str]],
    ) -> int:
        """Sweep a bipolar pair across all words."""
        values_set = 0

        # Process in batches
        for i in range(0, len(words), self.batch_size):
            batch = words[i : i + self.batch_size]
            word_list = [w[1] for w in batch]

            prompt = get_bipolar_batch_prompt(word_list, pole_a, pole_b)

            try:
                response = self.client.generate(
                    prompt=prompt,
                    system_prompt=SYSTEM_PROMPT,
                    config=self.config,
                )

                results = self.parse_bipolar_response(response, word_list, pole_a, pole_b)

                # Store results
                for (lex_id, lemma), (val_a, val_b) in zip(batch, [results.get(w, (0, 0)) for w in word_list]):
                    self.conn.execute(
                        """
                        INSERT OR REPLACE INTO primitive_values
                        (lexeme_id, primitive, value, confidence, source)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (lex_id, pole_a, val_a, 0.75, f"sweep:{self.model}"),
                    )

                    self.conn.execute(
                        """
                        INSERT OR REPLACE INTO primitive_values
                        (lexeme_id, primitive, value, confidence, source)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (lex_id, pole_b, val_b, 0.75, f"sweep:{self.model}"),
                    )

                    if val_a or val_b:
                        values_set += 1

                self.conn.commit()

            except Exception as e:
                logger.error(f"Batch failed for {pole_a}/{pole_b}: {e}")
                self.stats.errors += 1

        return values_set

    def sweep_single(
        self,
        primitive: str,
        words: List[Tuple[int, str]],
    ) -> int:
        """Sweep a single primitive across all words."""
        values_set = 0

        for i in range(0, len(words), self.batch_size):
            batch = words[i : i + self.batch_size]
            word_list = [w[1] for w in batch]

            prompt = get_single_batch_prompt(word_list, primitive)

            try:
                response = self.client.generate(
                    prompt=prompt,
                    system_prompt=SYSTEM_PROMPT,
                    config=self.config,
                )

                results = self.parse_single_response(response, word_list)

                # Store results
                for lex_id, lemma in batch:
                    val = results.get(lemma, 0)
                    self.conn.execute(
                        """
                        INSERT OR REPLACE INTO primitive_values
                        (lexeme_id, primitive, value, confidence, source)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (lex_id, primitive, val, 0.75, f"sweep:{self.model}"),
                    )

                    if val:
                        values_set += 1

                self.conn.commit()

            except Exception as e:
                logger.error(f"Batch failed for {primitive}: {e}")
                self.stats.errors += 1

        return values_set

    def run_full_sweep(
        self,
        word_limit: int = 1000,
        start_primitive: str = None,
    ) -> SweepStats:
        """
        Run full sweep: all primitives across top N words.
        """
        words = self.get_top_words(word_limit)
        logger.info(f"Sweeping {len(words)} words with {self.model}")

        start_time = time.time()

        # Bipolar pairs (14 pairs = 28 primitives)
        started = start_primitive is None
        for pole_a, pole_b in BIPOLAR_PAIRS:
            if not started:
                if pole_a == start_primitive or pole_b == start_primitive:
                    started = True
                else:
                    continue

            logger.info(f"Sweeping {pole_a}/{pole_b}...")
            values = self.sweep_bipolar(pole_a, pole_b, words)
            self.stats.primitives_processed += 2
            self.stats.values_set += values

            elapsed = time.time() - start_time
            logger.info(f"  -> {values} active | {self.stats} | {elapsed:.1f}s")

        # Single primitives (44)
        for prim in SINGLE_PRIMITIVES:
            if not started:
                if prim == start_primitive:
                    started = True
                else:
                    continue

            logger.info(f"Sweeping {prim}...")
            values = self.sweep_single(prim, words)
            self.stats.primitives_processed += 1
            self.stats.values_set += values

            elapsed = time.time() - start_time
            logger.info(f"  -> {values} active | {self.stats} | {elapsed:.1f}s")

        self.stats.words_processed = len(words)

        total_time = time.time() - start_time
        logger.info(f"Sweep complete in {total_time:.1f}s")

        return self.stats

    def close(self):
        self.conn.close()


def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Primitive Sweep")
    parser.add_argument("--db", default="data/lexicon.db")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--words", type=int, default=1000, help="Number of top words")
    parser.add_argument("--batch-size", type=int, default=20, help="Words per prompt")
    parser.add_argument("--start", help="Start from this primitive (resume)")

    args = parser.parse_args()

    sweep = PrimitiveSweep(
        db_path=args.db,
        model=args.model,
        batch_size=args.batch_size,
    )

    try:
        stats = sweep.run_full_sweep(
            word_limit=args.words,
            start_primitive=args.start,
        )

        print("\n" + "=" * 50)
        print("SWEEP COMPLETE")
        print("=" * 50)
        print(f"Primitives processed: {stats.primitives_processed}")
        print(f"Words processed: {stats.words_processed}")
        print(f"Values set (non-zero): {stats.values_set}")
        print(f"Errors: {stats.errors}")

    finally:
        sweep.close()


if __name__ == "__main__":
    main()
