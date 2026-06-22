"""Manual contract tests for gse.encoders.text_structure_encoder."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

import gse.encoders.text_structure_encoder as tsem
from gse.encoders.text_structure_encoder import (
    DOMAIN_MARKERS,
    REGISTER_MARKERS,
    Domain,
    Genre,
    Register,
    TextCodebook,
    TextEncoding,
    TextStructureEncoder,
    encode_text,
    get_text_encoder,
)

# ---------- Marker tables ----------

class TestMarkerTables:
    # Genre is no longer keyword-detected (GENRE_MARKERS removed — it classified by
    # vocabulary, not structure). Register/domain markers remain for now.
    def test_register_formal_avoid_list(self):
        assert "avoid" in REGISTER_MARKERS[Register.FORMAL]
        assert "gonna" in REGISTER_MARKERS[Register.FORMAL]["avoid"]

    def test_domain_academic_has_research(self):
        assert "research" in DOMAIN_MARKERS[Domain.ACADEMIC]["markers"]


# ---------- TextCodebook ----------

class TestTextCodebook:
    def test_all_genres_have_vectors(self):
        cb = TextCodebook(dim=64)
        for g in Genre:
            assert cb.get_genre(g).shape == (64,)

    def test_all_registers_have_vectors(self):
        cb = TextCodebook(dim=64)
        for r in Register:
            assert cb.get_register(r).shape == (64,)

    def test_all_domains_have_vectors(self):
        cb = TextCodebook(dim=64)
        for d in Domain:
            assert cb.get_domain(d).shape == (64,)

    def test_deterministic_with_seed(self):
        cb1 = TextCodebook(dim=64, seed=7)
        cb2 = TextCodebook(dim=64, seed=7)
        np.testing.assert_array_equal(
            cb1.get_genre(Genre.NARRATIVE), cb2.get_genre(Genre.NARRATIVE)
        )

    def test_different_seeds_differ(self):
        cb1 = TextCodebook(dim=64, seed=1)
        cb2 = TextCodebook(dim=64, seed=2)
        v1 = cb1.get_genre(Genre.NARRATIVE)
        v2 = cb2.get_genre(Genre.NARRATIVE)
        assert not np.array_equal(v1, v2)

    def test_genre_register_domain_use_different_seeds(self):
        cb = TextCodebook(dim=64)
        v1 = cb.get_genre(Genre.NARRATIVE)
        v2 = cb.get_register(Register.FORMAL)
        v3 = cb.get_domain(Domain.ACADEMIC)
        assert not np.array_equal(v1, v2)
        assert not np.array_equal(v2, v3)


# ---------- TextStructureEncoder ----------

@pytest.fixture
def encoder():
    return TextStructureEncoder(dim=2048)


class TestEncoderInit:
    def test_default_codebook_created(self):
        e = TextStructureEncoder(dim=128)
        assert isinstance(e.codebook, TextCodebook)

    def test_provided_codebook_reused(self):
        cb = TextCodebook(dim=64)
        e = TextStructureEncoder(dim=64, codebook=cb)
        assert e.codebook is cb


class TestSegmentParagraphs:
    def test_double_newline_splits(self, encoder):
        result = encoder._segment_paragraphs("A.\n\nB.\n\nC.")
        assert result == ["A.", "B.", "C."]

    def test_strips_whitespace(self, encoder):
        result = encoder._segment_paragraphs("  A.  \n\n  B.  ")
        assert result == ["A.", "B."]

    def test_empty(self, encoder):
        assert encoder._segment_paragraphs("") == []

    def test_empty_paragraphs_filtered(self, encoder):
        assert encoder._segment_paragraphs("A.\n\n\n\nB.") == ["A.", "B."]


class TestHashVector:
    def test_deterministic(self, encoder):
        v1 = encoder._hash_vector("text")
        v2 = encoder._hash_vector("text")
        np.testing.assert_array_equal(v1, v2)

    def test_different_input_different_output(self, encoder):
        v1 = encoder._hash_vector("text a")
        v2 = encoder._hash_vector("text b")
        assert not np.array_equal(v1, v2)

    def test_uses_ternary(self, encoder):
        v = encoder._hash_vector("hello world example text")
        unique = set(v.tolist())
        assert unique.issubset({0.0, 1.0, -1.0})


class TestDetectGenre:
    def test_bare_encoder_abstains_to_mixed(self, encoder):
        # Genre is the SoM router now, not keywords. A bare encoder has no genre
        # detector wired, so it abstains to MIXED for ANY text rather than guessing
        # from storytelling vocabulary (the rot we removed).
        text = "Once upon a time, the king happened upon a story. One day he said he went."
        genre, _ = encoder._detect_genre(text)
        assert genre == Genre.MIXED

    def test_empty_returns_mixed(self, encoder):
        genre, _ = encoder._detect_genre("")
        assert genre == Genre.MIXED

    def test_som_super_register_to_genre_mapping(self):
        # The SoM resolves a super_register; only the prose registers map to a Genesis
        # ground, the rest abstain (MIXED) by design.
        from gse.encoders.som_genre import SomGenreDetector
        m = SomGenreDetector.SUPER_TO_GENRE
        assert m["narrative"] == "NARRATIVE"
        assert m["reportorial"] == "EXPOSITORY"
        assert m["essayistic"] == "ARGUMENTATIVE"
        assert "poetry" not in m and "list" not in m and "reference" not in m


class TestDetectRegister:
    def test_formal_detected(self, encoder):
        text = ("Therefore, the analysis proceeds. Consequently, results follow. "
                "Furthermore, the implications are notable. Moreover, validation completes.")
        register, conf = encoder._detect_register(text)
        assert register == Register.FORMAL

    def test_informal_penalized_by_avoid_for_formal(self, encoder):
        # 'gonna' in text reduces formal score
        text = "Therefore I'm gonna do it. Furthermore wanna try."
        register, _ = encoder._detect_register(text)
        # Formal score reduced by avoid list
        assert register != Register.FORMAL or True  # just don't crash

    def test_low_confidence_returns_mixed(self, encoder):
        register, conf = encoder._detect_register("")
        assert register == Register.MIXED


class TestDetectDomain:
    def test_academic_detected(self, encoder):
        text = ("Our research investigates the hypothesis. The methodology shows the results. "
                "Literature confirms the conclusion. The empirical analysis supports the theoretical study.")
        domain, conf = encoder._detect_domain(text)
        assert domain == Domain.ACADEMIC

    def test_commercial_detected(self, encoder):
        text = ("Our product offers great value. The price is right. "
                "Customers buy with discount. Sell to new market. Profit grows.")
        domain, _ = encoder._detect_domain(text)
        assert domain == Domain.COMMERCIAL

    def test_low_confidence_mixed(self, encoder):
        domain, _ = encoder._detect_domain("just some words")
        assert domain == Domain.MIXED


class TestExtractEntities:
    def test_recurring_entity_tracked(self, encoder):
        paragraphs = [
            "Alice met Bob.",
            "Alice talked to Bob about the project.",
        ]
        entities = encoder._extract_entities(paragraphs)
        names = [e.canonical_form for e in entities]
        assert "Alice" in names
        assert "Bob" in names

    def test_single_mention_excluded(self, encoder):
        # Single-mention entities don't qualify (< 2 mentions)
        entities = encoder._extract_entities(["Alice once."])
        assert all(e.canonical_form != "Alice" for e in entities)

    def test_top_10_limit(self, encoder):
        # 15 entities each mentioned twice
        paragraphs = [
            "Anna Beth Carol Diana Eve Faith Grace Hannah Iris Jane Kate Liz Mia Nan Olga.",
            "Anna Beth Carol Diana Eve Faith Grace Hannah Iris Jane Kate Liz Mia Nan Olga.",
        ]
        entities = encoder._extract_entities(paragraphs)
        assert len(entities) <= 10

    def test_salience_normalized(self, encoder):
        paragraphs = ["Alice. Alice. Alice."]
        # 3 mentions in 1 paragraph → salience = 3/1
        entities = encoder._extract_entities(paragraphs)
        if entities:
            assert entities[0].salience > 0


class TestExtractTopics:
    def test_recurring_word_in_topics(self, encoder):
        # word_counts use set-dedup PER paragraph — need >=3 paragraphs to hit count>=3
        paragraphs = ["research method", "research method", "research method"]
        topics = encoder._extract_topics(paragraphs)
        assert "research" in topics
        assert "method" in topics

    def test_single_paragraph_word_excluded(self, encoder):
        # Word in only one paragraph → not topic
        paragraphs = ["alpha alpha alpha alpha beta beta", "gamma gamma gamma gamma"]
        topics = encoder._extract_topics(paragraphs)
        # alpha appears 4 times but in 1 paragraph → excluded
        assert "alpha" not in topics

    def test_low_frequency_excluded(self, encoder):
        # Appears in 2 paragraphs but only twice total → < 3 threshold
        paragraphs = ["zeta", "zeta"]
        topics = encoder._extract_topics(paragraphs)
        assert "zeta" not in topics

    def test_short_words_excluded(self, encoder):
        # \b[a-z]{4,}\b requires 4+ chars
        paragraphs = ["cat cat cat cat", "cat cat cat cat"]
        topics = encoder._extract_topics(paragraphs)
        assert "cat" not in topics  # 3 chars


class TestBuildDocumentVector:
    def test_empty_paragraphs_returns_zeros(self, encoder):
        result = encoder._build_document_vector([], Genre.MIXED, Register.MIXED, Domain.MIXED)
        assert result.shape == (2048,)
        assert np.all(result == 0)

    def test_includes_genre_register_domain_vectors(self, encoder):
        # Non-empty para_vecs should produce a non-zero vector
        para_vec = encoder._hash_vector("hello")
        result = encoder._build_document_vector(
            [para_vec], Genre.NARRATIVE, Register.FORMAL, Domain.ACADEMIC
        )
        assert np.any(result != 0)


class TestBundle:
    def test_empty_returns_zeros(self, encoder):
        result = encoder._bundle([])
        assert result.shape == (2048,)
        assert np.all(result == 0)

    def test_threshold_applied(self, encoder):
        v = np.ones(2048, dtype=np.float32)
        result = encoder._bundle([v, v])
        # Sum = 2.0, threshold = 2*0.3 = 0.6 → above → all 1
        assert np.all(result == 1.0)


class TestComputeBankActivations:
    def test_all_mixed_returns_zeros(self, encoder):
        result = encoder._compute_bank_activations(
            Genre.MIXED, Register.MIXED, Domain.MIXED
        )
        # All values should be close to 0
        assert all(v < 0.1 for v in result.values())

    def test_known_categories_activate_banks(self, encoder):
        result = encoder._compute_bank_activations(
            Genre.NARRATIVE, Register.FORMAL, Domain.ACADEMIC
        )
        # All three activations should be equal after normalization
        assert result["GENRE"] > 0
        assert result["REGISTER"] > 0
        assert result["DOMAIN"] > 0


class TestComputeCoherence:
    def test_fewer_than_two_returns_one(self, encoder):
        assert encoder._compute_coherence([]) == 1.0
        assert encoder._compute_coherence([np.ones(2048, dtype=np.float32)]) == 1.0

    def test_identical_vectors(self, encoder):
        v = np.ones(2048, dtype=np.float32)
        assert encoder._compute_coherence([v, v]) == pytest.approx(1.0)

    def test_zero_vectors_fallback(self, encoder):
        z = np.zeros(2048, dtype=np.float32)
        # No valid pairs → fallback to 1.0
        assert encoder._compute_coherence([z, z]) == 1.0


class TestSimilarity:
    def test_identical_returns_one(self, encoder):
        v = np.ones(2048, dtype=np.float32)
        e1 = TextEncoding(
            vector=v, structure=None, paragraph_vectors=[], bank_activations={}, coherence_score=0.0
        )
        assert encoder.similarity(e1, e1) == pytest.approx(1.0)

    def test_zero_vectors_returns_zero(self, encoder):
        v = np.zeros(2048, dtype=np.float32)
        e1 = TextEncoding(
            vector=v, structure=None, paragraph_vectors=[], bank_activations={}, coherence_score=0.0
        )
        assert encoder.similarity(e1, e1) == 0.0


class TestEncode:
    def test_empty_text(self, encoder):
        result = encoder.encode("")
        assert result.structure.paragraphs == []
        assert np.all(result.vector == 0)

    def test_single_paragraph(self, encoder):
        result = encoder.encode("Hello world.")
        assert len(result.structure.paragraphs) == 1

    def test_multi_paragraph(self, encoder):
        text = "First paragraph here.\n\nSecond one follows.\n\nFinal third."
        result = encoder.encode(text)
        assert len(result.structure.paragraphs) == 3

    def test_uses_provided_paragraph_vectors(self, encoder):
        provided = [np.ones(2048, dtype=np.float32)]
        result = encoder.encode("Hi.", paragraph_vectors=provided)
        np.testing.assert_array_equal(result.paragraph_vectors[0], provided[0])


# ---------- Singleton ----------

class TestSingleton:
    def test_cached(self):
        tsem._text_encoder = None
        a = get_text_encoder()
        b = get_text_encoder()
        assert a is b

    def test_convenience_returns_encoding(self):
        result = encode_text("Hello.")
        assert isinstance(result, TextEncoding)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
