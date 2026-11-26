import pytest

from GSE.curation.lexicon_builder.valency_absence import absent_banks, nonliving_root, person_bearer_primes


def test_the_person_bearer_primes_come_from_the_profiles_less_attested_thing_subjects():
    assert person_bearer_primes() == ("DO", "FEEL", "KNOW", "SAY", "THINK", "WANT")  # HAVE: a beak "has two parts"


@pytest.mark.parametrize(
    ("entry", "root"),
    [
        ("wordnet:hammer:hammer.n.02", "artifact.n.01"),
        ("wordnet:minute:minute.n.01", "time_unit.n.01"),
        ("wordnet:house:house.n.01", "artifact.n.01"),
    ],
)
def test_non_living_things_times_and_places_cannot_bear_experiencer_predicates(entry, root):
    assert nonliving_root(entry.rsplit(":", 1)[1]) == root
    assert absent_banks(entry) == person_bearer_primes()


@pytest.mark.parametrize(
    "entry",
    [
        "wordnet:dog:dog.n.01",  # a creature: Goddard 2018, creatures can feel
        "wordnet:mother:mother.n.01",  # a person
        "wordnet:invitation:invitation.n.01",  # an artifact that is also a communication
        "wordnet:family:family.n.01",  # a group of people
        "wordnet:run:run.v.01",  # not a noun
    ],
)
def test_possible_bearers_and_non_nouns_are_not_silenced(entry):
    assert absent_banks(entry) == ()
