"""Intent and MUST-NOT checks for the fresh lexical constructor."""

from decimal import Decimal

import pytest

from gse.lexicon_builder.basis import OPPOSITE_POLES, PRIMES
from gse.lexicon_builder.core import (
    CANONICAL_COORDINATES,
    Cell,
    Law,
    NumberScale,
    Observation,
    apply_number_scale,
    atomic_seed,
    canonical_pole,
    legal_domain,
    resolve,
)


def test_every_prime_has_exactly_one_literal_signed_seed_and_number_has_none():
    assert len(PRIMES) == 72
    assert len(OPPOSITE_POLES) == 14
    assert len(CANONICAL_COORDINATES) == 58
    assert {atom.prime for atom in map(atomic_seed, PRIMES)} == set(PRIMES)
    assert all(atom.sign in (Cell.PLUS, Cell.MINUS) for atom in map(atomic_seed, PRIMES))
    assert "NUMBER" not in PRIMES
    with pytest.raises(ValueError, match="not one of the 72"):
        atomic_seed("NUMBER")


def test_opposite_poles_are_one_coordinate_with_opposite_signs():
    for positive, negative in OPPOSITE_POLES:
        assert canonical_pole(positive) == (positive, 1)
        assert canonical_pole(negative) == (positive, -1)
        assert atomic_seed(positive).coordinate == atomic_seed(negative).coordinate
        assert atomic_seed(positive).sign == Cell.PLUS
        assert atomic_seed(negative).sign == Cell.MINUS
    assert Cell.MINUS not in legal_domain("FEEL")


def test_uncertified_or_wrong_reading_fact_cannot_assign_feel():
    readings = (
        Observation("love.n.01", "FrameNet", "lu-1", "own_denotatum", "affective_feeling", False),
        Observation("love.v.01", "FrameNet", "lu-2", "own_denotatum", "affective_feeling", True),
    )
    noun = resolve("love.n.01", readings)
    verb = resolve("love.v.01", readings)
    assert "FEEL" not in noun.forced()
    assert verb.forced()["FEEL"] == Cell.PLUS
    assert verb.forced()["KIND"] == Cell.ZERO
    assert verb.fired_rules == ("OWN_AFFECTIVE_FEELING", "FEELING_DENOTATUM_IS_NOT_A_CATEGORY")


def test_modifier_censor_writes_explicit_absence_without_conflating_it_with_silence():
    fact = Observation("big.adj.01", "reviewed", "reading-1", "own_role", "modifier_property_only", True)
    result = resolve("big.adj.01", (fact,))
    assert result.code == "PARTIAL"
    assert result.domains["SOMETHING"] == (Cell.ZERO,)
    assert result.forced()["SOMETHING"] == Cell.ZERO


def test_joint_constraint_can_force_a_value_without_any_unary_source_vote():
    # Mechanism proof only: this relation is synthetic, not a lexical law.
    fake = Law(
        "SYNTHETIC_SUDOKU",
        ("FEEL", "MOVE"),
        ((Cell.PLUS, Cell.ZERO), (Cell.ZERO, Cell.PLUS)),
        (),
        "mechanism-only test relation",
    )
    one_side = Law("SOURCE_A", ("FEEL",), ((Cell.PLUS,),), (), "mechanism-only")
    result = resolve("synthetic.01", laws=(fake, one_side))
    assert result.forced()["FEEL"] == Cell.PLUS
    assert result.forced()["MOVE"] == Cell.ZERO
    assert any(step["rule"] == "SYNTHETIC_SUDOKU" for step in result.trace)


def test_contradictory_laws_return_named_conflict():
    plus = Law("PLUS", ("FEEL",), ((Cell.PLUS,),), (), "mechanism-only")
    zero = Law("ZERO", ("FEEL",), ((Cell.ZERO,),), (), "mechanism-only")
    assert resolve("contradiction.01", laws=(plus, zero)).code == "CONFLICT"


def test_number_changes_relative_magnitude_but_preserves_written_pattern():
    base = {"GOOD": Cell.MINUS, "FEEL": Cell.PLUS, "MOVE": Cell.ZERO, "SOMETHING": Cell.SILENT}
    scale = NumberScale("fatigue", 2, ("GOOD", "FEEL"), Decimal("2"))
    result = apply_number_scale(base, scale)
    assert result == {"GOOD": Decimal("-2"), "FEEL": Decimal("2"), "MOVE": Decimal("0")}
    assert set(result) == {name for name, cell in base.items() if cell is not Cell.SILENT}
    assert all((result[name] > 0) == (base[name] is Cell.PLUS) for name in ("GOOD", "FEEL"))


def test_number_never_creates_content_or_crosses_polarity():
    with pytest.raises(ValueError, match="already written, nonzero"):
        apply_number_scale({"FEEL": Cell.SILENT}, NumberScale("fatigue", 1, ("FEEL",), Decimal("2")))
    with pytest.raises(ValueError, match="already written, nonzero"):
        apply_number_scale({"MOVE": Cell.ZERO}, NumberScale("motion", 1, ("MOVE",), Decimal("2")))
    with pytest.raises(ValueError, match="finite and positive"):
        NumberScale("fatigue", 1, ("FEEL",), Decimal("-1"))
    with pytest.raises(ValueError, match="reviewed numeric gain"):
        apply_number_scale({"FEEL": Cell.PLUS}, NumberScale("fatigue", 1, ("FEEL",)))
