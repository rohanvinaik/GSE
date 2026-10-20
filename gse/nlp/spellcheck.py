"""General deterministic spell-correction — the open-vocabulary instance of the
propose -> ground -> resolve shape that :mod:`gse.nlp.contractions` and
:mod:`gse.nlp.morphology` exercise on closed error models.

Domain theory: the **noisy-channel** model. A correction is

    argmax_w  P(w | x)  ∝  P(x | w) · P(w)

split into the two halves GSE already has tools for:

1. **error model  P(x|w)  — candidate generation.**  A typed surface ``x`` is a
   corruption of some real word ``w`` by a SMALL, closed set of slips: deletion,
   insertion, substitution, transposition (Damerau-Levenshtein edit-1; edit-2 as
   fallback). Substitutions/transpositions are cheaper between **keyboard-adjacent**
   keys (a realistic typo model), so the edit *cost* ranks candidates. This is the
   exact analogue of morphology's "four orthographic processes run backward": a
   closed deterministic generator, not a per-word lookup table.

2. **"language model"  P(w)  — a deterministic prior, NOT a learned/stochastic one.**
   Three deterministic signals, in precedence order:
     a. **grounding gate** — a candidate must be a real word: it must GROUND in the
        GSE lexicon (the 67K content lemmas), the closed-class function-word set
        (``gse.nlp.native._STOP``), or WordNet (coverage for lemmas the lexicon has
        not ingested, e.g. ``believe``). This is morphology's grounding oracle
        generalized from "is a gradable adjective" to "grounds at all".
     b. **frequency prior** — the operative tie-breaker. A *fixed, precompiled* rank
        (``lexemes.frequency_rank``, lower = more frequent), which is deterministic
        (same table every run) unlike a runtime corpus count. Closed-class function
        words are top-ranked (they are the most frequent words in English — a fact of
        the language, like the suppletive list); ranked content words follow; rare /
        unranked words sink to the bottom (this is what demotes spurious obscure
        edit-neighbours like ``harpy``/``boo``).
     c. **coherence hook (advisory, last-resort).** A primitive-set Jaccard against
        the clause context. Measured to be *too coarse to help* (NSM is definitional,
        not topical: it picked ``wired`` over ``weird``, ``harpy`` over ``happy``), so
        it sits BELOW the frequency prior in the sort key — inert unless edit cost AND
        frequency both tie. The real context signal for spell intent is structural
        (does the candidate make the clause cohere) or world-topical (sparse-wiki),
        deliberately NOT in the definitional lexicon — a documented future swap.

**Trigger.** Correction fires only when the surface itself does NOT ground (a
non-word). A word that grounds is correct and is never "corrected" — real-word
errors ("their"/"there") need full clause semantics and are out of scope here,
named honestly rather than guessed.

**Output contract.** :func:`correct` returns a ranked candidate set and commits to
the top candidate, which the (edit cost -> frequency prior) key makes a strict winner
in the normal case. It ABSTAINS (``committed=None``) only when nothing grounds, or in
the rare event the top two tie on every deterministic key. It never fabricates a word
that does not ground.
"""

from __future__ import annotations

import math
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

from gse.nlp.native import _STOP

# Absolute paths resolved from this module (repo root), so the corrector loads its
# data regardless of the process working directory — usable from any caller/repo.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_DB = os.path.join(_REPO_ROOT, "data", "lexicon_clean.db")

_ALPHABET = "abcdefghijklmnopqrstuvwxyz"

# QWERTY physical adjacency — the substitution/transposition error model. A slip to
# a neighbouring key is the common typo; the cost function makes those candidates
# cheaper than a substitution to a far key.
_KEYBOARD_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")


def _build_neighbors() -> Dict[str, FrozenSet[str]]:
    pos: Dict[str, Tuple[int, int]] = {}
    for r, row in enumerate(_KEYBOARD_ROWS):
        for c, ch in enumerate(row):
            pos[ch] = (r, c)
    neigh: Dict[str, Set[str]] = {ch: set() for ch in pos}
    for ch, (r, c) in pos.items():
        for ch2, (r2, c2) in pos.items():
            if ch2 != ch and abs(r - r2) <= 1 and abs(c - c2) <= 1:
                neigh[ch].add(ch2)
    return {ch: frozenset(s) for ch, s in neigh.items()}


_NEIGHBORS = _build_neighbors()

# Edit-operation costs. Keyboard-adjacent substitution is the cheapest real edit;
# a transposition (the classic "recieve") is cheap; other ops cost more. Integer
# costs keep ranking exact and deterministic.
_COST_TRANSPOSE = 1
_COST_SUB_ADJACENT = 1
_COST_SUB_FAR = 2
_COST_DELETE = 2  # surface has an extra char (delete it)
_COST_INSERT = 2  # surface is missing a char (insert one)


# --------------------------------------------------------------------------- #
# Error model: candidate generation                                           #
# --------------------------------------------------------------------------- #
def _edits1(word: str) -> Dict[str, int]:
    """Every Damerau-Levenshtein edit-1 of ``word`` -> its minimal edit cost.

    Deletes (drop an extra char), transposes (swap adjacent), substitutes (replace
    one char, keyboard-weighted), inserts (add a missing char).
    """
    out: Dict[str, int] = {}

    def offer(cand: str, cost: int) -> None:
        if cand and cand != word and cost < out.get(cand, 1 << 30):
            out[cand] = cost

    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    for left, right in splits:
        if right:  # delete
            offer(left + right[1:], _COST_DELETE)
        if len(right) > 1:  # transpose
            offer(left + right[1] + right[0] + right[2:], _COST_TRANSPOSE)
        if right:  # substitute
            for ch in _ALPHABET:
                if ch == right[0]:
                    continue
                adj = ch in _NEIGHBORS.get(right[0], ())
                offer(left + ch + right[1:], _COST_SUB_ADJACENT if adj else _COST_SUB_FAR)
        for ch in _ALPHABET:  # insert
            offer(left + ch + right, _COST_INSERT)
    return out


def _edits2(word: str) -> Dict[str, int]:
    """Edit-2 candidates -> cost (sum of the two edit costs). Used only as a
    fallback when no edit-1 candidate grounds."""
    out: Dict[str, int] = {}
    for c1, cost1 in _edits1(word).items():
        for c2, cost2 in _edits1(c1).items():
            total = cost1 + cost2
            if c2 != word and total < out.get(c2, 1 << 30):
                out[c2] = total
    return out


# --------------------------------------------------------------------------- #
# Grounding oracle + coherence signal (read from the lexicon)                 #
# --------------------------------------------------------------------------- #
# Frequency-prior tiers (lower sorts first = preferred). Function words are the most
# frequent words in English; ranked content words use their list rank; everything else
# that merely grounds (unranked lexicon words, WordNet-only lemmas) sinks below them.
_PRIOR_FUNCTION = -1
_PRIOR_UNRANKED = 1_000_000

# Rare-tail recovery: only correct *to* a word in the top-N Zipfian "common" set. Small
# by design — recovery is also slot-gated; this bounds the blast radius so jargon can
# never be a correction target.
_COMMON_TARGET_N = 1000

# Noisy-channel score = edit_cost + LAMBDA * freq_cost  (minimised). The true model is
# a PRODUCT P(x|w)*P(w), so a much-more-frequent word ONE edit farther can still win
# (which > wish, referred > revered). LAMBDA sets how much frequency overcomes an edit:
# a function word (freq_cost 0) beats a mid-frequency word (freq_cost ~3.5) that is one
# cheaper edit away iff LAMBDA > ~0.28. freq_cost is log10(rank): 0 for function words,
# ~0.6 (rank 4) .. 4.0 (rank 10000) for ranked words, and a fixed floor below the worst
# ranked word for grounded-but-unranked (rare) candidates.
_LAMBDA = 0.35
_FREQ_COST_UNRANKED = 4.5


def _freq_cost(prior: int) -> float:
    if prior == _PRIOR_FUNCTION:
        return 0.0
    if prior == _PRIOR_UNRANKED:
        return _FREQ_COST_UNRANKED
    return math.log10(prior)


def _score(edit_cost: int, prior: int, confusion_pos: int = -1) -> float:
    s = edit_cost + _LAMBDA * _freq_cost(prior)
    return s - _confusion_bonus(confusion_pos)


# Confusion-table (empirical P(x|w)) bonus. A candidate that is the OBSERVED correction
# for this exact surface (Wikipedia common-misspellings) is a strong, bounded prior —
# spelling errors are random human patterns, not rules, so applying the seen pattern
# makes the candidate set representative of real error distribution. The primary
# (first-listed) correction is favoured over secondary ones; a non-hit gets nothing.
# Bounded (not infinite) so the symbolic path still governs when the table is silent,
# and so the grounding gate can still veto a table entry that does not ground.
_MU = 3.0


def _confusion_bonus(confusion_pos: int) -> float:
    if confusion_pos < 0:
        return 0.0
    return _MU if confusion_pos == 0 else _MU * 0.6


def _damerau(a: str, b: str) -> int:
    """Damerau-Levenshtein distance — edit cost for an injected confusion candidate
    that may lie beyond the edit-1/2 generators (e.g. maintainance->maintenance)."""
    la, lb = len(a), len(b)
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[la][lb]


class _Lexicon:
    """Lazy, cached view of ``data/lexicon_clean.db`` (+ WordNet for coverage) for the
    grounding gate, the frequency prior, and the coherence Jaccard. Vocabulary =
    content lemmas ∪ closed-class function words ∪ WordNet lemmas."""

    def __init__(self, db_path: str = _DEFAULT_DB) -> None:
        self.db_path = db_path
        self._lex_vocab: Optional[FrozenSet[str]] = None
        self._wn_vocab: Optional[FrozenSet[str]] = None
        self._validity_vocab = None
        self._allowlist: Optional[FrozenSet[str]] = None
        self._usage: Optional[Dict[str, int]] = None
        self._usage_state: Optional[str] = None
        self._usage_reason: Optional[str] = None
        self._freq: Optional[Dict[str, int]] = None
        self._confusions: Optional[Dict[str, List[str]]] = None
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
        return self._conn

    @property
    def lex_vocab(self) -> FrozenSet[str]:
        if self._lex_vocab is None:
            rows = self.conn.execute("SELECT lemma FROM lexemes").fetchall()
            self._lex_vocab = frozenset(r[0].lower() for r in rows) | _STOP
        return self._lex_vocab

    @property
    def wn_vocab(self) -> FrozenSet[str]:
        if self._wn_vocab is None:
            from nltk.corpus import wordnet as wn

            self._wn_vocab = frozenset(n.lower() for n in wn.all_lemma_names() if n.isalpha())
        return self._wn_vocab

    @property
    def freq(self) -> Dict[str, int]:
        if self._freq is None:
            rows = self.conn.execute(
                "SELECT lemma, frequency_rank FROM lexemes WHERE frequency_rank IS NOT NULL"
            ).fetchall()
            self._freq = {r[0].lower(): int(r[1]) for r in rows}
        return self._freq

    @property
    def validity_vocab(self):
        """Broad word-VALIDITY membership (Wiktionary-derived; modern/technical/academic
        terms standard dictionaries lack). Backed by a compact EXACT marisa-trie
        (`wordlist_wiktionary.marisa`, ~24MB mmap) when present, else the raw `.txt` set,
        else empty. Loaded lazily — only consulted after the small lexicon/WordNet checks
        miss. Returns any object supporting ``in``."""
        if self._validity_vocab is None:
            trie = os.path.join(_REPO_ROOT, "data", "wordlist_wiktionary.marisa")
            txt = os.path.join(_REPO_ROOT, "data", "wordlist_wiktionary.txt")
            if os.path.exists(trie):
                import marisa_trie

                self._validity_vocab = marisa_trie.Trie().load(trie)  # exact, ~24MB, mmap
            elif os.path.exists(txt):
                with open(txt, encoding="utf-8") as f:
                    self._validity_vocab = frozenset(w for w in (line.strip() for line in f) if w)
            else:
                self._validity_vocab = frozenset()
        return self._validity_vocab

    @property
    def allowlist(self) -> FrozenSet[str]:
        """Committed project/tech allowlist (terms Wiktionary lacks); skips # comments."""
        if self._allowlist is None:
            path = os.path.join(os.path.dirname(__file__), "data", "project_allowlist.txt")
            try:
                with open(path, encoding="utf-8") as f:
                    self._allowlist = frozenset(
                        w for w in (line.strip().lower() for line in f) if w and not w.startswith("#")
                    )
            except FileNotFoundError:
                self._allowlist = frozenset()
        return self._allowlist

    def grounds(self, word: str) -> bool:
        from gse.curation.personal_dictionary import membership

        w = word.lower()
        # cheap in-memory sets first; the big validity filter is consulted last
        return (
            w in self.lex_vocab
            or w in self.wn_vocab
            or w in self.allowlist
            or membership(word)["state"] == "member"
            or w in self.validity_vocab
        )

    @property
    def usage(self) -> Dict[str, int]:
        """Observed combined usage ranks; an unread source is not observed absence."""
        if self._usage is None:
            m: Dict[str, int] = {}
            try:
                path = Path(_REPO_ROOT) / "data" / "frequency.db"
                with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
                    for word, rank in conn.execute("SELECT word, combined_rank FROM frequency"):
                        if not isinstance(word, str) or not word or type(rank) is not int or rank < 1:
                            raise ValueError("malformed_usage_rank")
                        m[word.lower()] = rank
                self._usage_state = "read"
            except (sqlite3.Error, ValueError) as exc:
                self._usage_state, self._usage_reason = "unread", str(exc)
                m = {}
            self._usage = m
        return self._usage

    def is_common_target(self, word: str) -> bool:
        """In the small Zipfian common set — the only words recovery may correct TO."""
        r = self.usage.get(word.lower())
        return r is not None and r <= _COMMON_TARGET_N

    def rarity_evidence(self, word: str) -> dict:
        """Separate broad-tail admission, observed use and unread frequency evidence.

        Absence from the observed combined-rank source licenses only a local slot
        check. It does not establish zero usage or prove the word is misspelled.
        """
        from gse.curation.personal_dictionary import membership

        w = word.lower()
        out = {"word": word, "state": "not_rare_tail", "policy": "gse.rare-tail/2"}
        protected = membership(word)
        if protected["state"] == "member":
            return {**out, "reason": "protected_dictionary"}
        if protected["state"] == "unread":
            return {**out, "state": "unread", "reason": "protected_dictionary_unread"}
        if w in self.lex_vocab or w in self.wn_vocab or w in self.allowlist or w in _STOP:
            return {**out, "reason": "core_or_protected_word"}
        if w not in self.validity_vocab:
            return {**out, "reason": "not_grounded_by_broad_tail"}
        usage = self.usage
        frequency = {"state": self._usage_state, "source": "frequency.db combined_rank"}
        if self._usage_state != "read":
            return {**out, "state": "unread", "reason": "usage_frequency_unread", "frequency": frequency}
        if w in usage:
            return {**out, "reason": "observed_usage", "frequency": {**frequency, "rank": usage[w]}}
        return {**out, "state": "rare_tail", "reason": "broad_tail_without_observed_rank", "frequency": frequency}

    def is_rare_tail(self, word: str) -> bool:
        """Legacy conservative projection: unread evidence never admits recovery."""
        return self.rarity_evidence(word)["state"] == "rare_tail"

    def prior(self, word: str) -> int:
        """Deterministic frequency prior (lower = preferred)."""
        w = word.lower()
        if w in _STOP:
            return _PRIOR_FUNCTION
        return self.freq.get(w, _PRIOR_UNRANKED)

    @property
    def confusions(self) -> Dict[str, List[str]]:
        """Common-misspelling confusion table: surface -> ordered intended words
        (Wikipedia CC-BY-SA). Empirical P(x|w); empty dict if the file is absent."""
        if self._confusions is None:
            import os

            path = os.path.join(os.path.dirname(__file__), "data", "misspellings_wikipedia.tsv")
            table: Dict[str, List[str]] = {}
            try:
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("#") or "\t" not in line:
                            continue
                        typo, corr = line.rstrip("\n").split("\t", 1)
                        table[typo] = corr.split("|")
            except FileNotFoundError:
                pass
            self._confusions = table
        return self._confusions

    def corrections(self, surface: str) -> List[str]:
        """Ordered observed corrections for ``surface`` (primary first), or []."""
        return self.confusions.get(surface.lower(), [])

    @lru_cache(maxsize=8192)
    def primitives(self, lemma: str) -> FrozenSet[str]:
        """The lemma's word-scale primitive set (for the coherence Jaccard). Empty
        for function words / words with no primitive rows."""
        rows = self.conn.execute(
            "SELECT pv.primitive FROM primitive_values pv JOIN lexemes lx ON lx.id = pv.lexeme_id WHERE lx.lemma = ?",
            (lemma.lower(),),
        ).fetchall()
        return frozenset(r[0] for r in rows)


_DEFAULT_LEXICON = _Lexicon()


def _jaccard(a: FrozenSet[str], b: FrozenSet[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# --------------------------------------------------------------------------- #
# Result type + public API                                                    #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Candidate:
    word: str
    edit_cost: int
    prior: int = _PRIOR_UNRANKED
    coherence: float = 0.0
    confusion_pos: int = -1  # position in the surface's confusion list; -1 = not a hit

    @property
    def score(self) -> float:
        """Noisy-channel score (lower = better): edit cost + weighted frequency cost,
        minus the empirical confusion-table bonus."""
        return _score(self.edit_cost, self.prior, self.confusion_pos)

    def __repr__(self) -> str:  # compact for demos
        p = "fn" if self.prior == _PRIOR_FUNCTION else ("-" if self.prior == _PRIOR_UNRANKED else self.prior)
        tag = " *seen" if self.confusion_pos >= 0 else ""
        return f"{self.word}(cost={self.edit_cost}, freq={p}, s={self.score:.2f}{tag})"


@dataclass(frozen=True)
class Correction:
    surface: str
    fired: bool  # did the trigger fire (surface is a non-word)?
    committed: Optional[str]  # the chosen correction, or None if it abstained
    ranked: Tuple[Candidate, ...] = field(default_factory=tuple)
    note: str = ""

    def __repr__(self) -> str:
        if not self.fired:
            return f"Correction({self.surface!r}: grounds, no correction)"
        head = self.committed if self.committed else "ABSTAIN"
        top = ", ".join(repr(c) for c in self.ranked[:5])
        return f"Correction({self.surface!r} -> {head} | [{top}])"


# ---- shape gate: surfaces that are not ordinary lowercase words -----------------
# The word path requires this margin to commit (no independent eager commit): it obeys
# the same discipline as the context path — structure governs, never a lone word guess.
WORD_COMMIT_MARGIN = 0.5


def looks_non_lexical(surface: str, sentence_initial: bool = False) -> bool:
    """True when SHAPE alone says this is not an ordinary misspelled English word — an
    acronym, a code identifier, or a (mid-sentence) proper noun. Such a surface is
    OFFERED as suggestions but NEVER auto-committed: the system must not 'correct' a
    token it has no business touching. (When the surface also grounds — e.g. once it is
    in the validity dictionaries — correction never triggers at all; this gate is the
    backstop for valid tokens absent from the dictionaries.)"""
    if not surface.isascii():
        return True  # preserve non-ASCII words, symbols and units
    if len(surface) >= 2 and surface.isupper():
        return True  # acronym: GSE, MCP, HDC
    if "'" in surface or "’" in surface:
        return True  # contraction / possessive: don't, Mike's
    if "-" in surface or "_" in surface:
        return True  # compound / identifier: set-theory, re_run
    if any(ch.isdigit() for ch in surface):
        return True  # identifier: v2, sha256, utf8
    if not (surface.islower() or surface.istitle() or surface.isupper()):
        return True  # internal caps: jsonParse
    if surface.istitle() and not sentence_initial:
        return True  # proper noun: Claude, Winston
    return False


def propose(surface: str, lexicon: _Lexicon = _DEFAULT_LEXICON) -> List[Candidate]:
    """The candidate set the symbolic system derives, then rates.

    Order matters and is deliberate: the symbolic error model runs FIRST (closed
    edit-1, then edit-2 generators), each candidate filtered by the grounding gate.
    The empirical confusion table is consulted AFTER, and only ever ADDS to this set —
    an observed correction that the edit generator missed (e.g. ``maintainance ->
    maintenance``, edit-4) is injected, **but it must still pass the same grounding
    gate** (the table proposes, the symbol disposes). It never pre-empts: there is no
    path where a table lookup returns an answer without the symbolic generation +
    grounding + scoring running. Its only effects are (a) widening the grounded
    candidate set and (b) a bonus term inside the score below."""
    word = surface.lower()
    cost = {c: ec for c, ec in _edits1(word).items() if lexicon.grounds(c)}
    if not cost:
        cost = {c: ec for c, ec in _edits2(word).items() if lexicon.grounds(c)}
    # empirical overlay: observed corrections, grounding-gated, injected INTO the set
    conf_pos: Dict[str, int] = {}
    for pos, c in enumerate(lexicon.corrections(word)):
        if lexicon.grounds(c):
            conf_pos[c] = pos
            cost.setdefault(c, _damerau(word, c))  # inject only if the gen missed it
    out = [Candidate(c, ec, lexicon.prior(c), confusion_pos=conf_pos.get(c, -1)) for c, ec in cost.items()]
    out.sort(key=lambda c: (c.score, c.word))
    return out


def suggest(surface: str, n: int = 5, lexicon: _Lexicon = _DEFAULT_LEXICON) -> List[Candidate]:
    """The top-``n`` ranked correction candidates for ``surface`` (phone-style "did
    you mean"). Empty if the surface already grounds or nothing grounds nearby."""
    if lexicon.grounds(surface.lower()):
        return []
    return propose(surface, lexicon)[:n]


def correct(
    surface: str,
    context: Optional[Sequence[str]] = None,
    lexicon: _Lexicon = _DEFAULT_LEXICON,
) -> Correction:
    """Correct one token under the noisy-channel model.

    * If ``surface`` grounds, it is correct -> ``fired=False``, no change.
    * Else propose grounded candidates (error model + grounding gate), rank by
      (edit cost, then coherence with ``context``), and COMMIT only when the choice
      is unambiguous; otherwise abstain and return the ranked set.
    """
    word = surface.lower()
    if lexicon.grounds(word):
        return Correction(surface, fired=False, committed=word, note="surface grounds")

    cands = propose(surface, lexicon)
    if not cands:
        return Correction(surface, fired=True, committed=None, note="no grounded candidate")

    # shape gate: acronym / code / proper-noun -> offer, never auto-commit
    if looks_non_lexical(surface):
        return Correction(
            surface,
            fired=True,
            committed=None,
            ranked=tuple(cands),
            note="non-lexical shape (acronym/code/proper-noun): offered, not committed",
        )

    # advisory coherence: context's pooled primitive set vs each candidate's. Sits
    # BELOW the frequency prior in the sort key (measured too coarse to lead).
    ctx_prims: FrozenSet[str] = frozenset()
    if context:
        pooled: Set[str] = set()
        for w in context:
            pooled |= lexicon.primitives(w)
        ctx_prims = frozenset(pooled)
    if ctx_prims:
        cands = [
            Candidate(c.word, c.edit_cost, c.prior, _jaccard(lexicon.primitives(c.word), ctx_prims)) for c in cands
        ]
    # noisy-channel score, then advisory coherence, then alpha
    cands.sort(key=lambda c: (c.score, -c.coherence, c.word))

    best = cands[0]
    second = cands[1] if len(cands) > 1 else None
    # commit only on a decisive margin (same discipline as the context path)
    unambiguous = second is None or (second.score - best.score) >= WORD_COMMIT_MARGIN
    committed = best.word if unambiguous else None
    note = "committed" if committed else "no decisive winner: abstained"
    return Correction(surface, fired=True, committed=committed, ranked=tuple(cands), note=note)
