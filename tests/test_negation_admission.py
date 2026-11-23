"""Recognition cannot silently replace incompatible selected lexical evidence."""

import pytest

from gse.api import GSEEncoder
from gse.curation.lexicon_builder.engine import Assertion, propagate
from gse.curation.lexicon_builder.evidence import Definition
from gse.curation.lexicon_builder.foundation import BANKS
from gse.curation.lexicon_builder.storage import open_build, store_entry
from gse.nlp.morphology import NEGATION, negation_admission
from gse.primitives_v2 import negate_decomposition

NEG = {"state": "resolved", "feature": NEGATION}


def test_selected_row_conflict_is_preserved_even_with_verified_antonymy():
    out = negation_admission(
        NEG,
        {"state": "primes", "selected_record": {"id": 1, "pos": "x"}, "primitives": {"ALIVE": 1}},
        {"state": "primes", "selected_record": {"id": 2, "pos": "x"}, "primitives": {"ALIVE": 1, "GOOD": -1}},
        "ADJ",
    )
    assert out["decision"] == "preserve"
    assert out["code"] == "selected_lexical_conflict"
    assert out["primitives"] is None


def test_compatible_subset_can_recover_supported_base_without_sign_loss():
    out = negation_admission(
        NEG,
        {"state": "primes", "selected_record": {"id": 1, "pos": "x"}, "primitives": {"GOOD": -1}},
        {"state": "primes", "selected_record": {"id": 2, "pos": "x"}, "primitives": {"GOOD": 1, "FEEL": 1}},
        "ADJ",
    )
    assert out["decision"] == "compose"
    assert out["primitives"] == {"GOOD": -1, "FEEL": 1}


def test_closed_class_homograph_never_supplies_a_negative_word_decomposition():
    out = negation_admission(
        NEG,
        {"state": "primes", "selected_record": {"id": 1, "pos": "x"}, "primitives": {"DO": 1, "FEEL": 1, "GOOD": -1}},
        {
            "state": "primes",
            "selected_record": {"id": 2, "pos": "x", "component_type": "closed_class"},
            "primitives": {"LIKE": 1},
        },
        "VERB",
    )
    assert out["decision"] == "preserve"
    assert out["code"] == "base_closed_class_or_operator"


def test_missing_surface_can_compose_supported_productive_negative():
    out = negation_admission(
        NEG,
        {"state": "no_row", "selected_record": None, "primitives": {}},
        {"state": "primes", "selected_record": {"id": 2, "pos": "a"}, "primitives": {"GOOD": 1}},
        "NOUN",
    )
    assert out["decision"] == "compose"
    assert out["code"] == "productive_negative"
    assert out["primitives"] == {"GOOD": -1}


def test_ambiguous_base_is_not_silently_presented_as_verified_sense():
    out = negation_admission(
        NEG,
        {"state": "no_row"},
        {"state": "primes", "ambiguous": True, "selected_record": {"id": 2, "pos": "a"}, "primitives": {"GOOD": 1}},
        "ADJ",
    )
    assert out["decision"] == "preserve"
    assert out["code"] == "sense_unresolved"


def test_designed_zero_and_unread_base_are_not_filled_with_guessed_primes():
    assert (
        negation_admission(
            NEG,
            {"state": "no_primes", "selected_record": {"id": 1, "pos": "a"}, "primitives": {}},
            {"state": "primes", "selected_record": {"id": 2, "pos": "a"}, "primitives": {"GOOD": 1}},
            "ADJ",
        )["code"]
        == "surface_lexical_zero"
    )
    assert negation_admission(NEG, {"state": "no_row"}, {"state": "unread"}, "ADJ")["code"] == "lexical_unread"
    assert (
        negation_admission(
            NEG,
            {"state": "no_row"},
            {"state": "primes", "selected_record": {"pos": "a"}, "primitives": {"FEEL": 1}},
            "ADJ",
        )["code"]
        == "base_without_bipolar_sign"
    )


def test_real_encoder_preserves_dislike_and_independent_and_retains_negation_evidence(encoder):
    with encoder:
        dislike = next(token for token in encoder.encode("I dislike it.").tokens if token.token == "dislike")
        independent = next(
            token for token in encoder.encode("The country is independent.").tokens if token.token == "independent"
        )
        assert dislike.word_primitives == encoder.lexical_lookup("dislike")["primitives"]
        assert independent.word_primitives == encoder.lexical_lookup("independent")["primitives"]
        assert dislike.negation_evidence["feature"] == NEGATION
        assert dislike.negation_evidence["admission"]["decision"] == "preserve"
        assert independent.negation_evidence["admission"]["code"] == "selected_lexical_conflict"


def test_real_encoder_keeps_canonical_and_productive_compositions(encoder):
    with encoder:
        for surface, base in [("unhappy", "happy"), ("unkind", "kind"), ("unloyal", "loyal")]:
            token = encoder.encode(surface).tokens[0]
            assert token.word_primitives == negate_decomposition(encoder.lexical_lookup(base)["primitives"])
            assert token.negation_evidence["admission"]["decision"] == "compose"


@pytest.fixture
def encoder(tmp_path):
    """Partial synthetic mechanism fixtures, not a semantic evaluation lexicon."""
    path = tmp_path / "definitions.db"
    connection = open_build(path)
    records = (
        ("like", "verb", {"FEEL": 1, "GOOD": 1}),
        ("dislike", "verb", {"FEEL": 1, "GOOD": -1}),
        ("dependent", "adj", {"WITH": 1}),
        ("independent", "adj", {"WITH": -1, "CAN": 1}),
        ("happy", "adj", {"FEEL": 1, "GOOD": 1}),
        ("kind", "adj", {"GOOD": 1, "SOMETHING": 0}),
        ("loyal", "adj", {"GOOD": 1}),
    )
    for word, pos, values in records:
        entry_id = f"fixture:{word}"
        assertions = tuple(Assertion(bank, value, "fixture", entry_id, "mechanism") for bank, value in values.items())
        store_entry(
            connection,
            Definition(entry_id, word, pos, "Synthetic admission-mechanism fixture"),
            propagate(BANKS, assertions, ()),
            assertions,
        )
    connection.commit()
    connection.close()
    with GSEEncoder(str(path)) as instance:
        yield instance


@pytest.mark.parametrize("complete", [False, True])
@pytest.mark.parametrize("equal_geometry", [False, True])
def test_multiple_definitions_never_supply_first_row_negation(tmp_path, complete, equal_geometry):
    """Even fully specified identical synthetic vectors cannot identify a definition."""
    path = tmp_path / "ambiguous.db"
    connection = open_build(path)
    for index in range(2):
        entry_id = f"fixture:kind:{index}"
        values = dict.fromkeys(BANKS, 0) if complete else {}
        # Explicit synthetic coordinates test identity, not word-meaning claims.
        values["GOOD"] = 1 if equal_geometry or index == 0 else -1
        assertions = tuple(Assertion(bank, value, "fixture", entry_id, "mechanism") for bank, value in values.items())
        resolution = propagate(BANKS, assertions, ())
        assert resolution.code == ("RESOLVED" if complete else "PARTIAL")
        store_entry(
            connection,
            Definition(entry_id, "kind", "adj", f"Distinct fixture definition {index}"),
            resolution,
            assertions,
        )
    connection.commit()
    connection.close()
    with GSEEncoder(str(path)) as instance:
        evidence = instance.lexical_lookup("kind")
        assert evidence["selection_status"] == "AMBIGUOUS"
        assert evidence["selected_record"] is None
        assert evidence["primitives"] == {}
        assert len(evidence["candidate_entry_ids"]) == 2
        token = instance.encode("unkind").tokens[0]
        assert token.word_primitives == {}
        assert token.word_vec_nnz == 0
        assert token.negation_evidence["admission"]["decision"] == "preserve"
        assert token.negation_evidence["admission"]["code"] == "lexical_unread"
