"""Coverage is per bank, with no silent deletion of an identified omission.

Coupled repair fixtures test the mechanism, not proposed laws of English.
"""

import copy

from gse.lexicon_builder.core import Cell, Law, resolve
from gse.lexicon_builder.coverage import BANK_FIELDS, bank_coverage_status, review_banks


class BankSelector:
    def __init__(self, omissions=(), unresolved=(), repair="+1"):
        self.omissions, self.unresolved = omissions, unresolved
        self.repair = repair
        self.requests = []

    def select(self, payload, options):
        self.requests.append((copy.deepcopy(payload), copy.deepcopy(options)))
        if payload["operation"] == "BANK_OMISSION_REVIEW":
            answer = {}
            for field in options:
                domains = payload["bank_accounts"][field]["coordinate_domains"]
                answer[field] = (
                    "UNRESOLVED"
                    if field in self.unresolved
                    else (
                        "MISSING" if any(c in domains and len(domains[c]) > 1 for c in self.omissions) else "ACCOUNTED"
                    )
                )
        elif payload["operation"] == "LOCATE_BANK_OMISSION":
            answer = {
                f: next((c for c in self.omissions if c in values), "UNRESOLVED") for f, values in options.items()
            }
        else:
            answer = {c: self.repair for c in options}
        return {"answer": answer, "request_sha256": f"bank-test-{len(self.requests)}"}


def test_a_blank_or_partial_review_never_closes_other_banks():
    assert bank_coverage_status({}) == "INCOMPLETE_BANK_REVIEW"
    assert bank_coverage_status({"BANK_0": "ACCOUNTED"}) == "INCOMPLETE_BANK_REVIEW"
    accounts = dict.fromkeys(BANK_FIELDS, "ACCOUNTED")
    assert bank_coverage_status(accounts) == "BANKS_ACCOUNTED"
    accounts["BANK_7"] = "UNRESOLVED"
    assert bank_coverage_status(accounts) == "UNRESOLVED_BANK_REVIEW"
    accounts["BANK_1"] = "MISSING"
    assert bank_coverage_status(accounts) == "MISSING_COMPONENT"
    accounts["BANK_1"] = "NONE"
    assert bank_coverage_status(accounts) == "INVALID_BANK_REVIEW"


def test_all_eight_banks_are_explicit_and_each_field_has_three_options():
    selector = BankSelector()
    before = resolve("test", laws=())
    result = review_banks("test", (), [], before, {}, selector, {})
    assert result["code"] == "BANKS_ACCOUNTED"
    assert set(result["rounds"][0]["accounts"]) == set(BANK_FIELDS)
    assert len(selector.requests) == 2
    assert all(len(options) <= 5 for _, options in selector.requests)
    assert all(len(values) == 3 for _, options in selector.requests for values in options.values())
    assert result["state"].forced() == {}  # A model account alone writes nothing.


def test_missing_contract_stays_partial_instead_of_fabricating_a_sign():
    selector = BankSelector(omissions=("FEEL", "WORDS"))
    result = review_banks("test", (), [], resolve("test", laws=()), {}, selector, {})
    assert result["code"] == "MISSING_PROJECTION_CONTRACT"
    assert set(result["missing"]) == {"FEEL", "WORDS"}
    assert result["state"].forced() == {}
    locate = selector.requests[-1][1]
    assert "WORDS" not in locate["BANK_3"]
    assert "FEEL" not in locate["BANK_4"]


def test_one_scoped_repair_propagates_to_another_bank_before_rechecking():
    # Deliberately synthetic: no claim that FEEL universally entails WORDS.
    coupled = Law(
        "TEST_ONLY_COUPLED",
        ("FEEL", "WORDS"),
        ((Cell.PLUS, Cell.PLUS), (Cell.SILENT, Cell.SILENT)),
        (),
        "mechanism fixture",
    )
    laws = [coupled]
    selector = BankSelector(omissions=("FEEL", "WORDS"))
    before = resolve("test", laws=tuple(laws))
    result = review_banks("test", (), laws, before, {}, selector, {"FEEL": ["+1"]})
    assert result["code"] == "BANKS_ACCOUNTED"
    assert result["state"].forced() == {"FEEL": Cell.PLUS, "WORDS": Cell.PLUS}
    assert len(result["decisions"]) == 1
    assert len(result["rounds"]) == 2
    fills = [opts for payload, opts in selector.requests if payload["operation"] == "FILL_SCOPED_OMISSION"]
    assert fills == [{"FEEL": ["+1", "UNRESOLVED"]}]
    assert before.forced() == {}  # No mutation of the earlier result.


def test_uncertainty_and_an_illegal_repair_cannot_license_silence():
    unresolved = review_banks("test", (), [], resolve("test", laws=()), {}, BankSelector(unresolved=("BANK_2",)), {})
    assert unresolved["code"] == "UNRESOLVED_BANK_REVIEW"
    illegal = review_banks(
        "test", (), [], resolve("test", laws=()), {}, BankSelector(omissions=("FEEL",)), {"FEEL": ["-1"]}
    )
    assert illegal["code"] == "NO_LEGAL_REPAIR"
    refused = review_banks(
        "test",
        (),
        [],
        resolve("test", laws=()),
        {},
        BankSelector(omissions=("FEEL",), repair="UNRESOLVED"),
        {"FEEL": ["+1"]},
    )
    assert refused["code"] == "UNRESOLVED_REPAIR"


def test_repair_budget_never_becomes_default_closure():
    result = review_banks(
        "test", (), [], resolve("test", laws=()), {}, BankSelector(omissions=("FEEL",)), {"FEEL": ["+1"]}, max_repairs=0
    )
    assert result["code"] == "REPAIR_LIMIT"
    assert result["state"].forced() == {}
