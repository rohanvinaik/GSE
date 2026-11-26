"""The tail's cause classes (F148): each disagreement with NSM gets a computed cause, never a judged one.

The clauses here are written for the test (the NSM explications are copyrighted and git-ignored).
"""

from __future__ import annotations

import pytest

from GSE.curation.lexicon_builder import word_sense_nsm_tail as tail
from GSE.curation.lexicon_builder.applicability import bank_categories
from GSE.curation.lexicon_builder.template_types import verified_records


@pytest.fixture(scope="module")
def categories():
    return bank_categories()


def _kinds(clause, categories, introducers=("like this",)):
    out = {}
    for token in tail.tokens_in(clause, categories, introducers):
        out.setdefault(token.bank, set()).add(token.kind)
    return out


def test_the_category_formula_is_frame_but_its_substantive_is_content(categories):
    kinds = _kinds("people of one kind", categories)
    assert kinds["KIND"] == {"frame"}
    assert kinds["ONE"] == {"frame"}
    assert kinds["PEOPLE"] == {"content"}


def test_the_article_a_read_as_as_is_a_collision_and_like_itself_is_content(categories):
    kinds = _kinds("it is like a stone [m]", categories)
    assert kinds["LIKE"] == {"collision", "content"}
    assert tail.token_class("LIKE", tail.tokens_in("a long tail [m]", categories), categories) == "EXPONENT_COLLISION"


def test_the_plural_chart_exponent_kinds_matches_kind_without_collision(categories):
    kinds = _kinds("trees [m] of many different kinds grow here", categories)
    assert kinds["KIND"] == {"content"}


def test_this_is_deictic_and_someone_stays_content(categories):
    kinds = _kinds("this someone", categories)
    assert kinds["SOMETHING"] == {"deictic"}
    assert kinds["SOMEONE"] == {"content"}


def test_forms_of_be_are_the_copula(categories):
    kinds = _kinds("they are big", categories)
    assert kinds["BE"] == {"copula"}
    assert kinds["BIG"] == {"content"}


def test_the_component_introducer_is_frame_and_a_logical_concept_is_an_operator(categories):
    tokens = tail.tokens_in("they can move like this", categories, ("like this",))
    by_bank = {t.bank: t for t in tokens}
    assert by_bank["LIKE"].kind == "frame"
    assert tail.token_class("CAN", [t for t in tokens if t.bank == "CAN"], categories) == "LOGICAL_OPERATOR"
    assert tail.token_class("MOVE", [t for t in tokens if t.bank == "MOVE"], categories) == "CONTENT"


def test_a_negative_pole_keeps_its_sign(categories):
    (good,) = [t for t in tail.tokens_in("something very bad can happen", categories) if t.bank == "GOOD"]
    assert good.sign == -1


def test_a_convention_zero_names_the_convention_rule():
    senses = [
        {"assignments": {"GOOD": 0}, "provenance": {"GOOD": {"from": "members", "entries": ["e1"]}}},
    ]
    traces = {"e1": [{"kind": "RELATION", "bank": "GOOD", "rule_id": "founder:noun-own-evaluation"}]}
    assert tail.classify("GOOD", {"GOOD": 0}, senses, [], {}, traces) == "CONVENTION_ZERO"
    other = {"e1": [{"kind": "RELATION", "bank": "GOOD", "rule_id": "reviewed-guarded-pattern:x"}]}
    assert tail.classify("GOOD", {"GOOD": 0}, senses, [], {}, other) == "NO_TOKEN"


def test_a_value_one_sense_holds_is_a_sense_split():
    senses = [{"assignments": {"ALIVE": 1}, "provenance": {}}, {"assignments": {}, "provenance": {}}]
    assert tail.classify("ALIVE", {}, senses, [], {}, {}) == "SENSE_SPLIT"


def test_the_synset_carry_fills_derived_spellings_and_reports_clashes():
    entries = [
        ("wordnet:dog:dog.n.01", 1, "dog"),
        ("wordnet:dogs:dog.n.01", 2, "dogs"),
        ("wordnet:cat:cat.n.01", 3, "cat"),
        ("wordnet:cats:cat.n.01", 4, "cats"),
    ]
    values = {1: {"ALIVE": 1, "BODY": 1}, 2: {"ALIVE": 1}, 3: {"BODY": 1}, 4: {"BODY": 0}}
    carry = tail.synset_carry(entries, values)
    assert set(carry) == {"wordnet:dogs:dog.n.01", "wordnet:cats:cat.n.01"}
    assert carry["wordnet:dogs:dog.n.01"]["gained"] == {"BODY": 1}
    assert carry["wordnet:cats:cat.n.01"] == {
        "gained": {},
        "clash": {"BODY": [0, 1]},
        "native": ["wordnet:cat:cat.n.01"],
    }


@pytest.mark.skipif(not verified_records(), reason="the verified NSM extracts are not present (git-ignored)")
def test_the_component_introducers_come_from_nsm_template_records():
    assert tail.component_introducers() == ("like this",)
