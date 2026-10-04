import numpy as np
import pytest
from gse.coherence import CoherenceChecker
from gse.composer import Composer
from gse.lexicon_generator import LexiconEntry
from gse.parser import Parser
from gse.primitives import PRIMITIVES, ROLES
from gse.vectors import D, PrimitiveBasis, SparseVector


class SmartMockLexicon:
    def __init__(self, basis):
        self.basis = basis
        self.entries = {}

    def lookup(self, lemma, pos):
        if (lemma, pos) not in self.entries:
             self._create_entry(lemma, pos)
        return self.entries[(lemma, pos)]

    def _create_entry(self, lemma, pos):
        # Default random vector
        dimension = self.basis.dimension
        nnz = 800  # Adjusted for D=8192

        # Create dense array first to manipulate
        dense = np.zeros(dimension, dtype=np.int8)

        # Randomly fill rest
        seed = abs(hash(lemma))
        rng = np.random.default_rng(seed)
        indices = rng.choice(dimension, nnz, replace=False)
        mid = nnz // 2
        dense[indices[:mid]] = 1
        dense[indices[mid:]] = -1

        # Specific semantic adjustments for anomalies
        if lemma == "rock":
            # Inanimate: negative signal in 0-100
            # Set indices 0-50 to -1
            dense[0:50] = -1
            dense[50:100] = 0 # Clear others

        elif lemma in ["dog", "john", "mary", "committee"]:
            # Animate: positive signal
            dense[0:50] = 1
            dense[50:100] = 0

        elif lemma in ["book", "proposal", "idea"]:
            # Abstract/Inanimate
            dense[0:50] = -1

        vec = SparseVector.from_dense(dense)

        entry = LexiconEntry(
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
        self.entries[(lemma, pos)] = entry

@pytest.fixture
def checker():
    return CoherenceChecker(dimension=D)

@pytest.fixture
def composer():
    basis = PrimitiveBasis.generate(PRIMITIVES, ROLES)
    lexicon = SmartMockLexicon(basis)
    return Composer(lexicon, basis)

@pytest.fixture
def parser():
    return Parser()

def test_check_animacy_violation(checker, composer, parser):
    # "The rock thinks." -> rock is agent of thinks.
    # Rock is inanimate. Thinks implies agent.
    # Note: CoherenceChecker checks generic agent animacy, assuming all agents should be animate?
    # Or does it check verb requirements?
    # The implementation:
    # _check_agent_animacy checks agent_vec[animacy_dims].
    # It assumes ALL agents should have positive animacy logic in the 0-100 range?
    # Or is it checking verb compatibility?
    # The code: `_check_agent_animacy(self, composition, parsed)`
    # It finds "agent" role.
    # Then checks agent vector.
    # It does NOT check the verb vector.
    # So it enforces that ANY agent must be animate.
    # This is a simplification but works for "The rock thinks".
    # It would also fail "The car moved" if car is inanimate.

    text = "The rock thinks."
    parsed = parser.parse_single(text)
    comp = composer.compose(parsed)

    # We need to ensure "rock" was identified as agent.
    # "The rock thinks." -> rock (nsubj) -> agent.

    res = checker.check(comp, parsed)

    # Expect failure on animacy
    assert any("animacy" in a for a in res.anomalies)
    # Score should be impacted (with 6 coherence checks, one failure gives ~0.83)
    assert res.score < 0.9  # Some threshold

def test_check_valid_agent(checker, composer, parser):
    text = "The dog runs."
    parsed = parser.parse_single(text)
    comp = composer.compose(parsed)

    res = checker.check(comp, parsed)

    # Should not have animacy violation
    assert not any("animacy" in a for a in res.anomalies)

def test_check_completeness(checker, composer, parser):
    # "runs." (No subject)
    # Imperative? Or just fragment.
    # "runs" is main verb.
    text = "Run."
    parsed = parser.parse_single(text)
    comp = composer.compose(parsed)

    res = checker.check(comp, parsed)

    assert any("Missing" in a for a in res.anomalies)

def test_high_coherence_passed(checker, composer, parser):
    text = "John loves Mary."
    parsed = parser.parse_single(text)
    comp = composer.compose(parsed)

    res = checker.check(comp, parsed)
    assert res.passed
    assert len(res.anomalies) == 0

