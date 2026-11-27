"""The verified NSM explications, templates and molecules compiled into positive content (rebuild tasks 4-5).

Rohan, 2026-11-25 08:06: "You can't define a thing only by what it's not." 2026-11-26 02:35: a positive definition
can never be assembled through exclusion, so these records are the main source of positive content. 16:27: "the work
done in these books should be extended in ways that are relevant and useful".

The rules, as decided (the lead's brief of 2026-11-26):

1. Binding. An explication binds to the readings of its explicated lemma and the part of speech its frame shows
   (`nsm_frames`). One reading in the cohort: its content is a restriction on that reading. Several: the head line's
   category types them (`nsm_typing`, the lead's refinement of 2026-11-26). One typed reading takes a restriction,
   several an obligation over those only, none an obligation over all of them (`UNTYPED`); content is never copied
   onto each.
2. Content. Each prime exponent in the explication gives its bank the pole the chart says (bad gives GOOD -1).
   Forms come from the chart's boxes, matched as whole words; the bank mappings are the chart's `_EXACT`,
   `_ADAPTED` and `_METADATA`. Lower-case one-letter words are never exponents. The head line's category formula
   ("of one kind", "of this kind"), deictic THIS and the copula give nothing. "like this" is LIKE. The logical
   operators are content.
3. Head record. Substantive banks are written only from the head line, the first line of the explication, which
   says what the thing is. Substantives elsewhere are participants and give nothing.
4. An explication writes no zero and no silence; banks it does not mention are untouched.
5. Molecules. A head line "X [m] of one kind" carries the molecule X's own content, compiled from X's explication,
   to the explicated word.
6. Templates. A template's content goes to the member lemmas the record itself lists. Wider field membership is
   recorded, never applied.
7. Records of kind "other" and cross-linguistic explications write nothing.

How the chart's forms are read in running text, where the rules needed a reading of the chart:

- Inflected forms match their exponent through WordNet morphy (feels, felt: FEEL; bodies: BODY; kinds: KIND).
  "could" is CAN's past and "another" is the chart's own OTHER frame ("at another time"); morphy knows neither.
- "n't" is the chart's DON'T, an allolex of NOT; "can't", "couldn't" and "cannot" are CAN and NOT. The chart's
  DON'T WANT unit maps to WANT -1, a pole the registry does not have (WANT is unpaired, F040). The founder-accepted
  fear contract reads "don't want" as NOT +1 and WANT +1, and that is how it is read here.
- A parenthesised word in a chart form is the frame the chart prints with the exponent: (HAVE) PARTS is PARTS,
  (IS) MINE is MINE, ON (ONE) SIDE is SIDE. BE (SOMEWHERE) and BE (SOMEONE/SOMETHING) are the exception: a form of
  be is BE only directly before "somewhere", "someone" or "something", and the complement is read as its own
  exponent. Any other form of be is the copula or an auxiliary.
- THE SAME, A SHORT TIME, A LONG TIME (with any "very" between, which is VERY), (FOR) SOME TIME and THERE IS are
  read as units, so their words are not read again as THE, SHORT, SOME or TIME. The TIME box's own frame "at some
  time" is SOME and TIME, not the duration unit.
- On a noun's head line, the substantives written are the head referent: the first substantive and its "of"
  complements, so a head naming the parts of a human body gives PART and BODY. A genitive ("someone's") is a
  participant, as the brief's own example has it, and so is a substantive in a predicate or a relative clause on
  the head line ("a kind of fruit that people grow": KIND, not PEOPLE). A verb's or an
  adjective's head line names participants only: the verb and modifier head laws (`bank_laws.json`) give those
  readings no substantive head.
- Two records that give one lemma and part of speech the same banks are one observation published twice (the
  same explication in an article and in a book): they share a `witness`, and the later one names the earlier as
  `same_as` in the receipt.
- The chart notes' portmanteaus (often, sometimes, such, well, everywhere) are not in the boxes and are not read.

The record text is copyrighted and stays in memory; the receipt holds source keys, line ranges, lemmas and banks.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from nltk.corpus import wordnet as wn

from GSE.curation.external_sources.nsm_chart_data import _ADAPTED, _CHART_BOXES, _EXACT, _METADATA, _MISSING

from . import guards, inheritance, inventory, laws, nsm_frames, nsm_text, nsm_typing
from .cells import BANK_INDEX, BANKS, BIPOLAR, NEG, POS, SILENT, ZERO, State
from .closure import Derivations, close
from .relations import Relation

RECORDS = Path("data/external/references/notes/explications")
COHORT = Path("data/lexicon_builder/rebuild/cohort.jsonl")
RECEIPT = Path("docs/verification/2026-11-26-rebuild-nsm-content.json")

SUBSTANTIVE = frozenset({"I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY", "KIND", "PART"})
BE_FORMS = frozenset({"be", "is", "are", "was", "were", "am", "been", "being"})
_STATES = (POS, NEG, ZERO, SILENT)
_SIGN_BIT = {+1: POS, -1: NEG}

# --- The chart's exponents ------------------------------------------------------------------------------------


def _poles() -> dict[str, tuple[str, int] | None]:
    """Each chart unit's bank and pole; None for a unit with no bank."""
    poles: dict[str, tuple[str, int] | None] = {key: (bank, +1) for key, bank in _EXACT.items()}
    poles |= {key: (bank, sign) for key, (bank, sign, _) in _ADAPTED.items()}
    poles |= {key: ((bank, +1) if bank else None) for key, (bank, _) in _METADATA.items()}
    poles |= {key: None for key in _MISSING}
    poles["this"] = None  # deictic THIS: no bank (decided)
    poles["dont-want"] = None  # read as NOT + WANT (module docstring)
    for key, pole in poles.items():
        if pole is None:
            continue
        bank, sign = pole
        if bank not in BANK_INDEX or (sign == -1 and bank not in BIPOLAR):
            raise ValueError(f"CHART_POLE_NOT_IN_REGISTRY {key} {pole}")
    return poles


POLES = _poles()

_CORE = {"(have) parts": "parts", "(is) mine": "mine", "on (one) side": "side"}
_SEQUENCES = {
    "the same": ("the", "same"),
    "a short time": ("a", "short", "time"),
    "a long time": ("a", "long", "time"),
    "(for) some time": ("some", "time"),
    "there is": ("there", BE_FORMS),
}
_BE_FRAMES = {"be (somewhere)": frozenset({"somewhere"}), "be (someone/something)": frozenset({"someone", "something"})}
_DECOMPOSED = {"don't want"}
_REALIZATIONS = {"could": "can", "another": "other"}


def _forms():
    single: dict[str, str] = {}
    sequences: list[tuple[str, tuple]] = []
    be_frames: list[tuple[str, frozenset]] = []
    multi = set()
    for key, _, forms, _ in _CHART_BOXES:
        for form in forms:
            f = nsm_text.normalise(form).replace("\n", "").lower()
            if f == "i":
                single["I"] = key
            elif " " not in f and "(" not in f:
                single[f] = key
            else:
                multi.add(f)
                if f in _CORE:
                    single[_CORE[f]] = key
                elif f in _SEQUENCES:
                    sequences.append((key, _SEQUENCES[f]))
                elif f in _BE_FRAMES:
                    be_frames.append((key, _BE_FRAMES[f]))
    declared = set(_CORE) | set(_SEQUENCES) | set(_BE_FRAMES) | _DECOMPOSED
    if multi != declared:
        raise ValueError(f"CHART_MULTIWORD_FORMS {sorted(multi ^ declared)}")
    sequences.sort(key=lambda s: -len(s[1]))
    return single, tuple(sequences), tuple(be_frames)


SINGLE, SEQUENCES, BE_FRAMES = _forms()


def _bases(word: str) -> set[str]:
    return {b for p in (wn.NOUN, wn.VERB, wn.ADJ) for b in wn._morphy(word, p)}


def _inflection_index() -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    for form, key in SINGLE.items():
        if form == "I":
            continue
        for b in _bases(form) | {form}:
            if len(b) > 1:
                index[b].add(key)
    return index


_BASE_UNITS = _inflection_index()


def unit_of(word: str) -> str | None:
    """The chart unit a single word realises, or None. An inflection shared by two units realises neither."""
    if word in SINGLE:
        return SINGLE[word]
    if len(word) == 1:
        return None
    if word in _REALIZATIONS:
        return SINGLE[_REALIZATIONS[word]]
    units = {k for b in _bases(word) | {word} for k in _BASE_UNITS.get(b, ())}
    return units.pop() if len(units) == 1 else None


# --- Content --------------------------------------------------------------------------------------------------


@dataclass
class Content:
    """An explication's positive content: bank -> the signs its exponents give it."""

    poles: dict[str, set[int]] = field(default_factory=lambda: defaultdict(set))
    units: Counter = field(default_factory=Counter)
    participants: int = 0
    copulas: int = 0

    def add(self, other: Content) -> None:
        for bank, signs in other.poles.items():
            self.poles[bank] |= signs

    def masks(self) -> dict[str, int]:
        return {bank: sum(_SIGN_BIT[s] for s in signs) for bank, signs in sorted(self.poles.items()) if signs}


def _formula_at(words: list[str], i: int) -> bool:
    return words[i : i + 3] in (["of", "one", "kind"], ["of", "this", "kind"])


def _sequence_at(line, i):
    """(unit, next index, positions of a VERY inside) for a chart unit read as a sequence at i.

    "at some time" is the TIME box's own frame ("at some times", "at some other time"), SOME and TIME, not the
    duration unit (FOR) SOME TIME."""
    for key, seq in SEQUENCES:
        if key == "some-time" and i and line[i - 1].word == "at":
            continue
        j, very = i, []
        for k, want in enumerate(seq):
            while k and j < len(line) and line[j].word == "very" and not line[j].molecule:
                very.append(j)
                j += 1
            ok = j < len(line) and not line[j].molecule
            ok = ok and (line[j].word in want if isinstance(want, frozenset) else line[j].word == want)
            if not ok:
                break
            j += 1
        else:
            return key, j, very
    return None


def _head_referent(line, noun: bool) -> set[int]:
    """Positions of the head line's head referent: its first substantive and that substantive's "of" chain."""
    if not noun:
        return set()
    span: set[int] = set()
    started = False
    for i, t in enumerate(line):
        key = None if t.molecule or t.variable else unit_of(t.word)
        substantive = key is not None and POLES.get(key) is not None and POLES[key][0] in SUBSTANTIVE
        if not started:
            if substantive and not t.genitive:
                started = True
                span.add(i)
            continue
        if substantive:
            if not t.genitive:
                span.add(i)
        elif not (t.molecule or t.genitive or t.word == "of" or t.word in nsm_frames.DETERMINERS):
            if t.word not in nsm_frames.MODIFIERS:
                break
    return span


def read_content(body: nsm_text.Body, noun: bool) -> Content:
    """The content of an explication's lines; substantives only from the head line of a noun (rule 3)."""
    out = Content()
    for li, line in enumerate(body.lines):
        words = [t.word for t in line]
        referent = _head_referent(line, noun) if li == 0 else set()
        i = 0
        while i < len(line):
            t = line[i]
            if t.molecule or t.variable:
                i += 1
                continue
            if li == 0 and _formula_at(words, i):
                i += 3
                continue
            hit = _sequence_at(line, i)
            if hit:
                key, i, very = hit
                _write(out, key, True)
                for _ in very:
                    _write(out, SINGLE["very"], True)
                continue
            if t.word in BE_FORMS:
                nxt = line[i + 1].word if i + 1 < len(line) else ""
                frame = next((key for key, complements in BE_FRAMES if nxt in complements), None)
                if frame:
                    _write(out, frame, True)
                else:
                    out.copulas += 1
                i += 1
                continue
            key = unit_of(t.word)
            if key is not None:
                _write(out, key, i in referent)
            i += 1
    return out


def _write(out: Content, key: str, in_referent: bool) -> None:
    pole = POLES.get(key)
    out.units[key] += 1
    if pole is None:
        return
    bank, sign = pole
    if bank in SUBSTANTIVE and not in_referent:
        out.participants += 1
        return
    out.poles[bank].add(sign)


def molecule_head(body: nsm_text.Body) -> str | None:
    """The molecule X of a head line "X [m] of one kind", as a noun lemma (rule 5)."""
    head = body.head
    i = 1 if head and head[0].word in {"a", "an"} else 0
    if i < len(head) and head[i].molecule and [t.word for t in head[i + 1 : i + 4]] == ["of", "one", "kind"]:
        return nsm_frames.base(head[i].word, "noun") or head[i].word
    return None


def head_category(body: nsm_text.Body, noun: bool) -> str | None:
    """The category the head line types its word by, as a noun lemma (`nsm_typing`).

    It is the head line's first molecule or noun exponent (a substantive or WORDS), outside the category formula
    and not a genitive: "creatures [m] ..." is creature, a head naming parts of a body is part. In "a kind of
    stuff" KIND is read through to the noun after it. A predicate's head line has no category."""
    if not noun:
        return None
    line = body.head
    words = [t.word for t in line]
    i = 0
    while i < len(line):
        if _formula_at(words, i):
            i += 3
            continue
        t = line[i]
        if t.molecule:
            return nsm_frames.base(t.word, "noun") or t.word
        key = None if t.genitive or t.variable else unit_of(t.word)
        if key in _NOUN_UNITS and not (key == "kinds" and i + 1 < len(line) and words[i + 1] == "of"):
            return nsm_frames.base(t.word, "noun") or t.word
        i += 1
    return None


_NOUN_UNITS = frozenset(k for k, p in POLES.items() if p and p[0] in SUBSTANTIVE) | {"words"}
# The noun lemmas of the chart's SOMETHING~THING forms: the most general category, which types nothing.
MOST_GENERAL = frozenset(nsm_frames.base(f, "noun") or f for f, k in SINGLE.items() if k == "something")


# --- Records --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Record:
    source: str
    start: int
    end: int
    explicates: str
    kind: str
    text: str

    @property
    def key(self) -> str:
        return f"{self.source}:{self.start}-{self.end}"


def load_records(directory: Path = RECORDS) -> tuple[Record, ...]:
    out = []
    for path in sorted(directory.glob("*.verified.jsonl")):
        with path.open(encoding="utf-8") as src:
            for line in src:
                r = json.loads(line)
                out.append(Record(r["source"], r["start_line"], r["end_line"], r["explicates"], r["kind"], r["text"]))
    return tuple(out)


def records_digest(directory: Path = RECORDS) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.glob("*.verified.jsonl"))}


# --- Output ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class Obligation:
    """At least one of `rows` has all of `banks` in `states` together. A joint obligation (`joint`) is over two or
    more banks; each of its banks also has a single-bank obligation. Obligations that share a `witness` come from one
    source observation, so one reading can satisfy them all."""

    rule_id: str
    banks: tuple[str, ...]
    states: tuple[int, ...]
    rows: np.ndarray
    joint: bool
    witness: int

    @property
    def bank(self) -> str:
        if self.joint:
            raise AttributeError("JOINT_OBLIGATION_HAS_NO_SINGLE_BANK")
        return self.banks[0]

    @property
    def allowed(self) -> int:
        if self.joint:
            raise AttributeError("JOINT_OBLIGATION_HAS_NO_SINGLE_BANK")
        return self.states[0]


@dataclass
class Compiled:
    """Restrictions (cell rows[i], cols[i] keeps allowed[i], by rule rules[i]), obligations and the receipt."""

    rule_ids: tuple[str, ...]
    warrants: tuple[str, ...]
    rows: np.ndarray
    cols: np.ndarray
    allowed: np.ndarray
    rules: np.ndarray
    obligations: tuple[Obligation, ...]
    receipt: tuple[dict, ...]

    def __len__(self) -> int:
        return int(self.rows.size)


def label(mask: int) -> str:
    return "|".join(n for b, n in ((POS, "+1"), (NEG, "-1"), (ZERO, "0"), (SILENT, "SILENT")) if mask & b)


class _Writer:
    def __init__(self, readings):
        self.index: dict[tuple[str, str], list[int]] = defaultdict(list)
        self.pos_index: dict[str, set[str]] = defaultdict(set)
        for row, r in enumerate(readings):
            self.index[(r.lemma, r.pos)].append(row)
            self.pos_index[r.lemma].add(r.pos)
        self.rule_ids: list[str] = []
        self.warrants: list[str] = []
        self.restrictions: list[tuple[int, int, int, int]] = []
        self.obligations: list[Obligation] = []
        self.observations: dict[tuple, tuple[int, str]] = {}
        self.aligner = nsm_typing.Aligner(readings, self.index, MOST_GENERAL)

    def bind(self, rule_id: str, warrant: str, lemma: str, pos: str, masks: dict[str, int], category=None) -> dict:
        """Rule 1 with the typed alignment proof (`nsm_typing`): a restriction on the one reading (or the one the
        head category types), an obligation over the typed readings, or over all of them, `UNTYPED`."""
        rows = self.index.get((lemma, pos), [])
        entry = {"rule_id": rule_id, "lemma": lemma, "pos": pos, "readings": len(rows)}
        if not rows:
            return entry | {"disposition": "UNSUPPORTED", "reason": "NOT_IN_COHORT"}
        if not masks:
            return entry | {"disposition": "UNSUPPORTED", "reason": "NO_CONTENT"}
        rule = len(self.rule_ids)
        self.rule_ids.append(rule_id)
        self.warrants.append(warrant)
        observation = (lemma, pos, tuple(sorted(masks.items())))
        witness, first = self.observations.setdefault(observation, (rule, rule_id))
        if first != rule_id:
            entry["same_as"] = first
        if len(rows) == 1:
            self.restrictions.extend((rows[0], BANK_INDEX[b], m, rule) for b, m in masks.items())
            return entry | {"disposition": "RESTRICTION", "reading": rows[0]}
        typed = self.aligner.type(category, rows)
        entry["typing"] = typed.receipt()
        if typed.rows:
            self.warrants[rule] = f"{warrant}, typed by the head category {typed.category}"
        if len(typed.rows) == 1:
            self.restrictions.extend((typed.rows[0], BANK_INDEX[b], m, rule) for b, m in masks.items())
            return entry | {"disposition": "RESTRICTION", "reading": typed.rows[0]}
        members = np.array(typed.rows or rows, dtype=np.int64)
        banks = tuple(masks)
        if len(banks) > 1:
            self.obligations.append(Obligation(rule_id, banks, tuple(masks[b] for b in banks), members, True, witness))
        self.obligations.extend(Obligation(rule_id, (b,), (masks[b],), members, False, witness) for b in banks)
        disposition = "OBLIGATION" if typed.rows else "UNTYPED"
        return entry | {"disposition": disposition, "joint": len(banks) > 1, "rows": int(members.size)}

    def output(self, receipt) -> Compiled:
        r = np.array(self.restrictions, dtype=np.int64).reshape(-1, 4)
        return Compiled(
            rule_ids=tuple(self.rule_ids),
            warrants=tuple(self.warrants),
            rows=r[:, 0],
            cols=r[:, 1],
            allowed=r[:, 2].astype(np.uint8),
            rules=r[:, 3].astype(np.int32),
            obligations=tuple(self.obligations),
            receipt=tuple(receipt),
        )


@dataclass
class _Read:
    record: Record
    body: nsm_text.Body
    frame: nsm_frames.Frame
    content: Content
    molecule: str | None


def _read(record: Record, pos_index) -> _Read:
    body = nsm_text.read(record.text, record.explicates)
    lines = nsm_text.lines_text(record.text)
    language = nsm_frames.language(record.source, record.start, record.explicates)
    if language:
        frame = nsm_frames.Frame("CROSS_LINGUISTIC", supported=False, language=language)
    elif body.embedded:
        frame = nsm_frames.Frame("EMBEDDED_IN_PROSE", supported=False)
    else:
        frame = nsm_frames.of_record(record.source, record.start, record.explicates, lines, body.head, pos_index)
    content = read_content(body, noun=frame.pos == "noun") if frame.supported else Content()
    molecule = molecule_head(body) if frame.supported and frame.pos == "noun" else None
    return _Read(record, body, frame, content, molecule)


def _carried(name: str, by_lemma: dict, reads: dict, source: str, seen: frozenset) -> tuple[Content, list[str]]:
    """The molecule's own content (its explication, with whatever that explication carries in turn)."""
    keys = by_lemma.get(name, [])
    same = [k for k in keys if reads[k].record.source == source]
    chosen = same or keys
    out, used = Content(), []
    for k in chosen:
        if k in seen:
            continue
        out.add(reads[k].content)
        used.append(k)
        inner = reads[k].molecule
        if inner:
            more, inner_used = _carried(inner, by_lemma, reads, reads[k].record.source, seen | {k})
            out.add(more)
            used.extend(inner_used)
    return out, used


def _warrant(record: Record, lemma: str, pos: str, frame: str) -> str:
    return f"NSM {record.source} lines {record.start}-{record.end}: {record.kind} of {lemma} ({pos}), frame {frame}"


def _template(record: Record, w: _Writer) -> dict:
    raw = nsm_text.clean_lines(record.text)
    lines = nsm_text.lines_text(record.text)
    members = nsm_frames.template_members(record.explicates, raw)
    pos = nsm_frames.template_pos(lines)
    entry = {"field_named": bool(nsm_frames.template_field(record.explicates)), "field_applied": False}
    content = read_content(nsm_text.read(record.text, record.explicates), noun=False)
    masks = content.masks()
    entry |= {"banks": {b: label(m) for b, m in masks.items()}, "participants": content.participants}
    if not members:
        return entry | {"disposition": "UNSUPPORTED", "reason": "TEMPLATE_NO_MEMBERS"}
    if not masks:
        return entry | {"disposition": "UNSUPPORTED", "reason": "TEMPLATE_NO_CONTENT", "members": members}
    if not pos:
        return entry | {"disposition": "UNSUPPORTED", "reason": "TEMPLATE_POS_NOT_SHOWN", "members": members}
    bound = []
    for surface in members:
        lemma = nsm_frames.base(surface, pos) or surface
        bound.append(
            w.bind(f"nsm:{record.key}:{lemma}", _warrant(record, lemma, pos, "TEMPLATE_MEMBER"), lemma, pos, masks)
        )
    return entry | {"disposition": "TEMPLATE", "pos": pos, "members": bound}


def compile_records(records, readings) -> Compiled:
    """Every record's disposition, its restrictions and its obligations over `readings` (the cohort)."""
    w = _Writer(readings)
    reads = {r.key: _read(r, w.pos_index) for r in records if r.kind in {"explication", "molecule"}}
    by_lemma: dict[str, list[str]] = defaultdict(list)
    for k, rd in reads.items():
        if rd.frame.supported and rd.frame.pos == "noun":
            by_lemma[rd.frame.lemma].append(k)
    receipt = []
    for record in records:
        entry = {"source": record.source, "start_line": record.start, "end_line": record.end, "kind": record.kind}
        if record.kind == "other":
            receipt.append(entry | {"disposition": "OTHER"})
            continue
        if record.kind == "template":
            receipt.append(entry | _template(record, w))
            continue
        rd = reads[record.key]
        f = rd.frame
        entry |= {"frame": f.frame, "lemma": f.lemma, "pos": f.pos, "sense": f.sense}
        if not f.supported:
            if f.frame == "CROSS_LINGUISTIC":
                receipt.append(entry | {"disposition": "CROSS_LINGUISTIC", "language": f.language})
            else:
                receipt.append(entry | {"disposition": "UNSUPPORTED", "reason": f.frame})
            continue
        content = Content()
        content.add(rd.content)
        own = rd.content.masks()
        if rd.molecule:
            carried, used = _carried(rd.molecule, by_lemma, reads, record.source, frozenset({record.key}))
            content.add(carried)
            entry["molecule"] = {
                "lemma": rd.molecule,
                "from": used,
                "banks": {b: label(m) for b, m in carried.masks().items()},
            }
        masks = content.masks()
        category = head_category(rd.body, f.pos == "noun")
        entry |= {
            "head_category": category or "",
            "banks": {b: label(m) for b, m in masks.items()},
            "own_banks": len(own),
            "participants": rd.content.participants,
            "copulas": rd.content.copulas,
            "title_found": rd.body.title_found,
        }
        rule_id = f"nsm:{record.key}"
        warrant = _warrant(record, f.lemma, f.pos, f.frame)
        receipt.append(entry | w.bind(rule_id, warrant, f.lemma, f.pos, masks, category))
    return w.output(receipt)


# --- Closure --------------------------------------------------------------------------------------------------


def restriction_relations(compiled: Compiled, n: int) -> tuple[tuple[Relation, ...], dict[str, np.ndarray]]:
    """Each (rule, bank, mask) as a one-bank relation over the reading it restricts, so closure names the NSM
    record as the cause and wakes the laws that read the bank."""
    relations, scopes = [], {}
    keys = np.stack([compiled.rules.astype(np.int64), compiled.cols, compiled.allowed.astype(np.int64)])
    for rule, col, mask in np.unique(keys, axis=1).T if keys.size else ():
        rule_id, bank = compiled.rule_ids[rule], BANKS[col]
        scope = f"{rule_id}:{bank}:{label(int(mask))}"
        chosen = (keys[0] == rule) & (keys[1] == col) & (keys[2] == mask)
        scopes[scope] = np.zeros(n, dtype=bool)
        scopes[scope][compiled.rows[chosen]] = True
        allowed = tuple((s,) for s in _STATES if int(mask) & s)
        relations.append(Relation(rule_id, (bank,), allowed, compiled.warrants[rule], scope))
    return tuple(relations), scopes


def _obligation_status(state: State, obligations) -> dict[str, int]:
    """How many obligations the closed state leaves open, forcing (one reading fits) or in conflict (none fits)."""
    out = Counter()
    for o in obligations:
        cols = [BANK_INDEX[b] for b in o.banks]
        fits = np.ones(o.rows.size, dtype=bool)
        for c, s in zip(cols, o.states):
            fits &= (state.masks[o.rows, c] & s) != 0
        n = int(fits.sum())
        kind = "joint" if o.joint else "single"
        out[f"{kind}:{'conflict' if n == 0 else 'forcing' if n == 1 else 'open'}"] += 1
    return dict(sorted(out.items()))


def closure_round(readings, compiled: Compiled) -> dict:
    """The authored laws alone, then the laws with the NSM restrictions: census and H of each."""
    ids = [r.reading_id for r in readings]
    law_relations = laws.compile_laws()
    wanted = {r.scope for r in law_relations}
    opening = State.opening(ids).census()
    laws_only = State.opening(ids)
    laws_receipt = close(laws_only, law_relations, guards.scopes(readings, wanted))
    nsm_relations, nsm_scopes = restriction_relations(compiled, len(ids))
    state = State.opening(ids)
    derivations = Derivations()
    receipt = close(state, law_relations + nsm_relations, guards.scopes(readings, wanted) | nsm_scopes, derivations)
    d = derivations.arrays()
    by_rule = Counter(d["rule_ids"][d["rules"]].tolist()) if d["rules"].size else Counter()
    nsm_removals = sum(c for rule, c in by_rule.items() if rule.startswith("nsm:"))
    decided, before = state.counts() == 1, laws_only.counts() == 1
    newly = decided & ~before
    conflict_rows, conflict_cols = np.nonzero(state.counts() == 0)
    return {
        "opening": opening,
        "laws_only": laws_only.census() | {"seconds": laws_receipt["seconds"]},
        "laws_and_nsm": state.census() | {k: receipt[k] for k in ("relations", "applications", "removals", "seconds")},
        "bits_removed_by_nsm": laws_only.bits() - state.bits(),
        "nsm_removals": nsm_removals,
        "newly_decided_by_bank": {BANKS[c]: int(k) for c, k in enumerate(newly.sum(axis=0)) if k},
        "conflicts": [[ids[r], BANKS[c]] for r, c in zip(conflict_rows, conflict_cols)],
        "obligations_after_closure": _obligation_status(state, compiled.obligations),
    }


# --- Summary --------------------------------------------------------------------------------------------------


_BOUND = {"RESTRICTION", "OBLIGATION", "UNTYPED"}


def bindings(receipt):
    """Every binding in the receipt: a record's own, and each template member's."""
    for e in receipt:
        if "rule_id" in e:
            yield e
        for m in e.get("members", []):
            if isinstance(m, dict):
                yield m


def typing_summary(receipt) -> dict:
    """What the typed alignment did to the bindings over two or more readings."""
    outcome, categories, untyped = Counter(), defaultdict(Counter), Counter()
    before = after = outside = 0
    narrowing = []
    for b in bindings(receipt):
        t = b.get("typing")
        if t is None:
            continue
        kind = {"RESTRICTION": "restriction", "OBLIGATION": "narrowed"}.get(b["disposition"], "untyped")
        outcome[kind] += 1
        categories[t["category"] or "-"][kind] += 1
        if kind == "untyped":
            untyped[t["reason"]] += 1
            continue
        rows = 1 if kind == "restriction" else b["rows"]
        before, after, outside = before + b["readings"], after + rows, outside + t["outside_wordnet"]
        narrowing.append([b["readings"], rows])
    return {
        "bindings": sum(outcome.values()),
        "outcome": dict(sorted(outcome.items())),
        "untyped_by_reason": dict(sorted(untyped.items())),
        "typed_rows_before": before,
        "typed_rows_after": after,
        "outside_wordnet_left_out": outside,
        "by_category": {c: dict(sorted(k.items())) for c, k in sorted(categories.items())},
        "typed_readings_before_after": sorted(narrowing),
    }


def typing_check(compiled: Compiled, readings) -> dict:
    """An independent check that every typed row lies in its category's WordNet subtree. The subtree is computed
    downward from the hub (hyponyms and instance hyponyms), not by the upward ancestry the typing used."""
    synset = {row: name for name, rows in inheritance.wordnet_groups(readings).items() for row in rows}
    nouns: dict[str, list[int]] = defaultdict(list)
    for row, r in enumerate(readings):
        if r.pos == "noun":
            nouns[r.lemma].append(row)
    obligation_rows = {o.rule_id: set(o.rows.tolist()) for o in compiled.obligations}
    subtrees: dict[str, set[str]] = {}
    checked, outside = 0, []
    for b in bindings(compiled.receipt):
        t = b.get("typing")
        if not t or b["disposition"] not in {"RESTRICTION", "OBLIGATION"}:
            continue
        category = t["category"]
        if category not in subtrees:
            hub = {synset[r] for r in nouns[category] if r in synset}
            down = lambda s: s.hyponyms() + s.instance_hyponyms()  # noqa: E731
            subtrees[category] = hub | {h.name() for name in hub for h in wn.synset(name).closure(down)}
        rows = {b["reading"]} if b["disposition"] == "RESTRICTION" else obligation_rows[b["rule_id"]]
        for row in sorted(rows):
            checked += 1
            if synset.get(row) not in subtrees[category]:
                outside.append([b["rule_id"], readings[row].reading_id, category])
    return {"typed_rows_checked": checked, "outside_subtree": outside}


def summary(compiled: Compiled) -> dict:
    """Dispositions, restrictions and obligations by bank, typing, and the lemmas that bind and do not."""
    dispositions = Counter()
    bound, unbound = Counter(), Counter()
    for e in compiled.receipt:
        dispositions[e["disposition"] + (f":{e['reason']}" if "reason" in e else "")] += 1
        for b in e.get("members", []) if isinstance(e.get("members"), list) else []:
            if isinstance(b, dict):
                (bound if b["disposition"] in _BOUND else unbound)[f"{b['lemma']}/{b['pos']}"] += 1
        if e.get("lemma"):
            (bound if e["disposition"] in _BOUND else unbound)[f"{e['lemma']}/{e['pos'] or '?'}"] += 1
    restrictions = Counter(f"{BANKS[c]}:{label(int(m))}" for c, m in zip(compiled.cols, compiled.allowed))
    single = Counter(f"{o.banks[0]}:{label(o.states[0])}" for o in compiled.obligations if not o.joint)
    joint = [o for o in compiled.obligations if o.joint]
    return {
        "records": len(compiled.receipt),
        "dispositions": dict(sorted(dispositions.items())),
        "rules": len(compiled.rule_ids),
        "restrictions": len(compiled),
        "restricted_readings": int(np.unique(compiled.rows).size),
        "restrictions_by_bank": dict(sorted(restrictions.items())),
        "obligations_single": sum(single.values()),
        "obligations_joint": len(joint),
        "obligations_single_by_bank": dict(sorted(single.items())),
        "joint_obligation_banks": sorted(len(o.banks) for o in joint),
        "typing": typing_summary(compiled.receipt),
        "bound_lemmas": dict(sorted(bound.items())),
        "unbound_lemmas": dict(sorted(unbound.items())),
    }


def main(argv=None) -> dict:
    started = time.perf_counter()
    readings = inventory.load(COHORT)
    records = load_records()
    compiled = compile_records(records, readings)
    out = {
        "format": "GSE.rebuild-nsm-content/1",
        "inputs": {
            "records": records_digest(),
            "cohort_readings": len(readings),
            "cohort_sha256": inventory.digest(readings),
        },
        "summary": summary(compiled),
        "typing_check": typing_check(compiled, readings),
        "closure_round": closure_round(readings, compiled),
        "records": list(compiled.receipt),
        "seconds": round(time.perf_counter() - started, 2),
    }
    RECEIPT.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=int) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    result = main()
    print(json.dumps({k: result[k] for k in ("summary", "closure_round", "seconds")}, indent=1, default=int))
