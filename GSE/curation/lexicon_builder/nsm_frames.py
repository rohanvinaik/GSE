"""What an NSM record's frame shows: the explicated lemma and its part of speech (rebuild tasks 4-5, rule 1).

An explication binds to the readings of its explicated lemma, normalised through WordNet morphy for inflection only
(hands to hand, creatures to creature). The part of speech is the one its frame shows. The frames recognised here,
in order (the examples are invented, in the shape of the records' titles):

- `CROSS_LINGUISTIC`: the title names a language other than English, or the record is one of the untagged
  cross-linguistic explications listed in `_CROSS_LINGUISTIC`. These write nothing.
- `WITH_THE_WORD`: an abstract-noun explication, whose head line ends in SOMETHING, names its noun in a line
  "... with the word W".
- `FELT_NOUN` ("She felt dread"), `HAS_NOUN` ("He has a fever"): the object noun.
- `HAS_ATTRIBUTIVE` ("He has a stiff neck"), `ATTRIBUTIVE` ("X is a true friend"): an adjective modifying a noun.
- `PROGRESSIVE` ("Someone X is wading"): a form of be with an -ing verb.
- `PREDICATIVE` ("This thing is blunt", "I'm chilly", "It is damp in this place"): an adjective.
- `FINITE_VERB` ("Someone X tapped2 something", "X urged Y to leave"): a verb after an NSM subject. A particle
  makes a phrasal lemma ("pick up") and a reflexive object a reflexive one ("kill oneself").
- `SOMETHING_ADJ` ("something flat"): an adjective.
- `INDEFINITE_NOUN` ("a riddle"), `OF_NOUN` ("ache of the joints"): a noun.
- A bare citation form: `BARE_PLURAL` when it is an inflected plural noun ("creatures"); `BARE_NOMINAL_HEAD` when
  the explication's head line is a noun phrase (a substantive or a molecule, with no predicate). Otherwise
  `POS_NOT_SHOWN`, which records the cohort's part of speech when it has the lemma in one open class only
  (`sole_pos`): the frame does not show it, so it does not bind.

Anything else is `NO_FRAME`. A trailing digit is the source's sense index (hit1, happiness3) and is kept apart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from nltk.corpus import wordnet as wn

from .nsm_text import Token, normalise

LANGUAGES = ("polish", "russian", "french", "warlpiri", "kalam", "japanese", "maori", "māori", "arrernte", "malay")

# Cross-linguistic explications whose title carries no language tag: (source, start line) -> language.
_CROSS_LINGUISTIC = {
    ("GW2014", 3744): "Warlpiri",
    ("GW2014", 4569): "Tibetan Buddhist ideal, translated",
    ("GW2014", 5328): "Ancient Greek",
    ("GW2014", 6102): "Yankunytjatjara",
    ("GW2014", 6115): "Yankunytjatjara",
    ("GW2014", 6293): "French",
    ("GW2014", 6406): "French",
    ("GW2014", 6422): "French",
    ("GW2014", 6444): "French",
    ("GW2014", 6503): "Polish",
    ("GW2014", 8330): "Malay",
    ("GW2014", 8399): "Malay",
    ("GW2014", 8431): "Malay",
    ("GW2014", 8620): "Malay",
    ("GW2014", 8631): "Malay",
    ("GW2014", 8651): "Malay",
    ("GW2014", 8670): "Malay",
    ("GW2014", 10665): "Russian",
}

OPEN_CLASS = ("noun", "verb", "adj", "adv")
_WN_POS = {"noun": wn.NOUN, "verb": wn.VERB, "adj": wn.ADJ}
_SUBJECTS = {"someone", "something", "creature", "x", "i", "he", "she", "it"}
_NAMED_SUBJECTS = {"bill"}  # a proper name the records use as an NSM subject
_VARIABLES = {"x", "y", "z"}
_REFLEXIVES = {"himself", "herself", "oneself", "themselves", "itself", "myself"}
_PARTICLES = {"up"}
_BE = {"is", "was", "are", "were", "am"}
_NOT_VERBS = _BE | {"has", "had", "have", "can", "could", "felt", "feels"}

_WITH_THE_WORD = re.compile(r"\bwith the word ([a-z]+)")
_FELT_NOUN = re.compile(r"^(?:she|he|i|someone(?: x)?) (?:felt|feels|feel) ([a-z]+)$")
_HAS_NOUN = re.compile(r"^(?:she|he|i|x|someone(?: x)?) (?:has|had) an? ([a-z]+)$")
_HAS_ATTRIBUTIVE = re.compile(r"^(?:she|he|i|x|someone(?: x)?) (?:has|had) an? ([a-z]+) [a-z]+$")
_PROGRESSIVE = re.compile(r"^(?:[a-z]+ ){1,2}(?:is|was|are|were|am) ([a-z]+ing)(\d*)\b")
_PREDICATIVE = re.compile(r"^(?:this thing|[a-z]+) (?:is|was|are|am) ([a-z]+)(?: with| in this place| now)*$")
_ATTRIBUTIVE = re.compile(r"^(?:x|he|she|it|this thing|this) (?:is|was) an? ([a-z]+) [a-z]+$")
_SOMETHING_ADJ = re.compile(r"^something ([a-z]+)$")
_INDEFINITE = re.compile(r"^an? ([a-z]+(?: [a-z]+)?)$")
_OF_NOUN = re.compile(r"^([a-z]+) of [a-z]")
_BARE = re.compile(r"^([a-z]+?)(\d*)$")
_SENSE = re.compile(r"^([a-z]+?)(\d+)$")

DETERMINERS = {"a", "an", "one", "two", "some", "many", "the", "all", "this", "these"}
MODIFIERS = {"living", "small", "big", "very", "other"}
_NOMINAL_HEADS = {
    "someone",
    "something",
    "thing",
    "things",
    "people",
    "body",
    "bodies",
    "kind",
    "kinds",
    "part",
    "parts",
    "word",
    "words",
}
_CLAUSE_STOPS = {"that", "who", "which", "because", "when", "if"}
_CLAUSE_WORDS = _BE | {"can", "could", "will", "would", "be", "not"}
_VERB_EXPONENTS = {
    "think",
    "know",
    "want",
    "feel",
    "say",
    "do",
    "see",
    "hear",
    "happen",
    "move",
    "touch",
    "die",
    "live",
}


@dataclass(frozen=True)
class Frame:
    """The record's lemma and part of speech, or why it has none (`supported` False)."""

    frame: str
    lemma: str = ""
    pos: str = ""
    sense: str = ""
    supported: bool = True
    language: str = ""
    sole_pos: str = ""


def _refuse(reason: str, **kw) -> Frame:
    return Frame(reason, supported=False, **kw)


def base(word: str, pos: str) -> str | None:
    """The inflectional base of `word` in `pos` by WordNet morphy; None when two bases remain."""
    if pos not in _WN_POS:
        return word
    candidates = wn._morphy(word, _WN_POS[pos])
    others = sorted({c for c in candidates if c != word})
    if len(others) > 1:  # "singing": sing by stripping the suffix, singe by replacing it; stripping is the reading
        others = [c for c in others if word.startswith(c)]
    if not others:
        return word
    return others[0] if len(others) == 1 else None


def _verb_bases(word: str) -> list[str]:
    return wn._morphy(word, wn.VERB)


def title(explicates: str) -> str:
    """The title as lower-case words with brackets, parentheticals and punctuation removed."""
    t = normalise(explicates).lower()
    t = re.sub(r"\[[^\]]*\]", " ", t)
    previous = None
    while previous != t:
        previous, t = t, re.sub(r"\([^()]*\)", " ", t)
    t = t.replace("i'm", "i am").replace("it's", "it is")
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def language(source: str, start: int, explicates: str) -> str:
    """The language a cross-linguistic record explicates, or the empty string for English."""
    if (source, start) in _CROSS_LINGUISTIC:
        return _CROSS_LINGUISTIC[(source, start)]
    words = set(re.findall(r"[a-zā]+", normalise(explicates).lower()))
    named = [lang for lang in LANGUAGES if lang in words]
    return named[0].capitalize() if named else ""


def nominal_head(head: tuple[Token, ...]) -> bool:
    """The head line is a noun phrase: it opens with a substantive or a molecule and has no predicate."""
    i = 0
    while i < len(head) and (head[i].word in DETERMINERS or head[i].word in MODIFIERS) and not head[i].molecule:
        i += 1
    if i >= len(head) or not (head[i].molecule or head[i].word in _NOMINAL_HEADS):
        return False
    for t in head[i + 1 :]:
        if t.word in _CLAUSE_STOPS:
            break
        if t.word in _CLAUSE_WORDS or t.word in _VERB_EXPONENTS:
            return False
        if not t.word.endswith("ing") and any(b in _VERB_EXPONENTS for b in _verb_bases(t.word)):
            return False
    return True


def _ends_in_something(head: tuple[Token, ...]) -> bool:
    """The head line ends in SOMETHING, before any category formula: the abstract-noun head."""
    words = [t.word for t in head]
    if words[-3:] == ["of", "one", "kind"]:
        words = words[:-3]
    return bool(words) and words[-1] == "something"


def _split_sense(word: str) -> tuple[str, str]:
    m = _SENSE.match(word)
    return (m.group(1), m.group(2)) if m else (word, "")


def _finite_verb(t: str) -> Frame | None:
    words = t.split()
    if len(words) < 2:
        return None
    k = 0
    if words[0] in _SUBJECTS or words[0] in _NAMED_SUBJECTS:
        k = 1
        if words[0] in {"someone", "something", "creature"} and len(words) > 1 and words[1] in _VARIABLES:
            k = 2
    if k == 0 or k >= len(words):
        return None
    surface, sense = _split_sense(words[k])
    if surface in _NOT_VERBS or not _verb_bases(surface):
        return None
    lemma = base(surface, "verb")
    if lemma is None:
        return _refuse("LEMMA_AMBIGUOUS", lemma=surface, pos="verb")
    following = words[k + 1] if k + 1 < len(words) else ""
    if following in _PARTICLES:
        return Frame("FINITE_VERB_PHRASAL", f"{lemma} {following}", "verb", sense)
    if following in _REFLEXIVES:
        return Frame("FINITE_VERB_REFLEXIVE", f"{lemma} oneself", "verb", sense)
    return Frame("FINITE_VERB", lemma, "verb", sense)


def _bare(word: str, sense: str, head: tuple[Token, ...], pos_index: dict[str, set[str]]) -> Frame:
    noun = base(word, "noun")
    if noun is not None and noun != word and wn._morphy(word, wn.NOUN):
        return Frame("BARE_PLURAL", noun, "noun", sense)
    if nominal_head(head):
        return Frame("BARE_NOMINAL_HEAD", word, "noun", sense)
    open_pos = sorted(pos_index.get(word, set()) & set(OPEN_CLASS))
    sole = open_pos[0] if len(open_pos) == 1 else ""
    return _refuse("POS_NOT_SHOWN", lemma=word, sense=sense, sole_pos=sole)


def _with_pos(name: str, word: str, pos: str, sense: str = "") -> Frame:
    lemma = base(word, pos)
    if lemma is None:
        return _refuse("LEMMA_AMBIGUOUS", lemma=word, pos=pos)
    return Frame(name, lemma, pos, sense)


def of_record(source: str, start: int, explicates: str, lines: list[str], head: tuple[Token, ...], pos_index) -> Frame:
    """The frame of an English explication or molecule record (`language` is checked first, by the caller).

    `lines` are its cleaned lines (never stored)."""
    if _ends_in_something(head):
        for line in lines:
            m = _WITH_THE_WORD.search(line)
            if m:
                return _with_pos("WITH_THE_WORD", m.group(1), "noun")
    t = title(explicates)
    for name, pattern, pos in (
        ("FELT_NOUN", _FELT_NOUN, "noun"),
        ("HAS_NOUN", _HAS_NOUN, "noun"),
        ("HAS_ATTRIBUTIVE", _HAS_ATTRIBUTIVE, "adj"),
    ):
        m = pattern.match(t)
        if m:
            return _with_pos(name, m.group(1), pos)
    m = _PROGRESSIVE.match(t)
    if m and _verb_bases(m.group(1)):
        return _with_pos("PROGRESSIVE", m.group(1), "verb", m.group(2))
    for name, pattern, pos in (("PREDICATIVE", _PREDICATIVE, "adj"), ("ATTRIBUTIVE", _ATTRIBUTIVE, "adj")):
        m = pattern.match(t)
        if m:
            return _with_pos(name, m.group(1), pos)
    m = _SOMETHING_ADJ.match(t)
    if m:
        return _with_pos("SOMETHING_ADJ", m.group(1), "adj")
    verb = _finite_verb(t)
    if verb is not None:
        return verb
    for name, pattern, pos in (
        ("INDEFINITE_NOUN", _INDEFINITE, "noun"),
        ("OF_NOUN", _OF_NOUN, "noun"),
    ):
        m = pattern.match(t)
        if m:
            words = m.group(1).split()
            if len(words) > 1:
                return Frame(name, m.group(1), pos)
            return _with_pos(name, words[0], pos)
    m = _BARE.match(t)
    if m:
        return _bare(m.group(1), m.group(2), head, pos_index)
    return _refuse("NO_FRAME")


# --- Templates (rule 6) -----------------------------------------------------------------------------------------

_EG = re.compile(r"e\.g\.\s*([a-z][a-z ,]*)")
_TITLE_MEMBER = re.compile(r"^([a-z]+) \(")
_VERBAL_FRAME = re.compile(r"\bsomeone(?: x)? (?:is doing|was doing|does|did|said|says|is saying)\b")


def _members_in(segment: str) -> list[str]:
    out = []
    for m in _EG.finditer(segment):
        for word in re.split(r"[ ,]+", m.group(1)):
            if len(word) > 1 and word not in {"etc", "and"}:
                out.append(word)
    return out


def template_members(explicates: str, raw_lines: list[str]) -> list[str]:
    """The member lemmas the template record itself lists (surface forms)."""
    head = normalise(explicates).lower()
    found = _members_in(head)
    m = _TITLE_MEMBER.match(head)
    if not found and m:
        found = [m.group(1)]
    if not found:
        for line in raw_lines:
            for column in re.split(r"\s{3,}", line.lower()):
                found.extend(_members_in(column))
    return list(dict.fromkeys(found))


def template_pos(lines: list[str]) -> str:
    """Verb when the template shows a verbal lexico-syntactic frame (SOMEONE doing or saying)."""
    return "verb" if any(_VERBAL_FRAME.search(line) for line in lines) else ""


def template_field(explicates: str) -> str:
    """The wider class the template names, as a label (recorded, never applied)."""
    t = normalise(explicates).lower()
    t = re.sub(r"e\.g\..*$", "", t)
    inside = re.findall(r"\(([^()]*)\)", t)
    outside = re.sub(r"\([^()]*\)", " ", t)
    words = re.findall(r"[a-z]+", outside)
    if len(words) <= 1 and inside:
        words = re.findall(r"[a-z]+", inside[0])
    return "_".join(words[:6])
