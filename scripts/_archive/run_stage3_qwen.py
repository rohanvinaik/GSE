#!/usr/bin/env python3
"""
Stage 3: Run Qwen 32B on unencoded words

Processes words in batches through Qwen and applies primitive assignments.
"""

import sqlite3
import subprocess
import json
import re
import sys
from pathlib import Path

DB_PATH = Path("data/lexicon.db")
LOG_PATH = Path("data/logs/stage3_qwen.log")
BATCH_SIZE = 15

PROMPT_TEMPLATE = """/nothink
Assign semantic primitives to these words. Use 1 (present) or 0 (not applicable).

RULES:
- If ZERO=1, then SING=0 AND PLUR=0 (mutual transparency)
- If FEEL=1, add SOMEONE=1
- If SAY=1, add WORDS=1
- Verbs need DO=1 (intentional) or HAPPEN=1 (unintentional)

PRIMITIVES: SOMEONE, SOMETHING, GOOD, BAD, FEEL, THINK, SAY, WORDS, DO, HAPPEN, MOVE, SEE, HEAR, BODY, ALIVE, SING, PLUR, ZERO

OUTPUT FORMAT (one per line):
word: PRIM=val, PRIM=val, ... (reason: brief)

WORDS:
{words}

Encode each word now:"""


def get_unencoded_words(cursor, limit=None, offset=0):
    """Get ATOMIC words with 0 primitives."""
    query = """
        SELECT l.id, l.lemma, l.pos FROM lexemes l
        WHERE l.component_type = 'ATOMIC'
        AND NOT EXISTS (SELECT 1 FROM primitive_values pv WHERE pv.lexeme_id = l.id AND pv.value <> 0)
        ORDER BY l.frequency_rank
    """
    if limit:
        query += f" LIMIT {limit} OFFSET {offset}"
    cursor.execute(query)
    return cursor.fetchall()


def run_qwen(prompt):
    """Run prompt through Qwen 32B."""
    result = subprocess.run(
        ["ollama", "run", "qwen3:32b"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=600  # 10 minutes per batch
    )
    return result.stdout


def parse_qwen_output(output, word_ids):
    """Parse Qwen's output into primitive assignments."""
    assignments = []

    # Pattern: word: PRIM=val, PRIM=val, ... (reason: ...)
    pattern = r'^(\w+[\.\-]?\w*)\s*:\s*(.+?)(?:\s*\(reason:.*\))?$'

    for line in output.split('\n'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('```'):
            continue

        match = re.match(pattern, line, re.IGNORECASE)
        if match:
            lemma = match.group(1).lower()
            prims_str = match.group(2)

            # Find word ID
            word_id = word_ids.get(lemma)
            if not word_id:
                continue

            # Parse primitives
            prims = {}
            for prim_match in re.finditer(r'(\w+)\s*=\s*(\d+)', prims_str):
                prim_name = prim_match.group(1).upper()
                prim_val = int(prim_match.group(2))
                if prim_val != 0:  # Only store non-zero
                    prims[prim_name] = prim_val

            if prims:
                assignments.append((word_id, lemma, prims))

    return assignments


def apply_assignments(cursor, assignments):
    """Apply primitive assignments to database."""
    count = 0
    for word_id, lemma, prims in assignments:
        for prim, val in prims.items():
            cursor.execute("""
                INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                VALUES (?, ?, ?, 0.85, 'qwen:stage3')
                ON CONFLICT(lexeme_id, primitive)
                DO UPDATE SET value = ?, confidence = 0.85, source = 'qwen:stage3'
            """, (word_id, prim, val, val))
            count += 1
    return count


def log_print(log, msg):
    """Print and log with flush."""
    print(msg, flush=True)
    log.write(msg + "\n")
    log.flush()


def main():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get total count
    cursor.execute("""
        SELECT COUNT(*) FROM lexemes l
        WHERE l.component_type = 'ATOMIC'
        AND NOT EXISTS (SELECT 1 FROM primitive_values pv WHERE pv.lexeme_id = l.id AND pv.value <> 0)
    """)
    total = cursor.fetchone()[0]
    print(f"Total words to process: {total}", flush=True)

    processed = 0
    attempted = 0  # Track attempted to handle timeouts
    batch_num = 0

    with open(LOG_PATH, 'w', buffering=1) as log:  # Line buffered
        log_print(log, f"=== Stage 3 Qwen Processing ===\nTotal: {total}\n")

        while attempted < total:
            batch_num += 1
            words = get_unencoded_words(cursor, limit=BATCH_SIZE, offset=attempted)

            if not words:
                break

            attempted += len(words)  # Move offset forward regardless of success

            # Build prompt
            word_list = "\n".join(f"- {w[1]} ({w[2] or 'unknown'})" for w in words)
            prompt = PROMPT_TEMPLATE.format(words=word_list)

            # Build ID lookup
            word_ids = {w[1].lower(): w[0] for w in words}

            log_print(log, f"\n--- Batch {batch_num}: Processing {len(words)} words ---")
            log_print(log, f"Words: {', '.join(w[1] for w in words[:10])}...")

            try:
                output = run_qwen(prompt)
                log_print(log, f"Qwen output length: {len(output)} chars")
                log.write(f"Full output:\n{output}\n")
                log.flush()

                assignments = parse_qwen_output(output, word_ids)
                log_print(log, f"Parsed {len(assignments)} assignments")

                if assignments:
                    count = apply_assignments(cursor, assignments)
                    conn.commit()
                    processed += len(assignments)
                    log_print(log, f"Applied {count} primitives to {len(assignments)} words")
                else:
                    log_print(log, "No valid assignments parsed - skipping batch")
                    processed += len(words)

            except subprocess.TimeoutExpired:
                log_print(log, f"TIMEOUT on batch {batch_num}")
                processed += len(words)
            except Exception as e:
                log_print(log, f"ERROR: {e}")
                processed += len(words)

            # Progress
            remaining = total - processed
            log_print(log, f"Progress: {processed}/{total} ({100*processed//total}%), {remaining} remaining")

            # Safety limit for testing
            if batch_num >= 5 and '--full' not in sys.argv:
                print("\n[Test mode: stopping after 5 batches. Use --full to process all]")
                break

    conn.close()
    print(f"\nLog saved to {LOG_PATH}")


if __name__ == "__main__":
    main()
