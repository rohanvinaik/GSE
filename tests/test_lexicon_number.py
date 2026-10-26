"""NUMBER orders compatible definitions; it cannot alter their signs or masks."""

from __future__ import annotations

import copy
import json

import pytest

from gse.lexicon_builder.core import CANONICAL_COORDINATES
from gse.lexicon_builder.number import pair_precondition, paired_order_status, resolve_number_pair


def test_inverse_comparisons_and_equality_are_coherent():
    assert paired_order_status("LESS", "MORE") == "VALID_RELATIVE_ORDER"
    assert paired_order_status("MORE", "LESS") == "VALID_RELATIVE_ORDER"
    assert paired_order_status("EQUAL", "EQUAL") == "VALID_RELATIVE_ORDER"


def test_a_constant_direction_is_a_contradiction_not_a_scalar_value():
    assert paired_order_status("LESS", "LESS") == "CONTRADICTORY_ORDER"
    assert paired_order_status("MORE", "MORE") == "CONTRADICTORY_ORDER"
    assert paired_order_status("EQUAL", "MORE") == "CONTRADICTORY_ORDER"


def test_unresolved_and_illegal_answers_never_make_a_value():
    assert paired_order_status("UNRESOLVED", "MORE") == "UNRESOLVED_ORDER"
    assert paired_order_status("LESS", "UNRESOLVED") == "UNRESOLVED_ORDER"
    assert paired_order_status("wrong", "MORE") == "ILLEGAL_ORDER_CODE"
    assert paired_order_status("LESS", "wrong") == "ILLEGAL_ORDER_CODE"


class OrderSelector:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = []

    def select(self, payload, options):
        self.calls.append((payload, options))
        return {"answer": {"LEFT_INTENSITY_RELATIVE_TO_RIGHT": next(self.answers)}}


@pytest.fixture
def pair():
    states = dict.fromkeys(CANONICAL_COORDINATES, "empty")
    states.update(FEEL="+1", GOOD="+1", INTENSITY="+1", SOMETHING="0", KIND="0")
    return tuple(
        {
            "word": name,
            "reading_id": name + ":scoped_reading",
            "states": dict(states),
            "mask": [states[c] != "empty" for c in CANONICAL_COORDINATES],
            "number_scale": {"family": "feeling:+1", "native_ordinal_rank": 1},
        }
        for name in ["base", "stronger"]
    )


def test_relative_value_preserves_every_sign_mask_and_source_record(pair):
    left, right = pair
    before = json.dumps(pair, sort_keys=True)
    selector = OrderSelector(["LESS", "MORE"])
    result = resolve_number_pair(left, right, selector)
    assert result["code"] == "RESOLVED_RELATIVE_NUMBER"
    assert result["number_values"] == {"left": 0, "right": 1}
    assert result["numeric_gain"] is None
    assert result["coordinate_changes"] == []
    assert json.dumps(pair, sort_keys=True) == before
    assert len(selector.calls) == 2


def test_inconsistent_model_pair_cannot_export_a_number(pair):
    result = resolve_number_pair(*pair, OrderSelector(["MORE", "MORE"]))
    assert result["code"] == "CONTRADICTORY_ORDER"
    assert result["number_values"] is None


def test_same_reading_is_equal_without_a_model_call(pair):
    selector = OrderSelector([])
    result = resolve_number_pair(pair[0], pair[0], selector)
    assert result["number_values"] == {"left": 0, "right": 0}
    assert selector.calls == []


def test_incompatible_domains_or_definition_patterns_are_refused(pair):
    left, right = pair
    altered = copy.deepcopy(right)
    altered["number_scale"]["family"] = "another_domain"
    assert pair_precondition(left, altered) == "INCOMPATIBLE_SCALE_DOMAIN"
    altered = copy.deepcopy(right)
    altered["states"]["GOOD"] = "-1"
    assert pair_precondition(left, altered) == "INCOMPATIBLE_PATTERN"
    altered = copy.deepcopy(right)
    altered["mask"][CANONICAL_COORDINATES.index("FEEL")] = False
    assert pair_precondition(left, altered) == "INCOMPATIBLE_PATTERN"
    altered = copy.deepcopy(left)
    altered["states"]["INTENSITY"] = "empty"
    altered["mask"][CANONICAL_COORDINATES.index("INTENSITY")] = False
    assert pair_precondition(altered, altered) == "NO_INTENSITY_DOMAIN"
