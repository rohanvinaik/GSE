"""Independent SQLite snapshots with a copy-on-write path for rollback databases."""

import sqlite3
import subprocess
import sys
from contextlib import closing


def copy_database(source, target):
    """Copy an exact read snapshot into a private, initially absent path."""
    if target.exists():
        raise ValueError("SQLITE_SNAPSHOT_REQUIRES_NEW_PATH")
    with closing(sqlite3.connect(source.resolve(strict=True).as_uri() + "?mode=ro", uri=True)) as original:
        if sys.platform == "darwin" and original.execute("PRAGMA journal_mode").fetchone()[0] == "delete":
            original.execute("BEGIN")
            # In rollback mode this read pins the source pages under a shared
            # lock. A writer cannot start replacing them until the clone ends.
            original.execute("SELECT rootpage FROM sqlite_schema LIMIT 1").fetchone()
            if (
                not source.with_name(source.name + "-journal").exists()
                and not source.with_name(source.name + "-wal").exists()
            ):
                clone = subprocess.run(
                    ("/bin/cp", "-c", str(source), str(target)),
                    capture_output=True,
                    check=False,
                )
                if clone.returncode == 0:
                    return
                target.unlink(missing_ok=True)
        with closing(sqlite3.connect(target)) as copy:
            original.backup(copy)
