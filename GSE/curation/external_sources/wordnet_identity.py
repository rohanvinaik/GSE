"""Exact WordNet identity witnesses: a native ancestry path and an attested lemma, or abstention.

Moved unchanged from the retired builder's foundation module (2026-11-26); the runtime's lexical grounding uses them.
"""

from __future__ import annotations

import re
from urllib.parse import quote

POS_NAMES = {
    "n": "noun",
    "v": "verb",
    "a": "adjective",
    "s": "adjective",
    "r": "adverb",
    "adj": "adjective",
    "adv": "adverb",
}


def definition_context(pos: str) -> dict[str, str]:
    """Keep unknown POS unknown; only explicit lexical types activate a law."""
    normalized = pos.lower()
    return {"pos": POS_NAMES.get(normalized, normalized)}


_WORDNET_SYNSET = re.compile(r"[^\s:]+\.[nvasr]\.(?:0[1-9]|[1-9][0-9]+)\Z")


def _field(record, name):
    return record.get(name) if isinstance(record, dict) else getattr(record, name, None)


def _exact_wordnet_ancestry(definition, observation) -> frozenset[str]:
    """Read a complete exact native witness; malformed/mismatched data abstains.

    Native paths include the synset itself. Aliases are not guessed: both the
    definition identity and each path must name the recorded canonical synset.
    Candidate links and association observations supply no membership authority.
    """
    entry_id = _field(definition, "entry_id")
    if (
        _field(observation, "source") != "wordnet_hierarchy"
        or _field(observation, "scope") != "lexical"
        or _field(observation, "entry_id") != entry_id
        or _field(observation, "record_id") != entry_id
    ):
        return frozenset()
    features = _field(observation, "features")
    if not isinstance(features, dict):
        return frozenset()
    lemma, pos, gloss = (_field(definition, name) for name in ("lemma", "pos", "definition"))
    synset = features.get("synset_name")
    native_pos = features.get("pos")
    if (
        not isinstance(synset, str)
        or _WORDNET_SYNSET.fullmatch(synset) is None
        or not isinstance(lemma, str)
        or not isinstance(pos, str)
        or not isinstance(native_pos, str)
        or not isinstance(gloss, str)
        or not gloss.strip()
        or features.get("lemma") != lemma
        or features.get("definition") != gloss
        or entry_id != f"wordnet:{quote(lemma, safe='')}:{quote(synset, safe='')}"
        or definition_context(native_pos) != definition_context(pos)
        or definition_context(synset.rsplit(".", 2)[1]) != definition_context(pos)
    ):
        return frozenset()
    paths = features.get("hypernym_paths")
    if not isinstance(paths, (list, tuple)) or not paths:
        return frozenset()
    ancestors = set()
    for path in paths:
        if (
            not isinstance(path, (list, tuple))
            or not path
            or any(not isinstance(node, str) or _WORDNET_SYNSET.fullmatch(node) is None for node in path)
            or path[-1] != synset
            or len(set(path)) != len(path)
            or any(node.rsplit(".", 2)[1] != synset.rsplit(".", 2)[1] for node in path)
        ):
            return frozenset()
        ancestors.update(path)
    return frozenset(ancestors)


def _attested_wordnet_lemma(definition, observation) -> bool:
    """Test the native spelling after an exact WordNet identity check."""
    names = _field(observation, "features").get("lemma_names")
    return (
        isinstance(names, (list, tuple))
        and bool(names)
        and all(isinstance(name, str) and name.strip() for name in names)
        and _field(definition, "lemma").casefold().replace("_", " ")
        in {name.casefold().replace("_", " ") for name in names}
    )
