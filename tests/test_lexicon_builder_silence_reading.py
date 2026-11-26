"""Pre-silence relations under F088, and the F040 starting domains."""

from GSE.curation.lexicon_builder.engine import EMPTY, Assertion, Relation, propagate
from GSE.curation.lexicon_builder.silence import read_with_silence, starting_domains

I_SOMEONE = Relation(
    "i-someone",
    ("I", "SOMEONE"),
    ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 0), (0, 1), (1, 1)),
    ("law",),
    "foundational",
    True,
)
GOOD_BIG = Relation(
    "good-big", ("GOOD", "BIG"), ((-1, 0), (0, -1), (0, 0), (0, 1), (1, 0)), ("F067",), "foundational", True
)


def _a(bank, value):
    return Assertion(bank, value, "src", f"r:{bank}", "fam")


def test_presence_still_forces_its_consequence():
    lifted = read_with_silence(I_SOMEONE)
    start = starting_domains(("I", "SOMEONE"))
    result = propagate(("I", "SOMEONE"), (_a("I", 1),), (lifted,), initial_domains=start)
    assert result.assignments == {"I": 1, "SOMEONE": 1}


def test_a_silent_antecedent_leaves_the_consequent_free():
    lifted = read_with_silence(I_SOMEONE)
    assert (EMPTY, EMPTY) in lifted.allowed_rows and (EMPTY, 1) in lifted.allowed_rows
    assert (1, EMPTY) not in lifted.allowed_rows  # I present forces SOMEONE present


def test_a_forced_zero_stays_explicit_absence():
    lifted = read_with_silence(GOOD_BIG)
    assert (1, 0) in lifted.allowed_rows and (1, EMPTY) not in lifted.allowed_rows
    assert (EMPTY, -1) not in lifted.allowed_rows  # a size descriptor forces GOOD to explicit 0
    assert (EMPTY, EMPTY) in lifted.allowed_rows and (EMPTY, 1) not in lifted.allowed_rows


def test_a_relation_that_names_silence_is_taken_as_written():
    written = Relation("w", ("A",), ((EMPTY,), (1,)), ("law",), "foundational", True)
    assert read_with_silence(written) is written


def test_starting_domains_follow_f040_and_keep_want_signed():
    start = starting_domains(("GOOD", "FEEL", "WANT"))
    assert start["GOOD"] == {EMPTY, -1, 0, 1} and start["WANT"] == {EMPTY, -1, 0, 1}
    assert start["FEEL"] == {EMPTY, 0, 1}
