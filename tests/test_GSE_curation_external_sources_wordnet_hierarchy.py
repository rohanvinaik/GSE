"""Manual contract tests for GSE.curation.external_sources.wordnet_hierarchy."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from GSE.curation.external_sources.wordnet_hierarchy import (
    LEXNAME_TO_PRIMITIVE,
    ROOT_CONCEPT_PRIMITIVES,
    WordNetHierarchyEntry,
    WordNetHierarchyParser,
    download_wordnet,
)


def mk_entry(
    word="dog", pos="noun", synset_name="dog.n.01", depth=8, hypo=10, mero=False, holo=False, lexname="noun.animal"
):
    return WordNetHierarchyEntry(
        word=word,
        pos=pos,
        synset_name=synset_name,
        hypernym_depth=depth,
        hyponym_count=hypo,
        has_meronyms=mero,
        has_holonyms=holo,
        lexname=lexname,
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
        mock_lemma = MagicMock()
        mock_lemma.name.return_value = "x"
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
        # a genuine body part warrants PART, not own-word BODY
        d = p.to_primitives("hand")
        assert "BODY" not in d
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
        parser = WordNetHierarchyParser()
        prims = {}
        parser._apply_ancestor_primitives("dog", prims)
        assert prims == {}

    def test_delegates_primary_projection_preserving_known_values(self):
        parser = WordNetHierarchyParser()
        parser._wn = MagicMock()
        prims = {"SOMEONE": -1}
        with patch.object(parser, "to_primitives", return_value={"SOMEONE": 1, "ALIVE": 1}) as project:
            parser._apply_ancestor_primitives("dog", prims)
        project.assert_called_once_with("dog")
        assert prims == {"SOMEONE": -1, "ALIVE": 1}

    def test_programmer_errors_are_not_hidden(self):
        parser = WordNetHierarchyParser()
        parser._wn = MagicMock()
        with patch.object(parser, "to_primitives", side_effect=RuntimeError("broken projection")):
            with pytest.raises(RuntimeError, match="broken projection"):
                parser._apply_ancestor_primitives("dog", {})


class TestDefinitionProjection:
    @pytest.fixture(scope="class")
    def p(self):
        # Already-installed corpus only. No adapter load/download path.
        from nltk.corpus import wordnet

        wordnet.ensure_loaded()
        parser = WordNetHierarchyParser()
        parser._wn = wordnet
        parser._loaded = True
        return parser

    def test_specific_animal_and_person_definitions_do_not_mix(self, p):
        animal = p.to_primitives_for_definition("dog.n.01")
        person = p.to_primitives_for_definition("dog.n.03")
        assert animal == {"ALIVE": 1, "SOMETHING": 1}
        assert person["SOMEONE"] == 1
        assert "SOMEONE" not in animal

    @pytest.mark.parametrize("synset", ["flock.n.02", "food.n.01", "abstraction.n.06"])
    def test_unsafe_category_proposals_do_not_assert(self, p, synset):
        result = p.to_primitives_for_definition(synset)
        assert not {"PEOPLE", "BODY", "THINK"}.intersection(result)

    def test_feeling_category_warrants_feel(self, p):
        assert p.to_primitives_for_definition("emotion.n.01")["FEEL"] == 1
        assert p.to_primitives_for_definition("feeling.n.01")["FEEL"] == 1
        assert "FEEL" not in p.to_primitives_for_definition("psychological_feature.n.01")

    def test_travel_identity_root_carries_motion(self, p):
        # Founder correction 2 (2026-11-25): travel.v.01 ("change location; move, travel, or proceed")
        # is a reviewed identity root, so running on foot is MOVE.
        assert p.to_primitives_for_definition("run.v.01") == {"MOVE": 1}

    @pytest.mark.parametrize(
        "synset,bank",
        [
            ("think.v.03", "THINK"),
            ("know.v.01", "KNOW"),
            ("desire.v.01", "WANT"),
            ("see.v.01", "SEE"),
            ("hear.v.01", "HEAR"),
            ("state.v.01", "SAY"),
            ("perform.v.01", "DO"),
            ("act.v.01", "DO"),
            ("cause.v.01", "CAUSE"),
            ("happen.v.01", "HAPPEN"),
            ("feel.v.01", "FEEL"),
            ("move.v.03", "MOVE"),
        ],
    )
    def test_reviewed_exact_verb_definition_has_native_ancestry(self, p, synset, bank):
        paths = p._wn.synset(synset).hypernym_paths()
        assert any(synset in {node.name() for node in path} for path in paths)
        assert p.to_primitives_for_definition(synset)[bank] == 1

    def test_descendant_ancestry_does_not_leak_to_another_lemma_sense(self, p):
        assert p.to_primitives_for_definition("contemplate.v.02") == {"THINK": 1}
        assert p.to_primitives_for_definition("contemplate.v.01") == {}
        assert p.to_primitives_for_definition("shake.v.02") == {"MOVE": 1}
        # The emotional sense keeps its own ancestry: change.v.01 ("cause to change") gives CAUSE,
        # and the physical sense's MOVE does not leak to it.
        assert p.to_primitives_for_definition("shake.v.05") == {"CAUSE": 1}

    @pytest.mark.parametrize("synset", ["bridle.v.03", "rent.v.04", "summarize.v.02"])
    def test_reviewed_own_content_exclusion_withdraws_say(self, p, synset):
        sense = p._wn.synset(synset)
        assert any("state.v.01" in {ancestor.name() for ancestor in path} for path in sense.hypernym_paths())
        assert "SAY" not in p.to_primitives_for_definition(synset)

    @pytest.mark.parametrize("synset", ["answer.v.01", "articulate.v.05"])
    def test_reviewed_own_content_exclusion_preserves_expression_senses(self, p, synset):
        assert p.to_primitives_for_definition(synset)["SAY"] == 1

    @pytest.mark.parametrize(
        "synset,absent",
        [("understand.v.02", "SEE"), ("hear.v.03", "HEAR"), ("want.v.05", "WANT")],
    )
    def test_homograph_is_not_a_definition_link(self, p, synset, absent):
        assert absent not in p.to_primitives_for_definition(synset)

    def test_unknown_definition_abstains(self, p):
        assert p.to_primitives_for_definition("unknown_xyz.n.01") == {}

    def test_unloaded_projection_never_loads(self):
        parser = WordNetHierarchyParser()
        with patch.object(parser, "load", side_effect=AssertionError("must not load")):
            assert parser.to_primitives_for_definition("dog.n.01") == {}

    @pytest.mark.parametrize("invalid", [None, "", 42])
    def test_malformed_definition_id_is_named(self, p, invalid):
        with pytest.raises(ValueError, match="INVALID_DEFINITION_ID"):
            p.to_primitives_for_definition(invalid)


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
        m1 = MagicMock()
        m1.name.return_value = "a.n.01"
        m2 = MagicMock()
        m2.name.return_value = "b.n.01"
        m3 = MagicMock()
        m3.name.return_value = "a.n.01"  # duplicate
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
        mock_lemma = MagicMock()
        mock_lemma.name.return_value = "poodle"
        mock_hypo = MagicMock()
        mock_hypo.lemmas.return_value = [mock_lemma]
        mock_synset = MagicMock()
        mock_synset.hyponyms.return_value = [mock_hypo]
        mock_wn = MagicMock()
        mock_wn.synsets.return_value = [mock_synset]
        p._wn = mock_wn

        assert "poodle" in p.get_hyponyms("dog")

    def test_underscore_replaced(self):
        p = WordNetHierarchyParser()
        p._loaded = True
        mock_lemma = MagicMock()
        mock_lemma.name.return_value = "hot_dog"
        mock_hypo = MagicMock()
        mock_hypo.lemmas.return_value = [mock_lemma]
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
            m = MagicMock()
            m.name.return_value = f"h{i}"
            lemmas.append(m)
        mock_hypo = MagicMock()
        mock_hypo.lemmas.return_value = lemmas
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
        mock_lemma = MagicMock()
        mock_lemma.name.return_value = "wheel"
        mock_mero = MagicMock()
        mock_mero.lemmas.return_value = [mock_lemma]
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
            mock_lemma = MagicMock()
            mock_lemma.name.return_value = f"m{i}"
            mock_mero = MagicMock()
            mock_mero.lemmas.return_value = [mock_lemma]
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
        mock_lemma = MagicMock()
        mock_lemma.name.return_value = "wheel"
        mock_mero = MagicMock()
        mock_mero.lemmas.return_value = [mock_lemma]

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


class TestAdjectiveIdentity:
    """A satellite refines its head; a head whose own gloss is a prime's pole carries it (2026-11-25)."""

    @pytest.fixture(scope="class")
    def p(self):
        parser = WordNetHierarchyParser()
        parser.load()
        return parser

    @pytest.mark.parametrize(
        "synset,expected",
        [
            ("large.a.01", {"BIG": 1}),
            ("huge.s.01", {"BIG": 1}),
            ("tiny.s.01", {"BIG": -1}),
            ("superb.s.02", {"GOOD": 1}),
            ("terrible.s.02", {"GOOD": -1}),
            ("adjacent.s.01", {"FAR": -1}),
        ],
    )
    def test_prime_heads_and_their_satellites(self, p, synset, expected):
        assert p.to_primitives_for_definition(synset) == expected

    @pytest.mark.parametrize("synset", ["happy.a.01", "hot.a.01", "big.s.01"])
    def test_adjectives_outside_a_prime_cluster_assert_nothing(self, p, synset):
        assert p.to_primitives_for_definition(synset) == {}


class TestCausativeIdentity:
    """A verb WordNet states causes another verb has CAUSE in its definition (2026-11-25)."""

    @pytest.fixture(scope="class")
    def p(self):
        parser = WordNetHierarchyParser()
        parser.load()
        return parser

    @pytest.mark.parametrize("synset", ["kill.v.01", "burn.v.05", "transfer.v.05", "cheer.v.03"])
    def test_stated_causatives_carry_cause(self, p, synset):
        assert p.to_primitives_for_definition(synset)["CAUSE"] == 1

    def test_a_verb_without_a_stated_cause_gains_none_from_this(self, p):
        assert "CAUSE" not in p.to_primitives_for_definition("die.v.01")


class TestRoundTwoIdentity:
    """State denotation is BE (Rohan's convention), less the reserved nonbeing branch; verb roots."""

    @pytest.fixture(scope="class")
    def p(self):
        parser = WordNetHierarchyParser()
        parser.load()
        return parser

    @pytest.mark.parametrize(
        "synset,bank,value",
        [
            ("exit.v.01", "MOVE", 1),
            ("persuade.v.02", "CAUSE", 1),
        ],
    )
    def test_identity_roots(self, p, synset, bank, value):
        assert p.to_primitives_for_definition(synset)[bank] == value

    @pytest.mark.parametrize("synset", ["nonbeing.n.01", "nonexistence.n.01"])
    def test_reserved_nonbeing_branch_gains_no_be(self, p, synset):
        assert "BE" not in p.to_primitives_for_definition(synset)


class TestDerivedActIdentity:
    """An act or event noun takes the identity every derivationally related verb shares."""

    @pytest.fixture(scope="class")
    def p(self):
        parser = WordNetHierarchyParser()
        parser.load()
        return parser

    @pytest.mark.parametrize(
        "synset,bank", [("departure.n.01", "MOVE"), ("touch.n.05", "TOUCH"), ("movement.n.03", "MOVE")]
    )
    def test_the_act_of_a_verb_is_that_verb(self, p, synset, bank):
        assert p.to_primitives_for_definition(synset)[bank] == 1

    def test_a_related_verb_without_the_identity_blocks_it(self, p):
        # act.n.02 relates to act.v.01 (no CAUSE) and motivate.v.01 (CAUSE): nothing is shared.
        assert "CAUSE" not in p.to_primitives_for_definition("act.n.02")


class TestSensoryAdjectiveIdentity:
    """A head whose attribute is a sensory property, and its satellites, carry that sense."""

    @pytest.fixture(scope="class")
    def p(self):
        parser = WordNetHierarchyParser()
        parser.load()
        return parser

    @pytest.mark.parametrize(
        "synset,expected",
        [
            ("black.a.01", {"SEE": 1}),
            ("red.s.01", {"SEE": 1}),
            ("loud.a.01", {"HEAR": 1}),
            ("deafening.s.01", {"HEAR": 1}),
            ("coarse.a.01", {"TOUCH": 1}),
        ],
    )
    def test_sensory_attributes(self, p, synset, expected):
        assert p.to_primitives_for_definition(synset) == expected


class TestPeopleIdentity:
    """Groups of persons are PEOPLE; institutions (an airline, an agency) are not."""

    @pytest.fixture(scope="class")
    def p(self):
        parser = WordNetHierarchyParser()
        parser.load()
        return parser

    @pytest.mark.parametrize(
        "synset", ["family.n.01", "nuclear_family.n.01", "crowd.n.01", "power_couple.n.01", "baseball_club.n.01"]
    )
    def test_groups_of_persons_are_people(self, p, synset):
        assert p.to_primitives_for_definition(synset).get("PEOPLE") == 1

    @pytest.mark.parametrize("synset", ["airline.n.01", "ministry.n.02", "frau.n.01"])
    def test_institutions_and_titles_are_not(self, p, synset):
        assert "PEOPLE" not in p.to_primitives_for_definition(synset)
        assert "PART" not in p.to_primitives_for_definition(synset)


def test_every_identity_root_is_named_by_its_canonical_synset():
    """WordNet resolves a lemma-based name to another synset; ancestry uses canonical names only."""
    from nltk.corpus import wordnet as wn

    from GSE.curation.external_sources import wordnet_hierarchy as wh

    names = (
        set(wh._WARRANTED_ROOT_PRIMITIVES)
        | set(wh.ADJECTIVE_IDENTITY_HEADS)
        | set(wh.ADJECTIVE_ATTRIBUTE_IDENTITY)
        | {root for root, _bank in wh.REVIEWED_BRANCH_EXCLUSIONS}
        | set(wh.REVIEWED_BRANCH_EXCLUSIONS.values())
    )
    assert {name: wn.synset(name).name() for name in names if wn.synset(name).name() != name} == {}


def test_state_branch_carries_no_be_identity():
    """Withdrawn 2026-11-25: own state denotation is decided by the reviewed stative rule, not WordNet's branch."""
    parser = WordNetHierarchyParser()
    parser.load()
    for synset in ("illness.n.01", "context.n.02", "earthquake.n.02"):
        assert "BE" not in parser.to_primitives_for_definition(synset)
