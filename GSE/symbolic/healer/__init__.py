"""The statement healer — the law-grounded Society of Mind that cleans GSE's per-statement parse
output into clean statements (or honest holes) at the ``narrative.from_document(repair=)`` seam,
before compaction. See ``docs/SPINE_SOCIETY_DESIGN.md``.

Biology homology (the design's literal influence): the ENVELOPE is the cis-regulatory / epigenetic
mark (laid at parse time, carried forward to the trace-less seam); the SOCIETY is the DNA-repair
pathway ensemble (each lens one lesion class, by law, no cross-talk); abstention is the tolerated
lesion (graceful degradation); the cordoned residual model is translesion synthesis. NON-NEURAL:
structural re-read under the law + K-line/HDC recall by resemblance — never gradient descent.
"""

from __future__ import annotations

from .envelope import StatementMeta, build_envelope
from .lens import AdditiveLens, Hole, Lens, Repair
from .society import HealReport, Society, make_repair_hook

__all__ = [
    "StatementMeta",
    "build_envelope",
    "Lens",
    "AdditiveLens",
    "Repair",
    "Hole",
    "Society",
    "HealReport",
    "make_repair_hook",
]
