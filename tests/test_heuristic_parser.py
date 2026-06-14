"""Tests for the dependency-free HeuristicParser fallback in gse.parser."""

from unittest.mock import patch

import pytest

from gse.parser import (
    POS,
    HeuristicParser,
    ParsedSentence,
    POSTagger,
    make_parser,
)


@pytest.fixture
def parser():
    return HeuristicParser()


class TestPosTagging:
    def test_pronouns_tagged_as_pron(self, parser):
        sent = parser.parse_single("I see you")
        pos_map = {t.lemma: t.pos for t in sent.tokens}
        assert pos_map["i"] == POS.PRON
        assert pos_map["you"] == POS.PRON

    def test_determiners_tagged_as_det(self, parser):
        sent = parser.parse_single("the cat sat")
        pos_map = {t.lemma: t.pos for t in sent.tokens}
        assert pos_map["the"] == POS.DET

    def test_prepositions_tagged_as_adp(self, parser):
        sent = parser.parse_single("she sat on the mat")
        assert any(t.pos == POS.ADP and t.lemma == "on" for t in sent.tokens)

    def test_auxiliaries_tagged_as_aux(self, parser):
        sent = parser.parse_single("she is happy")
        assert any(t.pos == POS.AUX and t.lemma == "is" for t in sent.tokens)

    def test_adverb_ly_heuristic(self, parser):
        sent = parser.parse_single("she ran quickly")
        pos_map = {t.lemma: t.pos for t in sent.tokens}
        assert pos_map["quickly"] == POS.ADV

    def test_punctuation_tagged(self, parser):
        sent = parser.parse_single("hello, world!")
        assert any(t.pos == POS.PUNCT for t in sent.tokens)

    def test_default_unknown_word_falls_back_to_noun(self, parser):
        sent = parser.parse_single("blorp")
        assert sent.tokens[0].pos == POS.NOUN


class TestStructure:
    def test_returns_parsed_sentence(self, parser):
        out = parser.parse("She left.")
        assert all(isinstance(s, ParsedSentence) for s in out)

    def test_splits_on_terminal_punctuation(self, parser):
        sents = parser.parse("She left. He stayed.")
        assert len(sents) == 2

    def test_empty_text_returns_empty(self, parser):
        assert parser.parse("") == []

    def test_parse_single_raises_when_empty(self, parser):
        with pytest.raises(ValueError, match="Could not parse"):
            parser.parse_single("")

    def test_root_is_first_verb_when_present(self, parser):
        sent = parser.parse_single("the dog sat")
        # "sat" ends in 't' but our heuristic flags -ed and -ing — "sat" stays NOUN
        # but at least one VERB-likely token in "she walked": -ed marks it
        sent2 = parser.parse_single("she walked")
        verb_idx = next(i for i, t in enumerate(sent2.tokens) if t.pos == POS.VERB)
        assert sent2.root_idx == verb_idx
        assert sent2.tokens[verb_idx].is_root

    def test_roles_extracted_from_dependencies(self, parser):
        sent = parser.parse_single("she walked")
        # Subject (PRON before root) → agent
        role_names = {r.role for r in sent.roles}
        assert "agent" in role_names


class TestProtocolConformance:
    def test_heuristic_parser_satisfies_protocol(self, parser):
        assert isinstance(parser, POSTagger)

    def test_lower_confidence_than_spacy(self, parser):
        sent = parser.parse_single("she walked")
        # Heuristic should record lower confidence than the spaCy default 0.9
        if sent.roles:
            assert all(r.confidence < 0.9 for r in sent.roles)


class TestMakeParser:
    def test_heuristic_preference_returns_heuristic(self):
        p = make_parser(prefer="heuristic")
        assert isinstance(p, HeuristicParser)

    def test_falls_back_when_spacy_import_fails(self):
        with patch("gse.parser.Parser", side_effect=ImportError("no spacy")):
            p = make_parser(prefer="spacy")
        assert isinstance(p, HeuristicParser)

    def test_falls_back_when_spacy_model_missing(self):
        with patch("gse.parser.Parser", side_effect=OSError("model not found")):
            p = make_parser(prefer="spacy")
        assert isinstance(p, HeuristicParser)

    def test_returns_spacy_parser_when_available(self):
        fake_parser_instance = object()
        with patch("gse.parser.Parser", return_value=fake_parser_instance) as cls:
            result = make_parser(prefer="spacy", model="en_core_web_sm")
        cls.assert_called_once_with(model="en_core_web_sm")
        assert result is fake_parser_instance
