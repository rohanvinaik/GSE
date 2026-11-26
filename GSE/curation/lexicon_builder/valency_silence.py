"""Confirmed silence from NSM valency: a referent that cannot fill a prime's bearer slot makes that prime orthogonal.

The books' method extended to the lexicon (Rohan, 2026-11-26). Each prime's valency is in the October-reviewed prime
profiles (``REQUIRES_ARGUMENT``; F151: combinability is not content, and a cell needs content, explicit absence or
confirmed silence). The predicates whose first, bearer slot is typed ``person`` (THINK's thinker, FEEL's experiencer,
SAY's speaker, DO's agent, ...) can be predicated only of someone; Goddard (2018) widens that to creatures ("something
living ... something like this can feel something"). A noun whose approved identity is a non-living thing, a time or a
place cannot be their bearer, so for its definitions those cells are silent: orthogonal to the word's own meaning.

A prime is kept out when NSM's own texts give it a thing as subject: HAVE ("it has two parts" of a bird's beak, G18
lines 255 and 358 of the snake's body), so HAVE is never silenced here. The approved identity roots name the head
(``wordnet_hierarchy._WARRANTED_ROOT_PRIMITIVES``); a synset that also descends from a living thing, a person, a group
or a causal agent, or (for artifacts) from an abstraction, is excluded. A stored content value is never overwritten:
the caller records it as an exception.
"""

from __future__ import annotations

from functools import lru_cache

# Approved identity roots whose members are non-living things, times or places.
NONLIVING_ROOTS = ("artifact.n.01", "time_period.n.01", "time_unit.n.01", "location.n.01")
# A member that also descends from one of these can be a bearer (or a collective of bearers).
BEARER_ANCESTRY = (
    "living_thing.n.01",
    "organism.n.01",
    "person.n.01",
    "causal_agent.n.01",
    "group.n.01",
    "people.n.01",
    "social_group.n.01",
)
# An artifact that is also an abstraction (an invitation, a bid) is a communication or act, not only a thing.
ABSTRACT_COANCESTRY = {"artifact.n.01": "abstraction.n.06"}
# NSM's own texts give these a thing as subject (G18: a beak "has two parts"; a snake's body has no parts like arms).
THING_SUBJECT_ATTESTED = {"HAVE": ("G18 birds line 255", "G18 snakes line 358")}


@lru_cache(maxsize=1)
def person_bearer_primes() -> tuple[str, ...]:
    """Predicate primes whose reviewed profile types the bearer slot exactly ``person``, less those NSM attests with
    a thing as subject."""
    from .prime_profiles import coordinate, load_profiles

    out = set()
    for profile in load_profiles():
        heads = {c.get("value") for c in profile["claims"] if c["kind"] == "CLASSIFIES_HEAD"}
        slots = next((c.get("slots") for c in profile["claims"] if c["kind"] == "REQUIRES_ARGUMENT"), None) or []
        if "lexical_predicate" in heads and slots and slots[0].split(":", 1)[1] == "person":
            found = coordinate(profile["prime"])
            if found and found[0] not in THING_SUBJECT_ATTESTED:
                out.add(found[0])
    return tuple(sorted(out))


@lru_cache(maxsize=None)
def nonliving_root(synset_name: str) -> str | None:
    """The approved non-living root this synset descends from, or None when it is not one or can be a bearer."""
    from nltk.corpus import wordnet as wn

    try:
        synset = wn.synset(synset_name)
    except Exception:
        return None
    ancestors = {a.name() for a in synset.closure(lambda s: s.hypernyms() + s.instance_hypernyms())} | {synset_name}
    roots = [root for root in NONLIVING_ROOTS if root in ancestors]
    if not roots or ancestors & set(BEARER_ANCESTRY):
        return None
    root = roots[0]
    if ABSTRACT_COANCESTRY.get(root) in ancestors:
        return None
    return root


def silent_banks(entry_id: str) -> tuple[str, ...]:
    """The banks confirmed silent for a WordNet noun definition, by valency; () when the rule does not reach it."""
    if not entry_id.startswith("wordnet:") or ".n." not in entry_id:
        return ()
    return person_bearer_primes() if nonliving_root(entry_id.rsplit(":", 1)[1]) else ()
