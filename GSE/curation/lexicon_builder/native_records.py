"""Native source records the runtime re-validates (design E11, rebuild task 10.1).

GSE's grounding (`GSE.symbolic.lexical_grounding`) does not take a stored value on trust. For a WordNet reading, a
closed-class unit or an NSM chart unit, it re-reads the exact native record from `source_observations` and checks it
against the source before the reading may take part:

- `wordnet_hierarchy`: the synset's own record from WordNet 3.0 (nltk). It holds the synset, its hypernym paths,
  lemma names, lexicographer file, examples and definition (`_exact_wordnet_ancestry`, `_attested_wordnet_lemma`).
- `gse_closed_class`: the catalog entry (`GSEClosedClassParser`), compared field by field with the catalog.
- `nsm_chart`: the chart unit's record (`nsm_chart_data.chart_definition_records`), compared whole.

Every record is copied from its source. None is derived from a value the build decided, and none is read by the
build. The artifact carries them because the runtime's grounding reads them, the WordNet definitions and examples
included. The builder itself never reads a gloss (F080).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict

from GSE.curation.external_sources.nsm_chart_data import chart_definition_records

WORDNET_POS = {"n": "noun", "v": "verb", "a": "adj", "s": "adj", "r": "adv"}


def _record(record_id: str, entry_id: str, source: str, family: str, scope: str, features: dict) -> dict:
    return {
        "record_id": record_id,
        "entry_id": entry_id,
        "source": source,
        "family": family,
        "scope": scope,
        "candidate_entry_ids": [entry_id],
        "features": features,
    }


def wordnet_records(readings, wn=None) -> Iterator[dict]:
    """One record per WordNet reading, from the synset its id names."""
    from urllib.parse import unquote

    if wn is None:
        from nltk.corpus import wordnet as wn
    for r in readings:
        if r.source != "wordnet":
            continue
        synset = wn.synset(unquote(r.reading_id.rsplit(":", 1)[1]))
        features = {
            "synset_name": synset.name(),
            "pos": WORDNET_POS[synset.pos()],
            "lemma": r.lemma,
            "definition": synset.definition(),
            "hypernym_paths": [[node.name() for node in path] for path in synset.hypernym_paths()],
            "lemma_names": list(synset.lemma_names()),
            "lexname": synset.lexname(),
            "examples": list(synset.examples()),
        }
        yield _record(r.reading_id, r.reading_id, "wordnet_hierarchy", "wordnet", "lexical", features)


def closed_class_record(entry) -> dict:
    """One catalog entry's record (`GSEClosedClassEntry`), its fields as JSON."""
    features = {key: (list(v) if isinstance(v, tuple) else v) for key, v in asdict(entry).items()}
    return _record(entry.entry_id, entry.entry_id, "gse_closed_class", "gse_curated_grammar", "lexical", features)


def closed_class_records(readings) -> Iterator[dict]:
    """One record per closed-class reading, the catalog entry itself."""
    from GSE.curation.external_sources.gse_closed_class import GSEClosedClassParser

    parser = GSEClosedClassParser()
    for r in readings:
        if r.source != "gse_closed_class":
            continue
        entry = next((e for e in parser.get_entries(r.lemma) if e.entry_id == r.reading_id), None)
        if entry is not None:
            yield closed_class_record(entry)


def nsm_chart_records(readings) -> Iterator[dict]:
    """One record per NSM chart reading, the chart's own record."""
    ids = {r.reading_id for r in readings if r.source == "nsm_chart"}
    for record in chart_definition_records():
        if record["entry_id"] in ids:
            yield _record(
                f"{record['entry_id']}:chart",
                record["entry_id"],
                "nsm_chart",
                "nsm_primary_chart",
                "source_structure",
                record,
            )


def records(readings) -> list[dict]:
    return [*wordnet_records(readings), *closed_class_records(readings), *nsm_chart_records(readings)]


def validate(readings, found: list[dict]) -> dict:
    """Run the runtime's own checks over every record: how many it accepts, by source, and why it refuses the rest."""
    import json

    from GSE.curation.external_sources.wordnet_identity import _attested_wordnet_lemma, _exact_wordnet_ancestry
    from GSE.symbolic.lexical_grounding import _catalog_reading, _primary_records

    by_id = {r.reading_id: r for r in readings}
    out: dict[str, Counter] = {}
    primary = _primary_records()
    for record in found:
        wire = json.loads(json.dumps(record))
        r = by_id[record["entry_id"]]
        tally = out.setdefault(record["source"], Counter())
        if record["source"] == "wordnet_hierarchy":
            definition = {"entry_id": r.reading_id, "lemma": r.lemma, "pos": r.pos, "definition": r.gloss}
            accepted = bool(_exact_wordnet_ancestry(definition, wire)) and _attested_wordnet_lemma(definition, wire)
            names = {n.casefold().replace("_", " ") for n in wire["features"]["lemma_names"]}
            if accepted:
                reason = "ACCEPTED"
            elif wire["features"]["definition"] != r.gloss:
                reason = "GLOSS_DIFFERS_FROM_WORDNET"
            elif r.lemma.casefold().replace("_", " ") not in names:
                reason = "LEMMA_IS_NOT_A_LEMMA_NAME_OF_THE_SYNSET"
            else:
                reason = "REFUSED"
        elif record["source"] == "gse_closed_class":
            native = _catalog_reading(r.lemma, r.reading_id)
            f = wire["features"]
            accepted = native is not None and (
                f.get("entry_id") == r.reading_id
                and f.get("definition") == native.definition
                and f.get("grammar_roles") == list(native.grammar_roles)
                and f.get("grammatical_features") == native.grammatical_features
                and f.get("primitives") == native.primitives
            )
            reason = "ACCEPTED" if accepted else "REFUSED"
        else:
            reason = "ACCEPTED" if wire["features"] == primary.get(record["entry_id"]) else "REFUSED"
        tally[reason] += 1
    return {source: dict(sorted(t.items())) for source, t in sorted(out.items())}
