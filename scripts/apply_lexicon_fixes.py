#!/usr/bin/env python3
"""
Lexicon Fix Implementation
Applies fixes specified in prompts/lexicon_fixes.md

Run with: python scripts/apply_lexicon_fixes.py --db data/lexicon.db
"""

import argparse
import logging
import sqlite3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Word lists for each fix category
FUNCTION_WORDS = [
    'the', 'of', 'and', 'to', 'a', 'in', 'is', 'that', 'for', 'it',
    'with', 'as', 'on', 'at', 'by', 'from', 'or', 'an', 'be', 'this',
    'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had', 'not',
    'but', 'if', 'which', 'their', 'so', 'what', 'when', 'into', 'than',
    'its', 'any', 'no', 'do', 'how', 'up', 'out', 'just', 'about'
]

SAY_FALSE_POSITIVES = [
    'you', 'me', 'people', 'life', 'time', 'system', 'being',
    'example', 'human', 'social', 'world', 'control', 'something',
    'person', 'order', 'love', 'everything', 'protein', 'health',
    'living', 'water', 'relationship', 'sense', 'feeling', 'activity',
    'bit', 'food', 'air', 'medicine', 'hot', 'reaction', 'motion',
    'fish', 'eat', 'mushroom', 'caffeine', 'liquid', 'consumption',
    'fluid', 'salt', 'feed', 'pleasure', 'treat'
]

SPEECH_WORDS = [
    'said', 'told', 'word', 'language', 'response', 'communication',
    'expression', 'teaching', 'explain', 'saying', 'speaking', 'speech',
    'conversation', 'ask', 'answer', 'describe', 'introduction',
    'discussion', 'offer', 'argument', 'statement', 'feedback',
    'storytelling', 'talking', 'chat', 'promise', 'emphasis',
    'introduce', 'spoke', 'stated', 'ordered', 'conversational',
    'participation', 'sentence'
]

FEEL_FALSE_POSITIVES = [
    'time', 'system', 'structure', 'theory', 'energy', 'network',
    'result', 'production', 'resources', 'quality', 'war',
    'organization', 'management', 'policy', 'law', 'school',
    'body', 'death', 'past', 'full', 'weight', 'loss', 'operation',
    'trade', 'machine', 'error', 'music', 'ground', 'base',
    'established', 'period', 'constant', 'lines', 'effort',
    'strength', 'architecture', 'exchange', 'concentration',
    'assembly', 'statistical', 'sample', 'variable', 'spike',
    'assessment', 'university', 'government', 'economy', 'budget',
    'differential', 'mathematical', 'hypothesis', 'score',
    'execution', 'perturbation', 'mail', 'sun', 'fire', 'electric',
    'phone', 'birth', 'title', 'proof', 'challenge'
]

HIGH_VALENCE_WORDS = ['life', 'birth', 'cash', 'confidence', 'robustness']

FIRST_PERSON = ['i', 'me', 'my', 'myself', 'mine']
SECOND_PERSON = ['you', 'your', 'yourself', 'yours']
THIRD_PERSON = [
    'he', 'she', 'him', 'her', 'his', 'hers', 'himself', 'herself',
    'they', 'them', 'their', 'themselves', 'someone', 'somebody',
    'anyone', 'anybody', 'everyone', 'everybody', 'nobody',
    'person', 'people'
]


def apply_fixes(db_path: str, dry_run: bool = False):
    """Apply all lexicon fixes."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {
        'function_words': 0,
        'say_false_positives': 0,
        'words_added': 0,
        'feel_false_positives': 0,
        'good_fixes': 0,
        'pronoun_fixes': 0,
    }

    # Fix 1: Function words - reset all to 0
    logger.info("Fix 1: Resetting function words...")
    placeholders = ','.join(['?'] * len(FUNCTION_WORDS))
    cursor.execute(f"""
        UPDATE primitive_values
        SET value = 0, confidence = 0.9, source = 'fix:function_word'
        WHERE lexeme_id IN (
            SELECT id FROM lexemes WHERE lemma IN ({placeholders})
        )
    """, FUNCTION_WORDS)
    stats['function_words'] = cursor.rowcount
    logger.info(f"  -> Reset {cursor.rowcount} primitive values")

    # Fix 2a: SAY=0 for false positives
    logger.info("Fix 2a: Setting SAY=0 for false positives...")
    placeholders = ','.join(['?'] * len(SAY_FALSE_POSITIVES))
    cursor.execute(f"""
        UPDATE primitive_values
        SET value = 0, confidence = 0.8, source = 'fix:say_false_positive'
        WHERE primitive = 'SAY'
        AND lexeme_id IN (
            SELECT id FROM lexemes WHERE lemma IN ({placeholders})
        )
    """, SAY_FALSE_POSITIVES)
    stats['say_false_positives'] = cursor.rowcount
    logger.info(f"  -> Updated {cursor.rowcount} SAY values")

    # Fix 2b: WORDS=1 for speech-related words with SAY=1
    logger.info("Fix 2b: Setting WORDS=1 for speech words...")
    placeholders = ','.join(['?'] * len(SPEECH_WORDS))
    cursor.execute(f"""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'WORDS', 1, 0.85, 'fix:say_requires_words'
        FROM lexemes WHERE lemma IN ({placeholders})
    """, SPEECH_WORDS)
    stats['words_added'] = cursor.rowcount
    logger.info(f"  -> Set WORDS=1 for {cursor.rowcount} words")

    # Fix 3: FEEL=0 for abstract/inanimate
    logger.info("Fix 3: Setting FEEL=0 for abstract/inanimate words...")
    placeholders = ','.join(['?'] * len(FEEL_FALSE_POSITIVES))
    cursor.execute(f"""
        UPDATE primitive_values
        SET value = 0, confidence = 0.8, source = 'fix:feel_false_positive'
        WHERE primitive = 'FEEL'
        AND lexeme_id IN (
            SELECT id FROM lexemes WHERE lemma IN ({placeholders})
        )
    """, FEEL_FALSE_POSITIVES)
    stats['feel_false_positives'] = cursor.rowcount
    logger.info(f"  -> Updated {cursor.rowcount} FEEL values")

    # Fix 4: GOOD=1 for high-valence words
    logger.info("Fix 4: Setting GOOD=1 for high-valence words...")
    placeholders = ','.join(['?'] * len(HIGH_VALENCE_WORDS))
    cursor.execute(f"""
        UPDATE primitive_values
        SET value = 1, confidence = 0.9, source = 'fix:nrc_vad_positive'
        WHERE primitive = 'GOOD'
        AND lexeme_id IN (
            SELECT id FROM lexemes WHERE lemma IN ({placeholders})
        )
    """, HIGH_VALENCE_WORDS)
    stats['good_fixes'] = cursor.rowcount
    logger.info(f"  -> Updated {cursor.rowcount} GOOD values")

    # Fix 5a: First person pronouns - I=1, SOMEONE=1
    logger.info("Fix 5a: Setting I=1, SOMEONE=1 for first person pronouns...")
    placeholders = ','.join(['?'] * len(FIRST_PERSON))
    cursor.execute(f"""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'I', 1, 0.95, 'fix:pronoun_first_person'
        FROM lexemes WHERE lemma IN ({placeholders})
    """, FIRST_PERSON)
    cursor.execute(f"""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'SOMEONE', 1, 0.95, 'fix:pronoun_first_person'
        FROM lexemes WHERE lemma IN ({placeholders})
    """, FIRST_PERSON)

    # Fix 5b: Second person pronouns - YOU=1, SOMEONE=1
    logger.info("Fix 5b: Setting YOU=1, SOMEONE=1 for second person pronouns...")
    placeholders = ','.join(['?'] * len(SECOND_PERSON))
    cursor.execute(f"""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'YOU', 1, 0.95, 'fix:pronoun_second_person'
        FROM lexemes WHERE lemma IN ({placeholders})
    """, SECOND_PERSON)
    cursor.execute(f"""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'SOMEONE', 1, 0.95, 'fix:pronoun_second_person'
        FROM lexemes WHERE lemma IN ({placeholders})
    """, SECOND_PERSON)

    # Fix 5c: Third person pronouns - SOMEONE=1
    logger.info("Fix 5c: Setting SOMEONE=1 for third person pronouns...")
    placeholders = ','.join(['?'] * len(THIRD_PERSON))
    cursor.execute(f"""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'SOMEONE', 1, 0.9, 'fix:pronoun_third_person'
        FROM lexemes WHERE lemma IN ({placeholders})
    """, THIRD_PERSON)

    stats['pronoun_fixes'] = len(FIRST_PERSON) * 2 + len(SECOND_PERSON) * 2 + len(THIRD_PERSON)

    if dry_run:
        logger.info("DRY RUN - Rolling back changes...")
        conn.rollback()
    else:
        conn.commit()
        logger.info("Changes committed to database")

    # Summary
    cursor.execute("SELECT COUNT(DISTINCT lexeme_id) FROM primitive_values WHERE source LIKE 'fix:%'")
    result = cursor.fetchone()
    fixed_words = result[0] if result else 0

    cursor.execute("SELECT COUNT(*) FROM primitive_values WHERE source LIKE 'fix:%'")
    result = cursor.fetchone()
    fixed_values = result[0] if result else 0

    print("\n" + "=" * 50)
    print("LEXICON FIXES SUMMARY")
    print("=" * 50)
    print(f"Function word primitives reset: {stats['function_words']}")
    print(f"SAY false positives fixed:      {stats['say_false_positives']}")
    print(f"WORDS=1 added for speech words: {stats['words_added']}")
    print(f"FEEL false positives fixed:     {stats['feel_false_positives']}")
    print(f"GOOD valence fixes:             {stats['good_fixes']}")
    print(f"Pronoun fixes applied:          {stats['pronoun_fixes']}")
    print("-" * 50)
    print(f"Total words affected:           {fixed_words}")
    print(f"Total primitive values modified:{fixed_values}")
    print("=" * 50)

    conn.close()
    return stats


def verify_fixes(db_path: str):
    """Run verification queries."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 50)
    print("VERIFICATION")
    print("=" * 50)

    # 1. Check function words
    cursor.execute("""
        SELECT l.lemma, COUNT(*) as active
        FROM lexemes l
        JOIN primitive_values pv ON l.id = pv.lexeme_id
        WHERE l.lemma IN ('the', 'of', 'and', 'to', 'a', 'is')
        AND pv.value != 0
        GROUP BY l.lemma
    """)
    results = cursor.fetchall()
    print(f"\n1. Function words with active primitives: {len(results)}")
    if results:
        for lemma, count in results:
            print(f"   WARNING: {lemma} has {count} active primitives")
    else:
        print("   OK - All function words have 0 active primitives")

    # 2. Check SAY/WORDS consistency
    cursor.execute("""
        SELECT l.lemma
        FROM lexemes l
        JOIN primitive_values say ON l.id = say.lexeme_id AND say.primitive = 'SAY'
        LEFT JOIN primitive_values words ON l.id = words.lexeme_id AND words.primitive = 'WORDS'
        WHERE say.value = 1 AND (words.value IS NULL OR words.value = 0)
        AND l.lemma IN ('said', 'told', 'speak', 'conversation', 'speech')
    """)
    results = cursor.fetchall()
    print(f"\n2. Speech words missing WORDS=1: {len(results)}")
    if results:
        for (lemma,) in results:
            print(f"   WARNING: {lemma} has SAY=1 but WORDS!=1")
    else:
        print("   OK - All speech words have WORDS=1")

    # 3. Check pronouns
    cursor.execute("""
        SELECT l.lemma, GROUP_CONCAT(p.primitive || '=' || p.value)
        FROM lexemes l
        JOIN primitive_values p ON l.id = p.lexeme_id
        WHERE l.lemma IN ('i', 'me', 'you', 'he', 'she')
        AND p.primitive IN ('I', 'YOU', 'SOMEONE')
        GROUP BY l.lemma
    """)
    results = cursor.fetchall()
    print("\n3. Pronoun primitives:")
    for lemma, prims in results:
        print(f"   {lemma}: {prims}")

    # 4. Count fixes by source
    cursor.execute("""
        SELECT source, COUNT(*) as count
        FROM primitive_values
        WHERE source LIKE 'fix:%'
        GROUP BY source
        ORDER BY count DESC
    """)
    results = cursor.fetchall()
    print("\n4. Fixes by source:")
    for source, count in results:
        print(f"   {source}: {count}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Apply lexicon fixes")
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without committing")
    parser.add_argument("--verify-only", action="store_true", help="Only run verification queries")

    args = parser.parse_args()

    if args.verify_only:
        verify_fixes(args.db)
    else:
        apply_fixes(args.db, dry_run=args.dry_run)
        verify_fixes(args.db)


if __name__ == "__main__":
    main()
