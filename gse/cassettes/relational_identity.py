"""relational_identity — cassette: resolve a SPOUSE-kinship description to the name it implies, via
the ONOMASTIC title strand the single sentence can't see.

The naive spine leaves "her husband" (the agent of 'murder Duncan' / 'obtain the crown') as its own
referent, NEVER merged to Macbeth — because the text licenses the identity only RELATIONALLY ("her
husband", her = Lady Macbeth) with no ``Equality``/``TypeAssertion`` for entity_identity to bind on.
The resolving signal is out-of-frame and COMPOSITIONAL:

  strand 1 — relational : the possessor is stated (``husband``'s possessor entity = "Lady Macbeth").
  strand 2 — onomastic  : that possessor is a TITLED compound name (span ``lady``+``macbeth``);
                          stripping the title yields ``macbeth``, which grounds to a SEPARATE
                          bare-name person-agent already in the document.

The two converge on that agent. This is NOT proximity/centering (the M2.2 forbidden move): the title
"Lady X" *encodes* "X's wife", so "her husband" deterministically = X. Gender is a confirming strand
(a husband's titled possessor is female). It composes through the deck like every cassette and ABSTAINS
whenever the discipline isn't met — the possessor is not a titled name, the title-stripped residual
names no separate agent (so "Lady Anne", whose residual ``anne`` is no separate male agent, stays
silent) or names more than one, or the role is not spousal. If it can't converge, it leaves the spine
exactly as it was.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import Cassette
from .entity_identity import IdentityGap
from .multiscale import Mention, MultiScaleDoc

# Spousal kinship nouns — the only roles whose titled possessor names the SPOUSE.
_SPOUSE = frozenset({"husband", "wife", "spouse", "consort"})
# Personal-honorific TITLE tokens that prefix a name ("Lady Macbeth", "Sir Gawain"). Stripping the
# title leaves the bare name. Regnal titles (king/queen) are deliberately EXCLUDED: "King Duncan" is
# Duncan himself, not a spouse referent, and including them would invite over-firing.
_TITLES = frozenset({"lady", "lord", "sir", "dame", "mrs", "mr", "mister", "miss", "ms",
                     "madam", "madame", "master", "mistress"})


class RelationalIdentity(Cassette):
    name = "relational_identity"
    question = "who is this spouse-by-relation?"

    # -- trigger: a spouse description whose possessor is a titled compound name -------------
    def gaps(self, doc: MultiScaleDoc) -> List[IdentityGap]:
        out: List[IdentityGap] = []
        for eid, ms in doc.by_id.items():
            if doc.is_proper(eid):
                continue                                  # already a name — not a fragment
            rep = self._spouse_rep(ms, doc)
            if rep is not None:
                out.append(IdentityGap("merge", eid, rep))
        return out

    def _spouse_rep(self, ms: List[Mention], doc: MultiScaleDoc) -> Optional[Mention]:
        """The representative mention of a spouse description that carries a TITLED possessor — prefer
        an agent mention (its deeds are what a merge reattaches)."""
        cand = [m for m in ms
                if m.lemma in _SPOUSE and m.pos != "PROPN"
                and self._title_residual(m.possessor_span)]
        if not cand:
            return None
        return max(cand, key=lambda m: (m.is_agent, m.sent))

    @staticmethod
    def _title_residual(span) -> tuple:
        """The name tokens of a titled possessor span, title stripped: ('lady','macbeth') → ('macbeth',).
        Empty when the span has no title or nothing survives stripping (→ no onomastic signal)."""
        toks = tuple(span or ())
        if len(toks) < 2 or not (set(toks) & _TITLES):
            return ()
        return tuple(t for t in toks if t not in _TITLES)

    # -- propose: the separate bare-name agent the title-stripped residual names -------------
    def candidates(self, gap: IdentityGap, doc: MultiScaleDoc) -> List[Any]:
        residual = self._title_residual(gap.rep.possessor_span)
        if not residual:
            return []
        res_lemma = residual[-1]                          # the head of the residual name (surname)
        poss_eid = gap.rep.possessor_eid
        hits: List[str] = []
        for eid, ms in doc.by_id.items():
            if eid == gap.eid or eid == poss_eid or not doc.is_proper(eid):
                continue
            for m in ms:
                if m.pos == "PROPN" and m.lemma == res_lemma and not m.span:
                    hits.append(eid)                      # the BARE name (span ()), not the titled one
                    break
        return list(dict.fromkeys(hits))                  # de-dup, preserve order

    # -- ground: the candidate must be a grounded person, distinct from the possessor --------
    def ground(self, answer: Any, gap: IdentityGap, doc: MultiScaleDoc) -> bool:
        if not doc.is_proper(answer) or answer == gap.rep.possessor_eid:
            return False
        nm = next((m for m in doc.by_id.get(answer, []) if m.pos == "PROPN"), None)
        return bool(nm and doc.is_person(nm))

    # -- score: relational ⊥ onomastic converge; gender confirms --------------------------
    def score(self, answer: Any, gap: IdentityGap, doc: MultiScaleDoc) -> Dict[str, float]:
        kin_g = doc.gender(gap.rep)                        # husband → m, wife → f
        title_g = self._title_gender(gap.rep.possessor_span)
        # spouse genders are complementary: a husband's titled possessor (the wife) is female, etc.
        complementary = bool(kin_g and title_g and kin_g != title_g)
        return {
            "relational": 1.0,                            # the possessor is stated (the gate)
            "onomastic": 1.0,                             # residual uniquely matches a separate agent
            "gender": 0.15 if complementary else 0.0,     # confirming: spouse = opposite title gender
        }

    @staticmethod
    def _title_gender(span) -> Optional[str]:
        toks = set(span or ())
        if toks & {"lady", "dame", "mrs", "miss", "ms", "madam", "madame", "mistress"}:
            return "f"
        if toks & {"lord", "sir", "mr", "mister", "master"}:
            return "m"
        return None
