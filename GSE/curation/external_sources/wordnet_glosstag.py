"""Princeton WordNet Gloss Corpus (WordNet 3.0 glosstag): each gloss word linked to its synset.

Source: https://wordnetcode.princeton.edu/glosstag-files/WordNet-3.0-glosstag.tar.bz2 (WordNet Gloss Disambiguation
Project, Princeton University 2008, WordNet license; the notice travels with the data under
``data/external/wordnet-glosstag/``). Only the definition part of each gloss is read, never its examples.

A link is kept when its tag is ``man`` (an annotator assigned it), or when it is ``auto`` and the tagged lemma has
exactly one WordNet synset in that part of speech, so the link is exact however it was produced. Every other
``auto`` tag, every ``un`` (untagged) item and every key nltk cannot resolve is counted and dropped, never guessed.
"""

from __future__ import annotations

import pickle
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

GLOSSTAG_DIR = Path("data/external/wordnet-glosstag/WordNet-3.0/glosstag/merged")
FILES = ("noun.xml", "verb.xml", "adj.xml", "adv.xml")
SS_TYPE_POS = {"1": "n", "2": "v", "3": "a", "4": "r", "5": "a"}


def _satellite_key(sense_key: str) -> str | None:
    """The corpus writes adjective-satellite keys with type 3; a key naming a head word is a satellite (type 5)."""
    lemma, _, rest = sense_key.partition("%")
    fields = rest.split(":")
    if len(fields) == 5 and fields[0] == "3" and fields[3]:
        return f"{lemma}%5:" + ":".join(fields[1:])
    return None


def _resolve(sense_key: str, lemma: str, tag: str, wn, stats: Counter) -> str | None:
    synset = None
    for key in (sense_key, _satellite_key(sense_key)):
        if key is None:
            continue
        try:
            synset = wn.lemma_from_key(key).synset()
            if key != sense_key:
                stats["satellite_key_normalized"] += 1
            break
        except Exception:
            continue
    if synset is None:
        stats["unresolved_key"] += 1
        return None
    if tag == "man":
        stats["man"] += 1
        return synset.name()
    pos = SS_TYPE_POS.get(sense_key.split("%", 1)[1][:1], "")
    if len(wn.synsets(lemma, pos=pos)) == 1:
        stats["auto_monosemous"] += 1
        return synset.name()
    stats["auto_dropped_polysemous"] += 1
    return None


def read_links(root: Path) -> tuple[dict[str, list[dict]], Counter]:
    """synset name -> the definition's linked words, in order: {synset, key, tag, form}."""
    from nltk.corpus import wordnet as wn

    links: dict[str, list[dict]] = {}
    stats: Counter = Counter()
    for name in FILES:
        for _, element in ET.iterparse(root / GLOSSTAG_DIR / name, events=("end",)):
            if element.tag != "synset":
                continue
            try:
                synset = wn.synset_from_pos_and_offset(element.get("pos")[0], int(element.get("ofs"))).name()
            except Exception:
                stats["unresolved_synset"] += 1
                element.clear()
                continue
            found = []
            for gloss in element.iter("gloss"):
                if gloss.get("desc") != "wsd":
                    continue
                for definition in gloss.iter("def"):
                    for item in definition:
                        if item.tag not in ("wf", "glob"):
                            continue
                        tag = item.get("tag")
                        if tag == "un":
                            stats["untagged"] += 1
                        if tag not in ("man", "auto"):
                            continue
                        for ident in item.findall("id"):
                            target = _resolve(ident.get("sk"), ident.get("lemma") or "", tag, wn, stats)
                            if target:
                                found.append(
                                    {
                                        "synset": target,
                                        "key": ident.get("sk"),
                                        "tag": tag,
                                        "form": "".join(item.itertext()).strip(),
                                    }
                                )
            links[synset] = found
            stats["synsets"] += 1
            element.clear()
    return links, stats


def cached_links(root: Path) -> dict[str, list[dict]]:
    path = root / GLOSSTAG_DIR.parent / "glosstag-links.pkl"
    if not path.exists():
        links, stats = read_links(root)
        with path.open("wb") as handle:
            pickle.dump({"links": links, "stats": dict(stats)}, handle, protocol=pickle.HIGHEST_PROTOCOL)
    with path.open("rb") as handle:
        return pickle.load(handle)["links"]
