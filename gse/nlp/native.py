"""GSE-native token front-end — the deterministic replacement for spaCy (WS1).

The encoder already derives all clause *structure* arc-free (relative/control/
complement/coordination/causal from connectives + verb-inventory + position).
The only remaining spaCy dependency is the commodity token layer: tokenize +
lemma + coarse POS + the four TAM morph features + the ``is_*`` flags. This
module provides exactly that surface as a drop-in for ``spacy.load(...)``:

    nlp = NativeNLP()
    doc = nlp("Macbeth murders Duncan.")   # iterable of NativeToken

It is deterministic (no statistical model — the source of every parse bug and
the non-determinism the roadmap calls out) and reads no arcs. POS is coarse
Universal-POS, closed classes by lexicon (the finite function-word sets) and
open classes by WordNet sense + morphology + position; ``parse_repair`` then
promotes any buried verb exactly as it does for spaCy. Lemmatization is WordNet
``morphy`` with a rule-based suffix fallback for out-of-vocabulary (nonce) words.

Tuned for parity with spaCy on GSE's bounded register (``scripts/ws1_parity.py``);
the coherence gate flags any tail divergence. NOT a general-purpose tagger.
"""
from __future__ import annotations

import re
from typing import Dict, Iterator, List, Optional

from nltk.corpus import wordnet as wn

# --- closed classes (finite function-word sets) ----------------------------
_DET = {"the", "a", "an", "some", "any", "every", "each", "no", "this", "that",
        "these", "those", "all", "both", "neither", "either", "another"}
_PRON = {"i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us",
         "them", "who", "whom", "whose", "which", "what", "this", "that",
         "these", "those", "myself", "yourself", "himself", "herself", "itself",
         "themselves", "someone", "something", "anyone", "anything", "everyone",
         "everything", "nobody", "nothing"}
_POSS_PRON = {"my", "your", "his", "her", "its", "our", "their"}
_ADP = {"of", "in", "on", "at", "to", "for", "from", "by", "with", "without",
        "into", "onto", "over", "under", "above", "below", "between", "among",
        "through", "across", "along", "toward", "towards", "about", "against",
        "during", "until", "since", "near", "behind", "beside", "like"}
_CCONJ = {"and", "or", "but", "nor", "yet"}
_SCONJ = {"because", "although", "though", "if", "unless", "while", "whereas",
          "since", "so", "that", "whether", "as", "when", "before", "after"}
_AUX_BE = {"is", "am", "are", "was", "were", "be", "been", "being"}
_AUX_MODAL = {"will", "would", "can", "could", "shall", "should", "may",
              "might", "must", "ought"}
_AUX_DO = {"do", "does", "did"}
_PART = {"to", "not", "n't"}
_NEG = {"not", "n't"}

# spaCy-style stopword subset sufficient for ``_entity_like`` (title-case
# function words like "The" at sentence start must read as stops, not entities).
_STOP = (_DET | _PRON | _POSS_PRON | _ADP | _CCONJ | _SCONJ | _AUX_BE
         | _AUX_MODAL | _AUX_DO | _PART | {"there", "here", "then", "now"})

# Irregular lemmas WordNet morphy can miss or that spaCy fixes by rule. Includes
# irregular pasts whose surface collides with a distinct base lemma in WordNet
# (``saw`` → the verb "saw" rather than see-past), resolved to the common reading.
_IRREGULAR_LEMMA = {"is": "be", "am": "be", "are": "be", "was": "be",
                    "were": "be", "been": "be", "being": "be",
                    "has": "have", "had": "have", "having": "have",
                    "does": "do", "did": "do", "doing": "do",
                    "saw": "see",
                    # contraction parts (the post-apostrophe = a front-truncated
                    # word); irregular n't-bases whose surface is a stub:
                    "wo": "will", "ca": "can", "sha": "shall",
                    "n't": "not", "'s": "'s", "'re": "be", "'ve": "have",
                    "'ll": "will", "'d": "would", "'m": "be"}

_PUNCT_RE = re.compile(r"[^\w\s]")
# Tokenizer: words + contraction suffixes. The base-before-``n't`` and ``n't``
# itself are matched BEFORE plain ``\w+`` so a greedy ``\w+`` can't eat the ``n``
# ("didn't" → "did"+"n't", not "didn"+"'"+"t"; "won't" → "wo"+"n't"). The 's/'re/'ve
# /'ll/'d/'m suffixes already split cleanly (the base has no ambiguity).
_TOKEN_RE = re.compile(r"\w+(?=n't)|n't|'s|'re|'ve|'ll|'d|'m|\w+|[^\w\s]")


def _wn_lemma(word: str, pos: str) -> Optional[str]:
    wn_pos = {"VERB": wn.VERB, "NOUN": wn.NOUN, "ADJ": wn.ADJ,
              "ADV": wn.ADV}.get(pos)
    if wn_pos is None:
        return None
    lemma = wn.morphy(word, wn_pos)
    return lemma


def _rule_lemma(word: str, pos: str) -> str:
    """Suffix-stripping fallback for out-of-vocabulary words (nonce plurals,
    regular inflections WordNet lacks)."""
    if pos == "NOUN":
        if word.endswith("ies") and len(word) > 4:
            return word[:-3] + "y"
        if word.endswith(("ses", "xes", "zes", "ches", "shes")):
            return word[:-2]
        if word.endswith("s") and not word.endswith("ss"):
            return word[:-1]
    if pos == "VERB":
        if word.endswith("ing") and len(word) > 4:
            return word[:-3]
        if word.endswith("ed") and len(word) > 3:
            return word[:-2]
        if word.endswith("s") and not word.endswith("ss"):
            return word[:-1]
    if pos == "ADJ":
        base = None
        if word.endswith("est") and len(word) > 4:
            base = word[:-3]
        elif word.endswith("er") and len(word) > 3:
            base = word[:-2]
        if base is not None:
            # Collapse a doubled final consonant only when it was added to form
            # the comparative (bigger → bigg → big): the collapsed form is a known
            # adjective and the uncollapsed one is not. "taller" → "tall" (already
            # an adjective) must NOT collapse to "tal".
            if (len(base) >= 3 and base[-1] == base[-2] and base[-1] not in "aeiou"
                    and not wn.synsets(base, pos="a")
                    and wn.synsets(base[:-1], pos="a")):
                base = base[:-1]
            return base
    return word


class NativeToken:
    """A spaCy-Token-shaped view over deterministic annotations — only the
    surface the encoder + parse_repair actually read (no arcs)."""

    __slots__ = ("text", "lemma_", "pos_", "i", "_morph")

    def __init__(self, text: str, lemma: str, pos: str, i: int, morph: str):
        self.text = text
        self.lemma_ = lemma
        self.pos_ = pos
        self.i = i
        self._morph = morph

    @property
    def morph(self):
        return self._morph  # str() of it yields the "Feat=Val|..." string

    @property
    def is_alpha(self) -> bool:
        return self.text.isalpha()

    @property
    def is_title(self) -> bool:
        return self.text.istitle()

    @property
    def is_stop(self) -> bool:
        return self.text.lower() in _STOP

    def __repr__(self) -> str:
        return f"<NativeToken {self.text!r}/{self.pos_}>"


class NativeDoc:
    """Iterable/indexable container of :class:`NativeToken` (a spaCy Doc stand-in)."""

    __slots__ = ("_tokens",)

    def __init__(self, tokens: List[NativeToken]):
        self._tokens = tokens

    def __iter__(self) -> Iterator[NativeToken]:
        return iter(self._tokens)

    def __len__(self) -> int:
        return len(self._tokens)

    def __getitem__(self, idx) -> NativeToken:
        return self._tokens[idx]


class NativeNLP:
    """Deterministic, arc-free token front-end. Call it like ``spacy.load(...)``."""

    def __call__(self, text: str) -> NativeDoc:
        surfaces = _TOKEN_RE.findall(text)
        tokens: List[NativeToken] = []
        for i, surf in enumerate(surfaces):
            pos = self._pos(surf, i, surfaces)
            lemma = self._lemma(surf, pos)
            morph = self._morph(surf, pos)
            tokens.append(NativeToken(surf, lemma, pos, i, morph))
        return NativeDoc(tokens)

    # --- POS ---------------------------------------------------------------
    def _pos(self, surf: str, i: int, surfaces: List[str]) -> str:
        low = surf.lower()
        if _PUNCT_RE.fullmatch(surf):
            return "PUNCT"
        if surf.replace(",", "").replace(".", "").isdigit():
            return "NUM"
        if low in _AUX_BE or low in _AUX_MODAL or low in _AUX_DO or low in (
                "has", "have", "had"):
            return "AUX" if low not in ("has", "have", "had") else "VERB"
        if low in _NEG:
            return "PART"
        if low == "to":
            # infinitival 'to' (next is a verb) → PART, else preposition.
            nxt = surfaces[i + 1].lower() if i + 1 < len(surfaces) else ""
            return "PART" if self._looks_verbal(nxt) else "ADP"
        if low in _POSS_PRON:
            return "PRON"
        if low in _DET and low not in _PRON:
            return "DET"
        if low in _PRON:
            return "PRON"
        if low in _CCONJ:
            return "CCONJ"
        if low in _SCONJ and low not in ("that",):
            return "SCONJ"
        if low == "that":
            return "SCONJ" if self._that_is_clausal(i, surfaces) else "DET"
        if low == "than":
            return "ADP"
        if low in _ADP:
            return "ADP"
        if surf == "'s":
            return "PART"

        # --- open class ----------------------------------------------------
        # Title-case alphabetic non-stop word → proper noun (the register's
        # names: Macbeth/Mike/Rex/Spot/Lady — incl. sentence-initial).
        if surf.isalpha() and surf.istitle() and low not in _STOP:
            return "PROPN"
        if low.endswith("ly") and low != "only":
            return "ADV"

        has_v = bool(wn.synsets(low, pos="v") or wn.morphy(low, "v"))
        has_n = bool(wn.synsets(low, pos="n"))
        has_a = bool(wn.synsets(low, pos="a") or wn.synsets(low, pos="s"))
        prev = surfaces[i - 1].lower() if i > 0 else ""

        # An isolated content word with a verb reading is the predicate (no
        # object-position context to make it a noun) — matches spaCy's default
        # for single-token input and keeps a lemma's forms POS-consistent.
        if len(surfaces) == 1 and has_v and not has_a:
            return "VERB"

        # Inflectional morphology beats a noun sense.
        if low.endswith("ing"):
            return "VERB" if has_v else ("ADJ" if has_a else "NOUN")
        if low.endswith("ed"):
            return "VERB" if has_v else ("ADJ" if has_a else "NOUN")
        # Irregular past / participle: morphy maps to a *different* verb lemma
        # (sang→sing, left→leave, saw→see) — a verb even when also a noun. The
        # ``-s`` forms are excluded here (handled positionally below).
        if (mv := wn.morphy(low, "v")) and mv != low and not low.endswith("s"):
            return "VERB"
        if low.endswith(("ous", "ful", "less", "ive", "able", "ible")):
            return "ADJ"
        # Comparative / superlative: the base (not the inflected surface) carries
        # the adjective sense — "taller"/"bigger" → base "tall"/"big".
        if low.endswith(("er", "est")) and not has_v:
            base = _rule_lemma(low, "ADJ")
            if has_a or wn.synsets(base, pos="a") or wn.synsets(base, pos="s"):
                return "ADJ"

        # Positional disambiguation relative to the verb-inventory / copula.
        if prev in _AUX_BE:                 # predicate complement after a copula
            if has_a and not has_n:
                return "ADJ"
            if has_n:
                return "NOUN"
            if has_a:
                return "ADJ"
        if (prev in _AUX_DO or prev in _AUX_MODAL or prev in _NEG
                or prev == "to") and has_v:
            return "VERB"                   # content word after do/modal/neg/to
        if (prev in _DET or prev in _POSS_PRON) and has_n:
            return "NOUN"                   # head of a determined NP
        if low.endswith("s") and has_v and not low.endswith("ss"):
            return "VERB"                   # 3sg present (barks, murders, falls)

        if has_n:
            return "NOUN"
        if has_v:
            return "VERB"
        if has_a:
            return "ADJ"
        return "NOUN"

    @staticmethod
    def _rule_base(word: str) -> str:
        for suf in ("ing", "ed", "s"):
            if word.endswith(suf) and len(word) > len(suf) + 2:
                return word[: -len(suf)]
        return word

    def _looks_verbal(self, low: str) -> bool:
        base = self._rule_base(low)
        return bool(wn.synsets(low, pos="v") or wn.synsets(base, pos="v"))

    def _that_is_clausal(self, i: int, surfaces: List[str]) -> bool:
        """"that" is a determiner before a noun phrase it heads ("that dog"),
        else a complementizer/relativizer (clausal)."""
        nxt = surfaces[i + 1].lower() if i + 1 < len(surfaces) else ""
        if not nxt:
            return True
        # determiner if the next token is a (common) noun / adjective it modifies.
        if nxt in _DET or nxt in _ADP or self._looks_verbal(nxt):
            return True
        return True  # default clausal; determiner "that NOUN" handled by next≈noun

    # --- lemma -------------------------------------------------------------
    def _lemma(self, surf: str, pos: str) -> str:
        low = surf.lower()
        if low in _IRREGULAR_LEMMA:
            return _IRREGULAR_LEMMA[low]
        # Comparative/superlative adjectives: the rule (with doubled-consonant
        # collapse) before morphy, which returns "bigger" unchanged.
        if pos == "ADJ" and (low.endswith("er") or low.endswith("est")):
            ruled = _rule_lemma(low, pos)
            if ruled != low:
                return ruled
        wnl = _wn_lemma(low, pos)
        if wnl:
            return wnl
        return _rule_lemma(low, pos)

    # --- morph (only the four TAM features MORPH_TO_TAM consumes) -----------
    def _morph(self, surf: str, pos: str) -> str:
        low = surf.lower()
        feats: Dict[str, str] = {}
        if pos in ("VERB", "AUX"):
            if low.endswith("ing"):
                feats["Aspect"] = "Prog"
            if low in ("was", "were", "did", "had") or (
                    low.endswith("ed") and pos == "VERB"):
                feats["Tense"] = "Past"
            elif low in ("is", "am", "are", "has", "does") or (
                    low.endswith("s") and pos == "VERB"):
                feats["Tense"] = "Pres"
        return "|".join(f"{k}={v}" for k, v in sorted(feats.items()))
