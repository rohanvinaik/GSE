"""Forced cells and open fields for the emotion rows under the contract the NSM literature settles.

Reads the 58-coordinate basis from the builder and the slice population from emotion_population.json,
then writes one complete JSON file:
- the reading classes, and which population words fall in each;
- the cells each class gets from admitted laws and proposed rows, with the source of each;
- the coordinates left open, and their count under each approval scenario;
- published explications projected as evaluation gold (Wierzbicka 1999 and 1990b, primary text checked
  against the page images), each checked against its class's fixed cells with a named code;
- the controls for the typed GOOD field, each with its published feeling line;
- the four surprise-type words whose valence Goddard 2015 states, and which control words are in the slice.

Source keys are those of NSM_RESOLUTIONS.md. A gold explication is projected by the packet's rule:
every non-substantive prime it contains is written, whatever its scope, except GOOD, which is the felt
valence and is read from the feeling line only; substantives are roles unless they head the word's own
denotation; THIS has no coordinate in this basis.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from gse.lexicon_builder.basis import BANKS, BASIS_ID, OPPOSITE_POLES  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent
NEGATIVE = {negative: positive for positive, negative in OPPOSITE_POLES}
COORDINATES = [name for bank in BANKS for name in bank if name not in NEGATIVE]
BANK_OF = {name: index for index, bank in enumerate(BANKS) for name in bank}

PERSON_SUBSTANTIVES = ("I", "YOU", "SOMEONE", "PEOPLE", "BODY")
RELATIONAL_SUBSTANTIVES = ("KIND", "PART")
NON_VALENCE_SCALES = ("E5", "E6")  # USAS "trepidation/courage/surprise" and "apprehension/confidence"

Cell = tuple[int | str | None, str]

# Cells every emotion row gets (rows 1, 4, 5 are admitted laws; 22 is the proposed template row).
COMMON: dict[str, Cell] = {
    "FEEL": (1, "row 1 (F043); every NSM emotion explication: 'X felt something'"),
    "THINK": (1, "row 22 (F129); every sourced explication of a slice word has THINK, at least in its typicality line"),
    "LIKE": (1, "row 22; typicality in all published wordings ('X felt something like this', 'think like this')"),
    "KIND": (0, "row 4 (F007)"),
    "INTENSITY": (1, "row 5 (F125-F126)"),
}
# The typicality line's WHEN is invariant across the adjective and noun wordings. For verbs it stays a field: English
# verbs are explicated only in the noun format (W1990b fear, W1999 dread), and the verb-specific vihata (TVS19) has none.
TYPICALITY_WHEN: dict[str, Cell] = {
    "WHEN": (1, "row 22; 'sometimes' (W1990b), 'when this person thinks this' (W1999), 'when they think like this' (G15, GY14)")
}
# Row 22 writes BECAUSE only for classes in which every published wording links thought and feeling with it.
# For the other adjectives it is a field: W1999's "X was sad" (p.62) has no link by design, and W1999's happy
# (p.52) brackets it.
BECAUSE_SOURCE = {
    "adjective_fear": "row 22: every fear-family explication links thought and feeling with BECAUSE (W1990b pp.363-373; W1999 pp.75-86)",
    "noun_fear": "row 22: every fear-family explication links thought and feeling with BECAUSE (W1990b pp.363-373; W1999 pp.75-86)",
    "adjective_e5e6_outside_fear": "row 22: every sourced wording links them (G15 p.4; W1999 petrified p.77, horrified p.79, alarmed p.81, worried p.85, concern p.86)",
    "noun_e5e6_outside_fear": "row 22: every sourced wording links them (W1990b anguish p.371; W1999 concern p.86)",
    "noun_other": (
        "row 22: every sourced slice noun links them (W1999 sadness p.39, sorrow p.67, grief p.68, despair p.70, "
        "pity p.101; W1990b anger p.360). GW2014's happiness as an emotion ([H] p.120) has none; happiness is not "
        "in the population"
    ),
    "verb": "row 22: W1990b fear, noun and verb (p.363); W1999 dread (p.80); TVS19 vihata",
    "verb_e5e6": "row 22: W1990b fear, noun and verb (p.363); W1999 dread (p.80)",
}
FEAR_FRAME: dict[str, Cell] = {
    "CAN": (
        1,
        "row 24a; FrameNet Fear < Emotions_by_possibility. CAN occurs in all 8 sourced Fear readings (scope-blind): "
        "as 'can happen' in afraid, fear, scared, frightened, terrified, apprehension; only as the experiencer's "
        "ability in nervous ('if I can', 'what I can do') and dread ('if I can', 'I can't do anything')",
    ),
    "HAPPEN": (1, "row 24a; HAPPEN occurs in all 8 sourced Fear readings"),
}
POLE = "+1 or -1 from the certified pole"
GOOD_BY_CLASS: dict[str, Cell] = {
    "adjective_fear": (-1, "Q1 felt valence; every sourced Fear explication 'feels something (very) bad'"),
    "noun_fear": (
        -1,
        "Q1 felt valence (default); the F057 ruling covers every feeling noun: GOOD empty if F057 is read "
        "literally. Fixed either way, so the counts do not change.",
    ),
    "adjective_other": (POLE, "Q1 felt valence"),
    "noun_other": (POLE, "Q1 felt valence (default); empty if F057 is read literally"),
    "verb": (POLE, "Q1 felt valence"),
}
GOOD_FIELD_NOTE = (
    "GOOD is a typed field {+1, -1, empty}: USAS E5 and E6 are not valence scales, and concern's feeling is "
    "unspecified (W1990b p.373, W1999 p.86)"
)
CAUSE_SILENT: dict[str, Cell] = {
    "CAUSE": (
        None,
        "row 26, only under option A of the CAUSE decision (founder's call); under option B, CAUSE is an open field",
    )
}
ROLE_CONTRACT = "Q2 role contract: substantives other than the word's own head are roles (G12 p.16; GW2014 pp.56-59)"
CLASSES = (
    "adjective_fear",
    "adjective_other",
    "adjective_e5e6_outside_fear",
    "noun_fear",
    "noun_other",
    "noun_e5e6_outside_fear",
    "verb",
    "verb_e5e6",
)


def substantive_cells(part_of_speech: str, contract: bool) -> dict[str, Cell]:
    """Row 3 writes SOMETHING 0 for a modifier; under the Q2 contract only the word's own head is +1."""
    cells: dict[str, Cell] = {}
    if part_of_speech == "adjective":
        cells["SOMETHING"] = (0, "row 3 (F057, F088, F118)")
    if not contract:
        return cells
    head = "SOMETHING" if part_of_speech == "noun" else None
    for name in ("SOMETHING",) + PERSON_SUBSTANTIVES + ("PART",):
        if name == head:
            cells[name] = (1, "row 21: the noun names the 'something' X felt (W1999 'Fear (X felt fear) (a) X felt something')")
        elif name not in cells:
            label = "3b" if part_of_speech == "adjective" else f"row {20 if part_of_speech == 'verb' else 21}"
            cells[name] = (0, f"{label}; {ROLE_CONTRACT}")
    return cells


def reading_class(kind: str, extend: bool, cause_row: bool) -> dict[str, Cell]:
    part_of_speech = kind.split("_")[0]
    cells: dict[str, Cell] = dict(COMMON)
    if part_of_speech in ("adjective", "noun"):
        cells.update(TYPICALITY_WHEN)
    cells.update(substantive_cells(part_of_speech, extend))
    if kind in BECAUSE_SOURCE:
        cells["BECAUSE"] = (1, BECAUSE_SOURCE[kind])
    if kind in ("adjective_fear", "noun_fear"):
        cells.update(FEAR_FRAME)
    if kind in GOOD_BY_CLASS:
        cells["GOOD"] = GOOD_BY_CLASS[kind]
    if cause_row:
        cells.update(CAUSE_SILENT)
    return cells


def class_of(row: str, entry: dict) -> str:
    """Fear certification first; then a reading whose slice tags are all E5 or E6 gets the GOOD field."""
    frames = set(entry["framenet_frames"])
    non_valence = all(tag.startswith(NON_VALENCE_SCALES) for tag in entry["matching_tags"])
    if row == "19_adjective":
        return "adjective_fear" if "Fear.a" in frames else "adjective_e5e6_outside_fear" if non_valence else "adjective_other"
    if row == "21_noun":
        return "noun_fear" if "Fear.n" in frames else "noun_e5e6_outside_fear" if non_valence else "noun_other"
    return "verb_e5e6" if non_valence else "verb"


def pole_of(entry: dict) -> int:
    return -1 if entry["matching_tags"][0].rstrip("+").endswith("-") else 1


def project(primes: dict[str, int]) -> dict[str, int]:
    out = {}
    for name, sign in primes.items():
        coordinate, value = (NEGATIVE[name], -sign) if name in NEGATIVE else (name, sign)
        out[coordinate] = value
    return out


# Published explications, verbatim, line by line, with the primes each line contains. "feeling" names the line
# that states the felt quality; "links" names the lines that join thought and feeling.
GOLD = {
    "afraid": {
        "row": "19_adjective",
        "source": "W1999 p.75 (page image checked; matches K pp.150-151)",
        "lines": {
            "a X felt something because X thought something": ["FEEL", "BECAUSE", "THINK"],
            "b sometimes a person thinks about something:": ["QUANTITY", "WHEN", "THINK"],
            "c something bad can happen to me because of this": ["BAD", "CAN", "HAPPEN", "BECAUSE"],
            "d I don't want this to happen": ["NOT", "WANT", "HAPPEN"],
            "e I don't know if I can do anything now": ["NOT", "KNOW", "IF", "CAN", "DO", "NOW"],
            "f when this person thinks this this person feels something bad": ["WHEN", "THINK", "FEEL", "BAD"],
            "g X felt something like this": ["FEEL", "LIKE"],
            "h because X thought something like this": ["BECAUSE", "THINK", "LIKE"],
        },
        "feeling": "f",
        "links": ["a", "h"],
        "head": None,
    },
    "fear": {
        "row": "21_noun",
        "source": "W1999 p.75 (page image checked; matches K p.150)",
        "lines": {
            "a X felt something because X thought something": ["FEEL", "BECAUSE", "THINK"],
            "b sometimes a person thinks:": ["QUANTITY", "WHEN", "THINK"],
            "c I don't know what will happen": ["NOT", "KNOW", "HAPPEN"],
            "d some bad things can happen": ["QUANTITY", "BAD", "CAN", "HAPPEN"],
            "e I don't want these things to happen": ["NOT", "WANT", "HAPPEN"],
            "f I want to do something because of this if I can": ["WANT", "DO", "BECAUSE", "IF", "CAN"],
            "g I don't know if I can do anything": ["NOT", "KNOW", "IF", "CAN", "DO"],
            "h when this person thinks this this person feels something bad": ["WHEN", "THINK", "FEEL", "BAD"],
            "i X felt something like this": ["FEEL", "LIKE"],
            "j because X thought something like this": ["BECAUSE", "THINK", "LIKE"],
        },
        "feeling": "h",
        "links": ["a", "j"],
        "head": "SOMETHING",
    },
    "nervous": {
        "row": "19_adjective",
        "source": "W1999 p.84 (page image checked)",
        "lines": {
            "a X felt something because X thought something": ["FEEL", "BECAUSE", "THINK"],
            "b sometimes a person thinks:": ["QUANTITY", "WHEN", "THINK"],
            "c I have to do something": ["NOT", "CAN", "DO"],
            "d I don't know what will happen when I am doing it": ["NOT", "KNOW", "HAPPEN", "WHEN", "DO"],
            "e maybe something bad will happen": ["MAYBE", "BAD", "HAPPEN"],
            "f I don't want this to happen": ["NOT", "WANT", "HAPPEN"],
            "g I want to do something because of this if I can": ["WANT", "DO", "BECAUSE", "IF", "CAN"],
            "h I don't know what I can do": ["NOT", "KNOW", "CAN", "DO"],
            "i when this person thinks this this person feels something bad": ["WHEN", "THINK", "FEEL", "BAD"],
            "j X felt something like this": ["FEEL", "LIKE"],
            "k because X thought something like this": ["BECAUSE", "THINK", "LIKE"],
        },
        "feeling": "i",
        "links": ["a", "k"],
        "head": None,
    },
    "terrified": {
        "row": "19_adjective",
        "source": "W1999 p.77 (page image checked)",
        "lines": {
            "a X felt something because X thought something": ["FEEL", "BECAUSE", "THINK"],
            "b sometimes a person thinks:": ["QUANTITY", "WHEN", "THINK"],
            "c something very bad is happening": ["INTENSITY", "BAD", "HAPPEN"],
            "d something very bad can happen to me now because of this": ["INTENSITY", "BAD", "CAN", "HAPPEN", "NOW", "BECAUSE"],
            "e I don't want this to happen": ["NOT", "WANT", "HAPPEN"],
            "f I want to do something because of this if I can": ["WANT", "DO", "BECAUSE", "IF", "CAN"],
            "g I can't do anything now": ["NOT", "CAN", "DO", "NOW"],
            "h when this person thinks this this person feels something very bad": ["WHEN", "THINK", "FEEL", "INTENSITY", "BAD"],
            "i X felt something like this": ["FEEL", "LIKE"],
            "j because X thought something like this": ["BECAUSE", "THINK", "LIKE"],
        },
        "feeling": "h",
        "links": ["a", "j"],
        "head": None,
    },
    "scared": {
        "row": "19_adjective",
        "source": "W1990b p.365 (page image checked; W1999 gives no explication of scared)",
        "lines": {
            "a X feels something": ["FEEL"],
            "b sometimes a person thinks something like this:": ["QUANTITY", "WHEN", "THINK", "LIKE"],
            "c something bad can happen to me now": ["BAD", "CAN", "HAPPEN", "NOW"],
            "d I don't want this": ["NOT", "WANT"],
            "e because of this, I don't want to do something": ["BECAUSE", "NOT", "WANT", "DO"],
            "f because of this, this person feels something bad": ["BECAUSE", "FEEL", "BAD"],
            "g X feels like this": ["FEEL", "LIKE"],
        },
        "feeling": "f",
        "links": ["f"],
        "head": None,
    },
    "frightened": {
        "row": "19_adjective",
        "source": "W1990b p.367 (page image checked; W1999 gives no explication of frightened)",
        "lines": {
            "a X feels something": ["FEEL"],
            "b sometimes a person feels something like this:": ["QUANTITY", "WHEN", "FEEL", "LIKE"],
            "c something bad can happen now": ["BAD", "CAN", "HAPPEN", "NOW"],
            "d I don't want this": ["NOT", "WANT"],
            "e because of this, I would want to do something": ["BECAUSE", "IF", "WANT", "DO"],
            "f I don't know what I can do": ["NOT", "KNOW", "CAN", "DO"],
            "g because of this, this person feels something bad": ["BECAUSE", "FEEL", "BAD"],
            "h X feels like this": ["FEEL", "LIKE"],
        },
        "feeling": "g",
        "links": ["g"],
        "head": None,
        "codes": {"THINK": "NOT_IN_EXPLICATION_SUSPECTED_MISPRINT"},
        "note": (
            "Line b is printed 'feels' where every other explication in the paper prints 'thinks'; almost certainly "
            "a misprint. Projected literally, the explication has no THINK."
        ),
    },
    "apprehension": {
        "row": "21_noun",
        "source": "W1999 pp.86-87 (page images checked)",
        "lines": {
            "a X felt something because X thought something": ["FEEL", "BECAUSE", "THINK"],
            "b sometimes a person thinks:": ["QUANTITY", "WHEN", "THINK"],
            "c something bad can happen": ["BAD", "CAN", "HAPPEN"],
            "d I don't want this to happen": ["NOT", "WANT", "HAPPEN"],
            "e I don't know if it will happen": ["NOT", "KNOW", "IF", "HAPPEN"],
            "f when this person thinks this this person feels something bad, not very bad": ["WHEN", "THINK", "FEEL", "BAD", "NOT", "INTENSITY"],
            "g X felt something like this": ["FEEL", "LIKE"],
            "h because X thought something like this": ["BECAUSE", "THINK", "LIKE"],
        },
        "feeling": "f",
        "links": ["a", "h"],
        "head": "SOMETHING",
    },
    "dread": {
        "row": "21_noun",
        "source": "W1999 p.80 (page image checked)",
        "lines": {
            "a X felt something because X thought something": ["FEEL", "BECAUSE", "THINK"],
            "b sometimes a person thinks about something:": ["QUANTITY", "WHEN", "THINK"],
            "c if this happens, something very bad will happen to me": ["IF", "HAPPEN", "INTENSITY", "BAD"],
            "d I know what": ["KNOW"],
            "e I don't want this to happen": ["NOT", "WANT", "HAPPEN"],
            "f I want to do something because of this if I can": ["WANT", "DO", "BECAUSE", "IF", "CAN"],
            "g I can't do anything": ["NOT", "CAN", "DO"],
            "h when this person thinks this this person feels something very bad": ["WHEN", "THINK", "FEEL", "INTENSITY", "BAD"],
            "i X felt something like this": ["FEEL", "LIKE"],
            "j because X thought something like this": ["BECAUSE", "THINK", "LIKE"],
        },
        "feeling": "h",
        "links": ["a", "j"],
        "head": "SOMETHING",
    },
    "sad": {
        "row": "19_adjective",
        "source": "W1999 p.62 (page image checked; matches FBG22 p.265 in every prime)",
        "lines": {
            "a X felt something": ["FEEL"],
            "b sometimes a person thinks:": ["QUANTITY", "WHEN", "THINK"],
            "c I know: something bad happened": ["KNOW", "BAD", "HAPPEN"],
            "d I don't want things like this to happen": ["NOT", "WANT", "LIKE", "HAPPEN"],
            "e I can't think: I will do something because of it now": ["NOT", "CAN", "THINK", "DO", "BECAUSE", "NOW"],
            "f I know I can't do anything": ["KNOW", "NOT", "CAN", "DO"],
            "g when this person thinks this this person feels something bad": ["WHEN", "THINK", "FEEL", "BAD"],
            "h X felt something like this": ["FEEL", "LIKE"],
        },
        "feeling": "g",
        "links": [],
        "head": None,
    },
    "concerned": {
        "row": "19_adjective",
        "source": "W1999 p.86 (page image checked); W1990b p.373 also leaves the feeling open",
        "lines": {
            "a X felt something because X thought something": ["FEEL", "BECAUSE", "THINK"],
            "b sometimes a person thinks for some time about someone:": ["QUANTITY", "WHEN", "THINK"],
            "c something bad can happen to this person": ["BAD", "CAN", "HAPPEN"],
            "d I don't want this to happen": ["NOT", "WANT", "HAPPEN"],
            "e I want good things to happen to this person": ["WANT", "GOOD", "HAPPEN"],
            "f because of this I want to do something if I can": ["BECAUSE", "WANT", "DO", "IF", "CAN"],
            "g when this person thinks this this person feels something": ["WHEN", "THINK", "FEEL"],
            "h X felt something like this": ["FEEL", "LIKE"],
            "i because X thought something like this": ["BECAUSE", "THINK", "LIKE"],
        },
        "feeling": "g",
        "links": ["a", "i"],
        "head": None,
    },
    "sadness": {
        "row": "21_noun",
        "source": "W1999 p.39 (page image checked)",
        "lines": {
            "a X feels something": ["FEEL"],
            "b sometimes a person thinks:": ["QUANTITY", "WHEN", "THINK"],
            "c I know: something bad happened": ["KNOW", "BAD", "HAPPEN"],
            "d I don't want things like this to happen": ["NOT", "WANT", "LIKE", "HAPPEN"],
            "e I can't think now: I will do something because of this": ["NOT", "CAN", "THINK", "NOW", "DO", "BECAUSE"],
            "f I know that I can't do anything": ["KNOW", "NOT", "CAN", "DO"],
            "g because of this, this person feels something bad": ["BECAUSE", "FEEL", "BAD"],
            "h X feels something like this": ["FEEL", "LIKE"],
        },
        "feeling": "g",
        "links": ["g"],
        "head": "SOMETHING",
    },
    "pity": {
        "row": "21_noun",
        "source": "W1999 p.101 (page image checked)",
        "lines": {
            "a X felt something because X thought something": ["FEEL", "BECAUSE", "THINK"],
            "b sometimes a person thinks about someone else:": ["QUANTITY", "WHEN", "THINK"],
            "c something bad happened to this other person": ["BAD", "HAPPEN"],
            "d this is bad": ["BAD"],
            "e something like this is not happening to me": ["LIKE", "NOT", "HAPPEN"],
            "f when this person thinks this this person feels something": ["WHEN", "THINK", "FEEL"],
            "g X felt something like this": ["FEEL", "LIKE"],
            "h because X thought something like this": ["BECAUSE", "THINK", "LIKE"],
        },
        "feeling": "f",
        "links": ["a", "h"],
        "head": "SOMETHING",
        "codes": {"GOOD": "SOURCE_CONFLICTS_WITH_ITSELF"},
        "note": (
            "The explication leaves the feeling's quality open, while the text before it says 'the focus of pity, "
            "then, is on the other person ... and so the feeling is \"bad\" rather than \"good\"' (p.101). The pole "
            "(E4.1-) gives -1, which agrees with the prose and not with the explication."
        ),
    },
    "sorrow": {
        "row": "21_noun",
        "source": "W1999 p.67 (page image checked)",
        "lines": {
            "a X felt something because X thought something": ["FEEL", "BECAUSE", "THINK"],
            "b sometimes a person thinks for a long time:": ["QUANTITY", "WHEN", "THINK", "LONG_TIME"],
            "c something very bad is happening to me": ["INTENSITY", "BAD", "HAPPEN"],
            "d I don't want this to be happening": ["NOT", "WANT", "HAPPEN"],
            "e I can't think: I will do something because of this": ["NOT", "CAN", "THINK", "DO", "BECAUSE"],
            "f I can't do anything": ["NOT", "CAN", "DO"],
            "g I can't not think about this": ["NOT", "CAN", "THINK"],
            "h when this person thinks this this person feels something very bad": ["WHEN", "THINK", "FEEL", "INTENSITY", "BAD"],
            "i X felt something like this": ["FEEL", "LIKE"],
            "j because X thought something like this": ["BECAUSE", "THINK", "LIKE"],
        },
        "feeling": "h",
        "links": ["a", "j"],
        "head": "SOMETHING",
    },
}
# Controls for the typed GOOD field of the E5/E6 classes: the published feeling line and the value it gives.
GOOD_FIELD_CONTROLS = {
    "concerned": {
        "row": "19_adjective",
        "expected": "empty",
        "source": "W1999 p.86 (page image checked); W1990b p.373 'because of this, this person feels something'",
        "feeling_line": "(g) when this person thinks this this person feels something",
    },
    "concern": {
        "row": "21_noun",
        "expected": "empty",
        "source": "W1999 p.86, headed 'Concern (X was concerned)': one block for both forms, framed as the adjective",
        "feeling_line": "(g) when this person thinks this this person feels something",
    },
    "worried": {
        "row": "19_adjective",
        "expected": "-1",
        "source": "W1999 p.85 (page image checked); W1990b p.372",
        "feeling_line": "(h) when this person thinks this this person feels something bad",
    },
    "alarmed": {
        "row": "19_adjective",
        "expected": "-1",
        "source": "W1999 p.81 (page image checked)",
        "feeling_line": "(h) when this person thinks this this person feels something bad",
    },
    "anguish": {
        "row": "21_noun",
        "expected": "-1",
        "source": "W1990b p.371 (page image checked)",
        "feeling_line": "because of this, this person feels something bad",
    },
    "horrified": {
        "row": "19_adjective",
        "expected": "-1",
        "source": "W1999 p.79 (page image checked)",
        "feeling_line": "(g) when this person thinks this this person feels something very bad",
    },
    "petrified": {
        "row": "19_adjective",
        "expected": "-1",
        "source": "W1999 p.77 (page image checked)",
        "feeling_line": "(i) when this person thinks this this person feels something very bad",
    },
}
SURPRISE_VALENCE = {  # Goddard 2015 [A]-[D]: the feeling line's quality
    "amazed": "+1 ('felt something good', [B]); W1992's 'surprise or amazement do not imply anything good or bad' is superseded (precedence rule)",
    "shocked": "-1 ('felt something bad', [D]; W1999 p.97 agrees)",
    "surprised": "empty ('felt something', [A])",
    "astonished": "empty ('felt something', [C])",
}
CONTROL_WORDS = sorted(
    {"afraid", "frightened", "nervous", "scared", "terrified", "sad", "happy", "mad", "dread", "fear", "hatred", "hate",
     "love", "stunned", "flabbergasted", "concerned", "concern", "worried", "alarmed", "anguish", "pity", "pleasure",
     "sadness", "sorrow", "apprehension", "terror", "horrified", "petrified"} | set(SURPRISE_VALENCE)
)


def gold_vector(entry: dict) -> tuple[dict[str, int], list[str]]:
    """Every prime enters as +1 (the alias map turns BAD into GOOD -1 and NOW into THEN -1), except that GOOD and
    BAD count only on the feeling line; an evaluation inside the thought is returned separately."""
    primes: dict[str, int] = {}
    thought_evaluations = []
    for line, names in entry["lines"].items():
        for name in names:
            if name in ("GOOD", "BAD") and line.split(" ", 1)[0] != entry["feeling"]:
                thought_evaluations.append(f"{name} in line {line.split(' ', 1)[0]}")
                continue
            primes[name] = 1
    vector = project(primes)
    for name in PERSON_SUBSTANTIVES + ("SOMETHING",) + RELATIONAL_SUBSTANTIVES:
        vector.setdefault(name, 1 if name == entry["head"] else 0)
    return vector, thought_evaluations


def agreement(cell: str, fixed: int | None, gold: dict[str, int], codes: dict[str, str]) -> str:
    if cell in codes:
        return codes[cell]
    value = gold.get(cell)
    if fixed is None:
        return "AGREES" if value is None else "CONTRADICTS"
    if fixed == 0:
        return "AGREES" if value in (None, 0) else "CONTRADICTS"
    if value is None:
        return "WRITTEN_BY_DEGREE_LAW_NOT_IN_EXPLICATION" if cell == "INTENSITY" else "NOT_IN_EXPLICATION"
    return "AGREES" if value == fixed else "CONTRADICTS"


def because_link(entry: dict) -> str:
    keys = {line.split(" ", 1)[0]: names for line, names in entry["lines"].items()}
    if any("BECAUSE" in keys[k] for k in entry["links"]):
        return "THOUGHT_AND_FEELING_LINKED_BY_BECAUSE"
    if any("BECAUSE" in names for names in keys.values()):
        return "BECAUSE_ONLY_INSIDE_THE_THOUGHT"
    return "NO_BECAUSE"


def main() -> int:
    population = json.loads((EVIDENCE / "emotion_population.json").read_text(encoding="utf-8"))["population"]
    entries = {(row, e["word"]): e for row, items in population.items() for e in items}
    membership = {kind: [] for kind in CLASSES}
    for (row, word), entry in sorted(entries.items()):
        membership[class_of(row, entry)].append(word)
    control = {
        word: [
            {"row": row, "class": class_of(row, e), "matching_tags": e["matching_tags"], "framenet_frames": e["framenet_frames"]}
            for (row, w), e in sorted(entries.items())
            if w == word
        ]
        for word in CONTROL_WORDS
    }
    scenarios = {
        "with_3b_cause_fixed_option_A": {"extend": True, "cause_row": True},
        "with_3b_cause_open_option_B": {"extend": True, "cause_row": False},
        "without_3b_cause_fixed": {"extend": False, "cause_row": True},
        "without_3b_cause_open": {"extend": False, "cause_row": False},
    }
    report = {"basis": BASIS_ID, "coordinates": len(COORDINATES), "class_membership": membership, "classes": {}}
    for kind in CLASSES:
        recommended = reading_class(kind, **scenarios["with_3b_cause_fixed_option_A"])
        open_coordinates = [c for c in COORDINATES if c not in recommended]
        alternatives = {}
        for scenario, flags in scenarios.items():
            cells = reading_class(kind, **flags)
            alternatives[scenario] = {
                "fixed_count": len(cells),
                "open_count": len(COORDINATES) - len(cells),
                "left_open_compared_with_option_A": [c for c in COORDINATES if c in recommended and c not in cells],
            }
        report["classes"][kind] = {
            "population_words": len(membership[kind]),
            "with_3b_cause_fixed_option_A": {
                "fixed": {c: {"state": v, "source": s} for c, (v, s) in recommended.items()},
                "good": "fixed" if "GOOD" in recommended else GOOD_FIELD_NOTE,
                "open_by_bank": {
                    " ".join(BANKS[index][:3]) + " ...": [c for c in open_coordinates if BANK_OF[c] == index]
                    for index in range(len(BANKS))
                },
            },
            "counts_by_scenario": alternatives,
        }
    gold = {}
    for word, entry in GOLD.items():
        population_entry = entries[(entry["row"], word)]
        kind = class_of(entry["row"], population_entry)
        vector, thought_evaluations = gold_vector(entry)
        recommended = reading_class(kind, extend=True, cause_row=True)
        fixed: dict[str, int | None] = {}
        for c, (v, _) in recommended.items():
            fixed[c] = pole_of(population_entry) if isinstance(v, str) else v
        open_coordinates = [c for c in COORDINATES if c not in recommended]
        gold[word] = {
            "source": entry["source"],
            "class": kind,
            "explication_lines": entry["lines"],
            "feeling_line": entry["feeling"],
            "evaluations_inside_the_thought": thought_evaluations,
            "because": because_link(entry),
            "written_coordinates": dict(sorted(vector.items())),
            "fixed_cells_check": {c: agreement(c, fixed[c], vector, entry.get("codes", {})) for c in recommended},
            "open_coordinates_with_content": sorted(c for c in open_coordinates if vector.get(c) not in (None, 0)),
            "open_coordinates_silent_in_the_explication": sorted(c for c in open_coordinates if c not in vector),
            **({"note": entry["note"]} if "note" in entry else {}),
        }
    report["gold_from_published_explications"] = gold
    afraid = gold["afraid"]
    report["note_on_fixed_cells_vs_gold"] = (
        "Not a held-out test: the fixed cells were drawn from these same explications, so agreement shows only "
        "that the rows don't contradict their sources. INTENSITY +1 comes from row 5's degree law (F125); "
        "WRITTEN_BY_DEGREE_LAW_NOT_IN_EXPLICATION marks explications with no VERY. CAN and HAPPEN are fixed only "
        "for Fear readings; sad, concerned, sadness and sorrow must find theirs through their own fields."
    )
    report["projection_choices_in_the_gold"] = [
        "Every non-substantive prime an explication contains is written for the word, whatever its scope in the "
        "explication, except GOOD (next).",
        "GOOD is the felt valence (Q1). It is read from the feeling line only ('feels something good/bad'); a feeling "
        "line with no quality leaves GOOD empty. An evaluation inside the thought stays in the derivation.",
        "Substantives are roles unless they head the word's own denotation (Q2).",
        "'know if' is written as IF, though CH's IF box shows only conditionals.",
        "'now' is the THEN/NOW coordinate at -1.",
        "'sometimes' (CH: a portmanteau of a quantifier and time) is QUANTITY and WHEN; 'some' is QUANTITY.",
        "'will' and the past tense ('happened') write nothing; neither is a prime.",
        "'think like this', 'like this' and 'feels like this' count as LIKE.",
        "'this', 'these' have no coordinate (THIS is not in the basis).",
        "'very' writes INTENSITY: the basis has no VERY, and F125 makes INTENSITY the mark of degree-bearing "
        "content, 'not very bad' included.",
        "'maybe' writes MAYBE; 'can', 'can't' and 'could' write CAN, with NOT for the negation.",
        "'have to' writes NOT and CAN: the chart glosses it as 'can't not'.",
        "'would' writes IF: W1992's prime list pairs them as one meta-predicate ('if/would'). Only W1990b's "
        "frightened uses it here.",
        "'for some time' writes nothing ((FOR) SOME TIME has no coordinate); 'for a long time' writes LONG_TIME.",
        "Under option B of the CAUSE decision, each 'because' is sorted: CAUSE when a causer's DO or HAPPEN brings "
        "about a change in another participant, BECAUSE otherwise. Every 'because' in these explications is a "
        "thought-to-feeling or reason link, so the gold is the same under A and B; under B, CAUSE is one more open field.",
    ]
    report["unproven_versus_uncertain"] = (
        f"An open field is unproven, not necessarily uncertain: "
        f"{len(afraid['open_coordinates_silent_in_the_explication'])} of afraid's "
        f"{len(afraid['open_coordinates_silent_in_the_explication']) + len(afraid['open_coordinates_with_content'])} "
        "open coordinates are silent in its published explication, and stay open only until a scoped silence law "
        "(F101, checked against the explications) proves it for the class. That leaves afraid "
        f"{len(afraid['open_coordinates_with_content'])} real choices."
    )
    report["good_field_controls"] = {
        word: {
            **control,
            "class": class_of(control["row"], entries[(control["row"], word)]),
            "check": (
                "GOOD_IS_A_FIELD_IN_THIS_CLASS"
                if class_of(control["row"], entries[(control["row"], word)]) not in GOOD_BY_CLASS
                else "CONTROL_NOT_IN_A_FIELD_CLASS"
            ),
        }
        for word, control in GOOD_FIELD_CONTROLS.items()
    }
    report["surprise_valence_gold"] = SURPRISE_VALENCE
    report["control_word_membership"] = control
    Path(sys.argv[1]).write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
