#!/usr/bin/env python3
"""
Extend Database Schema for Audit System

This script adds the new tables required by the passive audit system:
- constraint_evidence: Stores evidence from each source
- aggregated_constraints: Stores aggregated constraint decisions
- constraint_review_queue: Queue for manual review items
- audit_log: Full audit trail with provenance
- audit_checkpoint: Resumable processing state
- audit_state: Per-word/primitive audit state

Run this once before starting the audit daemon.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from daemon.config import DB_PATH


def extend_schema(db_path: Path):
    """Add new tables for the audit system."""
    print(f"Extending schema for: {db_path}")

    conn = sqlite3.connect(str(db_path))

    # Table 1: Constraint evidence storage
    print("Creating constraint_evidence table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS constraint_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lexeme_id INTEGER NOT NULL,
            primitive TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_concept TEXT,
            value INTEGER NOT NULL,
            confidence REAL,
            constraint_type TEXT,
            evidence_strength REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_lexeme ON constraint_evidence(lexeme_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_primitive ON constraint_evidence(primitive)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_source ON constraint_evidence(source_name)")

    # Table 2: Aggregated constraints
    print("Creating aggregated_constraints table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS aggregated_constraints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lexeme_id INTEGER NOT NULL,
            primitive TEXT NOT NULL,
            final_value INTEGER NOT NULL,
            confidence REAL NOT NULL,
            status TEXT NOT NULL,
            supporting_sources TEXT,
            conflicting_sources TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE,
            UNIQUE(lexeme_id, primitive)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_constraints_lexeme ON aggregated_constraints(lexeme_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_constraints_status ON aggregated_constraints(status)")

    # Table 3: Review queue
    print("Creating constraint_review_queue table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS constraint_review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lexeme_id INTEGER NOT NULL,
            lemma TEXT NOT NULL,
            pos TEXT,
            primitive TEXT NOT NULL,
            current_value INTEGER,
            proposed_value INTEGER,
            nlp_constraints TEXT,
            model_votes TEXT,
            ollama_response TEXT,
            conflict_type TEXT,
            conflict_detail TEXT,
            confidence REAL,
            priority INTEGER DEFAULT 5,
            status TEXT DEFAULT 'pending',
            resolution TEXT,
            resolved_value INTEGER,
            reviewer TEXT,
            resolved_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_review_priority ON constraint_review_queue(priority, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_review_lexeme ON constraint_review_queue(lexeme_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_review_status ON constraint_review_queue(status)")

    # Table 4: Audit log
    print("Creating audit_log table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL,
            lemma TEXT NOT NULL,
            primitive TEXT NOT NULL,
            old_value INTEGER,
            new_value INTEGER,
            decision TEXT NOT NULL,
            confidence REAL,
            sources TEXT NOT NULL,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (word_id) REFERENCES lexemes(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_word ON audit_log(word_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_decision ON audit_log(decision)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_time ON audit_log(processed_at)")

    # Table 5: Audit checkpoint
    print("Creating audit_checkpoint table...")
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
            status TEXT DEFAULT 'initialized'
        )
    """)

    # Table 6: Audit state
    print("Creating audit_state table...")
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
            FOREIGN KEY (word_id) REFERENCES lexemes(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_state_status ON audit_state(audit_status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_state_word ON audit_state(word_id)")

    conn.commit()

    # Verify tables
    cursor = conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name LIKE '%audit%' OR name LIKE '%constraint%' OR name LIKE '%review%'
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\nCreated/verified tables: {tables}")

    conn.close()
    print("\nSchema extension complete!")


def main():
    """Main entry point."""
    extend_schema(DB_PATH)


if __name__ == "__main__":
    main()
