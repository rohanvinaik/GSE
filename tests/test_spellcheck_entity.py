"""Entity-leg spell-correction: the alias-free proper-noun instance of the
noisy-channel discipline (gse/nlp/spellcheck_entity.py).

Two layers: synthetic-fixture tests pin the DISCIPLINE (grounding gate, margin,
anchor corroboration, graceful absence); real-dictionary tests pin the behaviour
on the built substrate and guard the thesis (no redirect/alias data in the path).
"""
from __future__ import annotations

import sqlite3

import pytest

from gse.nlp.spellcheck_entity import (
    _DEFAULT_ENTITIES,
    EntityCorrection,
    _Entities,
    correct_entity,
    propose_entities,
)

_HAVE_DB = _DEFAULT_ENTITIES.available


# --------------------------------------------------------------------------- #
# synthetic fixture: the discipline                                           #
# --------------------------------------------------------------------------- #
def _fixture(tmp_path, rows, n_entities=1000):
    db = tmp_path / "entities.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE entity_names(name TEXT, canon TEXT, pagerank REAL);"
        "CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);"
        "CREATE INDEX idx_entity_name ON entity_names(name);"
    )
    conn.executemany("INSERT INTO entity_names VALUES(?,?,?)", rows)
    conn.execute("INSERT INTO meta VALUES('n_entities', ?)", (str(n_entities),))
    conn.commit()
    conn.close()
    return _Entities(str(db))


def test_absent_db_is_inert():
    ents = _Entities("/nonexistent/spell_entities.db")
    r = correct_entity("bosina", entities=ents)
    assert r.fired is False and r.committed is None
    assert "inert" in r.note


def test_grounding_name_never_touched(tmp_path):
    ents = _fixture(tmp_path, [("smithe", "john smithe", 0.4)])
    r = correct_entity("smithe", entities=ents, word_pool=())   # a real (rare) name
    assert r.fired is False and r.committed == "smithe"


def test_decisive_margin_commits(tmp_path):
    # one edit away; pagerank .99 vs .30 -> rank cost separates decisively
    ents = _fixture(tmp_path, [("bosnia", "bosnia and herzegovina", 0.99),
                               ("bovnia", "bovnia minor", 0.30)])
    r = correct_entity("bosina", entities=ents, anchors_fn=lambda c: {}, word_pool=())
    assert r.committed == "bosnia"


def test_close_priors_abstain(tmp_path):
    ents = _fixture(tmp_path, [("karlow", "karlow bridge", 0.80),
                               ("carlow", "county carlow", 0.80)])
    r = correct_entity("tarlow", entities=ents, anchors_fn=lambda c: {}, word_pool=())
    assert r.committed is None and len(r.ranked) == 2


def test_anchor_corroboration_confirms_unique_candidate(tmp_path):
    ents = _fixture(tmp_path, [("karlow", "karlow bridge", 0.80),
                               ("carlow", "county carlow", 0.80)])
    anchors = {"county carlow": {"ireland": 0.9}, "karlow bridge": {}}
    r = correct_entity("tarlow", context_words=["ireland", "farm"],
                       entities=ents, anchors_fn=lambda c: anchors.get(c, {}),
                       word_pool=())
    assert r.committed == "carlow"
    assert "corroborated" in r.note


def test_two_corroborated_candidates_abstain(tmp_path):
    ents = _fixture(tmp_path, [("karlow", "karlow bridge", 0.80),
                               ("carlow", "county carlow", 0.80)])
    anchors = {"county carlow": {"ireland": 0.9}, "karlow bridge": {"ireland": 0.2}}
    r = correct_entity("tarlow", context_words=["ireland"],
                       entities=ents, anchors_fn=lambda c: anchors.get(c, {}),
                       word_pool=())
    assert r.committed is None


def test_every_candidate_grounds_in_entity_space(tmp_path):
    ents = _fixture(tmp_path, [("bosnia", "bosnia and herzegovina", 0.99)])
    for c in propose_entities("bosina", entities=ents):
        assert ents.grounds(c.name)


# --------------------------------------------------------------------------- #
# real dictionary: behaviour + thesis guards                                  #
# --------------------------------------------------------------------------- #
needs_db = pytest.mark.skipif(not _HAVE_DB, reason="spell_entities.db not built")


@needs_db
@pytest.mark.parametrize("name", ["shakespear", "melbourn", "einstein", "bosnia"])
def test_real_entity_name_never_corrected(name):
    # incl. rare-but-real names (Richmond Shakespear; Melbourn, Cambridgeshire)
    r = correct_entity(name)
    assert r.fired is False


@needs_db
@pytest.mark.parametrize("typo,gold", [
    ("bosina", "bosnia"), ("einstien", "einstein"),
    ("hezegovina", "herzegovina"), ("shakespere", "shakespeare"),
])
def test_recovers_misspelled_entity(typo, gold):
    assert correct_entity(typo).committed == gold


@needs_db
@pytest.mark.parametrize("redirect", ["einstien", "napolean", "goverment"])
def test_no_redirect_aliases_in_dictionary(redirect):
    """THESIS GUARD: Wikipedia's misspelling-redirects exist in genealogy.db as alias
    rows; the entity dictionary must never contain them as names. If this fails,
    collated error-pair data has leaked into the correction path."""
    assert not _DEFAULT_ENTITIES.grounds(redirect)


@needs_db
def test_deterministic():
    a = correct_entity("bosina")
    b = correct_entity("bosina")
    assert a == b == EntityCorrection(a.surface, a.fired, a.committed, a.canon,
                                      a.ranked, a.note)


@needs_db
def test_server_sentence_entity_commit_and_casing():
    from gse.mcp.spell_server import spell_suggest
    r = spell_suggest("Einstien published the theory of relativity")
    assert r["corrected"].startswith("Einstein ")


@needs_db
def test_server_rare_tail_name_offer_only():
    from gse.mcp.spell_server import spell_suggest
    r = spell_suggest("we visited Bosina during the war")
    assert "Bosina" in r["corrected"]                 # never auto-applied
    tok = next(t for t in r["tokens"] if t["surface"] == "Bosina")
    assert tok["misspelled"] is False and tok["suggestions"]


@needs_db
def test_server_real_name_left_alone():
    from gse.mcp.spell_server import spell_suggest
    r = spell_suggest("we flew to Melbourn yesterday")
    assert "Melbourn" in r["corrected"]
