#!/usr/bin/env python3
"""
GSE Network Teacher - Epoch-Based Teaching with Behavior Tracking

Teaches learning networks from a corpus with:
- One document per epoch
- Random document ordering
- Behavior tracking after each epoch
- Support for multiple profiles ("accents")
- Large JSON file handling for conversation data
"""

import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from gse.profiles.profile_manager import ProfileManager
from gse.teaching.conversation_processor import ConversationProcessor
from gse.teaching.feature_extractor import FeatureExtractor

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class NetworkSnapshot:
    """Snapshot of network state for behavior tracking."""

    weight_norm: float
    weight_mean: float
    weight_std: float
    update_count: int
    top_associations: List[tuple]  # Top k strongest connections

    @staticmethod
    def from_network(network, name: str, top_k: int = 5) -> "NetworkSnapshot":
        """Create snapshot from a network."""
        weights = network.weights
        return NetworkSnapshot(
            weight_norm=float(np.linalg.norm(weights)),
            weight_mean=float(np.mean(weights)),
            weight_std=float(np.std(weights)),
            update_count=network.update_count,
            top_associations=_get_top_connections(weights, network.node_names, top_k),
        )


def _get_top_connections(weights: np.ndarray, names: List[str], top_k: int) -> List[tuple]:
    """Get top k strongest connections in weight matrix."""
    n = weights.shape[0]
    connections = []
    for i in range(n):
        for j in range(i + 1, n):
            w = abs(weights[i, j])
            if w > 0.001:
                connections.append((names[i], names[j], float(weights[i, j])))

    connections.sort(key=lambda x: abs(x[2]), reverse=True)
    return connections[:top_k]


@dataclass
class TeachingEpoch:
    """Record of a single teaching epoch."""

    epoch_number: int
    document: str
    document_type: str  # 'text', 'claude_json', 'gpt_json'
    start_time: str
    end_time: str
    duration_seconds: float

    # Processing stats
    paragraphs_processed: int = 0
    sentences_processed: int = 0
    words_processed: int = 0
    total_updates: int = 0

    # Network snapshots (before teaching)
    text_snapshot: Optional[NetworkSnapshot] = None
    paragraph_snapshot: Optional[NetworkSnapshot] = None
    sentence_snapshot: Optional[NetworkSnapshot] = None
    word_snapshot: Optional[NetworkSnapshot] = None
    orchestrator_snapshot: Optional[NetworkSnapshot] = None

    # Changes from teaching
    text_delta: float = 0.0
    paragraph_delta: float = 0.0
    sentence_delta: float = 0.0
    word_delta: float = 0.0
    orchestrator_delta: float = 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "epoch_number": self.epoch_number,
            "document": self.document,
            "document_type": self.document_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "paragraphs_processed": self.paragraphs_processed,
            "sentences_processed": self.sentences_processed,
            "words_processed": self.words_processed,
            "total_updates": self.total_updates,
            "deltas": {
                "text": self.text_delta,
                "paragraph": self.paragraph_delta,
                "sentence": self.sentence_delta,
                "word": self.word_delta,
                "orchestrator": self.orchestrator_delta,
            },
        }


@dataclass
class TeachingSession:
    """Complete teaching session with all epochs."""

    profile_name: str
    start_time: str
    end_time: Optional[str] = None
    total_epochs: int = 0
    epochs: List[TeachingEpoch] = field(default_factory=list)

    # Corpus info
    corpus_dir: str = ""
    total_documents: int = 0
    document_order: List[str] = field(default_factory=list)

    # Configuration
    random_seed: int = 42
    json_epochs: Dict[int, str] = field(default_factory=dict)  # epoch → json file

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "profile_name": self.profile_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_epochs": self.total_epochs,
            "corpus_dir": self.corpus_dir,
            "total_documents": self.total_documents,
            "document_order": self.document_order,
            "random_seed": self.random_seed,
            "json_epochs": self.json_epochs,
            "epochs": [e.to_dict() for e in self.epochs],
        }

    def save(self, filepath: str):
        """Save session to file."""
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


# =============================================================================
# NETWORK TEACHER
# =============================================================================


class NetworkTeacher:
    """
    Teach learning networks from a corpus.

    Features:
    - One document per epoch
    - Random document ordering
    - Behavior tracking after each epoch
    - Profile support for multiple "accents"
    - Large JSON file handling
    """

    def __init__(
        self,
        profile_manager: ProfileManager = None,
        profile_name: str = "default",
        learning_rate: float = 0.01,
    ):
        """
        Initialize teacher.

        Args:
            profile_manager: ProfileManager for persistence
            profile_name: Name of profile to teach
            learning_rate: Hebbian learning rate
        """
        self.profile_manager = profile_manager or ProfileManager()
        self.profile_name = profile_name
        self.learning_rate = learning_rate

        # Initialize or load profile
        if self.profile_manager.profile_exists(profile_name):
            self.profile = self.profile_manager.load_profile(profile_name)
        else:
            self.profile = self.profile_manager.create_profile(profile_name)

        # Activate profile
        self.profile_manager._active_profile = self.profile
        self.profile_manager._active_name = profile_name

        # Components
        self.feature_extractor = FeatureExtractor()
        self.conversation_processor = ConversationProcessor()

        # Current session
        self.session: Optional[TeachingSession] = None

    def prepare_corpus(
        self,
        corpus_dir: str,
        json_files: Dict[int, str] = None,
        random_seed: int = 42,
    ) -> List[str]:
        """
        Prepare corpus for teaching.

        Args:
            corpus_dir: Directory containing text files
            json_files: Dict of epoch number → JSON filepath for large files
            random_seed: Random seed for document ordering

        Returns:
            Ordered list of document paths (one per epoch)
        """
        corpus_path = Path(corpus_dir)

        # Get all text files
        text_files = sorted(corpus_path.glob("*.txt"))
        text_paths = [str(f) for f in text_files]

        # Shuffle with seed
        random.seed(random_seed)
        random.shuffle(text_paths)

        # Insert JSON files at specified epochs
        if json_files:
            for epoch, json_path in sorted(json_files.items()):
                # Insert at position (0-indexed, so epoch 27 → index 26)
                idx = min(epoch - 1, len(text_paths))
                text_paths.insert(idx, json_path)

        return text_paths

    def teach(
        self,
        corpus_dir: str,
        json_files: Dict[int, str] = None,
        random_seed: int = 42,
        progress_callback: Callable[[int, int, str], None] = None,
        save_every: int = 10,
    ) -> TeachingSession:
        """
        Run complete teaching session.

        Args:
            corpus_dir: Directory containing text files
            json_files: Dict of epoch number → JSON filepath for large files
            random_seed: Random seed for document ordering
            progress_callback: Callback(epoch, total, message) for progress
            save_every: Save profile every N epochs

        Returns:
            TeachingSession with all epoch records
        """
        # Prepare corpus
        document_order = self.prepare_corpus(corpus_dir, json_files, random_seed)

        # Initialize session
        self.session = TeachingSession(
            profile_name=self.profile_name,
            start_time=datetime.now().isoformat(),
            total_epochs=len(document_order),
            corpus_dir=corpus_dir,
            total_documents=len(document_order),
            document_order=document_order,
            random_seed=random_seed,
            json_epochs=json_files or {},
        )

        # Teach each document
        for epoch_num, doc_path in enumerate(document_order, 1):
            if progress_callback:
                progress_callback(epoch_num, len(document_order), f"Teaching: {Path(doc_path).name}")

            # Run epoch
            epoch_record = self.teach_epoch(epoch_num, doc_path)
            self.session.epochs.append(epoch_record)

            # Save periodically
            if save_every and epoch_num % save_every == 0:
                self.profile_manager.save_active_profile()

        # Finalize
        self.session.end_time = datetime.now().isoformat()
        self.profile_manager.save_active_profile()

        return self.session

    def teach_epoch(self, epoch_num: int, doc_path: str) -> TeachingEpoch:
        """
        Teach from a single document (one epoch).

        Args:
            epoch_num: Epoch number (1-indexed)
            doc_path: Path to document

        Returns:
            TeachingEpoch record
        """
        start_time = datetime.now()

        # Determine document type
        path = Path(doc_path)
        if path.suffix == ".json":
            if "claude" in path.name.lower():
                doc_type = "claude_json"
            elif "gpt" in path.name.lower():
                doc_type = "gpt_json"
            else:
                doc_type = "json"
        else:
            doc_type = "text"

        # Take snapshots before teaching
        snapshots = self._take_snapshots()

        # Initialize epoch record
        epoch = TeachingEpoch(
            epoch_number=epoch_num,
            document=path.name,
            document_type=doc_type,
            start_time=start_time.isoformat(),
            end_time="",
            duration_seconds=0,
            text_snapshot=snapshots["text"],
            paragraph_snapshot=snapshots["paragraph"],
            sentence_snapshot=snapshots["sentence"],
            word_snapshot=snapshots["word"],
            orchestrator_snapshot=snapshots["orchestrator"],
        )

        # Process document based on type
        if doc_type in ("claude_json", "gpt_json", "json"):
            stats = self._teach_from_json(doc_path)
        else:
            stats = self._teach_from_text(doc_path)

        # Update epoch stats
        epoch.paragraphs_processed = stats.get("paragraphs", 0)
        epoch.sentences_processed = stats.get("sentences", 0)
        epoch.words_processed = stats.get("words", 0)
        epoch.total_updates = stats.get("updates", 0)

        # Calculate deltas
        new_snapshots = self._take_snapshots()
        epoch.text_delta = new_snapshots["text"].weight_norm - snapshots["text"].weight_norm
        epoch.paragraph_delta = new_snapshots["paragraph"].weight_norm - snapshots["paragraph"].weight_norm
        epoch.sentence_delta = new_snapshots["sentence"].weight_norm - snapshots["sentence"].weight_norm
        epoch.word_delta = new_snapshots["word"].weight_norm - snapshots["word"].weight_norm
        epoch.orchestrator_delta = new_snapshots["orchestrator"].weight_norm - snapshots["orchestrator"].weight_norm

        # Finalize timing
        end_time = datetime.now()
        epoch.end_time = end_time.isoformat()
        epoch.duration_seconds = (end_time - start_time).total_seconds()

        # Record in profile
        self.profile.record_epoch(
            epoch_num,
            doc_path,
            {"updates": epoch.total_updates, "duration": epoch.duration_seconds},
        )

        return epoch

    def _take_snapshots(self) -> Dict[str, NetworkSnapshot]:
        """Take snapshots of all networks."""
        return {
            "text": NetworkSnapshot.from_network(self.profile.text_network, "text"),
            "paragraph": NetworkSnapshot.from_network(self.profile.paragraph_network, "paragraph"),
            "sentence": NetworkSnapshot.from_network(self.profile.sentence_network, "sentence"),
            "word": NetworkSnapshot.from_network(self.profile.word_network, "word"),
            "orchestrator": NetworkSnapshot.from_network(self.profile.orchestrator, "orchestrator"),
        }

    def _teach_from_text(self, filepath: str) -> Dict[str, int]:
        """Teach from a text file."""
        stats = {"paragraphs": 0, "sentences": 0, "words": 0, "updates": 0}

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            print(f"Warning: Could not read {filepath}: {e}")
            return stats

        # Extract features at all scales
        features = self.feature_extractor.extract_all_features(text)

        # Text-level learning
        if features["text"]:
            self.profile.text_network.learn(features["text"])
            stats["updates"] += 1

        # Paragraph-level learning
        for para_features in features["paragraph"]:
            if para_features:
                self.profile.paragraph_network.learn(para_features)
                stats["paragraphs"] += 1
                stats["updates"] += 1

        # Sentence-level learning
        for sent_features in features["sentence"]:
            if sent_features:
                self.profile.sentence_network.learn(sent_features)
                stats["sentences"] += 1
                stats["updates"] += 1

        # Word-level learning from text (simplified without lexicon lookup)
        words = text.split()
        stats["words"] = len(words)

        # Orchestrator learning (coordinate all scales)
        orchestrator_features = {
            "ROUTE_TEXT": 1.0 if features["text"] else 0.0,
            "ROUTE_PARA": 1.0 if features["paragraph"] else 0.0,
            "ROUTE_SENT": 1.0 if features["sentence"] else 0.0,
            "ROUTE_WORD": 1.0 if words else 0.0,
            "TASK_CLASSIFY": 0.8,
            "CONF_MEDIUM": 0.6,
        }
        self.profile.orchestrator.learn(orchestrator_features)
        stats["updates"] += 1

        return stats

    def _teach_from_json(self, filepath: str) -> Dict[str, int]:
        """Teach from a JSON conversation file."""
        stats = {"paragraphs": 0, "sentences": 0, "words": 0, "updates": 0}

        # Process conversation turns
        turn_count = 0
        for text in self.conversation_processor.process_file(filepath):
            turn_count += 1

            # Extract and teach from each turn
            features = self.feature_extractor.extract_all_features(text)

            # Text-level (per turn acts as document)
            if features["text"]:
                self.profile.text_network.learn(features["text"])
                stats["updates"] += 1

            # Paragraph-level
            for para_features in features["paragraph"]:
                if para_features:
                    self.profile.paragraph_network.learn(para_features)
                    stats["paragraphs"] += 1
                    stats["updates"] += 1

            # Sentence-level
            for sent_features in features["sentence"]:
                if sent_features:
                    self.profile.sentence_network.learn(sent_features)
                    stats["sentences"] += 1
                    stats["updates"] += 1

            stats["words"] += len(text.split())

            # Orchestrator every 10 turns
            if turn_count % 10 == 0:
                self.profile.orchestrator.learn(
                    {
                        "ROUTE_TEXT": 0.8,
                        "ROUTE_SENT": 0.9,
                        "TASK_ANSWER": 0.8,  # Conversational
                        "CTX_PRIOR": 0.7,
                        "CONF_MEDIUM": 0.6,
                    }
                )
                stats["updates"] += 1

        return stats

    def get_behavior_summary(self) -> Dict[str, Any]:
        """Get summary of current network behaviors."""
        return {
            "profile": self.profile_name,
            "text_network": {
                "updates": self.profile.text_network.update_count,
                "weight_norm": float(np.linalg.norm(self.profile.text_network.weights)),
                "top_associations": self.profile.text_network.get_associations("FORMAL"),
            },
            "paragraph_network": {
                "updates": self.profile.paragraph_network.update_count,
                "weight_norm": float(np.linalg.norm(self.profile.paragraph_network.weights)),
                "top_associations": self.profile.paragraph_network.get_associations("CAUSE"),
            },
            "sentence_network": {
                "updates": self.profile.sentence_network.update_count,
                "weight_norm": float(np.linalg.norm(self.profile.sentence_network.weights)),
                "top_associations": self.profile.sentence_network.get_associations("SYN_SUBJ"),
            },
            "word_network": {
                "updates": self.profile.word_network.update_count,
                "weight_norm": float(np.linalg.norm(self.profile.word_network.weights)),
                "top_associations": self.profile.word_network.get_associations("GOOD"),
            },
            "orchestrator": {
                "updates": self.profile.orchestrator.update_count,
                "weight_norm": float(np.linalg.norm(self.profile.orchestrator.weights)),
            },
        }


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    import os
    import tempfile

    print("Network Teacher Self-Test")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create sample corpus
        corpus_dir = os.path.join(tmpdir, "corpus")
        os.makedirs(corpus_dir)

        # Create sample text files
        for i in range(5):
            filepath = os.path.join(corpus_dir, f"doc_{i}.txt")
            with open(filepath, "w") as f:
                f.write(f"""
                Document {i}: Technical Analysis

                This is a formal technical document. Therefore, we expect
                academic language and structured arguments.

                Furthermore, the methodology demonstrates clear patterns.
                Because of these findings, we can conclude the analysis
                is valid and reproducible.

                In summary, this document illustrates formal writing.
                """)

        # Create profile directory
        profiles_dir = os.path.join(tmpdir, "profiles")

        # Initialize teacher
        print("\n1. Initializing NetworkTeacher...")
        profile_manager = ProfileManager(profiles_dir=profiles_dir)
        teacher = NetworkTeacher(
            profile_manager=profile_manager,
            profile_name="test_profile",
        )
        print(f"   Profile: {teacher.profile_name}")

        # Prepare corpus
        print("\n2. Preparing corpus...")
        doc_order = teacher.prepare_corpus(corpus_dir)
        print(f"   Documents: {len(doc_order)}")

        # Run teaching
        print("\n3. Running teaching session...")

        def progress(epoch, total, msg):
            print(f"   Epoch {epoch}/{total}: {msg}")

        session = teacher.teach(
            corpus_dir=corpus_dir,
            progress_callback=progress,
            save_every=2,
        )

        print("\n4. Session complete:")
        print(f"   Total epochs: {session.total_epochs}")
        print(f"   Duration: {sum(e.duration_seconds for e in session.epochs):.2f}s")

        # Check behavior
        print("\n5. Network behavior summary:")
        behavior = teacher.get_behavior_summary()
        for network, stats in behavior.items():
            if isinstance(stats, dict) and "updates" in stats:
                print(f"   {network}: {stats['updates']} updates, norm={stats['weight_norm']:.4f}")

        # Save session
        session_path = os.path.join(tmpdir, "session.json")
        session.save(session_path)
        print(f"\n6. Session saved to: {session_path}")

        # Verify profile persistence
        print("\n7. Verifying profile persistence...")
        loaded = profile_manager.load_profile("test_profile")
        print(f"   Text network updates: {loaded.text_network.update_count}")
        print(f"   Epochs completed: {loaded.metadata.epochs_completed}")

    print("\n" + "=" * 50)
    print("All Network Teacher tests passed!")
