"""A word's sign survives its hierarchy level: "very ugly" is very bad, never very good (SA L33, L43; GSE #98).

The lexicon writes a negative two ways, as its own surface pole ({BAD: 1}) or as the canonical pole negated
({GOOD: -1}), and the front end absorbs an intensifier's level into the word it modifies ("very ugly" becomes
{GOOD: -1, HIER_PLUS: 1}). The sign was lost in the vector step, which stacked the level on the unsigned pole
(c7cd661), so these pin that step through the real encoder: word_vector_plan's own pins cannot see a consumer that
drops the sign.
"""

import numpy as np
import pytest

from gse.api import GSEEncoder
from gse.api.errors import PrimitiveError
from gse.primitives_v2 import BIPOLAR_PRIMITIVES, get_canonical_pole
from gse.vectors_v2 import bundle, encode_hierarchy

ANTONYMS = [("ugly", "beautiful"), ("terrible", "wonderful"), ("sad", "happy"), ("cruel", "kind")]
SURFACE_NEGATIVES = sorted(p for p in BIPOLAR_PRIMITIVES if get_canonical_pole(p)[1] == -1)
LEVELS = [{}, {"HIER_PLUS": 1}, {"HIER_PLUS": 2}, {"HIER_MINUS": 1}, {"HIER_MINUS": 2}]


@pytest.fixture(scope="module")
def encoder():
    enc = GSEEncoder()
    yield enc
    enc.close()


def same(a, b):
    return np.array_equal(a.to_dense(), b.to_dense())


def absorbed_adjective(encoder, text):
    """The last word as the front end hands it over (the intensifier absorbed into it), through the encoder's own
    vector step."""
    word = [t for t in encoder.encode(text).tokens if t.pos != "PUNCT"][-1]
    primitives = dict(word.word_primitives)
    return primitives, encoder._encode_word_primitives(primitives)


@pytest.mark.parametrize("level", LEVELS, ids=lambda lv: "_".join(f"{k}{v}" for k, v in lv.items()) or "bare")
@pytest.mark.parametrize("surface", SURFACE_NEGATIVES)
def test_a_surface_negative_and_its_canonical_form_are_one_vector(encoder, surface, level):
    canonical, _ = get_canonical_pole(surface)
    alone = (
        encoder._encode_word_primitives({surface: 1, **level}),
        encoder._encode_word_primitives({canonical: -1, **level}),
    )
    beside = (
        encoder._encode_word_primitives({"FEEL": 1, surface: 1, **level}),
        encoder._encode_word_primitives({"FEEL": 1, canonical: -1, **level}),
    )
    assert same(*alone)
    assert same(*beside)


@pytest.mark.parametrize("intensifier", ["very", "extremely"])
@pytest.mark.parametrize("negative, positive", ANTONYMS)
def test_an_intensified_negative_stays_opposite_its_antonym(encoder, negative, positive, intensifier):
    neg_primitives, neg = absorbed_adjective(encoder, f"{intensifier} {negative}")
    pos_primitives, pos = absorbed_adjective(encoder, f"{intensifier} {positive}")
    # The level must be on both words, or the pair is only the bare reading, which was never wrong.
    assert "HIER_PLUS" in neg_primitives and "HIER_PLUS" in pos_primitives
    assert neg.cosine(pos) < 0


@pytest.mark.parametrize("negative, positive", ANTONYMS)
def test_very_x_reads_like_very_bad_not_like_its_antonym(encoder, negative, positive):
    sentence = encoder.encode(f"It is very {negative}.").vector
    assert sentence.cosine(encoder.encode("It is very bad.").vector) > sentence.cosine(
        encoder.encode(f"It is very {positive}.").vector
    )


def test_a_signed_companion_keeps_its_sign_beside_the_stacked_target(encoder):
    basis = encoder.word_basis
    stacked = encode_hierarchy(basis.get_primitive("GOOD"), basis.get_primitive("HIER_PLUS"), 1)
    expected = bundle([stacked, basis.get_primitive("FEEL").negate()])
    assert same(encoder._encode_word_primitives({"GOOD": 1, "FEEL": -1, "HIER_PLUS": 1}), expected)


def test_a_missing_companion_raises_in_strict_mode_and_is_skipped_otherwise(encoder):
    word = {"GOOD": 1, "NOT_A_PRIME": 1, "HIER_PLUS": 1}
    strict = GSEEncoder(strict=True)
    try:
        with pytest.raises(PrimitiveError):
            strict._encode_word_primitives(word)
    finally:
        strict.close()
    assert same(encoder._encode_word_primitives(word), encoder._encode_word_primitives({"GOOD": 1, "HIER_PLUS": 1}))
