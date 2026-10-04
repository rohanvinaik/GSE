"""
Gap Filler

Only queries LLM for primitives that have NO external source data.
Uses external source data as ground truth for covered primitives.

For bipolar pairs where one pole is covered:
- If GOOD=1 from external, infer BAD=0
- If GOOD=-1 from external, infer BAD=1
"""

import logging
import sqlite3
import time
from typing import Dict, Set

from gse.curation.llm.ollama_client import GenerationConfig, OllamaClient

logger = logging.getLogger(__name__)


# Primitives that need LLM (no external source coverage)
NEED_LLM = {
    "AFTER",
    "BAD",
    "BECAUSE",
    "BELOW",
    "CERTAINTY",
    "DEAD",
    "FALSE",
    "FAR",
    "HERE",
    "HIER_MINUS",
    "HIER_PLUS",
    "I",
    "IF",
    "INFER",
    "KIND",
    "LIKE",
    "LONG_TIME",
    "MOMENT",
    "NEAR",
    "NOT",
    "NOW",
    "ONE",
    "OTHER",
    "OUTSIDE",
    "PART",
    "PEOPLE",
    "QUANTITY",
    "SAME",
    "SHORT_TIME",
    "SIDE",
    "SMALL",
    "THEN",
    "TOWARD",
    "TRUE",
    "TWO",
    "WITHOUT",
    "YOU",
}

# Bipolar pairs where we can infer one from the other
BIPOLAR_INFERENCE = {
    ("GOOD", "BAD"): "GOOD",  # If GOOD is known, infer BAD
    ("BIG", "SMALL"): "BIG",
    ("ALIVE", "DEAD"): "ALIVE",
    ("BEFORE", "AFTER"): "BEFORE",
    ("INSIDE", "OUTSIDE"): "INSIDE",
    ("WITH", "WITHOUT"): "WITH",
    # These need both from LLM
    ("SAME", "OTHER"): None,
    ("LONG_TIME", "SHORT_TIME"): None,
    ("THEN", "NOW"): None,
    ("START", "END"): None,  # Both covered
    ("ABOVE", "BELOW"): None,
    ("FAR", "NEAR"): None,
    ("TOWARD", "AWAY"): None,
    ("TRUE", "FALSE"): None,
}


SYSTEM_PROMPT = """You are a semantic primitive analyst.
Answer with just: YES, NO, or OPPOSITE
No explanations needed."""


def get_single_prompt(word: str, primitive: str) -> str:
    """Simple single-primitive prompt."""
    return f"""Word: "{word}"
Primitive: {primitive}

Does this word's meaning involve {primitive}?
Answer: YES, NO, or OPPOSITE"""


class GapFiller:
    """
    Fill gaps in primitive data using LLM only where needed.
    """

    def __init__(
        self,
        db_path: str,
        model: str = "qwen2.5:7b",
    ):
        self.db_path = db_path
        self.model = model
        self.client = OllamaClient(model=model)
        self.config = GenerationConfig(temperature=0.1, max_tokens=20)
        self.conn = sqlite3.connect(db_path)

    def get_external_primitives(self, lexeme_id: int) -> Dict[str, int]:
        """Get primitives from external sources for a lexeme."""
        cursor = self.conn.execute(
            """
            SELECT primitive, value FROM primitive_values
            WHERE lexeme_id = ? AND source NOT LIKE 'llm:%'
        """,
            (lexeme_id,),
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def infer_bipolar_counterpart(
        self,
        external: Dict[str, int],
    ) -> Dict[str, int]:
        """Infer missing bipolar counterparts from external data.

        For bipolar pairs, if one pole has a value, the other should be 0.
        - If GOOD=+1, then BAD=0 (word is good, not bad)
        - If GOOD=-1, then BAD=0 (word is "not good" expressed via -1, BAD stays neutral)
        - If GOOD=0, then BAD=0 (both neutral)

        We never infer a positive value for the unknown pole.
        """
        inferred = {}

        for (pole_a, pole_b), known_pole in BIPOLAR_INFERENCE.items():
            if known_pole is None:
                continue

            unknown_pole = pole_b if known_pole == pole_a else pole_a

            if known_pole in external and unknown_pole not in external:
                # If one pole is known (any value), the other is 0
                # This prevents bipolar violations
                inferred[unknown_pole] = 0

        return inferred

    def get_primitives_to_query(
        self,
        lexeme_id: int,
    ) -> Set[str]:
        """Get primitives that need LLM query for this lexeme."""
        external = self.get_external_primitives(lexeme_id)
        inferred = self.infer_bipolar_counterpart(external)

        # Start with all primitives that need LLM
        to_query = NEED_LLM.copy()

        # Remove any that we can infer from external data
        to_query -= set(inferred.keys())

        # Also remove any that already have LLM data
        cursor = self.conn.execute(
            """
            SELECT primitive FROM primitive_values
            WHERE lexeme_id = ? AND source LIKE 'llm:%'
        """,
            (lexeme_id,),
        )
        already_done = {row[0] for row in cursor.fetchall()}
        to_query -= already_done

        return to_query

    def query_primitive(self, word: str, primitive: str) -> int:
        """Query LLM for a single primitive."""
        prompt = get_single_prompt(word, primitive)

        try:
            response = (
                self.client.generate(
                    prompt=prompt,
                    system_prompt=SYSTEM_PROMPT,
                    config=self.config,
                )
                .strip()
                .upper()
            )

            if response.startswith("YES") or response == "Y":
                return 1
            elif "OPPOSITE" in response or response.startswith("OPP"):
                return -1
            else:
                return 0

        except Exception as e:
            logger.warning(f"Query failed for {word}/{primitive}: {e}")
            return 0

    def process_word(self, lexeme_id: int, lemma: str) -> Dict[str, int]:
        """Process a single word - fill gaps only."""
        external = self.get_external_primitives(lexeme_id)
        inferred = self.infer_bipolar_counterpart(external)
        to_query = self.get_primitives_to_query(lexeme_id)

        result = {}

        # Store inferred values
        for prim, val in inferred.items():
            self.conn.execute(
                """
                INSERT OR REPLACE INTO primitive_values
                (lexeme_id, primitive, value, confidence, source)
                VALUES (?, ?, ?, ?, ?)
            """,
                (lexeme_id, prim, val, 0.8, "inferred:bipolar"),
            )
            result[prim] = val

        # Query LLM for remaining
        for prim in to_query:
            val = self.query_primitive(lemma, prim)
            self.conn.execute(
                """
                INSERT OR REPLACE INTO primitive_values
                (lexeme_id, primitive, value, confidence, source)
                VALUES (?, ?, ?, ?, ?)
            """,
                (lexeme_id, prim, val, 0.7, f"llm:{self.model}"),
            )
            result[prim] = val

        self.conn.commit()
        return result

    def process_batch(
        self,
        limit: int = None,
        start_rank: int = 1,
    ) -> Dict[str, int]:
        """Process words by frequency rank."""
        cursor = self.conn.execute(
            """
            SELECT id, lemma, frequency_rank FROM lexemes
            WHERE frequency_rank >= ?
            ORDER BY frequency_rank
        """,
            (start_rank,),
        )

        words = cursor.fetchall()
        if limit:
            words = words[:limit]

        logger.info(f"Processing {len(words)} words for gap filling...")

        stats = {"processed": 0, "inferred": 0, "llm_queries": 0}
        start_time = time.time()

        for i, (lex_id, lemma, rank) in enumerate(words):
            to_query = self.get_primitives_to_query(lex_id)
            external = self.get_external_primitives(lex_id)
            inferred = self.infer_bipolar_counterpart(external)

            result = self.process_word(lex_id, lemma)

            stats["processed"] += 1
            stats["inferred"] += len(inferred)
            stats["llm_queries"] += len(to_query)

            if (i + 1) % 10 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                logger.info(
                    f"Progress: {i + 1}/{len(words)} ({rate:.2f}/sec) - {lemma} "
                    f"[inferred: {len(inferred)}, queried: {len(to_query)}]"
                )

        return stats

    def close(self):
        self.conn.close()


def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Gap Filler")
    parser.add_argument("--db", default="data/lexicon.db")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--limit", type=int, help="Max words to process")
    parser.add_argument("--start-rank", type=int, default=1, help="Start from frequency rank")
    parser.add_argument("--word", help="Process single word")

    args = parser.parse_args()

    filler = GapFiller(db_path=args.db, model=args.model)

    try:
        if args.word:
            cursor = filler.conn.execute("SELECT id FROM lexemes WHERE lemma = ?", (args.word,))
            row = cursor.fetchone()
            if row:
                to_query = filler.get_primitives_to_query(row[0])
                print(f"Primitives to query for '{args.word}': {len(to_query)}")
                print(sorted(to_query))

                result = filler.process_word(row[0], args.word)
                active = {k: v for k, v in result.items() if v != 0}
                print(f"\nActive results: {active}")
            else:
                print(f"Word not found: {args.word}")
        else:
            stats = filler.process_batch(
                limit=args.limit,
                start_rank=args.start_rank,
            )
            print("\n" + "=" * 50)
            print("GAP FILLING COMPLETE")
            print("=" * 50)
            print(f"Words processed: {stats['processed']}")
            print(f"Primitives inferred: {stats['inferred']}")
            print(f"LLM queries made: {stats['llm_queries']}")

    finally:
        filler.close()


if __name__ == "__main__":
    main()
