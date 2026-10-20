"""MultiScaleDoc — the shared multi-scale grounding substrate a cassette composes.

This is the load-bearing object of the cassette architecture. A cassette is a CASSETTE: GSE is the
player, the cassette is the tape. GSE alone tops out at the SINGLE-SENTENCE scale (parse + set-theory
+ LSAT) — the ceiling of meaning extractable from isolated literal text. The MULTI-SCALE architecture
is the advanced reasoning, and a cassette is ENTIRELY CONTINGENT on it: it resolves an in-frame
uncertainty using OUT-OF-FRAME context. So the cassette never re-grounds anything — it reads the
LITERAL RAW TEXT once through GSE's existing grounding and exposes the four scales for the cassette to
converge over. (See ``~/Genesis/docs/CASSETTE_ARCHITECTURE_DESIGN_BRIEF.md``.)

The four scales, each a view built from the same raw-text pass:

  word      — each token's MEANING: NSM ``word_primitives``, WordNet/world ``type_thread`` (per Atom/Entity).
  sentence  — the structural parse (the resolved predicate trees) — the GSE ceiling.
  paragraph — ``window(t, k)``: the ±k-line cis-regulatory neighborhood (recent referents, the
              dropped/ambiguous subject) — where "who is the agent of this verb" is actually decided.
  document  — ``fold[id]``: ``read_fold``'s per-entity recurrence × timeline-span, role, eligibility,
              and which strands voted it real — the protagonist/role signal across the whole text.

ALL existing GSE machinery, composed: ``resolve_document`` (coref + type_thread), ``read_fold`` (the
multi-strand fold-reader = the working model of cross-scale convergence), the ``GenealogyStore`` world
strand. Nothing here re-implements grounding; it assembles the scales a cassette votes over.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from gse.api import GSEEncoder
from gse.discourse.intake import document_sentences
from gse.discourse.speech import encode_document_utterance_events
from gse.symbolic import GenealogyStore, resolve_document
from gse.symbolic.expression import Atom
from gse.symbolic.healer.fold_reader import EntityFold, read_fold
from gse.symbolic.healer.treewalk import walk
from gse.symbolic.narrative import _collect_predicates
from gse.symbolic.resolution import Entity

_GENRE_RE = re.compile(r"^\s*GENRE\s*:\s*(NARRATIVE|EXPOSITORY|ARGUMENTATIVE)\b", re.I | re.M)
_SCAFFOLD = re.compile(r"^(GENRE|TITLE|CONTEXT|WIKIPEDIA|WEB RESULTS)\s*:")

# Lexical (word-scale, DEFINITIONAL) gender of gender-marked kinship/title nouns and personal
# pronouns/determiners. This is a property of the WORD, not a story-specific table of names — it is
# the gender WordNet/the lexicon assigns to "husband" (a married man) etc. It is consumed only as ONE
# agreement strand in cross-scale convergence; it never names a referent on its own.
_MALE = frozenset(
    {
        "husband",
        "king",
        "father",
        "son",
        "lord",
        "man",
        "boy",
        "prince",
        "brother",
        "he",
        "him",
        "his",
        "himself",
        "uncle",
        "nephew",
        "widower",
        "sir",
        "duke",
        "thane",
    }
)
_FEMALE = frozenset(
    {
        "wife",
        "queen",
        "mother",
        "daughter",
        "lady",
        "woman",
        "girl",
        "princess",
        "sister",
        "she",
        "her",
        "hers",
        "herself",
        "aunt",
        "niece",
        "widow",
        "duchess",
    }
)
# type_thread roots that denote a person (the eligibility floor for an identity referent).
_PERSON_ROOTS = frozenset({"person", "individual", "someone", "soul", "relative", "kinsman"})
_NONPERSON_ROOTS = frozenset(
    {
        "place",
        "populatedplace",
        "settlement",
        "location",
        "region",
        "country",
        "city",
        "town",
        "village",
        "event",
        "societalevent",
        "militaryconflict",
        "work",
        "organisation",
        "organization",
        "language",
        "ethnicgroup",
        "social_group",
        "communication",
        "group",
        "animal",
        "plant",
    }
)


@dataclass(frozen=True)
class PersonEligibility:
    """Grounded person evidence; unknown and negative require different remedies."""

    code: str  # person | non_person | unknown
    evidence: Tuple[str, ...] = ()

    def __bool__(self):
        raise TypeError("PersonEligibility requires an explicit .code comparison")


@dataclass
class Mention:
    """One surface mention of a referent in the raw text — the unit a cassette reasons over.

    Carries everything the four scales expose for THIS mention, so a cassette never has to re-walk
    the tree: its document id (``eid``), its word-scale meaning (``type_thread``/``prims``), its local
    modifiers/possessor (paragraph-scale discriminators), and its sentence index (for the window)."""

    eid: Optional[str]
    lemma: str
    pos: Optional[str]
    sent: int  # sentence index — the paragraph-window coordinate
    type_thread: Tuple[str, ...] = ()
    prims: Dict[str, int] = field(default_factory=dict)
    number: Optional[str] = None
    modifier: Optional[str] = None  # the ADJ discriminator ("younger"/"elder") — the SPLIT signal
    graded: bool = False
    possessor_lemma: Optional[str] = None  # "his"/"her"/a name — the local agreement signal
    possessor_eid: Optional[str] = None  # the possessor entity's id (for relational resolution)
    possessor_span: Tuple[str, ...] = ()  # the possessor's demi-word ("Lady Macbeth" → lady,macbeth)
    span: Tuple[str, ...] = ()
    is_agent: bool = False  # appeared as an Event agent (a high-value identity referent)
    source_sentence_id: Optional[str] = None
    utterance_id: Optional[str] = None


def _strip_scaffold(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not _SCAFFOLD.match(ln))


def _sentences(text: str) -> List[str]:
    """GSE owns segmentation: split paragraphs on blank lines, collapse wrapped lines within a
    paragraph, then GSE's deterministic sentence splitter. (Mirrors the bridge's ``_sentences``.)"""
    return [unit.text for unit in document_sentences(_strip_scaffold(text))]


def _head_atom(node) -> Optional[Atom]:
    h = getattr(node, "head", None)
    return h if isinstance(h, Atom) else (node if isinstance(node, Atom) else None)


def _possessor_lemma(ent) -> Optional[str]:
    poss = getattr(ent, "possessor", None)
    if poss is None:
        return None
    h = _head_atom(poss)
    return h.lemma.lower() if h and h.lemma else None


class MultiScaleDoc:
    """Build the four-scale grounding of a raw document ONCE; expose it for cassettes to converge over.

    Pipeline (the existing GSE public surface, composed): per sentence
    ``evaluate_tree(resolve(from_trace(encoder.encode(s))))`` → the document-scope
    ``resolve_document(trees, store, genre)`` (cross-sentence coref + ``entity_id`` + ``type_thread``)
    → ``read_fold`` for the document-scale fold. Nothing is re-grounded."""

    def __init__(self, raw_text: str, encoder: Optional[GSEEncoder] = None, store: Optional[GenealogyStore] = None):
        self.raw = raw_text
        self.source_sentences = document_sentences(_strip_scaffold(raw_text))
        self.sentences = [unit.text for unit in self.source_sentences]
        m = _GENRE_RE.search(raw_text[:300])
        self.genre = m.group(1).upper() if m else None
        self.encoder = encoder or GSEEncoder()
        self.store = store if store is not None else _safe_store()

        # sentence scale — the resolved per-sentence predicate trees
        self.intake_events = list(encode_document_utterance_events(self.encoder, self.source_sentences))
        self.manifest = self.intake_events[0]
        self.utterance_outcomes = [event for event in self.intake_events if event["type"] == "utterance"]
        self.failures = [event for event in self.utterance_outcomes if event["state"] != "read"]
        successes = [event for event in self.utterance_outcomes if event["state"] == "read"]
        trees = [event["tree"] for event in successes]
        self.sentence_trees = list(trees)
        sentence_indices = {unit.id: index for index, unit in enumerate(self.source_sentences)}
        self._sent_of_tree: List[int] = []
        self.tree_sources: List[Dict[str, Any]] = []
        for index, event in enumerate(successes):
            self._sent_of_tree.append(sentence_indices[event["source_sentence_id"]])
            self.tree_sources.append(
                {
                    "tree_index": index,
                    "utterance_id": event["utterance_id"],
                    "source_sentence_id": event["source_sentence_id"],
                }
            )
        self.phases = {}
        expected = len(self.utterance_outcomes)
        state = "empty" if not expected else ("unread" if not trees else ("partial" if self.failures else "read"))
        self.phases["intake"] = {"state": state, "expected": expected, "read": len(trees), "failed": len(self.failures)}
        self.sentence_states = {}
        for unit in self.manifest["sentences"]:
            outcomes = [event for event in self.utterance_outcomes if event["source_sentence_id"] == unit["id"]]
            n_read = sum(event["state"] == "read" for event in outcomes)
            self.sentence_states[unit["id"]] = (
                "empty"
                if not outcomes
                else "unread"
                if not n_read
                else "read"
                if n_read == len(outcomes)
                else "partial"
            )
        try:
            self.resolved = resolve_document(trees, self.store, genre=self.genre, raw_text=raw_text) if trees else []
            self.phases["resolution"] = {"state": state, "error": None}
        except Exception as exc:
            self.resolved = trees
            self.phases["resolution"] = {"state": "unread", "error": _phase_error("resolution", exc)}

        # document scale — the multi-strand fold (recurrence × span, role, eligibility, strands)
        self.timed = []
        try:
            self.timed = [(t, p) for t, tree in enumerate(self.resolved) for p in _collect_predicates(tree)]
            self.fold: Dict[str, EntityFold] = read_fold(self.timed, None, self.store) if trees else {}
            self.phases["fold"] = {"state": state, "error": None}
            if self.phases["resolution"]["state"] == "unread" and trees:
                self.phases["fold"] = {"state": "unread", "error": {"code": "unresolved_document"}}
        except Exception as exc:
            self.fold = {}
            self.phases["fold"] = {"state": "unread", "error": _phase_error("fold", exc)}
        self.graph = None
        try:
            if trees and self.phases["resolution"]["state"] != "unread":
                from gse.symbolic.narrative import NarrativeGraph

                self.graph = NarrativeGraph.from_document(self.resolved, self.store, raw_text=raw_text)
                self.phases["graph"] = {"state": state, "error": None}
            else:
                self.phases["graph"] = {
                    "state": state if not trees else "unread",
                    "error": None if not trees else {"code": "unresolved_document"},
                }
        except Exception as exc:
            self.phases["graph"] = {"state": "unread", "error": _phase_error("graph", exc)}

        # word + paragraph scale — every mention, tagged with its sentence and its discriminators
        self.mentions: List[Mention] = []
        self.by_id: Dict[str, List[Mention]] = {}
        self._identity_links_cache: Optional[Dict[str, set]] = None
        self._index_mentions()

    # -- mention indexing ---------------------------------------------------
    def _agent_eids(self) -> set:
        from gse.symbolic.predicates import Event

        out = set()
        for _t, pred in self.timed:
            for n in walk(pred):
                if isinstance(n, Event):
                    ag = getattr(n, "agent", None)
                    eid = getattr(ag, "entity_id", None)
                    if eid:
                        out.add(eid)
        return out

    def _index_mentions(self) -> None:
        agents = self._agent_eids()
        for ti, tree in enumerate(self.resolved):
            sent = self._sent_of_tree[ti] if ti < len(self._sent_of_tree) else ti
            for n in walk(tree):
                if not isinstance(n, Entity):
                    continue
                h = _head_atom(n)
                if h is None or not h.lemma:
                    continue
                mod = getattr(n, "modifier", None)
                poss = getattr(n, "possessor", None)
                men = Mention(
                    eid=getattr(n, "entity_id", None),
                    lemma=h.lemma.lower(),
                    pos=h.pos,
                    sent=sent,
                    type_thread=tuple(getattr(n, "type_thread", ()) or ()),
                    prims=dict(getattr(h, "word_primitives", None) or {}),
                    number=getattr(h, "number", None),
                    modifier=(mod.lemma.lower() if isinstance(mod, Atom) and mod.lemma else None),
                    graded=bool(getattr(mod, "graded", False)) if isinstance(mod, Atom) else False,
                    possessor_lemma=_possessor_lemma(n),
                    possessor_eid=getattr(poss, "entity_id", None) if poss is not None else None,
                    possessor_span=tuple(getattr(poss, "span", ()) or ()) if poss is not None else (),
                    span=tuple(getattr(n, "span", ()) or ()),
                    is_agent=getattr(n, "entity_id", None) in agents,
                    source_sentence_id=self.tree_sources[ti]["source_sentence_id"],
                    utterance_id=self.tree_sources[ti]["utterance_id"],
                )
                self.mentions.append(men)
                if men.eid:
                    self.by_id.setdefault(men.eid, []).append(men)

    # -- the four-scale accessors a cassette composes -----------------------
    def window(self, sent: int, k: int = 2) -> List[Mention]:
        """The paragraph-scale ±k-line cis-neighborhood of a sentence — the recent referents that
        ground a dropped/ambiguous element. The ``±2`` of the design's ``±2-line`` neighborhood."""
        return [m for m in self.mentions if abs(m.sent - sent) <= k]

    def unit_view(self, *, paragraph_id: str | None = None, source_sentence_id: str | None = None) -> dict:
        """Select from the one document reading; retain out-of-unit antecedents.

        No encoding or resolution is performed. Supporting mentions carry their
        original source sentence and utterance IDs, including earlier paragraphs.
        """
        selected_ids = {
            unit.id
            for unit in self.source_sentences
            if (paragraph_id is None or unit.paragraph_id == paragraph_id)
            and (source_sentence_id is None or unit.id == source_sentence_id)
        }
        mentions = [mention for mention in self.mentions if mention.source_sentence_id in selected_ids]
        referents = {mention.eid for mention in mentions if mention.eid is not None}
        sources = [source for source in self.tree_sources if source["source_sentence_id"] in selected_ids]
        return {
            "source_sentence_ids": [unit.id for unit in self.source_sentences if unit.id in selected_ids],
            "tree_sources": sources,
            "trees": [self.resolved[source["tree_index"]] for source in sources],
            "mentions": mentions,
            "supporting_mentions": [
                mention
                for mention in self.mentions
                if mention.eid in referents and mention.source_sentence_id not in selected_ids
            ],
            "phases": self.phases,
        }

    def gender(self, m: Mention) -> Optional[str]:
        """Word-scale agreement gender of a mention: from its lexical gender (husband=m, wife=f), its
        possessor (his=m, her=f), or its type_thread roots. None = unknown → the agreement strand stays
        silent (it never fabricates a gender; an unknown gender simply does not license a merge)."""
        lemmas = {m.lemma} | set(m.span)
        if m.possessor_lemma:
            lemmas.add(m.possessor_lemma)
        if lemmas & _MALE:
            return "m"
        if lemmas & _FEMALE:
            return "f"
        for root in m.type_thread:
            if root in _MALE:
                return "m"
            if root in _FEMALE:
                return "f"
        return None

    def is_person(self, m: Mention) -> PersonEligibility:
        """Return person/non-person/unknown from grounded or definitional evidence.

        Proper-name syntax, recurrence, and ``fold.eligible`` establish neither
        personhood nor non-personhood. Conflicting accepted type evidence remains
        unknown. Other mentions with the same resolved ID can supply evidence.
        """
        mentions = [m] + list(self.by_id.get(m.eid or "", []))
        roots = {root.lower() for mention in mentions for root in mention.type_thread}
        positive = sorted(roots & _PERSON_ROOTS)
        negative = sorted(roots & _NONPERSON_ROOTS)
        lexical = [
            mention.lemma
            for mention in mentions
            if mention.pos in ("NOUN", "PROPN") and mention.lemma in (_MALE | _FEMALE)
        ]
        positive.extend(f"lexical:{lemma}" for lemma in sorted(set(lexical)))
        if positive and negative:
            return PersonEligibility("unknown", tuple(["conflicting_types"] + positive + negative))
        if negative:
            return PersonEligibility("non_person", tuple(negative))
        if positive:
            return PersonEligibility("person", tuple(positive))
        return PersonEligibility("unknown", ("no_decisive_person_evidence",))

    def is_proper(self, eid: Optional[str]) -> bool:
        """Is this id a proper-NAME referent? (a merge target must be a name, not another description)."""
        ms = self.by_id.get(eid or "", [])
        return any(m.pos == "PROPN" for m in ms)


def _safe_store() -> Optional[GenealogyStore]:
    try:
        return GenealogyStore()
    except Exception:
        return None


def _phase_error(phase: str, exc: Exception) -> dict:
    return {"code": f"{phase}_error", "error_type": type(exc).__name__, "message": str(exc)}
