#!/usr/bin/env python3
"""VoiceProfile — source-agnostic, GSE-derived voice/style profiler.

Point it at ANY source text and get the full GSE-computable fingerprint a reader ascribes to
the "sound"/"vibe" of a voice — diction, sentence architecture, rhetorical structure, affect+
register, stance, geometry. NO hardcoding to any particular author; this is the analysis/data
layer a later GENERATIVE step conditions on.

Every dimension is grounded in a verified GSE computation (via the gse_layer access wrapper over
GSE's symbolic/compact systems): word_primitives, doc_graph, propositions, doc_epa,
register_gradient. EPA is INCLUDED (it's a general voice feature; it happens to be ~flat for some
authors, which is itself a finding the OTHER dimensions resolve).

Usage:
  python voice_profile.py path/to/file_or_dir            # profile a file or a dir of texts
  python voice_profile.py --dense path/to/file           # + dense GSE geometry (expensive)
  from voice_profile import profile; profile(texts) -> dict
"""

from __future__ import annotations

import glob
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/tools/personal-wiki/src"))  # GSE-access wrapper (thin over GSE)
from personal_wiki.semantic.gse_layer import SemanticLayer  # noqa: E402

BANK_MAP = {  # NSM prime -> semantic bank
    "I": "SUBSTANTIVES",
    "YOU": "SUBSTANTIVES",
    "SOMEONE": "SUBSTANTIVES",
    "PEOPLE": "SUBSTANTIVES",
    "SOMETHING": "SUBSTANTIVES",
    "BODY": "SUBSTANTIVES",
    "KIND": "SUBSTANTIVES",
    "PART": "SUBSTANTIVES",
    "WORDS": "SUBSTANTIVES",
    "OTHER": "SUBSTANTIVES",
    "THINK": "MENTAL",
    "KNOW": "MENTAL",
    "WANT": "MENTAL",
    "FEEL": "MENTAL",
    "SEE": "MENTAL",
    "HEAR": "MENTAL",
    "DO": "ACTION",
    "HAPPEN": "ACTION",
    "MOVE": "ACTION",
    "TOUCH": "ACTION",
    "SAY": "ACTION",
    "ALIVE": "ACTION",
    "DEAD": "ACTION",
    "GOOD": "EVALUATORS",
    "BAD": "EVALUATORS",
    "BIG": "EVALUATORS",
    "SMALL": "EVALUATORS",
    "INTENSITY": "EVALUATORS",
    "NOT": "LOGICAL",
    "MAYBE": "LOGICAL",
    "CAN": "LOGICAL",
    "MUST": "LOGICAL",
    "BECAUSE": "LOGICAL",
    "CAUSE": "LOGICAL",
    "IF": "LOGICAL",
    "TRUE": "LOGICAL",
    "FALSE": "LOGICAL",
    "BE": "LOGICAL",
    "EXIST": "LOGICAL",
    "HAVE": "LOGICAL",
    "INFER": "LOGICAL",
    "SAME": "LOGICAL",
    "LIKE": "LOGICAL",
    "WITH": "LOGICAL",
    "WITHOUT": "LOGICAL",
    "ONE": "QUANTITY",
    "TWO": "QUANTITY",
    "NUMBER": "QUANTITY",
    "QUANTITY": "QUANTITY",
    "HIER_PLUS": "QUANTITY",
    "HIER_MINUS": "QUANTITY",
    "WHEN": "TEMPORAL",
    "NOW": "TEMPORAL",
    "BEFORE": "TEMPORAL",
    "AFTER": "TEMPORAL",
    "LONG_TIME": "TEMPORAL",
    "SHORT_TIME": "TEMPORAL",
    "MOMENT": "TEMPORAL",
    "THEN": "TEMPORAL",
    "START": "TEMPORAL",
    "END": "TEMPORAL",
    "WHERE": "SPATIAL",
    "HERE": "SPATIAL",
    "ABOVE": "SPATIAL",
    "BELOW": "SPATIAL",
    "FAR": "SPATIAL",
    "NEAR": "SPATIAL",
    "SIDE": "SPATIAL",
    "INSIDE": "SPATIAL",
    "OUTSIDE": "SPATIAL",
    "TOWARD": "SPATIAL",
    "AWAY": "SPATIAL",
}
BANKS = ["SUBSTANTIVES", "MENTAL", "ACTION", "EVALUATORS", "LOGICAL", "QUANTITY", "TEMPORAL", "SPATIAL"]
MODAL = {"CAN", "MUST", "MAYBE", "NOT"}  # hedging/assertion primitives

_SENT = re.compile(r"(?<=[.!?])\s+")
_TOK = re.compile(r"[a-z][a-z'\-]*", re.I)
_WORD = re.compile(r"[a-z]{3,}")
_1P = re.compile(r"\b(i|me|my|mine|myself|i'?m|i'?ve|i'?d|i'?ll)\b", re.I)
_2P = re.compile(r"\b(you|your|yours|you'?re|you'?ll|you'?ve|you'?d)\b", re.I)

_SL = None


def _sl():
    global _SL
    if _SL is None:
        _SL = SemanticLayer()
        if not _SL.available:
            raise RuntimeError("GSE unavailable")
    return _SL


def _ms(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"mean": 0.0, "std": 0.0}
    return {"mean": round(statistics.fmean(xs), 4), "std": round(statistics.pstdev(xs) if len(xs) > 1 else 0.0, 4)}


def _featurize(text: str, sl, with_dense: bool) -> dict:
    sents = [s for s in _SENT.split(text.strip()) if s.strip()]
    toks = _TOK.findall(text.lower())
    content = _WORD.findall(text.lower())
    ntok = max(1, len(toks))
    ncontent = max(1, len(content))

    # -- DICTION --
    prim = defaultdict(int)
    bank = defaultdict(int)
    nwp = 0
    miss = 0
    for w in content:
        sig = sl.word_primitives(w) or (sl.word_primitives(sl._lemma(w) or "") if sl._lemma(w) else {})
        if sig:
            nwp += 1
            for p in sig:
                prim[p] += 1
                if p in BANK_MAP:
                    bank[BANK_MAP[p]] += 1
        else:
            miss += 1
    bank_tot = sum(bank.values()) or 1
    prim_tot = sum(prim.values()) or 1
    types = len(set(toks))
    hapax = sum(1 for w, c in _counts(toks).items() if c == 1)
    diction = {
        "bank_signature": {b: round(bank.get(b, 0) / bank_tot, 4) for b in BANKS},
        "top_primes": dict(sorted(((p, round(c / prim_tot, 4)) for p, c in prim.items()), key=lambda x: -x[1])[:12]),
        "type_token_ratio": round(types / ntok, 4),
        "hapax_rate": round(hapax / max(1, types), 4),
        "mean_word_len": round(statistics.fmean([len(w) for w in toks]) if toks else 0, 3),
        "word_len_std": round(statistics.pstdev([len(w) for w in toks]) if len(toks) > 1 else 0, 3),
        "rare_word_rate": round(miss / ncontent, 4),  # lexicon-miss = jargon/idiosyncrasy
        "modal_rate": round(sum(prim.get(m, 0) for m in MODAL) / prim_tot, 4),
    }

    # -- SYNTAX (doc_graph + sentence stats) --
    g = sl.doc_graph(text) or {"nodes": [], "edges": []}
    nn, ne = len(g["nodes"]), len(g["edges"])
    ns = max(1, len(sents))
    pos_ct = defaultdict(int)
    for n in g["nodes"]:
        pos_ct[n.get("pos", "?")] += 1
    negated = sum(1 for e in g["edges"] if e.get("negated"))
    slens = [len(_TOK.findall(s)) for s in sents]
    sm = statistics.fmean(slens) if slens else 0
    syntax = {
        "sent_len_mean": round(sm, 2),
        "sent_len_std": round(statistics.pstdev(slens) if len(slens) > 1 else 0, 2),
        "sent_len_burstiness": round((statistics.pstdev(slens) / sm) if len(slens) > 1 and sm else 0, 3),
        "predicate_arg_density": round(ne / ns, 3),  # edges per sentence
        "entity_density": round(nn / ns, 3),
        "negation_rate": round(negated / max(1, ne), 4),
        "pos_distribution": {k: round(v / max(1, nn), 3) for k, v in sorted(pos_ct.items(), key=lambda x: -x[1])[:6]},
        "comma_cadence": round(text.count(",") / ns, 3),
        "semicolon_rate": round(text.count(";") / ns, 3),
        "emdash_rate": round((text.count("—") + text.count(" - ")) / ns, 3),
        "parenthetical_rate": round(text.count("(") / ns, 3),
    }

    # -- RHETORIC (propositions) --
    p = sl.propositions(text)
    props = p["props"]
    pos_props = sum(1 for pr in props if pr[0] > 0)
    rhetoric = {
        "claim_density": round(len(props) / ns, 3),
        "parse_coverage": round(p["n_parsed"] / max(1, p["n_sentences"]), 4),
        "assertion_rate": round(pos_props / max(1, len(props)), 4),
        "negation_rate_props": round((len(props) - pos_props) / max(1, len(props)), 4),
        "question_rate": round(sum(1 for s in sents if s.rstrip().endswith("?")) / ns, 4),
    }

    # -- AFFECT + REGISTER --
    epa = sl.doc_epa(text) or {}
    rg = sl.register_gradient(text) or {}
    series = rg.get("series", [])
    mags = [s.get("magnitude", 0) for s in series]
    affect_register = {
        "epa": {k: round(v, 4) for k, v in epa.items() if isinstance(v, (int, float))},
        "register_baseline": round(rg.get("baseline", 0), 3),
        "register_lift_rate": round(len(rg.get("lift_indices", [])) / max(1, len(series)), 4),
        "register_dynamics_std": round(statistics.pstdev(mags) if len(mags) > 1 else 0, 4),  # within-doc variation
    }

    # -- STANCE --
    stance = {
        "first_person_rate": round(len(_1P.findall(text)) / ntok, 4),
        "second_person_rate": round(len(_2P.findall(text)) / ntok, 4),
        "question_rate": rhetoric["question_rate"],
    }

    out = {
        "diction": diction,
        "syntax": syntax,
        "rhetoric": rhetoric,
        "affect_register": affect_register,
        "stance": stance,
    }
    if with_dense:
        d = _dense(text, sl)
        out["geometry"] = {
            "dense_norm": round(float((sum(x * x for x in d)) ** 0.5), 4) if d is not None else None,
            "dense_dim": len(d) if d is not None else None,
            "_dense": d,
        }
    return out


def _counts(xs):
    c = defaultdict(int)
    for x in xs:
        c[x] += 1
    return c


def _dense(text, sl):
    try:
        sys.path.insert(0, os.path.expanduser("~/Projects/gse"))
        from gse.api import GSEEncoder

        if not hasattr(sl, "_vp_enc"):
            sl._vp_enc = GSEEncoder(db_path=str(sl.lexicon_path))
        import numpy as np

        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 50] or [text[:2000]]
        vs = []
        for pa in paras[:40]:
            v = sl._vp_enc.encode(pa).vector
            vs.append(np.asarray(v.to_dense() if hasattr(v, "to_dense") else v, dtype=float))
        if not vs:
            return None
        m = np.mean(vs, axis=0)
        n = np.linalg.norm(m)
        return (m / n).tolist() if n else m.tolist()
    except Exception:
        return None


def profile(texts, with_dense: bool = False, source: str = "input") -> dict:
    """Profile one or many source texts -> a VoiceProfile. Scalar features are aggregated
    across texts as {mean, std} (central tendency AND consistency both matter for voice)."""
    if isinstance(texts, str):
        texts = [texts]
    sl = _sl()
    per = [_featurize(t, sl, with_dense) for t in texts if t and t.strip()]
    if not per:
        return {}

    # aggregate: recurse over the nested scalar structure, collecting per-text values
    def agg(key_path, getter):
        vals = []
        for f in per:
            v = getter(f)
            if isinstance(v, (int, float)):
                vals.append(v)
        return _ms(vals) if vals else None

    groups = ["diction", "syntax", "rhetoric", "affect_register", "stance"]
    prof = {"source": source, "n_texts": len(per), "with_dense": with_dense}
    for grp in groups:
        prof[grp] = {}
        for k, v in per[0][grp].items():
            if isinstance(v, (int, float)):
                prof[grp][k] = agg(None, lambda f, g=grp, kk=k: f[g][kk])
            elif isinstance(v, dict):  # distribution (bank/pos/primes/epa) -> mean across texts
                sub = {}
                for subk in v:
                    xs = [f[grp][k].get(subk) for f in per if isinstance(f[grp][k].get(subk), (int, float))]
                    if xs:
                        sub[subk] = round(statistics.fmean(xs), 4)
                prof[grp][k] = sub
    if with_dense:
        import numpy as np

        ds = [f["geometry"]["_dense"] for f in per if f.get("geometry", {}).get("_dense")]
        prof["geometry"] = {
            "dense_dim": len(ds[0]) if ds else None,
            "dense_vector": (np.mean(np.array(ds), axis=0)).tolist() if ds else None,
        }
    return prof


def main():
    args = [a for a in sys.argv[1:] if a != "--dense"]
    dense = "--dense" in sys.argv
    if not args:
        print(__doc__)
        return
    target = Path(args[0])
    if target.is_dir():
        texts = [
            Path(f).read_text(encoding="utf-8", errors="ignore")
            for f in glob.glob(str(target / "*.txt")) + glob.glob(str(target / "*.md"))
        ]
        src = target.name
    else:
        texts = [target.read_text(encoding="utf-8", errors="ignore")]
        src = target.stem
    print(json.dumps(profile(texts, with_dense=dense, source=src), indent=2))


if __name__ == "__main__":
    main()
