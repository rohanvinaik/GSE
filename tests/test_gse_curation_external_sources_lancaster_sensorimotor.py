"""Manual contract tests for gse.curation.external_sources.lancaster_sensorimotor."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.lancaster_sensorimotor import (
    DIMENSION_TO_PRIMITIVE,
    LancasterSensorimotorParser,
    SensorimotorEntry,
)


def mk_entry(word="x", aud=0, gus=0, hap=0, intero=0, olf=0, vis=0,
             foot=0, hand=0, head=0, mouth=0, torso=0):
    return SensorimotorEntry(
        word=word, auditory=aud, gustatory=gus, haptic=hap,
        interoceptive=intero, olfactory=olf, visual=vis,
        foot_leg=foot, hand_arm=hand, head=head, mouth=mouth, torso=torso,
    )


# ---------- SensorimotorEntry post_init ----------

class TestSensorimotorEntry:
    def test_max_perceptual(self):
        e = mk_entry(aud=2, vis=4, hap=3)
        assert e.max_perceptual == 4

    def test_dominant_perceptual(self):
        e = mk_entry(aud=2, vis=4, hap=3)
        assert e.dominant_perceptual == "visual"

    def test_max_action(self):
        e = mk_entry(foot=2, hand=4, head=1)
        assert e.max_action == 4

    def test_dominant_action(self):
        e = mk_entry(foot=2, hand=4, head=1)
        assert e.dominant_action == "hand_arm"

    def test_all_zero_dominants(self):
        e = mk_entry()
        # Empty/zero gives first key (auditory, foot_leg)
        assert e.dominant_perceptual in {"auditory", "gustatory", "haptic",
                                          "interoceptive", "olfactory", "visual"}
        assert e.dominant_action in {"foot_leg", "hand_arm", "head", "mouth", "torso"}


# ---------- DIMENSION_TO_PRIMITIVE ----------

class TestDimensionToPrimitive:
    def test_auditory_hear(self):
        assert DIMENSION_TO_PRIMITIVE["auditory"] == {"HEAR": 1}

    def test_visual_see(self):
        assert DIMENSION_TO_PRIMITIVE["visual"] == {"SEE": 1}

    def test_haptic_touch_body(self):
        assert DIMENSION_TO_PRIMITIVE["haptic"] == {"TOUCH": 1, "BODY": 1}

    def test_interoceptive_inside(self):
        assert DIMENSION_TO_PRIMITIVE["interoceptive"]["INSIDE"] == 1

    def test_mouth_say(self):
        assert DIMENSION_TO_PRIMITIVE["mouth"]["SAY"] == 1


# ---------- __init__ ----------

class TestInit:
    def test_default_path(self):
        p = LancasterSensorimotorParser()
        assert p.data_path.name == "lancaster_sensorimotor.csv"

    def test_custom_path(self, tmp_path):
        p = LancasterSensorimotorParser(data_path=str(tmp_path / "x.csv"))
        assert p.data_path == tmp_path / "x.csv"

    def test_initial_empty(self):
        assert LancasterSensorimotorParser().entries == {}
        assert LancasterSensorimotorParser()._loaded is False


# ---------- download ----------

class TestDownload:
    def test_success(self, tmp_path):
        p = LancasterSensorimotorParser(data_path=str(tmp_path / "ls.csv"))
        mock_resp = MagicMock()
        mock_resp.content = b"Word,Auditory.mean\n"
        with patch("requests.get", return_value=mock_resp):
            assert p.download() is True

    def test_failure(self, tmp_path):
        p = LancasterSensorimotorParser(data_path=str(tmp_path / "ls.csv"))
        with patch("requests.get", side_effect=Exception("network")):
            assert p.download() is False


# ---------- load ----------

class TestLoad:
    def test_missing_file_triggers_download(self, tmp_path):
        p = LancasterSensorimotorParser(data_path=str(tmp_path / "missing.csv"))
        with patch.object(p, "download", return_value=False) as mock_dl:
            assert p.load() is False
            mock_dl.assert_called_once()

    def test_basic_load(self, tmp_path):
        path = tmp_path / "ls.csv"
        path.write_text(
            "Word,Auditory.mean,Gustatory.mean,Haptic.mean,Interoceptive.mean,"
            "Olfactory.mean,Visual.mean,Foot_leg.mean,Hand_arm.mean,Head.mean,"
            "Mouth.mean,Torso.mean\n"
            "music,4.5,0,0,0,0,0,0,0,0,0,0\n"
        )
        p = LancasterSensorimotorParser(data_path=str(path))
        assert p.load() is True
        assert "music" in p.entries
        assert p.entries["music"].auditory == 4.5

    def test_empty_word_skipped(self, tmp_path):
        path = tmp_path / "ls.csv"
        path.write_text(
            "Word,Auditory.mean,Gustatory.mean,Haptic.mean,Interoceptive.mean,"
            "Olfactory.mean,Visual.mean,Foot_leg.mean,Hand_arm.mean,Head.mean,"
            "Mouth.mean,Torso.mean\n"
            ",4,0,0,0,0,0,0,0,0,0,0\n"
            "ok,3,0,0,0,0,0,0,0,0,0,0\n"
        )
        p = LancasterSensorimotorParser(data_path=str(path))
        p.load()
        assert "ok" in p.entries
        assert "" not in p.entries

    def test_empty_string_value_defaults_zero(self, tmp_path):
        path = tmp_path / "ls.csv"
        path.write_text(
            "Word,Auditory.mean,Gustatory.mean,Haptic.mean,Interoceptive.mean,"
            "Olfactory.mean,Visual.mean,Foot_leg.mean,Hand_arm.mean,Head.mean,"
            "Mouth.mean,Torso.mean\n"
            "x,,0,0,0,0,0,0,0,0,0,0\n"
        )
        p = LancasterSensorimotorParser(data_path=str(path))
        p.load()
        assert p.entries["x"].auditory == 0.0

    def test_invalid_float_skipped(self, tmp_path):
        path = tmp_path / "ls.csv"
        path.write_text(
            "Word,Auditory.mean,Gustatory.mean,Haptic.mean,Interoceptive.mean,"
            "Olfactory.mean,Visual.mean,Foot_leg.mean,Hand_arm.mean,Head.mean,"
            "Mouth.mean,Torso.mean\n"
            "bad,NOT_NUMERIC,0,0,0,0,0,0,0,0,0,0\n"
            "good,2,0,0,0,0,0,0,0,0,0,0\n"
        )
        p = LancasterSensorimotorParser(data_path=str(path))
        p.load()
        assert "good" in p.entries
        assert "bad" not in p.entries

    def test_lowercases_word(self, tmp_path):
        path = tmp_path / "ls.csv"
        path.write_text(
            "Word,Auditory.mean,Gustatory.mean,Haptic.mean,Interoceptive.mean,"
            "Olfactory.mean,Visual.mean,Foot_leg.mean,Hand_arm.mean,Head.mean,"
            "Mouth.mean,Torso.mean\n"
            "MUSIC,4,0,0,0,0,0,0,0,0,0,0\n"
        )
        p = LancasterSensorimotorParser(data_path=str(path))
        p.load()
        assert "music" in p.entries

    def test_exception_returns_false(self, tmp_path):
        path = tmp_path / "ls.csv"
        path.write_text("Word\nmusic\n")
        p = LancasterSensorimotorParser(data_path=str(path))
        with patch("builtins.open", side_effect=RuntimeError("boom")):
            assert p.load() is False


# ---------- get_sensorimotor ----------

class TestGetSensorimotor:
    def test_returns_entry(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries["dog"] = mk_entry(vis=4)
        assert p.get_sensorimotor("dog").visual == 4

    def test_unknown(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        assert p.get_sensorimotor("xyz") is None

    def test_case_insensitive(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries["dog"] = mk_entry()
        assert p.get_sensorimotor("DOG") is not None

    def test_auto_loads(self):
        p = LancasterSensorimotorParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_sensorimotor("x")
            mock_load.assert_called_once()


# ---------- to_primitives ----------

class TestToPrimitives:
    def _make(self, **kw):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries["x"] = mk_entry(**kw)
        return p

    def test_unknown_empty(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        assert p.to_primitives("nonexistent") == {}

    def test_high_auditory_hear(self):
        # auditory=4 ≥ 3.0 → HEAR=1
        # max also 4 ≥ 1.5 → no abstract
        assert self._make(aud=4).to_primitives("x")["HEAR"] == 1

    def test_high_visual_see(self):
        assert self._make(vis=4).to_primitives("x")["SEE"] == 1

    def test_high_haptic_touch_body(self):
        result = self._make(hap=4).to_primitives("x")
        assert result["TOUCH"] == 1
        assert result["BODY"] == 1

    def test_gustatory_lower_threshold(self):
        # gustatory ≥ 2.5 (high_threshold - 0.5) → BODY, FEEL
        result = self._make(gus=3, vis=4).to_primitives("x")
        assert result["BODY"] == 1
        assert result["FEEL"] == 1

    def test_olfactory_body(self):
        # olfactory ≥ 2.5 → BODY
        result = self._make(olf=3, vis=4).to_primitives("x")
        assert result["BODY"] == 1

    def test_interoceptive_inside(self):
        # interoceptive ≥ 2.5 → BODY, FEEL, INSIDE
        result = self._make(intero=3, vis=4).to_primitives("x")
        assert result["INSIDE"] == 1

    def test_high_foot_leg_move(self):
        # foot_leg ≥ 3.0 → MOVE
        result = self._make(foot=4).to_primitives("x")
        assert result["MOVE"] == 1
        assert result["BODY"] == 1
        assert result["DO"] == 1

    def test_high_hand_arm_touch(self):
        result = self._make(hand=4).to_primitives("x")
        assert result["TOUCH"] == 1

    def test_high_mouth_say(self):
        result = self._make(mouth=4).to_primitives("x")
        assert result["SAY"] == 1

    def test_low_scores_abstract(self):
        # All < 1.5 → THINK + SOMETHING=-1
        result = self._make(vis=1).to_primitives("x")
        assert result["THINK"] == 1
        assert result["SOMETHING"] == -1

    def test_at_high_threshold_inclusive(self):
        # >= 3.0 means 3.0 triggers
        assert self._make(aud=3).to_primitives("x")["HEAR"] == 1

    def test_just_below_threshold(self):
        # 2.99 < 3.0 → no HEAR, but also max < 1.5 might not be... 2.99 is above 1.5
        result = self._make(aud=2.99).to_primitives("x")
        # HEAR not triggered
        assert "HEAR" not in result
        # max action 0, max perceptual 2.99 → not abstract either
        assert "THINK" not in result

    def test_custom_high_threshold(self):
        # Raise threshold to 4.5; aud=4 doesn't trigger
        assert "HEAR" not in self._make(aud=4).to_primitives("x", high_threshold=4.5)

    def test_custom_abstract_threshold(self):
        # Raise to 3.0; max 2 < 3.0 → abstract
        result = self._make(vis=2).to_primitives("x", abstract_threshold=3.0)
        assert result["THINK"] == 1

    def test_action_score_threshold(self):
        # All actions below 3.0; perceptual high
        result = self._make(vis=4, foot=2, hand=2).to_primitives("x")
        assert "DO" not in result
        # SEE present from visual
        assert "SEE" in result

    # Boundary tests for every threshold in to_primitives
    def test_visual_just_below_3(self):
        # vis=2.99 → no SEE
        result = self._make(vis=2.99).to_primitives("x")
        assert "SEE" not in result

    def test_haptic_just_below_3(self):
        result = self._make(hap=2.99).to_primitives("x")
        assert "TOUCH" not in result

    def test_gustatory_just_below_2_5(self):
        # gus=2.49 → no FEEL/BODY contribution from gustatory
        # vis high to avoid abstract branch
        result = self._make(gus=2.49, vis=4).to_primitives("x")
        # gustatory branch not triggered. Note BODY might come from vis branch though.
        # vis=4 doesn't trigger BODY itself. So no BODY from this.
        # haptic, gustatory, olfactory, interoceptive all 0 → no BODY/FEEL contributions
        # Action max 0 → no DO
        # max = 4 (perceptual) → not abstract
        assert "FEEL" not in result

    def test_gustatory_at_2_5(self):
        # gus=2.5 → ≥ 2.5 → BODY, FEEL
        result = self._make(gus=2.5, vis=4).to_primitives("x")
        assert result["BODY"] == 1
        assert result["FEEL"] == 1

    def test_olfactory_at_2_5(self):
        result = self._make(olf=2.5, vis=4).to_primitives("x")
        assert result["BODY"] == 1

    def test_olfactory_just_below(self):
        result = self._make(olf=2.49, vis=4).to_primitives("x")
        # No BODY from olfactory specifically. BUT vis doesn't add BODY.
        # So BODY should be absent.
        assert "BODY" not in result

    def test_interoceptive_at_2_5(self):
        result = self._make(intero=2.5, vis=4).to_primitives("x")
        assert result["INSIDE"] == 1

    def test_interoceptive_just_below(self):
        result = self._make(intero=2.49, vis=4).to_primitives("x")
        assert "INSIDE" not in result

    def test_foot_at_3(self):
        # foot=3 → action_score=3 ≥ 3, AND foot_leg≥3 → MOVE
        result = self._make(foot=3).to_primitives("x")
        assert result["MOVE"] == 1

    def test_foot_just_below(self):
        result = self._make(foot=2.99).to_primitives("x")
        assert "MOVE" not in result
        # action max 2.99 not ≥ 3 → no DO either
        assert "DO" not in result

    def test_hand_at_3(self):
        result = self._make(hand=3).to_primitives("x")
        assert result["TOUCH"] == 1

    def test_hand_just_below(self):
        # Action score from hand=2.99 → action_score=2.99 < 3 → DO not triggered
        result = self._make(hand=2.99).to_primitives("x")
        assert "TOUCH" not in result

    def test_mouth_at_3(self):
        result = self._make(mouth=3).to_primitives("x")
        assert result["SAY"] == 1

    def test_mouth_just_below(self):
        result = self._make(mouth=2.99).to_primitives("x")
        assert "SAY" not in result

    def test_abstract_at_1_5(self):
        # 1.5 NOT < 1.5 → no THINK
        result = self._make(vis=1.5).to_primitives("x")
        assert "THINK" not in result

    def test_abstract_just_below_1_5(self):
        # 1.49 < 1.5 → THINK
        result = self._make(vis=1.49).to_primitives("x")
        assert result["THINK"] == 1
        assert result["SOMETHING"] == -1

    def test_aud_at_threshold_inclusive(self):
        # aud=3.0 inclusive triggers HEAR
        assert self._make(aud=3.0).to_primitives("x")["HEAR"] == 1

    def test_aud_just_below(self):
        assert "HEAR" not in self._make(aud=2.99).to_primitives("x")


# ---------- get_all_words ----------

class TestGetAllWords:
    def test_returns_keys(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"a": mk_entry(), "b": mk_entry()}
        assert set(p.get_all_words()) == {"a", "b"}

    def test_auto_loads(self):
        p = LancasterSensorimotorParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_all_words()
            mock_load.assert_called_once()


# ---------- get_new_words ----------

class TestGetNewWords:
    def test_filters(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"a": mk_entry(), "b": mk_entry()}
        assert set(p.get_new_words({"a"})) == {"b"}

    def test_auto_loads(self):
        p = LancasterSensorimotorParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_new_words(set())
            mock_load.assert_called_once()


# ---------- get_highly_embodied_words ----------

class TestGetHighlyEmbodiedWords:
    def test_high_action(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"run": mk_entry(foot=4.5)}
        assert "run" in p.get_highly_embodied_words()

    def test_high_haptic(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"x": mk_entry(hap=4.5)}
        assert "x" in p.get_highly_embodied_words()

    def test_high_interoceptive(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"pain": mk_entry(intero=4.5)}
        assert "pain" in p.get_highly_embodied_words()

    def test_action_at_4(self):
        # ≥ 4.0 inclusive
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"x": mk_entry(foot=4.0)}
        assert "x" in p.get_highly_embodied_words()

    def test_action_just_below_4(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"x": mk_entry(foot=3.99)}
        assert p.get_highly_embodied_words() == []

    def test_haptic_at_4(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"x": mk_entry(hap=4.0)}
        assert "x" in p.get_highly_embodied_words()

    def test_haptic_just_below_4(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"x": mk_entry(hap=3.99)}
        assert p.get_highly_embodied_words() == []

    def test_interoceptive_at_4(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"x": mk_entry(intero=4.0)}
        assert "x" in p.get_highly_embodied_words()

    def test_interoceptive_just_below_4(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"x": mk_entry(intero=3.99)}
        assert p.get_highly_embodied_words() == []

    def test_none_qualify(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"x": mk_entry(vis=2)}
        assert p.get_highly_embodied_words() == []

    def test_custom_threshold(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"x": mk_entry(foot=3)}
        assert "x" in p.get_highly_embodied_words(threshold=2.5)


# ---------- get_perceptual_words ----------

class TestGetPerceptualWords:
    def test_visual_high(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"red": mk_entry(vis=4.5), "music": mk_entry(aud=4.5)}
        assert p.get_perceptual_words("visual") == ["red"]

    def test_at_threshold_inclusive(self):
        # ≥ 4.0 inclusive
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"x": mk_entry(vis=4.0)}
        assert "x" in p.get_perceptual_words("visual")

    def test_just_below_threshold(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"x": mk_entry(vis=3.99)}
        assert p.get_perceptual_words("visual") == []

    def test_default_threshold_is_4(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"at_4": mk_entry(vis=4), "below_4": mk_entry(vis=3.99)}
        # Default threshold should treat 4 as included
        result = p.get_perceptual_words("visual")
        assert "at_4" in result
        assert "below_4" not in result

    def test_lowercases_modality(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"red": mk_entry(vis=4.5)}
        assert "red" in p.get_perceptual_words("VISUAL")

    def test_unknown_modality_empty(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"x": mk_entry(vis=4.5)}
        # Unknown attr → getattr returns 0 → never above threshold
        assert p.get_perceptual_words("unknown_modality") == []

    def test_custom_threshold(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"x": mk_entry(vis=3)}
        assert "x" in p.get_perceptual_words("visual", threshold=2.5)


# ---------- get_statistics ----------

class TestGetStatistics:
    def test_empty(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        assert p.get_statistics() == {}

    def test_basic(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {
            "a": mk_entry(aud=2, vis=4),
            "b": mk_entry(aud=4, vis=2),
        }
        stats = p.get_statistics()
        assert stats["total_words"] == 2
        assert stats["averages"]["auditory"] == 3.0
        assert stats["averages"]["visual"] == 3.0

    def test_highly_visual_count(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {
            "red": mk_entry(vis=4.5),
            "x": mk_entry(vis=2),
        }
        stats = p.get_statistics()
        assert stats["highly_visual"] == 1

    def test_highly_auditory_count(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"loud": mk_entry(aud=4.5)}
        stats = p.get_statistics()
        assert stats["highly_auditory"] == 1

    def test_highly_embodied_count(self):
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"run": mk_entry(foot=4.5)}
        stats = p.get_statistics()
        assert stats["highly_embodied"] == 1

    def test_averages_all_dimensions_present(self):
        # Pin every dimension key in the averages dict (11 keys)
        p = LancasterSensorimotorParser()
        p._loaded = True
        p.entries = {"x": mk_entry(aud=1, gus=2, hap=3, intero=4, olf=5, vis=1,
                                   foot=2, hand=3, head=4, mouth=5, torso=1)}
        avgs = p.get_statistics()["averages"]
        assert avgs["auditory"] == 1.0
        assert avgs["gustatory"] == 2.0
        assert avgs["haptic"] == 3.0
        assert avgs["interoceptive"] == 4.0
        assert avgs["olfactory"] == 5.0
        assert avgs["visual"] == 1.0
        assert avgs["foot_leg"] == 2.0
        assert avgs["hand_arm"] == 3.0
        assert avgs["head"] == 4.0
        assert avgs["mouth"] == 5.0
        assert avgs["torso"] == 1.0
        assert set(avgs.keys()) == {"auditory", "gustatory", "haptic",
                                     "interoceptive", "olfactory", "visual",
                                     "foot_leg", "hand_arm", "head", "mouth",
                                     "torso"}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
