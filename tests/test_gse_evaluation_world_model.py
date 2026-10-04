"""Manual contract tests for gse.evaluation.world_model."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.evaluation.world_model import (
    Entity,
    EntityType,
    Relation,
    SimpleWorldModel,
)


class TestEntityHasProperty:
    def test_present_no_value_returns_true(self):
        e = Entity(name="x", entity_type=EntityType.OBJECT, properties={"color": "red"})
        assert e.has_property("color")

    def test_absent_returns_false(self):
        e = Entity(name="x", entity_type=EntityType.OBJECT, properties={})
        assert not e.has_property("color")

    def test_matching_value_returns_true(self):
        e = Entity(name="x", entity_type=EntityType.OBJECT, properties={"color": "red"})
        assert e.has_property("color", "red")

    def test_mismatching_value_returns_false(self):
        e = Entity(name="x", entity_type=EntityType.OBJECT, properties={"color": "red"})
        assert not e.has_property("color", "blue")


class TestEntityGetProperty:
    def test_returns_value(self):
        e = Entity(name="x", entity_type=EntityType.OBJECT, properties={"size": "big"})
        assert e.get_property("size") == "big"

    def test_default_when_absent(self):
        e = Entity(name="x", entity_type=EntityType.OBJECT, properties={})
        assert e.get_property("size") is None
        assert e.get_property("size", default="medium") == "medium"


class TestRelationAsTuple:
    def test_returns_tuple(self):
        r = Relation("fido", "bigger_than", "whiskers")
        assert r.as_tuple() == ("fido", "bigger_than", "whiskers")


class TestSimpleWorldModelAddEntity:
    def test_adds_entity(self):
        w = SimpleWorldModel()
        w.add_entity(Entity(name="dog", entity_type=EntityType.ANIMAL))
        assert "dog" in w.entities

    def test_aliases_indexed(self):
        w = SimpleWorldModel()
        e = Entity(name="dog", entity_type=EntityType.ANIMAL, aliases={"the dog", "puppy"})
        w.add_entity(e)
        assert w.get_entity("the dog") is e
        assert w.get_entity("puppy") is e

    def test_case_insensitive_lookup(self):
        w = SimpleWorldModel()
        w.add_entity(Entity(name="Dog", entity_type=EntityType.ANIMAL))
        assert w.get_entity("DOG") is not None


class TestSimpleWorldModelAddRelation:
    def test_adds_relation(self):
        w = SimpleWorldModel()
        w.add_relation(Relation("a", "bigger_than", "b"))
        assert len(w.relations) == 1

    def test_indexes_for_lookup(self):
        w = SimpleWorldModel()
        w.add_relation(Relation("a", "bigger_than", "b"))
        assert w._relation_index[("a", "bigger_than", "b")] is True


class TestEntityHasPropertyMethod:
    def test_entity_not_found_returns_none(self):
        w = SimpleWorldModel()
        assert w.entity_has_property("xyzzy", "color") is None

    def test_entity_with_property(self):
        w = SimpleWorldModel()
        w.add_entity(Entity(name="dog", entity_type=EntityType.ANIMAL, properties={"color": "brown"}))
        assert w.entity_has_property("dog", "color")
        assert w.entity_has_property("dog", "color", "brown")
        assert not w.entity_has_property("dog", "color", "blue")


class TestRelationHolds:
    def test_known_true_relation(self):
        w = SimpleWorldModel()
        w.add_entity(Entity(name="a", entity_type=EntityType.OBJECT))
        w.add_entity(Entity(name="b", entity_type=EntityType.OBJECT))
        w.add_relation(Relation("a", "bigger_than", "b"))
        assert w.relation_holds("a", "bigger_than", "b") is True

    def test_undefined_relation_returns_false(self):
        w = SimpleWorldModel()
        w.add_entity(Entity(name="a", entity_type=EntityType.OBJECT))
        w.add_entity(Entity(name="b", entity_type=EntityType.OBJECT))
        # Relation not defined but both entities exist
        assert w.relation_holds("a", "bigger_than", "b") is False

    def test_unknown_entity_returns_none(self):
        w = SimpleWorldModel()
        assert w.relation_holds("xyzzy", "x", "y") is None


class TestEvaluateComparison:
    def test_big_maps_to_bigger_than(self):
        w = SimpleWorldModel()
        w.add_entity(Entity(name="a", entity_type=EntityType.OBJECT))
        w.add_entity(Entity(name="b", entity_type=EntityType.OBJECT))
        w.add_relation(Relation("a", "bigger_than", "b"))
        assert w.evaluate_comparison("a", "big", "b") is True

    def test_tall_maps_to_taller_than(self):
        w = SimpleWorldModel()
        w.add_entity(Entity(name="a", entity_type=EntityType.PERSON))
        w.add_entity(Entity(name="b", entity_type=EntityType.PERSON))
        w.add_relation(Relation("a", "taller_than", "b"))
        assert w.evaluate_comparison("a", "tall", "b") is True

    def test_unknown_property_falls_back(self):
        """For unknown properties, falls back to '{prop}_than'."""
        w = SimpleWorldModel()
        w.add_entity(Entity(name="a", entity_type=EntityType.OBJECT))
        w.add_entity(Entity(name="b", entity_type=EntityType.OBJECT))
        w.add_relation(Relation("a", "custom_than", "b"))
        assert w.evaluate_comparison("a", "custom", "b") is True

    def test_case_insensitive_property(self):
        w = SimpleWorldModel()
        w.add_entity(Entity(name="a", entity_type=EntityType.OBJECT))
        w.add_entity(Entity(name="b", entity_type=EntityType.OBJECT))
        w.add_relation(Relation("a", "bigger_than", "b"))
        assert w.evaluate_comparison("a", "BIG", "b") is True


class TestGetAllEntities:
    def test_returns_unique_entities(self):
        w = SimpleWorldModel()
        w.add_entity(Entity(name="dog", entity_type=EntityType.ANIMAL, aliases={"the dog"}))
        w.add_entity(Entity(name="cat", entity_type=EntityType.ANIMAL))
        all_entities = w.get_all_entities()
        # dog and cat are 2 unique
        assert len(all_entities) == 2

    def test_empty_world(self):
        w = SimpleWorldModel()
        assert w.get_all_entities() == []


class TestRepr:
    def test_includes_counts(self):
        w = SimpleWorldModel()
        w.add_entity(Entity(name="a", entity_type=EntityType.OBJECT))
        w.add_relation(Relation("a", "x", "a"))
        s = repr(w)
        assert "entities=" in s
        assert "relations=" in s


class TestCreateToyWorld:
    def test_creates_populated_world(self):
        w = SimpleWorldModel.create_toy_world()
        assert len(w.entities) > 0
        assert len(w.relations) > 0

    def test_contains_known_entities(self):
        w = SimpleWorldModel.create_toy_world()
        assert w.get_entity("fido") is not None
        assert w.get_entity("whiskers") is not None
        assert w.get_entity("john") is not None

    def test_fido_bigger_than_whiskers(self):
        w = SimpleWorldModel.create_toy_world()
        assert w.relation_holds("fido", "bigger_than", "whiskers") is True
        # Asymmetric: whiskers NOT bigger than fido
        assert w.relation_holds("whiskers", "bigger_than", "fido") is False

    def test_dog_alias_lookup(self):
        w = SimpleWorldModel.create_toy_world()
        # "the dog" should resolve to fido
        dog = w.get_entity("the dog")
        assert dog is not None
        assert dog.name == "fido"

    def test_jumbo_is_animal(self):
        w = SimpleWorldModel.create_toy_world()
        jumbo = w.get_entity("jumbo")
        assert jumbo.entity_type == EntityType.ANIMAL


class TestEvaluateTraceComparison:
    def test_no_operators_returns_none(self):
        w = SimpleWorldModel.create_toy_world()

        class FakeTrace:
            operators = []

        assert w.evaluate_trace_comparison(FakeTrace()) is None

    def test_non_comp_than_operator_skipped(self):
        w = SimpleWorldModel.create_toy_world()

        class FakeOp:
            primitive = "COMP_BUT"

        class FakeTrace:
            operators = [FakeOp()]

        assert w.evaluate_trace_comparison(FakeTrace()) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
