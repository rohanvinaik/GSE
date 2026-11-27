"""Identity obligations resolved between rounds (`identities.py`). The readings and obligations are written for the
test; they are not Wiktionary records."""

from __future__ import annotations

from GSE.curation.lexicon_builder import cells
from GSE.curation.lexicon_builder.cells import State
from GSE.curation.lexicon_builder.identities import IdentityObligation, node_key, resolve

B = cells.BANK_INDEX
IDS = ["wiktionary:happier-adj-1:x", "wordnet:happy:happy.a.01", "wordnet:happy:felicitous.s.02", "wiktionary:y:1"]


def _state():
    return State.opening(IDS)


def _set(state, row, bank, value):
    state.masks[row, B[bank]] = cells.bit(value)


def test_the_one_target_left_becomes_a_proposed_link_both_ways():
    s = _state()
    _set(s, 0, "FEEL", +1)
    _set(s, 2, "FEEL", 0)  # felicitous.s.02 cannot be the sense's meaning
    out = resolve(s.masks, s.readings, [IdentityObligation("form_of", 0, [1, 2], ("wiktionary:happier",))])
    assert out.links == (
        ("form_of", "happy.a.01", "wiktionary:happier-adj-1:x", "proposed"),
        ("form_of", "wiktionary:happier-adj-1:x", "happy.a.01", "proposed"),
    )
    assert out.located[0]["target"] == "wordnet:happy:happy.a.01" and out.open == 0


def test_no_target_left_is_a_conflict_and_several_stay_open():
    s = _state()
    _set(s, 0, "FEEL", +1)
    _set(s, 1, "FEEL", 0)
    _set(s, 2, "FEEL", 0)
    out = resolve(
        s.masks, s.readings, [IdentityObligation("alt_of", 0, [1, 2]), IdentityObligation("alt_of", 3, [1, 2])]
    )
    assert out.links == () and out.open == 1
    assert out.conflicts[0]["targets"] == ["wordnet:happy:happy.a.01", "wordnet:happy:felicitous.s.02"]


def test_a_sense_synonym_excludes_only_by_the_content_it_carries():
    # A zero or a silence on one side does not bar a near-synonym; an opposite decided pole does.
    s = _state()
    _set(s, 0, "GOOD", +1)
    _set(s, 0, "SEE", 0)
    _set(s, 1, "GOOD", -1)
    _set(s, 2, "SEE", "SILENT")
    out = resolve(s.masks, s.readings, [IdentityObligation("sense_synonym", 0, [1, 2])])
    assert out.located[0]["target"] == "wordnet:happy:felicitous.s.02"


def test_node_keys_follow_the_graph():
    assert node_key("wordnet:a%20b:a_b.n.01") == "a_b.n.01"
    assert node_key("wiktionary:x:1") == "wiktionary:x:1"


def test_a_hypernym_obligation_checks_only_what_the_parent_gives_its_kind():
    # A kind may add content its hub lacks; a hub's explicit zero bars a kind that has the content.
    s = _state()
    _set(s, 0, "FEEL", +1)
    _set(s, 0, "MOVE", +1)
    _set(s, 1, "FEEL", 0)  # happy.a.01 excludes feeling: it cannot be the hub
    _set(s, 2, "SEE", +1)  # felicitous.s.02 gives SEE +1; the sense leaves SEE open, so it can be
    out = resolve(s.masks, s.readings, [IdentityObligation("wiktionary_hypernym", 0, [1, 2])])
    assert out.links == (("wiktionary_hypernym", "felicitous.s.02", "wiktionary:happier-adj-1:x", "proposed"),)


def test_resolution_is_vectorised_over_many_obligations():
    s = State.opening([f"wiktionary:r{i}:1" for i in range(300)])
    for t in range(1, 300, 3):
        s.masks[t, B["FEEL"]] = cells.bit(0)
    s.masks[0, B["FEEL"]] = cells.bit(+1)
    obligations = [IdentityObligation("form_of", 0, [t, t + 1]) for t in range(1, 298, 3)]
    out = resolve(s.masks, s.readings, obligations)
    assert len(out.located) == len(obligations) and out.open == 0
    assert all(x["target"] == f"wiktionary:r{t + 1}:1" for x, t in zip(out.located, range(1, 298, 3)))
