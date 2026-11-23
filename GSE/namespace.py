"""The project's identifier namespace and its pre-rename spelling.

Identifiers minted by this package (format, schema and policy versions such as
``GSE.lexicon-builder/1``, and provenance labels such as ``GSE.lexicon.pronouns``)
were spelled ``gse.`` until the 2026-11-23 rename. Builds, receipts and cached
model answers written before then keep that spelling as records.

Two rules keep those records usable without rewriting them:

- ``current_id`` reads: a stored identifier is compared in its current spelling.
- ``identity_form`` hashes: content identities (record ids, request and context
  digests) are computed over the original spelling, so the rename never changes
  what an existing identity refers to.

Writers emit only the current spelling. The closed-class source key
(``gse_closed_class``) and the ``gse:`` entry-id namespace are stored primary keys,
not dotted identifiers, and are outside both rules.
"""

from __future__ import annotations

from typing import Any

CURRENT = "GSE."
LEGACY = "gse."


def current_id(identifier: Any) -> Any:
    """Return a stored identifier in its current spelling; other values unchanged."""
    if isinstance(identifier, str) and identifier.startswith(LEGACY):
        return CURRENT + identifier[len(LEGACY) :]
    return identifier


def current_form(value: Any) -> Any:
    """Apply ``current_id`` to every string inside nested JSON-shaped data."""
    if isinstance(value, str):
        return current_id(value)
    if isinstance(value, dict):
        return {current_form(key): current_form(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(current_form(item) for item in value)
    return value


def identity_form(value: Any) -> Any:
    """Spell every namespaced string as before the rename, for content hashing."""
    if isinstance(value, str):
        return LEGACY + value[len(CURRENT) :] if value.startswith(CURRENT) else value
    if isinstance(value, dict):
        return {identity_form(key): identity_form(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(identity_form(item) for item in value)
    return value
