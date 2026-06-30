"""person_validation — a CONSTRAINT cassette: is this named referent a real person?

Some identity merges are licensed by a stated identity that is actually a parse error: beowulf's
encyclopedic prose ("Continental Germanic figures such as Offa, king of …") yields a spurious
``Equality(germanic, king)``, and "Cawdor" is a place/title, not the king. Neither is a person, so
neither can be the target of a person-identity merge. This cassette answers that one question and
emits a VETO; the deck applies it as a cross-cassette constraint on the entity-identity merges (the
"different cassettes for edge cases" composition — a validator constrains a resolver).

It does NOT re-implement person-detection — it composes GSE's existing tools, and it only ever fires
on POSITIVE non-person evidence (the world-leg-gate discipline: positively-non-person → exclude;
shallow/unknown → ABSTAIN-keep, so a fictional character with no world grounding — Malcolm, Merope —
is never wrongly vetoed):

  word strand   — ``grounding._is_person`` (WordNet hypernymy): germanic → language → NOT a person.
  world strand  — the referent's DBpedia type: cawdor → Place/Settlement; war → Event; navy → Org.
  facets        — SCALE/DOMAIN geographic-ethnic typing (the demonym/nationality signal): a national/
                  ethnic collective (a demonym like "Russian"/"Germanic") is a people, not a person.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .base import Cassette
from .multiscale import Mention, MultiScaleDoc

# Positively-NON-PERSON world/type roots (DBpedia + WordNet). A target rooted here cannot be a person.
_NONPERSON_WORLD = frozenset({
    "Place", "PopulatedPlace", "Settlement", "Location", "Region", "Country", "City",
    "Event", "SocietalEvent", "MilitaryConflict", "Work", "Organisation", "Organization",
    "Language", "EthnicGroup",
})
_NONPERSON_WORDNET = frozenset({"language", "communication", "location", "region", "social_group"})


@dataclass(frozen=True)
class PersonGap:
    kind: str           # "veto"
    eid: str
    rep: Mention


class PersonValidation(Cassette):
    name = "person_validation"
    question = "is this named referent a real person?"

    def gaps(self, doc: MultiScaleDoc) -> List[PersonGap]:
        # every proper-NAME referent is a candidate merge target → a candidate to validate
        out = []
        for eid in doc.by_id:
            nm = next((m for m in doc.by_id[eid] if m.pos == "PROPN"), None)
            if nm is not None:
                out.append(PersonGap("veto", eid, nm))
        return out

    def candidates(self, gap: PersonGap, doc: MultiScaleDoc) -> List[Any]:
        return [gap.eid]            # the single judgment: should this id be vetoed as non-person?

    def ground(self, answer: Any, gap: PersonGap, doc: MultiScaleDoc) -> bool:
        return True

    def score(self, answer: Any, gap: PersonGap, doc: MultiScaleDoc) -> Dict[str, float]:
        """Score the POSITIVE non-person evidence. A genuine person blocks the veto (return all-zero →
        abstain → keep). Shallow/unknown also abstains (never veto without evidence)."""
        lemma = gap.rep.lemma
        # word strand — WordNet person check. True → a person → NEVER veto (block).
        wn = _is_person_safe(lemma)
        if wn is True:
            return {}                          # positively a person → no veto
        strands: Dict[str, float] = {}
        if wn is False:
            strands["wordnet_nonperson"] = 1.0  # germanic → language → not a person
        # world strand — the referent's DBpedia type (place/event/work/org)
        world = _world_thread(doc, lemma)
        if set(world) & _NONPERSON_WORLD or set(world) & _NONPERSON_WORDNET:
            strands["world_nonperson"] = 1.0    # cawdor → Place
        # facets — geographic/ethnic collective (the demonym/nationality signal)
        facets = _facets(doc, lemma)
        dom = set(facets.get("DOMAIN", ()))
        if (dom & {"Geography"}) and "person" not in world:
            strands["demonym"] = 0.5            # a geographic/national collective, not a person
        return strands

    # the deck reads committed vetoes; commit when ANY positive non-person strand fires (margin spine
    # commits a single candidate whose total > 0), abstain on a person or on no evidence.


def _is_person_safe(lemma: str):
    try:
        from gse.symbolic.grounding import _is_person
        return _is_person(lemma)
    except Exception:
        return None


def _world_thread(doc: MultiScaleDoc, lemma: str):
    if doc.store is None:
        return ()
    try:
        c = doc.store.candidates(lemma, "PROPN", True)
        return c[0] if c else ()
    except Exception:
        return ()


def _facets(doc: MultiScaleDoc, lemma: str) -> Dict[str, Any]:
    if doc.store is None or not hasattr(doc.store, "facets"):
        return {}
    try:
        return doc.store.facets(lemma) or {}
    except Exception:
        return {}
