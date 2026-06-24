"""Phase 1 — Wiktionary definitions → typed genus-differentia structure.

Scale-0 *deterministic* structural extraction (no LLM). The degenerate lexicon
came from **bag-of-words** extraction: a noun inherited every verb in its gloss
("a dog ... has been domesticated" → DO/HAVE/HAPPEN), so `dog`, `king`, `knife`
ended up with the same profile as `murder`, `kill`, `run` — category became
unrecoverable from prime-space.

The fix is structural. A dictionary definition is an *equation*:

    X  is-a  [GENUS]  that/which  [DIFFERENTIA]

- the **genus** (the IS-A head: dog→*mammal*, knife→*tool*, murder→*killing*) gives
  clean category by hypernym propagation — exactly what bag-of-words destroys;
- the **differentia** (relative clauses / participials / PPs) gives the *distinctive*
  content that separates siblings under the same genus;
- **definitional negatives** ("not ...", "without ...") become −1 banks downstream.

This module recovers that typed structure from a gloss. spaCy is used here purely
as the *bootstrap* definition-parser — it is clean on terse dictionary prose, and
the discriminative lexicon it yields is precisely what later lets GSE's own parser
replace spaCy in the loop (ROADMAP WS1). The output `DefinitionStructure` is the
typed, computable artifact Phase 2's genus-differentia→NSM mapper consumes.

Input:  `data/external/wiktionary/kaikki-english.jsonl` glosses.
Output: one `DefinitionStructure` per (lemma, pos, sense).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from typing import Iterator, List, Optional

# spaCy is the bootstrap parser only — loaded lazily so importing the dataclasses
# (and the gate that consumes them) never pays the model-load cost.
_NLP = None


def _nlp():
    global _NLP
    if _NLP is None:
        from gse.nlp.native import NativeNLP   # the deterministic front-end (spaCy retired)

        _NLP = NativeNLP()
    return _NLP


# ---------------------------------------------------------------------------
# Typed artifact
# ---------------------------------------------------------------------------

@dataclass
class Differentia:
    """One distinguishing modifier hung off the genus head."""
    dep: str            # spaCy relation to the genus (relcl, acl, prep, advcl, ...)
    head_lemma: str     # lemma of the modifier's own head (its content anchor)
    text: str           # surface span of the modifier subtree


@dataclass
class DefinitionStructure:
    """The genus-differentia *equation* recovered from one sense's gloss."""
    lemma: str
    pos: str                       # noun | verb | adj | adv | ...
    sense_id: str                  # (lemma, pos, sense index) — stable within a dump
    genus: Optional[str]           # IS-A head lemma  (dog→mammal); None if unparseable
    genus_phrase: Optional[str]    # full head NP/VP surface ("reference work")
    differentia: List[Differentia] = field(default_factory=list)
    negations: List[str] = field(default_factory=list)   # definitional negatives
    raw_gloss: str = ""
    note: str = ""                 # why genus is None / degraded, for triage

    def as_dict(self) -> dict:
        return {
            "lemma": self.lemma, "pos": self.pos, "sense_id": self.sense_id,
            "genus": self.genus, "genus_phrase": self.genus_phrase,
            "differentia": [d.__dict__ for d in self.differentia],
            "negations": self.negations, "raw_gloss": self.raw_gloss,
            "note": self.note,
        }


# ---------------------------------------------------------------------------
# Gloss normalization (strip the scaffolding before the genus)
# ---------------------------------------------------------------------------

# Leading register/domain tag the gloss sometimes keeps in raw_glosses: "(transitive)".
_LEAD_PAREN = re.compile(r"^\s*\([^)]*\)\s*")
# Determiner / infinitival scaffolding that precedes the genus head.
_LEAD_DET = re.compile(r"^\s*(an?|the|to|that which|one who|one that|something that"
                       r"|a person who|a person that)\s+", re.IGNORECASE)
# Wiktionary glosses are frequently a single NP/VP; cut at the first sentence end
# only when it clearly terminates the defining phrase (period + space + capital).
_FIRST_SENT = re.compile(r"^(.*?[.;])\s+[A-Z]")

# Differentia-bearing relations: the modifiers that *distinguish* this sense from
# its genus siblings. amod/compound on the head are genus-side, not differentia.
_DIFF_DEPS = {"relcl", "acl", "prep", "advcl", "acomp", "attr", "npadvmod",
              "nmod", "ccomp", "xcomp", "advmod"}
_NEG_LEMMAS = {"not", "without", "lacking", "lack", "absence", "no", "never",
               "non", "un-"}


def _strip_scaffolding(gloss: str) -> str:
    g = gloss.strip()
    m = _FIRST_SENT.match(g)
    if m:
        g = m.group(1)
    # peel leading parenthetical tag(s), then one determiner/infinitival lead
    prev = None
    while prev != g:
        prev = g
        g = _LEAD_PAREN.sub("", g)
    g = _LEAD_DET.sub("", g)
    return g.strip().rstrip(".;,")


# ---------------------------------------------------------------------------
# Genus selection by POS
# ---------------------------------------------------------------------------

_NOMINAL_POS = {"NOUN", "PROPN"}


# A noun phrase boundary: the leading genus NP ends where the differentia begins.
_NP_BOUNDARY_DEP = {"relcl", "acl", "advcl", "prep"}
_NP_BOUNDARY_LEMMA = {"that", "which", "who", "whom", "where", "when", "of",
                      "with", "for", "used", "having", "characterized"}


def _genus_token(doc, pos: str):
    """The IS-A head. Verbs/adjs: ROOT (or first of class). Nouns: the *head-final*
    nominal of the leading NP — English genus is head-final ("woody perennial
    *plant*", "reference *work*"), so ROOT-based selection mis-grabs the amod."""
    root = next((t for t in doc if t.head == t), None)
    if pos in ("verb", "adj"):
        want = {"VERB"} if pos == "verb" else {"ADJ", "VERB"}
        if root is not None and root.pos_ in want:
            return root
        return next((t for t in doc if t.pos_ in want), root)

    # noun (and default): rightmost NOUN/PROPN before the first clause/PP boundary.
    genus = None
    for t in doc:
        if genus is not None and (t.dep_ in _NP_BOUNDARY_DEP
                                  or t.pos_ == "SCONJ"
                                  or t.text.lower() in _NP_BOUNDARY_LEMMA):
            break
        if t.pos_ in _NOMINAL_POS:
            genus = t
    return genus if genus is not None else root


def _genus_phrase(tok) -> str:
    """Head + its left compound/amod chain: 'reference work', 'small mammal'."""
    if tok is None:
        return ""
    lefts = [c for c in tok.lefts if c.dep_ in ("compound", "amod", "nmod")]
    span = sorted(lefts + [tok], key=lambda t: t.i)
    return " ".join(t.text for t in span)


def extract_structure(lemma: str, pos: str, sense_id: str,
                      gloss: str) -> DefinitionStructure:
    """Recover the genus-differentia equation from one gloss. Deterministic."""
    cleaned = _strip_scaffolding(gloss)
    if not cleaned:
        return DefinitionStructure(lemma, pos, sense_id, None, None,
                                   raw_gloss=gloss, note="empty after strip")
    doc = _nlp()(cleaned)
    genus_tok = _genus_token(doc, pos)
    if genus_tok is None:
        return DefinitionStructure(lemma, pos, sense_id, None, None,
                                   raw_gloss=gloss, note="no head token")

    differentia: List[Differentia] = []
    negations: List[str] = []
    for child in genus_tok.children:
        if child.dep_ == "neg" or child.lemma_.lower() in _NEG_LEMMAS:
            negations.append(child.lemma_.lower())
            continue
        if child.dep_ in _DIFF_DEPS:
            sub = sorted(child.subtree, key=lambda t: t.i)
            differentia.append(Differentia(
                dep=child.dep_, head_lemma=child.lemma_.lower(),
                text=" ".join(t.text for t in sub)))
    # negations can also sit deeper (within a relcl) — scan the whole doc cheaply
    for t in doc:
        if t.dep_ == "neg" and t.lemma_.lower() not in negations:
            negations.append(t.lemma_.lower())

    genus = genus_tok.lemma_.lower() if genus_tok.lemma_ else genus_tok.text.lower()
    # a genus identical to the lemma is circular (no IS-A gained) — flag it
    note = "circular: genus==lemma" if genus == lemma.lower() else ""
    return DefinitionStructure(
        lemma=lemma, pos=pos, sense_id=sense_id,
        genus=genus, genus_phrase=_genus_phrase(genus_tok),
        differentia=differentia, negations=negations,
        raw_gloss=gloss, note=note)


# ---------------------------------------------------------------------------
# Drivers over kaikki-english.jsonl
# ---------------------------------------------------------------------------

DEFAULT_KAIKKI = "data/external/wiktionary/kaikki-english.jsonl"


def _first_gloss(sense: dict) -> Optional[str]:
    g = sense.get("glosses") or sense.get("raw_glosses")
    return g[0] if g else None


def structures_from_record(rec: dict, first_sense_only: bool = True
                           ) -> List[DefinitionStructure]:
    word, pos = rec.get("word"), rec.get("pos")
    if not word or not pos:
        return []
    out: List[DefinitionStructure] = []
    for idx, sense in enumerate(rec.get("senses", [])):
        gloss = _first_gloss(sense)
        if not gloss:
            continue
        out.append(extract_structure(word, pos, f"{word}.{pos}.{idx}", gloss))
        if first_sense_only:
            break
    return out


def pull_glosses(words: List[str], jsonl_path: str = DEFAULT_KAIKKI
                 ) -> Iterator[dict]:
    """Fast targeted fetch: grep the dump for the given headwords (C-speed scan
    over 2.7 GB), yield parsed records. For demos / spot-checks, not bulk runs."""
    pat = "|".join(rf'"word": "{re.escape(w)}"' for w in words)
    # One full C-speed pass over the dump (no -m: deep headwords must be reached).
    proc = subprocess.Popen(
        ["grep", "-E", pat, jsonl_path],
        stdout=subprocess.PIPE, text=True)
    assert proc.stdout is not None
    seen = set()
    for line in proc.stdout:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = (rec.get("word"), rec.get("pos"))
        if rec.get("word") in words and key not in seen:
            seen.add(key)
            yield rec
    proc.stdout.close()
    proc.terminate()


def stream_structures(jsonl_path: str = DEFAULT_KAIKKI, limit: Optional[int] = None
                      ) -> Iterator[DefinitionStructure]:
    """Bulk Scale-0 pass over the whole dump (the Phase 1 artifact builder)."""
    n = 0
    with open(jsonl_path) as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            for ds in structures_from_record(rec):
                yield ds
                n += 1
                if limit and n >= limit:
                    return


# ---------------------------------------------------------------------------
# Feasibility demo: does genus alone separate the must-discriminate pairs?
# ---------------------------------------------------------------------------

def _demo():
    targets = ["dog", "king", "knife", "house", "tree", "stone",
               "murder", "kill", "run", "eat", "give", "think"]
    print("=== Phase 1 genus-differentia extraction (real kaikki glosses) ===\n")
    recs = {(r["word"], r["pos"]): r for r in pull_glosses(targets)}
    for w in targets:
        rec = next((recs[(w, p)] for p in ("noun", "verb", "adj")
                    if (w, p) in recs), None)
        if not rec:
            print(f"  {w:8s}  (not found)")
            continue
        ds = structures_from_record(rec)[0]
        diff = ds.differentia[0].text[:48] + "…" if ds.differentia else "—"
        print(f"  {w:8s} [{ds.pos:4s}]  genus={str(ds.genus):12s} "
              f"phrase={ds.genus_phrase!r:22s} diff={diff}")
    print("\n→ category is recoverable from GENUS where bag-of-words destroyed it.")


if __name__ == "__main__":
    _demo()
