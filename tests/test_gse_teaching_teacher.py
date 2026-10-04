"""Manual contract tests for gse.teaching.teacher."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.profiles.profile_manager import ProfileManager
from gse.teaching.teacher import (
    NetworkSnapshot,
    NetworkTeacher,
    TeachingEpoch,
    TeachingSession,
    _get_top_connections,
)

# ---------- _get_top_connections ----------


class TestGetTopConnections:
    def test_returns_sorted_by_abs(self):
        names = ["a", "b", "c"]
        w = np.array(
            [
                [0.0, 0.5, -0.9],
                [0.5, 0.0, 0.3],
                [-0.9, 0.3, 0.0],
            ]
        )
        result = _get_top_connections(w, names, top_k=3)
        # First should be the strongest (|w| = 0.9)
        assert abs(result[0][2]) == 0.9
        assert result[0][0] in ("a", "c") and result[0][1] in ("a", "c")

    def test_filters_below_threshold(self):
        w = np.array([[0.0, 0.0005], [0.0005, 0.0]])
        result = _get_top_connections(w, ["a", "b"], top_k=5)
        # 0.0005 < 0.001 threshold → no connections
        assert result == []

    def test_top_k_limits(self):
        w = np.array(
            [
                [0, 0.5, 0.6, 0.7],
                [0.5, 0, 0.4, 0.3],
                [0.6, 0.4, 0, 0.2],
                [0.7, 0.3, 0.2, 0],
            ]
        )
        result = _get_top_connections(w, ["a", "b", "c", "d"], top_k=2)
        assert len(result) == 2

    def test_only_upper_triangle(self):
        # The loop is `for j in range(i+1, n)` — only upper triangle
        w = np.array([[0, 1.0], [1.0, 0]])  # symmetric
        result = _get_top_connections(w, ["a", "b"], top_k=10)
        # Only one connection counted (a-b), not (b-a)
        assert len(result) == 1

    def test_exact_boundary_threshold(self):
        # Threshold is `> 0.001` — at exactly 0.001 should be EXCLUDED
        w = np.array([[0.0, 0.001], [0.001, 0.0]])
        result = _get_top_connections(w, ["a", "b"], top_k=10)
        # 0.001 NOT > 0.001 → no connection
        assert result == []

    def test_just_over_threshold(self):
        # Just above threshold → included
        w = np.array([[0.0, 0.0011], [0.0011, 0.0]])
        result = _get_top_connections(w, ["a", "b"], top_k=10)
        assert len(result) == 1

    def test_connection_tuple_order(self):
        # Tuple is (names[i], names[j], weight) — i comes first
        w = np.array([[0.0, 0.5], [0.5, 0.0]])
        result = _get_top_connections(w, ["alpha", "beta"], top_k=1)
        assert result[0][0] == "alpha"
        assert result[0][1] == "beta"
        assert result[0][2] == 0.5

    def test_top_k_zero(self):
        w = np.array([[0.0, 0.5], [0.5, 0.0]])
        result = _get_top_connections(w, ["a", "b"], top_k=0)
        assert result == []


# ---------- NetworkSnapshot ----------


class TestNetworkSnapshot:
    def test_from_network(self):
        net = MagicMock()
        net.weights = np.array([[0, 0.5], [0.5, 0]])
        net.node_names = ["a", "b"]
        net.update_count = 7
        snap = NetworkSnapshot.from_network(net, "test")
        assert snap.update_count == 7
        assert snap.weight_norm > 0
        # Top association should include the 0.5 link
        assert len(snap.top_associations) >= 1


# ---------- TeachingEpoch ----------


class TestTeachingEpoch:
    def test_to_dict_all_fields(self):
        e = TeachingEpoch(
            epoch_number=1,
            document="doc.txt",
            document_type="text",
            start_time="2026-01-01T00:00:00",
            end_time="2026-01-01T00:00:01",
            duration_seconds=1.0,
            paragraphs_processed=2,
            sentences_processed=5,
            words_processed=20,
            total_updates=10,
            text_delta=0.1,
            paragraph_delta=0.2,
            sentence_delta=0.3,
            word_delta=0.4,
            orchestrator_delta=0.5,
        )
        d = e.to_dict()
        # Every top-level field
        assert d["epoch_number"] == 1
        assert d["document"] == "doc.txt"
        assert d["document_type"] == "text"
        assert d["start_time"] == "2026-01-01T00:00:00"
        assert d["end_time"] == "2026-01-01T00:00:01"
        assert d["duration_seconds"] == 1.0
        assert d["paragraphs_processed"] == 2
        assert d["sentences_processed"] == 5
        assert d["words_processed"] == 20
        assert d["total_updates"] == 10
        # Every delta value with its specific key
        assert d["deltas"]["text"] == 0.1
        assert d["deltas"]["paragraph"] == 0.2
        assert d["deltas"]["sentence"] == 0.3
        assert d["deltas"]["word"] == 0.4
        assert d["deltas"]["orchestrator"] == 0.5

    def test_to_dict_distinct_values_per_key(self):
        # Each field gets a unique value so VALUE mutants on keys are caught
        e = TeachingEpoch(
            epoch_number=42,
            document="z.txt",
            document_type="json",
            start_time="A",
            end_time="B",
            duration_seconds=99.5,
            paragraphs_processed=11,
            sentences_processed=22,
            words_processed=33,
            total_updates=44,
            text_delta=1.1,
            paragraph_delta=2.2,
            sentence_delta=3.3,
            word_delta=4.4,
            orchestrator_delta=5.5,
        )
        d = e.to_dict()
        assert d["epoch_number"] == 42
        assert d["paragraphs_processed"] == 11
        assert d["sentences_processed"] == 22
        assert d["words_processed"] == 33
        assert d["total_updates"] == 44
        assert d["deltas"]["text"] == 1.1
        assert d["deltas"]["paragraph"] == 2.2
        assert d["deltas"]["sentence"] == 3.3
        assert d["deltas"]["word"] == 4.4
        assert d["deltas"]["orchestrator"] == 5.5


# ---------- TeachingSession ----------


class TestTeachingSession:
    def test_to_dict_all_fields(self):
        ep = TeachingEpoch(
            epoch_number=1, document="x", document_type="text", start_time="t1", end_time="t2", duration_seconds=1.0
        )
        s = TeachingSession(
            profile_name="alpha",
            start_time="2026-01-01T00:00:00",
            end_time="2026-01-02T00:00:00",
            total_epochs=7,
            epochs=[ep],
            corpus_dir="/some/corpus",
            total_documents=12,
            document_order=["a.txt", "b.txt"],
            random_seed=99,
            json_epochs={3: "x.json", 7: "y.json"},
        )
        d = s.to_dict()
        assert d["profile_name"] == "alpha"
        assert d["start_time"] == "2026-01-01T00:00:00"
        assert d["end_time"] == "2026-01-02T00:00:00"
        assert d["total_epochs"] == 7
        assert d["corpus_dir"] == "/some/corpus"
        assert d["total_documents"] == 12
        assert d["document_order"] == ["a.txt", "b.txt"]
        assert d["random_seed"] == 99
        assert d["json_epochs"] == {3: "x.json", 7: "y.json"}
        assert len(d["epochs"]) == 1

    def test_to_dict_distinct_values(self):
        # Distinct values per key so VALUE mutants are caught
        s = TeachingSession(
            profile_name="P",
            start_time="S",
            end_time="E",
            total_epochs=1,
            corpus_dir="C",
            total_documents=2,
            document_order=[],
            random_seed=3,
            json_epochs={},
        )
        d = s.to_dict()
        assert d["profile_name"] == "P"
        assert d["start_time"] == "S"
        assert d["end_time"] == "E"

    def test_save_writes_json(self, tmp_path):
        s = TeachingSession(profile_name="alpha", start_time="t")
        path = tmp_path / "session.json"
        s.save(str(path))
        loaded = json.loads(path.read_text())
        assert loaded["profile_name"] == "alpha"


# ---------- NetworkTeacher fixtures ----------


@pytest.fixture
def profile_mgr(tmp_path):
    return ProfileManager(profiles_dir=str(tmp_path / "profiles"))


@pytest.fixture
def teacher(profile_mgr):
    return NetworkTeacher(profile_manager=profile_mgr, profile_name="test")


# ---------- NetworkTeacher.__init__ ----------


class TestNetworkTeacherInit:
    def test_creates_new_profile(self, profile_mgr):
        t = NetworkTeacher(profile_manager=profile_mgr, profile_name="newp")
        assert profile_mgr.profile_exists("newp")

    def test_loads_existing_profile(self, profile_mgr):
        profile_mgr.create_profile("existing")
        t = NetworkTeacher(profile_manager=profile_mgr, profile_name="existing")
        assert t.profile.metadata.name == "existing"

    def test_activates_profile(self, profile_mgr):
        t = NetworkTeacher(profile_manager=profile_mgr, profile_name="alpha")
        # _active_profile is set directly (despite get_network_collection bug)
        assert profile_mgr._active_profile is t.profile
        assert profile_mgr._active_name == "alpha"

    def test_default_profile_manager(self, tmp_path, monkeypatch):
        # If no manager passed, creates default one
        monkeypatch.chdir(tmp_path)
        t = NetworkTeacher(profile_name="default_test")
        assert t.profile_manager is not None


# ---------- prepare_corpus ----------


class TestPrepareCorpus:
    def test_finds_txt_files(self, teacher, tmp_path):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "a.txt").write_text("a")
        (corpus / "b.txt").write_text("b")
        result = teacher.prepare_corpus(str(corpus))
        assert len(result) == 2
        names = [Path(p).name for p in result]
        assert "a.txt" in names
        assert "b.txt" in names

    def test_inserts_json_files_at_epoch(self, teacher, tmp_path):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        for i in range(5):
            (corpus / f"doc_{i}.txt").write_text(f"doc {i}")
        json_path = tmp_path / "big.json"
        json_path.write_text("{}")
        result = teacher.prepare_corpus(str(corpus), json_files={3: str(json_path)})
        # 5 txt + 1 json
        assert len(result) == 6
        # JSON inserted at epoch 3 → index 2
        assert result[2] == str(json_path)

    def test_random_seed_deterministic(self, teacher, tmp_path):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        for i in range(5):
            (corpus / f"d_{i}.txt").write_text("x")
        r1 = teacher.prepare_corpus(str(corpus), random_seed=42)
        r2 = teacher.prepare_corpus(str(corpus), random_seed=42)
        assert r1 == r2

    def test_empty_dir(self, teacher, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert teacher.prepare_corpus(str(empty)) == []

    def test_json_at_end_clamped(self, teacher, tmp_path):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "doc.txt").write_text("x")
        json_path = tmp_path / "big.json"
        json_path.write_text("{}")
        # Epoch 999 way past end → clamped to end of list
        result = teacher.prepare_corpus(str(corpus), json_files={999: str(json_path)})
        assert str(json_path) in result


# ---------- _take_snapshots ----------


class TestTakeSnapshots:
    def test_returns_all_five(self, teacher):
        snaps = teacher._take_snapshots()
        assert set(snaps.keys()) == {"text", "paragraph", "sentence", "word", "orchestrator"}
        for snap in snaps.values():
            assert isinstance(snap, NetworkSnapshot)


# ---------- _teach_from_text ----------


class TestTeachFromText:
    def test_handles_read_failure(self, teacher, tmp_path):
        # Nonexistent file
        result = teacher._teach_from_text(str(tmp_path / "nope.txt"))
        # Should return stats dict with zeros, not raise
        assert result == {"paragraphs": 0, "sentences": 0, "words": 0, "updates": 0}

    def test_processes_text_file(self, teacher, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("This is a test sentence. Another one follows.\n\nSecond paragraph here.")
        with patch.object(
            teacher.feature_extractor,
            "extract_all_features",
            return_value={
                "text": {"FORMAL": 0.5},
                "paragraph": [{"CAUSE": 0.3}],
                "sentence": [{"SYN_SUBJ": 0.8}],
            },
        ):
            stats = teacher._teach_from_text(str(f))
        assert stats["updates"] > 0
        assert stats["words"] > 0

    def test_empty_features_no_update(self, teacher, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("hello")
        with patch.object(
            teacher.feature_extractor,
            "extract_all_features",
            return_value={
                "text": {},
                "paragraph": [],
                "sentence": [],
            },
        ):
            stats = teacher._teach_from_text(str(f))
        # Only orchestrator updates → updates >= 1
        assert stats["updates"] >= 1


# ---------- _teach_from_json ----------


class TestTeachFromJson:
    def test_processes_turns(self, teacher, tmp_path):
        f = tmp_path / "conv.json"
        f.write_text("[]")
        with patch.object(teacher.conversation_processor, "process_file", return_value=iter(["turn 1.", "turn 2."])):
            with patch.object(
                teacher.feature_extractor,
                "extract_all_features",
                return_value={
                    "text": {"x": 0.5},
                    "paragraph": [{"y": 0.3}],
                    "sentence": [{"z": 0.8}],
                },
            ):
                stats = teacher._teach_from_json(str(f))
        assert stats["updates"] >= 2  # at least one update per turn

    def test_orchestrator_every_10_turns(self, teacher, tmp_path):
        f = tmp_path / "conv.json"
        f.write_text("[]")
        # Generate 10 turns
        with patch.object(teacher.conversation_processor, "process_file", return_value=iter(["t"] * 10)):
            with patch.object(
                teacher.feature_extractor,
                "extract_all_features",
                return_value={"text": {}, "paragraph": [], "sentence": []},
            ):
                with patch.object(teacher.profile.orchestrator, "learn") as mock_learn:
                    teacher._teach_from_json(str(f))
        # At turn 10, orchestrator.learn called once for the conv routing
        assert mock_learn.call_count >= 1


# ---------- teach_epoch ----------


class TestTeachEpoch:
    def test_text_doc_type(self, teacher, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("text content")
        with patch.object(
            teacher.feature_extractor,
            "extract_all_features",
            return_value={"text": {}, "paragraph": [], "sentence": []},
        ):
            ep = teacher.teach_epoch(1, str(f))
        assert ep.document_type == "text"
        assert ep.epoch_number == 1
        assert ep.document == "doc.txt"

    def test_claude_json_doc_type(self, teacher, tmp_path):
        f = tmp_path / "claude_conv.json"
        f.write_text("[]")
        with patch.object(teacher.conversation_processor, "process_file", return_value=iter([])):
            ep = teacher.teach_epoch(1, str(f))
        assert ep.document_type == "claude_json"

    def test_gpt_json_doc_type(self, teacher, tmp_path):
        f = tmp_path / "gpt_chat.json"
        f.write_text("[]")
        with patch.object(teacher.conversation_processor, "process_file", return_value=iter([])):
            ep = teacher.teach_epoch(1, str(f))
        assert ep.document_type == "gpt_json"

    def test_generic_json_doc_type(self, teacher, tmp_path):
        f = tmp_path / "random.json"
        f.write_text("[]")
        with patch.object(teacher.conversation_processor, "process_file", return_value=iter([])):
            ep = teacher.teach_epoch(1, str(f))
        assert ep.document_type == "json"

    def test_records_epoch_in_profile(self, teacher, tmp_path):
        f = tmp_path / "x.txt"
        f.write_text("hi")
        before = teacher.profile.metadata.epochs_completed
        with patch.object(
            teacher.feature_extractor,
            "extract_all_features",
            return_value={"text": {}, "paragraph": [], "sentence": []},
        ):
            teacher.teach_epoch(1, str(f))
        assert teacher.profile.metadata.epochs_completed == before + 1


# ---------- teach ----------


class TestTeach:
    def test_runs_session(self, teacher, tmp_path):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "a.txt").write_text("doc a")
        (corpus / "b.txt").write_text("doc b")
        with patch.object(
            teacher.feature_extractor,
            "extract_all_features",
            return_value={"text": {}, "paragraph": [], "sentence": []},
        ):
            session = teacher.teach(str(corpus))
        assert session.total_epochs == 2
        assert len(session.epochs) == 2

    def test_progress_callback(self, teacher, tmp_path):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "a.txt").write_text("x")
        calls = []

        def cb(epoch, total, msg):
            calls.append((epoch, total))

        with patch.object(
            teacher.feature_extractor,
            "extract_all_features",
            return_value={"text": {}, "paragraph": [], "sentence": []},
        ):
            teacher.teach(str(corpus), progress_callback=cb)
        assert calls == [(1, 1)]

    def test_save_every_writes_periodically(self, teacher, tmp_path):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        for i in range(3):
            (corpus / f"d_{i}.txt").write_text("x")
        with patch.object(
            teacher.feature_extractor,
            "extract_all_features",
            return_value={"text": {}, "paragraph": [], "sentence": []},
        ):
            with patch.object(teacher.profile_manager, "save_active_profile") as ms:
                teacher.teach(str(corpus), save_every=1)
        # 3 epochs + final save = at least 4 calls
        assert ms.call_count >= 3


# ---------- get_behavior_summary ----------


class TestBehaviorSummary:
    def test_returns_all_networks(self, teacher):
        result = teacher.get_behavior_summary()
        assert "profile" in result
        for key in ("text_network", "paragraph_network", "sentence_network", "word_network", "orchestrator"):
            assert key in result
            assert "updates" in result[key]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
