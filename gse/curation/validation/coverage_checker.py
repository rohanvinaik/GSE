"""
Coverage Checker

Ensures all 72 primitives have explicit values in decompositions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from gse.curation.schema import ALL_PRIMITIVES


@dataclass
class ValidationResult:
    """Result of a validation check."""

    passed: bool
    validation_type: str
    violations: List[Dict[str, Any]] = field(default_factory=list)
    details: str = ""


class CoverageChecker:
    """
    Checks that all 72 primitives have explicit values.

    For robust decomposition, every primitive should have an explicit
    value (+1, 0, or -1), not just the active ones. This ensures:
    - Complete semantic specification
    - Consistent vector generation
    - No ambiguity about missing vs. zero values
    """

    def __init__(self):
        self.all_primitives = set(ALL_PRIMITIVES)
        self.primitive_count = len(ALL_PRIMITIVES)

    def validate(self, decomposition: Dict[str, int]) -> ValidationResult:
        """
        Check that all 72 primitives are present.

        Args:
            decomposition: Dict mapping primitive names to values

        Returns:
            ValidationResult with pass/fail status and missing primitives
        """
        present = set(decomposition.keys())
        missing = self.all_primitives - present

        violations = []
        if missing:
            violations.append(
                {
                    "type": "missing_primitives",
                    "count": len(missing),
                    "primitives": sorted(missing),
                    "message": f"Missing {len(missing)} primitives: {sorted(missing)[:5]}...",
                }
            )

        passed = len(missing) == 0
        coverage = len(present & self.all_primitives) / self.primitive_count

        return ValidationResult(
            passed=passed,
            validation_type="coverage",
            violations=violations,
            details=f"Coverage: {coverage:.1%} ({len(present & self.all_primitives)}/{self.primitive_count})",
        )

    def fill_missing(
        self,
        decomposition: Dict[str, int],
        default_value: int = 0,
    ) -> Dict[str, int]:
        """
        Fill in missing primitives with a default value.

        Args:
            decomposition: Dict with primitive values
            default_value: Value to use for missing primitives (default 0)

        Returns:
            Complete decomposition with all 72 primitives
        """
        complete = {prim: default_value for prim in ALL_PRIMITIVES}
        complete.update(decomposition)
        return complete

    def get_coverage_stats(self, decomposition: Dict[str, int]) -> Dict[str, Any]:
        """
        Get detailed coverage statistics.

        Returns:
            Dict with coverage metrics by bank and type
        """
        from gse.curation.schema import BIPOLAR_PRIMITIVES, PRIMITIVE_TO_BANK

        stats = {
            "total_primitives": self.primitive_count,
            "present": 0,
            "missing": 0,
            "non_zero": 0,
            "positive": 0,
            "negative": 0,
            "by_bank": {},
            "bipolar_coverage": 0,
        }

        for prim in ALL_PRIMITIVES:
            bank = PRIMITIVE_TO_BANK.get(prim, 7)
            if bank not in stats["by_bank"]:
                stats["by_bank"][bank] = {"total": 0, "present": 0, "non_zero": 0}

            stats["by_bank"][bank]["total"] += 1

            if prim in decomposition:
                stats["present"] += 1
                stats["by_bank"][bank]["present"] += 1

                value = decomposition[prim]
                if value != 0:
                    stats["non_zero"] += 1
                    stats["by_bank"][bank]["non_zero"] += 1
                    if value > 0:
                        stats["positive"] += 1
                    else:
                        stats["negative"] += 1
            else:
                stats["missing"] += 1

        # Bipolar coverage
        bipolar_present = sum(1 for p in BIPOLAR_PRIMITIVES if p in decomposition)
        stats["bipolar_coverage"] = bipolar_present / len(BIPOLAR_PRIMITIVES)

        return stats


def validate_coverage(decomposition: Dict[str, int]) -> ValidationResult:
    """Convenience function for coverage validation."""
    checker = CoverageChecker()
    return checker.validate(decomposition)


def ensure_full_coverage(decomposition: Dict[str, int]) -> Dict[str, int]:
    """Convenience function to ensure full 72-primitive coverage."""
    checker = CoverageChecker()
    return checker.fill_missing(decomposition)
