"""
M4-3a — document-scope resolution (RESOLVED_STRUCTURE_DESIGN.md §6).

Cross-sentence coreference: one referent shares an entity_id across sentences,
and a pronoun left unbound by its own sentence binds to a prior antecedent.
Hand-built trees make the mechanism deterministic; the real encoder confirms it
end-to-end.
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
    resolve_document,
)
from gse.symbolic.expression import Atom
from gse.symbolic.predicates import TypeAssertion
from gse.symbolic.resolution import Entity


def _refs(node):
    """Collect every emitted entity-ref (dicts carrying entity_id)."""
    out = []
    if isinstance(node, dict):
        if "entity_id" in node:
            out.append(node)
        for v in node.values():
            out += _refs(v)
    elif isinstance(node, list):
        for v in node:
            out += _refs(v)
    return out


def _ent(lemma, pos, position, eid=None):
    return Entity(
        head=Atom(lemma=lemma, word_primitives={"x": 1}, role=None, position=position, pos=pos), entity_id=eid
    )


# -- mechanism (hand-built) -------------------------------------------------


def test_same_referent_shares_id_across_sentences():
    # "The dog barks. The dog sleeps." → one 'dog' id spanning both trees.
    s1 = TypeAssertion(entity=_ent("dog", "NOUN", 1), kind=_ent("bark", "NOUN", 2))
    s2 = TypeAssertion(entity=_ent("dog", "NOUN", 1), kind=_ent("sleep", "NOUN", 2))
    r1, r2 = resolve_document([s1, s2])
    assert r1.entity.entity_id == r2.entity.entity_id  # same dog, same id


def test_cross_sentence_pronoun_binds_to_antecedent():
    # v1 binds to the MOST-RECENT prior entity, matching the within-sentence
    # binder — here 'duncan', not 'macbeth'. (Subject-preference / centering is
    # a documented refinement, not v1.) The mechanism — a cross-sentence pronoun
    # acquiring a prior referent's identity + shared id — is what's tested here.
    s1 = TypeAssertion(entity=_ent("macbeth", "PROPN", 0), kind=_ent("duncan", "PROPN", 2))
    s2 = TypeAssertion(entity=_ent("he", "PRON", 0), kind=_ent("king", "NOUN", 2))
    r1, r2 = resolve_document([s1, s2])
    assert r2.entity.head.lemma == "duncan"  # most-recent antecedent
    assert r2.entity.entity_id == r1.kind.entity_id  # shares duncan's id


def test_distinct_referents_distinct_ids_across_doc():
    s1 = TypeAssertion(entity=_ent("dog", "NOUN", 1), kind=_ent("animal", "NOUN", 3))
    s2 = TypeAssertion(entity=_ent("cat", "NOUN", 1), kind=_ent("animal", "NOUN", 3))
    r1, r2 = resolve_document([s1, s2])
    assert r1.entity.entity_id != r2.entity.entity_id  # dog ≠ cat
    # but 'animal' (the shared kind) is one id across both sentences
    assert r1.kind.entity_id == r2.kind.entity_id


def test_document_resolution_is_deterministic():
    def build():
        return [
            TypeAssertion(entity=_ent("dog", "NOUN", 1), kind=_ent("pet", "NOUN", 3)),
            TypeAssertion(entity=_ent("he", "PRON", 0), kind=_ent("good", "NOUN", 2)),
        ]

    a = resolve_document(build())
    b = resolve_document(build())
    assert [e.entity.entity_id for e in a] == [e.entity.entity_id for e in b]


# -- end-to-end (real encoder, store-gated) ---------------------------------

_DB = Path("data/genealogy.db")


@pytest.mark.skipif(not _DB.exists(), reason="genealogy.db not built")
def test_end_to_end_cross_sentence_coreference():
    with GSEEncoder() as enc, GenealogyStore() as store:
        trees = [
            evaluate_tree(resolve(from_trace(enc.encode(s))))
            for s in ["The dog is cuter than the cat", "The dog is bigger than the cat"]
        ]
        resolved = resolve_document(trees, store)
        # match on the thread leaf — the modifier ("cuter"/"bigger") folds into
        # the lemma string, but the referent (head 'dog') is one across sentences.
        dog_refs = [
            r for tree in resolved for r in _refs(emit(tree)) if r["type_thread"] and r["type_thread"][-1] == "dog"
        ]
        assert len(dog_refs) >= 2
        # one document-global id + one shared thread for 'dog' across both sentences
        assert len({r["entity_id"] for r in dog_refs}) == 1
        assert len({tuple(r["type_thread"]) for r in dog_refs}) == 1
