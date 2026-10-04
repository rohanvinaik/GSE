"""
Frequency Database Integration

Integrates the existing frequency.db with the lexicon builder.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Tuple


@dataclass
class WordFrequency:
    """A word with its frequency data."""

    word: str
    combined_rank: int
    david47k_rank: Optional[int]
    local_rank: Optional[int]
    weight: float


class FrequencyDatabase:
    """Read-only access to the frequency database."""

    def __init__(self, db_path: str):
        """
        Initialize frequency database connection.

        Args:
            db_path: Path to frequency.db
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Frequency database not found: {db_path}")

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

    def close(self):
        """Close the database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_word(self, word: str) -> Optional[WordFrequency]:
        """Get frequency data for a single word."""
        cursor = self.conn.execute("SELECT * FROM frequency WHERE word = ?", (word,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_word_freq(row)

    def _row_to_word_freq(self, row: sqlite3.Row) -> WordFrequency:
        """Convert a database row to WordFrequency."""
        return WordFrequency(
            word=row["word"],
            combined_rank=row["combined_rank"],
            david47k_rank=row["david47k_rank"],
            local_rank=row["local_rank"],
            weight=row["weight"],
        )

    def get_words_by_rank_range(
        self,
        start_rank: int,
        end_rank: Optional[int] = None,
    ) -> List[WordFrequency]:
        """Get words within a frequency rank range."""
        if end_rank is None:
            cursor = self.conn.execute(
                """
                SELECT * FROM frequency
                WHERE combined_rank >= ?
                ORDER BY combined_rank
                """,
                (start_rank,),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT * FROM frequency
                WHERE combined_rank >= ? AND combined_rank <= ?
                ORDER BY combined_rank
                """,
                (start_rank, end_rank),
            )
        return [self._row_to_word_freq(row) for row in cursor.fetchall()]

    def iter_words_by_rank(
        self,
        start_rank: int = 1,
        batch_size: int = 100,
    ) -> Iterator[List[WordFrequency]]:
        """Iterate through words in batches by frequency rank."""
        offset = 0
        while True:
            cursor = self.conn.execute(
                """
                SELECT * FROM frequency
                WHERE combined_rank >= ?
                ORDER BY combined_rank
                LIMIT ? OFFSET ?
                """,
                (start_rank, batch_size, offset),
            )
            rows = cursor.fetchall()
            if not rows:
                break
            yield [self._row_to_word_freq(row) for row in rows]
            offset += batch_size

    def count_words(self) -> int:
        """Get total number of words in the database."""
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM frequency")
        return cursor.fetchone()["count"]

    def get_rank_range(self) -> Tuple[int, int]:
        """Get the min and max combined_rank values."""
        cursor = self.conn.execute(
            "SELECT MIN(combined_rank) as min_rank, MAX(combined_rank) as max_rank FROM frequency"
        )
        row = cursor.fetchone()
        return row["min_rank"], row["max_rank"]


class FrequencyIntegration:
    """Integrates frequency.db with lexicon.db."""

    def __init__(
        self,
        freq_db_path: str,
        lexicon_db_path: str,
    ):
        """
        Initialize frequency integration.

        Args:
            freq_db_path: Path to frequency.db
            lexicon_db_path: Path to lexicon.db
        """
        self.freq_db = FrequencyDatabase(freq_db_path)
        self.lexicon_db_path = lexicon_db_path

    def close(self):
        """Close database connections."""
        self.freq_db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def populate_lexicon_from_frequency(
        self,
        start_rank: int = 1,
        end_rank: Optional[int] = None,
        default_pos: str = "unknown",
        phase: int = 0,
    ) -> int:
        """
        Populate lexicon with words from frequency database.

        Args:
            start_rank: Starting frequency rank
            end_rank: Ending frequency rank (None for all)
            default_pos: Default part of speech to assign
            phase: Phase number to assign

        Returns:
            Number of words added
        """
        from gse.curation.lexicon_db import LexiconDatabase

        freq_words = self.freq_db.get_words_by_rank_range(start_rank, end_rank)

        with LexiconDatabase(self.lexicon_db_path) as lexicon_db:
            added = 0
            for word_freq in freq_words:
                try:
                    lexicon_db.add_lexeme(
                        lemma=word_freq.word,
                        pos=default_pos,
                        source="frequency",
                        frequency_rank=word_freq.combined_rank,
                        frequency_weight=word_freq.weight,
                        phase=phase,
                    )
                    added += 1
                except sqlite3.IntegrityError:
                    # Word already exists, update frequency data
                    lexicon_db.update_frequency(
                        word_freq.word,
                        word_freq.combined_rank,
                        word_freq.weight,
                    )

            return added

    def get_words_for_phase(self, phase: int) -> List[WordFrequency]:
        """
        Get words appropriate for a build phase.

        Phase 1: ranks 1-1000 (core vocabulary)
        Phase 2: ranks 1001-3000 (extended vocabulary)
        Phase 3: ranks 3001+ (expansion)
        """
        if phase == 1:
            return self.freq_db.get_words_by_rank_range(1, 1000)
        elif phase == 2:
            return self.freq_db.get_words_by_rank_range(1001, 3000)
        elif phase == 3:
            return self.freq_db.get_words_by_rank_range(3001, None)
        else:
            raise ValueError(f"Invalid phase: {phase}")

    def get_phase_for_rank(self, rank: int) -> int:
        """Determine the build phase for a given frequency rank."""
        if rank <= 1000:
            return 1
        elif rank <= 3000:
            return 2
        else:
            return 3


def get_default_frequency_db_path() -> str:
    """Get the default path to frequency.db."""
    # Try relative to GSE data directory
    gse_data = Path(__file__).parent.parent.parent / "data" / "frequency.db"
    if gse_data.exists():
        return str(gse_data)

    # Fall back to common locations
    common_paths = [
        Path.home() / "gse" / "data" / "frequency.db",
        Path("/Users/rohanvinaik/gse/data/frequency.db"),
    ]

    for path in common_paths:
        if path.exists():
            return str(path)

    raise FileNotFoundError("Could not find frequency.db")
