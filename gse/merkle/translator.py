#!/usr/bin/env python3
"""
SQLite ↔ Merkle Tree Translator for GSE

Provides bidirectional conversion between:
- SQLite lexicon database (flat table storage)
- Merkle tree structure (hierarchical with hashes)

Features:
- Import existing SQLite lexicon into Merkle tree
- Export Merkle tree to SQLite for persistence
- Incremental sync with change detection
- Schema migration support
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import numpy as np

from gse.merkle.nodes import LexemeNode
from gse.merkle.tree import MerkleLexiconTree

# =============================================================================
# SQLITE SCHEMA
# =============================================================================

LEXICON_SCHEMA = """
-- Main lexeme table
CREATE TABLE IF NOT EXISTS lexemes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma TEXT NOT NULL,
    pos TEXT NOT NULL,
    sense_id TEXT NOT NULL DEFAULT '01',
    gloss TEXT,
    source TEXT DEFAULT 'manual',
    confidence REAL DEFAULT 1.0,
    frequency REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_hash TEXT,
    UNIQUE(lemma, pos, sense_id)
);

-- Decomposition table (normalized)
CREATE TABLE IF NOT EXISTS decompositions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lexeme_id INTEGER NOT NULL,
    primitive TEXT NOT NULL,
    role TEXT NOT NULL,
    polarity INTEGER NOT NULL DEFAULT 1,
    position INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE
);

-- Vector storage (sparse format)
CREATE TABLE IF NOT EXISTS vectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lexeme_id INTEGER NOT NULL UNIQUE,
    positive_indices BLOB,
    negative_indices BLOB,
    FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE
);

-- Metadata table
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_lexemes_lemma ON lexemes(lemma);
CREATE INDEX IF NOT EXISTS idx_lexemes_pos ON lexemes(pos);
CREATE INDEX IF NOT EXISTS idx_lexemes_hash ON lexemes(content_hash);
CREATE INDEX IF NOT EXISTS idx_decompositions_lexeme ON decompositions(lexeme_id);
CREATE INDEX IF NOT EXISTS idx_decompositions_primitive ON decompositions(primitive);
"""


# =============================================================================
# TRANSLATOR
# =============================================================================

class SQLiteMerkleTranslator:
    """
    Translates between SQLite database and Merkle tree.

    Usage:
        translator = SQLiteMerkleTranslator("lexicon.db")
        tree = translator.import_to_tree()
        # ... modify tree ...
        translator.export_from_tree(tree)
    """

    def __init__(self, db_path: str):
        """
        Initialize translator with database path.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _ensure_schema(self):
        """Create database and schema if needed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(LEXICON_SCHEMA)
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # IMPORT: SQLite → Merkle Tree
    # =========================================================================

    def import_to_tree(self, tree: Optional[MerkleLexiconTree] = None) -> MerkleLexiconTree:
        """
        Import all lexemes from SQLite into a Merkle tree.

        Args:
            tree: Optional existing tree to add to (creates new if None)

        Returns:
            MerkleLexiconTree with imported lexemes
        """
        if tree is None:
            tree = MerkleLexiconTree()

        with self._get_connection() as conn:
            # Get all lexemes
            cursor = conn.execute("""
                SELECT id, lemma, pos, sense_id, gloss, source, confidence, frequency
                FROM lexemes
            """)

            for row in cursor:
                lexeme = self._row_to_lexeme(conn, row)
                tree.add_lexeme(lexeme, recompute=False)

        # Recompute all hashes at once
        tree._recompute_all_hashes()

        return tree

    def import_incremental(
        self,
        tree: MerkleLexiconTree,
        since_hash: Optional[str] = None,
    ) -> Tuple[int, int, int]:
        """
        Incrementally import changes from SQLite.

        Args:
            tree: Existing tree to update
            since_hash: Only import lexemes changed since this hash

        Returns:
            (added, modified, removed) counts
        """
        added = 0
        modified = 0
        removed = 0

        with self._get_connection() as conn:
            # Get current DB hashes
            db_hashes = {}
            cursor = conn.execute("""
                SELECT lemma, pos, sense_id, content_hash
                FROM lexemes
            """)
            for row in cursor:
                key = f"{row['lemma']}_{row['pos']}_{row['sense_id']}"
                db_hashes[key] = row['content_hash']

            # Find changes
            tree_keys = set(tree.lexemes.keys())
            db_keys = set(db_hashes.keys())

            # New in DB
            for key in db_keys - tree_keys:
                lexeme = self._load_lexeme_by_key(conn, key)
                if lexeme:
                    tree.add_lexeme(lexeme, recompute=False)
                    added += 1

            # Removed from DB
            for key in tree_keys - db_keys:
                tree.remove_lexeme(key, recompute=False)
                removed += 1

            # Modified
            for key in tree_keys & db_keys:
                if tree.lexemes[key].content_hash != db_hashes[key]:
                    lexeme = self._load_lexeme_by_key(conn, key)
                    if lexeme:
                        tree.update_lexeme(lexeme, recompute=False)
                        modified += 1

        tree._recompute_all_hashes()
        return added, modified, removed

    def _row_to_lexeme(self, conn: sqlite3.Connection, row: sqlite3.Row) -> LexemeNode:
        """Convert database row to LexemeNode."""
        lexeme_id = row['id']

        # Get decomposition
        decomp_cursor = conn.execute("""
            SELECT primitive, role, polarity
            FROM decompositions
            WHERE lexeme_id = ?
            ORDER BY position
        """, (lexeme_id,))
        decomposition = [(r['primitive'], r['role'], r['polarity']) for r in decomp_cursor]

        # Get vectors
        vec_cursor = conn.execute("""
            SELECT positive_indices, negative_indices
            FROM vectors
            WHERE lexeme_id = ?
        """, (lexeme_id,))
        vec_row = vec_cursor.fetchone()

        if vec_row and vec_row['positive_indices']:
            positive = np.frombuffer(vec_row['positive_indices'], dtype=np.uint16)
            negative = np.frombuffer(vec_row['negative_indices'], dtype=np.uint16) if vec_row['negative_indices'] else np.array([], dtype=np.uint16)
        else:
            positive = np.array([], dtype=np.uint16)
            negative = np.array([], dtype=np.uint16)

        node = LexemeNode(
            node_id=f"{row['lemma']}_{row['pos']}_{row['sense_id']}",
            lemma=row['lemma'],
            pos=row['pos'],
            sense_id=row['sense_id'],
            gloss=row['gloss'] or "",
            decomposition=decomposition,
            vector_positive=positive,
            vector_negative=negative,
            source=row['source'] or "manual",
            confidence=row['confidence'] or 1.0,
            frequency=row['frequency'] or 1.0,
        )

        # Compute hash
        node.compute_content_hash()
        return node

    def _load_lexeme_by_key(self, conn: sqlite3.Connection, key: str) -> Optional[LexemeNode]:
        """Load a single lexeme by its key."""
        parts = key.rsplit('_', 2)
        if len(parts) != 3:
            return None

        lemma, pos, sense_id = parts
        cursor = conn.execute("""
            SELECT id, lemma, pos, sense_id, gloss, source, confidence, frequency
            FROM lexemes
            WHERE lemma = ? AND pos = ? AND sense_id = ?
        """, (lemma, pos, sense_id))

        row = cursor.fetchone()
        if row:
            return self._row_to_lexeme(conn, row)
        return None

    # =========================================================================
    # EXPORT: Merkle Tree → SQLite
    # =========================================================================

    def export_from_tree(self, tree: MerkleLexiconTree, replace: bool = False):
        """
        Export Merkle tree to SQLite database.

        Args:
            tree: Tree to export
            replace: If True, replace existing entries; if False, skip existing
        """
        with self._get_connection() as conn:
            for lexeme in tree.iter_lexemes():
                self._save_lexeme(conn, lexeme, replace)

            # Update metadata
            conn.execute("""
                INSERT OR REPLACE INTO metadata (key, value)
                VALUES ('root_hash', ?)
            """, (tree.get_root_hash(),))

            conn.execute("""
                INSERT OR REPLACE INTO metadata (key, value)
                VALUES ('total_lexemes', ?)
            """, (str(len(tree.lexemes)),))

            conn.commit()

    def export_incremental(
        self,
        tree: MerkleLexiconTree,
        changes: List[str],  # List of changed lexeme keys
    ):
        """
        Export only changed lexemes to SQLite.

        Args:
            tree: Tree with changes
            changes: List of lexeme keys that changed
        """
        with self._get_connection() as conn:
            for key in changes:
                if key in tree.lexemes:
                    self._save_lexeme(conn, tree.lexemes[key], replace=True)
                else:
                    # Deleted
                    self._delete_lexeme(conn, key)

            # Update metadata
            conn.execute("""
                INSERT OR REPLACE INTO metadata (key, value)
                VALUES ('root_hash', ?)
            """, (tree.get_root_hash(),))

            conn.commit()

    def _save_lexeme(self, conn: sqlite3.Connection, lexeme: LexemeNode, replace: bool):
        """Save a single lexeme to database."""
        try:
            if replace:
                # Try to get existing ID
                cursor = conn.execute("""
                    SELECT id FROM lexemes
                    WHERE lemma = ? AND pos = ? AND sense_id = ?
                """, (lexeme.lemma, lexeme.pos, lexeme.sense_id))
                row = cursor.fetchone()

                if row:
                    lexeme_id = row['id']
                    # Update existing
                    conn.execute("""
                        UPDATE lexemes SET
                            gloss = ?, source = ?, confidence = ?, frequency = ?,
                            content_hash = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (lexeme.gloss, lexeme.source, lexeme.confidence,
                          lexeme.frequency, lexeme.content_hash, lexeme_id))

                    # Delete old decomposition
                    conn.execute("DELETE FROM decompositions WHERE lexeme_id = ?", (lexeme_id,))
                    conn.execute("DELETE FROM vectors WHERE lexeme_id = ?", (lexeme_id,))
                else:
                    lexeme_id = self._insert_lexeme_main(conn, lexeme)
            else:
                lexeme_id = self._insert_lexeme_main(conn, lexeme)

            # Insert decomposition
            for i, (prim, role, pol) in enumerate(lexeme.decomposition):
                conn.execute("""
                    INSERT INTO decompositions (lexeme_id, primitive, role, polarity, position)
                    VALUES (?, ?, ?, ?, ?)
                """, (lexeme_id, prim, role, pol, i))

            # Insert vectors
            conn.execute("""
                INSERT OR REPLACE INTO vectors (lexeme_id, positive_indices, negative_indices)
                VALUES (?, ?, ?)
            """, (
                lexeme_id,
                lexeme.vector_positive.tobytes(),
                lexeme.vector_negative.tobytes(),
            ))

        except sqlite3.IntegrityError:
            if not replace:
                pass  # Skip existing
            else:
                raise

    def _insert_lexeme_main(self, conn: sqlite3.Connection, lexeme: LexemeNode) -> int:
        """Insert main lexeme record and return ID."""
        cursor = conn.execute("""
            INSERT INTO lexemes (lemma, pos, sense_id, gloss, source, confidence, frequency, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lexeme.lemma, lexeme.pos, lexeme.sense_id, lexeme.gloss,
            lexeme.source, lexeme.confidence, lexeme.frequency, lexeme.content_hash
        ))
        return cursor.lastrowid

    def _delete_lexeme(self, conn: sqlite3.Connection, key: str):
        """Delete a lexeme by key."""
        parts = key.rsplit('_', 2)
        if len(parts) != 3:
            return

        lemma, pos, sense_id = parts
        conn.execute("""
            DELETE FROM lexemes
            WHERE lemma = ? AND pos = ? AND sense_id = ?
        """, (lemma, pos, sense_id))

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def get_metadata(self) -> Dict[str, str]:
        """Get database metadata."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT key, value FROM metadata")
            return {row['key']: row['value'] for row in cursor}

    def get_statistics(self) -> Dict[str, int]:
        """Get database statistics."""
        with self._get_connection() as conn:
            stats = {}

            cursor = conn.execute("SELECT COUNT(*) as c FROM lexemes")
            stats['total_lexemes'] = cursor.fetchone()['c']

            cursor = conn.execute("SELECT COUNT(DISTINCT primitive) as c FROM decompositions")
            stats['unique_primitives'] = cursor.fetchone()['c']

            cursor = conn.execute("SELECT COUNT(*) as c FROM vectors WHERE positive_indices IS NOT NULL")
            stats['vectorized_lexemes'] = cursor.fetchone()['c']

            cursor = conn.execute("SELECT pos, COUNT(*) as c FROM lexemes GROUP BY pos")
            stats['by_pos'] = {row['pos']: row['c'] for row in cursor}

            return stats

    def iter_lexemes(self, batch_size: int = 1000) -> Iterator[LexemeNode]:
        """
        Iterate over all lexemes in batches.

        Args:
            batch_size: Number of lexemes per batch

        Yields:
            LexemeNode objects
        """
        with self._get_connection() as conn:
            offset = 0
            while True:
                cursor = conn.execute("""
                    SELECT id, lemma, pos, sense_id, gloss, source, confidence, frequency
                    FROM lexemes
                    ORDER BY id
                    LIMIT ? OFFSET ?
                """, (batch_size, offset))

                rows = cursor.fetchall()
                if not rows:
                    break

                for row in rows:
                    yield self._row_to_lexeme(conn, row)

                offset += batch_size


# =============================================================================
# MIGRATION UTILITIES
# =============================================================================

def migrate_legacy_lexicon(
    legacy_path: str,
    output_path: str,
    tree: Optional[MerkleLexiconTree] = None,
) -> Tuple[MerkleLexiconTree, SQLiteMerkleTranslator]:
    """
    Migrate a legacy JSON lexicon to new SQLite + Merkle format.

    Args:
        legacy_path: Path to legacy JSON lexicon
        output_path: Path for new SQLite database
        tree: Optional existing tree

    Returns:
        (tree, translator) tuple
    """
    from gse.vectors_v2 import compose_decomposition, create_basis

    basis = create_basis()
    translator = SQLiteMerkleTranslator(output_path)

    if tree is None:
        tree = MerkleLexiconTree()

    # Load legacy JSON
    with open(legacy_path) as f:
        legacy_data = json.load(f)

    # Convert entries
    for entry in legacy_data.get('lexemes', []):
        # Handle various legacy formats
        decomp = []
        for item in entry.get('decomposition', []):
            if isinstance(item, dict):
                decomp.append((item['primitive'], item.get('role', 'attribute'), item.get('polarity', 1)))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                decomp.append((item[0], item[1], item[2] if len(item) > 2 else 1))

        # Generate vector if not present
        if decomp:
            vec = compose_decomposition(basis, decomp)
            positive = vec.positive_indices
            negative = vec.negative_indices
        else:
            positive = np.array([], dtype=np.uint16)
            negative = np.array([], dtype=np.uint16)

        lexeme = LexemeNode(
            node_id=f"{entry['lemma']}_{entry['pos']}_{entry.get('sense_id', '01')}",
            lemma=entry['lemma'],
            pos=entry['pos'],
            sense_id=entry.get('sense_id', '01'),
            gloss=entry.get('gloss', ''),
            decomposition=decomp,
            vector_positive=positive,
            vector_negative=negative,
            source=entry.get('source', 'legacy'),
            confidence=entry.get('confidence', 1.0),
        )
        tree.add_lexeme(lexeme, recompute=False)

    tree._recompute_all_hashes()

    # Export to SQLite
    translator.export_from_tree(tree)

    return tree, translator


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    import os
    import tempfile

    print("SQLiteMerkleTranslator Tests")
    print("=" * 50)

    # Create temp database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_lexicon.db")

        # Create translator
        translator = SQLiteMerkleTranslator(db_path)
        print(f"✓ Created translator with database at {db_path}")

        # Create tree with sample data
        from gse.vectors_v2 import compose_decomposition, create_basis

        tree = MerkleLexiconTree()
        basis = create_basis()

        test_lexemes = [
            ("happy", "adj", "01", "feeling joy", [("FEEL", "experiencer", 1), ("GOOD", "attribute", 1)]),
            ("sad", "adj", "01", "feeling sorrow", [("FEEL", "experiencer", 1), ("BAD", "attribute", 1)]),
            ("run", "v", "01", "move fast", [("MOVE", "action", 1), ("SOMEONE", "agent", 1)]),
        ]

        for lemma, pos, sense, gloss, decomp in test_lexemes:
            vec = compose_decomposition(basis, decomp)
            lexeme = LexemeNode(
                node_id=f"{lemma}_{pos}_{sense}",
                lemma=lemma,
                pos=pos,
                sense_id=sense,
                gloss=gloss,
                decomposition=decomp,
                vector_positive=vec.positive_indices,
                vector_negative=vec.negative_indices,
            )
            tree.add_lexeme(lexeme)

        print(f"✓ Created tree with {len(tree.lexemes)} lexemes")
        original_hash = tree.get_root_hash()

        # Export to SQLite
        translator.export_from_tree(tree)
        print("✓ Exported tree to SQLite")

        # Get statistics
        stats = translator.get_statistics()
        print(f"✓ DB statistics: {stats['total_lexemes']} lexemes")

        # Import back to new tree
        new_tree = translator.import_to_tree()
        print(f"✓ Imported to new tree: {len(new_tree.lexemes)} lexemes")

        # Verify hashes match
        new_hash = new_tree.get_root_hash()
        assert original_hash == new_hash, f"Hash mismatch: {original_hash[:16]} vs {new_hash[:16]}"
        print(f"✓ Root hash verified: {original_hash[:16]}...")

        # Test incremental sync
        # Add new lexeme to tree
        new_vec = compose_decomposition(basis, [("THINK", "action", 1)])
        new_lexeme = LexemeNode(
            node_id="think_v_01",
            lemma="think",
            pos="v",
            sense_id="01",
            gloss="use mind",
            decomposition=[("THINK", "action", 1)],
            vector_positive=new_vec.positive_indices,
            vector_negative=new_vec.negative_indices,
        )
        new_tree.add_lexeme(new_lexeme)
        print("✓ Added new lexeme to tree")

        # Export changes
        translator.export_from_tree(new_tree, replace=True)
        stats2 = translator.get_statistics()
        assert stats2['total_lexemes'] == 4, f"Expected 4 lexemes, got {stats2['total_lexemes']}"
        print(f"✓ Incremental export: now {stats2['total_lexemes']} lexemes")

        # Test import incremental
        tree3 = MerkleLexiconTree()
        tree3 = translator.import_to_tree(tree3)
        assert len(tree3.lexemes) == 4
        print(f"✓ Full re-import: {len(tree3.lexemes)} lexemes")

        # Verify metadata
        meta = translator.get_metadata()
        assert 'root_hash' in meta
        print(f"✓ Metadata preserved: root_hash={meta['root_hash'][:16]}...")

    print("\n" + "=" * 50)
    print("All SQLiteMerkleTranslator tests passed!")
