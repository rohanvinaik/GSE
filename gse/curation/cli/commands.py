"""
CLI Commands for Lexicon Builder

Provides command-line interface for building and managing the GSE lexicon.
"""

import argparse
import logging
import sys
from contextlib import closing
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def cmd_build(args):
    """Build from typed source evidence, symbolic closure, and optional cell completion."""
    import json
    from pathlib import Path

    from gse.curation.lexicon_builder.pipeline import build_dictionary, build_from_sources, load_evidence

    options: dict[str, Any] = {
        "manifest": args.rules,
        "max_model_calls": args.max_model_calls,
        "discover": args.discover,
    }
    if getattr(args, "weights", None):
        from gse.curation.lexicon_builder.interchange import read_json

        options["weights"] = read_json(args.weights)
    if args.model:
        from gse.curation.lexicon_builder.residual import OllamaTransport

        if args.max_model_calls <= 0:
            raise ValueError("MODEL_REQUIRES_EXPLICIT_CALL_BUDGET")
        options["transport"] = OllamaTransport(args.model)
    if args.evidence:
        report = build_dictionary(load_evidence(args.evidence), args.lexicon_db, **options)
    else:
        words = tuple(Path(args.words_file).read_text().splitlines()) if args.words_file else None
        report = build_from_sources(args.lexicon_db, words=words, **options)
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if args.report:
        Path(args.report).write_text(encoded + "\n")
    print(encoded)


def cmd_evaluate(args):
    """Compare the dictionary to explicitly supplied per-definition gold cells."""
    import json
    from pathlib import Path

    from gse.curation.lexicon_builder.evaluation import evaluate_build

    result = evaluate_build(args.lexicon_db, args.gold)
    encoded = json.dumps(result, indent=2, sort_keys=True)
    if args.report:
        Path(args.report).write_text(encoded + "\n")
    print(encoded)
    if result["outcomes"]["WRONG"]:
        raise SystemExit(2)


def cmd_catalog(args):
    """Show primary inventory or the build's explicit prime-anchor coverage."""
    import json
    import sqlite3
    from pathlib import Path

    from gse.curation.lexicon_builder.catalog import catalog_inventory

    if args.inventory:
        result = catalog_inventory()
    else:
        with closing(sqlite3.connect(Path(args.lexicon_db).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            row = conn.execute("SELECT value FROM builder_metadata WHERE key='catalog'").fetchone()
            if row is None:
                raise ValueError("CATALOG_REPORT_UNAVAILABLE")
            result = json.loads(row[0])
    encoded = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False)
    if args.report:
        Path(args.report).write_text(encoded + "\n")
    print(encoded)


def cmd_init(args):
    """Create the versioned store without invented word entries or default zeros."""
    from gse.curation.lexicon_builder.storage import open_build

    with closing(open_build(args.lexicon_db)):
        pass
    print("INITIALIZED: use build to populate dictionary definitions from evidence")


def cmd_status(args):
    """Show build progress."""
    import json
    import sqlite3
    from pathlib import Path

    if Path(args.lexicon_db).exists():
        with closing(sqlite3.connect(f"file:{Path(args.lexicon_db).resolve()}?mode=ro", uri=True)) as conn:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='builder_metadata'").fetchone():
                row = conn.execute("SELECT value FROM builder_metadata WHERE key='last_report'").fetchone()
                print(json.dumps(json.loads(row[0]) if row else {"code": "NO_BUILD_REPORT"}, indent=2))
                return
    from gse.curation.pipeline.staged_builder import StagedBuilder

    with StagedBuilder(
        lexicon_db_path=args.lexicon_db,
        use_mock_llm=True,
    ) as builder:
        status = builder.get_status()
        _print_status(status)


def _print_status(status):
    """Pretty print build status."""
    print("\n" + "=" * 50)
    print("GSE LEXICON BUILD STATUS")
    print("=" * 50)

    for phase in [1, 2, 3]:
        if phase in status["phases"]:
            data = status["phases"][phase]
            print(f"\nPhase {phase}:")
            print(f"  Total:     {data['total']:,}")
            print(f"  Validated: {data['validated']:,}")
            print(f"  Pending:   {data['pending']:,}")
            print(f"  Rejected:  {data['rejected']:,}")

            if data["total"] > 0:
                rate = 100 * data["validated"] / data["total"]
                print(f"  Rate:      {rate:.1f}%")

    print("\n" + "-" * 50)
    total = status["total"]
    print(f"Total words:     {total['words']:,}")
    print(f"Total validated: {total['validated']:,}")
    print(f"Validation rate: {total['validation_rate']:.1f}%")
    print("=" * 50 + "\n")


def cmd_validate(args):
    """Validate decompositions in the database."""
    import json
    import sqlite3
    from pathlib import Path

    if Path(args.lexicon_db).exists():
        with closing(sqlite3.connect(f"file:{Path(args.lexicon_db).resolve()}?mode=ro", uri=True)) as conn:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='builder_metadata'").fetchone():
                from gse.curation.lexicon_builder.validation import validate_build

                result = validate_build(args.lexicon_db)
                print(json.dumps(result, indent=2))
                if result["code"] != "REPLAY_VALIDATED":
                    raise SystemExit(2)
                return
    from gse.curation.lexicon_db import LexiconDatabase
    from gse.curation.validation.bipolar_validator import BipolarValidator
    from gse.curation.validation.coverage_checker import CoverageChecker
    from gse.curation.validation.hierarchy_validator import HierarchyValidator

    db = LexiconDatabase(args.lexicon_db)
    bipolar = BipolarValidator()
    coverage = CoverageChecker()
    hierarchy = HierarchyValidator()

    entries = db.get_validated_entries()

    results = {
        "total": len(entries),
        "bipolar_pass": 0,
        "coverage_pass": 0,
        "hierarchy_pass": 0,
        "all_pass": 0,
    }

    for entry in entries:
        bp = bipolar.validate(entry.decomposition)
        cv = coverage.validate(entry.decomposition)
        hr = hierarchy.validate(entry.decomposition)

        if bp.passed:
            results["bipolar_pass"] += 1
        if cv.passed:
            results["coverage_pass"] += 1
        if hr.passed:
            results["hierarchy_pass"] += 1
        if bp.passed and cv.passed and hr.passed:
            results["all_pass"] += 1

    print("\n" + "=" * 50)
    print("VALIDATION RESULTS")
    print("=" * 50)
    print(f"Total entries:   {results['total']}")
    print(f"Bipolar pass:    {results['bipolar_pass']} ({100 * results['bipolar_pass'] / results['total']:.1f}%)")
    print(f"Coverage pass:   {results['coverage_pass']} ({100 * results['coverage_pass'] / results['total']:.1f}%)")
    print(f"Hierarchy pass:  {results['hierarchy_pass']} ({100 * results['hierarchy_pass'] / results['total']:.1f}%)")
    print(f"All pass:        {results['all_pass']} ({100 * results['all_pass'] / results['total']:.1f}%)")
    print("=" * 50 + "\n")

    db.close()


def cmd_export(args):
    """Export lexicon to JSON format."""
    import json
    import sqlite3
    from pathlib import Path

    from gse.curation.lexicon_builder.storage import read_entries

    if Path(args.lexicon_db).exists():
        with closing(sqlite3.connect(f"file:{Path(args.lexicon_db).resolve()}?mode=ro", uri=True)) as conn:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='builder_metadata'").fetchone():
                data = {"format": "gse.lexicon-export/1", "entries": read_entries(conn)}
                Path(args.output or "lexicon_export.json").write_text(json.dumps(data, indent=2))
                print(f"Exported {len(data['entries'])} definitions")
                return

    from gse.curation.lexicon_db import LexiconDatabase

    db = LexiconDatabase(args.lexicon_db)
    entries = db.get_validated_entries()

    export_data = {}
    for entry in entries:
        export_data[entry.lemma] = {
            "pos": entry.pos,
            "gloss": entry.gloss,
            "source": entry.source,
            "confidence": entry.confidence,
            "frequency_rank": entry.frequency_rank,
            "decomposition": entry.decomposition,
        }

    output_path = args.output or "lexicon_export.json"
    with open(output_path, "w") as f:
        json.dump(export_data, f, indent=2)

    print(f"Exported {len(export_data)} entries to {output_path}")

    db.close()


def cmd_lookup(args):
    """Look up a word's decomposition."""
    import json
    import sqlite3
    from pathlib import Path

    from gse.curation.lexicon_builder.storage import read_entries, runtime_lookup

    if Path(args.lexicon_db).exists():
        with closing(sqlite3.connect(f"file:{Path(args.lexicon_db).resolve()}?mode=ro", uri=True)) as conn:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='builder_metadata'").fetchone():
                result = runtime_lookup(conn, args.word, getattr(args, "entry_id", None))
                result["definitions"] = read_entries(conn, args.word, getattr(args, "entry_id", None))
                print(json.dumps(result, indent=2))
                return
    from gse.curation.lexicon_db import LexiconDatabase
    from gse.curation.schema import PRIMITIVE_TO_BANK

    db = LexiconDatabase(args.lexicon_db)
    entry = db.get_lexeme(args.word)

    if entry is None:
        print(f"Word '{args.word}' not found in lexicon")
        return

    print(f"\n{'=' * 50}")
    print(f"WORD: {entry.lemma}")
    print(f"{'=' * 50}")
    print(f"POS: {entry.pos}")
    print(f"Gloss: {entry.gloss or 'N/A'}")
    print(f"Source: {entry.source}")
    print(f"Confidence: {entry.confidence:.2f}")
    print(f"Frequency rank: {entry.frequency_rank}")
    print(f"Validation: {entry.validation_status}")

    print(f"\n{'DECOMPOSITION':^50}")
    print("-" * 50)

    # Group by bank
    by_bank = {}
    for prim, val in entry.decomposition.items():
        if val != 0:
            bank = PRIMITIVE_TO_BANK.get(prim, 7)
            if bank not in by_bank:
                by_bank[bank] = []
            by_bank[bank].append((prim, val))

    bank_names = {
        0: "SUBSTANTIVES",
        1: "QUANTITY",
        2: "EVALUATORS",
        3: "MENTAL",
        4: "ACTION",
        5: "TEMPORAL",
        6: "SPATIAL",
        7: "LOGICAL",
    }

    for bank in sorted(by_bank.keys()):
        print(f"\nBank {bank} ({bank_names.get(bank, 'UNKNOWN')}):")
        for prim, val in sorted(by_bank[bank]):
            sign = "+" if val > 0 else ""
            print(f"  {prim}: {sign}{val}")

    print("=" * 50 + "\n")

    db.close()


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="GSE Lexicon Builder CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--lexicon-db",
        default="lexicon.db",
        help="Path to lexicon database (default: lexicon.db)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # build command
    build_parser = subparsers.add_parser("build", help="Build lexicon")
    build_parser.add_argument("--evidence", help="Typed evidence JSON; otherwise read locally cached sources")
    build_parser.add_argument("--rules", help="Versioned approved relations, definition anchors, and hierarchy JSON")
    build_parser.add_argument("--words-file", help="Optional complete list of spellings to build")
    build_parser.add_argument("--model", help="Explicit local Ollama model for residual cell completion")
    build_parser.add_argument(
        "--max-model-calls", type=int, default=0, help="Explicit residual call budget; default zero"
    )
    build_parser.add_argument("--report", help="Write the computed build report to this JSON file")
    build_parser.add_argument("--weights", help="JSON mapping exact definition IDs to nonnegative frequency weights")
    build_parser.add_argument(
        "--discover", action="store_true", help="Record unapproved cross-bank candidate diagnostics"
    )
    build_parser.set_defaults(func=cmd_build)

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize an empty versioned dictionary")
    init_parser.set_defaults(func=cmd_init)

    # status command
    status_parser = subparsers.add_parser("status", help="Show build status")
    status_parser.set_defaults(func=cmd_status)

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate decompositions")
    validate_parser.set_defaults(func=cmd_validate)

    evaluate_parser = subparsers.add_parser("evaluate", help="Compare against explicitly supplied gold labels")
    evaluate_parser.add_argument("--gold", required=True, help="Versioned gold JSON with exact entry IDs and cells")
    evaluate_parser.add_argument("--report", help="Write the gold evaluation report to this JSON file")
    evaluate_parser.set_defaults(func=cmd_evaluate)

    catalog_parser = subparsers.add_parser("catalog", help="Inspect primary NSM units and anchor coverage")
    catalog_parser.add_argument(
        "--inventory", action="store_true", help="Show the saved primary chart independently of a build"
    )
    catalog_parser.add_argument("--report", help="Write the catalog report to this JSON file")
    catalog_parser.set_defaults(func=cmd_catalog)

    # export command
    export_parser = subparsers.add_parser("export", help="Export to JSON")
    export_parser.add_argument(
        "--output",
        help="Output file path (default: lexicon_export.json)",
    )
    export_parser.set_defaults(func=cmd_export)

    # lookup command
    lookup_parser = subparsers.add_parser("lookup", help="Look up a word")
    lookup_parser.add_argument("word", help="Word to look up")
    lookup_parser.add_argument("--entry-id", help="Select a dictionary definition explicitly")
    lookup_parser.set_defaults(func=cmd_lookup)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command in {"status", "validate", "export", "lookup", "evaluate"} or (
        args.command == "catalog" and not args.inventory
    ):
        from pathlib import Path

        if not Path(args.lexicon_db).is_file():
            parser.error("BUILD_NOT_FOUND: read commands require an existing dictionary")

    args.func(args)


if __name__ == "__main__":
    main()
