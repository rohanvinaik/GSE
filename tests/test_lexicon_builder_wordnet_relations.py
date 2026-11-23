"""Native relation evidence survives without becoming a lexical ruling."""

from dataclasses import asdict
from types import SimpleNamespace

from gse.curation.external_sources.wordnet_hierarchy import WordNetHierarchyParser
from gse.curation.lexicon_builder.evidence import _wordnet_relations, collect_evidence
from gse.curation.lexicon_builder.model_evidence import evidence_view


def test_real_adjective_edges_reach_collection_and_model_without_sign_inheritance():
    from nltk.corpus import wordnet as wn

    wn.ensure_loaded()
    parser = WordNetHierarchyParser()
    parser._wn = wn
    parser._loaded = True
    bundle = collect_evidence({"wordnet_hierarchy": parser}, ("dead", "big", "good"))
    adjective_ids = {d.entry_id for d in bundle.definitions if d.pos == "adj"}
    assert not any(a.record_id in adjective_ids for a in bundle.assertions)
    assert bundle.domain_restrictions == ()
    observations = {o.entry_id: o for o in bundle.observations}
    dead = observations["wordnet:dead:dead.a.01"]
    edges = dead.features["native_relations"]
    assert edges["wordnet_version"] == wn.get_version()
    assert edges["source_synset"] == "dead.a.01"
    antonym = edges["antonyms"]["records"][0]
    assert antonym["source_key"] == wn.lemma("dead.a.01.dead").key()
    assert antonym["target_key"] == wn.lemma("alive.a.01.alive").key()
    assert antonym["target"]["definition"] == "possessing life"
    satellites = {s["synset_name"]: s for s in edges["similar_to"]["records"]}
    assert satellites["doomed.s.01"]["definition"] == "marked for certain death"
    assert satellites["deathlike.s.01"]["definition"] == "having the physical appearance of death"
    assert {s["synset_name"] for s in edges["attributes"]["records"]} == {"animation.n.01", "animation.n.02"}
    large = observations["wordnet:big:large.a.01"].features["native_relations"]
    satellites = {s["synset_name"]: s for s in large["similar_to"]["records"]}
    assert satellites["life-size.s.01"]["definition"] == "being of the same size as an original"
    assert satellites["large-mouthed.s.01"]["definition"] == "having a relatively large mouth"
    # Keep each homograph's own native relation records rather than pooling.
    intensive = observations["wordnet:big:bad.s.01"].features["native_relations"]
    assert {s["synset_name"] for s in intensive["similar_to"]["records"]} == {"intense.a.01"}
    view = evidence_view([asdict(dead)], "ALIVE")
    assert view["records"][0]["features"]["native_relations"] == edges
    assert not any(r["field"] == "/features/native_relations" for r in view["records"][0]["omitted_fields"])


def test_relation_order_is_deterministic_and_complete():
    def node(name, text):
        return SimpleNamespace(
            name=lambda: name, pos=lambda: "s", definition=lambda: text, lemma_names=lambda: ["z", "a"]
        )

    first, second = node("a.s.01", "First full definition."), node("z.s.01", "Last full definition." * 100)
    targets = [second, first]
    source = SimpleNamespace(
        name=lambda: "root.a.01", similar_tos=lambda: targets, attributes=lambda: [], lemmas=lambda: []
    )
    before = _wordnet_relations(source, "fixture")
    targets.reverse()
    after = _wordnet_relations(source, "fixture")
    assert before == after
    assert before["similar_to"]["records"][1]["definition"] == second.definition()
    assert before["similar_to"]["records"][0]["lemma_names"] == ["a", "z"]
    assert before["attributes"] == before["antonyms"] == {"code": "READ", "records": []}


def test_unavailable_native_api_is_not_an_observed_empty_relation():
    result = _wordnet_relations(SimpleNamespace(name=lambda: "fixture.a.01"), None)
    assert result["wordnet_version"] is None
    for field in ("antonyms", "attributes", "similar_to"):
        assert result[field] == {"code": "RELATION_API_UNAVAILABLE", "records": []}
