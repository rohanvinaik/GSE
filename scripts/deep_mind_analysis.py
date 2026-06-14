#!/usr/bin/env python3
"""
Deep Mind Analysis via GSE

Uses the trained learning networks and semantic encoding to provide
deep analysis of a person's thinking style, cognitive patterns, and
semantic signature based on their writing.

This is interpretable AI introspection - using math to understand mind.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

import numpy as np
from gse.cascade import ConstraintCascade
from gse.primitives import PRIMITIVE_TO_BANK


@dataclass
class CognitiveProfile:
    """Complete cognitive profile from semantic analysis."""
    # Core primitive affinities
    dominant_primitives: List[Tuple[str, float]] = field(default_factory=list)
    suppressed_primitives: List[Tuple[str, float]] = field(default_factory=list)

    # Bank-level patterns
    bank_affinities: Dict[str, float] = field(default_factory=dict)

    # Pattern co-occurrences (what primitives fire together)
    thought_patterns: List[Tuple[Set[str], int]] = field(default_factory=list)

    # Polarity balance
    positive_bias: float = 0.0
    negative_bias: float = 0.0

    # Cognitive style metrics
    abstraction_level: float = 0.0  # Abstract vs concrete
    agency_level: float = 0.0       # Active vs passive
    certainty_level: float = 0.0    # Certain vs hedging
    temporal_focus: str = ""        # Past, present, future oriented
    social_orientation: float = 0.0  # Self vs other focused

    # Unique signature
    semantic_fingerprint: List[int] = field(default_factory=list)


class DeepMindAnalyzer:
    """Analyze mind/thinking patterns through GSE encodings."""

    def __init__(self):
        print("Loading GSE system...")
        self.cascade = ConstraintCascade(
            lexicon_path='data/lexicon.db',
            basis_path='data/basis.msgpack'
        )
        self.cascade.load_networks('data/networks')

        # Load trained network for pattern analysis
        self.word_network = self.cascade.word_network

        # Bank names for interpretation
        self.bank_names = [
            'SUBSTANTIVES', 'DETERMINERS', 'EVALUATORS', 'MENTAL',
            'ACTION', 'TEMPORAL', 'SPATIAL', 'LOGICAL'
        ]

        print("Ready for deep analysis.\n")

    def analyze_network_patterns(self) -> Dict:
        """Analyze what the trained network learned about the person's patterns."""
        print("=" * 70)
        print("LEARNED PATTERN ANALYSIS")
        print("(What the network learned from your writing)")
        print("=" * 70)

        patterns_raw = self.word_network.patterns
        nodes = self.word_network.nodes
        weights = np.array(self.word_network.weights)

        # Handle patterns as dict or list
        if isinstance(patterns_raw, dict):
            patterns = list(patterns_raw.values())
        else:
            patterns = patterns_raw

        results = {
            'total_patterns': len(patterns),
            'total_observations': self.word_network.total_observations,
            'top_patterns': [],
            'primitive_centrality': {},
            'strongest_associations': [],
            'bank_connectivity': {},
        }

        # Top patterns (most frequent co-occurrences)
        # Handle CompoundPattern objects or dicts
        def get_freq(p):
            if hasattr(p, 'frequency'):
                return p.frequency
            elif isinstance(p, dict):
                return p.get('frequency', p.get('freq', 0))
            return 0

        sorted_patterns = sorted(patterns, key=get_freq, reverse=True)

        print("\n📊 Network Statistics:")
        print(f"   Patterns learned: {len(patterns)}")
        print(f"   Total observations: {self.word_network.total_observations}")

        print("\n🧠 Your Most Common Thought Patterns:")
        print("   (Primitives that fire together in your writing)")

        for i, p in enumerate(sorted_patterns[:15]):
            # Handle CompoundPattern objects or dicts
            if hasattr(p, 'trigger'):
                trigger = p.trigger
                freq = p.frequency
                conf = p.confidence
            else:
                trigger = p.get('trigger', p.get('primitives', []))
                freq = p.get('frequency', p.get('freq', 0))
                conf = p.get('confidence', 0.5)

            prims = {nodes[idx] if isinstance(idx, int) else idx for idx in trigger}
            results['top_patterns'].append((prims, freq, conf))

            # Interpret the pattern
            interpretation = self._interpret_pattern(prims)
            print(f"\n   {i+1}. {prims}")
            print(f"      Frequency: {freq}x | Confidence: {conf:.2f}")
            print(f"      → {interpretation}")

        # Primitive centrality (which primitives are most connected)
        print("\n🎯 Primitive Centrality in Your Thinking:")
        print("   (How central each concept is to your expression)")

        centrality = {}
        for i, node in enumerate(nodes):
            # Sum of connection weights
            centrality[node] = float(np.sum(np.abs(weights[i, :])))

        sorted_centrality = sorted(centrality.items(), key=lambda x: -x[1])
        results['primitive_centrality'] = dict(sorted_centrality)

        for prim, score in sorted_centrality[:12]:
            bar = "█" * int(score * 3)
            bank = PRIMITIVE_TO_BANK.get(prim, "?")
            print(f"   {prim:12} {bar} ({score:.2f}) [{bank}]")

        # Strongest associations (pairs that co-occur most)
        print("\n🔗 Strongest Primitive Associations:")
        print("   (Concepts you consistently link together)")

        associations = []
        for i in range(len(nodes)):
            for j in range(i+1, len(nodes)):
                if weights[i, j] > 0.1:
                    associations.append((nodes[i], nodes[j], weights[i, j]))

        associations.sort(key=lambda x: -x[2])
        results['strongest_associations'] = associations[:20]

        for n1, n2, w in associations[:10]:
            print(f"   {n1} ↔ {n2}: {w:.3f}")

        return results

    def _interpret_pattern(self, prims: Set[str]) -> str:
        """Provide natural language interpretation of a primitive pattern."""
        interpretations = []

        # Check for specific combinations
        if 'FEEL' in prims and 'GOOD' in prims:
            interpretations.append("emotional positive expression")
        if 'THINK' in prims and 'KNOW' in prims:
            interpretations.append("epistemic reasoning")
        if 'SOMEONE' in prims and 'DO' in prims:
            interpretations.append("agent-action framing")
        if 'SOMETHING' in prims and 'BE' in prims:
            interpretations.append("existential/state description")
        if 'BECAUSE' in prims:
            interpretations.append("causal reasoning")
        if 'NOT' in prims:
            interpretations.append("negation/contrast")
        if 'WANT' in prims:
            interpretations.append("desire/goal expression")
        if 'MOVE' in prims:
            interpretations.append("dynamic/process thinking")
        if 'WHERE' in prims or 'ABOVE' in prims or 'INSIDE' in prims:
            interpretations.append("spatial metaphor")
        if 'NOW' in prims or 'BEFORE' in prims:
            interpretations.append("temporal anchoring")

        if not interpretations:
            return "complex conceptual blend"
        return " + ".join(interpretations)

    def analyze_corpus(self, corpus_path: str, sample_size: int = 50) -> Dict:
        """Analyze a corpus of text for deep semantic patterns."""
        print("\n" + "=" * 70)
        print("CORPUS SEMANTIC ANALYSIS")
        print("=" * 70)

        path = Path(corpus_path)
        if not path.exists():
            print(f"Corpus not found: {corpus_path}")
            return {}

        # Collect all text samples
        texts = []
        if path.is_dir():
            for f in list(path.glob("*.txt"))[:sample_size]:
                try:
                    texts.append(f.read_text(encoding='utf-8', errors='replace')[:2000])
                except:
                    continue

        print(f"\nAnalyzing {len(texts)} text samples...")

        # Aggregate vectors
        all_vectors = []
        bank_activations = defaultdict(list)
        primitive_activations = Counter()
        polarity_counts = {'positive': 0, 'negative': 0}

        for text in texts:
            result = self.cascade.process(text[:1000])
            vec = result.vector.to_dense()
            all_vectors.append(vec)

            # Analyze by bank
            for i, bank in enumerate(self.bank_names):
                start, end = i * 1024, (i + 1) * 1024
                bank_energy = np.sum(np.abs(vec[start:end]))
                bank_activations[bank].append(bank_energy)

            # Count polarity
            polarity_counts['positive'] += len(result.vector.positive_indices)
            polarity_counts['negative'] += len(result.vector.negative_indices)

        # Compute aggregate statistics
        mean_vector = np.mean(all_vectors, axis=0)
        std_vector = np.std(all_vectors, axis=0)

        results = {
            'samples_analyzed': len(texts),
            'bank_profiles': {},
            'consistency_score': 0.0,
            'polarity_balance': 0.0,
        }

        print("\n📈 Semantic Bank Energy Profile:")
        print("   (Which types of meaning you activate most)")

        for bank in self.bank_names:
            activations = bank_activations[bank]
            mean_act = np.mean(activations)
            std_act = np.std(activations)
            results['bank_profiles'][bank] = {'mean': mean_act, 'std': std_act}

            bar = "█" * int(mean_act / 100)
            consistency = "±" + str(int(std_act))
            print(f"   {bank:15} {bar} ({mean_act:.0f} {consistency})")

        # Polarity balance
        total_pol = polarity_counts['positive'] + polarity_counts['negative']
        if total_pol > 0:
            pos_ratio = polarity_counts['positive'] / total_pol
            results['polarity_balance'] = pos_ratio
            print("\n⚖️  Polarity Balance:")
            print(f"   Positive: {pos_ratio*100:.1f}%")
            print(f"   Negative: {(1-pos_ratio)*100:.1f}%")

        # Semantic consistency (how stable is your semantic signature?)
        if len(all_vectors) > 1:
            # Compute pairwise similarities
            similarities = []
            for i in range(min(20, len(all_vectors))):
                for j in range(i+1, min(20, len(all_vectors))):
                    v1, v2 = all_vectors[i], all_vectors[j]
                    sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
                    similarities.append(sim)

            consistency = np.mean(similarities)
            results['consistency_score'] = consistency
            print(f"\n🎯 Semantic Consistency Score: {consistency:.3f}")
            print("   (How stable your semantic signature is across texts)")
            if consistency > 0.6:
                print("   → HIGH consistency: very distinctive voice")
            elif consistency > 0.4:
                print("   → MODERATE consistency: recognizable but varied")
            else:
                print("   → LOW consistency: highly adaptive/varied style")

        return results

    def compute_cognitive_profile(self, texts: List[str]) -> CognitiveProfile:
        """Compute a complete cognitive profile from text samples."""
        print("\n" + "=" * 70)
        print("COGNITIVE PROFILE SYNTHESIS")
        print("=" * 70)

        profile = CognitiveProfile()

        # Encode all texts
        vectors = []
        for text in texts[:30]:
            result = self.cascade.process(text[:1000])
            vectors.append(result.vector.to_dense())

        if not vectors:
            return profile

        mean_vec = np.mean(vectors, axis=0)

        # Analyze bank affinities
        print("\n🧠 Your Cognitive Bank Affinities:")

        for i, bank in enumerate(self.bank_names):
            start, end = i * 1024, (i + 1) * 1024
            energy = np.sum(np.abs(mean_vec[start:end]))
            profile.bank_affinities[bank] = energy

        # Normalize
        total_energy = sum(profile.bank_affinities.values())
        for bank in profile.bank_affinities:
            profile.bank_affinities[bank] /= total_energy
            pct = profile.bank_affinities[bank] * 100
            bar = "█" * int(pct * 2)
            print(f"   {bank:15} {bar} ({pct:.1f}%)")

        # Derive cognitive style metrics
        print("\n📊 Derived Cognitive Style Metrics:")

        # Abstraction level (SOMETHING/SOMEONE vs concrete entities)
        substantive_pct = profile.bank_affinities.get('SUBSTANTIVES', 0)
        profile.abstraction_level = 1.0 - substantive_pct * 2  # Higher = more abstract
        print(f"   Abstraction Level: {profile.abstraction_level:.2f}")
        print(f"   → {'Abstract/conceptual thinker' if profile.abstraction_level > 0.3 else 'Concrete/grounded thinker'}")

        # Agency level (ACTION vs static)
        action_pct = profile.bank_affinities.get('ACTION', 0)
        profile.agency_level = action_pct * 3
        print(f"   Agency Level: {profile.agency_level:.2f}")
        print(f"   → {'Active/dynamic framing' if profile.agency_level > 0.3 else 'Static/state-based framing'}")

        # Logical orientation
        logical_pct = profile.bank_affinities.get('LOGICAL', 0)
        profile.certainty_level = logical_pct * 3
        print(f"   Logical Density: {profile.certainty_level:.2f}")
        print(f"   → {'Highly structured reasoning' if profile.certainty_level > 0.3 else 'Flowing/intuitive expression'}")

        # Temporal focus
        temporal_pct = profile.bank_affinities.get('TEMPORAL', 0)
        print(f"   Temporal Focus: {temporal_pct*100:.1f}%")

        # Mental/Evaluative (introspection)
        mental_pct = profile.bank_affinities.get('MENTAL', 0)
        eval_pct = profile.bank_affinities.get('EVALUATORS', 0)
        introspection = (mental_pct + eval_pct) * 2
        print(f"   Introspection Level: {introspection:.2f}")
        print(f"   → {'Highly reflective/meta-cognitive' if introspection > 0.3 else 'Externally focused'}")

        # Thought patterns from network
        print("\n🔮 Your Signature Thought Patterns:")
        patterns_raw = self.word_network.patterns
        nodes = self.word_network.nodes

        if isinstance(patterns_raw, dict):
            patterns = list(patterns_raw.values())
        else:
            patterns = patterns_raw

        def get_freq(p):
            if hasattr(p, 'frequency'):
                return p.frequency
            elif isinstance(p, dict):
                return p.get('frequency', p.get('freq', 0))
            return 0

        top_patterns = sorted(patterns, key=get_freq, reverse=True)[:5]
        for p in top_patterns:
            if hasattr(p, 'trigger'):
                trigger = p.trigger
                freq = p.frequency
            else:
                trigger = p.get('trigger', p.get('primitives', []))
                freq = p.get('frequency', p.get('freq', 0))
            prims = {nodes[idx] if isinstance(idx, int) else idx for idx in trigger}
            profile.thought_patterns.append((prims, freq))
            print(f"   • {prims}")

        return profile

    def generate_deep_insights(self, profile: CognitiveProfile) -> str:
        """Generate deep psychological/cognitive insights from profile."""
        print("\n" + "=" * 70)
        print("DEEP COGNITIVE INSIGHTS")
        print("=" * 70)

        insights = []

        # Bank-based insights
        banks = profile.bank_affinities

        # Dominant banks
        sorted_banks = sorted(banks.items(), key=lambda x: -x[1])
        top_banks = [b for b, _ in sorted_banks[:3]]

        print(f"\n🎭 Primary Cognitive Modes: {', '.join(top_banks)}")

        # Specific combinations
        if 'LOGICAL' in top_banks and 'MENTAL' in top_banks:
            insight = """
Your thinking is characterized by LOGICAL-MENTAL dominance:
You naturally frame ideas through structured reasoning combined with
psychological/cognitive awareness. This manifests as analytical introspection -
you don't just think about things, you think about HOW you think about things.
This is the signature of a meta-cognitive reasoner."""
            insights.append(insight)
            print(insight)

        if 'ACTION' in top_banks:
            insight = """
Strong ACTION bank activation indicates process-oriented thinking:
You conceptualize the world in terms of dynamics, changes, and movements
rather than static states. Ideas for you are things that DO something,
not just things that ARE."""
            insights.append(insight)
            print(insight)

        if 'EVALUATORS' in top_banks:
            insight = """
High EVALUATOR activation suggests value-laden cognition:
You naturally frame experiences in terms of good/bad, big/small, etc.
This isn't superficial judgment - it's how you organize meaning.
Every concept carries evaluative weight in your mental space."""
            insights.append(insight)
            print(insight)

        if 'SPATIAL' in top_banks:
            insight = """
Strong SPATIAL bank suggests embodied/metaphorical thinking:
You understand abstract concepts through spatial metaphor - ideas are
"above" or "below" others, arguments have "shape", thoughts are "inside".
This is characteristic of highly embodied cognition."""
            insights.append(insight)
            print(insight)

        # Pattern-based insights
        patterns = profile.thought_patterns
        pattern_prims = set()
        for prims, _ in patterns:
            pattern_prims.update(prims)

        print(f"\n🧬 Your Primitive Vocabulary: {pattern_prims}")

        if 'BECAUSE' in pattern_prims:
            insight = """
BECAUSE appears in your core patterns:
Causal reasoning is fundamental to how you structure thought.
You naturally seek and express explanatory connections."""
            insights.append(insight)
            print(insight)

        if 'NOT' in pattern_prims:
            insight = """
NOT is central to your expression:
You think in terms of what things are NOT as much as what they ARE.
This suggests dialectical thinking - understanding through contrast."""
            insights.append(insight)
            print(insight)

        if 'FEEL' in pattern_prims and 'THINK' in pattern_prims:
            insight = """
Both FEEL and THINK are core primitives:
You integrate emotional and cognitive processing naturally.
This isn't "thinking vs feeling" - it's thinking-feeling as unified mode."""
            insights.append(insight)
            print(insight)

        # Synthesis
        print("\n" + "=" * 70)
        print("COGNITIVE SIGNATURE SYNTHESIS")
        print("=" * 70)

        synthesis = f"""
Based on the geometric analysis of your semantic encodings:

DOMINANT MODE: {', '.join(top_banks[:2])}
Your mind naturally gravitates toward {top_banks[0].lower()} framings,
enriched by {top_banks[1].lower()} dimensions.

ABSTRACTION: {'High' if profile.abstraction_level > 0.3 else 'Moderate' if profile.abstraction_level > 0 else 'Grounded'}
You operate {'in the realm of concepts and relationships' if profile.abstraction_level > 0.3 else 'with concrete, tangible ideas'}.

AGENCY: {'High' if profile.agency_level > 0.3 else 'Moderate'}
You frame the world {'dynamically, in terms of actions and processes' if profile.agency_level > 0.3 else 'more statically, in terms of states and properties'}.

CORE PATTERNS: {len(patterns)} signature thought-forms learned
These represent the atomic "shapes" of your thinking - the recurring
ways you combine semantic primitives to express meaning.

This profile is INTERPRETABLE: every metric traces to specific
primitive activations in 8192-dimensional semantic space.
Unlike neural embeddings, these dimensions have MEANING.
"""
        print(synthesis)

        return synthesis

    def voice_signature_analysis(self, your_text: str, generic_text: str) -> Dict:
        """Analyze the geometric difference between your voice and generic."""
        print("\n" + "=" * 70)
        print("VOICE SIGNATURE EXTRACTION")
        print("=" * 70)

        your_vec = self.cascade.process(your_text).vector.to_dense()
        generic_vec = self.cascade.process(generic_text).vector.to_dense()

        delta = your_vec - generic_vec

        # Bank-level analysis
        print("\n📊 Bank-Level Voice Shifts:")

        shifts = {}
        for i, bank in enumerate(self.bank_names):
            start, end = i * 1024, (i + 1) * 1024
            bank_delta = delta[start:end]
            net_shift = np.sum(bank_delta)
            shifts[bank] = net_shift

            direction = "↑" if net_shift > 0 else "↓"
            bar_len = min(30, int(abs(net_shift) / 30))
            bar = ("+" if net_shift > 0 else "-") * bar_len
            print(f"   {bank:15} {direction} {bar} ({net_shift:+.0f})")

        # Interpretation
        print("\n🎭 Voice Signature Interpretation:")

        sorted_shifts = sorted(shifts.items(), key=lambda x: abs(x[1]), reverse=True)

        for bank, shift in sorted_shifts[:4]:
            direction = "ELEVATED" if shift > 0 else "SUPPRESSED"
            print(f"   {bank}: {direction}")

            if bank == 'LOGICAL' and shift > 0:
                print("      → More connective, flowing reasoning")
            elif bank == 'EVALUATORS' and shift < 0:
                print("      → Less explicit judgment, more implicit")
            elif bank == 'ACTION' and shift > 0:
                print("      → More dynamic, process-oriented language")
            elif bank == 'MENTAL' and shift > 0:
                print("      → More introspective, meta-cognitive")
            elif bank == 'TEMPORAL' and shift < 0:
                print("      → Less time-anchored, more timeless")

        return {'shifts': shifts, 'delta': delta}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Deep Mind Analysis via GSE")
    parser.add_argument("--corpus", type=str,
                       default="/Users/rohanvinaik/relational-ai/data/training_text",
                       help="Path to text corpus")
    parser.add_argument("--full", action="store_true", help="Run full analysis")
    args = parser.parse_args()

    analyzer = DeepMindAnalyzer()

    # 1. Analyze what the network learned
    network_results = analyzer.analyze_network_patterns()

    # 2. Analyze the corpus
    corpus_results = analyzer.analyze_corpus(args.corpus)

    # 3. Load sample texts for profile
    corpus_path = Path(args.corpus)
    sample_texts = []
    if corpus_path.is_dir():
        for f in list(corpus_path.glob("*.txt"))[:30]:
            try:
                sample_texts.append(f.read_text(encoding='utf-8', errors='replace')[:1500])
            except:
                continue

    # 4. Compute cognitive profile
    if sample_texts:
        profile = analyzer.compute_cognitive_profile(sample_texts)

        # 5. Generate deep insights
        insights = analyzer.generate_deep_insights(profile)

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)
    print("\nThis analysis used interpretable semantic primitives to understand")
    print("your cognitive patterns. Every insight traces to specific dimensions")
    print("in the 8192-dimensional geometric semantic space.")


if __name__ == "__main__":
    main()
