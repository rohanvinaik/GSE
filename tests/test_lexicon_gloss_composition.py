"""Positive gloss composition (gloss-composition.md): the rules the prototype runs established, on a fixture lexicon."""

import json
import sqlite3
from pathlib import Path

import pytest

from GSE.curation.lexicon_builder import gloss_composition as gcm
from GSE.curation.lexicon_builder.foundation import BANKS

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    not (ROOT / gcm.gd.CATEGORY_TABLE).exists(), reason="the NSM chart text (identity banks) is not on this machine"
)
OPEN = [-1, 0, 1]


def _domains(**settled):
    return json.dumps({bank: [settled[bank]] if bank in settled else OPEN for bank in BANKS})


def _lexicon(tmp_path, rows, parses):
    """rows: (entry_id, lemma, pos, gloss, settled values)."""
    conn = sqlite3.connect(tmp_path / "fixture.db")
    conn.execute("CREATE TABLE lexemes (id INTEGER PRIMARY KEY, lemma TEXT, pos TEXT, gloss TEXT)")
    conn.execute("CREATE TABLE definition_states (entry_id TEXT, lexeme_id INTEGER, domains TEXT)")
    for k, (entry, lemma, pos, gloss, settled) in enumerate(rows, 1):
        conn.execute("INSERT INTO lexemes VALUES (?, ?, ?, ?)", (k, lemma, pos, gloss))
        conn.execute("INSERT INTO definition_states VALUES (?, ?, ?)", (entry, k, _domains(**settled)))
    return gcm.Lexicon(conn, ROOT, parses)


def _gd(genus=None, differentia=(), negated=False, template="genus_differentia"):
    return {"template": template, "genus": genus, "differentia": list(differentia), "negated": negated}


def test_a_homonym_never_lends_its_values(tmp_path):
    # "nail" the unit holds QUANTITY; "nail" the fastener says nothing: "brad: a small nail" gains no QUANTITY.
    lex = _lexicon(
        tmp_path,
        [
            ("w:nail:unit", "nail", "noun", "a unit of length", {"QUANTITY": 1, "SOMETHING": 1}),
            ("w:nail:fastener", "nail", "noun", "a metal fastener", {"SOMETHING": 1}),
            ("w:brad", "brad", "noun", "a small nail", {}),
        ],
        {"w:brad": _gd("nail")},
    )
    comp = lex.close()
    assert comp.derived.get("w:brad") == {"SOMETHING": 1}


def test_a_predicate_takes_its_genus_not_its_arguments(tmp_path):
    lex = _lexicon(
        tmp_path,
        [
            ("w:diligent", "diligent", "adj", "careful and persistent", {"GOOD": 1}),
            ("w:investigation", "investigation", "noun", "an inquiry", {"DO": 1}),
            ("w:inquisitory", "inquisitory", "adj", "diligent in investigation", {}),
        ],
        {"w:inquisitory": _gd("diligent", ["investigation"])},
    )
    assert lex.close().derived["w:inquisitory"] == {"GOOD": 1}


def test_a_noun_takes_only_its_genus(tmp_path):
    lex = _lexicon(
        tmp_path,
        [
            ("w:hen", "hen", "noun", "a bird", {"BODY": 1}),
            ("w:lay", "lay", "verb", "to produce eggs", {"DO": 1, "CAUSE": 1}),
            ("w:layer", "layer", "noun", "a hen that lays eggs", {}),
        ],
        {"w:layer": _gd("hen", ["lay"])},
    )
    assert lex.close().derived.get("w:layer") == {"BODY": 1}


def test_identity_enters_only_through_a_nouns_genus(tmp_path):
    lex = _lexicon(
        tmp_path,
        [
            ("w:superior", "superior", "noun", "a person of higher rank", {"SOMEONE": 1}),
            ("w:diligent", "diligent", "adj", "careful and persistent", {"GOOD": 1}),
            ("w:overwhelmed", "overwhelmed", "adj", "overcome by a superior", {}),
            ("w:inquisitory", "inquisitory", "adj", "diligent in inquiry", {}),
        ],
        {"w:overwhelmed": _gd("overcome", ["superior"]), "w:inquisitory": _gd("diligent", ["inquiry"])},
    )
    comp = lex.close()
    assert "w:overwhelmed" not in comp.derived
    assert comp.derived["w:inquisitory"] == {"GOOD": 1}


def test_an_identity_template_is_its_operand(tmp_path):
    lex = _lexicon(
        tmp_path,
        [
            ("w:autistic", "autistic", "noun", "a person with autism", {"SOMEONE": 1}),
            ("w:autistics", "autistics", "noun", "plural of autistic", {}),
        ],
        {"w:autistics": _gd("autistic", template="plural_of")},
    )
    assert lex.close().derived["w:autistics"] == {"SOMEONE": 1}


def test_a_negated_gloss_adds_no_differentia(tmp_path):
    lex = _lexicon(
        tmp_path,
        [
            ("w:happy", "happy", "adj", "feeling joy", {"FEEL": 1, "GOOD": 1}),
            ("w:glum", "glum", "adj", "not happy", {}),
        ],
        {"w:glum": _gd(None, ["happy"], negated=True)},
    )
    assert "w:glum" not in lex.close().derived


def test_nothing_composed_is_a_zero_and_conflicts_are_not_admitted(tmp_path):
    lex = _lexicon(
        tmp_path,
        [
            ("wordnet:kind:kind.n.09", "kind", "noun", "a good one", {"GOOD": 1}),
            ("wordnet:cruel:cruel.n.09", "cruel", "noun", "a bad one", {"GOOD": -1}),
            ("wordnet:mixed:mixed.n.09", "mixed", "noun", "a kind and a cruel one", {}),
            ("w:kind", "kind", "adj", "good", {"GOOD": 1}),
            ("w:held", "held", "adj", "kind", {"GOOD": -1}),
            ("w:zeroed", "zeroed", "noun", "a dog", {}),
            ("w:dog", "dog", "noun", "an animal", {"GOOD": 0, "ALIVE": 1}),
        ],
        {
            "wordnet:mixed:mixed.n.09": {**_gd("one"), "synset_genus": ["cruel.n.09", "kind.n.09"]},
            "w:held": _gd("kind"),
            "w:zeroed": _gd("dog"),
        },
    )
    comp = lex.close()
    assert "wordnet:mixed:mixed.n.09" not in comp.derived and comp.contested["wordnet:mixed:mixed.n.09"]["GOOD"]
    assert "w:held" not in comp.derived
    assert {r["kind"] for r in comp.contradictions} == {"OPPOSES_HELD_VALUE"}
    assert comp.derived["w:zeroed"] == {"ALIVE": 1}  # the genus's stored GOOD 0 is not composed
    assert all(v for cells in comp.derived.values() for v in cells.values())


def test_the_fixpoint_reaches_through_a_chain(tmp_path):
    lex = _lexicon(
        tmp_path,
        [
            ("w:feeling", "feeling", "noun", "an experience", {"FEEL": 1}),
            ("w:emotion", "emotion", "noun", "a strong feeling", {}),
            ("w:anger", "anger", "noun", "a hostile emotion", {}),
        ],
        {"w:emotion": _gd("feeling"), "w:anger": _gd("emotion")},
    )
    comp = lex.close()
    assert comp.derived["w:anger"] == {"FEEL": 1} and comp.passes == [1, 1]
    assert comp.trace["w:anger"]["FEEL"].startswith("pass 2")
