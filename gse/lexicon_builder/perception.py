"""One native perception function; modality supplied by a second typed view."""

from __future__ import annotations

from gse.lexicon_builder.core import Cell, Law
from gse.lexicon_builder.model import OllamaSelector
from gse.lexicon_builder.reading import ask, model_task_status

PERCEPTION_RULE = "VN_USAS_PERCEPTION_MODE"


def perception_constraints(
    word: str, frame: dict, native: dict, rulebook: dict, selector: OllamaSelector | None, cache: dict
) -> dict:
    rule = next((r for r in rulebook.get("native_residual_rules", []) if r["rule_id"] == PERCEPTION_RULE), None)
    if rule is None:
        return {"laws": [], "calls": [], "decisions": []}
    predicates = [
        p
        for p in frame["predicates"]
        if p["predicate"]["value"] == rule["native_predicate"] and p["predicate"].get("bool") != "!"
    ]
    if not predicates:
        return {"laws": [], "calls": [], "decisions": []}
    modes = set()
    witnesses = []
    for record in native["usas"]["records"]:
        row = record["values"]
        if row["pos"] != rule["source_pos"]:
            continue
        for alternative in row["alternatives"]:
            for category in alternative.split("/"):
                # Native negative-scale categories are not positive perception
                # assertions and do not license a blind pole flip.
                mode = rule["category_modes"].get(category.rstrip("+"))
                if mode:
                    modes.add(mode)
                    witnesses.append({"record_id": record["record_id"], "category": category})
    calls = []
    code = next(iter(modes)) if len(modes) == 1 else "UNRESOLVED"
    admission = model_task_status(rule.get("model_selection_policy"), "SEE")
    if admission == "ADMITTED_MODEL_TASK_TYPE":
        admission = model_task_status(rule.get("model_selection_policy"), "HEAR")
    if code == "UNRESOLVED" and selector is not None and admission == "ADMITTED_MODEL_TASK_TYPE":
        payload = {
            "schema": "GSE_PERCEPTION_MODE_V1",
            "word": word,
            "pos": "VERB",
            "function": "NATIVE_PERCEPTION",
            "native_predicates": predicates,
            "native_categories": {s: [r["values"] for r in native[s]["records"]] for s in ("usas", "framenet")},
            "decision": {"PERCEPTION_MODE": None},
            "mode_requires": "INHERENT_TO_THE_LOCATED_DEFINITION; NO_INCIDENTAL_OR_POSSIBLE_CHANNEL",
            "typed_anchors": rule["typed_anchors"],
        }
        options = sorted(modes) + ["UNRESOLVED"] if modes else rule["residual_options"]
        call = ask("PERCEPTION_MODE", options, payload, selector, cache)
        calls.append(call)
        code = call["answer"]["PERCEPTION_MODE"]
    coordinate = rule["mode_coordinates"].get(code)
    laws = (
        []
        if coordinate is None
        else [Law(rule["rule_id"] + ":" + code, (coordinate,), ((Cell.PLUS,),), (), rule["warrant"])]
    )
    return {
        "laws": laws,
        "calls": calls,
        "decisions": [
            {
                "function": "perception",
                "mode": code,
                "coordinate": coordinate,
                "witnesses": witnesses,
                "authority": "MODEL_CANDIDATE" if calls else "TYPED_SOURCE_CONJUNCTION",
                **({"selection_status": admission} if selector is not None and code == "UNRESOLVED" else {}),
            }
        ],
    }
