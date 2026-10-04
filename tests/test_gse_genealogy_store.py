"""
M2.2a — the DB-backed two-strand GenealogyStore (RESOLVED_STRUCTURE_DESIGN.md).

Verifies real WordNet word-threads and sparse-wiki world-threads flow through
the provider and into resolve_references / emit v2. Skips cleanly if the local
genealogy.db hasn't been built (scripts/build_genealogy_db.py).
"""

from pathlib import Path

import pytest

from gse.api import GSEEncoder
from gse.symbolic import (
    GenealogyStore,
    emit,
    evaluate_tree,
    from_trace,
    resolve,
    resolve_references,
)
from gse.symbolic.expression import Atom
from gse.symbolic.predicates import TypeAssertion
from gse.symbolic.resolution import Entity

_DB = Path("data/genealogy.db")
pytestmark = pytest.mark.skipif(not _DB.exists(), reason="genealogy.db not built (scripts/build_genealogy_db.py)")


@pytest.fixture(scope="module")
def store():
    s = GenealogyStore()
    yield s
    s.close()


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


# -- word strand (WordNet) ---------------------------------------------------


def test_word_thread_is_root_to_leaf(store):
    t = store.thread("dog", "NOUN", is_proper=False)
    assert t[0] == "entity"  # WordNet root
    assert t[-1] == "dog"  # leaf is the lemma
    assert "animal" in t  # climbs the real lineage


def test_word_thread_covers_thane_and_king(store):
    assert store.thread("thane", "NOUN", False)[-1] == "thane"
    king = store.thread("king", "NOUN", False)
    assert king[-1] == "king" and "person" in king


def test_candidates_expose_multiple_senses(store):
    # 'king' is polysemous in WordNet — the selector (M2.2b) needs them all.
    cands = store.candidates("king", "NOUN", False)
    assert len(cands) > 1
    assert all(c[0] == "entity" for c in cands)


def test_unknown_lemma_returns_empty(store):
    assert store.thread("zzqxnotaword", "NOUN", False) == ()


def test_pronoun_gets_no_thread(store):
    # A pronoun's identity is its antecedent, not a WordNet homograph ("I"→iodine).
    assert store.candidates("i", "PRON", is_proper=False) == []
    assert store.thread("he", "PRON", is_proper=False) == ()


# -- world strand (sparse-wiki) ---------------------------------------------


def test_world_strand_returns_thing_rooted_lineage(store):
    # Pull a real world label from the store's own db, then resolve it.
    row = store._conn.execute("SELECT label FROM world_thread WHERE depth>=3 LIMIT 1").fetchone()
    assert row is not None, "world_thread should be populated"
    label = row[0]
    t = store.thread(label, "PROPN", is_proper=True)
    assert t[0] == "Thing"  # DBpedia world root
    assert len(t) >= 3


# -- end-to-end: real threads into entity-refs -------------------------------


def test_threads_flow_into_entity_refs(encoder, store):
    tree = evaluate_tree(resolve(from_trace(encoder.encode("Spot is a dog"))))
    resolved = resolve_references(tree, store)
    node = emit(resolved)
    assert node["op"] == "TYPE_ASSERT"
    kind = node["args"][1]  # "dog"
    assert kind["lemma"] == "dog"
    assert kind["type_thread"][-1] == "dog"
    assert "animal" in kind["type_thread"]


def test_store_satisfies_provider_via_resolve_references(store):
    # A hand-built tree, annotated by the real store.
    thane = Entity(head=Atom(lemma="thane", pos="NOUN", position=2))
    macbeth = Entity(head=Atom(lemma="macbeth", pos="PROPN", position=0))
    tree = TypeAssertion(entity=macbeth, kind=thane)
    out = resolve_references(tree, store)
    assert out.kind.type_thread[-1] == "thane"
    # 'macbeth' is a proper noun; WordNet has macbeth.n.01 as the word fallback.
    assert out.entity.entity_id is not None
