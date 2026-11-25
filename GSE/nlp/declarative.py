"""Declarative mode: a declared mini-universe of one simple clause per line (openspec change declarative-mode).

Rohan (2026-11-26): "Teach declaratives as an alternative mode. It's a complete 'mini-universe' in which the rules
of grammar are swapped around into an extremely simple form, almost Ogden's basic but with some fancier words."

    SUBJECT [MODAL] [not] VERB [OBJECT] [PREPOSITION NOUN-PHRASE]*
    NOUN-PHRASE := [DETERMINER] [ADJECTIVE]* NOUN+          (head = last noun)

Position decides role and the slot decides part of speech: a word is read only through the senses its slot allows
in the active lexicon. The verb position is the one where the rest of the line parses and present-tense subject-verb agreement holds;
when two positions both do, the line is refused as ambiguous rather than guessed. Capitalization is ignored for grammar; a capitalized word with no
lexical sense may fill a noun slot as a proper name. Anything else is refused by name (``NOT_DECLARATIVE_FORM``),
with the position and slot: pronouns, coordination, subordinate clauses, fronted phrases, imperatives, questions.
The output is the standard front end's ``NativeDoc``, so everything downstream is unchanged.
"""

from __future__ import annotations

import re
import sqlite3

from GSE.nlp.native import NativeDoc, NativeNLP, NativeToken

REFUSAL = "NOT_DECLARATIVE_FORM"
MODALS = frozenset({"can", "could", "may", "might", "must", "shall", "should", "will", "would"})
DETERMINERS = frozenset(
    {"a", "an", "the", "this", "that", "these", "those", "some", "all", "every", "each", "no", "any", "many", "few"}
    | {"my", "your", "his", "her", "its", "our", "their"}
)
PREPOSITIONS = frozenset(
    {"to", "from", "in", "on", "at", "by", "for", "with", "about", "into", "onto", "over", "under", "through"}
    | {"between", "across", "against", "among", "around", "after", "before", "during", "without", "within", "of"}
)
PRONOUNS = frozenset({"i", "you", "he", "she", "it", "we", "they", "me", "him", "us", "them", "who", "what", "which"})
COORDINATORS = frozenset({"and", "or", "but", "nor", "yet", "so"})
SUBORDINATORS = frozenset(
    {"because", "if", "when", "while", "although", "though", "since", "unless", "that", "whether"}
)


def refusal(position: int, slot: str, reason: str, word: str = "") -> dict:
    return {"code": REFUSAL, "position": position, "slot": slot, "reason": reason, "word": word}


class _Senses:
    """Part-of-speech eligibility from the active lexicon's word senses (nothing guessed or re-tagged)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._cache: dict[str, frozenset] = {}

    def pos_of(self, word: str) -> frozenset:
        key = word.lower()
        if key not in self._cache:
            rows = self.conn.execute("SELECT DISTINCT pos FROM word_senses WHERE lemma = ?", (key,)).fetchall()
            self._cache[key] = frozenset(row[0] for row in rows)
        return self._cache[key]


def _tokens(line: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'\-]*|[0-9]+|[.?!,;:]", line)


class DeclarativeNLP:
    """Call like ``NativeNLP``: one declarative line -> ``NativeDoc``; a refusal raises ``DeclarativeRefusal``."""

    def __init__(self, conn: sqlite3.Connection):
        self.senses = _Senses(conn)
        self.native = NativeNLP()

    def parse(self, line: str) -> list[tuple[str, str]] | dict:
        words = _tokens(line)
        if words and words[-1] in {"."}:
            words = words[:-1]
        if not words:
            return refusal(0, "LINE", "EMPTY")
        for i, word in enumerate(words):
            low = word.lower()
            if word in {"?", "!"}:
                return refusal(i, "LINE", "QUESTION_OR_EXCLAMATION", word)
            if word in {",", ";", ":"} or low in COORDINATORS:
                return refusal(i, "LINE", "COORDINATION", word)
            if low in SUBORDINATORS:
                return refusal(i, "LINE", "SUBORDINATE_CLAUSE", word)
            if low in PRONOUNS:
                return refusal(i, "NOUN_PHRASE", "PRONOUN", word)
        if words[0].lower() in PREPOSITIONS:
            return refusal(0, "SUBJECT", "FRONTED_PHRASE", words[0])
        parses = []
        for v in range(1, len(words)):
            subject = self._noun_phrase(words, 0, v)
            rest = self._predicate(words, v) if subject is not None else None
            if rest is not None and self._agrees(subject, rest):
                parses.append(subject + rest)
        if len(parses) > 1:  # the grammar leaves two readings: refuse, never guess
            verbs = [next(w for w, pos in parse if pos == "VERB") for parse in parses]
            return refusal(0, "VERB", "AMBIGUOUS_VERB_POSITION", "|".join(verbs))
        if not parses:
            first = words[0].lower()
            reason = "IMPERATIVE_OR_NO_SUBJECT" if "verb" in self.senses.pos_of(first) else "NO_DECLARATIVE_PARSE"
            return refusal(0, "LINE", reason, words[0])
        return parses[0]

    def _agrees(self, subject, predicate) -> bool:
        """Present-tense subject-verb agreement (no modal): a -s verb needs a singular head, a bare verb a plural one."""
        if predicate[0][1] == "AUX":
            return True
        verb = next(w for w, pos in predicate if pos == "VERB").lower()
        head = subject[-1][0].lower()
        lemma = self._verb_lemma(verb)
        plural = subject[-1][1] == "NOUN" and self.native._lemma(head, "NOUN") != head
        if verb != lemma and verb.endswith("s") and lemma + "s" == verb or verb == lemma + "es":
            return not plural
        if verb == lemma:
            return plural
        return True

    def _noun(self, word: str) -> str | None:
        if "noun" in self.senses.pos_of(word):
            return "NOUN"
        if word[:1].isupper() and not self.senses.pos_of(word):
            return "PROPN"
        return None

    def _noun_phrase(self, words, start, end):
        """[DET] [ADJ]* NOUN+ exactly covering words[start:end], or None."""
        i, out = start, []
        if i < end and words[i].lower() in DETERMINERS:
            out.append((words[i], "DET"))
            i += 1
        if i >= end or not self._noun(words[end - 1]):
            return None
        seen_noun = False
        for word in words[i : end - 1]:  # before the head: the adjective slot, then the noun compound
            if not seen_noun and "adj" in self.senses.pos_of(word):
                out.append((word, "ADJ"))
            elif self._noun(word):
                seen_noun = True
                out.append((word, self._noun(word)))
            else:
                return None
        out.append((words[end - 1], self._noun(words[end - 1])))
        return out

    def _predicate(self, words, start):
        """[MODAL] [not] VERB [NP] [PREP NP]* covering words[start:]."""
        i, out = start, []
        if i < len(words) and words[i].lower() in MODALS:
            out.append((words[i], "AUX"))
            i += 1
        if i < len(words) and words[i].lower() == "not":
            out.append((words[i], "PART"))
            i += 1
        if i >= len(words) or "verb" not in self.senses.pos_of(self._verb_lemma(words[i])):
            return None
        out.append((words[i], "VERB"))
        i += 1
        preps = [k for k in range(i, len(words)) if words[k].lower() in PREPOSITIONS]
        cut = preps[0] if preps else len(words)
        if cut > i:
            obj = self._noun_phrase(words, i, cut)
            if obj is None:
                return None
            out.extend(obj)
        bounds = preps + [len(words)]
        for a, b in zip(bounds, bounds[1:], strict=False):
            phrase = self._noun_phrase(words, a + 1, b)
            if phrase is None:
                return None
            out.append((words[a], "ADP"))
            out.extend(phrase)
        return out

    def _verb_lemma(self, word: str) -> str:
        from GSE.nlp.native import _rule_lemma, _wn_lemma

        low = word.lower()
        return _wn_lemma(low, "VERB") or _rule_lemma(low, "VERB") or low

    def __call__(self, line: str) -> NativeDoc:
        parsed = self.parse(line)
        if isinstance(parsed, dict):
            raise DeclarativeRefusal(parsed)
        tokens = []
        for i, (word, pos) in enumerate(parsed):
            low = word.lower()
            lemma = self._verb_lemma(word) if pos == "VERB" else self.native._lemma(low, pos)
            tokens.append(NativeToken(word, lemma, pos, i, self.native._morph(word, pos)))
        if line.rstrip().endswith("."):
            tokens.append(NativeToken(".", ".", "PUNCT", len(tokens), ""))
        return NativeDoc(tokens)


class DeclarativeRefusal(ValueError):
    """A line outside the declarative grammar, refused by name; never re-read by the standard front end."""

    def __init__(self, detail: dict):
        super().__init__(f"{detail['code']}:{detail['reason']}@{detail['position']}:{detail['slot']}")
        self.detail = detail


_HEADER = re.compile(r"^\s*#?\s*mode\s*:\s*(declarative|standard)\s*$", re.I)


def declared_mode(text: str) -> tuple[str | None, str, str | None]:
    """(mode, body, form) from a story's header: ``#mode: declarative`` or ``MODE: declarative`` on a leading line.

    The two spellings are one declaration, normalized here and recorded by ``form``; with no header the mode is
    None and the text is returned unchanged (undeclared input reads exactly as before).
    """
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        match = _HEADER.match(line)
        if match is None:
            if line.lstrip().upper().startswith(("GENRE:", "TITLE:", "CONTEXT:")):
                continue
            return None, text, None
        form = "hash_header" if line.lstrip().startswith("#") else "label_header"
        return match.group(1).lower(), "\n".join(lines[:index] + lines[index + 1 :]), form
    return None, text, None
