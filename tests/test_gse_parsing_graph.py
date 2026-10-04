"""Manual contract tests for gse.parsing.graph."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.lexicon.word_encoding import (
    ComponentType,
    GrammaticalFeatures,
    GramRole,
    LexemeEntry,
)
from gse.parsing.graph import EdgeType, ParseEdge, ParseGraph, ParseNode
from gse.vectors_v2 import SparseVector


def make_vec():
    return SparseVector(
        dimension=8192,
        positive_indices=np.array([0], dtype=np.uint16),
        negative_indices=np.array([], dtype=np.uint16),
    )


def make_lexeme(lemma="word", surface=None, roles=None):
    return LexemeEntry(
        lemma=lemma,
        surface_form=surface or lemma,
        semantic_vector=make_vec(),
        possible_roles=frozenset([GramRole.NOUN] if roles is None else roles),
        gram_features=GrammaticalFeatures(),
        component_type=ComponentType.ATOMIC,
    )


# ============================================================
# ParseNode
# ============================================================


class TestParseNodePostInit:
    def test_initializes_possible_roles_from_lexeme(self):
        lex = make_lexeme(roles=[GramRole.NOUN, GramRole.VERB])
        node = ParseNode(position=0, lexeme=lex)
        assert node.possible_roles == {GramRole.NOUN, GramRole.VERB}

    def test_preserves_explicit_possible_roles(self):
        lex = make_lexeme(roles=[GramRole.NOUN])
        node = ParseNode(position=0, lexeme=lex, possible_roles={GramRole.ADJ})
        assert node.possible_roles == {GramRole.ADJ}

    def test_no_lexeme_keeps_empty_roles(self):
        lex = make_lexeme(roles=[])
        node = ParseNode(position=0, lexeme=lex)
        assert node.possible_roles == set()


class TestParseNodeProperties:
    def test_word_returns_surface_form(self):
        lex = make_lexeme(lemma="run", surface="ran")
        node = ParseNode(position=0, lexeme=lex)
        assert node.word == "ran"

    def test_lemma_returns_lemma(self):
        lex = make_lexeme(lemma="run", surface="ran")
        node = ParseNode(position=0, lexeme=lex)
        assert node.lemma == "run"


class TestHasRole:
    def test_present_role_returns_true(self):
        lex = make_lexeme(roles=[GramRole.NOUN, GramRole.VERB])
        node = ParseNode(position=0, lexeme=lex)
        assert node.has_role(GramRole.NOUN)
        assert node.has_role(GramRole.VERB)

    def test_absent_role_returns_false(self):
        lex = make_lexeme(roles=[GramRole.NOUN])
        node = ParseNode(position=0, lexeme=lex)
        assert not node.has_role(GramRole.VERB)


class TestAssignRole:
    def test_valid_role_assigns(self):
        lex = make_lexeme(roles=[GramRole.NOUN])
        node = ParseNode(position=0, lexeme=lex)
        node.assign_role(GramRole.NOUN)
        assert node.assigned_role == GramRole.NOUN

    def test_invalid_role_raises(self):
        lex = make_lexeme(roles=[GramRole.NOUN])
        node = ParseNode(position=0, lexeme=lex)
        with pytest.raises(ValueError, match="Cannot assign role"):
            node.assign_role(GramRole.VERB)


class TestPruneRoles:
    def test_pruning_removes_unmatched_roles(self):
        lex = make_lexeme(roles=[GramRole.NOUN, GramRole.VERB, GramRole.ADJ])
        node = ParseNode(position=0, lexeme=lex)
        changed = node.prune_roles({GramRole.NOUN})
        assert node.possible_roles == {GramRole.NOUN}
        assert changed is True

    def test_pruning_no_change_returns_false(self):
        lex = make_lexeme(roles=[GramRole.NOUN])
        node = ParseNode(position=0, lexeme=lex)
        changed = node.prune_roles({GramRole.NOUN, GramRole.VERB})
        assert not changed
        assert node.possible_roles == {GramRole.NOUN}

    def test_pruning_to_empty(self):
        lex = make_lexeme(roles=[GramRole.NOUN])
        node = ParseNode(position=0, lexeme=lex)
        changed = node.prune_roles(set())
        assert changed
        assert node.possible_roles == set()


# ============================================================
# ParseEdge
# ============================================================


class TestParseEdgeDirection:
    def test_forward_edge(self):
        e = ParseEdge(source=0, target=3, edge_type=EdgeType.SUBJECT)
        assert e.is_forward
        assert not e.is_backward

    def test_backward_edge(self):
        e = ParseEdge(source=5, target=2, edge_type=EdgeType.MODIFIER)
        assert e.is_backward
        assert not e.is_forward

    def test_self_edge_neither(self):
        e = ParseEdge(source=2, target=2, edge_type=EdgeType.SUBJECT)
        assert not e.is_forward
        assert not e.is_backward


class TestParseEdgeDistance:
    @pytest.mark.parametrize(
        "source,target,expected",
        [
            (0, 5, 5),
            (5, 0, 5),
            (3, 3, 0),
            (10, 7, 3),
            (0, 1, 1),
        ],
    )
    def test_distance(self, source, target, expected):
        e = ParseEdge(source=source, target=target, edge_type=EdgeType.SUBJECT)
        assert e.distance == expected


# ============================================================
# ParseGraph
# ============================================================


def make_graph(num_words=3):
    nodes = []
    for i in range(num_words):
        lex = make_lexeme(lemma=f"w{i}", surface=f"w{i}")
        nodes.append(ParseNode(position=i, lexeme=lex))
    return ParseGraph(nodes=nodes)


class TestParseGraphLen:
    def test_empty_graph_len_zero(self):
        assert len(ParseGraph()) == 0

    def test_len_matches_node_count(self):
        g = make_graph(5)
        assert len(g) == 5


class TestGetNode:
    def test_valid_position_returns_node(self):
        g = make_graph(3)
        node = g.get_node(1)
        assert node.position == 1

    def test_out_of_range_raises(self):
        g = make_graph(3)
        with pytest.raises(IndexError):
            g.get_node(5)

    def test_negative_position_raises(self):
        g = make_graph(3)
        with pytest.raises(IndexError):
            g.get_node(-1)


class TestEdgeAccessors:
    def test_get_edges_from(self):
        g = make_graph(3)
        g.add_edge(0, 1, EdgeType.SUBJECT)
        g.add_edge(0, 2, EdgeType.OBJECT)
        g.add_edge(1, 2, EdgeType.MODIFIER)
        from_0 = g.get_edges_from(0)
        assert len(from_0) == 2
        assert all(e.source == 0 for e in from_0)

    def test_get_edges_to(self):
        g = make_graph(3)
        g.add_edge(0, 2, EdgeType.SUBJECT)
        g.add_edge(1, 2, EdgeType.OBJECT)
        g.add_edge(0, 1, EdgeType.MODIFIER)
        to_2 = g.get_edges_to(2)
        assert len(to_2) == 2
        assert all(e.target == 2 for e in to_2)

    def test_get_edges_from_no_edges(self):
        g = make_graph(2)
        assert g.get_edges_from(0) == []

    def test_get_edge_found(self):
        g = make_graph(3)
        g.add_edge(0, 1, EdgeType.SUBJECT)
        edge = g.get_edge(0, 1)
        assert edge is not None
        assert edge.edge_type == EdgeType.SUBJECT

    def test_get_edge_not_found(self):
        g = make_graph(3)
        g.add_edge(0, 1, EdgeType.SUBJECT)
        assert g.get_edge(0, 2) is None
        assert g.get_edge(1, 0) is None


class TestAddEdge:
    def test_appends_edge(self):
        g = make_graph(2)
        g.add_edge(0, 1, EdgeType.SUBJECT)
        assert len(g.edges) == 1

    def test_returns_edge_object(self):
        g = make_graph(2)
        edge = g.add_edge(0, 1, EdgeType.SUBJECT, weight=0.5)
        assert isinstance(edge, ParseEdge)
        assert edge.weight == 0.5
        assert edge.edge_type == EdgeType.SUBJECT


class TestGetSubject:
    def test_returns_subject_node(self):
        g = make_graph(3)
        g.add_edge(0, 1, EdgeType.SUBJECT)
        subj = g.get_subject()
        assert subj is not None
        assert subj.position == 0

    def test_no_subject_returns_none(self):
        g = make_graph(2)
        g.add_edge(0, 1, EdgeType.OBJECT)
        assert g.get_subject() is None

    def test_empty_graph_returns_none(self):
        g = ParseGraph()
        assert g.get_subject() is None


class TestGetPredicate:
    def test_returns_predicate_node(self):
        g = make_graph(3)
        g.add_edge(0, 1, EdgeType.SUBJECT)
        pred = g.get_predicate()
        assert pred is not None
        assert pred.position == 1

    def test_no_subject_edge_no_predicate(self):
        g = make_graph(2)
        g.add_edge(0, 1, EdgeType.OBJECT)
        assert g.get_predicate() is None


class TestGetObject:
    def test_returns_object_node(self):
        g = make_graph(3)
        g.add_edge(1, 2, EdgeType.OBJECT)
        obj = g.get_object()
        assert obj is not None
        assert obj.position == 2

    def test_no_object_returns_none(self):
        g = make_graph(2)
        g.add_edge(0, 1, EdgeType.SUBJECT)
        assert g.get_object() is None


class TestGetModifiers:
    def test_returns_modifier_nodes(self):
        g = make_graph(4)
        g.add_edge(0, 2, EdgeType.MODIFIER)
        g.add_edge(1, 2, EdgeType.MODIFIER)
        g.add_edge(3, 2, EdgeType.OBJECT)
        modifiers = g.get_modifiers(2)
        positions = {n.position for n in modifiers}
        assert positions == {0, 1}

    def test_empty_when_no_modifiers(self):
        g = make_graph(2)
        assert g.get_modifiers(0) == []


class TestToDict:
    def test_serializes_nodes_and_edges(self):
        g = make_graph(2)
        g.nodes[0].assigned_role = GramRole.NOUN
        g.nodes[0].pending_sign = -1
        g.nodes[0].hierarchy_level = 1
        g.add_edge(0, 1, EdgeType.SUBJECT, weight=0.8)

        d = g.to_dict()
        assert len(d["nodes"]) == 2
        assert d["nodes"][0]["position"] == 0
        assert d["nodes"][0]["word"] == "w0"
        assert d["nodes"][0]["lemma"] == "w0"
        assert d["nodes"][0]["assigned_role"] == "NOUN"
        assert d["nodes"][0]["pending_sign"] == -1
        assert d["nodes"][0]["hierarchy_level"] == 1
        assert len(d["edges"]) == 1
        assert d["edges"][0]["source"] == 0
        assert d["edges"][0]["target"] == 1
        assert d["edges"][0]["edge_type"] == "SUBJECT"
        assert d["edges"][0]["weight"] == 0.8

    def test_no_role_serializes_as_none(self):
        g = make_graph(1)
        d = g.to_dict()
        assert d["nodes"][0]["assigned_role"] is None


class TestPrettyPrint:
    def test_includes_header(self):
        g = make_graph(1)
        output = g.pretty_print()
        assert "Parse Graph" in output

    def test_includes_node_word(self):
        g = make_graph(2)
        output = g.pretty_print()
        assert "w0" in output
        assert "w1" in output

    def test_includes_edge_type(self):
        g = make_graph(2)
        g.add_edge(0, 1, EdgeType.SUBJECT)
        output = g.pretty_print()
        assert "SUBJECT" in output

    def test_negation_marker(self):
        g = make_graph(1)
        g.nodes[0].pending_sign = -1
        output = g.pretty_print()
        assert "[NEG]" in output

    def test_hierarchy_marker(self):
        g = make_graph(1)
        g.nodes[0].hierarchy_level = 2
        output = g.pretty_print()
        assert "[HIER" in output

    def test_no_markers_when_default(self):
        g = make_graph(1)
        output = g.pretty_print()
        assert "[NEG]" not in output
        assert "[HIER" not in output


# ============================================================
# Mutation-prescribed additional tests
# ============================================================


class TestGetNodeBoundary:
    """Catch BOUNDARY mutations on `0 <= position < len(nodes)`."""

    def test_position_zero_in_non_empty_graph_works(self):
        g = make_graph(3)
        node = g.get_node(0)
        assert node.position == 0

    def test_position_last_in_range(self):
        g = make_graph(3)
        node = g.get_node(2)
        assert node.position == 2

    def test_position_equal_to_len_raises(self):
        g = make_graph(3)
        with pytest.raises(IndexError):
            g.get_node(3)

    def test_position_one_past_end_raises(self):
        g = make_graph(5)
        with pytest.raises(IndexError):
            g.get_node(5)

    def test_position_negative_one_raises(self):
        g = make_graph(3)
        with pytest.raises(IndexError):
            g.get_node(-1)


class TestAssignRoleErrorMessage:
    def test_error_message_contains_role_name(self):
        lex = make_lexeme(roles=[GramRole.NOUN])
        node = ParseNode(position=0, lexeme=lex)
        with pytest.raises(ValueError, match="VERB") as exc_info:
            node.assign_role(GramRole.VERB)
        assert "Cannot assign role" in str(exc_info.value)


class TestHasRoleExact:
    """Catches VALUE mutation on the membership test."""

    def test_returns_bool_true(self):
        lex = make_lexeme(roles=[GramRole.NOUN])
        node = ParseNode(position=0, lexeme=lex)
        result = node.has_role(GramRole.NOUN)
        assert result is True

    def test_returns_bool_false(self):
        lex = make_lexeme(roles=[GramRole.NOUN])
        node = ParseNode(position=0, lexeme=lex)
        result = node.has_role(GramRole.VERB)
        assert result is False


class TestPruneRolesReturnsBool:
    def test_returns_true_when_changed(self):
        lex = make_lexeme(roles=[GramRole.NOUN, GramRole.VERB])
        node = ParseNode(position=0, lexeme=lex)
        result = node.prune_roles({GramRole.NOUN})
        assert result is True

    def test_returns_false_when_unchanged(self):
        lex = make_lexeme(roles=[GramRole.NOUN])
        node = ParseNode(position=0, lexeme=lex)
        result = node.prune_roles({GramRole.NOUN, GramRole.VERB})
        assert result is False


class TestPrettyPrintLiterals:
    """Catches VALUE mutations on specific string literals in pretty_print output."""

    def test_includes_nodes_header(self):
        g = make_graph(1)
        output = g.pretty_print()
        assert "Nodes:" in output

    def test_includes_edges_header(self):
        g = make_graph(2)
        g.add_edge(0, 1, EdgeType.SUBJECT)
        output = g.pretty_print()
        assert "Edges:" in output

    def test_question_mark_for_unassigned_role(self):
        g = make_graph(1)
        # node.assigned_role is None by default
        output = g.pretty_print()
        # The role_str should be "?" when no role assigned
        assert "?" in output

    def test_assigned_role_appears(self):
        g = make_graph(1)
        g.nodes[0].assigned_role = GramRole.NOUN
        output = g.pretty_print()
        assert "NOUN" in output

    def test_negation_marker_exact(self):
        g = make_graph(1)
        g.nodes[0].pending_sign = -1
        output = g.pretty_print()
        assert "[NEG]" in output

    def test_no_negation_marker_when_positive(self):
        g = make_graph(1)
        g.nodes[0].pending_sign = 1
        output = g.pretty_print()
        # Only -1 produces the [NEG] marker per the code
        assert "[NEG]" not in output

    def test_hierarchy_positive_signed(self):
        g = make_graph(1)
        g.nodes[0].hierarchy_level = 2
        output = g.pretty_print()
        assert "+2" in output

    def test_hierarchy_negative_signed(self):
        g = make_graph(1)
        g.nodes[0].hierarchy_level = -3
        output = g.pretty_print()
        assert "-3" in output

    def test_position_appears(self):
        g = make_graph(3)
        output = g.pretty_print()
        assert "0:" in output
        assert "1:" in output
        assert "2:" in output

    def test_edge_arrow_format(self):
        g = make_graph(2)
        g.add_edge(0, 1, EdgeType.SUBJECT)
        output = g.pretty_print()
        assert "--SUBJECT-->" in output


class TestToDictEdgeType:
    """Catches the edge_type.name serialization."""

    @pytest.mark.parametrize(
        "edge_type,name",
        [
            (EdgeType.SUBJECT, "SUBJECT"),
            (EdgeType.OBJECT, "OBJECT"),
            (EdgeType.MODIFIER, "MODIFIER"),
            (EdgeType.DETERMINER, "DETERMINER"),
            (EdgeType.AUXILIARY, "AUXILIARY"),
        ],
    )
    def test_edge_type_name_in_dict(self, edge_type, name):
        g = make_graph(2)
        g.add_edge(0, 1, edge_type)
        d = g.to_dict()
        assert d["edges"][0]["edge_type"] == name


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
