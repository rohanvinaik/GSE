#!/usr/bin/env python3
"""
LLM-Based Semantic Decomposition

Re-decomposes words with poor or missing decompositions using Claude API.
Prioritizes high-frequency words that have semantic importance.

Usage:
    # Dry run (show what would be decomposed)
    python scripts/llm_decompose.py --dry-run --limit 50

    # Actually decompose top 200 words
    python scripts/llm_decompose.py --limit 200

    # Decompose specific word
    python scripts/llm_decompose.py --word "speed" --pos "NOUN"

Environment:
    ANTHROPIC_API_KEY - Your Claude API key
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from gse.primitives import PRIMITIVES, ROLES
from gse.vectors import PrimitiveBasis

# Try to import anthropic
try:
    import anthropic
except ImportError:
    anthropic = None


DECOMPOSITION_PROMPT = """You are a semantic analyst decomposing words into universal semantic primitives from Natural Semantic Metalanguage (NSM).

PRIMITIVES (use ONLY these 62 primitives):
{primitives}

ROLES (use ONLY these 30 roles):
{roles}

Decompose this word into primitive-role pairs that capture its core meaning.

Word: {word}
Part of speech: {pos}
Definition: {definition}

Output ONLY valid JSON in this exact format:
{{"decomposition": [
  {{"primitive": "PRIMITIVE_NAME", "role": "role_name"}},
  ...
]}}

Guidelines:
1. Use 3-8 primitive-role pairs (typical)
2. Focus on CORE meaning, not every nuance
3. Include:
   - An action/state primitive (DO, BE, MOVE, FEEL, etc.)
   - Who/what is involved (SOMEONE, SOMETHING, I, etc.)
   - Key attributes or manner
4. For antonyms, use the POSITIVE primitive with indication:
   - "sad" uses FEEL + GOOD (with evaluation=negative implied)
   - "small" uses BIG (negated)
5. For verbs: include agent, patient, action, and any result
6. For adjectives: include the attribute and what it applies to
7. For nouns: include what KIND of thing and key properties

Examples:

Word: "run" (VERB) - "move at a speed faster than a walk"
{{"decomposition": [
  {{"primitive": "MOVE", "role": "action"}},
  {{"primitive": "SOMEONE", "role": "agent"}},
  {{"primitive": "MUCH", "role": "manner"}},
  {{"primitive": "BODY", "role": "instrument"}},
  {{"primitive": "WHERE", "role": "path"}}
]}}

Word: "receive" (VERB) - "get something; come into possession of"
{{"decomposition": [
  {{"primitive": "HAVE", "role": "result"}},
  {{"primitive": "SOMEONE", "role": "recipient"}},
  {{"primitive": "SOMETHING", "role": "theme"}},
  {{"primitive": "SOMEONE", "role": "source"}},
  {{"primitive": "DO", "role": "action"}}
]}}

Word: "cover" (VERB) - "provide with a covering"
{{"decomposition": [
  {{"primitive": "DO", "role": "action"}},
  {{"primitive": "SOMEONE", "role": "agent"}},
  {{"primitive": "SOMETHING", "role": "instrument"}},
  {{"primitive": "ABOVE", "role": "location"}},
  {{"primitive": "SOMETHING", "role": "patient"}},
  {{"primitive": "SEE", "role": "result"}}
]}}

Now decompose: "{word}" ({pos}) - "{definition}"
"""


def get_client():
    """Get Anthropic client."""
    if anthropic is None:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")

    return anthropic.Anthropic(api_key=api_key)


def decompose_word(client, word: str, pos: str, definition: str) -> Optional[List[Tuple[str, str]]]:
    """Get LLM decomposition for a word."""
    prompt = DECOMPOSITION_PROMPT.format(
        primitives=", ".join(PRIMITIVES),
        roles=", ".join(ROLES),
        word=word,
        pos=pos,
        definition=definition or f"a {pos.lower()}",
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=500, messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()

        # Handle markdown code blocks
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                if "{" in part and "decomposition" in part:
                    text = part
                    break
            if text.startswith("json"):
                text = text[4:]

        text = text.strip()

        # Find JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]

        data = json.loads(text)
        decomposition = []

        for item in data.get("decomposition", []):
            prim = item.get("primitive", "").upper()
            role = item.get("role", "").lower()

            # Validate
            if prim not in PRIMITIVES:
                print(f"  Warning: Unknown primitive '{prim}', skipping")
                continue
            if role not in ROLES:
                print(f"  Warning: Unknown role '{role}', skipping")
                continue

            decomposition.append((prim, role))

        if len(decomposition) < 2:
            print(f"  Warning: Too few valid primitives ({len(decomposition)})")
            return None

        return decomposition

    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        print(f"  Response was: {text[:200]}...")
        return None
    except Exception as e:
        print(f"  API error: {e}")
        return None


def get_words_to_decompose(db_path: Path, limit: int = 100) -> List[Dict]:
    """Get prioritized list of words needing decomposition."""
    conn = sqlite3.connect(str(db_path))

    # Attach frequency database
    freq_path = db_path.parent / "frequency.db"
    if freq_path.exists():
        conn.execute(f"ATTACH '{freq_path}' AS freq")
        has_freq = True
    else:
        has_freq = False

    if has_freq:
        # Priority: high frequency + poor decomposition + real semantic words
        query = """
            SELECT l.id, l.lemma, l.pos, l.gloss, f.combined_rank as freq_rank
            FROM lexicon l
            LEFT JOIN freq.frequency f ON LOWER(l.lemma) = f.word
            WHERE (
                l.decomposition = '[[\"SOMETHING\", \"theme\"]]'
                OR l.decomposition = '[[\"SOMETHING\", \"attribute\"]]'
                OR l.decomposition LIKE '%[[\"SOMETHING\", \"theme\"]]' AND LENGTH(l.decomposition) < 60
            )
            AND LENGTH(l.lemma) > 2
            AND l.lemma NOT LIKE '%.%'
            AND l.lemma NOT GLOB '*[0-9]*'
            AND l.pos IN ('VERB', 'ADJ', 'ADV', 'NOUN')
            AND (l.gloss IS NULL OR l.gloss NOT LIKE 'Auto-generated%')
            ORDER BY
                CASE WHEN f.combined_rank IS NOT NULL THEN f.combined_rank ELSE 99999 END,
                l.confidence DESC
            LIMIT ?
        """
    else:
        query = """
            SELECT l.id, l.lemma, l.pos, l.gloss, 99999 as freq_rank
            FROM lexicon l
            WHERE (
                l.decomposition = '[[\"SOMETHING\", \"theme\"]]'
                OR l.decomposition = '[[\"SOMETHING\", \"attribute\"]]'
            )
            AND LENGTH(l.lemma) > 2
            AND l.pos IN ('VERB', 'ADJ', 'ADV', 'NOUN')
            ORDER BY l.frequency DESC
            LIMIT ?
        """

    rows = conn.execute(query, (limit,)).fetchall()
    conn.close()

    return [{"id": r[0], "lemma": r[1], "pos": r[2], "gloss": r[3] or "", "freq_rank": r[4]} for r in rows]


def update_decomposition(db_path: Path, basis: PrimitiveBasis, word_id: int, decomposition: List[Tuple[str, str]]):
    """Update database with new decomposition and re-encoded vector."""
    from gse.lexicon_generator import LexiconGenerator

    encoder = LexiconGenerator(basis)
    vector = encoder.encode_decomposition(decomposition)

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        UPDATE lexicon
        SET decomposition = ?, vector = ?, source = 'llm-redecompose', confidence = 0.85
        WHERE id = ?
    """,
        (json.dumps(decomposition), vector.serialize(), word_id),
    )
    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="LLM-based semantic decomposition")
    parser.add_argument("--limit", type=int, default=50, help="Max words to decompose")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--word", type=str, help="Decompose a specific word")
    parser.add_argument("--pos", type=str, default="NOUN", help="POS for specific word")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between API calls (seconds)")

    args = parser.parse_args()

    base = Path(__file__).parent.parent / "data"
    db_path = base / "lexicon.db"
    basis_path = base / "basis.msgpack"

    if not db_path.exists():
        print(f"ERROR: lexicon.db not found at {db_path}")
        return 1

    # Handle single word
    if args.word:
        if args.dry_run:
            print(f"Would decompose: {args.word} ({args.pos})")
            return 0

        client = get_client()
        basis = PrimitiveBasis.load(str(basis_path))

        print(f"Decomposing: {args.word} ({args.pos})")
        decomp = decompose_word(client, args.word, args.pos, "")

        if decomp:
            print(f"Result: {json.dumps(decomp, indent=2)}")
        else:
            print("Failed to decompose")
        return 0

    # Get words to decompose
    print(f"\nFinding top {args.limit} words needing decomposition...")
    words = get_words_to_decompose(db_path, args.limit)
    print(f"Found {len(words)} candidates")

    if args.dry_run:
        print("\n[DRY RUN] Words that would be decomposed:")
        print(f"{'Word':<20} {'POS':<6} {'Freq Rank':<10} {'Definition':<50}")
        print("-" * 90)
        for w in words[:50]:
            gloss = (w["gloss"][:47] + "...") if len(w["gloss"]) > 50 else w["gloss"]
            print(f"{w['lemma']:<20} {w['pos']:<6} {w['freq_rank']:<10} {gloss}")
        if len(words) > 50:
            print(f"... and {len(words) - 50} more")
        return 0

    # Actually decompose
    client = get_client()
    basis = PrimitiveBasis.load(str(basis_path))

    print(f"\nDecomposing {len(words)} words...")
    success = 0
    failed = 0

    for i, w in enumerate(words):
        print(f"\n[{i + 1}/{len(words)}] {w['lemma']} ({w['pos']}): {w['gloss'][:60]}...")

        decomp = decompose_word(client, w["lemma"], w["pos"], w["gloss"])

        if decomp:
            update_decomposition(db_path, basis, w["id"], decomp)
            print(f"  -> {decomp}")
            success += 1
        else:
            print("  -> FAILED")
            failed += 1

        time.sleep(args.delay)

    print(f"\n{'=' * 60}")
    print(f"Complete! Success: {success}, Failed: {failed}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
