"""Model choices must use GSE's actual pole vocabulary and scoped domains."""

from pathlib import Path

import pytest

from gse.lexicon_builder.build import adjective_seed, build, source_matches
from gse.lexicon_builder.core import coordinate_vocabulary
from gse.lexicon_builder.reading import construct_reading
from gse.lexicon_builder.registry import load_rulebook
from gse.lexicon_builder.sources import NativeSources
from gse.lexicon_builder.tail import attach_tail
from tests.lexicon_sources import requires_lexicon_sources


def test_coordinate_vocabulary_matches_signed_aliases_instead_of_numeric_guessing():
    assert coordinate_vocabulary("THEN")["signed_prime_names"] == {"+1": "THEN", "-1": "NOW"}
    assert coordinate_vocabulary("GOOD")["signed_prime_names"] == {"+1": "GOOD", "-1": "BAD"}
    assert coordinate_vocabulary("MOVE")["signed_prime_names"] == {"+1": "MOVE"}
    with pytest.raises(ValueError, match="UNKNOWN_COORDINATE"):
        coordinate_vocabulary("NUMBER")


@requires_lexicon_sources
def test_family_temporal_domain_and_both_selector_routes_preserve_the_scope():
    source = NativeSources(["afraid"], Path("data/external"), Path.home() / "nltk_data/corpora")
    book = load_rulebook()
    native = source.for_word("afraid")
    match = source_matches(native, book)[0]
    seed = adjective_seed("afraid", match, native)
    result = construct_reading(seed, book, None)
    assert set(result["after_selection"]["domains"]["THEN"]) == {"-1", "0", "empty"}
    assert match["rule"]["definition_boundary"]["revision"] == 4
    assert result["after_selection"]["domains"]["MAYBE"] == ["+1", "empty"]
    assert "0" in result["after_selection"]["domains"]["DO"]
    assert "MUST" not in result["residual_coordinates"]

    class ScopeRecorder:
        def __init__(self):
            self.calls = []

        def select(self, payload, options):
            self.calls.append(payload)
            assert payload["projection_scope"] == match["rule"]["fill_scope"]
            assert all("ABSTAIN" in domain for domain in options.values())
            return {"request_sha256": "scope-witness", "answer": {c: "empty" for c in options}}

    library = ScopeRecorder()
    construct_reading(seed, book, library)
    assert library.calls == []
    # Explicit fixture admission proves the bounded model mechanism still
    # works when source facts leave a choice. This is not lexical admission.
    seed.selection_policy = {**seed.selection_policy, "status": "ADMITTED", "reason": "Mechanics fixture only"}
    construct_reading(seed, book, library)
    assert library.calls[0]["coordinate_vocabulary"]["THEN"]["signed_prime_names"]["-1"] == "NOW"
    task = {
        "reading_id": seed.reading_id,
        "coordinate": "THEN",
        "options": result["after_selection"]["domains"]["THEN"],
        "reason": "UNRESOLVED_COMPONENT",
        "source_record_ids": match["premises"],
    }
    queued = ScopeRecorder()
    queue_seed = adjective_seed("afraid", match, native)
    blocked = construct_reading(attach_tail(queue_seed, [task]), book, queued)
    assert queued.calls == []
    assert blocked["decisions"][0]["code"] == "WITHHELD_MODEL_TASK_TYPE"
    queue_seed.selection_policy = seed.selection_policy
    construct_reading(attach_tail(queue_seed, [task]), book, queued)
    assert queued.calls[0]["coordinate_vocabulary"]["signed_prime_names"]["-1"] == "NOW"
    assert "family_optional_warrants" not in queued.calls[0]["native_observations"]


@requires_lexicon_sources
def test_quantified_template_decomposes_through_the_real_builder_without_a_call():
    sources = NativeSources(["afraid", "scared"], Path("data/external"), Path.home() / "nltk_data/corpora")
    for record in build(["afraid", "scared"], sources, load_rulebook(), None):
        for reading in record["readings"]:
            if reading.get("rule_id") == "EMOTION_FEAR_ADJ":
                assert reading["after_selection"]["forced"]["QUANTITY"] == "+1"
                assert reading["after_selection"]["forced"]["WHEN"] == "+1"
                assert reading["model_calls"] == []
                assert "QUANTITY" not in reading["residual_coordinates"]


@requires_lexicon_sources
def test_quantification_expectation_cannot_replace_its_deleted_warrant():
    sources = NativeSources(["afraid"], Path("data/external"), Path.home() / "nltk_data/corpora")
    book = load_rulebook()
    book["laws"] = [r for r in book["laws"] if r["rule_id"] != "QUANTIFIED_TIME_PORTMANTEAU"]
    result = next(build(["afraid"], sources, book, None))["readings"][0]
    assert len(result["after_selection"]["domains"]["QUANTITY"]) > 1
    assert result["after_selection"]["forced"]["WHEN"] == "+1"
    assert "QUANTITY" in result["definition_accounting"]["unresolved"]
    assert result["candidate_vector"] is None
