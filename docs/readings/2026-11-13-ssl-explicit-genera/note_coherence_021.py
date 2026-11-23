"""Record the bounded 021 candidate outcome without authorizing publication."""

import argparse
import json
import os
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from GSE.curation.lexicon_builder.epoch import fingerprint, read, record

NOTES = Path(__file__).resolve().parent
ROOT = NOTES.parents[2]
PAPER = Path.home() / "Projects/rohan-vinaik.github.io/papers/Core Documents/Semantic_Specification_Learning/07_GSE_LEXICON_NSM_WORKING_DRAFT.md"
WORK = ROOT / "data/lexicon_builder/2026-11-12/ssl-explicit-genera/coherence-021"
HEADING = "#### Vertebrate body-template learning cycle\n"
BOUNDARY = "### 6. Linguistic and sociological implications\n"


def available(path):
    try:
        return read(path)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def install_section(section):
    original = PAPER.read_text()
    prefix, boundary, suffix = original.partition(BOUNDARY)
    if not boundary:
        raise ValueError("NOTEBOOK_RESULT_BOUNDARY_MISSING")
    if HEADING in prefix:
        raise ValueError("NOTEBOOK_CYCLE_SECTION_ALREADY_EXISTS_WITHOUT_RECEIPT")
    revised = prefix + section + boundary + suffix
    fd, name = tempfile.mkstemp(prefix=".gse-021-notebook-", dir=PAPER.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(revised)
            stream.flush()
            os.fsync(stream.fileno())
        if PAPER.read_text() != original:
            raise ValueError("NOTEBOOK_CHANGED_DURING_RESULT_INSTALLATION")
        os.replace(temporary, PAPER)
    finally:
        temporary.unlink(missing_ok=True)


def render_result(result):
    signs = Counter(
        (row["bank"], row["after"][0])
        for row in result["changes"]
        if len(row["before"]) > 1 and len(row["after"]) == 1
    )
    delta = ", ".join(f"{bank}={sign:+d}: {count:,}" for (bank, sign), count in sorted(signs.items())) or "none"
    audits = Counter()
    for epoch in result["epochs"]:
        audits.update(epoch.get("audit_outcomes", {}))
    audit_text = ", ".join(f"{key}: {count}" for key, count in sorted(audits.items())) or "no held-out audit outcome recorded"
    outcomes = ", ".join(epoch["code"] for epoch in result["epochs"])
    return f"""{HEADING}
The continuation rebased the source-reviewed vertebrate proposal on validated active 020 and ran the existing Zipf epoch controller. Its bounded construction used {result['typed_questions_used']} model questions. The epoch outcome was {outcomes}; held-out audit outcomes were {audit_text}. There were {len(result['admitted'])} admitted candidate rules. Audits record separate signed answers or abstentions; audit answers themselves write no lexical cells. [Frozen plan](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/021-coherence-plan.json) · [Source warrant and reserved taxa](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/021-vertebrate-source-review.json)

The replay-validated candidate has {result['new_cells']:,} new singleton assignments ({delta}) and {result['reopened_cells']:,} reopenings. Full replay checked {result['replay']['entries_checked']:,} records with complete search and {result['replay']['entries_mismatched']:,} mismatches. These are candidate results: this continuation performs no activation, and its gains are excluded from published release totals. Unknown domains remain explicit. Independent runtime and cumulative semantic checks, full publication replay and rolling retention are still required for a successor release. This round establishes no joint-support count or cross-epoch contraction rate. [Candidate result](../../../../gse/data/lexicon_builder/2026-11-12/ssl-explicit-genera/coherence-021/zipf/arm-result.json) · [Round status](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/021-round-status.json)

"""


def watch(producer):
    if (NOTES / "021-notebook-update.json").exists():
        print("COHERENCE_021_NOTEBOOK_ALREADY_RECORDED", flush=True)
        return
    if producer < 1:
        raise ValueError("INVALID_CONTINUATION_PRODUCER_PID")
    print("COHERENCE_021_NOTEBOOK_WAITING_FOR_VERIFIED_RESULT", flush=True)
    while True:
        status = available(NOTES / "021-round-status.json")
        failure = available(NOTES / "021-continuation-failure.json")
        if status and status.get("code") in {
            "CANDIDATE_REPLAY_VALIDATED_PENDING_PUBLICATION_REVIEW",
            "RULE_WITHHELD_CANDIDATE_REPLAY_VALIDATED",
        }:
            result = read(WORK / "zipf/arm-result.json")
            if (
                result["replay"]["code"] != "REPLAY_VALIDATED"
                or not result["replay"]["complete_search"]
                or fingerprint(Path(result["candidate"])) != result["candidate_sha256"]
            ):
                raise ValueError("NOTEBOOK_CANDIDATE_RECEIPT_INVALID")
            section = render_result(result)
            break
        if failure:
            section = (
                HEADING + "\nThe queued continuation stopped without a replay-validated round result. "
                "Its journal is retained and no candidate gain is added to published totals. "
                "[Failure record](../../../../gse/docs/readings/2026-11-13-ssl-explicit-genera/021-continuation-failure.json)\n\n"
            )
            break
        try:
            os.kill(producer, 0)
        except ProcessLookupError:
            raise ValueError("CONTINUATION_ENDED_WITHOUT_RESULT_RECORD") from None
        time.sleep(10)
    install_section(section)
    record(NOTES / "021-notebook-update.json", {
        "format": "GSE.experiment-notebook-update/1",
        "code": "CANDIDATE_OUTCOME_RECORDED_SEPARATELY_FROM_PUBLISHED_TOTALS",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "notebook": str(PAPER),
        "notebook_sha256": fingerprint(PAPER),
        "activation_performed": False,
    })
    print("COHERENCE_021_NOTEBOOK_UPDATED", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer", type=int, required=True)
    watch(parser.parse_args().producer)
