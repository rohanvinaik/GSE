"""Select the active lexical resource without creating or modifying databases.

Activation is explicit: ``data/lexicon_active.json`` names a validated versioned
build. The former dictionary remains an archive and a transition fallback only
while that pointer is absent. An invalid activation never silently selects it.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from functools import lru_cache
from pathlib import Path

from GSE.namespace import current_id

DATA = Path(__file__).resolve().parents[1] / "data"
ACTIVE_POINTER = DATA / "lexicon_active.json"
ARCHIVED_LEXICON = DATA / "lexicon_clean.db"
POINTER_FORMAT = "GSE.active-lexicon/1"


def _signature(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size, stat.st_ino


@lru_cache(maxsize=16)
def _pointer_target(path: Path, signature: tuple[int, int, int]) -> Path:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError("INVALID_ACTIVE_LEXICON") from error
    if (
        not isinstance(payload, dict)
        or set(payload) != {"format", "path"}
        or current_id(payload["format"]) != POINTER_FORMAT
        or not isinstance(payload["path"], str)
        or not payload["path"].strip()
    ):
        raise ValueError("INVALID_ACTIVE_LEXICON")
    target = Path(payload["path"]).expanduser()
    return (target if target.is_absolute() else path.parent / target).resolve()


@lru_cache(maxsize=16)
def _validate_active(path: Path, signature: tuple[int, int, int]) -> None:
    from GSE.curation.lexicon_builder.storage import VERSION

    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
            row = conn.execute("SELECT value FROM builder_metadata WHERE key='format'").fetchone()
            if row is None or current_id(json.loads(row[0])) != VERSION:
                raise ValueError("ACTIVE_LEXICON_NOT_VERSIONED")
    except (sqlite3.Error, TypeError, ValueError) as error:
        raise ValueError("ACTIVE_LEXICON_NOT_VERSIONED") from error


def resolve_lexicon_path(db_path: str | Path | None = None, *, pointer_path: str | Path | None = None) -> Path:
    """Resolve an explicit resource or the activated default at call time.

    Relative pointer targets are relative to the pointer file, never the process
    working directory. Explicit paths retain their usual caller-relative meaning
    and bypass activation, including intentional access to archived resources.
    This reader validates format; the build/promotion operation owns validation
    of the lexical contents before writing the pointer.
    """
    if db_path is not None:
        if not isinstance(db_path, (str, Path)) or not str(db_path).strip():
            raise ValueError("INVALID_LEXICON_PATH")
        return Path(db_path).expanduser()
    pointer = Path(pointer_path) if pointer_path is not None else ACTIVE_POINTER
    pointer = pointer.resolve()
    try:
        signature = _signature(pointer)
    except FileNotFoundError:
        archive = pointer.parent / "lexicon_clean.db" if pointer_path is not None else ARCHIVED_LEXICON
        return archive.resolve()
    except OSError as error:
        raise ValueError("INVALID_ACTIVE_LEXICON") from error
    target = _pointer_target(pointer, signature)
    try:
        if not target.is_file():
            raise FileNotFoundError(f"ACTIVE_LEXICON_UNAVAILABLE: {target}")
        target_signature = _signature(target)
    except OSError as error:
        raise FileNotFoundError(f"ACTIVE_LEXICON_UNAVAILABLE: {target}") from error
    _validate_active(target, target_signature)
    return target
