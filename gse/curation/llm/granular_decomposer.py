"""
Granular Decomposer

Instead of 10 words per prompt, sends prompts with focused primitive subsets
for each word. More accurate but slower.

Strategy:
1. Get primitives already filled from external sources
2. Group remaining primitives by semantic bank
3. Send focused prompts: "For word X, evaluate these 10 primitives: ..."
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from gse.curation.llm.ollama_client import OllamaClient
from gse.curation.schema import ALL_PRIMITIVES

logger = logging.getLogger(__name__)


# Group primitives by semantic bank for focused prompts
PRIMITIVE_GROUPS = {
    "substantives": ["I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY", "KIND", "PART", "SAME", "OTHER"],
    "quantity": ["ONE", "TWO", "QUANTITY"],
    "evaluators": ["GOOD", "BAD", "BIG", "SMALL"],
    "mental": ["THINK", "KNOW", "WANT", "FEEL", "SEE", "HEAR", "INFER"],
    "action": ["SAY", "WORDS", "DO", "HAPPEN", "MOVE", "BE", "HAVE", "EXIST", "ALIVE", "DEAD"],
    "temporal": ["MOMENT", "WHEN", "LONG_TIME", "SHORT_TIME", "BEFORE", "AFTER", "THEN", "NOW", "START", "END"],
    "spatial": [
        "WHERE",
        "HERE",
        "SIDE",
        "TOUCH",
        "ABOVE",
        "BELOW",
        "FAR",
        "NEAR",
        "OUTSIDE",
        "INSIDE",
        "TOWARD",
        "AWAY",
        "WITH",
        "WITHOUT",
    ],
    "logical": [
        "NOT",
        "MAYBE",
        "CAN",
        "MUST",
        "BECAUSE",
        "CAUSE",
        "IF",
        "LIKE",
        "TRUE",
        "FALSE",
        "HIER_PLUS",
        "HIER_MINUS",
        "INTENSITY",
        "CERTAINTY",
    ],
}


GRANULAR_SYSTEM_PROMPT = """You are a semantic primitive analyst. For the given word, evaluate ONLY the specified primitives.

For each primitive, assign:
- +1 if the word POSITIVELY involves this primitive (core semantic component)
- -1 if the word NEGATIVELY involves this primitive (opposite/absence is key)
- 0 if the primitive is NOT RELEVANT to the word's meaning

BIPOLAR CONSTRAINTS - these pairs cannot BOTH be non-zero:
- GOOD/BAD, BIG/SMALL, ALIVE/DEAD, SAME/OTHER
- BEFORE/AFTER, THEN/NOW, START/END, LONG_TIME/SHORT_TIME
- ABOVE/BELOW, FAR/NEAR, OUTSIDE/INSIDE, TOWARD/AWAY, WITH/WITHOUT, TRUE/FALSE

Return ONLY a JSON object with the primitive names as keys and values as integers (-1, 0, or +1).
"""


def get_granular_prompt(word: str, primitives: List[str], pos: str = None) -> str:
    """Generate a focused prompt for specific primitives."""
    prim_list = ", ".join(primitives)
    pos_hint = f" ({pos})" if pos else ""

    return f"""Word: "{word}"{pos_hint}

Evaluate ONLY these primitives: {prim_list}

Think carefully about each primitive's relevance to this word's core meaning.
Return a JSON object with exactly these primitives as keys.

Example format:
{{"PRIMITIVE1": 1, "PRIMITIVE2": 0, "PRIMITIVE3": -1}}"""


@dataclass
class GranularResult:
    """Result from granular decomposition."""

    word: str
    primitives: Dict[str, int]
    source: str  # "external" or "llm:{model}"
    bank: str  # which bank was queried
    raw_response: Optional[str] = None


class GranularDecomposer:
    """
    Decompose words with granular, focused prompts.

    For each word:
    1. Check which primitives are already filled from external sources
    2. For missing primitives, query LLM by semantic bank
    3. Store results with source tracking
    """

    def __init__(
        self,
        db_path: str,
        model: str = "qwen3:32b",
        temperature: float = 0.2,
    ):
        self.db_path = db_path
        self.model = model
        self.temperature = temperature
        self.client = OllamaClient(model=model)
        self.conn = sqlite3.connect(db_path)

    def get_filled_primitives(self, lexeme_id: int) -> Dict[str, Tuple[int, str]]:
        """Get primitives already filled with their values and sources."""
        cursor = self.conn.execute(
            "SELECT primitive, value, source FROM primitive_values WHERE lexeme_id = ?", (lexeme_id,)
        )
        return {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

    def get_missing_primitives(self, lexeme_id: int) -> List[str]:
        """Get primitives that need LLM evaluation."""
        filled = set(self.get_filled_primitives(lexeme_id).keys())
        return [p for p in ALL_PRIMITIVES if p not in filled]

    def decompose_primitives(
        self,
        word: str,
        primitives: List[str],
        pos: str = None,
    ) -> Dict[str, int]:
        """Query LLM for specific primitives."""
        if not primitives:
            return {}

        prompt = get_granular_prompt(word, primitives, pos)

        try:
            from gse.curation.llm.ollama_client import GenerationConfig

            config = GenerationConfig(temperature=self.temperature)
            response = self.client.generate(
                prompt=prompt,
                system_prompt=GRANULAR_SYSTEM_PROMPT,
                config=config,
            )

            # Parse JSON from response
            # Try to extract JSON object
            import re

            json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                # Normalize values to -1, 0, +1
                result = {}
                for prim in primitives:
                    if prim in data:
                        val = data[prim]
                        if isinstance(val, (int, float)):
                            result[prim] = 1 if val > 0 else (-1 if val < 0 else 0)
                        else:
                            result[prim] = 0
                    else:
                        result[prim] = 0
                return result

        except Exception as e:
            logger.warning(f"Failed to decompose {word}: {e}")

        return {p: 0 for p in primitives}

    def process_word(
        self,
        lexeme_id: int,
        lemma: str,
        pos: str = None,
        skip_filled: bool = True,
    ) -> Dict[str, GranularResult]:
        """
        Process a single word with granular prompts.

        Returns dict of bank_name -> GranularResult
        """
        results = {}

        # Get what's already filled
        filled = self.get_filled_primitives(lexeme_id)

        # Process each bank
        for bank_name, bank_primitives in PRIMITIVE_GROUPS.items():
            # Filter to primitives that need evaluation
            if skip_filled:
                to_evaluate = [p for p in bank_primitives if p not in filled]
            else:
                to_evaluate = bank_primitives

            if not to_evaluate:
                continue

            # Query LLM
            llm_result = self.decompose_primitives(lemma, to_evaluate, pos)

            # Store results
            for prim, value in llm_result.items():
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO primitive_values
                    (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (lexeme_id, prim, value, 0.7, f"llm:{self.model}"),
                )

            results[bank_name] = GranularResult(
                word=lemma,
                primitives=llm_result,
                source=f"llm:{self.model}",
                bank=bank_name,
            )

        self.conn.commit()
        return results

    def process_batch(
        self,
        limit: int = None,
        only_missing: bool = True,
    ) -> Dict[str, int]:
        """
        Process words that need LLM evaluation.

        Args:
            limit: Max words to process
            only_missing: Only process words with missing primitives

        Returns:
            Stats dict
        """
        # Get words to process
        if only_missing:
            # Words with fewer than all primitives filled
            cursor = self.conn.execute("""
                SELECT l.id, l.lemma, l.pos, COUNT(p.id) as filled_count
                FROM lexemes l
                LEFT JOIN primitive_values p ON l.id = p.lexeme_id
                GROUP BY l.id
                HAVING filled_count < 72
                ORDER BY l.frequency_rank
            """)
        else:
            cursor = self.conn.execute("""
                SELECT id, lemma, pos, 0
                FROM lexemes
                ORDER BY frequency_rank
            """)

        words = cursor.fetchall()
        if limit:
            words = words[:limit]

        logger.info(f"Processing {len(words)} words with granular decomposition...")

        stats = {"processed": 0, "primitives_filled": 0}

        for i, (lex_id, lemma, pos, _) in enumerate(words):
            results = self.process_word(lex_id, lemma, pos)

            stats["processed"] += 1
            stats["primitives_filled"] += sum(len(r.primitives) for r in results.values())

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(words)} - {lemma}")

        return stats

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/lexicon.db")
    parser.add_argument("--model", default="qwen3:32b")
    parser.add_argument("--limit", type=int, help="Max words to process")
    parser.add_argument("--word", help="Process single word")

    args = parser.parse_args()

    decomposer = GranularDecomposer(args.db, model=args.model)

    if args.word:
        # Process single word
        cursor = decomposer.conn.execute("SELECT id, pos FROM lexemes WHERE lemma = ?", (args.word,))
        row = cursor.fetchone()
        if row:
            results = decomposer.process_word(row[0], args.word, row[1], skip_filled=False)
            print(f"\n=== {args.word} ===")
            for bank, result in results.items():
                print(f"{bank}: {result.primitives}")
        else:
            print(f"Word not found: {args.word}")
    else:
        # Process batch
        stats = decomposer.process_batch(limit=args.limit)
        print("\n=== Complete ===")
        print(f"Processed: {stats['processed']}")
        print(f"Primitives filled: {stats['primitives_filled']}")

    decomposer.close()
