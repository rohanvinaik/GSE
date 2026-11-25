"""Source agreement: independent source families vote, bank by bank, on a word's meaning.

Rohan's design (``openspec/changes/lexicon-symbolic-foundation/design.md``, *Founder correction*):
each independent source family gives a sign per bank within its declared scope
(``SOURCE_PRIMITIVE_SCOPE``). A sign commits when at least two independent families agree and
none opposes; opposition leaves the bank open with its possible signs. Nothing is weighted or
voted into a winner, and silence never counts as a vote. Correlated sources count as one family.

Votes come through the existing grounding pipeline: each source's parser ``to_primitives`` and
its declared scope. Names from the old basis's negative poles (BAD, SMALL, DEAD, …) fold into
the opposite sign of their positive bank, as the builder's basis does.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from GSE.curation.external_sources.source_scope import filter_votes_by_scope

from .foundation import BANKS, NEGATIVE_POLES

# The correlation structure of the source set (carried from the June build, 2026-07-01). The
# original independent datasets keep their own family; SentiWordNet, NRC-Emotion and NRC-VAD
# are different methods over different data, so their agreement is convergence. VerbNet,
# FrameNet and PropBank describe the same verbs' frames, and ConceptNet and USAS are both broad
# topical taggers: agreement within either group is one observation counted twice.
FAMILY = {
    # NRC-Emotion and NRC-VAD come from the same lab and the same crowd-sourced association method.
    "nrc_emotion": "nrc",
    "nrc_vad": "nrc",
    "verbnet": "verb_structure",
    "framenet": "verb_structure",
    "propbank": "verb_structure",
    "conceptnet": "topical",
    "usas": "topical",
}

# Sources that do not vote on an ordinary word's meaning here: the closed-class catalogue and the
# prime chart are encoded directly in the release, and wiktionary_v2 was dropped as degenerate.
NON_VOTING = frozenset({"gse_closed_class", "nsm_chart", "wiktionary_v2"})

MIN_FAMILIES = 2

# The banks each family measures: what the instrument literally rates, not what it is associated
# with. Only measuring families count toward agreement; a family's other in-scope signs are
# recorded but never commit anything. Rohan, 2026-11-24: "I do NOT want crap in the lexicon."
# Lancaster's action-effector ratings (BODY, DO, MOVE, SAY), NRC's emotion-to-WANT/KNOW
# associations and the topical taggers are associations; two of them agreeing is not evidence.
MEASURES = {
    "sentiwordnet": frozenset({"GOOD"}),  # synset polarity
    "nrc": frozenset({"GOOD", "FEEL"}),  # strong valence; a genuine emotion
    "lancaster_sensorimotor": frozenset({"SEE", "HEAR", "TOUCH", "FEEL"}),  # perceptual and interoceptive strength
    "concreteness": frozenset({"SOMETHING"}),
    "wordnet_hierarchy": frozenset(
        {
            "SOMETHING",
            "SOMEONE",
            "ALIVE",
            "BODY",
            "PEOPLE",
            "PART",
            "FEEL",
            "THINK",
            "KNOW",
            "SAY",
            "WANT",
            "SEE",
            "HEAR",
        }
    ),  # IS-A categories and lexical files
    "verb_structure": frozenset(
        {
            "DO",
            "MOVE",
            "CAUSE",
            "HAVE",
            "SAY",
            "KNOW",
            "THINK",
            "WANT",
            "SEE",
            "HEAR",
            "FEEL",
            "HAPPEN",
            "BE",
            "TOUCH",
            "EXIST",
            "START",
        }
    ),  # verb predicates
}


def measures(family: str, bank: str) -> bool:
    return bank in MEASURES.get(family, frozenset())


# Which parts of speech a family speaks to. VerbNet, FrameNet and PropBank describe verbs; the
# WordNet hierarchy's word-level projection follows noun hypernyms. The general ratings (NRC,
# VAD, SentiWordNet, Lancaster, concreteness, topical taggers, dictionary glosses) rate a word's
# dominant use, so they vote only for its dominant part of speech.
POS_FAMILIES = {"verb_structure": frozenset({"verb"}), "wordnet_hierarchy": frozenset({"noun"})}
_BANKS = frozenset(BANKS)


def family_of(source: str) -> str:
    return FAMILY.get(source, source)


def to_bank_signs(primitives: Mapping[str, int]) -> dict[str, int]:
    """One source's signs on the release's banks; negative poles fold into their positive bank.

    A source that asserts both a bank and its negative pole with conflicting signs gives no sign
    on that bank.
    """
    signs: dict[str, set[int]] = {}
    for name, value in primitives.items():
        if not value:
            continue
        sign = 1 if value > 0 else -1
        if name in NEGATIVE_POLES:
            name, sign = NEGATIVE_POLES[name], -sign
        if name in _BANKS:
            signs.setdefault(name, set()).add(sign)
    return {bank: next(iter(values)) for bank, values in signs.items() if len(values) == 1}


@dataclass(frozen=True)
class BankAgreement:
    """What the independent families say about one bank of one word."""

    bank: str
    support: Mapping[int, tuple[str, ...]]  # sign -> agreeing families (all), sorted

    @property
    def signs(self) -> frozenset[int]:
        return frozenset(self.support)

    @property
    def measuring(self) -> dict[int, tuple[str, ...]]:
        """sign -> the agreeing families that measure this bank."""
        return {
            sign: tuple(f for f in families if measures(f, self.bank))
            for sign, families in self.support.items()
            if any(measures(f, self.bank) for f in families)
        }

    @property
    def committed(self) -> int | None:
        """The sign two independent measuring families agree on, with no measuring opposition."""
        measuring = self.measuring
        if len(measuring) != 1:
            return None
        ((sign, families),) = measuring.items()
        return sign if len(families) >= MIN_FAMILIES else None

    @property
    def state(self) -> str:
        measuring = self.measuring
        if len(measuring) > 1:
            return "OPPOSED"
        if not measuring:
            return "UNMEASURED"
        return "AGREED" if self.committed is not None else "SINGLE_FAMILY"


def agree(votes_by_source: Mapping[str, Mapping[str, int]]) -> dict[str, BankAgreement]:
    """Combine sources' bank signs by family: agreement commits, opposition stays open."""
    by_bank: dict[str, dict[int, set[str]]] = {}
    for source, signs in votes_by_source.items():
        family = family_of(source)
        for bank, sign in signs.items():
            by_bank.setdefault(bank, {}).setdefault(sign, set()).add(family)
    return {
        bank: BankAgreement(bank, {sign: tuple(sorted(families)) for sign, families in sorted(support.items())})
        for bank, support in sorted(by_bank.items())
    }


# Strong measurements from the raw ratings (Rohan's F066: "words with strong encoding of emotive
# valence"). NRC-VAD valence runs from -1 to 1: |v| >= 0.5 keeps happy, love, good, kind, hate,
# pain, sad, difficult and drops real (0.44) and rather (-0.24). A mildly pleasant word such as
# learn (0.67) passes here but cannot commit GOOD: NRC is one family, and GOOD also needs
# SentiWordNet's independent polarity. Only a
# genuine emotion makes a feeling (not trust, anticipation or bare positive/negative), and only
# interoceptive strength (felt inside the body) does in Lancaster's ratings.
VALENCE_STRENGTH = 0.5
GENUINE_EMOTIONS = frozenset({"joy", "sadness", "anger", "fear", "disgust", "surprise"})
MODALITY_STRENGTH = 3.0  # Lancaster's own "strong modality" threshold on its 0-5 scale
# Felt strength for FEEL: genuine feelings rate >= 3.5 (proud 3.5, lonely 3.67, hurt 3.94, angry 4.15,
# afraid 4.36, happy 4.5); words that cause a feeling rate below (dangerous 3.2). jealous (3.32)
# stays open: a missing value, never a wrong one.
FELT_STRENGTH = 3.5


def measured_signs(source: str, parser: object, word: str) -> dict[str, int] | None:
    """A rating source's signs from its raw ratings, or None to use the parser's projection."""
    if source == "nrc_vad":
        entry = parser.get_vad(word)  # type: ignore[attr-defined]
        valence = getattr(entry, "valence", None) if entry is not None else None
        if valence is None or abs(valence) < VALENCE_STRENGTH:
            return {}
        return {"GOOD": 1 if valence > 0 else -1}
    if source == "nrc_emotion":
        emotions = parser.get_emotions(word) or {}  # type: ignore[attr-defined]
        return {"FEEL": 1} if any(emotions.get(emotion) == 1 for emotion in GENUINE_EMOTIONS) else {}
    if source == "lancaster_sensorimotor":
        entry = parser.get_sensorimotor(word)  # type: ignore[attr-defined]
        if entry is None:
            return {}
        signs = {}
        for bank, field, strength in (
            ("SEE", "visual", MODALITY_STRENGTH),
            ("HEAR", "auditory", MODALITY_STRENGTH),
            ("TOUCH", "haptic", MODALITY_STRENGTH),
            ("FEEL", "interoceptive", FELT_STRENGTH),
        ):
            if (getattr(entry, field, 0) or 0) >= strength:
                signs[bank] = 1
        return signs
    return None


def word_votes(parsers: Mapping[str, object], word: str) -> dict[str, dict[str, int]]:
    """Each voting source's in-scope bank signs for one word, through its parser."""
    votes: dict[str, dict[str, int]] = {}
    for source, parser in sorted(parsers.items()):
        if source in NON_VOTING:
            continue
        measured = measured_signs(source, parser, word)
        if measured is not None:
            if measured:
                votes[source] = measured
            continue
        with_confidence = getattr(parser, "to_primitives_with_confidence", None)
        if callable(with_confidence):
            raw = with_confidence(word)
        else:
            raw = {name: (value, 1.0) for name, value in parser.to_primitives(word).items()}
        scoped = filter_votes_by_scope(source, raw)
        signs = to_bank_signs({name: value for name, (value, _confidence) in scoped.items()})
        if signs:
            votes[source] = signs
    return votes


def word_agreement(parsers: Mapping[str, object], word: str) -> dict[str, BankAgreement]:
    return agree(word_votes(parsers, word))


def votes_for_pos(
    votes_by_source: Mapping[str, Mapping[str, int]], pos: str, dominant: bool
) -> dict[str, dict[str, int]]:
    """The votes that speak to one part of speech of the word."""
    kept = {}
    for source, signs in votes_by_source.items():
        family = family_of(source)
        speaks = POS_FAMILIES.get(family)
        if (speaks is not None and pos in speaks) or (speaks is None and dominant):
            kept[source] = dict(signs)
    return kept


def committed_signs(agreement: Mapping[str, BankAgreement]) -> dict[str, int]:
    return {bank: row.committed for bank, row in agreement.items() if row.committed is not None}


def describe(agreement: Mapping[str, BankAgreement], banks: Iterable[str] | None = None) -> list[str]:
    """Readable lines, for reports: bank, state and the families behind each sign."""
    wanted = set(banks) if banks is not None else None
    lines = []
    for bank, row in agreement.items():
        if wanted is not None and bank not in wanted:
            continue
        parts = ", ".join(f"{'+' if sign > 0 else '-'}: {'/'.join(families)}" for sign, families in row.support.items())
        lines.append(f"{bank} {row.state} ({parts})")
    return lines
