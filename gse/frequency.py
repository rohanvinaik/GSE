# gse/frequency.py
"""
Word Frequency Weighting for GSE

Implements frequency-aware semantic encoding where:
- High-frequency words provide structural scaffolding (lower weight)
- Low-frequency words carry specific semantic content (higher weight)

This follows the linguistic insight that function words (the, a, is) are
common but semantically "light", while content words (photosynthesis,
algorithm) are rare but semantically "heavy".

Weight Transform:
    weight = log(max_rank / rank) / log(max_rank)

This gives:
- Rank 1 (most common): weight ≈ 1.0
- Rank 1000: weight ≈ 1.4
- Rank 10000: weight ≈ 1.75
- Unknown words: weight = 2.0 (maximum weight, they're very specific)

The weights are applied during bundling to modulate each token's
contribution to the composed sentence vector.
"""

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple


@dataclass
class FrequencyInfo:
    """Frequency information for a word."""

    word: str
    rank: int  # 1 = most common
    david47k_rank: Optional[int]
    local_rank: Optional[int]
    weight: float


class FrequencyDatabase:
    """
    Unified frequency database combining multiple sources.

    Sources:
    1. david47k/top-english-wordlists (general English)
    2. word_frequency_report.txt (domain-specific corpus)

    Rankings are averaged when both sources have the word.
    """

    DEFAULT_MAX_RANK = 100000  # For unknown words
    MAX_WEIGHT = 2.0  # Cap weight for very rare words
    MIN_WEIGHT = 0.3  # Floor weight for very common words

    def __init__(self, db_path: Optional[str] = None):
        """Initialize frequency database."""
        self.db_path = db_path or str(Path(__file__).parent.parent / "data" / "frequency.db")
        self._cache: Dict[str, FrequencyInfo] = {}
        self._max_rank = self.DEFAULT_MAX_RANK

    def build_from_sources(self, david47k_path: str, local_freq_path: str, output_db_path: Optional[str] = None) -> int:
        """
        Build frequency database from source files.

        Args:
            david47k_path: Path to top english wordlist (one word per line, ranked)
            local_freq_path: Path to word_frequency_report.txt (word: count format)
            output_db_path: Where to save the SQLite database

        Returns:
            Number of words in combined database
        """
        db_path = output_db_path or self.db_path

        # Load david47k rankings (rank = line number)
        david47k_ranks: Dict[str, int] = {}
        with open(david47k_path, "r") as f:
            for rank, line in enumerate(f, start=1):
                word = line.strip().lower()
                if word and word not in david47k_ranks:
                    david47k_ranks[word] = rank

        # Load local frequency rankings (sort by count descending)
        local_counts: Dict[str, int] = {}
        with open(local_freq_path, "r") as f:
            for line in f:
                if ":" in line:
                    parts = line.strip().split(":")
                    word = parts[0].strip().lower()
                    try:
                        count = int(parts[1].strip())
                        if word and word not in local_counts:
                            local_counts[word] = count
                    except ValueError:
                        continue

        # Convert local counts to ranks
        local_sorted = sorted(local_counts.items(), key=lambda x: -x[1])
        local_ranks = {word: rank for rank, (word, _) in enumerate(local_sorted, start=1)}

        # Combine all unique words
        all_words = set(david47k_ranks.keys()) | set(local_ranks.keys())

        # Find max ranks for normalization
        max_david47k = max(david47k_ranks.values()) if david47k_ranks else 10000
        max_local = max(local_ranks.values()) if local_ranks else 10000

        # Create database
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS frequency (
                word TEXT PRIMARY KEY,
                combined_rank INTEGER NOT NULL,
                david47k_rank INTEGER,
                local_rank INTEGER,
                weight REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_freq_rank ON frequency(combined_rank)")
        conn.execute("DELETE FROM frequency")  # Clear existing

        # Compute combined ranks and weights
        combined_data = []
        for word in all_words:
            d_rank = david47k_ranks.get(word)
            l_rank = local_ranks.get(word)

            # Normalize ranks to same scale (0-1 where 0 = most common)
            d_norm = (d_rank / max_david47k) if d_rank else 1.0
            l_norm = (l_rank / max_local) if l_rank else 1.0

            # Average the normalized ranks
            if d_rank and l_rank:
                avg_norm = (d_norm + l_norm) / 2
            elif d_rank:
                avg_norm = d_norm
            else:
                avg_norm = l_norm

            # Convert back to combined rank (1 = most common)
            combined_rank = max(1, int(avg_norm * max_david47k))

            # Compute weight
            weight = self._rank_to_weight(combined_rank, max_david47k)

            combined_data.append((word, combined_rank, d_rank, l_rank, weight))

        # Sort by combined rank and insert
        combined_data.sort(key=lambda x: x[1])
        conn.executemany(
            "INSERT INTO frequency (word, combined_rank, david47k_rank, local_rank, weight) VALUES (?, ?, ?, ?, ?)",
            combined_data,
        )

        conn.commit()
        conn.close()

        self._cache.clear()
        self._max_rank = max_david47k

        return len(combined_data)

    def _rank_to_weight(self, rank: int, max_rank: int) -> float:
        """
        Convert frequency rank to semantic weight.

        Uses log transform so that:
        - Most common words get lower weights (structural scaffolding)
        - Rare words get higher weights (specific semantics)

        The formula:
            weight = MIN_WEIGHT + (MAX_WEIGHT - MIN_WEIGHT) * log(rank) / log(max_rank)

        This maps:
            rank=1     -> MIN_WEIGHT (most common = lowest weight)
            rank=max   -> MAX_WEIGHT (least common = highest weight)
        """
        if rank <= 0:
            rank = 1
        if rank > max_rank:
            rank = max_rank

        # Log transform with bounds
        log_ratio = math.log(rank) / math.log(max_rank)
        weight = self.MIN_WEIGHT + (self.MAX_WEIGHT - self.MIN_WEIGHT) * log_ratio

        return round(weight, 4)

    def lookup(self, word: str) -> FrequencyInfo:
        """
        Look up frequency info for a word.

        Returns FrequencyInfo with DEFAULT_MAX_RANK and MAX_WEIGHT for unknown words.
        """
        word = word.lower()

        # Check cache
        if word in self._cache:
            return self._cache[word]

        # Query database
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                "SELECT combined_rank, david47k_rank, local_rank, weight FROM frequency WHERE word = ?", (word,)
            ).fetchone()
            conn.close()

            if row:
                info = FrequencyInfo(word=word, rank=row[0], david47k_rank=row[1], local_rank=row[2], weight=row[3])
            else:
                # Unknown word - high specificity
                info = FrequencyInfo(
                    word=word, rank=self.DEFAULT_MAX_RANK, david47k_rank=None, local_rank=None, weight=self.MAX_WEIGHT
                )

            self._cache[word] = info
            return info

        except sqlite3.Error:
            # Database not available
            return FrequencyInfo(
                word=word, rank=self.DEFAULT_MAX_RANK, david47k_rank=None, local_rank=None, weight=self.MAX_WEIGHT
            )

    def get_weight(self, word: str) -> float:
        """Get just the weight for a word (convenience method)."""
        return self.lookup(word).weight

    def get_rank(self, word: str) -> int:
        """Get just the rank for a word (convenience method)."""
        return self.lookup(word).rank

    def batch_lookup(self, words: list) -> Dict[str, FrequencyInfo]:
        """Look up frequency info for multiple words efficiently."""
        results = {}
        uncached = []

        # Check cache first
        for word in words:
            word = word.lower()
            if word in self._cache:
                results[word] = self._cache[word]
            else:
                uncached.append(word)

        if not uncached:
            return results

        # Batch query for uncached
        try:
            conn = sqlite3.connect(self.db_path)
            placeholders = ",".join("?" * len(uncached))
            rows = conn.execute(
                f"SELECT word, combined_rank, david47k_rank, local_rank, weight FROM frequency WHERE word IN ({placeholders})",
                uncached,
            ).fetchall()
            conn.close()

            found = set()
            for row in rows:
                word = row[0]
                info = FrequencyInfo(word=word, rank=row[1], david47k_rank=row[2], local_rank=row[3], weight=row[4])
                results[word] = info
                self._cache[word] = info
                found.add(word)

            # Handle not found
            for word in uncached:
                if word not in found:
                    info = FrequencyInfo(
                        word=word,
                        rank=self.DEFAULT_MAX_RANK,
                        david47k_rank=None,
                        local_rank=None,
                        weight=self.MAX_WEIGHT,
                    )
                    results[word] = info
                    self._cache[word] = info

        except sqlite3.Error:
            # Database error - return defaults for all
            for word in uncached:
                info = FrequencyInfo(
                    word=word, rank=self.DEFAULT_MAX_RANK, david47k_rank=None, local_rank=None, weight=self.MAX_WEIGHT
                )
                results[word] = info

        return results

    def stats(self) -> Dict:
        """Get database statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            total = conn.execute("SELECT COUNT(*) FROM frequency").fetchone()[0]
            both = conn.execute(
                "SELECT COUNT(*) FROM frequency WHERE david47k_rank IS NOT NULL AND local_rank IS NOT NULL"
            ).fetchone()[0]
            david_only = conn.execute(
                "SELECT COUNT(*) FROM frequency WHERE david47k_rank IS NOT NULL AND local_rank IS NULL"
            ).fetchone()[0]
            local_only = conn.execute(
                "SELECT COUNT(*) FROM frequency WHERE david47k_rank IS NULL AND local_rank IS NOT NULL"
            ).fetchone()[0]
            conn.close()

            return {
                "total_words": total,
                "in_both_sources": both,
                "david47k_only": david_only,
                "local_only": local_only,
            }
        except sqlite3.Error:
            return {"error": "Database not available"}


# =============================================================================
# WEIGHT PROFILES
# =============================================================================


class WeightProfile:
    """
    Different weighting strategies for different use cases.

    Profiles adjust how frequency affects semantic weight:
    - BALANCED: Equal treatment of structure and content
    - CONTENT_FOCUSED: Emphasize rare/specific words
    - STRUCTURE_FOCUSED: Emphasize common/structural words
    - IDF_STYLE: Inverse document frequency style
    """

    BALANCED = "balanced"
    CONTENT_FOCUSED = "content_focused"
    STRUCTURE_FOCUSED = "structure_focused"
    STRUCTURE_DOMINANT = "structure_dominant"  # New: High freq = High weight
    IDF_STYLE = "idf_style"

    @staticmethod
    def apply(profile: str, base_weight: float) -> float:
        """Apply weight profile transformation."""
        if profile == WeightProfile.BALANCED:
            # Linear mapping, no change
            return base_weight

        elif profile == WeightProfile.CONTENT_FOCUSED:
            # Square the weight to emphasize rare words more
            return base_weight**1.5

        elif profile == WeightProfile.STRUCTURE_FOCUSED:
            # Square root to compress the range
            return math.sqrt(base_weight)

        elif profile == WeightProfile.STRUCTURE_DOMINANT:
            # Invert the weight: Common (0.3) -> 3.33, Rare (2.0) -> 0.5
            # This makes common words dominate structure
            return 1.0 / max(0.1, base_weight)

        elif profile == WeightProfile.IDF_STYLE:
            # Classic IDF transform
            # weight = log(N / df) -> here mapped to log(max_rank / rank)
            # Already done in base computation
            return base_weight

        else:
            return base_weight


# =============================================================================
# INTEGRATION HELPERS
# =============================================================================


def build_frequency_database(
    david47k_url: str = "https://raw.githubusercontent.com/david47k/top-english-wordlists/refs/heads/main/top_english_words_10000.txt",
    local_path: str = "/Users/rohanvinaik/relational-ai/word_frequency_report.txt",
    david47k_local: str = "/tmp/top_english_10000.txt",
    output_path: str = None,
) -> Tuple[FrequencyDatabase, int]:
    """
    Build or update the frequency database.

    Downloads david47k wordlist if not present, combines with local frequencies.
    """
    import urllib.request
    from pathlib import Path

    # Download david47k if needed
    if not Path(david47k_local).exists():
        print("Downloading david47k wordlist...")
        urllib.request.urlretrieve(david47k_url, david47k_local)

    db = FrequencyDatabase(output_path)
    count = db.build_from_sources(david47k_local, local_path, output_path)

    return db, count


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("GSE Frequency Weighting System")
    print("=" * 70)

    # Build database
    print("\n1. Building frequency database...")
    db, count = build_frequency_database()
    print(f"   Built database with {count} words")

    # Show stats
    print("\n2. Database statistics:")
    stats = db.stats()
    for k, v in stats.items():
        print(f"   {k}: {v}")

    # Test lookups
    print("\n3. Sample frequency weights:")
    test_words = [
        "the",
        "a",
        "is",
        "and",  # Very common
        "because",
        "although",
        "however",  # Moderately common
        "algorithm",
        "photosynthesis",
        "cryptocurrency",  # Technical
        "xyzzy",
        "qwfpgj",  # Unknown
    ]

    for word in test_words:
        info = db.lookup(word)
        print(f"   {word:20s} rank={info.rank:6d} weight={info.weight:.3f}")

    # Show weight distribution
    print("\n4. Weight by rank tier:")
    tiers = [1, 10, 100, 1000, 10000, 50000, 100000]
    for rank in tiers:
        weight = db._rank_to_weight(rank, 100000)
        print(f"   rank={rank:6d} -> weight={weight:.3f}")

    print("\n" + "=" * 70)
    print("Done!")
