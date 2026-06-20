#!/usr/bin/env python3
"""
Lexicon Enhancement Script
--------------------------
Enhances lexicon entries with proper semantic decompositions using Ollama.

Prioritizes words by frequency and ensures the top 1000+ words have
robust characterizations (3+ primitives per word).
"""
import json
import os
import sqlite3
import sys
import time
from typing import Dict, List, Optional, Tuple

import requests

sys.path.insert(0, '/Users/rohanvinaik/gse')
from gse.lexicon_generator import LexiconGenerator
from gse.primitives import PRIMITIVES, ROLES
from gse.vectors import PrimitiveBasis

# Configuration
DB_PATH = '/Users/rohanvinaik/gse/data/lexicon.db'
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
OLLAMA_MODEL = 'llama3.2:3b'  # Fast model for decomposition

# Decomposition prompt template
DECOMPOSITION_PROMPT = '''You are a semantic analyst decomposing words into universal semantic primitives.

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
- "family" (NOUN): PEOPLE-theme, SAME-attribute, LIVE-state, GOOD-evaluation
- "school" (NOUN): SOMETHING-theme, KNOW-purpose, PEOPLE-participant, WHERE-location
- "keep" (VERB): HAVE-action, SOMEONE-agent, SOMETHING-theme, LONG_TIME-duration

Output ONLY valid JSON in this exact format:
{{"decomposition": [["PRIMITIVE", "role"], ["PRIMITIVE", "role"], ...]}}

Decompose "{word}" ({pos}):'''


def call_ollama(prompt: str, model: str = OLLAMA_MODEL, max_retries: int = 3) -> Optional[str]:
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
                    }
                },
                timeout=60
            )
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                print(f"  Ollama error: {response.status_code}")
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            time.sleep(1)
    return None


def parse_decomposition(response: str, word: str) -> Optional[List[Tuple[str, str]]]:
    """Parse and validate decomposition from LLM response."""
    try:
        # Clean up response
        text = response.strip()

        # Find JSON in response
        start = text.find('{')
        end = text.rfind('}') + 1
        if start == -1 or end == 0:
            print(f"  No JSON found in response for {word}")
            return None

        json_str = text[start:end]
        data = json.loads(json_str)

        decomposition = data.get("decomposition", [])
        if not decomposition:
            print(f"  Empty decomposition for {word}")
            return None

        # Validate and convert to tuples
        valid_decomp = []
        for item in decomposition:
            if isinstance(item, list) and len(item) == 2:
                prim, role = item[0].upper(), item[1].lower()
            elif isinstance(item, dict):
                prim = item.get("primitive", "").upper()
                role = item.get("role", "").lower()
            else:
                continue

            # Validate against allowed primitives and roles
            if prim in PRIMITIVES and role in ROLES:
                valid_decomp.append((prim, role))
            else:
                if prim not in PRIMITIVES:
                    print(f"    Invalid primitive: {prim}")
                if role not in ROLES:
                    print(f"    Invalid role: {role}")

        if len(valid_decomp) < 2:
            print(f"  Too few valid primitives for {word}: {len(valid_decomp)}")
            return None

        return valid_decomp

    except json.JSONDecodeError as e:
        print(f"  JSON parse error for {word}: {e}")
        return None
    except Exception as e:
        print(f"  Parse error for {word}: {e}")
        return None


def enhance_word(word: str, pos: str, generator: LexiconGenerator) -> Optional[Dict]:
    """Generate enhanced decomposition for a word."""
    prompt = DECOMPOSITION_PROMPT.format(
        primitives=", ".join(PRIMITIVES),
        roles=", ".join(ROLES),
        word=word,
        pos=pos
    )

    response = call_ollama(prompt)
    if not response:
        return None

    decomposition = parse_decomposition(response, word)
    if not decomposition:
        return None

    # Encode to vector
    vector = generator.encode_decomposition(decomposition)

    return {
        "decomposition": decomposition,
        "vector": vector.serialize(),
        "source": "ollama-enhanced",
        "confidence": 0.85
    }


def get_words_to_enhance(conn: sqlite3.Connection, limit: int = 1000, min_primitives: int = 3) -> List[Dict]:
    """Get words that need enhancement, sorted by frequency."""
    rows = conn.execute("""
        SELECT lemma, pos, decomposition, frequency, id
        FROM lexicon
        WHERE json_array_length(decomposition) < ?
        ORDER BY frequency DESC
        LIMIT ?
    """, (min_primitives, limit)).fetchall()

    return [
        {"id": row[4], "lemma": row[0], "pos": row[1],
         "current_decomp": json.loads(row[2]), "frequency": row[3]}
        for row in rows
    ]


def update_lexicon_entry(conn: sqlite3.Connection, entry_id: int,
                         decomposition: List[Tuple[str, str]],
                         vector: bytes, source: str, confidence: float):
    """Update a lexicon entry with new decomposition."""
    conn.execute("""
        UPDATE lexicon
        SET decomposition = ?, vector = ?, source = ?, confidence = ?
        WHERE id = ?
    """, (json.dumps(decomposition), vector, source, confidence, entry_id))


def run_enhancement(target_count: int = 1000, batch_size: int = 50):
    """Run lexicon enhancement."""
    print("=" * 70)
    print("LEXICON ENHANCEMENT")
    print("=" * 70)

    # Initialize
    basis = PrimitiveBasis.generate(PRIMITIVES, ROLES)
    generator = LexiconGenerator(basis)
    conn = sqlite3.connect(DB_PATH)

    # Get words to enhance
    print(f"\nFinding top {target_count} words needing enhancement...")
    words_to_enhance = get_words_to_enhance(conn, target_count)
    print(f"Found {len(words_to_enhance)} words to enhance")

    # Check Ollama
    print(f"\nChecking Ollama at {OLLAMA_URL}...")
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            if any(OLLAMA_MODEL.split(":")[0] in m for m in models):
                print(f"  ✓ Ollama ready with {OLLAMA_MODEL}")
            else:
                print(f"  Available models: {models}")
                print(f"  Warning: {OLLAMA_MODEL} not found, will try anyway")
        else:
            print(f"  Ollama error: {resp.status_code}")
            return
    except Exception as e:
        print(f"  Ollama not available: {e}")
        return

    # Process in batches
    enhanced_count = 0
    failed_count = 0

    print(f"\nEnhancing words in batches of {batch_size}...")
    print("-" * 70)

    for i, word_info in enumerate(words_to_enhance):
        word = word_info["lemma"]
        pos = word_info["pos"]
        entry_id = word_info["id"]
        freq = word_info["frequency"]

        print(f"[{i+1}/{len(words_to_enhance)}] {word} ({pos}) freq={freq:.2f}...", end=" ")

        result = enhance_word(word, pos, generator)

        if result:
            update_lexicon_entry(
                conn, entry_id,
                result["decomposition"],
                result["vector"],
                result["source"],
                result["confidence"]
            )
            decomp_str = ", ".join([f"{p}-{r}" for p, r in result["decomposition"][:4]])
            print(f"✓ [{decomp_str}...]")
            enhanced_count += 1
        else:
            print("✗ failed")
            failed_count += 1

        # Commit every batch
        if (i + 1) % batch_size == 0:
            conn.commit()
            print(f"\n  Committed batch. Enhanced: {enhanced_count}, Failed: {failed_count}")
            print("-" * 70)

        # Small delay to avoid overwhelming Ollama
        time.sleep(0.1)

    # Final commit
    conn.commit()
    conn.close()

    print("\n" + "=" * 70)
    print("ENHANCEMENT COMPLETE")
    print("=" * 70)
    print(f"  Enhanced: {enhanced_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Success rate: {enhanced_count / max(1, enhanced_count + failed_count) * 100:.1f}%")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Enhance lexicon decompositions")
    parser.add_argument("--count", type=int, default=100, help="Number of words to enhance")
    parser.add_argument("--batch", type=int, default=50, help="Batch size for commits")
    args = parser.parse_args()

    run_enhancement(target_count=args.count, batch_size=args.batch)
