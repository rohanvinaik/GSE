"""Reports retain their attributed content without committing to its truth."""

import pytest

from GSE.api import GSEEncoder
from GSE.discourse.speech import encode_document_utterance_events
from GSE.symbolic import evaluate_tree, from_trace, resolve, resolve_document
from GSE.symbolic.inference import KnowledgeBase
from GSE.symbolic.modality import _CLAUSAL_COMPLEMENT_KINDS, assertion_mode
from GSE.symbolic.narrative import NarrativeGraph
from GSE.symbolic.propositions import commitment, commitment_modes, polarity, proposition_status, propositions


@pytest.fixture(scope="module")
def encoder():
    return GSEEncoder()


@pytest.mark.parametrize("verb", ["say", "tell", "report", "claim", "assert", "state", "announce", "declare", "allege"])
@pytest.mark.parametrize("kind", sorted(_CLAUSAL_COMPLEMENT_KINDS))
def test_reported_clauses_never_become_facts_by_their_predicate_kind(verb, kind):
    assert assertion_mode("Event", verb, kind) == "reported"


@pytest.mark.parametrize("kind", ["Entity", "Atom", "Phrase", "Coordination", "NoneType", "", "unknown"])
def test_reporting_verb_does_not_impose_clause_scope_on_an_entity(kind):
    assert assertion_mode("Event", "say", kind) == "asserted"


def test_reporting_scope_does_not_expand_the_ruled_factive_class():
    assert assertion_mode("Event", "know", "Event") == "epistemic"
    assert assertion_mode("Event", "believe", "Event") == "belief"
    assert assertion_mode("Control", "tell", "Event") == "asserted"
    assert assertion_mode("Event", "discover", "Event") == "asserted"
    assert assertion_mode("", "", "") == "asserted"


@pytest.mark.parametrize(
    "text,matrix,content,status,sign",
    [
        ("Alice says that Bob left.", "committed", "non_committed", "reported", 1),
        ("Alice did not say that Bob left.", "committed", "abstained", "abstained", 1),
        ("Alice says that Bob did not leave.", "committed", "non_committed", "reported", -1),
        ("Alice might say that Bob left.", "non_committed", "non_committed", "possible", 1),
    ],
)
def test_public_encoder_retains_matrix_and_local_negation_with_report_scope(
    encoder, text, matrix, content, status, sign
):
    tree = evaluate_tree(resolve(from_trace(encoder.encode(text))))
    by_verb = {p.node.verb: p for p in propositions(tree) if p.kind == "Event"}
    assert set(by_verb) == {"say", "leave"}
    assert commitment(by_verb["say"]) == matrix
    report = by_verb["leave"]
    assert commitment(report) == content
    assert report.status == status
    assert polarity(report).clause_sign == sign
    scope = next(scope for scope in report.scopes if scope.mode == "reported")
    assert scope.owner is by_verb["say"].node and scope.field == "patient"


def test_negated_report_is_unknown_content_not_an_inverted_fact():
    assert proposition_status(["negated", "reported"]) == "abstained"
    assert commitment_modes(("negated", "reported")) == "abstained"
    assert commitment_modes(("reported", "negated")) == "non_committed"
    assert commitment_modes(("reported", "epistemic")) == "non_committed"
    assert commitment_modes(("epistemic",)) == "committed"


def test_real_document_knowledge_base_and_narrative_do_not_promote_reported_content(encoder):
    events = list(encode_document_utterance_events(encoder, ["Alice says that Bob left.", "Bob stayed."]))
    utterances = [event for event in events if event["type"] == "utterance"]
    assert len(utterances) == 2 and all(event["state"] == "read" for event in utterances)
    trees = resolve_document([event["tree"] for event in utterances], None)
    kb = KnowledgeBase.from_trees(trees)
    assert kb.event("say", "alice").state == "entailed"
    assert kb.event("leave", "bob").state == "not_entailed"
    assert kb.event("stay", "bob").state == "entailed"
    graph = NarrativeGraph.from_document(trees)
    assert not any(edge.rel == "leave" for edge in graph.edges)
    report = next(edge for edge in graph.edges if edge.rel == "say")
    assert report.themes == ("leave",)


def test_know_still_commits_content_through_public_encoder_and_kb(encoder):
    tree = evaluate_tree(resolve(from_trace(encoder.encode("Alice knows that Bob left."))))
    claims = {p.node.verb: p for p in propositions(tree) if p.kind == "Event"}
    assert commitment(claims["leave"]) == "committed"
    assert KnowledgeBase.from_trees([tree]).event("leave", "bob").state == "entailed"


def test_negated_matrix_report_is_retained_in_story_without_negative_content(encoder):
    tree = evaluate_tree(resolve(from_trace(encoder.encode("Alice did not say that Bob left."))))
    graph = NarrativeGraph.from_document(resolve_document([tree], None))
    assert not any(edge.rel == "leave" for edge in graph.edges)
    report = next(edge for edge in graph.edges if edge.rel == "say")
    assert report.negated is True and report.themes == ("leave",)
