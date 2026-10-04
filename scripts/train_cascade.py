#!/usr/bin/env python3
"""
Train the Constraint Cascade Networks

Trains:
1. WordScaleNetwork (24 nodes) - from lexicon decompositions
2. OrchestratorNetwork (36 nodes) - from text corpus

Usage:
    python scripts/train_cascade.py --lexicon data/lexicon.db --corpus /path/to/texts
    python scripts/train_cascade.py --all  # Use default paths
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gse.cascade import ConstraintCascade


def main():
    parser = argparse.ArgumentParser(description="Train cascade networks")
    parser.add_argument("--lexicon", type=str, default="data/lexicon.db", help="Path to lexicon database")
    parser.add_argument("--basis", type=str, default="data/basis.msgpack", help="Path to basis vectors")
    parser.add_argument(
        "--corpus",
        type=str,
        default="/Users/rohanvinaik/relational-ai/data/training_text",
        help="Path to text corpus directory",
    )
    parser.add_argument("--output", type=str, default="data/networks", help="Output directory for trained networks")
    parser.add_argument("--all", action="store_true", help="Train all networks with default paths")

    args = parser.parse_args()

    # Resolve paths
    base = Path(__file__).parent.parent
    lexicon_path = base / args.lexicon
    basis_path = base / args.basis
    corpus_path = Path(args.corpus)
    output_path = base / args.output

    print("=" * 60)
    print("GSE Constraint Cascade Training")
    print("=" * 60)
    print(f"\nLexicon: {lexicon_path}")
    print(f"Basis: {basis_path}")
    print(f"Corpus: {corpus_path}")
    print(f"Output: {output_path}")

    # Create cascade
    print("\nInitializing cascade...")
    cascade = ConstraintCascade(
        lexicon_path=str(lexicon_path) if lexicon_path.exists() else None,
        basis_path=str(basis_path) if basis_path.exists() else None,
        use_cache=False,  # No caching during training
    )

    # Train
    print("\n" + "-" * 40)
    print("Training networks...")
    print("-" * 40)

    stats = cascade.train(
        lexicon_path=str(lexicon_path) if lexicon_path.exists() else None,
        corpus_dir=str(corpus_path) if corpus_path.exists() else None,
    )

    # Report results
    print("\n" + "-" * 40)
    print("Training Results")
    print("-" * 40)

    for key, value in stats.items():
        print(f"  {key}: {value:,}")

    # Save networks
    print(f"\nSaving networks to {output_path}...")
    cascade.save_networks(str(output_path))

    # Quick validation
    print("\n" + "-" * 40)
    print("Validation")
    print("-" * 40)

    # Test word network predictions
    test_prims = {"FEEL", "GOOD"}
    predictions = cascade.word_network.predict(test_prims, top_k=5)
    print(f"\nWord network test - Input: {test_prims}")
    print(f"  Predictions: {predictions}")

    # Test orchestrator routing
    test_features = {"ROUTE_TEXT": 1.0, "CONF_HIGH": 0.8}
    routing = cascade.orchestrator.route_decision(test_features)
    print(f"\nOrchestrator test - Input: {test_features}")
    print(f"  Routing: {dict(list(routing.items())[:5])}")

    # Test full cascade on sample text
    sample_text = "The happy dog runs quickly through the park."
    print(f"\nFull cascade test: '{sample_text}'")

    result = cascade.process(sample_text)
    print(f"  Confidence: {result.confidence:.3f}")
    print(f"  Processing time: {result.processing_time * 1000:.1f}ms")
    print(f"  Vector density: {result.vector.nnz}/{result.vector.dimension}")
    print(f"  Ambiguities: {result.ambiguities}")

    for scale, frame in result.frames.items():
        active_str = ", ".join(f"{k}:{v:.2f}" for k, v in list(frame.active.items())[:3])
        print(f"  {scale.value}: {active_str}")

    print("\n" + "=" * 60)
    print("Training complete!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
