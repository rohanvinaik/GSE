"""Manual contract tests for gse.curation.external_sources.integrator."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.integrator import (
    ExternalSourcesIntegrator,
    ExternalWordData,
    download_all_sources,
)

# ---------- ExternalWordData ----------

class TestExternalWordData:
    def test_defaults(self):
        e = ExternalWordData(word="x")
        assert e.word == "x"
        assert e.pos is None
        assert e.sources == []
        assert e.primitives == {}
        assert e.confidence_scores == {}
        assert e.metadata == {}


# ---------- __init__ ----------

class TestInit:
    def test_no_db(self):
        i = ExternalSourcesIntegrator()
        assert i.lexicon_db is None
        assert i.parsers == {}
        assert i.word_data == {}
        assert i._loaded is False

    def test_with_db_path(self, tmp_path):
        with patch("gse.curation.external_sources.integrator.LexiconDatabase") as MockDB:
            i = ExternalSourcesIntegrator(lexicon_db_path=str(tmp_path / "x.db"))
            MockDB.assert_called_once_with(str(tmp_path / "x.db"))
            assert i.lexicon_db is not None


# ---------- load_all_sources ----------

class TestLoadAllSources:
    # every parser load_all_sources registers — kept in sync with integrator.py
    _ALL_PARSERS = [
        "gse.curation.external_sources.sentiwordnet.SentiWordNetParser",
        "gse.curation.external_sources.nrc_emotion.NRCEmotionParser",
        "gse.curation.external_sources.nrc_vad.NRCVADParser",
        "gse.curation.external_sources.verbnet.VerbNetParser",
        "gse.curation.external_sources.concreteness.ConcretenessParser",
        "gse.curation.external_sources.lancaster_sensorimotor.LancasterSensorimotorParser",
        "gse.curation.external_sources.wordnet_hierarchy.WordNetHierarchyParser",
        "gse.curation.external_sources.framenet.FrameNetParser",
        "gse.curation.external_sources.propbank.PropBankParser",
        "gse.curation.external_sources.conceptnet.ConceptNetParser",
        "gse.curation.external_sources.usas.USASParser",
    ]

    def test_all_unavailable(self):
        from contextlib import ExitStack

        i = ExternalSourcesIntegrator()
        with ExitStack() as stack:
            for target in self._ALL_PARSERS:
                stack.enter_context(patch(target, side_effect=ImportError))
            stats = i.load_all_sources()
        assert stats == {}
        assert i._loaded is True

    def test_loads_one_source(self):
        i = ExternalSourcesIntegrator()
        mp = MagicMock()
        mp.load.return_value = True
        mp.entries = {"a": [], "b": []}
        with patch("gse.curation.external_sources.sentiwordnet.SentiWordNetParser",
                   return_value=mp):
            with patch("gse.curation.external_sources.nrc_emotion.NRCEmotionParser",
                       side_effect=ImportError):
                with patch("gse.curation.external_sources.nrc_vad.NRCVADParser",
                           side_effect=ImportError):
                    with patch("gse.curation.external_sources.verbnet.VerbNetParser",
                               side_effect=ImportError):
                        with patch("gse.curation.external_sources.concreteness.ConcretenessParser",
                                   side_effect=ImportError):
                            with patch("gse.curation.external_sources.lancaster_sensorimotor.LancasterSensorimotorParser",
                                       side_effect=ImportError):
                                stats = i.load_all_sources()
        assert stats["sentiwordnet"] == 2
        assert "sentiwordnet" in i.parsers

    def test_load_returning_false_excluded(self):
        i = ExternalSourcesIntegrator()
        mp = MagicMock()
        mp.load.return_value = False
        with patch("gse.curation.external_sources.sentiwordnet.SentiWordNetParser",
                   return_value=mp):
            with patch("gse.curation.external_sources.nrc_emotion.NRCEmotionParser",
                       side_effect=ImportError):
                with patch("gse.curation.external_sources.nrc_vad.NRCVADParser",
                           side_effect=ImportError):
                    with patch("gse.curation.external_sources.verbnet.VerbNetParser",
                               side_effect=ImportError):
                        with patch("gse.curation.external_sources.concreteness.ConcretenessParser",
                                   side_effect=ImportError):
                            with patch("gse.curation.external_sources.lancaster_sensorimotor.LancasterSensorimotorParser",
                                       side_effect=ImportError):
                                stats = i.load_all_sources()
        assert "sentiwordnet" not in stats


# ---------- get_all_words ----------

class TestGetAllWords:
    def test_union_from_parsers(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        p1 = MagicMock()
        p1.get_all_words.return_value = ["a", "b"]
        p2 = MagicMock()
        p2.get_all_words.return_value = ["b", "c"]
        i.parsers = {"s1": p1, "s2": p2}
        assert i.get_all_words() == {"a", "b", "c"}

    def test_empty(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        assert i.get_all_words() == set()

    def test_auto_loads(self):
        i = ExternalSourcesIntegrator()
        with patch.object(i, "load_all_sources") as mock_load:
            mock_load.side_effect = lambda: setattr(i, "_loaded", True)
            i.get_all_words()
            mock_load.assert_called_once()


# ---------- get_existing_words ----------

class TestGetExistingWords:
    def test_no_db_empty(self):
        i = ExternalSourcesIntegrator()
        assert i.get_existing_words() == set()

    def test_lowercases_results(self):
        i = ExternalSourcesIntegrator()
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("Apple",), ("DOG",)]
        mock_db.conn.execute.return_value = mock_cursor
        i.lexicon_db = mock_db
        assert i.get_existing_words() == {"apple", "dog"}

    def test_exact_sql_query(self):
        # Pin the exact SQL string literal
        i = ExternalSourcesIntegrator()
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.conn.execute.return_value = mock_cursor
        i.lexicon_db = mock_db
        i.get_existing_words()
        mock_db.conn.execute.assert_called_once_with("SELECT DISTINCT lemma FROM lexemes")


# ---------- get_new_words ----------

class TestGetNewWords:
    def test_set_diff(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        with patch.object(i, "get_all_words", return_value={"a", "b", "c"}):
            with patch.object(i, "get_existing_words", return_value={"a"}):
                assert i.get_new_words() == {"b", "c"}


# ---------- aggregate_primitives ----------

class TestAggregatePrimitives:
    def test_no_sources(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        result = i.aggregate_primitives("x")
        assert result.word == "x"
        assert result.sources == []
        assert result.primitives == {}

    def test_single_source(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        p = MagicMock()
        p.to_primitives.return_value = {"GOOD": 1}
        i.parsers = {"s1": p}
        result = i.aggregate_primitives("x")
        assert result.primitives == {"GOOD": 1}
        assert result.sources == ["s1"]
        # Confidence = 1/1 = 1.0
        assert result.confidence_scores["GOOD"] == 1.0

    def test_multiple_agree(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        p1 = MagicMock(); p1.to_primitives.return_value = {"GOOD": 1}
        p2 = MagicMock(); p2.to_primitives.return_value = {"GOOD": 1}
        i.parsers = {"s1": p1, "s2": p2}
        result = i.aggregate_primitives("x")
        assert result.primitives["GOOD"] == 1
        assert result.confidence_scores["GOOD"] == 1.0  # 2/2

    def test_disagreement_majority_wins(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        p1 = MagicMock(); p1.to_primitives.return_value = {"GOOD": 1}
        p2 = MagicMock(); p2.to_primitives.return_value = {"GOOD": 1}
        p3 = MagicMock(); p3.to_primitives.return_value = {"GOOD": -1}
        i.parsers = {"s1": p1, "s2": p2, "s3": p3}
        result = i.aggregate_primitives("x")
        # 2 say +1, 1 says -1 → majority +1
        assert result.primitives["GOOD"] == 1
        # confidence = 2/3
        assert result.confidence_scores["GOOD"] == pytest.approx(2/3)

    def test_empty_primitives_excludes_source(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        p = MagicMock(); p.to_primitives.return_value = {}
        i.parsers = {"s1": p}
        result = i.aggregate_primitives("x")
        assert result.sources == []

    def test_auto_loads(self):
        i = ExternalSourcesIntegrator()
        with patch.object(i, "load_all_sources") as mock_load:
            mock_load.side_effect = lambda: setattr(i, "_loaded", True)
            i.aggregate_primitives("x")
            mock_load.assert_called_once()


# ---------- get_prefilled_entries ----------

class TestGetPrefilledEntries:
    def test_no_new_words(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        with patch.object(i, "get_new_words", return_value=set()):
            assert i.get_prefilled_entries() == []

    def test_returns_words_meeting_threshold(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        p = MagicMock(); p.to_primitives.return_value = {"GOOD": 1}
        i.parsers = {"s1": p}
        with patch.object(i, "get_new_words", return_value={"happy"}):
            result = i.get_prefilled_entries(min_sources=1, min_confidence=0.0)
        assert len(result) == 1
        assert result[0].word == "happy"

    def test_min_sources_filter(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        p = MagicMock(); p.to_primitives.return_value = {"GOOD": 1}
        i.parsers = {"s1": p}
        with patch.object(i, "get_new_words", return_value={"happy"}):
            # min_sources=2 → 1 source not enough
            assert i.get_prefilled_entries(min_sources=2) == []

    def test_filter_low_confidence(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        p1 = MagicMock(); p1.to_primitives.return_value = {"GOOD": 1, "BIG": 1}
        p2 = MagicMock(); p2.to_primitives.return_value = {"GOOD": 1}  # disagree on BIG (silence)
        i.parsers = {"s1": p1, "s2": p2}
        with patch.object(i, "get_new_words", return_value={"x"}):
            # BIG confidence 1/2=0.5; min_confidence=0.6 → BIG filtered
            result = i.get_prefilled_entries(min_sources=1, min_confidence=0.6)
        # GOOD passes (2/2=1.0), BIG filtered out
        assert "GOOD" in result[0].primitives
        assert "BIG" not in result[0].primitives

    def test_excluded_if_no_primitives_after_filter(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        p = MagicMock(); p.to_primitives.return_value = {"GOOD": 1}
        i.parsers = {"s1": p}
        with patch.object(i, "get_new_words", return_value={"x"}):
            # min_confidence=1.5 → no primitive qualifies → entry excluded
            assert i.get_prefilled_entries(min_confidence=1.5) == []


# ---------- export_for_llm_processing ----------

class TestExportForLLM:
    def test_exports_to_json(self, tmp_path):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        with patch.object(i, "get_prefilled_entries", return_value=[
            ExternalWordData(word="happy", primitives={"GOOD": 1},
                             sources=["s1"], confidence_scores={"GOOD": 0.9}),
        ]):
            output = tmp_path / "out.json"
            n = i.export_for_llm_processing(str(output))
        assert n == 1
        data = json.loads(output.read_text())
        assert data[0]["word"] == "happy"
        assert data[0]["known_primitives"] == {"GOOD": 1}
        assert data[0]["sources"] == ["s1"]
        assert data[0]["confidence"]["GOOD"] == 0.9
        # needed_primitives = ALL - known
        assert "GOOD" not in data[0]["needed_primitives"]

    def test_limit_truncates(self, tmp_path):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        entries = [ExternalWordData(word=f"w{n}", primitives={"GOOD": 1}) for n in range(5)]
        with patch.object(i, "get_prefilled_entries", return_value=entries):
            output = tmp_path / "out.json"
            n = i.export_for_llm_processing(str(output), limit=3)
        assert n == 3

    def test_needed_primitives_full_when_no_known(self, tmp_path):
        from gse.curation.schema import ALL_PRIMITIVES
        i = ExternalSourcesIntegrator()
        i._loaded = True
        with patch.object(i, "get_prefilled_entries", return_value=[
            ExternalWordData(word="x", primitives={}),
        ]):
            output = tmp_path / "out.json"
            i.export_for_llm_processing(str(output))
        data = json.loads(output.read_text())
        assert set(data[0]["needed_primitives"]) == set(ALL_PRIMITIVES)


# ---------- get_statistics ----------

class TestGetStatistics:
    def test_basic(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        p = MagicMock()
        p.get_all_words.return_value = ["a", "b"]
        i.parsers = {"s1": p}
        with patch.object(i, "get_existing_words", return_value={"a"}):
            stats = i.get_statistics()
        assert stats["sources_loaded"] == ["s1"]
        assert stats["words_per_source"] == {"s1": 2}
        assert stats["total_unique_words"] == 2
        assert stats["existing_in_lexicon"] == 1
        assert stats["new_words"] == 1

    def test_empty(self):
        i = ExternalSourcesIntegrator()
        i._loaded = True
        stats = i.get_statistics()
        assert stats["sources_loaded"] == []
        assert stats["total_unique_words"] == 0


# ---------- close ----------

class TestClose:
    def test_with_db(self):
        i = ExternalSourcesIntegrator()
        i.lexicon_db = MagicMock()
        i.close()
        i.lexicon_db.close.assert_called_once()

    def test_without_db(self):
        i = ExternalSourcesIntegrator()
        # Should not raise
        i.close()


# ---------- download_all_sources ----------

class TestDownloadAllSources:
    def test_calls_nltk_and_parsers(self, capsys):
        with patch("nltk.download") as mock_dl:
            with patch.object(
                __import__("gse.curation.external_sources.nrc_emotion", fromlist=["NRCEmotionParser"]).NRCEmotionParser,
                "download"
            ) as mock_em:
                with patch.object(
                    __import__("gse.curation.external_sources.nrc_vad", fromlist=["NRCVADParser"]).NRCVADParser,
                    "download"
                ) as mock_vad:
                    with patch.object(
                        __import__("gse.curation.external_sources.concreteness", fromlist=["ConcretenessParser"]).ConcretenessParser,
                        "download"
                    ) as mock_conc:
                        download_all_sources()

        # 5 NLTK downloads
        assert mock_dl.call_count == 5
        mock_em.assert_called_once()
        mock_vad.assert_called_once()
        mock_conc.assert_called_once()

    def test_prints_progress(self, capsys):
        with patch("nltk.download"):
            with patch.object(
                __import__("gse.curation.external_sources.nrc_emotion", fromlist=["NRCEmotionParser"]).NRCEmotionParser,
                "download"
            ):
                with patch.object(
                    __import__("gse.curation.external_sources.nrc_vad", fromlist=["NRCVADParser"]).NRCVADParser,
                    "download"
                ):
                    with patch.object(
                        __import__("gse.curation.external_sources.concreteness", fromlist=["ConcretenessParser"]).ConcretenessParser,
                        "download"
                    ):
                        download_all_sources()
        out = capsys.readouterr().out
        assert "NLTK resources" in out
        assert "NRC resources" in out
        assert "All sources downloaded" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
