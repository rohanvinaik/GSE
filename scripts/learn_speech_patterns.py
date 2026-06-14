#!/usr/bin/env python3
"""
Personal Speech Pattern Learning

Analyzes your conversation history to learn:
1. Vocabulary preferences and phrase patterns
2. Semantic signatures (how you express ideas)
3. Rhetorical patterns (how you structure arguments)
4. Gestalt markers (your pre-verbal expression style)

Usage:
    python scripts/learn_speech_patterns.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List

import ijson


@dataclass
class SpeechPattern:
    """A learned speech pattern."""
    pattern: str
    frequency: int
    examples: List[str]
    category: str


class SpeechPatternLearner:
    """Learns speech patterns from conversation history."""

    # Phrase patterns to detect
    PHRASE_PATTERNS = {
        "hedging": [
            r"\bi think\b", r"\bmaybe\b", r"\bprobably\b", r"\bkind of\b",
            r"\bsort of\b", r"\bi guess\b", r"\bperhaps\b",
        ],
        "emphasis": [
            r"\breally\b", r"\bvery\b", r"\babsolutely\b", r"\bcompletely\b",
            r"\btotally\b", r"\bincredibly\b", r"\bextremely\b",
        ],
        "meta_cognitive": [
            r"\bi'm trying to\b", r"\bwhat i mean is\b", r"\bthe thing is\b",
            r"\bi'm realizing\b", r"\bi notice\b", r"\bit's hard to articulate\b",
            r"\blet me think\b", r"\bwhat's interesting\b",
        ],
        "gestalt": [
            r"\bit's like\b", r"\bthere's this\b", r"\bi can feel\b",
            r"\bsomething about\b", r"\bthe shape of\b", r"\bi just know\b",
        ],
        "reasoning": [
            r"\bbecause\b", r"\btherefore\b", r"\bso\b", r"\bthus\b",
            r"\bwhich means\b", r"\bimplies\b", r"\bconsequently\b",
        ],
        "contrasting": [
            r"\bbut\b", r"\bhowever\b", r"\balthough\b", r"\bwhile\b",
            r"\bwhereas\b", r"\bon the other hand\b", r"\bdespite\b",
        ],
        "analogy": [
            r"\blike\b.*\bbut\b", r"\banalog", r"\bsimilar to\b",
            r"\bremind.*of\b", r"\bis to.*as\b", r"\bmetaphor\b",
        ],
    }

    def __init__(self):
        self.phrase_counts = defaultdict(Counter)
        self.n_grams: Dict[int, Counter] = {2: Counter(), 3: Counter(), 4: Counter()}
        self.vocabulary = Counter()
        self.sentence_starters = Counter()
        self.intensity_words = Counter()
        self.total_messages = 0
        self.total_words = 0

    def learn_from_conversations(self, json_path: Path):
        """Stream through conversations and learn patterns."""
        print(f"Learning speech patterns from: {json_path}")
        print("Streaming through conversations...")

        with open(json_path, 'rb') as f:
            for item in ijson.items(f, 'item'):
                for msg in item.get('chat_messages', []):
                    if msg.get('sender') != 'human':
                        continue

                    text = msg.get('text', '')
                    if len(text) < 20:
                        continue

                    self._analyze_message(text)
                    self.total_messages += 1

                    if self.total_messages % 500 == 0:
                        print(f"  Analyzed {self.total_messages} messages...")

        print(f"\nTotal messages analyzed: {self.total_messages}")
        print(f"Total words: {self.total_words:,}")

    def _analyze_message(self, text: str):
        """Analyze a single message for patterns."""
        text_lower = text.lower()
        words = text_lower.split()
        self.total_words += len(words)

        # Vocabulary
        for word in words:
            word = re.sub(r'[^\w]', '', word)
            if len(word) > 2:
                self.vocabulary[word] += 1

        # Phrase patterns
        for category, patterns in self.PHRASE_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text_lower)
                for match in matches:
                    self.phrase_counts[category][pattern] += 1

        # N-grams
        for n in [2, 3, 4]:
            for i in range(len(words) - n + 1):
                ngram = ' '.join(words[i:i+n])
                # Filter out punctuation-only
                if re.search(r'\w', ngram):
                    self.n_grams[n][ngram] += 1

        # Sentence starters
        sentences = re.split(r'[.!?]+', text)
        for sent in sentences:
            sent = sent.strip()
            if sent:
                first_words = ' '.join(sent.lower().split()[:3])
                if first_words:
                    self.sentence_starters[first_words] += 1

        # Intensity words
        for word in ["fucking", "goddamn", "absolutely", "incredible",
                     "insane", "ridiculous", "unbelievable"]:
            if word in text_lower:
                self.intensity_words[word] += re.findall(word, text_lower).__len__()

    def get_signature(self) -> Dict:
        """Generate a semantic signature of speech patterns."""
        signature = {
            "vocabulary_size": len(self.vocabulary),
            "messages_analyzed": self.total_messages,
            "avg_words_per_message": self.total_words / max(1, self.total_messages),
            "phrase_patterns": {},
            "favorite_words": [],
            "favorite_phrases": [],
            "sentence_starters": [],
            "intensity_profile": {},
        }

        # Phrase pattern summary
        for category, counts in self.phrase_counts.items():
            total = sum(counts.values())
            signature["phrase_patterns"][category] = {
                "total": total,
                "per_message": total / max(1, self.total_messages),
                "top_examples": counts.most_common(3),
            }

        # Top words (excluding common words)
        common_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                       "to", "of", "and", "in", "that", "it", "for", "on", "with",
                       "as", "at", "by", "this", "from", "or", "but", "not", "have",
                       "has", "had", "you", "your", "i", "me", "my", "we", "our"}
        filtered_vocab = [(w, c) for w, c in self.vocabulary.most_common(100)
                         if w not in common_words]
        signature["favorite_words"] = filtered_vocab[:20]

        # Top phrases (3-grams)
        # Filter out low-value phrases
        meaningful_phrases = [(p, c) for p, c in self.n_grams[3].most_common(200)
                             if c > 2 and not all(w in common_words for w in p.split())]
        signature["favorite_phrases"] = meaningful_phrases[:15]

        # Top sentence starters
        signature["sentence_starters"] = self.sentence_starters.most_common(10)

        # Intensity profile
        signature["intensity_profile"] = dict(self.intensity_words.most_common())

        return signature

    def print_report(self):
        """Print a formatted report of speech patterns."""
        sig = self.get_signature()

        print("\n" + "="*70)
        print("YOUR SPEECH PATTERN ANALYSIS")
        print("="*70)

        print("\n📊 Overview")
        print(f"  Messages analyzed: {sig['messages_analyzed']:,}")
        print(f"  Vocabulary size: {sig['vocabulary_size']:,}")
        print(f"  Avg words/message: {sig['avg_words_per_message']:.1f}")

        print("\n🗣️ Phrase Pattern Usage (per 100 messages):")
        for category, data in sorted(sig["phrase_patterns"].items(),
                                    key=lambda x: -x[1]["total"]):
            per_100 = data["per_message"] * 100
            bar = "█" * int(per_100 / 2)
            print(f"  {category:15} {bar} {per_100:.1f}")

        print("\n💬 Your Favorite Words:")
        for i, (word, count) in enumerate(sig["favorite_words"][:10]):
            bar = "█" * min(20, count // 5)
            print(f"  {i+1:2}. {word:15} {bar} ({count})")

        print("\n🔤 Your Signature Phrases:")
        for phrase, count in sig["favorite_phrases"][:10]:
            print(f"  • \"{phrase}\" ({count}x)")

        print("\n🚀 How You Start Sentences:")
        for starter, count in sig["sentence_starters"][:7]:
            print(f"  • \"{starter}...\" ({count}x)")

        if sig["intensity_profile"]:
            print("\n🔥 Intensity Markers:")
            for word, count in sorted(sig["intensity_profile"].items(),
                                     key=lambda x: -x[1])[:5]:
                bar = "█" * min(20, count)
                print(f"  {word:15} {bar} ({count})")

        # Meta-cognitive signature
        meta = sig["phrase_patterns"].get("meta_cognitive", {})
        gestalt = sig["phrase_patterns"].get("gestalt", {})

        print("\n🧠 Cognitive Style:")
        if meta.get("total", 0) > 20:
            print("  HIGH meta-cognitive awareness - you frequently reflect on your thinking")
        if gestalt.get("total", 0) > 10:
            print("  GESTALT expression style - you often describe intuitive/pre-verbal insights")

        hedging = sig["phrase_patterns"].get("hedging", {})
        emphasis = sig["phrase_patterns"].get("emphasis", {})

        if hedging.get("total", 0) > emphasis.get("total", 0):
            print("  TENTATIVE style - more hedging than emphatic")
        else:
            print("  ASSERTIVE style - more emphatic than hedging")

        print(f"\n{'='*70}")

    def save_patterns(self, output_path: Path):
        """Save learned patterns to JSON."""
        sig = self.get_signature()
        with open(output_path, 'w') as f:
            json.dump(sig, f, indent=2)
        print(f"Saved patterns to: {output_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Learn speech patterns from conversations")
    parser.add_argument("--input", type=Path,
                       default=Path("/Users/rohanvinaik/relational-ai/data/training_text/conversations.json"),
                       help="Path to conversations JSON")
    parser.add_argument("--output", type=Path,
                       default=Path("data/speech_patterns.json"),
                       help="Output path for patterns")
    args = parser.parse_args()

    learner = SpeechPatternLearner()
    learner.learn_from_conversations(args.input)
    learner.print_report()
    learner.save_patterns(args.output)


if __name__ == "__main__":
    main()
