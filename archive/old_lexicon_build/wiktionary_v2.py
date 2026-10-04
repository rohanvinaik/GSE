"""
Wiktionary Primitives v2 loader.

Reads the pre-built ``data/external/wiktionary/wiktionary_primitives_v2.db``
produced by ``scripts/build_wiktionary_primitives.py``. That script
processes the kaikki.org English Wiktionary dump via hardcoded
keyword-to-primitive patterns (e.g., ``"feeling": {"FEEL": 1}``) — no LLM
involvement, fully deterministic, source-grounded.

The v2 DB schema:

    primitive_dictionary(id, name, bank, is_bipolar, bipolar_partner_id)
    source_dictionary(id, name, reliability)
    word_primitives_v2(id, word, pos, primitive_id, value, confidence, source_id)
    genus_hierarchy(word, pos, genus, depth, confidence)
    semantic_relations(source_word, target_word, relation, weight)

This loader joins ``word_primitives_v2`` against ``primitive_dictionary``
to surface primitive names + per-vote confidences. It is the **primary**
lexeme source for the rebuild: its 1.3 M-word vocabulary drives the word
list and other parsers contribute additional primitive evidence per word.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from gse.curation.external_sources.base_parser import BaseExternalParser, ParserConfig

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "external"
DEFAULT_V2_DB = DATA_DIR / "wiktionary" / "wiktionary_primitives_v2.db"


class WiktionaryPrimitivesV2Loader(BaseExternalParser):
    """Read deterministic Wiktionary-derived primitive decompositions from v2 DB.

    Includes a **scaffolding filter**: primitives that Wiktionary's
    definition-keyword patterns vote for on more than ``scaffolding_threshold``
    of all words are deemed uninformative (definitional scaffolding like BE,
    SOMETHING, ONE that appear in every gloss) and dropped from votes. The
    threshold defaults to 0.80 — primitives the parser votes for on >80% of
    words add no discriminative signal and contribute to the cross-word
    pollution found in the May 2026 antonym investigation.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        scaffolding_threshold: float = 0.80,
    ):
        super().__init__(ParserConfig(name="wiktionary_v2"))
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_V2_DB
        self.conn: Optional[sqlite3.Connection] = None
        self.scaffolding_threshold = scaffolding_threshold
        self._scaffolding: Optional[set] = None

    def load(self) -> bool:
        if not self.db_path.exists():
            logger.warning(
                "Wiktionary v2 DB not found at %s — run "
                "scripts/build_wiktionary_primitives.py --build to create it",
                self.db_path,
            )
            return False

        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            # Confirm expected schema is present before claiming success.
            rows = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('word_primitives_v2', 'primitive_dictionary')"
            ).fetchall()
            if {r[0] for r in rows} != {"word_primitives_v2", "primitive_dictionary"}:
                logger.error(
                    "Wiktionary v2 DB %s missing expected tables; have %s",
                    self.db_path,
                    [r[0] for r in rows],
                )
                self.conn.close()
                self.conn = None
                return False

            count = self.conn.execute(
                "SELECT COUNT(DISTINCT word) FROM word_primitives_v2"
            ).fetchone()[0]
            logger.info("Loaded Wiktionary v2 with %d distinct words", count)
            self._loaded = True
            self._scaffolding = self._compute_scaffolding(count)
            if self._scaffolding:
                logger.info(
                    "Wiktionary scaffolding filter dropped %d primitives "
                    "voted on > %.0f%% of words: %s",
                    len(self._scaffolding),
                    self.scaffolding_threshold * 100,
                    sorted(self._scaffolding),
                )
            return True
        except sqlite3.Error as exc:
            logger.error("Failed to open Wiktionary v2 DB: %s", exc)
            self.conn = None
            return False

    def _compute_scaffolding(self, total_words: int) -> set:
        """Identify primitives Wiktionary votes for on > scaffolding_threshold of words.

        These are the "BE / SOMETHING / ONE / BEFORE / SOME / MUCH" pattern —
        common definitional scaffolding that every gloss mentions. They add no
        discriminative signal between words and pollute cross-word geometry.
        Computed once at load time and cached.
        """
        if total_words == 0 or self.conn is None:
            return set()
        threshold_count = int(total_words * self.scaffolding_threshold)
        rows = self.conn.execute(
            """
            SELECT pd.name, COUNT(DISTINCT wp.word) AS word_count
            FROM word_primitives_v2 wp
            JOIN primitive_dictionary pd ON wp.primitive_id = pd.id
            WHERE wp.value != 0
            GROUP BY pd.name
            HAVING word_count > ?
            """,
            (threshold_count,),
        ).fetchall()
        return {r["name"] for r in rows}

    def to_primitives(self, word: str) -> Dict[str, int]:
        """Map word to {primitive_name: value} via the v2 schema."""
        return {p: v for p, (v, _) in self.to_primitives_with_confidence(word).items()}

    def to_primitives_with_confidence(self, word: str) -> Dict[str, Tuple[int, float]]:
        """Map word to {primitive_name: (value, confidence)} — preferred entry.

        The v2 DB stores confidence per (word, primitive) pair. We surface
        it here so the integrator's weighted voting can use real
        confidences instead of a source-level prior.
        """
        if not self._loaded or self.conn is None:
            return {}

        rows = self.conn.execute(
            """
            SELECT pd.name AS primitive,
                   wp.value AS value,
                   wp.confidence AS confidence
            FROM word_primitives_v2 wp
            JOIN primitive_dictionary pd ON wp.primitive_id = pd.id
            WHERE wp.word = ? AND wp.value != 0
            """,
            (word.lower(),),
        ).fetchall()

        out: Dict[str, Tuple[int, float]] = {}
        scaffolding = self._scaffolding or set()
        # If multiple rows for the same (word, primitive) — e.g., from
        # different POS or sources — keep the one with highest confidence.
        for row in rows:
            prim = row["primitive"]
            if prim in scaffolding:
                # Scaffolding primitives (votes on >threshold of vocabulary)
                # carry no discriminative signal — drop them. See
                # _compute_scaffolding for the empirical rule.
                continue
            val = int(row["value"])
            conf = float(row["confidence"]) if row["confidence"] is not None else 1.0
            if prim not in out or out[prim][1] < conf:
                out[prim] = (val, conf)
        return out

    def get_all_words(self) -> List[str]:
        """Return every distinct word in the v2 DB (~1.3M)."""
        if not self._loaded or self.conn is None:
            return []
        rows = self.conn.execute(
            "SELECT DISTINCT word FROM word_primitives_v2"
        ).fetchall()
        return [r[0] for r in rows]

    def has_word(self, word: str) -> bool:
        if not self._loaded or self.conn is None:
            return False
        row = self.conn.execute(
            "SELECT 1 FROM word_primitives_v2 WHERE word = ? LIMIT 1",
            (word.lower(),),
        ).fetchone()
        return row is not None

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        super().close()
