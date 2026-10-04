"""
ConceptNet Memory-Efficient Parser

Handles 9.5GB (34M assertions) ConceptNet dump:
- Single-pass processing into SQLite index
- English-only filtering (reduces to ~10M assertions)
- On-demand relation queries via SQL
- LRU caching for frequent lookups

Memory strategy:
- Never load full dataset into memory
- Build SQLite index on first run (~1.5GB)
- Query by word for audit needs
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from gse.curation.external_sources.base_parser import BaseExternalParser

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "external"
CONCEPTNET_CSV = DATA_DIR / "conceptnet-assertions-5.7.0.csv"
CONCEPTNET_DB = DATA_DIR / "conceptnet-en.sqlite"


@dataclass
class ConceptNetEdge:
    """An edge from ConceptNet."""
    relation: str
    start_word: str
    end_word: str
    weight: float
    source: str


# ConceptNet relations to GSE primitives
RELATION_TO_PRIMITIVE = {
    # Taxonomic relations
    'IsA': {'KIND': 1},  # X is a type of Y
    'InstanceOf': {'KIND': 1},
    'HasA': {'HAVE': 1, 'PART': 1},
    'PartOf': {'PART': 1},
    'MemberOf': {'PART': 1},

    # Semantic similarity
    'Synonym': {},  # Same meaning - no direct primitive
    'Antonym': {'NOT': 1},  # Opposite - implies negation relation
    'DistinctFrom': {'OTHER': 1},
    'SimilarTo': {'LIKE': 1},
    'RelatedTo': {},  # Too general

    # Spatial/locative
    'AtLocation': {'WHERE': 1},
    'LocatedNear': {'WHERE': 1, 'NEAR': 1},

    # Causal/temporal
    'Causes': {'CAUSE': 1},
    'HasPrerequisite': {'BEFORE': 1},
    'HasFirstSubevent': {'START': 1},
    'HasLastSubevent': {'END': 1},
    'HasSubevent': {'PART': 1},

    # Properties
    'HasProperty': {},  # Depends on property
    'CapableOf': {'CAN': 1},
    'NotCapableOf': {'CAN': -1},

    # Usage/purpose
    'UsedFor': {'DO': 1},
    'CreatedBy': {'DO': 1, 'CAUSE': 1},
    'ReceivesAction': {},
    'MannerOf': {'LIKE': 1},

    # Desire/motivation
    'Desires': {'WANT': 1},
    'MotivatedByGoal': {'WANT': 1, 'BECAUSE': 1},
    'CausesDesire': {'WANT': 1, 'CAUSE': 1},

    # Physical/sensory
    'MadeOf': {'SOMETHING': 1},

    # Definition
    'DefinedAs': {},  # Too general
}

# Property values to primitives (for HasProperty relations)
PROPERTY_PRIMITIVES = {
    'good': {'GOOD': 1},
    'bad': {'GOOD': -1},
    'big': {'BIG': 1},
    'large': {'BIG': 1},
    'small': {'BIG': -1},
    'little': {'BIG': -1},
    'fast': {'INTENSITY': 1},
    'slow': {'INTENSITY': -1},
    'alive': {'ALIVE': 1},
    'dead': {'ALIVE': -1},
    'abstract': {'THINK': 1},
    'concrete': {'SOMETHING': 1},
    'physical': {'BODY': 1, 'SOMETHING': 1},
    'mental': {'THINK': 1},
    'emotional': {'FEEL': 1},
    'old': {'BEFORE': 1},
    'new': {'AFTER': 1},
    'beautiful': {'GOOD': 1},
    'ugly': {'GOOD': -1},
    'dangerous': {'GOOD': -1},
    'safe': {'GOOD': 1},
    'hot': {'FEEL': 1},
    'cold': {'FEEL': 1},
    'hard': {'TOUCH': 1},
    'soft': {'TOUCH': 1},
    'loud': {'HEAR': 1},
    'quiet': {'HEAR': 1, 'INTENSITY': -1},
    'visible': {'SEE': 1},
    'invisible': {'SEE': -1},
    'human': {'SOMEONE': 1},
    'animal': {'ALIVE': 1},
    'living': {'ALIVE': 1},
    'moving': {'MOVE': 1},
}


class ConceptNetParser(BaseExternalParser):
    """
    Memory-efficient ConceptNet parser using SQLite indexing.

    First run processes the 9.5GB CSV into a ~1.5GB SQLite database.
    Subsequent runs query the index directly.
    """

    def __init__(
        self,
        csv_path: Optional[Path] = None,
        db_path: Optional[Path] = None,
        min_weight: float = 1.0,  # Filter low-confidence edges
        english_only: bool = True,
    ):
        super().__init__()
        self.config.name = "conceptnet"
        self.csv_path = csv_path or CONCEPTNET_CSV
        self.db_path = db_path or CONCEPTNET_DB
        self.min_weight = min_weight
        self.english_only = english_only
        self.conn: Optional[sqlite3.Connection] = None

    def _build_index(self) -> bool:
        """
        Build SQLite index from ConceptNet CSV.

        Memory-efficient: streams CSV line by line.
        Time: ~30 minutes on 2013 MacBook Pro.
        """
        if not self.csv_path.exists():
            logger.error(f"ConceptNet CSV not found: {self.csv_path}")
            logger.info("Please download from: https://s3.amazonaws.com/conceptnet/downloads/2019/edges/conceptnet-assertions-5.7.0.csv.gz")
            return False

        logger.info(f"Building ConceptNet index from {self.csv_path}...")
        logger.info("This may take 20-30 minutes on first run...")

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))

        # Create schema
        conn.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY,
                relation TEXT NOT NULL,
                start_word TEXT NOT NULL,
                end_word TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                source TEXT
            )
        """)

        # Process CSV in streaming fashion
        batch = []
        count = 0
        skipped = 0

        with open(self.csv_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) < 5:
                    continue

                uri, relation, start, end, metadata_json = parts[:5]

                # Extract relation type
                relation = relation.split('/')[-1]

                # Parse concept URIs
                start_word = self._parse_concept(start)
                end_word = self._parse_concept(end)

                if not start_word or not end_word:
                    skipped += 1
                    continue

                # Parse weight
                try:
                    metadata = json.loads(metadata_json)
                    weight = metadata.get('weight', 1.0)
                except:
                    weight = 1.0

                if weight < self.min_weight:
                    skipped += 1
                    continue

                source = ''
                try:
                    source = metadata.get('dataset', '')
                except:
                    pass

                batch.append((relation, start_word, end_word, weight, source))

                if len(batch) >= 10000:
                    conn.executemany(
                        "INSERT INTO edges (relation, start_word, end_word, weight, source) "
                        "VALUES (?, ?, ?, ?, ?)",
                        batch
                    )
                    conn.commit()
                    count += len(batch)
                    batch = []

                    if count % 500000 == 0:
                        logger.info(f"Processed {count:,} edges...")

        if batch:
            conn.executemany(
                "INSERT INTO edges (relation, start_word, end_word, weight, source) "
                "VALUES (?, ?, ?, ?, ?)",
                batch
            )
            count += len(batch)

        # Create indices
        logger.info("Creating indices...")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_start ON edges(start_word)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_end ON edges(end_word)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_relation ON edges(relation)")
        conn.commit()

        conn.close()

        logger.info(f"Built index with {count:,} edges (skipped {skipped:,})")
        return True

    def _parse_concept(self, uri: str) -> Optional[str]:
        """Parse ConceptNet URI to extract English word."""
        # URI format: /c/en/word/pos or /c/en/word
        parts = uri.split('/')

        if len(parts) < 4:
            return None

        lang = parts[2]

        # Filter for English only if configured
        if self.english_only and lang != 'en':
            return None

        word = parts[3].lower().replace('_', ' ')
        return word

    def load(self) -> bool:
        """Load ConceptNet index (builds if necessary)."""
        if not self.db_path.exists():
            logger.info("ConceptNet SQLite index not found.")
            if self.csv_path.exists():
                if not self._build_index():
                    return False
            else:
                logger.warning(f"ConceptNet CSV not found at {self.csv_path}")
                logger.info("ConceptNet parser will be unavailable.")
                return False

        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row

            cursor = self.conn.execute("SELECT COUNT(*) FROM edges")
            count = cursor.fetchone()[0]

            logger.info(f"Loaded ConceptNet index with {count:,} edges")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load ConceptNet: {e}")
            return False

    def get_edges(self, word: str, as_start: bool = True, as_end: bool = True, limit: int = 100) -> List[ConceptNetEdge]:
        """Get all edges involving a word."""
        if not self._loaded:
            if not self.load():
                return []

        word = word.lower()
        edges = []

        if as_start:
            cursor = self.conn.execute(
                "SELECT * FROM edges WHERE start_word = ? ORDER BY weight DESC LIMIT ?",
                (word, limit)
            )
            for row in cursor.fetchall():
                edges.append(ConceptNetEdge(
                    relation=row['relation'],
                    start_word=row['start_word'],
                    end_word=row['end_word'],
                    weight=row['weight'],
                    source=row['source'],
                ))

        if as_end:
            cursor = self.conn.execute(
                "SELECT * FROM edges WHERE end_word = ? ORDER BY weight DESC LIMIT ?",
                (word, limit)
            )
            for row in cursor.fetchall():
                edges.append(ConceptNetEdge(
                    relation=row['relation'],
                    start_word=row['start_word'],
                    end_word=row['end_word'],
                    weight=row['weight'],
                    source=row['source'],
                ))

        return edges

    @lru_cache(maxsize=20000)
    def to_primitives(self, word: str) -> Dict[str, int]:
        """Map word to GSE primitives based on ConceptNet relations."""
        if not self._loaded:
            if not self.load():
                return {}

        edges = self.get_edges(word.lower())
        if not edges:
            return {}

        primitives: Dict[str, int] = {}

        for edge in edges:
            # Apply relation-based primitives
            if edge.relation in RELATION_TO_PRIMITIVE:
                for prim, val in RELATION_TO_PRIMITIVE[edge.relation].items():
                    if prim not in primitives:
                        primitives[prim] = val

            # Handle HasProperty specially
            if edge.relation == 'HasProperty':
                prop = edge.end_word if edge.start_word == word.lower() else edge.start_word
                if prop in PROPERTY_PRIMITIVES:
                    for prim, val in PROPERTY_PRIMITIVES[prop].items():
                        if prim not in primitives:
                            primitives[prim] = val

            # Handle IsA for entity types
            if edge.relation == 'IsA' and edge.start_word == word.lower():
                hypernym = edge.end_word
                if hypernym in ['person', 'human', 'people']:
                    primitives['SOMEONE'] = 1
                elif hypernym in ['animal', 'creature']:
                    primitives['ALIVE'] = 1
                elif hypernym in ['place', 'location']:
                    primitives['WHERE'] = 1
                elif hypernym in ['time', 'period']:
                    primitives['WHEN'] = 1
                elif hypernym in ['feeling', 'emotion']:
                    primitives['FEEL'] = 1
                elif hypernym in ['action', 'activity']:
                    primitives['DO'] = 1

        return primitives

    def get_all_words(self) -> List[str]:
        """Get all unique words (memory-efficient generator would be better for full list)."""
        if not self._loaded:
            if not self.load():
                return []

        # Return a sample for testing - full list would be very large
        cursor = self.conn.execute("""
            SELECT DISTINCT start_word FROM edges
            LIMIT 50000
        """)
        return [row[0] for row in cursor.fetchall()]

    def get_related_words(self, word: str, relation: str = None) -> List[Tuple[str, float]]:
        """Get words related to input word, optionally filtered by relation."""
        if not self._loaded:
            if not self.load():
                return []

        word = word.lower()

        if relation:
            cursor = self.conn.execute("""
                SELECT end_word, weight FROM edges
                WHERE start_word = ? AND relation = ?
                ORDER BY weight DESC LIMIT 50
            """, (word, relation))
        else:
            cursor = self.conn.execute("""
                SELECT end_word, weight FROM edges
                WHERE start_word = ?
                ORDER BY weight DESC LIMIT 50
            """, (word,))

        return [(row[0], row[1]) for row in cursor.fetchall()]

    def get_synonyms(self, word: str) -> List[str]:
        """Get synonyms for a word."""
        related = self.get_related_words(word, 'Synonym')
        return [w for w, _ in related]

    def get_antonyms(self, word: str) -> List[str]:
        """Get antonyms for a word."""
        related = self.get_related_words(word, 'Antonym')
        return [w for w, _ in related]

    def get_hypernyms(self, word: str) -> List[str]:
        """Get IsA (hypernym) relations for a word."""
        related = self.get_related_words(word, 'IsA')
        return [w for w, _ in related]

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
        super().close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = ConceptNetParser()
    if parser.load():
        # Test some words
        test_words = ['dog', 'run', 'happy', 'computer', 'love', 'water']
        for word in test_words:
            primitives = parser.to_primitives(word)
            related = parser.get_related_words(word)[:3]
            print(f"{word}: primitives={primitives}, related={[w for w, _ in related]}")
    else:
        print("ConceptNet not available - CSV file needed for first-time index build")
