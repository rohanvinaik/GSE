"""The rules fix what they can; every cell they leave open is filled one bank per call.

The model sees exactly the states the rules leave, written 0 included (F078, F158), and every answer
is solved again before the next bank.
"""

from __future__ import annotations

import copy

from gse.lexicon_builder.build import construct, source_matches
from gse.lexicon_builder.fill import usas_type
from gse.lexicon_builder.registry import load_rulebook


def native(tag: str, frame: str) -> dict:
    empty = {"status": "NO_RECORD", "scope": "WORD", "units": "fixture", "records": []}
    record = {s: copy.deepcopy(empty) for s in ("concreteness", "lancaster", "vad", "emotion", "verbnet")}
    record["usas"] = {
        **empty,
        "records": [{"record_id": "usas:1", "values": {"lemma": "afraid", "pos": "ADJ", "alternatives": [tag]}}],
    }
    record["framenet"] = {**empty, "records": [{"record_id": "fn:1", "values": {"pos": "a", "frame": frame}}]}
    return record


class BankSelector:
    """Answers silent unless told otherwise, and records what each call offered."""

    def __init__(self, answers: dict[str, str] | None = None):
        self.answers = answers or {}
        self.calls: list[tuple[dict, dict]] = []

    def select(self, payload: dict, options: dict) -> dict:
        self.calls.append((payload, options))
        answer = {key: self.answers.get(key, "empty") for key in options}
        return {"request_sha256": f"fill-{len(self.calls)}", "answer": answer}


def test_a_fear_adjective_gets_its_template_from_rules_and_the_rest_by_bank():
    book, record = load_rulebook(), native("E5-", "Fear")
    (match,) = source_matches(record, book)
    assert match["rule"]["rule_id"] == "EMOTION_FEAR_ADJ"
    selector = BankSelector({"THEN": "-1", "WANT": "+1"})
    reading = construct("afraid", match, record, book, selector, fill_labels={})
    forced = reading["symbolic_before"]["forced"]
    assert {c: forced[c] for c in ("FEEL", "THINK", "LIKE", "WHEN", "BECAUSE", "CAN", "HAPPEN")} == dict.fromkeys(
        ("FEEL", "THINK", "LIKE", "WHEN", "BECAUSE", "CAN", "HAPPEN"), "+1"
    )
    assert forced["GOOD"] == "-1" and forced["SOMETHING"] == "0" and forced["KIND"] == "0"
    assert reading["code"] == "CANDIDATE_COMPLETE"
    states = reading["candidate_vector"]["states"]
    assert states["THEN"] == "-1"  # a signed option reaches the model: "now"
    assert states["WANT"] == "+1"
    banks = [payload["bank"] for payload, _ in selector.calls]
    assert len(banks) == len(set(banks))  # one call per bank
    for payload, options in selector.calls:
        assert payload["definition_scope"].startswith("THE_FEELING_AND_THE_PROTOTYPICAL_THOUGHT")
        for coordinate, values in options.items():
            assert coordinate not in forced
            assert "0" in values  # a written 0 that survives the rules is offered (F078, F158)
            assert values[0] == "empty"


def test_without_a_selector_the_open_cells_stay_open():
    book, record = load_rulebook(), native("E5-", "Fear")
    (match,) = source_matches(record, book)
    reading = construct("afraid", match, record, book, None, fill_labels={})
    assert reading["code"] == "PARTIAL"
    assert reading["candidate_vector"] is None


def test_a_courage_tag_or_another_frame_does_not_match_the_fear_rule():
    book = load_rulebook()
    assert [m["rule"]["rule_id"] for m in source_matches(native("E5+", "Fear"), book)] == []
    assert [m["rule"]["rule_id"] for m in source_matches(native("E5-", "Emotion_directed"), book)] == []


def test_a_usas_tag_is_typed_with_its_category_label_and_scale_side():
    labels = {"E5": "Fear/bravery/shock"}
    assert usas_type("E5-", labels) == {"tag": "E5-", "category": "E5", "label": "Fear/bravery/shock", "scale": "-"}
    assert usas_type("A5.1+++", {})["scale"] == "+++"
    assert usas_type("Z99", {})["label"] is None
