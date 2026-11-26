"""The population state: every reading's 56 banks as masks over four states (design E1).

F118: "0 is explicit absence; empty is silence." F140: confirmed silence is decided. A cell's mask holds the states
still legal for it. One state is a decided cell; two or more are a residual; none is a conflict. Zero and silence
are separate bits, so neither can stand in for the other.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from GSE.curation.schema import ALL_PRIMITIVES, BIPOLAR_PAIRS

POS, NEG, ZERO, SILENT = 1, 2, 4, 8
ALL = POS | NEG | ZERO | SILENT
STATE_BITS = {+1: POS, -1: NEG, 0: ZERO, "SILENT": SILENT}
BIT_NAMES = {POS: "+1", NEG: "-1", ZERO: "0", SILENT: "SILENT"}

NEGATIVE_POLES = {negative: positive for positive, negative in BIPOLAR_PAIRS}
BANKS: tuple[str, ...] = tuple(
    p for p in ALL_PRIMITIVES if p not in NEGATIVE_POLES and p not in {"NUMBER", "HIER_PLUS", "HIER_MINUS"}
)
BANK_INDEX = {bank: i for i, bank in enumerate(BANKS)}
BIPOLAR: frozenset[str] = frozenset(positive for positive, _ in BIPOLAR_PAIRS)

# A bank without a declared negative pole cannot be -1 (F040).
START = np.array([ALL if bank in BIPOLAR else POS | ZERO | SILENT for bank in BANKS], dtype=np.uint8)

_POPCOUNT = np.array([bin(i).count("1") for i in range(16)], dtype=np.uint8)
_LOG2 = np.array([0.0 if n == 0 else float(np.log2(n)) for n in range(5)])


def bit(value) -> int:
    """The state bit of a value: +1, -1, 0 or "SILENT"."""
    return STATE_BITS[value]


@dataclass
class State:
    """Masks for every (reading, bank) cell, with the reading ids in dense order."""

    readings: tuple[str, ...]
    masks: np.ndarray

    @classmethod
    def opening(cls, readings) -> State:
        readings = tuple(readings)
        masks = np.tile(START, (len(readings), 1))
        return cls(readings, masks)

    def __post_init__(self):
        if self.masks.shape != (len(self.readings), len(BANKS)) or self.masks.dtype != np.uint8:
            raise ValueError("STATE_SHAPE")
        self.index = {reading: i for i, reading in enumerate(self.readings)}

    def copy(self) -> State:
        return State(self.readings, self.masks.copy())

    def counts(self) -> np.ndarray:
        """How many states each cell still allows."""
        return _POPCOUNT[self.masks]

    def bits(self) -> float:
        """H = the sum over cells of log2 of the legal states (the marginal-domain specification bits)."""
        return float(_LOG2[self.counts()].sum())

    def census(self) -> dict:
        """Every cell in exactly one class: decided by state, residual, or conflict."""
        counts = self.counts()
        decided = counts == 1
        out: dict[str, int | float] = {
            BIT_NAMES[b]: int((decided & (self.masks == b)).sum()) for b in (POS, NEG, ZERO, SILENT)
        }
        out["residual"] = int((counts > 1).sum())
        out["conflict"] = int((counts == 0).sum())
        out["cells"] = int(counts.size)
        out["bits"] = self.bits()
        return out

    def save(self, path) -> None:
        np.savez_compressed(path, masks=self.masks, readings=np.array(self.readings, dtype=object))

    @classmethod
    def load(cls, path) -> State:
        data = np.load(path, allow_pickle=True)
        return cls(tuple(data["readings"].tolist()), data["masks"].astype(np.uint8))
