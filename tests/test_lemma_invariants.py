"""Word-scale lemma invariants.

Per ``sentence_architecture.md`` line 52:

    "The word-scale semantic meaning of 'ran' and 'run' are identical—both
    are a verb that refers to the act of running. Tense only matters in
    higher-order systems that encode different semantic dimensions (i.e.
    sentences)."
    ...
    "On the word scale, 'ran' and 'run' have a similarity of 1.0, as do
    'am' and 'was'."

These tests assert that:

1. The token-level ``word_primitives`` field is identical across
   inflected surface forms of the same lemma (the strict architecture
   contract — word-scale is lemma-keyed).
2. Word geometry remains equal for selected definitions, while progressive
   aspect is represented independently at sentence scale. No bundled cosine
   floor defines lexical identity.
"""

import numpy as np
import pytest

from GSE.api import GSEEncoder
from GSE.curation.external_sources.gse_closed_class import grammatical_entry_ids
from GSE.curation.lexicon_builder.engine import Assertion, propagate
from GSE.curation.lexicon_builder.evidence import Definition
from GSE.curation.lexicon_builder.storage import open_build, store_entry


@pytest.fixture(scope="module")
def encoder(tmp_path_factory):
    # Synthetic nonempty coordinates test the mechanism, not lexical gold.
    path = tmp_path_factory.mktemp("lemma-geometry") / "fixture.db"
    conn = open_build(path)
    entries = [
        (f"fixture:{word}", word, bank)
        for word, bank in (("run", "DO"), ("be", "SOMETHING"), ("big", "BIG"), ("know", "KNOW"), ("see", "SEE"))
    ]
    for form in ("be", "am", "was", "is", "were", "are"):
        entries.extend((entry, form, "SOMETHING") for entry in grammatical_entry_ids(form, "AUX"))
    try:
        for entry, word, bank in entries:
            assertions = (Assertion(bank, 1, "fixture", entry, "dictionary"),)
            store_entry(
                conn,
                Definition(entry, word, "v", "synthetic geometry fixture"),
                propagate((bank,), assertions, ()),
                assertions,
            )
        conn.commit()
    finally:
        conn.close()
    with GSEEncoder(path) as result:
        yield result


# Inflected forms whose lemma is the same English word. spaCy's
# lemmatizer is responsible for the normalization at encode time.
LEMMA_GROUPS = [
    # (group label, surface forms)
    ("run", ["run", "ran", "running", "runs"]),
    ("be", ["be", "am", "was", "is", "were", "are"]),
    ("big", ["big", "bigger", "biggest"]),
    ("know", ["know", "knew", "known", "knows"]),
    ("see", ["see", "saw", "seen", "sees"]),
]


class TestWordPrimitivesLemmaInvariant:
    """word_primitives dict must be identical across inflections."""

    @pytest.mark.parametrize("group_name,forms", LEMMA_GROUPS)
    def test_word_primitives_identical_within_lemma_group(self, encoder, group_name, forms):
        traces = [encoder.encode(form) for form in forms]
        # First form's word_primitives is the reference; every other
        # form must match it exactly.
        reference = traces[0].tokens[0].word_primitives
        assert reference, "Fixture must exercise nonempty word geometry"
        for form, trace in zip(forms[1:], traces[1:]):
            actual = trace.tokens[0].word_primitives
            assert actual == reference, (
                f"Lemma invariance violated: {forms[0]!r} and {form!r} "
                f"differ at word-scale (architecture says they should be "
                f"identical at the word lens)."
            )

    @pytest.mark.parametrize("group_name,forms", LEMMA_GROUPS)
    def test_all_forms_lemmatize_to_same_root(self, encoder, group_name, forms):
        # spaCy lemmatization is the mechanism behind the invariant;
        # if this fails, the word_primitives equality test will too.
        lemmas = [encoder.encode(form).tokens[0].lemma for form in forms]
        assert len(set(lemmas)) == 1, f"spaCy produced different lemmas for {forms!r}: {lemmas!r}"


class TestWordGeometryAndSentenceAspect:
    """Equal lexical geometry does not imply identical sentence geometry."""

    @pytest.mark.parametrize(
        "w1,w2",
        [
            ("ran", "run"),
            ("running", "run"),
            ("bigger", "big"),
            ("biggest", "big"),
            ("knew", "know"),
            ("known", "know"),
        ],
    )
    def test_inflected_vs_lemma_word_geometry_equal(self, encoder, w1, w2):
        tokens = [encoder.encode(word).tokens[0] for word in (w1, w2)]
        assert tokens[0].word_primitives == tokens[1].word_primitives != {}
        vectors = [encoder.encode_definition(token.lexical_evidence["selected_record"]["entry_id"]) for token in tokens]
        assert all(vector.nnz > 0 for vector in vectors)
        np.testing.assert_array_equal(vectors[0].to_dense(), vectors[1].to_dense())

    def test_progressive_aspect_changes_sentence_not_word(self, encoder):
        plain, progressive = encoder.encode("run"), encoder.encode("running")
        assert plain.tokens[0].word_primitives == progressive.tokens[0].word_primitives != {}
        assert "SYN_ASPECT_PROG" not in plain.tokens[0].sent_primitives
        assert progressive.tokens[0].sent_primitives["SYN_ASPECT_PROG"] == 1
        assert not np.array_equal(plain.vector.to_dense(), progressive.vector.to_dense())

    def test_missing_word_is_abstention_not_a_zero_assignment(self, encoder):
        token = encoder.encode("zxqvunknown").tokens[0]
        assert token.word_primitives == {}
        assert token.word_vec_nnz == 0
        assert token.lexical_evidence["selection_status"] == "NOT_FOUND"
        assert token.lexical_evidence["selected_record"] is None
        assert token.lexical_evidence.get("primitive_evidence", []) == []
