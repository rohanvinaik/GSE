#!/usr/bin/env python3
"""
GSE Network Teaching Script

Teaches the learning networks from a corpus with:
- One document per epoch (72 total: 70 text + 2 JSON)
- Random document ordering (seed 42)
- Large JSON files at epochs 27 and 54
- Behavior tracking after each epoch
- Session logging and summary

Usage:
    python scripts/teach_networks.py --corpus /path/to/corpus --profile default
    python scripts/teach_networks.py --resume  # Resume from last session
    python scripts/teach_networks.py --summary  # Show current profile stats
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gse.profiles.profile_manager import ProfileManager
from gse.teaching.teacher import NetworkTeacher, TeachingSession

# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_CORPUS = "/Users/rohanvinaik/relational-ai/data/training_text"
DEFAULT_PROFILE = "default"
PROFILES_DIR = "data/profiles"
SESSIONS_DIR = "data/teaching_sessions"

# JSON files to be processed at specific epochs
JSON_EPOCHS = {
    27: "/Users/rohanvinaik/relational-ai/data/training_text/claude_conversations.json",
    54: "/Users/rohanvinaik/relational-ai/data/training_text/gpt_conversations.json",
}


# =============================================================================
# PROGRESS DISPLAY
# =============================================================================


def print_progress(epoch: int, total: int, message: str):
    """Print progress with formatting."""
    pct = (epoch / total) * 100
    bar_len = 30
    filled = int(bar_len * epoch / total)
    bar = "=" * filled + "-" * (bar_len - filled)

    # Clear line and print
    print(f"\r[{bar}] {pct:5.1f}% Epoch {epoch}/{total}: {message}", end="", flush=True)

    # Newline on completion
    if epoch == total:
        print()


def print_epoch_summary(epoch):
    """Print summary for an epoch."""
    print(f"\n  Epoch {epoch.epoch_number}: {epoch.document}")
    print(f"    Type: {epoch.document_type}")
    print(f"    Duration: {epoch.duration_seconds:.1f}s")
    print(
        f"    Processed: {epoch.paragraphs_processed} paras, {epoch.sentences_processed} sents, {epoch.words_processed} words"
    )
    print(f"    Updates: {epoch.total_updates}")
    print(
        f"    Deltas: text={epoch.text_delta:.4f}, para={epoch.paragraph_delta:.4f}, "
        f"sent={epoch.sentence_delta:.4f}, word={epoch.word_delta:.4f}"
    )


def print_session_summary(session: TeachingSession, behavior: dict):
    """Print complete session summary."""
    print("\n" + "=" * 60)
    print("TEACHING SESSION SUMMARY")
    print("=" * 60)

    print(f"\nProfile: {session.profile_name}")
    print(f"Start: {session.start_time}")
    print(f"End: {session.end_time}")
    print(f"Total epochs: {session.total_epochs}")
    print(f"Random seed: {session.random_seed}")

    # Duration
    total_duration = sum(e.duration_seconds for e in session.epochs)
    print(f"Total duration: {total_duration:.1f}s ({total_duration / 60:.1f} min)")

    # Processing stats
    total_paras = sum(e.paragraphs_processed for e in session.epochs)
    total_sents = sum(e.sentences_processed for e in session.epochs)
    total_words = sum(e.words_processed for e in session.epochs)
    total_updates = sum(e.total_updates for e in session.epochs)

    print("\nProcessing Statistics:")
    print(f"  Paragraphs: {total_paras:,}")
    print(f"  Sentences: {total_sents:,}")
    print(f"  Words: {total_words:,}")
    print(f"  Network updates: {total_updates:,}")

    # Network behavior
    print("\nNetwork Behavior:")
    for network, stats in behavior.items():
        if isinstance(stats, dict) and "updates" in stats:
            print(f"  {network}:")
            print(f"    Updates: {stats['updates']}")
            print(f"    Weight norm: {stats['weight_norm']:.4f}")
            if "top_associations" in stats and stats["top_associations"]:
                top = stats["top_associations"][:3]
                assoc_str = ", ".join([f"{a[0]}={a[1]:.3f}" for a in top])
                print(f"    Top associations: {assoc_str}")

    # JSON epochs
    print("\nJSON File Processing:")
    for epoch_num, filepath in session.json_epochs.items():
        epoch = next((e for e in session.epochs if e.epoch_number == epoch_num), None)
        if epoch:
            print(f"  Epoch {epoch_num}: {Path(filepath).name}")
            print(f"    Duration: {epoch.duration_seconds:.1f}s")
            print(f"    Words processed: {epoch.words_processed:,}")

    print("\n" + "=" * 60)


# =============================================================================
# MAIN TEACHING FUNCTION
# =============================================================================


def run_teaching(
    corpus_dir: str,
    profile_name: str,
    json_epochs: dict = None,
    random_seed: int = 42,
    verbose: bool = True,
) -> TeachingSession:
    """
    Run complete teaching session.

    Args:
        corpus_dir: Path to corpus directory
        profile_name: Name of profile to teach
        json_epochs: Dict of epoch → JSON filepath
        random_seed: Random seed for ordering
        verbose: Whether to print progress

    Returns:
        TeachingSession record
    """
    # Ensure directories exist
    Path(PROFILES_DIR).mkdir(parents=True, exist_ok=True)
    Path(SESSIONS_DIR).mkdir(parents=True, exist_ok=True)

    # Initialize
    profile_manager = ProfileManager(profiles_dir=PROFILES_DIR)
    teacher = NetworkTeacher(
        profile_manager=profile_manager,
        profile_name=profile_name,
    )

    if verbose:
        print("\nGSE Network Teaching")
        print("=" * 40)
        print(f"Corpus: {corpus_dir}")
        print(f"Profile: {profile_name}")
        print(f"Random seed: {random_seed}")
        if json_epochs:
            print(f"JSON epochs: {list(json_epochs.keys())}")
        print()

    # Run teaching
    session = teacher.teach(
        corpus_dir=corpus_dir,
        json_files=json_epochs,
        random_seed=random_seed,
        progress_callback=print_progress if verbose else None,
        save_every=5,
    )

    # Get final behavior
    behavior = teacher.get_behavior_summary()

    if verbose:
        print_session_summary(session, behavior)

    # Save session
    session_file = Path(SESSIONS_DIR) / f"session_{profile_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    session.save(str(session_file))

    if verbose:
        print(f"\nSession saved to: {session_file}")

    return session


def show_profile_summary(profile_name: str):
    """Show current profile statistics."""
    profile_manager = ProfileManager(profiles_dir=PROFILES_DIR)

    if not profile_manager.profile_exists(profile_name):
        print(f"Profile '{profile_name}' not found")
        return

    profile = profile_manager.load_profile(profile_name)

    print(f"\nProfile: {profile_name}")
    print("=" * 40)
    print(f"Created: {profile.metadata.created_at[:19]}")
    print(f"Modified: {profile.metadata.modified_at[:19]}")
    print(f"Epochs completed: {profile.metadata.epochs_completed}")
    print(f"Documents processed: {profile.metadata.documents_processed}")
    print(f"Total tokens: {profile.metadata.total_tokens}")

    stats = profile.get_statistics()
    print("\nNetwork Statistics:")
    for key, value in stats.items():
        if "_updates" in key:
            print(f"  {key}: {value}")

    # Show recent epoch history
    if profile.metadata.epoch_history:
        print("\nRecent Epochs:")
        for epoch in profile.metadata.epoch_history[-5:]:
            print(f"  Epoch {epoch['epoch']}: {Path(epoch['file']).name}")


def list_profiles():
    """List all available profiles."""
    profile_manager = ProfileManager(profiles_dir=PROFILES_DIR)
    profiles = profile_manager.list_profiles()

    if not profiles:
        print("No profiles found")
        return

    print("\nAvailable Profiles:")
    print("=" * 40)
    for name in profiles:
        try:
            info = profile_manager.get_profile_info(name)
            epochs = info.get("epochs_completed", 0)
            print(f"  {name}: {epochs} epochs, modified {info.get('modified_at', 'N/A')[:10]}")
        except Exception:
            print(f"  {name}: (error reading info)")


# =============================================================================
# CLI
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Teach GSE learning networks from corpus",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run full teaching session
    python scripts/teach_networks.py --corpus /path/to/corpus

    # Use specific profile
    python scripts/teach_networks.py --profile technical_writing

    # Show profile stats
    python scripts/teach_networks.py --summary --profile default

    # List all profiles
    python scripts/teach_networks.py --list
        """,
    )

    parser.add_argument(
        "--corpus",
        type=str,
        default=DEFAULT_CORPUS,
        help=f"Path to corpus directory (default: {DEFAULT_CORPUS})",
    )

    parser.add_argument(
        "--profile",
        type=str,
        default=DEFAULT_PROFILE,
        help=f"Profile name (default: {DEFAULT_PROFILE})",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for document ordering (default: 42)",
    )

    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show profile summary instead of teaching",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available profiles",
    )

    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Skip large JSON files",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    # Handle commands
    if args.list:
        list_profiles()
        return

    if args.summary:
        show_profile_summary(args.profile)
        return

    # Verify corpus exists
    if not Path(args.corpus).exists():
        print(f"Error: Corpus directory not found: {args.corpus}")
        sys.exit(1)

    # Configure JSON epochs
    json_epochs = None if args.no_json else JSON_EPOCHS

    # Verify JSON files exist
    if json_epochs:
        for epoch, filepath in json_epochs.items():
            if not Path(filepath).exists():
                print(f"Warning: JSON file not found for epoch {epoch}: {filepath}")
                json_epochs = {k: v for k, v in json_epochs.items() if Path(v).exists()}

    # Run teaching
    try:
        run_teaching(
            corpus_dir=args.corpus,
            profile_name=args.profile,
            json_epochs=json_epochs,
            random_seed=args.seed,
            verbose=not args.quiet,
        )

        if not args.quiet:
            print("\nTeaching complete!")

    except KeyboardInterrupt:
        print("\n\nTeaching interrupted. Progress has been saved.")
        sys.exit(1)

    except Exception as e:
        print(f"\nError during teaching: {e}")
        raise


if __name__ == "__main__":
    main()
