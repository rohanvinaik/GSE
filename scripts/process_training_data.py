"""
Training data pipeline for multi-scale GSE encoding.

Processes the user's training corpus with special handling for:
- Pre-verbal gestalt expressions
- Analogies and semantic shortcuts
- Meta-cognitive markers
- Emotional intensity patterns
"""

import json
import logging
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

import ijson

# Ensure gse is in path for imports if needed
sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ContentType(Enum):
    """Types of content with training significance."""

    THEORETICAL = "theoretical"  # System frameworks
    METACOGNITIVE = "metacognitive"  # How user thinks
    TECHNICAL = "technical"  # Problem-solving
    PHILOSOPHICAL = "philosophical"  # Deep analogical reasoning
    COMMUNICATION = "communication"  # Rhetorical patterns
    EMOTIONAL = "emotional"  # High-intensity writing
    CONVERSATION = "conversation"  # Dialogue format


# Content classification based on filename patterns
CONTENT_CLASSIFIERS = {
    ContentType.THEORETICAL: [
        "coec",
        "minsky",
        "otp",
        "theory",
        "framework",
        "computation",
        "ontological",
        "langlands",
    ],
    ContentType.METACOGNITIVE: ["shadow", "cognitive", "adhd", "natural_philosopher", "cognition", "mental"],
    ContentType.TECHNICAL: ["genomevault", "hdc", "neural", "pde", "solver", "blockchain", "kimaiya", "bio"],
    ContentType.PHILOSOPHICAL: ["gita", "helpless", "moral", "kami", "ethics", "ontological_framework"],
    ContentType.COMMUNICATION: ["winston", "lecture", "psa", "letter"],
    ContentType.EMOTIONAL: ["political", "rant", "raw_text"],
}

# Special markers to detect in text (from user's patterns)
GESTALT_MARKERS = [
    "it's like",
    "there's this",
    "i can feel",
    "i just know",
    "something about",
    "the shape of",
    "hard to articulate",
    "pre-verbal",
    "gestalt",
    "ineffable",
    "intangible",
]

META_MARKERS = [
    "i'm trying to",
    "what i mean is",
    "the thing is",
    "thinking about this",
    "i'm realizing",
    "notice how",
    "the pattern here",
    "what's interesting",
]

INTENSITY_MARKERS = [
    "fucking",
    "goddamn",
    "absolute",
    "utter",
    "complete",
    "incredible",
    "unbelievable",
    "insane",
    "ridiculous",
]


@dataclass
class TrainingDocument:
    """A document from the training corpus."""

    source: str
    content_type: ContentType
    text: str
    metadata: Dict[str, Any]

    # Enhanced features
    has_gestalt_markers: bool = False
    has_meta_markers: bool = False
    intensity_level: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "content_type": self.content_type.value,
            "text": self.text,
            "metadata": self.metadata,
            "has_gestalt_markers": self.has_gestalt_markers,
            "has_meta_markers": self.has_meta_markers,
            "intensity_level": self.intensity_level,
        }


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    uuid: str
    role: str
    content: str
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrainingConversation:
    """A conversation from the training corpus."""

    uuid: str
    title: str
    turns: List[ConversationTurn]
    metadata: Dict[str, Any]

    # Enhanced features
    has_gestalt_emergence: bool = False
    has_meta_reflection: bool = False
    intensity_arc: List[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "title": self.title,
            "turns": [t.to_dict() for t in self.turns],
            "metadata": self.metadata,
            "has_gestalt_emergence": self.has_gestalt_emergence,
            "has_meta_reflection": self.has_meta_reflection,
        }


def classify_content(filename: str, text: str) -> ContentType:
    """Classify content type based on filename and content analysis."""
    filename_lower = filename.lower()

    # Check filename patterns
    for content_type, patterns in CONTENT_CLASSIFIERS.items():
        for pattern in patterns:
            if pattern in filename_lower:
                return content_type

    # Fallback: analyze content
    text_lower = text.lower()[:1000]

    if any(m in text_lower for m in GESTALT_MARKERS + META_MARKERS):
        return ContentType.METACOGNITIVE
    elif any(m in text_lower for m in INTENSITY_MARKERS):
        return ContentType.EMOTIONAL

    return ContentType.THEORETICAL


def analyze_text_features(text: str) -> Tuple[bool, bool, float]:
    """Analyze text for gestalt markers, meta markers, and intensity."""
    text_lower = text.lower()

    has_gestalt = any(m in text_lower for m in GESTALT_MARKERS)
    has_meta = any(m in text_lower for m in META_MARKERS)

    # Calculate intensity
    intensity = 0.5
    for marker in INTENSITY_MARKERS:
        if marker in text_lower:
            intensity = min(1.0, intensity + 0.1)

    # Check for caps
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if caps_ratio > 0.1:
        intensity = min(1.0, intensity + 0.2)

    # Check for exclamation marks
    if text.count("!") > 3:
        intensity = min(1.0, intensity + 0.15)

    return has_gestalt, has_meta, intensity


def process_text_file(filepath: Path) -> TrainingDocument:
    """Process a single text file."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    # Remove BOM if present
    if text.startswith("\ufeff"):
        text = text[1:]

    content_type = classify_content(filepath.name, text)
    has_gestalt, has_meta, intensity = analyze_text_features(text)

    return TrainingDocument(
        source=str(filepath),
        content_type=content_type,
        text=text,
        metadata={
            "filename": filepath.name,
            "size_bytes": filepath.stat().st_size,
        },
        has_gestalt_markers=has_gestalt,
        has_meta_markers=has_meta,
        intensity_level=intensity,
    )


def stream_conversations(json_path: Path) -> Generator[TrainingConversation, None, None]:
    """
    Stream conversations from a large JSON export.

    Uses ijson for memory-efficient streaming.
    """
    logger.info(f"Streaming conversations from {json_path}")

    with open(json_path, "rb") as f:
        parser = ijson.parse(f)

        current_conv = None
        current_turns = []
        in_messages = False
        current_message = {}

        for prefix, event, value in parser:
            # Start of a new conversation
            if prefix == "item" and event == "start_map":
                current_conv = {"uuid": None, "title": None, "turns": []}
                current_turns = []

            # UUID field
            elif prefix == "item.uuid":
                current_conv["uuid"] = value

            # Title field (might be "name" in some exports)
            elif prefix in ["item.title", "item.name"]:
                current_conv["title"] = value

            # Start of messages array
            elif prefix == "item.chat_messages" and event == "start_array":
                in_messages = True

            # Individual message fields
            elif in_messages and prefix.startswith("item.chat_messages.item"):
                if event == "start_map":
                    current_message = {}
                elif event == "end_map":
                    if current_message.get("text"):
                        role = current_message.get("sender", "unknown")
                        # Normalize role names
                        if role in ["human", "user"]:
                            role = "user"
                        elif role in ["assistant", "claude"]:
                            role = "assistant"

                        turn = ConversationTurn(
                            uuid=current_message.get("uuid", ""),
                            role=role,
                            content=current_message.get("text", ""),
                            timestamp=current_message.get("created_at"),
                        )
                        current_turns.append(turn)
                elif event in ["string", "number", "boolean"]:
                    # Extract field name from prefix
                    parts = prefix.split(".")
                    if len(parts) >= 4:
                        field = parts[-1]
                        current_message[field] = value

            # End of messages array
            elif prefix == "item.chat_messages" and event == "end_array":
                in_messages = False

            # End of conversation
            elif prefix == "item" and event == "end_map":
                if current_conv and current_turns:
                    # Analyze for special features
                    all_text = " ".join(t.content for t in current_turns)
                    has_gestalt, has_meta, _ = analyze_text_features(all_text)

                    # Calculate intensity arc
                    intensity_arc = []
                    for turn in current_turns:
                        _, _, intensity = analyze_text_features(turn.content)
                        intensity_arc.append(intensity)

                    conv = TrainingConversation(
                        uuid=current_conv["uuid"] or "",
                        title=current_conv["title"] or "",
                        turns=current_turns,
                        metadata={},
                        has_gestalt_emergence=has_gestalt,
                        has_meta_reflection=has_meta,
                        intensity_arc=intensity_arc,
                    )

                    yield conv

                current_conv = None
                current_turns = []


class TrainingDataPipeline:
    """Pipeline for processing training data."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.text_dir = data_dir / "training_text"
        self.conversations_file = self.text_dir / "conversations.json"

    def process_text_files(self) -> Generator[TrainingDocument, None, None]:
        """Process all text files in the training directory."""
        if not self.text_dir.exists():
            logger.warning(f"Text directory not found: {self.text_dir}")
            return

        for filepath in self.text_dir.glob("*.txt"):
            logger.info(f"Processing: {filepath.name}")
            try:
                doc = process_text_file(filepath)
                yield doc
            except Exception as e:
                logger.error(f"Error processing {filepath}: {e}")

    def process_conversations(self) -> Generator[TrainingConversation, None, None]:
        """Process conversations from JSON export."""
        if not self.conversations_file.exists():
            logger.warning(f"Conversations file not found: {self.conversations_file}")
            return

        yield from stream_conversations(self.conversations_file)

    def get_content_statistics(self) -> Dict[str, Any]:
        """Get statistics about the training data."""
        stats = {
            "text_files": {},
            "conversations": {
                "total": 0,
                "with_gestalt": 0,
                "with_meta": 0,
            },
        }

        # Count text files by type
        for doc in self.process_text_files():
            content_type = doc.content_type.value
            if content_type not in stats["text_files"]:
                stats["text_files"][content_type] = {
                    "count": 0,
                    "total_size": 0,
                    "with_gestalt": 0,
                    "with_meta": 0,
                }
            stats["text_files"][content_type]["count"] += 1
            stats["text_files"][content_type]["total_size"] += len(doc.text)
            if doc.has_gestalt_markers:
                stats["text_files"][content_type]["with_gestalt"] += 1
            if doc.has_meta_markers:
                stats["text_files"][content_type]["with_meta"] += 1

        # Count conversations (sample first 100 to avoid processing all)
        conv_count = 0
        for conv in self.process_conversations():
            stats["conversations"]["total"] += 1
            if conv.has_gestalt_emergence:
                stats["conversations"]["with_gestalt"] += 1
            if conv.has_meta_reflection:
                stats["conversations"]["with_meta"] += 1

            conv_count += 1
            if conv_count >= 100:
                logger.info("Sampled 100 conversations for statistics")
                break

        return stats


# ============================================================================
# TESTS
# ============================================================================


def test_pipeline():
    """Test the training pipeline."""
    # Test content classification
    assert classify_content("shadow_adhd.txt", "test") == ContentType.METACOGNITIVE
    assert classify_content("genomevault_pitch.txt", "test") == ContentType.TECHNICAL
    assert classify_content("political_rants.txt", "test") == ContentType.EMOTIONAL

    # Test feature analysis
    has_gestalt, has_meta, intensity = analyze_text_features(
        "It's like there's this shape I can feel but can't articulate."
    )
    assert has_gestalt

    has_gestalt, has_meta, intensity = analyze_text_features(
        "I'm trying to understand the pattern here. What's interesting is..."
    )
    assert has_meta

    has_gestalt, has_meta, intensity = analyze_text_features(
        "This is absolutely FUCKING ridiculous!! I can't believe it!"
    )
    assert intensity > 0.7

    print("✓ Training pipeline tests passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_pipeline()
    else:
        # Run actual pipeline if data exists
        # Default to a data directory relative to the script or user home
        data_dir = Path("/Users/rohanvinaik/relational-ai/data")
        if not data_dir.exists():
            data_dir = Path("data")  # Fallback to local data dir

        if data_dir.exists():
            pipeline = TrainingDataPipeline(data_dir)
            stats = pipeline.get_content_statistics()
            print("\nTraining Data Statistics:")
            print(json.dumps(stats, indent=2))
        else:
            print(f"Data directory not found: {data_dir}")
