"""
M3b — persist / Tier-3 triage (RESOLVED_STRUCTURE_DESIGN.md).

Over a corpus of flagged trees, a tag-class that systematically flags is a
*mechanism fault* (distrust the class); scattered flags are SNPs. Hand-built
trees make the split deterministic.
"""

from gse.symbolic import triage_flags
from gse.symbolic.expression import Atom
from gse.symbolic.predicates import Comparison, TypeAssertion
from gse.symbolic.resolution import Entity


def _ent(lemma, pos, position, prims, eid, thread):
    return Entity(head=Atom(lemma=lemma, word_primitives=prims, role=None,
                            position=position, pos=pos),
                  entity_id=eid, type_thread=thread)


# Grounded common nouns (lots, to set a low baseline) + ungrounded propers.
_DOG = ("entity", "physical_entity", "object", "animal", "dog")
_CAT = ("entity", "physical_entity", "object", "animal", "cat")
_IDEA = ("entity", "abstraction", "psychological_feature", "idea")


def _grounded_noun(name, pos_idx, eid, thread):
    return _ent(name, "NOUN", pos_idx, {"x": 1}, eid, thread)


def _ungrounded_propn(name, pos_idx, eid):
    return _ent(name, "PROPN", pos_idx, {}, eid, ())   # no prims, no thread


def test_propn_flags_systematically():
    # 5 sentences, each: an ungrounded PROPN subject + a grounded NOUN kind.
    corpus = []
    for i in range(5):
        corpus.append(TypeAssertion(
            entity=_ungrounded_propn(f"name{i}", 0, f"p{i}"),
            kind=_grounded_noun("dog", 3, f"k{i}", _DOG)))
    # plus several extra grounded-noun-only trees to lower the NOUN baseline
    for i in range(5):
        corpus.append(TypeAssertion(
            entity=_grounded_noun("cat", 0, f"c{i}", _CAT),
            kind=_grounded_noun("animal", 3, f"a{i}", _DOG)))
    # one incomparable NOUN pair — the SNP
    corpus.append(Comparison(
        lhs=_grounded_noun("dog", 1, "sx", _DOG),
        rhs=_grounded_noun("idea", 4, "sy", _IDEA)))

    res = triage_flags(corpus)
    sys_pos = {p for p, _, _, _ in res.systematic}
    assert "PROPN" in sys_pos                     # PROPN is the systematic fault
    assert "NOUN" not in sys_pos                  # NOUN flags are not systematic
    # the incomparable NOUN flag survives as a SNP
    assert any(f.kind == "incomparable" and f.pos == "NOUN" for f in res.snps)
    # PROPN flags are NOT in the SNP residue (they're the systematic class)
    assert not any(f.pos == "PROPN" for f in res.snps)


def test_scattered_flags_are_all_snps():
    # No class concentrates: a single incomparable NOUN flag among grounded nouns.
    corpus = [Comparison(lhs=_grounded_noun("dog", 1, "a", _DOG),
                         rhs=_grounded_noun("idea", 4, "b", _IDEA))]
    corpus += [TypeAssertion(entity=_grounded_noun("cat", 0, f"c{i}", _CAT),
                             kind=_grounded_noun("animal", 3, f"k{i}", _DOG))
               for i in range(5)]
    res = triage_flags(corpus)
    assert res.systematic == ()                   # nothing systematic
    assert len(res.snps) == 1 and res.snps[0].kind == "incomparable"


def test_triage_is_deterministic():
    corpus = [TypeAssertion(entity=_ungrounded_propn("x", 0, "p"),
                            kind=_grounded_noun("dog", 3, "k", _DOG))
              for _ in range(4)]
    a, b = triage_flags(corpus), triage_flags(corpus)
    assert a.systematic == b.systematic and a.concentration == b.concentration
