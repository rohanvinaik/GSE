"""Manual contract tests for gse.curation.llm.prompts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.llm.prompts import (
    BATCH_CONFIG,
    EXAMPLE_DECOMPOSITIONS,
    SYSTEM_PROMPT,
    build_batch_prompt,
    build_few_shot_prompt,
    build_user_prompt,
)

# ---------- BATCH_CONFIG ----------


class TestBatchConfig:
    def test_has_three_phases(self):
        assert set(BATCH_CONFIG.keys()) == {"phase_1", "phase_2", "phase_3"}

    def test_phase_1_batch_size(self):
        assert BATCH_CONFIG["phase_1"]["batch_size"] == 10

    def test_phase_1_temperature(self):
        assert BATCH_CONFIG["phase_1"]["temperature"] == 0.3

    def test_phase_1_max_tokens(self):
        assert BATCH_CONFIG["phase_1"]["max_tokens"] == 2000

    def test_phase_1_retry(self):
        assert BATCH_CONFIG["phase_1"]["retry_on_validation_fail"] is True

    def test_phase_1_review_threshold(self):
        assert BATCH_CONFIG["phase_1"]["human_review_threshold"] == 0.7

    def test_phase_2_matches_phase_1(self):
        # Phase 2 explicitly mirrors phase 1
        for key in ("batch_size", "temperature", "human_review_threshold"):
            assert BATCH_CONFIG["phase_2"][key] == BATCH_CONFIG["phase_1"][key]


# ---------- SYSTEM_PROMPT ----------


class TestSystemPrompt:
    def test_mentions_72_primitives(self):
        assert "72" in SYSTEM_PROMPT

    def test_mentions_8_banks(self):
        assert "8" in SYSTEM_PROMPT and "bank" in SYSTEM_PROMPT.lower()

    def test_mentions_bipolar_constraints(self):
        assert "BIPOLAR" in SYSTEM_PROMPT or "Bipolar" in SYSTEM_PROMPT

    def test_mentions_good_bad_pair(self):
        assert "GOOD/BAD" in SYSTEM_PROMPT

    def test_mentions_output_format_json(self):
        assert "JSON" in SYSTEM_PROMPT


# ---------- build_user_prompt ----------


class TestBuildUserPrompt:
    def test_default_uses_full_template(self):
        result = build_user_prompt("happy")
        assert "happy" in result
        # Full template mentions step-by-step
        assert "step by step" in result

    def test_pos_propagated(self):
        result = build_user_prompt("walk", pos="verb")
        assert "verb" in result

    def test_gloss_used_when_provided(self):
        result = build_user_prompt("happy", gloss="feeling joy")
        assert "feeling joy" in result

    def test_gloss_default_not_provided(self):
        # Without gloss, should say "Not provided"
        result = build_user_prompt("happy")
        assert "Not provided" in result

    def test_simple_uses_short_template(self):
        result = build_user_prompt("happy", simple=True)
        # Simple prompt doesn't have step-by-step
        assert "step by step" not in result

    def test_simple_pos_propagated(self):
        result = build_user_prompt("happy", pos="adj", simple=True)
        assert "adj" in result

    def test_default_pos_unknown(self):
        result = build_user_prompt("happy")
        assert "unknown" in result


# ---------- build_batch_prompt ----------


class TestBuildBatchPrompt:
    def test_empty_list(self):
        result = build_batch_prompt([])
        # Should not crash, mentions decompose
        assert "Decompose" in result

    def test_single_word(self):
        result = build_batch_prompt([{"word": "happy", "pos": "adj"}])
        assert "happy" in result
        assert "adj" in result

    def test_numbers_each_word(self):
        result = build_batch_prompt(
            [
                {"word": "happy"},
                {"word": "sad"},
            ]
        )
        assert "1. happy" in result
        assert "2. sad" in result

    def test_default_pos_unknown(self):
        result = build_batch_prompt([{"word": "x"}])
        assert "unknown" in result

    def test_gloss_appended_when_present(self):
        result = build_batch_prompt([{"word": "happy", "gloss": "feeling joy"}])
        assert "feeling joy" in result

    def test_no_gloss_no_dash(self):
        result = build_batch_prompt([{"word": "happy"}])
        # No " - " after the pos paren for words without gloss
        assert "happy (unknown)" in result

    def test_mentions_bipolar(self):
        result = build_batch_prompt([{"word": "x"}])
        assert "Bipolar" in result or "bipolar" in result

    def test_mentions_72_primitives(self):
        result = build_batch_prompt([{"word": "x"}])
        assert "72" in result

    def test_enumeration_starts_at_1(self):
        # First word numbered "1." not "0."
        result = build_batch_prompt([{"word": "first"}, {"word": "second"}])
        assert "1. first" in result
        assert "2. second" in result
        assert "0. first" not in result

    def test_gloss_separator_format(self):
        # The " - " separator between pos and gloss
        result = build_batch_prompt([{"word": "x", "gloss": "def"}])
        assert "(unknown) - def" in result

    def test_exact_prompt_intro(self):
        # Pin exact intro line
        result = build_batch_prompt([{"word": "x"}])
        assert "Decompose each of these words into GSE primitives:" in result

    def test_exact_response_format_line(self):
        result = build_batch_prompt([{"word": "x"}])
        assert "JSON array" in result

    def test_exact_all_72_line(self):
        result = build_batch_prompt([{"word": "x"}])
        assert "all 72 primitives" in result.lower() or "ALL 72 primitives" in result

    def test_newline_separator_between_words(self):
        # chr(10) is newline → each numbered item on its own line
        result = build_batch_prompt([{"word": "a"}, {"word": "b"}])
        # Lines containing the words should be on separate lines
        lines = result.split("\n")
        line_a = next(i for i, l in enumerate(lines) if "1. a" in l)
        line_b = next(i for i, l in enumerate(lines) if "2. b" in l)
        # They should be on different lines, b after a
        assert line_b > line_a

    def test_one_object_per_word_text(self):
        result = build_batch_prompt([{"word": "x"}])
        assert "one object per word" in result


# ---------- EXAMPLE_DECOMPOSITIONS ----------


class TestExampleDecompositions:
    def test_contains_happy(self):
        assert "happy" in EXAMPLE_DECOMPOSITIONS

    def test_contains_sad(self):
        assert "sad" in EXAMPLE_DECOMPOSITIONS

    def test_contains_walk(self):
        assert "walk" in EXAMPLE_DECOMPOSITIONS

    def test_happy_good_positive(self):
        assert EXAMPLE_DECOMPOSITIONS["happy"]["GOOD"] == 1

    def test_sad_good_negative(self):
        # "sad" uses GOOD=-1 not BAD=1 per bipolar rules
        assert EXAMPLE_DECOMPOSITIONS["sad"]["GOOD"] == -1
        assert EXAMPLE_DECOMPOSITIONS["sad"]["BAD"] == 0

    def test_walk_do_and_move(self):
        assert EXAMPLE_DECOMPOSITIONS["walk"]["DO"] == 1
        assert EXAMPLE_DECOMPOSITIONS["walk"]["MOVE"] == 1


# ---------- build_few_shot_prompt ----------


class TestBuildFewShotPrompt:
    def test_basic(self):
        result = build_few_shot_prompt("happy")
        assert "happy" in result

    def test_pos_propagated(self):
        result = build_few_shot_prompt("walk", pos="verb")
        assert "verb" in result

    def test_includes_examples(self):
        result = build_few_shot_prompt("x", n_examples=2)
        # Should include "happy" and "sad" examples
        assert '"happy"' in result
        assert '"sad"' in result

    def test_n_examples_limits(self):
        result = build_few_shot_prompt("x", n_examples=1)
        assert '"happy"' in result
        assert '"sad"' not in result
        assert '"walk"' not in result

    def test_gloss_appended(self):
        result = build_few_shot_prompt("x", gloss="meaning")
        assert "meaning" in result

    def test_no_gloss_no_appendage(self):
        # When gloss is None, no " - " after the pos paren
        result = build_few_shot_prompt("x")
        # Word followed by "(unknown)" and immediately newline / using
        assert "(unknown) using" in result

    def test_n_examples_zero(self):
        result = build_few_shot_prompt("x", n_examples=0)
        # No examples included
        assert '"happy"' not in result

    def test_examples_use_json_format(self):
        result = build_few_shot_prompt("x", n_examples=1)
        # Should contain "GOOD": 1 from happy example
        assert '"GOOD": 1' in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
