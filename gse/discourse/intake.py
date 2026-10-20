"""Source-unit normalization shared by document readers.

Offsets remain the source owner's concern. These functions never rewrite stored
source text; paragraph whitespace is collapsed only by ``document_sentences``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_PARAGRAPH_BOUNDARY = re.compile(r"(?:\r?\n)[ \t]*(?:\r?\n)(?:[ \t]*(?:\r?\n))*")


@dataclass(frozen=True)
class SourceSentence:
    """A complete sentence with an identity supplied by the source owner."""

    id: str
    text: str
    paragraph_id: str | None = None


def split_paragraphs(text: str) -> list[str]:
    """Return nonempty paragraphs; preserve their internal whitespace verbatim."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return [part.strip() for part in _PARAGRAPH_BOUNDARY.split(text) if part.strip()]


def split_sentences(text: str) -> list[str]:
    """Deterministic bounded-register split at whitespace following . ! or ?."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return [part.strip() for part in _SENTENCE_BOUNDARY.split(text.strip()) if part.strip()]


def document_sentences(text: str) -> list[SourceSentence]:
    """Segment paragraphs and wrapped prose once, retaining paragraph identities."""
    result = []
    for p, paragraph in enumerate(split_paragraphs(text)):
        for sentence in split_sentences(re.sub(r"\s+", " ", paragraph)):
            result.append(SourceSentence(f"s{len(result)}", sentence, f"p{p}"))
    return result


def source_sentences(sentences: Iterable) -> list[SourceSentence]:
    """Normalize supported public inputs and reject duplicate or malformed IDs.

    Strings receive deterministic positional IDs. A dict accepts ``id`` or
    ``source_sentence_id`` and ``text``. Explicit IDs are never renumbered.
    """
    result = []
    seen = set()
    for index, sentence in enumerate(sentences):
        if isinstance(sentence, SourceSentence):
            item = sentence
        elif isinstance(sentence, str):
            item = SourceSentence(f"s{index}", sentence)
        elif isinstance(sentence, dict):
            item = SourceSentence(
                sentence.get("id", sentence.get("source_sentence_id")),
                sentence.get("text"),
                sentence.get("paragraph_id"),
            )
        elif isinstance(sentence, tuple) and len(sentence) == 2:
            item = SourceSentence(sentence[0], sentence[1])
        else:
            raise TypeError("sentence must be text, SourceSentence, a pair, or a source record")
        if not isinstance(item.id, str) or not item.id or not isinstance(item.text, str):
            raise ValueError("source sentences require a nonempty string id and string text")
        if item.id in seen:
            raise ValueError(f"duplicate source sentence id: {item.id}")
        seen.add(item.id)
        result.append(item)
    return result
