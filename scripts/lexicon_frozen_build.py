"""Frozen-build comparison for the lexicon gate: the source lock first, then the outputs.

    lexicon_frozen_build.py check <build-dir> <gate-dir>
    lexicon_frozen_build.py write <build-dir> <gate-dir>

A check returns a named outcome. IDENTICAL and KEY_ORDER_ONLY pass, since key order is not
part of the output contract. CHANGED and DATA_CHANGED fail; the complete list of differing
words or source files is written to <build-dir>/frozen_report.json. Source files are keyed by
their portable IDs, so the lock and the baseline hold on any machine with the same sources.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

EXIT_CODES = {"IDENTICAL": 0, "KEY_ORDER_ONLY": 0, "CHANGED": 1, "DATA_CHANGED": 3}


def source_lock(manifest: dict) -> dict:
    """Each source's status and files by portable ID; a machine path is not identity."""
    return {
        s["source"]: {"status": s["status"], "files": {f["id"]: f["sha256"] for f in s["files"]}}
        for s in manifest["sources"]
    }


def fingerprint(build: Path) -> dict:
    """Byte hashes of the outputs, plus each word record's hash as key-order-free JSON."""
    raw = build.joinpath("words.jsonl").read_bytes()
    records = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    return {
        "words_sha256": hashlib.sha256(raw).hexdigest(),
        "summary_sha256": hashlib.sha256(build.joinpath("summary.json").read_bytes()).hexdigest(),
        "words": [r["word"] for r in records],
        "record_sha256": [
            hashlib.sha256(json.dumps(r, sort_keys=True, ensure_ascii=False).encode()).hexdigest() for r in records
        ],
    }


def frozen_status(baseline: dict, current: dict, expected_lock: dict, current_lock: dict) -> str:
    """Named outcome of one comparison. MUST-NOT: report a source-data change as a code change."""
    if current_lock != expected_lock:
        return "DATA_CHANGED"
    same_summary = current["summary_sha256"] == baseline["summary_sha256"]
    if same_summary and current["words_sha256"] == baseline["words_sha256"]:
        return "IDENTICAL"
    if same_summary and current["words"] == baseline["words"] and current["record_sha256"] == baseline["record_sha256"]:
        return "KEY_ORDER_ONLY"
    return "CHANGED"


def report(status: str, baseline: dict, current: dict, expected_lock: dict, current_lock: dict) -> dict:
    """Every difference, never a sample."""
    if status == "DATA_CHANGED":
        sources = {}
        for name in sorted(set(expected_lock) | set(current_lock)):
            then, now = expected_lock.get(name, {}), current_lock.get(name, {})
            if then != now:
                old, new = then.get("files", {}), now.get("files", {})
                sources[name] = {
                    "status": [then.get("status"), now.get("status")],
                    "added": sorted(set(new) - set(old)),
                    "removed": sorted(set(old) - set(new)),
                    "changed": sorted(f for f in set(old) & set(new) if old[f] != new[f]),
                }
        return {"status": status, "sources": sources}
    pairs = zip(baseline["words"], baseline["record_sha256"], current["words"], current["record_sha256"])
    return {
        "status": status,
        "summary_changed": current["summary_sha256"] != baseline["summary_sha256"],
        "word_list_changed": current["words"] != baseline["words"],
        "changed_records": [word for word, old, new_word, new in pairs if word == new_word and old != new],
        "baseline_records": len(baseline["words"]),
        "current_records": len(current["words"]),
    }


def main(argv: list[str]) -> int:
    command, build, gate = argv[1], Path(argv[2]), Path(argv[3])
    manifest = json.loads(build.joinpath("manifest.json").read_text())
    current, current_lock = fingerprint(build), source_lock(manifest)
    if command == "write":
        gate.joinpath("baseline.json").write_text(json.dumps(current, indent=1) + "\n")
        gate.joinpath("sources.lock.json").write_text(json.dumps(current_lock, indent=2, sort_keys=True) + "\n")
        shutil.copyfile(build / "summary.json", gate / "summary.json")
        print(f"baseline written: {len(current['words'])} records; refresh only with the change that justifies it")
        return 0
    baseline = json.loads(gate.joinpath("baseline.json").read_text())
    expected_lock = json.loads(gate.joinpath("sources.lock.json").read_text())
    status = frozen_status(baseline, current, expected_lock, current_lock)
    print(f"frozen build: {status}")
    if EXIT_CODES[status]:
        path = build / "frozen_report.json"
        path.write_text(json.dumps(report(status, baseline, current, expected_lock, current_lock), indent=2) + "\n")
        print(f"complete report: {path}")
    return EXIT_CODES[status]


if __name__ == "__main__":
    sys.exit(main(sys.argv))
