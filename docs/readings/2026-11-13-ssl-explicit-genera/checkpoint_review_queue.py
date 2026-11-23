"""Refine a gap proposal and expose distinct-spelling, exact-source review cases."""

from __future__ import annotations

import json
from pathlib import Path

from gse.curation.lexicon_builder.completion import _priority_source
from gse.curation.lexicon_builder.epoch import Family, _sense_group, census, fingerprint, forecast, record, scope_rows

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / "data/lexicon_builder/2026-11-12/sparse-release-021.db"


def main():
    priority, frequencies = _priority_source("zipf", None)
    family = Family(
        "explicit-human-person-genus-body", None, ("BODY", 1),
        (("pos", "noun"), ("wordnet_native_lemma", "true"),
         ("wordnet_ancestor:person.n.01", "true"), ("native_noun_frame:explicit_person", "true")), (),
        {"kind": "DEFINITIONAL_DERIVATION", "warrant_id": "gap-refinement:explicit-human-person-genus-body",
         "review_id": "UNADMITTED_REQUIRES_SEMANTIC_AUDITS", "reviewer": "PROPOSAL_ONLY",
         "statement": "Test constitutive BODY on an exact native human noun whose own gloss has an explicit "
         "person genus, with ALIVE and SOMEONE already justified. This positive defining-head condition "
         "reserves title-denoting and merely metonymic descriptions without assigning them an opposing value.",
         "source_refs": [str(HERE / "021-body-convention-approval.json"),
                         str(HERE / "gap-constitutive-human-person-body-stage.json")]},
        premises=(("ALIVE", 1), ("SOMEONE", 1)))
    inventory = census(BASE, {family.id: family})[family.id]
    rules, rows = scope_rows(BASE, inventory)
    stage = forecast(rows, rules, (family.relation(),))
    record(HERE / "gap-explicit-human-person-genus-body-stage.json", {
        "code": "UNADMITTED_POSITIVE_GENUS_REFINEMENT", "family": family.proposal(),
        "definitions": [{**r, "definition": rows[r["entry_id"]][0].definition} for r in inventory], **stage})
    report = {"code": "SOURCE_GAP_REVIEW_QUEUE_NOT_ADMISSION", "frequency_source": priority,
              "ordering": "DISTINCT_NATIVE_SENSE_AND_DISTINCT_SPELLING_PER_REVIEW_ROUND",
              "frequency_semantics": "SPELLING_ORDER_ONLY_NOT_SENSE_FREQUENCY",
              "refinement": {"family": family.id, "scope_definitions": len(rows),
                             "native_sense_groups": len({_sense_group(r) for r in inventory}),
                             "provisional_new_singletons": sum(len(r["before"]) > 1 and len(r["after"]) == 1
                                                                 for r in stage["changes"]),
                             "formal_contradictions": len(stage["contradictions"])},
              "families": []}
    for name in ("constitutive-human-person-body", "physical-contact-touch", "repeated-light-contact-touch",
                 "collision-touch", "possess-have", "concrete-or-abstract-possession-have"):
        proposal = json.loads((HERE / ("gap-" + name + "-stage.json")).read_text())
        ordered = sorted(proposal["definitions"], key=lambda r: (-frequencies.get(r["lemma"].casefold(), 0), r["entry_id"]))
        senses, spellings, cases = set(), set(), []
        for item in ordered:
            spelling = item["lemma"].casefold()
            if item["synset"] in senses or spelling in spellings:
                continue
            senses.add(item["synset"])
            spellings.add(spelling)
            cases.append({k: item[k] for k in ("entry_id", "lemma", "definition", "source_sha256", "bank_domain")}
                         | {"subtlex_spelling_count": frequencies.get(spelling, 0)})
            if len(cases) == 12:
                break
        report["families"].append({"family": name, "scope_definitions": len(ordered), "review_candidates": cases,
                                   "rare_sense_and_name_review": "REQUIRED_BEFORE_TEACHER_SELECTION"})
    report["baseline_sha256"] = fingerprint(BASE)
    report["code_sha256"] = fingerprint(Path(__file__))
    record(HERE / "checkpoint-proposal-review-queue-v2.json", report)
    print(json.dumps(report["refinement"], indent=2))


if __name__ == "__main__":
    main()
