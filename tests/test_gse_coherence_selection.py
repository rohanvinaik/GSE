"""
M2.2b — coherence-scored sense selection (RESOLVED_STRUCTURE_DESIGN.md).

The selector picks, per referent, the candidate thread that coheres with the
rest of the sentence — deterministically. A controlled fake provider proves
coherence *flips* an ambiguous sense; the real store proves it stays sane.
"""

from pathlib import Path

import pytest

from gse.symbolic import resolve_references
from gse.symbolic.expression import Atom
from gse.symbolic.predicates import Comparison
from gse.symbolic.resolution import Entity


# A two-sense lemma ("king": monarch vs chess piece) plus context words that
# each cohere with exactly one sense.
class FakeChess:
    _T = {
        "king": [
            ("entity", "person", "ruler", "king"),  # sense 0 (primary)
            ("entity", "artifact", "game_equipment", "chessman", "king"),  # sense 1
        ],
        "queen": [("entity", "person", "ruler", "queen")],  # → monarch
        "bishop": [("entity", "artifact", "game_equipment", "chessman", "bishop")],  # → chess
    }

    def candidates(self, lemma, pos, is_proper):
        return self._T.get(lemma, [])

    def thread(self, lemma, pos, is_proper):
        c = self.candidates(lemma, pos, is_proper)
        return c[0] if c else ()


def _pair(a, b):
    return Comparison(
        lhs=Entity(head=Atom(lemma=a, pos="NOUN", position=1)),
        rhs=Entity(head=Atom(lemma=b, pos="NOUN", position=4)),
    )


def test_coherence_keeps_monarch_sense_near_queen():
    out = resolve_references(_pair("king", "queen"), FakeChess())
    assert out.lhs.type_thread[-1] == "king"
    assert "ruler" in out.lhs.type_thread  # monarch sense (primary, coheres)


def test_coherence_flips_to_chess_sense_near_bishop():
    out = resolve_references(_pair("king", "bishop"), FakeChess())
    assert out.lhs.type_thread[-1] == "king"
    # Coherence overrides the primary sense: the chess 'king' wins next to 'bishop'.
    assert "chessman" in out.lhs.type_thread
    assert "ruler" not in out.lhs.type_thread


def test_single_entity_keeps_primary_sense():
    # No other entity to cohere with → primary (sense 0) stays.
    lone = Comparison(
        lhs=Entity(head=Atom(lemma="king", pos="NOUN", position=1)),
        rhs=Entity(head=Atom(lemma="dog", pos="NOUN", position=4)),  # no candidates
    )
    out = resolve_references(lone, FakeChess())
    assert "ruler" in out.lhs.type_thread


def test_selection_is_deterministic():
    a = resolve_references(_pair("king", "bishop"), FakeChess())
    b = resolve_references(_pair("king", "bishop"), FakeChess())
    assert a.lhs.type_thread == b.lhs.type_thread


# -- real store: coherence selection produces sane threads -------------------

_DB = Path("data/genealogy.db")


@pytest.mark.skipif(not _DB.exists(), reason="genealogy.db not built")
def test_real_store_selection_stays_sane():
    from gse.symbolic import GenealogyStore

    with GenealogyStore() as store:
        out = resolve_references(_pair("dog", "cat"), store)
        # dog & cat cohere via 'animal'; both threads end at their lemma.
        assert out.lhs.type_thread[-1] == "dog"
        assert out.rhs.type_thread[-1] == "cat"
        assert "animal" in out.lhs.type_thread and "animal" in out.rhs.type_thread
