"""Signed felt valence for nouns that name a feeling (Rohan, 2026-11-25 05:30, ruling (c)).

"'Hatred' is a negative emotion ... it is expressing an idea that is inherently of negative valence. Be *very*
judicious about this, but yes, choose (c)." F066: "words with strong encoding of emotive valence are not '0', they are
positive or negative". GOOD/BAD here is the quality of the feeling, not a judgement of its bearer (October's
SIGNED_FELT_VALENCE_DOMAIN), so F057's noun-evaluation zero does not apply to these definitions.

Scope: a WordNet noun sense under an approved FEEL identity root (feeling.n.01, emotion.n.01), so the noun's own
denotation is a feeling. Judicious means convergence anchored on the sense: SentiWordNet scores the synset itself and
its sign (positive minus negative score) must be non-zero; at least one lemma-level source must agree (a single signed
USAS E-category on the noun, or NRC VAD valence on its side of the scale's own midpoint 0.5); and no source may
disagree. Lemma-level sources never decide alone: they score the word, not the sense (bang.n.04 'a great bang out of
it' and pet.n.03 'a fit of petulance' carry the sign of the word's other senses).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

FEEL_ROOTS = frozenset({"feeling.n.01", "emotion.n.01"})
VAD_MIDPOINT = 0.5  # NRC VAD's own scale: 0 most negative, 1 most positive
E_TAG = re.compile(r"^(E\d(?:\.\d)?)([+-]+)")


@lru_cache(maxsize=None)
def feeling_sense(synset_name: str) -> bool:
    from nltk.corpus import wordnet as wn

    try:
        synset = wn.synset(synset_name)
    except Exception:
        return False
    return bool(({a.name() for a in synset.closure(lambda s: s.hypernyms())} | {synset_name}) & FEEL_ROOTS)


def _sign(value: float) -> int:
    return (value > 0) - (value < 0)


def source_signs(conn) -> tuple[dict, dict, dict]:
    """(SentiWordNet sign per noun definition, USAS signs per noun lemma, NRC VAD sign per lemma) from the release."""
    swn, usas, vad = {}, {}, {}
    for (raw,) in conn.execute("SELECT payload FROM source_observations WHERE source='sentiwordnet'"):
        record = json.loads(raw)
        entry, features = record.get("entry_id") or "", record["features"]
        if ".n." in entry:
            swn[entry] = _sign((features.get("pos_score") or 0) - (features.get("neg_score") or 0))
    for (raw,) in conn.execute("SELECT payload FROM source_observations WHERE source='usas'"):
        features = json.loads(raw)["features"]
        if features.get("pos") != "NOUN":
            continue
        for tag in features.get("semantic_tags") or []:
            for part in tag.split("/"):
                match = E_TAG.match(part)
                if match:
                    usas.setdefault(features["lemma"], set()).add(1 if match.group(2)[0] == "+" else -1)
    for (raw,) in conn.execute("SELECT payload FROM source_observations WHERE source='nrc_vad'"):
        features = json.loads(raw)["features"]
        if isinstance(features.get("valence"), (int, float)) and features.get("lemma"):
            vad[features["lemma"]] = _sign(features["valence"] - VAD_MIDPOINT)
    return swn, usas, vad


def felt_valence(entry_id: str, signs: tuple[dict, dict, dict]) -> tuple[int, dict] | None:
    """(GOOD sign, the evidence) when the rule establishes it for this definition; None otherwise."""
    if not entry_id.startswith("wordnet:") or ".n." not in entry_id:
        return None
    lemma, synset = entry_id.split(":")[1], entry_id.rsplit(":", 1)[1]
    if not feeling_sense(synset):
        return None
    swn, usas, vad = signs
    anchor = swn.get(entry_id, 0)
    if not anchor:
        return None
    lemma_signs = {}
    if len(usas.get(lemma, ())) == 1:
        lemma_signs["usas"] = next(iter(usas[lemma]))
    if vad.get(lemma):
        lemma_signs["nrc_vad"] = vad[lemma]
    if not lemma_signs or any(sign != anchor for sign in lemma_signs.values()):
        return None
    return anchor, {"sentiwordnet": anchor, **lemma_signs}
