#!/usr/bin/env python3
"""
GSE Toy World Model for Truth-Conditional Evaluation.

A simple world model with entities, properties, and relations that can be
used to evaluate truth conditions of sentences encoded by GSE.

The world model serves as ground truth for testing GSE's semantic compiler
capabilities: Can we use the compiled trace to evaluate truth values?
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class EntityType(Enum):
    """Types of entities in our toy world."""

    ANIMAL = "animal"
    PERSON = "person"
    OBJECT = "object"
    PLACE = "place"


@dataclass
class Entity:
    """An entity in the world model."""

    name: str
    entity_type: EntityType
    properties: Dict[str, Any] = field(default_factory=dict)

    # Aliases for entity resolution
    aliases: Set[str] = field(default_factory=set)

    def has_property(self, prop: str, value: Any = None) -> bool:
        """Check if entity has a property (optionally with specific value)."""
        if prop not in self.properties:
            return False
        if value is None:
            return True
        return self.properties[prop] == value

    def get_property(self, prop: str, default: Any = None) -> Any:
        """Get a property value."""
        return self.properties.get(prop, default)


@dataclass
class Relation:
    """A relation between entities."""

    subject: str
    relation_type: str
    object: str
    value: bool = True  # For boolean relations

    def as_tuple(self) -> Tuple[str, str, str]:
        """Return as (subject, relation, object) tuple."""
        return (self.subject, self.relation_type, self.object)


class SimpleWorldModel:
    """
    A toy world model for evaluating truth conditions.

    Contains:
    - Named entities with types and properties
    - Binary relations between entities
    - Comparative relations (bigger_than, taller_than, etc.)

    Usage:
        world = SimpleWorldModel.create_toy_world()

        # Check property
        world.entity_has_property("fido", "color", "brown")  # True

        # Check relation
        world.relation_holds("fido", "bigger_than", "whiskers")  # True

        # Evaluate GSE trace
        world.evaluate_comparison_trace(trace)  # True/False
    """

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.relations: List[Relation] = []
        self._relation_index: Dict[Tuple[str, str, str], bool] = {}

    def add_entity(self, entity: Entity) -> None:
        """Add an entity to the world."""
        self.entities[entity.name.lower()] = entity
        # Index aliases
        for alias in entity.aliases:
            self.entities[alias.lower()] = entity

    def add_relation(self, relation: Relation) -> None:
        """Add a relation to the world."""
        self.relations.append(relation)
        # Index for fast lookup
        key = (relation.subject.lower(), relation.relation_type.lower(), relation.object.lower())
        self._relation_index[key] = relation.value

    def get_entity(self, name: str) -> Optional[Entity]:
        """Get entity by name or alias."""
        return self.entities.get(name.lower())

    def entity_has_property(self, entity_name: str, prop: str, value: Any = None) -> Optional[bool]:
        """Check if entity has property. Returns None if entity not found."""
        entity = self.get_entity(entity_name)
        if entity is None:
            return None
        return entity.has_property(prop, value)

    def relation_holds(self, subject: str, relation_type: str, obj: str) -> Optional[bool]:
        """Check if relation holds. Returns None if entities not found."""
        key = (subject.lower(), relation_type.lower(), obj.lower())

        # Direct lookup
        if key in self._relation_index:
            return self._relation_index[key]

        # Check if entities exist
        if self.get_entity(subject) is None or self.get_entity(obj) is None:
            return None

        # Relation not defined = False
        return False

    def evaluate_comparison(self, entity1: str, property_type: str, entity2: str) -> Optional[bool]:
        """
        Evaluate a comparison like "X is bigger than Y".

        Maps property types to comparison relations:
        - big/size -> bigger_than
        - tall/height -> taller_than
        - fast/speed -> faster_than
        - cute/cuteness -> cuter_than
        - old/age -> older_than
        """
        property_to_relation = {
            "big": "bigger_than",
            "size": "bigger_than",
            "BIG": "bigger_than",
            "tall": "taller_than",
            "height": "taller_than",
            "fast": "faster_than",
            "speed": "faster_than",
            "cute": "cuter_than",
            "cut": "cuter_than",  # lemmatized form
            "cuteness": "cuter_than",
            "old": "older_than",
            "age": "older_than",
            "strong": "stronger_than",
            "strength": "stronger_than",
        }

        relation = property_to_relation.get(property_type.lower())
        if relation:
            return self.relation_holds(entity1, relation, entity2)

        # Fallback: check if it's a direct relation type
        return self.relation_holds(entity1, f"{property_type}_than", entity2)

    def evaluate_trace_comparison(self, trace) -> Optional[bool]:
        """
        Evaluate a GSE OperationTrace against the world model.

        Looks for COMP_THAN operators and evaluates them.

        Args:
            trace: GSE OperationTrace object

        Returns:
            True if comparison holds in world
            False if comparison doesn't hold
            None if cannot evaluate (entity not found, etc.)
        """
        for op in trace.operators:
            if op.primitive == "COMP_THAN":
                # Extract entities from arguments
                arg1_entities = op.get_entity_args()[0]
                arg2_entities = op.get_entity_args()[1]

                if not arg1_entities or not arg2_entities:
                    continue

                entity1 = arg1_entities[0]  # First entity in arg1
                entity2 = arg2_entities[0]  # First entity in arg2

                # Extract property from arg1 (properties like "cute", "big")
                property_candidates = [
                    l
                    for l in op.arg1_lemmas
                    if l not in {"the", "a", "an", "be", "is", "are"} and l not in arg1_entities
                ]

                if property_candidates:
                    prop = property_candidates[0]
                    return self.evaluate_comparison(entity1, prop, entity2)

        return None

    def get_all_entities(self) -> List[Entity]:
        """Get all unique entities (not aliases)."""
        seen = set()
        result = []
        for entity in self.entities.values():
            if entity.name not in seen:
                seen.add(entity.name)
                result.append(entity)
        return result

    def __repr__(self) -> str:
        entities = len(set(e.name for e in self.entities.values()))
        relations = len(self.relations)
        return f"SimpleWorldModel(entities={entities}, relations={relations})"

    @classmethod
    def create_toy_world(cls) -> "SimpleWorldModel":
        """
        Create a toy world with ~15 entities for testing.

        Entities:
        - Animals: Fido (dog), Whiskers (cat), Tweety (bird), Jumbo (elephant)
        - People: John, Mary, Bob, Alice
        - Objects: table, chair, book, car
        - Places: house, garden, park

        Relations:
        - Size comparisons
        - Speed comparisons
        - Age comparisons
        - Location relations
        """
        world = cls()

        # === ANIMALS ===
        world.add_entity(
            Entity(
                name="fido",
                entity_type=EntityType.ANIMAL,
                properties={
                    "type": "dog",
                    "size": "medium",
                    "color": "brown",
                    "age": 5,
                    "friendly": True,
                },
                aliases={"the dog", "dog"},
            )
        )

        world.add_entity(
            Entity(
                name="whiskers",
                entity_type=EntityType.ANIMAL,
                properties={
                    "type": "cat",
                    "size": "small",
                    "color": "gray",
                    "age": 3,
                    "friendly": True,
                },
                aliases={"the cat", "cat"},
            )
        )

        world.add_entity(
            Entity(
                name="tweety",
                entity_type=EntityType.ANIMAL,
                properties={
                    "type": "bird",
                    "size": "tiny",
                    "color": "yellow",
                    "age": 1,
                    "can_fly": True,
                },
                aliases={"the bird", "bird"},
            )
        )

        world.add_entity(
            Entity(
                name="jumbo",
                entity_type=EntityType.ANIMAL,
                properties={
                    "type": "elephant",
                    "size": "huge",
                    "color": "gray",
                    "age": 20,
                },
                aliases={"the elephant", "elephant"},
            )
        )

        world.add_entity(
            Entity(
                name="rex",
                entity_type=EntityType.ANIMAL,
                properties={
                    "type": "dog",
                    "size": "large",
                    "color": "black",
                    "age": 7,
                },
                aliases={"the big dog"},
            )
        )

        # === PEOPLE ===
        world.add_entity(
            Entity(
                name="john",
                entity_type=EntityType.PERSON,
                properties={
                    "height": 180,
                    "age": 30,
                    "occupation": "teacher",
                },
                aliases={"the man"},
            )
        )

        world.add_entity(
            Entity(
                name="mary",
                entity_type=EntityType.PERSON,
                properties={
                    "height": 165,
                    "age": 28,
                    "occupation": "engineer",
                },
                aliases={"the woman"},
            )
        )

        world.add_entity(
            Entity(
                name="bob",
                entity_type=EntityType.PERSON,
                properties={
                    "height": 175,
                    "age": 45,
                    "occupation": "doctor",
                },
            )
        )

        world.add_entity(
            Entity(
                name="alice",
                entity_type=EntityType.PERSON,
                properties={
                    "height": 170,
                    "age": 25,
                    "occupation": "student",
                },
            )
        )

        # === OBJECTS ===
        world.add_entity(
            Entity(
                name="table",
                entity_type=EntityType.OBJECT,
                properties={
                    "size": "large",
                    "material": "wood",
                },
                aliases={"the table"},
            )
        )

        world.add_entity(
            Entity(
                name="chair",
                entity_type=EntityType.OBJECT,
                properties={
                    "size": "medium",
                    "material": "wood",
                },
                aliases={"the chair"},
            )
        )

        world.add_entity(
            Entity(
                name="book",
                entity_type=EntityType.OBJECT,
                properties={
                    "size": "small",
                    "color": "red",
                },
                aliases={"the book"},
            )
        )

        world.add_entity(
            Entity(
                name="car",
                entity_type=EntityType.OBJECT,
                properties={
                    "size": "large",
                    "color": "blue",
                    "fast": True,
                },
                aliases={"the car"},
            )
        )

        # === SIZE RELATIONS ===
        # Transitive: jumbo > fido > whiskers > tweety
        world.add_relation(Relation("jumbo", "bigger_than", "fido"))
        world.add_relation(Relation("jumbo", "bigger_than", "whiskers"))
        world.add_relation(Relation("jumbo", "bigger_than", "tweety"))
        world.add_relation(Relation("fido", "bigger_than", "whiskers"))
        world.add_relation(Relation("fido", "bigger_than", "tweety"))
        world.add_relation(Relation("whiskers", "bigger_than", "tweety"))
        world.add_relation(Relation("rex", "bigger_than", "fido"))
        world.add_relation(Relation("rex", "bigger_than", "whiskers"))

        # Dog vs cat - fido is cuter/bigger
        world.add_relation(Relation("fido", "cuter_than", "whiskers"))
        world.add_relation(Relation("dog", "cuter_than", "cat"))

        # People height: john > bob > alice > mary
        world.add_relation(Relation("john", "taller_than", "mary"))
        world.add_relation(Relation("john", "taller_than", "bob"))
        world.add_relation(Relation("john", "taller_than", "alice"))
        world.add_relation(Relation("bob", "taller_than", "alice"))
        world.add_relation(Relation("bob", "taller_than", "mary"))
        world.add_relation(Relation("alice", "taller_than", "mary"))

        # Age: bob > john > mary > alice
        world.add_relation(Relation("bob", "older_than", "john"))
        world.add_relation(Relation("bob", "older_than", "mary"))
        world.add_relation(Relation("bob", "older_than", "alice"))
        world.add_relation(Relation("john", "older_than", "mary"))
        world.add_relation(Relation("john", "older_than", "alice"))
        world.add_relation(Relation("mary", "older_than", "alice"))

        # Animal ages: jumbo > rex > fido > whiskers > tweety
        world.add_relation(Relation("jumbo", "older_than", "fido"))
        world.add_relation(Relation("jumbo", "older_than", "whiskers"))
        world.add_relation(Relation("fido", "older_than", "whiskers"))
        world.add_relation(Relation("fido", "older_than", "tweety"))
        world.add_relation(Relation("whiskers", "older_than", "tweety"))

        # Speed: car > fido > whiskers > john
        world.add_relation(Relation("car", "faster_than", "fido"))
        world.add_relation(Relation("fido", "faster_than", "whiskers"))
        world.add_relation(Relation("fido", "faster_than", "john"))
        world.add_relation(Relation("whiskers", "faster_than", "john"))

        return world


# Convenience function
def create_test_world() -> SimpleWorldModel:
    """Create the default toy world for testing."""
    return SimpleWorldModel.create_toy_world()


if __name__ == "__main__":
    # Demo
    world = create_test_world()
    print(world)
    print()

    print("Entities:")
    for entity in world.get_all_entities():
        print(f"  {entity.name}: {entity.entity_type.value}, props={entity.properties}")

    print()
    print("Sample evaluations:")
    print(f"  Fido bigger than Whiskers: {world.relation_holds('fido', 'bigger_than', 'whiskers')}")
    print(f"  Whiskers bigger than Fido: {world.relation_holds('whiskers', 'bigger_than', 'fido')}")
    print(f"  John taller than Mary: {world.relation_holds('john', 'taller_than', 'mary')}")
    print(f"  Dog cuter than cat: {world.evaluate_comparison('dog', 'cute', 'cat')}")
