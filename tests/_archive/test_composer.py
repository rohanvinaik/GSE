import pytest
from gse.composer import Composer
from gse.lexicon_generator import LexiconEntry
from gse.primitives import PRIMITIVES, ROLES
from gse.vectors import PrimitiveBasis, SparseVector

from gse.parser import Parser


class MockLexicon:
    def __init__(self, basis):
        self.basis = basis
        self.entries = {}
        # Pre-populate some common words
        self._add_word("dog", "NOUN")
        self._add_word("cat", "NOUN")
        self._add_word("run", "VERB")
        self._add_word("sleep", "VERB")
        self._add_word("chase", "VERB")
        self._add_word("big", "ADJ")
        self._add_word("quick", "ADV")
        self._add_word("john", "NOUN") # Proper noun
        self._add_word("mary", "NOUN")
        self._add_word("love", "VERB")
        self._add_word("book", "NOUN")
        self._add_word("give", "VERB")
        self._add_word("fox", "NOUN")
        self._add_word("jump", "VERB")
        self._add_word("brown", "ADJ")
        self._add_word("fast", "ADV")
        # Add 'the' just in case, though usually stopwords
        self._add_word("the", "DET")
        self._add_word("a", "DET")

    def _add_word(self, lemma, pos):
        # Generate random vector (nnz adjusted for D=8192)
        vec = SparseVector.random(self.basis.dimension, 400, seed=abs(hash(lemma)))
        self.entries[(lemma, pos)] = LexiconEntry(
            lemma=lemma,
            pos=pos,
            sense_id=f"{lemma}.01",
            gloss="mock",
            decomposition=[],
            vector=vec,
            frequency=1.0,
            source="mock",
            confidence=1.0
        )

    def lookup(self, lemma, pos):
        # normalize POS
        # If proper noun, maybe mapped to NOUN
        if pos == "PROPN": pos = "NOUN"
        return self.entries.get((lemma, pos))

@pytest.fixture
def composer(tmp_path):
    # Create basis using new Hadamard-OTP architecture
    basis = PrimitiveBasis.generate(PRIMITIVES, ROLES)

    lexicon = MockLexicon(basis)

    return Composer(lexicon, basis)

def test_simple_sentence_composition(composer):
    parser = Parser()
    parsed = parser.parse_single("The dog runs.")
    result = composer.compose(parsed)

    assert result.sentence_vector is not None
    # confidence relies on lexicon lookup. "The" might be missing if DET is not in MockLexicon or if skipped.
    # "dog" and "runs" (run) are in MockLexicon.
    assert result.confidence > 0
    assert result.merkle_root != ""

def test_transitive_sentence(composer):
    parser = Parser()
    parsed = parser.parse_single("John loves Mary.")
    result = composer.compose(parsed)

    # Should have sense selections for content words
    # John, loves(love), Mary
    assert len(result.sense_selections) >= 3

def test_composition_determinism(composer):
    parser = Parser()
    parsed = parser.parse_single("The quick brown fox jumps.")

    result1 = composer.compose(parsed)
    result2 = composer.compose(parsed)

    # Same input should produce same output
    assert result1.merkle_root == result2.merkle_root
    assert result1.sentence_vector.cosine(result2.sentence_vector) == pytest.approx(1.0)

def test_different_sentences_different_vectors(composer):
    parser = Parser()

    result1 = composer.compose(parser.parse_single("The dog runs."))
    result2 = composer.compose(parser.parse_single("The cat sleeps."))

    # Different sentences should have different vectors
    similarity = result1.sentence_vector.cosine(result2.sentence_vector)
    assert similarity < 0.9  # Not identical

def test_similar_sentences_similar_vectors(composer):
    parser = Parser()

    # "run" vs "runs" -> lemma "run".
    # "quickly" vs "fast".
    # We need "quickly" in mock lexicon? I added "quick" and "fast".
    # Spacy lemmatizes "quickly" -> "quickly"? Or "quick"?
    # Usually "quickly" -> "quickly".
    # So I should add "quickly" to MockLexicon if I want it to be found.
    # But checking equality: if "quickly" is unknown, it gets fallback (random deterministic).
    # If "fast" is known/unknown.

    result1 = composer.compose(parser.parse_single("The dog runs quickly."))
    result2 = composer.compose(parser.parse_single("The dog runs fast."))

    # Similar sentences should have similar vectors
    # Vectors will be bundle(dog + run + quickly) vs bundle(dog + run + fast)
    # They share dog and run components.
    # So similarity should be decent.
    similarity = result1.sentence_vector.cosine(result2.sentence_vector)
    assert similarity > 0.4  # Reasonably similar (0.5 might be optimistic for random vectors)
