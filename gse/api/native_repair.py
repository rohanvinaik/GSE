"""Native Tier-1 parse repair — the deterministic port of the enum_repair prototype.

The parse-strand of the multi-strand (DNA-style) error correction. Detects a degraded
clause against clause-form PROTOTYPES (required role slots + per-slot primitive signature,
derived empirically from clean exemplars), and repairs it by enumerating role assignments
around verb-sense pivots — all on the NATIVE, arc-free front-end:

  * roles come from ``encoder._syn_roles`` (positional SUBJ/PRED/OBJ/COMPL), NOT spaCy dep_;
  * a pivot's arguments are its nearest content flankers by POSITION, NOT .children/.head;
  * the verb-sense / transitive gates are WordNet dictionary facts (not a verb list).

Resolve: lone survivor → commit; ≥2 within EPS → bifurcate; none → literal. Every repair
carries provenance. Two faces: ``repair(sent)`` is the callable (this module); the
encode-time automatic step wires this in at stage 3 (deliberately not done here).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from nltk.corpus import wordnet as wn

from gse.api import GSEEncoder
from gse.api.parse_repair import _entity_like, verbs_to_promote

EPS = 0.10  # "comparable" band for bifurcation (empirical placeholder)

EXEMPLARS = {
    "EVENT_TRANS": [
        "Macbeth defeats Cawdor.", "Duncan executes Cawdor.", "Macduff kills Macbeth.",
        "Barry kills Katya.", "David fights Goliath.", "Archer loves Katya.",
        "Estonia insulted Russia.", "Macbeth murdered Duncan.",
    ],
    "EVENT_INTRANS": ["Goliath falls.", "Duncan goes to bed.", "The witches danced."],
    "COPULA": [
        "Duncan is a king.", "Macbeth is a thane.", "Macbeth is a noble.",
        "Dunsinane is a castle.", "Birnam Wood is a forest.",
    ],
}
EXPECT = {
    "EVENT_TRANS": {"SYN_SUBJ", "SYN_PRED", "SYN_OBJ"},
    "EVENT_INTRANS": {"SYN_SUBJ", "SYN_PRED"},
    "COPULA": {"SYN_SUBJ", "SYN_PRED", "SYN_COMPL"},
}
ARGUMENT_ROLES = frozenset({"SYN_SUBJ", "SYN_PRED", "SYN_OBJ", "SYN_COMPL"})
TRANSITIVE_FRAME_IDS = {8, 9, 10, 11}


def _has_verb_sense(lemma: str) -> bool:
    return bool(wn.synsets(lemma, pos="v"))


def _has_transitive_frame(lemma: str) -> bool:
    ids: Set[int] = set()
    for syn in wn.synsets(lemma, pos="v"):
        for lem in syn.lemmas():
            ids.update(lem.frame_ids())
    return bool(ids & TRANSITIVE_FRAME_IDS)


@dataclass
class Prototype:
    name: str
    required: frozenset
    signature: dict
    n_clean: int


@dataclass
class Candidate:
    roles: dict          # role -> native token
    frame: str
    shape: float
    filler: float

    @property
    def score(self) -> float:
        return self.shape * self.filler


class NativeRepair:
    def __init__(self, encoder: Optional[GSEEncoder] = None) -> None:
        self.enc = encoder or GSEEncoder()
        self.nlp = self.enc.nlp
        self.protos = self._derive()

    # --- native parse reading (positional, arc-free) -------------------------
    def _roles_of(self, doc) -> Dict[str, object]:
        """{role: representative token} from native positional _syn_roles. First token
        with a given argument-role wins (subject precedes the verb precedes the object)."""
        promote = verbs_to_promote(doc)
        syn = self.enc._syn_roles(doc, promote)
        toks = list(doc)
        chosen: Dict[str, object] = {}
        for i in sorted(syn):
            r = syn[i]
            if r in ARGUMENT_ROLES:
                chosen.setdefault(r, toks[i])
        return chosen

    def _prims(self, lemma: str) -> set:
        wp, _, _ = self.enc._lookup_lexeme(lemma.lower())
        return set(wp.keys())

    def _skeleton(self, sent: str) -> dict:
        return {r: (t.lemma_.lower(), self._prims(t.lemma_))
                for r, t in self._roles_of(self.nlp(sent)).items()}

    # --- prototype derivation (centroid; empirical) --------------------------
    def _derive(self) -> dict:
        protos = {}
        for frame, sents in EXEMPLARS.items():
            clean = [self._skeleton(s) for s in sents
                     if EXPECT[frame].issubset(self._skeleton(s))]
            n = max(len(clean), 1)
            slotcount: Counter = Counter()
            fillers: dict = {}
            for sk in clean:
                for r, (_, prims) in sk.items():
                    slotcount[r] += 1
                    fillers.setdefault(r, []).append(prims)
            required = frozenset(r for r, c in slotcount.items() if c >= 0.5 * n)
            sig = {}
            for r, plist in fillers.items():
                c: Counter = Counter()
                for ps in plist:
                    c.update(ps)
                sig[r] = {p for p, k in c.items() if k >= 0.5 * len(plist)}
            protos[frame] = Prototype(frame, required, sig, len(clean))
        return protos

    # --- scoring -------------------------------------------------------------
    def _filler_fit(self, roles_prims: dict, proto: Prototype) -> float:
        fits = []
        for r in proto.required:
            qp, sp = roles_prims.get(r, set()), proto.signature.get(r, set())
            fits.append(len(qp & sp) / len(sp) if sp else 1.0)
        return sum(fits) / len(fits) if fits else 0.0

    def _score_against(self, roles_prims: dict) -> list:
        present = set(roles_prims) & ARGUMENT_ROLES
        return [(p.name, 1.0, self._filler_fit(roles_prims, p))
                for p in self.protos.values()
                if (p.required & ARGUMENT_ROLES) == present]

    # --- enumeration repair (positional pivots + flankers) -------------------
    def _enumerate(self, doc) -> list:
        toks = list(doc)

        def nearest(i: int, step: int):
            j = i + step
            while 0 <= j < len(toks):
                if toks[j].pos_ not in ("PUNCT", "DET"):
                    return toks[j] if _entity_like(toks[j]) else None
                j += step
            return None

        cands: list = []
        seen: set = set()
        for pivot in toks:
            if pivot.pos_ == "PUNCT" or not _has_verb_sense(pivot.lemma_):
                continue
            pre, post = nearest(pivot.i, -1), nearest(pivot.i, +1)
            is_copula = pivot.lemma_.lower() == "be"   # "be" is no content transitive verb
            roles = {"SYN_PRED": pivot}
            if pre is not None:
                roles["SYN_SUBJ"] = pre
            if post is not None:
                roles["SYN_COMPL" if is_copula else "SYN_OBJ"] = post
            rp = {r: self._prims(t.lemma_) for r, t in roles.items()}
            for frame, shape, filler in self._score_against(rp):
                key = (frame, tuple(sorted((r, t.i) for r, t in roles.items())))
                if key in seen:
                    continue
                seen.add(key)
                cands.append(Candidate(dict(roles), frame, shape, filler))
        return cands

    def _false_clean_suspect(self, doc, frame: str, roles_tok: dict) -> bool:
        pred = roles_tok.get("SYN_PRED")
        if pred is None:
            return False
        if not _has_verb_sense(pred.lemma_):
            return True                                   # wrong pivot (no verb sense)
        event_no_obj = (frame.startswith("EVENT_")
                        and "SYN_OBJ" not in self.protos[frame].required)
        if event_no_obj and _has_transitive_frame(pred.lemma_):
            for t in doc:                                  # a post-pred nominal with no OBJ role
                if t.i <= pred.i or t.pos_ in ("PUNCT", "DET"):
                    continue
                if _entity_like(t):
                    return True
        return False

    # --- resolve -------------------------------------------------------------
    def repair(self, sent: str) -> dict:
        doc = self.nlp(sent)
        roles_tok = self._roles_of(doc)
        literal = {r: self._prims(t.lemma_) for r, t in roles_tok.items()}
        lit_match = self._score_against(literal)
        if lit_match and not self._false_clean_suspect(doc, lit_match[0][0], roles_tok):
            return {"verdict": "clean", "frame": lit_match[0][0],
                    "roles": {r: t.text for r, t in roles_tok.items()}, "provenance": []}
        cands = sorted(self._enumerate(doc), key=lambda c: -c.score)
        if not cands:
            return {"verdict": "fallback_literal",
                    "roles": {r: t.text for r, t in roles_tok.items()},
                    "provenance": ["repair: degraded, no prototype candidate — literal kept"]}
        top = cands[0]
        tied = [c for c in cands if top.score - c.score <= EPS and c.frame != top.frame]
        verdict = "bifurcate" if tied else "commit"
        return {
            "verdict": verdict, "frame": top.frame, "score": round(top.score, 3),
            "roles": {r: t.text for r, t in top.roles.items()},
            "provenance": ["repair(%s): literal %s → %s %s"
                           % (verdict, sorted(literal), top.frame,
                              {r: t.text for r, t in top.roles.items()})],
        }


def _main() -> None:
    rep = NativeRepair()
    print("=== derived prototypes (native) ===")
    for p in rep.protos.values():
        print("  %-14s required=%s  (n=%d)" % (p.name, sorted(p.required), p.n_clean))
    print("\n=== repair runs ===")
    for sent in [
        "Macbeth murders Duncan.", "Duncan compliments Macbeth.",
        "Macbeth defeats Cawdor.", "Goliath falls.", "Duncan is a king.",
        "The envious soldier murdered the old king.",
    ]:
        out = rep.repair(sent)
        print("\n%r\n   verdict=%s frame=%s roles=%s"
              % (sent, out["verdict"], out.get("frame"), out.get("roles")))


if __name__ == "__main__":
    raise SystemExit(_main())
