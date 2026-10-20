"""Word-scale negation — the morphology-as-operation slice for negation prefixes
(``docs/MORPHOLOGY_RESEARCH_BRIEF.md`` Part B/D; vision §IV-D ``dislike = NOT(like)``).

Two faces of one operation, each tested at its own layer:

* **HDC** — :func:`negate_decomposition` flips ONLY the bipolar evaluative poles
  (GOOD/BAD …), preserving unipolar/intensity primes. Not the blanket vector negate.
* **symbolic** — :func:`resolve_negation` recognizes a negation prefix and grounds
  the base (``unkind``→``(kind, NEGATION)``), the grounding gate rejecting false
  prefixes (``uncle``/``income``/``internal``).
* **encoder** — compute-and-override makes ``encode(un-X)`` == ``negate(X)``.
"""

import pytest

from gse.api.encoder import GSEEncoder
from gse.nlp.morphology import NEGATION, REVERSAL, resolve_negation
from gse.primitives_v2 import negate_decomposition

# --- Piece 1: selective bipolar negate ------------------------------------------


@pytest.mark.parametrize(
    "decomp,expected",
    [
        # bipolar pole flips, canonicalized to the positive pole
        ({"GOOD": 1}, {"GOOD": -1}),
        ({"GOOD": -1}, {"GOOD": 1}),
        ({"BAD": 1}, {"GOOD": 1}),  # bad = GOOD:-1 → flip → GOOD:+1 (dual convention)
        ({"BIG": 1}, {"BIG": -1}),
        # unipolar primes preserved; only the bipolar pole moves
        ({"GOOD": 1, "SOMETHING": 1}, {"GOOD": -1, "SOMETHING": 1}),  # ≈ kind → unkind
        ({"FEEL": 1, "GOOD": 1}, {"FEEL": 1, "GOOD": -1}),  # ≈ happy → unhappy
        # purely unipolar decomposition is unchanged (nothing evaluative to flip)
        ({"DO": 1, "SOMETHING": 1}, {"DO": 1, "SOMETHING": 1}),
        ({}, {}),
    ],
)
def test_negate_decomposition_flips_only_bipolar(decomp, expected):
    assert negate_decomposition(decomp) == expected


def test_negate_is_an_involution_on_bipolar():
    for d in ({"GOOD": 1}, {"FEEL": 1, "GOOD": 1}, {"BIG": -1, "ALIVE": 1}):
        assert negate_decomposition(negate_decomposition(d)) == d


# --- Piece 2: the negation-prefix operation -------------------------------------


@pytest.mark.parametrize(
    "surface,base",
    [
        ("unkind", "kind"),
        ("unhappy", "happy"),
        ("impossible", "possible"),
        ("illegal", "legal"),
        ("irregular", "regular"),
        ("disloyal", "loyal"),
        ("insane", "sane"),
        ("dislike", "like"),
    ],
)
def test_negation_prefix_grounds_to_adjective(surface, base):
    assert resolve_negation(surface) == (base, NEGATION)


@pytest.mark.parametrize(
    "surface,base",
    [
        ("unlock", "lock"),
        ("untie", "tie"),
        ("disconnect", "connect"),
    ],
)
def test_un_dis_plus_verb_is_reversal(surface, base):
    assert resolve_negation(surface) == (base, REVERSAL)


@pytest.mark.parametrize(
    "surface",
    [
        "uncle",  # → cle, grounds as nothing
        "income",  # → come is a verb, but in- is negation-only (no reversal)
        "internal",  # → ternal, grounds as nothing
        "dish",  # dis- can't strip (base too short) → no grounded base
    ],
)
def test_false_prefixes_decline(surface):
    assert resolve_negation(surface) is None


def test_known_lexical_surface_never_licenses_a_false_prefix(enc):
    """The old under->der proposal is now refused before encoder admission."""
    assert resolve_negation("under") is None
    base, _, _ = enc._lookup_lexeme("der")
    assert not base
    got = [t.word_primitives for t in enc.encode("under").tokens if t.word_primitives]
    assert got == []


# --- Piece 3: encoder compute-and-override (un-X == negate(X)) -------------------


@pytest.fixture(scope="module")
def enc():
    return GSEEncoder()


@pytest.mark.parametrize(
    "negated,base",
    [
        ("unhappy", "happy"),
        ("unkind", "kind"),
    ],
)
def test_encoder_negation_equals_negated_base(enc, negated, base):
    """The negated form's word-primitives ARE the sign-flipped base's — the
    representational collapse, not a separate stored ``un-`` row."""
    base_prims, _, _ = enc._lookup_lexeme(base)
    expected = negate_decomposition(base_prims)

    r = enc.encode(negated)
    got = next(t.word_primitives for t in r.tokens if t.word_primitives)
    assert got == expected


def test_encoder_concrete_values(enc):
    """Pin the exact decompositions so a lexicon regression on the base surfaces here."""
    assert next(t.word_primitives for t in enc.encode("unhappy").tokens if t.word_primitives) == {"FEEL": 1, "GOOD": -1}
    assert next(t.word_primitives for t in enc.encode("unkind").tokens if t.word_primitives) == {
        "GOOD": -1,
        "SOMETHING": 1,
    }
    # the base itself is untouched (no spurious negation of a non-prefixed word)
    assert next(t.word_primitives for t in enc.encode("happy").tokens if t.word_primitives) == {"FEEL": 1, "GOOD": 1}
