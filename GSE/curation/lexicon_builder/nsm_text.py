"""An NSM explication record read as lines and tokens (rebuild tasks 4-5).

The verified records (`data/external/references/notes/explications/*.verified.jsonl`) are page extracts of
copyrighted books. Their text is read here in memory only and is never stored, printed into a committed file or
redistributed; what leaves this module is tokens and line positions.

A record's `text` holds more than the explication. This module recovers the explication's own lines:

- characters are normalised (apostrophes, quotation marks, ligatures) and words hyphenated across a line break are
  joined;
- page furniture is dropped: page numbers, running heads (a chapter title followed by a page number), and lines
  naming the authors, the journal or the book;
- right-margin section labels are dropped: all-capital words ("CATEGORY", "LEXICOSYNTACTIC FRAME") and dash glosses
  set off by a wide gap ("— tail");
- editorial brackets are dropped (the item marker "[A]", an inserted gloss), except the molecule mark "[m]";
- the title, the explicated frame the record's `explicates` field names, is set apart, with a parenthetical gloss
  that directly follows it;
- list markers ("a.", "—") are removed.

The head line is the first line of the explication proper, the one that says what the thing is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CHARS = str.maketrans(
    {
        "’": "'",
        "ʼ": "'",
        "‘": "'",
        "′": "'",
        "“": '"',
        "”": '"',
        "\x0c": "\n",
        "": "",
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬀ": "ff",
        "ﬃ": "ffi",
        "ﬄ": "ffl",
    }
)
_FURNITURE = ("Goddard", "Wierzbicka", "Годдард", "РУДН", "Words and Meanings")
_PAGE = re.compile(r"^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$")
_RUNNING_HEAD = re.compile(r"^\s*\S.*\S\s{3,}\d{1,4}\s*$")
_HYPHEN_BREAK = re.compile(r"(?<=[a-z])-\n\s*(?=[a-z])")
_MOLECULE_MARK = re.compile(r"(?<=[A-Za-z'/])\s*[\[{]\s*[mM]\s*[\]}]")  # after a word; "[M]" opening a line is an item
_EDITORIAL = re.compile(r"\[(?!m\])[^\]\n]*\]")
_DASH_GLOSS = re.compile(r"(?<=\S)\s{2,}[—–]\s*\S.*$")
_LIST_MARKER = re.compile(r"^\s*(?:[a-z]\d?\.\s|\d+\.\s|[—–-]+\s)\s*")
_TOKEN = re.compile(r"\[m\]|[A-Za-z]+(?:'[A-Za-z]+)?")
_WORDS = re.compile(r"[a-z0-9]+")

# A contraction's second part. "n't" is NOT's allolex DON'T in the chart; its auxiliary carries no prime unless it
# is CAN. "'s" after these words is a form of be, elsewhere a genitive.
_CAN_STEMS = {"ca", "can", "could"}
_IS_HOSTS = {"it", "there", "that", "what", "here", "where", "he", "she", "who", "this"}
_SUFFIX_WORDS = {"m": "am", "re": "are", "ve": "have", "ll": "will", "d": "would"}


@dataclass(frozen=True)
class Token:
    """One word of an explication line. `word` is lower case, except the prime exponent "I"."""

    word: str
    molecule: bool = False
    genitive: bool = False
    variable: bool = False


@dataclass(frozen=True)
class Body:
    """The explication's own lines as tokens; `lines[0]` is the head line."""

    title_found: bool
    embedded: bool
    lines: tuple[tuple[Token, ...], ...]

    @property
    def head(self) -> tuple[Token, ...]:
        return self.lines[0] if self.lines else ()


def normalise(text: str) -> str:
    return text.translate(_CHARS)


def title_words(explicates: str) -> list[str]:
    return _WORDS.findall(_EDITORIAL.sub(" ", normalise(explicates)).lower())


def clean_lines(text: str) -> list[str]:
    text = _HYPHEN_BREAK.sub("", normalise(text))
    out = []
    for line in text.split("\n"):
        if _PAGE.match(line) or _RUNNING_HEAD.match(line) or any(m in line for m in _FURNITURE):
            continue
        line = _MOLECULE_MARK.sub(" [m]", line)
        line = _EDITORIAL.sub(" ", line)
        line = _DASH_GLOSS.sub("", line)
        if line.strip():
            out.append(line)
    return out


def _title_end(lines: list[str], title: list[str]) -> int | None:
    """The number of leading lines the title covers, or None when the text does not open with it."""
    if not title:
        return None
    seen: list[str] = []
    for i, line in enumerate(lines):
        seen.extend(_WORDS.findall(line.lower()))
        if len(seen) >= len(title):
            return i + 1 if seen[: len(title)] == title else None
        if seen != title[: len(seen)]:
            return None
    return None


def _contains(lines: list[str], title: list[str]) -> bool:
    words = [w for line in lines for w in _WORDS.findall(line.lower())]
    n = len(title)
    return bool(n) and any(words[i : i + n] == title for i in range(len(words) - n + 1))


def _skip_gloss(lines: list[str], start: int) -> int:
    """Skip a parenthetical gloss that directly follows the title."""
    if start >= len(lines) or not lines[start].lstrip().startswith("("):
        return start
    depth = 0
    for i in range(start, len(lines)):
        depth += lines[i].count("(") - lines[i].count(")")
        if depth <= 0:
            return i + 1
    return start


def _expand(raw: str) -> list[Token]:
    low = raw.lower()
    if low.endswith("n't"):
        stem = low[:-3]
        return [Token("can"), Token("not")] if stem in _CAN_STEMS else [Token("not")]
    if low == "cannot":
        return [Token("can"), Token("not")]
    if "'" in raw:
        stem, suffix = raw.split("'", 1)
        word = "I" if stem == "I" else stem.lower()
        if suffix.lower() == "s":
            if word in _IS_HOSTS:
                return [Token(word), Token("is")]
            return [Token(word, genitive=True)]
        extra = _SUFFIX_WORDS.get(suffix.lower())
        return [Token(word)] + ([Token(extra)] if extra else [])
    if raw == "I":
        return [Token("I")]
    if len(raw) == 1 and raw.isupper():
        return [Token(low, variable=True)]
    return [Token(low)]


def tokens(line: str) -> tuple[Token, ...]:
    """The line's words, with molecule marks attached and right-margin capitals dropped."""
    out: list[Token] = []
    for raw in _TOKEN.findall(_LIST_MARKER.sub("", line)):
        if raw == "[m]":
            if out:
                last = out[-1]
                out[-1] = Token(last.word, True, last.genitive, last.variable)
            continue
        if len(raw) > 1 and raw.replace("'", "").isupper():
            continue
        out.extend(_expand(raw))
    return tuple(out)


def read(text: str, explicates: str) -> Body:
    """The explication lines of a record: title and gloss set apart, furniture and labels removed."""
    lines = clean_lines(text)
    title = title_words(explicates)
    end = _title_end(lines, title)
    embedded = end is None and _contains(lines, title)
    start = _skip_gloss(lines, end) if end is not None else 0
    body = tuple(t for t in (tokens(line) for line in lines[start:]) if t)
    return Body(title_found=end is not None, embedded=embedded, lines=body)


def lines_text(text: str) -> list[str]:
    """The cleaned lines as text, for frame patterns that read words in order (never stored)."""
    return [re.sub(r"\s+", " ", _LIST_MARKER.sub("", line)).strip().lower() for line in clean_lines(text)]
