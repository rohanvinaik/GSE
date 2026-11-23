"""Recognize the NSM duration forms at a clause or temporal-link boundary."""

from dataclasses import dataclass
from typing import Literal, Sequence

from gse.api.trace import TokenTrace

Extent = Literal["unspecified", "short", "long"]
Relation = Literal["during", "before", "after"]


@dataclass(frozen=True)
class Duration:
    extent: Extent
    relation: Relation

    def __post_init__(self):
        if self.extent not in ("unspecified", "short", "long") or self.relation not in ("during", "before", "after"):
            raise ValueError("INVALID_DURATION")


_FORMS: dict[tuple[str, ...], Extent] = {
    ("some", "time"): "unspecified",
    ("a", "short", "time"): "short",
    ("a", "long", "time"): "long",
}


def _extent(tokens: Sequence[TokenTrace]) -> Extent | None:
    if not tokens or tokens[-1].pos != "NOUN" or any(t.is_operator for t in tokens):
        return None
    if any(right.position != left.position + 1 for left, right in zip(tokens, tokens[1:])):
        return None
    return _FORMS.get(tuple(t.lemma for t in tokens))


def split_duration(tokens: Sequence[TokenTrace]) -> tuple[Sequence[TokenTrace], Duration | None]:
    """Detach a clear fronted or trailing event adjunct, retaining source positions."""
    for width in (2, 3):
        if len(tokens) > width + 2 and tokens[0].lemma == "for" and tokens[0].pos == "ADP":
            end = width + 1
            extent = _extent(tokens[1:end])
            if extent is not None and tokens[end].token == "," and tokens[end].position == tokens[0].position + end:
                return tokens[end + 1 :], Duration(extent, "during")

    end = len(tokens)
    while end and tokens[end - 1].token in (".", "!", "?"):
        end -= 1
    for width in (2, 3):
        start = end - width - 1
        if start < 1 or tokens[start].lemma != "for" or tokens[start].pos != "ADP":
            continue
        extent = _extent(tokens[start + 1 : end])
        previous = tokens[start - 1]
        if extent is None or tokens[start + 1].position != tokens[start].position + 1:
            continue
        if previous.position != tokens[start].position - 1:
            continue
        # A nominal immediately before the PP may own it. A bare pronoun
        # object, a predicate, or a comma-delimited adjunct supplies a clause
        # attachment. A preceding negative marker requires its own scope.
        if previous.lemma not in ("not", "never", "no") and (
            previous.pos in ("VERB", "ADV", "PRON", "ADJ") or previous.token == ","
        ):
            return tokens[: start - (previous.token == ",")], Duration(extent, "during")
    return tokens, None


def temporal_offset(tokens: Sequence[TokenTrace], position: int) -> tuple[Duration | None, set[int]]:
    """Read an extent immediately qualifying a before/after clause linker."""
    by_position = {t.position: t for t in tokens}
    linker = by_position.get(position)
    if linker is None:
        return None, set()
    relation = linker.lemma
    if relation not in ("before", "after"):
        return None, set()
    for width in (2, 3):
        start = position - width
        span = [t for t in tokens if start <= t.position < position]
        if len(span) != width:
            continue
        extent = _extent(span)
        previous = by_position.get(start - 1)
        if extent is not None and (previous is None or previous.lemma not in ("for", "not", "never", "no")):
            return Duration(extent, relation), {t.position for t in span}
    return None, set()
