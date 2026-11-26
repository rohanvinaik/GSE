"""The authored bank laws compiled into relations (design E4; `bank_laws.json`).

The laws are founder-approved or source-justified (F043, F067, F088, F144). Each names its banks, the joint values it
permits, its guard and its warrant. A value "empty" is SILENT. A law applies to the readings its guard selects; the
guard's facts come from `guards.py`, never from the law itself.
"""

from __future__ import annotations

import json
from pathlib import Path

from .cells import NEG, POS, SILENT, ZERO
from .relations import Relation

LAWS = Path(__file__).with_name("bank_laws.json")
_VALUE = {"+1": POS, "-1": NEG, "0": ZERO, "empty": SILENT}


def scope_name(guard) -> str:
    return "&".join(f"{k}={v}" for k, v in sorted(tuple(g) for g in guard))


def compile_laws(path: Path = LAWS) -> tuple[Relation, ...]:
    book = json.loads(path.read_text())
    out = []
    for law in book["laws"]:
        allowed = tuple(tuple(_VALUE[v] for v in row) for row in law["allowed"])
        out.append(
            Relation(
                rule_id=f"law:{law['rule_id']}",
                banks=tuple(law["coordinates"]),
                allowed=allowed,
                warrant=f"{law.get('review_state')}: {law['warrant']}",
                scope=scope_name(law["guard"]),
            )
        )
    return tuple(out)
