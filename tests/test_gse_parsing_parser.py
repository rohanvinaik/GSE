"""Manual contract tests for gse.parsing.parser."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.lexicon.word_encoding import (
    BindingBehavior,
    ComponentType,
    GrammaticalFeatures,
    GramRole,
    LexemeEntry,
    OperatorSpec,
    OperatorType,
)
from gse.parsing.graph import EdgeType
from gse.parsing.parser import SentenceParser
from gse.vectors_v2 import SparseVector


def make_vec():
    return SparseVector(
        dimension=8192,
        positive_indices=np.array([0], dtype=np.uint16),
        negative_indices=np.array([], dtype=np.uint16),
    )


def make_lex(lemma, roles, component_type=ComponentType.ATOMIC, op_spec=None):
    return LexemeEntry(
        lemma=lemma,
        surface_form=lemma,
        semantic_vector=make_vec(),
        possible_roles=frozenset(roles),
        gram_features=GrammaticalFeatures(),
        component_type=component_type,
        operator_spec=op_spec,
    )


class TestParserInit:
    def test_no_lexicon_raises_on_lookup(self):
        parser = SentenceParser()
        with pytest.raises(ValueError, match="No lexicon"):
            parser._lookup("word")

    def test_lookup_func_used_when_set(self):
        parser = SentenceParser(lookup_func=lambda t: make_lex(t, [GramRole.NOUN]))
        result = parser._lookup("dog")
        assert result.lemma == "dog"

    def test_lexicon_used_when_set(self):
        class FakeLex:
            def lookup(self, t):
                return make_lex(t, [GramRole.NOUN])

        parser = SentenceParser(lexicon=FakeLex())
        assert parser._lookup("x").lemma == "x"

    def test_lookup_func_priority_over_lexicon(self):
        class FakeLex:
            def lookup(self, t):
                return make_lex("from-lexicon", [GramRole.NOUN])

        parser = SentenceParser(
            lexicon=FakeLex(),
            lookup_func=lambda t: make_lex("from-func", [GramRole.NOUN]),
        )
        assert parser._lookup("x").lemma == "from-func"


class TestParseBasic:
    def test_empty_token_list(self):
        parser = SentenceParser(lookup_func=lambda t: make_lex(t, [GramRole.NOUN]))
        graph = parser.parse([])
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_single_token(self):
        parser = SentenceParser(lookup_func=lambda t: make_lex(t, [GramRole.NOUN]))
        graph = parser.parse(["dog"])
        assert len(graph.nodes) == 1
        assert graph.nodes[0].lemma == "dog"

    def test_assigns_roles(self):
        parser = SentenceParser(lookup_func=lambda t: make_lex(t, [GramRole.NOUN]))
        graph = parser.parse(["dog", "cat"])
        for node in graph.nodes:
            assert node.assigned_role == GramRole.NOUN


class TestParseWithLexemes:
    def test_skips_lookup(self):
        parser = SentenceParser()  # no lexicon needed
        lexemes = [make_lex("dog", [GramRole.NOUN]), make_lex("cat", [GramRole.NOUN])]
        graph = parser.parse_with_lexemes(lexemes)
        assert len(graph.nodes) == 2

    def test_assigns_roles_correctly(self):
        parser = SentenceParser()
        lexemes = [
            make_lex("the", [GramRole.DET]),
            make_lex("dog", [GramRole.NOUN]),
            make_lex("ran", [GramRole.VERB]),
        ]
        graph = parser.parse_with_lexemes(lexemes)
        assert graph.nodes[0].assigned_role == GramRole.DET
        assert graph.nodes[1].assigned_role == GramRole.NOUN
        assert graph.nodes[2].assigned_role == GramRole.VERB

    def test_constructs_subject_edge(self):
        parser = SentenceParser()
        lexemes = [make_lex("dog", [GramRole.NOUN]), make_lex("ran", [GramRole.VERB])]
        graph = parser.parse_with_lexemes(lexemes)
        subj_edges = [e for e in graph.edges if e.edge_type == EdgeType.SUBJECT]
        assert len(subj_edges) == 1

    def test_constructs_object_edge(self):
        parser = SentenceParser()
        lexemes = [
            make_lex("dog", [GramRole.NOUN]),
            make_lex("ate", [GramRole.VERB]),
            make_lex("food", [GramRole.NOUN]),
        ]
        graph = parser.parse_with_lexemes(lexemes)
        obj_edges = [e for e in graph.edges if e.edge_type == EdgeType.OBJECT]
        assert len(obj_edges) >= 1

    def test_constructs_determiner_edge(self):
        parser = SentenceParser()
        lexemes = [make_lex("the", [GramRole.DET]), make_lex("dog", [GramRole.NOUN])]
        graph = parser.parse_with_lexemes(lexemes)
        det_edges = [e for e in graph.edges if e.edge_type == EdgeType.DETERMINER]
        assert len(det_edges) == 1

    def test_auxiliary_edge_when_aux_precedes_verb(self):
        parser = SentenceParser()
        did = make_lex(
            "did",
            [GramRole.AUX],
            component_type=ComponentType.OPERATOR,
            op_spec=OperatorSpec(
                op_type=OperatorType.AUXILIARY,
                binding=BindingBehavior.LAZY,
                seeks=frozenset({GramRole.VERB}),
            ),
        )
        run = make_lex("run", [GramRole.VERB])
        graph = parser.parse_with_lexemes([did, run])
        aux_edges = [e for e in graph.edges if e.edge_type == EdgeType.AUXILIARY]
        assert len(aux_edges) == 1


class TestConstraintPropagation:
    def test_det_followed_by_verb_prunes(self):
        """The DET → VERB transition is not allowed, so the next node loses VERB."""
        parser = SentenceParser()
        lexemes = [
            make_lex("the", [GramRole.DET]),
            make_lex("ambig", [GramRole.NOUN, GramRole.VERB]),  # both possible
        ]
        graph = parser.parse_with_lexemes(lexemes)
        # After constraint propagation, VERB should be pruned from position 1
        assert GramRole.VERB not in graph.nodes[1].possible_roles
        assert GramRole.NOUN in graph.nodes[1].possible_roles

    def test_short_sentence_no_pruning(self):
        """Single-node graph isn't pruned."""
        parser = SentenceParser()
        graph = parser.parse_with_lexemes([make_lex("x", [GramRole.NOUN, GramRole.VERB])])
        assert graph.nodes[0].possible_roles == {GramRole.NOUN, GramRole.VERB}


class TestSelectRole:
    def test_atomic_noun_selected(self):
        parser = SentenceParser()
        graph = parser.parse_with_lexemes([make_lex("dog", [GramRole.NOUN])])
        assert graph.nodes[0].assigned_role == GramRole.NOUN

    def test_operator_auxiliary_prefers_aux(self):
        parser = SentenceParser()
        did = make_lex(
            "did",
            [GramRole.AUX, GramRole.VERB],
            component_type=ComponentType.OPERATOR,
            op_spec=OperatorSpec(
                op_type=OperatorType.AUXILIARY,
                binding=BindingBehavior.LAZY,
            ),
        )
        graph = parser.parse_with_lexemes([did, make_lex("run", [GramRole.VERB])])
        assert graph.nodes[0].assigned_role == GramRole.AUX

    def test_hybrid_prefers_verb(self):
        parser = SentenceParser()
        have = make_lex("have", [GramRole.VERB, GramRole.AUX], component_type=ComponentType.HYBRID)
        graph = parser.parse_with_lexemes([have])
        assert graph.nodes[0].assigned_role == GramRole.VERB

    def test_priority_order_noun_first(self):
        parser = SentenceParser()
        graph = parser.parse_with_lexemes([make_lex("x", [GramRole.PREP, GramRole.NOUN])])
        # NOUN comes before PREP in priority
        assert graph.nodes[0].assigned_role == GramRole.NOUN


class TestValidEdgeWindow:
    def test_determiner_within_window(self):
        parser = SentenceParser()
        # DET → NOUN with 0 gap (j-i = 1) — should work
        assert parser._valid_edge(0, 1, EdgeType.DETERMINER, [])

    def test_determiner_too_far(self):
        parser = SentenceParser()
        # DET → NOUN with j-i = 4 — too far
        assert not parser._valid_edge(0, 4, EdgeType.DETERMINER, [])

    def test_subject_forward(self):
        parser = SentenceParser()
        assert parser._valid_edge(0, 1, EdgeType.SUBJECT, [])
        assert not parser._valid_edge(2, 0, EdgeType.SUBJECT, [])

    def test_object_forward(self):
        parser = SentenceParser()
        assert parser._valid_edge(0, 1, EdgeType.OBJECT, [])
        assert not parser._valid_edge(2, 1, EdgeType.OBJECT, [])

    def test_auxiliary_forward(self):
        parser = SentenceParser()
        assert parser._valid_edge(0, 1, EdgeType.AUXILIARY, [])
        assert not parser._valid_edge(2, 0, EdgeType.AUXILIARY, [])

    def test_prep_obj_window(self):
        parser = SentenceParser()
        assert parser._valid_edge(0, 1, EdgeType.PREP_OBJ, [])
        assert not parser._valid_edge(0, 4, EdgeType.PREP_OBJ, [])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
