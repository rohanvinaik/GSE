"""Native projection suggestions retain alternatives without becoming lexical facts."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from gse.curation.external_sources.nrc_emotion import EmotionEntry, NRCEmotionParser
from gse.curation.external_sources.nrc_vad import NRCVADParser, VADEntry
from gse.curation.external_sources.sentiwordnet import SentiWordEntry, SentiWordNetParser
from gse.curation.external_sources.wordnet_hierarchy import WordNetHierarchyParser
from gse.curation.lexicon_builder.evidence import collect_evidence


def sentiment(positive=0.4, negative=0.5):
    return SentiWordEntry("bank", "noun", positive, negative, 1 - positive - negative, "bank.n.01")


def vad(version, value):
    return VADEntry(
        "bank",
        value,
        0.5,
        0.5,
        native_version=version,
        native_scale=(0.0, 1.0) if version == "1" else (-1.0, 1.0),
        native_header=("word" if version == "1" else "term", "valence", "arousal", "dominance"),
    )


def values(candidates):
    return {candidate["bank"]: candidate["suggested_values"] for candidate in candidates}


def test_sentiwordnet_preserves_both_alternatives_without_larger_score_winner():
    parser = SentiWordNetParser()
    assert values(parser.projection_candidates_for_entry(sentiment())) == {"GOOD": [-1, 1]}
    assert values(parser.projection_candidates_for_entry(sentiment(0.5, 0.4))) == {"GOOD": [-1, 1]}
    assert values(parser.projection_candidates_for_entry(sentiment(0.4, 0.4))) == {"GOOD": [-1, 1]}
    assert parser.projection_candidates_for_entry(sentiment(0.0, 0.0)) == []
    assert parser.projection_candidates_for_entry(sentiment(0.25, 0.25)) == []


@pytest.mark.parametrize("value", [None, True, float("nan"), -0.1, 1.1, "0.4"])
def test_sentiwordnet_malformed_score_never_yields_candidate(value):
    assert SentiWordNetParser().projection_candidates_for_entry(replace(sentiment(), pos_score=value)) is None


def test_emotion_mapping_retains_conflicts_and_obeys_source_competence():
    parser = NRCEmotionParser()
    flags = {"joy": 1, "sadness": 1, "trust": 1, "surprise": 1, "anticipation": 1}
    first = parser.projection_candidates_for_entry(EmotionEntry("bank", flags))
    second = parser.projection_candidates_for_entry(EmotionEntry("bank", dict(reversed(tuple(flags.items())))))
    assert first == second
    assert values(first) == {"GOOD": [-1, 1], "FEEL": [1], "KNOW": [-1, 1], "WANT": [1]}
    assert all(candidate["mapping_provenance"] for candidate in first)
    assert parser.projection_candidates_for_entry(EmotionEntry("bank", {"joy": 0, "negative": 0})) == []
    assert parser.projection_candidates_for_entry(EmotionEntry("bank", {})) == []


@pytest.mark.parametrize("flags", [{"joy": True}, {"joy": -1}, {"joy": None}, {"other": 1}, None])
def test_emotion_malformed_native_flags_abstain(flags):
    assert NRCEmotionParser().projection_candidates_for_entry(EmotionEntry("bank", flags)) is None


@pytest.mark.parametrize(
    "version,score,expected",
    [
        ("1", 0.8, {"GOOD": [1]}),
        ("2", 0.6, {"GOOD": [1]}),
        ("1", 0.2, {"GOOD": [-1]}),
        ("2", -0.6, {"GOOD": [-1]}),
        ("1", 0.5, {}),
        ("2", 0.0, {}),
        ("1", 0.65, {}),
        ("1", 0.35, {}),
        ("2", 0.3, {}),
        ("2", -0.3, {}),
    ],
)
def test_vad_candidates_use_declared_scale_and_never_neutral_zero(version, score, expected):
    entry = vad(version, score)
    candidates = NRCVADParser().projection_candidates_for_entry(entry)
    assert values(candidates) == expected
    assert entry.valence == score
    assert all(0 not in candidate["suggested_values"] for candidate in candidates)


@pytest.mark.parametrize(
    "changes",
    [
        {"native_version": None},
        {"native_scale": (0.0, 1.0)},
        {"native_header": ("unknown",)},
        {"valence": True},
        {"valence": float("nan")},
        {"arousal": 2.0},
        {"dominance": "0.5"},
    ],
)
def test_vad_undeclared_inconsistent_or_malformed_scale_abstains(changes):
    assert NRCVADParser().projection_candidates_for_entry(replace(vad("2", 0.6), **changes)) is None


def test_vad_loader_preserves_header_version_and_raw_values(tmp_path):
    source = tmp_path / "vad.tsv"
    source.write_text("term\tvalence\tarousal\tdominance\nbank\t-0.6\t0.2\t-0.1\n")
    parser = NRCVADParser(str(source))
    assert parser.load()
    entry = parser.entries["bank"]
    assert (entry.valence, entry.arousal, entry.dominance) == (-0.6, 0.2, -0.1)
    assert entry.native_version == "2" and entry.native_scale == (-1.0, 1.0)
    candidates = parser.projection_candidates_for_entry(entry)
    assert "nrc_vad:v1_valence=(raw+1)/2" in candidates[0]["mapping_provenance"]
    source.write_text("unknown\tV\tA\tD\nbank\t-0.6\t0.2\t-0.1\n")
    assert parser.load()
    assert parser.entries["bank"].native_header == ("unknown", "V", "A", "D")
    assert parser.projection_candidates_for_entry(parser.entries["bank"]) is None


def spine():
    from nltk.corpus import wordnet

    wordnet.ensure_loaded()
    parser = WordNetHierarchyParser()
    parser._wn = wordnet
    parser._loaded = True
    return parser


def test_collector_keeps_candidates_per_record_without_assertions_restrictions_or_fanout():
    wordnet = spine()
    baseline = collect_evidence({"wordnet_hierarchy": wordnet}, ("bank",))
    senti = SentiWordNetParser()
    senti._loaded = True
    native_synsets = [o.features["synset_name"] for o in baseline.observations if o.features["pos"] == "noun"][:2]
    assert len(native_synsets) == 2
    first_synset, second_synset = native_synsets
    senti.entries = {
        "bank": [
            replace(sentiment(), synset_id=first_synset),
            replace(sentiment(0.9, 0.0), synset_id=second_synset),
        ]
    }
    emotion = NRCEmotionParser()
    emotion._loaded = True
    emotion.entries = {"bank": EmotionEntry("bank", {"positive": 1, "negative": 1})}
    ratings = NRCVADParser()
    ratings._loaded = True
    ratings.entries = {"bank": vad("2", 0.8)}
    sources = {"wordnet_hierarchy": wordnet, "sentiwordnet": senti, "nrc_emotion": emotion, "nrc_vad": ratings}
    result = collect_evidence(sources, ("bank",))
    assert result.assertions == baseline.assertions
    assert result.domain_restrictions == baseline.domain_restrictions == ()
    observations = [o for o in result.observations if o.source != "wordnet_hierarchy"]
    assert len(observations) == 4
    exact = {o.features["synset_id"]: o for o in observations if o.source == "sentiwordnet"}
    assert values(exact[first_synset].features["projection_candidates"]) == {"GOOD": [-1, 1]}
    assert values(exact[second_synset].features["projection_candidates"]) == {"GOOD": [1]}
    assert all(o.entry_id is not None for o in exact.values())
    assert all(
        o.entry_id is None and len(o.candidate_entry_ids) > 1 for o in observations if o.source != "sentiwordnet"
    )
    assert all(
        c["evidence_disposition"] == "ASSOCIATION_OWN_DEFINITION_UNESTABLISHED"
        for o in observations
        for c in o.features["projection_candidates"]
    )
    no_hooks = {
        name: SimpleNamespace(_loaded=True, entries=parser.entries)
        for name, parser in sources.items()
        if name != "wordnet_hierarchy"
    }
    without = collect_evidence({"wordnet_hierarchy": wordnet, **no_hooks}, ("bank",))
    assert {o.record_id for o in result.observations} == {o.record_id for o in without.observations}


@pytest.mark.parametrize(
    "candidate,code",
    [
        ({"bank": "GOOD", "suggested_values": [True]}, "INVALID_PROJECTION_CANDIDATES"),
        ({"bank": "GOOD", "suggested_values": []}, "INVALID_PROJECTION_CANDIDATES"),
        ({"bank": "GOOD", "suggested_values": [1, 1]}, "INVALID_PROJECTION_CANDIDATES"),
        ({"bank": "BAD", "suggested_values": [1]}, "INVALID_PROJECTION_CANDIDATES"),
        ({"bank": "DO", "suggested_values": [1]}, "CANDIDATE_OUTSIDE_SOURCE_SCOPE"),
        (
            {"bank": "GOOD", "suggested_values": [1], "evidence_disposition": "LEXICAL_FACT"},
            "INVALID_PROJECTION_CANDIDATES",
        ),
    ],
)
def test_collector_rejects_untyped_or_out_of_scope_candidates(candidate, code):
    candidate = {
        "mapping_provenance": ["fixture:mapping"],
        "evidence_disposition": "ASSOCIATION_OWN_DEFINITION_UNESTABLISHED",
        **candidate,
    }
    source = SimpleNamespace(
        _loaded=True, entries={"bank": [sentiment()]}, projection_candidates_for_entry=lambda entry: [candidate]
    )
    with pytest.raises(ValueError, match=code):
        collect_evidence({"sentiwordnet": source}, ("bank",))
