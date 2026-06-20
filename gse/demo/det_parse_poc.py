"""Deterministic-parser PoC — clause structure WITHOUT spaCy dependency arcs.

The feasibility test for Workstream 1 (docs/ROADMAP.md): can GSE derive clause
structure from its *own* signals — the token stream, POS/lemma (which GSE already
owns and corrects), the lexically-known connective inventory, WordNet verb-sense,
and linear position — using NO `dep_`/`head`/`subtree`?

Run on exactly the cases spaCy's arcs MIS-parse:
  B  "Because Macbeth murdered Duncan, Macduff fled."  (spaCy: empty leading clause)
  C  "Macbeth murdered Duncan and Macduff killed Macbeth."  (spaCy: 2nd clause swallowed)

If this gets them right from connectives + verb-inventory + position, the whole
"GSE is ~70% of a deterministic parser" claim holds, and B/C/D fall out of ONE
mechanism instead of three spaCy-mis-parse patches.

Scope: a minimal deriver for base / coordination / fronted-and-medial causal. Not
the full grammar — just enough to decide feasibility. spaCy is used ONLY for
tokenize + POS + lemma (the parts GSE already owns); the arcs are never touched.
"""

from __future__ import annotations

import spacy
from nltk.corpus import wordnet as wn

_NLP = spacy.load("en_core_web_sm")

# Clause-linking connectives GSE knows lexically (the comp operators) + the
# coordinator. lemma -> link operation.
_LINKERS = {"because": "CAUSAL_SOURCE", "so": "CONSEQUENCE",
            "and": "COORDINATION", "but": "CONTRAST"}
_NOMINAL = {"PROPN", "NOUN", "PRON"}


def _has_verb_sense(lemma: str) -> bool:
    return bool(wn.synsets(lemma, pos="v"))


def _has_adj_sense(lemma: str) -> bool:
    return bool(wn.synsets(lemma, pos="a") or wn.synsets(lemma, pos="s"))


def _entity_like(tok) -> bool:
    """A referential nominal — including a proper noun the POS may have demoted."""
    if tok["pos"] in _NOMINAL:
        return True
    return (tok["text"].isalpha() and tok["text"].istitle()
            and not _has_adj_sense(tok["lemma"]))


def _is_predicate(tok) -> bool:
    """A content predicate: a verb (or a verb-sense token), not the copula/aux."""
    if tok["lemma"] in ("be", "will", "would", "to"):
        return False
    return tok["pos"] == "VERB" or (tok["pos"] in ("NOUN", "X") and _has_verb_sense(tok["lemma"]))


def _tokens(sentence: str):
    # ONLY text/lemma/pos — never dep_/head/subtree.
    return [{"i": t.i, "text": t.text, "lemma": t.lemma_.lower(), "pos": t.pos_}
            for t in _NLP(sentence)]


def _build_clause(span):
    """One clause from a token span: predicate by verb-sense, args by position."""
    pred = next((t for t in span if _is_predicate(t)), None)
    if pred is None:
        return ("PHRASE", [t["text"] for t in span if t["pos"] not in ("PUNCT", "DET")])
    subj = [t["text"] for t in span if t["i"] < pred["i"] and _entity_like(t)]
    obj = [t["text"] for t in span if t["i"] > pred["i"] and _entity_like(t)]
    args = subj[:1] + obj[:1]   # nearest entity each side (minimal)
    return ("EVENT", pred["lemma"], args)


def derive(sentence: str):
    """Derive clause structure from connectives + verb-inventory + position."""
    toks = _tokens(sentence)
    # 1. find clause-linking connectives (lexical) and split points
    linkers = [(t["i"], t["lemma"]) for t in toks if t["lemma"] in _LINKERS]
    splits = sorted(i for i, _ in linkers)
    # also split at a comma that separates clauses (fronted subordinator boundary)
    commas = [t["i"] for t in toks if t["text"] == ","]

    # 2. cut the stream into chunks at linkers (drop the linker token) and clause commas
    cut_at = set(splits) | set(commas)
    chunks, cur = [], []
    for t in toks:
        if t["i"] in cut_at:
            if cur:
                chunks.append(cur)
            cur = []
        elif t["pos"] != "PUNCT":
            cur.append(t)
    if cur:
        chunks.append(cur)

    # 3. each chunk that contains a predicate is a clause
    clauses = [_build_clause(c) for c in chunks if any(_is_predicate(t) for t in c)]
    if not linkers or len(clauses) < 2:
        return clauses[0] if clauses else ("PHRASE", [])

    # 4. link: the connective's operation joins the two clauses. A fronted linker
    #    (position 0) marks its OWN (first) clause as the dependent (cause).
    op = _LINKERS[linkers[0][1]]
    return (op, clauses[0], clauses[1])


def _fmt(node):
    if not isinstance(node, tuple):
        return str(node)
    if node[0] == "EVENT":
        return f"EVENT({node[1]})[{', '.join(node[2])}]"
    if node[0] == "PHRASE":
        return f"PHRASE{node[1]}"
    return f"{node[0]}[{_fmt(node[1])}, {_fmt(node[2])}]"


def main():
    cases = [
        ("Macbeth murders Duncan.", "base SVO"),
        ("Goliath falls.", "base intransitive"),
        ("Mike left because Rex sang.", "medial causal (spaCy ok)"),
        ("Because Macbeth murdered Duncan, Macduff fled.", "B fronted (spaCy FAILS)"),
        ("Macbeth murdered Duncan and Macduff killed Macbeth.", "C coordination (spaCy FAILS)"),
    ]
    for sent, label in cases:
        print(f"• {sent}")
        print(f"    [{label}]")
        print(f"    arc-free derive -> {_fmt(derive(sent))}\n")


if __name__ == "__main__":
    main()
