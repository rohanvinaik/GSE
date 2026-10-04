#!/usr/bin/env python3
"""
Scale-Specific Feature Extraction for Teaching

Extracts features at each scale from GSE traces for Hebbian learning:
- Text scale: Genre, register, domain signals
- Paragraph scale: RST-style discourse relations
- Sentence scale: Syntactic structure patterns
- Word scale: Primitive co-occurrence from decompositions
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# =============================================================================
# FEATURE DEFINITIONS
# =============================================================================

# Text-level indicators (cue words/phrases for each feature)
TEXT_INDICATORS = {
    # Genre
    "NARRATIVE": {"once", "then", "suddenly", "meanwhile", "finally", "began", "ended"},
    "EXPOSITORY": {"explains", "describes", "defines", "means", "consists", "includes"},
    "ARGUMENTATIVE": {"therefore", "however", "although", "because", "thus", "hence"},
    "DESCRIPTIVE": {"appears", "looks", "seems", "resembles", "features"},

    # Register
    "FORMAL": {"furthermore", "moreover", "nevertheless", "hereby", "thereof"},
    "INFORMAL": {"kinda", "gonna", "wanna", "yeah", "okay", "cool", "stuff"},
    "TECHNICAL": {"algorithm", "parameter", "implementation", "architecture", "protocol"},
    "COLLOQUIAL": {"like", "you know", "basically", "literally", "actually"},

    # Domain
    "ACADEMIC": {"hypothesis", "methodology", "analysis", "conclusion", "findings"},
    "LITERARY": {"metaphor", "narrative", "prose", "poetry", "genre"},
    "JOURNALISTIC": {"reported", "according", "sources", "confirmed", "alleged"},
    "CONVERSATIONAL": {"think", "feel", "want", "need", "guess"},
}

# Paragraph-level discourse cues
DISCOURSE_CUES = {
    # RST relations
    "ELABORATION": {"specifically", "in particular", "namely", "for example", "such as"},
    "BACKGROUND": {"previously", "historically", "before this", "until now"},
    "CIRCUMSTANCE": {"when", "while", "during", "as", "once"},
    "CAUSE": {"because", "since", "due to", "as a result of", "owing to"},
    "RESULT": {"therefore", "consequently", "thus", "hence", "so"},
    "PURPOSE": {"in order to", "so that", "to", "for"},
    "CONDITION": {"if", "unless", "provided that", "in case"},
    "CONCESSION": {"although", "despite", "however", "nevertheless", "yet"},
    "CONTRAST": {"but", "however", "on the other hand", "whereas", "while"},
    "COMPARISON": {"similarly", "likewise", "in the same way", "compared to"},
    "SEQUENCE": {"first", "second", "then", "next", "finally"},
    "CONJUNCTION": {"and", "also", "moreover", "furthermore", "in addition"},
    "DISJUNCTION": {"or", "either", "alternatively"},
    "RESTATEMENT": {"in other words", "that is", "namely", "i.e."},
    "SUMMARY": {"in summary", "in conclusion", "overall", "to summarize"},
}

# Sentence-level syntactic patterns
SYNTACTIC_PATTERNS = {
    "SYN_SUBJ": r"^(The|A|An|[A-Z][a-z]+)\s+\w+",  # Starts with determiner/proper noun
    "SYN_PRED": r"\s+(is|are|was|were|has|have|had|does|do|did|will|would|can|could)\s+",
    "SYN_OBJ": r"\s+(the|a|an)\s+\w+\s*[.!?]?$",  # Ends with noun phrase
    "SYN_COMPL": r"\s+(that|which|who|whom|whose|where|when)\s+",
    "SYN_ADJ_MOD": r"\s+(very|quite|rather|extremely|fairly)\s+\w+",
    "SYN_ADV_MOD": r"\s+(quickly|slowly|carefully|easily|recently)\s+",
    "SYN_DET": r"\b(the|a|an|this|that|these|those|my|your|his|her|its|our|their)\b",
    "SYN_TENSE_PAST": r"\b(was|were|had|did|\w+ed)\b",
    "SYN_ASPECT_PERF": r"\b(has|have|had)\s+(been|\w+ed|\w+en)\b",
    "SYN_MOOD_INTER": r"^(What|Why|How|When|Where|Who|Is|Are|Do|Does|Did|Can|Could|Would)\b",
}


# =============================================================================
# FEATURE EXTRACTOR
# =============================================================================

@dataclass
class FeatureExtractor:
    """
    Extract scale-appropriate features from GSE encodings and raw text.

    Each method returns a Dict[str, float] suitable for Hebbian learning.
    """

    # Minimum feature activation to include
    min_activation: float = 0.1

    def extract_text_features(self, text: str) -> Dict[str, float]:
        """
        Extract text-level features (genre, register, domain).

        Args:
            text: Full document text

        Returns:
            Dict of feature → activation level
        """
        features = {}
        words = set(text.lower().split())
        word_count = len(text.split())

        # Check each feature category
        for feature, indicators in TEXT_INDICATORS.items():
            # Count matching indicators
            matches = len(words & indicators)
            if matches > 0:
                # Normalize by document length (capped at 1.0)
                activation = min(1.0, matches / max(1, word_count / 100))
                if activation >= self.min_activation:
                    features[feature] = activation

        # Additional heuristics

        # Formality from punctuation and structure
        formal_punct = text.count(';') + text.count(':') + text.count('—')
        if formal_punct > 0:
            features["FORMAL"] = min(1.0, features.get("FORMAL", 0) + formal_punct / 10)

        # Technical from numbers/equations
        numbers = len(re.findall(r'\b\d+\.?\d*\b', text))
        if numbers > word_count / 20:
            features["TECHNICAL"] = min(1.0, features.get("TECHNICAL", 0) + 0.3)

        # Average sentence length affects register
        sentences = text.count('.') + text.count('!') + text.count('?')
        if sentences > 0:
            avg_sent_len = word_count / sentences
            if avg_sent_len > 25:
                features["FORMAL"] = min(1.0, features.get("FORMAL", 0) + 0.2)
            elif avg_sent_len < 10:
                features["INFORMAL"] = min(1.0, features.get("INFORMAL", 0) + 0.2)

        return features

    def extract_paragraph_features(
        self,
        paragraph: str,
        prev_paragraph: str = None,
    ) -> Dict[str, float]:
        """
        Extract paragraph-level discourse features.

        Args:
            paragraph: Current paragraph text
            prev_paragraph: Previous paragraph (for transition detection)

        Returns:
            Dict of discourse relation → activation level
        """
        features = {}
        text_lower = paragraph.lower()

        # Check discourse cues
        for relation, cues in DISCOURSE_CUES.items():
            for cue in cues:
                if cue in text_lower:
                    # Stronger activation if cue at beginning
                    if text_lower.strip().startswith(cue):
                        features[relation] = min(1.0, features.get(relation, 0) + 0.8)
                    else:
                        features[relation] = min(1.0, features.get(relation, 0) + 0.4)

        # Structural features

        # Lists suggest sequence
        if re.search(r'^\s*[\d•\-\*]\s+', paragraph, re.MULTILINE):
            features["SEQUENCE"] = min(1.0, features.get("SEQUENCE", 0) + 0.5)

        # Questions suggest elaboration needed
        if '?' in paragraph:
            features["ELABORATION"] = min(1.0, features.get("ELABORATION", 0) + 0.3)

        # Short paragraphs often serve specific functions
        word_count = len(paragraph.split())
        if word_count < 20:
            if any(cue in text_lower for cue in {"in conclusion", "therefore", "thus"}):
                features["SUMMARY"] = min(1.0, features.get("SUMMARY", 0) + 0.5)

        # Filter by minimum activation
        return {k: v for k, v in features.items() if v >= self.min_activation}

    def extract_sentence_features(
        self,
        sentence: str,
        trace: Any = None,
    ) -> Dict[str, float]:
        """
        Extract sentence-level syntactic features.

        Args:
            sentence: Sentence text
            trace: Optional GSE OperationTrace for enhanced extraction

        Returns:
            Dict of syntactic feature → activation level
        """
        features = {}

        # Pattern-based extraction
        for feature, pattern in SYNTACTIC_PATTERNS.items():
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                # Calculate activation based on match strength
                match_len = len(match.group())
                sent_len = len(sentence)
                activation = min(1.0, match_len / max(10, sent_len / 3))
                features[feature] = max(activation, features.get(feature, 0))

        # Structural heuristics

        # Subject detection from first noun phrase
        first_word = sentence.split()[0] if sentence.split() else ""
        if first_word[0].isupper() and first_word.lower() not in {"the", "a", "an"}:
            features["SYN_SUBJ"] = max(0.7, features.get("SYN_SUBJ", 0))

        # Question detection
        if sentence.strip().endswith('?'):
            features["SYN_MOOD_INTER"] = 1.0

        # Tense from verb forms
        past_markers = len(re.findall(r'\b\w+ed\b|\bwas\b|\bwere\b|\bhad\b', sentence))
        if past_markers > 0:
            features["SYN_TENSE_PAST"] = min(1.0, past_markers * 0.3)

        # If trace provided, use it for enhanced extraction
        if trace is not None:
            features.update(self._extract_from_trace(trace))

        # Filter by minimum activation
        return {k: v for k, v in features.items() if v >= self.min_activation}

    def _extract_from_trace(self, trace: Any) -> Dict[str, float]:
        """Extract features from GSE OperationTrace."""
        features = {}

        # Extract from token traces if available
        if hasattr(trace, 'tokens'):
            for i, token_trace in enumerate(trace.tokens):
                if hasattr(token_trace, 'role'):
                    role = token_trace.role.upper()
                    if role in {"SUBJECT", "SUBJ"}:
                        features["SYN_SUBJ"] = 1.0
                    elif role in {"PREDICATE", "PRED", "VERB"}:
                        features["SYN_PRED"] = 1.0
                    elif role in {"OBJECT", "OBJ"}:
                        features["SYN_OBJ"] = 1.0

        return features

    def extract_word_features(
        self,
        word: str,
        primitives: Dict[str, int] = None,
        trace: Any = None,
    ) -> Dict[str, float]:
        """
        Extract word-level primitive co-occurrence features.

        Args:
            word: The word being processed
            primitives: Dict of primitive → polarity from lexicon
            trace: Optional TokenTrace for this word

        Returns:
            Dict of primitive → activation level (polarity-weighted)
        """
        features = {}

        if primitives:
            # Direct primitive extraction
            for prim, polarity in primitives.items():
                # Map lexicon primitives to network primitives
                network_prim = self._map_to_network_primitive(prim)
                if network_prim:
                    features[network_prim] = float(polarity)

        elif trace is not None and hasattr(trace, 'word_primitives'):
            # Extract from trace
            for prim, polarity in trace.word_primitives.items():
                network_prim = self._map_to_network_primitive(prim)
                if network_prim:
                    features[network_prim] = float(polarity)

        return features

    def _map_to_network_primitive(self, prim: str) -> Optional[str]:
        """Map lexicon primitive name to network primitive."""
        # The word network uses specific hub primitives
        WORD_NETWORK_PRIMS = {
            "SOMEONE", "SOMETHING", "PART",
            "ONE", "QUANTITY",
            "GOOD", "BIG",
            "THINK", "FEEL", "KNOW", "WANT", "INFER",
            "DO", "BE", "MOVE", "SAY", "ALIVE",
            "BEFORE", "MOMENT", "START",
            "WHERE", "ABOVE", "TOWARD", "WITH",
            "NOT", "BECAUSE", "CAUSE", "MUST", "CERTAINTY",
            "HIER_PLUS", "HIER_MINUS", "INTENSITY",
        }

        # Direct match
        if prim in WORD_NETWORK_PRIMS:
            return prim

        # Handle variations
        prim_upper = prim.upper()
        if prim_upper in WORD_NETWORK_PRIMS:
            return prim_upper

        # Map BAD → GOOD with negative, SMALL → BIG with negative, etc.
        bipolar_map = {
            "BAD": ("GOOD", -1),
            "SMALL": ("BIG", -1),
            "DEAD": ("ALIVE", -1),
            "END": ("START", -1),
            "AWAY": ("TOWARD", -1),
            "WITHOUT": ("WITH", -1),
            "AFTER": ("BEFORE", -1),
        }

        if prim_upper in bipolar_map:
            return bipolar_map[prim_upper][0]

        return None

    def extract_all_features(
        self,
        text: str,
        sentences: List[str] = None,
        paragraphs: List[str] = None,
        word_primitives: Dict[str, Dict[str, int]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """
        Extract features at all scales from a document.

        Args:
            text: Full document text
            sentences: Pre-split sentences (optional)
            paragraphs: Pre-split paragraphs (optional)
            word_primitives: Word → primitive mappings (optional)

        Returns:
            Dict with 'text', 'paragraph', 'sentence', 'word' keys
        """
        # Split text if not provided
        if paragraphs is None:
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        if sentences is None:
            sentences = []
            for para in paragraphs:
                sentences.extend(self._split_sentences(para))

        # Extract at each scale
        result = {
            "text": self.extract_text_features(text),
            "paragraph": [],
            "sentence": [],
            "word": {},
        }

        # Paragraph features
        prev_para = None
        for para in paragraphs:
            para_features = self.extract_paragraph_features(para, prev_para)
            result["paragraph"].append(para_features)
            prev_para = para

        # Sentence features
        for sent in sentences:
            sent_features = self.extract_sentence_features(sent)
            result["sentence"].append(sent_features)

        # Word features
        if word_primitives:
            for word, prims in word_primitives.items():
                word_features = self.extract_word_features(word, prims)
                if word_features:
                    result["word"][word] = word_features

        return result

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    print("Feature Extractor Self-Test")
    print("=" * 50)

    extractor = FeatureExtractor()

    # Test 1: Text features
    print("\n1. Text Feature Extraction:")
    text = """
    The methodology employed in this study represents a novel approach
    to understanding cognitive phenomena. Therefore, we hypothesize that
    the algorithm's implementation will yield significant findings.
    Furthermore, the analysis demonstrates clear patterns.
    """
    features = extractor.extract_text_features(text)
    print(f"   Features: {list(features.keys())}")
    for k, v in sorted(features.items(), key=lambda x: -x[1])[:3]:
        print(f"     {k}: {v:.3f}")

    # Test 2: Paragraph features
    print("\n2. Paragraph Feature Extraction:")
    para = "Therefore, we can conclude that the results support our hypothesis."
    para_features = extractor.extract_paragraph_features(para)
    print(f"   Discourse relations: {list(para_features.keys())}")

    # Test 3: Sentence features
    print("\n3. Sentence Feature Extraction:")
    sent = "The researcher carefully analyzed the complex data."
    sent_features = extractor.extract_sentence_features(sent)
    print(f"   Syntactic features: {list(sent_features.keys())}")

    # Test 4: Word features
    print("\n4. Word Feature Extraction:")
    prims = {"FEEL": 1, "GOOD": 1, "INTENSITY": 1}
    word_features = extractor.extract_word_features("happy", prims)
    print(f"   Primitives: {word_features}")

    # Test 5: Full extraction
    print("\n5. Full Document Extraction:")
    all_features = extractor.extract_all_features(text)
    print(f"   Text features: {len(all_features['text'])}")
    print(f"   Paragraph features: {len(all_features['paragraph'])}")
    print(f"   Sentence features: {len(all_features['sentence'])}")

    print("\n" + "=" * 50)
    print("All Feature Extractor tests passed!")
