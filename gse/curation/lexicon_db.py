"""
GSE Lexicon Database

Provides CRUD operations for the lexicon database with full 72-primitive support.
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from gse.curation.schema import (
    ALL_PRIMITIVES,
    SCHEMA,
)


@dataclass
class LexemeEntry:
    """A lexeme entry with its decomposition."""
    id: int
    lemma: str
    pos: str
    sense_id: str
    gloss: Optional[str]
    source: str
    confidence: float
    frequency_rank: Optional[int]
    frequency_weight: Optional[float]
    phase: int
    validation_status: str
    decomposition: Dict[str, int] = field(default_factory=dict)
    primitive_confidences: Dict[str, float] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    passed: bool
    validation_type: str
    violations: List[Dict[str, Any]] = field(default_factory=list)
    details: Optional[str] = None


class LexiconDatabase:
    """Database operations for the GSE lexicon."""

    def __init__(self, db_path: str = "lexicon.db"):
        """
        Initialize the lexicon database.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self):
        """Create tables if they don't exist."""
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        """Close the database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # =========================================================================
    # LEXEME OPERATIONS
    # =========================================================================

    def add_lexeme(
        self,
        lemma: str,
        pos: str,
        sense_id: str = "01",
        gloss: Optional[str] = None,
        source: str = "llm",
        confidence: float = 1.0,
        frequency_rank: Optional[int] = None,
        frequency_weight: Optional[float] = None,
        phase: int = 0,
    ) -> int:
        """
        Add a new lexeme entry.

        Returns:
            The ID of the inserted lexeme
        """
        cursor = self.conn.execute(
            """
            INSERT INTO lexemes (
                lemma, pos, sense_id, gloss, source, confidence,
                frequency_rank, frequency_weight, phase
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (lemma, pos, sense_id, gloss, source, confidence,
             frequency_rank, frequency_weight, phase)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_lexeme(self, lemma: str, pos: Optional[str] = None) -> Optional[LexemeEntry]:
        """Get a lexeme by lemma (and optionally pos)."""
        if pos:
            cursor = self.conn.execute(
                "SELECT * FROM lexemes WHERE lemma = ? AND pos = ?",
                (lemma, pos)
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM lexemes WHERE lemma = ?",
                (lemma,)
            )
        row = cursor.fetchone()
        if row is None:
            return None

        entry = self._row_to_entry(row)
        entry.decomposition = self.get_decomposition(entry.id)
        entry.primitive_confidences = self.get_primitive_confidences(entry.id)
        return entry

    def get_lexeme_by_id(self, lexeme_id: int) -> Optional[LexemeEntry]:
        """Get a lexeme by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM lexemes WHERE id = ?",
            (lexeme_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None

        entry = self._row_to_entry(row)
        entry.decomposition = self.get_decomposition(entry.id)
        entry.primitive_confidences = self.get_primitive_confidences(entry.id)
        return entry

    def _row_to_entry(self, row: sqlite3.Row) -> LexemeEntry:
        """Convert a database row to a LexemeEntry."""
        return LexemeEntry(
            id=row["id"],
            lemma=row["lemma"],
            pos=row["pos"],
            sense_id=row["sense_id"],
            gloss=row["gloss"],
            source=row["source"],
            confidence=row["confidence"],
            frequency_rank=row["frequency_rank"],
            frequency_weight=row["frequency_weight"],
            phase=row["phase"],
            validation_status=row["validation_status"],
        )

    def update_lexeme(
        self,
        lexeme_id: int,
        validation_status: Optional[str] = None,
        confidence: Optional[float] = None,
        source: Optional[str] = None,
        gloss: Optional[str] = None,
    ):
        """Update lexeme fields."""
        updates = []
        params = []

        if validation_status is not None:
            updates.append("validation_status = ?")
            params.append(validation_status)
        if confidence is not None:
            updates.append("confidence = ?")
            params.append(confidence)
        if source is not None:
            updates.append("source = ?")
            params.append(source)
        if gloss is not None:
            updates.append("gloss = ?")
            params.append(gloss)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(lexeme_id)
            self.conn.execute(
                f"UPDATE lexemes SET {', '.join(updates)} WHERE id = ?",
                params
            )
            self.conn.commit()

    def update_frequency(
        self,
        lemma: str,
        frequency_rank: int,
        frequency_weight: float,
    ):
        """Update frequency data for a lexeme."""
        self.conn.execute(
            """
            UPDATE lexemes
            SET frequency_rank = ?, frequency_weight = ?, updated_at = CURRENT_TIMESTAMP
            WHERE lemma = ?
            """,
            (frequency_rank, frequency_weight, lemma)
        )
        self.conn.commit()

    # =========================================================================
    # DECOMPOSITION OPERATIONS
    # =========================================================================

    def set_decomposition(
        self,
        lexeme_id: int,
        decomposition: Dict[str, int],
        source: str = "llm",
        confidences: Optional[Dict[str, float]] = None,
    ):
        """
        Set the full 72-primitive decomposition for a lexeme.

        Args:
            lexeme_id: The lexeme ID
            decomposition: Dict mapping primitive names to values (-1, 0, +1)
            source: Source of the decomposition (llm, rule, manual, morphology)
            confidences: Optional dict of per-primitive confidences
        """
        confidences = confidences or {}

        # Ensure all 72 primitives are present (fill missing with 0)
        full_decomp = {prim: decomposition.get(prim, 0) for prim in ALL_PRIMITIVES}

        # Delete existing decomposition
        self.conn.execute(
            "DELETE FROM primitive_values WHERE lexeme_id = ?",
            (lexeme_id,)
        )

        # Insert all 72 primitive values
        for primitive, value in full_decomp.items():
            conf = confidences.get(primitive, 1.0)
            self.conn.execute(
                """
                INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                (lexeme_id, primitive, value, conf, source)
            )

        self.conn.commit()

    def get_decomposition(self, lexeme_id: int) -> Dict[str, int]:
        """Get the full decomposition for a lexeme."""
        cursor = self.conn.execute(
            "SELECT primitive, value FROM primitive_values WHERE lexeme_id = ?",
            (lexeme_id,)
        )
        decomp = {row["primitive"]: row["value"] for row in cursor.fetchall()}

        # Fill missing primitives with 0
        for prim in ALL_PRIMITIVES:
            if prim not in decomp:
                decomp[prim] = 0

        return decomp

    def get_primitive_confidences(self, lexeme_id: int) -> Dict[str, float]:
        """Get per-primitive confidences for a lexeme."""
        cursor = self.conn.execute(
            "SELECT primitive, confidence FROM primitive_values WHERE lexeme_id = ?",
            (lexeme_id,)
        )
        return {row["primitive"]: row["confidence"] for row in cursor.fetchall()}

    def get_active_primitives(self, lexeme_id: int) -> Dict[str, int]:
        """Get only the non-zero primitives for a lexeme."""
        cursor = self.conn.execute(
            "SELECT primitive, value FROM primitive_values WHERE lexeme_id = ? AND value != 0",
            (lexeme_id,)
        )
        return {row["primitive"]: row["value"] for row in cursor.fetchall()}

    # =========================================================================
    # BATCH QUERY OPERATIONS
    # =========================================================================

    def get_words_by_rank_range(
        self,
        start_rank: int,
        end_rank: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get words within a frequency rank range."""
        if end_rank is None:
            cursor = self.conn.execute(
                """
                SELECT * FROM lexemes
                WHERE frequency_rank >= ?
                ORDER BY frequency_rank
                """,
                (start_rank,)
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT * FROM lexemes
                WHERE frequency_rank >= ? AND frequency_rank <= ?
                ORDER BY frequency_rank
                """,
                (start_rank, end_rank)
            )
        return [dict(row) for row in cursor.fetchall()]

    def get_unprocessed_words(
        self,
        phase: int,
        start_rank: int = 1,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get words that haven't been processed for a phase."""
        query = """
            SELECT * FROM lexemes
            WHERE phase = ? AND validation_status = 'pending'
            AND frequency_rank >= ?
            ORDER BY frequency_rank
        """
        params: List[Any] = [phase, start_rank]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_validated_entries(
        self,
        phase: Optional[int] = None,
    ) -> List[LexemeEntry]:
        """Get all validated lexeme entries."""
        if phase is not None:
            cursor = self.conn.execute(
                """
                SELECT * FROM lexemes
                WHERE validation_status = 'validated' AND phase = ?
                ORDER BY frequency_rank
                """,
                (phase,)
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT * FROM lexemes
                WHERE validation_status = 'validated'
                ORDER BY frequency_rank
                """
            )

        entries = []
        for row in cursor.fetchall():
            entry = self._row_to_entry(row)
            entry.decomposition = self.get_decomposition(entry.id)
            entries.append(entry)
        return entries

    def count_by_phase(self, phase: int) -> Dict[str, int]:
        """Count words by status for a phase."""
        cursor = self.conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN validation_status = 'validated' THEN 1 ELSE 0 END) as validated,
                SUM(CASE WHEN validation_status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN validation_status = 'rejected' THEN 1 ELSE 0 END) as rejected
            FROM lexemes
            WHERE phase = ?
            """,
            (phase,)
        )
        row = cursor.fetchone()
        return {
            "total": row["total"] or 0,
            "validated": row["validated"] or 0,
            "pending": row["pending"] or 0,
            "rejected": row["rejected"] or 0,
        }

    # =========================================================================
    # VALIDATION OPERATIONS
    # =========================================================================

    def store_validation_result(
        self,
        lexeme_id: int,
        validation_type: str,
        passed: bool,
        details: Optional[str] = None,
    ):
        """Store a validation result for a lexeme."""
        self.conn.execute(
            """
            INSERT INTO validation_results (lexeme_id, validation_type, passed, details)
            VALUES (?, ?, ?, ?)
            """,
            (lexeme_id, validation_type, passed, details)
        )
        self.conn.commit()

    def get_validation_results(
        self,
        lexeme_id: int,
    ) -> List[Dict[str, Any]]:
        """Get all validation results for a lexeme."""
        cursor = self.conn.execute(
            "SELECT * FROM validation_results WHERE lexeme_id = ? ORDER BY timestamp DESC",
            (lexeme_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def flag_for_review(self, lexeme_id: int):
        """Flag a lexeme for manual review."""
        self.update_lexeme(lexeme_id, validation_status="review")

    # =========================================================================
    # PROVENANCE OPERATIONS
    # =========================================================================

    def add_provenance(
        self,
        lexeme_id: int,
        source_type: str,
        source_detail: Optional[str] = None,
        primitive: Optional[str] = None,
        confidence_before: Optional[float] = None,
        confidence_after: Optional[float] = None,
    ):
        """Add a provenance record for a decomposition change."""
        self.conn.execute(
            """
            INSERT INTO decomposition_provenance
            (lexeme_id, primitive, source_type, source_detail, confidence_before, confidence_after)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (lexeme_id, primitive, source_type, source_detail,
             confidence_before, confidence_after)
        )
        self.conn.commit()

    # =========================================================================
    # CHECKPOINT OPERATIONS
    # =========================================================================

    def checkpoint(self, phase: int, last_rank: int, words_processed: int, words_validated: int):
        """Save a processing checkpoint."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO processing_checkpoints
            (phase, last_processed_rank, words_processed, words_validated)
            VALUES (?, ?, ?, ?)
            """,
            (phase, last_rank, words_processed, words_validated)
        )
        self.conn.commit()

    def get_last_checkpoint(self, phase: int) -> Optional[Dict[str, Any]]:
        """Get the last checkpoint for a phase."""
        cursor = self.conn.execute(
            "SELECT * FROM processing_checkpoints WHERE phase = ?",
            (phase,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get overall database statistics."""
        stats = {
            "total_lexemes": 0,
            "by_phase": {},
            "by_status": {},
            "by_source": {},
            "primitive_coverage": {},
        }

        # Total count
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM lexemes")
        stats["total_lexemes"] = cursor.fetchone()["count"]

        # By phase
        cursor = self.conn.execute(
            "SELECT phase, COUNT(*) as count FROM lexemes GROUP BY phase"
        )
        stats["by_phase"] = {row["phase"]: row["count"] for row in cursor.fetchall()}

        # By status
        cursor = self.conn.execute(
            "SELECT validation_status, COUNT(*) as count FROM lexemes GROUP BY validation_status"
        )
        stats["by_status"] = {row["validation_status"]: row["count"] for row in cursor.fetchall()}

        # By source
        cursor = self.conn.execute(
            "SELECT source, COUNT(*) as count FROM lexemes GROUP BY source"
        )
        stats["by_source"] = {row["source"]: row["count"] for row in cursor.fetchall()}

        return stats

    # =========================================================================
    # EXTERNAL SOURCE DISAGREEMENT OPERATIONS
    # =========================================================================

    def store_disagreement(
        self,
        lexeme_id: int,
        primitive: str,
        llm_value: int,
        external_value: int,
        external_source: str,
        severity: str,
    ):
        """Store a disagreement between LLM and external source."""
        self.conn.execute(
            """
            INSERT INTO external_disagreements
            (lexeme_id, primitive, llm_value, external_value, external_source, severity)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (lexeme_id, primitive, llm_value, external_value, external_source, severity)
        )
        self.conn.commit()

    def store_disagreements_batch(
        self,
        disagreements: List[Tuple[int, str, int, int, str, str]],
    ):
        """Store multiple disagreements at once."""
        self.conn.executemany(
            """
            INSERT INTO external_disagreements
            (lexeme_id, primitive, llm_value, external_value, external_source, severity)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            disagreements
        )
        self.conn.commit()

    def get_disagreements(
        self,
        lexeme_id: Optional[int] = None,
        severity: Optional[str] = None,
        unresolved_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get disagreement records."""
        query = "SELECT * FROM external_disagreements WHERE 1=1"
        params = []

        if lexeme_id is not None:
            query += " AND lexeme_id = ?"
            params.append(lexeme_id)
        if severity is not None:
            query += " AND severity = ?"
            params.append(severity)
        if unresolved_only:
            query += " AND resolved = FALSE"

        query += " ORDER BY timestamp DESC"
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def resolve_disagreement(
        self,
        disagreement_id: int,
        resolution: str,
        resolved_value: int,
    ):
        """Mark a disagreement as resolved."""
        self.conn.execute(
            """
            UPDATE external_disagreements
            SET resolved = TRUE, resolution = ?, resolved_value = ?
            WHERE id = ?
            """,
            (resolution, resolved_value, disagreement_id)
        )
        self.conn.commit()

    def store_source_coverage(
        self,
        lexeme_id: int,
        source_name: str,
        primitives_matched: int,
        primitives_agreed: int,
    ):
        """Store external source coverage stats for a lexeme."""
        agreement_rate = primitives_agreed / max(primitives_matched, 1)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO external_source_coverage
            (lexeme_id, source_name, primitives_matched, primitives_agreed, agreement_rate)
            VALUES (?, ?, ?, ?, ?)
            """,
            (lexeme_id, source_name, primitives_matched, primitives_agreed, agreement_rate)
        )
        self.conn.commit()

    def get_disagreement_stats(self) -> Dict[str, Any]:
        """Get statistics about disagreements."""
        stats = {}

        # Total disagreements
        cursor = self.conn.execute(
            "SELECT COUNT(*) as count FROM external_disagreements"
        )
        stats["total"] = cursor.fetchone()["count"]

        # By severity
        cursor = self.conn.execute(
            "SELECT severity, COUNT(*) as count FROM external_disagreements GROUP BY severity"
        )
        stats["by_severity"] = {row["severity"]: row["count"] for row in cursor.fetchall()}

        # By source
        cursor = self.conn.execute(
            "SELECT external_source, COUNT(*) as count FROM external_disagreements GROUP BY external_source"
        )
        stats["by_source"] = {row["external_source"]: row["count"] for row in cursor.fetchall()}

        # Unresolved
        cursor = self.conn.execute(
            "SELECT COUNT(*) as count FROM external_disagreements WHERE resolved = FALSE"
        )
        stats["unresolved"] = cursor.fetchone()["count"]

        return stats
