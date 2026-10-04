"""Manual contract tests for gse.curation.external_sources.wordnet_hierarchy."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.curation.external_sources.wordnet_hierarchy import (
    LEXNAME_TO_PRIMITIVE,
    ROOT_CONCEPT_PRIMITIVES,
    WordNetHierarchyEntry,
    WordNetHierarchyParser,
    download_wordnet,
)


def mk_entry(word="dog", pos="noun", synset_name="dog.n.01", depth=8, hypo=10,
             mero=False, holo=False, lexname="noun.animal"):
    return WordNetHierarchyEntry(
        word=word, pos=pos, synset_name=synset_name,
        hypernym_depth=depth, hyponym_count=hypo,
        has_meronyms=mero, has_holonyms=holo, lexname=lexname,
    )


# ---------- Entry ----------

class TestEntry:
    def test_construction(self):
        e = mk_entry(mero=True, holo=False)
        assert e.word == "dog"
        assert e.has_meronyms is True
        assert e.has_holonyms is False


# ---------- LEXNAME_TO_PRIMITIVE ----------

class TestLexnameMapping:
    def test_noun_animal(self):
        assert LEXNAME_TO_PRIMITIVE["noun.animal"] == {"ALIVE": 1, "SOMETHING": 1}

    def test_noun_person(self):
        assert LEXNAME_TO_PRIMITIVE["noun.person"] == {"SOMEONE": 1, "ALIVE": 1}

    def test_verb_motion(self):
        assert LEXNAME_TO_PRIMITIVE["verb.motion"] == {"MOVE": 1}

    def test_adj_all_empty(self):
        assert LEXNAME_TO_PRIMITIVE["adj.all"] == {}


# ---------- ROOT_CONCEPT_PRIMITIVES ----------

class TestRootConcepts:
    def test_person_someone(self):
        assert ROOT_CONCEPT_PRIMITIVES["person.n.01"] == {"SOMEONE": 1}

    def test_body_part(self):
        assert ROOT_CONCEPT_PRIMITIVES["body_part.n.01"] == {"BODY": 1, "PART": 1}


# ---------- __init__ ----------

class TestInit:
    def test_initial_state(self):
        p = WordNetHierarchyParser()
        assert p.entries == {}
        assert p._loaded is False
        assert p._synset_cache == {}
        assert p._wn is None

    def test_default_max_depth(self):
        assert WordNetHierarchyParser().max_depth == 10

    def test_custom_max_depth(self):
        assert WordNetHierarchyParser(max_hypernym_depth=5).max_depth == 5

    def test_config_name(self):
        assert WordNetHierarchyParser().config.name == "wordnet_hierarchy"


# ---------- _convert_pos ----------

class TestConvertPos:
    def test_noun(self):
        assert WordNetHierarchyParser()._convert_pos("n") == "noun"

    def test_verb(self):
        assert WordNetHierarchyParser()._convert_pos("v") == "verb"

    def test_adj(self):
        assert WordNetHierarchyParser()._convert_pos("a") == "adj"

    def test_adv(self):
        assert WordNetHierarchyParser()._convert_pos("r") == "adv"

    def test_satellite_adj(self):
        assert WordNetHierarchyParser()._convert_pos("s") == "adj"

    def test_unknown(self):
        assert WordNetHierarchyParser()._convert_pos("Z") == "unknown"


# ---------- _get_hypernym_depth ----------

class TestGetHypernymDepth:
    def test_no_paths_returns_zero(self):
        p = WordNetHierarchyParser()
        mock_synset = MagicMock()
        mock_synset.hypernym_paths.return_value = []
        assert p._get_hypernym_depth(mock_synset) == 0

    def test_min_path_length(self):
        p = WordNetHierarchyParser()
        mock_synset = MagicMock()
        mock_synset.hypernym_paths.return_value = [
            [1, 2, 3, 4, 5],
            [1, 2, 3],  # shortest = 3
            [1, 2, 3, 4],
        ]
        assert p._get_hypernym_depth(mock_synset) == 3

    def test_exception_returns_zero(self):
        p = WordNetHierarchyParser()
        mock_synset = MagicMock()
        mock_synset.hypernym_paths.side_effect = RuntimeError("boom")
        assert p._get_hypernym_depth(mock_synset) == 0


# ---------- load ----------

class TestLoad:
    def test_failure_returns_false(self):
        p = WordNetHierarchyParser()
        with patch("nltk.corpus.wordnet.synsets", side_effect=Exception("boom")):
            assert p.load() is False

    def test_successful_load(self):
        mock_lemma = MagicMock()
        mock_lemma.name.return_value = "dog"
        mock_synset = MagicMock()
        mock_synset.lemmas.return_value = [mock_lemma]
        mock_synset.pos.return_value = "n"
        mock_synset.name.return_value = "dog.n.01"
        mock_synset.lexname.return_value = "noun.animal"
        mock_synset.hypernyms.return_value = []
        mock_synset.hyponyms.return_value = []
        mock_synset.hypernym_paths.return_value = [[1, 2, 3]]
        mock_synset.part_meronyms.return_value = []
        mock_synset.member_meronyms.return_value = []
        mock_synset.substance_meronyms.return_value = []
        mock_synset.part_holonyms.return_value = []
        mock_synset.member_holonyms.return_value = []
        mock_synset.substance_holonyms.return_value = []

        with patch("nltk.corpus.wordnet.synsets"):
            with patch("nltk.corpus.wordnet.all_synsets", return_value=[mock_synset]):
                p = WordNetHierarchyParser()
                assert p.load() is True
                assert "dog" in p.entries
                assert p.entries["dog"][0].synset_name == "dog.n.01"
                assert p.entries["dog"][0].lexname == "noun.animal"
                assert p.entries["dog"][0].pos == "noun"

    def test_has_meronyms_true_when_any(self):
        mock_lemma = MagicMock(); mock_lemma.name.return_value = "x"
        mock_synset = MagicMock()
        mock_synset.lemmas.return_value = [mock_lemma]
        mock_synset.pos.return_value = "n"
        mock_synset.name.return_value = "x.n.01"
        mock_synset.lexname.return_value = "noun.object"
        mock_synset.hypernyms.return_value = []
        mock_synset.hyponyms.return_value = []
        mock_synset.hypernym_paths.return_value = []
        mock_synset.part_meronyms.return_value = ["m1"]  # truthy
        mock_synset.member_meronyms.return_value = []
        mock_synset.substance_meronyms.return_value = []
        mock_synset.part_holonyms.return_value = []
        mock_synset.member_holonyms.return_value = []
        mock_synset.substance_holonyms.return_value = []

        with patch("nltk.corpus.wordnet.synsets"):
            with patch("nltk.corpus.wordnet.all_synsets", return_value=[mock_synset]):
                p = WordNetHierarchyParser()
                p.load()
                assert p.entries["x"][0].has_meronyms is True


# ---------- to_primitives ----------

class TestToPrimitives:
    """``to_primitives`` reads the PRIMARY noun sense's IS-A path from real
    WordNet — primary-sense only (no union-over-senses bleed) and no
    meronym/holonym→PART (a genuine part gets PART from its IS-A ancestor
    instead). Exercised against the real taxonomy via a loaded parser."""

    @pytest.fixture(scope="class")
    def p(self):
        parser = WordNetHierarchyParser()
        parser.load()
        return parser

    def test_unknown_empty(self, p):
        assert p.to_primitives("nonexistent_xyz_qqq") == {}

    def test_no_noun_sense_empty(self, p):
        # purely adjectival — no noun synset → no category
        assert p.to_primitives("very") == {}

    def test_primary_sense_category(self, p):
        # dog's primary noun sense is the animal → ALIVE + SOMETHING
        d = p.to_primitives("dog")
        assert d.get("ALIVE") == 1
        assert d.get("SOMETHING") == 1

    def test_primary_sense_no_secondary_bleed(self, p):
        # the "contemptible person" sense of dog must NOT bleed SOMEONE in
        assert "SOMEONE" not in p.to_primitives("dog")

    def test_body_part_gets_part_via_isa(self, p):
        # a genuine body part inherits BODY/PART from its body_part ancestor
        d = p.to_primitives("hand")
        assert d.get("BODY") == 1
        assert d.get("PART") == 1

    def test_no_meronym_part(self, p):
        # an artifact "has parts" but is NOT a part → no PART (dropped rule)
        assert "PART" not in p.to_primitives("car")

    def test_case_insensitive(self, p):
        assert p.to_primitives("DOG") == p.to_primitives("dog")

    def test_auto_loads(self):
        parser = WordNetHierarchyParser()
        parser.to_primitives.cache_clear()
        with patch.object(parser, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(parser, "_loaded", True)
            # mocked load leaves _wn unset → returns {} without raising
            assert parser.to_primitives("x") == {}
            mock_load.assert_called_once()


# ---------- _apply_ancestor_primitives ----------

class TestApplyAncestorPrimitives:
    def test_no_wn_no_op(self):
        p = WordNetHierarchyParser()
        p._wn = None
        prims = {}
        p._apply_ancestor_primitives("dog", prims)
        assert prims == {}

    def test_adds_root_concept_primitives(self):
        p = WordNetHierarchyParser()
        mock_wn = MagicMock()
        mock_ancestor = MagicMock()
        mock_ancestor.name.return_value = "person.n.01"
        mock_synset = MagicMock()
        mock_synset.hypernym_paths.return_value = [[mock_ancestor]]
        mock_wn.synsets.return_value = [mock_synset]
        p._wn = mock_wn

        prims = {}
        p._apply_ancestor_primitives("dog", prims)
        assert prims["SOMEONE"] == 1

    def test_first_value_wins(self):
        p = WordNetHierarchyParser()
        mock_wn = MagicMock()
        mock_ancestor = MagicMock()
        mock_ancestor.name.return_value = "person.n.01"
        mock_synset = MagicMock()
        mock_synset.hypernym_paths.return_value = [[mock_ancestor]]
        mock_wn.synsets.return_value = [mock_synset]
        p._wn = mock_wn

        prims = {"SOMEONE": -1}  # pre-existing different value
        p._apply_ancestor_primitives("dog", prims)
        # Existing value preserved
        assert prims["SOMEONE"] == -1

    def test_exception_swallowed(self):
        p = WordNetHierarchyParser()
        mock_wn = MagicMock()
        mock_wn.synsets.side_effect = RuntimeError("boom")
        p._wn = mock_wn
        # Should not raise
        prims = {}
        p._apply_ancestor_primitives("x", prims)
        assert prims == {}

    def test_only_first_five_ancestors(self):
        p = WordNetHierarchyParser()
        mock_wn = MagicMock()
        ancestors = []
        for i in range(8):
            anc = MagicMock()
            anc.name.return_value = f"anc{i}.n.01"
            ancestors.append(anc)
        # Only first 5 should be checked; place person.n.01 at index 6 — won't trigger
        ancestors[6] = MagicMock()
        ancestors[6].name.return_value = "person.n.01"
        mock_synset = MagicMock()
        mock_synset.hypernym_paths.return_value = [ancestors]
        mock_wn.synsets.return_value = [mock_synset]
        p._wn = mock_wn

        prims = {}
        p._apply_ancestor_primitives("x", prims)
        # person.n.01 is at index 6, not in first 5 → SOMEONE not added
        assert "SOMEONE" not in prims


# ---------- get_all_words ----------

class TestGetAllWords:
    def test_returns_keys(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        p.entries = {"a": [], "b": []}
        assert set(p.get_all_words()) == {"a", "b"}

    def test_auto_loads(self):
        p = WordNetHierarchyParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_all_words()
            mock_load.assert_called_once()


# ---------- get_hypernyms ----------

class TestGetHypernyms:
    def test_no_wn_returns_empty(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        p._wn = None
        assert p.get_hypernyms("dog") == []

    def test_no_synsets_empty(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        mock_wn = MagicMock()
        mock_wn.synsets.return_value = []
        p._wn = mock_wn
        assert p.get_hypernyms("xyz") == []

    def test_returns_hypernym_chain(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        mock_anc = MagicMock()
        mock_anc.name.return_value = "animal.n.01"
        mock_anc2 = MagicMock()
        mock_anc2.name.return_value = "entity.n.01"
        mock_synset = MagicMock()
        mock_synset.hypernym_paths.return_value = [[mock_anc, mock_anc2]]
        mock_wn = MagicMock()
        mock_wn.synsets.return_value = [mock_synset]
        p._wn = mock_wn

        result = p.get_hypernyms("dog")
        assert "animal" in result
        assert "entity" in result

    def test_dedup_preserves_order(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        m1 = MagicMock(); m1.name.return_value = "a.n.01"
        m2 = MagicMock(); m2.name.return_value = "b.n.01"
        m3 = MagicMock(); m3.name.return_value = "a.n.01"  # duplicate
        mock_synset = MagicMock()
        mock_synset.hypernym_paths.return_value = [[m1, m2, m3]]
        mock_wn = MagicMock()
        mock_wn.synsets.return_value = [mock_synset]
        p._wn = mock_wn

        result = p.get_hypernyms("x")
        assert result == ["a", "b"]

    def test_pos_filter(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        mock_wn = MagicMock()
        mock_wn.synsets.return_value = []
        p._wn = mock_wn
        p.get_hypernyms("dog", pos="noun")
        # First char of "noun" = "n"
        mock_wn.synsets.assert_called_once_with("dog", pos="n")

    def test_exception_returns_empty(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        mock_wn = MagicMock()
        mock_wn.synsets.side_effect = RuntimeError("boom")
        p._wn = mock_wn
        assert p.get_hypernyms("x") == []


# ---------- get_hyponyms ----------

class TestGetHyponyms:
    def test_no_wn_empty(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        p._wn = None
        assert p.get_hyponyms("dog") == []

    def test_no_synsets_empty(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        mock_wn = MagicMock()
        mock_wn.synsets.return_value = []
        p._wn = mock_wn
        assert p.get_hyponyms("xyz") == []

    def test_returns_hyponym_lemmas(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        mock_lemma = MagicMock(); mock_lemma.name.return_value = "poodle"
        mock_hypo = MagicMock(); mock_hypo.lemmas.return_value = [mock_lemma]
        mock_synset = MagicMock()
        mock_synset.hyponyms.return_value = [mock_hypo]
        mock_wn = MagicMock()
        mock_wn.synsets.return_value = [mock_synset]
        p._wn = mock_wn

        assert "poodle" in p.get_hyponyms("dog")

    def test_underscore_replaced(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        mock_lemma = MagicMock(); mock_lemma.name.return_value = "hot_dog"
        mock_hypo = MagicMock(); mock_hypo.lemmas.return_value = [mock_lemma]
        mock_synset = MagicMock()
        mock_synset.hyponyms.return_value = [mock_hypo]
        mock_wn = MagicMock()
        mock_wn.synsets.return_value = [mock_synset]
        p._wn = mock_wn

        result = p.get_hyponyms("food")
        assert "hot dog" in result

    def test_limits_to_20(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        lemmas = []
        for i in range(25):
            m = MagicMock(); m.name.return_value = f"h{i}"
            lemmas.append(m)
        mock_hypo = MagicMock(); mock_hypo.lemmas.return_value = lemmas
        mock_synset = MagicMock()
        mock_synset.hyponyms.return_value = [mock_hypo]
        mock_wn = MagicMock()
        mock_wn.synsets.return_value = [mock_synset]
        p._wn = mock_wn

        assert len(p.get_hyponyms("x")) == 20

    def test_exception_returns_empty(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        mock_wn = MagicMock()
        mock_wn.synsets.side_effect = RuntimeError("boom")
        p._wn = mock_wn
        assert p.get_hyponyms("x") == []


# ---------- get_meronyms ----------

class TestGetMeronyms:
    def test_no_wn_empty(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        p._wn = None
        assert p.get_meronyms("car") == []

    def test_no_synsets_empty(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        mock_wn = MagicMock()
        mock_wn.synsets.return_value = []
        p._wn = mock_wn
        assert p.get_meronyms("xyz") == []

    def test_collects_all_meronym_types(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        mock_lemma = MagicMock(); mock_lemma.name.return_value = "wheel"
        mock_mero = MagicMock(); mock_mero.lemmas.return_value = [mock_lemma]
        mock_synset = MagicMock()
        mock_synset.part_meronyms.return_value = [mock_mero]
        mock_synset.member_meronyms.return_value = []
        mock_synset.substance_meronyms.return_value = []
        mock_wn = MagicMock()
        mock_wn.synsets.return_value = [mock_synset]
        p._wn = mock_wn

        assert "wheel" in p.get_meronyms("car")

    def test_limits_to_3_senses(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        # Create 5 synsets; only first 3 should be processed
        synsets = []
        for i in range(5):
            mock_lemma = MagicMock(); mock_lemma.name.return_value = f"m{i}"
            mock_mero = MagicMock(); mock_mero.lemmas.return_value = [mock_lemma]
            mock_synset = MagicMock()
            mock_synset.part_meronyms.return_value = [mock_mero]
            mock_synset.member_meronyms.return_value = []
            mock_synset.substance_meronyms.return_value = []
            synsets.append(mock_synset)
        mock_wn = MagicMock()
        mock_wn.synsets.return_value = synsets
        p._wn = mock_wn

        result = set(p.get_meronyms("x"))
        # Only m0, m1, m2 (first 3 senses)
        assert result == {"m0", "m1", "m2"}

    def test_exception_returns_empty(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        mock_wn = MagicMock()
        mock_wn.synsets.side_effect = RuntimeError("boom")
        p._wn = mock_wn
        assert p.get_meronyms("x") == []

    def test_dedup_via_set(self):
        # Same meronym from multiple synsets → dedup
        p = WordNetHierarchyParser()
        p._loaded = True
        mock_lemma = MagicMock(); mock_lemma.name.return_value = "wheel"
        mock_mero = MagicMock(); mock_mero.lemmas.return_value = [mock_lemma]

        synsets = []
        for _ in range(3):
            ms = MagicMock()
            ms.part_meronyms.return_value = [mock_mero]
            ms.member_meronyms.return_value = []
            ms.substance_meronyms.return_value = []
            synsets.append(ms)

        mock_wn = MagicMock()
        mock_wn.synsets.return_value = synsets
        p._wn = mock_wn

        result = p.get_meronyms("x")
        assert result == ["wheel"]  # deduped


# ---------- get_domain ----------

class TestGetDomain:
    def test_returns_first_entry_lexname(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        p.entries["dog"] = [mk_entry(lexname="noun.animal")]
        assert p.get_domain("dog") == "noun.animal"

    def test_unknown_none(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        assert p.get_domain("xyz") is None

    def test_case_insensitive(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        p.entries["dog"] = [mk_entry(lexname="noun.animal")]
        assert p.get_domain("DOG") == "noun.animal"

    def test_auto_loads(self):
        p = WordNetHierarchyParser()
        with patch.object(p, "load") as mock_load:
            mock_load.side_effect = lambda: setattr(p, "_loaded", True)
            p.get_domain("x")
            mock_load.assert_called_once()


# ---------- download_wordnet ----------

class TestDownloadWordnet:
    def test_calls_nltk_download(self, capsys):
        with patch("nltk.download") as mock_dl:
            download_wordnet()
            assert mock_dl.call_count == 2
            mock_dl.assert_any_call("wordnet")
            mock_dl.assert_any_call("omw-1.4")

    def test_prints_success(self, capsys):
        with patch("nltk.download"):
            download_wordnet()
            assert "successfully" in capsys.readouterr().out


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
