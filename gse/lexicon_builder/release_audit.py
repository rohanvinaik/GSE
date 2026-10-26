"""Measure a sparse build against local text, without constructing any meaning.

Surface homing, written evidence and fully settled coordinate profiles are
different measurements. None certifies semantic completeness or lexical truth.
The optional published-explication comparison is evaluation-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from gse.lexicon_builder.artifact import read_sparse, read_vectors
from gse.lexicon_builder.basis import BASIS_ID
from gse.lexicon_builder.core import CANONICAL_COORDINATES
from gse.lexicon_builder.sources import word_key
from gse.lexicon_builder.surprise import compare_artifact

HEAD_COORDINATES = frozenset({"I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY", "KIND", "PART"})
WORD_PATTERN = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)
CORPUS_ENCODINGS = {"brown": "ascii", "gutenberg": "latin1"}
TOKEN_POLICY = (
    "Unicode letter sequences with internal apostrophes/hyphens; NFC+casefold; "
    "no stemming, lemmatization, alias credit or inferred senses. Brown POS suffixes are removed first. "
    "Punctuation and numeric-only tokens are excluded; Gutenberg headers already removed by the corpus distributor."
)
METRICS = (
    "declared_surface",
    "native_record",
    "surface_home",
    "structural_home",
    "signed_evidence",
    "zero_evidence",
    "head_zero_evidence",
    "non_head_zero_evidence",
    "non_head_written_evidence",
    "any_complete_coordinate_profile",
    "all_readings_coordinate_complete",
)


@dataclass
class WordEvidence:
    native_record: bool = False
    structural_home: bool = False
    reading_count: int = 0
    complete_readings: int = 0
    unhandled_alternatives: int = 0
    signed_evidence: bool = False
    zero_evidence: bool = False
    head_zero_evidence: bool = False
    non_head_zero_evidence: bool = False
    non_head_written_evidence: bool = False
    conflict: bool = False


def file_digest(path: Path) -> str:
    """Hash arbitrarily large JSONL files with bounded memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def lexical_tokens(text: str) -> Iterator[str]:
    """Apply the declared surface-token policy after Unicode normalization."""
    return (match.group() for match in WORD_PATTERN.finditer(word_key(text)))


def _json_records(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError("INVALID_AUDIT_JSONL") from exc
            if not isinstance(record, dict):
                raise ValueError("INVALID_AUDIT_RECORD")
            yield record


def threshold_status(numerator: int, denominator: int, threshold: float = 0.9) -> dict:
    """A coverage threshold never changes the meaning of the measured metric."""
    if type(threshold) not in {int, float} or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("INVALID_COVERAGE_THRESHOLD")
    if type(numerator) is not int or type(denominator) is not int or not 0 <= numerator <= denominator:
        raise ValueError("INVALID_COVERAGE_COUNTS")
    ratio = numerator / denominator if denominator else None
    return {
        "matched_tokens": numerator,
        "eligible_tokens": denominator,
        "fraction": ratio,
        "threshold": threshold,
        "code": "NO_ELIGIBLE_TOKENS"
        if ratio is None
        else "THRESHOLD_MET"
        if ratio >= threshold
        else "THRESHOLD_NOT_MET",
    }


def _metric_flags(word: str, declared: set[str], evidence: dict[str, WordEvidence]) -> dict[str, bool]:
    item = evidence.get(word, WordEvidence())
    return {
        "declared_surface": word in declared,
        "native_record": item.native_record,
        "surface_home": item.reading_count > 0 or item.structural_home,
        "structural_home": item.structural_home,
        "signed_evidence": item.signed_evidence,
        "zero_evidence": item.zero_evidence,
        "head_zero_evidence": item.head_zero_evidence,
        "non_head_zero_evidence": item.non_head_zero_evidence,
        "non_head_written_evidence": item.non_head_written_evidence,
        "any_complete_coordinate_profile": item.complete_readings > 0,
        "all_readings_coordinate_complete": (
            item.reading_count > 0 and item.complete_readings == item.reading_count and item.unhandled_alternatives == 0
        ),
    }


def _coverage(counts: Counter, declared: set[str], evidence: dict[str, WordEvidence], threshold: float) -> dict:
    mass = Counter()
    for word, frequency in counts.items():
        for metric, present in _metric_flags(word, declared, evidence).items():
            if present:
                mass[metric] += frequency
    total = counts.total()
    oov = Counter({word: count for word, count in counts.items() if word not in declared})
    unhomed = Counter(
        {word: count for word, count in counts.items() if not _metric_flags(word, declared, evidence)["surface_home"]}
    )
    return {
        "eligible_tokens": total,
        "surface_types": len(counts),
        "metrics": {metric: threshold_status(mass[metric], total, threshold) for metric in METRICS},
        "out_of_declared_vocabulary": [
            {"word": word, "count": count} for word, count in sorted(oov.items(), key=lambda x: (-x[1], x[0]))
        ],
        "unhomed_surfaces": [
            {"word": word, "count": count} for word, count in sorted(unhomed.items(), key=lambda x: (-x[1], x[0]))
        ],
        "semantic_completion": "NOT_ESTABLISHED_BY_TOKEN_COVERAGE",
    }


def _source_pins(manifest: dict) -> dict:
    records = []
    for source in manifest.get("sources", []):
        for pin in source.get("files", []):
            path = Path(pin["path"])
            actual = file_digest(path) if path.is_file() else None
            records.append(
                {
                    "source": source["source"],
                    "id": pin.get("id", str(path)),
                    "expected_sha256": pin["sha256"],
                    "actual_sha256": actual,
                    "code": "SOURCE_FILE_UNAVAILABLE"
                    if actual is None
                    else "SOURCE_PIN_MATCH"
                    if actual == pin["sha256"]
                    else "SOURCE_PIN_MISMATCH",
                }
            )
    return {"outcomes": dict(Counter(r["code"] for r in records)), "files": records}


def _read_build(build_dir: Path) -> tuple[dict, set[str], dict[str, WordEvidence], dict]:
    for name in ("manifest.json", "words.jsonl", "sparse.jsonl", "structures.jsonl"):
        if not (build_dir / name).is_file():
            raise ValueError("MISSING_BUILD_ARTIFACT:" + name)
    manifest = json.loads((build_dir / "manifest.json").read_text())
    if not isinstance(manifest, dict) or manifest.get("basis_id") != BASIS_ID:
        raise ValueError("INVALID_BUILD_MANIFEST")
    if manifest.get("coordinate_order") != list(CANONICAL_COORDINATES):
        raise ValueError("INVALID_BUILD_COORDINATE_ORDER")
    words = manifest.get("words")
    if not isinstance(words, list) or any(not isinstance(w, str) or not word_key(w) for w in words):
        raise ValueError("INVALID_DECLARED_WORKLIST")
    declared = {word_key(word) for word in words}
    if len(declared) != len(words):
        raise ValueError("DUPLICATE_DECLARED_WORD")
    evidence: dict[str, WordEvidence] = {}
    sources: dict[str, Counter] = defaultdict(Counter)
    reading_states, scopes = Counter(), Counter()
    word_reading_ids = set()
    for record in _json_records(build_dir / "words.jsonl"):
        if not isinstance(record.get("word"), str) or not word_key(record["word"]):
            raise ValueError("INVALID_BUILD_WORD")
        word = word_key(record["word"])
        if word in evidence:
            raise ValueError("DUPLICATE_BUILD_WORD")
        readings, structures = record.get("readings", []), record.get("structural_entries", [])
        if not isinstance(readings, list) or not isinstance(structures, list):
            raise ValueError("INVALID_BUILD_READING_LIST")
        item = WordEvidence(structural_home=bool(structures), reading_count=len(readings))
        item.unhandled_alternatives = len(record.get("unhandled_native_alternatives", []))
        evidence[word] = item
        native = record.get("native", {})
        if not isinstance(native, dict):
            raise ValueError("INVALID_BUILD_NATIVE_ENVELOPE")
        for source in {s["source"] for s in manifest.get("sources", [])} | set(native):
            observation = native.get(source)
            if observation is None:
                sources[source]["MISSING_NATIVE_ENVELOPE"] += 1
                continue
            if not isinstance(observation, dict):
                raise ValueError("INVALID_BUILD_NATIVE_OBSERVATION")
            sources[source][observation.get("status", "MISSING_STATUS")] += 1
            if observation.get("status") == "OBSERVED":
                item.native_record = True
        for reading in readings:
            identity = (word, reading["reading_id"])
            if identity in word_reading_ids:
                raise ValueError("DUPLICATE_BUILD_READING")
            word_reading_ids.add(identity)
            reading_states[reading["code"]] += 1
            scopes[reading.get("source_scope", "SOURCE_CONTRACT_PROJECTION")] += 1
    cell_classes, cell_states, profile_classes = Counter(), Counter(), Counter()
    model_requests = set()
    coordinates: dict[str, Counter] = defaultdict(Counter)
    sparse_ids = set()
    for record in read_sparse(build_dir / "sparse.jsonl"):
        word = word_key(record["word"])
        identity = (word, record["reading_id"])
        if identity in sparse_ids:
            raise ValueError("DUPLICATE_SPARSE_READING")
        sparse_ids.add(identity)
        model_requests.update(record.get("provenance", {}).get("model_requests", []))
        if word not in evidence:
            raise ValueError("SPARSE_WORD_WITHOUT_BUILD_RECORD")
        item = evidence[word]
        written = set()
        unresolved = False
        conflict = record["code"] in {"CONFLICT", "SOURCE_CONFLICT"} or record["code"].startswith("SOURCE_CONFLICT_")
        reading_signed = reading_zero = reading_non_head = False
        reading_head_zero = reading_other_zero = False
        for coordinate, cell in record["cells"].items():
            state = cell["state"]
            cell_states[state] += 1
            coordinates[coordinate][state] += 1
            if state in {"+1", "-1"}:
                label = "SIGNED_CONTENT"
                reading_signed = True
            elif state == "0":
                label = "HEAD_COORDINATE_ZERO" if coordinate in HEAD_COORDINATES else "OTHER_WRITTEN_ZERO"
                reading_zero = True
                reading_head_zero |= coordinate in HEAD_COORDINATES
                reading_other_zero |= coordinate not in HEAD_COORDINATES
            else:
                label = {"empty": "EXPLICIT_SILENCE", "unresolved": "UNRESOLVED", "conflict": "CONFLICT"}[state]
            cell_classes[label] += 1
            if state in {"+1", "-1", "0"}:
                written.add(coordinate)
                if coordinate not in HEAD_COORDINATES:
                    reading_non_head = True
            unresolved |= state == "unresolved"
            conflict |= state == "conflict"
        item.conflict |= conflict
        if conflict:
            profile_classes["CONFLICTED_PROFILE"] += 1
        else:
            # A scoped SOURCE_CONFLICT need not empty any coordinate domain.
            # Keep its cells diagnostic, but never count them as support.
            item.signed_evidence |= reading_signed
            item.zero_evidence |= reading_zero
            item.head_zero_evidence |= reading_head_zero
            item.non_head_zero_evidence |= reading_other_zero
            item.non_head_written_evidence |= reading_non_head
            if not unresolved:
                item.complete_readings += 1
                profile_classes["FULLY_SETTLED_COORDINATE_PROFILE"] += 1
            elif written and written <= HEAD_COORDINATES:
                profile_classes["PARTIAL_HEAD_EVIDENCE_ONLY" if reading_signed else "PARTIAL_HEAD_ZEROS_ONLY"] += 1
            elif written:
                profile_classes["PARTIAL_DEFINITIONAL_EVIDENCE"] += 1
            else:
                profile_classes["NO_WRITTEN_DEFINITIONAL_EVIDENCE"] += 1
    structural_words, structural_records = set(), 0
    for entry in _json_records(build_dir / "structures.jsonl"):
        structural_words.add(word_key(entry["word"]))
        structural_records += 1
    expected_structures = {word for word, item in evidence.items() if item.structural_home}
    vectors = (
        sum(1 for _ in read_vectors(build_dir / "vectors.jsonl")) if (build_dir / "vectors.jsonl").is_file() else 0
    )
    consistent = (
        declared == set(evidence) and sparse_ids == word_reading_ids and structural_words == expected_structures
    )
    summary = {
        "code": "BUILD_ARTIFACTS_CONSISTENT" if consistent else "BUILD_ARTIFACT_SET_MISMATCH",
        "declared_words": len(declared),
        "word_records": len(evidence),
        "missing_declared_words": sorted(declared - set(evidence)),
        "undeclared_word_records": sorted(set(evidence) - declared),
        "missing_sparse_readings": [list(i) for i in sorted(word_reading_ids - sparse_ids)],
        "unexpected_sparse_readings": [list(i) for i in sorted(sparse_ids - word_reading_ids)],
        "reading_states": dict(reading_states),
        "reading_scopes": dict(scopes),
        "sparse_readings": len(sparse_ids),
        "candidate_vectors": vectors,
        "model_request_count": len(model_requests),
        "model_requests": sorted(model_requests),
        "cell_states": dict(cell_states),
        "cell_classes": dict(cell_classes),
        "coordinate_states": {c: dict(coordinates[c]) for c in CANONICAL_COORDINATES},
        "profile_classes": dict(profile_classes),
        "native_source_states_by_word": {source: dict(states) for source, states in sorted(sources.items())},
        "structural_records": structural_records,
        "structural_words": len(structural_words),
        "structural_word_set_matches": structural_words == expected_structures,
        "word_evidence": {
            metric: sum(_metric_flags(word, declared, evidence)[metric] for word in declared) for metric in METRICS
        },
        "words_with_conflicts": sum(item.conflict for item in evidence.values()),
    }
    return manifest, declared, evidence, summary


def corpus_counts(root: Path, corpus: str) -> tuple[dict[str, Counter], list[dict]]:
    """Read complete local corpus files; no downloads or corpus-trained model."""
    directory = root / corpus
    groups: dict[str, Counter] = defaultdict(Counter)
    pins = []
    if corpus == "brown":
        categories = directory / "cats.txt"
        if not categories.is_file():
            return {}, []
        pins.append({"id": "nltk:brown/cats.txt", "sha256": file_digest(categories)})
        files = []
        for line in categories.read_text().splitlines():
            fields = line.split()
            if len(fields) != 2:
                raise ValueError("INVALID_BROWN_CATEGORY_RECORD")
            files.append((fields[1], directory / fields[0]))
    elif corpus == "gutenberg":
        files = [(p.stem, p) for p in sorted(directory.glob("*.txt"))]
    else:
        raise ValueError("UNSUPPORTED_AUDIT_CORPUS")
    for group, path in files:
        if not path.is_file():
            raise ValueError("MISSING_CORPUS_FILE:" + str(path))
        counts = groups[group]
        # These encodings match the corpus declarations shipped by NLTK:
        # Brown is ASCII, Gutenberg Latin-1. Never drop undecodable bytes.
        with path.open(encoding=CORPUS_ENCODINGS[corpus]) as stream:
            for line in stream:
                pieces = (part.rsplit("/", 1)[0] for part in line.split()) if corpus == "brown" else (line,)
                for piece in pieces:
                    counts.update(lexical_tokens(piece))
        pins.append({"id": f"nltk:{corpus}/{path.name}", "sha256": file_digest(path)})
    return dict(groups), pins


def _reference_ledger(sparse_path: Path, gold: Path) -> dict:
    source = json.loads(gold.read_text())
    references = source["gold_from_published_explications"]
    # The existing comparator indexes its input. Bound that input to reference
    # words so it never retains the whole large lexicon in memory. Gold values
    # are passed only to the evaluator, after construction has finished.
    with TemporaryDirectory(prefix="gse-release-reference-") as scratch:
        selected = Path(scratch) / "reference-readings.jsonl"
        with selected.open("w") as stream:
            for record in read_sparse(sparse_path):
                if record["word"] in references:
                    stream.write(json.dumps(record) + "\n")
        result = compare_artifact(selected, references)
    result["comparison_projection_sha256"] = result.pop("input_sha256")
    result["input_sha256"] = file_digest(sparse_path)
    result["reference_sha256"] = file_digest(gold)
    result["reference_role"] = "EVALUATION_ONLY; NEVER_CONSTRUCTION_OR_TASK_GENERATION"
    return result


def release_audit(
    build_dir: Path,
    nltk_root: Path,
    corpora: tuple[str, ...] = ("brown", "gutenberg"),
    threshold: float = 0.9,
    gold: Path | None = None,
) -> dict:
    """Compute coverage and incompleteness from emitted artifacts and local text."""
    threshold_status(0, 0, threshold)
    manifest, declared, evidence, summary = _read_build(build_dir)
    reports, corpus_manifest = {}, []
    for corpus in corpora:
        groups, pins = corpus_counts(nltk_root, corpus)
        total = Counter()
        for counts in groups.values():
            total.update(counts)
        reports[corpus] = {
            "code": "CORPUS_MEASURED" if groups else "CORPUS_UNAVAILABLE",
            "encoding": CORPUS_ENCODINGS[corpus],
            "grouping": "NATIVE_BROWN_GENRE" if corpus == "brown" else "NATIVE_TEXT_FILE; NO_GENRE_LABEL_INFERRED",
            "total": _coverage(total, declared, evidence, threshold),
            "groups": {
                name: _coverage(counts, declared, evidence, threshold) for name, counts in sorted(groups.items())
            },
        }
        corpus_manifest.extend(pins)
    inputs = [
        p
        for p in sorted(build_dir.iterdir())
        if p.is_file()
        and p.name
        in {
            "manifest.json",
            "words.jsonl",
            "sparse.jsonl",
            "structures.jsonl",
            "vectors.jsonl",
        }
    ]
    result = {
        "schema": "GSE_LEXICON_RELEASE_AUDIT_V1",
        "code": "RELEASE_AUDIT_COMPUTED",
        "basis_id": BASIS_ID,
        "build": summary,
        "corpora": reports,
        "interpretation": {
            "surface_home": "At least one emitted lexical reading or structural entry; may carry no settled cells.",
            "signed_evidence": "At least one +1 or -1 cell, including a typed head; not a complete definition.",
            "head_coordinate_zero": "A written zero on one of the eight head coordinates; a positional count, not a new warrant.",
            "complete_coordinate_profile": "Every coordinate settled in one emitted reading; no claim that all meanings are present or correct.",
            "semantic_completion": "NOT_ESTABLISHED_BY_COVERAGE_AUDIT",
            "conflict_policy": "Conflicted readings remain diagnostic and may have a surface home; their cells never support evidence or coordinate-completion coverage.",
            "production_readiness": "NOT_ESTABLISHED_BY_COVERAGE_AUDIT",
            "threshold_scope": "Each token-mass metric is tested separately; 90% surface coverage does not certify semantic completion.",
            "token_policy": TOKEN_POLICY,
        },
        "manifest": {
            "build_manifest_sha256": file_digest(build_dir / "manifest.json"),
            "build_inputs": [{"name": p.name, "sha256": file_digest(p)} for p in inputs],
            "corpus_inputs": corpus_manifest,
            "native_source_pin_verification": _source_pins(manifest),
            "audit_implementation_sha256": file_digest(Path(__file__)),
        },
    }
    if gold is not None:
        result["published_explication_comparison"] = _reference_ledger(build_dir / "sparse.jsonl", gold)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--nltk", type=Path, default=Path.home() / "nltk_data/corpora")
    parser.add_argument("--corpora", nargs="+", choices=("brown", "gutenberg"), default=["brown", "gutenberg"])
    parser.add_argument("--threshold", type=float, default=0.9)
    parser.add_argument("--gold", type=Path)
    args = parser.parse_args(argv)
    try:
        report = release_audit(args.build_dir, args.nltk, tuple(args.corpora), args.threshold, args.gold)
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "release-audit.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "code": report["code"],
                "build": {k: report["build"][k] for k in ("declared_words", "sparse_readings", "profile_classes")},
                "corpora": {name: r["total"]["metrics"] for name, r in report["corpora"].items()},
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
