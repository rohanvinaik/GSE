"""Rohan Vinaik's personal dictionary (#60): his fields' formal terms and his own jargon, each with a dictionary
definition and a GSE word-scale decomposition.

The decompositions are written by hand, never by the old definitional decomposer, whose genus chain collapses
meaning (it built layer 2, where 25,735 words read SOMETHING alone). Two members draft each decomposition
independently; only the primes they agree on enter, and every other prime goes to the lead. The hypervector of an
entry is made by the live encoder's own word path, so a word read from this dictionary and the same word read by the
encoder are the same vector.

The typed runtime store below protects spellings independently. Its entries do
not yet assert curated decompositions or publish vectors; learned/draft
definitions retain their own provenance and semantic review remains pending.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Tuple

from gse.curation.schema import ALL_PRIMITIVES
from gse.primitives_v2 import get_canonical_pole

_PRIMES = frozenset(ALL_PRIMITIVES)
_HIERARCHY = frozenset({"HIER_PLUS", "HIER_MINUS"})  # degree is sentence-scale, never a word's identity (FA L741)
_GENERIC = frozenset({"SOMETHING", "SOMEONE", "DO", "BE", "EXIST"})
MIN_PRIMES, MAX_PRIMES = 2, 7


def check_decomposition(signed: Dict[str, int]) -> Tuple[Dict[str, int], List[str]]:
    """One drafted decomposition in canonical form, and every way it breaks GSE's word-scale rules.

    Each prime is mapped to its canonical pole (BAD +1 is GOOD -1, after gse.primitives_v2.get_canonical_pole). The
    named problems: ``UNKNOWN_PRIME:<p>``, ``HIERARCHY_MARKER:<p>``, ``NOT_TERNARY:<p>``,
    ``CONFLICTING_POLES:<pole>`` (both poles, or one pole with both signs), ``TOO_FEW``, ``TOO_MANY`` and
    ``GENERIC_ONLY`` (nothing beyond SOMETHING, SOMEONE, DO, BE, EXIST). A rejected prime stays out of the canonical
    form; an empty problem list means the decomposition may enter.
    """
    canon: Dict[str, int] = {}
    problems: List[str] = []
    for prime, value in signed.items():
        if prime in _HIERARCHY:
            problems.append(f"HIERARCHY_MARKER:{prime}")
        elif prime not in _PRIMES:
            problems.append(f"UNKNOWN_PRIME:{prime}")
        elif type(value) is not int or value not in (1, -1):
            problems.append(f"NOT_TERNARY:{prime}")
        else:
            pole, sign = get_canonical_pole(prime)
            if canon.get(pole, sign * value) != sign * value:
                problems.append(f"CONFLICTING_POLES:{pole}")
                del canon[pole]
            else:
                canon[pole] = sign * value
    if len(canon) < MIN_PRIMES:
        problems.append("TOO_FEW")
    if len(canon) > MAX_PRIMES:
        problems.append("TOO_MANY")
    if canon and set(canon) <= _GENERIC:
        problems.append("GENERIC_ONLY")
    return canon, problems


def concur(first: Dict[str, int], second: Dict[str, int]) -> Dict[str, str]:
    """How two independently drafted canonical decompositions relate, prime by prime.

    ``AGREED`` (both name it, same sign), ``SIGN_CONFLICT`` (both name it, opposite signs), ``ONLY_FIRST`` or
    ``ONLY_SECOND``. Only AGREED primes enter the dictionary; every other code goes to the lead.
    """
    out: Dict[str, str] = {}
    for prime in sorted(set(first) | set(second)):
        if prime in first and prime in second:
            out[prime] = "AGREED" if first[prime] == second[prime] else "SIGN_CONFLICT"
        else:
            out[prime] = "ONLY_FIRST" if prime in first else "ONLY_SECOND"
    return out


def validated_concurrence(first: Dict[str, int], second: Dict[str, int]) -> dict[str, Any]:
    """Validate both independent drafts AND their agreed intersection before admission.

    Disagreement remains inspectable. A valid intersection is a candidate for
    review, never an automatic semantic-lexicon write.
    """
    left, left_problems = check_decomposition(first)
    right, right_problems = check_decomposition(second)
    decisions = concur(left, right)
    agreed = {prime: left[prime] for prime, code in decisions.items() if code == "AGREED"}
    canonical, agreed_problems = check_decomposition(agreed)
    return {
        "state": "review_required" if not (left_problems or right_problems or agreed_problems) else "invalid",
        "agreed": canonical,
        "decisions": decisions,
        "problems": {"first": left_problems, "second": right_problems, "agreed": agreed_problems},
    }


SCHEMA = "gse.protected-dictionary/1"
DEFAULT_PATH = Path(__file__).resolve().parents[1] / "nlp" / "data" / "personal_dictionary.json"


@dataclass(frozen=True)
class DictionaryEntry:
    """Spelling protection is independent of semantic validation."""

    surface: str
    kind: Literal["term", "name"] = "term"
    aliases: tuple[str, ...] = ()
    definition: str | None = None
    source: Literal["confirmed", "draft", "learned"] = "learned"
    review_status: Literal["pending", "reviewed", "validated", "rejected"] = "pending"
    semantic_status: str = "pending"
    definition_source: Literal["confirmed", "draft", "learned"] | None = None


class DictionaryError(ValueError):
    """A named refusal that leaves the persisted dictionary unchanged."""


_CACHE: dict[str, tuple[tuple[int, int, int], tuple[DictionaryEntry, ...], str]] = {}


def _surface_valid(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value == value.strip()
        and len(value) >= 2
        and any(ch.isalpha() for ch in value)
        and all(ch.isalpha() or ch in " -'’" for ch in value)
        and "  " not in value
    )


def _entry(raw: dict[str, Any] | DictionaryEntry) -> DictionaryEntry:
    raw = asdict(raw) if isinstance(raw, DictionaryEntry) else raw
    if not isinstance(raw, dict):
        raise DictionaryError("malformed_entry")
    fields = set(DictionaryEntry.__dataclass_fields__)
    if set(raw) - fields or not _surface_valid(raw.get("surface")):
        raise DictionaryError("malformed_entry")
    aliases = raw.get("aliases", ())
    if not isinstance(aliases, (list, tuple)) or any(not _surface_valid(alias) for alias in aliases):
        raise DictionaryError("malformed_alias")
    if raw.get("kind", "term") not in ("term", "name") or raw.get("source", "learned") not in (
        "confirmed",
        "draft",
        "learned",
    ):
        raise DictionaryError("malformed_entry")
    if raw.get("review_status", "pending") not in ("pending", "reviewed", "validated", "rejected"):
        raise DictionaryError("malformed_review_status")
    if raw.get("semantic_status", "pending") != "pending":
        raise DictionaryError("semantic_validation_requires_curation")
    definition = raw.get("definition")
    if definition is not None and (not isinstance(definition, str) or not definition.strip()):
        raise DictionaryError("malformed_definition")
    definition_source = raw.get("definition_source") or (raw.get("source", "learned") if definition else None)
    if definition_source not in (None, "confirmed", "draft", "learned") or (
        definition is None and definition_source is not None
    ):
        raise DictionaryError("malformed_definition_source")
    unique = {alias.casefold(): alias for alias in aliases if alias.casefold() != raw["surface"].casefold()}
    return DictionaryEntry(
        surface=raw["surface"],
        kind=raw.get("kind", "term"),
        aliases=tuple(unique[key] for key in sorted(unique)),
        definition=definition,
        source=raw.get("source", "learned"),
        review_status=raw.get("review_status", "pending"),
        definition_source=definition_source,
    )


def _load(path: Path) -> tuple[tuple[DictionaryEntry, ...], str]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return (), hashlib.sha256(b"").hexdigest()
    signature = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
    cached = _CACHE.get(str(path))
    if cached is not None and cached[0] == signature:
        return cached[1], cached[2]
    try:
        raw_bytes = path.read_bytes()
        document = json.loads(raw_bytes)
        if (
            not isinstance(document, dict)
            or document.get("schema") != SCHEMA
            or not isinstance(document.get("entries"), list)
        ):
            raise DictionaryError("malformed_store")
        records = tuple(_entry(raw) for raw in document["entries"])
        _validate_unique(records)
    except (json.JSONDecodeError, UnicodeError, TypeError) as exc:
        raise DictionaryError("malformed_store") from exc
    digest = hashlib.sha256(raw_bytes).hexdigest()
    _CACHE[str(path)] = (signature, records, digest)
    return records, digest


def _validate_unique(records: tuple[DictionaryEntry, ...]) -> None:
    seen: set[str] = set()
    for entry in records:
        for spelling in (entry.surface, *entry.aliases):
            key = spelling.casefold()
            if key in seen:
                raise DictionaryError("duplicate_spelling")
            seen.add(key)


def entries(path: str | Path | None = None) -> tuple[DictionaryEntry, ...]:
    """Read validated entries; malformed stores raise rather than masquerade as empty."""
    return _load(Path(path or DEFAULT_PATH).resolve())[0]


def identity(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path or DEFAULT_PATH).resolve()
    try:
        records, digest = _load(path)
        return {
            "schema": SCHEMA,
            "path": str(path),
            "sha256": digest,
            "state": "read" if path.exists() else "absent",
            "n": len(records),
        }
    except (DictionaryError, OSError) as exc:
        return {"schema": SCHEMA, "path": str(path), "sha256": None, "state": "unread", "reason": str(exc)}


def membership(surface: str, path: str | Path | None = None) -> dict[str, Any]:
    """Return a protected term/name/alias without certifying its semantics."""
    try:
        for entry in entries(path):
            if surface.casefold() in {value.casefold() for value in (entry.surface, *entry.aliases)}:
                return {"state": "member", "entry": asdict(entry)}
        return {"state": "absent", "entry": None}
    except (DictionaryError, OSError) as exc:
        return {"state": "unread", "entry": None, "reason": str(exc)}


def learn(
    raw: str | dict[str, Any] | DictionaryEntry,
    *,
    path: str | Path | None = None,
    drafts: tuple[dict[str, int], dict[str, int]] | None = None,
) -> dict[str, Any]:
    """Atomically merge one validated entry. Confirmed definitions win conflicts.

    Casefolded display surface identifies an entry. Aliases are unioned; an alias
    already owned by a different entry is refused. A confirmed entry keeps its
    definition, source, kind and review status. Learning never writes primitives.
    """
    path = Path(path or DEFAULT_PATH).resolve()
    try:
        curation = None
        if drafts is not None:
            if (
                not isinstance(drafts, (list, tuple))
                or len(drafts) != 2
                or any(not isinstance(draft, dict) for draft in drafts)
            ):
                raise DictionaryError("malformed_decomposition_drafts")
            curation = validated_concurrence(drafts[0], drafts[1])
            if curation["state"] == "invalid":
                return {"ok": False, "code": "invalid_decomposition_drafts", "curation": curation}
        incoming = _entry({"surface": raw} if isinstance(raw, str) else raw)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.with_suffix(path.suffix + ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            records, _ = _load(path)
            existing = next(
                (record for record in records if record.surface.casefold() == incoming.surface.casefold()), None
            )
            updated = incoming
            if existing is not None:
                if existing.kind != incoming.kind:
                    raise DictionaryError("kind_conflict")
                priority = {"learned": 0, "draft": 1, "confirmed": 2}
                winner = existing if priority[existing.source] >= priority[incoming.source] else incoming
                aliases = {alias.casefold(): alias for alias in (*incoming.aliases, *existing.aliases)}
                defined = [record for record in (existing, incoming) if record.definition is not None]
                definition_owner = (
                    max(defined, key=lambda record: priority[record.definition_source or record.source])
                    if defined
                    else None
                )
                definition = definition_owner.definition if definition_owner else None
                updated = DictionaryEntry(
                    winner.surface,
                    winner.kind,
                    tuple(aliases[key] for key in sorted(aliases)),
                    definition,
                    winner.source,
                    winner.review_status,
                    definition_source=definition_owner.definition_source if definition_owner else None,
                )
            merged = tuple(
                sorted(
                    (record for record in records if record is not existing),
                    key=lambda record: record.surface.casefold(),
                )
            ) + (updated,)
            merged = tuple(sorted(merged, key=lambda record: record.surface.casefold()))
            _validate_unique(merged)
            if existing == updated:
                return {
                    "ok": True,
                    "code": "already_known",
                    "already_known": True,
                    "word": updated.surface,
                    "entry": asdict(updated),
                    "dictionary": identity(path),
                    "curation": curation,
                }
            payload = (
                json.dumps(
                    {"schema": SCHEMA, "entries": [asdict(record) for record in merged]},
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8")
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".dictionary-", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            _CACHE.pop(str(path), None)
        return {
            "ok": True,
            "code": "learned" if existing is None else "merged",
            "learned": True,
            "word": updated.surface,
            "entry": asdict(updated),
            "dictionary": identity(path),
            "curation": curation,
        }
    except (DictionaryError, OSError) as exc:
        return {
            "ok": False,
            "code": str(exc) if isinstance(exc, DictionaryError) else "store_unread",
            "error": str(exc),
        }
