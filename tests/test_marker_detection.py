"""Tests for gse.encoders.marker_detection."""

from gse.encoders.marker_detection import KeywordDetector, RegexPatternDetector


class TestKeywordDetector:
    def test_single_category_single_marker(self):
        detector = KeywordDetector({"A": ["foo"]})
        assert detector.detect("foo bar")["A"] == 1.0

    def test_count_matches_per_category(self):
        detector = KeywordDetector({"A": ["foo", "baz"]})
        assert detector.detect("foo baz foo")["A"] == 2.0

    def test_case_insensitive(self):
        detector = KeywordDetector({"A": ["foo"]})
        assert detector.detect("FOO bar")["A"] == 1.0

    def test_zero_score_when_no_match(self):
        detector = KeywordDetector({"A": ["foo"]})
        assert detector.detect("nothing here")["A"] == 0.0

    def test_avoid_penalty_subtracts(self):
        detector = KeywordDetector(
            markers={"A": ["foo"]},
            avoid={"A": ["bar"]},
            avoid_penalty=0.5,
        )
        # Match "foo" gives +1, avoid "bar" gives -0.5 → 0.5
        assert detector.detect("foo and bar")["A"] == 0.5

    def test_avoid_clamps_at_zero(self):
        detector = KeywordDetector(
            markers={"A": ["foo"]},
            avoid={"A": ["bar", "baz"]},
            avoid_penalty=0.5,
        )
        # +1 from foo, -1 from bar+baz → 0; clamps at 0 even if more avoids
        assert detector.detect("foo bar baz qux")["A"] == 0.0

    def test_multiple_categories_isolated(self):
        detector = KeywordDetector({"A": ["foo"], "B": ["bar"]})
        scores = detector.detect("foo bar")
        assert scores == {"A": 1.0, "B": 1.0}


class TestRegexPatternDetector:
    def test_single_pattern_match(self):
        detector = RegexPatternDetector({"A": [r"^hello"]})
        assert detector.detect("hello world")["A"] == 1.0

    def test_pattern_no_match(self):
        detector = RegexPatternDetector({"A": [r"^hello"]})
        assert detector.detect("world hello")["A"] == 0.0

    def test_compiles_patterns_once(self):
        detector = RegexPatternDetector({"A": [r"\w+"]})
        first = detector.patterns_for("A")
        second = detector.patterns_for("A")
        # Same compiled objects on repeated access
        assert first is second

    def test_patterns_for_unknown_category(self):
        detector = RegexPatternDetector({"A": [r"x"]})
        assert detector.patterns_for("missing") == []

    def test_count_matching_patterns_per_category(self):
        detector = RegexPatternDetector({"A": [r"foo", r"bar", r"baz"]})
        # All three patterns match the lowercased text
        assert detector.detect("foo bar baz")["A"] == 3.0
