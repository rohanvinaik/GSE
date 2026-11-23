"""A legacy bank-fill request cannot bypass task-type review or fabricate closure."""

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


def test_withheld_fear_selection_cannot_be_bypassed_by_bank_fill():
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
    assert reading["code"] == "PARTIAL"
    assert reading["candidate_vector"] is None
    assert selector.calls == []
    assert {d["code"] for d in reading["decisions"]} == {"UNADMITTED_BANK_FILL"}
    assert reading["after_selection"]["domains"]["THEN"] == ["-1", "0", "empty"]
    assert "0" in reading["after_selection"]["domains"]["DO"]
    assert reading["after_selection"]["domains"]["MAYBE"] == ["+1", "empty"]


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
