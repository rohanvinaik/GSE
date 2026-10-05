"""The one valence law and the per-pole E/P/A projection (#157).

literal_valence reads the evaluation dimension on its canonical pole; epa_projection keys its weights by pole, so the
storage form of a bipolar row (DEAD +1 or ALIVE -1) moves no coordinate. The values are the ones the SparseWiki and
personal-wiki copies carried for each prime as stored.
"""

import pytest

from gse.prime_projection import epa_projection
from gse.primitives_v2 import literal_valence


@pytest.mark.parametrize(
    ("signature", "valence"),
    [
        ({}, 0),
        ({"GOOD": 1}, 1),
        ({"GOOD": -1}, -1),
        ({"BAD": 1}, -1),  # the negative pole, read canonically
        ({"BAD": -1}, 1),
        ({"GOOD": 1, "BAD": 1}, 0),  # a non-canonical row whose poles cancel
        ({"GOOD": 2}, 1),  # a non-ternary value keeps its sign
        ({"FEEL": 1, "SOMETHING": 1}, 0),  # no evaluation dimension
        ({"GOOD": 0}, 0),
    ],
)
def test_literal_valence_is_the_canonical_sign_of_the_evaluation_dimension(signature, valence):
    assert literal_valence(signature) == valence


@pytest.mark.parametrize(
    ("one", "other"),
    [({"DEAD": 1}, {"ALIVE": -1}), ({"BAD": 1}, {"GOOD": -1}), ({"SMALL": 1}, {"BIG": -1})],
)
def test_a_pole_projects_the_same_whichever_way_it_is_stored(one, other):
    assert epa_projection(one) == epa_projection(other)


@pytest.mark.parametrize(
    ("signature", "coordinates"),
    [
        ({"GOOD": 1}, {"E": 1.0, "P": 0.0, "A": 0.0}),
        ({"DEAD": 1}, {"E": 0.0, "P": 0.0, "A": -1.0}),
        ({"ALIVE": 1}, {"E": 0.0, "P": 0.0, "A": 0.3}),
        ({"FEEL": 1}, {"E": 0.0, "P": 0.0, "A": 0.2}),  # a bare FEEL encodes no evaluation (literal valence)
        ({"FEEL": 1, "GOOD": -1}, {"E": -1.0, "P": 0.0, "A": 0.2}),
        ({"WANT": 1}, {"E": 0.0, "P": 0.2, "A": 0.3}),
        ({"CAN": 1, "NOT": 1}, {"E": 0.0, "P": 0.5, "A": 0.0}),
        ({"GOOD": 1, "DO": 1, "MOVE": 1}, {"E": 1.0, "P": 0.0, "A": 1.8}),
    ],
)
def test_the_projection_carries_the_copies_values(signature, coordinates):
    assert epa_projection(signature) == pytest.approx(coordinates)


def test_a_word_whose_poles_cancel_projects_to_zero_not_to_nothing():
    assert epa_projection({"GOOD": 1, "BAD": 1}) == {"E": 0.0, "P": 0.0, "A": 0.0}


@pytest.mark.parametrize("signature", [{}, {"SOMETHING": 1}, {"KNOW": 1, "PEOPLE": 1}, {"DO": 0}])
def test_a_word_with_no_projecting_prime_abstains(signature):
    assert epa_projection(signature) is None
