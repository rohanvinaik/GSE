#!/usr/bin/env python3
"""
Semantic Review using qwen3:32b

Processes ambiguous semantic primitive assignments using the 32B model.
"""

import argparse
import logging
import re
import sqlite3
from typing import Dict, List, Tuple

from gse.curation.llm.ollama_client import GenerationConfig, OllamaClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a semantic primitives expert reviewing word-primitive assignments.
For each word, determine if the primitive assignment is correct.
Be precise and consistent. Output ONLY the specified format, no explanations."""


def get_feel_review_prompt(words: List[str]) -> str:
    """Generate prompt for FEEL primitive review."""
    return f"""Review these words that have FEEL=1 but no SOMEONE/I/YOU experiencer.

FEEL primitive = subjective conscious experience (emotions, sensations, perceptions)
- CORRECT if word involves genuine subjective experience (emotions, feelings)
- INCORRECT if word is abstract, inanimate, or institutional

For each word, output ONE LINE in format:
WORD:value  (where value is 0 if FEEL should be removed, 1 if FEEL is correct and needs SOMEONE)

Words to review:
{", ".join(words)}

Output (one per line):"""


def get_do_happen_prompt(words: List[str]) -> str:
    """Generate prompt for DO/HAPPEN review."""
    return f"""Review these verbs for DO and HAPPEN primitives.

DO=1: Agentive action (someone intentionally does it)
HAPPEN=1: Non-agentive event (occurs without intention)
Some verbs can have both (e.g., "break" can be done or can happen)

For each word, output ONE LINE in format:
WORD:DO,HAPPEN  (use 1 or 0 for each)

Words to review:
{", ".join(words)}

Output (one per line):"""


def parse_feel_response(response: str) -> Dict[str, int]:
    """Parse FEEL review response."""
    results = {}
    for line in response.strip().split("\n"):
        line = line.strip()
        if ":" in line:
            match = re.match(r"(\w+)\s*:\s*([01])", line)
            if match:
                word, value = match.groups()
                results[word.lower()] = int(value)
    return results


def parse_do_happen_response(response: str) -> Dict[str, Tuple[int, int]]:
    """Parse DO/HAPPEN review response."""
    results = {}
    for line in response.strip().split("\n"):
        line = line.strip()
        if ":" in line:
            match = re.match(r"(\w+)\s*:\s*([01])\s*,\s*([01])", line)
            if match:
                word, do_val, happen_val = match.groups()
                results[word.lower()] = (int(do_val), int(happen_val))
    return results


def review_feel_primitives(
    conn: sqlite3.Connection,
    client: OllamaClient,
    config: GenerationConfig,
    batch_size: int = 20,
) -> int:
    """Review FEEL=1 assignments without experiencer."""
    cursor = conn.execute("""
        SELECT l.id, l.lemma
        FROM lexemes l
        JOIN primitive_values feel ON l.id = feel.lexeme_id
            AND feel.primitive = 'FEEL' AND feel.value = 1
        LEFT JOIN primitive_values someone ON l.id = someone.lexeme_id
            AND someone.primitive = 'SOMEONE' AND someone.value = 1
        LEFT JOIN primitive_values i_prim ON l.id = i_prim.lexeme_id
            AND i_prim.primitive = 'I' AND i_prim.value = 1
        LEFT JOIN primitive_values you_prim ON l.id = you_prim.lexeme_id
            AND you_prim.primitive = 'YOU' AND you_prim.value = 1
        WHERE someone.value IS NULL
          AND i_prim.value IS NULL
          AND you_prim.value IS NULL
          AND feel.source NOT LIKE 'fix:%'
          AND feel.source NOT LIKE 'llm:qwen3%'
        ORDER BY l.frequency_rank
    """)

    words_to_review = [(row[0], row[1]) for row in cursor.fetchall()]
    if not words_to_review:
        logger.info("No FEEL primitives to review")
        return 0

    logger.info(f"Reviewing {len(words_to_review)} FEEL assignments...")

    fixes_applied = 0
    for i in range(0, len(words_to_review), batch_size):
        batch = words_to_review[i : i + batch_size]
        batch_words = [w[1] for w in batch]
        batch_ids = {w[1]: w[0] for w in batch}

        prompt = get_feel_review_prompt(batch_words)
        response = client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            config=config,
        )

        results = parse_feel_response(response)
        logger.info(f"Batch {i // batch_size + 1}: Got {len(results)} decisions")

        for word, value in results.items():
            if word not in batch_ids:
                continue

            lexeme_id = batch_ids[word]

            if value == 0:
                # Remove FEEL
                conn.execute(
                    """
                    UPDATE primitive_values
                    SET value = 0, confidence = 0.85, source = 'llm:qwen3:32b_review'
                    WHERE lexeme_id = ? AND primitive = 'FEEL'
                """,
                    (lexeme_id,),
                )
                logger.info(f"  {word}: FEEL=0 (abstract/inanimate)")
            else:
                # Add SOMEONE
                conn.execute(
                    """
                    INSERT OR REPLACE INTO primitive_values
                    (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, 'SOMEONE', 1, 0.85, 'llm:qwen3:32b_review')
                """,
                    (lexeme_id,),
                )
                logger.info(f"  {word}: Added SOMEONE=1")

            fixes_applied += 1

        conn.commit()

    return fixes_applied


def review_do_happen(
    conn: sqlite3.Connection,
    client: OllamaClient,
    config: GenerationConfig,
) -> int:
    """Review verbs for DO/HAPPEN primitives."""
    # Get verbs missing both DO and HAPPEN
    cursor = conn.execute("""
        SELECT l.id, l.lemma
        FROM lexemes l
        LEFT JOIN primitive_values do_prim ON l.id = do_prim.lexeme_id
            AND do_prim.primitive = 'DO'
        LEFT JOIN primitive_values happen_prim ON l.id = happen_prim.lexeme_id
            AND happen_prim.primitive = 'HAPPEN'
        WHERE l.pos = 'VERB'
          AND (do_prim.value IS NULL OR do_prim.value = 0)
          AND (happen_prim.value IS NULL OR happen_prim.value = 0)
        ORDER BY l.frequency_rank
        LIMIT 50
    """)

    words_to_review = [(row[0], row[1]) for row in cursor.fetchall()]
    if not words_to_review:
        logger.info("No verbs to review for DO/HAPPEN")
        return 0

    logger.info(f"Reviewing {len(words_to_review)} verbs for DO/HAPPEN...")

    batch_words = [w[1] for w in words_to_review]
    batch_ids = {w[1]: w[0] for w in words_to_review}

    prompt = get_do_happen_prompt(batch_words)
    response = client.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
        config=config,
    )

    results = parse_do_happen_response(response)
    logger.info(f"Got {len(results)} decisions")

    fixes_applied = 0
    for word, (do_val, happen_val) in results.items():
        if word not in batch_ids:
            continue

        lexeme_id = batch_ids[word]

        if do_val == 1:
            conn.execute(
                """
                INSERT OR REPLACE INTO primitive_values
                (lexeme_id, primitive, value, confidence, source)
                VALUES (?, 'DO', 1, 0.85, 'llm:qwen3:32b_review')
            """,
                (lexeme_id,),
            )
            logger.info(f"  {word}: DO=1")
            fixes_applied += 1

        if happen_val == 1:
            conn.execute(
                """
                INSERT OR REPLACE INTO primitive_values
                (lexeme_id, primitive, value, confidence, source)
                VALUES (?, 'HAPPEN', 1, 0.85, 'llm:qwen3:32b_review')
            """,
                (lexeme_id,),
            )
            logger.info(f"  {word}: HAPPEN=1")
            fixes_applied += 1

    conn.commit()
    return fixes_applied


def main():
    parser = argparse.ArgumentParser(description="Semantic Review with qwen3:32b")
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument("--model", default="qwen3:32b", help="Model to use")
    parser.add_argument(
        "--review-type", choices=["feel", "do_happen", "all"], default="all", help="Type of review to run"
    )

    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    client = OllamaClient(model=args.model)
    config = GenerationConfig(temperature=0.1, max_tokens=2000)

    total_fixes = 0

    if args.review_type in ["feel", "all"]:
        fixes = review_feel_primitives(conn, client, config)
        total_fixes += fixes
        logger.info(f"FEEL review: {fixes} fixes applied")

    if args.review_type in ["do_happen", "all"]:
        fixes = review_do_happen(conn, client, config)
        total_fixes += fixes
        logger.info(f"DO/HAPPEN review: {fixes} fixes applied")

    print(f"\n{'=' * 50}")
    print("SEMANTIC REVIEW COMPLETE")
    print(f"{'=' * 50}")
    print(f"Total fixes applied: {total_fixes}")

    conn.close()


if __name__ == "__main__":
    main()
