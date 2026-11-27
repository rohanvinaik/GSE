"""The authored bank laws compiled into relations (design E4; `bank_laws.json`).

The laws are founder-approved or source-justified (F043, F067, F088, F144). Each names its banks, the joint values it
permits, its guard and its warrant. A value "empty" is SILENT. A law applies to the readings its guard selects; the
guard's facts come from `guards.py` and the source lenses, never from the law itself.

Three authored blocks compile into relations:

- `laws`: each law is one relation over its coordinates.
- A source rule's `definition_boundary` (EMOTION_FEAR_ADJ's GSE_FEAR_ADJ_BOUNDARY_V1). Each SILENT cell is an
  authored silence and becomes SILENT under the boundary's guard. Each OPTIONAL cell keeps exactly its authored
  domain, which removes states but writes no value. A REQUIRED cell is "Checked obligation only: ... the family
  boundary supplies no missing content", so it is never written. It is a check (`required_checks`), reported after
  closure as derived, open or contradicted.
- A source rule's `companions`: the content the rule states of its own reading alongside its coordinate, for example
  the Fear class's "every published wording of the Fear class has FEEL, THINK, LIKE, WHEN and BECAUSE". The
  companions apply under the guard of every reading fact the rule establishes, so they reach a reading only when the
  rule's own facts are established for it.

Not compiled:
- a boundary's HIER_PLUS and HIER_MINUS cells, which are not banks of the registry (`uncompiled_cells`);
- a source rule's `relations` (NEGATED_DESIRE), which is already the law FEAR_AVERSION, with the same guard and
  warrant;
- `model_selection_policy`, which is WITHHELD (design E12).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .cells import ALL, BANK_INDEX, NEG, POS, SILENT, ZERO
from .relations import Relation

LAWS = Path(__file__).with_name("bank_laws.json")
_VALUE = {"+1": POS, "-1": NEG, "0": ZERO, "empty": SILENT}


@dataclass(frozen=True)
class Check:
    """A REQUIRED boundary cell: under `scope`, other rules must derive `bank` within `allowed`; it writes nothing."""

    rule_id: str
    bank: str
    allowed: int
    scope: str
    reason: str


def scope_name(guard) -> str:
    return "&".join(f"{k}={v}" for k, v in sorted(tuple(g) for g in guard))


def mask(values) -> int:
    out = 0
    for v in values:
        out |= _VALUE[v]
    return out


def reading_facts(rule: dict) -> list[tuple[str, str]]:
    """The facts a source rule establishes of the reading it binds: its `reading_facts` and its `own_role`."""
    facts = [(k, v) for k, v in rule.get("reading_facts", [])]
    if rule.get("own_role"):
        facts.append(("own_role", rule["own_role"]))
    return facts


def _book(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def _authored(book: dict) -> list[Relation]:
    return [
        Relation(
            rule_id=f"law:{law['rule_id']}",
            banks=tuple(law["coordinates"]),
            allowed=tuple(tuple(_VALUE[v] for v in row) for row in law["allowed"]),
            warrant=f"{law.get('review_state')}: {law['warrant']}",
            scope=scope_name(law["guard"]),
        )
        for law in book["laws"]
    ]


def _boundaries(book: dict) -> tuple[list[Relation], list[Check], list[str]]:
    """SILENT and OPTIONAL cells as one-bank relations, REQUIRED cells as checks, and the cells left out."""
    relations, checks, skipped = [], [], []
    for rule in book["source_rules"]:
        boundary = rule.get("definition_boundary")
        if not boundary:
            continue
        scope = scope_name(boundary["guard"])
        for bank, cell in boundary["cells"].items():
            rule_id = f"boundary:{boundary['id']}:{bank}"
            if bank not in BANK_INDEX:
                skipped.append(f"{rule_id}: not a bank of the registry")
                continue
            warrant = f"{rule['review_state']}, {cell['kind']}: {cell['reason']} ({'; '.join(cell['source_refs'])})"
            if cell["kind"] == "REQUIRED":
                checks.append(Check(rule_id, bank, mask(cell["domain"]), scope, cell["reason"]))
            elif cell["kind"] == "SILENT" and cell["domain"] == ["empty"]:
                relations.append(Relation(rule_id, (bank,), ((SILENT,),), warrant, scope))
            elif cell["kind"] == "OPTIONAL":
                states = tuple((_VALUE[v],) for v in cell["domain"])
                relations.append(Relation(rule_id, (bank,), states, warrant, scope))
            else:
                skipped.append(f"{rule_id}: unknown cell kind {cell['kind']}")
    return relations, checks, skipped


def _companions(book: dict) -> list[Relation]:
    out = []
    for rule in book["source_rules"]:
        facts = reading_facts(rule)
        for bank, value in rule.get("companions", {}).items():
            out.append(
                Relation(
                    rule_id=f"law:{rule['rule_id']}:companions",
                    banks=(bank,),
                    allowed=((_VALUE[value],),),
                    warrant=f"{rule['review_state']}: {rule['warrant']}",
                    scope=scope_name(facts),
                )
            )
    return out


def compile_laws(path: Path = LAWS) -> tuple[Relation, ...]:
    """Every authored relation: the laws, the definition boundaries' silences and domains, the companions."""
    book = _book(path)
    boundary, _, _ = _boundaries(book)
    return tuple(_authored(book) + boundary + _companions(book))


def required_checks(path: Path = LAWS) -> tuple[Check, ...]:
    return tuple(_boundaries(_book(path))[1])


def uncompiled_cells(path: Path = LAWS) -> tuple[str, ...]:
    """Authored boundary cells that cannot compile, each with its reason."""
    return tuple(_boundaries(_book(path))[2])


def check(masks: np.ndarray, scopes: dict[str, np.ndarray], checks) -> dict[str, dict[str, int]]:
    """For each REQUIRED cell, the guarded readings where it is derived, still open, or contradicted."""
    out = {}
    for c in checks:
        cells = masks[np.flatnonzero(scopes[c.scope]), BANK_INDEX[c.bank]]
        inside = (cells != 0) & ((cells & (ALL ^ c.allowed)) == 0)
        contradicted = (cells & c.allowed) == 0
        out[c.rule_id] = {
            "derived": int(inside.sum()),
            "open": int((~inside & ~contradicted).sum()),
            "contradicted": int(contradicted.sum()),
        }
    return out
