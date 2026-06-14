"""
Audit Logger

Comprehensive audit logging with full provenance tracking.
Every decision is logged with source attribution.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Logs all audit decisions with full provenance.

    Every primitive assignment is logged with:
    - Source attribution (which sources contributed)
    - Confidence scores
    - Decision type (auto_applied, manual_required, etc.)
    - Before/after values
    """

    def __init__(self, db_path: Path):
        """
        Initialize audit logger.

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
        """Ensure audit log table exists."""
        conn = self._get_connection()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER NOT NULL,
                lemma TEXT NOT NULL,
                primitive TEXT NOT NULL,

                -- Before/after state
                old_value INTEGER,
                new_value INTEGER,

                -- Decision details
                decision TEXT NOT NULL,
                confidence REAL,

                -- Source attribution (JSON)
                sources TEXT NOT NULL,

                -- Timestamps
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (word_id) REFERENCES lexemes(id)
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_word ON audit_log(word_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_decision ON audit_log(decision)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_time ON audit_log(processed_at)")

        conn.commit()
        logger.info("Audit log table initialized")

    def log_decision(
        self,
        word_id: int,
        lemma: str,
        primitive: str,
        decision: str,
        old_value: Optional[int],
        new_value: Optional[int],
        sources: Dict,
        confidence: float = 0.0,
    ):
        """
        Log an audit decision with full provenance.

        Args:
            word_id: Word ID
            lemma: Word lemma
            primitive: Primitive name
            decision: Decision type (auto_applied, manual_required, no_change, llm_inferred, no_data)
            old_value: Previous value in database
            new_value: New value (if applied)
            sources: Dict of source attributions
            confidence: Confidence score
        """
        conn = self._get_connection()

        conn.execute("""
            INSERT INTO audit_log
            (word_id, lemma, primitive, old_value, new_value, decision, confidence, sources)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            word_id, lemma, primitive, old_value, new_value,
            decision, confidence, json.dumps(sources)
        ))

        conn.commit()
        logger.debug(f"Logged: {lemma}/{primitive} -> {decision} (conf={confidence:.2f})")

    def get_decisions_for_word(self, word_id: int) -> List[Dict]:
        """Get all audit decisions for a word."""
        conn = self._get_connection()

        cursor = conn.execute("""
            SELECT * FROM audit_log
            WHERE word_id = ?
            ORDER BY processed_at DESC
        """, (word_id,))

        decisions = []
        for row in cursor.fetchall():
            decision = dict(row)
            decision['sources'] = json.loads(decision['sources'])
            decisions.append(decision)

        return decisions

    def get_recent_decisions(self, limit: int = 100) -> List[Dict]:
        """Get most recent audit decisions."""
        conn = self._get_connection()

        cursor = conn.execute("""
            SELECT * FROM audit_log
            ORDER BY processed_at DESC
            LIMIT ?
        """, (limit,))

        decisions = []
        for row in cursor.fetchall():
            decision = dict(row)
            decision['sources'] = json.loads(decision['sources'])
            decisions.append(decision)

        return decisions

    def get_summary(self) -> Dict:
        """Get summary statistics of audit decisions."""
        conn = self._get_connection()

        # Count by decision type
        cursor = conn.execute("""
            SELECT
                decision,
                COUNT(*) as count,
                AVG(confidence) as avg_confidence
            FROM audit_log
            GROUP BY decision
        """)
        by_decision = {row['decision']: {'count': row['count'], 'avg_confidence': row['avg_confidence']}
                       for row in cursor.fetchall()}

        # Total counts
        cursor = conn.execute("SELECT COUNT(*) as total FROM audit_log")
        total = cursor.fetchone()['total']

        # Count unique words processed
        cursor = conn.execute("SELECT COUNT(DISTINCT word_id) as unique_words FROM audit_log")
        unique_words = cursor.fetchone()['unique_words']

        # Recent activity (last hour)
        cursor = conn.execute("""
            SELECT COUNT(*) as recent
            FROM audit_log
            WHERE processed_at > datetime('now', '-1 hour')
        """)
        recent = cursor.fetchone()['recent']

        return {
            "total_decisions": total,
            "unique_words": unique_words,
            "recent_hour": recent,
            "by_decision": by_decision,
        }

    def export_to_json(self, output_path: Path, word_ids: List[int] = None):
        """
        Export audit log to JSON file.

        Args:
            output_path: Path to output file
            word_ids: Optional list of word IDs to export (None for all)
        """
        conn = self._get_connection()

        if word_ids:
            placeholders = ','.join('?' * len(word_ids))
            cursor = conn.execute(f"""
                SELECT * FROM audit_log
                WHERE word_id IN ({placeholders})
                ORDER BY word_id, primitive
            """, word_ids)
        else:
            cursor = conn.execute("""
                SELECT * FROM audit_log
                ORDER BY word_id, primitive
            """)

        records = []
        for row in cursor.fetchall():
            record = dict(row)
            record['sources'] = json.loads(record['sources'])
            # Convert datetime to string
            if record['processed_at']:
                record['processed_at'] = str(record['processed_at'])
            records.append(record)

        with open(output_path, 'w') as f:
            json.dump(records, f, indent=2)

        logger.info(f"Exported {len(records)} audit records to {output_path}")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None


if __name__ == "__main__":
    from daemon.config import DB_PATH

    logging.basicConfig(level=logging.INFO)

    audit_logger = AuditLogger(DB_PATH)
    print("Audit log summary:", audit_logger.get_summary())

    recent = audit_logger.get_recent_decisions(limit=5)
    print(f"\nRecent {len(recent)} decisions:")
    for d in recent:
        print(f"  {d['lemma']}/{d['primitive']}: {d['decision']} ({d['old_value']} -> {d['new_value']})")
