"""
Operator resolution during parsing.

The three-component operator model:

1. SIGN: Direction flag (-1/+1)
   - Sets pending_sign
   - Does NOT operate directly
   - Consumed by next operator or atomic

2. HIERARCHY: Intensity modifier
   - Consumes sign if present (inverts direction)
   - Sets pending_hierarchy
   - Acts on next atomic

3. AUXILIARY: Feature transmitter
   - Lazy binding to verb
   - Pushed to stack until verb found
   - Transmits tense/aspect/mood features

Examples:
- "not very happy"
  → "not" sets pending_sign=-1
  → "very" consumes sign, sets pending_hierarchy=-1 (inverted)
  → "happy" receives hierarchy_level=-1

- "did not run"
  → "did" pushed to aux stack
  → "not" sets pending_sign=-1
  → "run" receives aux features + negation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from ..lexicon.word_encoding import LexemeEntry
    from .graph import ParseNode


# ============================================================
# OPERATOR STATE
# ============================================================


@dataclass
class OperatorState:
    """
    Tracks pending operators during left-to-right parse.

    This state machine accumulates operators until an atomic
    word is encountered, at which point all pending operations
    are applied.

    The state is consumed when applied to an atomic, then reset.
    """

    pending_sign: Optional[int] = None  # -1 for negators, +1 for emphatic
    pending_hierarchy: Optional[int] = None  # Accumulated hierarchy delta
    pending_auxiliaries: List["LexemeEntry"] = field(default_factory=list)

    def consume_sign(self) -> Optional[int]:
        """
        Take pending sign, return it, clear state.

        Used by HIERARCHY operators to invert their direction
        when following a negator.
        """
        sign = self.pending_sign
        self.pending_sign = None
        return sign

    def has_pending_sign(self) -> bool:
        """Is there a sign waiting to be consumed?"""
        return self.pending_sign is not None

    def has_pending_hierarchy(self) -> bool:
        """Is there a hierarchy modification waiting?"""
        return self.pending_hierarchy is not None

    def has_pending_auxiliaries(self) -> bool:
        """Are there auxiliaries waiting for a verb?"""
        return len(self.pending_auxiliaries) > 0

    def is_empty(self) -> bool:
        """Is the operator state completely empty?"""
        return (
            self.pending_sign is None
            and self.pending_hierarchy is None
            and not self.pending_auxiliaries
        )

    def copy(self) -> "OperatorState":
        """Create a copy of this state."""
        return OperatorState(
            pending_sign=self.pending_sign,
            pending_hierarchy=self.pending_hierarchy,
            pending_auxiliaries=self.pending_auxiliaries.copy(),
        )

    def reset(self) -> "OperatorState":
        """Return a fresh empty state."""
        return OperatorState()


# ============================================================
# OPERATOR RESOLUTION
# ============================================================


def resolve_operator(
    token: "LexemeEntry",
    state: OperatorState,
) -> OperatorState:
    """
    Process an operator token, updating state.

    Rules:
    - SIGN: Sets pending_sign, does not operate directly
    - HIERARCHY: Consumes pending_sign (inverts if present), waits for atomic
    - AUXILIARY: Lazy, pushed to stack until verb found
    - DETERMINER: No operator state change (handled in edge construction)
    - PREPOSITION: No operator state change (handled in edge construction)
    - CONJUNCTION: No operator state change (handled in edge construction)
    - COMPLEMENTIZER: No operator state change (handled in edge construction)

    Args:
        token: The operator lexeme entry
        state: Current operator state

    Returns:
        Updated operator state (may be same object or new)
    """
    from ..lexicon.word_encoding import OperatorType

    if not token.operator_spec:
        return state

    spec = token.operator_spec
    new_state = state.copy()

    if spec.op_type == OperatorType.SIGN:
        # Sign just waits to be consumed
        # If there's already a pending sign, they combine
        if new_state.pending_sign is not None:
            # Double negation or emphasis
            new_state.pending_sign *= spec.sign_value
        else:
            new_state.pending_sign = spec.sign_value

    elif spec.op_type == OperatorType.HIERARCHY:
        # Hierarchy consumes sign if present
        sign = new_state.consume_sign()
        if sign is None:
            sign = 1

        # Sign inverts the hierarchy direction
        # "not very" → -1 * +1 = -1 (attenuated)
        # "very" → 1 * +1 = +1 (intensified)
        delta = spec.hier_delta * sign

        # Accumulate hierarchy (stacking: "very very" = +2)
        if new_state.pending_hierarchy is not None:
            new_state.pending_hierarchy += delta
        else:
            new_state.pending_hierarchy = delta

    elif spec.op_type == OperatorType.AUXILIARY:
        # Lazy: push to stack
        new_state.pending_auxiliaries.append(token)

        # If there's a pending sign, it applies to the aux's eventual target
        # Keep sign pending (it will apply to verb)

    # DETERMINER, PREPOSITION, CONJUNCTION, COMPLEMENTIZER
    # These don't modify operator state - they're handled during edge construction

    return new_state


def apply_operators_to_atomic(
    atomic: "ParseNode",
    state: OperatorState,
) -> "ParseNode":
    """
    Apply all pending operators to an atomic node.

    Order of application:
    1. Sign (if not consumed by hierarchy)
    2. Hierarchy (with sign already folded in)
    3. Auxiliaries (transmit features to verb)

    Args:
        atomic: The atomic parse node to modify
        state: Current operator state with pending operators

    Returns:
        The modified atomic node (modified in place)
    """
    from ..lexicon.word_encoding import GramRole

    # Apply sign directly if no hierarchy consumed it
    if state.pending_sign is not None and state.pending_hierarchy is None:
        atomic.pending_sign = state.pending_sign

    # Apply hierarchy (sign already folded in during resolve_operator)
    if state.pending_hierarchy is not None:
        atomic.hierarchy_level = state.pending_hierarchy

    # Apply auxiliaries (transmit features to verb)
    if atomic.assigned_role == GramRole.VERB or GramRole.VERB in atomic.possible_roles:
        for aux in state.pending_auxiliaries:
            if aux.operator_spec and aux.operator_spec.transmits:
                for feature in aux.operator_spec.transmits:
                    # Get feature value from aux's grammatical features
                    feature_value = getattr(aux.gram_features, feature, None)
                    if feature_value is not None:
                        atomic.features[feature] = feature_value

        # If there was a sign pending that wasn't consumed by hierarchy,
        # and we have auxiliaries, the sign applies to the verb
        if state.pending_sign is not None and state.pending_hierarchy is None:
            atomic.pending_sign = state.pending_sign

    return atomic


def can_operator_apply(
    operator: "LexemeEntry",
    target: "LexemeEntry",
) -> bool:
    """
    Check if an operator can apply to a target.

    Args:
        operator: The operator lexeme
        target: The potential target lexeme

    Returns:
        True if the operator can bind to the target
    """
    if not operator.operator_spec:
        return False

    # Check if target has any role the operator seeks
    seeks = operator.operator_spec.seeks
    if not seeks:
        return True  # No restriction

    return bool(target.possible_roles & seeks)
