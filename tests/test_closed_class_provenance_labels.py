"""Closed-class provenance labels are stored identifiers, not import paths.

Each label is hashed into stored record identity, so moving or renaming a module
must never change one (openspec change organize-package-by-subsystem, task 3.1).
"""

from GSE.curation.external_sources import gse_closed_class as closed

PINNED = {
    "ORIGIN_PRONOUNS": "GSE.lexicon.pronouns",
    "ORIGIN_FUNCTION_WORDS": "GSE.lexicon.function_words",
    "ORIGIN_CLOSED_CLASS_BUILD": "GSE.curation.build_clean_closed_class",
    "ORIGIN_TIER_0_DISPATCH": "GSE.curation.external_sources.tier_0_dispatch",
    "ORIGIN_NATIVE_FRONT_END": "GSE.nlp.native",
}


def test_each_label_keeps_its_exact_bytes():
    for name, value in PINNED.items():
        assert getattr(closed, name) == value
    assert closed.ORIGIN_LABELS == frozenset(PINNED.values())


def test_every_closed_class_record_names_its_origin_with_a_pinned_label():
    parser = closed.GSEClosedClassParser()
    assert parser.load()
    entries = [entry for group in parser.entries.values() for entry in group]
    assert entries
    for entry in entries:
        assert {native["module"] for native in entry.native_encodings} <= closed.ORIGIN_LABELS, entry.entry_id
        assert {item.split(":", 1)[0] for item in entry.provenance} <= closed.ORIGIN_LABELS, entry.entry_id
