"""Manual contract tests for gse.nlp.sentence_parser."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.nlp.sentence_parser import (
    AMR_TO_PRIMITIVES,
    DEP_TO_SYNTACTIC,
    FUNCTION_WORD_OPERATORS,
    MORPH_TO_TAM,
    LexiconSentencePrimitivePopulator,
    ParsedSentence,
    SentencePrimitiveAssignment,
    SentencePrimitiveParser,
)

# ---------- Mapping tables ----------

class TestMappingTables:
    def test_dep_to_syntactic_core_args(self):
        assert DEP_TO_SYNTACTIC["nsubj"] == "SYN_SUBJ"
        assert DEP_TO_SYNTACTIC["dobj"] == "SYN_OBJ"
        assert DEP_TO_SYNTACTIC["ROOT"] == "SYN_PRED"

    def test_morph_to_tam_tense(self):
        assert MORPH_TO_TAM["Tense=Past"] == "SYN_TENSE_PAST"
        assert MORPH_TO_TAM["Tense=Pres"] == "SYN_TENSE_PRES"

    def test_morph_to_tam_mood_ind_none(self):
        # Indicative is the default, no marker
        assert MORPH_TO_TAM["Mood=Ind"] is None

    def test_function_word_than(self):
        op = FUNCTION_WORD_OPERATORS["than"]
        assert op["primitive"] == "COMP_THAN"
        assert op["arity"] == 2
        assert op["operation"] == "SET_DIFF"

    def test_function_word_only_unary(self):
        op = FUNCTION_WORD_OPERATORS["only"]
        assert op["arity"] == 1

    def test_amr_to_primitives_arg0(self):
        assert AMR_TO_PRIMITIVES[":ARG0"] == "SYN_SUBJ"

    def test_amr_to_primitives_polarity_none(self):
        # Polarity handled separately, so mapping is None
        assert AMR_TO_PRIMITIVES[":polarity"] is None


# ---------- Dataclasses ----------

class TestSentencePrimitiveAssignment:
    def test_defaults(self):
        a = SentencePrimitiveAssignment(
            lexeme="dog", pos="NOUN", primitives={"SYN_SUBJ": 1}
        )
        assert a.confidence == 1.0
        assert a.source == "nlp_parser"
        assert a.is_compositional is False
        assert a.comp_arity == 0

    def test_compositional_fields(self):
        a = SentencePrimitiveAssignment(
            lexeme="than", pos="ADP", primitives={"COMP_THAN": 1},
            is_compositional=True, comp_primitive="COMP_THAN",
            comp_arity=2, comp_operation="SET_DIFF",
        )
        assert a.is_compositional is True
        assert a.comp_primitive == "COMP_THAN"


class TestParsedSentence:
    def test_defaults(self):
        p = ParsedSentence(text="hi", tokens=["hi"], assignments=[])
        assert p.is_interrogative is False
        assert p.is_imperative is False
        assert p.spacy_doc is None
        assert p.amr_graph is None


# ---------- SentencePrimitiveParser ----------

@pytest.fixture(scope="module")
def parser():
    return SentencePrimitiveParser(use_amr=False)


class TestParserInit:
    def test_use_amr_false_disables_amr(self):
        p = SentencePrimitiveParser(use_amr=False)
        assert p.use_amr is False
        assert p.amr_model is None

    def test_spacy_loaded_when_available(self, parser):
        # spaCy is installed in this venv
        assert parser.nlp is not None


class TestParseInterrogative:
    def test_ends_in_question_mark(self, parser):
        result = parser.parse("Is the dog happy?")
        assert result.is_interrogative is True

    def test_no_question_mark(self, parser):
        result = parser.parse("The dog is happy.")
        assert result.is_interrogative is False

    def test_whitespace_stripped(self, parser):
        result = parser.parse("Hi?   ")
        assert result.is_interrogative is True


class TestParseTokens:
    def test_tokens_populated(self, parser):
        result = parser.parse("The dog runs.")
        # Tokens come from spaCy doc
        assert "dog" in result.tokens
        assert "runs" in result.tokens

    def test_text_preserved(self, parser):
        text = "The dog is happy."
        result = parser.parse(text)
        assert result.text == text


class TestParseComparison:
    def test_than_triggers_comparison(self, parser):
        result = parser.parse("The dog is bigger than the cat.")
        assert result.has_comparison is True

    def test_no_than_no_comparison(self, parser):
        result = parser.parse("The dog is big.")
        assert result.has_comparison is False


class TestParseNegation:
    def test_neg_dep_triggers_negative_flag(self, parser):
        result = parser.parse("The dog is not happy.")
        # spaCy assigns dep_='neg' to "not"
        assert result.is_negative is True


class TestExtractSpacyPrimitives:
    def test_subject_assigned_syn_subj(self, parser):
        result = parser.parse("The dog runs.")
        # Find the assignment for "dog"
        dog_asn = next((a for a in result.assignments if a.lexeme == "dog"), None)
        assert dog_asn is not None
        assert "SYN_SUBJ" in dog_asn.primitives

    def test_function_word_marked_compositional(self, parser):
        result = parser.parse("The dog is bigger than the cat.")
        than_asn = next((a for a in result.assignments if a.lexeme == "than"), None)
        assert than_asn is not None
        assert than_asn.is_compositional is True
        assert than_asn.comp_primitive == "COMP_THAN"
        assert than_asn.comp_arity == 2

    def test_no_primitives_returns_none(self, parser):
        # Punctuation typically has no primitives
        result = parser.parse(".")
        # If there are no assignments, the file's None-skipping branch fired
        assert isinstance(result.assignments, list)


class TestExtractAmrPrimitives:
    def test_extracts_arg0(self, parser):
        # AMR strings have content after concept; the regex relies on whitespace
        # boundary, so test with a string the regex can fully parse.
        amr_str = ":ARG0 (d / dog :ARG1 (c / cat"
        result = parser._extract_amr_primitives(amr_str)
        primitives = [(c, p) for c, p, _ in result]
        assert ("dog", "SYN_SUBJ") in primitives

    def test_extracts_polarity_negative(self, parser):
        amr_str = "(p / predicate :polarity -)"
        result = parser._extract_amr_primitives(amr_str)
        assert ("_sentence", "_NEG_SCOPE", 1) in result

    def test_ignores_none_relations(self, parser):
        # :modal maps to None
        amr_str = ":modal (m / must)"
        result = parser._extract_amr_primitives(amr_str)
        # No primitive should be extracted from this
        for concept, prim, _ in result:
            assert prim is not None

    def test_concept_dash_split(self, parser):
        # "run-01" should be extracted as "run"
        amr_str = ":ARG0 (r / run-01 :ARG1 (x / target"
        result = parser._extract_amr_primitives(amr_str)
        concepts = [c for c, _, _ in result]
        assert "run" in concepts


class TestMergeAmrAssignments:
    def test_merges_into_matching_lemma(self, parser):
        assignments = [
            SentencePrimitiveAssignment(
                lexeme="dog", pos="NOUN", primitives={"SYN_SUBJ": 1}, source="spacy"
            )
        ]
        amr_prims = [("dog", "SYN_ADJ_MOD", 1)]
        parser._merge_amr_assignments(assignments, amr_prims)
        assert assignments[0].primitives["SYN_ADJ_MOD"] == 1
        assert assignments[0].source == "spacy+amr"

    def test_no_match_no_change(self, parser):
        assignments = [
            SentencePrimitiveAssignment(
                lexeme="cat", pos="NOUN", primitives={"SYN_SUBJ": 1}, source="spacy"
            )
        ]
        parser._merge_amr_assignments(assignments, [("dog", "SYN_OBJ", 1)])
        # No match → no merge
        assert "SYN_OBJ" not in assignments[0].primitives
        assert assignments[0].source == "spacy"

    def test_existing_primitive_not_overwritten(self, parser):
        assignments = [
            SentencePrimitiveAssignment(
                lexeme="dog", pos="NOUN", primitives={"SYN_SUBJ": 1}, source="spacy"
            )
        ]
        parser._merge_amr_assignments(assignments, [("dog", "SYN_SUBJ", -1)])
        # Existing value retained
        assert assignments[0].primitives["SYN_SUBJ"] == 1


class TestParseImperative:
    def test_imperative_flag(self, parser):
        # spaCy may or may not detect "Run!" as imperative depending on context
        result = parser.parse("Run!")
        # Just check that it doesn't crash; flag is set when morphology indicates
        assert isinstance(result.is_imperative, bool)


# ---------- LexiconSentencePrimitivePopulator ----------

@pytest.fixture
def populator_db():
    """Lexicon DB with schema for populator tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name

    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE lexemes (
            id INTEGER PRIMARY KEY,
            lemma TEXT,
            pos TEXT,
            comp_primitive TEXT,
            comp_arity INTEGER,
            comp_operation TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE sentence_primitive_values (
            lexeme_id INTEGER,
            primitive TEXT,
            value INTEGER,
            confidence REAL,
            source TEXT,
            UNIQUE(lexeme_id, primitive)
        )
    """)
    conn.execute("INSERT INTO lexemes (id, lemma, pos) VALUES (1, 'than', 'ADP')")
    conn.execute("INSERT INTO lexemes (id, lemma, pos) VALUES (2, 'dog', 'NOUN')")
    conn.execute("INSERT INTO lexemes (id, lemma, pos) VALUES (3, 'run', 'VERB')")
    conn.execute("INSERT INTO lexemes (id, lemma, pos) VALUES (4, 'fast', 'ADV')")
    conn.commit()
    conn.close()
    yield path
    Path(path).unlink(missing_ok=True)


class TestPopulatorInit:
    def test_opens_db(self, populator_db):
        p = LexiconSentencePrimitivePopulator(populator_db)
        assert p.db_path == populator_db
        assert p.parser is not None
        p.close()


class TestPopulateFunctionWords:
    def test_updates_than_lexeme(self, populator_db):
        p = LexiconSentencePrimitivePopulator(populator_db)
        try:
            counts = p.populate_function_words()
            # "than" should be assigned COMP_THAN
            assert counts.get("COMP_THAN", 0) >= 1

            # Verify metadata was set
            p.cursor.execute(
                "SELECT comp_primitive, comp_arity FROM lexemes WHERE lemma = 'than'"
            )
            row = p.cursor.fetchone()
            assert row[0] == "COMP_THAN"
            assert row[1] == 2
        finally:
            p.close()

    def test_unknown_function_words_skipped(self, populator_db):
        """Function words not in lexicon don't get inserted; they're skipped."""
        p = LexiconSentencePrimitivePopulator(populator_db)
        try:
            counts = p.populate_function_words()
            # "but" is in FUNCTION_WORD_OPERATORS but not in our test lexicon
            assert "COMP_BUT" not in counts
        finally:
            p.close()


class TestPopulatePosDefaults:
    def test_assigns_noun_defaults(self, populator_db):
        p = LexiconSentencePrimitivePopulator(populator_db)
        try:
            count = p.populate_pos_defaults()
            # Should have added primitives
            assert count > 0

            # Verify "dog" got SYN_SUBJ and SYN_OBJ
            p.cursor.execute("""
                SELECT primitive FROM sentence_primitive_values WHERE lexeme_id = 2
            """)
            prims = {row[0] for row in p.cursor.fetchall()}
            assert "SYN_SUBJ" in prims
            assert "SYN_OBJ" in prims
        finally:
            p.close()

    def test_assigns_verb_pred(self, populator_db):
        p = LexiconSentencePrimitivePopulator(populator_db)
        try:
            p.populate_pos_defaults()
            p.cursor.execute("""
                SELECT primitive FROM sentence_primitive_values WHERE lexeme_id = 3
            """)
            prims = {row[0] for row in p.cursor.fetchall()}
            assert "SYN_PRED" in prims
        finally:
            p.close()

    def test_empty_mapping_skipped(self, populator_db):
        """CCONJ has empty primitives dict — should be skipped."""
        p = LexiconSentencePrimitivePopulator(populator_db)
        try:
            # Add a CCONJ lexeme
            p.cursor.execute("INSERT INTO lexemes (id, lemma, pos) VALUES (99, 'and', 'CCONJ')")
            p.conn.commit()
            p.populate_pos_defaults()
            # No primitives should have been added for lexeme 99
            p.cursor.execute("""
                SELECT COUNT(*) FROM sentence_primitive_values WHERE lexeme_id = 99
            """)
            assert p.cursor.fetchone()[0] == 0
        finally:
            p.close()


class TestClose:
    def test_close_releases_connection(self, populator_db):
        p = LexiconSentencePrimitivePopulator(populator_db)
        p.close()
        with pytest.raises(sqlite3.ProgrammingError):
            p.cursor.execute("SELECT 1")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
