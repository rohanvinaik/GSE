"""entity_identity — cassette "B": resolve who a referent really is, from out-of-frame context.

The naive spine fragments one person across many ids (Macbeth = ``macbeth`` ∪ ``his kinsman`` ∪
``husband``; Oedipus = ``oedipus`` ∪ ``king`` ∪ ``son``; Jocasta = ``wife`` ∪ ``mother``) and collapses
distinct people into one (the Prodigal's two sons → one ``son``). Both are identity errors that NO
single sentence can fix — "his kinsman" denotes Macbeth only by the surrounding text; the two sons are
distinct only by their order across the whole parable. So this is a cassette: it reads the raw text and
converges the four scales.

Two faces, each disciplined identically (commit-by-margin-or-abstain in ``base.Cassette.resolve``):

  MERGE  a relational/role DESCRIPTION ("the king", "the queen", "the mother") → the proper NAME it
         refers to, licensed by a POSITIVE identity signal the text itself states — a document
         ``Equality``/``TypeAssertion`` predicating that the name IS that role ("Jocasta is the queen"
         → queen≡Jocasta; "Malcolm is the heir" → heir≡Malcolm). Proximity/centering is NOT identity
         evidence (the M2.2 lesson: centering is a tie-breaker, not an identity source — a proximity
         merge fabricates), so without a stated identity the cassette ABSTAINS. It also ABSTAINS when
         the role is predicated of >1 name (Oedipus: "mother" ≡ Merope AND Jocasta — the tragedy's own
         ambiguity), because fusing two distinct people is fabrication, worse than an honest miss.
         The strands: ``predicative`` (the stated identity — the GATE) · ``agreement`` (lexical gender
         must not contradict) · ``recency``/``centering`` (confirming only, never sufficient).

  SPLIT  one id whose mentions carry CONTRASTIVE order/age modifiers ("younger" vs "elder") → two
         referents. ABSTAIN on a bare repeated "the son" (that merge is correct).

This is exactly the entity-identity work the M2.2 effort concluded "requires a dedicated parser
project" — clause-scoped, reading raw text, abstention-gated — which is what a cassette is.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import Cassette
from .multiscale import Mention, MultiScaleDoc

# A description triggers a MERGE gap when its head is an inherently RELATIONAL / unique-role person
# noun (spousal/parental/regnal — these denote a specific figure, not a generic extra). Generic minor
# roles (servant/attendant/soldier) are NOT identity gaps — they are real distinct characters, so the
# cassette stays silent on them (trigger discipline: fire only on a genuine gap).
_RELATIONAL = frozenset({"husband", "wife", "king", "queen", "mother", "father",
                         "kinsman", "spouse", "consort", "widow", "widower"})
# Contrastive order/age modifiers — the SPLIT signal (two distinct sons/brothers). The parse emits
# the BASE adjective form ("young"/"old"), not only the comparative, so the axis includes both.
_CONTRASTIVE_YOUNG = frozenset({"young", "younger", "youngest", "first"})
_CONTRASTIVE_OLD = frozenset({"old", "older", "elder", "eldest", "oldest", "second"})
_ORDER_AXIS = _CONTRASTIVE_YOUNG | _CONTRASTIVE_OLD


@dataclass(frozen=True)
class IdentityGap:
    kind: str                    # "merge" | "split"
    eid: str
    rep: Mention                 # a representative mention (the description, or one split member)
    payload: Any = None          # split: the modifier→[mentions] partition


class EntityIdentity(Cassette):
    name = "entity_identity"
    question = "who is this referent, really?"

    # -- triggers -----------------------------------------------------------
    def gaps(self, doc: MultiScaleDoc) -> List[IdentityGap]:
        out: List[IdentityGap] = []
        out.extend(self._merge_gaps(doc))
        out.extend(self._split_gaps(doc))
        return out

    def _is_description(self, m: Mention, doc: MultiScaleDoc) -> bool:
        """A relational/possessive DESCRIPTION of a person — the thing that denotes someone without
        naming them. NOT a proper name, NOT a generic extra."""
        if m.pos == "PROPN":
            return False
        if not doc.is_person(m):
            return False
        if m.lemma in _RELATIONAL:
            return True
        # a possessive person-description: "his kinsman", "her son" (possessor is a pronoun or name)
        if m.possessor_lemma and (set(m.type_thread) & {"person", "relative", "kinsman"} or
                                  m.lemma in _RELATIONAL):
            return True
        return False

    def _merge_gaps(self, doc: MultiScaleDoc) -> List[IdentityGap]:
        gaps: List[IdentityGap] = []
        for eid, ms in doc.by_id.items():
            if doc.is_proper(eid):
                continue                              # already a name — not a fragment
            descr = [m for m in ms if self._is_description(m, doc)]
            if descr:
                rep = max(descr, key=lambda m: (m.is_agent, m.sent))  # prefer an agent mention
                gaps.append(IdentityGap("merge", eid, rep))
        return gaps

    def _split_gaps(self, doc: MultiScaleDoc) -> List[IdentityGap]:
        gaps: List[IdentityGap] = []
        for eid, ms in doc.by_id.items():
            mods = {m.modifier for m in ms if m.modifier in _ORDER_AXIS}
            if (mods & _CONTRASTIVE_YOUNG) and (mods & _CONTRASTIVE_OLD):
                partition: Dict[str, List[Mention]] = {}
                for m in ms:
                    if m.modifier in _ORDER_AXIS:
                        partition.setdefault(m.modifier, []).append(m)
                gaps.append(IdentityGap("split", eid, ms[0], partition))
        return gaps

    # -- propose ------------------------------------------------------------
    def candidates(self, gap: IdentityGap, doc: MultiScaleDoc) -> List[Any]:
        if gap.kind == "split":
            return [gap.payload]                      # the one partition; scoring decides commit/abstain
        # MERGE: ONLY names the text predicatively states ARE this role (Equality/TypeAssertion). No
        # stated identity → no candidate → abstain. Proximity is never an identity source.
        links = self._identity_links(doc)             # role-key -> {name_eid}
        d_gender = doc.gender(gap.rep)
        names: List[str] = []
        for eid in links.get(gap.rep.lemma, set()) | links.get(gap.eid, set()):
            if eid == gap.eid or not doc.is_proper(eid):
                continue
            nm = self._name_mention(eid, doc)
            n_gender = (doc.gender(nm) if nm else None) or self._name_gender(eid, doc)
            if d_gender and n_gender and d_gender != n_gender:
                continue                              # hard agreement gate — never merge across gender
            names.append(eid)
        return names

    def _identity_links(self, doc: MultiScaleDoc) -> Dict[str, set]:
        """The POSITIVE identity signal: every document ``Equality``/``TypeAssertion`` that predicates a
        proper NAME to a common-noun ROLE → ``{role-lemma | role-eid : {name_eid}}``. This is the only
        thing that licenses a merge. A role predicated of >1 name stays multi-valued → the cassette
        abstains on it (genuine ambiguity, e.g. Oedipus's two 'mother's). Cached per doc."""
        cache = getattr(doc, "_identity_links_cache", None)
        if cache is not None:
            return cache
        links: Dict[str, set] = {}

        def ent(x):
            from gse.symbolic.resolution import Entity
            return x if isinstance(x, Entity) else None

        def add(name_ent, role_ent):
            if name_ent is None or role_ent is None:
                return
            nh, rh = name_ent.head, role_ent.head
            if getattr(nh, "pos", None) != "PROPN" or getattr(rh, "pos", None) == "PROPN":
                return                                # need exactly one NAME and one common-noun ROLE
            name_eid = getattr(name_ent, "entity_id", None)
            if not name_eid:
                return
            for key in (rh.lemma.lower() if rh.lemma else None, getattr(role_ent, "entity_id", None)):
                if key:
                    links.setdefault(key, set()).add(name_eid)

        from gse.symbolic.healer.treewalk import walk
        for _t, pred in doc.timed:
            for n in walk(pred):
                nm = type(n).__name__
                if nm == "Equality":
                    a, b = ent(getattr(n, "lhs", None)), ent(getattr(n, "rhs", None))
                    add(a, b)
                    add(b, a)                          # either side may be the name
                elif nm == "TypeAssertion":
                    add(ent(getattr(n, "entity", None)), ent(getattr(n, "kind", None)))
        try:
            doc._identity_links_cache = links          # type: ignore[attr-defined]
        except Exception:
            pass
        return links

    # -- ground gate --------------------------------------------------------
    def ground(self, answer: Any, gap: IdentityGap, doc: MultiScaleDoc) -> bool:
        if gap.kind == "split":
            parts = answer
            # both groups must independently denote a person (the dictionary gate for a split)
            return len(parts) >= 2 and all(
                any(doc.is_person(m) for m in members) for members in parts.values())
        return doc.is_proper(answer)                  # a merge target must be a grounded name

    # -- score by orthogonal strands ---------------------------------------
    def score(self, answer: Any, gap: IdentityGap, doc: MultiScaleDoc) -> Dict[str, float]:
        if gap.kind == "split":
            parts: Dict[str, List[Mention]] = answer
            young = sum(len(v) for k, v in parts.items() if k in _CONTRASTIVE_YOUNG)
            old = sum(len(v) for k, v in parts.items() if k in _CONTRASTIVE_OLD)
            # word: the modifiers are decisively contrastive; document: each side actually recurs.
            return {"word_contrastive": 1.0 if (young and old) else 0.0,
                    "document_presence": 0.5 if (young >= 1 and old >= 1) else 0.0}
        # MERGE strands — STRICT SSC CONVERGENCE (2026-07-01). A merge commits only when >=2 ORTHOGONAL
        # IDENTITY strands agree (the deck's convergence floor). ``predicative`` (the text's stated
        # identity) is the GATE and is always 1.0 here; ``agreement`` (an INFORMATIVE gender match) is the
        # only other identity strand. PROXIMITY (recency / centering) is DELIBERATELY NOT SCORED: the
        # brief's M2.2 law is that proximity/centering is NOT an identity source — counting it fabricated
        # `chambermaid≡claudio` (a central protagonist proximity-merged into a minor role, corpus
        # validation 2026-07-01). So a LONE predicative link (no gender corroboration) scores confidence 1
        # → the deck abstains; only a doubly-corroborated identity commits (predicative + gender-agreement,
        # or — via the deck — a second cassette's stated link). Two names both predicated of the role tie
        # at 1.0 → not decisive → abstain on genuine ambiguity. Abstention over destruction, by design.
        name = self._name_mention(answer, doc)
        d, strands = gap.rep, {"predicative": 1.0}
        dg, ng = doc.gender(d), (doc.gender(name) if name else None) or self._name_gender(answer, doc)
        strands["agreement"] = 0.15 if (dg and ng and dg == ng) else 0.0
        return strands

    # -- helpers ------------------------------------------------------------
    def _name_mention(self, eid: str, doc: MultiScaleDoc) -> Optional[Mention]:
        ms = [m for m in doc.by_id.get(eid, []) if m.pos == "PROPN"]
        return ms[0] if ms else None

    def _name_gender(self, eid: str, doc: MultiScaleDoc) -> Optional[str]:
        """A name's gender inferred from any gendered DESCRIPTION already merged onto it (e.g. a name
        that also appears with a gendered title). Word-scale, abstaining when unknown."""
        for m in doc.by_id.get(eid, []):
            g = doc.gender(m)
            if g:
                return g
        return None
    # NOTE (2026-07-01): the former ``_recency``/``_centering`` proximity strands were REMOVED — the
    # brief's M2.2 law is that proximity/centering is not an identity source (it fabricated
    # chambermaid≡claudio). Identity now rests on stated predication + gender agreement only.
