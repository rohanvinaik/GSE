#!/usr/bin/env python3
"""
Lexicon Enhancement from Frequency List
----------------------------------------
Processes words from a frequency-sorted word list in sequential batches.
Records failures for each batch.

Usage:
    python enhance_from_frequency_list.py --start 0 --count 100
"""

import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

sys.path.insert(0, "/Users/rohanvinaik/gse")
from gse.lexicon_generator import LexiconGenerator
from gse.primitives import PRIMITIVES, ROLES
from gse.vectors import PrimitiveBasis

# Configuration
DB_PATH = "/Users/rohanvinaik/gse/data/lexicon.db"
FREQ_FILE = "/Users/rohanvinaik/relational-ai/word_frequency_report.txt"
FAILURES_LOG = "/Users/rohanvinaik/relational-ai/data/lexicon_enhancement_failures.jsonl"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = "llama3.2:3b"

# POS mapping for common words
POS_DEFAULTS = {
    # Determiners/Articles
    "the": "DET",
    "a": "DET",
    "an": "DET",
    "this": "DET",
    "that": "DET",
    "these": "DET",
    "those": "DET",
    "my": "DET",
    "your": "DET",
    "his": "DET",
    "her": "DET",
    "its": "DET",
    "our": "DET",
    "their": "DET",
    "some": "DET",
    "any": "DET",
    "no": "DET",
    "every": "DET",
    "each": "DET",
    "all": "DET",
    # Pronouns
    "i": "PRON",
    "you": "PRON",
    "he": "PRON",
    "she": "PRON",
    "it": "PRON",
    "we": "PRON",
    "they": "PRON",
    "me": "PRON",
    "him": "PRON",
    "us": "PRON",
    "them": "PRON",
    "what": "PRON",
    "which": "PRON",
    "who": "PRON",
    # Conjunctions
    "and": "CONJ",
    "or": "CONJ",
    "but": "CONJ",
    "if": "CONJ",
    "because": "CONJ",
    "while": "CONJ",
    "although": "CONJ",
    "when": "CONJ",
    "where": "CONJ",
    # Prepositions
    "in": "ADP",
    "on": "ADP",
    "at": "ADP",
    "to": "ADP",
    "for": "ADP",
    "with": "ADP",
    "by": "ADP",
    "from": "ADP",
    "of": "ADP",
    "about": "ADP",
    "into": "ADP",
    "through": "ADP",
    "without": "ADP",
    "between": "ADP",
    # Adverbs
    "not": "ADV",
    "just": "ADV",
    "only": "ADV",
    "even": "ADV",
    "also": "ADV",
    "very": "ADV",
    "so": "ADV",
    "too": "ADV",
    "more": "ADV",
    "most": "ADV",
    "how": "ADV",
    "here": "ADV",
    "there": "ADV",
    "now": "ADV",
    "then": "ADV",
    # Common verbs
    "is": "VERB",
    "are": "VERB",
    "was": "VERB",
    "were": "VERB",
    "be": "VERB",
    "have": "VERB",
    "has": "VERB",
    "had": "VERB",
    "do": "VERB",
    "does": "VERB",
    "can": "VERB",
    "could": "VERB",
    "will": "VERB",
    "would": "VERB",
    "should": "VERB",
    "might": "VERB",
    "must": "VERB",
    "may": "VERB",
}

DECOMPOSITION_PROMPT = """You are a semantic analyst decomposing words into universal semantic primitives.

AVAILABLE PRIMITIVES (use ONLY these exact strings):
{primitives}

AVAILABLE ROLES (use ONLY these exact strings):
{roles}

Decompose the word "{word}" ({pos}) into 3-7 primitive-role pairs that capture its core meaning.

Rules:
1. Use ONLY primitives and roles from the lists above - exact spelling required
2. Every word needs at least 3 primitives to capture meaning properly
3. Include an action/state primitive (DO, BE, MOVE, THINK, FEEL, etc.)
4. Include relevant participants (SOMEONE, SOMETHING, PEOPLE, etc.)
5. Include evaluative or descriptive aspects if relevant

Examples:
- "run" (VERB): MOVE-action, SOMEONE-agent, DO-manner, BODY-instrument
- "happy" (ADJ): FEEL-state, GOOD-evaluation, SOMEONE-experiencer
- "and" (CONJ): SAME-relation, THIS-theme, OTHER-theme
- "the" (DET): THIS-theme, SAME-attribute, SOMETHING-patient
- "because" (CONJ): BECAUSE-cause, THIS-theme, HAPPEN-result

Output ONLY valid JSON in this exact format:
{{"decomposition": [["PRIMITIVE", "role"], ["PRIMITIVE", "role"], ...]}}

Decompose "{word}" ({pos}):"""


def load_frequency_words(filepath: str, start: int = 0, count: int = 100) -> List[Tuple[str, int]]:
    """Load words from frequency file."""
    words = []
    with open(filepath, "r") as f:
        for i, line in enumerate(f):
            if i < start:
                continue
            if i >= start + count:
                break

            line = line.strip()
            if not line or ":" not in line:
                continue

            # Parse "word: count" format
            parts = line.rsplit(":", 1)
            if len(parts) == 2:
                word = parts[0].strip()
                try:
                    freq = int(parts[1].strip())
                    words.append((word, freq))
                except ValueError:
                    continue

    return words


def guess_pos(word: str) -> str:
    """Guess part of speech for a word."""
    word_lower = word.lower()

    # Check defaults
    if word_lower in POS_DEFAULTS:
        return POS_DEFAULTS[word_lower]

    # Single letters/numbers
    if len(word) == 1:
        if word.isdigit():
            return "NUM"
        return "X"  # Unknown

    # All digits
    if word.isdigit():
        return "NUM"

    # Common suffixes
    if word.endswith("ing"):
        return "VERB"
    if word.endswith("ed"):
        return "VERB"
    if word.endswith("ly"):
        return "ADV"
    if word.endswith("tion") or word.endswith("sion"):
        return "NOUN"
    if word.endswith("ness") or word.endswith("ment"):
        return "NOUN"
    if word.endswith("able") or word.endswith("ible"):
        return "ADJ"
    if word.endswith("ful") or word.endswith("less"):
        return "ADJ"
    if word.endswith("ive") or word.endswith("ous"):
        return "ADJ"
    if word.endswith("er") or word.endswith("or"):
        return "NOUN"
    if word.endswith("ist") or word.endswith("ism"):
        return "NOUN"

    # Default to NOUN for unknown words
    return "NOUN"


def call_ollama(prompt: str, model: str = OLLAMA_MODEL, max_retries: int = 2) -> Optional[str]:
    """Call Ollama API with retries."""
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 256,
                    },
                },
                timeout=60,
            )
            if response.status_code == 200:
                return response.json().get("response", "")
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(0.5)
    return None


def parse_decomposition(response: str, word: str) -> Optional[List[Tuple[str, str]]]:
    """Parse and validate decomposition from LLM response."""
    try:
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return None

        json_str = text[start:end]
        data = json.loads(json_str)
        decomposition = data.get("decomposition", [])

        if not decomposition:
            return None

        valid_decomp = []
        for item in decomposition:
            if isinstance(item, list) and len(item) == 2:
                prim, role = item[0].upper(), item[1].lower()
            elif isinstance(item, dict):
                prim = item.get("primitive", "").upper()
                role = item.get("role", "").lower()
            else:
                continue

            if prim in PRIMITIVES and role in ROLES:
                valid_decomp.append((prim, role))

        if len(valid_decomp) < 2:
            return None

        return valid_decomp

    except Exception:
        return None


def enhance_word(word: str, pos: str, generator: LexiconGenerator) -> Optional[Dict]:
    """Generate enhanced decomposition for a word."""
    prompt = DECOMPOSITION_PROMPT.format(primitives=", ".join(PRIMITIVES), roles=", ".join(ROLES), word=word, pos=pos)

    response = call_ollama(prompt)
    if not response:
        return None

    decomposition = parse_decomposition(response, word)
    if not decomposition:
        return None

    vector = generator.encode_decomposition(decomposition)

    return {
        "decomposition": decomposition,
        "vector": vector.serialize(),
        "source": "ollama-enhanced",
        "confidence": 0.85,
    }


def update_or_insert_lexicon(
    conn: sqlite3.Connection,
    word: str,
    pos: str,
    decomposition: List[Tuple[str, str]],
    vector: bytes,
    source: str,
    confidence: float,
    frequency: int,
):
    """Update existing entry or insert new one."""
    # Check if entry exists
    existing = conn.execute("SELECT id FROM lexicon WHERE lemma = ? AND pos = ?", (word.lower(), pos)).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE lexicon
            SET decomposition = ?, vector = ?, source = ?, confidence = ?, frequency = ?
            WHERE id = ?
        """,
            (json.dumps(decomposition), vector, source, confidence, frequency / 10000.0, existing[0]),
        )
    else:
        conn.execute(
            """
            INSERT INTO lexicon (lemma, pos, sense_id, gloss, decomposition, vector, frequency, source, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                word.lower(),
                pos,
                f"{word.lower()}.{pos}.01",
                "",
                json.dumps(decomposition),
                vector,
                frequency / 10000.0,
                source,
                confidence,
            ),
        )


def log_failure(word: str, pos: str, freq: int, reason: str):
    """Log a failed enhancement."""
    with open(FAILURES_LOG, "a") as f:
        entry = {"timestamp": datetime.now().isoformat(), "word": word, "pos": pos, "frequency": freq, "reason": reason}
        f.write(json.dumps(entry) + "\n")


def process_batch(start: int, count: int = 100) -> Dict:
    """Process a batch of words from the frequency list."""
    print(f"\n{'=' * 70}")
    print(f"BATCH: Words {start + 1} to {start + count}")
    print(f"{'=' * 70}")

    # Initialize
    basis = PrimitiveBasis.generate(PRIMITIVES, ROLES)
    generator = LexiconGenerator(basis)
    conn = sqlite3.connect(DB_PATH)

    # Load words
    words = load_frequency_words(FREQ_FILE, start, count)
    print(f"Loaded {len(words)} words from frequency list")

    # Check Ollama
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code != 200:
            print("ERROR: Ollama not responding")
            return {"enhanced": 0, "failed": len(words), "skipped": 0}
    except Exception as e:
        print(f"ERROR: Ollama not available: {e}")
        return {"enhanced": 0, "failed": len(words), "skipped": 0}

    enhanced = 0
    failed = 0
    skipped = 0
    failures = []

    print("-" * 70)

    for i, (word, freq) in enumerate(words):
        word_lower = word.lower()

        # Skip single characters/numbers unless meaningful
        if len(word) == 1 and not word.isalpha():
            skipped += 1
            continue
        if word.isdigit():
            skipped += 1
            continue

        # Guess POS
        pos = guess_pos(word)
        if pos in ("NUM", "X"):
            skipped += 1
            continue

        print(f"[{start + i + 1}] {word:20} ({pos:6}) freq={freq}...", end=" ", flush=True)

        result = enhance_word(word, pos, generator)

        if result:
            update_or_insert_lexicon(
                conn,
                word_lower,
                pos,
                result["decomposition"],
                result["vector"],
                result["source"],
                result["confidence"],
                freq,
            )
            decomp_str = ", ".join([f"{p}-{r}" for p, r in result["decomposition"][:3]])
            print(f"✓ [{decomp_str}...]")
            enhanced += 1
        else:
            print("✗")
            failed += 1
            failures.append({"word": word, "pos": pos, "freq": freq})
            log_failure(word, pos, freq, "decomposition_failed")

        # Commit every 25 words
        if (i + 1) % 25 == 0:
            conn.commit()

        time.sleep(0.05)  # Small delay

    conn.commit()
    conn.close()

    # Summary
    print("-" * 70)
    print(f"BATCH SUMMARY (words {start + 1}-{start + count}):")
    print(f"  Enhanced: {enhanced}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped}")

    if failures:
        print(f"  Failed words: {', '.join([f['word'] for f in failures[:10]])}")
        if len(failures) > 10:
            print(f"    ... and {len(failures) - 10} more")

    return {
        "batch_start": start,
        "batch_end": start + count,
        "enhanced": enhanced,
        "failed": failed,
        "skipped": skipped,
        "failures": failures,
    }


def run_all_batches(total_words: int = 4000, batch_size: int = 100):
    """Run all batches and produce summary."""
    print("=" * 70)
    print("LEXICON ENHANCEMENT - FULL RUN")
    print(f"Processing first {total_words} words in batches of {batch_size}")
    print("=" * 70)

    # Clear failures log
    os.makedirs(os.path.dirname(FAILURES_LOG), exist_ok=True)
    open(FAILURES_LOG, "w").close()

    all_results = []
    total_enhanced = 0
    total_failed = 0
    total_skipped = 0

    for start in range(0, total_words, batch_size):
        result = process_batch(start, batch_size)
        all_results.append(result)
        total_enhanced += result["enhanced"]
        total_failed += result["failed"]
        total_skipped += result["skipped"]

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"Total Enhanced: {total_enhanced}")
    print(f"Total Failed: {total_failed}")
    print(f"Total Skipped: {total_skipped}")
    print(f"Success Rate: {total_enhanced / max(1, total_enhanced + total_failed) * 100:.1f}%")
    print(f"\nFailures logged to: {FAILURES_LOG}")

    # Save summary
    summary_path = "/Users/rohanvinaik/relational-ai/data/lexicon_enhancement_summary.json"
    with open(summary_path, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "total_words": total_words,
                "batch_size": batch_size,
                "total_enhanced": total_enhanced,
                "total_failed": total_failed,
                "total_skipped": total_skipped,
                "batches": all_results,
            },
            f,
            indent=2,
        )
    print(f"Summary saved to: {summary_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enhance lexicon from frequency list")
    parser.add_argument("--start", type=int, default=0, help="Starting word index")
    parser.add_argument("--count", type=int, default=100, help="Number of words to process")
    parser.add_argument("--all", action="store_true", help="Process all 4000 words")
    args = parser.parse_args()

    if args.all:
        run_all_batches(total_words=4000, batch_size=100)
    else:
        process_batch(args.start, args.count)
