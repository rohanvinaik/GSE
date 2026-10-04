"""Phase B5 tests — argument resolution.

Covers:
* Phrase → Entity collapse (function words filtered, head identified).
* Possessive grouping ("Mike's dog" → nested Entity).
* Single-sentence pronoun binding (most-recent matching entity).
* Idempotence (resolve(resolve(x)) shape-stable).
"""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import Atom, Op, Phrase, from_trace, resolve
from gse.symbolic.resolution import Entity


@pytest.fixture(scope="module")
def encoder():
    return GSEEncoder()


def _atom(lemma: str, pos: str = "NOUN") -> Atom:
    return Atom(lemma=lemma, word_primitives={}, position=0, pos=pos)


# ---------------------------------------------------------------------------
# Phrase → Entity collapse
# ---------------------------------------------------------------------------


class TestPhraseCollapse:
    def test_single_noun_in_phrase_becomes_entity(self):
        # "the dog" → Phrase([the(DET), dog(NOUN)]) → Entity(head=dog)
        phrase = Phrase(atoms=[_atom("the", "DET"), _atom("dog", "NOUN")])
        result = resolve(phrase)
        assert isinstance(result, Entity)
        assert result.head.lemma == "dog"

    def test_function_words_filtered(self):
        # "the big dog" → keep "big" only if it's the entity head?
        # ADJ is predicate-ish; for v1 the entity head is the rightmost NOUN/PROPN.
        phrase = Phrase(
            atoms=[
                _atom("the", "DET"),
                _atom("big", "ADJ"),
                _atom("dog", "NOUN"),
            ]
        )
        result = resolve(phrase)
        assert isinstance(result, Entity)
        assert result.head.lemma == "dog"

    def test_lone_entity_atom_promoted(self):
        # Bare Atom that's a NOUN/PROPN gets wrapped in Entity by resolve
        a = _atom("rex", "PROPN")
        result = resolve(a)
        assert isinstance(result, Entity)
        assert result.head.lemma == "rex"

    def test_non_entity_atom_left_unchanged(self):
        # ADJ doesn't get wrapped — only NOUN/PROPN/PRON do
        a = _atom("happy", "ADJ")
        result = resolve(a)
        assert isinstance(result, Atom)  # left as-is

    def test_empty_phrase_stays_phrase(self):
        result = resolve(Phrase(atoms=[]))
        assert isinstance(result, Phrase)
        assert result.atoms == []


class TestModifierPreservation:
    """v2 fix: ADJ/ADV atoms from the source Phrase survive as Entity.modifier."""

    def test_adj_in_phrase_becomes_entity_modifier(self):
        # "the tall dog" → Entity(head=dog, modifier=tall)
        phrase = Phrase(
            atoms=[
                _atom("the", "DET"),
                _atom("tall", "ADJ"),
                _atom("dog", "NOUN"),
            ]
        )
        result = resolve(phrase)
        assert isinstance(result, Entity)
        assert result.head.lemma == "dog"
        assert result.modifier is not None
        assert result.modifier.lemma == "tall"

    def test_no_adj_means_no_modifier(self):
        phrase = Phrase(atoms=[_atom("the", "DET"), _atom("dog", "NOUN")])
        result = resolve(phrase)
        assert isinstance(result, Entity)
        assert result.modifier is None

    def test_adv_also_captured(self):
        phrase = Phrase(atoms=[_atom("the", "DET"), _atom("quickly", "ADV"), _atom("dog", "NOUN")])
        result = resolve(phrase)
        assert isinstance(result, Entity)
        assert result.modifier is not None
        assert result.modifier.lemma == "quickly"


class TestPossessiveGrouping:
    def test_propn_possessive_noun_nests(self):
        # "Mike's dog" → Entity(head=dog, possessor=Entity(head=Mike))
        phrase = Phrase(
            atoms=[
                _atom("mike", "PROPN"),
                Atom(lemma="'s", word_primitives={}, position=1, pos="PART"),
                _atom("dog", "NOUN"),
            ]
        )
        result = resolve(phrase)
        assert isinstance(result, Entity)
        assert result.head.lemma == "dog"
        assert result.possessor is not None
        assert result.possessor.head.lemma == "mike"

    def test_no_possessive_no_nesting(self):
        # "Mike Rex" (a meaningless juxtaposition) shouldn't produce a
        # possessor — just falls back to taking the last entity
        phrase = Phrase(atoms=[_atom("mike", "PROPN"), _atom("rex", "PROPN")])
        result = resolve(phrase)
        assert isinstance(result, Entity)
        assert result.head.lemma == "rex"
        assert result.possessor is None


# ---------------------------------------------------------------------------
# Pronoun binding
# ---------------------------------------------------------------------------


class TestPronounBinding:
    def test_he_bound_to_most_recent_propn(self):
        # Construct an Op with two args: first is "Mike", second is "he"
        # (a pronoun Entity). Resolve should bind "he" → Mike.
        mike_entity = Entity(head=_atom("mike", "PROPN"))
        he_entity = Entity(head=_atom("he", "PRON"))
        op = Op(primitive="COMP_BECAUSE", operation="CAUSAL_SOURCE", arity=2, args=[mike_entity, he_entity])
        result = resolve(op)
        assert isinstance(result, Op)
        # The "he" entity should now point to Mike's head
        assert result.args[1].head.lemma == "mike"

    def test_unbound_pronoun_left_alone(self):
        # No antecedent before the pronoun — leave it as-is
        he_entity = Entity(head=_atom("he", "PRON"))
        result = resolve(he_entity)
        assert isinstance(result, Entity)
        assert result.head.lemma == "he"

    def test_resolution_uses_most_recent_not_first(self):
        # "Mike", "Rex", "he" — "he" should bind to Rex (most recent)
        mike = Entity(head=_atom("mike", "PROPN"))
        rex = Entity(head=_atom("rex", "PROPN"))
        he = Entity(head=_atom("he", "PRON"))
        op = Op(
            primitive="COMP_SO",
            operation="CONSEQUENCE",
            arity=2,
            args=[
                Phrase(atoms=[])
                if False
                else Op(  # nested op to put Mike+Rex in same flow
                    primitive="COMP_BUT", operation="CONTRAST", arity=2, args=[mike, rex]
                ),
                he,
            ],
        )
        result = resolve(op)
        # Walking left-to-right: Mike seen first, then Rex, then he → he becomes Rex
        # Find the "he" slot (right arg of outer Op)
        he_resolved = result.args[1]
        assert isinstance(he_resolved, Entity)
        assert he_resolved.head.lemma == "rex"


# ---------------------------------------------------------------------------
# End-to-end: encoded sentence → AST → resolved
# ---------------------------------------------------------------------------


class TestEndToEndResolution:
    def test_simple_sentence_entities_recovered(self, encoder):
        trace = encoder.encode("Mike is taller than Rex")
        expr = resolve(from_trace(trace))
        # After resolution, both args of the Op should be Entities
        assert isinstance(expr, Op)
        lhs = expr.args[0]
        rhs = expr.args[1]
        # LHS may have been collapsed from a Phrase containing Mike + is + taller;
        # the Entity head should be Mike (the PROPN)
        assert _find_entity_lemma(lhs, "mike")
        assert _find_entity_lemma(rhs, "rex")

    def test_possessive_in_sentence_grouped(self, encoder):
        trace = encoder.encode("Mike's dog ran fast")
        expr = resolve(from_trace(trace))
        # No COMP_* operator — top-level should be a Phrase or Entity
        # containing "dog" as entity head with Mike as possessor
        assert _contains_possessive_entity(expr, head="dog", possessor="mike")

    def test_pronoun_bound_in_causal_sentence(self, encoder):
        trace = encoder.encode("Mike left because he was happy")
        expr = resolve(from_trace(trace))
        # The "he" pronoun should be bound to Mike. Check by walking the
        # AST and verifying no "he" lemma appears in any Entity head.
        assert not _contains_entity_lemma(expr, "he"), f"Pronoun 'he' was not resolved to Mike: {expr!r}"

    def test_resolution_is_idempotent(self, encoder):
        trace = encoder.encode("Mike is taller than Rex")
        once = resolve(from_trace(trace))
        twice = resolve(once)
        # Same shape, same lemmas — Entity nodes pass through unchanged
        assert _structure_equal(once, twice)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _find_entity_lemma(expr, lemma):
    """True if some Entity in the tree has this lemma at head or possessor."""
    if isinstance(expr, Entity):
        if expr.head.lemma == lemma:
            return True
        if expr.possessor is not None and _find_entity_lemma(expr.possessor, lemma):
            return True
        return False
    if isinstance(expr, Op):
        return any(_find_entity_lemma(a, lemma) for a in expr.args)
    if isinstance(expr, Phrase):
        return any(a.lemma == lemma for a in expr.atoms)
    if isinstance(expr, Atom):
        return expr.lemma == lemma
    return False


def _contains_possessive_entity(expr, head, possessor):
    """Search the tree for Entity(head=head, possessor=Entity(head=possessor))."""
    if isinstance(expr, Entity):
        if expr.head.lemma == head and expr.possessor is not None and expr.possessor.head.lemma == possessor:
            return True
        if expr.possessor is not None:
            return _contains_possessive_entity(expr.possessor, head, possessor)
        return False
    if isinstance(expr, Op):
        return any(_contains_possessive_entity(a, head, possessor) for a in expr.args)
    if isinstance(expr, Phrase):
        # Phrase didn't get collapsed — search atoms
        return False
    return False


def _contains_entity_lemma(expr, lemma):
    """True if some Entity in the tree has this exact lemma at its head."""
    if isinstance(expr, Entity):
        if expr.head.lemma == lemma:
            return True
        if expr.possessor is not None and _contains_entity_lemma(expr.possessor, lemma):
            return True
        return False
    if isinstance(expr, Op):
        return any(_contains_entity_lemma(a, lemma) for a in expr.args)
    if isinstance(expr, Phrase):
        return any(a.lemma == lemma and a.pos == "PRON" for a in expr.atoms)
    return False


def _structure_equal(a, b):
    """Shape + lemma equality (ignores pre-Entity Phrase identity)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, Atom):
        return a.lemma == b.lemma
    if isinstance(a, Entity):
        if a.head.lemma != b.head.lemma:
            return False
        if (a.possessor is None) != (b.possessor is None):
            return False
        if a.possessor is not None:
            return _structure_equal(a.possessor, b.possessor)
        return True
    if isinstance(a, Op):
        return (
            a.operation == b.operation
            and len(a.args) == len(b.args)
            and all(_structure_equal(x, y) for x, y in zip(a.args, b.args))
        )
    return False
