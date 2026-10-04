#!/usr/bin/env python3
"""
Encode Proper Nouns in GSE Lexicon Database

Identifies likely proper nouns and assigns:
- SOMEONE=1 for person names
- SOMETHING=1 for places/organizations/other named entities

Uses heuristics:
1. Capitalized words
2. Known name patterns (endings like -son, -man, -ton, etc.)
3. Words with 0 primitives that look like names
"""

import argparse
import sqlite3
from pathlib import Path

# Conservative person name endings (avoid common verb/noun endings)
# Only use distinctive name-like patterns
PERSON_ENDINGS = [
    "mann",
    "berg",
    "stein",
    "baum",  # German names
    "ski",
    "sky",
    "ovich",
    "evich",
    "ova",
    "eva",  # Slavic names
]

# Conservative place name endings (avoid common words)
PLACE_ENDINGS = [
    "istan",
    "burg",
    "burgh",  # Distinctive place endings
]

# Known person first names (common ones)
PERSON_NAMES = {
    "james",
    "john",
    "robert",
    "michael",
    "david",
    "william",
    "richard",
    "joseph",
    "thomas",
    "charles",
    "mary",
    "patricia",
    "jennifer",
    "linda",
    "elizabeth",
    "barbara",
    "susan",
    "jessica",
    "sarah",
    "karen",
    "emily",
    "washington",
    "lincoln",
    "jefferson",
    "roosevelt",
    "kennedy",
    "obama",
    "trump",
    "biden",
    "clinton",
    "bush",
    "reagan",
    "nixon",
    "carter",
    "darwin",
    "einstein",
    "newton",
    "galileo",
    "edison",
    "tesla",
    "shakespeare",
    "dickens",
    "austen",
    "hemingway",
    "fitzgerald",
    "marx",
    "freud",
    "jung",
    "nietzsche",
    "kant",
    "plato",
    "aristotle",
    "peter",
    "paul",
    "matthew",
    "mark",
    "luke",
    "john",
    "moses",
    "abraham",
}

# Known organization/brand names (common ones)
ORG_NAMES = {
    "google",
    "apple",
    "microsoft",
    "amazon",
    "facebook",
    "twitter",
    "fbi",
    "cia",
    "nasa",
    "fda",
    "epa",
    "irs",
    "sec",
    "doj",
    "un",
    "who",
    "nato",
    "eu",
    "unicef",
    "unesco",
    "nfl",
    "nba",
    "mlb",
    "nhl",
    "fifa",
    "olympic",
    "harvard",
    "yale",
    "princeton",
    "stanford",
    "mit",
    "oxford",
    "cambridge",
    "cnn",
    "bbc",
    "nbc",
    "abc",
    "cbs",
    "fox",
    "nyt",
    "wsj",
}

# Known place names (common ones)
PLACE_NAMES = {
    "america",
    "africa",
    "asia",
    "europe",
    "australia",
    "antarctica",
    "america",
    "canada",
    "mexico",
    "brazil",
    "argentina",
    "chile",
    "england",
    "france",
    "germany",
    "italy",
    "spain",
    "portugal",
    "russia",
    "china",
    "japan",
    "korea",
    "india",
    "pakistan",
    "israel",
    "egypt",
    "iran",
    "iraq",
    "syria",
    "turkey",
    "california",
    "texas",
    "florida",
    "york",
    "alaska",
    "hawaii",
    "london",
    "paris",
    "berlin",
    "rome",
    "madrid",
    "moscow",
    "tokyo",
    "atlantic",
    "pacific",
    "indian",
    "arctic",
    "mediterranean",
    "mississippi",
    "amazon",
    "nile",
    "ganges",
    "danube",
    "rhine",
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "colorado",
    "connecticut",
    "delaware",
    "georgia",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "hampshire",
    "jersey",
    "mexico",
    "carolina",
    "dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode",
    "tennessee",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "wisconsin",
    "wyoming",
}


def is_likely_person_name(word: str) -> bool:
    """Check if word looks like a person name."""
    word_lower = word.lower()

    # Known person names
    if word_lower in PERSON_NAMES:
        return True

    # Person name endings
    for ending in PERSON_ENDINGS:
        if word_lower.endswith(ending) and len(word_lower) > len(ending) + 2:
            return True

    return False


def is_likely_place_name(word: str) -> bool:
    """Check if word looks like a place name."""
    word_lower = word.lower()

    # Known place names
    if word_lower in PLACE_NAMES:
        return True

    # Place name endings
    for ending in PLACE_ENDINGS:
        if word_lower.endswith(ending) and len(word_lower) > len(ending) + 2:
            return True

    return False


def is_likely_org_name(word: str) -> bool:
    """Check if word looks like an organization name."""
    word_lower = word.lower()
    return word_lower in ORG_NAMES


def encode_proper_nouns(db_path: Path, dry_run: bool = False) -> dict:
    """
    Identify and encode proper nouns.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {
        "analyzed": 0,
        "persons": 0,
        "places": 0,
        "orgs": 0,
        "skipped": 0,
    }

    # Get words with 0 primitives (unencoded)
    cursor.execute("""
        SELECT l.id, l.lemma
        FROM lexemes l
        LEFT JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.value != 0
        WHERE l.component_type = 'ATOMIC'
        GROUP BY l.id
        HAVING COUNT(pv.id) = 0
        ORDER BY l.frequency_rank
    """)

    words = cursor.fetchall()
    print(f"Analyzing {len(words)} unencoded words...")

    for lexeme_id, lemma in words:
        stats["analyzed"] += 1

        # Classify the word
        entity_type = None
        primitive = None

        if is_likely_person_name(lemma):
            entity_type = "PERSON"
            primitive = "SOMEONE"
            stats["persons"] += 1
        elif is_likely_place_name(lemma):
            entity_type = "PLACE"
            primitive = "SOMETHING"
            stats["places"] += 1
        elif is_likely_org_name(lemma):
            entity_type = "ORG"
            primitive = "SOMETHING"
            stats["orgs"] += 1
        else:
            stats["skipped"] += 1
            continue

        if not dry_run:
            # Set the primitive
            cursor.execute(
                """
                INSERT INTO primitive_values (lexeme_id, primitive, value, source)
                VALUES (?, ?, 1, 'proper_noun_encoding')
                ON CONFLICT(lexeme_id, primitive)
                DO UPDATE SET value = 1, source = 'proper_noun_encoding'
            """,
                (lexeme_id, primitive),
            )

            # Set animacy
            animacy = "ANIMATE" if entity_type == "PERSON" else "INANIMATE"
            cursor.execute(
                """
                UPDATE lexemes SET animacy = ? WHERE id = ?
            """,
                (animacy, lexeme_id),
            )

            # Add entity type as gram feature
            cursor.execute(
                """
                INSERT INTO gram_feature_values (lexeme_id, feature, value, source)
                VALUES (?, 'entity_type', ?, 'proper_noun_encoding')
                ON CONFLICT(lexeme_id, feature)
                DO UPDATE SET value = ?, source = 'proper_noun_encoding'
            """,
                (lexeme_id, entity_type, entity_type),
            )

        print(f"  {lemma}: {entity_type} -> {primitive}=1")

    if not dry_run:
        conn.commit()

    conn.close()
    return stats


def verify_proper_nouns(db_path: Path) -> None:
    """Show current state of proper noun encodings."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=== Proper Noun Encoding Verification ===\n")

    # Count by entity type
    cursor.execute("""
        SELECT value, COUNT(*) as cnt
        FROM gram_feature_values
        WHERE feature = 'entity_type'
        GROUP BY value
    """)

    rows = cursor.fetchall()
    print("By Entity Type:")
    for entity_type, count in rows:
        print(f"  {entity_type}: {count}")

    # Sample proper nouns
    print("\nSample Proper Nouns:")
    for entity_type in ["PERSON", "PLACE", "ORG"]:
        cursor.execute(
            """
            SELECT l.lemma FROM gram_feature_values g
            JOIN lexemes l ON g.lexeme_id = l.id
            WHERE g.feature = 'entity_type' AND g.value = ?
            LIMIT 5
        """,
            (entity_type,),
        )
        words = [r[0] for r in cursor.fetchall()]
        if words:
            print(f"  {entity_type}: {', '.join(words)}")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Encode proper nouns in GSE lexicon")
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--verify", action="store_true", help="Verify current encodings")
    args = parser.parse_args()

    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        exit(1)

    if args.verify:
        verify_proper_nouns(db_path)
        exit(0)

    print("=== Encoding Proper Nouns ===")
    print(f"Database: {db_path}")
    print()

    stats = encode_proper_nouns(db_path, dry_run=args.dry_run)

    print()
    print("=== Summary ===")
    print(f"Words analyzed: {stats['analyzed']}")
    print(f"Persons identified: {stats['persons']}")
    print(f"Places identified: {stats['places']}")
    print(f"Organizations identified: {stats['orgs']}")
    print(f"Skipped (unrecognized): {stats['skipped']}")

    if args.dry_run:
        print("\n[DRY RUN] No changes applied")
