"""A compiled candidate must never become an admitted bank law by accident."""

from gse.lexicon_builder.atomics import atomic_proof
from gse.lexicon_builder.build import construct, source_matches
from gse.lexicon_builder.core import Cell, admitted_laws, law_admission_status, resolve
from gse.lexicon_builder.registry import load_rulebook
from tests.lexicon_rulebook import certify_rule


def test_only_a_recorded_or_validated_contract_can_write():
    assert law_admission_status(load_rulebook()["laws"][0]) == "ADMITTED"
    assert law_admission_status({"rule_id": "INVENTED", "review_state": "FOUNDER_APPROVED"}) == "NOT_ADMITTED"
    assert law_admission_status({"review_state": "CANDIDATE"}) == "NOT_ADMITTED"
    assert law_admission_status({"review_state": "DISCOVERED_NOT_ADMITTED"}) == "NOT_ADMITTED"
    assert law_admission_status({"review_state": "IMPLEMENTED_FOR_PROTOTYPE_AUDIT"}) == "NOT_ADMITTED"
    assert law_admission_status({"review_state": None}) == "NOT_ADMITTED"
    assert law_admission_status({}) == "NOT_ADMITTED"


def test_unapproved_relation_is_inert_in_both_atomic_and_word_paths():
    book = load_rulebook()
    book["laws"].append(
        {
            "rule_id": "UNAPPROVED_TEST_KNOW",
            "review_state": "CANDIDATE",
            "coordinates": ["KNOW"],
            "allowed": [["+1"]],
            "guard": [],
            "warrant": "Test-only inadmissible relation; must not change any output",
        }
    )
    atom = next(r for r in atomic_proof(book)["records"] if r["prime"] == "FEEL")
    baseline = next(r for r in atomic_proof()["records"] if r["prime"] == "FEEL")
    assert atom["vector"] == baseline["vector"] and atom["vector"]["KNOW"] == "empty"
    assert atom["definition_check"] == "RECONSTRUCTED"
    native = {
        "usas": {"records": [{"record_id": "USAS:test", "values": {"pos": "ADJ", "alternatives": ["A5.1+"]}}]},
        "framenet": {"records": [{"record_id": "FN:test", "values": {"pos": "a", "frame": "Desirability"}}]},
    }
    reading = construct("test", source_matches(native, book)[0], native, book, None)
    assert "KNOW" not in reading["symbolic_before"]["forced"]
    assert "UNAPPROVED_TEST_KNOW" not in reading["symbolic_before"]["fired_rules"]
    # Admission must make a real difference, rather than simply ignoring laws.
    book["laws"][-1]["review_state"] = "FOUNDER_APPROVED"
    assert "KNOW" not in resolve("test", laws=admitted_laws(book)).forced()
    certify_rule(
        book["laws"][-1],
        positive="tests/test_lexicon_rule_admission.py::test_unapproved_relation_is_inert_in_both_atomic_and_word_paths",
        must_not="tests/test_lexicon_rule_admission.py::test_only_a_recorded_or_validated_contract_can_write",
    )
    assert resolve("test", laws=admitted_laws(book)).forced()["KNOW"] == Cell.PLUS
    # Admitted, it contradicts FEEL's examined boundary, and the foundation says so.
    assert atomic_proof(book)["code"] == "FOUNDATION_CONFLICT"
