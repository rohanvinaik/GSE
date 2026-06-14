"""Manual contract tests for gse.teaching.feature_extractor."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.teaching.feature_extractor import (
    DISCOURSE_CUES,
    SYNTACTIC_PATTERNS,
    TEXT_INDICATORS,
    FeatureExtractor,
)

# ---------- Indicator tables ----------

class TestTextIndicators:
    def test_narrative_words(self):
        assert "once" in TEXT_INDICATORS["NARRATIVE"]
        assert "suddenly" in TEXT_INDICATORS["NARRATIVE"]

    def test_formal_words(self):
        assert "furthermore" in TEXT_INDICATORS["FORMAL"]

    def test_technical_words(self):
        assert "algorithm" in TEXT_INDICATORS["TECHNICAL"]


class TestDiscourseCues:
    def test_cause_cues(self):
        assert "because" in DISCOURSE_CUES["CAUSE"]

    def test_contrast_cues(self):
        assert "but" in DISCOURSE_CUES["CONTRAST"]


class TestSyntacticPatterns:
    def test_inter_pattern_starts_with_wh(self):
        # Pattern detects question-start words
        assert SYNTACTIC_PATTERNS["SYN_MOOD_INTER"].startswith("^")


# ---------- Fixtures ----------

@pytest.fixture
def extractor():
    return FeatureExtractor()


# ---------- extract_text_features ----------

class TestExtractTextFeatures:
    def test_narrative_text(self, extractor):
        text = "Once upon a time, suddenly meanwhile finally happened."
        features = extractor.extract_text_features(text)
        assert "NARRATIVE" in features

    def test_formal_punctuation(self, extractor):
        text = "Section one; section two: see notes—therefore."
        features = extractor.extract_text_features(text)
        # Semicolons, colons, em-dashes boost FORMAL
        assert features.get("FORMAL", 0) > 0

    def test_technical_from_numbers(self, extractor):
        # Many numbers → TECHNICAL boost
        text = "Run 1.0 2.0 3.5 4.7 5.2 6.8 process."
        features = extractor.extract_text_features(text)
        assert features.get("TECHNICAL", 0) > 0

    def test_long_sentences_formal(self, extractor):
        # avg sent length > 25 → FORMAL boost
        long_sent = "word " * 30 + "."
        features = extractor.extract_text_features(long_sent)
        assert features.get("FORMAL", 0) > 0

    def test_short_sentences_informal(self, extractor):
        # avg sent length < 10 → INFORMAL boost
        text = "Hi. Bye. Cool. Wow. Nope."
        features = extractor.extract_text_features(text)
        assert features.get("INFORMAL", 0) > 0

    def test_min_activation_filters(self, extractor):
        # Very large text with sparse markers — activation below threshold
        text = "word " * 10000 + " once."
        features = extractor.extract_text_features(text)
        # NARRATIVE activation = 1 / (10001/100) ≈ 0.01 < 0.1 → filtered
        assert "NARRATIVE" not in features


# ---------- extract_paragraph_features ----------

class TestExtractParagraphFeatures:
    def test_cue_at_start_stronger(self, extractor):
        para = "Therefore, we conclude."
        features = extractor.extract_paragraph_features(para)
        # "therefore" at start → RESULT 0.8
        assert features.get("RESULT", 0) >= 0.8

    def test_cue_in_middle(self, extractor):
        para = "We see that because of this, we conclude."
        features = extractor.extract_paragraph_features(para)
        # "because" in middle → CAUSE 0.4
        assert "CAUSE" in features

    def test_list_pattern_sequence(self, extractor):
        para = "1. First item\n2. Second item\n3. Third"
        features = extractor.extract_paragraph_features(para)
        assert features.get("SEQUENCE", 0) > 0

    def test_question_marks_elaboration(self, extractor):
        para = "What is going on?"
        features = extractor.extract_paragraph_features(para)
        assert features.get("ELABORATION", 0) > 0

    def test_short_paragraph_summary(self, extractor):
        para = "In conclusion, we are done."  # < 20 words + conclusion cue
        features = extractor.extract_paragraph_features(para)
        assert features.get("SUMMARY", 0) > 0

    def test_filters_below_min_activation(self, extractor):
        # Empty paragraph → no features
        features = extractor.extract_paragraph_features("")
        assert features == {}


# ---------- extract_sentence_features ----------

class TestExtractSentenceFeatures:
    def test_capitalized_first_word_subj(self, extractor):
        features = extractor.extract_sentence_features("Alice ran fast.")
        assert features.get("SYN_SUBJ", 0) >= 0.7

    def test_question_mood_inter(self, extractor):
        features = extractor.extract_sentence_features("What is going on?")
        assert features.get("SYN_MOOD_INTER", 0) == 1.0

    def test_past_tense(self, extractor):
        features = extractor.extract_sentence_features("She walked yesterday.")
        # 'walked' matches \w+ed
        assert features.get("SYN_TENSE_PAST", 0) > 0

    @pytest.mark.xfail(reason="Source bug: first_word[0] raises IndexError on empty input.")
    def test_empty_sentence_safe(self, extractor):
        features = extractor.extract_sentence_features("")
        assert isinstance(features, dict)

    def test_trace_enriches(self, extractor):
        sent = "alice runs."
        # Without trace
        without = extractor.extract_sentence_features(sent)
        # With trace providing SYN_SUBJ via role
        tok_trace = MagicMock()
        tok_trace.role = "SUBJECT"
        trace = MagicMock()
        trace.tokens = [tok_trace]
        with_trace = extractor.extract_sentence_features(sent, trace=trace)
        # Trace adds SYN_SUBJ
        assert with_trace.get("SYN_SUBJ", 0) == 1.0


# ---------- _extract_from_trace ----------

class TestExtractFromTrace:
    def test_subject_role(self, extractor):
        tok = MagicMock()
        tok.role = "SUBJECT"
        trace = MagicMock()
        trace.tokens = [tok]
        result = extractor._extract_from_trace(trace)
        assert result["SYN_SUBJ"] == 1.0

    def test_predicate_role(self, extractor):
        tok = MagicMock()
        tok.role = "PREDICATE"
        trace = MagicMock()
        trace.tokens = [tok]
        result = extractor._extract_from_trace(trace)
        assert result["SYN_PRED"] == 1.0

    def test_object_role(self, extractor):
        tok = MagicMock()
        tok.role = "OBJ"
        trace = MagicMock()
        trace.tokens = [tok]
        result = extractor._extract_from_trace(trace)
        assert result["SYN_OBJ"] == 1.0

    def test_no_tokens_attr(self, extractor):
        # Trace without 'tokens' attribute should not crash
        trace = object()  # no tokens attr
        result = extractor._extract_from_trace(trace)
        assert result == {}

    def test_unknown_role_ignored(self, extractor):
        tok = MagicMock()
        tok.role = "WHATEVER"
        trace = MagicMock()
        trace.tokens = [tok]
        result = extractor._extract_from_trace(trace)
        assert result == {}


# ---------- extract_word_features ----------

class TestExtractWordFeatures:
    def test_known_primitive(self, extractor):
        features = extractor.extract_word_features("happy", {"GOOD": 1, "FEEL": 1})
        assert features["GOOD"] == 1.0
        assert features["FEEL"] == 1.0

    def test_unknown_primitive_skipped(self, extractor):
        features = extractor.extract_word_features("xyz", {"UNKNOWN_PRIM": 1})
        # No primitive map → empty
        assert features == {}

    def test_bipolar_maps_negative(self, extractor):
        features = extractor.extract_word_features("sad", {"BAD": 1})
        # BAD → GOOD with polarity preserved
        assert "GOOD" in features

    def test_polarity_preserved(self, extractor):
        features = extractor.extract_word_features("hate", {"GOOD": -1})
        assert features["GOOD"] == -1.0

    def test_no_primitives_no_trace(self, extractor):
        features = extractor.extract_word_features("word")
        assert features == {}

    def test_trace_fallback(self, extractor):
        trace = MagicMock()
        trace.word_primitives = {"GOOD": 1}
        features = extractor.extract_word_features("word", trace=trace)
        assert features.get("GOOD") == 1.0


# ---------- _map_to_network_primitive ----------

class TestMapToNetworkPrimitive:
    def test_direct_match(self, extractor):
        assert extractor._map_to_network_primitive("GOOD") == "GOOD"

    def test_case_normalized(self, extractor):
        assert extractor._map_to_network_primitive("good") == "GOOD"

    def test_bipolar_bad_maps_good(self, extractor):
        assert extractor._map_to_network_primitive("BAD") == "GOOD"

    def test_bipolar_small_maps_big(self, extractor):
        assert extractor._map_to_network_primitive("SMALL") == "BIG"

    def test_unknown_returns_none(self, extractor):
        assert extractor._map_to_network_primitive("nonsense") is None


# ---------- extract_all_features ----------

class TestExtractAllFeatures:
    def test_returns_4_scales(self, extractor):
        text = "Hello world. Goodbye world."
        result = extractor.extract_all_features(text)
        assert "text" in result
        assert "paragraph" in result
        assert "sentence" in result
        assert "word" in result

    def test_paragraph_split_on_double_newline(self, extractor):
        text = "Para one.\n\nPara two."
        result = extractor.extract_all_features(text)
        assert len(result["paragraph"]) == 2

    def test_sentence_split(self, extractor):
        text = "First sentence. Second one! Third?"
        result = extractor.extract_all_features(text)
        assert len(result["sentence"]) == 3

    def test_provided_sentences_override(self, extractor):
        text = "Long text would split into many sentences."
        result = extractor.extract_all_features(text, sentences=["only one"])
        # Custom sentences used
        assert len(result["sentence"]) == 1

    def test_word_primitives_populate_word_scale(self, extractor):
        result = extractor.extract_all_features(
            "Hello.", word_primitives={"happy": {"GOOD": 1}}
        )
        assert "happy" in result["word"]

    def test_word_with_no_known_primitives_excluded(self, extractor):
        result = extractor.extract_all_features(
            "Hello.", word_primitives={"happy": {"UNKNOWN": 1}}
        )
        # No features extracted → not in dict
        assert "happy" not in result["word"]


# ---------- _split_sentences ----------

class TestSplitSentences:
    def test_period_split(self, extractor):
        result = extractor._split_sentences("One. Two. Three.")
        assert len(result) == 3

    def test_strips_whitespace(self, extractor):
        result = extractor._split_sentences("  Hi.  Bye.  ")
        for s in result:
            assert not s.startswith(" ")

    def test_empty_filtered(self, extractor):
        result = extractor._split_sentences(".")
        # Period alone → empty after split → filtered
        assert "" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
