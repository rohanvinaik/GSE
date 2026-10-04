#!/usr/bin/env python3
"""
Rebuild GSE Lexicon from All External Sources

This script builds a fresh GSE lexicon by aggregating primitives from:
1. USAS semantic tagger (46K words)
2. Wiktionary primitive resolver (200K+ words)
3. SentiWordNet (147K words)
4. NRC Emotion & VAD (55K+ words)
5. VerbNet, FrameNet, PropBank (verb semantics)
6. Lancaster Sensorimotor (40K words)
7. Concreteness ratings (40K words)
8. WordNet hierarchy

The goal is to create a high-coverage, high-quality lexicon with
100-200K words, each with robust primitive decompositions.

Usage:
    python scripts/rebuild_lexicon_from_sources.py --stats      # Show source stats
    python scripts/rebuild_lexicon_from_sources.py --build      # Build new lexicon
    python scripts/rebuild_lexicon_from_sources.py --validate   # Validate results
"""

import argparse
import logging
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Setup paths
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from daemon.config import ALL_PRIMITIVES
from daemon.primitive_rules import infer_primitive_value

DATA_DIR = BASE_DIR / "data"
LEXICON_DB = DATA_DIR / "lexicon.db"
WIKTIONARY_DB = DATA_DIR / "external" / "wiktionary" / "wiktionary_primitives.db"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PrimitiveAssignment:
    """A single primitive assignment with provenance."""
    primitive: str
    value: int
    confidence: float
    source: str


@dataclass
class WordProfile:
    """Complete primitive profile for a word."""
    word: str
    pos: str
    definition: Optional[str]
    primitives: Dict[str, PrimitiveAssignment]  # primitive -> assignment
    sources: Set[str]
    overall_confidence: float


# =============================================================================
# SOURCE LOADERS
# =============================================================================

class SourceLoader:
    """Base class for loading external sources."""

    def __init__(self):
        self.name = "base"
        self.entries = {}
        self._loaded = False

    def load(self) -> bool:
        raise NotImplementedError

    def get_primitives(self, word: str) -> Dict[str, Tuple[int, float]]:
        """Get primitives for a word. Returns {primitive: (value, confidence)}"""
        raise NotImplementedError


class WiktionaryLoader(SourceLoader):
    """Load primitives from Wiktionary resolver database."""

    def __init__(self):
        super().__init__()
        self.name = "wiktionary"
        self.conn = None

    def load(self) -> bool:
        if not WIKTIONARY_DB.exists():
            logger.warning(f"Wiktionary database not found at {WIKTIONARY_DB}")
            return False

        self.conn = sqlite3.connect(str(WIKTIONARY_DB))
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.execute("SELECT COUNT(DISTINCT word) FROM word_primitives")
        count = cursor.fetchone()[0]
        logger.info(f"Loaded Wiktionary resolver with {count:,} words")

        self._loaded = True
        return True

    def get_primitives(self, word: str) -> Dict[str, Tuple[int, float]]:
        if not self._loaded:
            return {}

        cursor = self.conn.execute("""
            SELECT primitive, value, confidence
            FROM word_primitives
            WHERE word = ?
        """, (word.lower(),))

        result = {}
        for row in cursor:
            prim = row['primitive']
            if prim not in result:  # First occurrence wins
                result[prim] = (row['value'], row['confidence'])

        return result

    def get_all_words(self) -> Set[str]:
        """Get all words in the database."""
        if not self._loaded:
            return set()

        cursor = self.conn.execute("SELECT DISTINCT word FROM word_primitives")
        return {row[0] for row in cursor}


class AggregationEngineLoader(SourceLoader):
    """Load primitives from constraint aggregation engine (all NLP sources)."""

    def __init__(self):
        super().__init__()
        self.name = "aggregation_engine"
        self.engine = None

    def load(self) -> bool:
        try:
            from gse.curation.constraint_aggregation.engine import ConstraintAggregationEngine

            self.engine = ConstraintAggregationEngine(include_large_sources=False)
            stats = self.engine.load_sources()

            logger.info(f"Loaded aggregation engine with {len(stats)} sources:")
            for name, count in stats.items():
                logger.info(f"  - {name}: {count:,}")

            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load aggregation engine: {e}")
            return False

    def get_primitives(self, word: str) -> Dict[str, Tuple[int, float]]:
        if not self._loaded:
            return {}

        try:
            profile = self.engine.aggregate_constraints(word)

            result = {}
            for prim, constraint in profile.constraints.items():
                if constraint.status == "auto_apply":
                    result[prim] = (constraint.value, constraint.confidence)
                elif constraint.status == "flag_review":
                    # Lower confidence for conflicting sources
                    result[prim] = (constraint.value, constraint.confidence * 0.7)

            return result

        except Exception as e:
            logger.debug(f"Error getting primitives for '{word}': {e}")
            return {}


# =============================================================================
# LEXICON BUILDER
# =============================================================================

class LexiconBuilder:
    """Build GSE lexicon from multiple sources."""

    def __init__(self):
        self.sources: List[SourceLoader] = []
        self.word_profiles: Dict[str, WordProfile] = {}

    def add_source(self, source: SourceLoader):
        """Add a source loader."""
        if source.load():
            self.sources.append(source)
        else:
            logger.warning(f"Failed to load source: {source.name}")

    def get_source_stats(self) -> Dict[str, int]:
        """Get word count stats for each source."""
        stats = {}
        for source in self.sources:
            if hasattr(source, 'get_all_words'):
                stats[source.name] = len(source.get_all_words())
            else:
                stats[source.name] = -1  # Unknown
        return stats

    def build_word_profile(self, word: str, pos: str = None) -> WordProfile:
        """Build a complete primitive profile for a word."""
        primitives: Dict[str, List[PrimitiveAssignment]] = defaultdict(list)
        sources_with_data = set()

        # Collect from all sources
        for source in self.sources:
            source_prims = source.get_primitives(word)
            if source_prims:
                sources_with_data.add(source.name)
                for prim, (val, conf) in source_prims.items():
                    primitives[prim].append(PrimitiveAssignment(
                        primitive=prim,
                        value=val,
                        confidence=conf,
                        source=source.name
                    ))

        # Aggregate primitives (majority vote with confidence weighting)
        final_primitives = {}
        for prim, assignments in primitives.items():
            # Weighted vote
            pos_weight = sum(a.confidence for a in assignments if a.value > 0)
            neg_weight = sum(a.confidence for a in assignments if a.value < 0)

            if pos_weight > neg_weight:
                final_value = 1
                confidence = pos_weight / (pos_weight + neg_weight + 0.01)
            elif neg_weight > pos_weight:
                final_value = -1
                confidence = neg_weight / (pos_weight + neg_weight + 0.01)
            else:
                final_value = 0
                confidence = 0.5

            # Boost confidence based on source agreement
            source_count = len(set(a.source for a in assignments))
            confidence *= min(1.0, 0.7 + 0.1 * source_count)

            final_primitives[prim] = PrimitiveAssignment(
                primitive=prim,
                value=final_value,
                confidence=confidence,
                source=",".join(sorted(set(a.source for a in assignments)))
            )

        # Apply rule-based inference
        known_values = {p: a.value for p, a in final_primitives.items()}

        for prim in ALL_PRIMITIVES:
            if prim not in final_primitives:
                val, method = infer_primitive_value(
                    prim, word, pos or "",
                    known_values,
                    source_has_data=bool(sources_with_data)
                )
                if val is not None and method in ("bipolar", "grammatical"):
                    final_primitives[prim] = PrimitiveAssignment(
                        primitive=prim,
                        value=val,
                        confidence=0.85 if method == "bipolar" else 0.9,
                        source=f"rule:{method}"
                    )

        # Calculate overall confidence
        if final_primitives:
            overall_conf = sum(a.confidence for a in final_primitives.values()) / len(final_primitives)
        else:
            overall_conf = 0.0

        return WordProfile(
            word=word,
            pos=pos or "",
            definition=None,
            primitives=final_primitives,
            sources=sources_with_data,
            overall_confidence=overall_conf
        )

    def build_lexicon(self, max_words: int = None) -> int:
        """Build the complete lexicon."""
        logger.info("Building lexicon from all sources...")

        # Collect all words
        all_words = set()
        for source in self.sources:
            if hasattr(source, 'get_all_words'):
                words = source.get_all_words()
                all_words.update(words)
                logger.info(f"  {source.name}: {len(words):,} words")

        logger.info(f"Total unique words: {len(all_words):,}")

        if max_words:
            # Prioritize by word length (shorter words are more common)
            sorted_words = sorted(all_words, key=len)[:max_words]
            all_words = set(sorted_words)
            logger.info(f"Limited to {len(all_words):,} words")

        # Build profiles
        count = 0
        start_time = time.time()

        for word in all_words:
            profile = self.build_word_profile(word)
            if profile.primitives:
                self.word_profiles[word] = profile
                count += 1

            if count % 10000 == 0:
                elapsed = time.time() - start_time
                rate = count / elapsed if elapsed > 0 else 0
                logger.info(f"Built {count:,} profiles ({rate:.0f}/sec)")

        logger.info(f"Built {count:,} word profiles in {time.time() - start_time:.1f}s")
        return count

    def save_to_database(self, db_path: Path = LEXICON_DB, backup: bool = True):
        """Save the lexicon to SQLite database."""
        if backup and db_path.exists():
            backup_path = db_path.with_suffix('.db.backup')
            import shutil
            shutil.copy(db_path, backup_path)
            logger.info(f"Backed up existing database to {backup_path}")

        conn = sqlite3.connect(str(db_path))

        # Create schema
        conn.executescript("""
            DROP TABLE IF EXISTS lexemes;
            DROP TABLE IF EXISTS primitive_values;
            DROP TABLE IF EXISTS decomposition_provenance;

            CREATE TABLE lexemes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lemma TEXT NOT NULL,
                pos TEXT,
                sense_id TEXT,
                gloss TEXT,
                frequency_rank INTEGER,
                confidence REAL,
                validation_status TEXT DEFAULT 'pending',
                component_type TEXT,
                UNIQUE(lemma, pos, sense_id)
            );

            CREATE TABLE primitive_values (
                lexeme_id INTEGER NOT NULL,
                primitive TEXT NOT NULL,
                value INTEGER NOT NULL,
                confidence REAL,
                source TEXT,
                PRIMARY KEY (lexeme_id, primitive),
                FOREIGN KEY (lexeme_id) REFERENCES lexemes(id)
            );

            CREATE TABLE decomposition_provenance (
                lexeme_id INTEGER NOT NULL,
                primitive TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lexeme_id) REFERENCES lexemes(id)
            );

            CREATE INDEX idx_lexemes_lemma ON lexemes(lemma);
            CREATE INDEX idx_lexemes_pos ON lexemes(pos);
            CREATE INDEX idx_primitive_values_lexeme ON primitive_values(lexeme_id);
            CREATE INDEX idx_primitive_values_primitive ON primitive_values(primitive);
        """)

        # Insert data
        logger.info("Inserting word profiles into database...")
        count = 0

        for word, profile in self.word_profiles.items():
            # Insert lexeme
            cursor = conn.execute("""
                INSERT INTO lexemes (lemma, pos, confidence, validation_status)
                VALUES (?, ?, ?, ?)
            """, (word, profile.pos, profile.overall_confidence, 'validated'))

            lexeme_id = cursor.lastrowid

            # Insert primitives
            for prim, assignment in profile.primitives.items():
                conn.execute("""
                    INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, ?, ?, ?, ?)
                """, (lexeme_id, prim, assignment.value, assignment.confidence, assignment.source))

                # Insert provenance
                conn.execute("""
                    INSERT INTO decomposition_provenance (lexeme_id, primitive, source, confidence)
                    VALUES (?, ?, ?, ?)
                """, (lexeme_id, prim, assignment.source, assignment.confidence))

            count += 1
            if count % 10000 == 0:
                conn.commit()
                logger.info(f"Inserted {count:,} lexemes")

        conn.commit()
        conn.close()

        logger.info(f"Saved {count:,} lexemes to {db_path}")
        return count

    def get_coverage_stats(self) -> Dict:
        """Get coverage statistics for the lexicon."""
        if not self.word_profiles:
            return {}

        primitive_counts = defaultdict(int)
        total_primitives = 0
        confidence_sum = 0

        for profile in self.word_profiles.values():
            for prim, assignment in profile.primitives.items():
                if assignment.value != 0:
                    primitive_counts[prim] += 1
                    total_primitives += 1
            confidence_sum += profile.overall_confidence

        return {
            'total_words': len(self.word_profiles),
            'total_primitive_assignments': total_primitives,
            'avg_primitives_per_word': total_primitives / len(self.word_profiles),
            'avg_confidence': confidence_sum / len(self.word_profiles),
            'primitive_coverage': dict(sorted(primitive_counts.items(), key=lambda x: -x[1])[:20]),
        }


# =============================================================================
# MAIN
# =============================================================================

def show_stats():
    """Show statistics for all sources."""
    builder = LexiconBuilder()

    logger.info("Loading sources...")

    # Load Wiktionary
    wikt = WiktionaryLoader()
    builder.add_source(wikt)

    # Load aggregation engine (all NLP sources)
    agg = AggregationEngineLoader()
    builder.add_source(agg)

    stats = builder.get_source_stats()

    print("\n" + "=" * 60)
    print("Source Statistics")
    print("=" * 60)

    for name, count in stats.items():
        print(f"  {name}: {count:,} words")

    print("=" * 60)


def build_lexicon(max_words: int = None):
    """Build the lexicon."""
    builder = LexiconBuilder()

    logger.info("Loading sources...")

    # Load Wiktionary
    wikt = WiktionaryLoader()
    builder.add_source(wikt)

    # Load aggregation engine
    agg = AggregationEngineLoader()
    builder.add_source(agg)

    # Build
    builder.build_lexicon(max_words=max_words)

    # Stats
    stats = builder.get_coverage_stats()
    print("\n" + "=" * 60)
    print("Lexicon Statistics")
    print("=" * 60)
    print(f"  Total words: {stats.get('total_words', 0):,}")
    print(f"  Total primitive assignments: {stats.get('total_primitive_assignments', 0):,}")
    print(f"  Avg primitives per word: {stats.get('avg_primitives_per_word', 0):.1f}")
    print(f"  Avg confidence: {stats.get('avg_confidence', 0):.2f}")
    print("\n  Top primitives by coverage:")
    for prim, count in list(stats.get('primitive_coverage', {}).items())[:15]:
        print(f"    {prim}: {count:,}")
    print("=" * 60)

    # Save
    builder.save_to_database()


def validate_lexicon():
    """Validate the lexicon."""
    if not LEXICON_DB.exists():
        logger.error(f"Lexicon database not found at {LEXICON_DB}")
        return

    conn = sqlite3.connect(str(LEXICON_DB))

    cursor = conn.execute("SELECT COUNT(*) FROM lexemes")
    total_words = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*) FROM primitive_values WHERE value != 0")
    total_prims = cursor.fetchone()[0]

    cursor = conn.execute("SELECT AVG(confidence) FROM lexemes")
    avg_conf = cursor.fetchone()[0]

    cursor = conn.execute("""
        SELECT primitive, COUNT(*) as cnt
        FROM primitive_values
        WHERE value != 0
        GROUP BY primitive
        ORDER BY cnt DESC
        LIMIT 20
    """)
    top_prims = cursor.fetchall()

    print("\n" + "=" * 60)
    print("Lexicon Validation")
    print("=" * 60)
    print(f"  Total lexemes: {total_words:,}")
    print(f"  Total primitive assignments: {total_prims:,}")
    print(f"  Avg primitives per word: {total_prims / total_words:.1f}")
    print(f"  Avg confidence: {avg_conf:.2f}")
    print("\n  Top primitives:")
    for prim, count in top_prims:
        print(f"    {prim}: {count:,}")
    print("=" * 60)

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Rebuild GSE Lexicon from Sources")
    parser.add_argument('--stats', action='store_true', help='Show source statistics')
    parser.add_argument('--build', action='store_true', help='Build lexicon')
    parser.add_argument('--validate', action='store_true', help='Validate lexicon')
    parser.add_argument('--max-words', type=int, help='Max words to include')

    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.build:
        build_lexicon(args.max_words)
    elif args.validate:
        validate_lexicon()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
