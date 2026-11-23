"""referent_validation — a CONSTRAINT cassette: is this "entity" a real REFERENT at all?

The single-sentence parser sometimes tags a sentence-initial ADVERB / connective as a PROPN and it
becomes a standing entity: "Finally, the last bed…" → an entity ``finally``; a stray ``then``/``once``/
``meanwhile`` likewise. Such a non-referent is invisible at the single-sentence scale (locally it IS a
capitalized token in subject position) — only OUT-OF-FRAME does its nature show: it is a closed-class
function word the lexicon knows as an adverb, it never world-grounds, and it never recurs as a coherent
referent. A spurious document ``Equality``/``TypeAssertion`` can then bind a real description to it
(snow-white: ``Equality[finally, wife]`` → entity_identity merged ``wife`` onto ``finally`` — a
DESTROYED correct value). This cassette answers "is this a referent?" and emits a VETO; the deck strips
vetoed ids from every merge's candidate pool (the same validator-constrains-resolver composition as
``person_validation`` — a validator kills the edge case the resolver can't see).

It is the SymbolicSpellCheck *dictionary gate* generalized: SSC never operates on a token that is not a
real word; this never treats a non-referent token as a nameable entity. Discipline (mirrors
``person_validation``): fire ONLY on POSITIVE non-referent evidence — a known function/adverb lemma with
NO world grounding; abstain-keep otherwise, so a genuine name that merely happens to be rare is never
vetoed. Never destroys a correct value; a wrong guess here would only be NON-recovery (a kept junk id).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .base import Cassette
from .multiscale import Mention, MultiScaleDoc

# Closed-class / adverbial / connective lemmas that are NEVER legitimate entity names — the words that
# get PROPN-tagged only by sentence-initial capitalization. Ordinals (first/second/next) are
# DELIBERATELY EXCLUDED: they are the entity_identity SPLIT signal and the nominalized-adjective guard's
# territory, so vetoing them would fight another cassette. Temporal/logical adverbs + discourse
# connectives only.
_NON_REFERENT = frozenset(
    {
        "finally",
        "then",
        "later",
        "thus",
        "however",
        "meanwhile",
        "moreover",
        "furthermore",
        "therefore",
        "hence",
        "afterward",
        "afterwards",
        "once",
        "soon",
        "now",
        "today",
        "tomorrow",
        "yesterday",
        "nevertheless",
        "nonetheless",
        "eventually",
        "initially",
        "subsequently",
        "indeed",
        "perhaps",
        "maybe",
        "often",
        "always",
        "never",
        "sometimes",
        "suddenly",
        "immediately",
        "instead",
        "besides",
        "likewise",
        "similarly",
        "consequently",
        "accordingly",
        "otherwise",
        "overall",
        "meanwhile",
        "thereafter",
        "henceforth",
        "anyway",
        "somehow",
    }
)


@dataclass(frozen=True)
class ReferentGap:
    kind: str  # "veto"
    eid: str
    rep: Mention


class ReferentValidation(Cassette):
    name = "referent_validation"
    question = "is this a real referent, or a mis-tagged function word?"

    def gaps(self, doc: MultiScaleDoc) -> List[ReferentGap]:
        # every referent whose head lemma is a known non-referent function word is a candidate to veto.
        out = []
        for eid, ms in doc.by_id.items():
            rep = next((m for m in ms if m.lemma in _NON_REFERENT), None)
            if rep is not None:
                out.append(ReferentGap("veto", eid, rep))
        return out

    def candidates(self, gap: ReferentGap, doc: MultiScaleDoc) -> List[Any]:
        return [gap.eid]

    def ground(self, answer: Any, gap: ReferentGap, doc: MultiScaleDoc) -> bool:
        return True

    def score(self, answer: Any, gap: ReferentGap, doc: MultiScaleDoc) -> Dict[str, float]:
        """Score the POSITIVE non-referent evidence. A function-word lemma is the word-scale signal; a
        world grounding (the token really names something) BLOCKS the veto (return all-zero → keep)."""
        lemma = gap.rep.lemma
        if lemma not in _NON_REFERENT:
            return {}
        # world strand — if the token world-grounds as a real entity, it IS a referent → never veto.
        if _world_grounds(doc, lemma):
            return {}
        strands: Dict[str, float] = {"function_word": 1.0}
        # document strand — a real referent recurs or carries a type; a singleton untyped mention
        # corroborates junk (confirming only; the word signal already commits).
        ms = doc.by_id.get(gap.eid, [])
        if len(ms) <= 1 and not any(m.type_thread for m in ms):
            strands["singleton_untyped"] = 0.5
        return strands


def _world_grounds(doc: MultiScaleDoc, lemma: str) -> bool:
    if doc.store is None:
        return False
    try:
        c = doc.store.candidates(lemma, "PROPN", True)
        return bool(c and c[0])
    except Exception:
        return False
