"""
LLM Response Parser

Parses LLM output into primitive decompositions with validation.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from gse.curation.schema import ALL_PRIMITIVES, BIPOLAR_PAIRS


class ParseError(Exception):
    """Error parsing LLM response."""

    pass


@dataclass
class ParseResult:
    """Result of parsing an LLM response."""

    decomposition: Dict[str, int]
    confidence: float
    warnings: List[str]
    raw_response: str


def extract_json_from_response(response: str) -> str:
    """
    Extract JSON from an LLM response.

    Handles:
    - Direct JSON
    - JSON in code blocks (```json ... ```)
    - JSON with leading/trailing text
    """
    response = response.strip()

    # Try to find JSON in code blocks first
    code_block_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", response)
    if code_block_match:
        return code_block_match.group(1)

    # Try to find JSON array in code blocks (for batch)
    array_block_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", response)
    if array_block_match:
        return array_block_match.group(1)

    # Try to find standalone JSON object
    json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", response, re.DOTALL)
    if json_match:
        return json_match.group()

    # Try to find JSON array
    array_match = re.search(r"\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]", response, re.DOTALL)
    if array_match:
        return array_match.group()

    # If nothing found, try the whole response
    return response


def normalize_primitive_value(value: Any) -> int:
    """Normalize a primitive value to -1, 0, or +1."""
    if value is None:
        return 0

    if isinstance(value, bool):
        return 1 if value else 0

    if isinstance(value, str):
        value = value.strip().lower()
        if value in ("1", "+1", "true", "yes", "positive"):
            return 1
        elif value in ("-1", "false", "no", "negative"):
            return -1
        else:
            return 0

    if isinstance(value, (int, float)):
        if value > 0:
            return 1
        elif value < 0:
            return -1
        else:
            return 0

    return 0


def normalize_primitive_name(name: str) -> Optional[str]:
    """Normalize a primitive name to match our schema."""
    name = name.strip().upper()

    # Direct match
    if name in ALL_PRIMITIVES:
        return name

    # Handle common variations
    name_map = {
        "LONG": "LONG_TIME",
        "LONGTIME": "LONG_TIME",
        "SHORT": "SHORT_TIME",
        "SHORTTIME": "SHORT_TIME",
        "HIERPLUS": "HIER_PLUS",
        "HIER+": "HIER_PLUS",
        "HIERMINUS": "HIER_MINUS",
        "HIER-": "HIER_MINUS",
        "DEAD": "DEAD",
        "DIE": "DEAD",
    }

    if name in name_map:
        return name_map[name]

    return None


def parse_llm_response(
    response: str,
    strict: bool = False,
) -> ParseResult:
    """
    Parse an LLM response into a primitive decomposition.

    Args:
        response: The raw LLM response text
        strict: If True, raise error on any parsing issues

    Returns:
        ParseResult with decomposition and metadata
    """
    warnings = []

    # Extract JSON from response
    try:
        json_str = extract_json_from_response(response)
    except Exception as e:
        raise ParseError(f"Failed to extract JSON: {e}")

    # Parse JSON - fix common issues first
    try:
        # Fix +1 to 1 (invalid JSON)
        json_str = re.sub(r":\s*\+(\d+)", r": \1", json_str)
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON: {e}")

    # Handle array response (for batch)
    if isinstance(data, list):
        if len(data) == 1:
            data = data[0]
        else:
            raise ParseError("Unexpected array response - use parse_batch_response for batches")

    if not isinstance(data, dict):
        raise ParseError(f"Expected dict, got {type(data)}")

    # Build decomposition with normalized values
    decomposition: Dict[str, int] = {}

    for key, value in data.items():
        norm_name = normalize_primitive_name(key)
        if norm_name is None:
            warnings.append(f"Unknown primitive: {key}")
            continue

        norm_value = normalize_primitive_value(value)
        decomposition[norm_name] = norm_value

    # Fill missing primitives with 0
    missing = []
    for prim in ALL_PRIMITIVES:
        if prim not in decomposition:
            decomposition[prim] = 0
            missing.append(prim)

    if missing:
        warnings.append(f"Filled {len(missing)} missing primitives with 0")

    # Check bipolar consistency
    bipolar_violations = check_bipolar_consistency(decomposition)
    if bipolar_violations:
        for pos, neg in bipolar_violations:
            # Auto-fix: zero out the negative pole
            decomposition[neg] = 0
            warnings.append(f"Fixed bipolar violation: {pos}/{neg} both non-zero")

    # Calculate confidence (crude heuristic based on warnings)
    confidence = 1.0
    if len(missing) > 10:
        confidence -= 0.2
    if bipolar_violations:
        confidence -= 0.1 * len(bipolar_violations)
    confidence = max(0.1, confidence)

    if strict and warnings:
        raise ParseError(f"Parsing warnings in strict mode: {warnings}")

    return ParseResult(
        decomposition=decomposition,
        confidence=confidence,
        warnings=warnings,
        raw_response=response,
    )


def parse_batch_response(
    response: str,
    expected_count: int,
) -> List[ParseResult]:
    """
    Parse a batch LLM response containing multiple decompositions.

    Args:
        response: The raw LLM response text
        expected_count: Expected number of decompositions

    Returns:
        List of ParseResult, one per word
    """
    # Extract JSON array
    try:
        json_str = extract_json_from_response(response)
        data = json.loads(json_str)
    except (json.JSONDecodeError, Exception) as e:
        raise ParseError(f"Failed to parse batch JSON: {e}")

    if not isinstance(data, list):
        # Try to wrap single result
        data = [data]

    if len(data) != expected_count:
        raise ParseError(f"Expected {expected_count} decompositions, got {len(data)}")

    results = []
    for i, item in enumerate(data):
        try:
            # Create a fake single response
            single_response = json.dumps(item)
            result = parse_llm_response(single_response)
            results.append(result)
        except ParseError as e:
            # Create empty result with error
            results.append(
                ParseResult(
                    decomposition={p: 0 for p in ALL_PRIMITIVES},
                    confidence=0.0,
                    warnings=[f"Parse error for item {i}: {e}"],
                    raw_response=json.dumps(item),
                )
            )

    return results


def check_bipolar_consistency(decomposition: Dict[str, int]) -> List[Tuple[str, str]]:
    """
    Check for bipolar consistency violations.

    Returns:
        List of (positive, negative) pairs that both have non-zero values
    """
    violations = []

    for pos, neg in BIPOLAR_PAIRS:
        pos_val = decomposition.get(pos, 0)
        neg_val = decomposition.get(neg, 0)

        if pos_val != 0 and neg_val != 0:
            violations.append((pos, neg))

    return violations


def decomposition_to_sparse(decomposition: Dict[str, int]) -> Dict[str, int]:
    """Convert a full decomposition to sparse format (only non-zero values)."""
    return {k: v for k, v in decomposition.items() if v != 0}


def sparse_to_decomposition(sparse: Dict[str, int]) -> Dict[str, int]:
    """Convert sparse format to full 72-primitive decomposition."""
    return {prim: sparse.get(prim, 0) for prim in ALL_PRIMITIVES}


def decomposition_to_vector_format(
    decomposition: Dict[str, int],
) -> List[Tuple[str, str, int]]:
    """
    Convert decomposition to format expected by vectors_v2.compose_decomposition.

    Returns:
        List of (primitive, role, polarity) tuples for non-zero primitives
    """
    from gse.curation.schema import PRIMITIVE_TO_BANK

    # Bank to role mapping
    BANK_TO_ROLE = {
        0: "entity",
        1: "quantity",
        2: "evaluation",
        3: "mental",
        4: "action",
        5: "temporal",
        6: "spatial",
        7: "logical",
    }

    result = []
    for prim, value in decomposition.items():
        if value != 0:
            bank = PRIMITIVE_TO_BANK.get(prim, 7)
            role = BANK_TO_ROLE.get(bank, "default")
            result.append((prim, role, value))

    return result
