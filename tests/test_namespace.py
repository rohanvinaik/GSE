"""The rename keeps pre-rename records readable and their identities unchanged."""

import hashlib
import json

import pytest

from GSE.namespace import current_form, current_id, identity_form


@pytest.mark.parametrize(
    "stored, expected",
    [
        ("gse.lexicon-builder/1", "GSE.lexicon-builder/1"),
        ("GSE.lexicon-builder/1", "GSE.lexicon-builder/1"),
        ("gse.lexicon.pronouns", "GSE.lexicon.pronouns"),
        ("gse_closed_class:pronoun:you", "gse_closed_class:pronoun:you"),
        ("gse:prime:want", "gse:prime:want"),
        ("wordnet:dog:dog.n.01", "wordnet:dog:dog.n.01"),
        (3, 3),
        (None, None),
    ],
)
def test_current_reads_legacy_identifiers_and_leaves_other_values(stored, expected):
    assert current_id(stored) == expected


def test_current_form_reaches_nested_keys_and_values_and_keeps_container_types():
    stored = {"format": "gse.heal/1", "origins": ({"module": "gse.nlp.native"},), "gse.key": ["x", "gse.claim/1"]}
    assert current_form(stored) == {
        "format": "GSE.heal/1",
        "origins": ({"module": "GSE.nlp.native"},),
        "GSE.key": ["x", "GSE.claim/1"],
    }


def test_identity_form_hashes_the_original_spelling():
    renamed = {"format": "GSE.bank-request/2", "provenance": ["GSE.lexicon.pronouns:PRONOUN_ENCODINGS:you"]}
    original = {"format": "gse.bank-request/2", "provenance": ["gse.lexicon.pronouns:PRONOUN_ENCODINGS:you"]}

    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    assert digest(identity_form(renamed)) == digest(original)
    assert identity_form(current_form(original)) == original


def test_unrelated_strings_are_never_respelled():
    for value in ("GSEEncoder", "GSE-lexicon", "/Users/x/Projects/GSE/data", "the GSE project"):
        assert identity_form(value) == value
        assert current_id(value) == value
