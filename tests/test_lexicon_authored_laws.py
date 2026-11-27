"""The authored laws compile into relations and fire only on warranted guards (rebuild tasks 4-5).

The readings and guard facts here are written for the test; the laws, boundaries and companions are the authored
ones in `bank_laws.json`.
"""

from __future__ import annotations

import json

import numpy as np

from GSE.curation.lexicon_builder import guards, laws
from GSE.curation.lexicon_builder.cells import BANK_INDEX, NEG, POS, SILENT, START, ZERO, State, bit
from GSE.curation.lexicon_builder.closure import close
from GSE.curation.lexicon_builder.inventory import Reading

FEAR = "source_frame_family=Fear"
FEAR_ADJ_FACTS = [
    "own_denotatum=affective_feeling",
    "own_degree_domain=graded_property",
    FEAR,
    "own_valence_domain=signed_felt_pole",
    "own_template_quantification=SOMETIMES",
]
BOUNDARY = "boundary:GSE_FEAR_ADJ_BOUNDARY_V1:"


def _close(readings, facts):
    rels = laws.compile_laws()
    s = State.opening([r.reading_id for r in readings])
    wanted = {r.scope for r in rels} | {c.scope for c in laws.required_checks()}
    scopes = guards.scopes(readings, wanted, facts)
    close(s, rels, scopes)
    return s, scopes


def _facts(n, rows_by_fact):
    out = {}
    for name, rows in rows_by_fact.items():
        out[name] = np.zeros(n, dtype=bool)
        out[name][rows] = True
    return out


def _get(s, row, bank):
    return int(s.masks[row, BANK_INDEX[bank]])


def _start(bank):
    return int(START[BANK_INDEX[bank]])


def test_every_authored_block_compiles_with_its_warrant():
    book = json.loads(laws.LAWS.read_text())
    rels = laws.compile_laws()
    assert all(r.warrant for r in rels)
    assert len([r for r in rels if r.rule_id.startswith("law:") and r.rule_id.count(":") == 1]) == 16
    companions = [r for r in rels if r.rule_id.endswith(":companions")]
    assert len(companions) == sum(len(rule["companions"]) for rule in book["source_rules"])
    cells = next(r["definition_boundary"] for r in book["source_rules"] if "definition_boundary" in r)["cells"]
    written = sorted(b for b, c in cells.items() if c["kind"] in {"SILENT", "OPTIONAL"} and b in BANK_INDEX)
    assert sorted(r.banks[0] for r in rels if r.rule_id.startswith(BOUNDARY)) == written
    assert {c.bank for c in laws.required_checks()} == {b for b, c in cells.items() if c["kind"] == "REQUIRED"}
    assert laws.uncompiled_cells() == tuple(
        f"{BOUNDARY}{b}: not a bank of the registry" for b in ("HIER_PLUS", "HIER_MINUS")
    )


def test_a_verb_and_an_adjective_have_no_substantive_head_and_a_noun_is_untouched():
    readings = (
        Reading("wordnet:run:run.v.01", "run", "verb", "move fast"),
        Reading("wordnet:big:big.a.01", "big", "adj", "above average in size"),
        Reading("wordnet:dog:dog.n.01", "dog", "noun", "a domesticated animal"),
    )
    s, _ = _close(readings, None)
    assert _get(s, 0, "SOMEONE") == ZERO
    assert _get(s, 1, "SOMETHING") == ZERO
    assert _get(s, 2, "SOMEONE") & POS


def test_an_unwarranted_guard_selects_nothing():
    readings = (Reading("wordnet:love:love.n.01", "love", "noun", "a strong positive emotion"),)
    masks = guards.scopes(readings, {"own_denotatum=affective_feeling"})
    assert not masks["own_denotatum=affective_feeling"].any()
    assert bit(0) == ZERO


def test_a_conjoined_guard_holds_only_where_every_fact_does():
    readings = (Reading("w:afraid", "afraid", "adj", ""), Reading("w:fear", "fear", "noun", ""))
    name = laws.scope_name([("source_frame_family", "Fear"), ("own_role", "modifier_property_only")])
    unwarranted = laws.scope_name([("source_frame_family", "Fear"), ("own_role", "no_such_fact")])
    masks = guards.scopes(readings, {name, unwarranted}, _facts(2, {FEAR: [0, 1]}))
    assert masks[name].tolist() == [True, False]
    assert not masks[unwarranted].any()


def test_the_fear_boundary_writes_its_silences_and_domains_only_on_a_fear_adjective():
    readings = (
        Reading("w:afraid", "afraid", "adj", ""),
        Reading("w:fear", "fear", "noun", ""),
        Reading("w:sad", "sad", "adj", ""),
    )
    s, _ = _close(readings, _facts(3, {FEAR: [0, 1]}))
    assert _get(s, 0, "SEE") == _get(s, 0, "CAUSE") == _get(s, 0, "BIG") == SILENT
    assert _get(s, 0, "THEN") == NEG | ZERO | SILENT  # OPTIONAL: "optional NOW, not automatic future THEN"
    assert _get(s, 0, "MAYBE") == POS | SILENT  # OPTIONAL: present or unaddressed, never explicitly absent
    assert _get(s, 0, "KNOW") == _start("KNOW")
    for row in (1, 2):
        assert _get(s, row, "SEE") == _start("SEE")
        assert _get(s, row, "THEN") == _start("THEN")


def test_a_required_boundary_cell_is_checked_and_never_written_by_the_boundary():
    readings = (Reading("w:afraid", "afraid", "adj", ""),)
    s, scopes = _close(readings, _facts(1, {FEAR: [0]}))
    report = laws.check(s.masks, scopes, laws.required_checks())
    assert _get(s, 0, "THINK") == _start("THINK")
    assert report[BOUNDARY + "THINK"] == {"derived": 0, "open": 1, "contradicted": 0}
    assert report[BOUNDARY + "SOMEONE"] == {"derived": 1, "open": 0, "contradicted": 0}  # the modifier head law
    assert not any(r.rule_id == BOUNDARY + "THINK" for r in laws.compile_laws())


def test_companions_reach_a_reading_only_with_every_fact_their_rule_establishes():
    readings = (Reading("w:afraid", "afraid", "adj", ""), Reading("w:nervous", "nervous", "adj", ""))
    s, scopes = _close(readings, _facts(2, {name: [0] for name in FEAR_ADJ_FACTS} | {FEAR: [0, 1]}))
    for bank in ("THINK", "LIKE", "WHEN", "BECAUSE", "CAN", "HAPPEN"):
        assert _get(s, 0, bank) == POS
        assert _get(s, 1, bank) == _start(bank)
    report = laws.check(s.masks, scopes, laws.required_checks())
    assert report[BOUNDARY + "THINK"] == {"derived": 1, "open": 1, "contradicted": 0}
    assert _get(s, 0, "GOOD") == POS | NEG  # the signed felt-valence domain; the pole is the source tag's
