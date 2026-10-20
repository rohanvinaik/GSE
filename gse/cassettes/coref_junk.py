"""coref_junk — the GENERIC-noun identity cassette: is this bare person-noun a named character?

The measured gap (2026-07-01, 14 current-era spines): 13% of all event edges carry a GENERIC
person-noun agent — ``man``/``woman``/``boy``/``sister`` — that is really a named character the
document itself identifies: The Old Man and the Sea's ``man`` (×10 edges) IS Santiago (the story's
own naming); Inanna's ``sister`` is Ereshkigal. The split makes the protagonist's arc invisible
(the viz reads "Doom (man)" where the story means Haman) and no single sentence can repair it —
which is what makes this a cassette (multi-scale resolution over the raw text), the sibling of
``entity_identity``: that cassette handles RELATIONAL role nouns (husband/king/mother) licensed by
a stated identity; this one handles the possessor-less GENERICS, licensed by scale convergence.

Strands (orthogonal, each speaking only where it has signal):

  naming     — the document PREDICATES the identity ("a Jewish orphan named Esther", "the old man,
               Santiago") — the same Equality/TypeAssertion links entity_identity gates on. The
               strongest signal (gate-weight 2.0).
  title      — the generic lemma appears in the document's TITLE ("The Old Man and the Sea") and
               the candidate is the document's top named protagonist (the fold's max agent-count).
               A title names its protagonist; the generic in a title IS that protagonist.
  adjacency  — the ±2-sentence co-occurrence rate between the generic's mentions and this name's
               mentions (the cis-regulatory neighborhood): an alias interleaves with its name.
  exclusive  — the candidate is the ONLY gender-compatible named person in the document.

Abstain-by-construction on the mixed-referent case: Esther's ``man`` really is Haman in one clause,
Mordecai in the next, Ahasuerus in a third — no strand separates them, the margin never clears, the
cassette abstains (fusing them would be fabrication, worse than the split). A generic with ANY
plural mention (``women``) is a collective, not an alias — the trigger stays silent. A generic with
a possessor ("her sister") is entity_identity's territory — skipped here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .base import Cassette
from .multiscale import Mention, MultiScaleDoc

# The possessor-less generic person-nouns the corpus measurement surfaced as alias-agents.
# Deliberately small: a generic must EARN entry via the measured gap, not enumerate the lexicon.
_GENERIC = frozenset(
    {
        "man",
        "woman",
        "boy",
        "girl",
        "sister",
        "brother",
        "old man",
        "young man",
        "old woman",
        "fisherman",
        "lad",
        "maiden",
    }
)
_MALE = frozenset({"man", "boy", "brother", "old man", "young man", "fisherman", "lad"})
_FEMALE = frozenset({"woman", "girl", "sister", "old woman", "maiden"})


@dataclass(frozen=True)
class GenericGap:
    kind: str  # "merge"
    eid: str
    rep: Mention


class CorefJunk(Cassette):
    name = "coref_junk"
    question = "is this generic person-noun a named character in this document?"

    # -- trigger ------------------------------------------------------------
    def gaps(self, doc: MultiScaleDoc) -> List[GenericGap]:
        out: List[GenericGap] = []
        for eid, ms in doc.by_id.items():
            if not ms:
                continue
            rep = max(ms, key=lambda m: (m.is_agent, m.sent))
            lemma = (rep.lemma or "").lower()
            if lemma not in _GENERIC:
                continue
            # NB: no is_proper skip here — a capitalized generic ("The Old Man") tags PROPN,
            # but for a _GENERIC lemma that is orthography, not properhood; the licensing
            # gate + gender gate carry the safety.
            # a collective ("women", plural mentions) is not an alias; a possessed generic
            # ("her sister") is entity_identity's stated-identity territory.
            if any(getattr(m, "number", None) == "plural" for m in ms):
                continue
            if any(m.possessor_lemma for m in ms):
                continue
            # an alias RECURS as an agent; a one-shot generic extra is a real extra.
            if sum(1 for m in ms if m.is_agent) < 2 and len(ms) < 3:
                continue
            out.append(GenericGap("merge", eid, rep))
        return out

    # -- propose ------------------------------------------------------------
    def candidates(self, gap: GenericGap, doc: MultiScaleDoc) -> List[str]:
        g_gender = self._generic_gender(gap.rep)
        names: List[str] = []
        for eid, ms in doc.by_id.items():
            if eid == gap.eid or not doc.is_proper(eid):
                continue
            nm = next((m for m in ms if m.pos == "PROPN"), None)
            if nm is None or doc.is_person(nm).code != "person":
                continue
            # NAME-quality gate (the orthographic discipline): a capitalized common English
            # word ('Sea', 'Old', 'Written', 'February') tags PROPN at a sentence start and
            # leaks in as a person candidate — a real NAME has no lowercase dictionary life.
            if self._common_word((nm.lemma or "").lower()):
                continue
            n_gender = doc.gender(nm)
            if g_gender and n_gender and g_gender != n_gender:
                continue  # hard agreement gate — never merge across gender
            names.append(eid)
        return names

    def ground(self, answer: str, gap: GenericGap, doc: MultiScaleDoc) -> bool:
        return doc.is_proper(answer)

    # -- score --------------------------------------------------------------
    def score(self, answer: str, gap: GenericGap, doc: MultiScaleDoc) -> Dict[str, float]:
        strands: Dict[str, float] = {}
        lemma = (gap.rep.lemma or "").lower()
        # naming — the document states the identity: an Equality/TypeAssertion link, OR the
        # raw text's own naming construction in one sentence ("a Jewish woman … known as
        # Esther", "a lad named Aladdin") — the literal-raw-text scale the cassette law is for.
        links = self._identity_links(doc)
        if answer in (links.get(lemma, set()) | links.get(gap.eid, set())):
            strands["naming"] = 2.0
        elif self._surface_naming(doc, lemma, answer):
            strands["naming"] = 2.0
        # title — the generic is the TITLE's referent (word-boundary — 'lad' is NOT in
        # "Aladdin") and the candidate is the protagonist.
        title = self._title(doc)
        if title and answer == self._protagonist(doc):
            import re as _re

            if _re.search(r"\b" + _re.escape(lemma) + r"\b", title):
                strands["title"] = 1.0
        # adjacency — ±2-sentence co-occurrence rate with THIS name.
        g_sents = {m.sent for m in doc.by_id.get(gap.eid, ())}
        n_sents = {m.sent for m in doc.by_id.get(answer, ())}
        if g_sents:
            near = sum(1 for s in g_sents if any(abs(s - t) <= 2 for t in n_sents))
            strands["adjacency"] = round(near / len(g_sents), 3)
        # exclusive — the only gender-compatible named person in the document.
        if len(self.candidates(gap, doc)) == 1:
            strands["exclusive"] = 1.0
        return strands

    # -- commit gate --------------------------------------------------------
    def resolve(self, gap: GenericGap, doc: MultiScaleDoc):
        """The base margin spine, PLUS the identity-license gate: a merge commits ONLY when a
        LICENSING strand (naming / title) carried the winner — adjacency and exclusivity are
        CONFIRMING-only. Without this, the boy (Manolin) merges into Santiago on adjacency 1.0
        alone: two characters sharing every scene is proximity, and proximity is never identity
        (the M2.2 lesson, and the measured DESTRUCTION case of this cassette's first run)."""
        res = super().resolve(gap, doc)
        if res.committed is not None:
            s = res.ranked[0].strands
            if not (s.get("naming", 0) > 0 or s.get("title", 0) > 0):
                return type(res)(
                    res.cassette,
                    res.gap,
                    None,
                    res.ranked,
                    "winner lacks an identity license (naming/title): abstained",
                )
            # MIXED-REFERENT guard: a second name whose adjacency rivals the winner's means the
            # generic's mentions interleave with TWO people — a wiki article's 'man' is Santiago
            # in the plot paragraphs and Hemingway in the frame paragraphs (measured: an exact
            # 0.417/0.417 tie). A per-lemma merge would mis-attribute the loser's deeds to the
            # winner — abstain; splitting the entity per-mention is the recorded v2.
            win_adj = s.get("adjacency", 0.0)
            for other in res.ranked[1:]:
                if other.strands.get("adjacency", 0.0) >= max(0.3, win_adj - 0.1):
                    return type(res)(
                        res.cassette, res.gap, None, res.ranked, "mixed referent (rival adjacency): abstained"
                    )
        return res

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _generic_gender(rep: Mention) -> Optional[str]:
        lemma = (rep.lemma or "").lower()
        if lemma in _MALE:
            return "male"
        if lemma in _FEMALE:
            return "female"
        return None

    @staticmethod
    def _identity_links(doc: MultiScaleDoc) -> Dict[str, set]:
        from .entity_identity import EntityIdentity

        return EntityIdentity()._identity_links(doc)

    @staticmethod
    def _surface_naming(doc: MultiScaleDoc, lemma: str, answer: str) -> bool:
        """The raw text names the generic within one sentence: ``<lemma> … named|known as|
        called <Name>`` where <Name> is the candidate's proper lemma."""
        raw = getattr(doc, "raw", "") or ""
        names = {(m.lemma or "").lower() for m in doc.by_id.get(answer, ()) if m.pos == "PROPN"}
        if not names or not lemma:
            return False
        import re as _re

        for m in _re.finditer(
            r"\b" + _re.escape(lemma) + r"\b[^.?!]{0,90}?\b(?:named|known as|called)\s+([A-Z][\w'-]+)", raw
        ):
            if m.group(1).lower() in names:
                return True
        return False

    @staticmethod
    def _common_word(tok: str) -> bool:
        """True when the token has a LOWERCASE dictionary life (any POS) — the same discipline
        as the genealogy token-alias filter: a real name has none."""
        if not tok or not tok.isalpha():
            return True
        try:
            from nltk.corpus import wordnet as wn

            for pos in ("n", "v", "a", "r", "s"):
                for syn in wn.synsets(tok, pos):
                    for lem in syn.lemmas():
                        if lem.name().lower() == tok and not lem.name()[0].isupper():
                            return True
            return False
        except Exception:
            return False

    @staticmethod
    def _title(doc: MultiScaleDoc) -> str:
        for line in (getattr(doc, "raw", "") or "").splitlines():
            if line.startswith("TITLE:"):
                return line[6:].strip().lower()
        return ""

    def _protagonist(self, doc: MultiScaleDoc) -> Optional[str]:
        best, best_n = None, 0
        for eid, fold in (getattr(doc, "fold", None) or {}).items():
            if not doc.is_proper(eid):
                continue
            n = getattr(fold, "agent_count", 0)
            if n > best_n:
                best, best_n = eid, n
        return best
