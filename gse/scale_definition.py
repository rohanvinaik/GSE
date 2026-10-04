"""
ScaleDefinition — parameterized Genesis Atom for multi-scale semantic encoding.

Each scale (word, sentence, paragraph, text) is defined as a ScaleDefinition
that auto-generates: bank enum, primitive registry, lookup functions.
This eliminates the 4× copy-paste pattern in primitives_v2.py.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class BankDef:
    """Definition of a single semantic bank within a scale."""
    name: str
    primitives: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PrimitiveInfo:
    """Universal primitive info — works across all scales."""
    name: str
    bank_index: int
    bank_name: str
    scale: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ScaleDefinition:
    """
    Parameterized scale definition that generates bank enums, registries,
    and lookup functions from a list of BankDefs.

    This is the Genesis Atom pattern from DGA: define the structure once,
    instantiate it for each scale with different data.
    """

    def __init__(
        self,
        name: str,
        banks: List[BankDef],
        dimension: int = 8192,
        n_banks: int = 8,
        hub_primitives: Optional[List[str]] = None,
        families: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.name = name
        self.banks = banks
        self.dimension = dimension
        self.n_banks = n_banks
        self.dims_per_bank = dimension // n_banks
        self.hub_primitives = hub_primitives or []
        self.families = families or {}

        self.bank_enum = self._build_bank_enum()
        self.bank_names = {i: b.name for i, b in enumerate(banks)}
        self.primitive_registry = self._build_registry()

        self._bank_primitives_cache: Dict[int, List[str]] = {}

    def _build_bank_enum(self):
        members = {b.name: i for i, b in enumerate(self.banks)}
        return IntEnum(f"{self.name.title()}Bank", members)

    def _build_registry(self) -> Dict[str, PrimitiveInfo]:
        registry: Dict[str, PrimitiveInfo] = {}
        for i, bank in enumerate(self.banks):
            for prim in bank.primitives:
                registry[prim] = PrimitiveInfo(
                    name=prim,
                    bank_index=i,
                    bank_name=bank.name,
                    scale=self.name,
                    metadata=bank.metadata.get(prim, {}),
                )
        return registry

    def get_primitive_info(self, name: str) -> Optional[PrimitiveInfo]:
        return self.primitive_registry.get(name)

    def get_bank_primitives(self, bank_index: int) -> List[str]:
        if bank_index not in self._bank_primitives_cache:
            self._bank_primitives_cache[bank_index] = [
                name for name, info in self.primitive_registry.items()
                if info.bank_index == bank_index
            ]
        return self._bank_primitives_cache[bank_index]

    def get_all_primitives(self) -> List[str]:
        return list(self.primitive_registry.keys())

    def count_primitives(self) -> Dict[str, int]:
        counts = {"total": len(self.primitive_registry)}
        for i, bank in enumerate(self.banks):
            counts[f"bank_{i}_{bank.name.lower()}"] = len(bank.primitives)
        return counts

    def primitives_per_bank_counts(self) -> Dict[int, int]:
        return {i: len(b.primitives) for i, b in enumerate(self.banks)}

    @property
    def all_primitive_names(self) -> List[str]:
        result = []
        for bank in self.banks:
            result.extend(bank.primitives)
        return result

    def __repr__(self) -> str:
        return (
            f"ScaleDefinition(name={self.name!r}, "
            f"primitives={len(self.primitive_registry)}, "
            f"banks={len(self.banks)})"
        )
