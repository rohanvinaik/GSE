"""Head linking needs both licensed wording and the sentence-head position."""

import pytest

from gse.nlp.linkers import head_linker_operation


@pytest.mark.parametrize(
    "word,code",
    [
        ("however", "CONTRAST"),
        ("yet", "CONTRAST"),
        ("still", "CONTRAST"),
        ("instead", "CONTRAST"),
        ("thus", "CONSEQUENCE"),
        ("therefore", "CONSEQUENCE"),
        ("hence", "CONSEQUENCE"),
        ("consequently", "CONSEQUENCE"),
        ("and", "CLAUSE_COORD"),
        ("then", "TEMPORAL"),
    ],
)
def test_every_supported_head_has_a_scoped_named_relation(word, code):
    assert head_linker_operation(word, True) == code
    assert head_linker_operation(word, False) == "none"


@pytest.mark.parametrize("word", ["", "when", "before", "because", "so", "xqzzt", "However"])
def test_other_wording_does_not_invent_an_open_discourse_relation(word):
    assert head_linker_operation(word, True) == "none"
