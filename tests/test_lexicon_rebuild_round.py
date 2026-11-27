"""The round runner composes every channel, iterates to a round that admits nothing, and accounts for every cell.

The cohort is synthetic. The synsets are real, because WordNet supplies the types and the graph, but the facts are
written for the test and are not lexical claims.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from GSE.curation.lexicon_builder import nsm, projection
from GSE.curation.lexicon_builder import obligations as ob
from GSE.curation.lexicon_builder.cells import BANK_INDEX, BANKS, NEG, POS, START, ZERO
from GSE.curation.lexicon_builder.coherence import Derivation, Observation
from GSE.curation.lexicon_builder.inventory import Reading

ROOT = Path(__file__).resolve().parents[1]


def _runner():
    spec = importlib.util.spec_from_file_location("rebuild_lexicon", ROOT / "scripts/rebuild_lexicon.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up while the class is built
    spec.loader.exec_module(module)
    return module


R = _runner()

READINGS = (
    Reading("wordnet:animal:animal.n.01", "animal", "noun", ""),
    Reading("wordnet:dog:dog.n.01", "dog", "noun", ""),
    Reading("wordnet:cat:cat.n.01", "cat", "noun", ""),
    Reading("wordnet:horse:horse.n.01", "horse", "noun", ""),
    Reading("wordnet:bird:bird.n.01", "bird", "noun", ""),
    Reading("wordnet:run:run.v.01", "run", "verb", ""),
    Reading("test:grim:1", "grim", "adj", ""),
    Reading("test:zorb:1", "zorb", "noun", ""),
    Reading("test:zorb:2", "zorb", "noun", ""),
)
ANIMAL, DOG, CAT, HORSE, BIRD, RUN, GRIM, ZORB1, ZORB2 = range(len(READINGS))


def _lens() -> projection.LensOutput:
    rows = np.array([DOG, CAT, HORSE], dtype=np.int64)
    restrictions = projection.Restrictions(
        rows=rows,
        cols=np.full(3, BANK_INDEX["MOVE"], dtype=np.int64),
        allowed=np.full(3, POS, dtype=np.uint8),
        rules=np.zeros(3, dtype=np.int32),
        premises=np.arange(3, dtype=np.int32),
        rule_ids=("TEST_MOVES",),
        warrants=("a test lens rule",),
        premise_ids=("vn:t:dog", "vn:t:cat", "vn:t:horse"),
        rule_sources=("verbnet",),
    )
    zorb = ob.Obligation("TEST_ZORB_ALIVE", "ALIVE", POS, np.array([ZORB1, ZORB2]), 0, ("usas:t:zorb",))
    return projection.LensOutput(restrictions, {}, [zorb], {})


def _nsm() -> nsm.Compiled:
    record = nsm.Record(
        "T", 1, 2, "This thing is grim.", "explication", "[A] This thing is grim.\na. bad wind can blow"
    )
    return nsm.compile_records((record,), READINGS)


def _obs(row, bank, states, root):
    return Observation(READINGS[row].reading_id, bank, states, "test", root)


STATED = (
    _obs(DOG, "ALIVE", POS, "cc:dog"),
    _obs(CAT, "ALIVE", POS, "cc:cat"),
    _obs(BIRD, "MOVE", ZERO, "cc:bird-moves"),
    _obs(BIRD, "ALIVE", ZERO, "cc:bird-lives"),
    _obs(ANIMAL, "FEEL", POS, "cc:animal"),
    _obs(ZORB1, "ALIVE", ZERO, "cc:zorb"),
)
DERIVED = (Derivation(READINGS[RUN].reading_id, "DO", POS, "law:TEST_PROFILE", ("profile:run",)),)
LINKS = [("hypernym", "animal.n.01", s) for s in ("dog.n.01", "cat.n.01", "horse.n.01", "bird.n.01")]


@pytest.fixture(scope="module")
def outcome():
    inputs = R.compose(READINGS, _lens(), _nsm(), STATED, DERIVED, LINKS)
    rounds, final = R.run(inputs)
    return inputs, rounds, final


def _class(inputs, final, layer, row, bank):
    rule = getattr(final.provenance, f"{layer}_rule")
    return R.CLASSES[R.warrant_classes(rule, inputs.table)[row, BANK_INDEX[bank]]]


def _cell(final, layer, row, bank):
    state = final.settlement.known if layer == "known" else final.settlement.state
    return int(state.masks[row, BANK_INDEX[bank]])


def test_a_round_composes_every_channel(outcome):
    inputs, _, final = outcome
    expected = {
        ("known", DOG, "ALIVE"): ("stated", POS),
        ("known", RUN, "DO"): ("profile_derivation", POS),
        ("known", RUN, "SOMEONE"): ("law", ZERO),  # a verb heads no substantive
        ("known", DOG, "MOVE"): ("lens", POS),
        ("known", GRIM, "GOOD"): ("nsm", NEG),
        ("known", ZORB2, "ALIVE"): ("forced_obligation", POS),  # the other zorb states ALIVE 0
        ("known", HORSE, "ALIVE"): ("admitted", POS),  # MOVE => ALIVE, witnessed by dog and cat, exposed by bird
        ("interpolated", DOG, "FEEL"): ("inherited", POS),  # from animal.n.01, kind-of
    }
    for (layer, row, bank), (warrant, state) in expected.items():
        assert _class(inputs, final, layer, row, bank) == warrant, (layer, READINGS[row].lemma, bank)
        assert _cell(final, layer, row, bank) == state, (layer, READINGS[row].lemma, bank)
    assert _cell(final, "known", DOG, "FEEL") & ZERO  # inherited content stays out of the known layer


def test_iteration_stops_when_a_round_admits_nothing(outcome):
    _, rounds, _ = outcome
    assert len(rounds) == 2
    assert rounds[0]["discovery"]["admitted"] and not rounds[1]["discovery"]["admitted"]
    assert rounds[1]["admitted_relations_in_force"] == len(rounds[0]["discovery"]["admitted"])
    first, second = rounds[0]["known"]["bits"], rounds[1]["known"]["bits"]
    assert second < first  # the admitted rule removed states the first round's closure held


def test_the_receipt_accounts_for_every_cell(outcome):
    inputs, rounds, final = outcome
    cells = len(READINGS) * len(BANKS)
    for r in rounds:
        for layer in ("known", "interpolated"):
            m = r[layer]
            census = m["census"]
            decided = sum(census[k] for k in ("+1", "-1", "0", "SILENT"))
            assert decided + census["residual"] + census["conflict"] == census["cells"] == cells
            assert sum(m["cells_by_warrant"].values()) == cells
            assert sum(m["decided_by_warrant"].values()) == decided
            assert sum(sum(b.values()) for b in m["cells_by_bank"].values()) == cells
            o = m["obligations"]
            assert o["located"] + o["open"] + o["conflict"] + o["blocked"] == o["groups"]
    for layer, state in (("known", final.settlement.known), ("interpolated", final.settlement.state)):
        classes = R.warrant_classes(getattr(final.provenance, f"{layer}_rule"), inputs.table)
        assert np.array_equal(classes == R.UNTOUCHED, state.masks == START[None, :])


def test_the_final_state_and_its_provenance_persist(outcome, tmp_path):
    inputs, _, final = outcome
    receipt = R.persist(tmp_path / "round.npz", inputs, final)
    data = np.load(tmp_path / "round.npz", allow_pickle=True)
    assert receipt["rules"] == len(data["rule_ids"])
    assert tuple(data["readings"].tolist()) == inputs.ids
    assert np.array_equal(data["known_masks"], final.settlement.known.masks)
    assert np.array_equal(data["interpolated_masks"], final.settlement.state.masks)
    rule = data["known_rule"][HORSE, BANK_INDEX["ALIVE"]]
    assert str(data["rule_ids"][rule]).startswith("coherence:")
    assert data["classes"][data["known_class"][ZORB2, BANK_INDEX["ALIVE"]]] == "forced_obligation"


# --- The Wiktionary binding through the extension hook ------------------------------------------------------------

WIKT = (
    Reading("wiktionary:dog:1", "dog", "noun", ""),  # aligned to dog.n.01: a proposed identity
    Reading("wiktionary:doggo:1", "doggo", "noun", ""),  # form_of dog.n.01, one target: a stated identity
    Reading("wiktionary:birdy:1", "birdy", "noun", ""),  # form_of one of dog.n.01 or bird.n.01: an obligation
)
W_ALIGNED, W_FORM, W_OBLIGED = range(len(READINGS), len(READINGS) + len(WIKT))


def _links():
    links = []
    for family, sense, standing in (
        ("aligned", "wiktionary:dog:1", "proposed"),
        ("form_of", "wiktionary:doggo:1", "stated"),
    ):
        links += [(family, sense, "dog.n.01", standing), (family, "dog.n.01", sense, standing)]
    return links


def _classes(*joined):
    classes = np.arange(len(READINGS) + len(WIKT))
    classes[list(joined)] = DOG
    return classes


def _obligation():
    from GSE.curation.lexicon_builder.identities import IdentityObligation

    targets = np.array([DOG, BIRD], dtype=np.int64)
    return IdentityObligation("form_of", W_OBLIGED, targets, ("wiktionary:birdy:1:form_of:x",))


def _extension():
    n = len(READINGS) + len(WIKT)
    zoology = np.zeros(n, dtype=bool)
    zoology[W_ALIGNED] = True
    return R.extensions.Extension(
        name="wiktionary",
        groups={w.reading_id: [row] for w, row in zip(WIKT, (W_ALIGNED, W_FORM, W_OBLIGED))},
        links=_links(),
        facts={"wiktionary_topic=zoology": zoology},
        classes=_classes(W_ALIGNED, W_FORM),
        identity_obligations=[_obligation()],
    )


def _wiktionary_round(resolver):
    readings = READINGS + WIKT
    stated = STATED + (Observation("wiktionary:birdy:1", "ALIVE", ZERO, "test", "cc:birdy"),)
    inputs = R.compose(readings, _lens(), _nsm(), stated, DERIVED, LINKS, (_extension(),), resolver=resolver)
    rounds, final = R.run(inputs)
    return inputs, rounds, final


@pytest.fixture(scope="module")
def wiktionary_outcome():
    return _wiktionary_round(R.identity_resolver())


def test_the_binding_becomes_an_extension_in_declared_families_at_their_standing():
    import dataclasses

    from GSE.curation.lexicon_builder import wiktionary_binding as wb

    readings = READINGS + WIKT
    plain = [link[:3] for link in _links()] + [("made_up_family", "wiktionary:dog:1", "cat.n.01")]
    fields = {f.name for f in dataclasses.fields(wb.Binding)}
    given = {
        "groups": _extension().groups,
        "links": plain,
        "classes": _classes(W_ALIGNED, W_FORM),
        "obligations": [_obligation()],
        "facts": {"wiktionary_topic=zoology": np.array([W_ALIGNED])},
        "dispositions": {},
        "aligned": {W_ALIGNED: DOG},
        "known_classes": _classes(W_FORM),
    }
    ext = R.extensions.from_binding(wb.Binding(**{k: v for k, v in given.items() if k in fields}), readings)
    assert ext.receipt["links_left_out_undeclared_family"] == {"made_up_family": 1}
    assert ext.receipt["links_by_standing"] == {"aligned:proposed": 2, "form_of:stated": 2}
    assert ext.facts["wiktionary_topic=zoology"].tolist() == [i == W_ALIGNED for i in range(len(readings))]
    assert len(ext.identity_obligations) == 1


def test_the_binding_enters_as_edges_at_their_standing_classes_and_topic_facts(wiktionary_outcome):
    inputs, _, final = wiktionary_outcome
    assert inputs.scopes["wiktionary_topic=zoology"][W_ALIGNED]
    known, every = final.known_classes, final.classes
    assert known[W_FORM] == known[DOG] and known[W_ALIGNED] != known[DOG]  # only a stated identity is known
    assert every[W_ALIGNED] == every[DOG] == every[W_FORM]
    assert _cell(final, "known", W_FORM, "MOVE") == POS  # a stated identity carries known values as known
    assert _class(inputs, final, "known", W_FORM, "MOVE") == "stated_identity"
    assert _cell(final, "interpolated", W_ALIGNED, "MOVE") == POS  # dog's lens value crosses the alignment
    assert _class(inputs, final, "interpolated", W_ALIGNED, "MOVE") == "inherited"
    assert _cell(final, "known", W_ALIGNED, "MOVE") & ZERO  # and stays out of the known layer


def test_an_identity_obligation_resolves_between_rounds_into_a_link_for_the_next(wiktionary_outcome):
    inputs, rounds, final = wiktionary_outcome
    first = rounds[0]["identities"]
    assert (first["pending_before"], first["pending_after"], first["links_added"]) == (1, 0, 2)
    assert first["links_added_by_standing"] == {"proposed": 2}  # resolved among several targets: proposed
    assert rounds[0]["links_in_force"] == 0 and rounds[1]["links_in_force"] == 2
    assert not rounds[-1]["identities"]["links_added"] and not rounds[-1]["discovery"]["admitted"]
    assert final.classes[W_OBLIGED] == final.classes[BIRD]  # the resolved identity joins its class
    assert _cell(final, "interpolated", W_OBLIGED, "MOVE") == ZERO  # bird's stated MOVE 0, across the new link
    assert _class(inputs, final, "interpolated", W_OBLIGED, "MOVE") == "inherited"


def test_without_a_resolver_identity_obligations_are_carried_and_counted():
    _, rounds, final = _wiktionary_round(None)
    assert all(r["identities"]["pending_after"] == 1 and not r["identities"]["links_added"] for r in rounds)
    assert _cell(final, "interpolated", W_OBLIGED, "MOVE") & POS  # no link, nothing crosses
