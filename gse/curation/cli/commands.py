"""
CLI Commands for Lexicon Builder

Provides command-line interface for building and managing the GSE lexicon.
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def cmd_build(args):
    """Build lexicon for specified phase(s)."""
    from gse.curation.pipeline.staged_builder import StagedBuilder

    phases = args.phases if args.phases else [1, 2, 3]

    logger.info(f"Building lexicon: phases {phases}")
    logger.info(f"Lexicon DB: {args.lexicon_db}")
    logger.info(f"Frequency DB: {args.frequency_db}")
    logger.info(f"Resume: {not args.no_resume}")
    logger.info(f"Mock LLM: {args.mock}")

    with StagedBuilder(
        lexicon_db_path=args.lexicon_db,
        frequency_db_path=args.frequency_db,
        use_mock_llm=args.mock,
    ) as builder:
        for phase in phases:
            if phase == 1:
                builder.build_phase_one(resume=not args.no_resume)
            elif phase == 2:
                builder.build_phase_two(resume=not args.no_resume)
            elif phase == 3:
                builder.build_phase_three(resume=not args.no_resume)

        status = builder.get_status()
        _print_status(status)


def cmd_init(args):
    """Initialize lexicon from frequency database."""
    from gse.curation.pipeline.staged_builder import StagedBuilder

    phases = args.phases if args.phases else [1, 2, 3]

    logger.info(f"Initializing lexicon with phases: {phases}")

    with StagedBuilder(
        lexicon_db_path=args.lexicon_db,
        frequency_db_path=args.frequency_db,
        use_mock_llm=True,  # No LLM needed for init
    ) as builder:
        builder.initialize_from_frequency(phases)

    logger.info("Initialization complete")


def cmd_status(args):
    """Show build progress."""
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

            if data['total'] > 0:
                rate = 100 * data['validated'] / data['total']
                print(f"  Rate:      {rate:.1f}%")

    print("\n" + "-" * 50)
    total = status["total"]
    print(f"Total words:     {total['words']:,}")
    print(f"Total validated: {total['validated']:,}")
    print(f"Validation rate: {total['validation_rate']:.1f}%")
    print("=" * 50 + "\n")


def cmd_validate(args):
    """Validate decompositions in the database."""
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
    print(f"Bipolar pass:    {results['bipolar_pass']} ({100*results['bipolar_pass']/results['total']:.1f}%)")
    print(f"Coverage pass:   {results['coverage_pass']} ({100*results['coverage_pass']/results['total']:.1f}%)")
    print(f"Hierarchy pass:  {results['hierarchy_pass']} ({100*results['hierarchy_pass']/results['total']:.1f}%)")
    print(f"All pass:        {results['all_pass']} ({100*results['all_pass']/results['total']:.1f}%)")
    print("=" * 50 + "\n")

    db.close()


def cmd_export(args):
    """Export lexicon to JSON format."""
    import json

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
    build_parser.add_argument(
        "--phases",
        type=int,
        nargs="+",
        choices=[1, 2, 3],
        help="Phases to build (default: all)",
    )
    build_parser.add_argument(
        "--frequency-db",
        help="Path to frequency database",
    )
    build_parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh instead of resuming",
    )
    build_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock LLM for testing",
    )
    build_parser.set_defaults(func=cmd_build)

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize from frequency database")
    init_parser.add_argument(
        "--phases",
        type=int,
        nargs="+",
        choices=[1, 2, 3],
        help="Phases to initialize (default: all)",
    )
    init_parser.add_argument(
        "--frequency-db",
        help="Path to frequency database",
    )
    init_parser.set_defaults(func=cmd_init)

    # status command
    status_parser = subparsers.add_parser("status", help="Show build status")
    status_parser.set_defaults(func=cmd_status)

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate decompositions")
    validate_parser.set_defaults(func=cmd_validate)

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
    lookup_parser.set_defaults(func=cmd_lookup)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
