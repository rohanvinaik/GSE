"""F129: a rule writes cells only once Rohan has admitted it.

One MUST-NOT per path an unreviewed rule used to write through, each with a positive control
showing that admitting the same rule restores the projection, so no check passes vacuously.
"""

from __future__ import annotations

import copy

from gse.lexicon_builder.build import build
from gse.lexicon_builder.registry import load_rulebook
from tests.lexicon_rulebook import admitted_rulebook, withheld_rulebook


class FixtureSources:
    """Stands in for NativeSources: one fixed native record, no local data needed."""

    def __init__(self, native: dict):
        self.native = native

    def for_word(self, word: str) -> dict:
        return copy.deepcopy(self.native)


def native(usas=(), framenet=(), verbnet=()) -> dict:
    empty = {"status": "NO_RECORD", "scope": "WORD", "units": "fixture", "records": []}
    record = {s: copy.deepcopy(empty) for s in ("concreteness", "lancaster", "vad", "emotion")}
    record["usas"] = {**empty, "records": list(usas)}
    record["framenet"] = {**empty, "records": list(framenet)}
    record["verbnet"] = {**empty, "records": list(verbnet)}
    return record


FEELING_ADJECTIVE = native(
    usas=[{"record_id": "external:usas:1", "values": {"lemma": "fixture", "pos": "ADJ", "alternatives": ["E4.1+"]}}],
    framenet=[{"record_id": "nltk:lu:1", "values": {"pos": "a", "frame": "Emotion_directed", "frame_id": "1"}}],
)


def frame(*predicates: str) -> dict:
    args = [{"type": "Event", "value": "during(E)"}, {"type": "ThemRole", "value": "Theme"}]
    return {
        "class": "fixture-1",
        "frame_index": 0,
        "predicates": [{"predicate": {"value": p}, "arguments": args} for p in predicates],
    }


def verb(*predicates: str, usas_tags=()) -> dict:
    membership = {"record_id": "nltk:verbnet:fixture", "values": {"class": "fixture-1", "frames": [frame(*predicates)]}}
    usas = [
        {"record_id": "external:usas:2", "values": {"lemma": "fixture", "pos": "VERB", "alternatives": list(usas_tags)}}
    ]
    return native(usas=usas if usas_tags else (), verbnet=[membership])


class CountingSelector:
    def __init__(self, answer: str):
        self.answer, self.calls = answer, 0

    def select(self, payload, options):
        self.calls += 1
        return {"request_sha256": f"admission-test-{self.calls}", "answer": {key: self.answer for key in options}}


def run(native_record: dict, book: dict, selector=None) -> dict:
    return next(build(["fixture"], FixtureSources(native_record), book, selector))


def test_an_unadmitted_source_rule_writes_no_restriction_companion_or_fact():
    record = run(FEELING_ADJECTIVE, load_rulebook())
    assert record["readings"][0]["source_scope"] == "LEMMA_POS_HEAD_CONTRACT"
    assert not {"FEEL", "GOOD", "INTENSITY"} & set(record["readings"][0]["symbolic_before"]["forced"])
    (withheld,) = record["withheld_unadmitted_writes"]
    assert withheld["rule_ids"] == ["USAS_OWN_HAPPY_SAD_STATE"]
    assert withheld["would_write"] == {"GOOD": "+1", "FEEL": "+1"}  # restriction and companion
    assert ["own_denotatum", "affective_feeling"] in withheld["would_assert"]  # facts admitted laws would consume


def test_admitting_the_same_source_rule_restores_every_path():
    record = run(FEELING_ADJECTIVE, admitted_rulebook("USAS_OWN_HAPPY_SAD_STATE"))
    (reading,) = record["readings"]
    forced = reading["symbolic_before"]["forced"]
    assert forced["GOOD"] == "+1"  # the rule's own restriction
    assert forced["FEEL"] == "+1"  # its companion
    assert forced["INTENSITY"] == "+1" and forced["SOMETHING"] == "0" and forced["KIND"] == "0"  # its facts, via laws
    assert record["withheld_unadmitted_writes"] == []


def test_an_unadmitted_verbnet_predicate_rule_writes_no_cell():
    record = run(verb("motion"), withheld_rulebook("VN_EVENT_MOTION"))
    assert record["readings"] == []
    assert record["code"] == "PARTIAL_UNADMITTED_RULES_ONLY"
    (withheld,) = record["withheld_unadmitted_writes"]
    assert withheld["rule_ids"] == ["VN_EVENT_MOTION"]
    assert withheld["would_write"] == {"MOVE": ["+1"]}
    live = run(verb("motion"), load_rulebook())  # approved in F144 and live
    assert live["readings"][0]["symbolic_before"]["forced"]["MOVE"] == "+1"


def test_an_unadmitted_perception_rule_writes_nothing_and_asks_no_model():
    ambiguous = verb("perceive", usas_tags=("X3.2", "X3.4"))
    selector = CountingSelector("VISION")
    record = run(ambiguous, withheld_rulebook("VN_USAS_PERCEPTION_MODE"), selector)
    assert selector.calls == 0
    assert not {"SEE", "HEAR"} & set(record["readings"][0]["symbolic_before"]["forced"])
    (withheld,) = record["withheld_unadmitted_writes"]
    assert withheld["model_decision_withheld"] is True
    assert withheld["would_write"] == {}
    live = run(ambiguous, load_rulebook(), selector)  # approved in F144 and live
    assert selector.calls == 1
    assert live["readings"][0]["after_selection"]["forced"]["SEE"] == "+1"


def test_a_word_no_rule_matches_is_not_reported_as_awaiting_review():
    record = run(native(), load_rulebook())
    assert record["code"] == "PARTIAL_NO_APPLICABLE_RULE"
    assert record["withheld_unadmitted_writes"] == []
