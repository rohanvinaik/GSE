"""Definitional decomposer — the definition-specific structural processor.

Definitions are their own genre with their own grammar. This classifies each gloss
into its definitional TEMPLATE and emits the **set-theory / vector OPERATION** that
template denotes — binding to GSE's *existing* operators (hierarchy scalars,
TYPE_ASSERT / SET_*, NOT, EVENT, BIND), not a regex-and-lookup. The genus-differentia
residual is handed to `definition_structure` (the ported sentence-architecture-style
decomposition of the remaining clause material).

This stage produces the OPERATION STRUCTURE only. Linking the operands to the grounded
primitive set and *applying* the operation (the vector/set math) is the next stage.

Template → operation map (confirmed against the engine's operators):
  plural of X            -> QUANTITY_SCALAR   (X ⊕ QUANTITY via encode_hierarchy)
  comparative of X       -> HIER_PLUS         (X ⊕ HIER_PLUS, level +1)
  superlative of X       -> HIER_MAX          (hierarchy max — NOT the SCALAR_EXTREME stub)
  past/participle of X   -> IDENTITY          (tense is sentence-scale; ran = run)
  alt form/spelling of X -> IDENTITY
  in a [adj] manner      -> IDENTITY          (adverb reduces to its adjective)
  of or relating to X    -> BIND              (relational adjective)
  not / without X        -> NOT               (sign-flip + POLARITY_PROPAGATION)
  having/characterized X -> INHERIT           (attributive adj: genus-differentia of the content)
  a [genus] ... (default)-> TYPE_ASSERT        (IS-A: inherit genus's set, restrict by differentia)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from gse.curation.decomposition.definition_structure import extract_structure
from gse.curation.external_sources.tier_0_dispatch import is_tier_0
from gse.lexicon.function_words import (
    CONJUNCTION_ENCODINGS,
    DETERMINER_ENCODINGS,
    PREPOSITION_ENCODINGS,
)

# Grammatical closed-class POS (kaikki labels): no word-scale primitive content —
# informational zero, handled at sentence scale. The closed-class words that ARE
# primes (I/you/not/if/because/with…) are spared by the is_tier_0 guard.
_CLOSED_CLASS = {
    "det",
    "article",
    "prep",
    "prep_phrase",
    "postp",
    "conj",
    "pron",
    "particle",
    "aux",
    "intj",
    "interj",
    "symbol",
    "punct",
    "character",
    "abbrev",
    "prefix",
    "suffix",
    "infix",
    "contraction",
    "phrase",
    "num",
}

# Sentence-scale OPERATORS that frequently carry a content POS tag (adj/adv/verb)
# and so slip past _CLOSED_CLASS. NSM treats these as quantity / intensity /
# modality, which GSE realizes as the sentence-scale QUANTITY / INTENSITY / HIER /
# COMP_* operators — not word-lexicon content (see docs/NSM_GRAMMAR_MAPPING.md).
# Decomposing them yields noise (`very→ONE`, `would→DO`); they are informational
# zero, unless they are a word-scale prime (then tier-0 grounds them).
_OPERATOR_WORDS = {
    "very",
    "too",
    "quite",
    "rather",
    "so",
    "how",
    "more",
    "most",  # intensity / degree
    "much",
    "many",
    "few",
    "little",
    "less",
    "least",  # quantity
    "would",
    "could",
    "should",
    "may",
    "might",
    "will",
    "shall",
    "ought",  # modality
    "only",
    "just",
    "also",
    "even",
    "than",  # focus (COMP_*)
    "often",
    "always",
    "never",
    "sometimes",
    "usually",
    "rarely",
    "seldom",
    "ever",  # frequency (MANY/ALL + TIME)
}

# A word is sentence-scale (informational zero in the lexicon) if it is in the
# system's own function-word inventory (determiners / conjunctions / prepositions)
# OR a sentence-scale operator above — sourced from gse/lexicon/function_words.py,
# not hand-rolled here.
_SENTENCE_SCALE_WORDS = (
    set(DETERMINER_ENCODINGS) | set(CONJUNCTION_ENCODINGS) | set(PREPOSITION_ENCODINGS) | _OPERATOR_WORDS
)


@dataclass
class DefinitionOp:
    """The structural decomposition of one definition into a GSE operation."""

    word: str
    pos: str
    template: str  # which definitional template matched
    operation: str  # the GSE operation it binds to
    operand: Optional[str] = None  # base word for redirect / scalar / negation / identity
    genus: Optional[str] = None  # IS-A head, for genus-differentia / attributive / relational
    differentia: List[str] = field(default_factory=list)  # distinctive modifier heads
    raw: str = ""
    note: str = ""


_LEADPAREN = re.compile(r"^\s*(?:\([^)]*\)\s*)+")

# (template, operation, regex capturing the operand). Order matters — most specific first.
_TEMPLATES: List[Tuple[str, str, "re.Pattern[str]"]] = [
    ("plural_of", "QUANTITY_SCALAR", re.compile(r"^plural of (?:the )?(.+?)\.?$", re.I)),
    (
        "inflection_of",
        "IDENTITY",
        re.compile(
            r"^[\w\s,'-]*?\b(?:participle|gerund|tense|indicative|subjunctive|"
            r"(?:third|second|first)[- ]person|singular|plural|infinitive)\b"
            r"[\w\s,'-]*? of (.+?)\.?$",
            re.I,
        ),
    ),
    ("comparative_of", "HIER_PLUS", re.compile(r"^comparative (?:degree |form )?of (.+?)\.?$", re.I)),
    ("superlative_of", "HIER_MAX", re.compile(r"^superlative (?:degree |form )?of (.+?)\.?$", re.I)),
    (
        "altform_of",
        "IDENTITY",
        re.compile(
            r"^(?:alternative (?:form|spelling)|misspelling|initialism|abbreviation|"
            r"acronym|obsolete (?:form|spelling)|synonym) of (.+?)\.?$",
            re.I,
        ),
    ),
    ("adv_manner", "IDENTITY", re.compile(r"^in an? (.+?) (?:manner|way|fashion)\b", re.I)),
    ("adj_relational", "BIND", re.compile(r"^(?:of or )?(?:relating|pertaining|belonging|related) to (.+?)\.?$", re.I)),
    ("adj_negative", "NOT", re.compile(r"^(?:not|without|lacking(?: in)?) (.+?)\.?$", re.I)),
    (
        "adj_attributive",
        "INHERIT",
        re.compile(
            r"^(?:having|possessing|containing|characterized by|marked by|"
            r"full of|consisting of) (.+?)\.?$",
            re.I,
        ),
    ),
]


# clause / alternative-sense boundaries: a redirect operand is the FIRST base word only.
_OPERAND_BOUNDARY = re.compile(r"\s*[;:,]\s*|\s+\bor\b\s+|\s+\band\b\s+", re.I)


def _clean_operand(s: str) -> str:
    """Keep just the base word/phrase: drop parentheticals + possessive markup, then
    stop at the first clause/alternative boundary."""
    s = re.sub(r"\([^)]*\)", "", s)  # drop (parentheticals)
    s = _OPERAND_BOUNDARY.split(s, maxsplit=1)[0]  # first base only
    s = re.sub(r"['’]s\b", "", s)  # drop possessive 's
    return s.strip().strip(".'\"’“”")


def classify(gloss: str) -> Tuple[Optional[str], Optional[str], Optional[str], str]:
    """Return (template, operation, operand, cleaned_gloss). template=None → default genus."""
    g = _LEADPAREN.sub("", gloss).strip()
    for template, op, rx in _TEMPLATES:
        m = rx.match(g)
        if m:
            return template, op, m.group(1).strip().rstrip(".,;"), g
    return None, None, None, g


def decompose(word: str, pos: str, gloss: str) -> DefinitionOp:
    """Decompose one definition into its structural GSE operation."""
    # Sentence-scale function words / operators (det, conj, prep, and the
    # quantity/intensity/modality operators) carry no word-scale content — they are
    # informational zero, handled by the sentence-scale system, not decomposed.
    # Spared when the word is itself a prime (tier-0 grounds it).
    if word.lower() in _SENTENCE_SCALE_WORDS and not is_tier_0(word):
        return DefinitionOp(
            word,
            pos,
            "sentence_scale",
            "ZERO",
            raw=gloss,
            note="function word / sentence-scale operator (informational zero)",
        )
    # Grammatical closed-class words carry no word-scale content (informational
    # zero) — unless they're a prime (then tier-0 already grounds them).
    if pos in _CLOSED_CLASS and not is_tier_0(word):
        return DefinitionOp(word, pos, "closed_class", "ZERO", raw=gloss, note="informational zero (sentence-scale)")

    template, op, operand, g = classify(gloss)

    if template in ("adj_attributive", "adj_relational"):
        # the content after the frame is itself a (mini) genus-differentia; drop
        # secondary senses (after ';') before extracting.
        content = re.split(r"\s*;\s*", operand or "", maxsplit=1)[0]
        ds = extract_structure(word, pos, "x", content)
        return DefinitionOp(
            word,
            pos,
            template,
            op or "INHERIT",
            genus=ds.genus,
            differentia=[d.head_lemma for d in ds.differentia],
            raw=gloss,
        )
    if template:
        # redirect / scalar / negation / identity: the operand is the base word
        return DefinitionOp(word, pos, template, op or "IDENTITY", operand=_clean_operand(operand or ""), raw=gloss)

    # default: genus-differentia (noun "a [genus]…", verb "to [verb]…", agentive, act-of)
    ds = extract_structure(word, pos, "x", gloss)
    return DefinitionOp(
        word,
        pos,
        "genus_differentia",
        "TYPE_ASSERT",
        genus=ds.genus,
        differentia=[d.head_lemma for d in ds.differentia],
        note=ds.note,
        raw=gloss,
    )


def _demo():
    from gse.curation.decomposition.source_index import primary_gloss

    probes = [
        ("happy", "adj"),
        ("unhappy", "adj"),
        ("happily", "adv"),
        ("dog", "noun"),
        ("kill", "verb"),
        ("men", "noun"),
        ("bigger", "adj"),
        ("biggest", "adj"),
        ("running", "verb"),
        ("national", "adj"),
        ("teacher", "noun"),
    ]
    print("=== definitional decomposer — operation structure per template ===\n")
    for w, p in probes:
        pg = primary_gloss(w, p)
        if not pg:
            print(f"  {w:9s} (no def)")
            continue
        op = decompose(w, pg[0], pg[1])
        extra = f"operand={op.operand}" if op.operand else f"genus={op.genus} diff={op.differentia[:3]}"
        print(f"  {w:9s}[{op.pos:4s}] {op.template:16s} -> {op.operation:14s} {extra}")
        print(f'             "{pg[1][:66]}"')


if __name__ == "__main__":
    _demo()
