"""The bounded checkpoint child cannot convert scope challenges into signs."""

import json
import runpy
from copy import deepcopy
from pathlib import Path

import pytest


@pytest.fixture
def helper():
    root = Path(__file__).resolve().parents[1]
    notes = root / "docs/readings/2026-11-13-ssl-explicit-genera"
    return runpy.run_path(str(notes / "ssl_api_checkpoint_happening.py")), json.loads(
        (notes / "ssl-api-controller-happening-child.json").read_text()
    )["family"]


def test_child_keeps_exact_native_guard_warrant_and_disjoint_roster(helper):
    module, raw = helper
    original = deepcopy(raw)
    family = module["child_family"](raw)
    assert raw == original
    assert family.proposal()["guards"] == raw["guards"]
    assert family.proposal()["warrant"] == raw["warrant"]
    assert list(family.holdouts) == raw["holdouts"]
    assert family.antecedent is None
    assert family.consequent == ("HAPPEN", 1)
    assert "wordnet:explosion:explosion.n.01" not in family.holdouts


@pytest.mark.parametrize(
    "change", [{"id": "blanket-event"}, {"antecedent": ["SOMETHING", 1]}, {"absent_evidence": ["HAPPEN"]}]
)
def test_replacement_population_or_absence_shortcut_is_not_the_frozen_child(helper, change):
    module, raw = helper
    with pytest.raises(ValueError, match="FROZEN_CHILD_CHANGED"):
        module["child_family"]({**raw, **change})


@pytest.mark.parametrize(
    "code", ["MODEL_ABSTAINED", "MODEL_COUNTEREXAMPLE", "AUDIT_CALL_BUDGET_EXHAUSTED", "MODEL_CONFLICT"]
)
def test_unknown_counterexample_or_missing_audit_cannot_pass_as_agreement(helper, code):
    module, _ = helper
    report = {"candidates": [{"audits": [{"code": "MODEL_AGREEMENT"}, {"code": code}]}]}
    before = deepcopy(report)
    with pytest.raises(ValueError, match="INDEPENDENT_AUDIT_PENDING"):
        module["require_audits"](report)
    assert report == before


def test_agreements_remain_proposals_for_ordinary_admission_not_writes(helper):
    module, _ = helper
    candidate = {"audits": [{"code": "MODEL_AGREEMENT"} for _ in range(3)]}
    assert module["require_audits"]({"candidates": [candidate]}) is candidate


@pytest.mark.parametrize("count", [0, 1, 2])
def test_fewer_than_frozen_three_independent_audits_is_pending(helper, count):
    module, _ = helper
    with pytest.raises(ValueError, match="INDEPENDENT_AUDIT_PENDING"):
        module["require_audits"]({"candidates": [{"audits": [{"code": "MODEL_AGREEMENT"}] * count}]})
