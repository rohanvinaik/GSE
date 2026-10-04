"""Manual contract tests for gse.curation.external_sources.framenet."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.framenet import (
    FE_TO_PRIMITIVE,
    FRAME_TO_PRIMITIVE,
    FrameNetEntry,
    FrameNetParser,
    download_framenet,
)


def mk_entry(word="run", pos="v", frame_name="Self_motion", frame_id=1, core_fes=None, is_core=True):
    return FrameNetEntry(
        word=word, pos=pos, frame_name=frame_name, frame_id=frame_id,
        core_fes=core_fes or [], is_core_lu=is_core,
    )


# ---------- FrameNetEntry ----------

class TestFrameNetEntry:
    def test_construction(self):
        e = mk_entry(word="run", core_fes=["Self_mover"])
        assert e.word == "run"
        assert e.pos == "v"
        assert e.frame_name == "Self_motion"
        assert e.frame_id == 1
        assert e.core_fes == ["Self_mover"]
        assert e.is_core_lu is True


# ---------- FRAME_TO_PRIMITIVE ----------

class TestFrameToPrimitive:
    def test_motion(self):
        assert FRAME_TO_PRIMITIVE["Motion"] == {"MOVE": 1}

    def test_self_motion_body(self):
        assert FRAME_TO_PRIMITIVE["Self_motion"] == {"MOVE": 1, "BODY": 1, "DO": 1}

    def test_killing_negative_alive(self):
        assert FRAME_TO_PRIMITIVE["Killing"]["ALIVE"] == -1

    def test_commerce_sell_negative_have(self):
        assert FRAME_TO_PRIMITIVE["Commerce_sell"]["HAVE"] == -1

    def test_cognition(self):
        assert FRAME_TO_PRIMITIVE["Cognition"]["THINK"] == 1


# ---------- FE_TO_PRIMITIVE ----------

class TestFEToPrimitive:
    def test_agent(self):
        assert FE_TO_PRIMITIVE["Agent"] == {"SOMEONE": 1, "DO": 1}

    def test_experiencer(self):
        assert FE_TO_PRIMITIVE["Experiencer"] == {"SOMEONE": 1, "FEEL": 1}

    def test_self_mover(self):
        assert FE_TO_PRIMITIVE["Self_mover"] == {"SOMEONE": 1, "MOVE": 1, "DO": 1}

    def test_goal_toward(self):
        assert FE_TO_PRIMITIVE["Goal"]["TOWARD"] == 1


# ---------- __init__ ----------

class TestInit:
    def test_initial_state(self):
        p = FrameNetParser()
        assert p.entries == {}
        assert p._loaded is False
        assert p._frame_cache == {}

    def test_config_name_is_framenet(self):
        assert FrameNetParser().config.name == "framenet"


# ---------- load ----------

class TestLoad:
    @pytest.fixture(autouse=True)
    def _stub_corpus(self, monkeypatch):
        # The parser imports the corpus at call time. Replace NLTK's LazyCorpusLoader itself, so the
        # attribute patches below never trigger a real corpus load (which needs installed NLTK data:
        # missing, or a corrupt zip, made these unit tests fail before their mocks were in place).
        monkeypatch.setattr("nltk.corpus.framenet", MagicMock())

    def test_failure_returns_false(self):
        p = FrameNetParser()
        with patch("nltk.corpus.framenet.frames", side_effect=Exception("boom")):
            assert p.load() is False

    def test_successful_load(self):
        # Mock a frame
        mock_fe = MagicMock()
        mock_fe.name = "Self_mover"
        mock_fe.coreType = "Core"

        mock_lu = MagicMock()

        mock_frame = MagicMock()
        mock_frame.name = "Self_motion"
        mock_frame.ID = 42
        mock_frame.FE = {"sm": mock_fe}
        mock_frame.lexUnit = {"run.v": mock_lu}
        mock_frame.definition = "Motion frame description"

        with patch("nltk.corpus.framenet.frames", return_value=[mock_frame]):
            p = FrameNetParser()
            assert p.load() is True
            assert p._loaded is True
            assert "run" in p.entries
            assert p.entries["run"][0].frame_name == "Self_motion"
            assert p.entries["run"][0].pos == "v"
            assert p.entries["run"][0].core_fes == ["Self_mover"]

    def test_frame_cache_populated(self):
        mock_fe = MagicMock()
        mock_fe.name = "Agent"
        mock_fe.coreType = "Core"
        mock_frame = MagicMock()
        mock_frame.name = "Action"
        mock_frame.ID = 1
        mock_frame.FE = {"a": mock_fe}
        mock_frame.lexUnit = {}
        mock_frame.definition = "X" * 300  # > 200 chars, truncated

        with patch("nltk.corpus.framenet.frames", return_value=[mock_frame]):
            p = FrameNetParser()
            p.load()
            assert "Action" in p._frame_cache
            # Definition truncated to 200
            assert len(p._frame_cache["Action"]["definition"]) == 200

    def test_empty_definition_handled(self):
        mock_frame = MagicMock()
        mock_frame.name = "X"
        mock_frame.ID = 1
        mock_frame.FE = {}
        mock_frame.lexUnit = {}
        mock_frame.definition = ""  # falsy
        with patch("nltk.corpus.framenet.frames", return_value=[mock_frame]):
            p = FrameNetParser()
            p.load()
            assert p._frame_cache["X"]["definition"] == ""

    def test_non_core_fe_excluded(self):
        # FE without coreType="Core" → excluded from core_fes
        mock_fe = MagicMock()
        mock_fe.name = "Time"
        mock_fe.coreType = "Peripheral"
        mock_frame = MagicMock()
        mock_frame.name = "X"
        mock_frame.ID = 1
        mock_frame.FE = {"t": mock_fe}
        mock_frame.lexUnit = {"run.v": MagicMock()}
        mock_frame.definition = ""
        with patch("nltk.corpus.framenet.frames", return_value=[mock_frame]):
            p = FrameNetParser()
            p.load()
            assert "Time" not in p.entries["run"][0].core_fes

    def test_lu_name_without_pos_skipped(self):
        # LU name without dot → skipped
        mock_frame = MagicMock()
        mock_frame.name = "X"
        mock_frame.ID = 1
        mock_frame.FE = {}
        mock_frame.lexUnit = {"no_pos_separator": MagicMock()}
        mock_frame.definition = ""
        with patch("nltk.corpus.framenet.frames", return_value=[mock_frame]):
            p = FrameNetParser()
            p.load()
            assert "no_pos_separator" not in p.entries

    def test_underscore_replaced_with_space(self):
        mock_frame = MagicMock()
        mock_frame.name = "X"
        mock_frame.ID = 1
        mock_frame.FE = {}
        mock_frame.lexUnit = {"call_off.v": MagicMock()}
        mock_frame.definition = ""
        with patch("nltk.corpus.framenet.frames", return_value=[mock_frame]):
            p = FrameNetParser()
            p.load()
            assert "call off" in p.entries

    def test_word_lowercased(self):
        mock_frame = MagicMock()
        mock_frame.name = "X"
        mock_frame.ID = 1
        mock_frame.FE = {}
        mock_frame.lexUnit = {"Run.v": MagicMock()}
        mock_frame.definition = ""
        with patch("nltk.corpus.framenet.frames", return_value=[mock_frame]):
            p = FrameNetParser()
            p.load()
            assert "run" in p.entries


# ---------- to_primitives ----------

class TestToPrimitives:
    def test_unknown_returns_empty(self):
        p = FrameNetParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        assert p.to_primitives("nonexistent_xyz") == {}

    def test_frame_mapping(self):
        p = FrameNetParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        p.entries["run"] = [mk_entry(frame_name="Self_motion")]
        result = p.to_primitives("run")
        assert result["MOVE"] == 1
        assert result["BODY"] == 1
        assert result["DO"] == 1

    def test_fe_mapping(self):
        p = FrameNetParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        # Frame not in FRAME_TO_PRIMITIVE; FE is Agent
        p.entries["x"] = [mk_entry(word="x", frame_name="UnknownFrame", core_fes=["Agent"])]
        result = p.to_primitives("x")
        assert result["SOMEONE"] == 1
        assert result["DO"] == 1

    def test_frame_takes_priority_over_fe(self):
        # Frame Killing has ALIVE=-1; FE Patient has SOMETHING=1
        # The frame value should be inserted first
        p = FrameNetParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        p.entries["kill"] = [mk_entry(word="kill", frame_name="Killing", core_fes=["Patient"])]
        result = p.to_primitives("kill")
        assert result["ALIVE"] == -1
        assert result["CAUSE"] == 1
        # Patient still adds SOMETHING since not present
        assert result["SOMETHING"] == 1

    def test_unknown_frame_no_mapping(self):
        p = FrameNetParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        p.entries["x"] = [mk_entry(word="x", frame_name="UnknownFrame", core_fes=[])]
        assert p.to_primitives("x") == {}

    def test_first_value_wins(self):
        # Two entries: first sets MOVE=1, second wouldn't override
        p = FrameNetParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        # Frame Motion=MOVE:1, then Killing=ALIVE:-1
        p.entries["x"] = [
            mk_entry(word="x", frame_name="Motion"),
            mk_entry(word="x", frame_name="Killing"),
        ]
        result = p.to_primitives("x")
        assert result["MOVE"] == 1
        assert result["ALIVE"] == -1

    def test_case_insensitive(self):
        p = FrameNetParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        p.entries["run"] = [mk_entry(word="run", frame_name="Motion")]
        result = p.to_primitives("RUN")
        assert result["MOVE"] == 1

    def test_auto_loads(self):
        p = FrameNetParser()
        p.to_primitives.cache_clear()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.to_primitives("x")
            mock_load.assert_called_once()

    def test_unknown_fe_ignored(self):
        p = FrameNetParser()
        p._loaded = True
        p.to_primitives.cache_clear()
        p.entries["x"] = [mk_entry(word="x", frame_name="Motion", core_fes=["UnknownFE"])]
        result = p.to_primitives("x")
        # Frame still maps; FE ignored
        assert result == {"MOVE": 1}


# ---------- get_all_words ----------

class TestGetAllWords:
    def test_returns_keys(self):
        p = FrameNetParser()
        p._loaded = True
        p.entries = {"run": [], "walk": []}
        assert set(p.get_all_words()) == {"run", "walk"}

    def test_auto_loads(self):
        p = FrameNetParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_all_words()
            mock_load.assert_called_once()


# ---------- get_frames_for_word ----------

class TestGetFramesForWord:
    def test_returns_frames(self):
        p = FrameNetParser()
        p._loaded = True
        p.entries["run"] = [
            mk_entry(frame_name="Motion"),
            mk_entry(frame_name="Self_motion"),
        ]
        result = p.get_frames_for_word("run")
        assert set(result) == {"Motion", "Self_motion"}

    def test_dedup_via_set(self):
        p = FrameNetParser()
        p._loaded = True
        p.entries["run"] = [
            mk_entry(frame_name="Motion"),
            mk_entry(frame_name="Motion"),
        ]
        assert p.get_frames_for_word("run") == ["Motion"]

    def test_unknown_empty(self):
        p = FrameNetParser()
        p._loaded = True
        assert p.get_frames_for_word("xyz") == []

    def test_case_insensitive(self):
        p = FrameNetParser()
        p._loaded = True
        p.entries["run"] = [mk_entry(frame_name="Motion")]
        assert p.get_frames_for_word("RUN") == ["Motion"]

    def test_auto_loads(self):
        p = FrameNetParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_frames_for_word("x")
            mock_load.assert_called_once()


# ---------- get_frame_info ----------

class TestGetFrameInfo:
    def test_returns_cached(self):
        p = FrameNetParser()
        p._loaded = True
        p._frame_cache["X"] = {"id": 1, "core_fes": [], "definition": "test"}
        assert p.get_frame_info("X") == {"id": 1, "core_fes": [], "definition": "test"}

    def test_unknown_none(self):
        p = FrameNetParser()
        p._loaded = True
        assert p.get_frame_info("Unknown") is None

    def test_auto_loads(self):
        p = FrameNetParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_frame_info("X")
            mock_load.assert_called_once()


# ---------- download_framenet ----------

class TestDownloadFramenet:
    def test_calls_nltk_download(self, capsys):
        with patch("nltk.download") as mock_dl:
            download_framenet()
            mock_dl.assert_called_once_with("framenet_v17")

    def test_prints_success(self, capsys):
        with patch("nltk.download"):
            download_framenet()
            assert "successfully" in capsys.readouterr().out


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
