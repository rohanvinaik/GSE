"""Repeated native tags are not senses; independent located joins remain distinct."""

from copy import deepcopy
from pathlib import Path

from gse.lexicon_builder.build import adjective_seed, build, source_matches
from gse.lexicon_builder.registry import load_rulebook
from gse.lexicon_builder.sources import NativeSources
from tests.lexicon_sources import requires_lexicon_sources


def fixture():
    rule = {
        "rule_id": "TEST_QUALITY",
        "family": "quality",
        "pos": ["ADJ"],
        "category": "A5.1",
        "frames": ["desirability"],
        "coordinate": "GOOD",
        "warrant": "Synthetic identity fixture",
        "residual": [],
        "companions": {},
        "coverage": None,
    }
    native = {
        "usas": {"records": [{"record_id": "usas:1", "values": {"pos": "ADJ", "alternatives": ["A5.1+", "A5.1+"]}}]},
        "framenet": {"records": [{"record_id": "fn:1", "values": {"pos": "a", "frame": "desirability"}}]},
    }
    return native, {"source_rules": [rule]}


def test_a_repeated_tag_on_the_same_source_record_is_one_reading():
    native, book = fixture()
    matches = source_matches(native, book)
    assert len(matches) == 1
    assert adjective_seed("word", matches[0], native).reading_id == "word:ADJ:A5.1+:quality"


def test_independent_source_joins_remain_separate_and_order_independent():
    native, book = fixture()
    other = deepcopy(native["usas"]["records"][0])
    other["record_id"] = "usas:2"
    native["usas"]["records"].append(other)
    matches = source_matches(native, book)
    ids = {adjective_seed("word", m, native).reading_id for m in matches}
    assert len(matches) == len(ids) == 2
    native["usas"]["records"].reverse()
    assert {adjective_seed("word", m, native).reading_id for m in source_matches(native, book)} == ids


@requires_lexicon_sources
def test_actual_magnificent_duplicate_does_not_break_release_identity():
    sources = NativeSources(["magnificent"], Path("data/external"), Path.home() / "nltk_data/corpora")
    record = next(build(["magnificent"], sources, load_rulebook(), None))
    identities = [r["reading_id"] for r in record["readings"]]
    assert len(identities) == len(set(identities))
    assert identities.count("magnificent:ADJ:A5.1+:quality") == 1
