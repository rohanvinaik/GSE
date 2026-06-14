#!/usr/bin/env python3
"""
GSE Lexicon Builder from NLTK Resources

This script builds a comprehensive GSE lexicon by integrating:
1. FrameNet - semantic frames and roles (primary source)
2. WordNet - synsets, definitions, synonyms, antonyms
3. Word frequency data

The key insight: FrameNet's frame elements map to GSE's semantic roles,
and we can derive NSM primitive decompositions from frame semantics.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# NLTK imports - will be downloaded if needed
try:
    import nltk
    from nltk.corpus import framenet as fn
    from nltk.corpus import wordnet as wn
except ImportError:
    print("Installing NLTK...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "nltk"])
    import nltk
    from nltk.corpus import framenet as fn
    from nltk.corpus import wordnet as wn


def ensure_nltk_data():
    """Download required NLTK data if not present."""
    required = [
        ('corpora/framenet_v17', 'framenet_v17'),
        ('corpora/wordnet', 'wordnet'),
        ('corpora/omw-1.4', 'omw-1.4'),  # Open Multilingual WordNet
    ]

    for path, name in required:
        try:
            nltk.data.find(path)
            print(f"  ✓ {name} already downloaded")
        except LookupError:
            print(f"  Downloading {name}...")
            nltk.download(name, quiet=True)

    print("NLTK data ready.\n")


# =============================================================================
# NSM PRIMITIVE MAPPINGS
# =============================================================================

# Map FrameNet frames to likely NSM primitives
# This is the key semantic bridge
FRAME_TO_PRIMITIVES: Dict[str, List[Tuple[str, str]]] = {
    # Mental/Cognitive frames
    "Awareness": [("KNOW", "state")],
    "Certainty": [("KNOW", "state"), ("VERY", "manner")],
    "Cogitation": [("THINK", "action")],
    "Coming_to_believe": [("KNOW", "result"), ("BEFORE", "time"), ("NOT", "evaluation")],
    "Contemplation": [("THINK", "action"), ("LONG_TIME", "manner")],
    "Desiring": [("WANT", "state")],
    "Emotion_directed": [("FEEL", "state")],
    "Emotions_by_possibility": [("FEEL", "state"), ("MAYBE", "manner")],
    "Experiencer_focus": [("FEEL", "state")],
    "Experiencer_obj": [("FEEL", "state")],
    "Feeling": [("FEEL", "state")],
    "Mental_property": [("THINK", "attribute")],
    "Opinion": [("THINK", "state")],
    "Perception_active": [("SEE", "action")],
    "Perception_experience": [("SEE", "state")],

    # Communication frames
    "Communication": [("SAY", "action"), ("WORDS", "instrument")],
    "Commitment": [("SAY", "action"), ("WANT", "content")],
    "Request": [("SAY", "action"), ("WANT", "content")],
    "Statement": [("SAY", "action"), ("TRUE", "evaluation")],
    "Telling": [("SAY", "action"), ("SOMEONE", "recipient")],
    "Text_creation": [("SAY", "action"), ("WORDS", "result")],

    # Action/Causation frames
    "Cause_change": [("DO", "action"), ("SOMETHING", "patient")],
    "Cause_harm": [("DO", "action"), ("BAD", "evaluation"), ("SOMEONE", "patient")],
    "Cause_motion": [("DO", "action"), ("MOVE", "result")],
    "Causation": [("BECAUSE", "relation"), ("HAPPEN", "result")],
    "Event": [("HAPPEN", "action")],
    "Intentionally_act": [("DO", "action"), ("WANT", "manner")],
    "Transitive_action": [("DO", "action"), ("SOMETHING", "patient")],

    # Motion frames
    "Arriving": [("MOVE", "action"), ("HERE", "goal")],
    "Departing": [("MOVE", "action"), ("HERE", "source")],
    "Motion": [("MOVE", "action")],
    "Self_motion": [("MOVE", "action"), ("SOMEONE", "agent")],
    "Travel": [("MOVE", "action"), ("FAR", "manner")],

    # Existence/State frames
    "Being_located": [("BE", "state"), ("WHERE", "attribute")],
    "Existence": [("EXIST", "state")],
    "State": [("BE", "state")],
    "State_continue": [("BE", "state"), ("LONG_TIME", "manner")],

    # Life frames
    "Being_born": [("LIVE", "result"), ("BEFORE", "time"), ("NOT", "evaluation")],
    "Death": [("DIE", "action")],
    "Killing": [("DO", "action"), ("DIE", "result"), ("SOMEONE", "patient")],

    # Evaluation frames
    "Desirability": [("GOOD", "evaluation")],
    "Judgment": [("THINK", "action"), ("GOOD", "evaluation")],
    "Judgment_communication": [("SAY", "action"), ("GOOD", "evaluation")],

    # Quantity/Size frames
    "Abundance": [("MUCH", "attribute")],
    "Dimension": [("BIG", "attribute")],
    "Position_on_a_scale": [("MORE", "attribute")],
    "Quantity": [("MUCH", "attribute")],
    "Size": [("BIG", "attribute")],

    # Temporal frames
    "Duration_description": [("LONG_TIME", "attribute")],
    "Frequency": [("WHEN", "attribute")],
    "Relative_time": [("BEFORE", "relation")],
    "Time_vector": [("WHEN", "attribute")],

    # Spatial frames
    "Direction": [("WHERE", "attribute")],
    "Goal": [("WHERE", "goal")],
    "Locative_relation": [("WHERE", "relation")],
    "Source": [("WHERE", "source")],
    "Spatial_contact": [("TOUCH", "relation")],

    # Social frames
    "Commerce_buy": [("DO", "action"), ("HAVE", "result"), ("SOMETHING", "patient")],
    "Commerce_sell": [("DO", "action"), ("HAVE", "result"), ("SOMEONE", "recipient")],
    "Giving": [("DO", "action"), ("HAVE", "result"), ("SOMEONE", "recipient")],
    "Getting": [("DO", "action"), ("HAVE", "result")],
    "Possession": [("HAVE", "state")],

    # Relational frames
    "Kinship": [("SOMEONE", "relation"), ("KIND", "attribute")],
    "Personal_relationship": [("SOMEONE", "relation")],
    "Social_connection": [("SOMEONE", "relation")],
}

# Map FrameNet frame elements to GSE roles
FE_TO_ROLE: Dict[str, str] = {
    # Core participants
    "Agent": "agent",
    "Actor": "agent",
    "Experiencer": "experiencer",
    "Cognizer": "experiencer",
    "Speaker": "agent",
    "Communicator": "agent",
    "Patient": "patient",
    "Theme": "theme",
    "Undergoer": "patient",
    "Entity": "theme",
    "Content": "content",
    "Message": "content",
    "Topic": "content",
    "Phenomenon": "theme",
    "Stimulus": "cause",

    # Recipients and beneficiaries
    "Recipient": "recipient",
    "Addressee": "recipient",
    "Beneficiary": "beneficiary",
    "Goal": "goal",
    "Destination": "goal",

    # Sources and instruments
    "Source": "source",
    "Origin": "source",
    "Instrument": "instrument",
    "Means": "instrument",
    "Cause": "cause",

    # Modifiers
    "Manner": "manner",
    "Degree": "manner",
    "Time": "time",
    "Duration": "time",
    "Place": "location",
    "Location": "location",
    "Purpose": "intention",
    "Reason": "cause",
    "Result": "result",
    "Effect": "result",

    # Evaluative
    "Evaluee": "patient",
    "Evaluation": "evaluation",
    "State": "state",
    "Attribute": "attribute",
    "Value": "attribute",
}

# Map WordNet POS to GSE POS
WN_POS_MAP = {
    'n': 'NOUN',
    'v': 'VERB',
    'a': 'ADJ',
    's': 'ADJ',  # satellite adjective
    'r': 'ADV',
}

# Core vocabulary to prioritize (high frequency words)
CORE_VOCABULARY = {
    # Verbs
    "be", "have", "do", "say", "go", "get", "make", "know", "think", "take",
    "see", "come", "want", "look", "use", "find", "give", "tell", "work", "call",
    "try", "ask", "need", "feel", "become", "leave", "put", "mean", "keep", "let",
    "begin", "seem", "help", "show", "hear", "play", "run", "move", "live", "believe",
    "hold", "bring", "happen", "write", "sit", "stand", "lose", "pay", "meet", "include",
    "continue", "set", "learn", "change", "lead", "understand", "watch", "follow", "stop",
    "create", "speak", "read", "allow", "add", "spend", "grow", "open", "walk", "win",
    "offer", "remember", "love", "consider", "appear", "buy", "wait", "serve", "die",
    "send", "expect", "build", "stay", "fall", "cut", "reach", "kill", "remain",

    # Nouns
    "time", "year", "people", "way", "day", "man", "thing", "woman", "life", "child",
    "world", "school", "state", "family", "student", "group", "country", "problem",
    "hand", "part", "place", "case", "week", "company", "system", "program", "question",
    "work", "government", "number", "night", "point", "home", "water", "room", "mother",
    "area", "money", "story", "fact", "month", "lot", "right", "study", "book", "eye",
    "job", "word", "business", "issue", "side", "kind", "head", "house", "service",
    "friend", "father", "power", "hour", "game", "line", "end", "member", "law", "car",
    "city", "community", "name", "president", "team", "minute", "idea", "body", "information",

    # Adjectives
    "good", "new", "first", "last", "long", "great", "little", "own", "other", "old",
    "right", "big", "high", "different", "small", "large", "next", "early", "young",
    "important", "few", "public", "bad", "same", "able", "human", "local", "sure",
    "free", "better", "true", "whole", "real", "best", "special", "easy", "clear",
    "recent", "strong", "possible", "full", "happy", "serious", "ready", "simple",
    "left", "physical", "general", "environmental", "financial", "hard", "likely",

    # Adverbs
    "up", "out", "just", "now", "how", "then", "more", "also", "here", "well",
    "only", "very", "even", "back", "there", "still", "too", "where", "much",
    "down", "off", "really", "already", "never", "why", "always", "away", "again",
    "often", "however", "almost", "later", "once", "ever", "probably", "rather",
    "certainly", "perhaps", "finally", "today", "far", "usually", "quickly", "early",
}


# =============================================================================
# LEXICON BUILDER
# =============================================================================

class GSELexiconBuilder:
    """Build GSE lexicon from NLTK resources."""

    def __init__(self, output_dir: str = "data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Track what we've processed
        self.processed_words: Set[str] = set()
        self.decompositions: List[Dict] = []
        self.stats = defaultdict(int)

        # Load existing decompositions to avoid duplicates
        self.existing_words = self._load_existing()

    def _load_existing(self) -> Set[str]:
        """Load existing word decompositions."""
        existing = set()
        json_path = self.output_dir / "word_decompositions.json"
        if json_path.exists():
            with open(json_path) as f:
                data = json.load(f)
                for entry in data.get("words", []):
                    key = f"{entry['word'].lower()}_{entry['pos']}"
                    existing.add(key)
        return existing

    def process_framenet(self, max_frames: int = None):
        """Extract lexical units and decompositions from FrameNet."""
        print("Processing FrameNet...")

        frames = list(fn.frames())
        if max_frames:
            frames = frames[:max_frames]

        for frame in frames:
            frame_name = frame.name
            self.stats['frames_processed'] += 1

            # Get base decomposition for this frame
            base_decomposition = FRAME_TO_PRIMITIVES.get(frame_name, [])

            # Process each lexical unit in the frame
            for lu in frame.lexUnit.values():
                self._process_lexical_unit(lu, frame, base_decomposition)

        print(f"  Processed {self.stats['frames_processed']} frames")
        print(f"  Extracted {self.stats['framenet_words']} words")

    def _process_lexical_unit(self, lu, frame, base_decomposition: List[Tuple[str, str]]):
        """Process a single FrameNet lexical unit."""
        # Parse LU name (format: "word.pos")
        name_parts = lu.name.rsplit('.', 1)
        if len(name_parts) != 2:
            return

        word, pos_code = name_parts
        word = word.lower().replace('_', ' ')

        # Skip multi-word expressions for now
        if ' ' in word:
            return

        # Map POS
        pos_map = {'v': 'VERB', 'n': 'NOUN', 'a': 'ADJ', 'adv': 'ADV', 'prep': 'ADP'}
        pos = pos_map.get(pos_code, 'OTHER')
        if pos == 'OTHER':
            return

        # Skip if already processed
        key = f"{word}_{pos}"
        if key in self.processed_words or key in self.existing_words:
            return

        # Build decomposition
        decomposition = list(base_decomposition) if base_decomposition else []

        # Add frame-element based roles if we have examples
        if hasattr(lu, 'exemplars'):
            fe_roles = self._extract_fe_roles(lu)
            for prim, role in fe_roles:
                if (prim, role) not in decomposition:
                    decomposition.append((prim, role))

        # If no decomposition from frame, try to infer from WordNet
        if not decomposition:
            decomposition = self._infer_from_wordnet(word, pos)

        if not decomposition:
            # Minimal fallback
            if pos == 'VERB':
                decomposition = [("DO", "action")]
            elif pos == 'NOUN':
                decomposition = [("SOMETHING", "theme")]
            elif pos == 'ADJ':
                decomposition = [("BE", "state")]
            elif pos == 'ADV':
                decomposition = [("VERY", "manner")]

        # Get definition from WordNet if available
        definition = self._get_wordnet_definition(word, pos)
        if not definition and hasattr(lu, 'definition'):
            definition = lu.definition

        # Calculate frequency score (prioritize core vocab)
        frequency = 0.9 if word in CORE_VOCABULARY else 0.5

        entry = {
            "word": word,
            "pos": pos,
            "definition": definition or f"({frame.name} frame)",
            "decomposition": decomposition,
            "frequency": frequency,
            "source": f"framenet:{frame.name}"
        }

        self.decompositions.append(entry)
        self.processed_words.add(key)
        self.stats['framenet_words'] += 1

    def _extract_fe_roles(self, lu) -> List[Tuple[str, str]]:
        """Extract semantic roles from frame element annotations."""
        roles = []

        # Get the frame's core FEs
        if hasattr(lu, 'frame') and hasattr(lu.frame, 'FE'):
            for fe_name, fe in lu.frame.FE.items():
                if fe.coreType == 'Core':
                    role = FE_TO_ROLE.get(fe_name)
                    if role:
                        # Map FE to likely primitive
                        prim = self._fe_to_primitive(fe_name, lu.frame.name)
                        if prim:
                            roles.append((prim, role))

        return roles

    def _fe_to_primitive(self, fe_name: str, frame_name: str) -> Optional[str]:
        """Map frame element to NSM primitive."""
        fe_primitives = {
            "Agent": "SOMEONE",
            "Experiencer": "SOMEONE",
            "Cognizer": "SOMEONE",
            "Speaker": "SOMEONE",
            "Patient": "SOMETHING",
            "Theme": "SOMETHING",
            "Content": "SOMETHING",
            "Goal": "WHERE",
            "Source": "WHERE",
            "Time": "WHEN",
            "Manner": "VERY",
            "Cause": "BECAUSE",
            "Result": "HAPPEN",
            "Purpose": "WANT",
        }
        return fe_primitives.get(fe_name)

    def process_wordnet(self, max_synsets: int = None):
        """Extract words from WordNet with antonym/synonym relationships."""
        print("Processing WordNet...")

        count = 0
        for synset in wn.all_synsets():
            if max_synsets and count >= max_synsets:
                break

            pos = WN_POS_MAP.get(synset.pos())
            if not pos:
                continue

            for lemma in synset.lemmas():
                word = lemma.name().lower().replace('_', ' ')

                # Skip multi-word and already processed
                if ' ' in word:
                    continue

                key = f"{word}_{pos}"
                if key in self.processed_words or key in self.existing_words:
                    continue

                # Build decomposition
                decomposition = self._infer_from_wordnet(word, pos, synset)

                if not decomposition:
                    continue

                # Get definition
                definition = synset.definition()

                # Check for antonyms
                antonyms = [ant.name() for ant in lemma.antonyms()] if lemma.antonyms() else []

                # Frequency based on core vocab membership
                frequency = 0.85 if word in CORE_VOCABULARY else 0.4

                entry = {
                    "word": word,
                    "pos": pos,
                    "definition": definition,
                    "decomposition": decomposition,
                    "frequency": frequency,
                    "source": f"wordnet:{synset.name()}",
                }

                if antonyms:
                    entry["antonyms"] = antonyms

                self.decompositions.append(entry)
                self.processed_words.add(key)
                self.stats['wordnet_words'] += 1
                count += 1

        print(f"  Extracted {self.stats['wordnet_words']} words from WordNet")

    def _infer_from_wordnet(self, word: str, pos: str, synset=None) -> List[Tuple[str, str]]:
        """Infer NSM decomposition from WordNet relations."""
        decomposition = []

        if synset is None:
            synsets = wn.synsets(word, pos=self._pos_to_wn(pos))
            if not synsets:
                return []
            synset = synsets[0]

        # Use hypernym path to infer primitives
        hypernyms = synset.hypernym_paths()
        if hypernyms:
            top_hypernyms = [h.name().split('.')[0] for h in hypernyms[0][-3:] if h]

            # Map common hypernyms to primitives
            hypernym_map = {
                'entity': [("SOMETHING", "theme")],
                'physical_entity': [("SOMETHING", "theme"), ("BODY", "attribute")],
                'abstraction': [("SOMETHING", "theme"), ("THINK", "content")],
                'person': [("SOMEONE", "theme")],
                'organism': [("LIVE", "state")],
                'psychological_feature': [("FEEL", "state")],
                'cognition': [("THINK", "content")],
                'communication': [("SAY", "action"), ("WORDS", "theme")],
                'act': [("DO", "action")],
                'event': [("HAPPEN", "action")],
                'state': [("BE", "state")],
                'attribute': [("BE", "attribute")],
                'group': [("PEOPLE", "theme"), ("SOME", "quantity")],
                'measure': [("MUCH", "attribute")],
                'time': [("WHEN", "attribute")],
                'location': [("WHERE", "attribute")],
                'feeling': [("FEEL", "state")],
                'emotion': [("FEEL", "state")],
                'desire': [("WANT", "state")],
                'knowledge': [("KNOW", "state")],
                'motion': [("MOVE", "action")],
                'change': [("HAPPEN", "action")],
            }

            for h in top_hypernyms:
                if h in hypernym_map:
                    decomposition.extend(hypernym_map[h])
                    break

        # Check for sentiment/evaluation
        lemmas = synset.lemmas()
        if lemmas:
            for lemma in lemmas:
                if lemma.antonyms():
                    # Has antonyms - likely evaluative
                    ant_name = lemma.antonyms()[0].name().lower()
                    if ant_name in ['bad', 'evil', 'wrong', 'negative']:
                        decomposition.append(("GOOD", "evaluation"))
                    elif ant_name in ['good', 'positive', 'right']:
                        decomposition.append(("BAD", "evaluation"))

        # Ensure uniqueness
        seen = set()
        unique_decomp = []
        for item in decomposition:
            if item not in seen:
                seen.add(item)
                unique_decomp.append(item)

        return unique_decomp if unique_decomp else None

    def _pos_to_wn(self, pos: str) -> Optional[str]:
        """Convert GSE POS to WordNet POS."""
        return {'NOUN': 'n', 'VERB': 'v', 'ADJ': 'a', 'ADV': 'r'}.get(pos)

    def _get_wordnet_definition(self, word: str, pos: str) -> Optional[str]:
        """Get definition from WordNet."""
        wn_pos = self._pos_to_wn(pos)
        if not wn_pos:
            return None

        synsets = wn.synsets(word, pos=wn_pos)
        if synsets:
            return synsets[0].definition()
        return None

    def add_core_vocabulary(self):
        """Ensure core vocabulary words are included with good decompositions."""
        print("Adding core vocabulary...")

        # Manual high-quality decompositions for common words
        core_decompositions = {
            # Common verbs
            ("be", "VERB"): [("BE", "state")],
            ("have", "VERB"): [("HAVE", "state")],
            ("do", "VERB"): [("DO", "action")],
            ("say", "VERB"): [("SAY", "action"), ("WORDS", "content")],
            ("go", "VERB"): [("MOVE", "action")],
            ("get", "VERB"): [("HAVE", "result"), ("DO", "action")],
            ("make", "VERB"): [("DO", "action"), ("SOMETHING", "result")],
            ("know", "VERB"): [("KNOW", "state")],
            ("think", "VERB"): [("THINK", "action")],
            ("take", "VERB"): [("DO", "action"), ("HAVE", "result")],
            ("see", "VERB"): [("SEE", "action")],
            ("come", "VERB"): [("MOVE", "action"), ("HERE", "goal")],
            ("want", "VERB"): [("WANT", "state")],
            ("look", "VERB"): [("SEE", "action"), ("WANT", "manner")],
            ("use", "VERB"): [("DO", "action"), ("SOMETHING", "instrument")],
            ("find", "VERB"): [("KNOW", "result"), ("SEE", "action")],
            ("give", "VERB"): [("DO", "action"), ("HAVE", "result"), ("SOMEONE", "recipient")],
            ("tell", "VERB"): [("SAY", "action"), ("SOMEONE", "recipient")],
            ("feel", "VERB"): [("FEEL", "state")],
            ("become", "VERB"): [("BE", "result"), ("BEFORE", "time"), ("NOT", "evaluation")],
            ("leave", "VERB"): [("MOVE", "action"), ("HERE", "source")],
            ("begin", "VERB"): [("DO", "action"), ("BEFORE", "time"), ("NOT", "evaluation")],
            ("help", "VERB"): [("DO", "action"), ("GOOD", "evaluation"), ("SOMEONE", "beneficiary")],
            ("live", "VERB"): [("LIVE", "state")],
            ("die", "VERB"): [("DIE", "action")],
            ("love", "VERB"): [("FEEL", "state"), ("GOOD", "evaluation"), ("VERY", "manner")],
            ("hate", "VERB"): [("FEEL", "state"), ("BAD", "evaluation"), ("VERY", "manner")],
            ("believe", "VERB"): [("THINK", "state"), ("TRUE", "evaluation")],
            ("kill", "VERB"): [("DO", "action"), ("DIE", "result"), ("SOMEONE", "patient")],
            ("happen", "VERB"): [("HAPPEN", "action")],
            ("move", "VERB"): [("MOVE", "action")],
            ("hear", "VERB"): [("HEAR", "action")],
            ("run", "VERB"): [("MOVE", "action"), ("VERY", "manner")],
            ("walk", "VERB"): [("MOVE", "action")],
            ("eat", "VERB"): [("DO", "action"), ("BODY", "instrument"), ("SOMETHING", "patient")],
            ("sleep", "VERB"): [("LIVE", "action"), ("NOT", "evaluation"), ("DO", "state")],

            # Common nouns
            ("person", "NOUN"): [("SOMEONE", "theme")],
            ("people", "NOUN"): [("PEOPLE", "theme")],
            ("man", "NOUN"): [("SOMEONE", "theme"), ("KIND", "attribute")],
            ("woman", "NOUN"): [("SOMEONE", "theme"), ("KIND", "attribute")],
            ("child", "NOUN"): [("SOMEONE", "theme"), ("SMALL", "attribute"), ("YOUNG", "attribute")],
            ("thing", "NOUN"): [("SOMETHING", "theme")],
            ("time", "NOUN"): [("WHEN", "theme")],
            ("place", "NOUN"): [("WHERE", "theme")],
            ("way", "NOUN"): [("DO", "theme"), ("KIND", "attribute")],
            ("day", "NOUN"): [("WHEN", "theme"), ("LONG_TIME", "attribute")],
            ("world", "NOUN"): [("WHERE", "theme"), ("ALL", "quantity")],
            ("life", "NOUN"): [("LIVE", "theme")],
            ("hand", "NOUN"): [("BODY", "theme"), ("PART", "attribute")],
            ("part", "NOUN"): [("PART", "theme")],
            ("word", "NOUN"): [("WORDS", "theme")],
            ("fact", "NOUN"): [("TRUE", "theme"), ("SOMETHING", "attribute")],
            ("body", "NOUN"): [("BODY", "theme")],
            ("idea", "NOUN"): [("THINK", "theme"), ("SOMETHING", "attribute")],

            # Common adjectives
            ("good", "ADJ"): [("GOOD", "evaluation")],
            ("bad", "ADJ"): [("BAD", "evaluation")],
            ("big", "ADJ"): [("BIG", "attribute")],
            ("small", "ADJ"): [("SMALL", "attribute")],
            ("new", "ADJ"): [("NOW", "attribute"), ("BEFORE", "time"), ("NOT", "evaluation")],
            ("old", "ADJ"): [("LONG_TIME", "attribute"), ("BEFORE", "time")],
            ("long", "ADJ"): [("BIG", "attribute"), ("LONG_TIME", "manner")],
            ("great", "ADJ"): [("GOOD", "evaluation"), ("VERY", "manner")],
            ("little", "ADJ"): [("SMALL", "attribute")],
            ("high", "ADJ"): [("ABOVE", "attribute"), ("BIG", "manner")],
            ("different", "ADJ"): [("SAME", "attribute"), ("NOT", "evaluation")],
            ("large", "ADJ"): [("BIG", "attribute"), ("VERY", "manner")],
            ("young", "ADJ"): [("LIVE", "attribute"), ("SHORT_TIME", "manner")],
            ("important", "ADJ"): [("GOOD", "evaluation"), ("MUCH", "manner")],
            ("true", "ADJ"): [("TRUE", "evaluation")],
            ("real", "ADJ"): [("EXIST", "evaluation"), ("TRUE", "manner")],
            ("happy", "ADJ"): [("FEEL", "state"), ("GOOD", "evaluation")],
            ("sad", "ADJ"): [("FEEL", "state"), ("BAD", "evaluation")],
            ("sure", "ADJ"): [("KNOW", "state"), ("VERY", "manner")],
            ("possible", "ADJ"): [("CAN", "evaluation"), ("MAYBE", "manner")],
            ("same", "ADJ"): [("SAME", "attribute")],
            ("other", "ADJ"): [("SAME", "attribute"), ("NOT", "evaluation")],
            ("dead", "ADJ"): [("LIVE", "state"), ("NOT", "evaluation")],
            ("alive", "ADJ"): [("LIVE", "state")],
            ("near", "ADJ"): [("NEAR", "attribute")],
            ("far", "ADJ"): [("FAR", "attribute")],

            # Common adverbs
            ("very", "ADV"): [("VERY", "manner")],
            ("now", "ADV"): [("NOW", "time")],
            ("here", "ADV"): [("HERE", "location")],
            ("there", "ADV"): [("WHERE", "location")],
            ("well", "ADV"): [("GOOD", "manner")],
            ("also", "ADV"): [("SAME", "manner"), ("MORE", "quantity")],
            ("just", "ADV"): [("SAME", "manner"), ("NOW", "time")],
            ("only", "ADV"): [("ONE", "quantity"), ("NOT", "evaluation"), ("MORE", "quantity")],
            ("always", "ADV"): [("ALL", "time")],
            ("never", "ADV"): [("NOT", "evaluation"), ("ALL", "time")],
            ("often", "ADV"): [("MUCH", "time")],
            ("still", "ADV"): [("NOW", "time"), ("BEFORE", "relation")],
            ("already", "ADV"): [("BEFORE", "time"), ("NOW", "result")],
            ("again", "ADV"): [("BEFORE", "time"), ("SAME", "manner")],
            ("maybe", "ADV"): [("MAYBE", "evaluation")],
            ("quickly", "ADV"): [("SHORT_TIME", "manner")],
            ("slowly", "ADV"): [("LONG_TIME", "manner")],
        }

        added = 0
        for (word, pos), decomp in core_decompositions.items():
            key = f"{word}_{pos}"
            if key not in self.processed_words and key not in self.existing_words:
                # Get definition
                definition = self._get_wordnet_definition(word, pos) or ""

                entry = {
                    "word": word,
                    "pos": pos,
                    "definition": definition,
                    "decomposition": decomp,
                    "frequency": 0.95,
                    "source": "core_vocabulary"
                }

                self.decompositions.append(entry)
                self.processed_words.add(key)
                added += 1

        print(f"  Added {added} core vocabulary entries")

    def save(self):
        """Save decompositions to JSON and rebuild the lexicon database."""
        # Sort by frequency (highest first)
        self.decompositions.sort(key=lambda x: -x.get('frequency', 0))

        # Merge with existing
        json_path = self.output_dir / "word_decompositions.json"
        existing_words = []

        if json_path.exists():
            with open(json_path) as f:
                data = json.load(f)
                existing_words = data.get("words", [])

        # Combine, avoiding duplicates
        all_words = existing_words + self.decompositions
        seen = set()
        unique_words = []
        for entry in all_words:
            key = f"{entry['word']}_{entry['pos']}"
            if key not in seen:
                seen.add(key)
                unique_words.append(entry)

        # Save JSON
        output = {
            "metadata": {
                "version": "3.0",
                "architecture": "Hadamard-OTP",
                "generated_by": "build_lexicon_from_nltk.py",
                "sources": ["FrameNet", "WordNet", "core_vocabulary"],
                "word_count": len(unique_words)
            },
            "words": unique_words
        }

        with open(json_path, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\nSaved {len(unique_words)} words to {json_path}")

        # Print statistics
        print("\n=== Statistics ===")
        print(f"  Total words: {len(unique_words)}")
        print(f"  From FrameNet: {self.stats['framenet_words']}")
        print(f"  From WordNet: {self.stats['wordnet_words']}")
        print(f"  Core vocabulary: {len([w for w in unique_words if w.get('source') == 'core_vocabulary'])}")

        return json_path


def main():
    """Main entry point."""
    print("=" * 60)
    print("GSE Lexicon Builder")
    print("=" * 60)

    # Ensure we have NLTK data
    print("\n1. Checking NLTK data...")
    ensure_nltk_data()

    # Initialize builder
    print("2. Initializing lexicon builder...")
    builder = GSELexiconBuilder(output_dir="data")

    # Add core vocabulary first (highest quality)
    print("\n3. Processing core vocabulary...")
    builder.add_core_vocabulary()

    # Process FrameNet
    print("\n4. Processing FrameNet...")
    builder.process_framenet(max_frames=None)  # Process all frames

    # Process WordNet (limit to avoid explosion)
    print("\n5. Processing WordNet...")
    builder.process_wordnet(max_synsets=20000)  # Top 20k synsets

    # Save results
    print("\n6. Saving lexicon...")
    json_path = builder.save()

    print("\n" + "=" * 60)
    print("Lexicon build complete!")
    print(f"Output: {json_path}")
    print("\nNext step: Run 'python scripts/rebuild_lexicon.py' to generate vectors")
    print("=" * 60)


if __name__ == "__main__":
    main()
