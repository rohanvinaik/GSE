"""The genus/differentia closure (Rohan, 2026-11-26): a kind is its genus plus its differentia."""

from __future__ import annotations

import pytest

from GSE.curation.lexicon_builder import word_sense_genus_differentia as gd
from GSE.curation.lexicon_builder.engine import Relation
from GSE.curation.lexicon_builder.foundation import BANKS


def state(**banks):
    return gd.pack({bank: values for bank, values in banks.items()})


ZERO_ALL = gd.pack({bank: [0] for bank in BANKS})


def determined(**banks):
    """Fully determined: the named values, 0 on every other bank."""
    return gd.pack({bank: banks.get(bank, [0]) for bank in BANKS})


def no_exceptions(_entry):
    return ()


def edge(genus=(), differentia=(), entry="kind"):
    return gd.Edge(entry, "noun", "test", tuple(genus), tuple(differentia))


def values(packed, bank):
    return gd.bank_values(packed, BANKS.index(bank))


def test_packing_round_trips_and_finds_open_and_empty_banks():
    packed = state(GOOD=[0], ALIVE=[1], FEEL=[0, 1])
    assert gd.unpack(packed)["GOOD"] == [0] and gd.unpack(packed)["FEEL"] == [0, 1]
    assert gd.unpack(packed)["BIG"] == [-1, 0, 1]
    assert len(gd.open_banks(packed)) == len(BANKS) - 2
    assert gd.empty_banks(packed & state(GOOD=[1])) == [BANKS.index("GOOD")]
    assert gd.pack(gd.unpack(packed)) == packed


def test_without_differentia_a_kind_takes_its_genus_state_zeros_included():
    world = {"animal": determined(ALIVE=[1])}
    allowed = gd.compile_constraint(edge([("animal", ("animal",))]), world)
    assert values(allowed, "ALIVE") == (1,) and values(allowed, "GOOD") == (0,) and values(allowed, "FEEL") == (0,)


def test_differentia_sets_the_banks_it_touches_and_leaves_the_rest_to_the_genus():
    world = {
        "animal": determined(ALIVE=[1]),
        "barks": determined(SAY=[1]),  # definitely touches SAY only
        "fierce": state(GOOD=[0], FEEL=[0, 1]),  # zero on GOOD, maybe FEEL, unknown elsewhere
    }
    one = gd.compile_constraint(edge([("animal", ("animal",))], [("barks", ("barks",))]), world)
    assert values(one, "SAY") == (1,)  # touched: the differentia's contribution
    assert values(one, "ALIVE") == (1,) and values(one, "GOOD") == (0,)  # untouched: the genus, zeros included
    two = gd.compile_constraint(edge([("animal", ("animal",))], [("fierce", ("fierce",))]), world)
    assert values(two, "GOOD") == (0,)  # every differentia word is 0 there
    assert values(two, "FEEL") == (0, 1)  # maybe touched: the union, never a guess
    assert values(two, "BIG") == (-1, 0, 1)  # unknown stays unknown: genus 0, or the word's own sign
    assert values(two, "ALIVE") == (-1, 1)  # genus +1 if untouched, the word's own sign if touched


def test_a_word_with_several_definitions_carries_all_of_them_and_an_undefined_word_is_unknown():
    world = {"bank.1": determined(WHERE=[1]), "bank.2": determined(SOMEONE=[1])}
    allowed = gd.compile_constraint(edge([("bank", ("bank.1", "bank.2"))]), world)
    assert values(allowed, "WHERE") == (0, 1) and values(allowed, "SOMEONE") == (0, 1)
    assert values(allowed, "GOOD") == (0,)
    unknown = gd.compile_constraint(edge([("bank", ("bank.1",))], [("zorp", ())]), world)
    assert values(unknown, "GOOD") == (-1, 0, 1)


def test_several_hypernyms_are_each_a_genus_and_their_conflict_is_typed_with_both_causes():
    world = {"a": state(ALIVE=[1], GOOD=[0, 1]), "b": state(ALIVE=[0, 1], GOOD=[0]), "c": state(ALIVE=[-1])}
    both = gd.compile_constraint(edge([("a", ("a",)), ("b", ("b",))]), world)
    assert values(both, "ALIVE") == (1,) and values(both, "GOOD") == (0,)
    with pytest.raises(gd.GenusDifferentiaContradiction) as caught:
        gd.compile_constraint(edge([("a", ("a",)), ("c", ("c",))]), world)
    record = caught.value.as_record()
    assert record["kind"] == "GENUS_CONFLICT" and record["bank"] == "ALIVE"
    assert record["stated"]["genus"][0]["values"] == [1] and record["derived"]["genus"][0]["values"] == [-1]


def test_resolution_applies_the_release_rules_and_never_widens():
    rule = Relation(
        "r:move-happen",
        ("MOVE", "HAPPEN"),
        ((1, 1), (0, -1), (0, 0), (0, 1), (-1, -1), (-1, 0), (-1, 1)),
        ("test",),
        authority="foundational",
        approved=True,
    )
    current = state(GOOD=[0])
    result = gd.resolve_entry("kind", "verb", current, state(MOVE=[1]), (rule,), no_exceptions, {})
    packed, resolution = result
    assert values(packed, "MOVE") == (1,) and values(packed, "HAPPEN") == (1,)  # the rule's consequence
    assert values(packed, "GOOD") == (0,) and not packed & ~current
    assert any(row["kind"] == "INFERENCE_SCOPE" for row in gd.receipts(resolution))
    assert gd.resolve_entry("kind", "verb", current, state(GOOD=[0]), (rule,), no_exceptions, {}) is None


def test_a_stored_value_is_never_overwritten_the_contradiction_names_both_sides():
    with pytest.raises(gd.GenusDifferentiaContradiction) as caught:
        gd.resolve_entry("kind", "noun", state(ALIVE=[1]), state(ALIVE=[0]), (), no_exceptions, {"edge": "test"})
    record = caught.value.as_record()
    assert record["kind"] == "STORED_CONFLICT" and record["stated"]["values"] == [1]
    assert record["derived"]["allowed"] == [0] and record["derived"]["edge"] == "test"


def test_a_rule_conflict_is_typed():
    rule = Relation("r:x", ("MOVE", "HAPPEN"), ((1, 1), (0, 0)), ("test",), authority="foundational", approved=True)
    with pytest.raises(gd.GenusDifferentiaContradiction) as caught:
        gd.resolve_entry("kind", "verb", state(HAPPEN=[0]), state(MOVE=[1]), (rule,), no_exceptions, {})
    assert caught.value.kind == "RULE_CONFLICT"


def test_axioms_are_fully_determined_only_when_their_own_bank_is_settled():
    result, errors = gd.determine_axiom("gse:prime:feel", "verb", state(FEEL=[1]), (), no_exceptions)
    packed, _ = result
    assert not errors and values(packed, "FEEL") == (1,) and values(packed, "GOOD") == (0,)
    assert not gd.open_banks(packed)
    result, errors = gd.determine_axiom("nsm_chart:v20:die", "nsm_lexical_unit", gd.FULL, (), no_exceptions)
    assert result is None and errors[0]["kind"] == "AXIOM_OWN_BANK_OPEN"
    result, errors = gd.determine_axiom("gse_closed_class:determiner:the", "determiner", gd.FULL, (), no_exceptions)
    assert not errors and result[0] == ZERO_ALL


def test_the_fixpoint_carries_an_axiom_down_a_chain_in_passes_and_stops():
    stored = {"prime": state(FEEL=[1]), "emotion": gd.FULL, "joy": state(GOOD=[1]), "glee": gd.FULL, "x": gd.FULL}
    pos = dict.fromkeys(stored, "noun")
    edges = {
        "emotion": gd.Edge("emotion", "noun", "t", (("prime", ("prime",)),)),
        "joy": gd.Edge("joy", "noun", "t", (("emotion", ("emotion",)),)),
        "glee": gd.Edge("glee", "noun", "t", (("joy", ("joy",)),)),
        "x": gd.Edge("x", "noun", "t", (("glee", ("glee",)),), (("undefined", ()),)),
    }
    closure = gd.close(stored, pos, edges, ["prime"], (), no_exceptions)
    # pass 0: the axiom; pass 1: emotion from the prime, glee from joy's stored GOOD+; pass 2: joy, x
    assert closure.changed_in == {"prime": 0, "emotion": 1, "glee": 1, "x": 2}
    assert values(closure.state["emotion"], "FEEL") == (1,) and values(closure.state["emotion"], "BIG") == (0,)
    assert values(closure.state["glee"], "GOOD") == (1,)
    # joy's stored GOOD+ contradicts its genus's GOOD 0: recorded with both causes, joy unchanged
    assert closure.state["joy"] == stored["joy"]
    assert [(row["kind"], row["entry_id"], row["pass"]) for row in closure.contradictions] == [
        ("STORED_CONFLICT", "joy", 2)
    ]
    assert closure.contradictions[0]["stated"]["values"] == [1]
    assert closure.contradictions[0]["derived"]["explanation"]["genus"][0]["values"] == [0]
    # An undefined differentia word may or may not touch a bank: where the genus is open, x stays open;
    # where the genus is GOOD+, x is GOOD+ (untouched) or the word's own sign (touched), never 0.
    assert values(closure.state["x"], "FEEL") == (-1, 0, 1)
    assert values(closure.state["x"], "GOOD") == (-1, 1)
    assert [p["changed"] for p in closure.passes] == [1, 2, 1]
    for entry, packed in closure.state.items():
        assert not packed & ~stored[entry]


def test_edges_follow_the_sources_and_refuse_what_is_not_a_kind():
    index = gd.Index.build(
        [
            ("wordnet:dog:dog.n.01", "dog", "noun"),
            ("wordnet:canine:canine.n.02", "canine", "noun"),
            ("wordnet:part:part.n.01", "part", "noun"),
            ("wiktionary:happy:1", "happy", "adj"),
            ("wiktionary:dog:1", "dog", "noun"),
            ("wiktionary:Dog:1", "Dog", "name"),
        ]
    )
    parsed = {"template": "genus_differentia", "genus": "x", "differentia": [], "negated": False}
    built, _ = gd.build_edge("wordnet:dog:dog.n.01", "dog", "noun", parsed, index, hypernyms=("canine.n.02",))
    assert built.genus == (("canine.n.02", ("wordnet:canine:canine.n.02",)),)
    built, _ = gd.build_edge(
        "wordnet:dog:dog.n.01",
        "dog",
        "noun",
        parsed,
        index,
        hypernyms=("part.n.01",),
        withdrawn=frozenset({"part.n.01"}),
    )
    assert built.genus == (("part.n.01", ()),)  # a withdrawn identity root carries nothing
    assert gd.build_edge("wordnet:dog:dog.n.01", "dog", "noun", parsed, index)[1] == "WORDNET_ROOT"
    manner = {"template": "adv_manner", "genus": "happy", "differentia": [], "negated": False}
    built, _ = gd.build_edge("wiktionary:happily:1", "happily", "adv", manner, index)
    assert built.genus == (("happy", ("wiktionary:happy:1",)),)
    built, _ = gd.build_edge("wiktionary:dogs:1", "dogs", "noun", None, index, form_of=("dog",))
    assert built.template == "wiktionary_form_of"
    assert built.genus == (("dog", ("wiktionary:dog:1", "wordnet:dog:dog.n.01")),)  # every noun "dog", no name
    negated = {**parsed, "genus": "dog", "negated": True}
    assert gd.build_edge("wiktionary:x:1", "x", "noun", negated, index)[1] == "NEGATED_DIFFERENTIA"
    relational = {"template": "adj_relational", "genus": None, "differentia": [], "negated": False}
    assert gd.build_edge("wiktionary:x:2", "x", "adj", relational, index)[1] == "NO_GENUS:adj_relational"
    assert gd.Edge.from_json(built.as_json()) == built


def test_wordnet_genus_is_read_from_sorted_hypernym_paths():
    pytest.importorskip("nltk")
    try:
        assert gd.wordnet_genus("dog.n.01") == ("canine.n.02", "domestic_animal.n.01")
    except LookupError:
        pytest.skip("local WordNet unavailable")
    assert gd.wordnet_genus("entity.n.01") == ()


def test_the_linker_parse_gives_templates_genus_and_differentia():
    assert gd.parse_gloss("dogs", "noun", "plural of dog")["genus"] == "dog"
    assert gd.parse_gloss("happily", "adv", "In a happy manner.")["template"] == "adv_manner"
    assert gd.parse_gloss("unhappy", "adj", "Not happy.")["genus"] is None
    assert gd.parse_gloss("quite", "adv", "To a great extent.")["template"] == "sentence_scale"
