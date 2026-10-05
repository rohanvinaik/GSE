"""The personal dictionary's two decisions, stated as the readings GSE's word-scale rules require (#60)."""

from gse.curation.personal_dictionary import check_decomposition, concur


def test_a_surface_pole_is_written_as_its_canonical_pole():
    # BAD is GOOD with the opposite sign: one dimension, one canonical name (GT §5.3).
    assert check_decomposition({"BAD": 1, "FEEL": 1}) == ({"GOOD": -1, "FEEL": 1}, [])


def test_both_poles_of_one_dimension_conflict():
    canon, problems = check_decomposition({"SAME": 1, "OTHER": 1, "KIND": 1, "PART": 1})
    assert "CONFLICTING_POLES:SAME" in problems and "SAME" not in canon


def test_degree_never_enters_a_words_identity():
    # Hierarchy is bound at encode time, never stored as a word's value (FA L741).
    assert "HIERARCHY_MARKER:HIER_PLUS" in check_decomposition({"HIER_PLUS": 1, "BIG": 1, "KIND": 1})[1]


def test_only_generic_primes_is_not_a_meaning():
    assert check_decomposition({"SOMETHING": 1, "DO": 1}) == ({"SOMETHING": 1, "DO": 1}, ["GENERIC_ONLY"])


def test_two_members_concur_prime_by_prime():
    assert concur({"GOOD": -1, "FEEL": 1, "KNOW": 1}, {"GOOD": 1, "FEEL": 1, "SEE": 1}) == {
        "FEEL": "AGREED",
        "GOOD": "SIGN_CONFLICT",
        "KNOW": "ONLY_FIRST",
        "SEE": "ONLY_SECOND",
    }


def test_concurrence_is_written_in_sorted_order():
    # A dictionary file built from these codes is byte-reproducible only if their order is fixed.
    first = {"WANT": 1, "SEE": 1, "KNOW": 1, "FEEL": 1, "GOOD": -1, "BODY": 1}
    second = {"BODY": 1, "GOOD": 1, "FEEL": 1, "KNOW": 1, "SEE": 1, "WANT": 1}
    assert list(concur(first, second)) == ["BODY", "FEEL", "GOOD", "KNOW", "SEE", "WANT"]
