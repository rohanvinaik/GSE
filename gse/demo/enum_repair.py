"""Tier-1 enumeration repair — OFF-PIPELINE PROTOTYPE.

A standalone play artifact for the upstream parse-repair design discussed in
the COMPLEX_SENTENCE work. It does NOT touch ``gse.api.encoder``'s encode path;
nothing in the pipeline imports it. Run it directly to watch the repair fire.

Mechanism (the settled enumeration policy, tier 1 only):

  * Derive clause-form prototypes (required role slots + per-slot primitive
    signature) from cleanly-parsed Genesis exemplars — centroid-style, so the
    values are empirical, not hand-authored.
  * Detect: score the *literal* parse against the prototypes. A parse that
    completes some prototype is clean — never touched.
  * Repair (only on a degraded parse): freeze the attachment skeleton (pivot +
    its nominal dependents — spaCy recovers this even when it mislabels), then
    permute the role *labels*, pruned by
        - linear order  (pre-pivot nominal -> SUBJ, post-pivot -> OBJ), and
        - a verb-sense gate (pivot -> PRED only if its lemma has a WordNet verb
          sense; this is the dictionary fact that replaces a hardcoded verb list).
  * Score survivors with the hybrid: hard shape gate x graded filler (the filler
    half is provisional/weak until wired to the grounding strand).
  * Resolve: lone survivor -> commit; >=2 within EPS -> bifurcate; none -> literal.

Tier 2 (attachment revision) is deliberately absent — gated on measurement.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from nltk.corpus import wordnet as wn

from gse.api import GSEEncoder
from gse.api.encoder import DEP_TO_SYNTACTIC

EPS = 0.10  # "comparable" band for bifurcation (empirical; placeholder)

# Clean exemplars mined from the Genesis plot corpus (Macbeth, Cyberwar,
# David/Goliath, Archer). Proper-noun subjects throughout — the real register.
EXEMPLARS = {
    "EVENT_TRANS": [
        "Macbeth defeats Cawdor.",
        "Duncan executes Cawdor.",
        "Macduff kills Macbeth.",
        "Barry kills Katya.",
        "David fights Goliath.",
        "Archer loves Katya.",
        "Estonia insulted Russia.",
        "Macbeth murdered Duncan.",
    ],
    "EVENT_INTRANS": [
        "Goliath falls.",
        "Duncan goes to bed.",
        "The witches danced and chanted.",
    ],
    "COPULA": [
        "Duncan is a king.",
        "Macbeth is a thane.",
        "Macbeth is a noble.",
        "Dunsinane is a castle.",
        "Birnam Wood is a forest.",
    ],
}
# Shape each frame must have, used to filter bug-hit exemplars out of derivation.
EXPECT = {
    "EVENT_TRANS": {"SYN_SUBJ", "SYN_PRED", "SYN_OBJ"},
    "EVENT_INTRANS": {"SYN_SUBJ", "SYN_PRED"},
    "COPULA": {"SYN_SUBJ", "SYN_PRED", "SYN_COMPL"},
}

# Function-word dependency labels to exclude when collecting candidate fillers.
# We must NOT filter by POS — the mistag is precisely a corrupted POS (it demotes
# the subject to ADJ), so trusting pos_ here would re-drop the token we're trying
# to recover. We exclude only deps that can never be an entity slot.
_FUNCTION_DEPS = {"punct", "det", "aux", "auxpass", "cc", "mark", "case", "cop", "prep"}

# Frames are discriminated over their *argument* roles only — determiners and
# modifiers are not frame-distinguishing, so exact-match ignores them (otherwise
# a determiner on the object would stop a transitive clause from matching, and a
# subset frame like INTRANS would silently co-match every transitive clause).
ARGUMENT_ROLES = frozenset({"SYN_SUBJ", "SYN_PRED", "SYN_OBJ", "SYN_COMPL"})


@dataclass
class Prototype:
    name: str
    required: frozenset  # required role slots
    signature: dict  # role -> set of signature primitives
    n_clean: int


@dataclass
class Candidate:
    roles: dict  # role -> spaCy token
    frame: str  # prototype it completes
    shape: float
    filler: float

    @property
    def score(self) -> float:
        return self.shape * self.filler


def has_verb_sense(lemma: str) -> bool:
    """Dictionary fact: does this lemma have a verb reading? (Not a verb list.)"""
    return bool(wn.synsets(lemma, pos="v"))


# WordNet sentence-frame ids for transitive readings ("Somebody ----s
# something / somebody", etc.). Another dictionary fact, not a verb list.
TRANSITIVE_FRAME_IDS = {8, 9, 10, 11}


def has_transitive_frame(lemma: str) -> bool:
    """Dictionary fact: does this verb take a direct object?"""
    ids = set()
    for syn in wn.synsets(lemma, pos="v"):
        for lem in syn.lemmas():
            ids.update(lem.frame_ids())
    return bool(ids & TRANSITIVE_FRAME_IDS)


class Tier1Repair:
    def __init__(self) -> None:
        self.enc = GSEEncoder()
        self.nlp = self.enc.nlp
        self.protos = self._derive()

    # --- prototype derivation -------------------------------------------------
    def _skeleton(self, sent: str) -> dict:
        """role -> (lemma, primitive-set), read from the parse via DEP_TO_SYNTACTIC."""
        roles = {}
        for t in self.nlp(sent):
            r = DEP_TO_SYNTACTIC.get(t.dep_)
            if r:
                wp, _, _ = self.enc._lookup_lexeme(t.lemma_.lower())
                roles[r] = (t.lemma_.lower(), set(wp.keys()))
        return roles

    def _derive(self) -> dict:
        protos = {}
        for frame, sents in EXEMPLARS.items():
            clean = [self._skeleton(s) for s in sents if EXPECT[frame].issubset(self._skeleton(s))]
            n = len(clean)
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
            protos[frame] = Prototype(frame, required, sig, n)
        return protos

    # --- scoring --------------------------------------------------------------
    def _filler_fit(self, roles_prims: dict, proto: Prototype) -> float:
        fits = []
        for r in proto.required:
            qp = roles_prims.get(r, set())
            sp = proto.signature.get(r, set())
            fits.append(len(qp & sp) / len(sp) if sp else 1.0)
        return sum(fits) / len(fits) if fits else 0.0

    def _score_against(self, roles_prims: dict) -> list:
        """Return (frame, shape, filler) for every prototype whose argument-role
        shape matches *exactly* (determiners/modifiers ignored)."""
        out = []
        present = set(roles_prims) & ARGUMENT_ROLES
        for proto in self.protos.values():
            if (proto.required & ARGUMENT_ROLES) == present:
                out.append((proto.name, 1.0, self._filler_fit(roles_prims, proto)))
        return out

    def _prims(self, lemma: str) -> set:
        wp, _, _ = self.enc._lookup_lexeme(lemma.lower())
        return set(wp.keys())

    # --- detection + repair ---------------------------------------------------
    def _literal_roles(self, doc) -> dict:
        roles_prims = {}
        for t in doc:
            r = DEP_TO_SYNTACTIC.get(t.dep_)
            if r:
                roles_prims[r] = self._prims(t.lemma_)
        return roles_prims

    def _enumerate(self, doc) -> list:
        """Tier 1: freeze the dependency *arcs*, permute role labels — including
        which node is the predicate.

        The pivot is any arc-token with a verb sense (ROOT-hood is itself a
        corrupted label in the period-degenerate parse), and its frozen
        arc-neighbors (head + children) take SUBJ/OBJ by linear order.
        """
        cands: list = []
        seen: set = set()
        for pivot in doc:
            if pivot.dep_ == "punct" or not has_verb_sense(pivot.lemma_):
                continue
            neighbors = set(pivot.children)
            if pivot.head.i != pivot.i:  # not the ROOT (which heads itself)
                neighbors.add(pivot.head)
            fillers = [n for n in neighbors if n.dep_ not in _FUNCTION_DEPS]
            pre = sorted((n for n in fillers if n.i < pivot.i), key=lambda n: n.i)
            post = sorted((n for n in fillers if n.i > pivot.i), key=lambda n: n.i)

            roles = {"SYN_PRED": pivot}
            if pre:
                roles["SYN_SUBJ"] = pre[0]
            if post:
                roles["SYN_OBJ"] = post[0]

            roles_prims = {r: self._prims(t.lemma_) for r, t in roles.items()}
            for frame, shape, filler in self._score_against(roles_prims):
                key = (frame, tuple(sorted((r, t.i) for r, t in roles.items())))
                if key in seen:
                    continue
                seen.add(key)
                cands.append(Candidate(dict(roles), frame, shape, filler))
        return cands

    def _false_clean_suspect(self, doc, frame: str) -> bool:
        """A literal frame match that is probably a partial mistag.

        Two dictionary-fact guards (see eyeball/measurement findings):
          1. the matched predicate has no verb sense  -> wrong pivot (Type 2),
          2. the frame has no object slot, the predicate is WordNet-transitive,
             and a nominal sits in a non-argument slot -> dropped object (Type 1).
        """
        pred = next((t for t in doc if DEP_TO_SYNTACTIC.get(t.dep_) == "SYN_PRED"), None)
        if pred is None:
            return False
        if not has_verb_sense(pred.lemma_):
            return True
        # Dropped-object logic applies only to *event* frames missing an object —
        # never to COPULA, whose complement is a predicate, not a patient (and
        # whose verb "be" spuriously registers as WordNet-transitive).
        event_no_obj = frame.startswith("EVENT_") and "SYN_OBJ" not in self.protos[frame].required
        if event_no_obj and has_transitive_frame(pred.lemma_):
            for t in doc:
                # A dropped object is a *direct dependent of the predicate* in a
                # non-argument slot. Requiring t.head is pred excludes possessors
                # (children of the complement) and conjuncts (children of the
                # first conjunct), which otherwise falsely trip the guard.
                # spaCy Tokens aren't identity-stable — compare by index, not `is`.
                if t.i == pred.i or t.dep_ == "punct" or t.head.i != pred.i:
                    continue
                syn = DEP_TO_SYNTACTIC.get(t.dep_)
                if syn in ARGUMENT_ROLES:
                    continue
                if t.pos_ in {"PROPN", "NOUN", "PRON"} or syn == "SYN_ADV_MOD":
                    return True
        return False

    def _clean_result(self, doc, frame: str, literal: dict) -> dict:
        lit_tokens = {DEP_TO_SYNTACTIC[t.dep_]: t.text for t in doc if DEP_TO_SYNTACTIC.get(t.dep_) in ARGUMENT_ROLES}
        return {"verdict": "clean", "frame": frame, "roles": lit_tokens, "literal_slots": sorted(literal)}

    def _enumerated_result(self, doc, literal: dict):
        cands = sorted(self._enumerate(doc), key=lambda c: -c.score)
        if not cands:
            return None
        top = cands[0]
        tied = [c for c in cands if top.score - c.score <= EPS and c.frame != top.frame]
        verdict = "bifurcate" if tied else "commit"
        return {
            "verdict": verdict,
            "literal_slots": sorted(literal),
            "candidates": [
                {
                    "frame": c.frame,
                    "roles": {r: t.text for r, t in c.roles.items()},
                    "shape": round(c.shape, 2),
                    "filler": round(c.filler, 3),
                    "score": round(c.score, 3),
                }
                for c in cands
            ],
        }

    def repair(self, sent: str) -> dict:
        doc = self.nlp(sent)
        literal = self._literal_roles(doc)
        literal_match = self._score_against(literal)
        if literal_match:
            frame = literal_match[0][0]
            # A suspect clean is only overridden if enumeration can do better —
            # never downgrade a good parse to a fallback.
            if self._false_clean_suspect(doc, frame):
                better = self._enumerated_result(doc, literal)
                if better is not None:
                    return better
            return self._clean_result(doc, frame, literal)
        # degraded -> enumerate
        enum = self._enumerated_result(doc, literal)
        if enum is None:
            return {"verdict": "fallback_literal", "literal_slots": sorted(literal)}
        return enum


def _main() -> None:
    rep = Tier1Repair()
    print("=== derived prototypes ===")
    for p in rep.protos.values():
        print(f"  {p.name:14} required={sorted(p.required)}  (n={p.n_clean})")
    print("\n=== repair runs ===")
    for sent in [
        "Macbeth murders Duncan.",  # seam -> recover EVENT_TRANS
        "Duncan compliments Macbeth.",  # seam -> recover EVENT_TRANS
        "Macbeth defeats Cawdor.",  # clean -> no repair
        "Goliath falls.",  # clean intransitive -> no repair
    ]:
        out = rep.repair(sent)
        print(f"\n{sent!r}")
        print(f"   verdict: {out['verdict']}   literal_slots: {out.get('literal_slots')}")
        for c in out.get("candidates", []):
            print(
                f"     -> {c['frame']:14} roles={c['roles']} shape={c['shape']} filler={c['filler']} score={c['score']}"
            )
        if "frame" in out:
            print(f"     -> matched {out['frame']} on the literal parse")


if __name__ == "__main__":
    _main()
