"""
Review Queue

Manages the review queue for constraints that need manual review.
Items are added when sources disagree or confidence is low.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ReviewQueue:
    """
    Manages the review queue for manual review items.

    Items are added when:
    - Sources disagree on a primitive value
    - Confidence is below threshold
    - Bipolar violations detected
    """

    def __init__(self, db_path: Path):
        """
        Initialize review queue.

        Args:
            db_path: Path to the lexicon database
        """
        self.db_path = db_path
        self.conn = None
        self._ensure_table()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def _ensure_table(self):
        """Ensure review queue table exists."""
        conn = self._get_connection()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS constraint_review_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lexeme_id INTEGER NOT NULL,
                lemma TEXT NOT NULL,
                pos TEXT,
                primitive TEXT NOT NULL,
                current_value INTEGER,
                proposed_value INTEGER,

                -- Constraint sources (JSON)
                nlp_constraints TEXT,
                model_votes TEXT,
                ollama_response TEXT,

                -- Conflict details
                conflict_type TEXT,
                conflict_detail TEXT,
                confidence REAL,

                -- Review tracking
                priority INTEGER DEFAULT 5,
                status TEXT DEFAULT 'pending',
                resolution TEXT,
                resolved_value INTEGER,
                reviewer TEXT,
                resolved_at TIMESTAMP,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lexeme_id) REFERENCES lexemes(id)
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_review_priority ON constraint_review_queue(priority, status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_review_lexeme ON constraint_review_queue(lexeme_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_review_status ON constraint_review_queue(status)")

        conn.commit()
        logger.info("Review queue table initialized")

    def add(
        self,
        lexeme_id: int,
        lemma: str,
        pos: str,
        primitive: str,
        current_value: Optional[int],
        proposed_value: Optional[int],
        nlp_constraints: Dict,
        conflict_type: str,
        conflict_detail: str = None,
        confidence: float = 0.0,
        priority: int = 5,
        model_votes: Dict = None,
        ollama_response: str = None,
    ):
        """
        Add item to review queue.

        Args:
            lexeme_id: Word ID
            lemma: Word lemma
            pos: Part of speech
            primitive: Primitive name
            current_value: Current value in database
            proposed_value: Proposed value (may be None if uncertain)
            nlp_constraints: Dict of NLP source constraints
            conflict_type: Type of conflict
            conflict_detail: Human-readable conflict description
            confidence: Confidence score
            priority: Priority level (1=highest, 10=lowest)
            model_votes: Dict of model votes (if any)
            ollama_response: Raw Ollama response (if any)
        """
        conn = self._get_connection()

        # Check if already exists
        cursor = conn.execute("""
            SELECT id FROM constraint_review_queue
            WHERE lexeme_id = ? AND primitive = ? AND status = 'pending'
        """, (lexeme_id, primitive))

        if cursor.fetchone():
            logger.debug(f"Review item already exists for {lemma}/{primitive}")
            return

        conn.execute("""
            INSERT INTO constraint_review_queue
            (lexeme_id, lemma, pos, primitive, current_value, proposed_value,
             nlp_constraints, model_votes, ollama_response,
             conflict_type, conflict_detail, confidence, priority, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            lexeme_id, lemma, pos, primitive, current_value, proposed_value,
            json.dumps(nlp_constraints), json.dumps(model_votes or {}), ollama_response,
            conflict_type, conflict_detail, confidence, priority
        ))

        conn.commit()
        logger.debug(f"Added review item: {lemma}/{primitive} ({conflict_type})")

    def get_pending(self, limit: int = 100) -> List[Dict]:
        """
        Get pending review items, ordered by priority.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of review item dicts
        """
        conn = self._get_connection()

        cursor = conn.execute("""
            SELECT * FROM constraint_review_queue
            WHERE status = 'pending'
            ORDER BY priority ASC, created_at ASC
            LIMIT ?
        """, (limit,))

        items = []
        for row in cursor.fetchall():
            item = dict(row)
            # Parse JSON fields
            item['nlp_constraints'] = json.loads(item['nlp_constraints'] or '{}')
            item['model_votes'] = json.loads(item['model_votes'] or '{}')
            items.append(item)

        return items

    def get_by_word(self, lexeme_id: int) -> List[Dict]:
        """Get all review items for a word."""
        conn = self._get_connection()

        cursor = conn.execute("""
            SELECT * FROM constraint_review_queue
            WHERE lexeme_id = ?
            ORDER BY primitive
        """, (lexeme_id,))

        items = []
        for row in cursor.fetchall():
            item = dict(row)
            item['nlp_constraints'] = json.loads(item['nlp_constraints'] or '{}')
            item['model_votes'] = json.loads(item['model_votes'] or '{}')
            items.append(item)

        return items

    def resolve(
        self,
        item_id: int,
        resolution: str,
        resolved_value: Optional[int],
        reviewer: str = "manual",
    ):
        """
        Resolve a review item.

        Args:
            item_id: Review item ID
            resolution: Resolution type (accepted, rejected, modified)
            resolved_value: Final value to use
            reviewer: Who resolved (manual, override, consensus)
        """
        conn = self._get_connection()

        conn.execute("""
            UPDATE constraint_review_queue
            SET status = 'resolved',
                resolution = ?,
                resolved_value = ?,
                reviewer = ?,
                resolved_at = ?
            WHERE id = ?
        """, (resolution, resolved_value, reviewer, datetime.now(), item_id))

        conn.commit()
        logger.info(f"Resolved review item {item_id}: {resolution} -> {resolved_value}")

    def get_stats(self) -> Dict:
        """Get review queue statistics."""
        conn = self._get_connection()

        # Count by status
        cursor = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM constraint_review_queue
            GROUP BY status
        """)
        by_status = {row['status']: row['count'] for row in cursor.fetchall()}

        # Count by conflict type
        cursor = conn.execute("""
            SELECT conflict_type, COUNT(*) as count
            FROM constraint_review_queue
            WHERE status = 'pending'
            GROUP BY conflict_type
        """)
        by_conflict = {row['conflict_type']: row['count'] for row in cursor.fetchall()}

        # Count by priority
        cursor = conn.execute("""
            SELECT priority, COUNT(*) as count
            FROM constraint_review_queue
            WHERE status = 'pending'
            GROUP BY priority
            ORDER BY priority
        """)
        by_priority = {row['priority']: row['count'] for row in cursor.fetchall()}

        return {
            "by_status": by_status,
            "by_conflict_type": by_conflict,
            "by_priority": by_priority,
            "total_pending": by_status.get('pending', 0),
            "total_resolved": by_status.get('resolved', 0),
        }

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None


if __name__ == "__main__":
    from daemon.config import DB_PATH

    logging.basicConfig(level=logging.INFO)

    queue = ReviewQueue(DB_PATH)
    print("Review queue stats:", queue.get_stats())

    pending = queue.get_pending(limit=5)
    print(f"\nTop {len(pending)} pending items:")
    for item in pending:
        print(f"  {item['lemma']}/{item['primitive']}: {item['conflict_type']} (priority={item['priority']})")
