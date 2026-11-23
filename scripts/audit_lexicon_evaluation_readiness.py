"""Read existing human-label cohorts without converting them into bank gold.

Only the requested JSON receipt is written. SQLite is opened read-only in one
transaction; source files are never downloaded or modified. Candidate identity
counts describe spelling/POS matches, never verified annotation sense identity.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path

from GSE.curation.lexicon_builder.foundation import definition_context
from GSE.curation.lexicon_builder.storage import VERSION
from GSE.namespace import current_id

ROOT = Path(__file__).resolve().parents[1]
STATUSES = ("MISSING", "UNIQUE_CANDIDATE", "MULTIPLE_DEFINITIONS")


def source_text(path: Path) -> tuple[str, dict]:
    """Parse and fingerprint the same bytes, not two potentially different reads."""
    data = path.read_bytes()
    return data.decode("utf-8-sig"), {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def source_reference(path: Path) -> dict:
    return source_text(path)[1] if path.is_file() else {"path": str(path.resolve()), "code": "SOURCE_MISSING"}


def parse_rankings(text: str) -> tuple[tuple[int, tuple[str, ...]], ...]:
    """Retain each original rank and its entire tied group; never flatten ties."""
    groups = []
    seen = set()
    previous = -1
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise ValueError("INVALID_SCALAR_ROW")
        rank_text, terms = parts
        if not rank_text.isdecimal():
            raise ValueError("INVALID_SCALAR_RANK")
        rank = int(rank_text)
        words = tuple(word.strip().lower() for word in terms.split("||"))
        if rank <= previous or any(not word or word in seen for word in words) or len(set(words)) != len(words):
            raise ValueError("INVALID_SCALAR_GROUP")
        groups.append((rank, words))
        previous = rank
        seen.update(words)
    if not groups:
        raise ValueError("EMPTY_SCALAR_SOURCE")
    return tuple(groups)


def parse_pairs(text: str, *, simlex: bool) -> list[dict]:
    """Keep human scores as scores and validate the source's declared columns."""
    reader = csv.DictReader(io.StringIO(text), delimiter="\t" if simlex else ",")
    required = {"word1", "word2", "POS", "SimLex999"} if simlex else {"Word 1", "Word 2", "Human (Mean)"}
    fields = reader.fieldnames or []
    if len(fields) != len(set(fields)) or not required <= set(fields):
        raise ValueError("INVALID_PAIR_COLUMNS")
    pairs = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("INVALID_PAIR_ROW")
        w1, w2, score_key = ("word1", "word2", "SimLex999") if simlex else ("Word 1", "Word 2", "Human (Mean)")
        first, second = row[w1].strip().lower(), row[w2].strip().lower()
        if not first or not second:
            raise ValueError("EMPTY_PAIR_WORD")
        score = float(row[score_key])
        if not math.isfinite(score) or not 0 <= score <= 10:
            raise ValueError("INVALID_PAIR_SCORE")
        pos = {"N": "noun", "V": "verb", "A": "adjective"}.get(row["POS"]) if simlex else None
        if simlex and pos is None:
            raise ValueError("INVALID_PAIR_POS")
        pairs.append({"word1": first, "word2": second, "pos": pos, "score": score})
    if not pairs:
        raise ValueError("EMPTY_PAIR_SOURCE")
    return pairs


def identity_index(path: Path) -> tuple[dict, dict]:
    """Fingerprint all definition identities in a consistent read-only snapshot."""
    by_pos = defaultdict(list)
    by_word = defaultdict(list)
    digest = hashlib.sha256()
    seen = set()
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        row = conn.execute("SELECT value FROM builder_metadata WHERE key='format'").fetchone()
        if row is None or current_id(json.loads(row[0])) != VERSION:
            raise ValueError("UNSUPPORTED_BUILD_FORMAT")
        for entry_id, lemma, pos in conn.execute(
            "SELECT s.entry_id,l.lemma,l.pos FROM definition_states s JOIN lexemes l ON s.lexeme_id=l.id "
            "ORDER BY s.entry_id"
        ):
            if any(type(value) is not str or not value.strip() for value in (entry_id, lemma, pos)) or entry_id in seen:
                raise ValueError("INVALID_BUILD_IDENTITY")
            seen.add(entry_id)
            digest.update(
                (json.dumps([entry_id, lemma, pos], ensure_ascii=False, separators=(",", ":")) + "\n").encode()
            )
            by_pos[(lemma.lower(), definition_context(pos)["pos"])].append(entry_id)
            by_word[lemma.lower()].append(entry_id)
        lexemes = conn.execute("SELECT count(*) FROM lexemes").fetchone()[0]
        states = conn.execute("SELECT count(*) FROM definition_states").fetchone()[0]
        if len(seen) != lexemes or len(seen) != states:
            raise ValueError("UNMATCHED_BUILD_IDENTITY")
    return {"by_pos": by_pos, "by_word": by_word}, {
        "path": str(path.resolve()),
        "format": VERSION,
        "definitions": len(seen),
        "identity_sha256": digest.hexdigest(),
        "fingerprint_scope": "ORDERED_ENTRY_ID_LEMMA_POS_JSON_LINES_NOT_DATABASE_BYTES_OR_SEMANTIC_VALUES",
        "read_mode": "SQLITE_MODE_RO_QUERY_ONLY_SINGLE_TRANSACTION",
    }


def candidate_record(index: dict, word: str, pos: str | None) -> dict:
    ids = index["by_pos"].get((word, pos), ()) if pos else index["by_word"].get(word, ())
    status = "MISSING" if not ids else "UNIQUE_CANDIDATE" if len(ids) == 1 else "MULTIPLE_DEFINITIONS"
    return {"word": word, "pos": pos, "code": status, "candidate_entry_ids": list(ids)}


def identity_summary(index: dict, words: set[tuple[str, str | None]]) -> dict:
    records = [
        candidate_record(index, word, pos) for word, pos in sorted(words, key=lambda value: (value[0], value[1] or ""))
    ]
    counts = Counter(record["code"] for record in records)
    return {
        "word_pos_records": len(records),
        "outcomes": {status: counts[status] for status in STATUSES},
        "outcomes_sha256": hashlib.sha256(
            json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "examples": {status: [record for record in records if record["code"] == status][:3] for status in STATUSES},
        "verified_sense_links": 0,
        "policy": "SPELLING_POS_CANDIDATES_ONLY_UNIQUE_IS_NOT_VERIFIED_SENSE_IDENTITY",
    }


def pair_cohort(path: Path, index: dict, *, simlex: bool) -> dict:
    if not path.is_file():
        return {"code": "SOURCE_MISSING", "source": source_reference(path), "bank_gold": "NOT_BANK_GOLD"}
    text, source = source_text(path)
    pairs = parse_pairs(text, simlex=simlex)
    pair_outcomes = Counter()
    words = set()
    for pair in pairs:
        statuses = []
        for key in ("word1", "word2"):
            word = pair[key]
            words.add((word, pair["pos"]))
            statuses.append(candidate_record(index, word, pair["pos"])["code"])
        pair_outcomes[" + ".join(sorted(statuses))] += 1
    return {
        "code": "SOURCE_READ",
        "bank_gold": "NOT_BANK_GOLD",
        "label_kind": "HUMAN_SIMILARITY_SCORE" if simlex else "HUMAN_RELATEDNESS_SCORE",
        "source": source,
        "records": len(pairs),
        "matching_basis": "SPELLING_AND_MAJORITY_POS" if simlex else "SPELLING_ONLY_NO_SOURCE_POS",
        "pair_identity_outcomes": dict(sorted(pair_outcomes.items())),
        "identity": identity_summary(index, words),
        "missing_for_bank_evaluation": ["VERIFIED_DEFINITION_IDENTITY", "AUTHORITATIVE_BANK_TRIT_LABELS"],
    }


def scalar_cohort(directory: Path, index: dict) -> dict:
    files = sorted(directory.glob("*.rankings"))
    if not files:
        return {"code": "SOURCE_MISSING", "path": str(directory.resolve()), "bank_gold": "NOT_BANK_GOLD"}
    sources, words = [], set()
    groups = ties = occurrences = 0
    ranking_digest = hashlib.sha256()
    for path in files:
        text, source = source_text(path)
        ranks = parse_rankings(text)
        n_ties = sum(len(terms) > 1 for _, terms in ranks)
        sources.append({**source, "rank_groups": len(ranks), "tied_rank_groups": n_ties})
        groups += len(ranks)
        ties += n_ties
        for _, terms in ranks:
            words.update((word, "adjective") for word in terms)
            occurrences += len(terms)
        ranking_digest.update((json.dumps([path.name, ranks], separators=(",", ":")) + "\n").encode())
    return {
        "code": "SOURCE_READ",
        "bank_gold": "NOT_BANK_GOLD",
        "label_kind": "ORDINAL_INTENSITY_GROUPS_WITH_TIES",
        "matching_basis": "SPELLING_AND_ADJECTIVE_POS_NO_SOURCE_SENSE_IDS",
        "sources": sources,
        "scale_files": len(files),
        "rank_groups": groups,
        "tied_rank_groups": ties,
        "word_occurrences": occurrences,
        "ranked_groups_sha256": ranking_digest.hexdigest(),
        "tie_policy": "ORIGINAL_INTEGER_RANK_AND_TUPLE_OF_TIED_TERMS_PRESERVED_NO_FLATTENING",
        "identity": identity_summary(index, words),
        "missing_for_bank_evaluation": ["VERIFIED_DEFINITION_IDENTITY", "AUTHORITATIVE_BANK_TRIT_LABELS"],
        "missing_for_hierarchy_evaluation": ["VERIFIED_DEFINITION_IDENTITY", "NAMED_COMMON_HIERARCHY_AXIS"],
    }


def audit(lexicon_db: Path, *, project_root: Path = ROOT, benchmark_cache: Path | None = None) -> dict:
    index, build = identity_index(lexicon_db)
    cache = benchmark_cache if benchmark_cache is not None else Path.home() / ".cache/gse_benchmarks"
    scalar = project_root / "data/external/scalar-adj"
    cohorts = {
        "simlex999": pair_cohort(cache / "SimLex-999.txt", index, simlex=True),
        "wordsim353": pair_cohort(project_root / "data/benchmarks/wordsim353.csv", index, simlex=False),
        **{
            name: scalar_cohort(scalar / "globalorder/data" / name / "gold_rankings", index)
            for name in ("demelo", "crowd", "wilkinson")
        },
    }
    return {
        "format": "GSE.lexicon-evaluation-readiness/1",
        "code": "READINESS_AUDITED",
        "bank_gold": "NOT_BANK_GOLD",
        "semantic_correctness": "NOT_EVALUATED",
        "build": build,
        "tool": source_reference(Path(__file__)),
        "cohorts": cohorts,
        "provenance_documents": [
            source_reference(path)
            for path in (
                cache / "SimLex-999/README.txt",
                project_root / "GSE/benchmarks/datasets.py",
                scalar / "README.md",
                scalar / "globalorder/README.md",
                scalar / "globalorder/data/socal/readme.md",
            )
        ],
        "limitations": [
            "SOURCE_LABELS_ARE_SCORES_OR_ORDINAL_RANKS_NOT_GSE_BANK_TRITS",
            "SINGLE_DICTIONARY_CANDIDATE_DOES_NOT_PROVE_ANNOTATOR_SENSE_IDENTITY",
            "NO_UNKNOWN_COORDINATE_WAS_CONVERTED_TO_ZERO",
            "NO_SOURCE_LABEL_OR_RULE_WAS_ADMITTED_TO_THE_LEXICON",
            "SOURCE_BYTE_IDENTITIES_ARE_RECORDED_BUT_INDEPENDENT_ANNOTATION_AUTHENTICITY_IS_NOT_REAUDITED",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lexicon-db", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--benchmark-cache", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.output is not None and args.output.resolve() == args.lexicon_db.resolve():
        parser.error("OUTPUT_MUST_NOT_OVERWRITE_DATABASE")
    result = audit(args.lexicon_db, project_root=args.project_root, benchmark_cache=args.benchmark_cache)
    rendered = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
