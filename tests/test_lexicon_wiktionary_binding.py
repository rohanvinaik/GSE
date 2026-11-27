"""The Wiktionary binding uses structured fields only (rebuild-lexicon-symbolic-closure task 6.2, design E8).

The readings, senses and taxonomy here are hand-built for the test. The glosses are never read (F080), and the
first test proves it on a native record whose glosses refuse to be read.
"""

from __future__ import annotations

from GSE.curation.external_sources.framenet import FrameNetEntry
from GSE.curation.external_sources.usas import USASEntry
from GSE.curation.lexicon_builder.cells import NEG, State
from GSE.curation.lexicon_builder.inventory import Reading
from GSE.curation.lexicon_builder.projection import Sources, candidates, project, settled_round
from GSE.curation.lexicon_builder.wiktionary_binding import (
    Sense,
    Taxonomy,
    bind,
    located_groups,
    sense_fields,
)


class _NoGlosses(dict):
    def __getitem__(self, key):
        if key in {"glosses", "raw_glosses"}:
            raise AssertionError("a gloss was read")
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key in {"glosses", "raw_glosses"}:
            raise AssertionError("a gloss was read")
        return super().get(key, default)


def _wn(lemma, synset, pos="adj"):
    return Reading(f"wordnet:{lemma}:{synset}", lemma, pos, "")


def _wk(lemma, n, pos="adj"):
    return Reading(f"wiktionary:{lemma}-{pos}-{n}:x", lemma, pos, "")


TAXONOMY = Taxonomy(
    synsets_of=lambda w: {
        "small": frozenset({"small.a.01"}),
        "large": frozenset({"large.a.01"}),
        "size": frozenset({"size.n.01"}),
        "river": frozenset({"river.n.01"}),
        "money": frozenset({"money.n.01"}),
        "slope": frozenset({"slope.n.01"}),
    }.get(w, frozenset()),
    parents={
        "bantam.s.01": ("small.a.01",),
        "big.s.03": ("large.a.01",),
        "bank.n.01": ("slope.n.01",),
        "bank.n.02": ("depository_financial_institution.n.01",),
        "slope.n.01": ("geological_formation.n.01",),
        "depository_financial_institution.n.01": ("financial_institution.n.01",),
    },
)


def test_only_structured_fields_are_read_and_namespaced_links_are_not_words():
    native = _NoGlosses(
        {
            "glosses": ["refuses to be read"],
            "raw_glosses": ["refuses to be read"],
            "links": [["small", "small"], ["see", "Thesaurus:tiny"], ["size", "size#Noun"]],
            "form_of": [{"word": "Tiny"}],
            "synonyms": [{"word": "wee", "sense": "a gloss-like label, never read"}],
            "topics": ["measurement"],
            "categories": [
                {"name": "Pages with entries", "kind": "other"},
                {"name": "Places in Fife", "kind": "place"},
            ],
        }
    )
    sense = sense_fields(0, "teeny", "adj", native)
    assert sense.links == ("small", "size")
    assert sense.form_of == ("tiny",) and sense.synonyms == ("wee",)
    assert sense.topics == ("measurement", "Places in Fife")


def test_a_form_of_with_one_target_reading_is_an_identity_and_with_several_an_obligation():
    readings = (
        _wk("tinier", 1),
        _wn("tiny", "bantam.s.01"),
        _wk("bigger", 1),
        _wn("big", "large.a.01"),
        _wn("big", "big.s.03"),
        _wn("tiny", "tiny.n.01", pos="noun"),
    )
    senses = [Sense(0, "tinier", "adj", form_of=("tiny",)), Sense(2, "bigger", "adj", form_of=("big",))]
    b = bind(readings, senses, TAXONOMY)
    assert set(b.links) == {
        ("form_of", readings[0].reading_id, "bantam.s.01"),
        ("form_of", "bantam.s.01", readings[0].reading_id),
    }
    assert b.classes[0] == b.classes[1]
    [o] = b.obligations
    assert (o.kind, o.row, o.targets.tolist()) == ("form_of", 2, [3, 4])
    assert b.dispositions["form_of"] == {"IDENTITY_EDGE": 1, "IDENTITY_OBLIGATION": 1}


def test_a_synonym_is_an_identity_candidate_that_joins_no_class():
    readings = (_wk("wee", 1), _wn("tiny", "bantam.s.01"))
    b = bind(readings, [Sense(0, "wee", "adj", synonyms=("tiny",))], TAXONOMY)
    assert ("sense_synonym", readings[0].reading_id, "bantam.s.01") in b.links
    assert b.classes[0] != b.classes[1]


def test_a_sense_aligns_only_when_exactly_one_candidate_has_a_linked_synset_among_its_ancestors():
    readings = (
        _wn("bank", "bank.n.01", "noun"),
        _wn("bank", "bank.n.02", "noun"),
        _wk("bank", 1, "noun"),
        _wk("bank", 2, "noun"),
        _wk("bank", 3, "noun"),
        _wk("bank", 4, "noun"),
    )
    senses = [
        Sense(2, "bank", "noun", links=("river", "slope")),  # slope.n.01 is bank.n.01's ancestor only
        Sense(3, "bank", "noun", links=("money",)),  # no candidate has money.n.01 above it
        Sense(4, "bank", "noun", links=("slope", "bank")),  # the own lemma names no synset here
        Sense(5, "bank", "noun"),
    ]
    b = bind(readings, senses, TAXONOMY)
    assert b.aligned == {2: 0, 4: 0}
    assert ("aligned", readings[2].reading_id, "bank.n.01") in b.links
    assert b.classes[2] == b.classes[0] != b.classes[1]
    assert b.dispositions["aligned"] == {"ALIGNED": 2, "NO_CANDIDATE_MATCHES": 1, "NO_LINKS": 1}


def test_two_matching_candidates_abstain():
    readings = (_wn("bank", "bank.n.01", "noun"), _wn("bank", "bank.n.02", "noun"), _wk("bank", 1, "noun"))
    taxonomy = Taxonomy(
        synsets_of=lambda w: frozenset({"bank.n.01", "bank.n.02"}) if w == "bank" else frozenset(), parents={}
    )
    b = bind(readings, [Sense(2, "bank", "noun", links=("bank",))], taxonomy)
    assert not b.aligned and not b.links
    assert b.dispositions["aligned"] == {"SEVERAL_CANDIDATES_MATCH": 1}
    assert b.dispositions["aligned_detail"] == {"SEVERAL_WITH_OWN_LEMMA_LINKED": 1}


def test_topics_are_guard_facts_not_edges():
    readings = (_wk("quark", 1, "noun"), _wk("quark", 2, "noun"))
    b = bind(readings, [Sense(0, "quark", "noun", topics=("physics",)), Sense(1, "quark", "noun")], TAXONOMY)
    assert {name: rows.tolist() for name, rows in b.facts.items()} == {"wiktionary_topic=physics": [0]}
    assert not b.links


def test_an_aligned_pair_is_one_candidate_so_a_lens_obligation_is_located_on_it():
    readings = (_wn("tiny", "bantam.s.01"), _wk("tiny", 1))
    sources = Sources(
        usas={"tiny": [USASEntry("tiny", "ADJ", ["N3.2-"])]},
        framenet={"tiny": [FrameNetEntry("tiny", "a", "Size", 0, [], True)]},
    )
    lens = project(readings, sources)
    b = bind(readings, [Sense(1, "tiny", "adj", links=("small",))], TAXONOMY)
    masks = State.opening([r.reading_id for r in readings]).masks
    [found] = candidates(masks, lens.obligations, b.classes).values()
    assert found.size == 1
    [group] = located_groups(readings, lens, b, masks)
    assert group["readings"] == [r.reading_id for r in readings]
    assert group["claims"] == {"BIG": NEG}
    assert "own_semantic_kind=size_descriptor" in group["facts"]


def test_a_class_that_would_identify_two_wordnet_senses_of_one_lemma_is_dissolved():
    readings = (
        _wn("bank", "bank.n.01", "noun"),
        _wn("bank", "bank.n.02", "noun"),
        _wk("bank", 1, "noun"),
        _wk("bank", 2, "noun"),
        _wn("shore", "shore.n.01", "noun"),
    )
    taxonomy = Taxonomy(
        synsets_of=lambda w: {"slope": frozenset({"slope.n.01"}), "money": frozenset({"money.n.01"})}.get(
            w, frozenset()
        ),
        parents={"bank.n.01": ("slope.n.01",), "bank.n.02": ("money.n.01",)},
    )
    senses = [
        Sense(2, "bank", "noun", links=("slope",), alt_of=("shore",)),
        Sense(3, "bank", "noun", links=("money",), alt_of=("shore",)),
    ]
    b = bind(readings, senses, taxonomy)
    assert b.aligned == {2: 0, 3: 1}
    assert len(set(b.classes.tolist())) == len(readings)
    assert b.dispositions["classes"] == {"DISSOLVED_TWO_WORDNET_SENSES_OF_ONE_LEMMA": 1}


def test_settle_locates_the_aligned_pair_in_the_interpolated_layer_only_and_wakes_its_laws():
    readings = (_wn("tiny", "bantam.s.01"), _wk("tiny", 1))
    sources = Sources(
        usas={"tiny": [USASEntry("tiny", "ADJ", ["N3.2-"])]},
        framenet={"tiny": [FrameNetEntry("tiny", "a", "Size", 0, [], True)]},
    )
    lens = project(readings, sources)
    b = bind(readings, [Sense(1, "tiny", "adj", links=("small",))], TAXONOMY)
    result = settled_round(readings, lens, links=b.links, groups=b.groups, classes=b.classes)
    assert result["known"]["facts_located"] == {}
    assert result["interpolated"]["obligation_groups_by_candidates"] == {"1": 1}
    assert result["interpolated"]["facts_located"]["own_semantic_kind=size_descriptor"] == 2
    assert result["interpolated"]["laws_woken"]["law:SIZE_DESCRIPTOR_EXCLUDES_EVALUATION"] == 2


def test_a_sense_hypernym_is_a_kind_of_edge_from_its_one_parent_or_an_obligation_over_several():
    readings = (
        _wk("dictionary", 1, "noun"),
        _wn("wordbook", "wordbook.n.01", "noun"),
        _wk("lexicon", 1, "noun"),
        _wn("book", "book.n.01", "noun"),
        _wk("book", 1, "noun"),
    )
    native = {"hypernyms": [{"word": "wordbook"}], "glosses": ["never read"]}
    senses = [sense_fields(0, "dictionary", "noun", native), Sense(2, "lexicon", "noun", hypernyms=("book",))]
    b = bind(readings, senses, TAXONOMY)
    assert b.links == [("wiktionary_hypernym", "wordbook.n.01", readings[0].reading_id)]
    assert b.classes[0] != b.classes[1]
    [o] = b.obligations
    assert (o.kind, o.row, o.targets.tolist()) == ("wiktionary_hypernym", 2, [3, 4])
    assert b.census(readings)["edges_by_family"] == {"wiktionary_hypernym": 1}
