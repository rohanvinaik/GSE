"""Stage source-witnessed gap hypotheses; legacy signs never enter the resolver."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

from GSE.curation.lexicon_builder.epoch import Family, census, fingerprint, forecast, record, scope_rows

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / "data/lexicon_builder/2026-11-12/sparse-release-021.db"

# The roots below are proposal scopes, not admissions. Every root's native
# definition is retained, together with all scoped definitions and their domains.
SPECS = (
    ("emotion-feel", "emotion.n.01", "noun", "FEEL",
     "Emotion denotes a feeling; test whether verified defining-genus content warrants FEEL=+1 on this scope."),
    ("desire-want", "desire.v.01", "verb", "WANT",
     "Desiring entails wanting; test the exact native desire branch, reserving need/lack and lexicalized figurative uses."),
    ("physical-contact-touch", "touch.v.01", "verb", "TOUCH",
     "Making physical contact supplies touching content; test senses for figurative contact, resultant state and instrument boundaries."),
    ("possess-have", "own.v.01", "verb", "HAVE",
     "Owning entails having; test the exact native ownership branch rather than every occurrence of the word have."),
    ("repeated-light-contact-touch", "stroke.v.01", "verb", "TOUCH",
     "Repeated light touching supplies contact content; test this child independently of the overbroad contact parent."),
    ("collision-touch", "hit.v.02", "verb", "TOUCH",
     "Sudden physical contact supplies touching content; test the collision child and retain metaphorical boundary cases."),
    ("concrete-or-abstract-possession-have", "have.v.01", "verb", "HAVE",
     "The native have/possess branch proposes possession content; inspect experiential and relational descendants before admission."),
)


def definition_order(record):
    value = record["spelling_weight"]
    if value is None:
        weight = 0.0
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        weight = float(value)
    else:
        raise ValueError("INVALID_SPELLING_WEIGHT")
    return -weight, record["entry_id"]


def main():
    baseline_sha256 = fingerprint(BASE)
    code_sha256 = fingerprint(Path(__file__))
    families = {}
    for name, ancestor, pos, bank, explanation in SPECS:
        families[name] = Family(name, None, (bank, 1),
                                (("pos", pos), ("wordnet_native_lemma", "true"),
                                 ("wordnet_ancestor:" + ancestor, "true")), (),
                                {"kind": "DEFINITIONAL_DERIVATION", "warrant_id": "gap-hypothesis:" + name,
                                 "review_id": "UNADMITTED_REQUIRES_SOURCE_REVIEW_AND_AUDITS",
                                 "reviewer": "PROPOSAL_ONLY", "statement": explanation,
                                 "source_refs": ["wordnet:" + ancestor,
                                                 str(HERE / "checkpoint-and-legacy-hypotheses.md")]})
    families["constitutive-human-person-body"] = Family(
        "constitutive-human-person-body", None, ("BODY", 1),
        (("pos", "noun"), ("wordnet_native_lemma", "true"),
         ("wordnet_ancestor:person.n.01", "true")), (),
        {"kind": "DEFINITIONAL_DERIVATION", "warrant_id": "gap-hypothesis:constitutive-human-person-body",
         "review_id": "UNADMITTED_REQUIRES_SOURCE_REVIEW_AND_AUDITS", "reviewer": "PROPOSAL_ONLY",
         "statement": "Under the approved constitutive-anatomy convention, test whether ALIVE and SOMEONE "
         "on an exact native human-person noun witness bodily constitution through the defining genus. "
         "Pronominal reference alone supplies no BODY assertion; the native nominal genus is essential.",
         "source_refs": [str(HERE / "021-body-convention-approval.json"), "wordnet:person.n.01",
                         str(ROOT / "docs/program/LEXICON_CONSTRUCTION_DESIGN.md")]},
        premises=(("ALIVE", 1), ("SOMEONE", 1)))
    inventory = census(BASE, families)
    legacy = sqlite3.connect(f"file:{ROOT / 'data/lexicon_clean.db'}?mode=ro", uri=True)
    conn = sqlite3.connect(f"file:{BASE}?mode=ro", uri=True)
    summaries, union = [], {}
    try:
        for name, family in families.items():
            rules, rows = scope_rows(BASE, inventory[name])
            stage = forecast(rows, rules, (family.relation(),))
            union.update(rows)
            definitions = []
            for item in inventory[name]:
                entry = item["entry_id"]
                d, _, _, _, domains = rows[entry]
                old = [list(r) for r in legacy.execute(
                    "SELECT p.primitive,p.value FROM lexemes l JOIN primitive_values p ON p.lexeme_id=l.id "
                    "WHERE lower(l.lemma)=lower(?) AND p.primitive=? ORDER BY l.id", (d.lemma, family.consequent[0]))]
                rank, weight = conn.execute("SELECT frequency_rank,frequency_weight FROM lexemes "
                                           "JOIN definition_states d ON d.lexeme_id=lexemes.id WHERE d.entry_id=?",
                                           (entry,)).fetchone()
                definitions.append({**item, "definition": d.definition, "bank_domain": domains[family.consequent[0]],
                                    "frequency_rank": rank, "spelling_weight": weight,
                                    "legacy_spelling_suggestions": old,
                                    "legacy_identity_status": "SPELLING_ONLY_NOT_SENSE_MATCHED"})
            definitions.sort(key=definition_order)
            report = {"code": "UNADMITTED_GAP_HYPOTHESIS_STAGE", "family": family.proposal(),
                      "definitions": definitions, **stage}
            record(HERE / ("gap-" + name + "-stage.json"), report)
            summaries.append({"family": name, "bank": family.consequent[0], "scope_definitions": len(rows),
                              "native_sense_groups": len({r["synset"] for r in inventory[name]}),
                              "target_domain_populations": dict(Counter(str(d["bank_domain"]) for d in definitions)),
                              "provisional_new_singletons": sum(len(c["before"]) > 1 and len(c["after"]) == 1
                                                                  for c in stage["changes"]),
                              "reopened_cells": sum(len(c["before"]) == 1 and len(c["after"]) > 1
                                                    for c in stage["changes"]),
                              "formal_contradictions": len(stage["contradictions"]),
                              "legacy_target_spelling_matches": sum(bool(d["legacy_spelling_suggestions"]) for d in definitions),
                              "report": str(HERE / ("gap-" + name + "-stage.json"))})
            print(json.dumps(summaries[-1]), flush=True)
        joint = forecast(union, rules, tuple(f.relation() for f in families.values()))
        if fingerprint(BASE) != baseline_sha256 or fingerprint(Path(__file__)) != code_sha256:
            raise ValueError("GAP_STAGE_FROZEN_INPUT_CHANGED")
        record(HERE / "gap-hypotheses-expanded-joint-stage.json", joint)
        record(HERE / "gap-hypotheses-expanded-summary.json", {
            "code": "UNADMITTED_GAP_HYPOTHESES_NO_BANK_WRITES",
            "baseline_sha256": baseline_sha256, "code_sha256": code_sha256,
            "baseline": str(BASE), "baseline_rule_version": json.loads(conn.execute(
                "SELECT value FROM builder_metadata WHERE key='rule_version'").fetchone()[0]),
            "families": summaries, "joint_definitions": len(union),
            "joint_new_singletons": sum(len(c["before"]) > 1 and len(c["after"]) == 1 for c in joint["changes"]),
            "joint_reopened_cells": sum(len(c["before"]) == 1 and len(c["after"]) > 1 for c in joint["changes"]),
            "joint_formal_contradictions": len(joint["contradictions"]),
            "bank_assignments_written": 0, "model_questions": 0,
            "legacy_role": "DISCOVERY_SUGGESTIONS_ONLY_NO_ASSERTIONS", "semantic_admission": "PENDING"})
    finally:
        conn.close()
        legacy.close()


if __name__ == "__main__":
    main()
