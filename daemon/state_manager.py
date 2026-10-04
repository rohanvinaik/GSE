"""
State Manager

Manages persistent state for the audit daemon:
- Progress checkpoints (resumable processing)
- Audit state per word/primitive
- Statistics tracking

All state is stored in the lexicon.db SQLite database.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class StateManager:
    """
    Manages persistent state for resumable audit processing.

    Features:
    - Progress checkpointing
    - Per-word/primitive audit state
    - Statistics tracking
    """

    def __init__(self, db_path: Path):
        """
        Initialize state manager.

        Args:
            db_path: Path to the lexicon database
        """
        self.db_path = db_path
        self.conn = None
        self._ensure_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def _ensure_tables(self):
        """Ensure required tables exist."""
        conn = self._get_connection()

        # Audit checkpoint table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_checkpoint (
                id INTEGER PRIMARY KEY,
                last_word_id INTEGER NOT NULL DEFAULT 0,
                last_primitive_idx INTEGER DEFAULT 0,
                total_words_processed INTEGER DEFAULT 0,
                total_primitives_audited INTEGER DEFAULT 0,
                auto_applied INTEGER DEFAULT 0,
                flagged_review INTEGER DEFAULT 0,
                conflicts_found INTEGER DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'running'
            )
        """)

        # Audit state per word/primitive
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER NOT NULL,
                primitive TEXT NOT NULL,
                audit_status TEXT DEFAULT 'pending',
                current_value INTEGER,
                proposed_value INTEGER,
                confidence REAL,
                source_agreement TEXT,
                decision TEXT,
                decision_reason TEXT,
                processed_at TIMESTAMP,
                UNIQUE(word_id, primitive),
                FOREIGN KEY (word_id) REFERENCES lexemes(id)
            )
        """)

        # Create indices
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_state_status ON audit_state(audit_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_state_word ON audit_state(word_id)")

        conn.commit()
        logger.info("State tables initialized")

    def get_checkpoint(self) -> Dict:
        """Get current checkpoint state."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM audit_checkpoint WHERE id = 1")
        row = cursor.fetchone()

        if row:
            return dict(row)
        else:
            # Initialize checkpoint
            conn.execute("""
                INSERT INTO audit_checkpoint (id, last_word_id, status)
                VALUES (1, 0, 'initialized')
            """)
            conn.commit()
            return self.get_checkpoint()

    def save_checkpoint(
        self,
        last_word_id: int,
        words_processed: int = None,
        primitives_audited: int = None,
        auto_applied: int = None,
        flagged_review: int = None,
        conflicts_found: int = None,
    ):
        """
        Save checkpoint state.

        Args:
            last_word_id: Last processed word ID
            words_processed: Total words processed (incremental)
            primitives_audited: Total primitives audited (incremental)
            auto_applied: Auto-applied count (incremental)
            flagged_review: Flagged for review count (incremental)
            conflicts_found: Conflicts found count (incremental)
        """
        conn = self._get_connection()

        # Build update query dynamically
        updates = ["last_word_id = ?", "last_heartbeat = ?", "status = 'running'"]
        params = [last_word_id, datetime.now()]

        if words_processed is not None:
            updates.append("total_words_processed = total_words_processed + ?")
            params.append(words_processed)

        if primitives_audited is not None:
            updates.append("total_primitives_audited = total_primitives_audited + ?")
            params.append(primitives_audited)

        if auto_applied is not None:
            updates.append("auto_applied = auto_applied + ?")
            params.append(auto_applied)

        if flagged_review is not None:
            updates.append("flagged_review = flagged_review + ?")
            params.append(flagged_review)

        if conflicts_found is not None:
            updates.append("conflicts_found = conflicts_found + ?")
            params.append(conflicts_found)

        query = f"UPDATE audit_checkpoint SET {', '.join(updates)} WHERE id = 1"
        conn.execute(query, params)
        conn.commit()

    def set_checkpoint_status(self, status: str):
        """Set checkpoint status (running, paused, completed)."""
        conn = self._get_connection()
        conn.execute(
            "UPDATE audit_checkpoint SET status = ?, last_heartbeat = ? WHERE id = 1",
            (status, datetime.now())
        )
        conn.commit()

    def get_words_to_audit(
        self,
        resume_from: int = 0,
        batch_size: int = 10,
        max_frequency_rank: int = 5000,
    ) -> List[Dict]:
        """
        Get next batch of words to audit.

        Args:
            resume_from: Resume from this word_id
            batch_size: Number of words to return
            max_frequency_rank: Only include words with rank <= this

        Returns:
            List of word records with id, lemma, pos, frequency_rank
        """
        conn = self._get_connection()

        cursor = conn.execute("""
            SELECT l.id, l.lemma, l.pos, l.gloss,
                   COALESCE(l.frequency_rank, 99999) as frequency_rank
            FROM lexemes l
            WHERE l.id > ?
              AND l.component_type = 'ATOMIC'
              AND COALESCE(l.frequency_rank, 99999) <= ?
            ORDER BY frequency_rank ASC, l.id ASC
            LIMIT ?
        """, (resume_from, max_frequency_rank, batch_size))

        return [dict(row) for row in cursor.fetchall()]

    def get_primitive_value(self, word_id: int, primitive: str) -> Optional[int]:
        """Get current primitive value for a word."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT value FROM primitive_values
            WHERE lexeme_id = ? AND primitive = ?
        """, (word_id, primitive))
        row = cursor.fetchone()
        return row['value'] if row else None

    def set_primitive_value(
        self,
        word_id: int,
        primitive: str,
        value: int,
        source: str,
        confidence: float = 1.0,
    ):
        """
        Set primitive value for a word.

        Args:
            word_id: Word ID
            primitive: Primitive name
            value: Value to set (+1, 0, -1)
            source: Source of the value (e.g., "audit:unanimous")
            confidence: Confidence score
        """
        conn = self._get_connection()

        # Use INSERT OR REPLACE to handle both new and existing values
        conn.execute("""
            INSERT OR REPLACE INTO primitive_values
            (lexeme_id, primitive, value, confidence, source)
            VALUES (?, ?, ?, ?, ?)
        """, (word_id, primitive, value, confidence, source))

        conn.commit()

    def save_audit_state(
        self,
        word_id: int,
        primitive: str,
        status: str,
        current_value: Optional[int],
        proposed_value: Optional[int],
        confidence: float,
        sources: Dict,
        decision: str,
        reason: str = None,
    ):
        """
        Save audit state for a word/primitive.

        Args:
            word_id: Word ID
            primitive: Primitive name
            status: Audit status (pending, processing, completed, conflict, manual_review)
            current_value: Current value in database
            proposed_value: Proposed new value
            confidence: Confidence score
            sources: Dict of source agreements
            decision: Decision made (auto_applied, manual_required, no_change, etc.)
            reason: Reason for decision
        """
        conn = self._get_connection()

        conn.execute("""
            INSERT OR REPLACE INTO audit_state
            (word_id, primitive, audit_status, current_value, proposed_value,
             confidence, source_agreement, decision, decision_reason, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            word_id, primitive, status, current_value, proposed_value,
            confidence, json.dumps(sources), decision, reason, datetime.now()
        ))

        conn.commit()

    def get_audit_summary(self) -> Dict:
        """Get summary statistics of audit progress."""
        conn = self._get_connection()

        # Get checkpoint stats
        checkpoint = self.get_checkpoint()

        # Get audit state breakdown
        cursor = conn.execute("""
            SELECT
                decision,
                COUNT(*) as count,
                AVG(confidence) as avg_confidence
            FROM audit_state
            GROUP BY decision
        """)
        by_decision = {row['decision']: {'count': row['count'], 'avg_confidence': row['avg_confidence']}
                       for row in cursor.fetchall()}

        # Get status breakdown
        cursor = conn.execute("""
            SELECT audit_status, COUNT(*) as count
            FROM audit_state
            GROUP BY audit_status
        """)
        by_status = {row['audit_status']: row['count'] for row in cursor.fetchall()}

        return {
            "checkpoint": checkpoint,
            "by_decision": by_decision,
            "by_status": by_status,
        }

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None


if __name__ == "__main__":
    from daemon.config import DB_PATH

    logging.basicConfig(level=logging.INFO)

    state = StateManager(DB_PATH)
    print("Checkpoint:", state.get_checkpoint())
    print("Summary:", state.get_audit_summary())

    # Test getting words
    words = state.get_words_to_audit(resume_from=0, batch_size=5)
    print(f"Next {len(words)} words to audit:")
    for w in words:
        print(f"  {w['id']}: {w['lemma']} (rank={w['frequency_rank']})")
