"""Intent at the document intake/profile/cassette boundary, including refusals."""

import time
from types import SimpleNamespace

import pytest

from gse.api import GSEEncoder
from gse.api.trace import OperationTrace, TokenTrace
from gse.cassettes.deck import CassetteDeck
from gse.cassettes.entity_identity import EntityIdentity, IdentityGap
from gse.cassettes.multiscale import Mention, MultiScaleDoc
from gse.cassettes.relational_identity import RelationalIdentity
from gse.discourse.intake import SourceSentence, document_sentences, split_paragraphs
from gse.discourse.profile import PROFILE_FIELDS, text_profile
from gse.discourse.speech import encode_document_utterance_events, encode_document_utterances_traced, segment_document
from gse.structure import (
    clause_depth,
    clause_head_evidence,
    entity_source_evidence,
    operation_counts,
    structural_loss_evidence,
    verb_head_evidence,
)
from gse.symbolic.expression import Atom
from gse.symbolic.predicates import Event
from gse.symbolic.resolution import Entity


class Encoder:
    word_basis = SimpleNamespace(primitives={"GOOD": object(), "BAD": object()})

    def __init__(self, fail=(), lookup_fail=False):
        self.fail = fail
        self.lookup_fail = lookup_fail
        self.calls = []

    def encode(self, text):
        self.calls.append(text)
        if text in self.fail:
            raise ValueError("intentional encode failure")
        tokens = [
            TokenTrace("Alice", "alice", "PROPN", 0, {}, {}, 0, 0, 0),
            TokenTrace("runs", "run", "VERB", 1, {"GOOD": 1, "BAD": 1}, {}, 0, 0, 0),
        ]
        return OperationTrace(text, tokens, [], 0, 1.0, {"GOOD": 1.0, "BAD": 1.0}, {}, "test")

    def _lookup_lexeme(self, lemma):
        if self.lookup_fail and lemma == "run":
            raise ValueError("late lookup failure")
        return ({"GOOD": 1, "BAD": 1}, {}, {})


@pytest.fixture
def simple_pipeline(monkeypatch):
    import gse.symbolic

    alice = Entity(Atom("alice", {}, position=0, pos="PROPN"), entity_id="alice")
    tree = Event("run", alice)
    monkeypatch.setattr(gse.symbolic, "from_trace", lambda trace: tree)
    monkeypatch.setattr(gse.symbolic, "resolve", lambda node: node)
    monkeypatch.setattr(gse.symbolic, "evaluate_tree", lambda node: node)
    return tree


def test_manifest_precedes_results_and_failures_do_not_renumber(simple_pipeline):
    enc = Encoder(fail=("bad",))
    events = list(
        encode_document_utterance_events(
            enc, [{"id": "original-4", "text": "bad"}, {"id": "original-9", "text": "good"}]
        )
    )
    assert events[0]["type"] == "manifest"
    assert events[0]["sentences"][0]["expected_utterance_ids"] == ["original-4:u0"]
    assert [event["utterance_id"] for event in events[1:-1]] == ["original-4:u0", "original-9:u0"]
    assert [event["state"] for event in events[1:-1]] == ["unread", "read"]
    assert events[1]["error"]["code"] == "encode_error"
    assert events[-1]["reason"] == "complete"


def test_deadline_accounts_for_all_expected_ids_without_encoding(simple_pipeline):
    enc = Encoder()
    events = list(encode_document_utterance_events(enc, [("a", "one"), ("b", "two")], time.monotonic() - 1))
    assert [event["utterance_id"] for event in events[1:-1]] == ["a:u0", "b:u0"]
    assert all(event["error"]["code"] == "deadline" for event in events[1:-1])
    assert enc.calls == []
    assert events[-1]["reason"] == "deadline"


def test_empty_manifest_is_explicit(simple_pipeline):
    events = list(encode_document_utterance_events(Encoder(), []))
    assert [event["type"] for event in events] == ["manifest", "end"]
    assert events[0]["utterances"] == []
    assert events[-1]["expected"] == 0


def test_deixis_failure_is_a_located_outcome(simple_pipeline, monkeypatch):
    import gse.discourse.speech as speech

    def fail(tree, utterance):
        raise ValueError("deixis failed")

    monkeypatch.setattr(speech, "_apply_deixis", fail)
    events = list(encode_document_utterance_events(Encoder(), [("fixed", "good")]))
    assert events[1]["error"]["code"] == "deixis_error"
    assert events[1]["utterance_id"] == "fixed:u0"
    assert events[1]["tree"] is None
    assert encode_document_utterances_traced(Encoder(), ["good"]) == []


@pytest.mark.parametrize("phase", ["construction", "evaluation"])
def test_construction_and_evaluation_failures_are_named(simple_pipeline, monkeypatch, phase):
    import gse.symbolic

    def fail(node):
        raise ValueError("phase failed")

    monkeypatch.setattr(gse.symbolic, "from_trace" if phase == "construction" else "evaluate_tree", fail)
    events = list(encode_document_utterance_events(Encoder(), [("fixed", "good")]))
    assert events[1]["error"]["code"] == f"{phase}_error"


def test_malformed_source_ids_are_refused_before_manifest():
    with pytest.raises(ValueError, match="duplicate"):
        list(encode_document_utterance_events(Encoder(), [("same", "one"), ("same", "two")]))
    with pytest.raises(ValueError, match="string text"):
        list(encode_document_utterance_events(Encoder(), [{"id": "a", "text": None}]))


def test_quote_attribution_keeps_supplied_source_ids():
    utterances = segment_document([SourceSentence("first", '"I ran.'), SourceSentence("last", 'I left," said Bob.')])
    assert [item.source_sentence_id for item in utterances] == ["first", "last"]
    assert all(item.speaker == "bob" for item in utterances)


def test_paragraphs_preserve_text_and_document_units_keep_paragraph_ids():
    assert split_paragraphs("one\r\nwrapped\r\n\r\nsecond") == ["one\r\nwrapped", "second"]
    assert [unit.paragraph_id for unit in document_sentences("One.\n\nTwo. Three.")] == ["p0", "p1", "p1"]


def test_all_unread_profile_never_claims_measured_neutrality(simple_pipeline):
    profile = text_profile(Encoder(fail=("bad.",)), "bad.")
    assert profile.state == "unread" and profile.n_read == 0
    assert profile.affect["valence_mean"] is None
    assert profile.coherence["degraded_rate"] is None
    assert profile.populations["structure"]["state"] == "unread"
    assert len(profile.failures) == 1
    assert all(value == 0.0 for value in profile.legacy_vector())


def test_late_profile_failure_cannot_leave_partial_observation(simple_pipeline):
    profile = text_profile(Encoder(lookup_fail=True), "good.")
    assert profile.n_read == 0
    assert profile.register["mean_lemma_len"] is None
    assert profile.operator_mix["EVENT"] is None
    assert profile.operations["EVENT"] == 0


def test_balanced_measured_zero_and_legacy_layout(simple_pipeline):
    profile = text_profile(Encoder(), "good.")
    assert profile.affect["valence_mean"] == 0.0
    assert profile.populations["affect"]["state"] == "measured"
    assert len(profile.legacy_vector()) == len(PROFILE_FIELDS) + 2
    assert profile.operations["EVENT"] == 1


def test_empty_profile_has_absent_populations(simple_pipeline):
    profile = text_profile(Encoder(), "")
    assert profile.state == "empty" and profile.n_sentences == 0
    assert profile.populations["structure"]["state"] == "absent"
    assert profile.complexity["tokens_per_sent"] is None


def test_structural_measurements_retain_temporal_and_nested_boundaries():
    tree = {
        "_kind": "Temporal",
        "setting": {"_kind": "Atom", "lemma": "today"},
        "event": {
            "_kind": "Control",
            "controller": {},
            "inner": {
                "_kind": "RelativeRestriction",
                "head": {},
                "restriction": {"_kind": "Control", "controller": {}, "inner": {"_kind": "Event", "verb": "run"}},
            },
        },
    }
    assert operation_counts(tree)["TEMPORAL"] == 1
    assert operation_counts(tree)["CONTROL"] == 2
    assert clause_depth(tree) == 3
    assert clause_depth({"arbitrary": {"deep": {"dict": {"value": 1}}}}) == 0
    assert clause_depth({"_kind": "Event", "patient": {"_kind": "Event", "patient": {"_kind": "Event"}}}) == 2


def test_swallowed_verb_and_empty_operand_cannot_look_preserved():
    trace = {"tokens": [{"pos": "VERB", "lemma": "run", "position": 2}]}
    tree = {"_kind": "Op", "operation": "CONTRAST", "arity": 2, "args": [{"_kind": "Phrase", "atoms": []}]}
    findings = structural_loss_evidence(trace, tree, utterance_id="fixed:u0")
    assert {finding["code"] for finding in findings} >= {"missing_predicate", "empty_operand", "operand_arity_mismatch"}
    assert all(finding["utterance_id"] == "fixed:u0" for finding in findings)
    assert structural_loss_evidence(trace, {"_kind": "Event", "verb": "run"}) == []
    assert (
        structural_loss_evidence(
            trace, {"_kind": "Op", "operation": "EVENT", "primitive": "run", "arity": 0, "args": []}
        )
        == []
    )


def test_head_positions_refuse_guessed_repeated_verb_alignment():
    trace = {"tokens": [{"pos": "VERB", "lemma": "run", "position": 2}, {"pos": "VERB", "lemma": "run", "position": 5}]}
    heads = verb_head_evidence(trace, {"_kind": "Event", "verb": "run"})
    assert heads == [{"path": [], "verb": "run", "positions": [2, 5], "state": "ambiguous"}]
    assert verb_head_evidence(trace, {"_kind": "Event", "verb": "swim"})[0]["state"] == "absent"


def test_clause_heads_are_local_and_mismatched_antecedent_coordinates_are_unsupported():
    trace = {"tokens": [{"position": 0, "lemma": "alice"}, {"position": 2, "lemma": "bob"}]}
    tree = {
        "_kind": "Event",
        "agent": {"_kind": "Entity", "head": {"lemma": "alice", "position": 0}},
        "patient": {"_kind": "Entity", "head": {"lemma": "bob", "position": 2}},
    }
    row = clause_head_evidence(trace, tree)[0]
    assert row["state"] == "supported" and row["subject_positions"] == [0] and row["object_positions"] == [2]
    tree["agent"]["head"]["lemma"] = "earlier_antecedent"
    assert clause_head_evidence(trace, tree)[0]["state"] == "unsupported"


def test_person_evidence_is_three_way_and_never_truthy():
    doc = MultiScaleDoc.__new__(MultiScaleDoc)
    doc.by_id = {}
    assert doc.is_person(Mention("paris", "paris", "PROPN", 0, ("Place", "City"))).code == "non_person"
    assert doc.is_person(Mention("london", "london", "PROPN", 0, ("location",))).code == "non_person"
    assert doc.is_person(Mention("alice", "alice", "PROPN", 0, ("Person",))).code == "person"
    unknown = doc.is_person(Mention("zorb", "zorb", "PROPN", 0))
    assert unknown.code == "unknown"
    with pytest.raises(TypeError, match="explicit"):
        bool(unknown)


def test_cassette_deck_cannot_merge_role_to_city_or_unknown():
    for thread in [("Place", "City"), ()]:
        doc = MultiScaleDoc.__new__(MultiScaleDoc)
        role = Mention(
            "husband", "husband", "NOUN", 0, ("person",), possessor_eid="wife", possessor_span=("lady", "paris")
        )
        name = Mention("paris", "paris", "PROPN", 0, thread)
        doc.by_id = {"husband": [role], "paris": [name]}
        result = CassetteDeck([RelationalIdentity()]).resolve(doc)
        assert result.merges == {}


def test_supported_person_survives_cassette_deck():
    doc = MultiScaleDoc.__new__(MultiScaleDoc)
    role = Mention("husband", "husband", "NOUN", 0, ("person",), possessor_eid="wife", possessor_span=("lady", "alice"))
    name = Mention("alice", "alice", "PROPN", 0, ("Person",))
    doc.by_id = {"husband": [role], "alice": [name]}
    result = CassetteDeck([RelationalIdentity()]).resolve(doc)
    assert result.merges == {"husband": "alice"}


def test_entity_identity_split_requires_positive_person_evidence():
    doc = MultiScaleDoc.__new__(MultiScaleDoc)
    doc.by_id = {}
    member = Mention("unknown", "zorb", "PROPN", 0)
    gap = IdentityGap("split", "unknown", member)
    assert EntityIdentity().ground({"a": [member], "b": [member]}, gap, doc) is False


def test_multiscale_resolution_failure_keeps_sentence_success(simple_pipeline, monkeypatch):
    import gse.cassettes.multiscale as multiscale

    def fail(*args, **kwargs):
        raise ValueError("resolution failed")

    monkeypatch.setattr(multiscale, "resolve_document", fail)
    doc = MultiScaleDoc("good.", Encoder(), object())
    assert len(doc.sentence_trees) == 1
    assert doc.tree_sources == [{"tree_index": 0, "utterance_id": "s0:u0", "source_sentence_id": "s0"}]
    assert doc.phases["intake"]["state"] == "read"
    assert doc.phases["resolution"]["state"] == "unread"
    assert doc.phases["fold"]["state"] == "unread"
    assert doc.phases["graph"]["state"] == "unread"


def test_fold_failure_does_not_destroy_resolved_document(simple_pipeline, monkeypatch):
    import gse.cassettes.multiscale as multiscale

    monkeypatch.setattr(multiscale, "resolve_document", lambda trees, *args, **kwargs: trees)

    def fail(*args, **kwargs):
        raise ValueError("fold failed")

    monkeypatch.setattr(multiscale, "read_fold", fail)
    doc = MultiScaleDoc("good.", Encoder(), object())
    assert doc.phases["resolution"]["state"] == "read"
    assert doc.phases["fold"]["state"] == "unread"
    assert doc.resolved == doc.sentence_trees
    assert len(doc.mentions) == 1


def test_graph_failure_is_independent_of_successful_fold(simple_pipeline, monkeypatch):
    import gse.cassettes.multiscale as multiscale
    from gse.symbolic.narrative import NarrativeGraph

    monkeypatch.setattr(multiscale, "resolve_document", lambda trees, *args, **kwargs: trees)

    def fail(*args, **kwargs):
        raise ValueError("graph failed")

    monkeypatch.setattr(NarrativeGraph, "from_document", fail)
    doc = MultiScaleDoc("good.", Encoder(), object())
    assert doc.phases["fold"]["state"] == "read"
    assert doc.phases["graph"]["state"] == "unread"
    assert len(doc.sentence_trees) == 1


def test_paragraph_view_keeps_whole_document_referent_and_antecedent(simple_pipeline, monkeypatch):
    import gse.cassettes.multiscale as multiscale

    monkeypatch.setattr(multiscale, "resolve_document", lambda trees, *args, **kwargs: trees)
    encoder = Encoder()
    doc = MultiScaleDoc("first.\n\nsecond.", encoder, object())
    calls = list(encoder.calls)
    view = doc.unit_view(paragraph_id="p1")
    assert view["source_sentence_ids"] == ["s1"]
    assert view["mentions"][0].eid == view["supporting_mentions"][0].eid == "alice"
    assert view["supporting_mentions"][0].source_sentence_id == "s0"
    assert encoder.calls == calls


def test_real_document_context_keeps_cross_paragraph_antecedent(monkeypatch):
    import gse.cassettes.multiscale as multiscale

    monkeypatch.setattr(multiscale, "_safe_store", lambda: None)
    doc = MultiScaleDoc("A woman smiled.\n\nShe ran.", GSEEncoder())
    view = doc.unit_view(paragraph_id="p1")
    assert doc.phases["resolution"]["state"] == "read"
    assert view["mentions"][0].eid == view["supporting_mentions"][0].eid
    assert view["supporting_mentions"][0].source_sentence_id == "s0"


def test_real_event_construction_witness_must_not_report_surviving_verb_lost():
    events = list(encode_document_utterance_events(GSEEncoder(), [("fixed", "Alice can run.")]))
    assert events[1]["state"] == "read"
    assert events[1]["structural_loss"] == []
    assert events[1]["verb_heads"][0]["state"] == "unique"
    assert events[1]["verb_heads"][0]["positions"] == [2]


@pytest.mark.parametrize(
    "text", ["A woman smiled.", "A woman smiled because she ran.", "Her dog barked.", "Alice and Bob ran."]
)
def test_source_resolution_preserves_default_bound_tree(text):
    from gse.symbolic import evaluate_tree, from_trace, resolve, resolve_with_sources
    from gse.symbolic.serialization import to_dict

    expression = from_trace(GSEEncoder().encode(text))
    pair = resolve_with_sources(expression)
    assert to_dict(evaluate_tree(pair["bound"])) == to_dict(evaluate_tree(resolve(expression)))


def test_source_entity_join_retains_local_pronoun_with_document_identity():
    from gse.symbolic import resolve_document

    outcomes = [
        event
        for event in encode_document_utterance_events(GSEEncoder(), [("a", "A woman smiled."), ("b", "She ran.")])
        if event["type"] == "utterance"
    ]
    resolved = resolve_document([event["tree"] for event in outcomes], None)
    origin = entity_source_evidence(outcomes[1]["trace"], outcomes[1]["source_tree"], resolved[1])["mentions"][0]
    assert origin["state"] == "read"
    assert origin["source_head"]["lemma"] == "she"
    assert origin["source_head"]["pos"] == "PRON"
    assert origin["source_head"]["position"] == 0
    assert origin["resolved_head"]["lemma"] == "woman"
    assert origin["entity_id"] is not None


def test_source_entity_join_retains_within_sentence_pronoun_before_binding():
    event = next(
        event
        for event in encode_document_utterance_events(GSEEncoder(), [("fixed", "A woman smiled because she ran.")])
        if event["type"] == "utterance"
    )
    origins = entity_source_evidence(event["trace"], event["source_tree"], event["tree"])
    assert origins["state"] == "read"
    pronouns = [row for row in origins["mentions"] if row["source_head"]["pos"] == "PRON"]
    assert len(pronouns) == 1
    assert pronouns[0]["source_head"]["lemma"] == "she"
    assert pronouns[0]["source_head"]["position"] == 4
    assert pronouns[0]["resolved_head"]["lemma"] == "woman"


def test_source_origin_failure_does_not_erase_primary_reading(simple_pipeline, monkeypatch):
    import gse.symbolic

    calls = []

    def evaluate(node):
        calls.append(node)
        if len(calls) == 2:
            raise ValueError("auxiliary source evaluation failed")
        return node

    monkeypatch.setattr(gse.symbolic, "evaluate_tree", evaluate)
    event = list(encode_document_utterance_events(Encoder(), [("fixed", "good")]))[1]
    assert event["state"] == "read" and event["tree"] is not None and event["error"] is None
    assert event["source_tree"] is None
    assert event["source_origins"] == {
        "state": "unread",
        "reason": "source_evaluation_error",
        "error_type": "ValueError",
    }


def test_source_entity_join_refuses_changed_path_and_does_not_count_copied_antecedent_children():
    trace = {"tokens": [{"position": 0, "lemma": "she", "token": "She"}]}
    source = {"_kind": "Event", "agent": {"_kind": "Entity", "head": {"lemma": "she", "position": 0}}}
    bound = {
        "_kind": "Event",
        "agent": {
            "_kind": "Entity",
            "head": {"lemma": "woman", "position": 1},
            "entity_id": "e0",
            "possessor": {"_kind": "Entity", "head": {"lemma": "bob"}},
        },
    }
    evidence = entity_source_evidence(trace, source, bound)
    assert evidence["state"] == "read" and len(evidence["mentions"]) == 1
    assert evidence["mentions"][0]["entity_id"] == "e0"
    changed = entity_source_evidence(trace, source, {"_kind": "Event", "patient": bound["agent"]})
    assert changed["state"] == "partial"
    assert changed["mentions"][0]["reason"] == "source_entity_path_changed"
    assert changed["mentions"][0]["entity_id"] is None
