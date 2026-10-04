#!/usr/bin/env python3
"""
GSE Profile Manager - Multiple Learning Behavior Profiles ("Accents")

Manages multiple independent learned behavior profiles, each with their own
network weights, K-line patterns, and training statistics. Supports:
- Creating new profiles from scratch or by cloning
- Saving/loading profiles to/from disk
- Switching active profiles at runtime
- Merging multiple profiles

Usage:
    manager = ProfileManager()
    manager.create_profile("technical_writing")
    manager.switch_profile("technical_writing")

    # Get active networks for teaching
    networks = manager.get_active_networks()
    networks.word_scale.learn({"GOOD": 1.0, "FEEL": 0.8})

    # Save after teaching
    manager.save_active_profile()
"""

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from gse.patterns.networks_v2 import (
    ParagraphScaleNetwork,
    ScaleNetworkCollection,
    SentenceScaleNetwork,
    TextScaleNetwork,
    WordScaleNetwork,
)
from gse.patterns.orchestrator import OrchestratorNetwork


@dataclass
class ProfileMetadata:
    """Metadata about a learning profile."""
    name: str
    created_at: str
    modified_at: str
    description: str = ""

    # Teaching statistics
    epochs_completed: int = 0
    documents_processed: int = 0
    total_tokens: int = 0
    teaching_corpus: List[str] = field(default_factory=list)

    # Epoch history for tracking behavior changes
    epoch_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "description": self.description,
            "epochs_completed": self.epochs_completed,
            "documents_processed": self.documents_processed,
            "total_tokens": self.total_tokens,
            "teaching_corpus": self.teaching_corpus,
            "epoch_history": self.epoch_history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProfileMetadata":
        return cls(
            name=data["name"],
            created_at=data["created_at"],
            modified_at=data["modified_at"],
            description=data.get("description", ""),
            epochs_completed=data.get("epochs_completed", 0),
            documents_processed=data.get("documents_processed", 0),
            total_tokens=data.get("total_tokens", 0),
            teaching_corpus=data.get("teaching_corpus", []),
            epoch_history=data.get("epoch_history", []),
        )


@dataclass
class LearningProfile:
    """
    A complete learned behavior profile (accent).

    Contains all network weights and patterns that define
    a particular learned behavior style.
    """
    metadata: ProfileMetadata

    # Scale-specific networks
    text_network: TextScaleNetwork = field(default_factory=TextScaleNetwork)
    paragraph_network: ParagraphScaleNetwork = field(default_factory=ParagraphScaleNetwork)
    sentence_network: SentenceScaleNetwork = field(default_factory=SentenceScaleNetwork)
    word_network: WordScaleNetwork = field(default_factory=WordScaleNetwork)

    # Orchestrator network
    orchestrator: OrchestratorNetwork = field(default_factory=OrchestratorNetwork)

    def get_network_collection(self) -> ScaleNetworkCollection:
        """Get networks as a collection."""
        return ScaleNetworkCollection(
            text_scale=self.text_network,
            paragraph_scale=self.paragraph_network,
            sentence_scale=self.sentence_network,
            word_scale=self.word_network,
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get current profile statistics."""
        return {
            "name": self.metadata.name,
            "epochs_completed": self.metadata.epochs_completed,
            "documents_processed": self.metadata.documents_processed,
            "total_tokens": self.metadata.total_tokens,
            "text_network_updates": self.text_network.update_count,
            "paragraph_network_updates": self.paragraph_network.update_count,
            "sentence_network_updates": self.sentence_network.update_count,
            "word_network_updates": self.word_network.update_count,
            "orchestrator_updates": self.orchestrator.update_count,
        }

    def record_epoch(self, epoch_num: int, file_processed: str, stats: Dict[str, Any]):
        """Record epoch completion in history."""
        self.metadata.epoch_history.append({
            "epoch": epoch_num,
            "file": file_processed,
            "timestamp": datetime.now().isoformat(),
            "stats": stats,
        })
        self.metadata.epochs_completed = epoch_num
        self.metadata.modified_at = datetime.now().isoformat()


class ProfileManager:
    """
    Manage multiple learning profiles.

    Handles creation, persistence, and switching of profiles.
    Each profile is stored in a separate directory with:
    - metadata.json: Profile metadata and statistics
    - text_network.json: Text scale network weights
    - paragraph_network.json: Paragraph scale network weights
    - sentence_network.json: Sentence scale network weights
    - word_network.json: Word scale network weights
    - orchestrator.json: Orchestrator network weights
    """

    def __init__(self, profiles_dir: str = "data/profiles"):
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

        self._active_profile: Optional[LearningProfile] = None
        self._active_name: Optional[str] = None

    @property
    def active_profile(self) -> Optional[LearningProfile]:
        """Get currently active profile."""
        return self._active_profile

    @property
    def active_name(self) -> Optional[str]:
        """Get name of currently active profile."""
        return self._active_name

    def list_profiles(self) -> List[str]:
        """List all available profile names."""
        profiles = []
        for path in self.profiles_dir.iterdir():
            if path.is_dir() and (path / "metadata.json").exists():
                profiles.append(path.name)
        return sorted(profiles)

    def profile_exists(self, name: str) -> bool:
        """Check if a profile exists."""
        return (self.profiles_dir / name / "metadata.json").exists()

    def create_profile(
        self,
        name: str,
        description: str = "",
        clone_from: Optional[str] = None,
    ) -> LearningProfile:
        """
        Create a new learning profile.

        Args:
            name: Profile name (alphanumeric + underscores)
            description: Optional description
            clone_from: Optional existing profile to clone from

        Returns:
            New LearningProfile instance
        """
        # Validate name
        if not name.replace("_", "").isalnum():
            raise ValueError(f"Invalid profile name: {name}")

        profile_dir = self.profiles_dir / name
        if profile_dir.exists():
            raise ValueError(f"Profile '{name}' already exists")

        profile_dir.mkdir(parents=True)

        if clone_from:
            # Clone from existing profile
            source_dir = self.profiles_dir / clone_from
            if not source_dir.exists():
                raise ValueError(f"Source profile '{clone_from}' not found")

            # Copy network files
            for file in ["text_network.json", "paragraph_network.json",
                         "sentence_network.json", "word_network.json",
                         "orchestrator.json"]:
                src = source_dir / file
                if src.exists():
                    shutil.copy(src, profile_dir / file)

            # Load and modify metadata
            profile = self._load_profile(clone_from)
            profile.metadata.name = name
            profile.metadata.description = f"Cloned from {clone_from}. {description}"
            profile.metadata.created_at = datetime.now().isoformat()
            profile.metadata.modified_at = datetime.now().isoformat()

        else:
            # Create fresh profile
            metadata = ProfileMetadata(
                name=name,
                created_at=datetime.now().isoformat(),
                modified_at=datetime.now().isoformat(),
                description=description,
            )
            profile = LearningProfile(metadata=metadata)

        # Save the new profile
        self._save_profile(profile)

        return profile

    def load_profile(self, name: str) -> LearningProfile:
        """Load a profile from disk."""
        if not self.profile_exists(name):
            raise ValueError(f"Profile '{name}' not found")
        return self._load_profile(name)

    def _load_profile(self, name: str) -> LearningProfile:
        """Internal: Load profile without existence check."""
        profile_dir = self.profiles_dir / name

        # Load metadata
        with open(profile_dir / "metadata.json") as f:
            metadata = ProfileMetadata.from_dict(json.load(f))

        # Create profile with fresh networks
        profile = LearningProfile(metadata=metadata)

        # Load network weights
        network_files = {
            "text_network.json": profile.text_network,
            "paragraph_network.json": profile.paragraph_network,
            "sentence_network.json": profile.sentence_network,
            "word_network.json": profile.word_network,
            "orchestrator.json": profile.orchestrator,
        }

        for filename, network in network_files.items():
            filepath = profile_dir / filename
            if filepath.exists():
                with open(filepath) as f:
                    data = json.load(f)
                    network.weights = np.array(data["weights"])
                    network.update_count = data.get("update_count", 0)
                    network.total_activations = data.get("total_activations", 0)

        return profile

    def save_profile(self, profile: LearningProfile):
        """Save a profile to disk."""
        self._save_profile(profile)

    def _save_profile(self, profile: LearningProfile):
        """Internal: Save profile to disk."""
        profile_dir = self.profiles_dir / profile.metadata.name
        profile_dir.mkdir(parents=True, exist_ok=True)

        # Save metadata
        profile.metadata.modified_at = datetime.now().isoformat()
        with open(profile_dir / "metadata.json", "w") as f:
            json.dump(profile.metadata.to_dict(), f, indent=2)

        # Save network weights
        network_files = {
            "text_network.json": profile.text_network,
            "paragraph_network.json": profile.paragraph_network,
            "sentence_network.json": profile.sentence_network,
            "word_network.json": profile.word_network,
            "orchestrator.json": profile.orchestrator,
        }

        for filename, network in network_files.items():
            filepath = profile_dir / filename
            with open(filepath, "w") as f:
                json.dump({
                    "weights": network.weights.tolist(),
                    "update_count": network.update_count,
                    "total_activations": network.total_activations,
                }, f)

    def save_active_profile(self):
        """Save the currently active profile."""
        if self._active_profile:
            self._save_profile(self._active_profile)

    def switch_profile(self, name: str) -> LearningProfile:
        """
        Switch to a different profile.

        Saves current profile before switching.

        Args:
            name: Name of profile to switch to

        Returns:
            The newly activated profile
        """
        # Save current profile if any
        if self._active_profile:
            self._save_profile(self._active_profile)

        # Load and activate new profile
        profile = self.load_profile(name)
        self._active_profile = profile
        self._active_name = name

        return profile

    def get_active_networks(self) -> Optional[ScaleNetworkCollection]:
        """Get network collection from active profile."""
        if self._active_profile:
            return self._active_profile.get_network_collection()
        return None

    def delete_profile(self, name: str):
        """Delete a profile."""
        if name == self._active_name:
            raise ValueError("Cannot delete active profile")

        profile_dir = self.profiles_dir / name
        if profile_dir.exists():
            shutil.rmtree(profile_dir)

    def get_profile_info(self, name: str) -> Dict[str, Any]:
        """Get information about a profile without fully loading it."""
        profile_dir = self.profiles_dir / name
        if not (profile_dir / "metadata.json").exists():
            raise ValueError(f"Profile '{name}' not found")

        with open(profile_dir / "metadata.json") as f:
            return json.load(f)

    def merge_profiles(
        self,
        names: List[str],
        output_name: str,
        weights: Optional[List[float]] = None,
    ) -> LearningProfile:
        """
        Merge multiple profiles into a new profile.

        Network weights are averaged (or weighted average if weights provided).

        Args:
            names: List of profile names to merge
            output_name: Name for the merged profile
            weights: Optional weights for averaging (must sum to 1)

        Returns:
            New merged profile
        """
        if len(names) < 2:
            raise ValueError("Need at least 2 profiles to merge")

        if weights is None:
            weights = [1.0 / len(names)] * len(names)

        if abs(sum(weights) - 1.0) > 1e-6:
            raise ValueError("Weights must sum to 1")

        # Load all profiles
        profiles = [self.load_profile(name) for name in names]

        # Create new profile
        merged = self.create_profile(
            output_name,
            description=f"Merged from: {', '.join(names)}",
        )

        # Average network weights
        for attr in ["text_network", "paragraph_network", "sentence_network",
                     "word_network", "orchestrator"]:
            merged_weights = sum(
                w * getattr(p, attr).weights
                for w, p in zip(weights, profiles)
            )
            getattr(merged, attr).weights = merged_weights

        self._save_profile(merged)
        return merged


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    import tempfile

    print("=== Profile Manager Self-Test ===\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ProfileManager(profiles_dir=tmpdir)

        # Test 1: Create profile
        print("1. Creating profile 'test_profile'...")
        profile = manager.create_profile("test_profile", "Test description")
        print(f"   Created: {profile.metadata.name}")
        print(f"   Networks initialized: text={profile.text_network.weights.shape}")

        # Test 2: List profiles
        print("\n2. Listing profiles...")
        profiles = manager.list_profiles()
        print(f"   Found: {profiles}")

        # Test 3: Switch and learn
        print("\n3. Switching to profile and learning...")
        manager.switch_profile("test_profile")
        manager.active_profile.word_network.learn({"GOOD": 1.0, "FEEL": 0.8})
        print(f"   Word network updates: {manager.active_profile.word_network.update_count}")

        # Test 4: Save and reload
        print("\n4. Saving and reloading...")
        manager.save_active_profile()
        manager._active_profile = None  # Force reload
        reloaded = manager.load_profile("test_profile")
        print(f"   Reloaded update count: {reloaded.word_network.update_count}")

        # Test 5: Clone profile
        print("\n5. Cloning profile...")
        cloned = manager.create_profile("cloned_profile", clone_from="test_profile")
        print(f"   Cloned weights match: {np.allclose(profile.word_network.weights, cloned.word_network.weights)}")

        # Test 6: Get profile info
        print("\n6. Getting profile info...")
        info = manager.get_profile_info("test_profile")
        print(f"   Name: {info['name']}, Created: {info['created_at'][:10]}")

    print("\n=== All Tests Passed ===")
