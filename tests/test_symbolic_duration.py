"""Sentence duration through the normal encoder, symbolic tree and emit contract."""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import evaluate_tree, from_dict, from_trace, is_logically_equal_to, resolve, to_dict
from gse.symbolic.duration import Duration
from gse.symbolic.emit import emit_contract
from gse.symbolic.serialization import SerializationError


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as encoder:
        yield encoder


def _read(encoder, sentence):
    expr = from_trace(encoder.encode(sentence))
    assert from_dict(to_dict(expr)) == expr
    predicate = evaluate_tree(resolve(expr))
    assert from_dict(to_dict(predicate)) == predicate
    return predicate


def test_duration_distinguishes_extent_from_no_qualifier(encoder):
    plain = _read(encoder, "I waited.")
    some = _read(encoder, "I waited for some time.")
    short = _read(encoder, "I waited for a short time.")
    long = _read(encoder, "I waited for a long time.")
    assert plain.duration is None
    assert [node.duration for node in (some, short, long)] == [
        Duration("unspecified", "during"),
        Duration("short", "during"),
        Duration("long", "during"),
    ]
    assert all(node.patient is None for node in (plain, some, short, long))
    assert not is_logically_equal_to(some, plain)
    assert not is_logically_equal_to(some, long)
    assert is_logically_equal_to(some, _read(encoder, "For some time, I waited."))
    assert emit_contract(some)["predicate"]["features"]["duration"] == {"extent": "unspecified", "relation": "during"}


def test_duration_keeps_negation_and_scope_on_its_own_clause(encoder):
    negated = _read(encoder, "I didn't wait for a long time.")
    assert negated.operand.duration == Duration("long", "during")
    assert emit_contract(negated)["predicate"]["op"] == "NOT"
    controlled = _read(encoder, "I decided to wait for some time.")
    assert controlled.duration is None
    assert controlled.inner.duration == Duration("unspecified", "during")
    state = _read(encoder, "I was ill for some time.")
    assert type(state).__name__ == "TypeAssertion"
    assert state.duration == Duration("unspecified", "during")


def test_temporal_offset_and_event_duration_have_different_owners(encoder):
    before = _read(encoder, "I left some time before he spoke.")
    after = _read(encoder, "Some time after he spoke, I left.")
    assert before.duration == Duration("unspecified", "before")
    assert after.duration == Duration("unspecified", "after")
    assert before.event.verb == after.event.verb == "leave"
    assert before.setting.verb == after.setting.verb == "speak"
    assert before.event.patient is None
    assert not is_logically_equal_to(before, after)
    event_duration = _read(encoder, "I waited for some time before he spoke.")
    assert event_duration.conjunction == "before"
    assert event_duration.duration is None
    assert event_duration.event.duration == Duration("unspecified", "during")


def test_duration_abstains_on_nominal_and_incomplete_attachments(encoder):
    for sentence in ("I needed some time.", "I signed a lease for a long time.", "I waited for some."):
        node = _read(encoder, sentence)
        assert node.duration is None


@pytest.mark.parametrize(
    "value",
    [None, {}, {"extent": 0, "relation": "during"}, {"extent": "unspecified", "relation": "after"}],
)
def test_duration_rejects_invalid_scope_or_encoding(encoder, value):
    payload = to_dict(_read(encoder, "I waited for some time."))
    payload["duration"] = value
    with pytest.raises(SerializationError, match="INVALID_DURATION"):
        from_dict(payload)
