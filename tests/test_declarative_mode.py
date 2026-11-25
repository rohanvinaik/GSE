"""Declarative mode (openspec change declarative-mode): a declared mini-universe, refused by name outside it."""

import pytest

from GSE.nlp.declarative import DeclarativeRefusal, declared_mode


@pytest.fixture(scope="module")
def declarative():
    from GSE.api import GSEEncoder

    return GSEEncoder(mode="declarative")


@pytest.mark.parametrize(
    "line, expected",
    [
        ("The happy dog runs to his mother.", ["DET", "ADJ", "NOUN", "VERB", "ADP", "DET", "NOUN", "PUNCT"]),
        ("The team leads projects.", ["DET", "NOUN", "VERB", "NOUN", "PUNCT"]),
        (
            "The engineer should not delete the database.",
            ["DET", "NOUN", "AUX", "PART", "VERB", "DET", "NOUN", "PUNCT"],
        ),
    ],
)
def test_position_decides_role_and_slot_decides_part_of_speech(declarative, line, expected):
    assert [t.pos_ for t in declarative.nlp(line)] == expected


@pytest.mark.parametrize(
    "line, reason",
    [
        ("Run the tests.", "IMPERATIVE_OR_NO_SUBJECT"),
        ("The team ships code and writes docs.", "COORDINATION"),
        ("In the morning the team meets.", "FRONTED_PHRASE"),
        ("She leads the project.", "PRONOUN"),
    ],
)
def test_lines_outside_the_grammar_are_refused_by_name(declarative, line, reason):
    with pytest.raises(DeclarativeRefusal) as refused:
        declarative.nlp(line)
    assert refused.value.detail["code"] == "NOT_DECLARATIVE_FORM" and refused.value.detail["reason"] == reason


def test_both_header_spellings_are_one_declaration():
    assert declared_mode("#mode: declarative\nThe team leads.")[0::2] == ("declarative", "hash_header")
    assert declared_mode("GENRE: NARRATIVE\nMODE: declarative\nX.")[0::2] == ("declarative", "label_header")
    assert declared_mode("The dog runs.") == (None, "The dog runs.", None)


def test_undeclared_reading_uses_the_standard_front_end():
    from GSE.api import GSEEncoder
    from GSE.nlp.native import NativeNLP

    encoder = GSEEncoder()
    assert encoder.mode == "standard" and type(encoder.nlp) is NativeNLP
