import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from gse.graph.builder import GraphBuilder
from gse.graph.semantic_graph import EdgeType
from gse.graph.traversal import HierarchicalTraversal
from gse.vectors import SparseVector

from gse.scales import DiscourseScale, SyntacticScale, TextualScale


class TestGraph:
    """Test Semantic Graph and Builder."""

    @pytest.fixture
    def mock_lexicon_db(self, tmp_path):
        db_path = tmp_path / "graph_lexicon.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE lexicon (lemma TEXT, pos TEXT, decomposition TEXT, frequency REAL)")

        # Add "doctor" -> PERSON, HEAL
        doc = json.dumps([("PERSON", "agent"), ("HEAL", "action")])
        conn.execute("INSERT INTO lexicon VALUES (?, ?, ?, ?)", ("doctor", "noun", doc, 0.5))

        # Add "nurse" -> PERSON, HEAL
        nurse = json.dumps([("PERSON", "agent"), ("HEAL", "action")])
        conn.execute("INSERT INTO lexicon VALUES (?, ?, ?, ?)", ("nurse", "noun", nurse, 0.4))

        # Add "apple" -> FRUIT (assume valid primitive for test or mock it)
        # Using standard primitives: "SOMETHING", "GOOD"
        apple = json.dumps([("SOMETHING", "agent"), ("GOOD", "evaluation")])
        conn.execute("INSERT INTO lexicon VALUES (?, ?, ?, ?)", ("apple", "noun", apple, 0.6))

        conn.commit()
        conn.close()
        return str(db_path)

    def test_build_graph(self, mock_lexicon_db):
        builder = GraphBuilder(primitives=["PERSON", "HEAL", "SOMETHING", "GOOD"])
        graph = builder.build(mock_lexicon_db)

        # Check nodes
        assert "doctor.noun" in graph.nodes
        assert "PERSON" in graph.nodes

        # Check edges
        edges = graph.get_neighbors("doctor.noun")
        targets = {e.target for e in edges if e.type == EdgeType.DECOMPOSES_TO}
        assert "PERSON" in targets
        assert "HEAL" in targets

    def test_traversal_distance(self, mock_lexicon_db):
        builder = GraphBuilder(primitives=["PERSON", "HEAL", "SOMETHING", "GOOD"])
        graph = builder.build(mock_lexicon_db)
        trav = HierarchicalTraversal(graph)

        # doctor and nurse share ALL primitives -> distance 0
        dist_dn = trav.semantic_distance("doctor.noun", "nurse.noun")
        assert dist_dn < 0.1

        # doctor and apple share NO primitives -> distance 1.0
        dist_da = trav.semantic_distance("doctor.noun", "apple.noun")
        assert dist_da > 0.9


class TestScales:
    """Test Multi-Scale Encoders."""

    def test_discourse_coherence(self):
        scale = DiscourseScale()

        # Create vectors
        v1 = SparseVector.zeros(100)
        v1.positive_indices = [1, 2, 3]

        v2 = SparseVector.zeros(100)
        v2.positive_indices = [1, 2, 4]  # distinct but similar

        v3 = SparseVector.zeros(100)
        v3.positive_indices = [50, 60]  # orthogonal

        # v1 and v2 are similar
        coh = scale.measure_coherence([v1, v2])
        assert coh > 0.5

        # Detect shift
        shifts = scale.identify_topic_shifts([v1, v2, v3], threshold=0.1)
        # v1-v2 coherent. v2-v3 not. Shift at index 2 (v3)
        assert 2 in shifts

    def test_textual_theme(self):
        scale = TextualScale()
        # Mock vector dominated by Bank 0 (indices 0-100)
        v = SparseVector.zeros(800)  # 8 banks of 100
        v.positive_indices = list(range(0, 50))

        themes = scale.extract_theme(v, n_banks=8)
        assert themes[0] > 0
        assert themes[1] == 0

    @patch("gse.scales.syntactic.spacy")
    def test_syntactic_encoding(self, mock_spacy):
        # Mock LexicalScale
        mock_lex = MagicMock()
        mock_lex.encode.return_value = SparseVector.zeros(8192)

        # Mock spaCy behavior
        mock_nlp = MagicMock()
        mock_doc = MagicMock()
        mock_token = MagicMock()
        mock_token.pos_ = "NOUN"
        mock_token.lemma_ = "dog"
        mock_token.dep_ = "nsubj"  # agent -> shift 0

        mock_doc.__iter__.return_value = [mock_token]
        mock_nlp.return_value = mock_doc

        # Set up scale with mock nlp
        scale = SyntacticScale(mock_lex)
        scale.nlp = mock_nlp

        vec = scale.encode("The dog barks.")
        assert vec is not None
        mock_lex.encode.assert_called()
