#!/usr/bin/env python3
"""
Apply Manual Lexicon Fixes from JSONL file
"""
import json
import sqlite3
import sys

sys.path.insert(0, '/Users/rohanvinaik/gse')
from gse.lexicon_generator import LexiconGenerator
from gse.primitives import PRIMITIVES, ROLES
from gse.vectors import PrimitiveBasis

DB_PATH = '/Users/rohanvinaik/gse/data/lexicon.db'
FIXES_FILE = '/Users/rohanvinaik/relational-ai/manual_lexicon_fixes.jsonl'

# Role corrections for common typos/invalid roles
ROLE_CORRECTIONS = {
    'maaner': 'manner',
    'manners': 'manner',
    'part': 'attribute',
    'group': 'theme',
    'perception': 'state',
    'structure': 'theme',
    'connection': 'relation',
    'scope': 'quantity',
    'process': 'manner',
    'energy': 'attribute',
    'function': 'goal',
    'method': 'manner',
    'measure': 'quantity',
    'capability': 'evaluation',
    'comparison': 'relation',
    'have': 'state',
    'move': 'action',
    'see': 'action',
    'do': 'action',
    'bad': 'evaluation',
    'same': 'attribute',
    'here': 'location',
}

# Primitive corrections for invalid primitives
PRIMITIVE_CORRECTIONS = {
    'MANY': 'MUCH',
    'TIME': 'MOMENT',
    'NEW': 'OTHER',
    'CHANGE': 'MOVE',
    'CONTROL': 'DO',
    'GIVE': 'HAVE',
    'CAUSE': 'BECAUSE',
    'CHECK': 'SEE',
    'water': 'SOMETHING',
    'cause': 'BECAUSE',
    'time': 'MOMENT',
    'machine': 'SOMETHING',
    'rule': 'DO',
    'symbol': 'WORDS',
    'do': 'DO',
}


def validate_and_fix(decomposition):
    """Validate and fix decomposition, returning corrected version or None if unfixable."""
    fixed = []
    for item in decomposition:
        if isinstance(item, dict):
            prim = item.get('primitive', '').upper()
            role = item.get('role', '').lower()
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            prim, role = item[0].upper(), item[1].lower()
        else:
            continue

        # Apply corrections
        if prim in PRIMITIVE_CORRECTIONS:
            prim = PRIMITIVE_CORRECTIONS[prim]
        if role in ROLE_CORRECTIONS:
            role = ROLE_CORRECTIONS[role]

        # Validate
        if prim in PRIMITIVES and role in ROLES:
            fixed.append((prim, role))

    return fixed if len(fixed) >= 1 else None


def apply_fixes():
    """Apply all fixes from JSONL file."""
    print("=" * 70)
    print("APPLYING MANUAL LEXICON FIXES")
    print("=" * 70)

    # Initialize
    basis = PrimitiveBasis.generate(PRIMITIVES, ROLES)
    generator = LexiconGenerator(basis)
    conn = sqlite3.connect(DB_PATH)

    # Load fixes
    fixes = []
    with open(FIXES_FILE, 'r') as f:
        for line in f:
            if line.strip():
                fixes.append(json.loads(line))

    print(f"Loaded {len(fixes)} fixes from {FIXES_FILE}")
    print("-" * 70)

    applied = 0
    skipped = 0
    invalid = []

    for fix in fixes:
        word = fix['word']
        pos = fix['pos']
        decomp_raw = fix['decomposition']

        # Validate and fix
        decomp = validate_and_fix(decomp_raw)

        if not decomp:
            invalid.append((word, pos, decomp_raw))
            skipped += 1
            continue

        # Ensure minimum 3 primitives for good coverage
        if len(decomp) < 2:
            # Try to pad with reasonable defaults based on POS
            if pos == 'NOUN':
                decomp.append(('SOMETHING', 'theme'))
                decomp.append(('BE', 'state'))
            elif pos == 'VERB':
                decomp.append(('DO', 'action'))
                decomp.append(('SOMEONE', 'agent'))
            elif pos == 'ADJ':
                decomp.append(('BE', 'state'))
                decomp.append(('SOMETHING', 'theme'))
            elif pos == 'ADV':
                decomp.append(('BE', 'manner'))

        # Encode to vector
        vector = generator.encode_decomposition(decomp)

        # Check if entry exists
        existing = conn.execute(
            "SELECT id FROM lexicon WHERE lemma = ? AND pos = ?",
            (word.lower(), pos)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE lexicon
                SET decomposition = ?, vector = ?, source = ?, confidence = ?
                WHERE id = ?
            """, (json.dumps(decomp), vector.serialize(), 'manual-fix', 0.90, existing[0]))
        else:
            conn.execute("""
                INSERT INTO lexicon (lemma, pos, sense_id, gloss, decomposition, vector, frequency, source, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (word.lower(), pos, f"{word.lower()}.{pos}.01", "",
                  json.dumps(decomp), vector.serialize(), 0.5, 'manual-fix', 0.90))

        decomp_str = ", ".join([f"{p}-{r}" for p, r in decomp[:3]])
        print(f"  {word:20} ({pos:6}) -> [{decomp_str}...]")
        applied += 1

        # Commit every 50
        if applied % 50 == 0:
            conn.commit()

    conn.commit()
    conn.close()

    print("-" * 70)
    print("SUMMARY:")
    print(f"  Applied: {applied}")
    print(f"  Skipped (invalid): {skipped}")

    if invalid:
        print("\nInvalid entries (could not fix):")
        for word, pos, decomp in invalid[:10]:
            print(f"  - {word} ({pos}): {decomp}")
        if len(invalid) > 10:
            print(f"  ... and {len(invalid) - 10} more")

    return applied, skipped


if __name__ == "__main__":
    apply_fixes()
