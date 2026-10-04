"""
Bipolar Consistency Validator

Ensures that bipolar pairs (GOOD/BAD, BIG/SMALL, etc.) cannot both be non-zero.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from gse.curation.schema import BIPOLAR_PAIRS


@dataclass
class ValidationResult:
    """Result of a validation check."""

    passed: bool
    validation_type: str
    violations: List[Dict[str, Any]] = field(default_factory=list)
    details: str = ""


class BipolarValidator:
    """
    Validates bipolar dimension consistency.

    The 14 bipolar pairs (e.g., GOOD/BAD, BIG/SMALL) represent
    opposite poles of the same semantic dimension. They cannot
    both have non-zero values simultaneously.

    Valid states for a bipolar pair (POS, NEG):
    - (0, 0) - neither pole relevant
    - (+1, 0) - positive pole active
    - (-1, 0) - negative pole expressed via positive's -1
    - (0, +1) - SHOULD BE CONVERTED to POS=-1 (canonical form)
    - (0, -1) - SHOULD BE CONVERTED to POS=+1 (canonical form)

    Invalid:
    - Both non-zero (semantic contradiction)
    """

    def __init__(self):
        self.bipolar_pairs = BIPOLAR_PAIRS

    def validate(self, decomposition: Dict[str, int]) -> ValidationResult:
        """
        Check that bipolar pairs don't both have non-zero values.

        Args:
            decomposition: Dict mapping primitive names to values (-1, 0, +1)

        Returns:
            ValidationResult with pass/fail status and any violations
        """
        violations = []

        for pos_prim, neg_prim in self.bipolar_pairs:
            pos_val = decomposition.get(pos_prim, 0)
            neg_val = decomposition.get(neg_prim, 0)

            if pos_val != 0 and neg_val != 0:
                violations.append(
                    {
                        "type": "bipolar_conflict",
                        "pair": (pos_prim, neg_prim),
                        "positive_value": pos_val,
                        "negative_value": neg_val,
                        "message": f"Both {pos_prim} ({pos_val}) and {neg_prim} ({neg_val}) are non-zero",
                    }
                )

        passed = len(violations) == 0

        return ValidationResult(
            passed=passed,
            validation_type="bipolar",
            violations=violations,
            details=f"Checked {len(self.bipolar_pairs)} bipolar pairs, found {len(violations)} violations",
        )

    def fix_violations(self, decomposition: Dict[str, int]) -> Tuple[Dict[str, int], List[str]]:
        """
        Fix bipolar violations by zeroing out the negative pole.

        The convention is to use the positive pole with appropriate polarity:
        - If both GOOD and BAD are set, keep GOOD's value and zero BAD

        Args:
            decomposition: Dict with primitive values

        Returns:
            Tuple of (fixed_decomposition, list of fixes applied)
        """
        fixed = decomposition.copy()
        fixes = []

        for pos_prim, neg_prim in self.bipolar_pairs:
            pos_val = fixed.get(pos_prim, 0)
            neg_val = fixed.get(neg_prim, 0)

            if pos_val != 0 and neg_val != 0:
                # Keep positive pole, zero negative
                fixed[neg_prim] = 0
                fixes.append(f"Zeroed {neg_prim} (was {neg_val}) - keeping {pos_prim}={pos_val}")

        return fixed, fixes

    def canonicalize(self, decomposition: Dict[str, int]) -> Tuple[Dict[str, int], List[str]]:
        """
        Convert decomposition to canonical form (only positive poles used).

        The canonical form uses only the positive pole of each bipolar pair.
        If the negative pole is set, convert to positive pole with flipped polarity.

        Example:
            BAD: +1 -> GOOD: -1, BAD: 0
            SMALL: +1 -> BIG: -1, SMALL: 0

        Args:
            decomposition: Dict with primitive values

        Returns:
            Tuple of (canonical_decomposition, list of conversions applied)
        """
        canonical = decomposition.copy()
        conversions = []

        for pos_prim, neg_prim in self.bipolar_pairs:
            pos_val = canonical.get(pos_prim, 0)
            neg_val = canonical.get(neg_prim, 0)

            # If negative pole is set and positive is not, convert
            if neg_val != 0 and pos_val == 0:
                canonical[pos_prim] = -neg_val  # Flip polarity
                canonical[neg_prim] = 0
                conversions.append(f"Converted {neg_prim}={neg_val} to {pos_prim}={-neg_val}")

        return canonical, conversions


def validate_bipolar(decomposition: Dict[str, int]) -> ValidationResult:
    """Convenience function for bipolar validation."""
    validator = BipolarValidator()
    return validator.validate(decomposition)
