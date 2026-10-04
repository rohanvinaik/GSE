"""Manual contract tests for gse.merkle.tree."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.merkle.nodes import LexemeNode
from gse.merkle.tree import MerkleLexiconTree


def make_lex(lemma="happy", pos="adj", sense_id="01", decomposition=None, **kwargs):
    decomposition = decomposition or [("FEEL", "experiencer", 1), ("GOOD", "attribute", 1)]
    return LexemeNode(
        node_id=f"{lemma}_{pos}_{sense_id}",
        lemma=lemma,
        pos=pos,
        sense_id=sense_id,
        gloss=kwargs.get("gloss", "definition"),
        decomposition=decomposition,
        vector_positive=kwargs.get("vector_positive", np.array([1, 2, 3], dtype=np.uint16)),
        vector_negative=kwargs.get("vector_negative", np.array([10, 20], dtype=np.uint16)),
    )


# ---------- __init__ and _initialize_structure ----------


class TestInitAndStructure:
    def test_empty_tree_has_root(self):
        tree = MerkleLexiconTree()
        assert tree.root is not None
        assert tree.root.combined_hash != ""

    def test_root_node_id_is_root(self):
        tree = MerkleLexiconTree()
        assert tree.root.node_id == "root"

    def test_banks_populated(self):
        tree = MerkleLexiconTree()
        assert len(tree.banks) == 8

    def test_families_populated(self):
        tree = MerkleLexiconTree()
        assert len(tree.families) > 0

    def test_hubs_populated(self):
        tree = MerkleLexiconTree()
        assert len(tree.hubs) > 0

    def test_lexemes_initially_empty(self):
        tree = MerkleLexiconTree()
        assert tree.lexemes == {}
        assert tree._lexeme_to_hub == {}

    def test_initial_lookup_indices_consistent(self):
        tree = MerkleLexiconTree()
        # Every hub maps to a family
        for hub in tree.hubs:
            assert hub in tree._hub_to_family
        # Every family maps to a bank
        for fam in tree.families:
            assert fam in tree._family_to_bank

    def test_bank_family_hashes_initialized(self):
        tree = MerkleLexiconTree()
        # After _initialize_structure + _recompute_all_hashes,
        # family hashes in banks should be populated
        for bank in tree.banks.values():
            for fid, h in bank.family_hashes.items():
                # All family hashes should be non-empty strings
                assert isinstance(h, str)

    def test_root_total_lexemes_zero(self):
        tree = MerkleLexiconTree()
        assert tree.root.total_lexemes == 0

    def test_two_empty_trees_have_same_root(self):
        # Empty tree is deterministic
        t1 = MerkleLexiconTree()
        t2 = MerkleLexiconTree()
        assert t1.get_root_hash() == t2.get_root_hash()


# ---------- add_lexeme ----------


class TestAddLexeme:
    def test_adds_new_lexeme(self):
        tree = MerkleLexiconTree()
        lex = make_lex()
        assert tree.add_lexeme(lex) is True
        assert lex.key in tree.lexemes

    def test_duplicate_returns_false(self):
        tree = MerkleLexiconTree()
        lex = make_lex()
        tree.add_lexeme(lex)
        assert tree.add_lexeme(lex) is False

    def test_root_hash_changes(self):
        tree = MerkleLexiconTree()
        before = tree.get_root_hash()
        tree.add_lexeme(make_lex())
        assert tree.get_root_hash() != before

    def test_no_recompute_preserves_old_root_until_invoked(self):
        # add_lexeme with recompute=False doesn't immediately update root
        tree = MerkleLexiconTree()
        before = tree.get_root_hash()
        tree.add_lexeme(make_lex(), recompute=False)
        # Root hash NOT updated until recompute is called
        assert tree.get_root_hash() == before

    def test_lexeme_parent_hub_set(self):
        tree = MerkleLexiconTree()
        lex = make_lex()
        tree.add_lexeme(lex)
        # Parent hub set; FEEL is a hub per primitives_v2
        assert lex.parent_hub != ""


# ---------- remove_lexeme ----------


class TestRemoveLexeme:
    def test_removes_existing(self):
        tree = MerkleLexiconTree()
        lex = make_lex()
        tree.add_lexeme(lex)
        assert tree.remove_lexeme(lex.key) is True
        assert lex.key not in tree.lexemes

    def test_missing_returns_false(self):
        tree = MerkleLexiconTree()
        assert tree.remove_lexeme("nonexistent_x_01") is False

    def test_root_hash_reverts_after_add_then_remove(self):
        tree = MerkleLexiconTree()
        empty_root = tree.get_root_hash()
        lex = make_lex()
        tree.add_lexeme(lex)
        tree.remove_lexeme(lex.key)
        assert tree.get_root_hash() == empty_root


# ---------- update_lexeme ----------


class TestUpdateLexeme:
    def test_updates_existing(self):
        tree = MerkleLexiconTree()
        lex = make_lex(gloss="original")
        tree.add_lexeme(lex)

        updated = make_lex(gloss="updated definition")
        assert tree.update_lexeme(updated) is True
        assert tree.lexemes[lex.key].gloss == "updated definition"

    def test_missing_returns_false(self):
        tree = MerkleLexiconTree()
        assert tree.update_lexeme(make_lex()) is False

    def test_root_hash_changes_after_update(self):
        tree = MerkleLexiconTree()
        lex = make_lex(gloss="original")
        tree.add_lexeme(lex)
        before = tree.get_root_hash()
        tree.update_lexeme(make_lex(gloss="new"))
        assert tree.get_root_hash() != before

    def test_update_preserves_lexeme_count(self):
        tree = MerkleLexiconTree()
        lex = make_lex()
        tree.add_lexeme(lex)
        before_count = len(tree.lexemes)
        tree.update_lexeme(make_lex(gloss="changed"))
        assert len(tree.lexemes) == before_count


# ---------- _find_hub_for_lexeme ----------


class TestFindHubForLexeme:
    def test_empty_decomposition_returns_first_hub(self):
        tree = MerkleLexiconTree()
        lex = make_lex(decomposition=[])
        hub = tree._find_hub_for_lexeme(lex)
        # Returns the first hub from the hubs dict
        assert hub in tree.hubs

    def test_uses_role_priority(self):
        tree = MerkleLexiconTree()
        # Pick a primitive that is a hub; pair with role 'agent' for highest priority
        hub_names = list(tree.hubs.keys())
        first_hub = hub_names[0]
        lex = make_lex(
            decomposition=[
                ("OTHERWORDLY", "attribute", 1),  # not a hub
                (first_hub, "agent", 1),  # is a hub, high-priority role
            ]
        )
        result = tree._find_hub_for_lexeme(lex)
        # Agent-priority match wins
        assert result == first_hub

    def test_falls_back_to_first_hub_match(self):
        tree = MerkleLexiconTree()
        hub_names = list(tree.hubs.keys())
        lex = make_lex(
            decomposition=[
                ("UNKNOWN", "patient", 1),
                (hub_names[0], "weird_role", 1),
            ]
        )
        result = tree._find_hub_for_lexeme(lex)
        assert result == hub_names[0]

    def test_role_priority_agent_beats_action(self):
        tree = MerkleLexiconTree()
        hub_names = list(tree.hubs.keys())
        if len(hub_names) < 2:
            pytest.skip("Need at least 2 hubs")
        # Both hubs in decomposition: one as 'agent' (priority 0), one as 'action' (priority 1)
        lex = make_lex(
            decomposition=[
                (hub_names[1], "action", 1),
                (hub_names[0], "agent", 1),
            ]
        )
        result = tree._find_hub_for_lexeme(lex)
        # Agent priority wins
        assert result == hub_names[0]

    def test_role_priority_action_beats_patient(self):
        tree = MerkleLexiconTree()
        hub_names = list(tree.hubs.keys())
        if len(hub_names) < 2:
            pytest.skip("Need at least 2 hubs")
        lex = make_lex(
            decomposition=[
                (hub_names[1], "patient", 1),
                (hub_names[0], "action", 1),
            ]
        )
        result = tree._find_hub_for_lexeme(lex)
        assert result == hub_names[0]

    def test_no_hub_in_decomposition_returns_first(self):
        tree = MerkleLexiconTree()
        first_hub = list(tree.hubs.keys())[0]
        lex = make_lex(decomposition=[("NOTAHUB1", "agent", 1), ("NOTAHUB2", "action", 1)])
        result = tree._find_hub_for_lexeme(lex)
        # No matches → ultimate fallback to first hub
        assert result == first_hub

    def test_patient_beats_attribute(self):
        tree = MerkleLexiconTree()
        hub_names = list(tree.hubs.keys())
        if len(hub_names) < 2:
            pytest.skip("Need 2+ hubs")
        lex = make_lex(
            decomposition=[
                (hub_names[1], "attribute", 1),
                (hub_names[0], "patient", 1),
            ]
        )
        assert tree._find_hub_for_lexeme(lex) == hub_names[0]

    def test_attribute_beats_theme(self):
        tree = MerkleLexiconTree()
        hub_names = list(tree.hubs.keys())
        if len(hub_names) < 2:
            pytest.skip("Need 2+ hubs")
        lex = make_lex(
            decomposition=[
                (hub_names[1], "theme", 1),
                (hub_names[0], "attribute", 1),
            ]
        )
        assert tree._find_hub_for_lexeme(lex) == hub_names[0]

    def test_result_is_always_a_known_hub(self):
        # Kills the LOGICAL `and` → `or` mutant.
        # If `and` becomes `or`, a non-hub primitive in role priority would
        # be returned. Asserting result is in self.hubs catches that.
        tree = MerkleLexiconTree()
        lex = make_lex(decomposition=[("NOT_A_HUB", "agent", 1)])
        result = tree._find_hub_for_lexeme(lex)
        assert result in tree.hubs

    def test_first_role_match_wins_over_later_in_decomposition(self):
        tree = MerkleLexiconTree()
        hub_names = list(tree.hubs.keys())
        if len(hub_names) < 2:
            pytest.skip("Need 2+ hubs")
        # Two prims with same role 'agent' — first one in decomposition wins
        lex = make_lex(
            decomposition=[
                (hub_names[0], "agent", 1),
                (hub_names[1], "agent", 1),
            ]
        )
        assert tree._find_hub_for_lexeme(lex) == hub_names[0]


# ---------- _get_fallback_hub ----------


class TestGetFallbackHub:
    def test_returns_family_hub_when_prim_in_family(self):
        tree = MerkleLexiconTree()
        # Pick a primitive that is in some family
        for family in tree.families.values():
            if family.member_primitives:
                prim = next(iter(family.member_primitives))
                lex = make_lex(decomposition=[(prim, "weird", 1)])
                result = tree._get_fallback_hub(lex)
                assert result == family.hub_primitive
                return
        pytest.skip("No families with member primitives")

    def test_unknown_returns_first_hub(self):
        tree = MerkleLexiconTree()
        first_hub = list(tree.hubs.keys())[0]
        lex = make_lex(decomposition=[("XYZZY_UNK_PRIM", "weird", 1)])
        result = tree._get_fallback_hub(lex)
        # When no family contains the primitive, returns first hub
        assert result == first_hub


# ---------- add_lexemes_batch ----------


class TestAddLexemesBatch:
    def test_returns_count_added(self):
        tree = MerkleLexiconTree()
        lexemes = [
            make_lex(lemma="word1"),
            make_lex(lemma="word2"),
            make_lex(lemma="word3"),
        ]
        added = tree.add_lexemes_batch(lexemes)
        assert added == 3
        assert len(tree.lexemes) == 3

    def test_empty_batch_returns_zero(self):
        tree = MerkleLexiconTree()
        assert tree.add_lexemes_batch([]) == 0

    def test_duplicates_not_double_counted(self):
        tree = MerkleLexiconTree()
        lex1 = make_lex(lemma="word")
        lex2 = make_lex(lemma="word")  # same key
        added = tree.add_lexemes_batch([lex1, lex2])
        assert added == 1
        assert len(tree.lexemes) == 1


# ---------- Lookup ----------


class TestGetLexeme:
    def test_known(self):
        tree = MerkleLexiconTree()
        lex = make_lex()
        tree.add_lexeme(lex)
        assert tree.get_lexeme(lex.key) is lex

    def test_unknown_returns_none(self):
        tree = MerkleLexiconTree()
        assert tree.get_lexeme("nonexistent_x_01") is None


class TestGetLexemesByHub:
    def test_unknown_hub_returns_empty(self):
        tree = MerkleLexiconTree()
        assert tree.get_lexemes_by_hub("XYZZY") == []

    def test_known_hub_returns_lexemes(self):
        tree = MerkleLexiconTree()
        lex = make_lex()
        tree.add_lexeme(lex)
        # lex's parent_hub should now contain it
        result = tree.get_lexemes_by_hub(lex.parent_hub)
        assert lex in result


class TestGetLexemesByFamily:
    def test_unknown_returns_empty(self):
        tree = MerkleLexiconTree()
        assert tree.get_lexemes_by_family("XYZZY_FAM") == []

    def test_known_family(self):
        tree = MerkleLexiconTree()
        lex = make_lex()
        tree.add_lexeme(lex)
        # Find which family the lex went into
        hub = lex.parent_hub
        family_id = tree._hub_to_family[hub]
        result = tree.get_lexemes_by_family(family_id)
        assert lex in result


class TestGetLexemesByBank:
    def test_unknown_returns_empty(self):
        tree = MerkleLexiconTree()
        assert tree.get_lexemes_by_bank(999) == []

    def test_known_bank(self):
        tree = MerkleLexiconTree()
        lex = make_lex()
        tree.add_lexeme(lex)
        # Find which bank the lex went into
        family_id = tree._hub_to_family[lex.parent_hub]
        bank_id = tree._family_to_bank[family_id]
        result = tree.get_lexemes_by_bank(bank_id)
        assert lex in result


class TestIterLexemes:
    def test_iterates_all(self):
        tree = MerkleLexiconTree()
        lex1 = make_lex(lemma="a")
        lex2 = make_lex(lemma="b")
        tree.add_lexeme(lex1)
        tree.add_lexeme(lex2)
        result = list(tree.iter_lexemes())
        assert len(result) == 2


# ---------- Verification ----------


class TestGetRootHash:
    def test_returns_combined_hash(self):
        tree = MerkleLexiconTree()
        assert tree.get_root_hash() == tree.root.combined_hash


class TestVerifyIntegrity:
    def test_clean_tree_passes(self):
        tree = MerkleLexiconTree()
        tree.add_lexeme(make_lex())
        is_valid, errors = tree.verify_integrity()
        assert is_valid is True
        assert errors == []


class TestGetMembershipProof:
    def test_known_returns_proof(self):
        tree = MerkleLexiconTree()
        lex = make_lex()
        tree.add_lexeme(lex)
        proof = tree.get_membership_proof(lex.key)
        assert proof is not None
        assert proof.lexeme_hash == lex.combined_hash
        assert proof.root_hash == tree.root.combined_hash

    def test_unknown_returns_none(self):
        tree = MerkleLexiconTree()
        assert tree.get_membership_proof("nonexistent") is None


# ---------- Diff ----------


class TestComputeDiff:
    def test_identical_trees_no_diff(self):
        t1 = MerkleLexiconTree()
        t2 = MerkleLexiconTree()
        diff = t1.compute_diff(t2)
        assert diff.added_lexemes == []
        assert diff.removed_lexemes == []
        assert diff.modified_lexemes == []

    def test_added_in_other(self):
        t1 = MerkleLexiconTree()
        t2 = MerkleLexiconTree()
        t2.add_lexeme(make_lex(lemma="new"))
        diff = t1.compute_diff(t2)
        assert "new_adj_01" in diff.added_lexemes

    def test_removed_in_other(self):
        t1 = MerkleLexiconTree()
        t1.add_lexeme(make_lex(lemma="old"))
        t2 = MerkleLexiconTree()
        diff = t1.compute_diff(t2)
        assert "old_adj_01" in diff.removed_lexemes

    def test_modified_lexeme(self):
        t1 = MerkleLexiconTree()
        t1.add_lexeme(make_lex(lemma="x", gloss="A"))
        t2 = MerkleLexiconTree()
        t2.add_lexeme(make_lex(lemma="x", gloss="B"))
        diff = t1.compute_diff(t2)
        assert "x_adj_01" in diff.modified_lexemes


# ---------- Serialization ----------


class TestToDict:
    def test_includes_root_hash(self):
        tree = MerkleLexiconTree()
        d = tree.to_dict()
        assert d["root_hash"] == tree.root.combined_hash
        assert d["total_lexemes"] == 0

    def test_includes_lexemes(self):
        tree = MerkleLexiconTree()
        lex = make_lex()
        tree.add_lexeme(lex)
        d = tree.to_dict()
        assert lex.key in d["lexemes"]

    def test_all_top_level_keys_present(self):
        tree = MerkleLexiconTree()
        d = tree.to_dict()
        assert set(d.keys()) == {"root_hash", "total_lexemes", "banks", "families", "hubs", "lexemes"}

    def test_total_lexemes_matches_count(self):
        tree = MerkleLexiconTree()
        for i in range(3):
            tree.add_lexeme(make_lex(lemma=f"word{i}"))
        d = tree.to_dict()
        assert d["total_lexemes"] == 3

    def test_banks_entries_have_hash_and_count(self):
        tree = MerkleLexiconTree()
        d = tree.to_dict()
        for bank_id, info in d["banks"].items():
            assert set(info.keys()) == {"hash", "lexeme_count"}
            assert info["hash"] == tree.banks[bank_id].combined_hash
            assert info["lexeme_count"] == tree.banks[bank_id].lexeme_count

    def test_families_entries_have_hash_and_count(self):
        tree = MerkleLexiconTree()
        d = tree.to_dict()
        for fid, info in d["families"].items():
            assert info["hash"] == tree.families[fid].combined_hash
            assert info["lexeme_count"] == tree.families[fid].lexeme_count

    def test_hubs_entries_have_hash_and_count(self):
        tree = MerkleLexiconTree()
        d = tree.to_dict()
        for hub_name, info in d["hubs"].items():
            assert info["hash"] == tree.hubs[hub_name].combined_hash
            assert info["lexeme_count"] == tree.hubs[hub_name].lexeme_count

    def test_lexemes_serialized_via_to_dict(self):
        tree = MerkleLexiconTree()
        lex = make_lex(gloss="testing gloss")
        tree.add_lexeme(lex)
        d = tree.to_dict()
        # Lexeme's to_dict result is what's stored
        assert d["lexemes"][lex.key] == lex.to_dict()

    def test_lex_counts_track_actual_lexemes(self):
        tree = MerkleLexiconTree()
        tree.add_lexeme(make_lex())
        d = tree.to_dict()
        # Sum of bank lexeme_count == total_lexemes
        bank_total = sum(b["lexeme_count"] for b in d["banks"].values())
        assert bank_total == 1


class TestSaveLoad:
    def test_roundtrip(self, tmp_path):
        t1 = MerkleLexiconTree()
        t1.add_lexeme(make_lex(lemma="happy"))
        t1.add_lexeme(make_lex(lemma="sad", decomposition=[("BAD", "attribute", 1)]))

        path = str(tmp_path / "tree.json")
        t1.save(path)

        t2 = MerkleLexiconTree.load(path)
        assert len(t2.lexemes) == 2
        assert "happy_adj_01" in t2.lexemes
        assert "sad_adj_01" in t2.lexemes

    def test_save_writes_valid_json(self, tmp_path):
        tree = MerkleLexiconTree()
        path = str(tmp_path / "tree.json")
        tree.save(path)
        with open(path) as f:
            data = json.load(f)
        assert "root_hash" in data


# ---------- Statistics ----------


class TestGetStatistics:
    def test_basic_fields(self):
        tree = MerkleLexiconTree()
        stats = tree.get_statistics()
        assert stats["total_lexemes"] == 0
        assert stats["banks"] == 8
        assert "root_hash" in stats

    def test_with_lexemes(self):
        tree = MerkleLexiconTree()
        tree.add_lexeme(make_lex())
        stats = tree.get_statistics()
        assert stats["total_lexemes"] == 1
        # Lexeme should appear in some hub
        assert any(c > 0 for c in stats["lexemes_per_hub"].values())


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
