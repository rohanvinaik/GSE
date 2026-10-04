"""
Hierarchy Consistency Validator

Validates consistency of hierarchical modifiers (QUANTITY, INTENSITY, CERTAINTY).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from gse.curation.schema import (
    CERTAINTY_HIERARCHY,
    INTENSITY_HIERARCHY,
    QUANTITY_HIERARCHY,
)


@dataclass
class ValidationResult:
    """Result of a validation check."""

    passed: bool
    validation_type: str
    violations: List[Dict[str, Any]] = field(default_factory=list)
    details: str = ""


class HierarchyValidator:
    """
    Validates hierarchy marker consistency.

    The GSE system has three hierarchies:
    - QUANTITY: NONE(-3) to ALL(+3) with MIDDLE(0) as anchor
    - INTENSITY: BARELY(-2) to EXTREMELY(+2) with MODERATE(0)
    - CERTAINTY: IMPOSSIBLE(-3) to CERTAIN(+3) with POSSIBLE(0)

    Each uses HIER_PLUS and HIER_MINUS markers to indicate level.

    Rules:
    - HIER_PLUS and HIER_MINUS should not both be active
    - If a hierarchy base is active (QUANTITY/INTENSITY/CERTAINTY),
      hierarchy markers should be consistent
    """

    def __init__(self):
        self.hierarchies = {
            "QUANTITY": QUANTITY_HIERARCHY,
            "INTENSITY": INTENSITY_HIERARCHY,
            "CERTAINTY": CERTAINTY_HIERARCHY,
        }

    def validate(self, decomposition: Dict[str, int]) -> ValidationResult:
        """
        Check hierarchy marker consistency.

        Args:
            decomposition: Dict mapping primitive names to values

        Returns:
            ValidationResult with pass/fail status and violations
        """
        violations = []

        # Check HIER_PLUS/HIER_MINUS conflict
        hier_plus = decomposition.get("HIER_PLUS", 0)
        hier_minus = decomposition.get("HIER_MINUS", 0)

        if hier_plus != 0 and hier_minus != 0:
            violations.append(
                {
                    "type": "hierarchy_conflict",
                    "detail": f"Both HIER_PLUS ({hier_plus}) and HIER_MINUS ({hier_minus}) are non-zero",
                    "message": "Hierarchy markers should not both be active",
                }
            )

        # Check each hierarchy base
        for base_name in ["QUANTITY", "INTENSITY", "CERTAINTY"]:
            base_val = decomposition.get(base_name, 0)

            if base_val != 0:
                # Base is active, check marker consistency
                if hier_plus != 0 and hier_minus != 0:
                    violations.append(
                        {
                            "type": "hierarchy_base_conflict",
                            "base": base_name,
                            "detail": f"{base_name} is active but both markers are set",
                        }
                    )

        # Check for orphaned hierarchy markers (markers without base)
        if hier_plus != 0 or hier_minus != 0:
            bases_active = any(decomposition.get(base, 0) != 0 for base in ["QUANTITY", "INTENSITY", "CERTAINTY"])
            if not bases_active:
                violations.append(
                    {
                        "type": "orphaned_markers",
                        "detail": "Hierarchy markers present without active hierarchy base",
                        "markers": {"HIER_PLUS": hier_plus, "HIER_MINUS": hier_minus},
                    }
                )

        passed = len(violations) == 0

        return ValidationResult(
            passed=passed,
            validation_type="hierarchy",
            violations=violations,
            details=f"Checked 3 hierarchies, found {len(violations)} issues",
        )

    def infer_hierarchy_level(
        self,
        decomposition: Dict[str, int],
    ) -> Dict[str, int]:
        """
        Infer the hierarchy level from the decomposition.

        Returns:
            Dict mapping hierarchy base to inferred level (-3 to +3)
        """
        levels = {}

        hier_plus = decomposition.get("HIER_PLUS", 0)
        hier_minus = decomposition.get("HIER_MINUS", 0)

        for base_name in ["QUANTITY", "INTENSITY", "CERTAINTY"]:
            base_val = decomposition.get(base_name, 0)

            if base_val != 0:
                # Base is active, determine level
                if hier_plus > 0:
                    level = hier_plus  # Positive level
                elif hier_minus > 0:
                    level = -hier_minus  # Negative level
                else:
                    level = 0  # Neutral level

                levels[base_name] = level

        return levels

    def get_hierarchy_word(self, base: str, level: int) -> str:
        """
        Get the English word for a hierarchy level.

        Args:
            base: Hierarchy base (QUANTITY, INTENSITY, CERTAINTY)
            level: Level (-3 to +3)

        Returns:
            English word representing this level
        """
        if base == "QUANTITY":
            for word, lvl in QUANTITY_HIERARCHY.items():
                if lvl == level:
                    return word
        elif base == "INTENSITY":
            for word, lvl in INTENSITY_HIERARCHY.items():
                if lvl == level:
                    return word
        elif base == "CERTAINTY":
            for word, lvl in CERTAINTY_HIERARCHY.items():
                if lvl == level:
                    return word

        return f"{base}[{level:+d}]"


def validate_hierarchy(decomposition: Dict[str, int]) -> ValidationResult:
    """Convenience function for hierarchy validation."""
    validator = HierarchyValidator()
    return validator.validate(decomposition)
