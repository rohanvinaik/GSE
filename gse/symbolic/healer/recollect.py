"""The recollective memory — vibed unknowns recalled BY RESEMBLANCE (Law-as-Architecture §6).

The structural lenses (the law = the topology) carry the inference; each RECOVER-AND-ATTACH lens
(participial / infinitival / vp_coord) leaves ONE thin unknown the structure cannot supply: the
**subject binding** — which entity the recovered EVENT predicates. That vibed unknown is what lives
here, "recalled by resemblance rather than re-derived from scratch per instance or frozen into
weights" (the paper's Recollective-Memory thesis).

This is Minsky's K-line rendered as a hypervector over GSE's OWN ternary substrate (`vectors_v2`),
NOT an activation-set rule and NOT frequency statistics:

  KEY    = a hypervector of the instance CONTEXT — the local-token-context structural signature
           (prev-class, possessor/object/coordination markers, clause depth, participle distance),
           the participle's word-strand NSM character, and the REGIME (genre) — the paper's
           "geometry, log character, regime."
  VALUE  = the vibed unknown: the subject-binding SELECTOR as an entity-free SLOT DESCRIPTOR
           (animacy / pos-class / sentence-initial / clause-head / possessor / object / distance) —
           NEVER the referent (della/joe is too specific) and NEVER the whole clean statement (an
           over-flexible value destroys the coefficient's identifiability — §5).
  RECALL  = cosine-nearest stored CONTEXTS vote (closeness-weighted) a target slot descriptor; the
           live candidate whose own descriptor most resembles it is bound; closeness IS the recall
           confidence that feeds the abstention censor (clean-or-hole).

Encoding discipline: features are atomic codebook symbols minted via GSE's `generate_role_pattern`
(orthogonal, native to the substrate) and composed by `bundle` (superposition — verified
cosine-recoverable). Binding is avoided: `generate_role_pattern` uses disjoint partitions, so binding
two role symbols collapses; bundling is the correct VSA op for a resemblance key. Recall is a linear
cosine scan (brute force is exact and trivial at corpus scale).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Tuple

from gse.vectors_v2 import (
    SparseVector,
    bundle,
    generate_role_pattern,
    weighted_bundle,
)

# --- surface lexical classes (the key/descriptor vocabulary's grounding) --------------------------

_PERS_PRON = {"he", "she", "they", "i", "we", "you", "it"}
_OBJ_PRON = {"it", "him", "her", "them", "us", "me"}
_BE = {"be", "am", "is", "are", "was", "were", "been", "being"}
_COORD = {"and", "or", "but", "nor"}
_SUBORD = {"while", "as", "when", "after", "before", "though", "although", "since"}

_ROLE_CAPACITY = 170  # generate_role_pattern: 1024 // 6 dims-per-role


# =================================================================================================
# The native feature codebook — atomic symbol HVs over GSE's ternary substrate
# =================================================================================================


class FeatureCodebook:
    """Maps a closed set of feature SYMBOLS to orthogonal ternary HVs via `generate_role_pattern`.

    Symbols are assigned a stable index on first request and persisted, so a saved memory reloads to
    the same geometry. The codebook is native: every HV is a GSE role pattern, the same substrate the
    signals live in.
    """

    def __init__(self, symbol_index: Optional[Dict[str, int]] = None):
        self._index: Dict[str, int] = dict(symbol_index or {})
        self._hv: Dict[str, SparseVector] = {}

    def index_of(self, symbol: str) -> int:
        idx = self._index.get(symbol)
        if idx is None:
            idx = len(self._index)
            if idx >= _ROLE_CAPACITY:
                raise ValueError(
                    f"feature codebook exceeded {_ROLE_CAPACITY} symbols at {symbol!r}"
                )
            self._index[symbol] = idx
        return idx

    def hv(self, symbol: str) -> SparseVector:
        v = self._hv.get(symbol)
        if v is None:
            v = generate_role_pattern(role_index=self.index_of(symbol))
            self._hv[symbol] = v
        return v

    def encode(self, symbols: List[str]) -> SparseVector:
        """Bundle (superpose) a list of feature symbols into one context/descriptor HV."""
        if not symbols:
            return SparseVector.zeros(generate_role_pattern(0).dimension)
        return bundle([self.hv(s) for s in symbols])

    def to_dict(self) -> Dict[str, int]:
        return dict(self._index)


# =================================================================================================
# Feature extraction — the literal-token-context signature (surface structure only)
# =================================================================================================


def _is_nominal(t) -> bool:
    return (t.lemma or "").lower() in _PERS_PRON or t.pos in ("PROPN", "NOUN")


def _is_possessor(trace, t) -> bool:
    nxt = trace.tokens[t.position + 1] if t.position + 1 < len(trace.tokens) else None
    if nxt is None:
        return False
    return (nxt.token or "").startswith(("'", "’")) and (nxt.token or "").lower().endswith("s")


def _is_object_pron(trace, t) -> bool:
    if (t.lemma or "").lower() not in _OBJ_PRON:
        return False
    prev = trace.tokens[t.position - 1] if t.position - 1 >= 0 else None
    return prev is not None and prev.pos == "VERB" and (prev.lemma or "").lower() not in _BE


def _nearest_finite_verb(trace, p: int) -> Optional[int]:
    vpos = None
    for t in trace.tokens:
        if t.position < p and t.pos == "VERB":
            lem = (t.lemma or "").lower()
            if lem not in _BE and not (t.token or "").lower().endswith("ing"):
                vpos = t.position
    return vpos


def candidate_nominals(trace, p: int) -> List:
    """Every nominal token strictly before the participle — the live attachment candidates."""
    return [t for t in trace.tokens if t.position < p and _is_nominal(t)]


def _pos_class(t) -> str:
    if (t.lemma or "").lower() in _PERS_PRON:
        return "SF_PRON"
    if t.pos == "PROPN":
        return "SF_PROPN"
    return "SF_NOUN"


def _dist_bucket(prefix: str, d: int) -> str:
    return prefix + ("0_3" if d <= 3 else "4_7" if d <= 7 else "8_15" if d <= 15 else "16P")


def slot_descriptor_symbols(trace, tok, p: int, finite_v: Optional[int]) -> List[str]:
    """Entity-FREE surface descriptor of a candidate slot — the same schema for the stored VALUE
    (the gold subject) and for each live candidate at recall."""
    syms = [_pos_class(tok)]
    syms.append("SF_ANIMATE" if (tok.lemma or "").lower() in _PERS_PRON or tok.pos == "PROPN"
                else "SF_INANIMATE")
    if tok.position <= 1:
        syms.append("SF_SENT_INITIAL")
    survivor = not _is_possessor(trace, tok) and not _is_object_pron(trace, tok)
    if survivor and (finite_v is None or tok.position < finite_v):
        syms.append("SF_CLAUSE_HEAD")
    if _is_possessor(trace, tok):
        syms.append("SF_POSSESSOR")
    if _is_object_pron(trace, tok):
        syms.append("SF_OBJECT")
    syms.append(_dist_bucket("SDIST_", p - tok.position))
    return syms


def context_symbols(trace, p_tok, genre: str, mangle: str = "") -> List[str]:
    """The SUPERPOSITION signature (the training key, user's design): the firing-pattern + the
    mangle/hole shape + the full envelope context + regime (genre), bundled into one hypervector. One
    Brown-baseline library holds every form; the ``MANGLE_<shape>`` / ``FIRING_<lens>`` tag is what lets
    a single library separate the forms while sharing the substrate (the superposition of firing
    patterns). ``mangle`` = the recover-and-attach shape the firing lens detected (participial /
    infinitival / vpcoord)."""
    p = p_tok.position
    syms: List[str] = []
    if mangle:
        syms.append("MANGLE_" + mangle)        # the hole shape = the specific lens firing-pattern
        syms.append("FIRING_" + mangle)

    # prev-class (what the participle hangs off)
    if p - 1 < 0:
        syms.append("PREV_START")
    else:
        prev = trace.tokens[p - 1]
        pl = (prev.token or "").lower(); plem = (prev.lemma or "").lower()
        if pl == ",":
            syms.append("PREV_COMMA")
        elif plem in _COORD:
            syms.append("PREV_COORD")
        elif plem in _SUBORD:
            syms.append("PREV_SUBORD")
        elif prev.pos == "VERB" and plem not in _BE:
            syms.append("PREV_VERB")
        else:
            syms.append("PREV_OTHER")

    cands = candidate_nominals(trace, p)
    finite_v = _nearest_finite_verb(trace, p)

    # structural markers (the discriminating signal the analysis pass surfaced)
    if any(_is_possessor(trace, t) for t in cands):
        syms.append("HAS_POSSESSOR")
    if any(_is_object_pron(trace, t) for t in cands):
        syms.append("HAS_OBJ_INTERVENE")
    if sum(1 for t in cands if (t.lemma or "").lower() in _PERS_PRON or t.pos == "PROPN") >= 2:
        syms.append("MULTI_ANIMATE")

    # the decision is almost always "sentence-subject vs nearest-animate": tag the two
    # decision-relevant candidates' descriptors into the key so contexts with the same COMPETITION
    # SHAPE cluster (the diagnosed fix for same-selector clustering — keeps recall sharp).
    if cands:
        for s in slot_descriptor_symbols(trace, cands[-1], p, finite_v):   # NEAREST to participle
            syms.append("NEAR_" + s)
        for s in slot_descriptor_symbols(trace, cands[0], p, finite_v):    # FIRST / leftmost
            syms.append("FIRST_" + s)
        if cands[0].position == cands[-1].position:
            syms.append("NEAR_IS_FIRST")   # single dominant candidate — the easy case

    # clause depth + participle distance buckets
    depth = sum(1 for t in trace.tokens if t.position < p and t.pos == "VERB"
                and (t.lemma or "").lower() not in _BE and not (t.token or "").lower().endswith("ing"))
    syms.append("DEPTH_" + ("0" if depth == 0 else "1" if depth == 1 else "2" if depth == 2 else "3P"))
    syms.append(_dist_bucket("PDIST_", p))

    # candidate-field summary (how crowded / what's available)
    n = len(cands)
    syms.append("NCAND_" + ("0" if n == 0 else "1" if n == 1 else "2" if n == 2 else "3P"))
    if any((t.lemma or "").lower() in _PERS_PRON or t.pos == "PROPN" for t in cands):
        syms.append("HAS_ANIMATE_CAND")

    # word strand (NSM character of the participle; often empty — that's the multi-strand point)
    for name in sorted((p_tok.word_primitives or {}).keys()):
        syms.append("WP_" + str(name))

    # regime
    syms.append("GENRE_" + (genre or "unknown"))
    return syms


# =================================================================================================
# The recollective memory
# =================================================================================================


@dataclass
class _Entry:
    key_syms: FrozenSet[str]
    value_syms: FrozenSet[str]
    freq: int = 1
    strength: float = 1.0
    key_hv: Optional[SparseVector] = field(default=None, compare=False)
    value_hv: Optional[SparseVector] = field(default=None, compare=False)


@dataclass
class Recollection:
    """The outcome of a recall: the bound candidate index (into the live candidate list) and the
    closeness confidence the abstention censor reads. ``index is None`` ⇒ abstain (honest hole)."""
    index: Optional[int]
    confidence: float
    resemblance: float  # mean cosine to the recalled contexts


class RecollectiveMemory:
    """Resemblance-addressed store of subject-binding selectors over GSE's ternary substrate."""

    def __init__(self, codebook: Optional[FeatureCodebook] = None):
        self.cb = codebook or FeatureCodebook()
        self._entries: List[_Entry] = []
        self._by_key: Dict[FrozenSet[str], _Entry] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def _hv(self, e: _Entry) -> Tuple[SparseVector, SparseVector]:
        if e.key_hv is None:
            e.key_hv = self.cb.encode(sorted(e.key_syms))
        if e.value_hv is None:
            e.value_hv = self.cb.encode(sorted(e.value_syms))
        return e.key_hv, e.value_hv

    def store(self, key_syms: List[str], value_syms: List[str]) -> _Entry:
        """Add a context→selector case, or reinforce an identical one (K-line frequency/strength)."""
        kf, vf = frozenset(key_syms), frozenset(value_syms)
        existing = self._by_key.get(kf)
        if existing is not None and existing.value_syms == vf:
            existing.freq += 1
            existing.strength = min(10.0, existing.strength + 0.05)
            return existing
        e = _Entry(key_syms=kf, value_syms=vf)
        self._entries.append(e)
        self._by_key[kf] = e  # last-writer wins on identical key, different value (the field disagrees)
        return e

    def recall(
        self,
        query_key_syms: List[str],
        candidate_descriptor_syms: List[List[str]],
        top_k: int = 3,   # SHARP recall: a broad blend washes the discriminating slot feature (diagnosed)
        min_resemblance: float = 0.30,
    ) -> Recollection:
        """Recall the subject-binding by resemblance, then bind the closest live candidate."""
        if not self._entries or not candidate_descriptor_syms:
            return Recollection(index=None, confidence=0.0, resemblance=0.0)

        q = self.cb.encode(sorted(set(query_key_syms)))
        scored: List[Tuple[_Entry, float]] = []
        for e in self._entries:
            khv, _ = self._hv(e)
            sim = q.cosine(khv)
            if sim >= min_resemblance:
                scored.append((e, sim))
        if not scored:
            return Recollection(index=None, confidence=0.0, resemblance=0.0)

        scored.sort(key=lambda x: -x[1])
        scored = scored[:top_k]

        # closeness-weighted blend of the recalled selectors (reconstructive recall)
        vhvs = [self._hv(e)[1] for e, _ in scored]
        weights = [sim * e.strength for e, sim in scored]
        target = weighted_bundle(vhvs, weights)

        # bind the live candidate whose own descriptor most resembles the recalled selector
        best_i, best_sim = None, -1.0
        for i, syms in enumerate(candidate_descriptor_syms):
            sim = target.cosine(self.cb.encode(sorted(set(syms))))
            if sim > best_sim:
                best_i, best_sim = i, sim

        resemblance = sum(s for _, s in scored) / len(scored)
        confidence = max(0.0, best_sim) * resemblance
        return Recollection(index=best_i, confidence=confidence, resemblance=resemblance)

    # --- persistence: symbol-sets + codebook only; HVs reconstruct deterministically -------------

    def save(self, path: str) -> None:
        data = {
            "codebook": self.cb.to_dict(),
            "entries": [
                {"k": sorted(e.key_syms), "v": sorted(e.value_syms), "f": e.freq, "s": e.strength}
                for e in self._entries
            ],
        }
        with open(path, "w") as fh:
            json.dump(data, fh)

    @classmethod
    def load(cls, path: str) -> "RecollectiveMemory":
        with open(path) as fh:
            data = json.load(fh)
        mem = cls(FeatureCodebook(data.get("codebook")))
        for it in data["entries"]:
            e = _Entry(key_syms=frozenset(it["k"]), value_syms=frozenset(it["v"]),
                       freq=it["f"], strength=it["s"])
            mem._entries.append(e)
            mem._by_key[e.key_syms] = e
        return mem


# =================================================================================================
# Seam adapter — build the K-line query from the ENVELOPE (the trace-less repair seam)
# =================================================================================================
#
# The lens runs downstream of the parse, where the OperationTrace is gone; the envelope is the
# parse-time mark that carries the token stream (surface/lemma/pos/prev/next/prims per position). The
# same feature extractors above run over a lightweight adapter built from it — no trace, no new fields.


@dataclass
class _Tok:
    position: int
    token: str
    lemma: str
    pos: str
    word_primitives: dict


class _EnvAdapter:
    """Mimics a trace (`.tokens`, position == list index) so the extractors run unchanged."""

    def __init__(self, tokens: List[_Tok]):
        self.tokens = tokens


def _adapter_from_env(env) -> Tuple[_EnvAdapter, Dict[int, int]]:
    poss = sorted(env.surface)
    toks = [
        _Tok(position=i, token=env.surface.get(pos, ""),
             lemma=(env.lemma.get(pos) or env.surface.get(pos, "")).lower(),
             pos=env.pos.get(pos, ""), word_primitives=env.prims.get(pos, {}) or {})
        for i, pos in enumerate(poss)
    ]
    return _EnvAdapter(toks), {pos: i for i, pos in enumerate(poss)}


def envelope_query(env, position: int, mangle: str = ""):
    """Build the recall query for a mangle at ``position`` from the envelope:
    ``(key_syms, [(candidate_lemma, descriptor_syms), …])``. The firing lens passes its ``mangle`` tag
    so the query carries the same superposition signature the library was trained on. Returns ``None``
    if the position is absent or there are no candidates."""
    adapter, posmap = _adapter_from_env(env)
    pidx = posmap.get(position)
    if pidx is None:
        return None
    p_tok = adapter.tokens[pidx]
    cands = candidate_nominals(adapter, pidx)
    if not cands:
        return None
    fv = _nearest_finite_verb(adapter, pidx)
    key = context_symbols(adapter, p_tok, getattr(env, "genre", None) or "unknown", mangle)
    out = [((c.lemma or "").lower(), slot_descriptor_symbols(adapter, c, pidx, fv)) for c in cands]
    return key, out


# --- warm lazy loader (load once, ride — the deployed memory's home) -----------------------------

_MEM_CACHE: Dict[str, Optional["RecollectiveMemory"]] = {}


def default_memory_path(name: str = "participial") -> str:
    """Per-type memory home (``data/healer_klines/<name>.json``); env override for the participial
    default keeps the old single-memory contract. Each RECOVER-AND-ATTACH lens owns its own memory
    (regime separation, §8) — participial / infinitival / vp_coord."""
    if name == "participial" and os.environ.get("GENESIS_HEALER_KLINES"):
        return os.environ["GENESIS_HEALER_KLINES"]
    return str(Path(__file__).resolve().parents[3] / "data" / "healer_klines" / f"{name}.json")


def default_memory(path: Optional[str] = None, name: str = "participial") -> Optional["RecollectiveMemory"]:
    """The warm, resident recollective memory for a mangle type (cached). Returns ``None`` if not yet
    trained/persisted — the lens then abstains exactly as before (graceful: no memory ⇒ honest hole)."""
    p = path or default_memory_path(name)
    if p not in _MEM_CACHE:
        try:
            _MEM_CACHE[p] = RecollectiveMemory.load(p)
        except Exception:
            _MEM_CACHE[p] = None
    return _MEM_CACHE[p]
