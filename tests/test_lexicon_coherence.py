"""Intent and negative specification for the source-native coherence calculation."""

import math

import pytest

from scripts.lexicon_coherence import (
    Corpus,
    binary_entropy,
    coherence_statistics,
    conjunction_relations,
    fold,
    relation_status,
    restrict_to_single_words,
    table,
)


def test_exact_relation_retains_counterexample_count_and_direction():
    result = coherence_statistics(100, 0, 0, 100)
    assert result["signed_coherence"] == 1
    assert result["entropy_reduction_bits"] == 1
    assert result["violations"] == 0
    assert result["phi"] == 1


def test_anticorrelation_does_not_become_positive_coherence():
    result = coherence_statistics(0, 100, 100, 0)
    assert result["signed_coherence"] == -1
    assert result["phi"] == -1
    assert result["conditional_probability"] == 0


def test_independence_carries_no_information_gain():
    result = coherence_statistics(25, 25, 25, 25)
    assert result["entropy_reduction_bits"] == 0
    assert result["phi"] == 0
    assert result["lift"] == 1


def test_absent_antecedent_is_unmeasured_not_false_or_silent():
    assert coherence_statistics(0, 0, 10, 10) == {"status": "NO_ANTECEDENT", "population": 20, "support": 0}


def test_zero_target_probability_keeps_lift_undefined():
    result = coherence_statistics(0, 10, 0, 10)
    assert result["conditional_probability"] == 0
    assert result["lift"] is None


@pytest.mark.parametrize("counts", [(-1, 0, 0, 0), (0.5, 1, 0, 0), (True, 0, 0, 0)])
def test_invalid_counts_are_refused(counts):
    with pytest.raises(ValueError):
        coherence_statistics(*counts)


def test_entropy_endpoints_and_invalid_input():
    assert binary_entropy(0) == binary_entropy(1) == 0
    assert binary_entropy(0.5) == 1
    with pytest.raises(ValueError):
        binary_entropy(math.nan)


def test_repeated_rule_is_candidate_even_without_observed_exceptions():
    train = coherence_statistics(60, 0, 10, 100)
    heldout = coherence_statistics(40, 0, 10, 100)
    assert relation_status(train, heldout, 40) == "EXCEPTION_FREE_OBSERVED_CANDIDATE"


def test_high_base_rate_alone_is_not_rule_evidence():
    train = coherence_statistics(98, 2, 98, 2)
    heldout = coherence_statistics(98, 2, 98, 2)
    assert relation_status(train, heldout, 40) == "BASE_RATE_DOMINATED"


def test_heldout_failure_cannot_be_hidden_by_training_success():
    train = coherence_statistics(100, 0, 10, 100)
    heldout = coherence_statistics(50, 50, 10, 100)
    assert relation_status(train, heldout, 40) == "EXCEPTIONS_TOO_FREQUENT"


def test_no_support_does_not_get_promoted():
    train = coherence_statistics(0, 0, 10, 100)
    heldout = coherence_statistics(50, 0, 10, 100)
    assert relation_status(train, heldout, 40) == "INSUFFICIENT_SUPPORT"


def test_missing_source_records_never_become_negative_observations():
    result = table({"seen", "not-in-b"}, {"seen", "not-in-a"}, {"seen", "other"})
    assert result["table"] == [1, 0, 0, 1]


def test_single_word_scope_preserves_native_spelling():
    corpus = Corpus()
    for word in ["word", "mother-in-law", "façade", "don't", "two words", "two_words", "&"]:
        corpus.words["vad"].add(word)
        corpus.feature("vad", "x", word)
        corpus.number("vad", "x", word, "0")
    restrict_to_single_words(corpus)
    assert corpus.words["vad"] == {"word", "mother-in-law", "façade", "don't"}
    assert corpus.features["vad:x"] == corpus.words["vad"]
    assert set(corpus.numeric["vad:x"]) == corpus.words["vad"]


def test_complementary_pair_survives_without_singleton_correlation():
    """Significance Weighting §13: a bridge cannot be screened by singleton gain."""
    corpus = Corpus()
    bins = {i: [] for i in range(5)}
    for i in range(1000):
        word = f"w{i}"
        if len(bins[fold(word)]) < 16:
            bins[fold(word)].append(word)
    for words in bins.values():
        assert len(words) == 16
        for i, word in enumerate(words):
            a, b = i % 2, (i // 2) % 2
            for source in ("usas", "framenet", "vad"):
                corpus.words[source].add(word)
            if a:
                corpus.feature("usas", "category=X", word)
            if b:
                corpus.feature("framenet", "frame=Y", word)
            if a == b:
                corpus.feature("vad", "valence_sign=positive", word)
    relations = conjunction_relations(corpus, 2)
    assert len(relations) == 1
    assert relations[0]["zero_or_negative_singleton_lift"]
    assert relations[0]["overall"]["conditional_probability"] == 1
    assert relations[0]["conditional_entropy_reduction_bits"] == [[1, 1], [1, 1]]
