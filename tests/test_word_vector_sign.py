"""A word's sign survives its hierarchy level: "very ugly" is very bad, never very good (SA L33, L43; GSE #98).

The lexicon writes a negative two ways, as its own surface pole ({BAD: 1}) or as the canonical pole negated
({GOOD: -1}). The public trace carries degree on the modified token, independently of lexical signs. The sign was lost in the vector step, which stacked the level on the unsigned pole
(c7cd661), so these pin that step through the real encoder: word_vector_plan's own pins cannot see a consumer that
drops the sign.
"""

import pytest  # noqa: E402

pytest.importorskip(
    "GSE.curation.lexicon_builder.storage",
    reason="fixture lexicons await the rebuilt artifact writer (rebuild-lexicon-symbolic-closure task 10.1)",
)

import numpy as np
import pytest

from GSE.api import GSEEncoder
from GSE.api.errors import PrimitiveError
from GSE.curation.lexicon_builder.engine import Assertion, propagate
from GSE.curation.lexicon_builder.evidence import Definition
from GSE.curation.lexicon_builder.storage import open_build, store_entry
from GSE.primitives_v2 import BIPOLAR_PRIMITIVES, SemanticBank, get_canonical_pole
from GSE.vectors_v2 import bundle, encode_hierarchy

ANTONYMS = [("ugly", "beautiful"), ("terrible", "wonderful"), ("sad", "happy"), ("cruel", "kind")]
SURFACE_NEGATIVES = sorted(p for p in BIPOLAR_PRIMITIVES if get_canonical_pole(p)[1] == -1)
LEVELS = [{}, {"HIER_PLUS": 1}, {"HIER_PLUS": 2}, {"HIER_MINUS": 1}, {"HIER_MINUS": 2}]


@pytest.fixture(scope="module")
def encoder(tmp_path_factory):
    """Synthetic sign-mechanism fixtures, not semantic gold or corpus coverage."""
    path = tmp_path_factory.mktemp("word-sign") / "definitions.db"
    connection = open_build(path)
    records = [(word, "adj", {"GOOD": sign}, {}) for pair in ANTONYMS for word, sign in zip(pair, (-1, 1))]
    records += [
        ("bad", "adj", {"GOOD": -1}, {}),
        ("very", "adv", {"INTENSITY": 1}, {"INTENSITY": 1}),
        ("extremely", "adv", {"INTENSITY": 1}, {"INTENSITY": 2}),
    ]
    for word, pos, values, hierarchy in records:
        entry_id = f"fixture:{word}"
        assertions = tuple(Assertion(bank, value, "fixture", entry_id, "mechanism") for bank, value in values.items())
        store_entry(
            connection,
            Definition(entry_id, word, pos, "Synthetic sign-mechanism fixture"),
            propagate(("GOOD", "INTENSITY"), assertions, ()),
            assertions,
            hierarchy,
        )
    connection.commit()
    connection.close()
    with GSEEncoder(str(path)) as enc:
        yield enc


def same(a, b):
    return np.array_equal(a.to_dense(), b.to_dense())


def absorbed_adjective(encoder, text):
    """Project the actual phrase vector to its fixture's sole evaluative axis.

    Shared grammatical and intensifier components are not an antonym sign.
    The separate sentence tests retain the original unprojected comparisons.
    """
    trace = encoder.encode(text)
    word = [token for token in trace.tokens if token.pos != "PUNCT"][-1]
    return word, trace.vector.with_bank_only(SemanticBank.EVALUATORS)


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
    neg_target, neg = absorbed_adjective(encoder, f"{intensifier} {negative}")
    pos_target, pos = absorbed_adjective(encoder, f"{intensifier} {positive}")
    level = {"very": 1, "extremely": 2}[intensifier]
    for target, sign in ((neg_target, -1), (pos_target, 1)):
        assert target.degree == {"scale": "INTENSITY", "level": level, "sources": [0]}
        assert target.word_primitives == {"GOOD": sign}
        assert target.word_vec_nnz > 0
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
    strict = GSEEncoder(encoder.db_path, strict=True)
    try:
        with pytest.raises(PrimitiveError):
            strict._encode_word_primitives(word)
    finally:
        strict.close()
    assert same(encoder._encode_word_primitives(word), encoder._encode_word_primitives({"GOOD": 1, "HIER_PLUS": 1}))
