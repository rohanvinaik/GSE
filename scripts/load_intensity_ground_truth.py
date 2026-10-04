#!/usr/bin/env python3
"""
Load and parse external intensity ground truth data for GSE modifier validation.

Sources:
- acocos/scalar-adj: DeMelo, Crowd, Wilkinson scales
- SO-CAL sentiment dictionary
- Linguistic literature on degree adverbs

Usage:
    from scripts.load_intensity_ground_truth import get_modifier_ground_truth

    gt = get_modifier_ground_truth()
    level = gt.get_level("extremely")  # Returns 2
    expected = gt.get_expected_encoding("very")  # Returns {"INTENSITY": 1, "HIER_PLUS": 1}
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class ModifierEntry:
    """A modifier word with its ground truth intensity level."""

    word: str
    hierarchy_type: str  # "INTENSITY", "QUANTITY", "CERTAINTY"
    level: int  # -3 to +3
    category: str  # e.g., "minimal", "high", "absolute"
    source: str  # Which dataset it came from
    notes: str = ""


class IntensityGroundTruth:
    """
    Ground truth database for modifier intensity validation.
    """

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data" / "external"
        self.data_dir = Path(data_dir)

        self.modifiers: Dict[str, ModifierEntry] = {}
        self.scalar_scales: Dict[str, List[str]] = {}

        self._load_consolidated_ground_truth()
        self._load_scalar_adj_rankings()

    def _load_consolidated_ground_truth(self):
        """Load the consolidated JSON ground truth."""
        gt_path = self.data_dir / "intensity_ground_truth.json"
        if not gt_path.exists():
            print(f"Warning: {gt_path} not found")
            return

        with open(gt_path) as f:
            data = json.load(f)

        # Load degree adverbs -> INTENSITY
        for category in ["scale_diminishing", "scale_neutral", "scale_intensifying", "scale_absolute"]:
            if category in data.get("degree_adverbs", {}):
                for entry in data["degree_adverbs"][category]:
                    word = entry["word"].lower()
                    self.modifiers[word] = ModifierEntry(
                        word=word,
                        hierarchy_type="INTENSITY",
                        level=entry["level"],
                        category=entry.get("category", category),
                        source="consolidated_ground_truth",
                        notes=entry.get("note", ""),
                    )

        # Load quantity determiners -> QUANTITY
        for entry in data.get("quantity_determiners", {}).get("scale", []):
            word = entry["word"].lower()
            self.modifiers[word] = ModifierEntry(
                word=word,
                hierarchy_type="QUANTITY",
                level=entry["level"],
                category="quantity",
                source="consolidated_ground_truth",
                notes=entry.get("note", ""),
            )

        # Load epistemic modality -> CERTAINTY
        for entry in data.get("epistemic_modality", {}).get("scale", []):
            word = entry["word"].lower()
            self.modifiers[word] = ModifierEntry(
                word=word,
                hierarchy_type="CERTAINTY",
                level=entry["level"],
                category="epistemic",
                source="consolidated_ground_truth",
                notes=entry.get("note", ""),
            )

        # Load scalar adjective scales
        for scale_name, scale_data in data.get("scalar_adjectives", {}).items():
            if scale_name.startswith("_"):
                continue
            if "scale" in scale_data:
                self.scalar_scales[scale_name] = scale_data["scale"]

    def _load_scalar_adj_rankings(self):
        """Load rankings from acocos/scalar-adj dataset."""
        scalar_adj_dir = self.data_dir / "scalar-adj"
        if not scalar_adj_dir.exists():
            return

        # Load DeMelo gold rankings
        demelo_dir = scalar_adj_dir / "globalorder" / "data" / "demelo" / "gold_rankings"
        if demelo_dir.exists():
            for ranking_file in demelo_dir.glob("*.rankings"):
                scale_name = ranking_file.stem
                words = self._parse_ranking_file(ranking_file)
                if words:
                    self.scalar_scales[f"demelo_{scale_name}"] = words

        # Load Crowd gold rankings
        crowd_dir = scalar_adj_dir / "globalorder" / "data" / "crowd" / "gold_rankings"
        if crowd_dir.exists():
            for ranking_file in crowd_dir.glob("*.rankings"):
                scale_name = ranking_file.stem
                words = self._parse_ranking_file(ranking_file)
                if words:
                    self.scalar_scales[f"crowd_{scale_name}"] = words

        # Load Wilkinson terms
        wilkinson_dir = scalar_adj_dir / "globalorder" / "data" / "wilkinson" / "terms"
        if wilkinson_dir.exists():
            for terms_file in wilkinson_dir.glob("*.terms"):
                scale_name = terms_file.stem
                words = self._parse_ranking_file(terms_file)
                if words:
                    self.scalar_scales[f"wilkinson_{scale_name}"] = words

    def _parse_ranking_file(self, filepath: Path) -> List[str]:
        """
        Parse a ranking file. Format:
        0   word1
        1   word2 || word3
        2   word4

        Returns flat list ordered from lowest to highest intensity.
        """
        words = []
        try:
            with open(filepath) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        # Handle ties with ||
                        word_part = parts[1]
                        for word in word_part.split("||"):
                            word = word.strip().lower()
                            if word:
                                words.append(word)
        except Exception as e:
            print(f"Error parsing {filepath}: {e}")
        return words

    def get_level(self, word: str) -> Optional[int]:
        """Get the expected hierarchy level for a modifier word."""
        word = word.lower()
        entry = self.modifiers.get(word)
        return entry.level if entry else None

    def get_hierarchy_type(self, word: str) -> Optional[str]:
        """Get the hierarchy type (INTENSITY/QUANTITY/CERTAINTY) for a word."""
        word = word.lower()
        entry = self.modifiers.get(word)
        return entry.hierarchy_type if entry else None

    def get_entry(self, word: str) -> Optional[ModifierEntry]:
        """Get the full entry for a word."""
        return self.modifiers.get(word.lower())

    def get_expected_encoding(self, word: str) -> Optional[Dict[str, int]]:
        """
        Get the expected GSE primitive encoding for a modifier word.

        Returns dict like:
            {"INTENSITY": 1, "HIER_PLUS": 1}  for "very"
            {"QUANTITY": 1, "HIER_MINUS": 2}  for "few"
        """
        entry = self.get_entry(word)
        if not entry:
            return None

        encoding = {entry.hierarchy_type: 1}  # Base primitive always +1

        if entry.level > 0:
            encoding["HIER_PLUS"] = entry.level
        elif entry.level < 0:
            encoding["HIER_MINUS"] = abs(entry.level)
        # level == 0: no HIER markers needed

        return encoding

    def get_all_modifiers(self) -> List[str]:
        """Get all modifier words in the ground truth."""
        return list(self.modifiers.keys())

    def get_modifiers_by_type(self, hierarchy_type: str) -> List[ModifierEntry]:
        """Get all modifiers of a specific type."""
        return [e for e in self.modifiers.values() if e.hierarchy_type == hierarchy_type]

    def get_scale_ranking(self, word: str) -> Optional[Tuple[str, int, int]]:
        """
        Find which scale a word belongs to and its position.

        Returns (scale_name, position, total_scale_length) or None.
        """
        word = word.lower()
        for scale_name, words in self.scalar_scales.items():
            if word in words:
                pos = words.index(word)
                return (scale_name, pos, len(words))
        return None

    def compare_intensity(self, word1: str, word2: str) -> Optional[int]:
        """
        Compare intensity of two words on the same scale.

        Returns:
            -1 if word1 < word2
            0 if word1 == word2
            1 if word1 > word2
            None if not comparable
        """
        # First check if they're both modifiers with levels
        entry1 = self.get_entry(word1)
        entry2 = self.get_entry(word2)

        if entry1 and entry2 and entry1.hierarchy_type == entry2.hierarchy_type:
            if entry1.level < entry2.level:
                return -1
            elif entry1.level > entry2.level:
                return 1
            else:
                return 0

        # Check if they're on the same scalar adjective scale
        for scale_name, words in self.scalar_scales.items():
            w1_lower = word1.lower()
            w2_lower = word2.lower()
            if w1_lower in words and w2_lower in words:
                pos1 = words.index(w1_lower)
                pos2 = words.index(w2_lower)
                if pos1 < pos2:
                    return -1
                elif pos1 > pos2:
                    return 1
                else:
                    return 0

        return None

    def summary(self) -> Dict:
        """Get summary statistics."""
        type_counts = {}
        for entry in self.modifiers.values():
            type_counts[entry.hierarchy_type] = type_counts.get(entry.hierarchy_type, 0) + 1

        return {
            "total_modifiers": len(self.modifiers),
            "by_type": type_counts,
            "scalar_scales": len(self.scalar_scales),
            "total_scale_words": sum(len(w) for w in self.scalar_scales.values()),
        }


# Singleton instance
_ground_truth: Optional[IntensityGroundTruth] = None


def get_modifier_ground_truth() -> IntensityGroundTruth:
    """Get the singleton ground truth instance."""
    global _ground_truth
    if _ground_truth is None:
        _ground_truth = IntensityGroundTruth()
    return _ground_truth


if __name__ == "__main__":
    # Test the loader
    gt = get_modifier_ground_truth()

    print("=" * 60)
    print("INTENSITY GROUND TRUTH SUMMARY")
    print("=" * 60)

    summary = gt.summary()
    print(f"\nTotal modifiers: {summary['total_modifiers']}")
    print(f"By type: {summary['by_type']}")
    print(f"Scalar scales: {summary['scalar_scales']}")
    print(f"Total scale words: {summary['total_scale_words']}")

    print("\n" + "=" * 60)
    print("SAMPLE INTENSITY LOOKUPS")
    print("=" * 60)

    test_words = ["very", "extremely", "barely", "slightly", "many", "few", "likely", "impossible"]
    for word in test_words:
        entry = gt.get_entry(word)
        if entry:
            encoding = gt.get_expected_encoding(word)
            print(f"{word:15} -> {entry.hierarchy_type} level {entry.level:+d} -> {encoding}")
        else:
            print(f"{word:15} -> NOT FOUND")

    print("\n" + "=" * 60)
    print("SAMPLE SCALE RANKINGS")
    print("=" * 60)

    for scale_name in list(gt.scalar_scales.keys())[:5]:
        words = gt.scalar_scales[scale_name]
        print(f"\n{scale_name}:")
        print(f"  {' < '.join(words[:6])}" + (" ..." if len(words) > 6 else ""))

    print("\n" + "=" * 60)
    print("INTENSITY COMPARISONS")
    print("=" * 60)

    comparisons = [
        ("very", "extremely"),
        ("slightly", "barely"),
        ("few", "many"),
        ("possible", "certain"),
        ("small", "tiny"),
    ]

    for w1, w2 in comparisons:
        result = gt.compare_intensity(w1, w2)
        if result == -1:
            print(f"{w1} < {w2}")
        elif result == 1:
            print(f"{w1} > {w2}")
        elif result == 0:
            print(f"{w1} = {w2}")
        else:
            print(f"{w1} vs {w2}: not comparable")
