"""Recognition cannot silently replace incompatible selected lexical evidence."""

from gse.api import GSEEncoder
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
        {"state": "primes", "selected_record": {"id": 2, "pos": "x"}, "primitives": {"GOOD": 1, "SOMETHING": 1}},
        "ADJ",
    )
    assert out["decision"] == "compose"
    assert out["primitives"] == {"GOOD": -1, "SOMETHING": 1}


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
            {"state": "primes", "selected_record": {"pos": "a"}, "primitives": {"SOMETHING": 1}},
            "ADJ",
        )["code"]
        == "base_without_bipolar_sign"
    )


def test_real_encoder_preserves_dislike_and_independent_and_retains_negation_evidence():
    with GSEEncoder() as encoder:
        dislike = next(token for token in encoder.encode("I dislike it.").tokens if token.token == "dislike")
        independent = next(
            token for token in encoder.encode("The country is independent.").tokens if token.token == "independent"
        )
        assert dislike.word_primitives == encoder.lexical_lookup("dislike")["primitives"]
        assert independent.word_primitives == encoder.lexical_lookup("independent")["primitives"]
        assert dislike.negation_evidence["feature"] == NEGATION
        assert dislike.negation_evidence["admission"]["decision"] == "preserve"
        assert independent.negation_evidence["admission"]["code"] == "selected_lexical_conflict"


def test_real_encoder_keeps_canonical_and_productive_compositions():
    with GSEEncoder() as encoder:
        for surface, base in [("unhappy", "happy"), ("unkind", "kind"), ("unloyal", "loyal")]:
            token = encoder.encode(surface).tokens[0]
            assert token.word_primitives == negate_decomposition(encoder.lexical_lookup(base)["primitives"])
            assert token.negation_evidence["admission"]["decision"] == "compose"
