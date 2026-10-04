"""Linkage / application stage — DefinitionOp → ternary decomposition.

Takes the structural operation the definitional decomposer emits and *applies* it
against the grounded set (Layer 0 primes + Layer 1 source-grounded words), recursing
genus chains down to the primes. The operations are the GSE set-theory ones:

  ZERO                          -> {}                      (closed-class)
  IDENTITY (inflection/altform/ -> the operand's decomposition (ran = run)
            manner/plural/comparative/superlative — word-scale is identity; the
            QUANTITY/HIER scalar is a sentence-scale feature, handled separately)
  NOT (adj_negative)            -> operand's decomposition, evaluative pole flipped
  genus_differentia / INHERIT / -> inherit the genus's grounded set (recurse),
            BIND / TYPE_ASSERT      then add the differentia's distinctive primes

Recursive with memoization, cycle-guarded, depth-limited; bottoms out at the
grounded clean DB (primes + Layer 1). Word-scale ternary dicts, no vectors.
"""

from __future__ import annotations

import sqlite3
from typing import Dict, Optional, Tuple

from gse.curation.decomposition.definitional_decomposer import decompose
from gse.curation.decomposition.source_index import primary_gloss
from gse.curation.external_sources.tier_0_dispatch import canonical_decomposition
from gse.curation.schema import ALL_PRIMITIVES

CLEAN_DB = "data/lexicon_clean.db"
MAX_DEPTH = 8
_PRIMSET = set(ALL_PRIMITIVES)
# NOT flips ONLY the evaluative pole (GSE_vision IV-D: like ⟷ dislike flips {GOOD,BAD}).
_FLIP = {"GOOD", "BAD"}
_IDENTITY_OPS = {"IDENTITY", "QUANTITY_SCALAR", "HIER_PLUS", "HIER_MAX"}


def _merge(acc: Dict[str, int], d: Dict[str, int], sign: int = 1) -> None:
    for p, v in d.items():
        if p in _PRIMSET and v != 0:
            acc[p] = acc.get(p, 0) + sign * (1 if v > 0 else -1)


def _resolve(acc: Dict[str, int]) -> Dict[str, int]:
    return {p: (1 if s > 0 else -1) for p, s in acc.items() if s != 0}


def _flip_eval(d: Dict[str, int]) -> Dict[str, int]:
    return {p: (-v if p in _FLIP else v) for p, v in d.items()}


class Linker:
    """Evaluates words to decompositions against the clean DB, with memoization."""

    def __init__(self, clean_db: str = CLEAN_DB):
        self.con = sqlite3.connect(f"file:{clean_db}?mode=ro", uri=True)
        self._memo: Dict[Tuple[str, Optional[str]], Dict[str, int]] = {}
        self._cat_memo: Dict[str, Dict[str, int]] = {}

    def grounded(self, word: str) -> Optional[Dict[str, int]]:
        r = self.con.execute("SELECT id FROM lexemes WHERE lemma=? LIMIT 1", (word,)).fetchone()
        if not r:
            return None
        return {
            p: v
            for p, v in self.con.execute(
                "SELECT primitive, value FROM primitive_values WHERE lexeme_id=? AND value!=0", (r[0],)
            )
        }

    def category(self, word: str, depth: int = 0, seen: frozenset = frozenset()) -> Dict[str, int]:
        """Pure IS-A category — follow the genus chain ONLY (no differentia) to the
        grounded set / primes. This is the inheritance; differentia is added by the
        caller at the word's own level."""
        word = (word or "").lower().strip()
        if not word:
            return {}
        if word in self._cat_memo:
            return self._cat_memo[word]
        g = self.grounded(word)
        if g is not None:
            return g
        t = canonical_decomposition(word)
        if t:
            return t
        if depth >= MAX_DEPTH or word in seen:
            return {}
        pg = primary_gloss(word, "noun")  # genus head is a noun — POS from role, not a guess
        if not pg:
            return {}
        pos, gloss = pg
        op = decompose(word, pos, gloss)
        seen2 = seen | {word}
        if op.operation in _IDENTITY_OPS and op.operand:
            res = self.category(op.operand, depth + 1, seen2)
        elif op.genus:
            res = self.category(op.genus, depth + 1, seen2)  # follow the chain — no differentia
        else:
            res = {}
        if depth == 0:
            self._cat_memo[word] = res
        return res

    def evaluate(
        self, word: str, pos: Optional[str] = None, depth: int = 0, seen: frozenset = frozenset()
    ) -> Dict[str, int]:
        word = (word or "").lower().strip()
        if not word:
            return {}
        key = (word, pos)
        if key in self._memo:
            return self._memo[key]

        # 1. already grounded (Layer 0 prime / Layer 1 source-grounded)
        g = self.grounded(word)
        if g is not None:
            self._memo[key] = g
            return g
        # 2. prime exponent (tier-0 axiom)
        t = canonical_decomposition(word)
        if t:
            self._memo[key] = t
            return t
        # 3. bounded recursion
        if depth >= MAX_DEPTH or word in seen:
            return {}
        pg = primary_gloss(word, pos)  # POS from role when the caller knows it
        if not pg:
            return {}
        rpos, gloss = pg
        op = decompose(word, rpos, gloss)
        seen2 = seen | {word}

        if op.operation == "ZERO":
            result: Dict[str, int] = {}
        elif op.operation in _IDENTITY_OPS:
            result = dict(self.evaluate(op.operand, None, depth + 1, seen2)) if op.operand else {}
        elif op.operation == "NOT":
            result = _flip_eval(self.evaluate(op.operand, None, depth + 1, seen2)) if op.operand else {}
        else:  # genus-differentia / INHERIT / BIND / TYPE_ASSERT
            acc: Dict[str, int] = {}
            if op.genus:
                _merge(acc, self.category(op.genus, depth + 1, seen2))  # PURE category (genus chain only)
            for dh in op.differentia[:4]:
                _merge(acc, self.evaluate(dh, None, depth + 1, seen2))  # word's OWN differentia
            result = _resolve(acc)

        if depth == 0:  # only cache top-level results (recursion partials vary by path)
            self._memo[key] = result
        return result

    def close(self):
        self.con.close()


def _demo():
    lk = Linker()
    print("=== linkage stage: definition op → grounded decomposition ===\n")
    # (word, role-POS) — the POS the word is being asked about, as it would come
    # from the sentence parse. Never a global frequency guess.
    probes = [
        ("happy", "adj"),
        ("sad", "adj"),
        ("hate", "verb"),
        ("dislike", "verb"),
        ("unhappy", "adj"),
        ("love", "verb"),
        ("fear", "noun"),
        ("dog", "noun"),
        ("cat", "noun"),
        ("kill", "verb"),
        ("knife", "noun"),
        ("king", "noun"),
        ("murder", "noun"),
        ("men", "noun"),
        ("bigger", "adj"),
        ("teacher", "noun"),
    ]
    for w, p in probes:
        d = lk.evaluate(w, p)
        pos = sorted(k for k, v in d.items() if v > 0)
        neg = sorted(k for k, v in d.items() if v < 0)
        print(f"  {w:8s}[{p:4s}] +[{','.join(pos)}]  -[{','.join(neg)}]")
    lk.close()


if __name__ == "__main__":
    _demo()
