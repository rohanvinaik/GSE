#!/usr/bin/env python3
"""
Semantic Encoding Playground

Interactive exploration of GSE's semantic encoding capabilities.
Play with your personal corpus, find semantic patterns, and explore
how meaning is encoded in hyperdimensional space.

Usage:
    python scripts/semantic_playground.py
    python scripts/semantic_playground.py --demo
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from collections import Counter
from typing import Dict, List, Tuple

import numpy as np
from gse.pipeline import GSEResult, load_cascade_pipeline

from gse.patterns.klines import KLineStore


class SemanticPlayground:
    """Interactive exploration of semantic encodings."""

    def __init__(self):
        print("Loading GSE Cascade Pipeline (trained on your corpus)...")
        self.pipeline = load_cascade_pipeline(
            lexicon_path="data/lexicon.db", basis_path="data/basis.msgpack", networks_path="data/networks"
        )
        self.klines = KLineStore()
        self.encoded_cache: Dict[str, GSEResult] = {}
        print("Ready!\n")

    def encode(self, text: str) -> GSEResult:
        """Encode text and cache result."""
        if text not in self.encoded_cache:
            self.encoded_cache[text] = self.pipeline.process(text)
        return self.encoded_cache[text]

    def similarity(self, text1: str, text2: str) -> float:
        """Compute semantic similarity between two texts."""
        return self.pipeline.similarity(text1, text2)

    def show_encoding(self, text: str):
        """Display the semantic encoding of a text."""
        result = self.encode(text)

        print(f"\n{'=' * 60}")
        print(f"TEXT: {text}")
        print(f"{'=' * 60}")
        print(f"Confidence: {result.confidence:.3f}")
        print(f"Processing: {result.processing_time_ms:.1f}ms")
        print(f"Vector: {result.vector.nnz}/{result.vector.dimension} non-zero")

        if result.anomalies:
            print(f"Anomalies: {', '.join(result.anomalies)}")

        # Show vector statistics
        print("\nVector Profile:")
        print(f"  Positive activations: {len(result.vector.positive_indices)}")
        print(f"  Negative activations: {len(result.vector.negative_indices)}")
        print(f"  Density: {result.vector.sparsity * 100:.1f}%")

        return result

    def compare(self, texts: List[str]):
        """Compare multiple texts semantically."""
        print(f"\n{'=' * 60}")
        print("SEMANTIC COMPARISON")
        print(f"{'=' * 60}\n")

        results = [self.encode(t) for t in texts]

        # Print texts
        for i, t in enumerate(texts):
            print(f"[{i + 1}] {t[:60]}{'...' if len(t) > 60 else ''}")

        # Compute similarity matrix
        print("\nSimilarity Matrix:")
        print("    " + "  ".join(f"[{i + 1}]  " for i in range(len(texts))))

        for i in range(len(texts)):
            row = f"[{i + 1}]"
            for j in range(len(texts)):
                sim = results[i].vector.cosine(results[j].vector)
                row += f" {sim:.3f}"
            print(row)

        # Find overlap in vector support
        print("\nVector Overlap Analysis:")
        all_support = [set(r.vector.support.tolist()) for r in results]

        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                shared = len(all_support[i] & all_support[j])
                total = len(all_support[i] | all_support[j])
                overlap = shared / total if total > 0 else 0
                print(f"  [{i + 1}] ∩ [{j + 1}]: {shared} shared dimensions ({overlap * 100:.1f}%)")

    def analogy(self, a: str, b: str, c: str) -> List[Tuple[str, float]]:
        """
        Semantic analogy: A is to B as C is to ?

        Uses vector arithmetic: ? ≈ B - A + C
        """
        print(f"\n{'=' * 60}")
        print(f"ANALOGY: '{a}' is to '{b}' as '{c}' is to ?")
        print(f"{'=' * 60}")

        va = self.encode(a).vector
        vb = self.encode(b).vector
        vc = self.encode(c).vector

        # Compute target vector
        # In HDC we use bundling, but for analogy we use arithmetic
        target = vb.to_dense().astype(float) - va.to_dense().astype(float) + vc.to_dense().astype(float)

        # Find top activated primitives in target
        from gse.vectors import SparseVector

        target_sparse = SparseVector(dimension=va.dimension)

        # Get top components
        top_indices = np.argsort(np.abs(target))[-20:]
        for idx in top_indices:
            # Find primitive name (this is approximate)
            target_sparse.indices[len(target_sparse.indices)] = idx
            target_sparse.values[len(target_sparse.values)] = target[idx]

        print("\nTarget semantic direction:")
        for i, (idx, val) in enumerate(zip(target_sparse.indices.values(), target_sparse.values.values())):
            if i >= 10:
                break
            print(f"  Component {idx}: {val:.2f}")

        return []

    def cluster_texts(self, texts: List[str], n_clusters: int = 3):
        """Cluster texts by semantic similarity."""
        print(f"\n{'=' * 60}")
        print(f"SEMANTIC CLUSTERING ({n_clusters} clusters)")
        print(f"{'=' * 60}\n")

        results = [self.encode(t) for t in texts]
        vectors = np.array([r.vector.to_dense() for r in results])

        # Simple k-means-ish clustering
        # Pick initial centroids
        centroid_indices = np.random.choice(len(texts), n_clusters, replace=False)
        centroids = vectors[centroid_indices]

        # Assign to clusters
        for iteration in range(10):
            # Compute distances to centroids
            distances = np.zeros((len(texts), n_clusters))
            for i, vec in enumerate(vectors):
                for j, centroid in enumerate(centroids):
                    distances[i, j] = 1 - np.dot(vec, centroid) / (
                        np.linalg.norm(vec) * np.linalg.norm(centroid) + 1e-8
                    )

            # Assign to nearest centroid
            assignments = np.argmin(distances, axis=1)

            # Update centroids
            new_centroids = np.zeros_like(centroids)
            for j in range(n_clusters):
                members = vectors[assignments == j]
                if len(members) > 0:
                    new_centroids[j] = members.mean(axis=0)
            centroids = new_centroids

        # Print clusters
        for j in range(n_clusters):
            members = [texts[i] for i in range(len(texts)) if assignments[i] == j]
            print(f"\nCluster {j + 1} ({len(members)} texts):")
            for m in members[:5]:
                print(f"  - {m[:70]}{'...' if len(m) > 70 else ''}")
            if len(members) > 5:
                print(f"  ... and {len(members) - 5} more")

    def find_your_patterns(self, corpus_path: str):
        """Analyze your writing patterns from the corpus."""
        print(f"\n{'=' * 60}")
        print("ANALYZING YOUR SEMANTIC PATTERNS")
        print(f"{'=' * 60}\n")

        path = Path(corpus_path)
        if not path.exists():
            print(f"Corpus not found: {corpus_path}")
            return

        # Load and encode samples from corpus
        all_prims = Counter()
        intensity_patterns = []
        meta_markers = []

        files = list(path.glob("*.txt"))[:20]  # Sample 20 files
        print(f"Analyzing {len(files)} documents...")

        for file in files:
            try:
                text = file.read_text(encoding="utf-8", errors="replace")[:2000]
                result = self.encode(text[:500])  # First 500 chars

                # Count primitive usage
                for prim, val in result.vector.top_k(10):
                    if val > 0.1:
                        all_prims[prim] += 1

                # Detect intensity
                text_lower = text.lower()
                if any(m in text_lower for m in ["fucking", "absolute", "incredible"]):
                    intensity_patterns.append(file.stem)

                # Detect meta-cognition
                if any(m in text_lower for m in ["i'm trying to", "what i mean is", "the thing is"]):
                    meta_markers.append(file.stem)

            except Exception:
                continue

        # Report findings
        print("\n📊 Your Dominant Semantic Primitives:")
        for prim, count in all_prims.most_common(15):
            bar = "█" * (count * 2)
            print(f"  {prim:15} {bar} ({count})")

        print(f"\n🔥 High-Intensity Documents ({len(intensity_patterns)}):")
        for doc in intensity_patterns[:5]:
            print(f"  - {doc}")

        print(f"\n🧠 Meta-Cognitive Reflection ({len(meta_markers)}):")
        for doc in meta_markers[:5]:
            print(f"  - {doc}")

        # Semantic signature
        print("\n✨ Your Semantic Signature:")
        sig_prims = [p for p, _ in all_prims.most_common(5)]
        print(f"  {' + '.join(sig_prims)}")

    def interactive(self):
        """Interactive REPL for exploration."""
        print("""
╔══════════════════════════════════════════════════════════╗
║         GSE Semantic Encoding Playground                 ║
╠══════════════════════════════════════════════════════════╣
║ Commands:                                                ║
║   encode <text>     - Show semantic encoding             ║
║   compare           - Compare multiple texts             ║
║   similar <text>    - Find similar concepts              ║
║   patterns          - Analyze your writing patterns      ║
║   demo              - Run demo comparisons               ║
║   quit              - Exit                               ║
╚══════════════════════════════════════════════════════════╝
        """)

        while True:
            try:
                cmd = input("\n🔮 > ").strip()

                if not cmd:
                    continue

                if cmd.lower() in ["quit", "exit", "q"]:
                    print("Goodbye!")
                    break

                if cmd.lower().startswith("encode "):
                    text = cmd[7:]
                    self.show_encoding(text)

                elif cmd.lower() == "compare":
                    print("Enter texts to compare (empty line to finish):")
                    texts = []
                    while True:
                        t = input(f"  [{len(texts) + 1}] ").strip()
                        if not t:
                            break
                        texts.append(t)
                    if len(texts) >= 2:
                        self.compare(texts)

                elif cmd.lower().startswith("similar "):
                    text = cmd[8:]
                    # This would need a corpus to search
                    result = self.encode(text)
                    print(f"\nSemantic fingerprint for: {text}")
                    print(f"Top primitives: {[p for p, _ in result.vector.top_k(5)]}")

                elif cmd.lower() == "patterns":
                    self.find_your_patterns("/Users/rohanvinaik/relational-ai/data/training_text")

                elif cmd.lower() == "demo":
                    self.run_demo()

                else:
                    # Treat as text to encode
                    self.show_encoding(cmd)

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")

    def run_demo(self):
        """Run demonstration of capabilities."""
        print("\n" + "=" * 60)
        print("DEMO: Exploring Semantic Space")
        print("=" * 60)

        # Demo 1: Similar concepts
        print("\n[1] SEMANTIC SIMILARITY")
        pairs = [
            ("happy", "joyful"),
            ("happy", "sad"),
            ("run", "sprint"),
            ("think", "ponder"),
            ("dog", "cat"),
            ("dog", "philosophy"),
        ]

        for a, b in pairs:
            sim = self.similarity(a, b)
            bar = "█" * int(sim * 20)
            print(f"  '{a}' ↔ '{b}': {bar} {sim:.3f}")

        # Demo 2: Sentence comparison
        print("\n[2] SENTENCE SEMANTICS")
        sentences = [
            "The constraint propagation eliminates invalid interpretations.",
            "Invalid options are removed through constraint satisfaction.",
            "The happy dog runs through the park.",
            "I'm trying to articulate something hard to express.",
        ]
        self.compare(sentences)

        # Demo 3: Your patterns
        print("\n[3] YOUR SEMANTIC SIGNATURE")
        self.find_your_patterns("/Users/rohanvinaik/relational-ai/data/training_text")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Semantic Encoding Playground")
    parser.add_argument("--demo", action="store_true", help="Run demo")
    parser.add_argument("--encode", type=str, help="Encode specific text")
    parser.add_argument("--patterns", action="store_true", help="Analyze your patterns")
    args = parser.parse_args()

    playground = SemanticPlayground()

    if args.demo:
        playground.run_demo()
    elif args.encode:
        playground.show_encoding(args.encode)
    elif args.patterns:
        playground.find_your_patterns("/Users/rohanvinaik/relational-ai/data/training_text")
    else:
        playground.interactive()


if __name__ == "__main__":
    main()
