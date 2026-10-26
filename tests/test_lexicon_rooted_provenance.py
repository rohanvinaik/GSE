"""Independent roots, cyclic counterexamples and joint provenance support."""

from gse.lexicon_builder.core import rooted_law_status
from gse.lexicon_builder.foundation import decision_check

EQUAL = (("THINK", "KNOW"), (("0", "0"), ("+1", "+1")))


def test_a_relation_cannot_root_either_of_two_separate_decisions():
    vector = {"THINK": "0", "KNOW": "0"}
    laws = {"EQUAL": EQUAL}
    assert decision_check("0", ["EQUAL"], ["THINK"], vector, ["EQUAL"], laws) == "CITED_LAW_NOT_ROOTED"
    assert decision_check("0", ["EQUAL"], ["KNOW"], vector, ["EQUAL"], laws) == "CITED_LAW_NOT_ROOTED"


def test_an_independent_root_supports_the_consequence_but_not_reverse_credit():
    vector = {"THINK": "0", "KNOW": "0"}
    laws = {"EQUAL": EQUAL, "ROOT_THINK": (("THINK",), (("0",),))}
    active = ["EQUAL", "ROOT_THINK"]
    assert decision_check("0", ["EQUAL"], ["KNOW"], vector, active, laws) == "RECONSTRUCTED"
    assert decision_check("0", ["EQUAL"], ["THINK"], vector, active, laws) == "CITED_LAW_NOT_ROOTED"
    assert decision_check("0", ["ROOT_THINK"], ["THINK"], vector, active, laws) == "RECONSTRUCTED"


def test_genuine_redundant_roots_remain_credited_after_another_root_is_removed():
    vector = {"THINK": "0", "KNOW": "0"}
    laws = {
        "EQUAL": EQUAL,
        "ROOT_THINK": (("THINK",), (("0",),)),
        "ROOT_KNOW": (("KNOW",), (("0",),)),
    }
    active = list(laws)
    assert decision_check("0", ["ROOT_THINK", "EQUAL"], ["THINK"], vector, active, laws) == "RECONSTRUCTED"
    assert decision_check("0", ["EQUAL"], ["THINK"], vector, ["EQUAL", "ROOT_KNOW"], laws) == "RECONSTRUCTED"
    assert decision_check("0", ["EQUAL"], ["THINK"], vector, ["EQUAL"], laws) == "CITED_LAW_NOT_ROOTED"


def test_a_transitive_cycle_cannot_return_the_target_as_an_independent_root():
    laws = {
        "THINK_KNOW": EQUAL,
        "KNOW_WANT": (("KNOW", "WANT"), (("0", "0"), ("+1", "+1"))),
        "WANT_THINK": (("WANT", "THINK"), (("0", "0"), ("+1", "+1"))),
        "ROOT_THINK": (("THINK",), (("0",),)),
    }
    vector = {"THINK": "0", "KNOW": "0", "WANT": "0"}
    assert decision_check("0", ["WANT_THINK"], ["THINK"], vector, list(laws), laws) == "CITED_LAW_NOT_ROOTED"
    assert decision_check("0", ["KNOW_WANT"], ["WANT"], vector, list(laws), laws) == "RECONSTRUCTED"


def test_joint_independent_constraints_can_prove_a_value_without_singleton_premises():
    # KNOW and WANT may both be 0 or both +1. THINK is their parity: always 0.
    laws = {
        "JOINT_PREMISE": (("KNOW", "WANT"), (("0", "0"), ("+1", "+1"))),
        "PARITY": (
            ("THINK", "KNOW", "WANT"),
            (("0", "0", "0"), ("+1", "0", "+1"), ("+1", "+1", "0"), ("0", "+1", "+1")),
        ),
    }
    assert rooted_law_status("0", ["THINK"], "PARITY", laws, list(laws)) == "ROOTED"
    assert (
        decision_check(
            "0", ["PARITY"], ["THINK"], {"THINK": "0", "KNOW": "unresolved", "WANT": "unresolved"}, list(laws), laws
        )
        == "RECONSTRUCTED"
    )


def test_permissive_and_inactive_laws_cannot_gain_provenance_credit():
    laws = {"ANY": (("INTENSITY",), (("0",), ("+1",), ("empty",))), "ROOT": (("INTENSITY",), (("+1",),))}
    vector = {"INTENSITY": "+1"}
    assert decision_check("+1", ["ANY"], ["INTENSITY"], vector, list(laws), laws) == "CITED_LAW_DOES_NOT_FORCE"
    assert decision_check("+1", ["ROOT"], ["INTENSITY"], vector, ["ANY"], laws) == "CITED_LAW_INACTIVE"


def test_a_proof_limit_is_a_residual_and_never_a_root():
    laws = {"EQUAL": EQUAL, "ROOT_KNOW": (("KNOW",), (("0",),))}
    assert rooted_law_status("0", ["THINK"], "EQUAL", laws, list(laws), max_joint_assignments=0) == (
        "PROVENANCE_SOLVER_LIMIT"
    )


def test_a_background_contradiction_is_not_vacuous_proof():
    laws = {
        "EQUAL": EQUAL,
        "ROOT_KNOW": (("KNOW",), (("0",),)),
        "CONTRARY_KNOW": (("KNOW",), (("+1",),)),
    }
    assert rooted_law_status("0", ["THINK"], "EQUAL", laws, list(laws)) == "PROVENANCE_BACKGROUND_CONFLICT"
