"""
Comprehensive tests for multi-scale GSE encoding.
Tests designed around user's cognitive patterns.
"""

import hashlib
import sys
from pathlib import Path

import pytest
import torch

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))

from gse.encoders.conversation_encoder import ConversationEncoder, ConversationGoal
from gse.encoders.paragraph_encoder import CoherenceRelation, ParagraphEncoder
from gse.encoders.sentence_encoder import EmotionalRegister, Modality, RhetoricalFunction, SentenceEncoder


class MockEncoder:
    """Mock word encoder for testing."""
    def encode(self, text):
        seed = int(hashlib.md5(text.lower().encode()).hexdigest()[:8], 16)
        torch.manual_seed(seed)
        vec = torch.zeros(8192)
        rand = torch.rand(8192)
        vec[rand < 0.33] = 1.0
        vec[rand > 0.67] = -1.0
        return {"hdc_vector": vec}


@pytest.fixture
def sentence_encoder():
    return SentenceEncoder(MockEncoder())


@pytest.fixture
def paragraph_encoder(sentence_encoder):
    return ParagraphEncoder(sentence_encoder)


@pytest.fixture
def conversation_encoder(paragraph_encoder):
    return ConversationEncoder(paragraph_encoder)


class TestSentenceEncoder:
    """Tests for sentence-level encoding."""

    def test_role_binding(self, sentence_encoder):
        """'Cat chased dog' should differ from 'Dog chased cat'."""
        enc1 = sentence_encoder.encode("The cat chased the dog.")
        enc2 = sentence_encoder.encode("The dog chased the cat.")
        sim = sentence_encoder.similarity(enc1, enc2)
        # Should have some similarity (same verb) but not high
        assert 0.1 < sim < 0.8, f"Expected moderate similarity, got {sim}"

    def test_negation(self, sentence_encoder):
        """Negated sentences should have low similarity to affirmative."""
        enc1 = sentence_encoder.encode("The cat chased the dog.")
        enc2 = sentence_encoder.encode("The cat didn't chase the dog.")
        sim = sentence_encoder.similarity(enc1, enc2)
        assert sim < 0.3, f"Expected low similarity for negation, got {sim}"

    def test_rhetorical_question_detection(self, sentence_encoder):
        """Should detect rhetorical questions."""
        enc = sentence_encoder.encode("What exactly did you all think you'd accomplish???")
        assert enc.structure.modality == Modality.RHETORICAL_QUESTION

    def test_sarcasm_detection(self, sentence_encoder):
        """Should detect sarcasm markers."""
        enc = sentence_encoder.encode("Well, congratulations on your brilliant discovery.")
        assert enc.structure.emotional_register == EmotionalRegister.IRONIC

    def test_analogy_detection(self, sentence_encoder):
        """Should detect analogies."""
        enc = sentence_encoder.encode("It's like the structural meaning is a hologram.")
        assert enc.structure.has_analogy == True
        assert enc.structure.rhetorical_function == RhetoricalFunction.ANALOGY

    def test_intensity_scoring(self, sentence_encoder):
        """Should score intensity correctly."""
        enc_low = sentence_encoder.encode("The weather is nice today.")
        enc_high = sentence_encoder.encode("This is absolutely FUCKING ridiculous!!")
        assert enc_high.structure.intensity_score > enc_low.structure.intensity_score

    def test_meta_commentary(self, sentence_encoder):
        """Should detect meta-commentary."""
        enc = sentence_encoder.encode("What I mean is, the thing is really about structure.")
        assert enc.structure.has_meta_commentary == True


class TestParagraphEncoder:
    """Tests for paragraph-level encoding."""

    def test_coherence_detection(self, paragraph_encoder):
        """Should detect coherence relations."""
        para = "HDC uses high-dimensional vectors. Therefore, it's robust to noise."
        enc = paragraph_encoder.encode(para)
        relations = [r[2] for r in enc.structure.relations]
        assert CoherenceRelation.RESULT in relations

    def test_gestalt_detection(self, paragraph_encoder):
        """Should detect gestalt crystallization points."""
        para = """
        The core insight is this: meaning is relational, not content-based.
        Think of it like a hologram. Each piece contains the whole.
        """
        enc = paragraph_encoder.encode(para)
        assert len(enc.structure.gestalt_points) > 0

    def test_intensity_trajectory(self, paragraph_encoder):
        """Should track intensity across paragraph."""
        para = """
        Let me explain calmly. THIS IS IMPORTANT.
        Actually, it's absolutely CRITICAL. WE CANNOT IGNORE THIS!!!!
        """
        enc = paragraph_encoder.encode(para)
        print(f"\nIntensity values: {enc.structure.intensity_trajectory.values}")
        print(f"Trajectory type: {enc.structure.intensity_trajectory.trajectory_type}")
        assert enc.structure.intensity_trajectory is not None
        assert enc.structure.intensity_trajectory.trajectory_type == "building"

    def test_main_claim_identification(self, paragraph_encoder):
        """Should identify main claim."""
        para = """
        Here's an example. Consider how music works.
        The fundamental truth is that patterns matter more than notes.
        Specifically, rhythm creates meaning.
        """
        enc = paragraph_encoder.encode(para)
        # Main claim should be the "fundamental truth" sentence
        main_sent = enc.structure.sentences[enc.structure.main_claim_idx]
        assert "fundamental" in main_sent.lower() or "truth" in main_sent.lower()


class TestConversationEncoder:
    """Tests for conversation-level encoding."""

    def test_goal_detection(self, conversation_encoder):
        """Should detect conversation goal."""
        question_turns = [
            {"speaker": "user", "content": "What is the capital of France?"},
        ]
        enc = conversation_encoder.encode(question_turns)
        assert enc.structure.goal == ConversationGoal.INFORMATION_SEEKING

        task_turns = [
            {"speaker": "user", "content": "Please implement a sorting algorithm."},
        ]
        enc = conversation_encoder.encode(task_turns)
        assert enc.structure.goal == ConversationGoal.TASK_COMPLETION

    def test_resolution_detection(self, conversation_encoder):
        """Should detect resolution status."""
        resolved = [
            {"speaker": "user", "content": "How do I sort a list?"},
            {"speaker": "assistant", "content": "Use the sorted() function."},
            {"speaker": "user", "content": "Thanks, that worked!"},
        ]
        enc = conversation_encoder.encode(resolved)
        assert enc.structure.resolution_status == "resolved"

    def test_gestalt_emergence(self, conversation_encoder):
        """Should detect gestalt emergence points."""
        conv = [
            {"speaker": "user", "content": "I'm trying to articulate something. It's like there's this shape I can feel."},
            {"speaker": "assistant", "content": "Tell me more about that feeling."},
            {"speaker": "user", "content": "It's hard to explain. The pattern is becoming clearer now."},
        ]
        enc = conversation_encoder.encode(conv)
        assert len(enc.structure.gestalt_emergence_points) > 0

    def test_meta_reflection(self, conversation_encoder):
        """Should detect meta-reflection turns."""
        conv = [
            {"speaker": "user", "content": "I'm thinking about how I think about this problem."},
            {"speaker": "assistant", "content": "That's a meta-cognitive observation."},
        ]
        enc = conversation_encoder.encode(conv)
        assert len(enc.structure.meta_reflection_points) > 0


class TestIntegration:
    """Integration tests for full pipeline."""

    def test_user_style_paragraph(self, paragraph_encoder):
        """Test with actual user writing style."""
        # From psa_letters.txt style
        para = """
        Well, congratulations. You did it. You and all the other 
        pseudo-intellectual elitist liberal cronies have successfully 
        torpedoed any hope we had. What exactly did you all think 
        you'd accomplish??? Do you really think this will help?
        """
        enc = paragraph_encoder.encode(para)

        # Should detect high intensity
        assert enc.structure.intensity_trajectory.peak_index >= 0

        # Should detect rhetorical questions
        rhet_funcs = [s.structure.rhetorical_function
                      for s in enc.structure.sentence_encodings]
        assert RhetoricalFunction.QUESTION in rhet_funcs

    def test_philosophical_paragraph(self, paragraph_encoder):
        """Test with philosophical writing style."""
        # From personal_gita style
        para = """
        The core insight is that nothing really exists and all 
        differentiation in reality is basically a hallucination. 
        It's like two parts of a pair of particles arguing about 
        whether or not they are energy. The answer doesn't matter 
        because they'll collapse back into non-coherence anyway.
        """
        enc = paragraph_encoder.encode(para)

        # Should detect analogy
        assert len(enc.structure.analogy_indices) > 0

        # Should identify philosophical claim as main
        assert enc.structure.main_claim_idx == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
