#!/usr/bin/env python3
"""RohanVoice — GSE-native voice recognizer for Rohan's own hand-written text.

Consolidates two implementations:
  - the earlier relational-ai voice system (bank signature + composite style features +
    dense-vector cosine to an authentic-voice profile), and
  - the 2026-07-05 per-class recognizer (authored/personal/llm centroids + is_rohan +
    first/second-person + assistant-framing markers).

GSE-NATIVE: uses gse.api for the dense embedding and the lexicon primitive_values table
directly; NO personal-wiki dependency. EPA is deliberately omitted — both implementations
independently found Rohan's EPA/bank distribution is ~UNIFORM, so voice separation comes from
primitive TEXTURE + person-markers, not affect.

Usage:
  python rohan_voice.py --fit                  # build data/voice/model.json from the corpus
  python rohan_voice.py path/to/file.txt       # recognize a file
  echo "text" | python rohan_voice.py -        # recognize stdin
  from rohan_voice import recognize; recognize(text) -> dict
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from gse.primitives_v2 import get_all_primitives, get_bank_for_primitive

GSE_REPO = Path(os.environ.get("GSE_REPO", os.path.expanduser("~/Projects/gse")))
LEXICON = Path(os.environ.get("GSE_LEXICON", str(GSE_REPO / "data" / "lexicon_clean.db")))
MODEL = GSE_REPO / "data" / "voice" / "model.json"
CORPUS = Path(os.path.expanduser("~/Projects/relational-ai/data/training_text/text_files"))
VOICE_WEIGHT = 2.5

# NSM prime -> its semantic bank, read from GSE's own registry (gse.primitives_v2). The hand copy this replaces put
# 12 of the 73 primes in the wrong bank (BE, EXIST and HAVE as LOGICAL; WITH, WITHOUT and TOUCH outside SPATIAL; …)
# and lacked CERTAINTY (#148). BANKS keeps its order: it is the order of the model's bank features.
BANK_MAP = {p: bank.name for p in get_all_primitives() if (bank := get_bank_for_primitive(p)) is not None}
BANKS = ["SUBSTANTIVES", "MENTAL", "ACTION", "EVALUATORS", "LOGICAL", "QUANTITY", "TEMPORAL", "SPATIAL"]
CURATED = ["FEEL", "WANT", "THINK", "KNOW", "SAY", "GOOD", "BAD", "DO", "HAPPEN", "SEE", "BIG", "CAN", "GET", "PEOPLE"]

LABELS = {
    "personal": {
        "functional_life_principles",
        "raw_text",
        "helpless_moral_random",
        "life_organization_plan",
        "tai_lung",
        "old_telehealth",
        "letter",
        "personal_gita_text",
        "psa_letters",
        "Sentiment Analysis Content",
        "mental_parkinson",
        "shadow_adhd",
        "shadow_cognition",
        "turtling",
    },
    "llm": {
        "ontological_framework_life",
        "personal_gita_analysis",
        "neural_net_pde_solver",
        "home_creative_hacks",
        "winston_media",
        "fungal_water_filter",
        "HDC_dump",
        "ai_chip_design",
    },
}
SKIP = {"clinical_differential_diagnosis", "ai_philosophy_summary copy", "shadow_adhd_copy"}

_WORD = re.compile(r"[a-z]{3,}")
_1P = re.compile(r"\b(i|me|my|mine|myself|i'?m|i'?ve|i'?d|i'?ll)\b", re.I)
_2P = re.compile(r"\b(you|your|yours|you'?re|you'?ll|you'?ve|you'?d)\b", re.I)
_META = re.compile(
    r"\b(let me (?:walk|explain|break|focus|show|dive|clarify|conduct|help|start|unpack)|"
    r"here'?s (?:a|how|the|what|why|my)|below is|i'?ll (?:help|focus|walk|conduct|explain|show|start|dive|break)|"
    r"great question|you'?re (?:absolutely )?(?:right|onto)|to summari|in summary|"
    r"does that (?:make sense|help)|happy to help|i can help|feel free|let'?s (?:dive|break|explore|start|walk))\b",
    re.I,
)
_ENTH = re.compile(r"^\W*(fantastic|excellent|absolutely|certainly|perfect|wonderful|great)\b", re.I | re.M)

_LEX = None
_PRIM_CACHE: dict = {}
_ENC = None
_WN = None


def _lex():
    global _LEX
    if _LEX is None:
        _LEX = sqlite3.connect(f"file:{LEXICON}?mode=ro", uri=True)
    return _LEX


def _primitives(lemma: str) -> dict:
    lemma = lemma.lower()
    if lemma in _PRIM_CACHE:
        return _PRIM_CACHE[lemma]
    rows = (
        _lex()
        .execute(
            "SELECT pv.primitive, pv.value FROM primitive_values pv JOIN lexemes l ON l.id=pv.lexeme_id "
            "WHERE LOWER(l.lemma)=?",
            (lemma,),
        )
        .fetchall()
    )
    sig = {p: v for p, v in rows}
    _PRIM_CACHE[lemma] = sig
    return sig


def _lemma(w: str):
    global _WN
    if _WN is None:
        sys.path.insert(0, str(GSE_REPO))
        try:
            from gse.nlp.morphology import wn

            wn.morphy("tests")
            _WN = wn
        except Exception:
            _WN = False
    if not _WN:
        return None
    for pos in (None, "v", "n", "a"):
        lem = _WN.morphy(w, pos) if pos else _WN.morphy(w)
        if lem and lem != w:
            return lem
    return None


def _dense(text: str):
    """Averaged, normalized GSE dense vector over paragraphs (the earlier system's style vector)."""
    global _ENC
    if _ENC is None:
        sys.path.insert(0, str(GSE_REPO))
        from gse.api import GSEEncoder

        _ENC = GSEEncoder(db_path=str(LEXICON))
    import numpy as np

    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 50] or [text[:2000]]
    vecs = []
    for p in paras[:60]:
        try:
            v = _ENC.encode(p).vector
            v = v.to_dense() if hasattr(v, "to_dense") else v
            vecs.append(np.asarray(v, dtype=float))
        except Exception:
            continue
    if not vecs:
        return None
    sv = np.mean(vecs, axis=0)
    n = np.linalg.norm(sv)
    return (sv / n) if n > 0 else sv


def _style_features(banks: dict) -> dict:
    g = lambda k: banks.get(k, 0.0)  # noqa: E731
    return {
        "formality": round(min(1.0, (g("LOGICAL") + g("QUANTITY")) / 2 + (1 - g("EVALUATORS")) / 2), 3),
        "technicality": round(min(1.0, (g("LOGICAL") + g("QUANTITY") + g("SUBSTANTIVES")) / 3), 3),
        "emotionality": round(min(1.0, (g("EVALUATORS") + g("MENTAL")) / 2), 3),
        "narrative_strength": round(min(1.0, (g("TEMPORAL") + g("SPATIAL") + g("ACTION")) / 3), 3),
        "abstract_thinking": round(min(1.0, (g("MENTAL") + g("LOGICAL")) / 2), 3),
        "action_orientation": round(g("ACTION"), 3),
    }


def featurize(text: str, with_dense: bool = False) -> dict | None:
    words = _WORD.findall(text.lower())
    nw = len(words)
    if nw == 0:
        return None
    prim = defaultdict(int)
    bank = defaultdict(float)
    nwp = 0
    for w in words:
        sig = _primitives(w) or (_primitives(_lemma(w) or "") if _lemma(w) else {})
        if sig:
            nwp += 1
            for p in sig:
                prim[p] += 1
                if p in BANK_MAP:
                    bank[BANK_MAP[p]] += 1
    bank_total = sum(bank.values()) or 1
    bank_sig = {b: round(bank.get(b, 0) / bank_total, 4) for b in BANKS}
    dist = [prim.get(p, 0) / max(1, nwp) for p in CURATED]
    onep, twop = len(_1P.findall(text)) / nw, len(_2P.findall(text)) / nw
    meta = len(_META.findall(text)) / nw
    enth = len(_ENTH.findall(text)) / max(1, text.count("\n") + 1)
    out = {
        "bank": [bank_sig[b] for b in BANKS],
        "dist": dist,
        "voice": [onep, twop, meta, enth],
        "bank_sig": bank_sig,
        "style_features": _style_features(bank_sig),
        "markers": {
            "first_person_pct": round(onep * 100, 2),
            "second_person_pct": round(twop * 100, 2),
            "assistant_framing_per1k": round(meta * 1000, 2),
            "opening_enthusiasm_pct": round(enth * 100, 2),
        },
    }
    if with_dense:
        d = _dense(text)
        out["dense"] = d.tolist() if d is not None else None
    return out


def _mean_std(rows, i, n):
    col = [r[i] for r in rows]
    m = sum(col) / n
    sd = (sum((x - m) ** 2 for x in col) / n) ** 0.5 or 1e-9
    return m, sd


def fit() -> dict:
    import numpy as np

    label_of = {nm: lab for lab, names in LABELS.items() for nm in names}
    feats, labels, denses = [], [], []
    for txt in sorted(CORPUS.glob("*.txt")):
        if txt.stem in SKIP:
            continue
        content = txt.read_text(encoding="utf-8", errors="ignore")
        f = featurize(content, with_dense=True)
        if not f:
            continue
        feats.append(f["bank"] + f["dist"] + f["voice"])
        labels.append(label_of.get(txt.stem, "authored"))
        if f.get("dense"):
            denses.append(f["dense"])
    n = len(feats)
    nfeat = len(feats[0])
    nv = 4
    stats = [_mean_std(feats, i, n) for i in range(nfeat)]

    def std(vec):
        return [((vec[i] - stats[i][0]) / stats[i][1]) * (VOICE_WEIGHT if i >= nfeat - nv else 1) for i in range(nfeat)]

    Z = [std(v) for v in feats]
    cents = {
        lab: [sum(Z[i][d] for i in range(n) if labels[i] == lab) / labels.count(lab) for d in range(nfeat)]
        for lab in set(labels)
    }
    profile_vec = (np.mean(np.array(denses), axis=0)).tolist() if denses else None
    model = {
        "stats": stats,
        "centroids": cents,
        "nfeat": nfeat,
        "nv": nv,
        "voice_weight": VOICE_WEIGHT,
        "banks": BANKS,
        "curated": CURATED,
        "n_train": n,
        "labels": {k: labels.count(k) for k in set(labels)},
        "profile_dense": profile_vec,
        "note": "RohanVoice; GSE-native; EPA-omitted (uniform).",
    }
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    MODEL.write_text(json.dumps(model))
    return {
        "trained_on": n,
        "classes": model["labels"],
        "model": str(MODEL),
        "has_dense_profile": profile_vec is not None,
    }


def recognize(text: str, with_dense: bool = False) -> dict | None:
    """Classify text's voice. Fast by default (banks + primitive texture + markers = lexicon
    lookups only). with_dense=True adds the GSE dense-vector cosine 'authentic_similarity' —
    accurate but EXPENSIVE on long docs (encodes up to 60 paragraphs through GSE)."""
    if not MODEL.exists():
        raise RuntimeError(f"model not fit — run: python {Path(__file__).name} --fit")
    m = json.loads(MODEL.read_text())
    f = featurize(text, with_dense=with_dense and bool(m.get("profile_dense")))
    if not f:
        return None
    vec = f["bank"] + f["dist"] + f["voice"]
    nfeat, nv = m["nfeat"], m["nv"]
    z = [
        ((vec[i] - m["stats"][i][0]) / m["stats"][i][1]) * (m["voice_weight"] if i >= nfeat - nv else 1)
        for i in range(nfeat)
    ]
    dists = {lab: math.sqrt(sum((z[d] - c[d]) ** 2 for d in range(nfeat))) for lab, c in m["centroids"].items()}
    negs = {lab: -d for lab, d in dists.items()}
    mx = max(negs.values())
    exps = {lab: math.exp(v - mx) for lab, v in negs.items()}
    tot = sum(exps.values())
    scores = {lab: round(exps[lab] / tot, 3) for lab in exps}
    sim = None
    if m.get("profile_dense") and f.get("dense"):
        import numpy as np

        a, b = np.array(f["dense"]), np.array(m["profile_dense"])
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        sim = round(float(a.dot(b) / (na * nb)), 3) if na and nb else None
    return {
        "voice": min(dists, key=dists.get),
        "is_rohan": round(scores.get("authored", 0) + scores.get("personal", 0), 3),
        "scores": scores,
        "authentic_similarity": sim,
        "bank_signature": f["bank_sig"],
        "style_features": f["style_features"],
        "markers": f["markers"],
    }


def main():
    args = sys.argv[1:]
    if args and args[0] == "--fit":
        print(json.dumps(fit(), indent=2))
        return
    dense = "--dense" in args
    args = [a for a in args if a != "--dense"]
    if not args:
        print(__doc__)
        return
    text = sys.stdin.read() if args[0] == "-" else Path(args[0]).read_text(encoding="utf-8", errors="ignore")
    print(json.dumps(recognize(text, with_dense=dense), indent=2))


if __name__ == "__main__":
    main()
