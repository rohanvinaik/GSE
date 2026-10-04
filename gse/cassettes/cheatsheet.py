"""The cheat-sheet — how the cassette resolutions inform CORRECTION of the spine, catalytically.

Confirmed mechanism (Rohan, + the AIMO3 pipeline `pipeline_architecture.md`): there are (1) the clean
deterministic spine, and (2) the cheat-sheet (the deck's committed resolutions); the cheat-sheet is used
to INFORM CORRECTION of the errors in (1). It is NOT a raw-text rewrite — that mutates the canonical IR
and was measured DESTRUCTIVE (it deleted "Duncan"). Instead this follows AIMO3's two laws:

  CATALYTIC DISCIPLINE (§1.1) — a stage READS shared state and EMITS a new artifact; it never mutates
      shared state in place. So ``correct_contracts`` reads the emitted spine + the cheat-sheet and
      RETURNS a corrected copy; the input contracts are untouched.
  COHERENCE-BY-CONFIDENCE (§3) — each cheat-sheet record carries a confidence; a correction applies only
      when it clears a threshold, and the highest-confidence record wins per referent. A low-confidence
      cassette signal never overrides a clean spine value.

The cheat-sheet is also the ride-along artifact "passed to the bridge/envelope" — ``to_records()``
emits it as typed evidence (slot/value/confidence/strategy/provenance), the same shape as AIMO3's
``MathEvidence`` ledger rows, so any consumer can aggregate it without knowing the cassettes.

SCOPE NOTE: a MERGE relabels entity_ids on the EMITTED spine (post-parse, non-destructive — only ids
and the canonical lemma change). A SPLIT must be applied at the PRE-COMPACTION seam (the two referents
are already one id once compaction collapses them), so it is recorded here but applied where the bridge
runs the deck before ``compress`` — see the wiring. Nothing here is destructive: an abstention emits no
record, and a correction only RELABELS, never deletes.
"""

from __future__ import annotations

import copy
import dataclasses as _dc
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .deck import DeckResult


@dataclass
class CheatSheet:
    """The committed resolutions as typed, confidence-tagged correction records — the ride-along artifact.

    ``merges`` maps a description lemma → (canonical name lemma, confidence, provenance). ``splits``
    records a collapsed lemma → its contrastive groups. ``min_confidence`` gates application."""

    merges: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    splits: List[Dict[str, Any]] = field(default_factory=list)
    min_confidence: float = 2.0

    def to_records(self) -> List[dict]:
        """Emit as typed evidence rows (AIMO3 ``MathEvidence`` shape) — the ride-along the bridge passes
        to the envelope. ``slot`` = what it corrects, ``strategy`` = CASSETTE, ``confidence`` weights it."""
        rows = []
        for desc, m in self.merges.items():
            rows.append(
                {
                    "slot": "entity_identity",
                    "value": f"{desc} ≡ {m['name']}",
                    "kind": "merge",
                    "subject": desc,
                    "answer": m["name"],
                    "confidence": m["confidence"],
                    "strategy": "CASSETTE",
                    "provenance": m.get("provenance", {}),
                }
            )
        for s in self.splits:
            rows.append(
                {
                    "slot": "entity_identity",
                    "value": f"{s['lemma']} → {s['groups']}",
                    "kind": "split",
                    "subject": s["lemma"],
                    "answer": s["groups"],
                    "confidence": s["confidence"],
                    "strategy": "CASSETTE",
                }
            )
        return rows


def build_cheatsheet(result: DeckResult, doc, min_confidence: float = 2.0) -> CheatSheet:
    """Project a DeckResult into the lemma-keyed correction artifact. ``doc`` supplies the name's
    canonical lemma for each committed merge target id."""
    cs = CheatSheet(min_confidence=min_confidence)
    for e in result.entries:
        desc_lemma = _split_lemma(e)
        if e.kind == "merge":
            name_lemma = _canonical_name(doc, e.answer)
            if name_lemma and desc_lemma and name_lemma != desc_lemma:
                cs.merges[desc_lemma] = {
                    "name": name_lemma,
                    "name_span": _canonical_span(doc, e.answer),
                    "confidence": e.confidence,
                    "provenance": {"strands": e.strands, "name_eid": e.answer, "desc_eid": e.eid},
                }
        elif e.kind == "split":
            cs.splits.append({"lemma": desc_lemma, "groups": e.answer, "confidence": e.confidence})
    return cs


def correct_contracts(contracts: List[dict], cs: CheatSheet) -> List[dict]:
    """CATALYTIC merge correction: read the emitted spine + cheat-sheet → RETURN a corrected COPY.

    For each committed merge (desc-lemma → name-lemma) above the confidence floor, relabel every spine
    operand whose lemma == the description to the name's canonical entity_id + lemma + type_thread —
    the fragmented referent becomes one. The input is never mutated; only ids/lemmas are relabeled
    (never deleted), so no correct value is destroyed. SPLITs are not applied here (post-compaction;
    see module docstring)."""
    out = copy.deepcopy(contracts)
    # canonical (entity_id, type_thread) for each name lemma, harvested from the spine itself
    canon: Dict[str, Dict[str, Any]] = {}
    for c in out:
        for op in _operands(c):
            lemma = (op.get("lemma") or "").lower()
            if lemma in {m["name"] for m in cs.merges.values()} and lemma not in canon:
                canon[lemma] = {"entity_id": op.get("entity_id"), "type_thread": op.get("type_thread") or []}
    applied = 0
    for c in out:
        for op in _operands(c):
            lemma = (op.get("lemma") or "").lower()
            rec = cs.merges.get(lemma)
            if rec and rec["confidence"] >= cs.min_confidence and rec["name"] in canon:
                tgt = canon[rec["name"]]
                op["entity_id"] = tgt["entity_id"]  # relabel — non-destructive
                op["lemma"] = rec["name"]
                if tgt["type_thread"]:
                    op["type_thread"] = tgt["type_thread"]
                op.setdefault("_corrected", []).append(f"cassette:{lemma}≡{rec['name']}")
                applied += 1
    return out


# -- helpers ----------------------------------------------------------------
def _operands(contract: dict):
    """Every grounded operand anywhere in a contract — an EVENT agent/patient, but ALSO a
    TypeAssertion/Equality/Comparison side (the NAME of a stated identity, "Merope is the mother",
    lives there, not in an EVENT arg). Recursive: any nested dict carrying an entity_id is an operand."""
    seen: set = set()

    def walk(node):
        if isinstance(node, dict):
            if "entity_id" in node and "lemma" in node and id(node) not in seen:
                seen.add(id(node))
                yield node
            for v in node.values():
                yield from walk(v)
        elif isinstance(node, list):
            for x in node:
                yield from walk(x)

    if isinstance(contract, dict):
        yield from walk(contract)


def _canonical_name(doc, eid: str) -> Optional[str]:
    for m in doc.by_id.get(eid, []):
        if m.pos == "PROPN":
            return m.lemma
    ms = doc.by_id.get(eid, [])
    return ms[0].lemma if ms else None


def _canonical_span(doc, eid: str) -> tuple:
    """The PROPN mention's demi-word span (``()`` for a bare name, ``(lady, macbeth)`` for a titled
    one) — disambiguates names that share a head lemma when the relabel target is resolved."""
    for m in doc.by_id.get(eid, []):
        if m.pos == "PROPN":
            return tuple(m.span or ())
    return ()


def _split_lemma(entry) -> str:
    return entry.subject.split("[")[0] if isinstance(entry.subject, str) else str(entry.subject)


# -- PRE-COMPACTION application: the cheat-sheet's MERGEs at the from_document(repair=) seam --------
#
# correct_contracts (above) relabels EMITTED contract dicts — useful in the no-compact projection,
# but POST-compaction the compactor has already dropped the minor referents (heir/merope), so the
# merge has nothing left to thread. The load-bearing application is therefore at the SAME seam the
# statement-healer uses: ``NarrativeGraph.from_document(repair=...)``, over the WIDE statement set,
# BEFORE the collapse. ``make_merge_repair`` builds a repair pass with that exact contract
# (``[(t, predicate), ...] -> [(t, predicate), ...]``) so it COMPOSES with the healer hook — run the
# healer first (statement-formation laws), then this (identity normalization). It is NOT a lens
# inside the Society: a node a healer lens claims is ``break``-ed before any other lens sees it
# (one-law-per-node), but a predicate can need both a healer repair AND an identity relabel — two
# sequential full passes give both. Catalytic + non-destructive: only ``entity_id`` is relabeled
# toward the stated identity (never a lemma, a verb, or a deletion), so no correct value is destroyed.


def build_relabel_map(cs: CheatSheet, resolved_trees: List[Any]) -> Dict[str, str]:
    """Resolve each committed MERGE (desc-lemma → name-lemma, above the floor) to a
    ``{desc_lemma: canonical_entity_id}`` map IN THE CONSUMER'S id-space.

    The cheat-sheet is lemma-keyed precisely so it is portable across grounding passes (the cassette
    deck reads the raw text on its own pass; the bridge's resolved trees carry their own ids). Here we
    pin each NAME to a proper-noun ``entity_id`` in the SAME trees ``from_document`` will collapse, so
    the relabel lands in the right id-space. A merge whose name has no proper referent in these trees
    is skipped (nothing to thread to — honest non-recovery, never a guess)."""
    from gse.symbolic.healer.treewalk import walk
    from gse.symbolic.resolution import Entity

    # Each committed merge wants (name_lemma, name_span). The SPAN disambiguates names that share a
    # head lemma — "Macbeth" (span ()) vs "Lady Macbeth" (span lady,macbeth) — so a relational merge
    # threads "her husband" to the bare agent, never to his titled wife.
    wanted = {
        desc: (rec["name"], tuple(rec.get("name_span") or ()))
        for desc, rec in cs.merges.items()
        if rec["confidence"] >= cs.min_confidence
    }
    if not wanted:
        return {}
    by_lemma_span: Dict[tuple, str] = {}
    by_lemma: Dict[str, str] = {}
    for tree in resolved_trees:
        for n in walk(tree):
            if not isinstance(n, Entity) or not n.head or not n.entity_id or n.head.pos != "PROPN":
                continue
            lem = (n.head.lemma or "").lower()
            sp = tuple(getattr(n, "span", ()) or ())
            by_lemma_span.setdefault((lem, sp), n.entity_id)
            by_lemma.setdefault(lem, n.entity_id)
    out: Dict[str, str] = {}
    for desc, (name, name_span) in wanted.items():
        eid = by_lemma_span.get((name, name_span)) or by_lemma.get(name)  # exact span, else any
        if eid:
            out[desc] = eid
    return out


def make_merge_repair(relabel_map: Dict[str, str]) -> Callable[[List[tuple]], List[tuple]]:
    """Build the pre-compaction repair pass that applies the cheat-sheet's MERGEs.

    Contract matches ``NarrativeGraph.from_document(repair=...)``: ``[(t, predicate), ...] ->
    [(t, predicate), ...]``. For every ``Entity`` whose head lemma is a committed merge description,
    its ``entity_id`` is relabeled to the canonical name's id — so the fragmented referent is ONE
    before the collapse and survives compaction. Empty map → an inert pass-through (safe to wire
    before any merge lands). Non-destructive: only ``entity_id`` changes; predicates are rebuilt by
    ``dataclasses.replace`` (the inputs are frozen), nothing is deleted."""
    if not relabel_map:
        return lambda timed: timed

    def hook(timed: List[tuple]) -> List[tuple]:
        return [(t, _relabel_node(p, relabel_map)) for (t, p) in timed]

    return hook


def _relabel_node(node: Any, relabel_map: Dict[str, str]) -> Any:
    """Recursively rebuild a frozen predicate/operand, relabeling any ``Entity`` whose head lemma is
    in ``relabel_map`` to that canonical ``entity_id``. Returns the SAME object when nothing changes
    (so ``is not`` identity checks upstream stay cheap and correct)."""
    from gse.symbolic.resolution import Entity

    if isinstance(node, Entity):
        lem = (node.head.lemma or "").lower() if node.head else ""
        new_poss = _relabel_node(node.possessor, relabel_map) if node.possessor is not None else None
        changes: Dict[str, Any] = {}
        tgt = relabel_map.get(lem)
        if tgt and node.entity_id != tgt:
            changes["entity_id"] = tgt
        if new_poss is not node.possessor:
            changes["possessor"] = new_poss
        return _dc.replace(node, **changes) if changes else node
    if _dc.is_dataclass(node) and not isinstance(node, type):
        changes = {}
        for f in _dc.fields(node):
            v = getattr(node, f.name)
            nv = _relabel_value(v, relabel_map)
            if nv is not v:
                changes[f.name] = nv
        return _dc.replace(node, **changes) if changes else node
    return node


def _relabel_value(v: Any, relabel_map: Dict[str, str]) -> Any:
    from gse.symbolic.resolution import Entity

    if isinstance(v, Entity) or (_dc.is_dataclass(v) and not isinstance(v, type)):
        return _relabel_node(v, relabel_map)
    if isinstance(v, tuple):
        items = [_relabel_value(x, relabel_map) for x in v]
        return tuple(items) if any(a is not b for a, b in zip(items, v)) else v
    if isinstance(v, list):
        items = [_relabel_value(x, relabel_map) for x in v]
        return items if any(a is not b for a, b in zip(items, v)) else v
    return v


# -- AGENT-ELIGIBILITY: re-type an ineligible referent so person-typed frames self-reject it -----------
#
# The engine keys ``x is a person`` off the entity's emitted ``type_thread`` (GseWalker), and an
# entity with an EMPTY thread defaults to person-eligible — so a PLACE (bosnia) or a plural COLLECTIVE
# (patriots/loyalists) with no thread fires the person-typed frames (relationship objectification,
# narrative_base harm-chains, …) as if it were an individual person. The agent-eligibility cassette
# detects these and this repair injects a POSITIVE non-person ``type_thread`` (location / group), so
# the same person-typed frames self-reject them. Non-destructive: only ``type_thread`` is set (the
# referent, its id, and every predicate stay intact — nothing is dropped); untyped frames are
# unaffected. Composes at the same ``from_document(repair=)`` seam as the merge repair.


def make_retype_repair(retype_map: Dict[str, tuple]) -> Callable[[List[tuple]], List[tuple]]:
    """Build the pre-compaction repair that OVERWRITES the ``type_thread`` of each ineligible agent.

    ``retype_map``: ``{head_lemma: (non_person_type, …)}`` (e.g. ``{"bosnia": ("location",),
    "patriots": ("group",)}``). Empty map → inert pass-through."""
    if not retype_map:
        return lambda timed: timed

    def hook(timed: List[tuple]) -> List[tuple]:
        return [(t, _retype_node(p, retype_map)) for (t, p) in timed]

    return hook


def _retype_node(node: Any, retype_map: Dict[str, tuple]) -> Any:
    from gse.symbolic.resolution import Entity

    if isinstance(node, Entity):
        lem = (node.head.lemma or "").lower() if node.head else ""
        new_poss = _retype_node(node.possessor, retype_map) if node.possessor is not None else None
        changes: Dict[str, Any] = {}
        tgt = retype_map.get(lem)
        if tgt is not None and tuple(getattr(node, "type_thread", ()) or ()) != tuple(tgt):
            changes["type_thread"] = tuple(tgt)
        if new_poss is not node.possessor:
            changes["possessor"] = new_poss
        return _dc.replace(node, **changes) if changes else node
    if _dc.is_dataclass(node) and not isinstance(node, type):
        changes = {}
        for f in _dc.fields(node):
            v = getattr(node, f.name)
            nv = _retype_value(v, retype_map)
            if nv is not v:
                changes[f.name] = nv
        return _dc.replace(node, **changes) if changes else node
    return node


def _retype_value(v: Any, retype_map: Dict[str, tuple]) -> Any:
    from gse.symbolic.resolution import Entity

    if isinstance(v, Entity) or (_dc.is_dataclass(v) and not isinstance(v, type)):
        return _retype_node(v, retype_map)
    if isinstance(v, tuple):
        items = [_retype_value(x, retype_map) for x in v]
        return tuple(items) if any(a is not b for a, b in zip(items, v)) else v
    if isinstance(v, list):
        items = [_retype_value(x, retype_map) for x in v]
        return items if any(a is not b for a, b in zip(items, v)) else v
    return v
