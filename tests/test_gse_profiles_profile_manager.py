"""Manual contract tests for gse.profiles.profile_manager."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.profiles.profile_manager import (
    LearningProfile,
    ProfileManager,
    ProfileMetadata,
)


@pytest.fixture
def tmp_profiles_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestProfileMetadata:
    def test_to_dict(self):
        m = ProfileMetadata(name="test", created_at="2026-01-01", modified_at="2026-01-02")
        d = m.to_dict()
        assert d["name"] == "test"
        assert d["created_at"] == "2026-01-01"
        assert d["modified_at"] == "2026-01-02"
        assert d["epochs_completed"] == 0

    def test_from_dict_roundtrip(self):
        original = ProfileMetadata(
            name="test",
            created_at="2026-01-01",
            modified_at="2026-01-02",
            description="desc",
            epochs_completed=5,
            documents_processed=10,
            total_tokens=100,
        )
        restored = ProfileMetadata.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.epochs_completed == 5

    def test_from_dict_defaults(self):
        d = {"name": "test", "created_at": "x", "modified_at": "y"}
        m = ProfileMetadata.from_dict(d)
        assert m.description == ""
        assert m.epochs_completed == 0
        assert m.documents_processed == 0


class TestLearningProfileGetStatistics:
    def test_returns_stats_dict(self):
        m = ProfileMetadata(name="test", created_at="x", modified_at="y")
        p = LearningProfile(metadata=m)
        stats = p.get_statistics()
        assert stats["name"] == "test"
        assert "epochs_completed" in stats
        assert "text_network_updates" in stats


class TestLearningProfileRecordEpoch:
    def test_appends_to_history(self):
        m = ProfileMetadata(name="test", created_at="x", modified_at="y")
        p = LearningProfile(metadata=m)
        p.record_epoch(1, "file.txt", {"tokens": 100})
        assert len(p.metadata.epoch_history) == 1
        assert p.metadata.epoch_history[0]["epoch"] == 1
        assert p.metadata.epoch_history[0]["file"] == "file.txt"
        assert p.metadata.epochs_completed == 1

    def test_updates_modified_at(self):
        m = ProfileMetadata(name="test", created_at="x", modified_at="orig")
        p = LearningProfile(metadata=m)
        p.record_epoch(1, "file", {})
        assert p.metadata.modified_at != "orig"


class TestProfileManagerInit:
    def test_creates_dir(self, tmp_profiles_dir):
        sub = Path(tmp_profiles_dir) / "new"
        ProfileManager(profiles_dir=str(sub))
        assert sub.exists()

    def test_no_active_initially(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        assert manager.active_profile is None
        assert manager.active_name is None


class TestListProfiles:
    def test_empty_dir(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        assert manager.list_profiles() == []

    def test_lists_created_profiles(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        manager.create_profile("alpha")
        manager.create_profile("beta")
        profiles = manager.list_profiles()
        assert sorted(profiles) == ["alpha", "beta"]


class TestProfileExists:
    def test_false_for_missing(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        assert not manager.profile_exists("xyzzy")

    def test_true_after_create(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        manager.create_profile("alpha")
        assert manager.profile_exists("alpha")


class TestCreateProfile:
    def test_creates_dir_and_files(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        manager.create_profile("alpha", description="test profile")
        profile_dir = Path(tmp_profiles_dir) / "alpha"
        assert profile_dir.exists()
        assert (profile_dir / "metadata.json").exists()
        assert (profile_dir / "text_network.json").exists()

    def test_returns_learning_profile(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        p = manager.create_profile("alpha")
        assert isinstance(p, LearningProfile)
        assert p.metadata.name == "alpha"

    def test_invalid_name_raises(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        with pytest.raises(ValueError, match="Invalid profile name"):
            manager.create_profile("invalid name with spaces")

    def test_invalid_special_chars_raises(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        with pytest.raises(ValueError):
            manager.create_profile("name-with-dashes")

    def test_duplicate_raises(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        manager.create_profile("alpha")
        with pytest.raises(ValueError, match="already exists"):
            manager.create_profile("alpha")

    def test_alphanumeric_underscore_allowed(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        manager.create_profile("test_profile_123")
        assert manager.profile_exists("test_profile_123")


class TestCloneProfile:
    def test_clone_copies_networks(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        original = manager.create_profile("alpha")
        # Modify weights
        original.text_network.update_count = 5
        manager.save_profile(original)

        clone = manager.create_profile("beta", clone_from="alpha")
        # Verify clone has same statistics
        assert clone.text_network.update_count == 5

    def test_clone_unknown_source_raises(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        with pytest.raises(ValueError, match="not found"):
            manager.create_profile("beta", clone_from="nonexistent")

    def test_clone_updates_metadata(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        manager.create_profile("alpha")
        clone = manager.create_profile("beta", clone_from="alpha", description="cloned")
        assert clone.metadata.name == "beta"
        assert "Cloned from alpha" in clone.metadata.description


class TestLoadProfile:
    def test_loads_existing(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        manager.create_profile("alpha")
        loaded = manager.load_profile("alpha")
        assert loaded.metadata.name == "alpha"

    def test_unknown_raises(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        with pytest.raises(ValueError, match="not found"):
            manager.load_profile("nonexistent")


class TestSaveProfile:
    def test_saves_state_changes(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        p = manager.create_profile("alpha")
        p.text_network.update_count = 10
        manager.save_profile(p)

        loaded = manager.load_profile("alpha")
        assert loaded.text_network.update_count == 10


class TestSaveActiveProfile:
    def test_no_active_no_op(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        # Should not raise
        manager.save_active_profile()

    def test_saves_active(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        manager.create_profile("alpha")
        manager.switch_profile("alpha")
        manager.active_profile.text_network.update_count = 7
        manager.save_active_profile()

        loaded = manager.load_profile("alpha")
        assert loaded.text_network.update_count == 7


class TestSwitchProfile:
    def test_switches(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        manager.create_profile("alpha")
        manager.create_profile("beta")

        active = manager.switch_profile("alpha")
        assert manager.active_name == "alpha"
        assert active is manager.active_profile

        manager.switch_profile("beta")
        assert manager.active_name == "beta"


class TestGetActiveNetworks:
    def test_no_active_returns_none(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        assert manager.get_active_networks() is None

    def test_active_returns_collection(self, tmp_profiles_dir):
        # Was xfailed: get_network_collection passed text_scale=/… but ScaleNetworkCollection's
        # fields are text/paragraph/sentence/word, so this raised TypeError.
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        manager.create_profile("alpha")
        manager.switch_profile("alpha")
        networks = manager.get_active_networks()
        profile = manager.active_profile
        assert networks is not None
        # The collection carries the profile's OWN networks, not fresh defaults.
        assert networks.text is profile.text_network
        assert networks.paragraph is profile.paragraph_network
        assert networks.sentence is profile.sentence_network
        assert networks.word is profile.word_network


class TestDeleteProfile:
    def test_removes_dir(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        manager.create_profile("alpha")
        manager.delete_profile("alpha")
        assert not manager.profile_exists("alpha")

    def test_active_profile_raises(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        manager.create_profile("alpha")
        manager.switch_profile("alpha")
        with pytest.raises(ValueError, match="active"):
            manager.delete_profile("alpha")

    def test_nonexistent_no_op(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        # Should not raise (delete is permissive for nonexistent)
        manager.delete_profile("nonexistent")


class TestGetProfileInfo:
    def test_returns_metadata_dict(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        manager.create_profile("alpha", description="hello")
        info = manager.get_profile_info("alpha")
        assert info["name"] == "alpha"
        assert info["description"] == "hello"

    def test_unknown_raises(self, tmp_profiles_dir):
        manager = ProfileManager(profiles_dir=tmp_profiles_dir)
        with pytest.raises(ValueError, match="not found"):
            manager.get_profile_info("nonexistent")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
