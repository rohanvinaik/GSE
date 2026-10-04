"""The closed set of communicative figures (the Janus enum).

Two kinds, both resolved by the Janus comparator:
  * **TROPES** — constitutively relational (intended meaning != literal): each figure
    is named by *which grounded relation licenses the substitution*.
  * **APPEALS / reasoning** — modes of persuasion (Aristotle's pisteis) and figures of
    reasoning; NOT meaning-substitution, but sensible modes of communication we still
    resolve (``is_trope = False``).

Closed basis, disciplined like the lexicon: no "borderline" slot; anchored to the
established theory, not invented. Grounded by two research passes (2026-06-21):

  * **The trope/scheme criterion** (Silva Rhetoricae, Quintilian): a TROPE turns word
    *meaning*; a scheme rearranges words; wordplay/metaplasm alters form/sound;
    implicature/speech-acts are pragmatic. Only meaning-turning figures are tropes — so
    apostrophe (address-act), pun/paronomasia (form), zeugma (arrangement), and
    innuendo (implicature) are deliberately OUT.
  * **Banks ARE the relation families** (Jakobson similarity/contiguity; Radden &
    Kovecses metonymy-as-access with synecdoche = part-for-whole; irony is ECHOIC/
    attributive, NOT "say the opposite"; metaphor != hyperbole).
  * **Resolution targets, not psychological kinds**: the discrete set is an engineering
    ontology; the relevance-theory continuum is real but orthogonal to it. Burke: tropes
    "shade into one another" -> overlap expected -> multi-label.

Single source of truth for: the typed-skeleton extraction enum, Face B's label set,
each figure's Face-A tell + licensing relation, and the subsumption lattice
(``refines``) the resolution voting propagates over. See ``docs/JANUS_FIGURE_SYSTEM.md``
(architecture, data contract) and ``docs/JANUS_MODULE_DESIGN.md`` (ternary resolution).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

# Banks = the relation families that license each trope (+ the non-trope buckets).
BANK_SIMILARITY = "similarity"  # cross-domain resemblance (metaphoric pole)
BANK_CONTIGUITY = "contiguity"  # association / part–whole (metonymic pole)
BANK_ATTRIBUTION = "attribution"  # echoic / dissociative (the irony family)
BANK_MAGNITUDE = "magnitude"  # quantity distortion (over/under-statement)
BANK_VALENCE = "valence"  # valence distortion (word-affect ⟂ world-salience)
BANK_INVERSION = "inversion"  # Silva "Semantic Inversions": contradiction / form↔function
BANK_APPEAL = "appeal"  # NON-trope: modes of persuasion + reasoning
BANK_BASELINE = "baseline"  # the null class

BANKS: Tuple[str, ...] = (
    BANK_SIMILARITY,
    BANK_CONTIGUITY,
    BANK_ATTRIBUTION,
    BANK_MAGNITUDE,
    BANK_VALENCE,
    BANK_INVERSION,
    BANK_APPEAL,
    BANK_BASELINE,
)


@dataclass(frozen=True)
class Figure:
    """One communicative figure — a closed-set member.

    Attributes:
        name: canonical snake_case label (the enum value).
        bank: the licensing-relation family it belongs to.
        definition: one-line gloss.
        face_a_tell: the deductive symbolic signature the comparator keys on.
        licensing_relation: the grounded relation GSE reads to fire the tell (from the
            existing WordNet / sparse-wiki substrate — never a new ontology).
        refines: the figure this one is a sub-type of (subsumption lattice edge); a vote
            for this figure also credits ``refines`` in resolution. Empty = top.
        is_trope: True for constitutively-relational tropes (literal != intended); False
            for the appeals/reasoning sub-group and the baseline.
        gated_on: a capability the figure's *full* detection needs but which is not yet
            built (Face B can still learn its shape now); empty if none.
    """

    name: str
    bank: str
    definition: str
    face_a_tell: str
    licensing_relation: str = ""
    refines: str = ""
    is_trope: bool = True
    gated_on: str = ""


# The closed set. Declaration order is stable and is the canonical bank ordering.
FIGURES: Tuple[Figure, ...] = (
    # — SIMILARITY (metaphoric pole) —
    Figure(
        "metaphor",
        BANK_SIMILARITY,
        "cross-domain identity ('Juliet is the sun')",
        "a TypeAssertion that fails coherence",
        licensing_relation="cross-domain similarity (mapping, NOT broadening)",
    ),
    Figure(
        "simile",
        BANK_SIMILARITY,
        "marked cross-domain comparison ('brave as a lion')",
        "comparison + explicit like/as marker",
        licensing_relation="cross-domain similarity (marked)",
    ),
    Figure(
        "personification",
        BANK_SIMILARITY,
        "agency given to a non-agent",
        "inanimate subject of an animate-only verb",
        licensing_relation="similarity to a person / agent",
        refines="metaphor",
    ),
    Figure(
        "catachresis",
        BANK_SIMILARITY,
        "forced metaphor filling a lexical gap ('leg of a table')",
        "cross-domain predication where no literal term exists",
        licensing_relation="forced cross-domain similarity",
        refines="metaphor",
    ),
    # — CONTIGUITY (metonymic pole; whole-part / part-part) —
    Figure(
        "metonymy",
        BANK_CONTIGUITY,
        "associated referent for the thing ('the crown')",
        "grounded referent != predicate's selectional fit; an associate fits",
        licensing_relation="contiguity: part-for-part within an ICM (the hub)",
    ),
    Figure(
        "synecdoche",
        BANK_CONTIGUITY,
        "part for whole ('all hands on deck')",
        "part-noun in a whole-noun role",
        licensing_relation="contiguity: part-for-whole (whole↔part)",
        refines="metonymy",
    ),
    Figure(
        "antonomasia",
        BANK_CONTIGUITY,
        "epithet for a name, or a name for a class ('the Bard' = Shakespeare)",
        "a descriptive / proper substitute for the referent's name",
        licensing_relation="contiguity: name ↔ attribute association",
        refines="metonymy",
    ),
    Figure(
        "metalepsis",
        BANK_CONTIGUITY,
        "remote reference via a chained association ('lead foot' = fast driver)",
        "referent reached through a chained association",
        licensing_relation="contiguity: metonymy of a metonymy",
        refines="metonymy",
    ),
    # — ATTRIBUTION (echoic / the irony family) —
    Figure(
        "verbal_irony",
        BANK_ATTRIBUTION,
        "literal content echoes an attributed thought with a dissociative attitude",
        "literal reading clashes with the attributed / expected reading",
        licensing_relation="echoic attribution (dissociative)",
    ),
    Figure(
        "sarcasm",
        BANK_ATTRIBUTION,
        "echoic irony with a hostile / mocking attitude",
        "echoic clash + negative target",
        licensing_relation="echoic attribution (hostile)",
        refines="verbal_irony",
    ),
    # — MAGNITUDE (over / under-statement) —
    Figure(
        "hyperbole",
        BANK_MAGNITUDE,
        "deliberate overstatement",
        "intensity inflation vs. situation",
        licensing_relation="magnitude inflation",
    ),
    Figure(
        "understatement",
        BANK_MAGNITUDE,
        "deliberate understatement (deminutio — the genus)",
        "intensity damping vs. situation",
        licensing_relation="magnitude damping",
    ),
    Figure(
        "litotes",
        BANK_MAGNITUDE,
        "affirmation by denying the contrary ('not bad')",
        "negation of the opposite pole",
        licensing_relation="magnitude damping + valence (negate-the-contrary)",
        refines="understatement",
    ),
    Figure(
        "meiosis",
        BANK_MAGNITUDE,
        "belittling understatement",
        "diminishing intensity damping",
        licensing_relation="magnitude damping (belittling)",
        refines="understatement",
    ),
    Figure(
        "auxesis",
        BANK_MAGNITUDE,
        "amplifying overstatement / climactic magnification",
        "intensity inflation (amplifying)",
        licensing_relation="magnitude inflation (amplifying)",
        refines="hyperbole",
    ),
    # — VALENCE (word-affect ⟂ world-salience) —
    Figure(
        "euphemism",
        BANK_VALENCE,
        "mild word for a grave referent ('passed away')",
        "low word-valence, high world-salience",
        licensing_relation="valence softening",
        gated_on="sparse-wiki potency",
    ),
    Figure(
        "dysphemism",
        BANK_VALENCE,
        "harsh word for a benign / neutral referent",
        "high word-valence magnitude, low world-salience",
        licensing_relation="valence harshening",
        gated_on="sparse-wiki potency",
    ),
    # — INVERSION (Silva "Semantic Inversions": contradiction / form↔function) —
    Figure(
        "oxymoron",
        BANK_INVERSION,
        "adjacent contradictory terms ('deafening silence')",
        "adjacent primes with opposed signs",
        licensing_relation="semantic inversion: adjacent self-contradiction",
    ),
    Figure(
        "paradox",
        BANK_INVERSION,
        "propositional self-contradiction that resolves",
        "clause coherence failure that re-coheres at scope",
        licensing_relation="semantic inversion: propositional self-contradiction",
    ),
    Figure(
        "humor_gardenpath",
        BANK_INVERSION,
        "a committed reading overturned by wider scope (funny as set theory)",
        "commitment reversal at wider scope",
        licensing_relation="semantic inversion: self-caught commitment reversal",
        gated_on="commitment TMS (Tier 2)",
    ),
    Figure(
        "rhetorical_question",
        BANK_INVERSION,
        "interrogative form, assertive function (erotema)",
        "question form, no genuine information gap",
        licensing_relation="semantic inversion: form ↔ function (interrogative → assertion)",
    ),
    # — APPEAL / reasoning (NON-trope: modes of persuasion + argument structure) —
    Figure(
        "logos",
        BANK_APPEAL,
        "appeal via logic / structure",
        "high IMPLIES / CAUSAL operator density",
        licensing_relation="mode of persuasion (pistis)",
        is_trope=False,
    ),
    Figure(
        "pathos",
        BANK_APPEAL,
        "appeal via emotion",
        "high affect magnitude / valence arc",
        licensing_relation="mode of persuasion (pistis)",
        is_trope=False,
    ),
    Figure(
        "ethos",
        BANK_APPEAL,
        "appeal via character / credibility",
        "source / credibility predication",
        licensing_relation="mode of persuasion (pistis)",
        is_trope=False,
    ),
    Figure(
        "postulation",
        BANK_APPEAL,
        "a claim floated as a question then settled (anthypophora)",
        "assertion content raised as a question and answered",
        licensing_relation="figure of reasoning (anthypophora)",
        is_trope=False,
    ),
    # — BASELINE: the null class (required negative set + the contrast ε needs) —
    Figure(
        "literal",
        BANK_BASELINE,
        "no figure; Face A and Face B agree",
        "A and B agree — the null class and matched negative set",
        is_trope=False,
    ),
)

# Read-only views over the closed set (the tuple above is the source of truth).
BY_NAME: Dict[str, Figure] = {f.name: f for f in FIGURES}
FIGURE_NAMES: Tuple[str, ...] = tuple(f.name for f in FIGURES)


def figures_in_bank(bank: str) -> List[Figure]:
    """All figures in one bank (= licensing-relation family), in declaration order."""
    return [f for f in FIGURES if f.bank == bank]


def tropes() -> List[Figure]:
    """The constitutively-relational figures (literal != intended)."""
    return [f for f in FIGURES if f.is_trope]


def appeals() -> List[Figure]:
    """The non-trope modes of communication (persuasion appeals + reasoning figures)."""
    return [f for f in FIGURES if f.bank == BANK_APPEAL]


def enum_for_bank(bank: str) -> List[str]:
    """The figure-name enum for one bank's typed-skeleton extraction pass.

    Bank-organized passes keep the LLM from confusing figures across banks during
    curation (workflow doc 1, §3a).
    """
    return [f.name for f in FIGURES if f.bank == bank]


def with_supertypes(name: str) -> List[str]:
    """``name`` plus its ``refines`` chain up the subsumption lattice.

    Used by the resolution voting: a vote for a sub-figure also credits its
    supertype(s), so 'synecdoche' partly confirms 'metonymy' and 'litotes' partly
    confirms 'understatement' (``docs/JANUS_MODULE_DESIGN.md``).
    """
    chain, cur, seen = [], name, set()
    while cur and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        cur = BY_NAME[cur].refines if cur in BY_NAME else ""
    return chain


def is_gated(name: str) -> bool:
    """True if this figure's *full* detection needs a capability not yet built.

    Gated figures (``humor_gardenpath``, ``euphemism``, ``dysphemism``) are still in the
    closed set — Face B can learn their shape now — but the comparator's deductive
    Face-A tell for them is incomplete until the named capability lands.
    """
    return bool(BY_NAME[name].gated_on)
