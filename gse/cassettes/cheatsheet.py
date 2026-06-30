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
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
            rows.append({"slot": "entity_identity", "value": f"{desc} ≡ {m['name']}",
                         "kind": "merge", "subject": desc, "answer": m["name"],
                         "confidence": m["confidence"], "strategy": "CASSETTE",
                         "provenance": m.get("provenance", {})})
        for s in self.splits:
            rows.append({"slot": "entity_identity", "value": f"{s['lemma']} → {s['groups']}",
                         "kind": "split", "subject": s["lemma"], "answer": s["groups"],
                         "confidence": s["confidence"], "strategy": "CASSETTE"})
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
                    "name": name_lemma, "confidence": e.confidence,
                    "provenance": {"strands": e.strands, "name_eid": e.answer, "desc_eid": e.eid}}
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
                canon[lemma] = {"entity_id": op.get("entity_id"),
                                "type_thread": op.get("type_thread") or []}
    applied = 0
    for c in out:
        for op in _operands(c):
            lemma = (op.get("lemma") or "").lower()
            rec = cs.merges.get(lemma)
            if rec and rec["confidence"] >= cs.min_confidence and rec["name"] in canon:
                tgt = canon[rec["name"]]
                op["entity_id"] = tgt["entity_id"]      # relabel — non-destructive
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


def _split_lemma(entry) -> str:
    return entry.subject.split("[")[0] if isinstance(entry.subject, str) else str(entry.subject)
