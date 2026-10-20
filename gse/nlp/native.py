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

from gse.nlp.contractions import POSSESSIVE_PLURAL, resolve_apostrophe_s, resolve_contraction
from gse.nlp.morphology import resolve_degree

# --- closed classes (finite function-word sets) ----------------------------
_DET = {
    "the",
    "a",
    "an",
    "some",
    "any",
    "every",
    "each",
    "no",
    "this",
    "that",
    "these",
    "those",
    "all",
    "both",
    "neither",
    "either",
    "another",
}
_PRON = {
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
    "me",
    "him",
    "her",
    "us",
    "them",
    "who",
    "whom",
    "whose",
    "which",
    "what",
    "this",
    "that",
    "these",
    "those",
    "myself",
    "yourself",
    "himself",
    "herself",
    "itself",
    "themselves",
    "someone",
    "something",
    "anyone",
    "anything",
    "everyone",
    "everything",
    "nobody",
    "nothing",
}
_POSS_PRON = {"my", "your", "his", "her", "its", "our", "their"}
# Words that only ever open a noun phrase: the articles, and the possessives that are never an object pronoun. A
# V-ing/V-ed word right after one is nominal, never the clause predicate. "her" is left out ("saw her running"), as are
# the determiners that also stand alone as pronouns ("All agreed.", "Each divided in two").
_NP_OPENER = {"the", "a", "an", "every", "no", "another", "my", "your", "his", "its", "our", "their"}
# Nominative subject pronouns — a verb-capable word right after one is the clause predicate
# "by exclusion" (the subject slot is filled; the predicate is the only role left to assign).
_SUBJ_PRON = {"i", "you", "he", "she", "it", "we", "they", "who"}
_ADP = {
    "of",
    "in",
    "on",
    "at",
    "to",
    "for",
    "from",
    "by",
    "with",
    "without",
    "into",
    "onto",
    "over",
    "under",
    "above",
    "below",
    "between",
    "among",
    "through",
    "across",
    "along",
    "toward",
    "towards",
    "about",
    "against",
    "during",
    "until",
    "since",
    "near",
    "behind",
    "beside",
    "like",
    # Unambiguous prepositions that were MISSING — so the object/oblique split in
    # _try_event never fired on them and the PP accreted into the patient blob
    # ("scribble receipt upon sheet", "hurl it upon ground"). "upon" alone is the
    # single most common missing one in literary prose. Only UNAMBIGUOUS prepositions
    # are added (NOT up/down/out/off/round/past — those double as particles/adverbs/
    # nouns and forcing ADP would mis-tag phrasal verbs). Text-agnostic.
    "upon",
    "within",
    "beyond",
    "beneath",
    "underneath",
    "throughout",
    "amid",
    "amidst",
    "amongst",
    "betwixt",
    "unto",
    "atop",
    "despite",
}
_CCONJ = {"and", "or", "but", "nor", "yet"}
_SCONJ = {
    "because",
    "although",
    "though",
    "if",
    "unless",
    "while",
    "whereas",
    "since",
    "so",
    "that",
    "whether",
    "as",
    "when",
    "before",
    "after",
}
_AUX_BE = {"is", "am", "are", "was", "were", "be", "been", "being", "'m", "'re"}
_AUX_MODAL = {"will", "would", "can", "could", "shall", "should", "may", "might", "must", "ought", "'ll", "'d"}
_AUX_DO = {"do", "does", "did"}
_PART = {"to", "not", "n't"}
_NEG = {"not", "n't"}
# The stems the tokenizer splits off before n't whose surface is a stub ("can't" → ca + n't, "won't" → wo + n't,
# "shan't" → sha + n't): an auxiliary only when n't follows, so a standalone "ca" (circa) is left to the open class.
_NT_STEM = {"ca", "wo", "sha"}
# The contraction fragments whose lemma and tense come from their expansion (resolve_contraction): 's has its own
# three-way pass (_resolve_apostrophe_s) and n't is already "not".
_CONTRACTED_AUX = {"'m", "'re", "'ve", "'ll", "'d"}
# Closed-class adverbs / conjunctive adverbs / deictic adverbs with no entity reading
# in narrative. A WordNet noun sense (there/now → NOUN) or sentence-initial title-case
# (Instead/Sometimes → PROPN) was promoting these to eligible ENTITIES and then to AGENT
# ("instead —obey→ jim", "sometimes —say→ little", "there —take→ money"). They are pure
# function words: tag ADV unconditionally. Text-agnostic — universal English connectives,
# not a per-story patch. Conservative set: only words with no common noun/verb entity use
# (excludes back/still/once/just/even/around, which have strong nominal/adjectival senses).
_ADV_CLOSED = {
    "yes",
    "instead",
    "sometimes",
    "now",
    "then",
    "there",
    "here",
    "however",
    "therefore",
    "moreover",
    "meanwhile",
    "thus",
    "hence",
    "nevertheless",
    "nonetheless",
    "furthermore",
    "besides",
    "otherwise",
    "anyway",
    "anyhow",
    "perhaps",
    "maybe",
    "indeed",
    "thereby",
    "thereupon",
    "henceforth",
    "afterward",
    "afterwards",
    "meantime",
    "likewise",
    "accordingly",
    "consequently",
    "nowadays",
    "somewhere",
    "anywhere",
    "everywhere",
    "nowhere",
}

_ADV_DEGREE = {
    "very",
    "quite",
    "rather",
    "too",
    "always",
    "never",
    "often",
    "usually",
    "almost",
    "nearly",
    "somewhat",
    "also",
}
_COPULA_SKIP = _ADV_DEGREE | {"really", "sometimes"}
_CONTRACTED_IS_BASES = {
    "it",
    "he",
    "she",
    "that",
    "this",
    "there",
    "here",
    "what",
    "who",
    "where",
    "how",
}
_COPULA_PARTICIPLE_EXCLUSIONS = {"red", "indeed"}
_COPULA_PARTICIPLE_MODIFIERS = {"daily"}

# spaCy-style stopword subset sufficient for ``_entity_like`` (title-case
# function words like "The" at sentence start must read as stops, not entities).
_STOP = (
    _DET
    | _PRON
    | _POSS_PRON
    | _ADP
    | _CCONJ
    | _SCONJ
    | _AUX_BE
    | _AUX_MODAL
    | _AUX_DO
    | _PART
    | _ADV_CLOSED
    | {"there", "here", "then", "now"}
)

# Irregular lemmas WordNet morphy can miss or that spaCy fixes by rule. Includes
# irregular pasts whose surface collides with a distinct base lemma in WordNet
# (``saw`` → the verb "saw" rather than see-past), resolved to the common reading.
_IRREGULAR_LEMMA = {
    "is": "be",
    "am": "be",
    "are": "be",
    "was": "be",
    "were": "be",
    "been": "be",
    "being": "be",
    "has": "have",
    "had": "have",
    "having": "have",
    "does": "do",
    "did": "do",
    "doing": "do",
    "saw": "see",
    # contraction parts (the post-apostrophe = a front-truncated
    # word); irregular n't-bases whose surface is a stub:
    "wo": "will",
    "ca": "can",
    "sha": "shall",
    "n't": "not",
    "'s": "'s",
    "'re": "be",
    "'ve": "have",
    "'ll": "will",
    "'d": "would",
    "'m": "be",
}

# Morphy-opaque irregular pasts: forms whose OWN surface is also a verb/noun lemma
# ("fell"=cut-down AND past-of-fall; "rose"=a flower AND past-of-rise), so ``morphy``
# returns the surface unchanged and the irregular-past POS rule (which needs lemma ≠
# surface) misses them. A finite-verb position (not after a determiner/possessive)
# disambiguates. The enumerable irregular table the morphology design explicitly
# sanctions; extend as the register demands.
_IRREGULAR_PAST_VERB = {
    "fell": "fall",
    "rose": "rise",
    "bore": "bear",
    "ground": "grind",
    "wound": "wind",
}

_PUNCT_RE = re.compile(r"[^\w\s]")
# Tokenizer: words + contraction suffixes. The base-before-``n't`` and ``n't``
# itself are matched BEFORE plain ``\w+`` so a greedy ``\w+`` can't eat the ``n``
# ("didn't" → "did"+"n't", not "didn"+"'"+"t"; "won't" → "wo"+"n't"). "cannot" splits
# the same way, into "can"+"not". A 's/'re/'ve/'ll/'d/'m suffix is split off only when
# a word character comes right before its apostrophe; any other apostrophe is a quote
# ("'dividing'" keeps its word, where it once became "'d"+"ividing").
_TOKEN_RE = re.compile(r"\w+(?=(?i:n't))|(?i:n't)|(?i:can)(?=(?i:not)\b)|(?<=\w)'(?i:s|re|ve|ll|d|m)\b|\w+|[^\w\s]")


def copula_left_role(word, previous, has_a, is_be, is_neg) -> str:
    word = word.lower() if isinstance(word, str) else ""
    previous = previous.lower() if isinstance(previous, str) else ""
    if is_be:
        return "BE"
    if word == "'s" and previous in _CONTRACTED_IS_BASES:
        return "CONTRACTED_BE"
    if is_neg:
        return "SKIP"
    if word in _COPULA_SKIP:
        return "SKIP"
    if word.endswith("ly") and word != "only" and not has_a:
        return "SKIP"
    return "OTHER"


def copula_participle_kind(word, verb_lemma, has_v, closed_nonverb) -> str:
    word = word.lower() if isinstance(word, str) else ""
    verb_lemma = verb_lemma.lower() if isinstance(verb_lemma, str) else ""
    if (
        closed_nonverb
        or word in _COPULA_PARTICIPLE_EXCLUSIONS
        or not has_v
        or not verb_lemma
        or verb_lemma == word
        or word.endswith("s")
    ):
        return "NOT_PARTICIPLE"
    return "PARTICIPLE"


def copula_modifier_context(word, has_a, has_r, next_kind) -> str:
    word = word.lower() if isinstance(word, str) else ""
    if (
        isinstance(next_kind, str)
        and next_kind == "PARTICIPLE"
        and (word in _COPULA_PARTICIPLE_MODIFIERS or (has_r and not has_a))
    ):
        return "MODIFIER"
    return "NOT_MODIFIER"


def copula_complement_reading(
    left_roles,
    participle,
    modifier_context,
    has_a,
    has_n,
) -> str:
    if not isinstance(left_roles, list):
        return "NOT_COMPLEMENT"
    j = len(left_roles) - 1
    while j >= 0 and isinstance(left_roles[j], str) and left_roles[j] == "SKIP":
        j -= 1
    if j < 0:
        return "NOT_COMPLEMENT"
    role = left_roles[j]
    if not isinstance(role, str) or role not in ("BE", "CONTRACTED_BE"):
        return "NOT_COMPLEMENT"
    if modifier_context:
        return "MODIFIER"
    if participle:
        return "PARTICIPLE"
    if has_a:
        return "ADJ"
    if has_n:
        return "NOUN"
    return "NO_READING"


def copula_degree_reading(word, previous_nominal) -> str:
    word = word.lower() if isinstance(word, str) else ""
    if word in _ADV_DEGREE and not previous_nominal:
        return "DEGREE_ADV"
    return "DEFER"


def _wn_lemma(word: str, pos: str) -> Optional[str]:
    wn_pos = {"VERB": wn.VERB, "NOUN": wn.NOUN, "ADJ": wn.ADJ, "ADV": wn.ADV}.get(pos)
    if wn_pos is None:
        return None
    lemma = wn.morphy(word, wn_pos)
    return lemma


def _tokenize(text: str) -> list:
    """The surfaces of a text, in order: words, contraction parts and punctuation (``_TOKEN_RE``).

    Typographic apostrophes become ASCII first, so the contraction patterns match published prose ("doesn’t" → does +
    n't); without it the stray "t" leaked in as a content token and became a clause agent.
    """
    return _TOKEN_RE.findall(text.replace("’", "'").replace("‘", "'"))


def _skip_adverbs(pos_tags: list, texts: list, start: int) -> int:
    """The index of the first token at or after ``start`` that is neither an adverb nor a negation, or the end.

    It finds the word that decides what a contracted auxiliary stands for: "I'd already gone" → gone (had), "It's not
    raining" → raining (is), as the has/have rule already scans past adverbs and negation. ``pos_tags`` and ``texts``
    run in parallel; the scan stops at the end of the shorter one.
    """
    end = min(len(pos_tags), len(texts))
    i = max(start, 0)
    while i < end and (pos_tags[i] == "ADV" or texts[i].lower() in _NEG):
        i += 1
    return min(i, end)


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
            if (
                len(base) >= 3
                and base[-1] == base[-2]
                and base[-1] not in "aeiou"
                and not wn.synsets(base, pos="a")
                and wn.synsets(base[:-1], pos="a")
            ):
                base = base[:-1]
            # Gate: the strip may only FIRE if it yields a known adjective. Many words
            # merely END in -er/-est without being comparatives (together, whatsoever,
            # latter) — stripping would mint a non-word. If the base is not a known
            # adjective the word "shouldn't have" the suffix, so the rule must not fire:
            # leave the real surface word intact rather than mangling it. (Genuine
            # comparatives whose base needs orthographic repair — nicer→"nice",
            # earlier→"early" — are left as the real surface word and recovered
            # downstream by the failed-word resolver / general spell-check, never by an
            # inverse-spelling table here.)
            if wn.synsets(base, pos="a"):
                return base
    return word


def _inflected_pos(prev_kind: str, has_v: bool, has_n: bool, has_a: bool, next_is_noun: bool) -> str:
    """The part of speech of a V-ing or V-ed word, from the word before it and the senses it has.

    ``prev_kind`` is ``"np_opener"`` when the word before is an article or a plain possessive (``_NP_OPENER``),
    anything else otherwise. After an NP opener the word is nominal: a modifier when a noun head follows it ("the
    dividing cell" → ADJ), else the head of the noun phrase ("the meaning of the story" → NOUN), and an adjective when it
    has no noun sense ("the annotated." → ADJ). Elsewhere inflection beats a noun sense, as it always has ("he was
    dividing" → VERB). Returns ``"VERB"``, ``"NOUN"`` or ``"ADJ"``.
    """
    if prev_kind == "np_opener":
        if next_is_noun:
            return "ADJ"
        if has_n:
            return "NOUN"
        return "ADJ" if (has_a or has_v) else "NOUN"
    if has_v:
        return "VERB"
    return "ADJ" if has_a else "NOUN"


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
        surfaces = _tokenize(text)
        tokens: List[NativeToken] = []
        for i, surf in enumerate(surfaces):
            pos = self._pos(surf, i, surfaces)
            lemma = self._lemma(surf, pos)
            morph = self._morph(surf, pos)
            tokens.append(NativeToken(surf, lemma, pos, i, morph))
        self._resolve_contractions(tokens)
        self._resolve_apostrophe_s(tokens)
        return NativeDoc(tokens)

    def _resolve_contractions(self, tokens: List["NativeToken"]) -> None:
        """Give each contracted auxiliary ('m 're 've 'll 'd) the lemma and tense of the word it stands for, as
        :func:`gse.nlp.contractions.resolve_contraction` reads it from the token after it: "I'd gone" → had (have,
        Tense=Past), "I'd go" → would, "I'm" → am (be, Tense=Pres)."""
        pos_tags, texts = [t.pos_ for t in tokens], [t.text for t in tokens]
        for i, t in enumerate(tokens):
            if t.text.lower() not in _CONTRACTED_AUX:
                continue
            j = _skip_adverbs(pos_tags, texts, i + 1)  # "I'd already gone" is decided by gone
            reading = resolve_contraction(t.text, tokens[j] if j < len(tokens) else None)
            if reading:
                t.lemma_ = _IRREGULAR_LEMMA.get(reading, reading)
                t._morph = self._morph(reading, t.pos_)

    def _resolve_apostrophe_s(self, tokens: List["NativeToken"]) -> None:
        """Spell-check voice-mode: re-tag a VERBAL ``'s`` to its copula/perfect verb so
        the downstream copula TYPE_ASSERT synthesis fires (``fire's too big`` → fire IS
        too big). Possessive ``'s`` is left as the PART — its resolution already works,
        and re-tagging is conservative (only when nothing else could be the predicate).
        See :func:`gse.nlp.contractions.resolve_apostrophe_s`."""
        for i, t in enumerate(tokens):
            if t.text.lower() != "'s" or t.pos_ != "PART":
                continue
            # The very next token, not the verb past an adverb as for 'd: before a participle 's is "is" (passive,
            # "It's instead retained as a whole") or "has" (perfect), which the participle alone cannot decide (#76).
            following = tokens[i + 1] if i + 1 < len(tokens) else None
            # 's is possessive when the clause ALREADY has a predicate — a verb/copula
            # elsewhere in the SAME clause, BEFORE or after the 's. (Scanning only AFTER
            # missed the matrix verb in "Gnash destroyed Pip's house" / "...could not
            # destroy Hew's house", misread the genitive as the copula, and dropped the
            # verb.) Both directions, stopping at a clause boundary so a verb in a
            # NEIGHBOURING clause ("Because Mike ran, Pip's happy") can't suppress a real
            # copula.
            verb_or_copula_in_clause = self._clause_has_predicate(tokens, i)
            host = tokens[i - 1] if i > 0 else None
            reading = resolve_apostrophe_s(
                following,
                verb_or_copula_in_clause,
                host.text if host is not None else "",
                host is not None and host.pos_ == "PROPN",
            )
            if reading == "is":
                t.lemma_, t.pos_ = "be", "AUX"
            elif reading == "has":
                t.lemma_, t.pos_ = "have", "AUX"
            elif reading == "us":
                t.lemma_, t.pos_ = self._lemma("us", "PRON"), "PRON"
            elif reading == POSSESSIVE_PLURAL and following is not None:
                # "Duncan's guards": the plural the third-singular rule tagged VERB is the possessed noun.
                following.pos_ = "NOUN"
                following.lemma_ = self._lemma(following.text, "NOUN")
                following._morph = self._morph(following.text, "NOUN")
            if reading in ("is", "has"):
                t._morph = self._morph(reading, t.pos_)
            # POSSESSIVE → leave the PART unchanged (the possessive path handles it).

    # A clause boundary for the local 's scan: a connective or punctuation separates
    # the genitive's clause from a neighbour's predicate.
    _CLAUSE_BOUNDARY_POS = ("SCONJ", "CCONJ", "PUNCT")

    def _clause_has_predicate(self, tokens: List["NativeToken"], i: int) -> bool:
        """Is there a VERB/AUX in the same clause as ``tokens[i]`` (the ``'s``), excluding
        it — scanning both directions and stopping at a clause boundary?"""
        for rng in (range(i + 1, len(tokens)), range(i - 1, -1, -1)):
            for j in rng:
                if tokens[j].pos_ in self._CLAUSE_BOUNDARY_POS:
                    break
                if tokens[j].pos_ in ("VERB", "AUX"):
                    return True
        return False

    # --- POS ---------------------------------------------------------------
    def _pos(self, surf: str, i: int, surfaces: List[str]) -> str:
        low = surf.lower()
        previous = surfaces[i - 1] if i > 0 else ""
        prev = previous.lower() if isinstance(previous, str) else ""
        if _PUNCT_RE.fullmatch(surf):
            return "PUNCT"
        if surf.replace(",", "").replace(".", "").isdigit():
            return "NUM"
        if (
            low in _AUX_MODAL
            and i > 0
            and (surfaces[i - 1].lower() in _POSS_PRON or surfaces[i - 1].lower() in ("the", "a", "an"))
        ):
            # A modal homograph right after an article or possessive is the NOUN, not the modal:
            # "makes his will" / "opened the can". A SUBJECT pronoun ("he will go") is not in this
            # set, so the modal reading is preserved. Without this, "will" tagged AUX is dropped as a
            # function word and "his will" collapses to the bare possessor (make(alonso, alonso)).
            return "NOUN"
        if low in _AUX_BE or low in _AUX_MODAL or low in _AUX_DO:
            return "AUX"
        if low in _NT_STEM and i + 1 < len(surfaces) and surfaces[i + 1].lower() == "n't":
            return "AUX"
        if low in ("has", "have", "had", "'ve"):
            # Perfect auxiliary ("had murdered Duncan") vs main/possessive verb ("had a
            # crown"): a determiner/pronoun/preposition next → the main verb; a verb
            # (the participle) next → the perfect auxiliary. Scan past intervening
            # adverbs/negation ("had never murdered"). Without this, "had" was tagged
            # VERB and stole the predicate slot, dropping the real verb (have(x,y)).
            j = i + 1
            while j < len(surfaces) and (surfaces[j].lower().endswith("ly") or surfaces[j].lower() in _NEG):
                j += 1
            nxt = surfaces[j].lower() if j < len(surfaces) else ""
            if nxt in _DET or nxt in _PRON or nxt in _POSS_PRON or nxt in _ADP:
                return "VERB"
            return "AUX" if self._looks_verbal(nxt) else "VERB"
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
        if low in _PRON and low != "that":
            return "PRON"
        if low in _CCONJ:
            return "CCONJ"
        if low in _SCONJ and low not in ("that",):
            return "SCONJ"
        if low == "that":
            # 'that' is genuinely 3-way (DET/SCONJ/PRON); resolved by enumerate-and-score,
            # not the _PRON trap above (excluded) nor a next-token rule.
            return self._resolve_that(i, surfaces)
        if low == "than":
            return "ADP"
        if low in _ADP:
            return "ADP"
        if low == "'s":
            return "PART"
        # Closed-class adverb / connective / deictic adverb — no entity reading; tag ADV
        # before the open-class WordNet/title-case logic that was mis-promoting these to
        # NOUN/PROPN and then to AGENT. (See _ADV_CLOSED.)
        if copula_degree_reading(low, prev in _DET or prev in _POSS_PRON) == "DEGREE_ADV":
            return "ADV"
        if low in _ADV_CLOSED:
            return "ADV"

        # --- open class ----------------------------------------------------
        # Title-case alphabetic non-stop word → proper noun (the register's
        # names: Macbeth/Mike/Rex/Spot/Lady — incl. sentence-initial).
        if surf.isalpha() and surf.istitle() and low not in _STOP:
            at_head = i == 0 or previous in (".", "!", "?")
            nxt = surfaces[i + 1].lower() if i + 1 < len(surfaces) else ""
            # Capitalization at a sentence boundary is orthographic evidence.
            # A known verb followed by a nominal opener is an imperative;
            # an adverb before a boundary retains its discourse reading.
            if at_head and wn.synsets(low, pos="v") and nxt in (_DET | _POSS_PRON | _PRON):
                return "VERB"
            if at_head and wn.synsets(low, pos="r") and nxt in (",", ".", "!", "?"):
                return "ADV"
            return "PROPN"

        senses = [wn.synsets(low, pos=pos) for pos in ("v", "n", "a", "s", "r")]
        mv = wn.morphy(low, "v") or ""
        has_v = bool(senses[0] or mv)
        has_n = bool(senses[1])
        has_a = bool(senses[2] or senses[3])
        has_r = bool(senses[4])
        closed_nonverbs = _NEG | _ADV_CLOSED | _ADV_DEGREE | _DET | _PRON | _POSS_PRON | _ADP | _CCONJ | _SCONJ
        participle_kind = copula_participle_kind(
            low,
            mv,
            has_v,
            low in closed_nonverbs,
        )
        next_kind = "NOT_PARTICIPLE"
        if i + 1 < len(surfaces):
            nxt = surfaces[i + 1].lower()
            next_senses = [wn.synsets(nxt, pos=pos) for pos in ("v", "n", "a", "s", "r")]
            next_mv = wn.morphy(nxt, "v") or ""
            next_kind = copula_participle_kind(
                nxt,
                next_mv,
                bool(next_senses[0] or next_mv),
                nxt in closed_nonverbs,
            )
        modifier_context = copula_modifier_context(
            low,
            has_a,
            has_r,
            next_kind,
        )
        left_roles = []
        j = i - 1
        while j >= 0:
            left = surfaces[j].lower()
            left_previous = surfaces[j - 1].lower() if j > 0 else ""
            left_a = wn.synsets(left, pos="a")
            left_s = wn.synsets(left, pos="s")
            role = copula_left_role(
                left,
                left_previous,
                bool(left_a or left_s),
                left in _AUX_BE,
                left in _NEG,
            )
            left_roles.append(role)
            if role != "SKIP":
                break
            j -= 1
        left_roles.reverse()
        reading = copula_complement_reading(
            left_roles,
            participle_kind == "PARTICIPLE",
            modifier_context == "MODIFIER",
            has_a,
            has_n,
        )
        if reading == "ADJ":
            return "ADJ"
        if reading == "NOUN":
            return "NOUN"

        if low.endswith("ly") and low != "only":
            return "ADV"

        # A *demonstrative-or-relativizer* "that" before this word is NOT a determiner context:
        # "the king that FELL" / "the sword that Macbeth HELD" — the verb after a relativizer
        # "that" must stay a verb, not be nominalized like the head of "that DOG". (When "that"
        # really is a determiner, the following word is a noun, which `has_n` tags NOUN anyway.)
        prev_det = (prev in _DET or prev in _POSS_PRON) and prev != "that"

        # An isolated content word with a verb reading is the predicate (no
        # object-position context to make it a noun) — matches spaCy's default
        # for single-token input and keeps a lemma's forms POS-consistent.
        if len(surfaces) == 1 and has_v and not has_a:
            return "VERB"

        # Inflectional morphology beats a noun sense, except right after an article or a possessive, where the word
        # opens or modifies a noun phrase ("the meaning", "a dividing cell") rather than being the predicate.
        if low.endswith(("ing", "ed")):
            nxt = surfaces[i + 1].lower() if i + 1 < len(surfaces) else ""
            next_is_noun = bool(nxt) and nxt not in _STOP and bool(wn.synsets(nxt, pos="n"))
            prev_kind = "np_opener" if prev in _NP_OPENER else "other"
            return _inflected_pos(prev_kind, has_v, has_n, has_a, next_is_noun)
        # Irregular past / participle: morphy maps to a *different* verb lemma
        # (sang→sing, left→leave, saw→see) — a verb even when also a noun. But a
        # determiner/possessive in front forces the nominal reading when the word
        # has a noun sense (``the dove``=the bird, not past-of-dive; ``the saw``=the
        # tool): a finite-verb position settles it, exactly as for the morphy-opaque
        # table below. The ``-s`` forms are excluded here (handled positionally below).
        if mv and mv != low and not low.endswith("s") and not (has_n and prev_det):
            return "VERB"
        # Morphy-opaque irregular past (fell/rose/…): a finite-verb position settles it.
        if low in _IRREGULAR_PAST_VERB and not prev_det:
            return "VERB"
        if low.endswith(("ous", "ful", "less", "ive", "able", "ible")):
            return "ADJ"
        # Comparative / superlative (incl. suppletive better/best/worse): the
        # morphology operation is the single source of truth for "is this a degree
        # form?". A grounded degree form is an ADJ — except in clearly verbal position
        # (after a modal/do/neg/"to"), where a homographic verb wins ("will best
        # them"). Subsumes the old -er/-est heuristic and also catches the suppletives.
        if resolve_degree(low) is not None and not (
            prev in _AUX_MODAL or prev in _AUX_DO or prev in _NEG or prev == "to"
        ):
            return "ADJ"

        # Positional disambiguation relative to the verb-inventory.
        if (prev in _AUX_DO or prev in _AUX_MODAL or prev in _NEG or prev == "to") and has_v:
            return "VERB"  # content word after do/modal/neg/to
        # Predicate by exclusion: a verb-capable word right after a nominative SUBJECT pronoun
        # ("I know", "they think", "he wants") is the clause predicate — the subject slot is
        # filled and the predicate is the only role left to assign, so a stray noun sense
        # (know/think/want all have one) must not strand the clause verb-less.
        if prev in _SUBJ_PRON and has_v:
            return "VERB"
        # Pre-nominal adjective: a determiner-preceded word that is adjectival AND is
        # followed by a noun head is a modifier, not the NP head — "the old king" → old
        # is ADJ (king is the head), not the nominalized "the old". Without this, an adj
        # with a noun sense (old/young/rich/poor/great…) was tagged NOUN before the head,
        # garbling the NP ("old king" as one unit). Guards the DET→NOUN rule below.
        nxt = surfaces[i + 1].lower() if i + 1 < len(surfaces) else ""
        if prev_det and has_a and nxt and nxt not in _STOP and bool(wn.synsets(nxt, pos="n")):
            return "ADJ"
        if prev_det and has_n:
            return "NOUN"  # head of a determined NP
        if low.endswith("s") and has_v and not low.endswith("ss") and prev not in _ADP:
            return "VERB"  # 3sg present (barks, murders, falls); but the
            # object of a preposition is nominal ("of sticks")
        # Adverb in modifier position: a word with a WordNet adverb sense, not in a determined
        # nominal slot, not a preposition's object, and not clause-initial, modifies the
        # predicate — "loved him much", "go far", "ran away" — rather than being a second
        # object/the subject. Determined ("the well"), PP ("of much"), copula-complement, and
        # subject-initial nominal uses were all settled by the rules above, so reaching here
        # with an adverb sense means the modifier reading. Keeps degree/quantity adverbs out
        # of the object span (they were defaulting to NOUN via the has_n fallback below).
        if has_r and not prev_det and prev not in _ADP and i > 0:
            return "ADV"

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

    def _resolve_that(self, i: int, surfaces: List[str]) -> str:
        """Resolve the 3-way ambiguity of "that" by enumerate-and-score (not a next-token rule).

        The three readings each imply a different clause decomposition:
          * **DET** — determines the following nominal as an argument NP head ("that dog").
          * **SCONJ** — a complementizer opening a finite subordinate clause ("…knows that she
            left"): a main predicate before AND a subject+predicate after.
          * **PRON** — a relativizer ("the king *that* fell": noun before + verb right after) or a
            demonstrative subject ("*That* is mine": clause-initial + verb right after).

        Each reading is scored by how well-formed the decomposition it induces is — predicates
        homed in clauses with a present main clause, an orphaned verb penalised — with clause-token
        balance as the tie-break. Generalises the parse-repair enumerate→score→commit shape to a
        high-ambiguity function word. ("that DOG barks"=DET vs "knows that DOGS bark"=SCONJ turns
        on whether what follows is an NP or a subject+predicate, i.e. mini-parsing; no next-token
        rule can split them — the silent-PRON-trap residual this replaces.)
        """
        n = len(surfaces)

        def pos_of(j: int) -> str:
            if j < 0 or j >= n:
                return ""
            if surfaces[j].lower() == "that":
                return ""  # an adjacent 'that' is no evidence (avoid recursion)
            return self._pos(surfaces[j], j, surfaces)

        prev, nxt = pos_of(i - 1), pos_of(i + 1)
        # The GOVERNOR (the reliable preceding token) decides attachment — not the ambiguous
        # following predicate, which can't be tagged in isolation:
        #   noun/pronoun before → relativizer ("the king that fell") → PRON, the POS the
        #                         relative-clause builder keys on (expression._is_relativizer);
        #   verb before         → complementizer ("knows that she left") → SCONJ, a clean
        #                         nested complement clause;
        #   clause-initial/other:
        #       nominal after   → demonstrative determiner ("that dog") → DET (filtered; deixis
        #                         only, no propositional content);
        #       predicate after → demonstrative pronoun ("that is mine") → PRON (a referent).
        # Only the demonstrative PRON carries meaning; DET/SCONJ/relativizer are structural glue.
        if prev in ("NOUN", "PROPN", "PRON"):
            return "PRON"
        if prev == "VERB":
            return "SCONJ"
        if nxt in ("NOUN", "PROPN", "ADJ"):
            return "DET"
        if nxt in ("VERB", "AUX"):
            return "PRON"
        return "DET"

    # --- lemma -------------------------------------------------------------
    def _lemma(self, surf: str, pos: str) -> str:
        low = surf.lower()
        if pos == "PROPN":
            return low
        # _IRREGULAR_LEMMA holds POS-invariant maps (function words: be/have/do,
        # contraction parts) plus open-class verb-pasts whose surface collides with a
        # distinct noun ("saw"=past-of-see AND the cutting tool). For the latter, a
        # NOUN reading must NOT inherit the verbal lemma — defer to POS-aware morphy
        # below ("the saw" → "saw", not "see"), exactly as the _IRREGULAR_PAST_VERB
        # table is gated to verbal position. Function words never tag NOUN, so they
        # are unaffected.
        if low in _IRREGULAR_LEMMA and not (pos == "NOUN" and wn.synsets(low, pos="n")):
            return _IRREGULAR_LEMMA[low]
        if pos == "VERB" and low in _IRREGULAR_PAST_VERB:  # fell→fall only when verbal
            return _IRREGULAR_PAST_VERB[low]
        # Comparative/superlative: a word-scale morphological OPERATION — propose
        # candidate bases via the inverse orthographic formation, select the one that
        # grounds as a gradable adjective (gse/nlp/morphology.py; see
        # docs/MORPHOLOGY_RESEARCH_BRIEF.md). Replaces the old suffix-strip. The base
        # is the word-lens identity (the lemma); the degree is the sentence-lens half.
        if pos in ("ADJ", "ADV"):
            degree = resolve_degree(low)
            if degree is not None:
                return degree[0]
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
            if low in ("was", "were", "did", "had") or (low.endswith("ed") and pos == "VERB"):
                feats["Tense"] = "Past"
            elif low in ("is", "am", "are", "has", "does") or (low.endswith("s") and pos == "VERB"):
                feats["Tense"] = "Pres"
        return "|".join(f"{k}={v}" for k, v in sorted(feats.items()))
